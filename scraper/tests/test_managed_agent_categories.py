"""Social account rows must stay out of auto-research and auto-generate.

Spec social-sources D1 (plan-critique-1 F5): research_sources rows with
agent_category facebook_page / x_account are account lists read by a dedicated
scraper. If auto_research assessed them it would demote them to not-viable;
if generate picked them up it would spend LLM budget on a scraper that cannot
work. No network, no database: the Supabase client is a fake.
"""
from __future__ import annotations

import pytest

from auto_scraper import auto_research, generate
from research_exclusions import (
    MANAGED_AGENT_CATEGORIES,
    UNMANAGED_ROWS_FILTER,
    managed_reason,
)
from social.models import AGENT_CATEGORY_TO_PLATFORM


def test_managed_categories_match_the_social_scraper():
    # One list decides what the social scraper reads and what automation skips.
    assert set(MANAGED_AGENT_CATEGORIES) == set(AGENT_CATEGORY_TO_PLATFORM)


def test_managed_reason():
    assert managed_reason({"agent_category": "facebook_page"})
    assert managed_reason({"agent_category": "x_account"})
    assert managed_reason({"agent_category": "peatix_organizer"}) is None
    assert managed_reason({"agent_category": None}) is None
    assert managed_reason({}) is None and managed_reason(None) is None


def test_filter_keeps_rows_without_a_category():
    # ``not.in`` alone would drop NULL agent_category rows — most of the table.
    assert UNMANAGED_ROWS_FILTER == "agent_category.is.null,agent_category.not.in.(facebook_page,x_account)"


@pytest.mark.parametrize("category", MANAGED_AGENT_CATEGORIES)
def test_auto_research_refuses_account_rows(category):
    row = {"status": "candidate", "url_verified": True, "url": "https://x.com/a_b", "agent_category": category}
    with pytest.raises(auto_research.AssessError) as err:
        auto_research._check_eligibility(row)
    assert err.value.status == "ineligible" and category in err.value.message
    auto_research._check_eligibility({**row, "agent_category": None, "url": "https://example.org/events"})


@pytest.mark.parametrize("category", MANAGED_AGENT_CATEGORIES)
def test_generate_refuses_account_rows(category):
    row = {"status": "researched", "url_verified": True, "url": "https://x.com/a_b", "agent_category": category}
    with pytest.raises(generate.GenerateError) as err:
        generate._check_eligibility(row)
    assert category in err.value.message


class _Query:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self._log.append((name, args))
            return self
        return call

    def execute(self):
        return type("Result", (), {"data": list(self._rows)})()


class _Client:
    def __init__(self, rows):
        self.rows, self.log = rows, []

    def table(self, name):
        self.log.append(("table", (name,)))
        return _Query(self.rows, self.log)


ROWS = [
    {"id": 1, "status": "candidate", "url": "https://example.org/events", "agent_category": None},
    {"id": 2, "status": "candidate", "url": "https://www.facebook.com/page.c", "agent_category": "facebook_page"},
    {"id": 3, "status": "candidate", "url": "https://x.com/a_b", "agent_category": "x_account"},
]


def test_auto_research_batch_excludes_account_rows_in_query_and_in_code(monkeypatch):
    processed: list[int] = []
    monkeypatch.setattr(auto_research, "run", lambda opts, sb=None: processed.append(opts.source_id) or 1)
    client = _Client(ROWS)   # a fake that ignores filters, as if the query filter were missing
    auto_research.run_batch(auto_research.BatchOptions(dry_run=True), sb=client)
    assert ("or_", (UNMANAGED_ROWS_FILTER,)) in client.log
    assert processed == [1]


def test_generate_batch_excludes_account_rows_in_query_and_in_code(monkeypatch):
    processed: list[int] = []
    monkeypatch.setattr(generate, "run", lambda opts, sb=None: processed.append(opts.source_id) or 1)
    rows = [{**r, "status": "researched", "url_verified": True, "scraping_feasibility": "easy"} for r in ROWS]
    client = _Client(rows)
    generate.run_batch(generate.BatchOptions(dry_run=True), sb=client)
    assert ("or_", (UNMANAGED_ROWS_FILTER,)) in client.log
    assert processed == [1]
