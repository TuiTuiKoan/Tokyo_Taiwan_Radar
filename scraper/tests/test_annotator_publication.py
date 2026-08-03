import json
import logging
from types import SimpleNamespace

import pytest

from annotator import (
    PUBLICATION_NULL_FIELDS,
    PUBLICATION_VENUE_NAME_FIELDS,
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


def test_pure_finalizer_consumes_publisher_evidence_with_existing_organizer():
    event = {
        "event_form": ["publication"],
        "organizer": "既存出版社",
        "organizer_url": None,
    }
    update = {
        "event_form": ["publication"],
        "_publisher_evidence": "証拠出版社",
    }

    assert _finalize_publication_update(event, update, {}, {}, {})
    assert update["organizer"] == "既存出版社"
    assert "_publisher_evidence" not in update


def test_pure_finalizer_logs_sanitized_path_after_consuming_evidence(caplog):
    event = {
        "id": "publication-observability-event",
        "event_form": ["publication"],
        "organizer": "既存出版社",
        "organizer_url": None,
    }
    update = {
        "event_form": ["publication"],
        "_publisher_evidence": "証拠出版社",
    }

    with caplog.at_level(logging.INFO, logger="annotator"):
        assert _finalize_publication_update(event, update, {}, {}, {})

    marker_records = [
        record
        for record in caplog.records
        if record.name == "annotator"
        and record.getMessage().startswith("publication_finalizer_path ")
    ]
    assert len(marker_records) == 1
    marker = json.loads(marker_records[0].getMessage().split(" ", 1)[1])
    assert marker == {
        "event_id": "publication-observability-event",
        "pure_publication": True,
        "existing_organizer_truthy": True,
        "publisher_evidence_present": True,
        "internal_key_consumed": True,
    }
    assert "既存出版社" not in caplog.text
    assert "証拠出版社" not in caplog.text
    assert "_publisher_evidence" not in update
    assert update["organizer"] == "既存出版社"


def test_pure_finalizer_uses_publisher_evidence_without_event_organizer():
    event = {
        "event_form": ["publication"],
        "organizer_url": None,
    }
    update = {
        "event_form": ["publication"],
        "_publisher_evidence": "証拠出版社",
    }

    assert _finalize_publication_update(event, update, {}, {}, {})
    assert update["organizer"] == "証拠出版社"
    assert "_publisher_evidence" not in update


def test_publication_capable_source_physical_talk_is_unchanged(caplog):
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

    with caplog.at_level(logging.INFO, logger="annotator"):
        assert not _finalize_publication_update(event, update, {}, {}, {})
    assert update["business_hours"] == "13:00〜"
    assert update["location_address"].startswith("東京都")
    assert "publication_finalizer_path" not in caplog.text


def test_pure_finalizer_clears_unprotected_venue_names():
    event = {"id": "pure-venue", "event_form": ["publication"], "organizer": "架空出版社"}
    update = {
        "event_form": ["publication"],
        "location_name": "誠品生活日本橋",
        "location_name_zh": "誠品生活日本橋",
        "location_name_en": "Eslite Spectrum Nihonbashi",
    }
    localized = {
        "location_name_zh": "誠品生活日本橋",
        "location_name_en": "Eslite Spectrum Nihonbashi",
    }

    assert _finalize_publication_update(event, update, localized, {}, {})
    assert all(update[field] is None for field in PUBLICATION_VENUE_NAME_FIELDS)
    assert localized == {}


def test_pure_finalizer_keeps_venue_name_with_nonempty_field_correction(caplog):
    event = {"id": "pure-fc", "event_form": ["publication"], "organizer": "架空出版社"}
    update = {
        "event_form": ["publication"],
        "location_name": "大阪城ホール",
        "location_name_zh": "GPTが推測した会場",
        "location_name_en": "GPT guessed venue",
    }
    localized = {"location_name_zh": "GPTが推測した会場"}

    with caplog.at_level(logging.INFO, logger="annotator"):
        assert _finalize_publication_update(
            event, update, localized, {"location_name": "大阪城ホール"}, {}
        )

    assert update["location_name"] == "大阪城ホール"
    assert update["location_name_zh"] is None
    assert update["location_name_en"] is None
    assert localized == {}

    markers = [
        record
        for record in caplog.records
        if record.getMessage().startswith("publication_venue_name_fc_exemption ")
    ]
    assert len(markers) == 1
    assert json.loads(markers[0].getMessage().split(" ", 1)[1]) == {
        "event_id": "pure-fc",
        "fields": ["location_name"],
    }
    assert "大阪城ホール" not in caplog.text


def test_pure_finalizer_treats_empty_venue_field_correction_as_unprotected():
    event = {"id": "pure-empty-fc", "event_form": ["publication"], "organizer": "架空出版社"}
    update = {"event_form": ["publication"], "location_name": "誠品生活日本橋"}

    assert _finalize_publication_update(event, update, {}, {"location_name": ""}, {})
    assert update["location_name"] is None


def test_pure_finalizer_keeps_venue_names_for_mixed_publication_form(caplog):
    event = {
        "id": "mixed-form",
        "event_form": ["publication", "lecture"],
        "organizer": "誠品生活日本橋",
    }
    update = {
        "event_form": ["publication", "lecture"],
        "location_name": "誠品生活日本橋",
        "location_name_zh": "誠品生活日本橋",
        "business_hours": "13:00〜",
        "location_url": "https://venue.example.test/",
    }

    with caplog.at_level(logging.INFO, logger="annotator"):
        assert not _finalize_publication_update(event, update, {}, {}, {})

    assert update["location_name"] == "誠品生活日本橋"
    assert update["location_name_zh"] == "誠品生活日本橋"
    assert update["business_hours"] == "13:00〜"
    assert update["location_url"] == "https://venue.example.test/"
    assert "publication_venue_name_fc_exemption" not in caplog.text


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


def test_pure_payload_guard_rejects_unprotected_venue_name():
    with pytest.raises(RuntimeError, match="venue="):
        _assert_pure_publication_payload(
            {
                "event_form": ["publication"],
                **{field: None for field in PUBLICATION_NULL_FIELDS},
                "location_name": "誠品生活日本橋",
            },
            {},
        )


def test_pure_payload_guard_allows_venue_name_with_nonempty_correction():
    _assert_pure_publication_payload(
        {
            "event_form": ["publication"],
            **{field: None for field in PUBLICATION_NULL_FIELDS},
            "location_name": "大阪城ホール",
        },
        {},
        {"location_name": "大阪城ホール"},
    )


def test_pure_payload_guard_ignores_mixed_publication_form():
    _assert_pure_publication_payload(
        {
            "event_form": ["publication", "lecture"],
            "location_name": "誠品生活日本橋",
            "business_hours": "13:00〜",
        },
        {"location_name_zh": "誠品生活日本橋"},
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


def test_annotation_postcondition_rejects_residual_venue_name():
    row = {
        "id": "pure-2",
        **{field: None for field in PUBLICATION_NULL_FIELDS},
        "location_name": "誠品生活日本橋",
    }

    with pytest.raises(RuntimeError, match="postcondition failed"):
        _verify_publication_postcondition(PostconditionClient([row]), "pure-2")


def test_annotation_postcondition_accepts_protected_venue_name():
    row = {
        "id": "pure-3",
        **{field: None for field in PUBLICATION_NULL_FIELDS},
        "location_name": "大阪城ホール",
        "location_name_zh": None,
        "location_name_en": None,
    }

    _verify_publication_postcondition(
        PostconditionClient([row]), "pure-3", {"location_name": "大阪城ホール"}
    )


def test_annotation_postcondition_rejects_protected_venue_name_mismatch():
    row = {
        "id": "pure-4",
        **{field: None for field in PUBLICATION_NULL_FIELDS},
        "location_name": "別の会場",
    }

    with pytest.raises(RuntimeError, match="postcondition failed"):
        _verify_publication_postcondition(
            PostconditionClient([row]), "pure-4", {"location_name": "大阪城ホール"}
        )