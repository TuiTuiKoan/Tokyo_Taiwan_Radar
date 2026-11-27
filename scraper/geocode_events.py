"""
Geocode events.location_address → latitude / longitude.

Strategy:
  1. Yahoo! JAPAN Geocoder API (requires YAHOO_GEOCODER_APPID in .env).
  2. Fallback: Nominatim (OSM) — 1 req/s rate-limit, no key required.

Candidates: active events without coordinates whose address is street-level
(address_quality.grade_address), upcoming events first.

Write-back: events.latitude / events.longitude only, never overwriting a value.
The venues table is not written (#706): the former venue back-fill copied event
addresses into venues.address unchecked. Venue coordinates have no reader yet;
when one appears they belong in #372, geocoded from the authoritative address.

Failed addresses are retried on the next run; there is no negative cache.

Usage:
    cd scraper
    python geocode_events.py --dry-run --limit 5   # preview, no DB writes
    python geocode_events.py --limit 50            # production run

# Phase A0 coverage measurement results (2026-05-30):
#   量測一 (has address ratio):    576 / 636 = 0.9057
#   量測二 (has venue_id ratio):   371 / 636 = 0.5833
#   量測三 (prefecture only count): 17
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

from address_quality import STREET, grade_address
from db_paging import fetch_all
from publication_rules import is_pure_publication_in_db, partition_pure_publications

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
NOMINATIM_UA = "TokyoTaiwanRadar/1.0 (geocode@tokyotaiwanradar.com)"
YAHOO_BASE = "https://map.yahooapis.jp/geocode/V1/geoCoder"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"


# ---------------------------------------------------------------------------
# Geocoding helpers
# ---------------------------------------------------------------------------

def _yahoo_geocode(address: str, appid: str) -> Optional[tuple[float, float]]:
    """Call Yahoo! JAPAN Geocoder API. Returns (lat, lng) or None."""
    params = {
        "query": address,
        "appid": appid,
        "output": "json",
        "count": "1",
    }
    try:
        resp = requests.get(YAHOO_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("Feature") or []
        if not features:
            return None
        coords = features[0].get("Geometry", {}).get("Coordinates", "")
        if not coords:
            return None
        # Format: "lng,lat"
        parts = coords.split(",")
        if len(parts) != 2:
            return None
        lng, lat = float(parts[0]), float(parts[1])
        return lat, lng
    except Exception as exc:
        logger.warning("Yahoo geocoder error for %r: %s", address, exc)
        return None


def _nominatim_geocode(address: str) -> Optional[tuple[float, float]]:
    """Call Nominatim (OSM) geocoder. Returns (lat, lng) or None. Caller must sleep 1s after."""
    params = {
        "q": address,
        "format": "json",
        "limit": "1",
        "accept-language": "ja",
    }
    headers = {"User-Agent": NOMINATIM_UA}
    try:
        resp = requests.get(NOMINATIM_BASE, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        logger.warning("Nominatim error for %r: %s", address, exc)
        return None


def geocode_address(address: str, yahoo_appid: Optional[str]) -> Optional[tuple[float, float]]:
    """Geocode an address using Yahoo! first, then Nominatim as fallback."""
    if yahoo_appid:
        result = _yahoo_geocode(address, yahoo_appid)
        if result:
            return result
        logger.info("Yahoo miss → trying Nominatim for %r", address)
    else:
        logger.debug("No YAHOO_GEOCODER_APPID, using Nominatim only")

    result = _nominatim_geocode(address)
    time.sleep(1)  # Nominatim rate-limit: 1 req/s
    return result


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

CANDIDATE_COLUMNS = (
    "id, source_id, location_name, location_address, latitude, event_form, "
    "start_date, end_date"
)


def is_geocodable(event: dict) -> bool:
    """Only street-level Japanese addresses are worth an API call.

    A town- or ward-level address resolves to the area's centre, which is not a
    location anyone can walk to.
    """
    name = event.get("location_name") or ""
    if "オンライン" in name:
        return False
    return grade_address(event.get("location_address"), name) == STREET


def order_candidates(events: list[dict], today: str) -> list[dict]:
    """Upcoming events first (soonest first), then past events (newest first).

    Without an order the same failing addresses came back first every day.
    """
    def last_day(e: dict) -> str:
        return str(e.get("end_date") or e.get("start_date") or "")

    upcoming = [e for e in events if last_day(e)[:10] >= today]
    past = [e for e in events if last_day(e)[:10] < today]
    upcoming.sort(key=lambda e: (str(e.get("start_date") or ""), e["id"]))
    past.sort(key=lambda e: (str(e.get("start_date") or ""), e["id"]), reverse=True)
    return upcoming + past


def fetch_candidates(sb: Client) -> list[dict]:
    return fetch_all(lambda: (
        sb.table("events")
        .select(CANDIDATE_COLUMNS)
        .eq("is_active", True)
        .not_.is_("location_address", "null")
        .is_("latitude", "null")
        .order("id")
    ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def geocode_one(sb: Client, event: dict, yahoo_appid: Optional[str], dry_run: bool) -> str:
    """Geocode one event. Returns "api" or "failed"."""
    event_id = event["id"]
    label = event.get("source_id") or event_id
    address = event["location_address"]

    result = geocode_address(address, yahoo_appid)
    if not result:
        logger.warning("[FAIL] %s | %s — no result from any geocoder", label, address)
        return "failed"
    lat, lng = result

    if dry_run:
        logger.info("[DRY-RUN] %s | %s → lat=%.6f lng=%.6f", label, address, lat, lng)
        return "api"
    if is_pure_publication_in_db(sb, event_id):
        logger.warning("SKIP pure publication (re-check): %s", event_id[:8])
        return "failed"
    (
        sb.table("events")
        .update({"latitude": lat, "longitude": lng})
        .eq("id", event_id)
        .is_("latitude", "null")
        .execute()
    )
    logger.info("%s | %s → lat=%.6f lng=%.6f", label, address, lat, lng)
    return "api"


def run(dry_run: bool, limit: int) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")

    yahoo_appid = os.environ.get("YAHOO_GEOCODER_APPID") or None
    if not yahoo_appid:
        logger.info("YAHOO_GEOCODER_APPID not set — using Nominatim only (slower)")

    sb = create_client(url, key)
    today = datetime.now(JST).date().isoformat()

    candidates, publications = partition_pure_publications(fetch_candidates(sb))
    if publications:
        logger.info("Skipped %d pure publication events (no venue by policy)", len(publications))
    geocodable = [e for e in candidates if is_geocodable(e)]
    logger.info(
        "Found %d events without coordinates; %d have a street-level address (limit=%d)",
        len(candidates), len(geocodable), limit,
    )
    batch = order_candidates(geocodable, today)[:limit] if limit > 0 else order_candidates(geocodable, today)

    counts = {"api": 0, "failed": 0, "error": 0}
    for event in batch:
        try:
            counts[geocode_one(sb, event, yahoo_appid, dry_run)] += 1
        except Exception as exc:  # one bad row must not stop the batch
            logger.warning("[ERROR] %s — %s", event["id"][:8], exc)
            counts["error"] += 1

    logger.info("Done. geocoded=%d failed=%d errors=%d", counts["api"], counts["failed"], counts["error"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode events.location_address → lat/lng")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    parser.add_argument("--limit", type=int, default=50, help="Max events to process (default: 50)")
    args = parser.parse_args()

    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
