"""Publication-policy guards for the location/address enrichment scripts.

Regression cover for the pipeline defect where annotator correctly cleared
PUBLICATION_NULL_FIELDS but a later enrichment step wrote publisher names back
into location_address. Each script must (1) drop pure publications at candidate
stage and (2) re-check event_form straight before every write (TOCTOU).

Run:
    python -m pytest scraper/tests/test_enrichment_publication_guards.py -q
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import sys

import pytest

import backfill_location_prefectures
import backfill_locations
import enrich_addresses
import enrich_location
import geocode_events


# ---------------------------------------------------------------------------
# Supabase test double
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.op = "select"
        self.columns = ""
        self.payload = None
        self.filters = []
        self.negate = False
        self.head = False
        self.count_mode = None
        self.single = False
        self.limit_n = None
        self.start = None
        self.end = None

    def select(self, columns="*", count=None, head=False):
        self.op = "select"
        self.columns = columns
        self.count_mode = count
        self.head = head
        self.client.selects.append((self.table, columns))
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = deepcopy(payload)
        return self

    def upsert(self, payload, **_kwargs):
        self.op = "upsert"
        self.payload = deepcopy(payload)
        return self

    @property
    def not_(self):
        self.negate = True
        return self

    def _filter(self, kind, column, value):
        self.filters.append((kind, column, value, self.negate))
        self.negate = False
        return self

    def eq(self, column, value):
        return self._filter("eq", column, value)

    def neq(self, column, value):
        return self._filter("neq", column, value)

    def is_(self, column, value):
        return self._filter("is", column, value)

    def in_(self, column, values):
        return self._filter("in", column, list(values))

    def limit(self, value):
        self.limit_n = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def maybe_single(self):
        self.single = True
        return self

    def _matches(self, row):
        for kind, column, value, negate in self.filters:
            got = row.get(column)
            if kind == "eq":
                ok = got == value
            elif kind == "neq":
                ok = got != value
            elif kind == "is":
                ok = got is None if value in (None, "null") else got == value
            elif kind == "in":
                ok = got in value
            else:
                ok = True
            if negate:
                ok = not ok
            if not ok:
                return False
        return True

    def execute(self):
        rows = self.client.tables.setdefault(self.table, {})

        if self.op == "update":
            hits = [row for row in rows.values() if self._matches(row)]
            for row in hits:
                row.update(self.payload)
                self.client.writes.append((self.table, row["id"], deepcopy(self.payload)))
            return _Result(data=[deepcopy(row) for row in hits])

        if self.op == "upsert":
            self.client.writes.append(
                (self.table, self.payload.get("event_id"), deepcopy(self.payload))
            )
            return _Result(data=[deepcopy(self.payload)])

        matched = sorted(
            (deepcopy(row) for row in rows.values() if self._matches(row)),
            key=lambda row: str(row.get("id", "")),
        )
        count = len(matched) if self.count_mode == "exact" else None
        if self.start is not None:
            matched = matched[self.start:self.end + 1]
        if self.limit_n is not None:
            matched = matched[:self.limit_n]
        if self.head:
            matched = []
        self.client.notify_select(self.table, self.columns)
        if self.single:
            return _Result(data=matched[0] if matched else None)
        return _Result(data=matched, count=count)


class _Client:
    def __init__(self, events=()):
        self.tables = {"events": {row["id"]: deepcopy(row) for row in events}}
        self.selects = []
        self.writes = []
        self.on_select = None

    def table(self, name):
        return _Query(self, name)

    def notify_select(self, table, columns):
        if self.on_select:
            self.on_select(self, table, columns)

    def make_publication(self, event_id):
        """Simulate the row turning into a pure publication mid-run."""
        self.tables["events"][event_id]["event_form"] = ["publication"]

    @property
    def event_writes(self):
        return [write for write in self.writes if write[0] == "events"]


def _event(event_id, **overrides):
    row = {
        "id": event_id,
        "source_id": f"src-{event_id}",
        "source_name": "peatix",
        "source_url": f"https://example.test/{event_id}",
        "name_ja": "Event",
        "parent_event_id": None,
        "location_name": "渋谷ホール",
        "location_address": None,
        "location_prefectures": None,
        "raw_description": "会場は東京都渋谷区神南1-1です。" * 8,
        "event_form": ["lecture"],
        "venue_id": None,
        "latitude": None,
        "is_active": True,
    }
    row.update(overrides)
    return row


def _boom(*_args, **_kwargs):
    raise AssertionError("pure publication must never reach the enrichment step")


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")


# ---------------------------------------------------------------------------
# enrich_location.py — two write points
# ---------------------------------------------------------------------------

def _run_enrich_location(monkeypatch, client, extract):
    monkeypatch.setattr(sys, "argv", ["enrich_location.py"])
    monkeypatch.setattr(enrich_location, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(enrich_location, "OpenAI", lambda **_k: object())
    monkeypatch.setattr(enrich_location, "time", SimpleNamespace(sleep=lambda *_a: None))
    monkeypatch.setattr(enrich_location, "extract_location", extract)
    enrich_location.main()


def test_enrich_location_drops_pure_publication_candidates(monkeypatch):
    client = _Client([_event("pub", event_form=["publication"])])
    calls = []

    def _extract(*_args, **_kwargs):
        # main() swallows exceptions from the extractor, so record instead of raise.
        calls.append(1)
        return "東京都渋谷区神南1-1"

    _run_enrich_location(monkeypatch, client, _extract)

    assert calls == []
    assert client.event_writes == []
    assert "event_form" in client.selects[0][1]


def test_enrich_location_rechecks_publication_before_gpt_write(monkeypatch):
    client = _Client([_event("race")])

    def _extract(*_args, **_kwargs):
        client.make_publication("race")
        return "東京都渋谷区神南1-1"

    _run_enrich_location(monkeypatch, client, _extract)

    assert client.event_writes == []


def test_enrich_location_rechecks_publication_before_tcc_fallback_write(monkeypatch):
    client = _Client([
        _event("tcc", source_name="taiwan_cultural_center", raw_description=""),
    ])
    client.on_select = lambda fake, table, columns: (
        fake.make_publication("tcc") if "raw_description" in columns else None
    )

    _run_enrich_location(monkeypatch, client, _boom)

    assert client.event_writes == []


def test_enrich_location_still_writes_physical_events(monkeypatch):
    client = _Client([_event("physical", location_name=None)])

    _run_enrich_location(monkeypatch, client, lambda *_a, **_k: "東京都渋谷区神南1-1")

    assert [write[1] for write in client.event_writes] == ["physical"]


# ---------------------------------------------------------------------------
# enrich_addresses.py
# ---------------------------------------------------------------------------

def _run_enrich_addresses(monkeypatch, client, lookup):
    monkeypatch.setattr(sys, "argv", ["enrich_addresses.py"])
    monkeypatch.setattr(enrich_addresses, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(enrich_addresses, "OpenAI", lambda **_k: object())
    monkeypatch.setattr(enrich_addresses, "time", SimpleNamespace(sleep=lambda *_a: None))
    monkeypatch.setattr(enrich_addresses, "lookup_address", lookup)
    enrich_addresses.main()


def _address_result():
    return {"location_address": "東京都渋谷区神南1-1", "confidence": "high"}


def test_enrich_addresses_drops_pure_publication_candidates(monkeypatch):
    # location_name holds the publisher, which is exactly what leaked into
    # location_address in production.
    client = _Client([
        _event(
            "pub",
            source_name="ndl_opensearch",
            event_form=["publication"],
            location_name="南山大学人類学研究所",
        ),
    ])

    _run_enrich_addresses(monkeypatch, client, _boom)

    assert client.writes == []
    assert "event_form" in client.selects[0][1]


def test_enrich_addresses_rechecks_publication_before_write(monkeypatch):
    client = _Client([_event("race")])

    def _lookup(*_args, **_kwargs):
        client.make_publication("race")
        return _address_result()

    _run_enrich_addresses(monkeypatch, client, _lookup)

    assert client.writes == []


def test_enrich_addresses_still_writes_physical_events(monkeypatch):
    client = _Client([_event("physical")])

    _run_enrich_addresses(monkeypatch, client, lambda *_a, **_k: _address_result())

    assert [write[1] for write in client.event_writes] == ["physical"]


# ---------------------------------------------------------------------------
# backfill_location_prefectures.py
# ---------------------------------------------------------------------------

def _run_backfill_prefectures(monkeypatch, client):
    monkeypatch.setattr(sys, "argv", ["backfill_location_prefectures.py", "--apply"])
    monkeypatch.setattr(
        backfill_location_prefectures, "create_client", lambda *_a, **_k: client
    )
    backfill_location_prefectures.main()


def test_backfill_prefectures_drops_pure_publication_candidates(monkeypatch):
    client = _Client([
        _event(
            "pub",
            event_form=["publication"],
            location_address="愛知県名古屋市昭和区山里町18",
        ),
    ])

    _run_backfill_prefectures(monkeypatch, client)

    assert client.event_writes == []
    assert any("event_form" in columns for _table, columns in client.selects)


def test_backfill_prefectures_rechecks_publication_before_write(monkeypatch):
    client = _Client([_event("race", location_address="東京都渋谷区神南1-1")])
    client.on_select = lambda fake, table, columns: (
        fake.make_publication("race") if "location_prefectures" in columns else None
    )

    _run_backfill_prefectures(monkeypatch, client)

    assert client.event_writes == []


def test_backfill_prefectures_still_writes_physical_events(monkeypatch):
    client = _Client([_event("physical", location_address="東京都渋谷区神南1-1")])

    _run_backfill_prefectures(monkeypatch, client)

    assert client.event_writes == [
        ("events", "physical", {"location_prefectures": ["東京都"]})
    ]


# ---------------------------------------------------------------------------
# geocode_events.py
# ---------------------------------------------------------------------------

def _run_geocode(monkeypatch, client, geocode):
    monkeypatch.setattr(geocode_events, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(geocode_events, "geocode_address", geocode)
    geocode_events.run(dry_run=False, limit=10)


def test_geocode_drops_pure_publication_candidates(monkeypatch):
    client = _Client([
        _event(
            "pub",
            event_form=["publication"],
            location_address="愛知県名古屋市昭和区山里町18",
        ),
    ])

    _run_geocode(monkeypatch, client, _boom)

    assert client.event_writes == []
    assert "event_form" in client.selects[0][1]


def test_geocode_rechecks_publication_before_write(monkeypatch):
    client = _Client([_event("race", location_address="東京都渋谷区神南1-1")])

    def _geocode(*_args, **_kwargs):
        client.make_publication("race")
        return (35.663, 139.700)

    _run_geocode(monkeypatch, client, _geocode)

    assert client.event_writes == []


def test_geocode_still_writes_physical_events(monkeypatch):
    client = _Client([_event("physical", location_address="東京都渋谷区神南1-1")])

    _run_geocode(monkeypatch, client, lambda *_a, **_k: (35.663, 139.700))

    assert [write[1] for write in client.event_writes] == ["physical"]


# ---------------------------------------------------------------------------
# backfill_locations.py
# ---------------------------------------------------------------------------

def test_backfill_locations_drops_pure_publication_candidates(monkeypatch):
    client = _Client([_event("pub", event_form=["publication"])])
    monkeypatch.setattr(backfill_locations, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(backfill_locations, "sync_playwright", _boom)

    backfill_locations.run(dry_run=False)

    assert client.event_writes == []
    assert all("event_form" in columns for _table, columns in client.selects)


def test_backfill_locations_apply_updates_rechecks_publication():
    """Direct write-path call, bypassing the candidate filter entirely."""
    client = _Client([_event("pub", event_form=["publication"])])

    applied = backfill_locations._apply_updates(
        client, [{"id": "pub", "payload": {"location_address": "東京都渋谷区神南1-1"}}]
    )

    assert applied == 0
    assert client.event_writes == []


def test_backfill_locations_apply_updates_writes_physical_events():
    client = _Client([_event("physical")])

    applied = backfill_locations._apply_updates(
        client, [{"id": "physical", "payload": {"location_address": "東京都渋谷区神南1-1"}}]
    )

    assert applied == 1
    assert [write[1] for write in client.event_writes] == ["physical"]
