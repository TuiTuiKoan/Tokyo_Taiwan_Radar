"""Annotator side of spec organizer-source-subevents.

- venue label inside parentheses is not the event venue (407a033b)
- cleaned tiff_jp article no longer triggers the keyword 'report' category
- schedule coverage retry eligibility mirrors every existing sub-event filter
- _annotate_one passes max_tokens through
"""

import json
import re
import types
from datetime import datetime
from pathlib import Path

import pytest

from annotator import (
    _annotate_one,
    _extract_venue_from_raw,
    _inject_keyword_categories,
    _should_retry_sub_events,
    _sub_event_retry_hint,
)
from sources.tiff import build_news_fields

FIXTURE = (Path(__file__).parent / "fixtures" / "tiff_jp_news_70779_body.txt").read_text(encoding="utf-8")
CLEANED = build_news_fields(FIXTURE, [], datetime(2026, 11, 15), lambda url: None)["raw_description"]
TITLE = "[東京国際映画祭 提携企画]台湾語映画 誕生70周年 特集 in Japan 12/2(水)～4(金)、8(火)～9(水)アテネ・フランセ文化センターにて開催！"


# ── venue label ─────────────────────────────────────────────────────────────

def test_parenthesised_venue_note_is_not_the_venue():
    assert "location_name" not in _extract_venue_from_raw(FIXTURE)


def test_line_venue_label_still_extracted():
    text = "日時：12月2日\n会場：白水出版センター\n東京都豊島区高田1-10-10"
    assert _extract_venue_from_raw(text).get("location_name") == "白水出版センター"


def test_halfwidth_paren_note_skipped_but_later_label_used():
    text = "懇親会(場所：別室)\n会場：アテネ・フランセ文化センター"
    assert _extract_venue_from_raw(text).get("location_name") == "アテネ・フランセ文化センター"


# ── report keyword injection ────────────────────────────────────────────────

def test_raw_page_with_navigation_gets_report_cleaned_does_not():
    assert "report" in _inject_keyword_categories(["movie"], TITLE + " " + FIXTURE)
    assert "report" not in _inject_keyword_categories(["movie"], TITLE + " " + CLEANED)


# ── coverage retry eligibility ──────────────────────────────────────────────

def _event(**kw):
    e = {"source_name": "tiff_jp", "source_id": "tiff_jp_70779", "raw_title": TITLE, "parent_event_id": None}
    e.update(kw)
    return e


def _ok(event=None, subs=None, raw=CLEANED, pub=False, inactive=False):
    return _should_retry_sub_events(
        event or _event(), subs, raw, is_pure_publication=pub, is_inactive=inactive
    )


def test_retry_when_schedule_has_slots_and_model_returned_none():
    assert _ok(subs=[]) is True
    assert _ok(subs=None) is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"subs": [{"name_ja": "x"}]},                                   # model already returned some
        {"event": _event(source_name="ks_cinema")},                     # not whitelisted
        {"event": _event(parent_event_id="p")},                         # sub-event itself
        {"event": _event(raw_title="台湾語映画特集 イベントレポート")},  # report article
        {"pub": True},
        {"inactive": True},
        {"raw": "12月2日\n10:00『花様年華』\n14:40『花様年華』\n18:00『花様年華』"},  # single film
        {"raw": "12月2日\n10:00『A』\n14:00『B』"},                    # only 2 slots
    ],
)
def test_retry_not_triggered(kwargs):
    assert _ok(**kwargs) is False


def test_hint_states_slot_count_and_series_rule():
    hint = _sub_event_retry_hint(11)
    assert "11 time slots" in hint and "NOT the single-film" in hint


# ── _annotate_one max_tokens ────────────────────────────────────────────────

class _FakeClient:
    def __init__(self):
        self.calls = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = types.SimpleNamespace(content=json.dumps({"sub_events": []}))
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=None)


def test_annotate_one_default_and_custom_max_tokens():
    c = _FakeClient()
    _annotate_one(c, "t", "d")
    _annotate_one(c, "t", "d", "hint", max_tokens=8000)
    assert [k["max_tokens"] for k in c.calls] == [4000, 8000]
    assert c.calls[1]["messages"][0]["content"].endswith("hint")
