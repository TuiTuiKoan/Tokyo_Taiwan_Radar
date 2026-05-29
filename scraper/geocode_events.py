"""
Geocode events.location_address → latitude / longitude.

Strategy:
  1. Cache hit: if event has venue_id and venues table already has lat/lng → copy, zero API calls.
  2. Yahoo! JAPAN Geocoder API (requires YAHOO_GEOCODER_APPID in .env).
  3. Fallback: Nominatim (OSM) — 1 req/s rate-limit, no key required.

Write-back:
  - events.latitude / events.longitude (never overwrites existing non-NULL values)
  - venues.latitude / venues.longitude / venues.address (opportunistic, skipped if field_corrections lock exists)

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
import urllib.parse
from typing import Optional

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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
# Venue cache helpers
# ---------------------------------------------------------------------------

def _get_venue_coords(sb: Client, venue_id: str) -> Optional[tuple[float, float]]:
    """Return (lat, lng) from venues table if already geocoded."""
    row = sb.table("venues").select("latitude, longitude").eq("id", venue_id).maybe_single().execute()
    if row.data and row.data.get("latitude") is not None and row.data.get("longitude") is not None:
        return float(row.data["latitude"]), float(row.data["longitude"])
    return None


def _has_field_correction_lock(sb: Client, venue_id: str) -> bool:
    """Check if field_corrections has a lat/lng lock for this venue."""
    rows = (
        sb.table("field_corrections")
        .select("id", count="exact", head=True)
        .eq("source_id", venue_id)
        .in_("field_name", ["latitude", "longitude"])
        .execute()
    )
    return (rows.count or 0) > 0


def _opportunistic_venue_backfill(
    sb: Client,
    venue_id: str,
    lat: float,
    lng: float,
    address: str,
    dry_run: bool,
) -> None:
    """Write lat/lng (and address if empty) back to venues, unless locked by field_corrections."""
    if _has_field_correction_lock(sb, venue_id):
        logger.warning("Skipping venue %s — field_corrections lock exists", venue_id)
        return

    venue = sb.table("venues").select("latitude, longitude, address").eq("id", venue_id).maybe_single().execute()
    if not venue.data:
        return

    update: dict = {}
    if venue.data.get("latitude") is None:
        update["latitude"] = lat
    if venue.data.get("longitude") is None:
        update["longitude"] = lng
    if not venue.data.get("address"):
        update["address"] = address

    if update:
        if dry_run:
            logger.info("[DRY-RUN] Would update venue %s: %s", venue_id, update)
        else:
            sb.table("venues").update(update).eq("id", venue_id).execute()
            logger.info("Back-filled venue %s: %s", venue_id, list(update.keys()))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool, limit: int) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")

    yahoo_appid = os.environ.get("YAHOO_GEOCODER_APPID") or None
    if not yahoo_appid:
        logger.info("YAHOO_GEOCODER_APPID not set — using Nominatim only (slower)")

    sb = create_client(url, key)

    # Fetch candidates: active, has address, no lat/lng yet, exclude online-only.
    # Try to filter latitude IS NULL at DB level first (requires migration 077).
    # If the column doesn't exist yet, fall back to fetching without that filter
    # and post-filtering in Python (useful for --dry-run before migration is applied).
    try:
        rows = (
            sb.table("events")
            .select("id, source_id, location_address, venue_id, latitude")
            .eq("is_active", True)
            .not_.is_("location_address", "null")
            .is_("latitude", "null")
            .neq("location_name", "オンライン")
            .limit(limit)
            .execute()
        )
        candidates = rows.data or []
    except Exception as exc:
        if "does not exist" in str(exc):
            logger.warning(
                "Column events.latitude not found — migration 077 not yet applied. "
                "Running in pre-migration mode (no NULL filter, first %d active events).",
                limit,
            )
            rows = (
                sb.table("events")
                .select("id, source_id, location_address, venue_id")
                .eq("is_active", True)
                .not_.is_("location_address", "null")
                .neq("location_name", "オンライン")
                .limit(limit)
                .execute()
            )
            # Treat all as needing geocoding (migration not applied yet)
            candidates = [dict(e, latitude=None) for e in (rows.data or [])]
        else:
            raise
    logger.info("Found %d candidate events to geocode (limit=%d)", len(candidates), limit)

    geocoded = 0
    cache_hits = 0
    failed = 0

    for event in candidates:
        event_id = event["id"]
        source_id = event.get("source_id", event_id)
        address = event["location_address"]
        venue_id = event.get("venue_id")

        # A2: Cache hit — copy from venues table
        if venue_id:
            cached = _get_venue_coords(sb, venue_id)
            if cached:
                lat, lng = cached
                if dry_run:
                    logger.info(
                        "[DRY-RUN] [CACHE] %s | %s → lat=%.6f lng=%.6f",
                        source_id, address, lat, lng,
                    )
                else:
                    sb.table("events").update({"latitude": lat, "longitude": lng}).eq("id", event_id).execute()
                    logger.info("[CACHE] %s | %s → lat=%.6f lng=%.6f", source_id, address, lat, lng)
                cache_hits += 1
                geocoded += 1
                continue

        # A3: Geocode via Yahoo! / Nominatim
        result = geocode_address(address, yahoo_appid)
        if not result:
            logger.warning("[FAIL] %s | %s — no result from any geocoder", source_id, address)
            failed += 1
            continue

        lat, lng = result
        if dry_run:
            logger.info(
                "[DRY-RUN] [API] %s | %s → lat=%.6f lng=%.6f",
                source_id, address, lat, lng,
            )
        else:
            # A4: Write events.latitude / longitude (never overwrite existing non-NULL)
            sb.table("events").update({"latitude": lat, "longitude": lng}).eq("id", event_id).is_("latitude", "null").execute()
            logger.info("[API] %s | %s → lat=%.6f lng=%.6f", source_id, address, lat, lng)

            # A4: Opportunistic venue backfill
            if venue_id:
                _opportunistic_venue_backfill(sb, venue_id, lat, lng, address, dry_run=False)

        geocoded += 1

    logger.info(
        "Done. geocoded=%d (cache_hits=%d api=%d) failed=%d",
        geocoded, cache_hits, geocoded - cache_hits, failed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode events.location_address → lat/lng")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    parser.add_argument("--limit", type=int, default=50, help="Max events to process (default: 50)")
    args = parser.parse_args()

    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
