"""Tests for scraper/observability.py (spec sentry-stacktrace).

The point of the module is that every Sentry event carries a stack trace, so
GitHub code mappings can link an issue to the line that raised it. These tests
check the options, that entrypoints call it, and — with an in-memory
transport — that a plain ``logger.error`` really arrives with frames.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

import observability

SCRAPER_DIR = Path(__file__).resolve().parent.parent

# Scripts that GitHub Actions runs directly and that must report to Sentry.
ENTRYPOINTS = [
    "main.py",
    "annotator.py",
    "merger.py",
    "enrich_location.py",
    "enrich_addresses.py",
    "enrich_ocr_event.py",
    "auto_qa.py",
    "refetch_thin_events.py",
]

FAKE_DSN = "https://public@example.invalid/1"


def test_disabled_without_dsn():
    assert observability.sentry_options({}) is None
    assert observability.sentry_options({"SENTRY_DSN": ""}) is None


def test_disabled_under_pytest():
    # conftest.py blanks SENTRY_DSN (#542); init must be a no-op here.
    assert observability.init_sentry("test") is False


def test_options_attach_stacktrace_and_production_on_actions():
    opts = observability.sentry_options(
        {"SENTRY_DSN": FAKE_DSN, "GITHUB_ACTIONS": "true", "GITHUB_SHA": "abc123"}
    )
    assert opts["attach_stacktrace"] is True
    assert opts["environment"] == "production"
    assert opts["release"] == "abc123"
    assert opts["traces_sample_rate"] == 0.1


def test_options_local_run():
    opts = observability.sentry_options({"SENTRY_DSN": FAKE_DSN})
    assert opts["environment"] == "local"
    # No release key: the SDK detects it from git.
    assert "release" not in opts


def test_options_explicit_overrides():
    opts = observability.sentry_options(
        {
            "SENTRY_DSN": FAKE_DSN,
            "GITHUB_ACTIONS": "true",
            "GITHUB_SHA": "abc123",
            "SENTRY_ENVIRONMENT": "staging",
            "SENTRY_RELEASE": "v9",
        }
    )
    assert opts["environment"] == "staging"
    assert opts["release"] == "v9"


@pytest.mark.parametrize("filename", ENTRYPOINTS)
def test_entrypoint_calls_init_sentry(filename):
    source = (SCRAPER_DIR / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "init_sentry"
    ]
    assert calls, f"{filename} must call observability.init_sentry()"


def test_sentry_sdk_init_only_in_observability():
    """One place decides the Sentry options; entrypoints must not call init directly."""
    offenders = []
    for path in SCRAPER_DIR.rglob("*.py"):
        if "tests" in path.parts or path.name == "observability.py":
            continue
        if "sentry_sdk.init(" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(path.relative_to(SCRAPER_DIR)))
    assert offenders == []


class _MemoryTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


@pytest.fixture
def captured_events():
    transport = _MemoryTransport()
    opts = observability.sentry_options({"SENTRY_DSN": FAKE_DSN})
    opts["traces_sample_rate"] = 0
    sentry_sdk.init(**opts, transport=transport)
    try:
        yield transport.events
    finally:
        sentry_sdk.flush()
        # Leave the SDK disabled for the rest of the test session.
        sentry_sdk.init()


def _frames(event: dict) -> list[dict]:
    frames: list[dict] = []
    for exc in (event.get("exception") or {}).get("values", []):
        frames.extend((exc.get("stacktrace") or {}).get("frames", []))
    for thread in (event.get("threads") or {}).get("values", []):
        frames.extend((thread.get("stacktrace") or {}).get("frames", []))
    return frames


def test_plain_logger_error_arrives_with_frames(captured_events):
    logging.getLogger("observability-test").error("source returned nothing")
    sentry_sdk.flush()
    assert len(captured_events) == 1
    frames = _frames(captured_events[0])
    assert frames, "attach_stacktrace must add the call-site stack"
    assert any(f.get("function") == "test_plain_logger_error_arrives_with_frames" for f in frames)


def test_logger_exception_carries_raising_frame(captured_events):
    def _fetch():
        raise RuntimeError("403 Forbidden")

    try:
        _fetch()
    except RuntimeError:
        logging.getLogger("observability-test").exception("failed to fetch")
    sentry_sdk.flush()
    assert len(captured_events) == 1
    exc_values = captured_events[0]["exception"]["values"]
    raised_in = [f.get("function") for v in exc_values for f in v["stacktrace"]["frames"]]
    assert "_fetch" in raised_in
