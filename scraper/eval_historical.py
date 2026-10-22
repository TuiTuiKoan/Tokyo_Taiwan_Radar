"""
eval_historical.py — Historical backtest of stored annotations (#355).

Samples active parent events older than 30 days, stratified by source, re-runs
the annotator LLM on their raw text without writing anything, and compares the
new output with what is stored. Each compared field lands in one class:

    agree          same value under scoring v2 (eval_annotator.compare_fields)
    protected      differs, but field_corrections locks the field: the lock is
                   what keeps the stored value, so it is working
    silent_drift   differs, not locked, both sides filled: the stored value may
                   be stale or wrong, or the prompt has moved; human review queue
    regression     the new output is empty where the stored one is filled, or the
                   category collapses to the `senses` fallback: prompt regression

Only fields the LLM owns are compared: names, descriptions, category and
event_form. location_name and is_paid mostly come from scrapers and defaults,
and movie titles come from the works / eiga.com lookup (scoring v2 lookup
bucket), so re-running the LLM alone would flag them wrongly. For the same
reason event_form is skipped on pure publication records (the scraper sets
it), and the new category / event_form go through the annotator's own
validators first, as they do before production stores them.

Usage:
    python eval_historical.py --output ../docs/evaluation/historical/2026-11-monthly.md
    python eval_historical.py --sample 20 --output /tmp/h.md      # smaller, cheaper

Cost: one gpt-4o-mini call per event, about $0.0026 each with the current
system prompt (100 events ≈ $0.26), plus a negligible embedding call. The run
stops before calling OpenAI when the estimate exceeds --budget-usd.

Does NOT write to the database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from annotator import _validate_categories, _validate_event_forms  # noqa: E402
from eval_annotator import (  # noqa: E402
    BUCKET_LOOKUP,
    _estimate_cost,
    annotate_one_async,
    compare_fields,
    is_title_lookup_case,
    semantic_scores_for,
)

logger = logging.getLogger(__name__)

UTC = timezone.utc
JST = timezone(timedelta(hours=9))

COMPARED_FIELDS = ("name_zh", "name_en", "description_zh", "description_en", "category", "event_form")
MIN_AGE_DAYS = 30
DEFAULT_SAMPLE = 100
COST_PER_EVENT_USD = 0.0026
CATEGORY_FALLBACK = ["senses"]
EVENT_URL = "https://tokyotaiwanradar.com/ja/events/{}"


def is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    return True


# ─── Sampling ─────────────────────────────────────────────────────────────────

def stratified_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Sample ``n`` rows with each source's share proportional to its size.

    Largest-remainder allocation, so the total is exactly ``min(n, len(rows))``.
    The seed makes a month's sample reproducible while different months differ.
    """
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_source[r["source_name"]].append(r)
    total = len(rows)
    n = min(n, total)
    if n == 0:
        return []
    quotas = {s: n * len(rs) / total for s, rs in by_source.items()}
    alloc = {s: int(q) for s, q in quotas.items()}
    leftover = n - sum(alloc.values())
    for s in sorted(quotas, key=lambda s: (-(quotas[s] - alloc[s]), s))[:leftover]:
        alloc[s] += 1
    rng = random.Random(seed)
    sample = []
    for s in sorted(by_source):
        pool = sorted(by_source[s], key=lambda r: r["id"])
        sample += rng.sample(pool, alloc[s])
    return sample


# ─── Classification ───────────────────────────────────────────────────────────

def classify_field(entry: dict, locked: bool) -> str:
    """Class for one compare_fields entry (expected = stored, got = new output)."""
    if entry["match"]:
        return "agree"
    if locked:
        return "protected"
    stored, new = entry["expected"], entry["got"]
    if is_filled(stored) and not is_filled(new):
        return "regression"
    if entry["field"] == "category" and new == CATEGORY_FALLBACK and stored != CATEGORY_FALLBACK:
        return "regression"
    return "silent_drift"


def stored_as_expected(event: dict) -> dict:
    """Shape stored values like golden ``expected`` entries for compare_fields."""
    return {
        f: ({"value": event.get(f), "tier": 1, "from_fc": False} if is_filled(event.get(f)) else None)
        for f in COMPARED_FIELDS
    }


def normalize_annotation(annotation: dict) -> dict:
    """Apply the validators production runs before storing the LLM output."""
    out = dict(annotation)
    out["category"] = _validate_categories(annotation.get("category"))
    out["event_form"] = _validate_event_forms(annotation.get("event_form"))
    return out


def classify_event(event: dict, annotation: dict, locked_fields: set[str], semantic: dict) -> list[dict]:
    annotation = normalize_annotation(annotation)
    case = {"source_name": event.get("source_name"), "expected": stored_as_expected(event)}
    if event.get("event_form") == ["publication"]:
        case["expected"]["event_form"] = None  # scraper-owned on pure publications
    entries = compare_fields(
        case["expected"], annotation,
        title_lookup=is_title_lookup_case(case, annotation),
        semantic_scores=semantic,
    )
    out = []
    for e in entries:
        if e["bucket"] == BUCKET_LOOKUP:
            continue
        out.append({
            "event_id": event["id"],
            "source_name": event.get("source_name"),
            "field": e["field"],
            "class": classify_field(e, e["field"] in locked_fields),
            "stored": e["expected"],
            "new": e["got"],
            "method": e["method"],
            "score": e["score"],
        })
    return out


def summarize(results: list[dict]) -> dict:
    by_field: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_field[r["field"]][r["class"]] += 1
    totals = Counter(r["class"] for r in results)
    return {"totals": dict(totals), "by_field": {f: dict(c) for f, c in sorted(by_field.items())}}


# ─── Report ───────────────────────────────────────────────────────────────────

CLASSES = ("agree", "protected", "silent_drift", "regression")
CLASS_LABEL = {"agree": "一致", "protected": "保護命中", "silent_drift": "沉默漂移", "regression": "GPT 倒退"}


def _short(value, limit=60) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = text.replace("\n", " ").replace("|", "／")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def write_report(output: Path, *, now: datetime, n_events: int, n_eligible: int, seed: int,
                 results: list[dict], cost: float, skipped: list[str]) -> None:
    s = summarize(results)
    lines = [
        f"# 歷史事件回測 — {now.astimezone(JST):%Y-%m-%d}",
        "",
        f"- 樣本：{n_events} 筆（母體 {n_eligible} 筆：有效、母事件、建立超過 {MIN_AGE_DAYS} 天），依來源分層，seed {seed}",
        f"- 比較欄位：{', '.join(COMPARED_FIELDS)}；電影片名屬於查詢型評估，不比較",
        f"- 花費：${cost:.4f}（估計）",
        f"- 略過（raw 文字為空或 LLM 錯誤）：{len(skipped)}",
        "",
        "## 總覽",
        "",
        "| 欄位 | " + " | ".join(CLASS_LABEL[c] for c in CLASSES) + " |",
        "|---|" + "---|" * len(CLASSES),
    ]
    for field, counts in s["by_field"].items():
        lines.append(f"| {field} | " + " | ".join(str(counts.get(c, 0)) for c in CLASSES) + " |")
    lines.append("| **合計** | " + " | ".join(f"**{s['totals'].get(c, 0)}**" for c in CLASSES) + " |")
    lines += [
        "",
        "- **保護命中**：LLM 現在會給出不同答案，但 `field_corrections` 鎖住了既有值，保護機制正常。",
        "- **沉默漂移**：值不同、沒有鎖、兩邊都有值。可能是舊資料錯了，也可能是 prompt 改變了判斷；列入下方人工檢查清單。",
        "- **GPT 倒退**：新輸出變空，或 category 退回 `senses`。需要對照 annotator 的 git 歷史找原因。",
        "",
    ]

    for cls, title in (("regression", "GPT 倒退"), ("silent_drift", "沉默漂移：人工檢查清單")):
        rows = [r for r in results if r["class"] == cls]
        lines += [f"## {title}（{len(rows)}）", ""]
        if not rows:
            lines += ["_無_", ""]
            continue
        lines += ["| 事件 | source | 欄位 | 目前值 | 重跑結果 | 分數 |", "|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: (r["field"], r["source_name"] or "")):
            score = f"{r['score']:.2f}" if r["score"] is not None else "—"
            lines.append(
                f"| [{r['event_id'][:8]}]({EVENT_URL.format(r['event_id'])}) | {r['source_name']} | {r['field']} | "
                f"{_short(r['stored'])} | {_short(r['new'])} | {score} |"
            )
        lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


# ─── Data access (read-only) and run ─────────────────────────────────────────

_PAGE = 1000


def _fetch_all(make_query) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        batch = make_query().range(start, start + _PAGE - 1).execute().data or []
        rows += batch
        if len(batch) < _PAGE:
            return rows
        start += _PAGE


def fetch_population(sb, now: datetime) -> list[dict]:
    cutoff = (now - timedelta(days=MIN_AGE_DAYS)).isoformat()
    return _fetch_all(lambda: sb.table("events").select("id,source_name")
                      .eq("is_active", True).is_("parent_event_id", "null")
                      .lt("created_at", cutoff).not_.is_("raw_description", "null")
                      .order("id"))


def fetch_details(sb, ids: list[str]) -> tuple[list[dict], dict[str, set[str]]]:
    cols = "id,source_name,raw_title,raw_description," + ",".join(COMPARED_FIELDS)
    events, locks = [], defaultdict(set)
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        events += sb.table("events").select(cols).in_("id", batch).execute().data or []
        for fc in (sb.table("field_corrections").select("event_id,field_name")
                   .in_("event_id", batch).in_("field_name", list(COMPARED_FIELDS))
                   .execute().data or []):
            locks[fc["event_id"]].add(fc["field_name"])
    return events, locks


async def run(sb, events: list[dict], locks: dict[str, set[str]]):
    from openai import AsyncOpenAI

    from category_feedback import build_feedback_prompt, load_corrections
    from selection_reason_feedback import build_sr_feedback_prompt, load_sr_corrections

    # Same feedback prompts production uses today.
    feedback = build_feedback_prompt(load_corrections(sb))
    sr_feedback = build_sr_feedback_prompt(load_sr_corrections(sb))
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(5)

    async def _one(ev):
        async with sem:
            try:
                return await annotate_one_async(
                    client, ev.get("raw_title") or "", ev.get("raw_description") or "", feedback, sr_feedback,
                )
            except Exception as exc:  # one bad event must not sink the run
                logger.warning("annotate failed for %s: %s", ev["id"], exc)
                return None

    outputs = await asyncio.gather(*[_one(ev) for ev in events])
    done = [(ev, out) for ev, out in zip(events, outputs) if out is not None]
    skipped = [ev["id"] for ev, out in zip(events, outputs) if out is None]
    annotations = [ann for _, (ann, _usage) in done]
    pseudo = [{"expected": stored_as_expected(ev)} for ev, _ in done]
    semantic, _negative, emb_usage = await semantic_scores_for(client, pseudo, annotations)

    results = []
    for (ev, (ann, _usage)), sem_scores in zip(done, semantic):
        results += classify_event(ev, ann, locks.get(ev["id"], set()), sem_scores)
    cost = _estimate_cost([usage for _, (_ann, usage) in done], emb_usage)
    return results, cost, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="Historical backtest of stored annotations")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--json-output", type=Path, default=None)
    ap.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    ap.add_argument("--seed", type=int, default=None, help="Default: YYYYMM of today (JST)")
    ap.add_argument("--budget-usd", type=float, default=0.50)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from database import _get_client

    now = datetime.now(tz=UTC)
    seed = args.seed if args.seed is not None else int(now.astimezone(JST).strftime("%Y%m"))
    estimate = args.sample * COST_PER_EVENT_USD
    if estimate > args.budget_usd:
        print(f"Estimated ${estimate:.2f} exceeds budget ${args.budget_usd:.2f}; not running.", file=sys.stderr)
        return 1
    logger.info("Estimated cost: $%.2f for %d events", estimate, args.sample)

    sb = _get_client()
    population = fetch_population(sb, now)
    sample = stratified_sample(population, args.sample, seed)
    events, locks = fetch_details(sb, [r["id"] for r in sample])
    events = [e for e in events if (e.get("raw_description") or "").strip()]
    results, cost, skipped = asyncio.run(run(sb, events, locks))

    write_report(args.output, now=now, n_events=len(events), n_eligible=len(population), seed=seed,
                 results=results, cost=cost, skipped=skipped)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(
            {"generated_at": now.isoformat(), "seed": seed, "summary": summarize(results),
             "results": results, "cost_usd": round(cost, 6), "skipped": skipped},
            ensure_ascii=False, indent=2, default=str,
        ))
    logger.info("Report written: %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
