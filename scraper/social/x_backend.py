"""X (Twitter) fetch backend: official API v2, app-only Bearer Token.

Reads ``GET /2/users/:id/tweets`` for each target, excluding retweets and
replies. X bills per post read, so every call is bounded by a per-target and a
per-run cap. Response → SocialPost conversion is a pure function over the
API's JSON so it can be tested from fixtures.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from .models import PLATFORM_X, BackendUnavailable, SocialPost, SocialTarget

logger = logging.getLogger(__name__)

ENV_BEARER_TOKEN = "X_BEARER_TOKEN"
DEFAULT_MAX_POSTS_PER_RUN = 30   # ≈ USD 4.5 a month at one run a day
DEFAULT_MAX_POSTS_PER_TARGET = 10
API_MIN_PAGE = 5     # the endpoint rejects max_results below 5
API_MAX_PAGE = 100
COST_PER_POST_USD = 0.005
COST_PER_USER_LOOKUP_USD = 0.010

DEFAULT_LOOKBACK_HOURS = 26      # one daily run plus slack; a post read on two UTC days is billed twice
_TWEET_FIELDS = ["created_at", "entities", "note_tweet", "referenced_tweets"]
_MEDIA_HOSTS = ("pic.x.com", "pic.twitter.com")


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_media_link(url: str) -> bool:
    lowered = url.lower()
    return any(host in lowered for host in _MEDIA_HOSTS) or "/photo/" in lowered or "/video/" in lowered


def tweet_to_post(tweet: Any, target: SocialTarget) -> Optional[SocialPost]:
    """Convert one API v2 tweet object (JSON dict) to a SocialPost, or None."""
    if not isinstance(tweet, dict):
        return None
    post_id = tweet.get("id")
    created_at = _parse_time(tweet.get("created_at"))
    if not isinstance(post_id, str) or not post_id.isdigit() or created_at is None:
        return None

    # Posts over 280 characters carry the full text in note_tweet.
    note = tweet.get("note_tweet") if isinstance(tweet.get("note_tweet"), dict) else {}
    text = note.get("text") if isinstance(note.get("text"), str) else tweet.get("text")
    text = text if isinstance(text, str) else ""

    links: list[str] = []
    for source in (note.get("entities"), tweet.get("entities")):
        urls = source.get("urls") if isinstance(source, dict) else None
        for item in urls if isinstance(urls, list) else []:
            if not isinstance(item, dict):
                continue
            url = item.get("unwound_url") or item.get("expanded_url")
            if isinstance(url, str) and url and not _is_media_link(url) and url not in links:
                links.append(url)

    referenced = tweet.get("referenced_tweets")
    is_repost = any(
        isinstance(ref, dict) and ref.get("type") == "retweeted"
        for ref in (referenced if isinstance(referenced, list) else [])
    )
    return SocialPost(
        platform=PLATFORM_X,
        post_id=post_id,
        url=f"https://x.com/{target.handle}/status/{post_id}",
        text=text.strip(),
        created_at=created_at,
        author_handle=target.handle,
        author_name=target.name,
        links=tuple(links),
        is_repost=is_repost,
    )


def posts_from_response(response: Any, target: SocialTarget) -> list[SocialPost]:
    """All usable posts in one ``users/:id/tweets`` JSON response."""
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    posts = [tweet_to_post(t, target) for t in (data if isinstance(data, list) else [])]
    return [p for p in posts if p is not None]


class XBackend:
    """Fetches recent posts for X targets within a per-run budget."""

    platform = PLATFORM_X

    def __init__(
        self,
        client: Any = None,
        *,
        max_posts_per_run: int = DEFAULT_MAX_POSTS_PER_RUN,
        max_posts_per_target: int = DEFAULT_MAX_POSTS_PER_TARGET,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._client = client
        self._max_run = max(0, max_posts_per_run)
        self._max_target = max(1, max_posts_per_target)
        self._now = now
        self.posts_read = 0
        self.user_lookups = 0

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        token = os.environ.get(ENV_BEARER_TOKEN, "").strip()
        if not token:
            raise BackendUnavailable(f"{ENV_BEARER_TOKEN} is not set")
        try:
            import tweepy
        except ImportError as exc:
            raise BackendUnavailable("tweepy is not installed") from exc
        # return_type=dict gives the API's JSON, which posts_from_response reads.
        self._client = tweepy.Client(bearer_token=token, return_type=dict, wait_on_rate_limit=False)
        return self._client

    def estimated_cost_usd(self) -> float:
        return round(self.posts_read * COST_PER_POST_USD + self.user_lookups * COST_PER_USER_LOOKUP_USD, 4)

    def _user_id(self, client: Any, target: SocialTarget) -> Optional[str]:
        if target.user_id:
            return target.user_id
        self.user_lookups += 1
        response = client.get_user(username=target.handle, user_auth=False)
        data = response.get("data") if isinstance(response, dict) else None
        user_id = data.get("id") if isinstance(data, dict) else None
        if isinstance(user_id, str) and user_id.isdigit():
            logger.info(
                "x: looked up @%s → id %s; store it as source_profile.x_user_id to skip this paid lookup",
                target.handle, user_id,
            )
            return user_id
        logger.warning("x: no user id for @%s", target.handle)
        return None

    def fetch(self, target: SocialTarget, lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> list[SocialPost]:
        """Recent original posts for one target. [] when the budget is spent."""
        remaining = self._max_run - self.posts_read
        # The endpoint returns (and bills) at least API_MIN_PAGE posts, so stop
        # while a full minimum page still fits in the budget.
        if remaining < API_MIN_PAGE:
            logger.info("x: run budget of %d posts reached; skipping @%s", self._max_run, target.handle)
            return []
        client = self._get_client()
        user_id = self._user_id(client, target)
        if not user_id:
            return []
        want = min(self._max_target, remaining)
        params: dict[str, Any] = {
            "max_results": max(API_MIN_PAGE, min(API_MAX_PAGE, want)),
            "exclude": ["retweets", "replies"],
            "tweet_fields": _TWEET_FIELDS,
            "user_auth": False,
        }
        if target.last_post_id:
            params["since_id"] = target.last_post_id
        else:
            params["start_time"] = (self._now() - timedelta(hours=max(1, lookback_hours))).replace(microsecond=0)
        response = client.get_users_tweets(user_id, **params)
        returned = response.get("data") if isinstance(response, dict) else None
        # X bills for every post returned, including any beyond ``want``.
        self.posts_read += len(returned) if isinstance(returned, list) else 0
        return posts_from_response(response, target)[:want]
