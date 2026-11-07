from datetime import datetime, timezone

from sources.eiga_com import EigaComScraper, _parse_date, _yyyymmdd_to_date


def test_yyyymmdd_to_date_is_utc_midnight():
    assert _yyyymmdd_to_date("20261113") == datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert _yyyymmdd_to_date("20261113").isoformat() == "2026-11-13T00:00:00+00:00"


def test_parse_date_is_utc_midnight():
    assert _parse_date("2026年11月7日").isoformat() == "2026-11-07T00:00:00+00:00"


def test_today_is_utc_midnight_and_comparable():
    today = EigaComScraper()._today
    assert today.utcoffset().total_seconds() == 0
    assert (today.hour, today.minute) == (0, 0)
    assert _parse_date("2026年11月7日") <= datetime(2027, 1, 1, tzinfo=timezone.utc)
