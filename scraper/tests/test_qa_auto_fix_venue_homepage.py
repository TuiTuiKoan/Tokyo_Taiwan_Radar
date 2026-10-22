from types import SimpleNamespace

import annotator
import qa_auto_fix
import venue_registry

EVENT = {
    "id": "ev-1",
    "source_url": "https://example.com/event/1",
    "official_url": None,
    "organizer_url": None,
    "location_name": "公式館",
    "location_address": "東京都港区1-1",
    "location_url": "https://example.com/event/1",
}


class _Query:
    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=dict(EVENT))


class _Client:
    def table(self, name):
        assert name == "events"
        return _Query()


def _run(monkeypatch, registry_row, ddg_result):
    writes, notes, ddg_calls = [], [], []
    monkeypatch.setattr(venue_registry, "lookup_venue_for_location", lambda name: (registry_row, False))

    def fake_ddg(name, address=None):
        ddg_calls.append(name)
        return ddg_result

    monkeypatch.setattr(annotator, "_search_venue_homepage", fake_ddg)
    monkeypatch.setattr(qa_auto_fix, "unlock_and_write", lambda sb, **kw: writes.append(kw) or True)
    monkeypatch.setattr(qa_auto_fix, "_confirm_report", lambda *a, **kw: None)
    monkeypatch.setattr(qa_auto_fix, "_append_report_note", lambda sb, rid, note, **kw: notes.append(note))
    ok = qa_auto_fix.handle_location_url_is_event_url(_Client(), "ev-1", {"id": "r-1"}, dry_run=True)
    return ok, writes, notes, ddg_calls


def test_registry_homepage_wins_without_web_search(monkeypatch):
    ok, writes, _, ddg_calls = _run(monkeypatch, {"homepage": "https://venue.example.jp/"}, "https://ddg.example")
    assert ok
    assert ddg_calls == []
    assert writes[0]["new_value"] == "https://venue.example.jp"
    assert writes[0]["model_used"] == "rule:venue_registry.homepage"


def test_falls_back_to_duckduckgo_when_registry_has_no_homepage(monkeypatch):
    ok, writes, _, ddg_calls = _run(monkeypatch, None, "https://found.example.jp")
    assert ok
    assert ddg_calls == ["公式館"]
    assert writes[0]["model_used"] == "rule:_search_venue_homepage"


def test_leaves_report_pending_when_nothing_is_found(monkeypatch):
    ok, writes, notes, _ = _run(monkeypatch, {"homepage": None}, None)
    assert not ok
    assert writes == []
    assert notes == ["venue homepage search failed for 公式館"]
