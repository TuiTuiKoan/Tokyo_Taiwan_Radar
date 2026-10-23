"""
eval_annotator.py — Annotator golden set regression runner.

Runs the AI annotator against frozen golden cases and produces a per-field
accuracy report. Uses frozen mode by default (reproducible, no DB needed)
or live mode for ad-hoc comparison.

Usage:
    python eval_annotator.py --output report.md            # frozen (CI default)
    python eval_annotator.py --live --output report.md     # live DB corrections
    python eval_annotator.py --sample 5 --output /tmp/t.md # debug with 5 cases
    python eval_annotator.py --case a1b2c3d4 --output /tmp/t.md  # single case

Notes:
    - If cases.jsonl is empty, prints WARNING and exits 0 (CI-safe).
    - Async with asyncio.Semaphore(5) for rate limiting.
    - Does NOT write to the database.

Scoring (scoring_version 2, #324):
    - Names and location_name: normalized string, then fuzzy ratio >= FUZZY_THRESHOLD.
    - Descriptions: embedding cosine >= SEMANTIC_THRESHOLD (0.70). Exact match scored every
      free-text field 0% even when the translation was fine.
    - Movie titles (name_zh / name_en on movie cases) go to the "lookup" bucket and are
      not part of the annotator score: the expected value is the official Taiwanese title,
      which the works table / eiga.com lookup resolves, not the LLM. Stage 2 measures it.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from llm_client import AsyncLLMClient, finish, get_async_client, get_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Import SYSTEM_PROMPT from annotator (same directory).
# _annotate_one is sync; we implement annotate_one_async below using the shared async client.
from annotator import (
    SYSTEM_PROMPT,
    _NEWS_MOVIE_SOURCES,
    _film_person_enrich_reasons,
    _fix_descriptions_with_people,
    _get_supabase,
    _pick_person_lookup_title,
    _resolve_event_people,
    _replace_title_in_desc,
    _resolve_movie_titles_for_event,
    _validate_categories,
    _validate_event_forms,
    build_event_user_content,
)
from category_feedback import load_corrections, build_feedback_prompt
from selection_reason_feedback import load_sr_corrections, build_sr_feedback_prompt
from sources._cinema_constants import FIXED_CINEMA_SOURCES

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

GOLDEN_DIR = Path(__file__).parent / "tests" / "golden"
CASES_PATH = GOLDEN_DIR / "cases.jsonl"
FROZEN_PATH = GOLDEN_DIR / "frozen_corrections.json"

# Fields evaluated — must stay in sync with build_golden_dataset.py MEASURED_FIELDS
MEASURED_FIELDS = frozenset({
    "name_zh", "name_en", "description_zh", "description_en",
    "category", "event_form", "primary_language",
    "is_paid", "has_japanese_support", "has_english_support",
    "location_name",
})

LIST_FIELDS = frozenset({"category", "event_form"})
BOOL_FIELDS = frozenset({"is_paid", "has_japanese_support", "has_english_support"})
FUZZY_FIELDS = frozenset({"name_zh", "name_en", "location_name"})
SEMANTIC_FIELDS = frozenset({"description_zh", "description_en"})
TITLE_LOOKUP_FIELDS = frozenset({"name_zh", "name_en"})

FUZZY_THRESHOLD = 0.85
# Calibrated on the 2026-10-22 baseline (PR #365): description_zh negative-control
# cosines topped out at 0.48 and description_en at 0.57 apart from one same-film
# pair (0.78); accepted translations scored from 0.73 up. See
# docs/evaluation/annotator/2026-10-22-scoring-v2-baseline.md.
SEMANTIC_THRESHOLD = 0.70
EMBEDDING_MODEL = "text-embedding-3-small"
SCORING_VERSION = 2

BUCKET_ANNOTATOR = "annotator"
BUCKET_LOOKUP = "lookup"

_STAGE_LABELS = {
    1: "LLM only",
    2: "LLM + enrich_movie_titles pipeline",
    3: "LLM + enrich_movie_titles + enrich_person_names pipeline",
}

def sync_title_in_descriptions(
    ann: dict,
    *,
    old_name_zh: str | None,
    old_name_en: str | None,
    new_name_zh: str | None,
    new_name_en: str | None,
    lookup_title: str = "",
    is_news_source: bool = False,
) -> None:
    """Rewrite bracketed old movie titles in ann's descriptions in place.

    Mirrors the description step of annotator.enrich_movie_titles(): after
    name_zh/name_en are resolved, descriptions that still quote the LLM's old
    title (e.g. 《霧的故事》) are updated to the resolved one (《大濛》).
    """
    desc_zh = ann.get("description_zh") or ""
    if new_name_zh and desc_zh:
        old_refs = [old_name_zh or ""]
        if is_news_source:
            old_refs.append(lookup_title)
        ann["description_zh"] = _replace_title_in_desc(desc_zh, old_refs, new_name_zh)

    desc_en = ann.get("description_en") or ""
    if new_name_en and desc_en:
        ann["description_en"] = _replace_title_in_desc(
            desc_en, [old_name_en or ""], new_name_en,
        )


# ─── Async annotator ─────────────────────────────────────────────────────────

async def annotate_one_async(
    client: AsyncLLMClient,
    raw_title: str,
    raw_description: str,
    feedback_prompt: str = "",
    sr_feedback_prompt: str = "",
    record_type: str | None = None,
) -> tuple[dict, object]:
    """Async version of annotator._annotate_one using the shared async client.

    Returns (annotation_dict, usage) matching _annotate_one's return signature.
    """
    system_content = SYSTEM_PROMPT + feedback_prompt + sr_feedback_prompt
    user_content = build_event_user_content(raw_title, raw_description, record_type)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )
    usage = response.usage
    text = response.choices[0].message.content
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        # Retry once with higher token budget
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=6000,
        )
        usage = response.usage
        return json.loads(response.choices[0].message.content), usage


# ─── Case loading ─────────────────────────────────────────────────────────────

def load_cases(cases_path: Path, limit: int | None = None, case_id: str | None = None) -> list[dict]:
    """Load cases from JSONL file. Returns list of case dicts."""
    if not cases_path.exists():
        return []
    lines = [l for l in cases_path.read_text().splitlines() if l.strip()]
    if not lines:
        return []
    cases = [json.loads(l) for l in lines]
    if case_id:
        cases = [c for c in cases if c.get("case_id") == case_id]
    if limit:
        cases = cases[:limit]
    return cases


# ─── Field comparison ─────────────────────────────────────────────────────────

# Quotes, brackets, separators and whitespace that differ between equally
# correct answers (「」 vs 『』, full- vs half-width, "ADRIFT" vs ADRIFT).
_IGNORABLE_RE = re.compile(
    r"[\s\"'`“”‘’「」『』《》〈〉【】〔〕()（）\[\]{}<>・·•、，,。.!！?？:：;；/／|｜\-‐‑–—―~〜～_]+"
)


def normalize_text(value) -> str:
    """NFKC, case-fold, and drop punctuation/whitespace."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return _IGNORABLE_RE.sub("", text)


def fuzzy_score(expected, got) -> float:
    """Similarity in [0, 1] between two short strings after normalization."""
    if got is None:
        return 0.0
    a, b = normalize_text(expected), normalize_text(got)
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def normalize_annotation(annotation: dict) -> dict:
    """Apply the validators production runs before storing the LLM output.

    annotator maps e.g. ``performance`` to ``performing_arts`` and drops values
    that are not categories or event forms. Scoring the raw LLM output counted
    those as misses (#383).
    """
    out = dict(annotation)
    out["category"] = _validate_categories(annotation.get("category"))
    out["event_form"] = _validate_event_forms(annotation.get("event_form"))
    return out


def is_title_lookup_case(case: dict, annotation: dict) -> bool:
    """True when name_zh / name_en should be scored as a title lookup.

    A case is a movie when either side says so: the expected or produced category
    contains ``movie``, or the source is a fixed cinema.
    """
    exp_cat = ((case.get("expected") or {}).get("category") or {}).get("value")
    got_cat = annotation.get("category")
    cats = set(exp_cat if isinstance(exp_cat, list) else []) | set(got_cat if isinstance(got_cat, list) else [])
    return "movie" in cats or case.get("source_name") in FIXED_CINEMA_SOURCES


def compare_fields(
    expected_dict: dict,
    annotation: dict,
    *,
    title_lookup: bool = False,
    semantic_scores: dict[str, float] | None = None,
) -> list[dict]:
    """Compare expected fields against annotation output.

    Returns list of dicts with keys: field, tier, from_fc, expected, got, match,
    method, score, bucket. Skips fields where expected value is None.
    ``semantic_scores`` maps a SEMANTIC_FIELDS name to its precomputed cosine;
    a field without one falls back to fuzzy scoring.
    """
    semantic_scores = semantic_scores or {}
    results = []
    for field, exp_entry in expected_dict.items():
        if exp_entry is None:
            continue
        expected_val = exp_entry.get("value")
        tier = exp_entry.get("tier", 1)
        from_fc = exp_entry.get("from_fc", False)

        got_val = annotation.get(field)
        score = None

        if field in LIST_FIELDS:
            method = "set"
            exp_set = set(expected_val) if isinstance(expected_val, list) else set()
            got_set = set(got_val) if isinstance(got_val, list) else set()
            match = exp_set == got_set
        elif isinstance(expected_val, bool) or field in BOOL_FIELDS:
            method = "exact"
            match = expected_val == got_val
        elif expected_val is None:
            method = "exact"
            match = got_val is None
        elif field in SEMANTIC_FIELDS and field in semantic_scores:
            method = "semantic"
            score = semantic_scores[field]
            match = score >= SEMANTIC_THRESHOLD
        elif field in FUZZY_FIELDS or field in SEMANTIC_FIELDS:
            method = "fuzzy"
            score = fuzzy_score(expected_val, got_val)
            match = score >= FUZZY_THRESHOLD
        else:
            method = "exact"
            match = got_val is not None and normalize_text(expected_val) == normalize_text(got_val)

        bucket = BUCKET_LOOKUP if title_lookup and field in TITLE_LOOKUP_FIELDS else BUCKET_ANNOTATOR

        results.append({
            "field": field,
            "tier": tier,
            "from_fc": from_fc,
            "expected": expected_val,
            "got": got_val,
            "match": match,
            "method": method,
            "score": None if score is None else round(score, 4),
            "bucket": bucket,
        })
    return results


# ─── Semantic similarity ──────────────────────────────────────────────────────

def _cosine(u: list[float], v: list[float]) -> float:
    dot = sum(a * b for a, b in zip(u, v))
    nu = math.sqrt(sum(a * a for a in u))
    nv = math.sqrt(sum(b * b for b in v))
    return dot / (nu * nv) if nu and nv else 0.0


async def semantic_scores_for(
    client: AsyncLLMClient,
    cases: list[dict],
    annotations: list[dict],
) -> tuple[list[dict[str, float]], dict[str, float], object]:
    """Embed expected vs produced free text and return per-case cosine scores.

    Returns ``(scores_per_case, negative_control, usage)``. ``negative_control``
    maps each field to the cosines between a case's expected text and the
    *next* case's output for the same field: the scores two unrelated texts get,
    which tells the reader how far above chance SEMANTIC_THRESHOLD sits.
    An empty or missing output scores 0.0 without an embedding call.
    """
    scores: list[dict[str, float]] = [{} for _ in cases]
    pairs: list[tuple[int, str, str, str]] = []
    for i, (case, ann) in enumerate(zip(cases, annotations)):
        for field in sorted(SEMANTIC_FIELDS):
            entry = (case.get("expected") or {}).get(field)
            if not entry or not entry.get("value"):
                continue
            got = ann.get(field)
            if not isinstance(got, str) or not got.strip():
                scores[i][field] = 0.0
                continue
            pairs.append((i, field, str(entry["value"]), got))

    if not pairs:
        return scores, {}, None

    texts = [t for _, _, exp, got in pairs for t in (exp, got)]
    resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    vectors = [d.embedding for d in resp.data]

    by_field: dict[str, list[tuple[list[float], list[float]]]] = {}
    for k, (i, field, _exp, _got) in enumerate(pairs):
        exp_vec, got_vec = vectors[2 * k], vectors[2 * k + 1]
        scores[i][field] = _cosine(exp_vec, got_vec)
        by_field.setdefault(field, []).append((exp_vec, got_vec))

    negative: dict[str, list[float]] = {}
    for field, vecs in by_field.items():
        if len(vecs) < 2:
            continue
        negative[field] = [
            round(_cosine(vecs[k][0], vecs[(k + 1) % len(vecs)][1]), 4) for k in range(len(vecs))
        ]

    return scores, negative, resp.usage


# ─── Cost estimation ─────────────────────────────────────────────────────────

def _estimate_cost(usages: list, embedding_usage=None) -> float:
    """Estimate cost in USD for GPT-4o-mini usage plus the embedding call."""
    total_in = sum((u.prompt_tokens if u else 0) for u in usages)
    total_out = sum((u.completion_tokens if u else 0) for u in usages)
    # GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output
    cost = total_in * 0.15 / 1_000_000 + total_out * 0.60 / 1_000_000
    if embedding_usage is not None:
        # text-embedding-3-small: $0.02/1M tokens
        cost += (getattr(embedding_usage, "total_tokens", 0) or 0) * 0.02 / 1_000_000
    return cost


# ─── Aggregation ──────────────────────────────────────────────────────────────

def _aggregate(diffs: list[list[dict]], bucket: str | None = None) -> dict[int, dict[str, dict]]:
    """Per tier, per field: tested / passed / failed, methods and scores.

    ``bucket=None`` aggregates every entry; otherwise only entries of that bucket.
    """
    stats: dict[int, dict[str, dict]] = {1: {}, 2: {}}
    for diff_list in diffs:
        for entry in diff_list:
            if bucket is not None and entry.get("bucket", BUCKET_ANNOTATOR) != bucket:
                continue
            s = stats.setdefault(entry["tier"], {}).setdefault(
                entry["field"],
                {"tested": 0, "passed": 0, "failed": 0, "methods": set(), "scores": []},
            )
            s["tested"] += 1
            s["passed" if entry["match"] else "failed"] += 1
            s["methods"].add(entry.get("method", "exact"))
            if entry.get("score") is not None:
                s["scores"].append(entry["score"])
    return stats


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _flatten(stats: dict[int, dict[str, dict]]) -> dict[str, dict]:
    """Collapse tiers into one entry per field; Tier 1 wins if a field is in both."""
    out: dict[str, dict] = {}
    for tier in sorted(stats):
        for f, s in stats[tier].items():
            if f in out:
                continue
            out[f] = {
                "tier": tier,
                "tested": s["tested"],
                "passed": s["passed"],
                "failed": s["failed"],
                "method": "/".join(sorted(s["methods"])),
                "mean_score": _mean(s["scores"]),
            }
    return out


def _totals(stats_by_field: dict[str, dict]) -> tuple[int, int]:
    return (
        sum(v["tested"] for v in stats_by_field.values()),
        sum(v["passed"] for v in stats_by_field.values()),
    )


# ─── Report writer ────────────────────────────────────────────────────────────

def build_snapshot(
    cases: list[dict],
    diffs: list[list[dict]],
    snapshot_meta: dict,
    runtime_s: float,
    usages: list,
    embedding_usage=None,
    negative_control: dict[str, list[float]] | None = None,
) -> dict:
    """Build a machine-readable snapshot of eval results.

    Used by CI KPI guards (eval-annotator.yml / eval-annotator-stage2.yml)
    so they can fail fast without parsing the markdown report.

    ``per_field`` keeps every bucket so the existing name_zh / name_en guards
    keep their denominator. ``annotator_fields`` and ``lookup_fields`` split it;
    the ``tier*`` totals count the annotator bucket only.
    """
    annotator = _aggregate(diffs, BUCKET_ANNOTATOR)
    lookup = _flatten(_aggregate(diffs, BUCKET_LOOKUP))

    t1_tested, t1_passed = _totals(annotator[1])
    t2_tested, t2_passed = _totals(annotator.get(2, {}))
    lk_tested, lk_passed = _totals(lookup)

    return {
        "scoring_version": SCORING_VERSION,
        "mode": snapshot_meta.get("mode", "frozen"),
        "stage": snapshot_meta.get("stage", 1),
        "snapshot_at": snapshot_meta.get("snapshot_at"),
        "sha256": snapshot_meta.get("sha256"),
        "validator_changed": snapshot_meta.get("validator_changed"),
        "n_cases": len(cases),
        "per_field": _flatten(_aggregate(diffs)),
        "annotator_fields": _flatten(annotator),
        "lookup_fields": lookup,
        "tier1_tested": t1_tested,
        "tier1_passed": t1_passed,
        "tier2_tested": t2_tested,
        "tier2_passed": t2_passed,
        "lookup_tested": lk_tested,
        "lookup_passed": lk_passed,
        "semantic_negative_control": negative_control or {},
        # Per-entry scores, so thresholds can be calibrated from a run's artifact.
        "entries": [
            {
                "case_id": case.get("case_id"),
                "source_name": case.get("source_name"),
                "field": e["field"],
                "tier": e["tier"],
                "bucket": e.get("bucket"),
                "method": e.get("method"),
                "score": e.get("score"),
                "match": e["match"],
            }
            for case, diff_list in zip(cases, diffs)
            for e in diff_list
        ],
        "cost_usd": round(_estimate_cost(usages, embedding_usage), 6),
        "runtime_s": round(runtime_s, 2),
        "ran_at": datetime.now(tz=JST).isoformat(),
    }


def _field_table(title: str, stats_by_field: dict[str, dict]) -> list[str]:
    lines = [
        title,
        "| Field | Method | Tested | Pass | Fail | Accuracy | Mean score |",
        "|---|---|---|---|---|---|---|",
    ]
    for field in sorted(stats_by_field):
        s = stats_by_field[field]
        acc = s["passed"] / s["tested"] if s["tested"] else 0.0
        mean = s.get("mean_score")
        mean_str = f"{mean:.2f}" if mean is not None else "—"
        lines.append(
            f"| {field} | {s['method']} | {s['tested']} | {s['passed']} | {s['failed']} | {acc:.1%} | {mean_str} |"
        )
    lines.append("")
    return lines


def write_report(
    cases: list[dict],
    diffs: list[list[dict]],
    snapshot_meta: dict,
    output_path: Path,
    runtime_s: float,
    usages: list,
    embedding_usage=None,
    negative_control: dict[str, list[float]] | None = None,
) -> None:
    """Write markdown accuracy report."""
    now_jst = datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M JST")
    cost = _estimate_cost(usages, embedding_usage)
    n_cases = len(cases)
    negative_control = negative_control or {}

    annotator = _aggregate(diffs, BUCKET_ANNOTATOR)
    tier1 = _flatten({1: annotator[1]})
    tier2 = _flatten({2: annotator.get(2, {})})
    lookup = _flatten(_aggregate(diffs, BUCKET_LOOKUP))

    lines = [
        f"# Annotator Golden Set Report — {now_jst}",
        "",
        "## 執行模式",
        f"- mode: {snapshot_meta.get('mode', 'frozen')}",
        f"- stage: {snapshot_meta.get('stage', 1)} "
        f"({_STAGE_LABELS.get(snapshot_meta.get('stage', 1), 'unknown')})",
    ]
    if snapshot_meta.get("mode") == "frozen":
        lines += [
            f"- frozen sha256: {snapshot_meta.get('sha256') or 'n/a'}",
            f"- snapshot_at: {snapshot_meta.get('snapshot_at') or 'n/a'}",
        ]
    changed = snapshot_meta.get("validator_changed")
    if changed:
        lines.append(
            f"- 正式環境驗證改動的 LLM 輸出：category {changed['category']} 筆、event_form {changed['event_form']} 筆（比較的是驗證後的值）"
        )
    lines += [
        f"- scoring: v{SCORING_VERSION}（名稱與 location_name：正規化後 fuzzy ≥ {FUZZY_THRESHOLD}；"
        f"description：{EMBEDDING_MODEL} cosine ≥ {SEMANTIC_THRESHOLD}；電影片名另列為查詢型評估）",
        f"- cases: {n_cases}",
        f"- cost: ${cost:.4f} (est.)",
        f"- runtime: {int(runtime_s // 60)}m {int(runtime_s % 60)}s",
        "",
    ]

    if tier1:
        lines += _field_table("## Per-Field Accuracy（Tier 1，annotator）", tier1)
    else:
        lines += ["## Per-Field Accuracy（Tier 1，annotator）", "_No Tier 1 cases_", ""]

    if tier2:
        lines += _field_table("## Per-Field Accuracy（Tier 2，annotator）", tier2)

    if lookup:
        lines += _field_table("## 片名查詢（不計入 annotator 分數）", lookup)
        lines += [
            "期望值是台灣官方片名，由 works 表與 eiga.com 查詢取得，不是 LLM 翻譯的結果。"
            "Stage 1 只看 LLM 輸出，這裡的數字只供對照；查詢管線的成績看 Stage 2。",
            "",
        ]

    semantic_rows = []
    for field in sorted(SEMANTIC_FIELDS):
        s = (tier1.get(field) or tier2.get(field))
        if not s or "semantic" not in s["method"]:
            continue
        neg = negative_control.get(field) or []
        neg_mean = f"{_mean(neg):.2f}" if neg else "n/a"
        neg_max = f"{max(neg):.2f}" if neg else "n/a"
        semantic_rows.append(
            f"| {field} | {SEMANTIC_THRESHOLD} | {s['mean_score']:.2f} | {neg_mean} | {neg_max} |"
        )
    if semantic_rows:
        lines += [
            "## 語意比對校準",
            "負對照是期望值與「下一筆 case 的輸出」之間的平均 cosine，代表兩段無關文字會拿到的分數。",
            "",
            "| Field | 門檻 | 平均 cosine | 負對照平均 | 負對照最高 |",
            "|---|---|---|---|---|",
            *semantic_rows,
            "",
        ]

    # Failures — Tier 1 annotator bucket only, max 10
    failures: list[tuple[str, str, dict]] = []
    for case, diff_list in zip(cases, diffs):
        for entry in diff_list:
            if entry["tier"] == 1 and entry.get("bucket") == BUCKET_ANNOTATOR and not entry["match"]:
                failures.append((case["case_id"], case.get("source_name", ""), entry))
    if failures:
        lines += ["## Failures（Tier 1 annotator，前 10 筆）"]
        for case_id, source, entry in failures[:10]:
            label = "[T1, from FC]" if entry.get("from_fc") else "[T1]"
            exp_str = json.dumps(entry["expected"], ensure_ascii=False)
            got_str = json.dumps(entry["got"], ensure_ascii=False)
            score = f", score {entry['score']:.2f}" if entry.get("score") is not None else ""
            lines += [
                "",
                f"### case {case_id} — source: {source}",
                f"- **{entry['field']}** {label} ({entry.get('method', 'exact')}{score}): "
                f"expected `{exp_str}`, got `{got_str}`",
            ]
        lines.append("")

    t1_tested, t1_pass = _totals(tier1)
    t2_tested, t2_pass = _totals(tier2)
    lk_tested, lk_pass = _totals(lookup)
    failed_cases = sum(
        1 for diff_list in diffs
        if any(not e["match"] and e.get("bucket") == BUCKET_ANNOTATOR for e in diff_list)
    )

    def _pct(passed: int, tested: int) -> str:
        return f"{passed / tested:.1%}" if tested else "n/a"

    lines += [
        "## Summary",
        f"- Total Tier 1 accuracy (annotator): {_pct(t1_pass, t1_tested)}",
        f"- Total Tier 2 accuracy (annotator): {_pct(t2_pass, t2_tested)}",
        f"- Title lookup accuracy (not in annotator score): {_pct(lk_pass, lk_tested)}",
        f"- Failed cases (annotator): {failed_cases} / {n_cases}",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    logger.info("Report written: %s", output_path)


# ─── Main runner ──────────────────────────────────────────────────────────────

async def run_golden(
    cases_path: Path,
    frozen_path: Path,
    output_path: Path,
    sample: int | None = None,
    use_live: bool = False,
    case_id: str | None = None,
    stage: int = 1,
    json_output: Path | None = None,
) -> None:
    cases = load_cases(cases_path, limit=sample, case_id=case_id)

    if not cases:
        print("WARNING: cases.jsonl is empty. Run build_golden_dataset.py --target 50 --interactive to populate.", file=sys.stderr)
        logger.warning("No cases found — golden set is empty. Exiting.")
        return  # exit 0

    logger.info("Loaded %d cases", len(cases))

    # Build feedback prompts
    if use_live:
        sb = _get_supabase()
        corrections = load_corrections(sb)
        sr_corrections = load_sr_corrections(sb)
        snapshot_meta = {"mode": "live", "stage": stage}
    else:
        if not frozen_path.exists():
            print(f"WARNING: {frozen_path} not found. Run build_golden_dataset.py --rebuild-frozen-only.", file=sys.stderr)
            frozen = {"snapshot_at": None, "category_corrections": [], "selection_reason_corrections": [], "sha256": None}
        else:
            frozen = json.loads(frozen_path.read_text())
        corrections = frozen.get("category_corrections", [])
        sr_corrections = frozen.get("selection_reason_corrections", [])
        snapshot_meta = {
            "mode": "frozen",
            "stage": stage,
            "sha256": frozen.get("sha256"),
            "snapshot_at": frozen.get("snapshot_at"),
        }

    # Stage 2 needs a Supabase client to query the works table.
    # Read-only — works table lookup mirrors enrich_movie_titles().
    sb_for_pipeline = None
    if stage >= 2:
        try:
            sb_for_pipeline = _get_supabase()
        except Exception as exc:
            logger.warning(
                "Stage 2 works lookup disabled — Supabase unavailable: %s", exc,
            )

    feedback_prompt = build_feedback_prompt(corrections)
    sr_feedback_prompt = build_sr_feedback_prompt(sr_corrections)

    client = get_async_client("eval.annotator")
    sem = asyncio.Semaphore(5)

    start_time = time.monotonic()

    async def annotate_one(case: dict) -> tuple[dict, object]:
        async with sem:
            inp = case["input"]
            annotation, usage = await annotate_one_async(
                client,
                inp.get("raw_title", ""),
                inp.get("raw_description", ""),
                feedback_prompt,
                sr_feedback_prompt,
            )
            return annotation, usage

    logger.info("Annotating %d cases with concurrency=5 ...", len(cases))
    results = await asyncio.gather(*[annotate_one(c) for c in cases])

    # Production validates category / event_form before storing, and the
    # enrichment stages below read the stored values.
    annotations = [normalize_annotation(r[0]) for r in results]
    usages = [r[1] for r in results]
    snapshot_meta["validator_changed"] = {
        f: sum(1 for (raw, _u), ann in zip(results, annotations) if raw.get(f) != ann[f])
        for f in ("category", "event_form")
    }

    # ── Stage 2 / --full-pipeline ────────────────────────────────────────
    # After LLM annotation, apply enrich_movie_titles() title resolution
    # in-memory: works table (B3 first, B2 title_zh fallback) → eiga.com.
    # No DB writes. FC lookup is skipped — the golden cases were derived
    # from field_corrections so the "expected" value already encodes the
    # post-FC state. Stage 2 measures how close the works + eiga.com pipeline
    # gets without the explicit FC override.
    pipeline_log: list[dict] = []
    if stage >= 2:
        for case, ann in zip(cases, annotations):
            cats = ann.get("category") or []
            if not isinstance(cats, list) or "movie" not in cats:
                continue
            inp = case.get("input", {})
            source_name = case.get("source_name") or ""
            name_zh, name_en, _url, _wp, _wd, _wi, title, _resolution_kind = _resolve_movie_titles_for_event(
                sb_for_pipeline,
                inp.get("raw_title"),
                ann.get("name_ja") or inp.get("raw_title"),
                source_name,
                has_parent=False,
            )
            before_zh = ann.get("name_zh")
            before_en = ann.get("name_en")
            changed_zh = bool(name_zh and name_zh != before_zh)
            changed_en = bool(name_en and name_en != before_en)
            if name_zh:
                ann["name_zh"] = name_zh
            if name_en:
                ann["name_en"] = name_en
            sync_title_in_descriptions(
                ann,
                old_name_zh=before_zh,
                old_name_en=before_en,
                new_name_zh=name_zh,
                new_name_en=name_en,
                lookup_title=title or "",
                is_news_source=source_name in _NEWS_MOVIE_SOURCES,
            )
            if changed_zh or changed_en:
                pipeline_log.append({
                    "case_id": case.get("case_id"),
                    "title": title,
                    "before_zh": before_zh,
                    "after_zh": ann.get("name_zh"),
                    "before_en": before_en,
                    "after_en": ann.get("name_en"),
                })
        logger.info(
            "Stage 2 pipeline applied: %d cases had movie titles resolved",
            len(pipeline_log),
        )

    # ── Stage 3 ──────────────────────────────────────────────────────────
    # After stage 2, apply the enrich_person_names ground-truth lookup
    # (eiga.com + Wikipedia) to description_zh / description_en in memory.
    # Same helpers as annotator.enrich_person_names_single; no DB writes.
    # The lookups are synchronous and rate-limited, so run them in threads.
    if stage >= 3:
        sync_client = get_client("eval.annotator.stage3")

        def _enrich_people(case: dict, ann: dict) -> dict | None:
            inp = case.get("input", {})
            event = {
                "id": case.get("case_id") or "",
                "source_name": case.get("source_name") or "",
                "name_ja": ann.get("name_ja") or "",
                "raw_title": inp.get("raw_title") or "",
                "raw_description": inp.get("raw_description") or "",
                "category": ann.get("category") or [],
                "event_form": ann.get("event_form") or [],
            }
            is_film = bool(_film_person_enrich_reasons(event))
            _title_source, title = _pick_person_lookup_title(event)
            people = _resolve_event_people(event, title, is_film)
            if not people:
                return None
            update = _fix_descriptions_with_people(
                sync_client,
                ann.get("description_zh") or "",
                ann.get("description_en") or "",
                people,
            )
            return {"people": people, "update": update}

        person_results = await asyncio.gather(*[
            asyncio.to_thread(_enrich_people, c, a)
            for c, a in zip(cases, annotations)
        ])
        patched = 0
        for case, ann, res in zip(cases, annotations, person_results):
            if res and res["update"]:
                for field, fixed in res["update"].items():
                    logger.info(
                        "Stage 3 %s %s\n  before: %r\n  after:  %r",
                        case.get("case_id"), field, ann.get(field), fixed,
                    )
                ann.update(res["update"])
                patched += 1
        logger.info(
            "Stage 3 pipeline applied: %d/%d cases had person names resolved",
            patched, len(cases),
        )

    try:
        semantic, negative_control, embedding_usage = await semantic_scores_for(client, cases, annotations)
    except Exception as exc:
        # Scoring falls back to fuzzy for descriptions; the report's method column shows it.
        logger.warning("Semantic scoring unavailable, descriptions use fuzzy: %s", exc)
        semantic, negative_control, embedding_usage = [{} for _ in cases], {}, None

    diffs = [
        compare_fields(
            c["expected"],
            ann,
            title_lookup=is_title_lookup_case(c, ann),
            semantic_scores=sem,
        )
        for c, ann, sem in zip(cases, annotations, semantic)
    ]

    runtime_s = time.monotonic() - start_time

    write_report(
        cases, diffs, snapshot_meta, output_path, runtime_s, usages,
        embedding_usage=embedding_usage, negative_control=negative_control,
    )

    if json_output is not None:
        snap = build_snapshot(
            cases, diffs, snapshot_meta, runtime_s, usages,
            embedding_usage=embedding_usage, negative_control=negative_control,
        )
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
        logger.info("Snapshot JSON written: %s", json_output)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run annotator golden set eval")
    ap.add_argument("--output", type=Path, default=Path("report.md"), help="Output markdown path")
    ap.add_argument("--live", action="store_true", help="Use live DB corrections (default: frozen)")
    ap.add_argument("--sample", type=int, default=None, help="Limit to N cases (debug)")
    ap.add_argument("--case", type=str, default=None, help="Run a single case by case_id")
    ap.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help=(
            "1 = LLM-only baseline (default); 2 = LLM + enrich_movie_titles pipeline "
            "(works → eiga.com); 3 = stage 2 + enrich_person_names ground-truth lookup."
        ),
    )
    ap.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Alias for --stage 2: run LLM output through the enrich_movie_titles resolver before scoring.",
    )
    ap.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional path to dump a machine-readable JSON snapshot (per-field passed/tested counts, cost, runtime). Used by CI KPI guards.",
    )
    args = ap.parse_args()

    stage = 2 if args.full_pipeline else args.stage

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    asyncio.run(run_golden(
        cases_path=CASES_PATH,
        frozen_path=FROZEN_PATH,
        output_path=args.output,
        sample=args.sample,
        use_live=args.live,
        case_id=args.case,
        stage=stage,
        json_output=args.json_output,
    ))
    return 0


if __name__ == "__main__":
    rc = main()
    finish()
    sys.exit(rc)
