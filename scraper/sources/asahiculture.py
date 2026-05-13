"""Scraper for 朝日カルチャーセンター（全国）

Search URL:
  https://www.asahiculture.com/asahiculture/asp-webapp/web/WKozaKensaku.do
  ?wbKozaKensakuJoken.keyWord=<SJIS-encoded>&wbKozaKensakuJoken.chikuId=0&kensakuKubun=0

Platform   : Legacy Java webapp (Struts); static HTML after Shift-JIS keyword search
Source name: asahiculture
Source ID  : asahiculture_{kozaId}  (unique numeric course ID in URL)

Strategy:
  1. Search with keyword "台湾" encoded as Shift-JIS (%91%E4%98p)
  2. Parse div.program-list cards from search results
  3. Extract: title (h2), branch (li.text-school*), start_date (li.list-time),
             description snippet, detail URL (a[href*=kozaId])
  4. For each detail page, fetch fuller description (optional)
  5. Taiwan filter is implicit (keyword search already filters)

Card selectors (confirmed 2026-05-13):
  div.program-list
    h2                   → raw_title
    li.text-school*      → branch name (e.g. 新宿教室, 川西教室)
    li.list-time         → "YYYY/MM/DD曜 ～ YYYY/MM/DD曜" range
    li.program-digest p  → description snippet
    a[href*=kozaId]      → detail URL

Detail page (WWebKozaShosaiNyuryoku.do?kozaId=NNN):
  h1 (2nd occurrence)     → title
  h2#日程 + text below    → "曜 YYYY/M/DD, M/DD"
  table tr[曜日・時間]    → schedule time
  教室 in breadcrumb area → location
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.asahiculture.com:443/asahiculture/asp-webapp/web"
SEARCH_URL = f"{BASE_URL}/WKozaKensaku.do"
DETAIL_URL = f"{BASE_URL}/WWebKozaShosaiNyuryoku.do"

# Shift-JIS encoded "台湾" — server rejects UTF-8 encoded keywords
TAIWAN_KEYWORD_SJIS = quote("台湾".encode("shift_jis"))  # %91%E4%98p

HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
    "Accept-Language": "ja,en;q=0.9",
}

REQUEST_DELAY = 0.5  # seconds between detail page fetches


class AsahiCultureScraper(BaseScraper):
    SOURCE_NAME = "asahiculture"

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        # Step 1: Keyword search (Shift-JIS encoded)
        url = (
            f"{SEARCH_URL}"
            f"?wbKozaKensakuJoken.keyWord={TAIWAN_KEYWORD_SJIS}"
            f"&wbKozaKensakuJoken.chikuId=0"
            f"&kensakuKubun=0"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = "MS932"
        except requests.RequestException as e:
            logger.error("asahiculture: fetch error: %s", e)
            return events

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", class_="program-list")
        logger.info("asahiculture: %d course cards found", len(cards))

        # Step 2: Parse each card
        for card in cards:
            event = self._parse_card(card)
            if event:
                events.append(event)
                time.sleep(REQUEST_DELAY)

        logger.info("AsahiCultureScraper: scraped %d events", len(events))
        return events

    # ------------------------------------------------------------------

    def _parse_card(self, card: BeautifulSoup) -> Event | None:
        # --- detail link / kozaId ---
        a_tag = card.find("a", href=lambda h: h and "kozaId" in str(h))
        if not a_tag:
            return None
        detail_link = a_tag["href"]
        koza_match = re.search(r"kozaId=(\d+)", detail_link)
        if not koza_match:
            return None
        koza_id = koza_match.group(1)
        source_id = f"asahiculture_{koza_id}"

        # --- title ---
        h2 = card.find("h2")
        if not h2:
            return None
        raw_title = h2.get_text(separator=" ", strip=True)

        # --- branch / venue ---
        school_li = card.find("li", class_=re.compile(r"text-school"))
        branch = school_li.get_text(strip=True) if school_li else ""

        # --- start date ---
        time_lis = card.find_all("li", class_="list-time")
        date_text = " ".join(li.get_text(strip=True) for li in time_lis)
        start_date = self._parse_date(date_text)
        if start_date is None:
            return None

        # --- description snippet ---
        digest = card.find("li", class_="program-digest")
        description = digest.get_text(separator="\n", strip=True) if digest else ""

        # --- Taiwan keyword check (safety net on full card text) ---
        card_text = card.get_text()
        if not any(kw in card_text for kw in ["台湾", "Taiwan", "臺灣"]):
            return None

        # --- Fetch detail page for fuller description ---
        detail_description = self._fetch_detail_description(koza_id)
        if detail_description:
            description = detail_description

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            raw_title=raw_title,
            raw_description=description,
            start_date=start_date,
            source_url=detail_link,
            location_name=branch,
            original_language="ja",
        )

    def _parse_date(self, date_text: str) -> datetime | None:
        """Extract earliest date from strings like '2026/04/07火～ 2026/06/16火'."""
        m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", date_text)
        if not m:
            return None
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    def _fetch_detail_description(self, koza_id: str) -> str:
        """Fetch course detail page and return description text."""
        try:
            r = requests.get(
                DETAIL_URL,
                params={"kozaId": koza_id},
                headers=HEADERS,
                timeout=15,
            )
            r.encoding = "MS932"
            soup = BeautifulSoup(r.text, "html.parser")

            # Description is usually the longest paragraph block
            # Find the section after the summary header
            # The page has a "詳細を見る" section that expands to full description
            # Fallback: grab all paragraph text near 台湾 mentions
            paragraphs = soup.find_all("p")
            relevant = []
            for p in paragraphs:
                txt = p.get_text(strip=True)
                if len(txt) > 50 and any(kw in txt for kw in ["台湾", "Taiwan"]):
                    relevant.append(txt)
            if relevant:
                return "\n".join(relevant[:3])

            # Fallback: first long paragraph
            for p in paragraphs:
                txt = p.get_text(strip=True)
                if len(txt) > 80:
                    return txt[:500]
        except requests.RequestException as e:
            logger.warning("asahiculture: detail fetch error kozaId=%s: %s", koza_id, e)
        return ""
