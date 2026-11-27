"""geocode_events: candidate selection and venue write-back (#706)."""

from types import SimpleNamespace

import geocode_events as ge

STREET_ADDR = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"


class _Query:
    def __init__(self, client, table):
        self.client, self.table, self.payload, self.filters = client, table, None, []

    def select(self, *_a, **_k):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self.payload is not None:
            self.client.writes.append((self.table, self.payload, tuple(self.filters)))
            return SimpleNamespace(data=[])
        venue_id = next(v for k, c, v in self.filters if c == "id")
        return SimpleNamespace(data=self.client.venues.get(venue_id))


class _Client:
    def __init__(self, venues=None):
        self.venues, self.writes = venues or {}, []

    def table(self, name):
        return _Query(self, name)


def _venue(**overrides):
    return {
        "id": "v1", "address": STREET_ADDR, "latitude": None, "longitude": None,
        "is_authoritative": True, "is_multi_venue": False, **overrides,
    }


def _event(**overrides):
    return {
        "id": "e1", "source_id": "s1", "location_name": "台湾文化センター",
        "location_address": STREET_ADDR, "venue_id": "v1", "latitude": None,
        "event_form": ["lecture"], "start_date": "2026-12-01", "end_date": None, **overrides,
    }


def _run(monkeypatch, client, event, result=(35.67, 139.75)):
    calls = []

    def geocode(address, _appid):
        calls.append(address)
        return result

    monkeypatch.setattr(ge, "geocode_address", geocode)
    monkeypatch.setattr(ge, "is_pure_publication_in_db", lambda *_a: False)
    outcome = ge.geocode_one(client, event, None, False)
    return outcome, calls


def test_only_street_level_addresses_are_geocoded():
    assert ge.is_geocodable(_event())
    assert not ge.is_geocodable(_event(location_address="東京都港区"))
    assert not ge.is_geocodable(_event(location_address="東京都港区六本木"))
    assert not ge.is_geocodable(_event(location_address="台北市信義區信義路五段7號"))
    assert not ge.is_geocodable(_event(location_name="オンライン"))


def test_upcoming_events_come_first_then_newest_past():
    events = [
        _event(id="past-old", start_date="2025-01-01"),
        _event(id="up-late", start_date="2026-12-20"),
        _event(id="past-new", start_date="2026-10-01"),
        _event(id="up-soon", start_date="2026-11-25"),
        _event(id="running", start_date="2026-10-01", end_date="2026-12-31"),
    ]
    ordered = [e["id"] for e in ge.order_candidates(events, "2026-11-22")]
    assert ordered == ["running", "up-soon", "up-late", "past-new", "past-old"]


def test_writes_event_coordinates_only(monkeypatch):
    client = _Client({"v1": _venue(address=None)})
    outcome, calls = _run(monkeypatch, client, _event())

    assert outcome == "api" and calls == [STREET_ADDR]
    assert [(t, p) for t, p, _ in client.writes] == [("events", {"latitude": 35.67, "longitude": 139.75})]
    assert ("is", "latitude", "null") in client.writes[0][2]


def test_a_failed_lookup_writes_nothing(monkeypatch):
    client = _Client()
    outcome, _ = _run(monkeypatch, client, _event(), result=None)

    assert outcome == "failed" and client.writes == []


def test_one_failing_event_does_not_stop_the_batch(monkeypatch):
    events = [_event(id="bad"), _event(id="good", venue_id=None)]
    client = _Client({"v1": _venue()})
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(ge, "create_client", lambda *_a: client)
    monkeypatch.setattr(ge, "fetch_candidates", lambda _sb: events)
    monkeypatch.setattr(ge, "is_pure_publication_in_db", lambda *_a: False)

    def geocode(address, _appid):
        if geocode.calls == 0:
            geocode.calls += 1
            raise RuntimeError("boom")
        return (35.0, 139.0)

    geocode.calls = 0
    monkeypatch.setattr(ge, "geocode_address", geocode)
    ge.run(dry_run=False, limit=10)

    assert [f[0][2] for t, _, f in client.writes if t == "events"] == ["good"]
