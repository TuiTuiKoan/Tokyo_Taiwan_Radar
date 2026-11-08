"""Shared Sentry setup for every scraper entrypoint (spec ``sentry-stacktrace``).

Call :func:`init_sentry` once, after ``load_dotenv`` and before any work starts.
It does nothing when ``SENTRY_DSN`` is empty, so tests (``tests/conftest.py``
blanks the DSN, #542) and runs without the secret never report.

Why each option is set:

- ``attach_stacktrace=True``: ``logger.error()`` called outside an ``except``
  block, or ``capture_message()``, has no exception to take a traceback from.
  Without this option Sentry receives only the text, so the issue page shows no
  Stack Trace section and code mappings cannot link to GitHub.
- ``environment``: GitHub Actions runs are ``production``; a run on a laptop is
  ``local``, so local debugging no longer mixes into production issues.
  ``SENTRY_ENVIRONMENT`` overrides both.
- ``release``: the commit SHA on GitHub Actions (``GITHUB_SHA``), so Sentry can
  attribute a regression to a deploy. Locally the SDK detects it from git.
"""

from __future__ import annotations

import os

import sentry_sdk

_TRACES_SAMPLE_RATE = 0.1


def sentry_options(environ: os._Environ[str] | dict[str, str] | None = None) -> dict | None:
    """Return the ``sentry_sdk.init`` keyword arguments, or ``None`` when disabled."""
    env = os.environ if environ is None else environ
    dsn = env.get("SENTRY_DSN")
    if not dsn:
        return None

    on_actions = env.get("GITHUB_ACTIONS") == "true"
    options: dict = {
        "dsn": dsn,
        "traces_sample_rate": _TRACES_SAMPLE_RATE,
        "attach_stacktrace": True,
        "environment": env.get("SENTRY_ENVIRONMENT") or ("production" if on_actions else "local"),
    }
    release = env.get("SENTRY_RELEASE") or env.get("GITHUB_SHA")
    if release:
        options["release"] = release
    return options


def init_sentry(component: str) -> bool:
    """Initialise Sentry for one entrypoint. Returns ``True`` when Sentry is on.

    ``component`` becomes the ``component`` tag (``main``, ``annotator``, …) so
    issues can be filtered by the script that raised them.
    """
    options = sentry_options()
    if options is None:
        return False
    sentry_sdk.init(**options)
    sentry_sdk.set_tag("component", component)
    return True
