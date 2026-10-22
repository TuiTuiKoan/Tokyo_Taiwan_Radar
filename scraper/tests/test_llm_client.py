import asyncio
import sys
from types import SimpleNamespace

import pytest

import llm_client


class _APIError(Exception):
    """Stand-in for openai.APIStatusError: classification only reads these attributes."""

    def __init__(self, status_code=None, code=None):
        super().__init__(f"status={status_code} code={code}")
        self.status_code = status_code
        self.code = code


class APITimeoutError(Exception):
    pass


@pytest.fixture(autouse=True)
def _fresh_stats():
    llm_client._reset_for_tests()
    yield
    llm_client._reset_for_tests()


def _client(behaviour):
    def create(**kwargs):
        if isinstance(behaviour, BaseException):
            raise behaviour
        return behaviour

    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        responses=SimpleNamespace(create=create),
        embeddings=SimpleNamespace(create=create),
    )
    return llm_client.LLMClient("enrich.test", sdk)


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (_APIError(404, "model_not_found"), "config"),
        (_APIError(401), "config"),
        (_APIError(403), "config"),
        (_APIError(429, "insufficient_quota"), "config"),
        (_APIError(429, "rate_limit_exceeded"), "transient"),
        (_APIError(400, "unsupported_parameter"), "config"),
        (_APIError(400, "context_length_exceeded"), "request"),
        (_APIError(503), "transient"),
        (APITimeoutError("slow"), "transient"),
        (ValueError("not from the SDK"), "other"),
    ],
)
def test_classify(exc, kind):
    assert llm_client.classify(exc) == kind


def test_retired_model_escapes_broad_except_blocks():
    llm = _client(_APIError(404, "model_not_found"))
    with pytest.raises(llm_client.LLMConfigError) as info:
        try:
            llm.chat.completions.create(model="gpt-4o-search-preview", messages=[])
        except Exception:  # the pattern most call sites use
            pytest.fail("LLMConfigError must not be an Exception")
    assert info.value.model == "gpt-4o-search-preview"
    assert info.value.status == 404
    assert "enrich.test" in str(info.value)


def test_transient_error_is_reraised_unchanged_and_counted():
    err = _APIError(429, "rate_limit_exceeded")
    llm = _client(err)
    with pytest.raises(_APIError) as info:
        llm.responses.create(model="gpt-4o-mini", input="x")
    assert info.value is err
    assert (llm_client.stats().calls, llm_client.stats().errors) == (1, 1)


def test_success_passes_the_response_through():
    resp = object()
    assert _client(resp).chat.completions.create(model="m", messages=[]) is resp
    assert (llm_client.stats().calls, llm_client.stats().errors) == (1, 0)


def test_async_client_classifies_the_same_way():
    async def create(**kwargs):
        raise _APIError(404, "model_not_found")

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm = llm_client.AsyncLLMClient("eval.test", sdk)
    with pytest.raises(llm_client.LLMConfigError):
        asyncio.run(llm.chat.completions.create(model="m", messages=[]))


def test_finish_fails_the_run_when_most_calls_failed():
    llm_client._STATS.calls, llm_client._STATS.errors = 5, 3
    with pytest.raises(SystemExit) as info:
        llm_client.finish()
    assert info.value.code == 1


@pytest.mark.parametrize(("calls", "errors"), [(0, 0), (10, 2), (2, 2), (6, 3)])
def test_finish_passes_runs_with_few_or_isolated_failures(calls, errors):
    llm_client._STATS.calls, llm_client._STATS.errors = calls, errors
    llm_client.finish()


def test_api_key_prefers_the_group_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "shared")
    monkeypatch.setenv("OPENAI_API_KEY_ENRICH", "enrich-only")
    assert llm_client.api_key_for("enrich.poster") == "enrich-only"
    assert llm_client.api_key_for("annotator.annotate") is None  # SDK falls back to OPENAI_API_KEY


def test_unknown_group_is_rejected():
    with pytest.raises(ValueError):
        llm_client.api_key_for("researcher.slot0")


def test_get_client_resolves_the_sdk_at_call_time(monkeypatch):
    seen = {}

    class FakeOpenAI:
        def __init__(self, api_key=None):
            seen["api_key"] = api_key
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: "ok"))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.delenv("OPENAI_API_KEY_QA", raising=False)
    llm = llm_client.get_client("qa.heartbeat")
    assert llm.chat.completions.create(model="m", messages=[]) == "ok"
    assert seen == {"api_key": None}


# ── Usage ledger ────────────────────────────────────────────────────────────

class _FakeDB:
    def __init__(self, fail=False):
        self.inserted, self.fail = [], fail

    def table(self, name):
        assert name == "llm_usage"
        return self

    def insert(self, rows):
        self._rows = rows
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("db down")
        self.inserted.extend(self._rows)


@pytest.fixture
def ledger(monkeypatch):
    db = _FakeDB()
    monkeypatch.setenv("LLM_USAGE_DISABLED", "0")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Daily Scraper")
    monkeypatch.setattr(llm_client, "_DB", db)
    return db


def _chat_response(prompt, cached, completion):
    return SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=prompt,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        completion_tokens=completion,
    ))


def test_chat_call_records_tokens_including_cached(ledger):
    _client(_chat_response(1200, 1000, 300)).chat.completions.create(model="gpt-4o-mini", messages=[])
    llm_client.flush()
    assert ledger.inserted == [{
        "caller": "enrich.test", "model": "gpt-4o-mini", "endpoint": "chat",
        "input_tokens": 1200, "cached_input_tokens": 1000, "output_tokens": 300,
        "web_search_calls": 0, "status": "ok", "error_code": None,
        "run_ref": "Daily Scraper#42",
    }]


def test_responses_call_counts_web_search_calls(ledger):
    resp = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=50, input_tokens_details=SimpleNamespace(cached_tokens=0), output_tokens=9),
        output=[SimpleNamespace(type="web_search_call"), SimpleNamespace(type="message"),
                SimpleNamespace(type="web_search_call")],
    )
    _client(resp).responses.create(model="gpt-4o-mini", input="x")
    llm_client.flush()
    row = ledger.inserted[0]
    assert (row["endpoint"], row["input_tokens"], row["output_tokens"], row["web_search_calls"]) == ("responses", 50, 9, 2)


def test_failed_call_records_an_error_row(ledger):
    with pytest.raises(llm_client.LLMConfigError):
        _client(_APIError(404, "model_not_found")).chat.completions.create(model="gpt-4o-search-preview", messages=[])
    llm_client.flush()
    assert ledger.inserted[0]["status"] == "error"
    assert ledger.inserted[0]["error_code"] == "model_not_found"
    assert ledger.inserted[0]["input_tokens"] == 0


def test_rows_flush_in_batches_and_at_finish(ledger):
    llm = _client(_chat_response(1, 0, 1))
    for _ in range(llm_client.FLUSH_EVERY + 3):
        llm.chat.completions.create(model="gpt-4o-mini", messages=[])
    assert len(ledger.inserted) == llm_client.FLUSH_EVERY
    llm_client.finish()
    assert len(ledger.inserted) == llm_client.FLUSH_EVERY + 3


def test_ledger_failure_never_breaks_the_run(monkeypatch):
    monkeypatch.setenv("LLM_USAGE_DISABLED", "0")
    monkeypatch.setattr(llm_client, "_DB", _FakeDB(fail=True))
    resp = _chat_response(1, 0, 1)
    assert _client(resp).chat.completions.create(model="m", messages=[]) is resp
    llm_client.flush()  # logs a warning, does not raise


def test_non_integer_usage_counts_as_zero(ledger):
    from unittest.mock import MagicMock

    _client(MagicMock()).chat.completions.create(model="gpt-4o", messages=[])
    llm_client.flush()
    row = ledger.inserted[0]
    assert (row["input_tokens"], row["cached_input_tokens"], row["output_tokens"]) == (0, 0, 0)


def test_recording_is_off_when_disabled(monkeypatch):
    db = _FakeDB()
    monkeypatch.setenv("LLM_USAGE_DISABLED", "1")
    monkeypatch.setattr(llm_client, "_DB", db)
    _client(_chat_response(1, 0, 1)).chat.completions.create(model="m", messages=[])
    llm_client.flush()
    assert db.inserted == []


def test_embeddings_call_records_input_tokens_only(ledger):
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=420, total_tokens=420), data=[])
    assert _client(resp).embeddings.create(model="text-embedding-3-small", input=["a", "b"]) is resp
    llm_client.flush()
    row = ledger.inserted[0]
    assert (row["endpoint"], row["model"], row["input_tokens"], row["cached_input_tokens"], row["output_tokens"]) == (
        "embeddings", "text-embedding-3-small", 420, 0, 0,
    )


def test_embeddings_async_client_records_too(ledger):
    async def create(**kwargs):
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=7, total_tokens=7))

    sdk = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    llm = llm_client.AsyncLLMClient("eval.test", sdk)
    asyncio.run(llm.embeddings.create(model="text-embedding-3-small", input=["x"]))
    llm_client.flush()
    assert ledger.inserted[0]["endpoint"] == "embeddings"
    assert ledger.inserted[0]["input_tokens"] == 7


def test_every_sdk_surface_in_use_is_exposed():
    """A scraper that calls an SDK surface the wrapper lacks bypasses the ledger or crashes.

    Embeddings were missed in the first inventory, which only grepped chat/responses;
    the Historical Backtest on PR #391 failed on `client.embeddings` for that reason.
    """
    import re
    from pathlib import Path

    surfaces = ("chat", "responses", "embeddings", "images", "audio", "moderations", "files", "batches", "beta")
    pattern = re.compile(r"\b(?:client|llm|ai|oai)\.(" + "|".join(surfaces) + r")\.[a-z_.]*\(")
    used = set()
    scraper = Path(__file__).resolve().parents[1]
    for path in scraper.rglob("*.py"):
        rel = path.relative_to(scraper).as_posix()
        if rel.startswith(("tests/", "auto_scraper/tests/")) or path.name.startswith("_oneoff_") or rel == "llm_client.py":
            continue
        used.update(pattern.findall(path.read_text(encoding="utf-8")))

    client = llm_client.LLMClient("enrich.test", SimpleNamespace())
    missing = sorted(name for name in used if not hasattr(client, name))
    assert not missing, f"LLMClient does not expose SDK surface(s) in use: {missing}"
    assert "embeddings" in used  # the pattern still finds the surface this test exists for
