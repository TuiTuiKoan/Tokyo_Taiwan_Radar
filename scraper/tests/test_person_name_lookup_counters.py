"""Milestone 0 of spec people-ground-truth: the lookup counters.

The counters only observe; none of these tests may change what the lookup returns.
"""

import pytest
import requests

import person_name_lookup as pnl


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clean_state():
    pnl.reset_lookup_counters()
    pnl._person_cache.clear()
    pnl._movie_cache.clear()
    yield
    pnl.reset_lookup_counters()
    pnl._person_cache.clear()
    pnl._movie_cache.clear()


def test_counters_start_at_zero_with_all_reserved_names():
    snapshot = pnl.lookup_counters()
    assert set(snapshot) == {
        "external_request", "external_error", "memory_hit", "verified_hit",
        "db_hit", "cache_hit", "cache_negative_hit", "offline_miss",
    }
    assert not any(snapshot.values())


def test_successful_request_counts_once_and_returns_the_response(monkeypatch):
    resp = _FakeResponse(200)
    monkeypatch.setattr(requests, "get", lambda url, **kw: resp)

    assert pnl._counted_get("https://example.test/") is resp
    assert pnl.lookup_counters()["external_request"] == 1
    assert pnl.lookup_counters()["external_error"] == 0


def test_http_error_status_counts_as_error_but_is_still_returned(monkeypatch):
    resp = _FakeResponse(429)
    monkeypatch.setattr(requests, "get", lambda url, **kw: resp)

    assert pnl._counted_get("https://example.test/") is resp
    counters = pnl.lookup_counters()
    assert counters["external_request"] == 1
    assert counters["external_error"] == 1


def test_exception_counts_as_error_and_still_propagates(monkeypatch):
    def boom(url, **kw):
        raise requests.Timeout("slow")

    monkeypatch.setattr(requests, "get", boom)

    with pytest.raises(requests.Timeout):
        pnl._counted_get("https://example.test/")
    counters = pnl.lookup_counters()
    assert counters["external_request"] == 1
    assert counters["external_error"] == 1


def test_session_is_used_when_given(monkeypatch):
    seen = []

    class FakeSession:
        def get(self, url, **kw):
            seen.append((url, kw))
            return _FakeResponse(200)

    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("plain requests used"))

    pnl._counted_get("https://example.test/", session=FakeSession(), timeout=15)
    assert seen == [("https://example.test/", {"timeout": 15})]


def test_wikipedia_lookup_goes_through_the_counter(monkeypatch):
    monkeypatch.setattr(
        requests, "get",
        lambda url, **kw: _FakeResponse(200, {"query": {"search": []}}),
    )

    assert pnl._lookup_zh_via_wikipedia("Someone Unknown") is None
    assert pnl.lookup_counters()["external_request"] == 1


def test_memory_cache_hits_are_counted_and_do_not_send_requests(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("network used"))
    pnl._person_cache["https://eiga.com/person/1/"] = ("Edward Yang", "楊德昌")
    pnl._person_cache["single:エドワード・ヤン"] = ("Edward Yang", "楊德昌")
    pnl._movie_cache["赤い糸"] = {}

    assert pnl._resolve_person("https://eiga.com/person/1/") == ("Edward Yang", "楊德昌")
    assert pnl.lookup_single_person("エドワード・ヤン").name_zh == "楊德昌"
    assert pnl.lookup_person_names("赤い糸") == {}

    counters = pnl.lookup_counters()
    assert counters["memory_hit"] == 3
    assert counters["external_request"] == 0


def test_log_skips_untouched_runs_and_lists_every_counter_otherwise(caplog):
    with caplog.at_level("INFO", logger=pnl.logger.name):
        pnl.log_lookup_counters()
    assert caplog.records == []

    pnl._count("external_request")
    with caplog.at_level("INFO", logger=pnl.logger.name):
        pnl.log_lookup_counters()
    message = caplog.records[-1].getMessage()
    assert "external_request=1" in message
    for name in pnl._COUNTER_NAMES:
        assert f"{name}=" in message
