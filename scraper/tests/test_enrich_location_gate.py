"""llm_cache.seen can ignore old marks, so enrich_location retries after 30 days (#360)."""

import llm_cache


class _Q:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def select(self, *a):
        return self

    def eq(self, *a):
        self.log.append(("eq", a))
        return self

    def in_(self, *a):
        return self

    def gte(self, *a):
        self.log.append(("gte", a))
        return self

    def execute(self):
        return type("R", (), {"data": self.rows})()


class _SB:
    def __init__(self, rows):
        self.rows, self.log = rows, []

    def table(self, name):
        assert name == "llm_cache"
        return _Q(self.rows, self.log)


def test_seen_max_age_adds_cutoff_filter():
    sb = _SB([{"subject_key": "a"}])
    assert llm_cache.seen(sb, "location_extract", ["a", "b"], max_age_days=30) == {"a"}
    assert any(c[0] == "gte" and c[1][0] == "attempted_at" for c in sb.log)


def test_seen_without_max_age_has_no_cutoff():
    sb = _SB([])
    llm_cache.seen(sb, "location_extract", ["a"])
    assert not any(c[0] == "gte" for c in sb.log)
