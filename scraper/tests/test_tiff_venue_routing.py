import json
from pathlib import Path
from types import SimpleNamespace

import database
from sources import tiff as tiff_module
from sources.tiff import TiffScraper, _screen_to_nearest_cinema


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


FILMS = _fixture("tiff_2025_films.json")
VENUES = _fixture("tiff_2025_venues.json")

REGISTRY = {
    "ヒューリックホール東京": {
        "id": "venue-hulic",
        "canonical_name_ja": "ヒューリックホール東京",
        "canonical_name_zh": "Hulic Hall 東京",
        "canonical_name_en": "Hulic Hall Tokyo",
        "address": "東京都千代田区有楽町2-5-1 有楽町マリオン11F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://hulic-theater.com/access/",
        "aliases": ["HULIC HALL TOKYO"],
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    "TOHOシネマズ シャンテ": {
        "id": "venue-chanter",
        "canonical_name_ja": "TOHOシネマズ シャンテ",
        "canonical_name_zh": "TOHO Cinemas Chanter",
        "canonical_name_en": "TOHO Cinemas Chanter",
        "address": "東京都千代田区有楽町1-2-2",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://www.tohotheater.jp/theater/081/access.html",
        "aliases": ["TOHOシネマズシャンテ"],
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    "TOHOシネマズ 日比谷 スクリーン12・13": {
        "id": "venue-hibiya-12-13",
        "canonical_name_ja": "TOHOシネマズ 日比谷 スクリーン12・13",
        "canonical_name_zh": "TOHO Cinemas 日比谷 12・13廳",
        "canonical_name_en": "TOHO Cinemas Hibiya Screens 12 and 13",
        "address": "東京都千代田区有楽町1-1-3 東京宝塚ビル地下1F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://www.tohotheater.jp/theater/081/access.html",
        "aliases": ["TOHOシネマズ日比谷 スクリーン12・13"],
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    "シネスイッチ銀座": {
        "id": "venue-cineswitch",
        "canonical_name_ja": "シネスイッチ銀座",
        "canonical_name_zh": "シネスイッチ銀座",
        "canonical_name_en": "Cineswitch Ginza",
        "address": "東京都中央区銀座4-4-5 簱ビル",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://cineswitch.com",
        "aliases": ["シネスイッチ銀座", "Cineswitch Ginza"],
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": None,
    },
}


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _install_api(monkeypatch, films=FILMS, venues=VENUES):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return _Response(venues if url.endswith("/api/venues") else films)

    monkeypatch.setattr(tiff_module.requests, "get", fake_get)
    return calls


def _install_registry(monkeypatch, registry=REGISTRY):
    monkeypatch.setattr(tiff_module, "lookup_venue", registry.get)
    monkeypatch.setattr(tiff_module, "lookup_movie_titles", lambda _: (None, None, None))


def test_screen_maps_to_nearest_cinema_through_nested_tree():
    venues = [
        {
            "id": 1,
            "type": "area",
            "name_ja": "日比谷",
            "children": [
                {
                    "id": 2,
                    "type": "cinema",
                    "name_ja": "正規館",
                    "children": [
                        {
                            "id": 3,
                            "type": "floor",
                            "name_ja": "地下",
                            "children": [
                                {
                                    "id": 4,
                                    "type": "screen",
                                    "name_ja": "スクリーン4",
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    screen_map = _screen_to_nearest_cinema(venues)

    assert screen_map["4"]["id"] == 2


def test_2025_fixture_routes_films_in_first_act_order(monkeypatch):
    calls = _install_api(monkeypatch)
    _install_registry(monkeypatch)

    events = TiffScraper(years=[2025]).scrape()

    assert [call[0] for call in calls] == [
        "https://api-2025.tiff-jp.net/api/films",
        "https://api-2025.tiff-jp.net/api/venues",
    ]
    by_title = {event.name_ja: event for event in events}
    assert by_title["木々の隙間"].location_name == "TOHOシネマズ シャンテ"
    assert by_title["エイプリル"].location_name == (
        "ヒューリックホール東京・TOHOシネマズ シャンテ・シネスイッチ銀座"
    )
    assert by_title["ダブル・ハピネス"].location_name == (
        "TOHOシネマズ 日比谷 スクリーン12・13・シネスイッチ銀座"
    )
    assert by_title["人生は海のように"].location_name == (
        "TOHOシネマズ シャンテ・TOHOシネマズ 日比谷 スクリーン12・13・"
        "シネスイッチ銀座"
    )
    assert by_title["木々の隙間"].venue_ids == ["venue-chanter"]
    assert by_title["エイプリル"].venue_ids == [
        "venue-hulic",
        "venue-chanter",
        "venue-cineswitch",
    ]
    assert by_title["エイプリル"].location_address is None
    assert by_title["エイプリル"].location_url is None
    assert by_title["エイプリル"].location_prefectures == ["東京都"]
    assert by_title["エイプリル"].business_hours == (
        "2025-10-31 15:20-17:46 / 2025-11-02 16:40-18:36 / "
        "2025-11-04 10:15-12:11"
    )
    assert by_title["エイプリル"].end_date.isoformat() == "2025-11-04T00:00:00+00:00"
    assert all(event.event_form == ["screening"] for event in events)


def test_single_venue_reaches_full_canonical_database_row(monkeypatch):
    _install_api(monkeypatch, films=[FILMS[1]])
    _install_registry(monkeypatch)
    event = TiffScraper(years=[2025]).scrape()[0]
    row = database._event_to_row(event)
    client = SimpleNamespace()

    class Query:
        def __init__(self, table):
            self.table = table
            self.mode = None
            self.values = []

        def select(self, *_):
            return self

        def in_(self, field, values):
            self.values = values
            if self.table == "venues" and field == "canonical_name_ja":
                self.mode = "canonical"
            elif self.table == "venues" and field == "id":
                self.mode = "venue_ids"
            elif self.table == "events":
                self.mode = "events"
            elif self.table == "field_corrections":
                self.mode = "corrections"
            return self

        def contains(self, field, values):
            self.mode = "alias"
            return self

        def eq(self, *_):
            return self

        def execute(self):
            if self.mode == "venue_ids":
                return SimpleNamespace(
                    data=[venue for venue in REGISTRY.values() if venue["id"] in self.values]
                )
            if self.mode == "canonical":
                return SimpleNamespace(data=[REGISTRY["TOHOシネマズ シャンテ"]])
            return SimpleNamespace(data=[])

    client.table = lambda name: Query(name)
    database._populate_entity_fks(client, [row])

    venue = REGISTRY["TOHOシネマズ シャンテ"]
    assert row["venue_id"] == venue["id"]
    assert row["location_name"] == venue["canonical_name_ja"]
    assert row["location_name_zh"] == venue["canonical_name_zh"]
    assert row["location_name_en"] == venue["canonical_name_en"]
    assert row["location_address"] == venue["address"]
    assert row["location_prefectures"] == venue["prefectures"]
    assert row["location_url"] == venue["homepage"]


def test_multi_venue_database_row_clears_physical_fields(monkeypatch):
    _install_api(monkeypatch, films=[FILMS[0]])
    _install_registry(monkeypatch)
    event = TiffScraper(years=[2025]).scrape()[0]
    row = database._event_to_row(event)

    class Query:
        def __init__(self, table):
            self.table = table
            self.mode = None
            self.values = []

        def select(self, *_):
            return self

        def in_(self, field, values):
            self.values = values
            if self.table == "venues" and field == "id":
                self.mode = "venue_ids"
            elif self.table == "events":
                self.mode = "events"
            elif self.table == "field_corrections":
                self.mode = "corrections"
            return self

        def eq(self, *_):
            return self

        def execute(self):
            if self.mode == "venue_ids":
                return SimpleNamespace(
                    data=[venue for venue in REGISTRY.values() if venue["id"] in self.values]
                )
            return SimpleNamespace(data=[])

    client = SimpleNamespace(table=lambda name: Query(name))
    database._populate_entity_fks(client, [row])

    assert "_venue_ids" not in row
    assert row["venue_id"] is None
    assert row["location_address"] is None
    assert row["location_address_zh"] is None
    assert row["location_address_en"] is None
    assert row["location_url"] is None
    assert row["location_prefectures"] == ["東京都"]


def test_unknown_screen_skips_whole_film(monkeypatch, caplog):
    films = [dict(FILMS[0], acts=[dict(FILMS[0]["acts"][0], venue_id=999)])]
    _install_api(monkeypatch, films=films)
    _install_registry(monkeypatch)

    assert TiffScraper(years=[2025]).scrape() == []
    assert "unknown TIFF screen venue_id 999" in caplog.text


def test_unresolved_cinema_skips_whole_film(monkeypatch, caplog):
    _install_api(monkeypatch, films=[FILMS[0]])
    registry = dict(REGISTRY)
    registry.pop("ヒューリックホール東京")
    _install_registry(monkeypatch, registry)

    assert TiffScraper(years=[2025]).scrape() == []
    assert "unresolved authoritative TIFF venue" in caplog.text


def test_venues_api_failure_skips_year_without_partial_events(monkeypatch, caplog):
    def fake_get(url, timeout):
        if url.endswith("/api/venues"):
            raise RuntimeError("venues unavailable")
        return _Response(FILMS)

    monkeypatch.setattr(tiff_module.requests, "get", fake_get)
    _install_registry(monkeypatch)

    assert TiffScraper(years=[2025]).scrape() == []
    assert "venues unavailable" in caplog.text
