"""Taxonomy file ↔ annotator contract (scraper/taxonomy.md is the single source)."""

import re

import pytest

import annotator
from annotator import (
    SYSTEM_PROMPT,
    TAXONOMY_PATH,
    VALID_CATEGORIES,
    _inject_keyword_categories,
    _queue_missing_category_report,
    _validate_categories,
    load_taxonomy_prompt,
)
from classifier import classify

_DEF_RE = re.compile(r'^\s*- "([a-z_]+)"(?: \([^)]*\))? =', re.MULTILINE)


def test_every_valid_category_has_exactly_one_definition():
    defined = _DEF_RE.findall(load_taxonomy_prompt())
    dupes = sorted({c for c in defined if defined.count(c) > 1})
    assert not dupes, f"duplicate definitions: {dupes}"
    assert set(defined) == set(VALID_CATEGORIES), (
        f"missing: {sorted(set(VALID_CATEGORIES) - set(defined))}, "
        f"unknown: {sorted(set(defined) - set(VALID_CATEGORIES))}"
    )


def test_system_prompt_embeds_taxonomy_and_full_slug_list():
    assert "<<CATEGORY_TAXONOMY>>" not in SYSTEM_PROMPT
    assert load_taxonomy_prompt() in SYSTEM_PROMPT
    assert "2. Categories must be from this list: " + ", ".join(VALID_CATEGORIES) in SYSTEM_PROMPT
    # Rule 3 must still follow the category block.
    assert SYSTEM_PROMPT.index("2. Categories must") < SYSTEM_PROMPT.index("3. Translate")


def test_schema_example_does_not_prime_senses():
    assert '"category": ["senses"]' not in SYSTEM_PROMPT


def test_taxonomy_markers_required(tmp_path):
    bad = tmp_path / "taxonomy.md"
    bad.write_text("no markers here", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_taxonomy_prompt(bad)


def test_taxonomy_file_is_next_to_annotator():
    assert TAXONOMY_PATH.name == "taxonomy.md"
    assert TAXONOMY_PATH.parent.name == "scraper"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ([], []),
        (["nonsense"], []),
        (None, []),
        (["movie", "nonsense", "movie", "lecture"], ["movie", "lecture"]),
    ],
)
def test_validate_categories_has_no_senses_fallback(raw, expected):
    assert _validate_categories(raw) == expected


@pytest.mark.parametrize(
    "text",
    ["湾生をめぐる記録映画", "国民党政権下の台湾", "二二八事件の記憶", "白色テロと文学"],
)
def test_political_identity_history_injects_history(text):
    assert "history" in _inject_keyword_categories([], text)


def test_election_injects_geopolitics():
    assert "geopolitics" in _inject_keyword_categories([], "台湾総統選の行方を読む")


def test_keyword_classifier_has_no_fallback_and_art_is_not_senses():
    assert classify("xyz", None, None, None, None, None) == []
    cats = classify("台湾写真展", None, None, None, None, None)
    assert "senses" not in cats and "art" in cats
    assert "senses" in classify("台湾アイデンティティを考える", None, None, None, None, None)


class _FakeQuery:
    def __init__(self, store, pending_rows):
        self.store = store
        self.pending_rows = pending_rows

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def contains(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self.store.append(row)
        return self

    def execute(self):
        return type("R", (), {"data": self.pending_rows})()


class _FakeSB:
    def __init__(self, pending_rows=None):
        self.inserted = []
        self.pending_rows = pending_rows or []

    def table(self, name):
        assert name == "event_reports"
        return _FakeQuery(self.inserted, self.pending_rows)


def test_missing_category_queues_wrong_category_report():
    sb = _FakeSB()
    _queue_missing_category_report(sb, {"id": "abcdef12-0000"}, dry_run=False)
    assert len(sb.inserted) == 1
    row = sb.inserted[0]
    assert row["report_types"] == ["wrongCategory"]
    assert row["status"] == "pending"
    assert row["event_id"] == "abcdef12-0000"


def test_missing_category_report_is_deduplicated():
    sb = _FakeSB(pending_rows=[{"id": "existing"}])
    _queue_missing_category_report(sb, {"id": "abcdef12-0000"}, dry_run=False)
    assert sb.inserted == []


def test_missing_category_report_dry_run_writes_nothing():
    sb = _FakeSB()
    _queue_missing_category_report(sb, {"id": "abcdef12-0000"}, dry_run=True)
    assert sb.inserted == []


def test_report_type_matches_web_user_report_type():
    # The admin UI already knows how to resolve "wrongCategory" reports.
    assert annotator.MISSING_CATEGORY_REPORT_TYPE == "wrongCategory"
