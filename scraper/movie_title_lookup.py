"""Lookup official multilingual titles for Japanese movie titles via eiga.com.

Usage:
    from movie_title_lookup import lookup_movie_titles
    name_zh, name_en = lookup_movie_titles("霧のごとく")
    # → ("大濛", "A Foggy Tale") or (None, None) if not found

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
import re
import time
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

# In-memory cache: name_ja → (name_zh, name_en)
_cache: dict[str, tuple[str | None, str | None]] = {}

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


def lookup_movie_titles(name_ja: str) -> tuple[str | None, str | None]:
    """Return (name_zh, name_en) for a Japanese movie title via eiga.com.

    Returns (None, None) if the title is not found, or on any network/parse error.
    Results are cached for the lifetime of the current process.
    """
    if not name_ja or not name_ja.strip():
        return None, None

    key = name_ja.strip()
    if key in _cache:
        return _cache[key]

    try:
        encoded = quote(key)
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
            _cache[key] = (None, None)
            return None, None

        time.sleep(LOOKUP_DELAY_SEC)
        detail_resp = _session.get(movie_link, timeout=15)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        # Parse p.data for 原題 line
        data_p = detail_soup.find("p", class_="data")
        data_text = data_p.get_text(separator="\n") if data_p else ""
        name_zh, name_en = _parse_original_title(data_text)

        logger.debug(
            "lookup_movie_titles: %r → zh=%r en=%r (via %s)",
            key, name_zh, name_en, movie_link,
        )
        _cache[key] = (name_zh, name_en)
        return name_zh, name_en

    except Exception as exc:
        logger.debug("lookup_movie_titles: error for %r: %s", key, exc)
        _cache[key] = (None, None)
        return None, None
