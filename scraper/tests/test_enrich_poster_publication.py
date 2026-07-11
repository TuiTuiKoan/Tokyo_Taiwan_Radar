from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import enrich_poster


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = "select"
        self.payload = None
        self.event_id = None

    def select(self, columns, **_kwargs):
        self.client.selects.append((self.table, columns))
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = deepcopy(payload)
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = deepcopy(payload)
        return self

    def eq(self, field, value):
        if field == "id":
            self.event_id = value
        return self

    def in_(self, *_args):
        return self

    @property
    def not_(self):
        return self

    def is_(self, *_args):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        if self.operation == "update":
            self.client.writes.append(("events", deepcopy(self.payload)))
            self.client.events[self.event_id].update(self.payload)
            return SimpleNamespace(data=[{"id": self.event_id}])
        if self.operation == "upsert":
            self.client.writes.append(("field_corrections", deepcopy(self.payload)))
            return SimpleNamespace(data=[deepcopy(self.payload)])
        rows = list(self.client.events.values())
        if self.event_id:
            rows = [row for row in rows if row["id"] == self.event_id]
        return SimpleNamespace(data=deepcopy(rows))


class _Client:
    def __init__(self, events):
        self.events = {event["id"]: deepcopy(event) for event in events}
        self.selects = []
        self.writes = []

    def table(self, name):
        return _Query(self, name)


def _event(event_id, **overrides):
    event = {
        "id": event_id,
        "source_name": "peatix",
        "name_ja": "Event",
        "start_date": None,
        "end_date": None,
        "location_name": None,
        "organizer": None,
        "annotation_status": "annotated",
        "image_url": "https://images.example.test/poster.jpg",
        "raw_description": "A" * 120,
        "event_form": ["lecture"],
        "is_active": True,
    }
    event.update(overrides)
    return event


def _vision_result():
    return {
        "event_date": "2026-08-20",
        "end_date": None,
        "venue": "Tokyo Hall",
        "organizer": "Example Organizer",
        "confidence": 0.95,
    }


def test_hanmoto_placeholder_guard_canonicalizes_variants_without_blocking_real_cover():
    assert enrich_poster._is_placeholder_image_url(
        "http://www.hanmoto.com/bd/img/noimage.jpg?cache=1"
    )
    assert enrich_poster._is_placeholder_image_url(
        "https://hanmoto.com/assets/no-cover_large.webp#v2"
    )
    assert not enrich_poster._is_placeholder_image_url(
        "https://www.hanmoto.com/bd/img/9784868140771.jpg"
    )
    assert not enrich_poster._is_placeholder_image_url(
        "https://images.example.test/noimage.jpg"
    )


def test_candidate_select_has_guard_fields_and_filters_pure_and_placeholder_rows():
    client = _Client(
        [
            _event("pure", event_form=["publication"]),
            _event(
                "placeholder",
                image_url="https://www.hanmoto.com/bd/img/noimage.jpg",
            ),
            _event("physical"),
        ]
    )

    candidates = enrich_poster._fetch_candidates(client)

    assert [event["id"] for event in candidates] == ["physical"]
    selected = client.selects[0][1]
    assert "event_form" in selected
    assert "source_name" in selected
    assert "image_url" in selected


def test_pure_and_placeholder_candidates_never_reach_vision_or_write(monkeypatch):
    client = _Client(
        [
            _event("pure", event_form=["publication"]),
            _event(
                "placeholder",
                image_url="https://www.hanmoto.com/bd/img/noimage.jpg?cache=1",
            ),
        ]
    )
    monkeypatch.setattr(enrich_poster, "_get_supabase", lambda: client)
    monkeypatch.setattr(enrich_poster, "_get_openai", lambda: object())
    monkeypatch.setattr(
        enrich_poster,
        "_download_image",
        lambda _url: (_ for _ in ()).throw(AssertionError("download must not run")),
    )
    monkeypatch.setattr(
        enrich_poster,
        "_extract_from_poster",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Vision must not run")),
    )

    enrich_poster.run()

    assert client.writes == []


def test_post_vision_guard_blocks_toctou_change_before_event_or_fc_write():
    original = _event("race")
    client = _Client([_event("race", event_form=["publication"])])

    applied = enrich_poster._apply_if_confident(
        client,
        original,
        _vision_result(),
        set(),
    )

    assert applied is False
    assert client.writes == []


def test_physical_hanmoto_real_poster_and_ordinary_nonpublication_can_enrich():
    physical = _event(
        "physical",
        source_name="hanmoto",
        image_url="https://www.hanmoto.com/bd/img/9784868140771.jpg",
        event_form=["lecture"],
    )
    ordinary = _event("ordinary", source_name="note_creators", event_form=[])
    client = _Client([physical, ordinary])

    for event in (physical, ordinary):
        assert enrich_poster._apply_if_confident(
            client,
            event,
            _vision_result(),
            set(),
        )

    event_writes = [payload for table, payload in client.writes if table == "events"]
    assert len(event_writes) == 2
    assert all(payload["location_name"] == "Tokyo Hall" for payload in event_writes)
    assert len([table for table, _payload in client.writes if table == "field_corrections"]) == 6
