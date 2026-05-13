"""
Scraper for RTI (Radio Taiwan International) Japanese-language programs.

Strategy:
  1. For each selected program, fetch the Podcast RSS feed:
     GET https://www.rti.org.tw/jp/programpodcasturl?id={program_id}
  2. Parse items — each episode has: title, pubDate, link (programnews URL), description
  3. Only include episodes published within LOOKBACK_DAYS
  4. Programs whose latest episode is older than STALE_DAYS are skipped (discontinued)
  5. source_id: rti_jp_{pid}  where pid is extracted from the link URL

Selected programs (music, culture, academic, business, history — NO general news):
  364  ミュージックステーション  performing_arts  (Taiwan T-POP / T-Rock weekly)
  378  文化の台湾      art + taiwan_japan    (Taiwan culture / arts biweekly)
  1456 ナルワンアワー  taiwan_japan         (Japan–Taiwan exchange topics weekly)

Active as of 2026-05-10:
  364  last episode: 2026-04-06 (33d)
  378  last episode: 2026-04-24 (15d)
  1456 last episode: 2026-05-04 (5d)

Previously included but discontinued (~July 2025):
  363  数字の台湾      (last: 2025-07-21, 292d ago)
  367  台湾ソフトパワー (last: 2025-07-22, 291d ago)
  375  生活中国語      (last: 2025-07-24, 289d ago)
  382  宝島再発見      (last: 2025-07-17, 296d ago)

Excluded (news / sports):
  73   ニュース&番組   (daily news — too high volume)
  371  対外関係        (political/diplomatic news)
  381  スポーツオンライン (sports)
  1558 きょうのキーワード (general current-affairs news)
  1567 こんにちは台湾  (general info / tourism news)

robots.txt: Allow: /jp/  (no restrictions on scraping this path)
Rendering: static XML RSS feed — no Playwright required
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional

import requests

from .base import BaseScraper, Event, dedup_events

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.rti.org.tw"
_PODCAST_RSS_URL = _BASE_URL + "/jp/programpodcasturl?id={program_id}"

# Episodes older than this many days are skipped.
# 60 days ensures we catch ミュージックステーション which publishes ~monthly.
LOOKBACK_DAYS = 60

# If a program's LATEST episode is older than this, the program is considered
# discontinued and is skipped entirely (avoids fetching dead RSS feeds).
STALE_DAYS = 90

# program_id → (name_ja, categories)
PROGRAMS: dict[int, tuple[str, list[str]]] = {
    364:  ("ミュージックステーション", ["performing_arts", "radio_program"]),
    378:  ("文化の台湾",              ["art", "taiwan_japan", "radio_program"]),
    1456: ("ナルワンアワー",          ["taiwan_japan", "radio_program"]),
}


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _parse_pubdate(pubdate_str: str) -> Optional[datetime]:
    """Parse RFC 2822 pubDate into a naive JST datetime."""
    try:
        dt = parsedate_to_datetime(pubdate_str)
        # Convert to JST (UTC+8), then make naive
        jst = timezone(timedelta(hours=8))
        return dt.astimezone(jst).replace(tzinfo=None)
    except Exception:
        return None


def _extract_pid(link: str) -> Optional[str]:
    """Extract pid query param from a programnews URL.

    The RSS feed double-encodes '&' as '&amp;', so the raw link text may look
    like '?uid=4&amp;pid=103701'.  Normalise before extracting.
    """
    normalised = link.replace("&amp;", "&")
    m = re.search(r"[?&]pid=(\d+)", normalised)
    return m.group(1) if m else None


class RtiJpScraper(BaseScraper):
    SOURCE_NAME = "rti_jp"

    def scrape(self) -> list[Event]:
        now = datetime.now()
        cutoff = now - timedelta(days=LOOKBACK_DAYS)
        headers = {"User-Agent": "Mozilla/5.0"}
        events: list[Event] = []

        for program_id, (program_name, categories) in PROGRAMS.items():
            rss_url = _PODCAST_RSS_URL.format(program_id=program_id)
            try:
                resp = requests.get(rss_url, headers=headers, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("rti_jp: RSS fetch failed for id=%s (%s): %s", program_id, program_name, exc)
                continue

            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as exc:
                logger.warning("rti_jp: XML parse error for id=%s: %s", program_id, exc)
                continue

            channel = root.find("channel")
            if channel is None:
                logger.warning("rti_jp: no <channel> in RSS for id=%s", program_id)
                continue

            items = channel.findall("item")
            if not items:
                logger.info("rti_jp: id=%s (%s) has 0 items — skipping", program_id, program_name)
                continue

            # Stale check: if the LATEST episode is older than STALE_DAYS, the
            # program is likely discontinued — skip to avoid 30-second fetch waste.
            latest_pubdate_el = items[0].find("pubDate")
            if latest_pubdate_el is not None and latest_pubdate_el.text:
                latest_dt = _parse_pubdate(latest_pubdate_el.text)
                if latest_dt and (now - latest_dt).days > STALE_DAYS:
                    logger.info(
                        "rti_jp: id=%s (%s) latest episode is %d days old — treating as discontinued",
                        program_id, program_name, (now - latest_dt).days,
                    )
                    continue

            for item in items:
                # pubDate → start_date
                pubdate_el = item.find("pubDate")
                if pubdate_el is None or not pubdate_el.text:
                    continue
                start_date = _parse_pubdate(pubdate_el.text)
                if start_date is None:
                    continue
                if start_date < cutoff:
                    continue

                # title
                title_el = item.find("title")
                raw_title = title_el.text.strip() if title_el is not None and title_el.text else ""
                if not raw_title:
                    continue

                # link → source_url + pid
                # The RSS feed double-encodes '&' as '&amp;' in the text node.
                link_el = item.find("link")
                link_raw = link_el.text.strip() if link_el is not None and link_el.text else ""
                link = link_raw.replace("&amp;", "&")
                if not link:
                    continue
                # Resolve relative URLs (the RSS emits absolute URLs, but be safe)
                if link.startswith("http"):
                    source_url = link
                else:
                    source_url = _BASE_URL + "/jp/" + link.lstrip("/")

                pid = _extract_pid(source_url)
                if not pid:
                    continue
                source_id = f"rti_jp_{pid}"

                # description → raw_description
                desc_el = item.find("description")
                desc_html = desc_el.text if desc_el is not None and desc_el.text else ""
                desc_plain = _strip_html(desc_html)

                # Build raw_description — prepend date per scraper convention
                date_str = f"{start_date.year}年{start_date.month}月{start_date.day}日"
                raw_description = (
                    f"開催日時: {date_str}\n\n"
                    f"番組: {program_name}\n"
                    f"RTI台湾国際放送（日本語部門）\n\n"
                    f"{desc_plain}"
                ).strip()

                events.append(Event(
                    source_name="rti_jp",
                    source_id=source_id,
                    source_url=source_url,
                    original_language="ja",
                    name_ja=raw_title,
                    raw_title=raw_title,
                    raw_description=raw_description,
                    start_date=start_date,
                    category=list(categories),
                    location_name="RTI台湾国際放送（日本語部門）",
                    location_url="https://www.rti.org.tw/jp",
                    event_form=["ラジオ放送"],
                ))

            time.sleep(0.5)

        result = dedup_events(events)
        logger.info("rti_jp: %d events after dedup", len(result))
        return result
