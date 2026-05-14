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

ORGANIZER = "朝日カルチャーセンター"

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

        # --- branch / venue (card-level; may be admin branch, not actual venue) ---
        school_li = card.find("li", class_=re.compile(r"text-school"))
        card_branch = school_li.get_text(strip=True) if school_li else ""

        # --- date range: start + end ---
        time_lis = card.find_all("li", class_="list-time")
        date_text = " ".join(li.get_text(strip=True) for li in time_lis)
        start_date, end_date = self._parse_date_range(date_text)
        if start_date is None:
            return None

        # --- description snippet (may be replaced by detail page) ---
        digest = card.find("li", class_="program-digest")
        description = digest.get_text(separator="\n", strip=True) if digest else ""

        # --- Taiwan keyword check (safety net on full card text) ---
        card_text = card.get_text()
        if not any(kw in card_text for kw in ["台湾", "Taiwan", "臺灣"]):
            return None

        # --- Fetch detail page: actual venue, performer, business_hours, fuller desc ---
        detail = self._fetch_detail(koza_id)
        if detail["description"]:
            description = detail["description"]

        # Prefer detail-page venue (e.g. satellite classroom); fall back to card branch
        location_name = detail["location_name"] or card_branch

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            raw_title=raw_title,
            raw_description=description,
            start_date=start_date,
            end_date=end_date,
            source_url=detail_link,
            location_name=location_name,
            location_address=detail["location_address"],
            business_hours=detail["business_hours"],
            performer=detail["performer"],
            organizer=ORGANIZER,
            original_language="ja",
        )

    def _parse_date_range(self, date_text: str) -> tuple[datetime | None, datetime | None]:
        """Extract (start_date, end_date) from strings like '2026/04/07火～ 2026/06/16火'.

        Returns (start, end) where end is None for single-day courses.
        """
        matches = re.findall(r"(\d{4})/(\d{1,2})/(\d{1,2})", date_text)
        if not matches:
            return None, None
        try:
            start = datetime(int(matches[0][0]), int(matches[0][1]), int(matches[0][2]))
            end = (
                datetime(int(matches[-1][0]), int(matches[-1][1]), int(matches[-1][2]))
                if len(matches) > 1
                else None
            )
            return start, end
        except ValueError:
            return None, None

    def _fetch_detail(self, koza_id: str) -> dict:
        """Fetch course detail page; return dict with description, venue, business_hours, performer.

        Keys: description (str), location_name (str|None), location_address (str|None),
              business_hours (str|None), performer (str|None)

        Design notes:
        - location_name: extracted from 備考 table row; satellite/external venues appear
          here as 「会場名」, while the card only shows the admin branch (e.g. 新宿教室).
        - business_hours: extracted from 曜日・時間 table row.
        - performer: extracted from h3 lecturer heading (pattern: Kanji Kanji（reading）Role).
        """
        result: dict = {
            "description": "",
            "location_name": None,
            "location_address": None,
            "business_hours": None,
            "performer": None,
        }
        try:
            r = requests.get(
                DETAIL_URL,
                params={"kozaId": koza_id},
                headers=HEADERS,
                timeout=15,
            )
            r.encoding = "MS932"
            soup = BeautifulSoup(r.text, "html.parser")

            # --- Table rows: 曜日・時間 (business hours) and 備考 (satellite venue) ---
            for tr in soup.find_all("tr"):
                th_tag = tr.find("th")
                td_tag = tr.find("td")
                if not (th_tag and td_tag):
                    continue
                label = th_tag.get_text(strip=True)
                value = td_tag.get_text(" ", strip=True)

                if "曜日" in label or "時間" in label:
                    # e.g. "火曜\u300011:45～13:15"
                    result["business_hours"] = re.sub(r"[\u3000\s]+", " ", value).strip()

                if "備考" in label:
                    # Satellite/external venue announced in「…」brackets
                    loc_m = re.search(r"「([^」]+)」", value)
                    if loc_m:
                        result["location_name"] = loc_m.group(1)
                    # Address: starts with a prefecture name
                    addr_m = re.search(
                        r"((?:東京都|神奈川県|大阪府|京都府|兵庫県|愛知県|福岡県|北海道|宮城県|広島県"
                        r"|埼玉県|千葉県|静岡県|新潟県|[^\s]{3}[都道府県])[^（。\n]+)",
                        value,
                    )
                    if addr_m:
                        result["location_address"] = addr_m.group(1).strip()

            # --- Performer: h3 with Japanese name pattern "姓 名 （よみ）役職" ---
            for h3 in soup.find_all("h3"):
                txt = h3.get_text(" ", strip=True)
                # Match: 1-6 CJK chars, space(s), 1-6 CJK chars, then （
                m = re.match(
                    r"([\u4e00-\u9fff]{1,6}[\s\u3000]+[\u4e00-\u9fff]{1,6})[\s\u3000]*[（(]",
                    txt,
                )
                if m:
                    name = re.sub(r"[\u3000\s]+", " ", m.group(1)).strip()
                    result["performer"] = name
                    break

            # --- Description: paragraphs containing Taiwan keywords ---
            paragraphs = soup.find_all("p")
            relevant = [
                p.get_text(strip=True)
                for p in paragraphs
                if len(p.get_text(strip=True)) > 50
                and any(kw in p.get_text() for kw in ["台湾", "Taiwan"])
            ]
            if relevant:
                result["description"] = "\n".join(relevant[:3])
            else:
                for p in paragraphs:
                    txt = p.get_text(strip=True)
                    if len(txt) > 80:
                        result["description"] = txt[:500]
                        break

        except requests.RequestException as e:
            logger.warning("asahiculture: detail fetch error kozaId=%s: %s", koza_id, e)
        return result
