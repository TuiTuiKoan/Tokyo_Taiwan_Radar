"""
Regression tests for the Taiwan Cultural Center external-venue override.

The TCC scraper defaults the location to the centre itself (correct for the
majority of TCC-hosted events). `_extract_explicit_location_from_body` is an
additive override-on-signal helper: it returns an external venue ONLY when the
body carries an explicit venue label or a known external hall, otherwise None so
the TCC default is preserved.

Covers the three plan-mandated cases:
  (a) Waseda venue detected               -> override the TCC default
  (b) TCC organiser/contact only, no label -> keep the TCC default (no override)
  (c) Generic non-Waseda `会場：<venue>`    -> override (helper is not Waseda-only)
"""
from types import SimpleNamespace

import database

from sources.taiwan_cultural_center import (
        TaiwanCulturalCenterScraper,
    _extract_explicit_location_from_body,
    _detect_multi_city_prefectures,
)


# ──────────────────────────────────────────────────────────────────────────────
# (a) External Waseda venue detected -> override
# ──────────────────────────────────────────────────────────────────────────────
class TestWasedaVenueDetected:
    def test_named_hall_without_label(self):
        # Reinforcement whitelist: a known external hall mentioned in prose.
        text = "台湾布袋戯文化月間。本展は早稲田大学坪内博士記念演劇博物館で開催します。"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "早稲田大学坪内博士記念演劇博物館"
        assert pref == "東京都"

    def test_ono_hall_with_venue_label(self):
        text = "会場：小野記念講堂\n日時：2025年7月12日 17:00〜"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "小野記念講堂"
        assert pref == "東京都"

    def test_waseda_gallery_whitelist(self):
        text = "関連展示はワセダギャラリーにて。"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "ワセダギャラリー"
        assert pref == "東京都"


# ──────────────────────────────────────────────────────────────────────────────
# (b) TCC organiser/contact only -> keep the TCC default (NO override)
#     Guards the 15 no-venue-label TCC events that legitimately run at the centre.
# ──────────────────────────────────────────────────────────────────────────────
class TestTccDefaultPreserved:
    def test_organizer_and_contact_only(self):
        text = (
            "台湾文化体験講座のご案内。\n"
            "主催：台北駐日経済文化代表処 台湾文化センター\n"
            "お問い合わせ：台湾文化センター TEL 03-xxxx-xxxx"
        )
        name, pref = _extract_explicit_location_from_body(text)
        assert name is None
        assert pref is None

    def test_venue_label_pointing_at_tcc_is_not_external(self):
        # `会場：…台湾文化センター…` is the centre itself, not an external venue.
        text = "会場：台北駐日経済文化代表処 台湾文化センター 2階"
        name, pref = _extract_explicit_location_from_body(text)
        assert name is None
        assert pref is None

    def test_empty_and_none(self):
        assert _extract_explicit_location_from_body("") == (None, None)
        assert _extract_explicit_location_from_body(None) == (None, None)

    def test_no_venue_signal_returns_none(self):
        text = "台湾の映画文化を紹介するイベントです。参加無料。"
        assert _extract_explicit_location_from_body(text) == (None, None)


# ──────────────────────────────────────────────────────────────────────────────
# (c) Generic non-Waseda venue label -> override (helper is NOT Waseda-only)
# ──────────────────────────────────────────────────────────────────────────────
class TestGenericExternalVenue:
    def test_generic_label_with_prefecture(self):
        text = "会場：大阪府立国際会議場（グランキューブ大阪）"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "大阪府立国際会議場"
        assert pref == "大阪府"  # derived from the full prefecture name in the string

    def test_generic_label_without_known_prefecture(self):
        text = "場所：横浜赤レンガ倉庫1号館\nお問い合わせ：台湾文化センター"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "横浜赤レンガ倉庫1号館"
        assert pref is None  # not a known hall, no full prefecture token -> unknown


# ──────────────────────────────────────────────────────────────────────────────
# Precedence sanity: the multi-city detector remains independent and unchanged.
# ──────────────────────────────────────────────────────────────────────────────
class TestMultiCityStillWorks:
    def test_multi_city_uses_full_prefecture_names(self):
        text = "会場：東京都／会場：大阪府 で順次開催。"
        found = _detect_multi_city_prefectures(text)
        assert "東京都" in found
        assert "大阪府" in found


class _TextElement:
    def __init__(self, text):
        self._text = text

    def inner_text(self):
        return self._text


class _DetailPage:
    def __init__(self, title, description):
        self._texts = {
            ".simple-text.title": title,
            ".essay": description,
            ".list-text.detail": "日付：2026-08-01",
        }

    def goto(self, *_args, **_kwargs):
        return None

    def query_selector(self, selector):
        text = self._texts.get(selector)
        return _TextElement(text) if text is not None else None


class _VenueQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, list(values)))
        return self

    def contains(self, field, values):
        self.filters.append(("contains", field, list(values)))
        return self

    def execute(self):
        rows = list(self.client.venues if self.table == "venues" else [])
        for operation, field, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif operation == "in":
                rows = [row for row in rows if row.get(field) in value]
            elif operation == "contains":
                rows = [
                    row
                    for row in rows
                    if all(item in (row.get(field) or []) for item in value)
                ]
        return SimpleNamespace(data=rows)


class _VenueClient:
    def __init__(self):
        self.venues = [
            {
                "id": "venue-tcc",
                "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター",
                "canonical_name_zh": "台北駐日經濟文化代表處 台灣文化中心",
                "canonical_name_en": "Taiwan Cultural Center, TECRO",
                "address": "東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
                "prefecture": "東京都",
                "prefectures": ["東京都"],
                "homepage": "https://jp.taiwan.culture.tw/",
                "aliases": ["台湾文化センター"],
                "is_authoritative": True,
                "is_multi_venue": False,
                "business_hours": None,
            }
        ]

    def table(self, name):
        return _VenueQuery(self, name)


def _writer_event(case_name, description):
    page = _DetailPage(f"会場回帰テスト {case_name}", description)
    url = f"https://jp.taiwan.culture.tw/News_Content.aspx?n=365&s={case_name}"
    event = TaiwanCulturalCenterScraper()._scrape_detail(page, url)
    assert event is not None
    return event


def _resolve_authoritative_venue(event):
    row = database._event_to_row(event)
    database._populate_entity_fks(_VenueClient(), [row])
    return row


def test_writer_default_center_receives_registry_owned_homepage():
    event = _writer_event(
        "default",
        "日時：2026年8月20日\n台湾映画文化を紹介する館内上映会です。",
    )

    assert event.location_name == "台北駐日経済文化代表処 台湾文化センター"
    assert event.location_address == "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
    assert event.location_url is None

    row = _resolve_authoritative_venue(event)
    assert row["venue_id"] == "venue-tcc"
    assert row["location_url"] == "https://jp.taiwan.culture.tw/"


def test_writer_explicit_external_venue_is_not_replaced_by_tcc_registry():
    event = _writer_event(
        "external",
        "日時：2026年8月21日\n会場：小野記念講堂\n台湾文化講座を開催します。",
    )

    assert event.location_name == "小野記念講堂"
    assert event.location_address is None
    assert event.location_prefectures == ["東京都"]

    row = _resolve_authoritative_venue(event)
    assert "venue_id" not in row
    assert row["location_name"] == "小野記念講堂"
    assert "location_url" not in row


def test_writer_multi_city_location_is_not_replaced_by_tcc_registry():
    event = _writer_event(
        "multi-city",
        "日時：2026年8月22日\n会場：東京都／会場：大阪府 で順次開催。",
    )

    assert event.location_name == "東京・大阪"
    assert event.location_address is None
    assert event.location_prefectures == ["東京都", "大阪府"]

    row = _resolve_authoritative_venue(event)
    assert "venue_id" not in row
    assert row["location_name"] == "東京・大阪"
    assert row["location_prefectures"] == ["東京都", "大阪府"]
    assert "location_url" not in row


def test_writer_online_location_is_not_replaced_by_tcc_registry():
    event = _writer_event(
        "online",
        "日時：2026年8月23日\n会場：オンライン\n配信イベントを開催します。",
    )

    assert event.location_name == "オンライン"
    assert event.location_address is None
    assert event.location_prefectures is None

    row = _resolve_authoritative_venue(event)
    assert "venue_id" not in row
    assert row["location_name"] == "オンライン"
    assert row["location_prefectures"] is None
    assert "location_url" not in row


def test_writer_mixed_location_batch_only_resolves_default_center():
    events = [
        _writer_event(
            "batch-default",
            "日時：2026年8月24日\n台湾映画文化を紹介する館内上映会です。",
        ),
        _writer_event(
            "batch-external",
            "日時：2026年8月25日\n会場：小野記念講堂\n台湾文化講座です。",
        ),
        _writer_event(
            "batch-multi-city",
            "日時：2026年8月26日\n会場：東京都／会場：大阪府 で順次開催。",
        ),
        _writer_event(
            "batch-online",
            "日時：2026年8月27日\n会場：オンライン\n配信イベントです。",
        ),
    ]
    rows = [database._event_to_row(event) for event in events]

    database._populate_entity_fks(_VenueClient(), rows)

    assert rows[0]["venue_id"] == "venue-tcc"
    assert rows[0]["location_url"] == "https://jp.taiwan.culture.tw/"
    assert [row["location_name"] for row in rows[1:]] == [
        "小野記念講堂",
        "東京・大阪",
        "オンライン",
    ]
    assert all("venue_id" not in row for row in rows[1:])
    assert all("location_url" not in row for row in rows[1:])
