from copy import deepcopy
from types import SimpleNamespace

import pytest

import database
from database import _populate_entity_fks, upsert_events
from sources.base import Event


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = "select"
        self.columns = ""
        self.payload = None
        self.filters = []

    def select(self, columns):
        self.columns = columns
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

    def like(self, field, value):
        self.filters.append(("like", field, value))
        return self

    def limit(self, value):
        self.filters.append(("limit", value))
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = deepcopy(payload)
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = deepcopy(payload)
        return self

    def execute(self):
        self.client.queries.append(self)
        if self.operation == "update":
            self.client.updates.append((self.table, deepcopy(self.payload), list(self.filters)))
            if self.table == "field_corrections":
                for row in self.client.field_corrections:
                    if all(kind != "eq" or row.get(field) == value for kind, field, value in self.filters):
                        row.update(deepcopy(self.payload))
            return SimpleNamespace(data=[])
        if self.operation == "upsert":
            assert self.table == "events"
            self.client.upserted_events = deepcopy(self.payload)
            return SimpleNamespace(data=[])

        if self.table == "venues":
            alias_filter = next(
                (
                    value[0]
                    for kind, field, value in self.filters
                    if kind == "contains" and field == "aliases"
                ),
                None,
            )
            if alias_filter in self.client.fail_venue_alias_for:
                raise RuntimeError("fixture alias lookup failure")

        rows = deepcopy(getattr(self.client, self.table))
        for item in self.filters:
            kind, field, value = item
            if kind == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif kind == "in":
                rows = [row for row in rows if row.get(field) in set(value)]
            elif kind == "contains":
                rows = [row for row in rows if all(v in (row.get(field) or []) for v in value)]
            elif kind == "like":
                needle = value.replace("%", "")
                rows = [row for row in rows if needle in str(row.get(field) or "")]
        return SimpleNamespace(data=rows)


class _Client:
    def __init__(
        self,
        *,
        venues=None,
        events=None,
        field_corrections=None,
        fail_venue_alias_for=(),
    ):
        self.venues = venues or []
        self.events = events or []
        self.field_corrections = field_corrections or []
        self.fail_venue_alias_for = set(fail_venue_alias_for)
        self.organizers = []
        self.queries = []
        self.updates = []
        self.upserted_events = []

    def table(self, name):
        return _Query(self, name)


def _venue(venue_id="venue-1", canonical="正規館", aliases=(), **overrides):
    row = {
        "id": venue_id,
        "canonical_name_ja": canonical,
        "canonical_name_zh": "正規館中文",
        "canonical_name_en": "Canonical Hall",
        "address": "東京都千代田区1-1-1 正規ビル2F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://venue.example/",
        "aliases": list(aliases),
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "10:00-18:00",
    }
    row.update(overrides)
    return row


def _row(location_name="正規館", **overrides):
    row = {
        "source_name": "fixture",
        "source_id": "fixture-1",
        "source_url": "https://source.example/event",
        "official_url": "https://organizer.example/event",
        "submission_url": "https://tickets.example/apply",
        "organizer_url": "https://organizer.example/",
        "location_name": location_name,
        "location_address": "旧住所",
        "location_url": "https://tickets.example/schedule",
        "business_hours": None,
        "event_form": ["screening"],
    }
    row.update(overrides)
    return row


def _event(**overrides):
    values = {
        "source_name": "fixture",
        "source_id": "fixture-1",
        "source_url": "https://source.example/event",
        "original_language": "ja",
        "location_name": "正規館",
        "location_address": "スクレイパー住所",
        "location_url": "https://tickets.example/schedule",
        "event_form": ["screening"],
    }
    values.update(overrides)
    return Event(**values)


def _venue_queries(client):
    return [query for query in client.queries if query.table == "venues"]


def test_canonical_unique_hit_populates_full_authoritative_fields_and_owned_url():
    client = _Client(venues=[_venue()])
    row = _row(
        location_address_zh="既有中文地址",
        location_address_en="Existing English address",
    )

    _populate_entity_fks(client, [row])

    assert row["venue_id"] == "venue-1"
    assert row["location_name"] == "正規館"
    assert row["location_name_zh"] == "正規館中文"
    assert row["location_name_en"] == "Canonical Hall"
    assert row["location_address"] == "東京都千代田区1-1-1 正規ビル2F"
    assert row["location_address_zh"] == "既有中文地址"
    assert row["location_address_en"] == "Existing English address"
    assert row["location_prefectures"] == ["東京都"]
    assert row["location_url"] == "https://venue.example/"
    assert row["business_hours"] == "10:00-18:00"
    assert row["source_url"] == "https://source.example/event"
    assert row["official_url"] == "https://organizer.example/event"
    assert row["submission_url"] == "https://tickets.example/apply"
    assert row["organizer_url"] == "https://organizer.example/"
    assert all(("eq", "is_authoritative", True) in query.filters for query in _venue_queries(client))


def test_alias_unique_hit_uses_complete_candidate_set_without_limit():
    client = _Client(venues=[_venue(aliases=["別名館"])])
    row = _row("別名館")

    _populate_entity_fks(client, [row])

    assert row["venue_id"] == "venue-1"
    alias_queries = [
        query for query in _venue_queries(client)
        if any(item[:2] == ("contains", "aliases") for item in query.filters)
    ]
    assert alias_queries
    assert all(not any(item[0] == "limit" for item in query.filters) for query in alias_queries)


def test_canonical_hit_fails_closed_when_alias_candidates_cannot_be_loaded(caplog):
    client = _Client(
        venues=[_venue(canonical="共通館")],
        fail_venue_alias_for=["共通館"],
    )
    row = _row("共通館", location_address=None, location_url=None)

    with caplog.at_level("WARNING", logger="database"):
        _populate_entity_fks(client, [row])

    assert "venue_id" not in row
    assert row["location_address"] is None
    assert row["location_url"] is None
    assert "cannot prove a unique authoritative match" in caplog.text


@pytest.mark.parametrize(
    "venues",
    [
        [_venue("venue-1", "A館", ["共通館"]), _venue("venue-2", "B館", ["共通館"])],
        [_venue("venue-1", "共通館"), _venue("venue-2", "B館", ["共通館"])],
    ],
)
def test_ambiguous_same_or_cross_tier_match_fails_closed(caplog, venues):
    client = _Client(venues=venues)
    row = _row("共通館", location_address=None, location_url=None)

    with caplog.at_level("WARNING", logger="database"):
        _populate_entity_fks(client, [row])

    assert "venue_id" not in row
    assert row["location_address"] is None
    assert row["location_url"] is None
    assert "ambiguous" in caplog.text


def test_non_authoritative_match_is_ignored():
    client = _Client(venues=[_venue(is_authoritative=False)])
    row = _row(location_address=None, location_url=None)

    _populate_entity_fks(client, [row])

    assert "venue_id" not in row
    assert row["location_address"] is None


def test_multi_venue_keeps_only_names_and_prefecture_without_physical_fields_or_url():
    client = _Client(venues=[_venue(
        canonical="東京国際映画祭",
        canonical_name_zh="東京國際影展",
        canonical_name_en="Tokyo International Film Festival",
        address=None,
        is_multi_venue=True,
    )])
    row = _row(
        "東京国際映画祭",
        venue_id="stale-id",
        location_address="stale",
        location_address_zh="stale-zh",
        location_address_en="stale-en",
    )

    _populate_entity_fks(client, [row])

    assert row.get("venue_id") is None
    assert row["location_address"] is None
    assert row["location_address_zh"] is None
    assert row["location_address_en"] is None
    assert row["location_name"] == "東京国際映画祭"
    assert row["location_name_zh"] == "東京國際影展"
    assert row["location_name_en"] == "Tokyo International Film Festival"
    assert row["location_prefectures"] == ["東京都"]
    assert row["location_url"] is None
    assert row["business_hours"] is None


def test_pure_publication_bypasses_all_venue_queries():
    client = _Client(venues=[_venue()])
    row = _row(event_form=["publication"])

    _populate_entity_fks(client, [row])

    assert _venue_queries(client) == []
    assert "venue_id" not in row


def test_business_hours_is_fill_only():
    client = _Client(venues=[_venue()])
    row = _row(business_hours="特別営業時間")

    _populate_entity_fks(client, [row])

    assert row["business_hours"] == "特別営業時間"


def test_field_correction_wins_and_records_registry_override_attempt():
    client = _Client(
        venues=[_venue()],
        events=[{"id": "event-1", "source_name": "fixture", "source_id": "fixture-1"}],
        field_corrections=[{
            "id": "fc-1",
            "event_id": "event-1",
            "field_name": "location_url",
            "corrected_value": "https://human.example/",
            "override_attempt_count": 2,
            "first_override_attempted_at": None,
        }],
    )
    row = _row(location_url="https://tickets.example/schedule")

    _populate_entity_fks(client, [row])

    assert row["location_url"] == "https://human.example/"
    fc_update = next(update for update in client.updates if update[0] == "field_corrections")
    assert fc_update[1]["override_attempt_count"] == 3
    assert fc_update[1]["override_attempted_value"] == "https://venue.example/"
    assert "first_override_attempted_at" in fc_update[1]
    assert "last_override_attempted_at" in fc_update[1]


def test_force_rescrape_strips_fc_protected_venue_field_from_final_upsert(monkeypatch):
    client = _Client(
        venues=[_venue()],
        events=[{
            "id": "event-1",
            "source_name": "fixture",
            "source_id": "fixture-1",
            "is_active": True,
            "annotation_status": "annotated",
            "force_rescrape": True,
            "category": [],
            "start_date": None,
            "end_date": None,
            "raw_description": None,
            "business_hours": None,
        }],
        field_corrections=[{
            "id": "fc-address",
            "event_id": "event-1",
            "field_name": "location_address",
            "corrected_value": "人工作業住所",
            "override_attempt_count": 0,
            "first_override_attempted_at": None,
        }],
    )
    monkeypatch.setattr(database, "_get_client", lambda: client)
    monkeypatch.setattr(database, "load_exclusions", lambda *_args: {})

    assert upsert_events([_event()]) == []

    assert len(client.upserted_events) == 1
    payload = client.upserted_events[0]
    assert "location_address" not in payload
    assert payload["venue_id"] == "venue-1"
    assert payload["location_url"] == "https://venue.example/"
    correction = next(row for row in client.field_corrections if row["id"] == "fc-address")
    assert correction["override_attempt_count"] == 1
    assert correction["override_attempted_value"] == "東京都千代田区1-1-1 正規ビル2F"