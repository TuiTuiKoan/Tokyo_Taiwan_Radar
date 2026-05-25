"""
qa_heartbeat.py — QA self-healing orchestrator.

Reads pending event_reports of `auto_qa_*` types, classifies each via GPT-4o,
and dispatches to the appropriate handler in `qa_auto_fix.HANDLER_MAP` or to
`annotator.enrich_person_names_single`. Every mutation is wrapped by
`qa_auto_fix.unlock_and_write`, which writes a `field_corrections_audit` row
and verifies the post-write state before confirming the report.

Safety:
- Default --limit 200 (manual dispatch); scheduled cron should pass --limit 20.
- 5-failure circuit breaker on the classifier — after 5 consecutive GPT errors
  the run aborts and writes a partial report.
- `--rollback-audit-id` / `--rollback-since` restore from the audit table.
- LINE notification only when `--dry-run` is NOT set OR
  `--allow-line-in-dry-run` is explicitly passed.

Usage:
    python qa_heartbeat.py --dry-run
    python qa_heartbeat.py --limit 50 --model gpt-4o
    python qa_heartbeat.py --rollback-audit-id <uuid>
    python qa_heartbeat.py --rollback-since 2026-05-24T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

load_dotenv(dotenv_path=SCRIPT_DIR / ".env")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
REPORTS_DIR = SCRIPT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Cost estimate (gpt-4o, May 2026 pricing): $5/M input, $15/M output tokens.
# Heartbeat payloads are tiny — average ~400 input / ~80 output tokens per call.
_GPT4O_IN_PER_M = 5.0
_GPT4O_OUT_PER_M = 15.0

CIRCUIT_BREAKER_THRESHOLD = 5

# Root-cause classes the classifier may emit. Kept in sync with cases.jsonl
# and SKILL.md catalog block.
R_CLASSES = (
    "R-ANN-SC",            # annotator simplified-Chinese output
    "R-ANN-AI-MARKER",     # annotator left "(AI翻譯)" / "(AI Translation)" marker
    "R-SCR-PERF-MULTI",    # scraper polluted performer with separator
    "R-ANN-PERF-PHON",     # annotator phonetic-translated katakana performer
    "R-ENRICH-MISS",       # enrich_person_names lookup failed; needs retry
    "R-AMBIGUOUS",         # GPT could not classify confidently
)

# Per-class handler routing. (None means "no auto-handler — review only".)
ROUTING: dict[str, dict[str, Any]] = {
    "R-ANN-SC": {"handler_key": "auto_qa_simplified_zh", "min_confidence": 0.80},
    "R-ANN-AI-MARKER": {"handler_key": "auto_qa_performer_ai_translation_marker", "min_confidence": 0.85},
    "R-SCR-PERF-MULTI": {"handler_key": "auto_qa_performer_multi_value_pollution", "min_confidence": 0.85},
    "R-ENRICH-MISS": {"handler_key": "__enrich_person__", "min_confidence": 0.75},
    "R-ANN-PERF-PHON": {"handler_key": "__enrich_person__", "min_confidence": 0.80},
    "R-AMBIGUOUS": {"handler_key": None, "min_confidence": 0.0},
}


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _openai_client():
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")
    return OpenAI(api_key=api_key)


_CLASSIFIER_SYSTEM = (
    "You classify Tokyo-Taiwan-Radar QA reports into one of these root-cause classes:\n"
    "  R-ANN-SC          — annotator left Simplified Chinese chars in *_zh fields\n"
    "  R-ANN-AI-MARKER   — translation field contains literal '（AI翻譯）' / '(AI Translation)' marker\n"
    "  R-SCR-PERF-MULTI  — scraper concatenated multiple performers into one field with separator (、, ／, ×)\n"
    "  R-ANN-PERF-PHON   — annotator phonetic-translated a katakana performer name (visible by char drift)\n"
    "  R-ENRICH-MISS     — enrich_person_names left katakana untranslated\n"
    "  R-AMBIGUOUS       — cannot decide confidently\n\n"
    "Reply STRICT JSON: {\"r_class\": str, \"confidence\": 0..1, \"reason\": str (<=120 chars)}.\n"
    "Be conservative — when in doubt, pick R-AMBIGUOUS with low confidence."
)


def _truncate_payload(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"…[truncated {len(text) - limit} chars]"


def _classify(client, report: dict, event: dict, max_input_chars: int, model: str) -> dict:
    """Call GPT-4o classifier. Returns {'r_class', 'confidence', 'reason',
    'tokens_in', 'tokens_out'} or raises on persistent API error."""
    payload = {
        "report_types": report.get("report_types") or [],
        "admin_notes": _truncate_payload(report.get("admin_notes"), max_input_chars),
        "event": {
            "source_name": event.get("source_name"),
            "category": event.get("category"),
            "name_ja": _truncate_payload(event.get("name_ja"), 200),
            "name_zh": _truncate_payload(event.get("name_zh"), 200),
            "description_zh": _truncate_payload(event.get("description_zh"), max_input_chars),
            "performer": _truncate_payload(event.get("performer"), 300),
            "performer_zh": _truncate_payload(event.get("performer_zh"), 300),
            "performer_en": _truncate_payload(event.get("performer_en"), 300),
            "performers": (event.get("performers") or [])[:20],
        },
    }
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    msg = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(msg)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"classifier returned non-JSON: {msg!r}") from exc

    r_class = parsed.get("r_class") or "R-AMBIGUOUS"
    if r_class not in R_CLASSES:
        r_class = "R-AMBIGUOUS"
    confidence = float(parsed.get("confidence") or 0.0)
    confidence = max(0.0, min(1.0, confidence))

    usage = getattr(resp, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
    tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0

    return {
        "r_class": r_class,
        "confidence": confidence,
        "reason": str(parsed.get("reason") or "")[:200],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def _fetch_pending_reports(sb, limit: int) -> list[dict]:
    """Pending auto_qa_* reports, oldest first."""
    from qa_auto_fix import SAFE_REPORT_TYPES

    rows: list[dict] = []
    for rt in SAFE_REPORT_TYPES:
        res = (
            sb.table("event_reports")
            .select("id,event_id,report_types,status,admin_notes,created_at")
            .eq("status", "pending")
            .contains("report_types", [rt])
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        rows.extend(res.data or [])
    # Dedup by id and re-sort
    seen: set[str] = set()
    out: list[dict] = []
    for r in sorted(rows, key=lambda x: x.get("created_at") or ""):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
        if len(out) >= limit:
            break
    return out


def _fetch_event(sb, event_id: str) -> dict:
    res = (
        sb.table("events")
        .select(
            "id,source_name,category,name_ja,name_zh,description_zh,"
            "performer,performer_zh,performer_en,performers,annotation_status"
        )
        .eq("id", event_id)
        .single()
        .execute()
    )
    return res.data or {}


def _dispatch(
    sb,
    *,
    report: dict,
    event: dict,
    classification: dict,
    model: str,
    dry_run: bool,
) -> dict:
    """Route a classified report to its handler. Returns result dict."""
    from qa_auto_fix import (
        HANDLER_MAP,
        _append_report_note,
        unlock_and_write,
    )
    import qa_auto_fix as _qaf  # for handler kwargs

    r_class = classification["r_class"]
    conf = classification["confidence"]
    routing = ROUTING.get(r_class) or {"handler_key": None, "min_confidence": 1.0}
    handler_key = routing["handler_key"]

    if not handler_key or conf < routing["min_confidence"]:
        # Below threshold or no auto-handler → review_only audit + note.
        unlock_and_write(
            sb,
            event_id=event["id"],
            field_name="__review__",
            new_value=None,
            mode="review_only",
            unlock_reason=f"heartbeat_review_only:{r_class}:{conf:.2f}:{classification['reason']}",
            report_id=report.get("id"),
            r_class=r_class,
            model_used=model,
            confidence=conf,
            dry_run=dry_run,
        )
        _append_report_note(
            sb, report["id"],
            f"heartbeat r_class={r_class} confidence={conf:.2f} — left for human review ({classification['reason']})",
            dry_run=dry_run,
        )
        return {"action": "review_only", "r_class": r_class, "confidence": conf}

    if handler_key == "__enrich_person__":
        # Person-name enrichment path
        from annotator import enrich_person_names_single
        try:
            result = enrich_person_names_single(
                sb, event_id=event["id"], event=None, client=None,
                force_fc_override=False, model=model,
            )
        except Exception as exc:  # pragma: no cover
            _append_report_note(sb, report["id"], f"heartbeat enrich failed: {exc!r}", dry_run=dry_run)
            return {"action": "enrich_failed", "r_class": r_class, "confidence": conf, "error": repr(exc)}
        if result.get("patched") and report.get("id"):
            _qaf._confirm_report(
                sb, report["id"],
                note=f"heartbeat enrich_person_names_single fixed {result.get('updated_fields')}",
                dry_run=dry_run,
            )
            return {"action": "enrich_applied", "r_class": r_class, "confidence": conf,
                    "fields": result.get("updated_fields")}
        _append_report_note(
            sb, report["id"],
            "heartbeat enrich found no fix (people lookup empty?)",
            dry_run=dry_run,
        )
        return {"action": "enrich_noop", "r_class": r_class, "confidence": conf}

    handler = HANDLER_MAP.get(handler_key)
    if handler is None:
        return {"action": "no_handler", "r_class": r_class, "confidence": conf}

    ok = handler(sb, event["id"], report, dry_run=dry_run)
    return {
        "action": "applied" if ok else "skipped",
        "r_class": r_class,
        "confidence": conf,
        "handler": handler_key,
    }


def rollback(sb, *, audit_id: str | None, since_iso: str | None, dry_run: bool) -> dict:
    """Restore events from `field_corrections_audit` rows.

    Identified by `audit_id` (one row) or `since_iso` (all applied rows newer
    than the timestamp). Restoration only undoes rows with
    `operation_status='applied'` and `rolled_back_at IS NULL`.
    """
    if not audit_id and not since_iso:
        raise ValueError("rollback requires --rollback-audit-id or --rollback-since")

    q = (
        sb.table("field_corrections_audit")
        .select("*")
        .eq("operation_status", "applied")
        .is_("rolled_back_at", "null")
    )
    if audit_id:
        q = q.eq("id", audit_id)
    if since_iso:
        q = q.gte("created_at", since_iso)
    rows = q.execute().data or []

    restored = 0
    for row in rows:
        eid = row["event_id"]
        field = row["field_name"]
        if field == "__review__":
            # review_only audit has no DB write to undo
            if not dry_run:
                sb.table("field_corrections_audit").update(
                    {
                        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
                        "rolled_back_reason": "manual_rollback (review_only no-op)",
                    }
                ).eq("id", row["id"]).execute()
            continue
        before = row.get("event_before_value_json")
        if dry_run:
            logger.info("[DRY] rollback %s.%s ← %r", eid[:8], field, before)
            restored += 1
            continue
        sb.table("events").update({field: before}).eq("id", eid).execute()
        # Restore FC row from snapshot if any
        fc_corrected_value = row.get("fc_before_corrected_value")
        fc_orig = row.get("fc_before_original_value")
        if fc_corrected_value is not None or fc_orig is not None:
            sb.table("field_corrections").upsert(
                {
                    "event_id": eid,
                    "field_name": field,
                    "original_value": fc_orig,
                    "corrected_value": fc_corrected_value,
                    "corrected_by": row.get("fc_before_corrected_by"),
                    "report_id": row.get("fc_before_report_id"),
                },
                on_conflict="event_id,field_name",
            ).execute()
        else:
            sb.table("field_corrections").delete().eq("event_id", eid).eq("field_name", field).execute()
        sb.table("field_corrections_audit").update(
            {
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
                "rolled_back_reason": f"manual_rollback{' since=' + since_iso if since_iso else ''}",
            }
        ).eq("id", row["id"]).execute()
        restored += 1

    return {"matched": len(rows), "restored": restored}


def _write_markdown_report(
    *,
    today_jst: str,
    summary: dict,
    classifications: list[dict],
    total_tokens_in: int,
    total_tokens_out: int,
    dry_run: bool,
) -> Path:
    cost = (total_tokens_in / 1_000_000.0) * _GPT4O_IN_PER_M + (total_tokens_out / 1_000_000.0) * _GPT4O_OUT_PER_M
    fname = f"qa_heartbeat_{today_jst.replace('/', '-')}.md"
    path = REPORTS_DIR / fname

    by_class: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for c in classifications:
        by_class[c["r_class"]] = by_class.get(c["r_class"], 0) + 1
        by_action[c.get("action", "?")] = by_action.get(c.get("action", "?"), 0) + 1

    lines = [
        f"# QA Heartbeat — {today_jst}",
        "",
        f"- mode: {'DRY-RUN' if dry_run else 'LIVE'}",
        f"- model: {summary.get('model')}",
        f"- reports scanned: {summary.get('scanned')}",
        f"- circuit-breaker tripped: {summary.get('circuit_breaker_tripped')}",
        f"- tokens: in={total_tokens_in:,} out={total_tokens_out:,}",
        f"- estimated cost: ${cost:.4f}",
        "",
        "## By r_class",
    ]
    for k, v in sorted(by_class.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## By action")
    for k, v in sorted(by_action.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Decisions")
    for c in classifications[:200]:
        lines.append(
            f"- {c['report_id'][:8]} event={c['event_id'][:8]} "
            f"r_class={c['r_class']} conf={c['confidence']:.2f} action={c.get('action')}"
        )
        if c.get("reason"):
            lines.append(f"  reason: {c['reason']}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(
    *,
    dry_run: bool,
    limit: int,
    model: str,
    max_input_chars: int,
    allow_line_in_dry_run: bool,
) -> dict:
    sb = _supabase_client()
    client = _openai_client()

    pending = _fetch_pending_reports(sb, limit=limit)
    logger.info("qa_heartbeat: %d pending reports (limit=%d)", len(pending), limit)

    classifications: list[dict] = []
    failures = 0
    circuit_tripped = False
    tokens_in = 0
    tokens_out = 0

    for report in pending:
        event = _fetch_event(sb, report["event_id"])
        if not event:
            logger.warning("  ⚠ report %s references missing event %s — skip",
                           report["id"][:8], report["event_id"][:8])
            continue

        try:
            classification = _classify(
                client, report, event, max_input_chars=max_input_chars, model=model,
            )
            failures = 0
        except Exception as exc:
            failures += 1
            logger.error("classifier failure (%d/%d): %r", failures, CIRCUIT_BREAKER_THRESHOLD, exc)
            if failures >= CIRCUIT_BREAKER_THRESHOLD:
                circuit_tripped = True
                logger.error("circuit breaker tripped — aborting run")
                break
            continue

        tokens_in += classification.get("tokens_in", 0)
        tokens_out += classification.get("tokens_out", 0)

        dispatch_res = _dispatch(
            sb, report=report, event=event, classification=classification,
            model=model, dry_run=dry_run,
        )
        classifications.append({
            "report_id": report["id"],
            "event_id": event["id"],
            **classification,
            **dispatch_res,
        })

    today_jst = datetime.now(timezone.utc).astimezone(JST).strftime("%Y/%m/%d")
    summary = {
        "model": model,
        "scanned": len(pending),
        "processed": len(classifications),
        "circuit_breaker_tripped": circuit_tripped,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    report_path = _write_markdown_report(
        today_jst=today_jst,
        summary=summary,
        classifications=classifications,
        total_tokens_in=tokens_in,
        total_tokens_out=tokens_out,
        dry_run=dry_run,
    )
    logger.info("qa_heartbeat report → %s", report_path)

    if (not dry_run) or allow_line_in_dry_run:
        try:
            from line_notify import send_line_message
            cost = (tokens_in / 1_000_000.0) * _GPT4O_IN_PER_M + (tokens_out / 1_000_000.0) * _GPT4O_OUT_PER_M
            msg = (
                f"🫀 QA Heartbeat（{today_jst}{' DRY' if dry_run else ''}）\n"
                f"scanned: {summary['scanned']}\n"
                f"processed: {summary['processed']}\n"
                f"tokens in/out: {tokens_in:,}/{tokens_out:,}\n"
                f"cost: ${cost:.4f}\n"
                f"circuit_breaker: {summary['circuit_breaker_tripped']}"
            )
            send_line_message(msg)
        except Exception as exc:  # pragma: no cover
            logger.warning("LINE send failed: %r", exc)

    return {"summary": summary, "report": str(report_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="QA Heartbeat self-healing orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes, no LINE (unless --allow-line-in-dry-run)")
    parser.add_argument("--limit", type=int, default=200, help="Max pending reports to process per run")
    parser.add_argument("--model", default="gpt-4o", help="Classifier model")
    parser.add_argument("--max-input-chars", type=int, default=1200,
                        help="Truncate each long text field in payload to this many chars")
    parser.add_argument("--allow-line-in-dry-run", action="store_true",
                        help="Send the LINE summary even when --dry-run is set")
    parser.add_argument("--rollback-audit-id", default=None,
                        help="Rollback a single field_corrections_audit row by id")
    parser.add_argument("--rollback-since", default=None,
                        help="Rollback all applied audit rows newer than this ISO timestamp")
    args = parser.parse_args()

    if args.rollback_audit_id or args.rollback_since:
        sb = _supabase_client()
        result = rollback(
            sb,
            audit_id=args.rollback_audit_id,
            since_iso=args.rollback_since,
            dry_run=args.dry_run,
        )
        logger.info("rollback: %s", result)
        return

    run(
        dry_run=args.dry_run,
        limit=args.limit,
        model=args.model,
        max_input_chars=args.max_input_chars,
        allow_line_in_dry_run=args.allow_line_in_dry_run,
    )


if __name__ == "__main__":
    main()
