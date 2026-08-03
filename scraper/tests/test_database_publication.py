from types import SimpleNamespace

import pytest

import database
from database import (
    PUBLICATION_NULL_FIELDS,
    _auto_lock_location,
    _event_to_row,
    _populate_entity_fks,
    _write_pure_publication_sentinels,
    upsert_events,
)
from sources.base import Event


def _event(**overrides):
    values = {
        "source_name": "fixture",
        "source_id": "fixture-1",
        "source_url": "https://example.test/source",
        "original_language": "ja",
        "event_form": ["publication"],
        "location_name": "紀伊國屋書店",
        "location_address": "東京都千代田区1-1",
        "location_prefectures": ["東京都"],
        "location_url": "https://venue.example.test/",
        "business_hours": "10:00-18:00",
    }
    values.update(overrides)
    return Event(**values)


def test_event_to_row_preserves_publication_form_and_enforces_null_policy():
    row = _event_to_row(_event())

    assert row["event_form"] == ["publication"]
    assert row["location_address"] is None
    assert row["location_address_zh"] is None
    assert row["location_address_en"] is None
    assert row["business_hours"] is None
    assert row["business_hours_zh"] is None
    assert row["business_hours_en"] is None
    assert row["location_prefectures"] is None
    assert row["location_url"] is None


def test_event_to_row_clears_scraper_venue_names_for_exact_pure():
    row = _event_to_row(_event())

    assert row["location_name"] is None
    assert row["location_name_zh"] is None
    assert row["location_name_en"] is None


def test_event_to_row_keeps_venue_name_for_physical_form():
    row = _event_to_row(_event(event_form=["lecture"]))

    assert row["location_name"] == "紀伊國屋書店"
    assert "location_name_zh" not in row
    assert "location_name_en" not in row


def test_event_to_row_keeps_venue_and_policy_fields_for_mixed_form():
    row = _event_to_row(_event(event_form=["publication", "lecture"]))

    assert row["event_form"] == ["publication", "lecture"]
    assert row["location_name"] == "紀伊國屋書店"
    assert row["location_address"] == "東京都千代田区1-1"
    assert row["location_prefectures"] == ["東京都"]
    assert row["business_hours"] == "10:00-18:00"
    assert row["location_url"] == "https://venue.example.test/"


def test_apply_pure_publication_policy_ignores_mixed_form_row():
    row = {
        "event_form": ["publication", "lecture"],
        "location_name": "紀伊國屋書店",
        "business_hours": "10:00-18:00",
        "venue_id": "venue-id",
    }

    assert database._apply_pure_publication_policy(row) is False
    assert row["location_name"] == "紀伊國屋書店"
    assert row["business_hours"] == "10:00-18:00"
    assert row["venue_id"] == "venue-id"


def test_event_to_row_keeps_physical_location_fields():
    row = _event_to_row(_event(event_form=["lecture"]))

    assert row["event_form"] == ["lecture"]
    assert row["location_address"] == "東京都千代田区1-1"
    assert row["location_prefectures"] == ["東京都"]
    assert row["location_url"] == "https://venue.example.test/"
    assert row["business_hours"] == "10:00-18:00"


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = None
        self.columns = None
        self.payload = None
        self.kwargs = {}
        self.filters = []

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def upsert(self, payload, **kwargs):
        self.operation = "upsert"
        self.payload = payload
        self.kwargs = kwargs
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, value):
        self.filters.append(("in", field, value))
        return self

    def contains(self, field, value):
        self.filters.append(("contains", field, value))
        return self

    def limit(self, value):
        self.filters.append(("limit", value))
        return self

    def like(self, field, value):
        self.filters.append(("like", field, value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, field, value):
        self.filters.append(("not_is", field, value))
        return self

    def execute(self):
        return SimpleNamespace(data=self.client.execute(self))


class FakeClient:
    def __init__(self, existing=None, force_corrections=None, fail_event_postcondition=False):
        self.existing = existing or []
        self.force_corrections = force_corrections or []
        self.fail_event_postcondition = fail_event_postcondition
        self.calls = []
        self.upserted_events = []
        self.corrections = []

    def table(self, name):
        return FakeQuery(self, name)

    def execute(self, query):
        self.calls.append(query)
        if query.table == "events" and query.operation == "select":
            if query.columns.startswith("source_name,source_id,is_active"):
                return self.existing
            if query.columns == "id,source_name,source_id":
                return [
                    {"id": row["id"], "source_name": row["source_name"], "source_id": row["source_id"]}
                    for row in self.existing
                ]
            if query.columns.startswith("id,location_address"):
                rows = []
                for row in self.upserted_events:
                    result = {"id": row["id"]}
                    result.update({field: row.get(field) for field in PUBLICATION_NULL_FIELDS})
                    if self.fail_event_postcondition:
                        result["business_hours"] = "stale"
                    rows.append(result)
                return rows
        if query.table == "events" and query.operation == "upsert":
            self.upserted_events = [
                {**row, "id": next(
                    (
                        existing["id"] for existing in self.existing
                        if existing["source_name"] == row["source_name"]
                        and existing["source_id"] == row["source_id"]
                    ),
                    f"uuid-{index}",
                )}
                for index, row in enumerate(query.payload)
            ]
            return self.upserted_events
        if query.table == "field_corrections" and query.operation == "upsert":
            for incoming in query.payload:
                self.corrections = [
                    row for row in self.corrections
                    if (row["event_id"], row["field_name"])
                    != (incoming["event_id"], incoming["field_name"])
                ]
                self.corrections.append(incoming)
            return query.payload
        if query.table == "field_corrections" and query.operation == "select":
            if any(item[0:2] == ("in", "field_name") for item in query.filters):
                return self.corrections
            return self.force_corrections
        if query.table == "organizers" and query.operation == "select":
            return [{
                "id": "publisher-id",
                "canonical_name_ja": "架空出版社",
                "aliases": [],
                "homepage": "https://publisher.example.test/",
            }]
        if query.table == "venues":
            raise AssertionError("pure publication must not query venues")
        return []


def _patch_writer(monkeypatch, client):
    monkeypatch.setattr(database, "_get_client", lambda: client)
    monkeypatch.setattr(database, "load_exclusions", lambda *_: {})
    monkeypatch.setattr(database, "_populate_entity_fks", lambda *_: None)


def test_entity_lookup_sets_registry_homepage_and_bypasses_venue():
    client = FakeClient()
    row = _event_to_row(_event(organizer="架空出版社", location_name="旧会場"))

    _populate_entity_fks(client, [row])

    assert row["organizer_id"] == "publisher-id"
    assert row["organizer_url"] == "https://publisher.example.test/"
    assert "venue_id" not in row


def test_entity_lookup_skips_unvalidated_registry_homepage_for_pure_publication():
    class InvalidHomepageClient(FakeClient):
        def execute(self, query):
            if query.table == "organizers" and query.operation == "select":
                return [{
                    "id": "publisher-id",
                    "canonical_name_ja": "架空出版社",
                    "aliases": [],
                    "homepage": "https://www.amazon.co.jp/example",
                }]
            return super().execute(query)

    client = InvalidHomepageClient()
    row = _event_to_row(_event(organizer="架空出版社", location_name="旧会場"))

    _populate_entity_fks(client, [row])

    assert row["organizer_id"] == "publisher-id"
    assert row.get("organizer_url") is None
    assert "venue_id" not in row


def test_auto_lock_skips_pure_publication():
    client = FakeClient()
    row = _event_to_row(_event(location_name="旧会場"))

    _auto_lock_location(client, {"uuid-1": row})

    assert not client.calls


def test_new_pure_upsert_overwrites_all_empty_sentinels(monkeypatch):
    client = FakeClient()
    _patch_writer(monkeypatch, client)

    new_ids = upsert_events([_event()])

    assert new_ids == ["uuid-0"]
    assert len(client.corrections) == len(PUBLICATION_NULL_FIELDS)
    assert {row["corrected_value"] for row in client.corrections} == {""}
    sentinel_call = next(
        call for call in client.calls
        if call.table == "field_corrections" and call.operation == "upsert"
    )
    assert sentinel_call.kwargs["ignore_duplicates"] is False


def test_force_pure_upsert_reapplies_policy_and_sentinels(monkeypatch):
    client = FakeClient(existing=[{
        "id": "existing-id",
        "source_name": "fixture",
        "source_id": "fixture-1",
        "is_active": True,
        "annotation_status": "annotated",
        "force_rescrape": True,
        "category": [],
        "start_date": None,
        "end_date": None,
        "raw_description": None,
        "business_hours": "stale",
    }])
    _patch_writer(monkeypatch, client)

    assert upsert_events([_event()]) == []
    assert client.upserted_events[0]["business_hours"] is None
    assert len(client.corrections) == len(PUBLICATION_NULL_FIELDS)


def test_existing_nonforced_publication_is_skipped(monkeypatch):
    client = FakeClient(existing=[{
        "id": "existing-id",
        "source_name": "fixture",
        "source_id": "fixture-1",
        "is_active": True,
        "annotation_status": "annotated",
        "force_rescrape": False,
        "category": [],
        "start_date": None,
        "end_date": None,
        "raw_description": None,
        "business_hours": None,
    }])
    _patch_writer(monkeypatch, client)

    assert upsert_events([_event()]) == []
    assert not client.upserted_events


def test_force_pure_rejects_nonempty_policy_correction(monkeypatch):
    client = FakeClient(
        existing=[{
            "id": "existing-id",
            "source_name": "fixture",
            "source_id": "fixture-1",
            "is_active": True,
            "annotation_status": "annotated",
            "force_rescrape": True,
            "category": [],
            "start_date": None,
            "end_date": None,
            "raw_description": None,
            "business_hours": "stale",
        }],
        force_corrections=[{
            "event_id": "existing-id",
            "field_name": "business_hours",
            "corrected_value": "10:00-18:00",
        }],
    )
    _patch_writer(monkeypatch, client)

    with pytest.raises(RuntimeError, match="policy conflicts"):
        upsert_events([_event()])
    assert not client.upserted_events


def test_pure_postcondition_failure_raises():
    client = FakeClient(fail_event_postcondition=True)
    row = _event_to_row(_event())
    upserted = [{**row, "id": "uuid-1"}]
    client.upserted_events = upserted

    with pytest.raises(RuntimeError, match="NULL postcondition failed"):
        _write_pure_publication_sentinels(client, [row], upserted)


def test_pure_sentinel_write_overwrites_legacy_nonempty_fc_values():
    client = FakeClient()
    row = _event_to_row(_event())
    upserted = [{**row, "id": "uuid-1"}]
    client.upserted_events = upserted
    client.corrections = [
        {"event_id": "uuid-1", "field_name": field, "corrected_value": "legacy"}
        for field in PUBLICATION_NULL_FIELDS
    ]

    _write_pure_publication_sentinels(client, [row], upserted)

    assert {
        (record["event_id"], record["field_name"], record["corrected_value"])
        for record in client.corrections
    } == {
        ("uuid-1", field, "")
        for field in PUBLICATION_NULL_FIELDS
    }