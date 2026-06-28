"""
Scraper for PR TIMES (prtimes.jp) — Japan's largest press release distribution platform.

Strategy:
  1. Query the internal API:
     GET https://prtimes.jp/api/keyword_search.php/search
         ?keyword=<kw>&page=<N>&limit=40
     This endpoint is discovered from the site's Next.js bundle (module 20400).
  2. Use multiple Taiwan×event keywords to improve recall.
  3. Filter PRs where the title contains BOTH a Taiwan keyword AND an
     event-type keyword (イベント / フェス / 開催 / 祭 / …).
  4. Fetch the PR detail page to extract the actual event date and venue.
  5. Only include PRs released within the last LOOKBACK_DAYS (default 90).

source_id  = "prtimes_{company_id}_{release_id}"  — avoids cross-company collisions.
source_url = "https://prtimes.jp{release_url}"  — the direct PR page URL.

No Playwright needed — the search API returns JSON and the detail pages are
server-rendered HTML.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "prtimes"

_API_URL = "https://prtimes.jp/api/keyword_search.php/search"
_PR_BASE = "https://prtimes.jp"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json",
    "Accept-Language": "ja,en;q=0.9",
}
_HTML_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ja,en;q=0.9",
}

# Max pages to fetch per keyword (40 results / page)
_MAX_PAGES = 5
# Only consider PRs released within this window
LOOKBACK_DAYS = 90
# Polite delay between requests (seconds)
_DELAY = 0.5

# Search keywords — broad Taiwan × event queries, NO geographic restriction
# (project scope is all of Japan — never add city names like 東京 here)
_SEARCH_KEYWORDS = [
    "台湾 イベント",
    "台湾フェア",
    "台湾フェス",
    "台湾 開催",
    "台湾 夜市",
    "台湾 祭",
    "台湾映画",  # 上映・配信・映画祭 全覆蓋；Amazon/U-NEXT 等有使用 prtimes 發稿
]

# Title must contain at least one Taiwan keyword
_TAIWAN_KW = re.compile(r"台湾|Taiwan|台灣|臺灣")

# Title must contain at least one event-type keyword
_EVENT_KW = re.compile(
    r"イベント|フェア|フェス|フェスタ|フェスティバル|開催|展示|展覧|祭|セミナー|"
    r"講演|シンポジウム|ワークショップ|体験|交流会|コンサート|公演|"
    r"上映|夜市|マルシェ|マーケット|博覧会|発表会|説明会|"
    r"配信|独占配信|デジタル配信"  # VOD / 串流平台上架公告
)

# PR body patterns to extract event date
_DATE_LABELS = re.compile(
    r"(?:開催日時|開催日|開催期間|日時|日程|イベント日時|期間)[：:]\s*"
    r"((?:\d{4}年)?\d{1,2}月\d{1,2}日[^\n。]{0,60})",
    re.MULTILINE,
)
_DATE_STANDALONE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_TIME_RE = re.compile(r"(\d{1,2})[：:](\d{2})")
_RELEASE_DATE_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})時(\d{2})分"
)

# Venue extraction from PR body
_VENUE_LABELS = re.compile(
    r"(?:開催場所|会場|場所|開催地|会場名)[：:]\s*([^\n。]{2,80})",
    re.MULTILINE,
)

# Titles that indicate the event is held IN Taiwan (not Japan) — skip these.
# NOTE: Pattern must NOT match Japan-held Taiwan fairs like「台湾フェア」で.
# Only match when "台湾" is followed by で/にて/開催 AND preceded by place context,
# or explicit Taiwan-city routing, or Taiwan-market keywords.
_TAIWAN_BASED_TITLE_RE = re.compile(
    r"(?:台湾(?:国内|現地|本島|の地).*?(?:で|にて|開催))|"  # 台湾国内で開催 (explicit context)
    r"(?:(?:in |IN )(?:台湾|Taiwan|台中|台北|高雄))|"        # in 台湾 / in Taiwan
    r"台湾(?:出展|輸出|進出|販路|海外展示|海外販売)"          # business/export context
)

# Multi-city event section pattern — e.g. "東京｜2026年5月2日" / "大阪｜5月9日"
# When detected, raw_description is extended to include the event schedule section
# so the Annotator can generate sub_events for each city.
_MULTI_CITY_SECTION_RE = re.compile(
    r"(?:東京|大阪|京都|名古屋|福岡|札幌|仙台|横浜|神戸|広島)[｜|].*?\d{1,2}月\d{1,2}日",
    re.MULTILINE,
)

# City/venue keywords that indicate the event is in Taiwan
_TAIWAN_VENUE_RE = re.compile(
    r"台北|台中|高雄|新竹|花蓮|嘉義|台南|桃園|基隆|宜蘭|屏東|"
    r"Taiwan|Taipei|Kaohsiung|Tainan|Taichung|Hsinchu"
)

_JAPAN_VISITOR_KW = (
    "日本人向け",
    "日本語対応",
    "日本語サポート付",
    "日本語サポート付き",
    "日本から",
    "日本発",
    "ファムトリップ",
    "日台交流ツアー",
)

_RELEASE_PATH_IDS_RE = re.compile(r"/(\d{9})\.(\d{9})\.html$")

_PLACEHOLDER_TITLE_RE = re.compile(
    r"^(?:" 
    r"[\s\-—–_・・]*" 
    r"|(?:\(|（)(?:未命名|無題|無標題)(?:\)|）)" 
    r"|(?:未命名|無題|無標題)" 
    r")[\s\-—–_・]*$"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_released_at(released_at: str) -> Optional[datetime]:
    """Parse "2026年4月25日 17時00分" → datetime."""
    m = _RELEASE_DATE_RE.search(released_at)
    if m:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)),
        )
    # fallback: date only
    m2 = _DATE_STANDALONE.search(released_at)
    if m2:
        return datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
    return None


def _extract_date_from_body(body_text: str, fallback: Optional[datetime]) -> Optional[datetime]:
    """Try to extract the actual event date from the PR body text.

    Priority:
      1. Labeled patterns (開催日時: / 日時: / etc.)
      2. First standalone YYYY年M月D日 after the opening paragraphs
      3. Fallback (PR release date)
    """
    # 1. Labeled patterns
    m = _DATE_LABELS.search(body_text)
    if m:
        date_str = m.group(1)
        dm = _DATE_STANDALONE.search(date_str)
        if dm:
            try:
                year = int(dm.group(1))
                month = int(dm.group(2))
                day = int(dm.group(3))
                # Try to find HH:MM
                remainder = date_str[dm.end():]
                tm = _TIME_RE.search(remainder)
                if tm:
                    return datetime(year, month, day, int(tm.group(1)), int(tm.group(2)))
                return datetime(year, month, day)
            except ValueError:
                pass
        # Date without year — inject from fallback year
        m2 = re.search(r"(\d{1,2})月(\d{1,2})日", date_str)
        if m2 and fallback:
            month, day = int(m2.group(1)), int(m2.group(2))
            year = fallback.year
            # Adjust year if month/day already passed
            try:
                dt = datetime(year, month, day)
                if dt < fallback - timedelta(days=30):
                    dt = datetime(year + 1, month, day)
                return dt
            except ValueError:
                pass

    # 2. Standalone date — find the first date that is plausibly an event date
    #    (not older than 2 years from now, to avoid picking up historical mentions)
    all_dates = list(_DATE_STANDALONE.finditer(body_text))
    now = datetime.now()
    for dm2 in all_dates[1:]:  # skip first (often the PR publish dateline)
        try:
            candidate = datetime(int(dm2.group(1)), int(dm2.group(2)), int(dm2.group(3)))
            if candidate > now - timedelta(days=730):
                return candidate
        except ValueError:
            continue

    return fallback


def _extract_venue_from_body(body_text: str) -> Optional[str]:
    """Try to extract the event venue/location from the PR body text."""
    m = _VENUE_LABELS.search(body_text)
    if m:
        venue = m.group(1).strip()
        # Remove trailing noise
        venue = re.split(r"[。\n（]", venue)[0].strip()
        if venue:
            return venue
    return None


def _extract_venue_context_from_body(body_text: str) -> str:
    m = _VENUE_LABELS.search(body_text)
    if not m:
        return ""
    return m.group(1).strip()


def _targets_japanese_visitors(title: str, body_text: str) -> bool:
    return any(kw in title or kw in body_text for kw in _JAPAN_VISITOR_KW)


def _is_taiwan_venue_context(body_text: str, venue: str | None) -> bool:
    venue_context = _extract_venue_context_from_body(body_text)
    return bool(
        (venue and _TAIWAN_VENUE_RE.search(venue))
        or (venue_context and _TAIWAN_VENUE_RE.search(venue_context))
    )


def _should_skip_taiwan_venue(title: str, body_text: str, venue: str | None) -> bool:
    return _is_taiwan_venue_context(body_text, venue) and not _targets_japanese_visitors(
        title, body_text
    )


def _build_source_id(release_id: int | str, company_id: int | str | None, release_url_path: str) -> str:
    """Build collision-safe source_id.

    Preferred format: prtimes_<company_id:09d>_<release_id:09d>
    Fallback:         prtimes_<release_id>
    """
    rid = str(release_id).strip()
    cid = str(company_id or "").strip()

    # 1) Prefer explicit company_id from API payload.
    if cid.isdigit() and rid.isdigit():
        return f"prtimes_{int(cid):09d}_{int(rid):09d}"

    # 2) Fallback: derive both IDs from release_url path /.../000000030.000050200.html
    m = _RELEASE_PATH_IDS_RE.search(release_url_path or "")
    if m:
        rid_from_path, cid_from_path = m.group(1), m.group(2)
        return f"prtimes_{cid_from_path}_{rid_from_path}"

    # 3) Last-resort legacy format.
    return f"prtimes_{rid}"


def _is_blank_or_placeholder_title(title: str) -> bool:
    cleaned = (title or "").strip()
    if not cleaned:
        return True
    if _PLACEHOLDER_TITLE_RE.match(cleaned):
        return True
    # Skip strings that contain no meaningful characters after removing common punctuation.
    stripped = re.sub(r"[\s\-—–_・「」『』（）()【】\[\]…。，．、/]+", "", cleaned)
    return not stripped


def _fetch_detail(url: str, session: requests.Session) -> tuple[str, str]:
    """Fetch a PR detail page and return (body_text, raw_description).

    Returns ("", "") on failure.
    """
    try:
        resp = session.get(url, headers=_HTML_HEADERS, timeout=20)
        if resp.status_code != 200:
            return "", ""
        soup = BeautifulSoup(resp.text, "html.parser")

        # PR TIMES body is in <div class="*body*"> or the article main section
        body_el = (
            soup.select_one(".release-content, .press-release-body, .article-body")
            or soup.select_one("article")
            or soup.select_one("main")
        )
        if not body_el:
            return "", ""

        text = body_el.get_text(separator="\n", strip=True)

        # If multiple city event sections detected (e.g. "東京｜5/2" + "大阪｜5/9"),
        # extend raw_description to include the event schedule block so the
        # Annotator can generate sub_events for each city.
        mc = _MULTI_CITY_SECTION_RE.search(text)
        if mc:
            # Include up to 300 chars before the first city marker (section header)
            section_start = max(0, mc.start() - 300)
            event_block = text[section_start:section_start + 4000]
            raw_desc = text[:2000] + "\n\n---[イベント開催情報]---\n" + event_block
        else:
            raw_desc = text[:3000]

        return text, raw_desc[:8000]
    except Exception as exc:
        logger.debug("Detail fetch error for %s: %s", url, exc)
        return "", ""


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class PrtimesScraper(BaseScraper):
    """Scrapes Taiwan-related event announcements from PR TIMES via internal API."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({"User-Agent": _UA})

        cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        seen_ids: set[str] = set()
        events: list[Event] = []

        for keyword in _SEARCH_KEYWORDS:
            kw_enc = requests.utils.quote(keyword)
            new_count = 0
            for page in range(1, _MAX_PAGES + 1):
                url = (
                    f"{_API_URL}?keyword={kw_enc}&page={page}&limit=40"
                )
                try:
                    resp = session.get(url, headers=_HEADERS, timeout=20)
                    resp.raise_for_status()
                    data = resp.json().get("data", {})
                except Exception as exc:
                    logger.warning("API error [%s p%d]: %s", keyword, page, exc)
                    break

                releases = data.get("release_list", [])
                if not releases:
                    break

                for rel in releases:
                    release_id = rel.get("release_id")
                    if not release_id:
                        continue

                    release_url_path = rel.get("release_url", "")
                    source_id = _build_source_id(
                        release_id=release_id,
                        company_id=rel.get("company_id"),
                        release_url_path=release_url_path,
                    )
                    if source_id in seen_ids:
                        continue

                    title = rel.get("title", "")
                    if _is_blank_or_placeholder_title(title):
                        logger.debug("Skip placeholder title: %s", title[:60])
                        continue
                    # Must contain Taiwan keyword in title
                    if not _TAIWAN_KW.search(title):
                        continue
                    # Must contain an event-type keyword
                    if not _EVENT_KW.search(title):
                        continue
                    # Skip PRs about events held IN Taiwan (not Japan)
                    if _TAIWAN_BASED_TITLE_RE.search(title):
                        logger.debug("Skip Taiwan-based: %s", title[:60])
                        continue

                    # Check PR release date within lookback window
                    released_at_str = rel.get("released_at", "")
                    released_dt = _parse_released_at(released_at_str)
                    if released_dt and released_dt < cutoff:
                        # Results are sorted newest-first; once we hit cutoff stop
                        logger.debug(
                            "Cutoff reached at page %d for '%s'", page, keyword
                        )
                        break

                    seen_ids.add(source_id)
                    new_count += 1

                    source_url = _PR_BASE + release_url_path

                    # Fetch detail page to get event date & venue
                    body_text, raw_desc = _fetch_detail(source_url, session)
                    time.sleep(_DELAY)

                    start_date = _extract_date_from_body(body_text, released_dt)
                    venue = _extract_venue_from_body(body_text)
                    if _should_skip_taiwan_venue(title, body_text, venue):
                        logger.debug("Skip Taiwan venue '%s': %s", (venue or "")[:30], title[:50])
                        seen_ids.discard(source_id)
                        new_count -= 1
                        continue

                    # Sanity-check date: reject if more than 2 years in the past
                    now = datetime.now()
                    if start_date and start_date < now - timedelta(days=730):
                        logger.debug(
                            "Suspicious date %s for '%s' — falling back to release date",
                            start_date.date(), title[:50],
                        )
                        start_date = released_dt

                    # Prepend date info to raw_description
                    if start_date and raw_desc:
                        date_prefix = (
                            f"開催日時: {start_date.year}年"
                            f"{start_date.month:02d}月{start_date.day:02d}日\n\n"
                        )
                        raw_desc = date_prefix + raw_desc
                    elif not raw_desc:
                        raw_desc = title

                    company = rel.get("company_name", "")
                    selection_reason = (
                        f'{{"ja":"PR TIMESに掲載された台湾関連イベント告知。'
                        f'発行元: {company}","zh":null,"en":null}}'
                    )

                    events.append(
                        Event(
                            source_name=SOURCE_NAME,
                            source_id=source_id,
                            source_url=source_url,
                            original_language="ja",
                            raw_title=title,
                            raw_description=raw_desc,
                            start_date=start_date,
                            end_date=start_date,
                            location_name=venue,
                            location_address=None,
                            is_active=True,
                        )
                    )

                else:
                    # Inner for-loop completed without break — continue to next page
                    time.sleep(_DELAY)
                    continue
                break  # Cutoff was hit

            logger.info(
                "PrtimesScraper: keyword='%s' → %d new events", keyword, new_count
            )

        logger.info("PrtimesScraper: %d total events", len(events))
        return events
