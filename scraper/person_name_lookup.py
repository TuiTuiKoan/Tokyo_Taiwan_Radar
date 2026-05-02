"""Lookup official Chinese/English names for cast & crew via eiga.com + Wikipedia.

Usage:
    from person_name_lookup import lookup_person_names
    people = lookup_person_names("赤い糸 輪廻のひみつ")
    # → {"ギデンズ・コー": PersonInfo(name_zh="九把刀", name_en="Giddens Ko", role="監督"), ...}

Strategy:
  1. Search eiga.com to find the movie page (reuses movie_title_lookup session).
  2. Parse staff/cast section → extract (role, ja_name, person_url) tuples.
  3. For each person, fetch eiga.com person page → get English name.
  4. Search zh.wikipedia with the English name → first result = Chinese name.
  5. Cache results in-memory for the current process lifetime.

Rate limiting: LOOKUP_DELAY_SEC between requests (polite crawl).
Failures are silenced and return empty dict so they never break scrapers.
"""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LOOKUP_DELAY_SEC = 1.0

_BASE_URL = "https://eiga.com"
_SEARCH_URL_TMPL = "https://eiga.com/search/{}/movie/"
_WIKI_ZH_API = "https://zh.wikipedia.org/w/api.php"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)
_WIKI_UA = "TokyoTaiwanRadar/1.0 (https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"

_session = requests.Session()
_session.headers.update({
    "User-Agent": _USER_AGENT,
    "Accept-Language": "ja,en;q=0.9",
})

# Cache: movie ja_name → dict[ja_person_name, PersonInfo]
_movie_cache: dict[str, dict[str, "PersonInfo"]] = {}

# Cache: eiga.com person URL → (name_en, name_zh)
_person_cache: dict[str, tuple[str | None, str | None]] = {}


@dataclass
class PersonInfo:
    name_zh: str | None
    name_en: str | None
    role: str


def _find_movie_url(name_ja: str) -> str | None:
    """Search eiga.com and return the first movie detail page URL."""
    encoded = quote(name_ja.strip())
    search_url = _SEARCH_URL_TMPL.format(encoded)

    time.sleep(LOOKUP_DELAY_SEC)
    resp = _session.get(search_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.select("ul.row.list-tile li.col-s-3 a[href]"):
        href = a.get("href", "")
        if re.match(r"^/movie/\d+/$", href):
            return _BASE_URL + href
    return None


def _extract_cast_crew(movie_url: str) -> list[tuple[str, str, str]]:
    """Parse the staff/cast section of an eiga.com movie page.

    Returns list of (role, ja_name, person_url) tuples.
    """
    time.sleep(LOOKUP_DELAY_SEC)
    resp = _session.get(movie_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results: list[tuple[str, str, str]] = []
    staff_h2 = soup.find("h2", string=lambda t: t and "スタッフ" in t)
    if not staff_h2:
        return results

    parent = staff_h2.find_parent("section") or staff_h2.parent
    if not parent:
        return results

    for dt in parent.find_all("dt"):
        role = dt.get_text(strip=True)
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        for a in dd.find_all("a"):
            href = a.get("href", "")
            if re.match(r"^/person/\d+/$", href):
                ja_name = a.get_text(strip=True)
                person_url = _BASE_URL + href
                results.append((role, ja_name, person_url))

    # Also extract cast from movie page links (outside the dl section)
    # eiga.com sometimes lists actors as direct links with role names
    for a in soup.select("a[href^='/person/']"):
        href = a.get("href", "")
        if re.match(r"^/person/\d+/$", href):
            ja_name = a.get_text(strip=True)
            person_url = _BASE_URL + href
            if not any(p_url == person_url for _, _, p_url in results):
                # Try to find role text near the link
                results.append(("出演", ja_name, person_url))

    return results


def _lookup_person_en(person_url: str) -> str | None:
    """Fetch eiga.com person page and extract the English name."""
    time.sleep(LOOKUP_DELAY_SEC)
    resp = _session.get(person_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    profile = soup.select_one("div.profile")
    if not profile:
        return None

    for dt in profile.find_all("dt"):
        if "英語" in dt.get_text():
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.get_text(strip=True) or None
    return None


def _lookup_zh_via_wikipedia(en_name: str) -> str | None:
    """Search zh.wikipedia with an English name and return the first result title."""
    if not en_name:
        return None

    params = {
        "action": "query",
        "list": "search",
        "srsearch": en_name,
        "srnamespace": "0",
        "srlimit": "1",
        "format": "json",
    }
    resp = requests.get(
        _WIKI_ZH_API,
        params=params,
        timeout=10,
        headers={"User-Agent": _WIKI_UA},
    )
    data = resp.json()
    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]

    # Sanity check: the result should contain CJK characters (Chinese name)
    if not re.search(r"[\u4e00-\u9fff]", title):
        return None

    return title


def _resolve_person(person_url: str) -> tuple[str | None, str | None]:
    """Get (name_en, name_zh) for a person, with caching."""
    if person_url in _person_cache:
        return _person_cache[person_url]

    try:
        name_en = _lookup_person_en(person_url)
        name_zh = _lookup_zh_via_wikipedia(name_en) if name_en else None
        _person_cache[person_url] = (name_en, name_zh)
        return name_en, name_zh
    except Exception as exc:
        logger.debug("_resolve_person error for %s: %s", person_url, exc)
        _person_cache[person_url] = (None, None)
        return None, None


def lookup_person_names(name_ja: str) -> dict[str, PersonInfo]:
    """Return a dict mapping Japanese person names to PersonInfo for a movie.

    Keys are Japanese names (katakana) as they appear on eiga.com.
    Returns empty dict if the movie is not found or on any error.
    Results are cached for the lifetime of the current process.
    """
    if not name_ja or not name_ja.strip():
        return {}

    key = name_ja.strip()
    if key in _movie_cache:
        return _movie_cache[key]

    try:
        movie_url = _find_movie_url(key)
        if not movie_url:
            logger.debug("lookup_person_names: no eiga.com result for %r", key)
            _movie_cache[key] = {}
            return {}

        cast_crew = _extract_cast_crew(movie_url)
        if not cast_crew:
            logger.debug("lookup_person_names: no cast/crew for %r", key)
            _movie_cache[key] = {}
            return {}

        result: dict[str, PersonInfo] = {}
        for role, ja_name, person_url in cast_crew:
            name_en, name_zh = _resolve_person(person_url)
            if name_en or name_zh:
                result[ja_name] = PersonInfo(
                    name_zh=name_zh,
                    name_en=name_en,
                    role=role,
                )
                logger.debug(
                    "  person: %s (%s) → zh=%r en=%r",
                    ja_name, role, name_zh, name_en,
                )

        _movie_cache[key] = result
        logger.info(
            "lookup_person_names: %r → %d people resolved",
            key, len(result),
        )
        return result

    except Exception as exc:
        logger.debug("lookup_person_names: error for %r: %s", key, exc)
        _movie_cache[key] = {}
        return {}
