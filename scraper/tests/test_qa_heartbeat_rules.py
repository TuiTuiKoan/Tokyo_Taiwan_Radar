"""qa_heartbeat classifies safe report types by rule, without a model call (#321)."""

import qa_auto_fix
import qa_heartbeat as hb


def test_every_safe_report_type_has_a_rule_and_a_handler():
    for t in qa_auto_fix.SAFE_REPORT_TYPES:
        assert t in hb.RULE_BY_REPORT_TYPE, t
        r_class = hb.RULE_BY_REPORT_TYPE[t]
        assert hb.ROUTING[r_class]["handler_key"] in qa_auto_fix.HANDLER_MAP
        assert hb.RULE_CONFIDENCE >= hb.ROUTING[r_class]["min_confidence"]


def test_single_known_type_is_classified_by_rule():
    c = hb._classify_by_rule({"report_types": ["auto_qa_simplified_zh"]})
    assert c["r_class"] == "R-ANN-SC" and c["source"] == "rule"
    assert c["tokens_in"] == c["tokens_out"] == 0


def test_unknown_or_compound_types_fall_back_to_the_model():
    assert hb._classify_by_rule({"report_types": ["something_else"]}) is None
    assert hb._classify_by_rule(
        {"report_types": ["auto_qa_simplified_zh", "auto_qa_location_url_is_event_url"]}
    ) is None
    assert hb._classify_by_rule({"report_types": []}) is None
