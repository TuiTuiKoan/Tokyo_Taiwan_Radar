"""
X (Twitter) auto-post — picks one upcoming Taiwan event from Supabase
and posts a Japanese tweet linking to its detail page on tokyotaiwanradar.com.

Usage:
    python x_post.py                 # post one tweet (production)
    python x_post.py --dry-run       # render tweet text but do not post
    python x_post.py --event-id <id> # post a specific event (manual override)

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (read events + app_settings)
    X_API_KEY, X_API_SECRET                  (Twitter API v1 consumer keys)
    X_ACCESS_TOKEN, X_ACCESS_SECRET          (OAuth1.0a user tokens for posting)
    NEXT_PUBLIC_SITE_URL                     (default: https://tokyotaiwanradar.com)

Selection strategy:
    1. Events with start_date in next 14 days, annotated/reviewed, no parent.
    2. Exclude events posted in the last 60 days (tracked in app_settings.x_post).
    3. Prefer events with a Japanese selection_reason and clear venue.
    4. Random pick among the top 12 candidates by closeness of start_date.

Tweet length budget:
    280 chars total - 23 (t.co URL) - 2 (newlines around URL) ≈ 255 free chars.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

JST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_SITE_URL = "https://tokyotaiwanradar.com"
APP_SETTINGS_KEY = "x_post"
HISTORY_RETENTION = 200  # keep last 200 posted event ids
COOLDOWN_DAYS = 60       # do not re-post the same event within this window
TWEET_MAX = 280
URL_LEN = 23             # t.co length


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)


def _load_post_history(sb: Client) -> dict[str, Any]:
    """Read app_settings.x_post → dict with `posted` (list of {id, at})."""
    res = (
        sb.table("app_settings")
        .select("value")
        .eq("key", APP_SETTINGS_KEY)
        .maybe_single()
        .execute()
    )
    if res and res.data and isinstance(res.data.get("value"), dict):
        return res.data["value"]
    return {"posted": []}


def _save_post_history(sb: Client, history: dict[str, Any]) -> None:
    sb.table("app_settings").upsert(
        {"key": APP_SETTINGS_KEY, "value": history},
        on_conflict="key",
    ).execute()


def _excluded_event_ids(history: dict[str, Any]) -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    excluded: set[str] = set()
    for entry in history.get("posted", []):
        try:
            at = datetime.fromisoformat(entry["at"].replace("Z", "+00:00"))
            if at >= cutoff:
                excluded.add(entry["id"])
        except (KeyError, ValueError):
            continue
    return excluded


# ---------------------------------------------------------------------------
# Event selection
# ---------------------------------------------------------------------------

def _fetch_candidates(sb: Client) -> list[dict]:
    now = datetime.now(JST)
    start_from = now.isoformat()
    start_to = (now + timedelta(days=14)).isoformat()
    res = (
        sb.table("events")
        .select(
            "id,name_ja,name_zh,name_en,start_date,end_date,category,"
            "location_name,location_address,selection_reason,is_paid,source_name"
        )
        .eq("is_active", True)
        .is_("parent_event_id", "null")
        .neq("source_name", "gguide_tv")
        .in_("annotation_status", ["annotated", "reviewed"])
        .gte("start_date", start_from)
        .lte("start_date", start_to)
        .order("start_date")
        .limit(40)
        .execute()
    )
    return res.data or []


def _fetch_event_by_id(sb: Client, event_id: str) -> dict | None:
    res = (
        sb.table("events")
        .select(
            "id,name_ja,name_zh,name_en,start_date,end_date,category,"
            "location_name,location_address,selection_reason,is_paid,source_name"
        )
        .eq("id", event_id)
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def _pick_event(candidates: list[dict], excluded: set[str]) -> dict | None:
    pool = [e for e in candidates if e["id"] not in excluded]
    if not pool:
        return None
    # Prefer events with non-null selection_reason and venue
    scored = []
    for e in pool:
        score = 0
        if e.get("selection_reason"):
            score += 2
        if e.get("location_name"):
            score += 1
        if (e.get("name_ja") or "").strip():
            score += 1
        scored.append((score, e))
    scored.sort(key=lambda t: -t[0])
    top = [e for _, e in scored[:12]]
    return random.choice(top)


# ---------------------------------------------------------------------------
# Tweet rendering
# ---------------------------------------------------------------------------

def _parse_selection_reason_ja(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed.get("ja") or parsed.get("zh") or parsed.get("en")
    except (json.JSONDecodeError, TypeError):
        pass
    return raw if isinstance(raw, str) else None


def _format_date_range(start: str | None, end: str | None) -> str:
    if not start:
        return ""
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(JST)
    except ValueError:
        return ""
    if end and end != start:
        try:
            e = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(JST)
            if e.date() == s.date():
                return f"{s.month}/{s.day}"
            if (s.year, s.month) == (e.year, e.month):
                return f"{s.month}/{s.day}〜{e.day}"
            return f"{s.month}/{s.day}〜{e.month}/{e.day}"
        except ValueError:
            pass
    return f"{s.month}/{s.day}"


def _truncate_for_tweet(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def render_tweet(event: dict, site_url: str) -> str:
    """Build the tweet text. Returns the full string including the URL.

    Guarantees Twitter-weighted length ≤ TWEET_MAX (URL counts as URL_LEN).
    """
    name = (
        event.get("name_ja")
        or event.get("name_zh")
        or event.get("name_en")
        or "(無題)"
    )
    date_str = _format_date_range(event.get("start_date"), event.get("end_date"))
    venue = event.get("location_name") or ""
    venue = re.sub(r"\s+", " ", venue).strip()
    reason = _parse_selection_reason_ja(event.get("selection_reason"))
    url = f"{site_url}/ja/events/{event['id']}"

    header = "🇹🇼 開催間近の台湾イベント"

    meta_parts: list[str] = []
    if date_str:
        meta_parts.append(f"📅 {date_str}")
    if venue:
        meta_parts.append(f"📍 {_truncate_for_tweet(venue, 30)}")
    meta_line = "　".join(meta_parts)

    def _compose(name_str: str, reason_str: str) -> tuple[str, int]:
        lines = [header, f"「{name_str}」"]
        if meta_line:
            lines.append(meta_line)
        if reason_str:
            lines.append(reason_str)
        lines.append(url)
        text = "\n".join(lines)
        # Twitter weight: real length minus actual URL length plus URL_LEN
        weight = len(text) - len(url) + URL_LEN
        return text, weight

    # Step 1: try with full name + full reason
    short_name = name
    short_reason = reason or ""
    text, weight = _compose(short_name, short_reason)

    # Step 2: trim reason until it fits
    while weight > TWEET_MAX and short_reason:
        new_len = max(0, len(short_reason) - (weight - TWEET_MAX) - 1)
        if new_len < 12:
            short_reason = ""
        else:
            short_reason = _truncate_for_tweet(short_reason, new_len)
        text, weight = _compose(short_name, short_reason)

    # Step 3: trim name until it fits (keep at least 8 chars + ellipsis)
    while weight > TWEET_MAX and len(short_name) > 8:
        new_len = max(8, len(short_name) - (weight - TWEET_MAX) - 1)
        short_name = _truncate_for_tweet(short_name, new_len)
        text, weight = _compose(short_name, short_reason)

    return text


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------

def _post_to_x(text: str) -> str:
    """Post to X via tweepy (OAuth1.0a). Returns the tweet id."""
    try:
        import tweepy  # local import so dry-run does not require the dep
    except ImportError as e:
        raise RuntimeError("tweepy is required to post. Run: pip install tweepy") from e

    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")
    if not all([api_key, api_secret, access_token, access_secret]):
        raise RuntimeError(
            "X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET are required"
        )

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    resp = client.create_tweet(text=text)
    return str(resp.data["id"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, event_id: str | None = None) -> int:
    site_url = (os.environ.get("NEXT_PUBLIC_SITE_URL") or DEFAULT_SITE_URL).rstrip("/")
    sb = _get_supabase()

    history = _load_post_history(sb)

    if event_id:
        event = _fetch_event_by_id(sb, event_id)
        if not event:
            logger.error("Event %s not found", event_id)
            return 2
        logger.info("Manual override: using event %s", event_id)
    else:
        candidates = _fetch_candidates(sb)
        if not candidates:
            logger.warning("No upcoming events found in the next 14 days")
            return 0
        excluded = _excluded_event_ids(history)
        logger.info("Found %d candidates, %d excluded by cooldown", len(candidates), len(excluded))
        event = _pick_event(candidates, excluded)
        if not event:
            logger.warning("All candidates were posted recently — skipping")
            return 0

    text = render_tweet(event, site_url)
    logger.info(
        "Selected event id=%s name_ja=%r length=%d",
        event["id"], (event.get("name_ja") or "")[:40], len(text),
    )
    print("---- TWEET PREVIEW ----")
    print(text)
    print(f"---- ({len(text)} chars) ----")

    if dry_run:
        logger.info("--dry-run: not posting")
        return 0

    tweet_id = _post_to_x(text)
    logger.info("Posted tweet id=%s", tweet_id)

    # Update history
    history.setdefault("posted", []).append({
        "id": event["id"],
        "at": datetime.now(timezone.utc).isoformat(),
        "tweet_id": tweet_id,
    })
    history["posted"] = history["posted"][-HISTORY_RETENTION:]
    _save_post_history(sb, history)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Post one upcoming event to X")
    p.add_argument("--dry-run", action="store_true", help="Render text but do not post")
    p.add_argument("--event-id", type=str, default=None, help="Force a specific event id")
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()
    sys.exit(run(dry_run=args.dry_run, event_id=args.event_id))
