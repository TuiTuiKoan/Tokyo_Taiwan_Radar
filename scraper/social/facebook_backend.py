"""Facebook fetch backend: public Page posts through an Apify actor.

Meta has no usable API for reading other organisations' public Pages, so this
uses a logged-out posts scraper hosted on Apify. No Facebook account, cookie or
session is involved. The actor id is fixed in code (ACTOR): changing which
third-party actor runs with the Apify token goes through a pull request.

NOT verified against a live run in M1 (a paid token is a human gate). The
field names in ``item_to_post`` come from the public documentation of several
Facebook posts actors (input ``startUrls`` / ``resultsLimit`` /
``onlyPostsNewerThan``; output ``postId`` / ``url`` / ``time`` / ``text``), and
the test fixtures are synthetic. M2 replaces them with a real response.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

from .models import PLATFORM_FACEBOOK, BackendUnavailable, SocialPost, SocialTarget

logger = logging.getLogger(__name__)

ENV_TOKEN = "APIFY_TOKEN"
ACTOR = "apify/facebook-posts-scraper"
DEFAULT_LOOKBACK_HOURS = 26
DEFAULT_MAX_POSTS_PER_TARGET = 5
DEFAULT_MAX_TARGETS_PER_RUN = 20
REQUEST_TIMEOUT = 300
API_BASE = "https://api.apify.com/v2"

_NUMERIC_POST_ID = re.compile(r"^\d{5,25}$")

# (actor, token, actor_input) → list of dataset items
Runner = Callable[[str, str, dict], list]


def _first_str(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return ""


def _parse_time(item: dict) -> Optional[datetime]:
    for key in ("time", "timeCreated", "createdAt", "date"):
        value = item.get(key)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    for key in ("timestamp", "timestampCreated"):
        value = item.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            seconds = value / 1000 if value > 1e11 else value  # tolerate milliseconds
            try:
                return datetime.fromtimestamp(seconds, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
    return None


def _is_facebook_post_url(url: str) -> bool:
    return bool(re.match(r"^https://(?:www\.|m\.)?facebook\.com/[^\s]+$", url))


def stable_post_id(raw_id: str, url: str) -> str:
    """An id that stays the same across runs and actors.

    Facebook exposes both numeric ids and opaque ``pfbid…`` tokens for the same
    post. A numeric id is used as is; anything else is replaced by a hash of
    the permalink without its query string.
    """
    if _NUMERIC_POST_ID.match(raw_id or ""):
        return raw_id
    parts = urlsplit(url)
    canonical = f"{(parts.hostname or '').lower().removeprefix('www.').removeprefix('m.')}{parts.path.rstrip('/')}"
    return "h" + hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def item_to_post(item: Any, target: SocialTarget) -> Optional[SocialPost]:
    """Convert one actor dataset item to a SocialPost, or None."""
    if not isinstance(item, dict):
        return None
    url = _first_str(item, "url", "topLevelUrl", "postUrl")
    created_at = _parse_time(item)
    if not _is_facebook_post_url(url) or created_at is None:
        return None
    post_id = stable_post_id(_first_str(item, "postId", "post_id", "id"), url)
    text = _first_str(item, "text", "message", "caption")

    links: list[str] = []
    for key in ("link", "externalUrl", "sharedLink"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("http") and value not in links:
            links.append(value)
    extra = item.get("textLinks") or item.get("links")
    for value in extra if isinstance(extra, list) else []:
        candidate = value.get("url") if isinstance(value, dict) else value
        if isinstance(candidate, str) and candidate.startswith("http") and candidate not in links:
            links.append(candidate)

    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    author_name = _first_str(item, "pageName") or _first_str(user, "name") or target.name
    return SocialPost(
        platform=PLATFORM_FACEBOOK,
        post_id=post_id,
        url=url,
        text=text,
        created_at=created_at,
        author_handle=target.handle,
        author_name=author_name,
        links=tuple(links),
        is_repost=bool(item.get("isShare") or item.get("sharedPost")),
    )


def run_actor(actor: str, token: str, actor_input: dict) -> list:
    """Run the actor synchronously and return its dataset items."""
    import requests

    response = requests.post(
        f"{API_BASE}/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
        headers={"Authorization": f"Bearer {token}"},  # never in the URL: URLs get logged
        json=actor_input,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


class FacebookBackend:
    """Fetches recent posts of public Pages, one actor run per target."""

    platform = PLATFORM_FACEBOOK

    def __init__(
        self,
        runner: Runner = run_actor,
        *,
        max_posts_per_target: int = DEFAULT_MAX_POSTS_PER_TARGET,
        max_targets_per_run: int = DEFAULT_MAX_TARGETS_PER_RUN,
    ):
        self._runner = runner
        self._max_target = max(1, max_posts_per_target)
        self._max_targets = max(0, max_targets_per_run)
        self.posts_read = 0
        self.targets_run = 0

    @staticmethod
    def _token() -> str:
        token = os.environ.get(ENV_TOKEN, "").strip()
        if not token:
            raise BackendUnavailable(f"{ENV_TOKEN} is not set")
        return token

    def fetch(self, target: SocialTarget, lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> list[SocialPost]:
        """Recent posts for one Page. [] when the per-run target cap is reached."""
        if self.targets_run >= self._max_targets:
            logger.info("facebook: run cap of %d pages reached; skipping %s", self._max_targets, target.handle)
            return []
        token = self._token()
        self.targets_run += 1
        items = self._runner(ACTOR, token, {
            "startUrls": [{"url": target.profile_url}],
            "resultsLimit": self._max_target,
            "onlyPostsNewerThan": f"{max(1, lookback_hours)} hours",
        })
        items = items if isinstance(items, list) else []
        self.posts_read += len(items)
        posts = [item_to_post(item, target) for item in items]
        return [p for p in posts if p is not None][: self._max_target]
