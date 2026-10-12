"""The annotator must act on its own Taiwan-relevance verdict.

2026-10-12: the model wrote 「台湾との直接的な関連はありません」 in
selection_reason for 16 iwafu events, but nothing read that verdict and the
events stayed active. _relevance_gate_update turns the structured
taiwan_relevance field into is_active=false.
"""

from annotator import (
    RELEVANCE_GATE_REASON,
    _relevance_gate_update,
)

IWAFU_EVENT = {"id": "e1", "source_name": "iwafu", "raw_title": "詳細を見る"}
NOT_TAIWAN = {"taiwan_relevance": {"is_relevant": False, "confidence": 0.95}}


def test_confident_irrelevant_event_is_deactivated():
    assert _relevance_gate_update(IWAFU_EVENT, NOT_TAIWAN, {}, False) == {
        "is_active": False,
        "deactivated_reason": RELEVANCE_GATE_REASON,
    }


def test_relevant_event_is_untouched():
    ann = {"taiwan_relevance": {"is_relevant": True, "confidence": 0.99}}
    assert _relevance_gate_update(IWAFU_EVENT, ann, {}, False) is None


def test_low_confidence_is_untouched():
    ann = {"taiwan_relevance": {"is_relevant": False, "confidence": 0.6}}
    assert _relevance_gate_update(IWAFU_EVENT, ann, {}, False) is None


def test_missing_or_malformed_verdict_is_untouched():
    assert _relevance_gate_update(IWAFU_EVENT, {}, {}, False) is None
    assert _relevance_gate_update(IWAFU_EVENT, {"taiwan_relevance": "no"}, {}, False) is None
    bad_conf = {"taiwan_relevance": {"is_relevant": False, "confidence": "high"}}
    assert _relevance_gate_update(IWAFU_EVENT, bad_conf, {}, False) is None
    # is_relevant must be an explicit False, not just falsy
    null_rel = {"taiwan_relevance": {"is_relevant": None, "confidence": 0.99}}
    assert _relevance_gate_update(IWAFU_EVENT, null_rel, {}, False) is None


def test_human_reviewed_events_are_never_gated():
    assert _relevance_gate_update(IWAFU_EVENT, NOT_TAIWAN, {"name_zh": "x"}, False) is None
    assert _relevance_gate_update(IWAFU_EVENT, NOT_TAIWAN, {}, True) is None


def test_user_submissions_are_never_gated():
    event = {"id": "e2", "source_name": "user_submission"}
    assert _relevance_gate_update(event, NOT_TAIWAN, {}, False) is None
