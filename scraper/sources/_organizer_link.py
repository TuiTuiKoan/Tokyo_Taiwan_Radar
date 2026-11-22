"""Helpers for aggregator ("relay") sources whose articles point to an organiser page.

Spec: docs/specs/active/organizer-source-subevents/

Pure functions (unit-tested without network):
  - pick_organizer_link(): choose the organiser page among an article's links
  - extract_schedule_dates(): event dates from a schedule written in prose
  - count_schedule_slots(): number of "HH:MM『title』"-style programme slots

fetch_page_text() is the only function that touches the network (Playwright).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domains that are never the organiser page: SNS, maps, ticketing, link shorteners.
_NEVER_ORGANIZER_DOMAINS = (
    "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com",
    "youtu.be", "tiktok.com", "line.me", "lin.ee", "threads.net", "note.com",
    "google.com", "goo.gl", "maps.app.goo.gl", "bit.ly",
    "peatix.com", "eplus.jp", "pia.jp", "t.pia.jp", "l-tike.com", "livepocket.jp",
    "ticket.rakuten.co.jp", "eventbrite.com", "teket.jp",
)
_FILE_EXT_RE = re.compile(r"\.(pdf|jpe?g|png|gif|webp|zip|docx?|xlsx?|pptx?)(?:$|[?#])", re.IGNORECASE)
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _domain_matches(host: str, domains: Iterable[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def pick_organizer_link(
    links: Iterable[tuple[str, str]],
    own_domains: Iterable[str],
) -> tuple[Optional[str], Optional[str]]:
    """Pick the organiser page from ``(href, anchor_text)`` pairs in article order.

    Returns ``(html_url, pdf_url)``:
      - html_url: first external http(s) link that is not SNS/maps/ticketing/file.
      - pdf_url: first external PDF link (a flyer), reported separately because we
        do not download PDFs; callers may still note it in raw_description.
    """
    own = tuple(d.lower() for d in own_domains)
    html_url: Optional[str] = None
    pdf_url: Optional[str] = None
    for href, _text in links:
        if not href or not href.startswith(("http://", "https://")):
            continue
        host = _host(href)
        if not host or _domain_matches(host, own) or _domain_matches(host, _NEVER_ORGANIZER_DOMAINS):
            continue
        if _PDF_RE.search(href):
            pdf_url = pdf_url or href
            continue
        if _FILE_EXT_RE.search(href):
            continue
        if html_url is None:
            html_url = href
    return html_url, pdf_url


# 12月2日 / 12月2日（水） — full month-day in the body.
_MD_KANJI_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
# 12/2(水) — slash form with a weekday marker, as used in TIFF headlines.
# The weekday marker is required so that "1/2" fractions or ratios do not match.
_MD_SLASH_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})\s*[（(][月火水木金土日祝・]+[)）]")


def extract_schedule_dates(
    texts: Iterable[Optional[str]],
    published: datetime,
    *,
    lookback_days: int = 7,
    horizon_days: int = 365,
    past_mention_days: int = 180,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Return ``(start, end)`` from month-day dates written in the article.

    Years are inferred from the publish date. A month-day up to
    ``past_mention_days`` before ``published`` is a past mention and ignored;
    one further back is moved to the next year. Dates outside
    ``[published - lookback_days, published + horizon_days]`` are ignored.
    Returns ``(None, None)`` when no date qualifies.
    """
    lo = published - timedelta(days=lookback_days)
    hi = published + timedelta(days=horizon_days)
    found: list[datetime] = []
    for text in texts:
        if not text:
            continue
        for rx in (_MD_KANJI_RE, _MD_SLASH_RE):
            for m in rx.finditer(text):
                month, day = int(m.group(1)), int(m.group(2))
                try:
                    d = datetime(published.year, month, day)
                except ValueError:
                    continue
                if d < lo:
                    # Up to ~half a year back is a mention of a past event
                    # (e.g. "10月30日に上映されました"); further back is next year's
                    # date written without a year (e.g. a January date in December).
                    if d >= published - timedelta(days=past_mention_days):
                        continue
                    try:
                        d = datetime(published.year + 1, month, day)
                    except ValueError:
                        continue
                if lo <= d <= hi:
                    found.append(d)
    if not found:
        return None, None
    return min(found), max(found)


# A programme slot: "16:00『夫の秘密』" or "17:10　シンポジウム".
_SLOT_RE = re.compile(
    r"^[ \t　]*(\d{1,2}[:：]\d{2})[～〜~\-－]?[ \t　]*"
    r"(?:[『「]([^』」\n]+)[』」]|(シンポジウム|トーク|講演|対談|座談会|ディスカッション))",
    re.MULTILINE,
)


def count_schedule_slots(text: Optional[str]) -> tuple[int, int]:
    """Return ``(slots, distinct_titles)`` for a schedule written as one slot per line.

    ``distinct_titles`` counts the different first titles (talk keywords count as
    one title each). A single film shown at several times gives many slots but
    one distinct title — the annotator's single-film EXCEPTION still applies.
    """
    if not text:
        return 0, 0
    slots = 0
    titles: set[str] = set()
    for m in _SLOT_RE.finditer(text):
        slots += 1
        titles.add((m.group(2) or m.group(3) or "").strip())
    return slots, len(titles)


def slice_article(
    text: str,
    header_re: re.Pattern[str],
    footer_markers: Iterable[str] = (),
) -> str:
    """Keep only the article: drop navigation above the first ``header_re`` match
    and sidebars/related-article lists from the first footer marker line onward.

    Each step is skipped when its marker is not found, so the worst case is the
    original text.
    """
    m = header_re.search(text)
    if m:
        text = text[m.start():]
    cut = len(text)
    for marker in footer_markers:
        fm = re.search(rf"^[ \t　]*{re.escape(marker)}[ \t　]*$", text, re.MULTILINE)
        if fm and fm.start() < cut:
            cut = fm.start()
    return text[:cut].rstrip()


def fetch_page_text(context, url: str, *, timeout_ms: int = 20_000, max_chars: int = 6000) -> Optional[str]:
    """Open ``url`` in a new Playwright page and return its body text (or None)."""
    page = None
    try:
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        text = page.locator("body").inner_text(timeout=5_000)
        text = (text or "").strip()
        return text[:max_chars] or None
    except Exception as exc:  # network, timeout, navigation errors
        logger.warning("organizer page fetch failed (%s): %s", url, exc)
        return None
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
