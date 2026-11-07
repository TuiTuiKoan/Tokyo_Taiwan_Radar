"""Offline coverage of PeatixScraper's DB organizer group path (issues #549, #572).

The group path only runs when ``_load_db_organizers()`` returns organizers, which
needs Supabase credentials. ``main.py --dry-run`` on CI has none, so it never reaches
the code that #556 fixed (cutoff compared against timezone-aware ``start_date``).
These tests replace the browser and the DB with fakes so the path runs offline.
"""
import contextlib
import logging
from datetime import datetime, timedelta, timezone

import pytest

from sources import peatix
from sources.base import Event
from sources.peatix import PeatixScraper

ORG = {"group_id": "11650910", "name": "Test Organizer", "categories": ["taiwan_japan"]}


class _FakePage:
    pass


class _FakeContext:
    def new_page(self):
        return _FakePage()


class _FakeBrowser:
    def new_context(self, **kwargs):
        return _FakeContext()

    def close(self):
        pass


class _FakeChromium:
    def launch(self, **kwargs):
        return _FakeBrowser()


class _FakePlaywright:
    chromium = _FakeChromium()


@contextlib.contextmanager
def _fake_sync_playwright():
    yield _FakePlaywright()


def _event(event_id: str, start_date: datetime | None) -> Event:
    return Event(
        source_name="peatix",
        source_id=event_id,
        source_url=f"https://peatix.com/event/{event_id}",
        original_language="ja",
        name_ja=f"event {event_id}",
        raw_title=f"event {event_id}",
        category=["lecture"],
        start_date=start_date,
    )


@pytest.fixture
def scraper(monkeypatch):
    """A PeatixScraper with the browser, sleeps and keyword search faked out."""
    monkeypatch.setattr(peatix, "sync_playwright", _fake_sync_playwright)
    monkeypatch.setattr(peatix.time, "sleep", lambda _s: None)
    monkeypatch.setattr(PeatixScraper, "_search_events", lambda self, page, keyword: [])
    return PeatixScraper()


def _wire_group(monkeypatch, events_by_url: dict[str, Event | None]):
    monkeypatch.setattr(PeatixScraper, "_load_db_organizers", lambda self: [ORG])
    monkeypatch.setattr(
        PeatixScraper,
        "_scrape_group_events",
        lambda self, page, group_id, cutoff: list(events_by_url),
    )
    monkeypatch.setattr(
        PeatixScraper, "_scrape_detail", lambda self, page, url: events_by_url[url]
    )


def test_group_path_handles_timezone_aware_start_dates(scraper, monkeypatch, caplog):
    """Regression for #549: aware start_date vs cutoff must not raise or drop the event."""
    now = datetime.now(timezone.utc)
    recent = _event("1", now + timedelta(days=10))
    old = _event("2", now - timedelta(days=peatix.DATE_LOOKBACK_DAYS + 30))
    _wire_group(
        monkeypatch,
        {recent.source_url: recent, old.source_url: old},
    )

    with caplog.at_level(logging.ERROR, logger="sources.peatix"):
        events = scraper.scrape()

    assert [e.source_id for e in events] == ["1"]
    assert events[0].category == ORG["categories"]  # organizer categories override
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_group_path_handles_naive_start_dates(scraper, monkeypatch, caplog):
    """A naive start_date is treated as UTC rather than raising."""
    naive_recent = _event("3", datetime.now() + timedelta(days=5))
    _wire_group(monkeypatch, {naive_recent.source_url: naive_recent})

    with caplog.at_level(logging.ERROR, logger="sources.peatix"):
        events = scraper.scrape()

    assert [e.source_id for e in events] == ["3"]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_group_path_skipped_without_db_organizers(scraper, monkeypatch):
    """No organizers (dry-run, DB unavailable) means the group scrape is never started."""
    monkeypatch.setattr(PeatixScraper, "_load_db_organizers", lambda self: [])

    def _must_not_run(self, page, group_id, cutoff):
        raise AssertionError("group path should not run without organizers")

    monkeypatch.setattr(PeatixScraper, "_scrape_group_events", _must_not_run)

    assert scraper.scrape() == []
