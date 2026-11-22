"""Posts → Events: filter, enrich from links, and build pipeline Events.

Nothing here writes to the database. The Events are meant for the existing
daily pipeline (merger → annotator → enrich), which extracts dates, venue,
names and categories; this module only decides which posts are worth it and
assembles the raw text the annotator reads.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Iterable, Optional, Protocol

from . import filters
from .enrich import INJECTION_BLOCK_SEVERITY, LinkEnricher
from .models import (
    SOURCE_ID_PREFIX,
    SOURCE_NAME,
    BackendUnavailable,
    LinkedPage,
    Rejected,
    RunReport,
    SocialPost,
    SocialTarget,
)

logger = logging.getLogger(__name__)

MAX_TITLE_CHARS = 100
MAX_POST_CHARS = 5000
DEFAULT_LOOKBACK_HOURS = 26
# One account cannot add more than this many events in a run; the rest are
# held for the audit. Limits the damage of a hijacked or runaway account.
MAX_EVENTS_PER_TARGET = 5
_URL = re.compile(r"https?://\S+")
_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[一-鿿]")


class Backend(Protocol):
    platform: str
    posts_read: int

    def fetch(self, target: SocialTarget, lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> list[SocialPost]: ...


def _language(text: str) -> str:
    if _KANA.search(text):
        return "ja"
    if _HAN.search(text):
        return "zh"
    return "en"


def _title(post: SocialPost, pages: list[LinkedPage]) -> str:
    for line in post.text.splitlines():
        cleaned = _URL.sub("", line).strip(" \t　#＃")
        if len(cleaned) >= 4:
            return cleaned[:MAX_TITLE_CHARS]
    for page in pages:
        if page.title:
            return page.title[:MAX_TITLE_CHARS]
    return f"{post.author_name or post.author_handle} の投稿"


def build_event(post: SocialPost, pages: list[LinkedPage]) -> Any:
    """One pipeline Event for a post. Dates and venue are left to the annotator."""
    from sources.base import Event

    author = post.author_name or post.author_handle
    parts = [
        # Year anchor in the form annotator.py looks for; without it the
        # annotator would anchor on scraped_at, which is wrong for older posts.
        f"（記事配信日: {filters.to_jst_date(post.created_at).isoformat()}）",
        "",
        f"投稿元: {post.url}",
        f"投稿者: {author} (@{post.author_handle})",
        "",
        post.text[:MAX_POST_CHARS],
    ]
    for page in pages:
        parts += ["", f"--- リンク先: {page.url} ---", page.title, page.text]
    raw_description = "\n".join(parts).strip()
    return Event(
        source_name=SOURCE_NAME[post.platform],
        source_id=f"{SOURCE_ID_PREFIX[post.platform]}{post.post_id}",
        source_url=post.url,
        original_language=_language(post.text + " ".join(p.text for p in pages)),
        raw_title=_title(post, pages),
        raw_description=raw_description,
        official_url=pages[0].url if pages else None,
    )


def _post_is_injection(text: str) -> bool:
    from security.injection_guard import max_severity, scan_for_injection

    return max_severity(scan_for_injection(text)) >= INJECTION_BLOCK_SEVERITY


def process_post(post: SocialPost, today: date, enricher: Optional[LinkEnricher], report: RunReport) -> bool:
    """Filter one post and record the outcome. True when an Event was added."""
    if _post_is_injection(post.text):
        # Deliberate exception to the detect-only policy of injection_guard:
        # these Events publish without review, so a hit drops the post. It is
        # kept in ``flagged`` with its link for the audit.
        report.drop(filters.DROP_INJECTION)
        report.flagged.append(Rejected(post_id=post.post_id, url=post.url, reason=filters.DROP_INJECTION))
        logger.warning("social: injection pattern in post %s; dropped", post.url)
        return False
    verdict, reason = filters.classify_post(post.text, post.created_at, today, is_repost=post.is_repost)
    if verdict == filters.VERDICT_DROP:
        report.drop(reason)
        return False
    # Always follow links when there are any: a post that looks complete may
    # only carry a deadline or a sale date, and plain HTTP fetches are free.
    pages = enricher.enrich(post) if enricher is not None else []
    combined = "\n".join([post.text] + [f"{p.title}\n{p.text}" for p in pages])
    gap = filters.completeness_gap(combined, post.created_at, today)
    if gap:
        report.insufficient.append(Rejected(post_id=post.post_id, url=post.url, reason=gap))
        return False
    report.events.append(build_event(post, pages))
    return True


def rotate(targets: list[SocialTarget], today: date) -> list[SocialTarget]:
    """Start from a different account each day so a run budget starves no one."""
    if not targets:
        return []
    offset = today.toordinal() % len(targets)
    return targets[offset:] + targets[:offset]


def run_pipeline(
    targets: Iterable[SocialTarget],
    backend: Backend,
    *,
    today: date,
    enricher: Optional[LinkEnricher] = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    max_events_per_target: int = MAX_EVENTS_PER_TARGET,
) -> RunReport:
    """Fetch, filter and enrich posts for every target of one platform.

    ``today`` is the current date in Japan.
    """
    report = RunReport(platform=backend.platform)
    seen: set[str] = set()
    own = [t for t in targets if t.platform == backend.platform]
    for target in rotate(own, today):
        try:
            posts = backend.fetch(target, lookback_hours=lookback_hours)
        except BackendUnavailable as exc:
            # Not configured: skip quietly. This is not a failure.
            report.skipped = str(exc)
            logger.info("social: %s backend not configured: %s", backend.platform, exc)
            break
        except Exception as exc:  # one failing account must not stop the others
            # Configured but failing (expired token, quota, HTTP error): an
            # error the caller must surface. Type name only, because exception
            # messages can carry request URLs.
            report.errors.append(f"{target.handle}: {type(exc).__name__}")
            logger.warning("social: fetch failed for %s: %s", target.handle, type(exc).__name__)
            continue
        newest: Optional[SocialPost] = None
        added = 0
        for post in sorted(posts, key=lambda p: p.created_at):
            if post.post_id in seen:
                continue
            seen.add(post.post_id)
            if newest is None or post.created_at > newest.created_at:
                newest = post
            if added >= max_events_per_target:
                report.insufficient.append(
                    Rejected(post_id=post.post_id, url=post.url, reason=filters.INSUFFICIENT_OVER_CAP)
                )
                continue
            if process_post(post, today, enricher, report):
                added += 1
        if newest is not None:
            report.newest_post_ids[target.handle] = newest.post_id
    report.posts_read = backend.posts_read
    if enricher is not None:
        report.pages_fetched = enricher.pages_fetched
        report.link_stats = enricher.link_stats
    return report
