"""Scraper for 台湾史研究会 (Taiwan History Research Society) — 定例研究会 posts.

Source URL : https://taiwanshi.exblog.jp/i3/
Feed URL   : https://taiwanshi.exblog.jp/atom.xml
Platform   : Excite Blog (exblog.jp) — Atom 0.3 feed with full CDATA content
Source name: taiwanshi
Source ID  : taiwanshi_{post_id}  (8-digit numeric post ID from URL)

The society holds monthly academic meetings (例会) on Taiwan history,
typically hybrid (in-person + Google Meet). Physical venues vary across
Japan (not exclusively Tokyo).
"""

import html as html_lib
import logging
import re
import requests
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "taiwanshi"
FEED_URL = "https://taiwanshi.exblog.jp/atom.xml"

# Atom 0.3 declares xmlns="http://www.w3.org/2005/Atom" (same NS as Atom 1.0)
_ATOM_NS = "http://www.w3.org/2005/Atom"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_NS = {"a": _ATOM_NS, "dc": _DC_NS}

_JST = timezone(timedelta(hours=9))
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Prefectures pattern for address extraction
_PREF_PATT = (
    r"(?:東京都|大阪府|京都府|神奈川県|愛知県|福岡県|兵庫県|埼玉県|千葉県|"
    r"北海道|宮城県|広島県|静岡県|茨城県|岡山県|新潟県|長野県|栃木県|"
    r"群馬県|滋賀県|岐阜県|山口県|奈良県|熊本県|石川県|島根県|鹿児島県)"
)


def _strip_html(raw: str) -> str:
    """Convert CDATA HTML to plain text (one logical line per <br />)."""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _extract_start_date(text: str) -> datetime | None:
    """Extract event start datetime from 日時：line."""
    m = re.search(
        r"日時[：:\s\u3000]*\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
        r"[（(]?[^)）\d]*[)）]?"              # 曜日 e.g. （土）
        r"\s*(?:(\d{1,2})時(\d{2})分)?",    # optional HH時MM分
        text,
    )
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour = int(m.group(4)) if m.group(4) else 0
    minute = int(m.group(5)) if m.group(5) else 0
    return datetime(year, month, day, hour, minute, tzinfo=_JST)


def _extract_venue(text: str) -> tuple[str | None, str | None]:
    """Return (location_name, location_address) from 会場：block."""
    m = re.search(r"(?:会場|場所)[\uff1a:\u3000 \t]+(.+)", text)
    if not m:
        return None, None

    venue_line = m.group(1).strip()

    # Strip online suffix: 「およびGoogle Meet…」「及びZoom…」「オンライン…」etc.
    venue_name = re.split(
        r"[、,]?\s*(?:および|及び|またはGoogle|Google Meet|Zoom|オンライン)", venue_line
    )[0].strip()

    # Remove trailing 「　（教室は未定）」style notes
    venue_name = re.sub(r"[\u3000\s]+（[^）]{1,20}）$", "", venue_name).strip()
    venue_name = venue_name or None

    # Look for prefecture-prefixed address in the ~3 lines after 会場：
    rest = text[m.end() :]
    addr_m = re.search(rf"({_PREF_PATT}[^\n]{{5,80}})", rest[:400])
    location_address = addr_m.group(1).strip() if addr_m else None

    return venue_name, location_address


class TaiwanshiScraper(BaseScraper):
    """Scrapes 台湾史研究会 monthly meeting announcements via Atom feed."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        try:
            resp = requests.get(
                FEED_URL,
                timeout=20,
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("taiwanshi: feed fetch failed: %s", exc)
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            logger.error("taiwanshi: XML parse error: %s", exc)
            return []

        events: list[Event] = []

        for entry in root.findall("a:entry", _NS):
            title_el = entry.find("a:title", _NS)
            link_el = entry.find("a:link[@rel='alternate']", _NS)
            content_el = entry.find("a:content", _NS)

            if title_el is None or link_el is None or content_el is None:
                continue

            title = (title_el.text or "").strip()
            url = link_el.get("href", "").replace("http://", "https://", 1)
            raw_html = content_el.text or ""

            # Extract stable 8-digit post ID from URL
            post_id_m = re.search(r"/(\d+)/?$", url)
            if not post_id_m:
                continue
            post_id = post_id_m.group(1)

            # Convert HTML to plain text for regex parsing
            text = _strip_html(raw_html)

            # Only process posts that contain a structured event date (日時：)
            if "日時" not in text:
                logger.debug("taiwanshi: no 日時 in post %s — skipping", post_id)
                continue

            start_date = _extract_start_date(text)
            if not start_date:
                logger.warning("taiwanshi: date parse failed for post %s", post_id)
                continue

            location_name, location_address = _extract_venue(text)

            date_header = (
                f"開催日時: {start_date.year}年"
                f"{start_date.month}月{start_date.day}日"
            )
            raw_description = f"{date_header}\n\n{text}"

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=f"taiwanshi_{post_id}",
                    source_url=url,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=raw_description,
                    category=["academic", "taiwan_japan"],
                    start_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                    is_paid=False,
                )
            )

        logger.info("taiwanshi: scraped %d events", len(events))
        return events
