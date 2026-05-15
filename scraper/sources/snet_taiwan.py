"""Scraper for SNET台湾 (日本台湾教育支援研究者ネットワーク)

Source URL : https://www.snet-taiwan.jp/
API        : /wp-json/wp/v2/accomplishment?per_page=100
Source name: snet_taiwan
Source ID  : snet_taiwan_{wp_post_id}

Target events (3-5/year):
  - Japan-based symposia/lectures (「○○開催のお知らせ」系)
  - Taiwan study tours for Japanese students (大学生限定ツアー案内)
  - Educational contests (プランニング大賞 作品募集)

Filter strategy (title-based, no detail-page fetch required for gating):
  INCLUDE: 開催のお知らせ | 申し込み | 申込 | プランニング大賞 | 作品募集 |
           ツアー.*ご案内 | ご案内.*ツアー | 限定.*ツアー
  EXCLUDE: アカデミー.*第\\d+回 | 受賞作品が決定 | 研修.*派遣 | 講師.*派遣 |
           事前学習 | 事後学習

Date extraction (from detail page get_text()):
  Priority 1: 日時　YYYY年M月D日 (symposium event line)
  Priority 2: Parenthetical  （YYYY年M月D日  (tour start date in title/body)
  Priority 3: 締切：YYYY年M月D日 (contest deadline → used as event proxy date)
  Priority 4: First bare YYYY年M月D日 in body
  Priority 5: WP publish date (fallback)

Venue: "会場|場所|開催場所" label in body text.
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "snet_taiwan"
API_URL = "https://www.snet-taiwan.jp/wp-json/wp/v2/accomplishment"

HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
    "Accept-Language": "ja,en;q=0.9",
}
REQUEST_DELAY = 0.5

# ---------------------------------------------------------------------------
# Filter patterns
# ---------------------------------------------------------------------------

_INCLUDE_RE = re.compile(
    r"開催のお知らせ"
    r"|申し込み|申込"
    r"|プランニング大賞"
    r"|作品募集"
    r"|ツアー.*ご案内|ご案内.*ツアー|限定.*ツアー|ツアー.*をプロデュース"
)
_EXCLUDE_RE = re.compile(
    r"アカデミー.*第\d+回"
    r"|受賞作品が決定"
    r"|研修.*派遣|講師.*派遣"
    r"|事前学習|事後学習"
)

# ---------------------------------------------------------------------------
# Date patterns
# ---------------------------------------------------------------------------

# 日時　2025年7月19日  /  日時：2026年5月3日
_DATE_JIJI_RE = re.compile(r"日時[　\s：:]*(\d{4})年(\d{1,2})月(\d{1,2})日")

# 締切：2026年11月13日
_DEADLINE_RE = re.compile(r"締切[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日")

# （2026年2月25日  — parenthetical tour start dates
_PAREN_DATE_RE = re.compile(r"[（(](\d{4})年(\d{1,2})月(\d{1,2})日")

# Bare YYYY年M月D日
_BARE_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

# 会場　早稲田大学早稲田キャンパス 3号館305教室
# Use + (one-or-more) separator so inline "場所」" phrases don't match.
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]+([^\n]{3,60})")


def _to_utc(m: re.Match) -> datetime:
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return datetime(y, mo, d, tzinfo=timezone.utc)


class SnetTaiwanScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        try:
            r = requests.get(
                API_URL,
                params={
                    "per_page": 100,
                    "_fields": "id,title,date,link",
                    "orderby": "date",
                    "order": "desc",
                },
                headers=HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            posts = r.json()
        except Exception as e:
            logger.error("snet_taiwan: WP API error: %s", e)
            return events

        logger.info("snet_taiwan: %d posts from API", len(posts))

        for post in posts:
            title_html = post["title"]["rendered"]
            # Strip HTML entities (WP may encode &amp; etc.)
            title_plain = BeautifulSoup(title_html, "html.parser").get_text()

            if not _INCLUDE_RE.search(title_plain):
                continue
            if _EXCLUDE_RE.search(title_plain):
                continue

            event = self._parse_detail(post, title_plain)
            if event:
                events.append(event)
            time.sleep(REQUEST_DELAY)

        logger.info("SnetTaiwanScraper: %d events scraped", len(events))
        return events

    # ------------------------------------------------------------------

    def _parse_detail(self, post: dict, title_plain: str) -> Event | None:
        source_id = f"snet_taiwan_{post['id']}"
        url = post["link"]

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            logger.warning("snet_taiwan: detail fetch failed %s: %s", url, e)
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        full_text = soup.get_text(" ", strip=True).replace("\x00", "")
        # Newline-separated text preserves block boundaries — used for venue
        # extraction so _VENUE_RE stops at the end of the venue line.
        full_text_nl = soup.get_text("\n", strip=True).replace("\x00", "")

        # Title: prefer <h3> (Elementor article heading); fallback to API title
        h3 = soup.find("h3")
        raw_title = (
            h3.get_text(strip=True).replace("\x00", "") if h3 else title_plain
        )

        # Body text: prefer <main> for cleaner output
        main_el = soup.select_one("main") or soup.body
        body_text = (
            main_el.get_text(" ", strip=True).replace("\x00", "")
            if main_el
            else full_text
        )

        # ------------------------------------------------------------------
        # start_date — 5-priority cascade
        # ------------------------------------------------------------------
        start_date: datetime | None = None

        m = _DATE_JIJI_RE.search(full_text)
        if m:
            start_date = _to_utc(m)

        if start_date is None:
            m = _PAREN_DATE_RE.search(full_text)
            if m:
                start_date = _to_utc(m)

        if start_date is None:
            m = _DEADLINE_RE.search(full_text)
            if m:
                start_date = _to_utc(m)

        if start_date is None:
            m = _BARE_DATE_RE.search(full_text)
            if m:
                start_date = _to_utc(m)

        if start_date is None:
            try:
                pub = post["date"]  # "2026-05-13T09:00:00"
                dt = datetime.fromisoformat(pub)
                start_date = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            except Exception:
                logger.warning("snet_taiwan: no date for %s", url)
                return None

        # Prepend date line to raw_description (SKILL convention)
        date_prefix = (
            f"開催日時: {start_date.year}年"
            f"{start_date.month:02d}月{start_date.day:02d}日\n\n"
        )
        raw_description = (date_prefix + body_text)[:3000]

        # ------------------------------------------------------------------
        # Venue
        # ------------------------------------------------------------------
        location_name: str | None = None
        mv = _VENUE_RE.search(full_text_nl)
        if mv:
            location_name = mv.group(1).strip()[:80]

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=raw_title,
            raw_title=raw_title,
            raw_description=raw_description,
            start_date=start_date,
            location_name=location_name,
            organizer="SNET台湾（日本台湾教育支援研究者ネットワーク）",
            organizer_url="https://www.snet-taiwan.jp/",
        )
