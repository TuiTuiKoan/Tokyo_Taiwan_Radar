"""enrich_poster sends each image to the model once and counts every outcome (#317)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import enrich_poster
import llm_cache


class _CacheStore:
    """In-memory llm_cache for llm_cache.seen / record."""

    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def seen(self, _sb, step, keys):
        return {k for k in keys if (step, k) in self.rows}

    def record(self, _sb, step, key, outcome, result=None):
        self.rows[(step, key)] = {"outcome": outcome, "result": result}


@pytest.fixture
def harness(monkeypatch):
    store = _CacheStore()
    calls: list[dict] = []
    state = {"extract": {"confidence": 0.95, "venue": "Tokyo Hall"}, "outcome": "applied"}

    events = [
        {"id": "aaaaaaaa-1", "name_ja": "A", "image_url": "https://x.test/a.jpg"},
        {"id": "bbbbbbbb-2", "name_ja": "B", "image_url": "https://x.test/b.jpg"},
    ]
    monkeypatch.setattr(enrich_poster, "_get_supabase", lambda: object())
    monkeypatch.setattr(enrich_poster, "_get_openai", lambda: object())
    monkeypatch.setattr(enrich_poster, "_fetch_candidates", lambda *_a, **_k: [dict(e) for e in events])
    monkeypatch.setattr(enrich_poster, "_download_image", lambda url: url.encode())

    def fake_extract(_client, _bytes, url, model, detail):
        calls.append({"url": url, "model": model, "detail": detail})
        return state["extract"]

    monkeypatch.setattr(enrich_poster, "_extract_from_poster", fake_extract)
    monkeypatch.setattr(enrich_poster, "_get_fc_protected_fields", lambda *_a: set())
    monkeypatch.setattr(enrich_poster, "_apply", lambda *_a, **_k: state["outcome"])
    monkeypatch.setattr(llm_cache, "seen", store.seen)
    monkeypatch.setattr(llm_cache, "record", store.record)
    return SimpleNamespace(store=store, calls=calls, state=state)


def test_an_image_is_sent_once_across_runs(harness):
    first = enrich_poster.run()
    second = enrich_poster.run()
    assert first["sent"] == 2 and first["applied"] == 2
    assert second["sent"] == 0 and second["already_processed"] == 2
    assert len(harness.calls) == 2
    row = harness.store.rows[(enrich_poster.CACHE_STEP, next(iter(harness.store.rows))[1])]
    assert row["outcome"] == "applied" and row["result"]["model"] == "gpt-4o"


def test_low_confidence_and_no_new_fields_are_counted_and_recorded(harness):
    harness.state["outcome"] = "low_confidence"
    counts = enrich_poster.run()
    assert counts["low_confidence"] == 2 and counts["applied"] == 0
    assert {r["outcome"] for r in harness.store.rows.values()} == {"low_confidence"}
    assert enrich_poster.run()["sent"] == 0


def test_dry_run_records_nothing_so_it_can_be_repeated(harness):
    harness.state["outcome"] = "would_apply"
    assert enrich_poster.run(dry_run=True)["would_apply"] == 2
    assert harness.store.rows == {}
    assert enrich_poster.run(dry_run=True)["sent"] == 2


def test_a_failed_call_is_not_recorded_and_is_retried(harness):
    harness.state["extract"] = None
    assert enrich_poster.run()["failed"] == 2
    assert harness.store.rows == {}
    harness.state["extract"] = {"confidence": 0.95}
    assert enrich_poster.run()["sent"] == 2


def test_resend_and_model_flags_reach_the_call(harness):
    enrich_poster.run()
    counts = enrich_poster.run(resend=True, model="gpt-4o-mini", detail="low")
    assert counts["sent"] == 2
    assert harness.calls[-1] == {"url": "https://x.test/b.jpg", "model": "gpt-4o-mini", "detail": "low"}


def test_extract_asks_for_json_with_the_given_model_and_detail():
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"confidence": 0.9}'))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    out = enrich_poster._extract_from_poster(client, b"img", "https://x.test/p.png", model="gpt-4o-mini", detail="low")
    assert out == {"confidence": 0.9}
    assert seen["response_format"] == {"type": "json_object"}
    assert seen["model"] == "gpt-4o-mini"
    assert seen["messages"][1]["content"][0]["image_url"]["detail"] == "low"


class _Rows:
    def __init__(self, data, log):
        self._data, self._log, self._keys = data, log, []

    def select(self, _c):
        return self

    def eq(self, _c, _v):
        return self

    def in_(self, _c, keys):
        self._keys = keys
        self._log.append(len(keys))
        return self

    def execute(self):
        return SimpleNamespace(data=[{"subject_key": k} for k in self._keys if k in self._data])


def test_seen_reads_in_chunks():
    log: list[int] = []
    known = {f"k{i}" for i in range(0, 250, 2)}
    sb = SimpleNamespace(table=lambda _n: _Rows(known, log))
    found = llm_cache.seen(sb, "poster_ocr", [f"k{i}" for i in range(250)])
    assert log == [100, 100, 50]
    assert found == known


def test_seen_raises_when_the_table_cannot_be_read():
    class Broken:
        def table(self, _n):
            raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        llm_cache.seen(Broken(), "poster_ocr", ["k"])
