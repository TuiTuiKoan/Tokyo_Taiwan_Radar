"""
Eurospace Cinema scraper — 渋谷のミニシアター（ユーロスペース）の上映中・近日公開作品を取得。
台湾制作（または台湾に言及）した映画をイベントとして登録する。

⚠️  HTTPS は SSL/TLS 互換性の問題でアクセス不可。HTTP を使用すること。
    理由: サーバー側が古い TLS 設定（Python 3.14 の strict SSL と非互換）
"""

import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

BASE_URL = "http://www.eurospace.co.jp"

TAIWAN_KEYWORDS = ["台湾", "Taiwan", "taiwan"]

logger = logging.getLogger(__name__)


class EurospaceScraper(BaseScraper):
    SOURCE_NAME = "eurospace"

    def scrape(self) -> list[Event]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        work_ids: list[str] = []
        # Current films (homepage) + upcoming films (/works/)
        for url in [BASE_URL + "/", BASE_URL + "/works/"]:
            ids = self._fetch_work_ids(url, headers)
            for wid in ids:
                if wid not in work_ids:
                    work_ids.append(wid)

        events: list[Event] = []
        for wid in work_ids:
            event = self._scrape_detail(wid, headers)
            if event:
                events.append(event)
            time.sleep(0.5)

        return events

    # ------------------------------------------------------------------
    def _fetch_work_ids(self, url: str, headers: dict) -> list[str]:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            ids = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = re.search(r"detail\.php\?w_id=(\d+)", href)
                if m:
                    ids.append(m.group(1))
            return ids
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return []

    def _scrape_detail(self, w_id: str, headers: dict) -> Optional[Event]:
        url = f"{BASE_URL}/works/detail.php?w_id={w_id}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")

            section = soup.find("section", id="workDetail")
            if not section:
                return None

            # ── 台湾チェック ──────────────────────────────────────
            caption_el = section.find("p", class_="work-caption")
            text_el = section.find("p", class_="work-text")
            caption_text = caption_el.get_text() if caption_el else ""
            body_text = text_el.get_text() if text_el else ""
            combined = caption_text + " " + body_text
            if not any(kw in combined for kw in TAIWAN_KEYWORDS):
                return None

            # ── タイトル ──────────────────────────────────────────
            h2 = section.find("h2")
            if not h2:
                return None
            title = h2.get_text().strip()
            if not title:
                return None

            # ── 公開日 / 上映期間 ─────────────────────────────────
            h3 = section.find("h3")
            date_text = h3.get_text().strip() if h3 else ""
            start_date, end_date = self._parse_date_range(date_text, section)

            # ── info ブロック (p.ttl → p.info) ───────────────────
            info_blocks: dict[str, str] = {}
            for li in section.select("ul.work-info li"):
                ttl_el = li.find("p", class_="ttl")
                info_el = li.find("p", class_="info")
                if ttl_el and info_el:
                    info_blocks[ttl_el.get_text().strip()] = info_el.get_text(
                        separator=" "
                    ).strip()

            official_url = ""
            if "公式サイト" in info_blocks:
                official_url = info_blocks["公式サイト"].strip()

            # ── 説明文 ────────────────────────────────────────────
            description = body_text.strip()
            tagline_el = section.find("h4")
            if tagline_el:
                tagline = tagline_el.get_text().strip()
                if tagline:
                    description = tagline + "\n\n" + description

            # ── 国・年度 (caption: "2024／台湾、フィリピン、韓国／…") ──
            country = ""
            year = ""
            if caption_text:
                parts = [p.strip() for p in caption_text.strip().split("／")]
                if parts:
                    year_m = re.match(r"(\d{4})", parts[0])
                    if year_m:
                        year = year_m.group(1)
                if len(parts) >= 2:
                    country = parts[1]

            name_zh, name_en, _ = lookup_movie_titles(title)

            return Event(
                source_name=self.SOURCE_NAME,
                source_id=f"eurospace_{w_id}",
                source_url=url,
                original_language="ja",
                name_ja=title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=title,
                raw_description=description,
                start_date=start_date,
                end_date=end_date,
                location_name="ユーロスペース",
                location_address="東京都渋谷区円山町1-5 KINOHAUS 3F・4F",
                category=["movie"],
                is_paid=True,
                official_url=official_url or url,
            )
        except Exception as e:
            logger.warning("Failed to scrape detail w_id=%s: %s", w_id, e)
            return None

    def _parse_date_range(
        self, date_text: str, section: BeautifulSoup
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """h3 のテキストから公開日・終了日を解析する。

        まで suffix を最優先で検出し、Pattern A が誤って終了日を
        start_date に塩込むバグを防止する。

        パターン:
        - "5月30日（土）公開"   →  (5/30, None)
        - "6/10（水）まで"     →  (上映時間首日, 6/10)
        - "5月3日まで"        →  (上映時間首日, 5/3)
        - "上映中"            →  (上映時間首日, None)
        """
        today = date.today()
        year = today.year

        def _to_dt(d: date) -> datetime:
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

        def _make_date(month: int, day: int) -> Optional[date]:
            try:
                d = date(year, month, day)
                if (today - d).days > 365:
                    d = date(year + 1, month, day)
                return d
            except ValueError:
                return None

        def _first_showtime_date() -> Optional[datetime]:
            """上映時間ブロックから最初の日付を抽出"""
            for li in section.select("ul.work-info li"):
                ttl_el = li.find("p", class_="ttl")
                if ttl_el and "上映時間" in ttl_el.get_text():
                    info_el = li.find("p", class_="info")
                    if info_el:
                        sm = re.search(r"(\d{1,2})月(\d{1,2})日", info_el.get_text())
                        if sm:
                            d = _make_date(int(sm.group(1)), int(sm.group(2)))
                            return _to_dt(d) if d else None
            return None

        # ── まで suffix を最優先で検出 ──────────────────────────────────────
        # Pattern C: X月X日まで  →  end_date = その日付; start_date = 上映時間首日
        m = re.search(r"(\d{1,2})月(\d{1,2})日.*?まで", date_text)
        if m:
            end_d = _make_date(int(m.group(1)), int(m.group(2)))
            end_dt = _to_dt(end_d) if end_d else None
            start_dt = _first_showtime_date()
            return start_dt, end_dt

        # Pattern C': X/Xまで  →  end_date = その日付; start_date = 上映時間首日
        m = re.search(r"(\d{1,2})/(\d{1,2}).*?まで", date_text)
        if m:
            end_d = _make_date(int(m.group(1)), int(m.group(2)))
            end_dt = _to_dt(end_d) if end_d else None
            start_dt = _first_showtime_date()
            return start_dt, end_dt

        # 上映中（まで なし）→ start_date = 上映時間首日, end_date = None
        if "上映中" in date_text:
            return _first_showtime_date(), None

        # Pattern A: X月X日（公開/から）→ start_date; end_date = None
        m = re.search(r"(\d{1,2})月(\d{1,2})日", date_text)
        if m:
            d = _make_date(int(m.group(1)), int(m.group(2)))
            return (_to_dt(d) if d else None), None

        # Pattern B: X/X 公開 → start_date; end_date = None
        m = re.search(r"(\d{1,2})/(\d{1,2})", date_text)
        if m and "公開" in date_text:
            d = _make_date(int(m.group(1)), int(m.group(2)))
            return (_to_dt(d) if d else None), None

        return None, None
