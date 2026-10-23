"""enrich_person_names only walks live events when no ids are given (#361)."""

from datetime import datetime, timezone

import annotator


class _Query:
    def __init__(self):
        self.calls = []

    def eq(self, *a):
        self.calls.append(("eq", a))
        return self

    def or_(self, *a):
        self.calls.append(("or_", a))
        return self


def test_restricts_to_active_and_not_long_ended():
    q = annotator._restrict_to_live_events(
        _Query(), now=datetime(2026, 10, 23, tzinfo=timezone.utc)
    )
    assert ("eq", ("is_active", True)) in q.calls
    assert (
        "or_",
        ("end_date.gte.2026-09-23T00:00:00+00:00,end_date.is.null",),
    ) in q.calls
