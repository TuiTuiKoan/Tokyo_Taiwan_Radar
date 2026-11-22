"""Data shapes shared by the social-source modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

PLATFORM_FACEBOOK = "facebook"
PLATFORM_X = "x"
PLATFORMS = (PLATFORM_FACEBOOK, PLATFORM_X)

# research_sources.agent_category value → platform
AGENT_CATEGORY_TO_PLATFORM = {
    "facebook_page": PLATFORM_FACEBOOK,
    "x_account": PLATFORM_X,
}

# platform → events.source_name / source_id prefix
SOURCE_NAME = {PLATFORM_FACEBOOK: "facebook_pages", PLATFORM_X: "x_accounts"}
SOURCE_ID_PREFIX = {PLATFORM_FACEBOOK: "fb_", PLATFORM_X: "x_"}


class BackendUnavailable(RuntimeError):
    """A fetch backend is not configured (no token, or its library is missing).

    The pipeline records it as ``RunReport.skipped`` and returns an empty
    result. A configured backend that fails (expired token, quota, HTTP error)
    raises something else and is recorded in ``RunReport.errors``.
    """


@dataclass(frozen=True)
class SocialTarget:
    """One account to follow, loaded from a ``research_sources`` row."""

    platform: str
    handle: str
    name: str
    research_source_id: Optional[int] = None
    user_id: Optional[str] = None       # X numeric id (saves a paid lookup)
    last_post_id: Optional[str] = None  # newest post already seen (M3)

    @property
    def profile_url(self) -> str:
        if self.platform == PLATFORM_X:
            return f"https://x.com/{self.handle}"
        return f"https://www.facebook.com/{self.handle}"


@dataclass(frozen=True)
class SocialPost:
    """One public post, normalised across platforms. All text is untrusted."""

    platform: str
    post_id: str
    url: str
    text: str
    created_at: datetime                 # timezone-aware
    author_handle: str
    author_name: str = ""
    links: tuple[str, ...] = ()          # expanded outbound URLs from the API
    is_repost: bool = False


@dataclass(frozen=True)
class LinkedPage:
    """Text fetched from a page a post links to."""

    url: str    # final URL after redirects, normalised
    title: str
    text: str


@dataclass
class Rejected:
    """A post that did not become an Event, kept for the audit report."""

    post_id: str
    url: str
    reason: str


@dataclass
class RunReport:
    """Outcome of one pipeline run for one platform."""

    platform: str
    events: list = field(default_factory=list)            # list[sources.base.Event]
    insufficient: list[Rejected] = field(default_factory=list)
    flagged: list[Rejected] = field(default_factory=list)   # dropped for an injection pattern
    dropped: dict[str, int] = field(default_factory=dict)  # reason → count
    link_stats: dict[str, dict[str, int]] = field(default_factory=dict)  # host → ok/failed
    skipped: str = ""                                       # backend not configured
    posts_read: int = 0
    pages_fetched: int = 0
    newest_post_ids: dict[str, str] = field(default_factory=dict)  # handle → id
    errors: list[str] = field(default_factory=list)

    def drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1
