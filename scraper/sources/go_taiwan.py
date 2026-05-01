"""Scraper for 台湾観光庁 Japan Event Page (go-taiwan.net/ikutabi).

いくたび、ふたたび台湾。 is the official Taiwan Tourism Administration website
for the Japanese market. It publishes:
  - Tourism promotion events held IN JAPAN (target)
  - News/reports about events held IN TAIWAN (excluded)

Strategy:
  1. Fetch listing pages: /archives/category/event and /archives/category/お知らせ
  2. Collect article links + publish dates from each page
  3. For each article, fetch full content and check for JAPAN location keywords
  4. Extract event date/venue/address from article body
  5. Skip articles whose venue is clearly in Taiwan (no Japan keywords in body)

Dedup key: go_taiwan_{post_id}
  e.g. /archives/16264 → go_taiwan_16264
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://go-taiwan.net/ikutabi"
LISTING_URLS = [
    f"{BASE_URL}/archives/category/event",
    f"{BASE_URL}/archives/category/%E3%81%8A%E7%9F%A5%E3%82%89%E3%81%9B",  # お知らせ
]

# Japan-side location keywords: if any appear in article body → event is in Japan
JAPAN_LOCATION_KW = [
    "東京", "大阪", "京都", "名古屋", "福岡", "北海道", "札幌",
    "横浜", "神戸", "仙台", "広島", "函館", "沖縄",
    "秋葉原", "渋谷", "新宿", "池袋", "銀座", "日本橋",
    "会場：", "会場:", "場所：", "場所:",
    "日本全国", "日本各地",
    "in 東京", "in 大阪", "in 日本",
    "関東", "関西", "近畿", "九州", "四国", "東北", "中部",
]

# Taiwan-only indicators: if title contains these AND body has no Japan keywords → skip
TAIWAN_ONLY_PATTERNS = re.compile(
    r"台湾ランタン|台湾国際蘭展|澎湖.*花火|台湾高速鉄道|台湾鉄道|"
    r"桃園空港|台北.*空港|ガイドブック.*台湾|台湾観光ツインイヤー|"
    r"台湾まるごとガイド|台湾基本情報"
)

# Venue-in-Taiwan signals: if present in article body, venue is Taiwan → exclude
TAIWAN_VENUE_KW = ["（台湾・", "（台湾）", "在台湾", "台湾開催", "台湾現地"]

_POST_ID_RE = re.compile(r"/archives/(\d+)")
_DATE_BODY_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
# Date ranges: YYYY年M月D日（曜）〜M月D日（曜）  — end month is optional
_DATE_RANGE_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日"
    r"[（(]?\S*?[）)]?"               # optional weekday e.g. （土）
    r"[〜～～\-~]"                      # range separator
    r"(?:(\d{1,2})月)?(\d{1,2})日"    # end: M月D日 or just D日
)
# Event date labeled with 日時/開催日時/期間 — highest priority
_LABELED_DATE_RE = re.compile(
    r"(?:日時|開催日時|開催日|開催期間|期間|会期)[：:]\s*"
    r"(\d{4})年(\d{1,2})月(\d{1,2})日"
)
# Nakaguro (middle dot) multi-day: YYYY年M月D日（曜）・D日（曜）
_DATE_NAKAGURO_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(][月火水木金土日・祝]{1,4}[）)]"
    r"[・･]"
    r"(?:(\d{1,2})月)?(\d{1,2})日"
)
# Event date with weekday marker (土)(日)(金祝) etc. — high priority
_DATE_WEEKDAY_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(][月火水木金土日・祝]{1,4}[）)]"
)
_VENUE_RE = re.compile(r"(?:会場|場所)[：:]\s*([^\n\r　。！「」]+)")
_ADDRESS_RE = re.compile(r"([東西南北].*?(?:都|道|府|県|市|区|町|村)[^\n\r。！「」]{0,40})")
_TIME_RE = re.compile(r"時間[：:]\s*([^\n\r。]{5,30})")

JST = timezone(timedelta(hours=9))


def _post_id(url: str) -> Optional[str]:
    m = _POST_ID_RE.search(url)
    return m.group(1) if m else None


def _is_japan_event(title: str, body_text: str) -> bool:
    """Return True if the event appears to be held in Japan."""
    # Quick title pre-filter: if clearly Taiwan-only, skip
    if TAIWAN_ONLY_PATTERNS.search(title):
        return False
    text = title + body_text
    # Explicit Taiwan-venue indicators: event is held in Taiwan, not Japan
    if any(kw in text for kw in TAIWAN_VENUE_KW):
        return False
    return any(kw in text for kw in JAPAN_LOCATION_KW)


def _parse_dates(body_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse event start_date and end_date from body text.

    Priority:
    1. Labeled date range  (日時：YYYY年...〜...日)
    2. Weekday-annotated range (YYYY年M月D日（土）〜D日（日）)
    3. Labeled single date (日時：YYYY年M月D日)
    4. Weekday-annotated single date (YYYY年M月D日（土）)
    5. Plain date range (YYYY年M月D日〜M月D日)
    6. First plain date in body (last resort — may be post publish date)

    Returns (start, end).  end equals start when only one date is found.
    """

    def _dt(y: str, m: str, d: str) -> Optional[datetime]:
        try:
            return datetime(int(y), int(m), int(d), tzinfo=JST)
        except ValueError:
            return None

    # 1. Labeled date range: 日時：YYYY年M月D日...〜...日
    labeled_range = re.search(
        r"(?:日時|開催日時|開催日|開催期間|期間|会期)[：:]\s*"
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\S*?"
        r"[〜～～\-~]"
        r"(?:(\d{1,2})月)?(\d{1,2})日",
        body_text,
    )
    if labeled_range:
        start = _dt(labeled_range.group(1), labeled_range.group(2), labeled_range.group(3))
        end_m = labeled_range.group(4) or labeled_range.group(2)
        end = _dt(labeled_range.group(1), end_m, labeled_range.group(5))
        if start:
            return start, (end or start)

    # 1a. Weekday-annotated nakaguro (middle-dot) range: YYYY年M月D日（祝）・D日（日）
    nm = _DATE_NAKAGURO_RE.search(body_text)
    if nm:
        start = _dt(nm.group(1), nm.group(2), nm.group(3))
        end_m = nm.group(4) or nm.group(2)
        end = _dt(nm.group(1), end_m, nm.group(5))
        if start:
            return start, (end or start)

    # 2. Weekday-annotated range: YYYY年M月D日（土）〜D日（日） / M月D日（日）
    weekday_range = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(][月火水木金土日・祝]{1,4}[）)]"
        r"\S*?"
        r"[〜～～\-~]"
        r"(?:(\d{1,2})月)?(\d{1,2})日",
        body_text,
    )
    if weekday_range:
        start = _dt(weekday_range.group(1), weekday_range.group(2), weekday_range.group(3))
        end_m = weekday_range.group(4) or weekday_range.group(2)
        end = _dt(weekday_range.group(1), end_m, weekday_range.group(5))
        if start:
            return start, (end or start)

    # 3. Labeled single date
    lm = _LABELED_DATE_RE.search(body_text)
    if lm:
        dt = _dt(lm.group(1), lm.group(2), lm.group(3))
        if dt:
            return dt, dt

    # 4. Weekday-annotated single date
    wm = _DATE_WEEKDAY_RE.search(body_text)
    if wm:
        dt = _dt(wm.group(1), wm.group(2), wm.group(3))
        if dt:
            return dt, dt

    # 5. Plain date range
    rng = _DATE_RANGE_RE.search(body_text)
    if rng:
        start = _dt(rng.group(1), rng.group(2), rng.group(3))
        end_m = rng.group(4) or rng.group(2)
        end = _dt(rng.group(1), end_m, rng.group(5))
        if start:
            return start, (end or start)

    # 6. Last resort: first plain date in body
    m = _DATE_BODY_RE.search(body_text)
    if m:
        dt = _dt(m.group(1), m.group(2), m.group(3))
        if dt:
            return dt, dt

    return None, None


def _parse_venue(body_text: str) -> tuple[Optional[str], Optional[str]]:
    name = None
    address = None
    vm = _VENUE_RE.search(body_text)
    if vm:
        name = vm.group(1).strip().rstrip("　。、")
    am = _ADDRESS_RE.search(body_text)
    if am:
        address = am.group(1).strip()
    return name, address


class GoTaiwanScraper(BaseScraper):
    """Scrapes Japan-based Taiwan promotion events from 台湾観光庁 (go-taiwan.net)."""

    SOURCE_NAME = "go_taiwan"

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        })

        articles = self._collect_articles(session, days=90)
        logger.info("go_taiwan: found %d articles on listing pages", len(articles))

        now = datetime.now(tz=JST)
        cutoff = now - timedelta(days=60)

        events: list[Event] = []
        seen_ids: set[str] = set()

        for article in articles:
            post_id = article["post_id"]
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            try:
                event = self._scrape_article(session, article, cutoff)
                if event:
                    events.append(event)
                time.sleep(0.6)
            except Exception as exc:
                logger.error("go_taiwan: failed to scrape %s: %s", article["url"], exc)

        logger.info("go_taiwan: %d Japan-side Taiwan events collected", len(events))
        return events

    def _collect_articles(self, session: requests.Session, days: int = 90) -> list[dict]:
        """Crawl listing pages; only return articles published within the past `days` days.

        Stops paginating once all articles on a page are older than the cutoff,
        since WordPress orders newest first.  Also pre-filters obvious Taiwan-only
        titles so we never bother fetching their full pages.
        """
        articles: list[dict] = []
        seen: set[str] = set()
        now = datetime.now(tz=JST)
        list_cutoff = now - timedelta(days=days)
        _date_attr_re = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

        for listing_url in LISTING_URLS:
            page = 1
            while True:
                url = listing_url if page == 1 else f"{listing_url}/page/{page}"
                try:
                    resp = session.get(url, timeout=15)
                    if resp.status_code == 404:
                        break
                    resp.raise_for_status()
                except Exception as exc:
                    logger.error("go_taiwan: listing fetch failed %s: %s", url, exc)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                found_any_recent = False

                for art_el in soup.select("article"):
                    # Locate the canonical permalink (first /archives/N link)
                    a_tag = None
                    for candidate in art_el.find_all("a", href=True):
                        if _post_id(candidate["href"]):
                            a_tag = candidate
                            break
                    if not a_tag:
                        continue
                    href = a_tag["href"]
                    if href in seen:
                        continue
                    pid = _post_id(href)
                    if not pid:
                        continue

                    # Parse post date from <time> element
                    pub_date: Optional[datetime] = None
                    time_el = art_el.find("time")
                    if time_el:
                        dt_attr = time_el.get("datetime", "")
                        dm = _date_attr_re.match(dt_attr)
                        if dm:
                            try:
                                pub_date = datetime(
                                    int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                                    tzinfo=JST,
                                )
                            except ValueError:
                                pass
                        if not pub_date:
                            tm = _DATE_BODY_RE.search(time_el.get_text())
                            if tm:
                                try:
                                    pub_date = datetime(
                                        int(tm.group(1)), int(tm.group(2)), int(tm.group(3)),
                                        tzinfo=JST,
                                    )
                                except ValueError:
                                    pass

                    # Skip articles older than the window
                    if pub_date and pub_date < list_cutoff:
                        seen.add(href)
                        continue

                    # Pre-filter obvious Taiwan-only articles by title
                    title_el = art_el.find(["h2", "h3", "h4"])
                    title = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)
                    if TAIWAN_ONLY_PATTERNS.search(title):
                        logger.debug("go_taiwan: listing pre-filter (Taiwan-only): %s", title[:50])
                        seen.add(href)
                        continue

                    articles.append({"url": href, "post_id": pid, "list_title": title, "pub_date": pub_date})
                    seen.add(href)
                    found_any_recent = True

                # Stop paginating if this page had no recent articles
                if not found_any_recent:
                    break
                page += 1
                time.sleep(0.4)

        return articles

    def _scrape_article(
        self, session: requests.Session, article: dict, cutoff: datetime
    ) -> Optional[Event]:
        url = article["url"]
        list_title = article.get("list_title", "")
        post_id = article["post_id"]

        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else list_title

        # Extract publish date from <time> or date patterns in content
        time_tag = soup.find("time")
        pub_date_str = ""
        if time_tag:
            pub_date_str = time_tag.get("datetime", time_tag.get_text(strip=True))

        # Extract body text
        content_area = (
            soup.find("div", class_=re.compile(r"entry-content|post-content|article-content"))
            or soup.find("article")
        )
        body_text = content_area.get_text(separator="\n", strip=True) if content_area else ""

        # Japan event filter
        if not _is_japan_event(title, body_text):
            logger.debug("go_taiwan: skipping Taiwan-only article: %s", title[:50])
            return None

        start_date, end_date = _parse_dates(body_text)

        # Skip old events beyond cutoff
        if start_date and start_date < cutoff:
            logger.debug("go_taiwan: skipping past event: %s (%s)", title[:40], start_date.date())
            return None

        venue_name, venue_address = _parse_venue(body_text)

        date_label = ""
        if start_date:
            date_label = f"{start_date.year}年{start_date.month}月{start_date.day}日"
        raw_description = (
            f"開催日時: {date_label}\n\n{body_text}" if date_label else body_text
        )

        source_id = f"go_taiwan_{post_id}"

        return Event(
            source_name="go_taiwan",
            source_id=source_id,
            source_url=url,
            original_language="ja",
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=venue_name,
            location_address=venue_address,
            is_paid=False,
            category=["tourism", "taiwan_japan"],
            is_active=True,
        )
