"""
refetch_thin_events.py — Re-fetch pages for thin-content events flagged by auto_qa.

Usage:
    python refetch_thin_events.py [--dry-run] [--limit N] [--source SOURCE_NAME]

Flow:
  1. Read event_reports where report_types contains 'auto_qa_thin_content' and status='pending'
  2. Skip: is_active=False, or source_name in SKIP_SOURCES
  3. HTTP probe (httpx, no Playwright) → 4xx/error = dead URL, log and continue
  4. Playwright fetch → extract visible text, filter nav/header/footer/script
  5. If new_len > max(old_len * 1.5, old_len + 100) and new_len >= 200: update DB
  6. Update: events.raw_description=new_text, events.annotation_status='pending'
             event_reports.admin_notes += '; refetched:DATE len=OLD→NEW'
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sources where thin content is structural — no benefit from re-fetching.
SKIP_SOURCES = frozenset({
    "google_news_rss",
    "nhk_rss",
    "prtimes",
    "note_creators",
    "walkerplus",
})

MIN_NEW_LEN = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def is_significant_improvement(old_len: int, new_len: int) -> bool:
    """Return True when new text is substantially longer than old text."""
    return new_len >= MIN_NEW_LEN and new_len > max(old_len * 1.5, old_len + 100)


def probe_url(url: str) -> int | None:
    """Return HTTP status code or None on network error."""
    try:
        r = httpx.head(url, follow_redirects=True, timeout=10)
        return r.status_code
    except Exception:
        try:
            r = httpx.get(url, follow_redirects=True, timeout=10)
            return r.status_code
        except Exception:
            return None


def fetch_page_text(url: str) -> str | None:
    """Fetch page text via Playwright; removes nav/header/footer noise."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.evaluate(
                "document.querySelectorAll('script,style,nav,header,footer')"
                ".forEach(el => el.remove())"
            )
            text = page.inner_text("body")
            return text.strip() if text else None
        except Exception as e:
            logger.error("  [Playwright error] %s", e)
            return None
        finally:
            browser.close()


def _append_note(existing: str | None, addition: str) -> str:
    if existing:
        return existing + "; " + addition
    return addition


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Re-fetch thin-content events")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show events to process without writing DB")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum number of events to process (default: 20)")
    parser.add_argument("--source", metavar="SOURCE_NAME",
                        help="Restrict to a specific source_name")
    args = parser.parse_args()

    sb = _supabase_client()
    today_str = date.today().isoformat()

    # ------------------------------------------------------------------
    # Step 1: Fetch pending thin_content reports
    # ------------------------------------------------------------------
    query = (
        sb.table("event_reports")
        .select("id, event_id, admin_notes")
        .ov("report_types", ["auto_qa_thin_content"])
        .eq("status", "pending")
    )
    reports = query.execute().data
    logger.info("Found %d pending auto_qa_thin_content reports", len(reports))

    if not reports:
        logger.info("Nothing to process.")
        return

    # ------------------------------------------------------------------
    # Step 2: Fetch associated events in one batch
    # ------------------------------------------------------------------
    event_ids = [r["event_id"] for r in reports]
    events_data = (
        sb.table("events")
        .select("id, source_name, source_url, raw_description, is_active, annotation_status")
        .in_("id", event_ids)
        .execute()
        .data
    )
    events_map: dict[str, dict] = {e["id"]: e for e in events_data}

    # Build report lookup by event_id (take the first pending report per event)
    report_by_event: dict[str, dict] = {}
    for r in reports:
        if r["event_id"] not in report_by_event:
            report_by_event[r["event_id"]] = r

    # ------------------------------------------------------------------
    # Step 3: Filter and apply --source / --limit
    # ------------------------------------------------------------------
    candidates = []
    for event_id, report in report_by_event.items():
        event = events_map.get(event_id)
        if not event:
            logger.warning("Event %s not found in DB (report %s)", event_id, report["id"])
            continue

        if not event.get("is_active", True):
            logger.info("  SKIP (inactive) %s", event_id)
            continue

        source = event.get("source_name", "")
        if source in SKIP_SOURCES:
            logger.info("  SKIP (skip-source=%s) %s", source, event_id)
            continue

        if args.source and source != args.source:
            continue

        if not event.get("source_url"):
            logger.info("  SKIP (no source_url) %s", event_id)
            continue

        candidates.append((event, report))

    candidates = candidates[: args.limit]

    if args.dry_run:
        logger.info("DRY-RUN: would process %d events:", len(candidates))
        for event, report in candidates:
            old_len = len(event.get("raw_description") or "")
            logger.info(
                "  [%s] source=%s url=%s raw_desc_len=%d",
                event["id"][:8],
                event.get("source_name"),
                event.get("source_url"),
                old_len,
            )
        return

    # ------------------------------------------------------------------
    # Step 4–6: Process each candidate
    # ------------------------------------------------------------------
    updated = 0
    dead = 0
    skipped = 0

    for event, report in candidates:
        event_id = event["id"]
        report_id = report["id"]
        url = event["source_url"]
        old_desc = event.get("raw_description") or ""
        old_len = len(old_desc)
        source = event.get("source_name", "")

        logger.info(
            "[%s] source=%s url=%s old_len=%d",
            event_id[:8], source, url, old_len,
        )

        # Step 3: HTTP probe
        status_code = probe_url(url)
        if status_code is None or status_code >= 400:
            label = f"dead_url:{status_code or 'network_error'}"
            new_note = _append_note(report.get("admin_notes"), label)
            sb.table("event_reports").update({"admin_notes": new_note}).eq("id", report_id).execute()
            logger.info("  → %s (no is_active change)", label)
            dead += 1
            continue

        # Step 4: Playwright fetch
        new_text = fetch_page_text(url)
        if not new_text:
            logger.info("  → Playwright returned empty text, skipping")
            skipped += 1
            continue

        new_len = len(new_text)

        # Step 5: Improvement threshold
        if not is_significant_improvement(old_len, new_len):
            logger.info(
                "  → No significant improvement (old=%d new=%d), skipping",
                old_len, new_len,
            )
            skipped += 1
            continue

        # Step 6: Update DB
        note_suffix = f"refetched:{today_str} len={old_len}→{new_len}"
        new_note = _append_note(report.get("admin_notes"), note_suffix)

        sb.table("events").update({
            "raw_description": new_text,
            "annotation_status": "pending",
        }).eq("id", event_id).execute()

        sb.table("event_reports").update({
            "admin_notes": new_note,
        }).eq("id", report_id).execute()

        logger.info("  → Updated: old=%d → new=%d chars", old_len, new_len)
        updated += 1

    logger.info(
        "Done. updated=%d dead=%d skipped=%d (of %d candidates)",
        updated, dead, skipped, len(candidates),
    )


if __name__ == "__main__":
    main()
