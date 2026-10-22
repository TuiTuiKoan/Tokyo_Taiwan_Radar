"""Single-source runs enrich only their own new events (#395)."""
import annotator
import main


def test_full_run_enriches_everything():
    assert main._enrichment_scope(None, None, ["a"]) is None


def test_single_source_run_is_scoped_to_new_events():
    assert main._enrichment_scope("mot", None, ["a", "b"]) == ["a", "b"]


def test_single_source_run_with_nothing_new_is_empty_not_full():
    assert main._enrichment_scope("mot", None, []) == []


def test_rescrape_ids_keep_the_full_pass():
    assert main._enrichment_scope("mot", ["mot_1"], []) is None
    assert main._enrichment_scope(None, ["mot_1"], []) is None


class FakeQuery:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args))
            return self
        return record

    def execute(self):
        class Res:
            data = []
        return Res()


class FakeSupabase:
    def __init__(self):
        self.query = FakeQuery()

    def table(self, name):
        return self.query


def test_enrich_movie_titles_restricts_to_event_ids(monkeypatch):
    sb = FakeSupabase()
    monkeypatch.setattr(annotator, "_get_supabase", lambda: sb)
    annotator.enrich_movie_titles(event_ids=["id-1", "id-2"])
    assert ("in_", ("id", ["id-1", "id-2"])) in sb.query.calls


def test_enrich_movie_titles_without_event_ids_is_unrestricted(monkeypatch):
    sb = FakeSupabase()
    monkeypatch.setattr(annotator, "_get_supabase", lambda: sb)
    annotator.enrich_movie_titles()
    assert not [c for c in sb.query.calls if c[0] == "in_"]
