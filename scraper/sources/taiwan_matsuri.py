"""
Scraper for 台湾祭（taiwan-matsuri.com）.

"台湾祭" is a recurring food-and-culture festival (夜市 theme) held at major
venues across Japan. This scraper captures Tokyo/Kanto-area events only.

Strategy:
  1. Fetch the homepage (static HTML) and extract all event anchor links
     matching the pattern /YYYYMM-<slug>/
  2. Filter to events held in the Tokyo/Kanto area
  3. Fetch each qualifying detail page and extract title, dates,
     venue/address, and hours from the structured text block (●開催期間: etc.)
  4. source_id = "taiwan_matsuri_{slug}" — slug is stable across runs

No Playwright needed — the site is server-rendered static HTML.
"""

import re
import logging
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://taiwan-matsuri.com"
HOMEPAGE_URL = f"{BASE_URL}/"

# Tokyo/Kanto keywords in venue text — events outside this list are skipped.
# Matches: 東京, スカイツリー, 東京タワー, 横浜, 幕張, 千葉, 埼玉
_TOKYO_KANTO_KEYWORDS = re.compile(
    r"東京|スカイツリー|横浜|幕張|千葉|埼玉|東京タワー"
)

# Markers that indicate end of the event info block (stop extracting description there)
_NOISE_MARKERS = (
    "TAIWAN FOOD",
    "本場の味を再現",
    "COLLABORATION MENU",
    "PICK UP MENU",
    "Q & A",
    "よくあるご質問",
    "SNSでも情報発信",
    "お問い合わせ",
    "台湾祭とは",
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse date range from text like:
      "2026年4月4日(土)〜5月31日(日)"
      "2026/04/04〜05/31"
    Returns (start_date, end_date).
    """
    # Pattern 1: YYYY年M月D日 ... M月D日 (or end day only)
    m = re.search(
        r'(\d{4})年(\d{1,2})月(\d{1,2})日[^〜～\d]*[〜～]\s*(\d{1,2})月(\d{1,2})日',
        text
    )
    if m:
        year = int(m.group(1))
        try:
            start = datetime(year, int(m.group(2)), int(m.group(3)))
            end = datetime(year, int(m.group(4)), int(m.group(5)))
            return start, end
        except ValueError:
            pass

    # Pattern 2: YYYY/MM/DD〜MM/DD or YYYY/MM/DD〜YYYY/MM/DD
    m2 = re.search(r'(\d{4})/(\d{2})/(\d{2})[〜～](?:(\d{4})/)?(\d{2})/(\d{2})', text)
    if m2:
        year = int(m2.group(1))
        try:
            start = datetime(year, int(m2.group(2)), int(m2.group(3)))
            end_year = int(m2.group(4)) if m2.group(4) else year
            end = datetime(end_year, int(m2.group(5)), int(m2.group(6)))
            return start, end
        except ValueError:
            pass

    # Pattern 3: single date YYYY年M月D日
    m3 = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m3:
        try:
            d = datetime(int(m3.group(1)), int(m3.group(2)), int(m3.group(3)))
            return d, d
        except ValueError:
            pass

    return None, None


def _slug_from_url(url: str) -> Optional[str]:
    """Extract slug like '202604-skytree' from URL."""
    m = re.search(r'taiwan-matsuri\.com/(2\d{5}-[a-z0-9-]+)/?', url)
    return m.group(1) if m else None


class TaiwanMatsuriScraper(BaseScraper):
    """Scrapes Tokyo/Kanto 台湾祭 events from taiwan-matsuri.com."""

    SOURCE_NAME = "taiwan_matsuri"

    def scrape(self) -> list[Event]:
        soup = _fetch(HOMEPAGE_URL)
        if not soup:
            logger.error("Failed to fetch taiwan-matsuri.com homepage")
            return []

        # Collect all event links — both current and past
        event_links: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=re.compile(r'/2\d{5}-')):
            href = a.get("href", "")
            # Normalise URL
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = BASE_URL + href
            if not href.startswith("http"):
                href = BASE_URL + "/" + href.lstrip("/")
            # Remove query strings / fragments
            href = href.split("?")[0].split("#")[0].rstrip("/") + "/"
            if href not in seen:
                seen.add(href)
                event_links.append(href)

        logger.info("Found %d event links on homepage", len(event_links))

        # Filter to Tokyo/Kanto area by examining the link text
        tokyo_links: list[str] = []
        for a in soup.find_all("a", href=re.compile(r'/2\d{5}-')):
            href = a.get("href", "")
            if href.startswith("/"):
                href = BASE_URL + href
            href = href.split("?")[0].rstrip("/") + "/"
            link_text = a.get_text(" ", strip=True)
            if _TOKYO_KANTO_KEYWORDS.search(link_text):
                if href not in {u for u in tokyo_links}:
                    tokyo_links.append(href)

        logger.info("Tokyo/Kanto events: %d", len(tokyo_links))

        events: list[Event] = []
        for url in tokyo_links:
            slug = _slug_from_url(url)
            if not slug:
                continue
            try:
                event = self._scrape_detail(url, slug)
                if event:
                    events.append(event)
                    logger.info("  ✓ %s — %s", slug, event.name_ja[:60] if event.name_ja else "")
                time.sleep(1.0)
            except Exception as exc:
                logger.error("Failed to scrape %s: %s", url, exc)

        return events

    def _scrape_detail(self, url: str, slug: str) -> Optional[Event]:
        soup = _fetch(url)
        if not soup:
            return None

        lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

        # --- Title: first meaningful heading (longer than 5 chars, not nav/system text) ---
        title = ""
        skip_patterns = re.compile(
            r'^(INFO|SNS|FOOD|MENU|Q&A|SCHEDULE|CONTACT|STRENGTHS|STORY|CONTENTS|EVENT)$'
            r'|^雨天時|^©', re.IGNORECASE
        )
        for line in lines[:20]:
            if len(line) > 8 and not skip_patterns.match(line) and "台湾祭" in line:
                title = line
                break
        if not title:
            # Fallback: use <title> tag
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True).replace("｜台湾祭", "").strip()

        if not title:
            logger.warning("No title found at %s", url)
            return None

        # --- Parse structured block (●開催期間: etc.) ---
        full_text = "\n".join(lines)
        start_date, end_date = None, None
        location_name = None
        location_address = None
        business_hours = None

        # Date: ●開催期間：2026年4月4日(土)〜5月31日(日)
        date_m = re.search(r'[●・開催期間：:]+\s*(.{10,60}?(?:〜|～)[^\n]{5,30})', full_text)
        if date_m:
            start_date, end_date = _parse_dates(date_m.group(1))

        # Fallback: scan all lines for a date pattern
        if not start_date:
            for line in lines:
                s, e = _parse_dates(line)
                if s:
                    start_date, end_date = s, e
                    break

        # Venue: ●場所：東京スカイツリータウン® 4階スカイアリーナ
        venue_m = re.search(r'[●・]?場所[：:]\s*(.{5,80})', full_text)
        if venue_m:
            location_name = venue_m.group(1).strip().split("\n")[0].split("（")[0].strip()

        # Address: （東京都墨田区押上1丁目1-2) — brackets may be mixed full-width/ascii
        addr_m = re.search(r'[（(]([^）)]{1,60}(?:都|道|府|県)[^）)]{3,60})[）)]', full_text)
        if addr_m:
            location_address = addr_m.group(1).strip()
        elif location_name:
            location_address = location_name

        # Hours: ●営業時間：【平日】11:00〜21:00\n【土日祝】10:30〜21:30
        # Capture 【...】 blocks across multiple lines
        hours_m = re.search(
            r'[●・]?営業時間[：:]\s*(.*?)(?:\n[●・]|\Z)',
            full_text, re.DOTALL
        )
        if hours_m:
            raw_hours = hours_m.group(1)
            blocks = re.findall(r'【[^】]+】[^【\n]{1,50}', raw_hours)
            if blocks:
                business_hours = '\u3000'.join(b.strip() for b in blocks[:4])[:160]
            else:
                business_hours = re.sub(r'\s+', ' ', raw_hours).strip()[:120]

        # Single-day rule
        if start_date and not end_date:
            end_date = start_date

        # --- Description: opening paragraphs before noise ---
        desc_lines: list[str] = []
        in_desc = False
        for line in lines:
            if "開催決定" in line or "開催いたします" in line or "台湾祭とは" in line:
                in_desc = True
            if in_desc:
                if any(line.startswith(m) for m in _NOISE_MARKERS):
                    break
                # Skip bullet info lines (●...) and hours lines (【平日】...)
                if len(line) > 15 and not re.match(r'^[●・【]', line):
                    desc_lines.append(line)
            if len(desc_lines) >= 8:
                break
        description = "\n".join(desc_lines[:5]) if desc_lines else ""

        # Prepend date to raw_description
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date and end_date != start_date:
                date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
            date_prefix += "\n\n"

        raw_description = f"{date_prefix}{description}" if description else date_prefix

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=f"taiwan_matsuri_{slug}",
            source_url=url,
            original_language="ja",
            name_ja=title,
            description_ja=description or None,
            raw_title=title,
            raw_description=raw_description or None,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            business_hours=business_hours,
            is_paid=False,  # 入場料：無料 (confirmed on detail pages)
            category=["lifestyle_food", "tourism"],
        )
