"""
eval_venues.py — Location pipeline eval, scored stage by stage (#325).

Stages:
    resolve   location_name → authoritative venue, through
              venue_registry.lookup_venue_for_location(). Runs against the frozen
              registry snapshot by default (no network, no secrets) or the live
              venues table with --live-registry.
    extract   raw text → location_name, through the annotator LLM. Cases freeze
              event_id + raw_md5 + the hand-labelled answer; the raw text is read
              from the DB at run time and a case whose text changed is reported as
              drifted and skipped.

    The geocode stage (address → lat/lng) is deferred: no authoritative venue has
    coordinates yet and geocode_events.py has never run in production.

Usage:
    python eval_venues.py --stage resolve --output report.md
    python eval_venues.py --stage resolve --enforce-baseline     # CI gate
    python eval_venues.py --stage all --output report.md --json-output snap.json
    python eval_venues.py --stage resolve --live-registry        # current DB registry

Does NOT write to the database.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import venue_registry  # noqa: E402
from eval_annotator import FUZZY_THRESHOLD, fuzzy_score, normalize_text  # noqa: E402

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

GOLDEN_DIR = Path(__file__).parent / "tests" / "golden"
CASES_PATH = GOLDEN_DIR / "venues.jsonl"
SNAPSHOT_PATH = GOLDEN_DIR / "venue_registry_snapshot.json"
MANIFEST_PATH = GOLDEN_DIR / "venues_manifest.json"

RESOLVE_KINDS = ("canonical", "alias", "sub_space", "variant", "negative")


# ─── Case loading ─────────────────────────────────────────────────────────────

def load_cases(path: Path = CASES_PATH, stage: str | None = None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [c for c in cases if stage is None or c["stage"] == stage]


# ─── Resolve stage ────────────────────────────────────────────────────────────

class _SnapshotQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def select(self, *_):
        return self

    def eq(self, field, value):
        if (field, value) != ("is_authoritative", True):
            raise ValueError(f"snapshot client only serves authoritative venues, got {field}={value}")
        return self

    def execute(self):
        return SimpleNamespace(data=[dict(r, is_authoritative=True) for r in self._rows])


class _SnapshotClient:
    """Stands in for the Supabase client inside venue_registry._build_cache()."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def table(self, name):
        if name != "venues":
            raise ValueError(f"snapshot client only serves the venues table, got {name}")
        return _SnapshotQuery(self._rows)


@contextmanager
def registry_from(rows: list[dict] | None):
    """Load venue_registry from ``rows``; ``None`` keeps the live DB client."""
    original = venue_registry._get_client
    venue_registry._reset_cache_for_tests()
    if rows is not None:
        venue_registry._get_client = lambda: _SnapshotClient(rows)
    try:
        yield
    finally:
        venue_registry._get_client = original
        venue_registry._reset_cache_for_tests()


def score_resolve(case: dict, venue: dict | None, preserve_label: bool) -> dict:
    """Score one resolve case.

    outcome: correct | missed (no venue, one expected) | wrong_venue (a different
    venue) | false_positive (a venue where none should resolve). A wrong venue is
    worse than none: it writes another venue's address onto the event.
    """
    got = venue.get("id") if venue else None
    expected = case.get("expected_venue_id")
    if got == expected:
        outcome = "correct"
    elif got is None:
        outcome = "missed"
    elif expected is None:
        outcome = "false_positive"
    else:
        outcome = "wrong_venue"

    label_ok = None
    if "expected_preserve_label" in case and outcome == "correct" and expected is not None:
        label_ok = preserve_label == case["expected_preserve_label"]

    return {
        "case_id": case["case_id"],
        "kind": case.get("kind"),
        "label": case["label"],
        "expected_venue": case.get("expected_venue"),
        "got_venue": (venue or {}).get("canonical_name_ja"),
        "outcome": outcome,
        "preserve_label": preserve_label if venue else None,
        "label_ok": label_ok,
    }


def run_resolve(cases: list[dict], rows: list[dict] | None) -> list[dict]:
    with registry_from(rows):
        return [
            score_resolve(c, *venue_registry.lookup_venue_for_location(c["label"]))
            for c in cases
        ]


def summarize_resolve(results: list[dict]) -> dict:
    def _count(rs, outcome):
        return sum(1 for r in rs if r["outcome"] == outcome)

    positives = [r for r in results if r["expected_venue"] is not None]
    by_kind = {}
    for kind in RESOLVE_KINDS:
        rs = [r for r in results if r["kind"] == kind]
        if rs:
            by_kind[kind] = {"tested": len(rs), "correct": _count(rs, "correct")}
    label_checked = [r for r in results if r["label_ok"] is not None]
    return {
        "tested": len(results),
        "correct": _count(results, "correct"),
        "missed": _count(results, "missed"),
        "wrong_venue": _count(results, "wrong_venue"),
        "false_positive": _count(results, "false_positive"),
        "recall": round(_count(positives, "correct") / len(positives), 4) if positives else None,
        "by_kind": by_kind,
        "label_checked": len(label_checked),
        "label_ok": sum(1 for r in label_checked if r["label_ok"]),
    }


# ─── Extract stage ────────────────────────────────────────────────────────────

def raw_md5(raw_title: str | None, raw_description: str | None) -> str:
    """Same recipe as the SQL used to freeze the cases: md5(title || '\\n' || description)."""
    return hashlib.md5(f"{raw_title or ''}\n{raw_description or ''}".encode("utf-8")).hexdigest()


def _clean(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def score_extract(case: dict, got, raw_text: str = "") -> dict:
    """Score one extract case.

    Expected null means the raw text names no venue, only an area or an address:
    only an empty answer passes. A filled answer that appears in the raw text is
    ``non_venue`` (an area or address copied into the venue field); one that does
    not is ``hallucinated``. Otherwise the best fuzzy score over the expected label
    and its accepted alternatives must reach FUZZY_THRESHOLD.
    """
    expected = case.get("expected_location_name")
    got = _clean(got)
    if expected is None:
        if got is None:
            outcome = "correct"
        elif normalize_text(got) in normalize_text(raw_text):
            outcome = "non_venue"
        else:
            outcome = "hallucinated"
        score = None
    else:
        candidates = [expected, *case.get("accepted", [])]
        score = max(fuzzy_score(c, got) for c in candidates)
        if got is None:
            outcome = "missed"
        else:
            outcome = "correct" if score >= FUZZY_THRESHOLD else "wrong"
    return {
        "case_id": case["case_id"],
        "source_name": case.get("source_name"),
        "event_id": case.get("event_id"),
        "expected": expected,
        "got": got,
        "score": None if score is None else round(score, 4),
        "outcome": outcome,
    }


def summarize_extract(results: list[dict], drifted: list[dict]) -> dict:
    scored = [r for r in results if r["outcome"] != "drifted"]
    null_cases = [r for r in scored if r["expected"] is None]
    named = [r for r in scored if r["expected"] is not None]
    return {
        "tested": len(scored),
        "correct": sum(1 for r in scored if r["outcome"] == "correct"),
        "named_tested": len(named),
        "named_correct": sum(1 for r in named if r["outcome"] == "correct"),
        "missed": sum(1 for r in named if r["outcome"] == "missed"),
        "wrong": sum(1 for r in named if r["outcome"] == "wrong"),
        "null_tested": len(null_cases),
        "non_venue": sum(1 for r in null_cases if r["outcome"] == "non_venue"),
        "hallucinated": sum(1 for r in null_cases if r["outcome"] == "hallucinated"),
        "drifted": [d["case_id"] for d in drifted],
    }


def _fetch_raw(sb, event_ids: list[str]) -> dict[str, dict]:
    rows = (
        sb.table("events")
        .select("id,raw_title,raw_description")
        .in_("id", event_ids)
        .execute()
        .data or []
    )
    return {r["id"]: r for r in rows}


async def run_extract(cases: list[dict]) -> tuple[list[dict], list[dict], list]:
    from openai import AsyncOpenAI
    from database import _get_client
    from eval_annotator import annotate_one_async

    raw_by_id = _fetch_raw(_get_client(), [c["event_id"] for c in cases])

    ready, drifted = [], []
    for c in cases:
        raw = raw_by_id.get(c["event_id"])
        if raw is None or raw_md5(raw.get("raw_title"), raw.get("raw_description")) != c["raw_md5"]:
            drifted.append(c)
        else:
            ready.append((c, raw))

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(5)

    async def _one(raw):
        async with sem:
            return await annotate_one_async(client, raw.get("raw_title") or "", raw.get("raw_description") or "")

    outputs = await asyncio.gather(*[_one(raw) for _, raw in ready])
    results = [
        score_extract(c, ann.get("location_name"), f"{raw.get('raw_title') or ''}\n{raw.get('raw_description') or ''}")
        for (c, raw), (ann, _usage) in zip(ready, outputs)
    ]
    results += [
        {"case_id": c["case_id"], "source_name": c.get("source_name"), "event_id": c.get("event_id"),
         "expected": c.get("expected_location_name"), "got": None, "score": None, "outcome": "drifted"}
        for c in drifted
    ]
    return results, drifted, [usage for _ann, usage in outputs]


# ─── Baseline gate ────────────────────────────────────────────────────────────

def check_baseline(resolve_summary: dict, manifest: dict) -> list[str]:
    """Return regressions against the recorded resolve baseline (empty = pass)."""
    base = manifest.get("resolve", {})
    problems = []
    if resolve_summary["correct"] < base.get("min_correct", 0):
        problems.append(
            f"resolve correct {resolve_summary['correct']} < baseline {base['min_correct']}"
        )
    wrong = resolve_summary["wrong_venue"] + resolve_summary["false_positive"]
    if wrong > base.get("max_wrong", 0):
        problems.append(f"resolve wrong venues {wrong} > baseline {base.get('max_wrong', 0)}")
    return problems


# ─── Report ───────────────────────────────────────────────────────────────────

def _pct(n: int, d: int) -> str:
    return f"{n / d:.1%}" if d else "n/a"


def write_report(
    output: Path,
    *,
    registry_label: str,
    resolve: tuple[list[dict], dict] | None,
    extract: tuple[list[dict], dict] | None,
    cost: float | None,
    runtime_s: float,
) -> None:
    now = datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M JST")
    lines = [
        f"# Venue Pipeline Eval — {now}",
        "",
        f"- registry: {registry_label}",
        f"- runtime: {runtime_s:.1f}s" + (f"；cost: ${cost:.4f} (est.)" if cost is not None else ""),
        "",
    ]

    if resolve is not None:
        results, s = resolve
        recall = f"{s['recall']:.1%}" if s["recall"] is not None else "n/a"
        lines += [
            "## 解析（location_name → 權威場館）",
            f"- 正確 {s['correct']}／{s['tested']}（{_pct(s['correct'], s['tested'])}）；應命中的 case 召回率 {recall}",
            f"- 漏判 {s['missed']}；錯配到其他場館 {s['wrong_venue']}；不該命中卻命中 {s['false_positive']}",
            f"- 保留子空間標籤：{s['label_ok']}／{s['label_checked']} 正確",
            "",
            "| 類型 | Tested | Correct | Accuracy |",
            "|---|---|---|---|",
        ]
        for kind, k in s["by_kind"].items():
            lines.append(f"| {kind} | {k['tested']} | {k['correct']} | {_pct(k['correct'], k['tested'])} |")
        lines.append("")
        misses = [r for r in results if r["outcome"] != "correct" or r["label_ok"] is False]
        if misses:
            lines += ["### 未通過", "", "| case | 類型 | label | 期望 | 實際 | 結果 |", "|---|---|---|---|---|---|"]
            for r in misses:
                outcome = r["outcome"] if r["outcome"] != "correct" else "label 未保留"
                lines.append(
                    f"| {r['case_id']} | {r['kind']} | {r['label']} | {r['expected_venue'] or '（無）'} | "
                    f"{r['got_venue'] or '（無）'} | {outcome} |"
                )
            lines.append("")

    if extract is not None:
        results, s = extract
        lines += [
            "## 抽取（raw 文字 → location_name）",
            f"- 正確 {s['correct']}／{s['tested']}（{_pct(s['correct'], s['tested'])}）",
            f"- 文中有場館：{s['named_correct']}／{s['named_tested']} 正確，漏抽 {s['missed']}，抽錯 {s['wrong']}",
            f"- 文中沒有場館：{s['null_tested']} 筆中 {s.get('non_venue', 0)} 筆把區域或地址填進場館欄，"
            f"{s['hallucinated']} 筆填入原文沒有的地點",
            f"- raw 已變動而跳過：{', '.join(s['drifted']) or '無'}",
            "",
        ]
        misses = [r for r in results if r["outcome"] not in ("correct", "drifted")]
        if misses:
            lines += ["### 未通過", "", "| case | source | 期望 | 實際 | score | 結果 |", "|---|---|---|---|---|---|"]
            for r in misses:
                score = f"{r['score']:.2f}" if r["score"] is not None else "—"
                lines.append(
                    f"| {r['case_id']} | {r['source_name']} | {r['expected'] or '（無）'} | "
                    f"{r['got'] or '（無）'} | {score} | {r['outcome']} |"
                )
            lines.append("")

    lines += [
        "## 定位（address → lat/lng）",
        "延後：權威場館目前沒有任何座標，`geocode_events.py` 也沒有正式執行紀錄。",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Venue pipeline eval (resolve / extract)")
    ap.add_argument("--stage", choices=["resolve", "extract", "all"], default="resolve")
    ap.add_argument("--live-registry", action="store_true", help="Resolve against the live venues table")
    ap.add_argument("--output", type=Path, default=Path("venues_report.md"))
    ap.add_argument("--json-output", type=Path, default=None)
    ap.add_argument("--enforce-baseline", action="store_true",
                    help="Exit 1 when the resolve stage regresses against venues_manifest.json")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    start = time.monotonic()
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    rows = None if args.live_registry else snapshot["venues"]
    registry_label = "live venues table" if args.live_registry else (
        f"snapshot {snapshot['snapshot_at']} ({len(snapshot['venues'])} venues, md5 {snapshot['md5'][:8]})"
    )

    resolve = extract = None
    cost = None
    snap: dict = {"ran_at": datetime.now(tz=JST).isoformat(), "registry": registry_label}

    if args.stage in ("resolve", "all"):
        results = run_resolve(load_cases(stage="resolve"), rows)
        resolve = (results, summarize_resolve(results))
        snap["resolve"] = {"summary": resolve[1], "entries": results}

    if args.stage in ("extract", "all"):
        from eval_annotator import _estimate_cost

        results, drifted, usages = asyncio.run(run_extract(load_cases(stage="extract")))
        extract = (results, summarize_extract(results, drifted))
        cost = _estimate_cost(usages)
        snap["extract"] = {"summary": extract[1], "entries": results, "cost_usd": round(cost, 6)}

    runtime_s = time.monotonic() - start
    write_report(args.output, registry_label=registry_label, resolve=resolve, extract=extract,
                 cost=cost, runtime_s=runtime_s)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(snap, ensure_ascii=False, indent=2))

    if args.enforce_baseline and resolve is not None:
        problems = check_baseline(resolve[1], json.loads(MANIFEST_PATH.read_text()))
        if problems:
            for p in problems:
                print(f"BASELINE REGRESSION: {p}", file=sys.stderr)
            return 1
        print("Resolve baseline held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
