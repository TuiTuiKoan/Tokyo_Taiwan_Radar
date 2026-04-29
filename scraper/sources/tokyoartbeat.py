"""
Tokyo Art Beat scraper — Contentful CDA API 経由で台湾関連アート展示を取得。

• Contentful スペース: j05yk38inose (公開 CDA トークン、ブラウザネットワークで確認済み)
• 「台湾」「Taiwan」でフルテキスト検索し、現在〜将来のイベントのみ取得
• 全国のギャラリー・美術館のイベントを対象（TokyoArtBeat は全国展覧会情報を掲載）

旧実装（Playwright + JS レンダリング）は query=台湾 がサーバー側で無視されるため
0件取得になっていた。Contentful API への直接アクセスに切り替え。
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event

CONTENTFUL_SPACE = "j05yk38inose"
CONTENTFUL_ENV = "master"
# 公開 Content Delivery API トークン（ブラウザネットワークリクエストから確認済み、読み取り専用）
CONTENTFUL_TOKEN = "pX663MZtc4BJd-IFo_VZOpqYtz7K9xrSxtBe2Vg33ic"
CONTENTFUL_BASE = (
    f"https://cdn.contentful.com/spaces/{CONTENTFUL_SPACE}"
    f"/environments/{CONTENTFUL_ENV}/entries"
)
TAB_EVENT_BASE = "https://www.tokyoartbeat.com/events/-/"

TAIWAN_QUERIES = ["台湾", "Taiwan"]


class TokyoArtBeatScraper(BaseScraper):
    """Tokyo Art Beat の Contentful API 経由で台湾関連展示イベントを取得。"""

    SOURCE_NAME = "tokyoartbeat"

    def scrape(self) -> list[Event]:
        today = date.today().isoformat()

        # Collect unique events across both queries (dedup by sys.id)
        seen_ids: set[str] = set()
        raw_items: list[tuple[dict, dict]] = []  # (item, linked_entries_map)

        for query in TAIWAN_QUERIES:
            params = {
                "content_type": "event",
                "locale": "*",
                "query": query,
                "fields.scheduleEndsOn[gte]": today,
                "limit": 200,
                "include": 1,  # resolve venue links (depth=1)
                "access_token": CONTENTFUL_TOKEN,
            }
            try:
                r = requests.get(CONTENTFUL_BASE, params=params, timeout=20)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                self.logger.warning("Contentful query '%s' failed: %s", query, e)
                continue

            includes = data.get("includes", {})
            linked_map: dict[str, dict] = {
                e["sys"]["id"]: e for e in includes.get("Entry", [])
            }

            for item in data.get("items", []):
                item_id = item["sys"]["id"]
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    raw_items.append((item, linked_map))

        events: list[Event] = []
        for item, linked_map in raw_items:
            event = self._parse_event(item, linked_map)
            if event:
                events.append(event)

        return events

    # ------------------------------------------------------------------

    def _parse_event(
        self, item: dict, linked_map: dict[str, dict]
    ) -> Optional[Event]:
        try:
            f = item.get("fields", {})
            item_id = item["sys"]["id"]

            # ── Title ─────────────────────────────────────────────────
            event_name_f = f.get("eventName", {})
            name_ja = self._loc(event_name_f, "ja-JP") or self._loc(
                event_name_f, "en-US"
            )
            name_en = self._loc(event_name_f, "en-US")
            if not name_ja:
                return None

            # ── Dates ─────────────────────────────────────────────────
            start_str = self._loc(f.get("scheduleStartsOn", {}), "en-US")
            end_str = self._loc(f.get("scheduleEndsOn", {}), "en-US")
            start_date = self._parse_date(start_str)
            end_date = self._parse_date(end_str)

            # ── Slug / URL ────────────────────────────────────────────
            slug = self._loc(f.get("slug", {}), "en-US") or ""
            source_url = TAB_EVENT_BASE + slug if slug else ""

            # ── Official URL ──────────────────────────────────────────
            official_url = (
                self._loc(f.get("showsWebpage", {}), "en-US")
                or self._loc(f.get("showsWebpage", {}), "ja-JP")
                or source_url
            )

            # ── Description ───────────────────────────────────────────
            desc_f = f.get("description", {})
            desc_ja = self._loc(desc_f, "ja-JP") or self._loc(desc_f, "en-US") or ""
            desc_en = self._loc(desc_f, "en-US") or ""

            # ── Venue ─────────────────────────────────────────────────
            venue_ref = f.get("venue", {})
            venue_ref_val = (
                venue_ref.get("en-US") if isinstance(venue_ref, dict) else venue_ref
            )
            venue_name = ""
            venue_address = ""
            if isinstance(venue_ref_val, dict):
                venue_id = venue_ref_val.get("sys", {}).get("id", "")
                linked = linked_map.get(venue_id, {})
                lf = linked.get("fields", {})
                venue_name = self._loc(lf.get("fullName", {}), "en-US") or ""
                venue_address = self._loc(lf.get("address", {}), "en-US") or ""

            # ── Fee ───────────────────────────────────────────────────
            fee_f = f.get("fee", {})
            fee_text = self._loc(fee_f, "ja-JP") or self._loc(fee_f, "en-US") or ""
            is_paid = bool(
                fee_text
                and fee_text.strip()
                and "free" not in fee_text.lower()
                and "無料" not in fee_text
            )

            return Event(
                source_name=self.SOURCE_NAME,
                source_id=f"tokyoartbeat_{item_id}",
                source_url=source_url,
                original_language="en",
                name_ja=name_ja,
                raw_title=name_en or name_ja,
                raw_description=desc_en or desc_ja,
                start_date=start_date,
                end_date=end_date,
                location_name=venue_name,
                location_address=venue_address,
                category=["art"],
                is_paid=is_paid,
                official_url=official_url,
            )
        except Exception as e:
            self.logger.warning(
                "Failed to parse event %s: %s", item.get("sys", {}).get("id"), e
            )
            return None

    @staticmethod
    def _loc(field: dict, locale: str) -> str:
        """ロケールキーからフィールド値を取得する。"""
        if not isinstance(field, dict):
            return str(field) if field else ""
        v = field.get(locale, "")
        if isinstance(v, dict) or isinstance(v, list):
            return ""
        return str(v) if v else ""

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            d = date.fromisoformat(date_str)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            return None
