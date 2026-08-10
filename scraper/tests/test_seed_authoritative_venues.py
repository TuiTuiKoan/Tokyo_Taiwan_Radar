from copy import deepcopy
from types import SimpleNamespace

import pytest

import _oneoff_seed_authoritative_venues as seed


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = "select"
        self.payload = None
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, list(values)))
        return self

    def limit(self, _value):
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = deepcopy(payload)
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = deepcopy(payload)
        return self

    def execute(self):
        if self.operation != "select":
            self.client.writes.append((self.operation, self.table, self.payload, list(self.filters)))
            return SimpleNamespace(data=[])
        if self.table == "venues":
            rows = self.client.venues
        elif self.table == "events":
            self.client.event_reads += 1
            rows = self.client.events
        else:
            raise AssertionError(self.table)
        for kind, field, value in self.filters:
            if kind == "eq":
                rows = [row for row in rows if row.get(field) == value]
            else:
                rows = [row for row in rows if row.get(field) in set(value)]
        return SimpleNamespace(data=deepcopy(rows))


class _Client:
    def __init__(self, venues=None, events=None):
        self.venues = venues or []
        self.events = events or []
        self.writes = []
        self.event_reads = 0

    def table(self, name):
        return _Query(self, name)


def _venue(canonical, aliases=(), **overrides):
    row = {
        "id": overrides.pop("id", f"id-{canonical}"),
        "canonical_name_ja": canonical,
        "canonical_name_zh": f"{canonical}-zh",
        "canonical_name_en": f"{canonical}-en",
        "address": "東京都千代田区1-1-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "千代田区",
        "aliases": list(aliases),
        "homepage": "https://example.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": None,
    }
    row.update(overrides)
    return row


def test_desired_aliases_replace_stale_values_and_exclude_canonical():
    existing = _venue("A館", ["古い別名", "A館"])
    desired = _venue("A館", ["A館", "新しい別名"])

    payload = seed._desired_payload(desired, existing)

    assert payload["aliases"] == ["新しい別名"]
    assert "古い別名" not in payload["aliases"]


@pytest.mark.parametrize(
    "rows,key",
    [
        ([_venue("A館"), _venue("A館", id="other")], "A館"),
        ([_venue("A館", ["共通"]), _venue("B館", ["共通"])], "共通"),
        ([_venue("A館"), _venue("B館", ["A館"])], "A館"),
    ],
)
def test_collision_preflight_covers_same_and_cross_tiers(rows, key):
    assert key in seed.check_key_collisions(rows)


def test_core_desired_state_has_no_key_collisions():
    rows = [seed._desired_payload(row, None) for row in seed.SEED_DATA]
    assert seed.check_key_collisions(rows) == {}


def test_eslite_uses_official_access_page_hours_and_keeps_forum_alias():
    venue = next(
        row for row in seed.SEED_DATA
        if row["canonical_name_ja"] == "誠品生活日本橋"
    )

    assert venue["homepage"] == (
        "https://www.eslitespectrum.jp/about/store/"
        "9cd1340f-26b6-4f55-9c33-d0487d7ac01d"
    )
    assert venue["address"] == "東京都中央区日本橋室町３丁目２−１ COREDO室町テラス 2F"
    assert venue["business_hours"] == "平日 11:00～20:00、土日祝 10:00～20:00"
    assert "誠品生活日本橋 イベントスペース「FORUM」" in venue["aliases"]


def test_address_compatibility_normalizes_postal_nfkc_dash_and_whitespace():
    official = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
    variants = [
        "〒105-0001 港区虎ノ門１−１−１２　別館",
        "東京都 港区 虎ノ門 1‐1‐12",
        "東京都港区虎ノ門1-1-12",
    ]

    assert all(seed._addresses_compatible(official, value) for value in variants)
    assert not seed._addresses_compatible(official, "東京都港区虎ノ門1-1-13")
    assert not seed._addresses_compatible(official, "大阪府大阪市北区1-1-12")


def test_active_event_conflict_ignores_inactive_rows():
    seed_row = {"address": "東京都港区虎ノ門1-1-12"}
    rows = [
        {"id": "active", "is_active": True, "location_address": "大阪府大阪市1-2-3"},
        {"id": "inactive", "is_active": False, "location_address": "北海道札幌市4-5-6"},
    ]

    conflict, addresses, conflicts = seed._has_conflict(seed_row, rows)

    assert conflict is True
    assert addresses == ["大阪府大阪市1-2-3"]
    assert conflicts == ["大阪府大阪市1-2-3"]


def test_build_plan_detects_noop_and_preserves_unverified_homepage(monkeypatch):
    desired = _venue("A館", ["別名"])
    desired["_preserve_existing_fields"] = ["homepage"]
    existing = deepcopy(desired)
    existing.pop("_preserve_existing_fields")
    existing["homepage"] = "https://live.example/"
    client = _Client([existing])
    monkeypatch.setattr(seed, "SEED_DATA", [desired])

    plan = seed._build_plan(client)[0]

    assert plan["action"] == "noop"
    assert plan["payload"]["homepage"] == "https://live.example/"


def test_dry_run_classifies_actions_and_never_writes(monkeypatch):
    existing_noop = _venue("Noop館")
    existing_update = _venue("Update館", ["古い別名"])
    desired_noop = deepcopy(existing_noop)
    desired_update = deepcopy(existing_update)
    desired_update["aliases"] = ["新しい別名"]
    desired_insert = _venue("Insert館")
    desired_insert.pop("id")
    desired_skip = _venue("Skip館", is_authoritative=False)
    desired_conflict = _venue("Conflict館", address="東京都港区1-1-1")
    client = _Client(
        [existing_noop, existing_update],
        events=[{
            "id": "event-conflict",
            "location_name": "Conflict館",
            "location_address": "大阪府大阪市2-2-2",
            "is_active": True,
        }],
    )
    monkeypatch.setattr(
        seed,
        "SEED_DATA",
        [desired_noop, desired_update, desired_insert, desired_skip, desired_conflict],
    )
    monkeypatch.setattr(seed, "_get_client", lambda: client)

    result = seed.run(dry_run=True)

    actions = {plan["canonical_name_ja"]: plan["action"] for plan in result["plans"]}
    assert actions == {
        "Noop館": "noop",
        "Update館": "update",
        "Insert館": "insert",
        "Skip館": "skip",
        "Conflict館": "conflict",
    }
    assert client.writes == []


def test_global_collision_stops_before_event_reads_or_writes(monkeypatch):
    desired = _venue("A館", ["既存別名"])
    desired.pop("id")
    live = _venue("B館", ["既存別名"])
    client = _Client([live])
    monkeypatch.setattr(seed, "SEED_DATA", [desired])

    with pytest.raises(seed.SeedCollisionError):
        seed._build_plan(client)

    assert client.event_reads == 0
    assert client.writes == []