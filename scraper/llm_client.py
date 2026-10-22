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

Callers are named "<group>.<name>". The group picks the API key:
OPENAI_API_KEY_<GROUP> when set, else OPENAI_API_KEY (#320).

The SDK is imported when a client is created, not at module import, so tests
that swap sys.modules["openai"] keep working.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

logger = logging.getLogger(__name__)

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
    global _STATS
    _STATS = _Stats()


def _group(caller: str) -> str:
    group = caller.split(".", 1)[0]
    if group not in GROUPS:
        raise ValueError(f"unknown LLM caller group {group!r} in {caller!r}; expected one of {sorted(GROUPS)}")
    return group


def api_key_for(caller: str) -> str | None:
    """The group's own key when set; None lets the SDK read OPENAI_API_KEY (and fail if absent)."""
    return os.environ.get(f"OPENAI_API_KEY_{_group(caller).upper()}") or None


def _on_error(caller: str, model: str | None, exc: BaseException) -> None:
    _STATS.errors += 1
    kind = classify(exc)
    if kind == "config":
        raise LLMConfigError(
            caller, model, getattr(exc, "status_code", None), getattr(exc, "code", None), str(exc)
        ) from exc
    logger.warning("[%s] OpenAI %s error (model=%s): %s", caller, kind, model, exc)


class _Endpoint:
    def __init__(self, caller: str, resolve: Callable[[], Callable[..., Any]]):
        self._caller = caller
        self._resolve = resolve

    def create(self, **kwargs: Any) -> Any:
        _STATS.calls += 1
        try:
            return self._resolve()(**kwargs)
        except Exception as exc:
            _on_error(self._caller, kwargs.get("model"), exc)
            raise


class _AsyncEndpoint(_Endpoint):
    async def create(self, **kwargs: Any) -> Any:  # type: ignore[override]
        _STATS.calls += 1
        try:
            return await self._resolve()(**kwargs)
        except Exception as exc:
            _on_error(self._caller, kwargs.get("model"), exc)
            raise


class LLMClient:
    """Mirrors the SDK surface the scraper uses: chat.completions.create and responses.create."""

    _endpoint_cls = _Endpoint

    def __init__(self, caller: str, sdk: Any):
        self.caller = caller
        self.chat = SimpleNamespace(
            completions=self._endpoint_cls(caller, lambda: sdk.chat.completions.create)
        )
        self.responses = self._endpoint_cls(caller, lambda: sdk.responses.create)


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
    s = _STATS
    if s.calls:
        logger.info("LLM calls: %d, errors: %d", s.calls, s.errors)
    if s.errors >= min_errors and s.errors > s.calls * max_error_ratio:
        logger.error("LLM error rate too high: %d of %d calls failed", s.errors, s.calls)
        raise SystemExit(1)
