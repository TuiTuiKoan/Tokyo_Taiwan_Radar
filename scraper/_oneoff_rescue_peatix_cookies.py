"""One-off direct-URL rescue for historical Peatix cookie-wall rows.

This intentionally bypasses ``main.py --rescrape-ids`` because that flag only
force-overwrites events that the normal Peatix crawl happens to rediscover.
Historical cookie-wall rows may be delisted or buried in search results, so the
repair must fetch each stored ``source_url`` directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from database import _get_client, upsert_events
from sources.base import Event
from sources.peatix import PeatixScraper, _looks_like_cookie_banner


LOGGER = logging.getLogger(__name__)
COOKIE_PREFIX = "About cookies on this site%"
REPORTABLE_STATUSES = {
    "rescue_ready",
    "scrape_none",
    "cookie_still_present",
    "field_missing",
    "source_id_mismatch",
    "not_updated_or_excluded",
}


@dataclass(frozen=True)
class Candidate:
    id: str
    source_id: str
    source_url: str
    annotation_status: str | None


def _load_env() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")


def _write_report(path: str | None, report: dict[str, Any]) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def _fetch_candidates() -> list[Candidate]:
    client = _get_client()
    result = (
        client.table("events")
        .select("id,source_id,source_url,annotation_status")
        .eq("source_name", "peatix")
        .eq("is_active", True)
        .like("raw_description", COOKIE_PREFIX)
        .execute()
    )
    return [
        Candidate(
            id=row["id"],
            source_id=row["source_id"],
            source_url=row["source_url"],
            annotation_status=row.get("annotation_status"),
        )
        for row in (result.data or [])
    ]


def _event_missing_fields(event: Event) -> list[str]:
    required = ["location_name", "location_address", "business_hours", "price_info"]
    return [field for field in required if not getattr(event, field)]


def _failure(candidate: Candidate, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "source_id": candidate.source_id,
        "source_url": candidate.source_url,
        "reason": reason,
        **extra,
    }


def _scrape_candidates(candidates: list[Candidate]) -> tuple[list[tuple[Candidate, Event]], list[dict[str, Any]]]:
    rescued: list[tuple[Candidate, Event]] = []
    failed_rows: list[dict[str, Any]] = []
    scraper = PeatixScraper()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="ja-JP")
        try:
            for candidate in candidates:
                LOGGER.info("Scraping Peatix rescue candidate %s", candidate.source_url)
                try:
                    event = scraper._scrape_detail(page, candidate.source_url)
                except Exception as exc:
                    failed_rows.append(_failure(candidate, "scrape_none", error=str(exc)))
                    continue

                if event is None:
                    failed_rows.append(_failure(candidate, "scrape_none"))
                    continue
                if event.source_id != candidate.source_id:
                    failed_rows.append(
                        _failure(
                            candidate,
                            "source_id_mismatch",
                            scraped_source_id=event.source_id,
                        )
                    )
                    continue
                if _looks_like_cookie_banner(event.raw_description):
                    failed_rows.append(_failure(candidate, "cookie_still_present"))
                    continue
                missing = _event_missing_fields(event)
                if missing:
                    failed_rows.append(_failure(candidate, "field_missing", missing_fields=missing))
                    continue
                rescued.append((candidate, event))
        finally:
            browser.close()

    return rescued, failed_rows


def _confirm_updates(rescued: list[tuple[Candidate, Event]]) -> tuple[list[str], list[dict[str, Any]]]:
    if not rescued:
        return [], []

    client = _get_client()
    expected_by_id = {candidate.id: candidate for candidate, _ in rescued}
    result = (
        client.table("events")
        .select("id,raw_description,location_name,location_address,business_hours,price_info")
        .in_("id", list(expected_by_id))
        .execute()
    )
    rows_by_id = {row["id"]: row for row in (result.data or [])}

    confirmed_ids: list[str] = []
    failed_rows: list[dict[str, Any]] = []
    for event_id, candidate in expected_by_id.items():
        row = rows_by_id.get(event_id)
        if not row:
            failed_rows.append(_failure(candidate, "not_updated_or_excluded"))
            continue
        if _looks_like_cookie_banner(row.get("raw_description")):
            failed_rows.append(_failure(candidate, "not_updated_or_excluded"))
            continue
        missing = [
            field
            for field in ["location_name", "location_address", "business_hours", "price_info"]
            if not row.get(field)
        ]
        if missing:
            failed_rows.append(_failure(candidate, "not_updated_or_excluded", missing_fields=missing))
            continue
        confirmed_ids.append(event_id)

    return confirmed_ids, failed_rows


def _build_report(
    candidates: list[Candidate],
    reviewed_rows: list[Candidate],
    rescue_ready: list[tuple[Candidate, Event]],
    failed_rows: list[dict[str, Any]],
    confirmed_rescued_ids: list[str] | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in REPORTABLE_STATUSES}
    status_counts["rescue_ready"] = len(rescue_ready)
    for row in failed_rows:
        reason = row.get("reason")
        if reason in status_counts:
            status_counts[reason] += 1

    return {
        "candidate_count": len(candidates),
        "reviewed_rows": [candidate.__dict__ for candidate in reviewed_rows],
        "stop_reason": stop_reason,
        "status_counts": {key: value for key, value in status_counts.items() if value},
        "rescue_ready": [
            {
                "id": candidate.id,
                "source_id": candidate.source_id,
                "source_url": candidate.source_url,
                "db_source_id": candidate.source_id,
                "scraped_source_id": event.source_id,
            }
            for candidate, event in rescue_ready
        ],
        "confirmed_rescued_ids": confirmed_rescued_ids or [],
        "failed_rows": failed_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Scrape and report without writing to Supabase")
    parser.add_argument("--report", help="Write JSON report to this path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    _load_env()

    candidates = _fetch_candidates()
    reviewed_rows = [candidate for candidate in candidates if candidate.annotation_status == "reviewed"]
    if reviewed_rows:
        report = _build_report(
            candidates,
            reviewed_rows,
            [],
            [],
            stop_reason="reviewed_rows_present",
        )
        _write_report(args.report, report)
        LOGGER.error("Reviewed Peatix cookie rows found; refusing automatic rescue: %s", reviewed_rows)
        return 1

    rescue_ready, failed_rows = _scrape_candidates(candidates)
    if args.dry_run:
        report = _build_report(candidates, reviewed_rows, rescue_ready, failed_rows)
        _write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if rescue_ready:
        events = [event for _, event in rescue_ready]
        force_keys = {(event.source_name, event.source_id) for event in events}
        upsert_events(events, force_keys=force_keys)

    confirmed_ids, update_failures = _confirm_updates(rescue_ready)
    failed_rows.extend(update_failures)
    report = _build_report(candidates, reviewed_rows, rescue_ready, failed_rows, confirmed_ids)
    _write_report(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if confirmed_ids or not candidates else 2


if __name__ == "__main__":
    sys.exit(main())
