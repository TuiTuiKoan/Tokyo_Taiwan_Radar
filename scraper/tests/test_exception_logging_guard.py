"""Guard: errors logged inside an ``except`` block must carry the traceback.

Spec ``sentry-stacktrace``. Sentry's logging integration turns every
``logger.error`` into an event, but only takes a stack trace from
``record.exc_info``. ``logger.error("...: %s", exc)`` inside ``except`` sends
text only, so the Sentry issue has no Stack Trace and code mappings cannot link
to GitHub (2026-11-08: ``KG+: failed to fetch WP types`` and
``scraper failed`` looked like this).

Use ``logger.exception(...)`` inside ``except``. When a traceback is really
unwanted (an expected, noisy failure), opt out explicitly with
``exc_info=False``; the guard accepts any ``exc_info`` keyword.
"""

from __future__ import annotations

import ast
from pathlib import Path

SCRAPER_DIR = Path(__file__).resolve().parent.parent
RECEIVERS = {"logger", "logging"}


def _violations(tree: ast.AST) -> list[int]:
    """Line numbers of ``logger.error`` calls inside an except handler without ``exc_info``."""
    found: list[int] = []

    def visit(node: ast.AST, in_handler: bool) -> None:
        for child in ast.iter_child_nodes(node):
            # A nested def/lambda/class runs later, outside the handler.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                visit(child, False)
                continue
            if isinstance(child, ast.ExceptHandler):
                visit(child, True)
                continue
            if (
                in_handler
                and isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "error"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id in RECEIVERS
                and not any(k.arg == "exc_info" for k in child.keywords)
            ):
                found.append(child.lineno)
            visit(child, in_handler)

    visit(tree, False)
    return found


def test_no_logger_error_without_traceback_in_except():
    offenders = []
    for path in sorted(SCRAPER_DIR.rglob("*.py")):
        rel = path.relative_to(SCRAPER_DIR)
        # One-off migration scripts are run once by hand and never report to Sentry.
        if "tests" in rel.parts or path.name.startswith("_oneoff_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        offenders.extend(f"{rel}:{line}" for line in _violations(tree))
    assert offenders == [], (
        "Use logger.exception(...) inside except (or pass exc_info=False on purpose):\n"
        + "\n".join(offenders)
    )


def test_guard_flags_error_in_except():
    src = "try:\n    f()\nexcept Exception as exc:\n    logger.error('x: %s', exc)\n"
    assert _violations(ast.parse(src)) == [4]


def test_guard_accepts_exception_and_explicit_exc_info():
    src = (
        "try:\n    f()\nexcept Exception as exc:\n"
        "    logger.exception('x')\n"
        "    logger.error('y', exc_info=True)\n"
        "    logging.error('z', exc_info=False)\n"
    )
    assert _violations(ast.parse(src)) == []


def test_guard_ignores_error_outside_except_and_in_nested_def():
    src = (
        "logger.error('no exception here')\n"
        "try:\n    f()\nexcept Exception:\n"
        "    def later():\n        logger.error('runs after the handler')\n"
    )
    assert _violations(ast.parse(src)) == []
