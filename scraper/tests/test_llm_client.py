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
