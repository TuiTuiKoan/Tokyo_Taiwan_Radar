"""Follow the links in a post to find the date and venue it leaves out.

Reused from ``ingest_url`` (spec url-intake): ``normalize_url``, and
``fetch_html`` with its limits — manual redirects (5 hops), each hop DNS-checked
against non-public addresses, 2 MB cap, 20 s timeout. Set here: at most
MAX_LINKS_PER_POST pages per post, MAX_PAGE_CHARS of text per page, and
MIN_PAGE_CHARS below which a page is treated as unusable.

Plain HTTP only: pages that need JavaScript or block bots are expected to
fail, and ``link_stats`` counts successes and failures per host so that can be
measured. Fetched text is untrusted and is scanned for prompt injection.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit

from .models import LinkedPage, SocialPost

logger = logging.getLogger(__name__)

MAX_LINKS_PER_POST = 2
MAX_PAGE_CHARS = 3000
MIN_PAGE_CHARS = 80
MAX_STRUCTURED_CHARS = 1200
INJECTION_BLOCK_SEVERITY = 2

# (final_url, title, text) or None when the page is unusable.
Fetcher = Callable[[str], Optional[tuple[str, str, str]]]

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'）)\]」』、。]+", re.IGNORECASE)

# Same-platform and login-walled hosts: nothing readable without an account.
_SKIP_HOSTS = frozenset({
    "facebook.com", "fb.com", "fb.me", "fb.watch", "messenger.com",
    "x.com", "twitter.com", "t.co",
    "instagram.com", "threads.net", "threads.com",
    "youtube.com", "youtu.be", "tiktok.com",
})
# Facebook wraps outbound links as l.facebook.com/l.php?u=<real url>.
_FB_REDIRECT_HOSTS = frozenset({"l.facebook.com", "lm.facebook.com"})
_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mov", ".mp3", ".zip", ".pdf",
)
# Ticketing / event platforms: usually the most complete date and venue. This
# is the opposite of base.extract_first_party_url, which skips them to find the
# organiser's own page.
_EVENT_PLATFORM_HOSTS = frozenset({
    "peatix.com", "eplus.jp", "livepocket.jp", "kokuchpro.com",
    "passmarket.yahoo.co.jp", "teket.jp", "tiget.net", "connpass.com", "doorkeeper.jp",
    "eventbrite.com", "eventbrite.jp", "l-tike.com", "pia.jp",
    "eventregist.com", "accupass.com", "kktix.com", "kktix.cc",
})
# Link-collection pages and forms rarely carry the venue themselves; try them last.
_LOW_VALUE_HOSTS = frozenset({
    "linktr.ee", "lit.link", "bio.site", "potofu.me", "linkin.bio", "beacons.ai", "instabio.cc",
    "forms.gle", "docs.google.com", "google.com",
})
_EVENT_TYPES = re.compile(r"Event$|Festival$|^ScreeningEvent$|^ExhibitionEvent$")


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, hosts: frozenset[str]) -> bool:
    return host in hosts or any(host.endswith("." + h) for h in hosts)


def _rank(url: str) -> int:
    host = _host(url)
    if _matches(host, _EVENT_PLATFORM_HOSTS):
        return 0
    if _matches(host, _LOW_VALUE_HOSTS):
        return 2
    return 1


def _usable(url: str) -> bool:
    host = _host(url)
    if not host or _matches(host, _SKIP_HOSTS):
        return False
    return not urlsplit(url).path.lower().endswith(_SKIP_EXTENSIONS)


def unwrap_redirect(url: str) -> str:
    """The real target of a Facebook outbound-link wrapper, else ``url``."""
    parts = urlsplit(url)
    if (parts.hostname or "").lower() in _FB_REDIRECT_HOSTS:
        target = (parse_qs(parts.query).get("u") or [""])[0]
        if target.lower().startswith(("http://", "https://")):
            return target
    return url


def candidate_links(post: SocialPost) -> list[str]:
    """Outbound links worth fetching: normalised, de-duplicated, best first."""
    from ingest_url import IntakeError, normalize_url

    raw: list[str] = list(post.links)
    raw.extend(m.group(0) for m in _URL_IN_TEXT.finditer(post.text or ""))
    seen: set[str] = set()
    links: list[str] = []
    for item in raw:
        try:
            url = normalize_url(unwrap_redirect(item))
        except IntakeError:
            continue
        if url in seen or not _usable(url):
            continue
        seen.add(url)
        links.append(url)
    # Stable sort: ties keep the order the links appear in the post.
    return sorted(links, key=_rank)


# ── structured data: what extract_page throws away ─────────────────────────

def _text(value: Any, limit: int = 200) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _walk_json_ld(node: Any, out: list[dict], depth: int = 0) -> None:
    if depth > 6 or len(out) >= 3:
        return
    if isinstance(node, list):
        for item in node[:50]:
            _walk_json_ld(item, out, depth + 1)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and _EVENT_TYPES.search(t) for t in types):
            out.append(node)
        _walk_json_ld(node.get("@graph"), out, depth + 1)


def _place(location: Any) -> str:
    if isinstance(location, list):
        location = location[0] if location else None
    if isinstance(location, str):
        return _text(location)
    if not isinstance(location, dict):
        return ""
    address = location.get("address")
    if isinstance(address, dict):
        address = " ".join(
            _text(address.get(k), 80)
            for k in ("addressRegion", "addressLocality", "streetAddress") if address.get(k)
        )
    return " ".join(part for part in (_text(location.get("name")), _text(address)) if part)


def structured_summary(html: str) -> str:
    """Date and venue lines from schema.org Event JSON-LD, plus the meta description.

    Ticketing pages often render their body with JavaScript but still ship
    this in the HTML; ``ingest_url.extract_page`` strips <script> and ignores
    descriptions, so it is read here. Returns "" when there is nothing.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    events: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"})[:10]:
        try:
            _walk_json_ld(json.loads(tag.string or ""), events)
        except (ValueError, TypeError):
            continue
    lines: list[str] = []
    for event in events:
        name, start, end = _text(event.get("name")), _text(event.get("startDate"), 40), _text(event.get("endDate"), 40)
        if name:
            lines.append(f"イベント名: {name}")
        if start:
            lines.append(f"開催日時: {start}" + (f" 〜 {end}" if end and end != start else ""))
        place = _place(event.get("location"))
        if place:
            lines.append(f"会場: {place}")
    for attrs in ({"property": "og:description"}, {"name": "description"}):
        tag = soup.find("meta", attrs=attrs)
        description = _text(tag.get("content"), 600) if tag else ""
        if description:
            lines.append(f"概要: {description}")
            break
    return "\n".join(lines)[:MAX_STRUCTURED_CHARS]


def default_fetcher(url: str) -> Optional[tuple[str, str, str]]:
    """Fetch a page with the URL-intake safety checks. None on any failure."""
    from ingest_url import IntakeError, extract_page, fetch_html

    try:
        final_url, html, _status = fetch_html(url)
    except IntakeError as exc:
        logger.info("social enrich: %s not fetched: %s", _host(url), exc)
        return None
    page = extract_page(html)
    text = "\n".join(part for part in (structured_summary(html), page["body"]) if part)
    return final_url, page["title"], text


def _is_injection(text: str) -> bool:
    from security.injection_guard import max_severity, scan_for_injection

    return max_severity(scan_for_injection(text)) >= INJECTION_BLOCK_SEVERITY


class LinkEnricher:
    """Fetches linked pages for posts, with a per-run cache.

    ``fetcher`` is injectable so tests never touch the network.
    """

    def __init__(self, fetcher: Fetcher = default_fetcher, max_links: int = MAX_LINKS_PER_POST):
        self._fetcher = fetcher
        self._max_links = max_links
        self._cache: dict[str, Optional[LinkedPage]] = {}
        self.pages_fetched = 0
        self.pages_blocked = 0
        self.link_stats: dict[str, dict[str, int]] = {}   # host → {"ok": n, "failed": n}

    def _count(self, url: str, outcome: str) -> None:
        stats = self.link_stats.setdefault(_host(url), {"ok": 0, "failed": 0})
        stats[outcome] += 1

    def _fetch(self, url: str) -> Optional[LinkedPage]:
        if url in self._cache:
            return self._cache[url]
        page: Optional[LinkedPage] = None
        try:
            fetched = self._fetcher(url)
        except Exception as exc:  # a fetcher bug must not stop the run
            logger.warning("social enrich: fetcher raised %s for %s", type(exc).__name__, _host(url))
            fetched = None
        if fetched:
            self.pages_fetched += 1
            final_url, title, text = fetched
            title = (title or "").strip()[:300]
            text = (text or "").strip()[:MAX_PAGE_CHARS]
            if _is_injection(title + "\n" + text):
                # The page is discarded; the post itself is still processed.
                self.pages_blocked += 1
                logger.warning("social enrich: injection pattern in %s; page text discarded", _host(final_url))
            elif len(text) >= MIN_PAGE_CHARS and _usable(final_url):
                page = LinkedPage(url=final_url, title=title, text=text)
                self._cache[final_url] = page
        self._count(url, "ok" if page else "failed")
        self._cache[url] = page
        return page

    def enrich(self, post: SocialPost) -> list[LinkedPage]:
        """Up to ``max_links`` linked pages for ``post``, best first."""
        pages: list[LinkedPage] = []
        attempts = 0
        for url in candidate_links(post):
            if len(pages) >= self._max_links or attempts >= self._max_links + 1:
                break
            attempts += 1
            page = self._fetch(url)
            if page is not None and all(p.url != page.url for p in pages):
                pages.append(page)
        return pages
