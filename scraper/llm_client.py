"""Shared OpenAI client for the scraper. Every OpenAI call goes through here.

    from llm_client import get_client, finish

    llm = get_client("enrich.location")
    resp = llm.chat.completions.create(model=..., messages=...)   # same shape as the SDK
    ...
    finish()   # at the end of main()

Error handling (#319):

- Config errors — retired model (404 / model_not_found), bad or revoked key
  (401 / 403), exhausted quota (429 insufficient_quota), and 400s that every
  call would hit (unsupported_parameter, …) — raise LLMConfigError. It derives
  from BaseException, not Exception, so the broad `except Exception` blocks
  around call sites cannot swallow it: the process exits non-zero and the
  workflow step fails. From 2026-08-20 the retired gpt-4o-search-preview
  failed this way for two months while every run reported success.
- Transient errors (rate limit, 5xx, timeout, connection) and per-request 400s
  are re-raised unchanged after the SDK's own retries, so call sites keep their
  current handling. They are counted; finish() exits non-zero when most calls
  of this process failed.

Usage ledger (#363): every call, ok or error, becomes one public.llm_usage row
(model, input / cached / output tokens, web search calls). Rows are buffered
and inserted every FLUSH_EVERY calls, at finish(), and at interpreter exit, so
a run that dies on LLMConfigError still records what it spent. A failed insert
only logs a warning. Cost is computed by the llm_cost_daily view from
llm_pricing; nothing here knows a price. LLM_USAGE_DISABLED=1 turns recording
off (the test suite sets it).

Callers are named "<group>.<name>". The group picks the API key:
OPENAI_API_KEY_<GROUP> when set, else OPENAI_API_KEY (#320).

The SDK is imported when a client is created, not at module import, so tests
that swap sys.modules["openai"] keep working.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

logger = logging.getLogger(__name__)

FLUSH_EVERY = 20

GROUPS = frozenset({"annotator", "enrich", "qa", "broadcast", "eval", "auto_scraper"})

# 400 codes that mean the request shape or account is wrong, not this input.
_CONFIG_400_CODES = frozenset({
    "model_not_found",
    "unsupported_parameter",
    "unsupported_value",
    "invalid_api_key",
})
_TRANSIENT_NAMES = frozenset({"APITimeoutError", "APIConnectionError"})


class LLMConfigError(BaseException):
    """An OpenAI error that every later call would hit too. Not an Exception on purpose."""

    def __init__(self, caller: str, model: str | None, status: int | None, code: str | None, message: str):
        self.caller = caller
        self.model = model
        self.status = status
        self.code = code
        super().__init__(f"[{caller}] OpenAI config error (model={model}, status={status}, code={code}): {message}")


def classify(exc: BaseException) -> str:
    """Return "config", "transient", "request" or "other" for an exception raised by the SDK."""
    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    if status in (401, 403, 404):
        return "config"
    if status == 429:
        return "config" if code == "insufficient_quota" else "transient"
    if status == 400:
        return "config" if code in _CONFIG_400_CODES else "request"
    if isinstance(status, int) and status >= 500:
        return "transient"
    if type(exc).__name__ in _TRANSIENT_NAMES:
        return "transient"
    if status is not None:
        return "request"
    return "other"


@dataclass
class _Stats:
    calls: int = 0
    errors: int = 0


_STATS = _Stats()


def stats() -> _Stats:
    return _STATS


def _reset_for_tests() -> None:
    global _STATS, _DB, _DB_UNAVAILABLE
    _STATS = _Stats()
    _BUFFER.clear()
    _DB = None
    _DB_UNAVAILABLE = False


def _group(caller: str) -> str:
    group = caller.split(".", 1)[0]
    if group not in GROUPS:
        raise ValueError(f"unknown LLM caller group {group!r} in {caller!r}; expected one of {sorted(GROUPS)}")
    return group


def api_key_for(caller: str) -> str | None:
    """The group's own key when set; None lets the SDK read OPENAI_API_KEY (and fail if absent)."""
    return os.environ.get(f"OPENAI_API_KEY_{_group(caller).upper()}") or None


# ── Usage ledger ────────────────────────────────────────────────────────────

_BUFFER: list[dict] = []
_LOCK = threading.Lock()
_DB: Any = None
_DB_UNAVAILABLE = False


def _int(value: Any) -> int:
    """Token counts only; anything else (None, a test MagicMock) counts as 0."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def usage_row(
    caller: str,
    endpoint: str,
    model: str | None,
    response: Any = None,
    error: BaseException | None = None,
) -> dict:
    """Build one llm_usage row from an SDK response (or the error that replaced it)."""
    usage = getattr(response, "usage", None)
    if endpoint == "embeddings":
        # Embeddings bill input tokens only; usage has prompt_tokens and total_tokens.
        input_tokens = _int(getattr(usage, "prompt_tokens", None))
        cached = 0
        output_tokens = 0
        searches = 0
    elif endpoint == "chat":
        input_tokens = _int(getattr(usage, "prompt_tokens", None))
        cached = _int(getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None))
        output_tokens = _int(getattr(usage, "completion_tokens", None))
        searches = 0
    else:
        input_tokens = _int(getattr(usage, "input_tokens", None))
        cached = _int(getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None))
        output_tokens = _int(getattr(usage, "output_tokens", None))
        output = getattr(response, "output", None)
        searches = sum(
            1 for item in (output if isinstance(output, list) else [])
            if getattr(item, "type", None) == "web_search_call"
        )
    row = {
        "caller": caller,
        "model": model if isinstance(model, str) and model else "unknown",
        "endpoint": endpoint,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output_tokens,
        "web_search_calls": searches,
        "status": "error" if error is not None else "ok",
        "error_code": None,
        "run_ref": None,
    }
    if error is not None:
        code = getattr(error, "code", None) or getattr(error, "status_code", None) or type(error).__name__
        row["error_code"] = str(code)[:100]
    run_id = os.environ.get("GITHUB_RUN_ID")
    if run_id:
        row["run_ref"] = f"{os.environ.get('GITHUB_WORKFLOW', 'actions')}#{run_id}"
    return row


def _recording_disabled() -> bool:
    return os.environ.get("LLM_USAGE_DISABLED") == "1"


def _usage_db() -> Any:
    global _DB, _DB_UNAVAILABLE
    if _DB is None and not _DB_UNAVAILABLE:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            _DB_UNAVAILABLE = True
            logger.warning("LLM usage not recorded: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        else:
            from supabase import create_client

            _DB = create_client(url, key)
    return _DB


def _record(row: dict) -> None:
    if _recording_disabled():
        return
    with _LOCK:
        _BUFFER.append(row)
        full = len(_BUFFER) >= FLUSH_EVERY
    if full:
        flush()


def flush() -> None:
    """Insert buffered usage rows. Never raises: the ledger must not break a run."""
    with _LOCK:
        rows = list(_BUFFER)
        _BUFFER.clear()
    if not rows:
        return
    try:
        db = _usage_db()
        if db is not None:
            db.table("llm_usage").insert(rows).execute()
    except Exception as exc:
        logger.warning("could not record %d LLM usage row(s): %s", len(rows), exc)


atexit.register(flush)


def _on_error(caller: str, endpoint: str, model: str | None, exc: BaseException) -> None:
    _STATS.errors += 1
    _record(usage_row(caller, endpoint, model, error=exc))
    kind = classify(exc)
    if kind == "config":
        raise LLMConfigError(
            caller, model, getattr(exc, "status_code", None), getattr(exc, "code", None), str(exc)
        ) from exc
    logger.warning("[%s] OpenAI %s error (model=%s): %s", caller, kind, model, exc)


class _Endpoint:
    def __init__(self, caller: str, endpoint: str, resolve: Callable[[], Callable[..., Any]]):
        self._caller = caller
        self._endpoint = endpoint
        self._resolve = resolve

    def create(self, **kwargs: Any) -> Any:
        _STATS.calls += 1
        model = kwargs.get("model")
        try:
            response = self._resolve()(**kwargs)
        except Exception as exc:
            _on_error(self._caller, self._endpoint, model, exc)
            raise
        _record(usage_row(self._caller, self._endpoint, model, response))
        return response


class _AsyncEndpoint(_Endpoint):
    async def create(self, **kwargs: Any) -> Any:  # type: ignore[override]
        _STATS.calls += 1
        model = kwargs.get("model")
        try:
            response = await self._resolve()(**kwargs)
        except Exception as exc:
            _on_error(self._caller, self._endpoint, model, exc)
            raise
        _record(usage_row(self._caller, self._endpoint, model, response))
        return response


class LLMClient:
    """Mirrors the SDK surface the scraper uses: chat.completions.create, responses.create and embeddings.create.

    Every SDK surface a scraper calls must be exposed here, or the call bypasses the ledger
    (or, as with embeddings in eval_annotator, fails). test_every_sdk_surface_in_use_is_exposed guards this.
    """

    _endpoint_cls = _Endpoint

    def __init__(self, caller: str, sdk: Any):
        _group(caller)
        self.caller = caller
        self.chat = SimpleNamespace(
            completions=self._endpoint_cls(caller, "chat", lambda: sdk.chat.completions.create)
        )
        self.responses = self._endpoint_cls(caller, "responses", lambda: sdk.responses.create)
        self.embeddings = self._endpoint_cls(caller, "embeddings", lambda: sdk.embeddings.create)


class AsyncLLMClient(LLMClient):
    _endpoint_cls = _AsyncEndpoint


def get_client(caller: str, *, api_key: str | None = None) -> LLMClient:
    import openai

    return LLMClient(caller, openai.OpenAI(api_key=api_key or api_key_for(caller)))


def get_async_client(caller: str, *, api_key: str | None = None) -> AsyncLLMClient:
    import openai

    return AsyncLLMClient(caller, openai.AsyncOpenAI(api_key=api_key or api_key_for(caller)))


def finish(*, min_errors: int = 3, max_error_ratio: float = 0.5) -> None:
    """Exit non-zero when most LLM calls of this process failed.

    Call at the end of main(). A run with no calls, or with only a few
    isolated failures, passes.
    """
    flush()
    s = _STATS
    if s.calls:
        logger.info("LLM calls: %d, errors: %d", s.calls, s.errors)
    if s.errors >= min_errors and s.errors > s.calls * max_error_ratio:
        logger.error("LLM error rate too high: %d of %d calls failed", s.errors, s.calls)
        raise SystemExit(1)
