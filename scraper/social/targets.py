"""Load the accounts to follow from ``research_sources``.

A row is a target when ``agent_category`` is ``facebook_page`` or
``x_account`` and ``status`` is ``implemented``. The handle comes from
``source_profile.handle`` or, failing that, from the row's ``url``.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Optional
from urllib.parse import parse_qs, urlsplit

from .models import (
    AGENT_CATEGORY_TO_PLATFORM,
    PLATFORM_FACEBOOK,
    PLATFORM_X,
    SocialTarget,
)

logger = logging.getLogger(__name__)

_X_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_FB_HANDLE = re.compile(r"^[A-Za-z0-9.\-]{2,80}$")
_NUMERIC_ID = re.compile(r"^\d{5,25}$")

_X_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com"}
_FB_HOSTS = {"facebook.com", "m.facebook.com", "fb.com"}

# First path segments that are site features, not account names.
_X_RESERVED = {
    "home", "explore", "search", "i", "intent", "share", "hashtag", "settings",
    "notifications", "messages", "compose", "login", "signup", "tos", "privacy",
}
_FB_RESERVED = {
    "events", "groups", "share", "sharer", "watch", "photo", "photos", "videos",
    "reel", "reels", "story", "stories", "hashtag", "login", "pages", "people",
    "marketplace", "gaming", "help", "policies", "permalink.php", "plugins",
    "dialog", "l.php",
}


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def clean_handle(platform: str, raw: Any) -> Optional[str]:
    """Return a validated handle, or None."""
    if not isinstance(raw, str):
        return None
    handle = raw.strip().lstrip("@").strip("/")
    if platform == PLATFORM_X:
        if _X_HANDLE.match(handle) and handle.lower() not in _X_RESERVED:
            return handle
        return None
    if platform == PLATFORM_FACEBOOK:
        if handle.lower() in _FB_RESERVED:
            return None
        if _NUMERIC_ID.match(handle) or _FB_HANDLE.match(handle):
            return handle
    return None


def handle_from_url(platform: str, url: Any) -> Optional[str]:
    """Account handle from a profile URL of the given platform, or None."""
    if not isinstance(url, str) or not url.strip():
        return None
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return None
    host = _host(url)
    segments = [s for s in parts.path.split("/") if s]
    if platform == PLATFORM_X:
        if host not in _X_HOSTS or not segments:
            return None
        return clean_handle(platform, segments[0])
    if platform == PLATFORM_FACEBOOK:
        if host not in _FB_HOSTS or not segments:
            return None
        if segments[0] == "profile.php":
            ids = parse_qs(parts.query).get("id") or []
            return ids[0] if ids and _NUMERIC_ID.match(ids[0]) else None
        if segments[0] == "people" and len(segments) >= 3:
            return segments[2] if _NUMERIC_ID.match(segments[2]) else None
        return clean_handle(platform, segments[0])
    return None


def _str_or_none(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def target_from_row(row: dict[str, Any]) -> Optional[SocialTarget]:
    """Build a target from one ``research_sources`` row, or None if unusable."""
    platform = AGENT_CATEGORY_TO_PLATFORM.get(row.get("agent_category") or "")
    if not platform:
        return None
    profile = row.get("source_profile")
    profile = profile if isinstance(profile, dict) else {}
    handle = clean_handle(platform, profile.get("handle")) or handle_from_url(platform, row.get("url"))
    if not handle:
        logger.warning(
            "social target skipped: research_sources id=%s has no valid %s handle",
            row.get("id"), platform,
        )
        return None
    user_id = _str_or_none(profile.get("x_user_id"))
    if user_id and not _NUMERIC_ID.match(user_id):
        user_id = None
    last_post_id = _str_or_none(profile.get("last_post_id"))
    if last_post_id and not _NUMERIC_ID.match(last_post_id):
        last_post_id = None
    name = row.get("name") if isinstance(row.get("name"), str) and row["name"].strip() else handle
    rid = row.get("id")
    return SocialTarget(
        platform=platform,
        handle=handle,
        name=name.strip(),
        research_source_id=rid if isinstance(rid, int) and not isinstance(rid, bool) else None,
        user_id=user_id,
        last_post_id=last_post_id,
    )


def targets_from_rows(rows: Iterable[dict[str, Any]], platform: Optional[str] = None) -> list[SocialTarget]:
    """Valid, de-duplicated targets (first row wins per platform + handle)."""
    seen: set[tuple[str, str]] = set()
    targets: list[SocialTarget] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        target = target_from_row(row)
        if target is None or (platform and target.platform != platform):
            continue
        key = (target.platform, target.handle.lower())
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def load_targets(platform: Optional[str] = None, client: Any = None) -> list[SocialTarget]:
    """Read implemented social targets from the database (read-only).

    Returns [] when the database is unavailable (dry-run or missing env),
    like ``PeatixScraper._load_db_organizers``.
    """
    try:
        if client is None:
            from database import _get_client  # deferred: not needed for fixtures
            client = _get_client()
        result = (
            client.table("research_sources")
            .select("id, name, url, agent_category, source_profile")
            .eq("status", "implemented")
            .in_("agent_category", sorted(AGENT_CATEGORY_TO_PLATFORM))
            .execute()
        )
    except Exception as exc:
        logger.warning("social targets not loaded (DB unavailable): %s", type(exc).__name__)
        return []
    return targets_from_rows(result.data or [], platform)
