"""cinemaclair reads the weekly schedule image once and reuses the answer (#321)."""

from sources import cinemaclair as cc


def test_cache_key_depends_on_image_and_titles_not_their_order():
    a = cc._ocr_cache_key("https://x/img/i1.jpg", ["B", "A"])
    assert a == cc._ocr_cache_key("https://x/img/i1.jpg", ["A", "B"])
    assert a != cc._ocr_cache_key("https://x/img/i2.jpg", ["A", "B"])
    assert a != cc._ocr_cache_key("https://x/img/i1.jpg", ["A"])


def test_cached_answer_skips_the_model(monkeypatch):
    import llm_cache

    monkeypatch.setattr(cc, "_cache_client", lambda: object())
    monkeypatch.setattr(llm_cache, "fetch", lambda sb, step, key: {"showtimes": {"A": "10:00"}})
    monkeypatch.setattr(
        cc, "_ocr_schedule_showtimes_uncached",
        lambda *a: (_ for _ in ()).throw(AssertionError("model called")),
    )
    assert cc._ocr_schedule_showtimes("u", ["A"]) == {"A": "10:00"}


def test_miss_reads_once_and_records_success_but_not_failure(monkeypatch):
    import llm_cache

    recorded = []
    monkeypatch.setattr(cc, "_cache_client", lambda: object())
    monkeypatch.setattr(llm_cache, "fetch", lambda *a: None)
    monkeypatch.setattr(llm_cache, "record", lambda *a: recorded.append(a))

    monkeypatch.setattr(cc, "_ocr_schedule_showtimes_uncached", lambda *a: {"A": "10:00"})
    assert cc._ocr_schedule_showtimes("u", ["A"]) == {"A": "10:00"}
    assert len(recorded) == 1

    monkeypatch.setattr(cc, "_ocr_schedule_showtimes_uncached", lambda *a: None)
    assert cc._ocr_schedule_showtimes("u", ["A"]) == {}
    assert len(recorded) == 1
