"""
Focused tests for `_build_sub_localized_location` (annotator).

Phase 3 prevention fix: a multi-venue parent (e.g. a culture-month umbrella
event) must NOT push its localized location / office hours onto sub-events that
run at a different venue. Same-location sub-events keep the existing inheritance
behaviour unchanged.

The helper is a pure function (module-level) extracted from the parent→sub
build path so the guard can be unit-tested without invoking the GPT pipeline.
"""
from annotator import _build_sub_localized_location

# A representative parent whose localized location is the TCC default — exactly
# the value that previously leaked onto Waseda-hosted sub-events.
PARENT_LOCALIZED = {
    "location_name_zh": "台北駐日經濟文化代表處 台灣文化中心",
    "location_name_en": "Taiwan Cultural Center, TECRO",
    "location_address_zh": "東京都港區虎之門1-1-12 虎之門大樓2樓",
    "location_address_en": "2F Toranomon Bldg, 1-1-12 Toranomon, Minato, Tokyo",
    "business_hours_zh": "10:00～17:00",
    "business_hours_en": "10:00 AM – 5:00 PM",
}
PARENT_NAME = "台北駐日経済文化代表処 台湾文化センター"

_LOCALIZED_KEYS = {
    "location_name_zh",
    "location_name_en",
    "location_address_zh",
    "location_address_en",
    "business_hours_zh",
    "business_hours_en",
}


# ──────────────────────────────────────────────────────────────────────────────
# Distinct venue -> NO inheritance of the parent's localized location.
# ──────────────────────────────────────────────────────────────────────────────
class TestDistinctVenueNoInheritance:
    def test_distinct_venue_no_own_localized_yields_empty(self):
        # The core regression: a Waseda sub-event with no own zh/en must NOT
        # inherit the parent's TCC localized strings — it stays empty so the
        # web ja→zh→en fallback can use the sub-event's own ja text instead.
        sub = {"location_name": "小野記念講堂"}
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert result == {}
        assert PARENT_LOCALIZED["location_name_zh"] not in result.values()

    def test_distinct_venue_keeps_own_localized(self):
        sub = {
            "location_name": "小野記念講堂",
            "location_name_zh": "小野紀念講堂",
            "location_name_en": "Ono Memorial Auditorium",
        }
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert result["location_name_zh"] == "小野紀念講堂"
        assert result["location_name_en"] == "Ono Memorial Auditorium"
        # Parent's localized location must NOT leak into address fields.
        assert "location_address_zh" not in result
        assert "location_address_en" not in result
        assert PARENT_LOCALIZED["location_name_zh"] not in result.values()

    def test_distinct_venue_with_own_hours_does_not_inherit_parent_hours(self):
        sub = {"location_name": "小野記念講堂", "business_hours": "18:00〜"}
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert "business_hours_zh" not in result
        assert "business_hours_en" not in result


# ──────────────────────────────────────────────────────────────────────────────
# Same venue -> preserve the existing inheritance behaviour (no regression).
# ──────────────────────────────────────────────────────────────────────────────
class TestSameVenueInheritancePreserved:
    def test_same_venue_inherits_parent_localized(self):
        sub = {"location_name": PARENT_NAME}
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert result["location_name_zh"] == PARENT_LOCALIZED["location_name_zh"]
        assert result["location_name_en"] == PARENT_LOCALIZED["location_name_en"]
        assert result["location_address_zh"] == PARENT_LOCALIZED["location_address_zh"]
        assert result["business_hours_zh"] == PARENT_LOCALIZED["business_hours_zh"]

    def test_no_sub_location_inherits_parent_localized(self):
        sub = {}
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert result["location_name_zh"] == PARENT_LOCALIZED["location_name_zh"]
        assert result["business_hours_zh"] == PARENT_LOCALIZED["business_hours_zh"]

    def test_same_venue_own_hours_not_inherited(self):
        # Even at the same venue, a sub with its own base business_hours must not
        # inherit the parent's office-hours localized strings.
        sub = {"location_name": PARENT_NAME, "business_hours": "14:00開演"}
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert "business_hours_zh" not in result
        # Location still inherits because the venue is the same.
        assert result["location_name_zh"] == PARENT_LOCALIZED["location_name_zh"]


# ──────────────────────────────────────────────────────────────────────────────
# Structural guards.
# ──────────────────────────────────────────────────────────────────────────────
class TestStructuralGuards:
    def test_helper_never_emits_non_localized_keys(self):
        # Sub-event source_id drift guard: the localized-fallback helper must
        # only ever emit the six localized location keys, never structural keys
        # such as source_id / parent_event_id. Proves this fix cannot add,
        # remove, or reorder _subN source_id allocation.
        sub = {
            "location_name": "小野記念講堂",
            "location_name_zh": "小野紀念講堂",
            "source_id": "puppet_month_sub3",
            "parent_event_id": "7446190c-64ad-4273-adbe-48f14be1cb0b",
        }
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert set(result).issubset(_LOCALIZED_KEYS)
        assert "source_id" not in result
        assert "parent_event_id" not in result

    def test_strips_leading_label_separator_in_location(self):
        # Mirrors the nested _loc cleaner: GPT sometimes leaves a leading "：".
        sub = {
            "location_name": "小野記念講堂",
            "location_name_en": "：Ono Hall",
        }
        result = _build_sub_localized_location(sub, PARENT_NAME, PARENT_LOCALIZED)
        assert result["location_name_en"] == "Ono Hall"

    def test_none_localized_parent_is_safe(self):
        sub = {"location_name": PARENT_NAME}
        result = _build_sub_localized_location(sub, PARENT_NAME, None)
        assert result == {}
