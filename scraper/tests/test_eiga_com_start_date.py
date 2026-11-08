"""Issue #537: per-theater start_date for eiga_com, and the DB extend rule that
keeps it from sliding forward with the weekly schedule window."""

from datetime import datetime, timezone

from database import _build_movie_extend_row, _normalize_legacy_jst_midnight
from sources.base import Event
from sources.eiga_com import _theater_start_date


def _d(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


# ── scraper: _theater_start_date ──────────────────────────────────────────


def test_release_week_theater_keeps_publication_date():
    # First-run theater observed in the release week → 劇場公開日
    assert _theater_start_date(_d(2026, 10, 10), _d(2026, 10, 10)) == _d(2026, 10, 10)
    assert _theater_start_date(_d(2026, 10, 10), _d(2026, 10, 16)) == _d(2026, 10, 10)


def test_later_run_theater_uses_first_screening():
    # シアター・イメージフォーラム: revival starts 11/7, 公開日 in October
    assert _theater_start_date(_d(2026, 10, 10), _d(2026, 11, 7)) == _d(2026, 11, 7)


def test_missing_publication_date_uses_first_screening():
    assert _theater_start_date(None, _d(2026, 11, 7)) == _d(2026, 11, 7)


# ── database: legacy JST-midnight normalization ───────────────────────────


def test_normalize_legacy_jst_midnight():
    assert _normalize_legacy_jst_midnight("2026-11-11T15:00:00+00:00") == "2026-11-12T00:00:00+00:00"
    assert _normalize_legacy_jst_midnight("2026-11-11T15:00:00Z") == "2026-11-12T00:00:00+00:00"
    assert _normalize_legacy_jst_midnight("2026-11-12T00:00:00+00:00") == "2026-11-12T00:00:00+00:00"
    assert _normalize_legacy_jst_midnight(None) is None


# ── database: movie extend rule for eiga_com ──────────────────────────────


def _event(source_name, start, end, desc="desc"):
    return Event(
        source_name=source_name,
        source_id="eiga_com_87201_3018",
        source_url="https://eiga.com/movie-area/87201/13/130301/",
        original_language="ja",
        raw_title="t",
        raw_description=desc,
        start_date=start,
        end_date=end,
    )


def _state(start, end, desc="desc"):
    return {"start_date": start, "end_date": end, "raw_description": desc, "business_hours": None}


def test_eiga_start_does_not_slide_forward_with_weekly_window():
    # Week 1 stored 10/10; week 3 scrape sees first screening 10/24 → start must stay 10/10
    ev = _event("eiga_com", _d(2026, 10, 24), _d(2026, 10, 30))
    row = _build_movie_extend_row(ev, _state("2026-10-10T00:00:00+00:00", "2026-10-23T00:00:00+00:00"))
    assert row["start_date"] == "2026-10-10T00:00:00+00:00"
    assert row["end_date"] == "2026-10-30T00:00:00+00:00"


def test_eiga_start_can_move_earlier():
    ev = _event("eiga_com", _d(2026, 10, 10), _d(2026, 10, 16))
    row = _build_movie_extend_row(ev, _state("2026-10-12T00:00:00+00:00", "2026-10-16T00:00:00+00:00"))
    assert row["start_date"] == "2026-10-10T00:00:00+00:00"


def test_eiga_legacy_jst_values_are_corrected_not_kept():
    # Row written before #547: start 10/15 and end 11/12 stored as previous-day 15:00Z
    ev = _event("eiga_com", _d(2026, 10, 15), _d(2026, 11, 13))
    row = _build_movie_extend_row(ev, _state("2026-10-14T15:00:00+00:00", "2026-11-11T15:00:00+00:00"))
    assert row["start_date"] == "2026-10-15T00:00:00+00:00"
    assert row["end_date"] == "2026-11-13T00:00:00+00:00"


def test_eiga_end_never_shrinks():
    ev = _event("eiga_com", _d(2026, 10, 10), _d(2026, 11, 5))
    row = _build_movie_extend_row(ev, _state("2026-10-10T00:00:00+00:00", "2026-11-11T15:00:00+00:00"))
    assert row["end_date"] == "2026-11-12T00:00:00+00:00"


def test_eiga_no_change_returns_none():
    ev = _event("eiga_com", _d(2026, 10, 10), _d(2026, 10, 16))
    assert _build_movie_extend_row(ev, _state("2026-10-10T00:00:00+00:00", "2026-10-16T00:00:00+00:00")) is None


def test_other_movie_sources_keep_prefer_new_start():
    # Unchanged behavior for non-eiga sources: current scrape's start wins
    ev = _event("kyoto_cinema", _d(2026, 10, 24), _d(2026, 10, 30))
    row = _build_movie_extend_row(ev, _state("2026-10-10T00:00:00+00:00", "2026-10-23T00:00:00+00:00"))
    assert row["start_date"] == "2026-10-24T00:00:00+00:00"
