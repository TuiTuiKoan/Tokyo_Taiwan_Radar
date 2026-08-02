"""
Vision OCR enrichment pipeline for event poster images.

Fetches events that have image_url set but may have thin data (missing
organizer, incorrect start_date from pubDate fallback), then uses
GPT-4o Vision to extract structured information from the poster image.

Usage:
    python enrich_poster.py [--dry-run] [--event-id UUID] [--max N]

Applies extracted fields only when confidence >= 0.8 and the field
is not already protected by field_corrections.

Guards:
- Blog/Creator Source Thin Content Guard: when raw_description < 100
  chars, organizer is NOT applied from poster (too risky for thin
  content sources like note_creators). Only start_date and location_name
  are applied.
- All applied fields are immediately locked via field_corrections to
  prevent future annotator overwrites.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlsplit

import requests
from dotenv import load_dotenv

from publication_rules import is_pure_publication_record

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_CONFIDENCE_THRESHOLD = 0.8
_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB safety cap
_GUARD_SELECT = "id,event_form,source_name,image_url,raw_description"
_HANMOTO_PLACEHOLDER_RE = re.compile(
    r"^no[-_]?(?:image|cover)(?:[-_][a-z0-9]+)?\.(?:gif|jpe?g|png|webp)$",
    re.IGNORECASE,
)


def _is_placeholder_image_url(image_url: object) -> bool:
    if not isinstance(image_url, str) or not image_url.strip():
        return False
    try:
        parsed = urlsplit(image_url.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if host != "hanmoto.com" and not host.endswith(".hanmoto.com"):
        return False
    filename = unquote(parsed.path).rstrip("/").rsplit("/", 1)[-1]
    return bool(_HANMOTO_PLACEHOLDER_RE.fullmatch(filename))


def _poster_guard_reason(event: dict) -> Optional[str]:
    if is_pure_publication_record(event):
        return "exact pure publication"
    if _is_placeholder_image_url(event.get("image_url")):
        return "known placeholder image"
    return None


def _get_supabase():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(url, key)


def _get_openai():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _fetch_candidates(sb, max_events: Optional[int] = None, event_id: Optional[str] = None):
    """Query events suitable for poster OCR enrichment."""
    q = (
        sb.table("events")
        .select(
            "id,source_name,name_ja,start_date,end_date,location_name,organizer,"
            "annotation_status,image_url,raw_description,event_form"
        )
        .eq("is_active", True)
        .not_.is_("image_url", "null")
        .in_("annotation_status", ["annotated", "reviewed"])
    )
    if event_id:
        q = q.eq("id", event_id)
    if max_events:
        q = q.limit(max_events)
    result = q.execute()
    rows = result.data or []
    candidates = [event for event in rows if not _poster_guard_reason(event)]
    if len(candidates) != len(rows):
        logger.info("  Skipped %d guarded rows (pure publication / placeholder image)",
                    len(rows) - len(candidates))
    return candidates


def _read_current_event(sb, event_id: str) -> Optional[dict]:
    result = (
        sb.table("events")
        .select(_GUARD_SELECT)
        .eq("id", event_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _get_fc_protected_fields(sb, event_id: str) -> set:
    """Return set of field names protected by field_corrections."""
    try:
        res = (
            sb.table("field_corrections")
            .select("field_name")
            .eq("event_id", event_id)
            .execute()
        )
        return {r["field_name"] for r in (res.data or [])}
    except Exception:
        return set()


def _download_image(image_url: str) -> Optional[bytes]:
    """Download image bytes with size cap. Returns None on failure."""
    try:
        resp = requests.get(image_url, timeout=15, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if not any(t in content_type for t in ["image/", "jpeg", "png", "webp"]):
            logger.debug("Non-image content-type: %s for %s", content_type, image_url)
            return None
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_IMAGE_BYTES:
                logger.debug("Image too large (>4MB), skipping: %s", image_url)
                return None
        return b"".join(chunks)
    except Exception as exc:
        logger.debug("Image download failed for %s: %s", image_url, exc)
        return None


_VISION_SYSTEM = """You are an expert at reading Japanese event poster images.
Extract ONLY information that is explicitly visible in the image.
Do NOT infer, guess, or use external knowledge.
Return ONLY valid JSON with this exact schema:
{
  "event_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "time_start": "HH:MM or null",
  "venue": "string or null",
  "organizer": "string or null",
  "admission": "string or null",
  "confidence": 0.0
}
confidence is a float 0.0-1.0 representing how certain you are about the extracted fields overall.
Set to 0.9+ only when the image is clear and dates/venue are unambiguous.
Set null for any field not clearly visible."""


def _extract_from_poster(client, image_bytes: bytes, image_url: str) -> Optional[dict]:
    """Call GPT-4o Vision to extract structured data from poster image.
    Returns parsed dict or None on failure.
    """
    import base64
    # Determine MIME type from URL
    url_lower = image_url.lower()
    if "png" in url_lower:
        mime = "image/png"
    elif "webp" in url_lower:
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    b64 = base64.b64encode(image_bytes).decode()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract event information from this poster. Return JSON only.",
                        },
                    ],
                },
            ],
            max_tokens=400,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("GPT-4o Vision call failed: %s", exc)
        return None


def _lock_fields_via_corrections(sb, event_id: str, update: dict) -> None:
    """Persist extracted corrections to field_corrections table."""
    for field, value in update.items():
        try:
            sb.table("field_corrections").upsert(
                {
                    "event_id": event_id,
                    "field_name": field,
                    "corrected_value": json.dumps(value),
                },
                on_conflict="event_id,field_name",
            ).execute()
        except Exception as exc:
            logger.warning("field_corrections lock failed for %s.%s: %s", event_id, field, exc)


def _apply_if_confident(
    sb,
    event: dict,
    extracted: dict,
    fc_protected: set,
    dry_run: bool = False,
) -> bool:
    """Apply extracted fields to event if confidence is sufficient.

    Returns True if any field was applied (or would be in dry_run).
    Blog/Creator Source Thin Content Guard: for thin-content events
    (raw_description < 100 chars), organizer is NOT applied.
    """
    guard_reason = _poster_guard_reason(event)
    if guard_reason:
        logger.info("  Skip %s - %s", event["id"][:8], guard_reason)
        return False

    current = _read_current_event(sb, event["id"])
    if not current:
        logger.info("  Skip %s - event no longer exists", event["id"][:8])
        return False
    guard_reason = _poster_guard_reason(current)
    if guard_reason:
        logger.info("  Skip %s - %s after Vision", event["id"][:8], guard_reason)
        return False
    event = {**event, **current}

    confidence = float(extracted.get("confidence") or 0)
    if confidence < _CONFIDENCE_THRESHOLD:
        logger.info(
            "  Skip %s \u2014 confidence %.2f < %.2f",
            event["id"][:8], confidence, _CONFIDENCE_THRESHOLD,
        )
        return False

    raw_desc = event.get("raw_description") or ""
    thin = len(raw_desc) < 100  # Blog/Creator Source Thin Content Guard

    update: dict = {}

    if extracted.get("event_date") and "start_date" not in fc_protected:
        try:
            dt = datetime.strptime(extracted["event_date"], "%Y-%m-%d")
            update["start_date"] = dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    if extracted.get("end_date") and "end_date" not in fc_protected:
        try:
            dt = datetime.strptime(extracted["end_date"], "%Y-%m-%d")
            update["end_date"] = dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    if extracted.get("venue") and "location_name" not in fc_protected:
        update["location_name"] = extracted["venue"]

    if (
        not thin
        and extracted.get("organizer")
        and "organizer" not in fc_protected
    ):
        update["organizer"] = extracted["organizer"]
    elif thin and extracted.get("organizer"):
        logger.debug(
            "  Thin content \u2014 skipping organizer '%s' for %s",
            extracted["organizer"], event["id"][:8],
        )

    if not update:
        logger.info("  Skip %s \u2014 no new fields to apply", event["id"][:8])
        return False

    if dry_run:
        logger.info("  [DRY-RUN] Would apply to %s: %s", event["id"][:8], update)
        return True

    sb.table("events").update(update).eq("id", event["id"]).execute()
    _lock_fields_via_corrections(sb, event["id"], update)
    logger.info(
        "  Applied to %s: %s (confidence=%.2f)",
        event["id"][:8], list(update.keys()), confidence,
    )
    return True


def run(
    dry_run: bool = False,
    event_id: Optional[str] = None,
    max_events: Optional[int] = None,
) -> None:
    """Main entry point for the enrich_poster pipeline."""
    sb = _get_supabase()
    openai_client = _get_openai()
    session = requests.Session()
    session.headers.update({"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"})

    candidates = _fetch_candidates(sb, max_events=max_events, event_id=event_id)
    logger.info("[enrich_poster] candidates: %d", len(candidates))

    processed = applied = skipped_confidence = skipped_download = 0

    for event in candidates:
        logger.info(
            "Processing %s: %s",
            event["id"][:8],
            (event.get("name_ja") or "")[:50],
        )
        img_url = event["image_url"]

        image_bytes = _download_image(img_url)
        if not image_bytes:
            logger.debug("  Download failed, skipping")
            skipped_download += 1
            continue

        extracted = _extract_from_poster(openai_client, image_bytes, img_url)
        if not extracted:
            skipped_confidence += 1
            continue

        fc_protected = _get_fc_protected_fields(sb, event["id"])
        was_applied = _apply_if_confident(sb, event, extracted, fc_protected, dry_run=dry_run)

        processed += 1
        if was_applied:
            applied += 1
        else:
            skipped_confidence += 1

    logger.info(
        "[enrich_poster] processed=%d applied=%d skipped(confidence)=%d skipped(download)=%d",
        processed, applied, skipped_confidence, skipped_download,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vision OCR enrichment for event poster images")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be applied without writing to DB")
    parser.add_argument("--event-id", metavar="UUID", help="Process a single event by UUID")
    parser.add_argument("--max", type=int, metavar="N", help="Process at most N events")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(dry_run=args.dry_run, event_id=args.event_id, max_events=args.max)
