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
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Import SYSTEM_PROMPT from annotator (same directory).
# _annotate_one is sync; we implement annotate_one_async below using AsyncOpenAI.
from annotator import SYSTEM_PROMPT, _get_supabase
from category_feedback import load_corrections, build_feedback_prompt
from selection_reason_feedback import load_sr_corrections, build_sr_feedback_prompt

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

# ─── Async annotator ─────────────────────────────────────────────────────────

async def annotate_one_async(
    client: AsyncOpenAI,
    raw_title: str,
    raw_description: str,
    feedback_prompt: str = "",
    sr_feedback_prompt: str = "",
) -> tuple[dict, object]:
    """Async version of annotator._annotate_one using AsyncOpenAI.

    Returns (annotation_dict, usage) matching _annotate_one's return signature.
    """
    system_content = SYSTEM_PROMPT + feedback_prompt + sr_feedback_prompt
    user_content = (
        f"Raw Title: {raw_title or '(no title)'}\n\n"
        f"Raw Description:\n{raw_description or '(no description)'}"
    )
    if len(user_content) > 20000:
        user_content = user_content[:20000] + "\n\n[... truncated ...]"

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

def compare_fields(expected_dict: dict, annotation: dict) -> list[dict]:
    """Compare expected fields against annotation output.

    Returns list of dicts with keys: field, tier, from_fc, expected, got, match.
    Skips fields where expected value is None.
    """
    results = []
    for field, exp_entry in expected_dict.items():
        if exp_entry is None:
            continue
        expected_val = exp_entry.get("value")
        tier = exp_entry.get("tier", 1)
        from_fc = exp_entry.get("from_fc", False)

        got_val = annotation.get(field)

        # Normalize and compare
        if field in LIST_FIELDS:
            # Set equality for list fields
            exp_set = set(expected_val) if isinstance(expected_val, list) else set()
            got_set = set(got_val) if isinstance(got_val, list) else set()
            match = exp_set == got_set
        elif isinstance(expected_val, bool) or field in {
            "is_paid", "has_japanese_support", "has_english_support"
        }:
            # Boolean equality
            match = expected_val == got_val
        elif expected_val is None:
            match = got_val is None
        else:
            # String exact match after strip
            exp_str = str(expected_val).strip() if expected_val is not None else ""
            got_str = str(got_val).strip() if got_val is not None else ""
            match = exp_str == got_str

        results.append({
            "field": field,
            "tier": tier,
            "from_fc": from_fc,
            "expected": expected_val,
            "got": got_val,
            "match": match,
        })
    return results


# ─── Cost estimation ─────────────────────────────────────────────────────────

def _estimate_cost(usages: list) -> float:
    """Estimate cost in USD for GPT-4o-mini usage."""
    total_in = sum((u.prompt_tokens if u else 0) for u in usages)
    total_out = sum((u.completion_tokens if u else 0) for u in usages)
    # GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output
    return total_in * 0.15 / 1_000_000 + total_out * 0.60 / 1_000_000


# ─── Report writer ────────────────────────────────────────────────────────────

def write_report(
    cases: list[dict],
    diffs: list[list[dict]],
    snapshot_meta: dict,
    output_path: Path,
    runtime_s: float,
    usages: list,
) -> None:
    """Write markdown accuracy report."""
    now_jst = datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M JST")
    cost = _estimate_cost(usages)
    n_cases = len(cases)

    # Aggregate per-field stats, split by tier
    tier_stats: dict[int, dict[str, dict]] = {1: {}, 2: {}}
    for diff_list in diffs:
        for entry in diff_list:
            t = entry["tier"]
            f = entry["field"]
            if f not in tier_stats[t]:
                tier_stats[t][f] = {"tested": 0, "pass": 0, "fail": 0}
            tier_stats[t][f]["tested"] += 1
            if entry["match"]:
                tier_stats[t][f]["pass"] += 1
            else:
                tier_stats[t][f]["fail"] += 1

    def _accuracy(stats: dict) -> float:
        return stats["pass"] / stats["tested"] if stats["tested"] else 0.0

    # Failures (Tier 1 only, max 10)
    tier1_failures: list[tuple[str, str, dict]] = []
    for case, diff_list in zip(cases, diffs):
        for entry in diff_list:
            if entry["tier"] == 1 and not entry["match"]:
                tier1_failures.append((case["case_id"], case.get("source_name", ""), entry))
                if len(tier1_failures) >= 10:
                    break
        if len(tier1_failures) >= 10:
            break

    # Total accuracy per tier
    def _tier_total(stats_by_field: dict) -> tuple[int, int]:
        total_tested = sum(v["tested"] for v in stats_by_field.values())
        total_pass = sum(v["pass"] for v in stats_by_field.values())
        return total_tested, total_pass

    t1_tested, t1_pass = _tier_total(tier_stats[1])
    t2_tested, t2_pass = _tier_total(tier_stats[2])

    lines = [
        f"# Annotator Golden Set Report — {now_jst}",
        "",
        "## 執行模式",
        f"- mode: {snapshot_meta.get('mode', 'frozen')}",
    ]
    if snapshot_meta.get("mode") == "frozen":
        lines += [
            f"- frozen sha256: {snapshot_meta.get('sha256') or 'n/a'}",
            f"- snapshot_at: {snapshot_meta.get('snapshot_at') or 'n/a'}",
        ]
    lines += [
        f"- cases: {n_cases}",
        f"- cost: ${cost:.4f} (est.)",
        f"- runtime: {int(runtime_s // 60)}m {int(runtime_s % 60)}s",
        "",
    ]

    # Per-Field Accuracy — Tier 1
    if tier_stats[1]:
        lines += [
            "## Per-Field Accuracy（Tier 1）",
            "| Field | Tested | Pass | Fail | Accuracy |",
            "|---|---|---|---|---|",
        ]
        for field in sorted(tier_stats[1]):
            s = tier_stats[1][field]
            acc = _accuracy(s)
            lines.append(f"| {field} | {s['tested']} | {s['pass']} | {s['fail']} | {acc:.1%} |")
        lines.append("")
    else:
        lines += ["## Per-Field Accuracy（Tier 1）", "_No Tier 1 cases_", ""]

    # Per-Field Accuracy — Tier 2 (only if any)
    if tier_stats[2]:
        lines += [
            "## Per-Field Accuracy（Tier 2）",
            "| Field | Tested | Pass | Fail | Accuracy |",
            "|---|---|---|---|---|",
        ]
        for field in sorted(tier_stats[2]):
            s = tier_stats[2][field]
            acc = _accuracy(s)
            lines.append(f"| {field} | {s['tested']} | {s['pass']} | {s['fail']} | {acc:.1%} |")
        lines.append("")

    # Failures — Tier 1 only, max 10
    if tier1_failures:
        lines += ["## Failures（Tier 1 only，前 10 筆）"]
        seen = set()
        for case_id, source, entry in tier1_failures:
            key = (case_id, entry["field"])
            if key in seen:
                continue
            seen.add(key)
            label = "[T1, from FC]" if entry.get("from_fc") else "[T1]"
            exp_str = json.dumps(entry["expected"], ensure_ascii=False)
            got_str = json.dumps(entry["got"], ensure_ascii=False)
            if case_id not in {k for k, _, _ in tier1_failures[:1]}:
                lines.append("")
            lines.append(f"### case {case_id} — source: {source}")
            lines.append(f"- **{entry['field']}** {label}: expected `{exp_str}`, got `{got_str}`")
        lines.append("")

    # Summary
    t1_acc_str = f"{t1_pass/t1_tested:.1%}" if t1_tested else "n/a"
    t2_acc_str = f"{t2_pass/t2_tested:.1%}" if t2_tested else "n/a"
    failed_cases = sum(
        1 for diff_list in diffs
        if any(not e["match"] for e in diff_list)
    )
    lines += [
        "## Summary",
        f"- Total Tier 1 accuracy: {t1_acc_str}",
        f"- Total Tier 2 accuracy: {t2_acc_str}",
        f"- Failed cases: {failed_cases} / {n_cases}",
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
        snapshot_meta = {"mode": "live"}
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
            "sha256": frozen.get("sha256"),
            "snapshot_at": frozen.get("snapshot_at"),
        }

    feedback_prompt = build_feedback_prompt(corrections)
    sr_feedback_prompt = build_sr_feedback_prompt(sr_corrections)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    client = AsyncOpenAI(api_key=api_key)
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

    annotations = [r[0] for r in results]
    usages = [r[1] for r in results]

    diffs = [
        compare_fields(c["expected"], ann)
        for c, ann in zip(cases, annotations)
    ]

    runtime_s = time.monotonic() - start_time

    write_report(cases, diffs, snapshot_meta, output_path, runtime_s, usages)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run annotator golden set eval")
    ap.add_argument("--output", type=Path, default=Path("report.md"), help="Output markdown path")
    ap.add_argument("--live", action="store_true", help="Use live DB corrections (default: frozen)")
    ap.add_argument("--sample", type=int, default=None, help="Limit to N cases (debug)")
    ap.add_argument("--case", type=str, default=None, help="Run a single case by case_id")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    asyncio.run(run_golden(
        cases_path=CASES_PATH,
        frozen_path=FROZEN_PATH,
        output_path=args.output,
        sample=args.sample,
        use_live=args.live,
        case_id=args.case,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
