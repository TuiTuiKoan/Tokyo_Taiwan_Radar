from datetime import datetime, timedelta, timezone

from sources.peatix import _is_before_cutoff


def test_aware_start_date_vs_aware_cutoff_does_not_raise():
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    assert _is_before_cutoff(cutoff - timedelta(days=1), cutoff) is True
    assert _is_before_cutoff(cutoff + timedelta(days=1), cutoff) is False


def test_naive_values_are_treated_as_utc():
    cutoff = datetime.now() - timedelta(days=30)  # naive
    aware_old = datetime.now(timezone.utc) - timedelta(days=60)
    aware_new = datetime.now(timezone.utc)
    assert _is_before_cutoff(aware_old, cutoff) is True
    assert _is_before_cutoff(aware_new, cutoff) is False
    assert _is_before_cutoff(datetime.now() - timedelta(days=60), cutoff) is True
