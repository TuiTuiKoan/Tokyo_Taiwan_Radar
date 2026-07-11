from types import SimpleNamespace

import pytest

from annotator import (
    PUBLICATION_NULL_FIELDS,
    _assert_pure_publication_payload,
    _finalize_publication_update,
    _verify_publication_postcondition,
)


@pytest.mark.parametrize("mode", ["normal", "fix-reviewed", "re-annotate-all"])
def test_all_annotation_modes_apply_final_pure_normalization(mode):
    event = {
        "id": f"pure-{mode}",
        "event_form": ["publication"],
        "organizer": "架空出版社",
        "organizer_url": None,
    }
    update = {
        "event_form": ["publication"],
        "location_address": "東京都千代田区1-1",
        "business_hours": "10:00-18:00",
        "location_prefectures": ["東京都"],
        "location_url": "https://venue.example.test/",
        "venue_id": "venue-id",
        "organizer": "GPTが推測した出版社",
    }
    localized = {
        "location_address_zh": "東京都千代田區1-1",
        "location_address_en": "1-1 Chiyoda, Tokyo",
        "business_hours_zh": "10:00-18:00",
        "business_hours_en": "10:00-18:00",
    }
    registry = {
        "架空出版社": {
            "id": "publisher-id",
            "homepage": "https://publisher.example.test/",
        }
    }

    assert _finalize_publication_update(event, update, localized, {}, registry)
    assert update["event_form"] == ["publication"]
    assert all(update[field] is None for field in PUBLICATION_NULL_FIELDS)
    assert update["location_url"] is None
    assert "venue_id" not in update
    assert update["organizer"] == "架空出版社"
    assert update["organizer_id"] == "publisher-id"
    assert update["organizer_url"] == "https://publisher.example.test/"
    assert localized == {}


def test_publication_capable_source_physical_talk_is_unchanged():
    event = {
        "source_name": "eslite_spectrum",
        "event_form": ["lecture"],
        "organizer": "誠品生活日本橋",
    }
    update = {
        "event_form": ["lecture"],
        "location_address": "東京都中央区日本橋室町3-2-1",
        "business_hours": "13:00〜",
        "location_prefectures": ["東京都"],
    }

    assert not _finalize_publication_update(event, update, {}, {}, {})
    assert update["business_hours"] == "13:00〜"
    assert update["location_address"].startswith("東京都")


def test_pure_finalizer_rejects_nonempty_policy_field_correction():
    event = {"event_form": ["publication"], "organizer": "架空出版社"}
    update = {"event_form": ["publication"]}

    with pytest.raises(RuntimeError, match="policy conflicts"):
        _finalize_publication_update(
            event,
            update,
            {},
            {"business_hours": "10:00-18:00"},
            {},
        )


def test_pure_finalizer_skips_unvalidated_registry_homepage_backfill():
    event = {
        "event_form": ["publication"],
        "organizer": "架空出版社",
        "organizer_url": None,
    }
    update = {"event_form": ["publication"]}
    registry = {
        "架空出版社": {
            "id": "publisher-id",
            "homepage": "https://www.amazon.co.jp/example",
            "aliases": [],
        }
    }

    assert _finalize_publication_update(event, update, {}, {}, registry)
    assert update["organizer_id"] == "publisher-id"
    assert update.get("organizer_url") is None


def test_pure_payload_guard_raises_before_write_on_non_null_policy_fields():
    with pytest.raises(RuntimeError, match="payload postcondition failed"):
        _assert_pure_publication_payload(
            {
                "event_form": ["publication"],
                "business_hours": "stale",
            },
            {},
        )


class PostconditionQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def eq(self, _field, _value):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class PostconditionClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "events"
        return PostconditionQuery(self.rows)


def test_annotation_postcondition_failure_raises():
    row = {"id": "pure-1", **{field: None for field in PUBLICATION_NULL_FIELDS}}
    row["business_hours"] = "stale"

    with pytest.raises(RuntimeError, match="postcondition failed"):
        _verify_publication_postcondition(PostconditionClient([row]), "pure-1")