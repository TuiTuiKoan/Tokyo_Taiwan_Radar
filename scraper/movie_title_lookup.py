"""Lookup official multilingual titles for Japanese movie titles via eiga.com.

Usage:
    from movie_title_lookup import lookup_movie_titles
    name_zh, name_en, official_url = lookup_movie_titles("霧のごとく")
    # → ("大濛", "A Foggy Tale", "https://...") or (None, None, None) if not found

Strategy:
  1. Search https://eiga.com/search/{encoded_title}/movie/
  2. Take the first /movie/{id}/ result link
  3. Fetch the detail page and parse p.data for 原題または英題
  4. Split into CJK part (name_zh) and ASCII part (name_en)
  5. Cache results in-memory for the current process lifetime

Rate limiting: LOOKUP_DELAY_SEC between requests (polite crawl).
Failures are silenced and return (None, None) so they never break scrapers.
"""

import logging
import os
import re
import time
import urllib.parse as _urlparse
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LOOKUP_DELAY_SEC = 1.0

_BASE_URL = "https://eiga.com"
_SEARCH_URL_TMPL = "https://eiga.com/search/{}/movie/"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Original title regex — same pattern used in eiga_com.py
_ORIG_TITLE_RE = re.compile(r"原題(?:または英題)?[：:]\s*([^\n]+)")

# Traditional Chinese → Japanese kanji normalisation map.
# eiga.com indexes movie titles using Japanese kanji (often simplified variants).
# TC-specific characters like 灣(U+7063) are not found; 湾(U+6E7E) is.
# Reference incident: 灣生回家 → 湾生回家 needed for lookup.
_TC_TO_JP = str.maketrans({
    "\u7063": "\u6e7e",  # 灣 → 湾
    "\u81fa": "\u53f0",  # 臺 → 台
    "\u570b": "\u56fd",  # 國 → 国
    "\u9ad4": "\u4f53",  # 體 → 体
    "\u5c08": "\u5c02",  # 專 → 専
    "\u6f22": "\u6f22",  # same: 漢
    "\u5be7": "\u5be7",  # same: 寧
})

# In-memory cache: name_ja → (name_zh, name_en, official_url)
_cache: dict[str, tuple[str | None, str | None, str | None]] = {}

_GOOGLE_CSE_API_KEY: str | None = os.environ.get("GOOGLE_CSE_API_KEY")
_GOOGLE_CSE_ID:      str | None = os.environ.get("GOOGLE_CSE_ID")

_AGGREGATOR_DOMAINS = frozenset({
    "eiga.com", "filmarks.com", "kinenote.com", "allcinema.net",
    "imdb.com", "yahoo.co.jp", "amazon.co.jp", "unext.jp",
    "netflix.com", "youtube.com", "x.com", "twitter.com",
    "facebook.com", "instagram.com", "wikipedia.org",
    "google.com", "google.co.jp",
})

_session = requests.Session()
_session.headers.update({
    "User-Agent": _USER_AGENT,
    "Accept-Language": "ja,en;q=0.9",
})


def _parse_original_title(data_text: str) -> tuple[str | None, str | None]:
    """Extract (name_zh, name_en) from p.data 原題 line.

    Handles:
      '原題：阿嬤的夢中情人 Forever Love'   → ('阿嬤的夢中情人', 'Forever Love')
      '原題または英題：Forever Love'         → (None, 'Forever Love')
      '原題：阿嬤的夢中情人'                 → ('阿嬤的夢中情人', None)
    """
    m = _ORIG_TITLE_RE.search(data_text)
    if not m:
        return None, None
    orig = m.group(1).strip()
    # Split on first CJK-block → space → ASCII transition
    split_m = re.match(r"^([^\x00-\x7f]+)\s+([A-Za-z].+)$", orig)
    if split_m:
        return split_m.group(1).strip(), split_m.group(2).strip()
    if re.search(r"[\u4e00-\u9fff]", orig):
        return orig, None
    return None, orig


def _parse_official_url(detail_soup) -> str | None:
    """Extract official site URL from eiga.com jump link on detail page.

    eiga.com wraps external links as:
      <a href="https://eiga.com/jump/?...&u=<URL-encoded-target>">オフィシャルサイト</a>
    """
    for a in detail_soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "eiga.com/jump/" in href and "オフィシャルサイト" in text:
            qs = _urlparse.parse_qs(_urlparse.urlparse(href).query)
            u_list = qs.get("u", [])
            if u_list:
                return u_list[0]
    return None


def _google_cse_official_url(name_ja: str) -> str | None:
    """Search Google CSE for official site URL when eiga.com returns nothing.

    Returns first non-aggregator URL from top 3 results, or None.
    Silently returns None if GOOGLE_CSE_API_KEY / GOOGLE_CSE_ID not set.
    Rate limiting: uses LOOKUP_DELAY_SEC before the request.
    """
    if not _GOOGLE_CSE_API_KEY or not _GOOGLE_CSE_ID:
        return None
    try:
        query = f'"{name_ja}" 映画 公式サイト'
        params = {
            "key": _GOOGLE_CSE_API_KEY,
            "cx":  _GOOGLE_CSE_ID,
            "q":   query,
            "num": 3,
            "lr":  "lang_ja",
        }
        time.sleep(LOOKUP_DELAY_SEC)
        resp = _session.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        for item in items:
            link = item.get("link", "")
            domain = _urlparse.urlparse(link).netloc.lstrip("www.")
            if not any(
                domain == d or domain.endswith("." + d)
                for d in _AGGREGATOR_DOMAINS
            ):
                logger.debug("_google_cse_official_url: %r → %s", name_ja, link)
                return link
    except Exception as exc:
        logger.debug("_google_cse_official_url: error for %r: %s", name_ja, exc)
    return None


def lookup_movie_titles(name_ja: str) -> tuple[str | None, str | None, str | None]:
    """Return (name_zh, name_en, official_url) for a Japanese movie title via eiga.com.

    Returns (None, None, None) if the title is not found, or on any network/parse error.
    Results are cached for the lifetime of the current process.
    """
    if not name_ja or not name_ja.strip():
        return None, None, None

    key = name_ja.strip()
    if key in _cache:
        return _cache[key]

    # Normalise Traditional Chinese characters to Japanese kanji equivalents
    # before searching eiga.com (which indexes Japanese titles only).
    search_key = key.translate(_TC_TO_JP)

    try:
        encoded = quote(search_key)
        search_url = _SEARCH_URL_TMPL.format(encoded)

        time.sleep(LOOKUP_DELAY_SEC)
        resp = _session.get(search_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find first movie result link: /movie/{id}/
        movie_link = None
        for a in soup.select("ul.row.list-tile li.col-s-3 a[href]"):
            href = a.get("href", "")
            if re.match(r"^/movie/\d+/$", href):
                movie_link = _BASE_URL + href
                break

        if not movie_link:
            logger.debug("lookup_movie_titles: no result for %r", key)
            # Phase B: try Google CSE for official_url only
            cse_url = _google_cse_official_url(key)
            _cache[key] = (None, None, cse_url)
            return None, None, cse_url

        time.sleep(LOOKUP_DELAY_SEC)
        detail_resp = _session.get(movie_link, timeout=15)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        # Parse p.data for 原題 line
        data_p = detail_soup.find("p", class_="data")
        data_text = data_p.get_text(separator="\n") if data_p else ""
        name_zh, name_en = _parse_original_title(data_text)
        official_url = _parse_official_url(detail_soup)

        logger.debug(
            "lookup_movie_titles: %r → zh=%r en=%r official=%r (via %s)",
            key, name_zh, name_en, official_url, movie_link,
        )
        _cache[key] = (name_zh, name_en, official_url)
        return name_zh, name_en, official_url

    except Exception as exc:
        logger.debug("lookup_movie_titles: error for %r: %s", key, exc)
        _cache[key] = (None, None, None)
        return None, None, None
