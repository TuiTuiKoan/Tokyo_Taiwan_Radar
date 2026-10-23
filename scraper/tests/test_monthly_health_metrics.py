"""A2 / A3 denominator fixes (#324) and human-only A1 / A4 (#373) in monthly_health_check."""

from monthly_health_check import (
    _aggregate_first_pass,
    _aggregate_recurrence,
    _aggregate_repair_latency,
    _fetch_human_corrections,
    _fields_per_event,
    _parse_annotator_notes,
    a3_scope_note,
    script_corrections_note,
)


# ─── A2 ───────────────────────────────────────────────────────────────────────

def test_parse_notes_prefers_annotated_over_total():
    notes = "re_annotate_all=False, total=40, annotated=33, field_protect_hits=174, dry_run=False"
    assert _parse_annotator_notes(notes) == (174, 33)


def test_parse_notes_falls_back_to_total_for_historical_rows():
    notes = "re_annotate_all=False, fix_reviewed=False, total=29, field_protect_hits=179"
    assert _parse_annotator_notes(notes) == (179, 29)


def test_parse_notes_does_not_read_re_annotate_flag_as_denominator():
    assert _parse_annotator_notes("re_annotated=7, field_protect_hits=3") == (3, 0)


def test_fields_per_event_is_an_average_not_a_percentage():
    # 2026-09 monthly review: 3515 protected fields over 775 annotated events.
    assert _fields_per_event(3515, 775) == 4.54


def test_fields_per_event_unavailable_without_denominator_or_on_fetch_failure():
    assert _fields_per_event(10, 0) is None
    assert _fields_per_event(-1, 50) is None


# ─── A3 ───────────────────────────────────────────────────────────────────────

def _events(source: str, n: int, created_at: str = "2026-10-01T00:00:00+00:00") -> list[dict]:
    return [{"id": f"{source}-{i}", "source_name": source, "created_at": created_at} for i in range(n)]


def test_system_reports_do_not_count_as_reader_reports():
    events = _events("ndl_opensearch", 40)
    reports = [
        {"event_id": e["id"], "created_at": "2026-10-01T03:00:00+00:00", "locale": None}
        for e in events
    ]
    a3 = _aggregate_first_pass(events, reports)
    assert a3["sources"] == [
        {"source_name": "ndl_opensearch", "total_new": 40, "reported_within_24h": 0, "error_rate": 0.0}
    ]
    assert a3["human_reported_24h"] == 0
    assert a3["system_reported_24h"] == 40


def test_reader_report_inside_window_counts_once_per_event():
    events = _events("kokuchpro", 5)
    reports = [
        {"event_id": "kokuchpro-0", "created_at": "2026-10-01T05:00:00Z", "locale": "ja"},
        {"event_id": "kokuchpro-0", "created_at": "2026-10-01T06:00:00Z", "locale": "zh"},
        {"event_id": "kokuchpro-1", "created_at": "2026-10-02T00:00:00Z", "locale": "ja"},  # exactly 24h: outside
        {"event_id": "kokuchpro-2", "created_at": "2026-09-30T23:00:00Z", "locale": "ja"},  # before creation
    ]
    a3 = _aggregate_first_pass(events, reports)
    assert a3["sources"][0]["reported_within_24h"] == 1
    assert a3["sources"][0]["error_rate"] == 0.2
    assert a3["human_reported_24h"] == 1


def test_small_sources_are_left_out_of_the_ranking():
    events = _events("nagano_aioiza", 1) + _events("peatix", 6)
    reports = [
        {"event_id": "nagano_aioiza-0", "created_at": "2026-10-01T01:00:00Z", "locale": "ja"},
        {"event_id": "peatix-0", "created_at": "2026-10-01T01:00:00Z", "locale": "ja"},
    ]
    a3 = _aggregate_first_pass(events, reports)
    assert [s["source_name"] for s in a3["sources"]] == ["peatix"]
    # The small source's reader report still counts in the overall total.
    assert a3["human_reported_24h"] == 2


def test_ranking_breaks_ties_by_volume():
    events = _events("a_src", 5) + _events("b_src", 10)
    a3 = _aggregate_first_pass(events, [])
    assert [s["source_name"] for s in a3["sources"]] == ["b_src", "a_src"]


def test_scope_note_states_what_was_excluded():
    note = a3_scope_note({"min_new_events": 5, "human_reported_24h": 2, "system_reported_24h": 40})
    assert "locale" in note and "≥ 5" in note and "40" in note


# ─── A1 / A4: human corrections only (#373) ──────────────────────────────────

class _Resp:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _Query:
    """Records filters; serves rows by whether corrected_by was required to be set."""

    def __init__(self, rows: list[dict], log: list):
        self.rows, self.log = rows, log
        self.filters: list[tuple] = []
        self.head = False
        self.not_ = self

    def select(self, columns, count=None, head=False):
        self.head = head
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def lt(self, col, val):
        self.filters.append(("lt", col, val))
        return self

    def is_(self, col, val):
        # `.not_.is_` and `.is_` share this method; head=True marks the count query.
        self.filters.append(("is_null" if self.head else "not_null", col))
        return self

    def execute(self):
        self.log.append(self.filters)
        human = [r for r in self.rows if r.get("corrected_by")]
        if self.head:
            return _Resp(count=len(self.rows) - len(human))
        return _Resp(data=human)


class _FakeSb:
    def __init__(self, rows):
        self.rows, self.log = rows, []

    def table(self, name):
        assert name == "field_corrections"
        return _Query(self.rows, self.log)


def test_script_written_corrections_are_counted_not_ranked():
    # 2026-09: kokuchpro/location_name had 77 script locks and no human edit.
    rows = [{"event_id": f"k{i}", "field_name": "location_name", "corrected_by": None} for i in range(77)]
    rows += [{"event_id": "p1", "field_name": "start_date", "corrected_by": "admin-uuid"}]
    sb = _FakeSb(rows)
    human, script = _fetch_human_corrections(sb, "event_id,field_name,created_at", "2026-09-01", "2026-10-01")
    assert [r["event_id"] for r in human] == ["p1"]
    assert script == 77
    row_filters, count_filters = sb.log
    assert ("not_null", "corrected_by") in row_filters and ("lt", "created_at", "2026-10-01") in row_filters
    assert ("is_null", "corrected_by") in count_filters


def test_report_id_alone_does_not_make_a_correction_human():
    rows = [{"event_id": "e1", "field_name": "location_name", "corrected_by": None, "report_id": "r1"}]
    human, script = _fetch_human_corrections(_FakeSb(rows), "event_id", "2026-09-01")
    assert human == [] and script == 1


def test_recurrence_needs_two_corrections_of_the_same_source_and_field():
    rows = [
        {"event_id": "a", "field_name": "location_name"},
        {"event_id": "b", "field_name": "location_name"},
        {"event_id": "c", "field_name": "start_date"},
    ]
    out = _aggregate_recurrence(rows, {"a": "peatix", "b": "peatix", "c": "peatix"})
    assert out == {
        "recurrence_pairs": 1,
        "top_pairs": [{"source_name": "peatix", "field_name": "location_name", "count": 2}],
    }


def test_repair_latency_is_median_days_per_source():
    rows = [
        {"event_id": "a", "created_at": "2026-09-03T00:00:00Z"},
        {"event_id": "b", "created_at": "2026-09-11T00:00:00Z"},
        {"event_id": "missing", "created_at": "2026-09-11T00:00:00Z"},
    ]
    created = {"a": "2026-09-01T00:00:00+00:00", "b": "2026-09-01T00:00:00+00:00"}
    out = _aggregate_repair_latency(rows, created, {"a": "peatix", "b": "peatix"})
    assert out == {"sources": [{"source_name": "peatix", "n_corrections": 2, "median_days": 6.0}]}


def test_script_note_reports_the_left_out_count():
    assert "698" in script_corrections_note({"script_corrections": 698})
    assert "失敗" in script_corrections_note({"script_corrections": None})
