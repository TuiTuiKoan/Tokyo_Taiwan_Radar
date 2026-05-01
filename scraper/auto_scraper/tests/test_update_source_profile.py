"""Tests for `scraper/update_source.py` Phase 1.3 source_profile fields.

Run with:
    cd scraper && source ../.venv/bin/activate && \
        python -m unittest auto_scraper.tests.test_update_source_profile -v
"""

from __future__ import annotations

import io
import os
import re
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make the `scraper/` package importable when this file runs from the repo root.
_THIS_DIR = Path(__file__).resolve().parent
_SCRAPER_DIR = _THIS_DIR.parent.parent
if str(_SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRAPER_DIR))

# Provide harmless env defaults so importing update_source never fails on a
# fresh checkout (the real Supabase client is mocked in every test).
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

import update_source  # noqa: E402


def _make_mock_sb(
    existing_row: dict | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Build a mock Supabase client and capture the .update() payload.

    Returns (sb_mock, captured_update_holder). Inspect
    ``captured_update_holder.payload`` after calling update_source().
    """
    sb = MagicMock()
    holder = MagicMock()
    holder.payload = None

    # Chain for SELECT
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(
        data=[existing_row] if existing_row is not None else []
    )

    # Chain for UPDATE — capture payload via side_effect
    def _update(payload):
        holder.payload = payload
        upd_chain = MagicMock()
        upd_chain.execute.return_value = MagicMock(data=[{}])
        upd_chain.eq.return_value = upd_chain
        return upd_chain

    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value = select_chain
    table_mock.update.side_effect = _update
    sb.table.return_value = table_mock
    return sb, holder


class FeasibilityArgparseTests(unittest.TestCase):
    def test_feasibility_required_when_researched(self):
        """argparse exits non-zero when --status researched without --feasibility."""
        parser = update_source._build_parser()
        args = parser.parse_args([
            "--url", "https://example.com",
            "--status", "researched",
        ])
        buf = io.StringIO()
        with redirect_stderr(buf), self.assertRaises(SystemExit) as cm:
            update_source._validate_args(parser, args)
        self.assertNotEqual(cm.exception.code, 0)
        self.assertIn("--feasibility is required", buf.getvalue())

    def test_feasibility_ok_when_researched(self):
        parser = update_source._build_parser()
        args = parser.parse_args([
            "--url", "https://example.com",
            "--status", "researched",
            "--feasibility", "easy",
        ])
        # Should not raise
        update_source._validate_args(parser, args)


class UpdateSourceTests(unittest.TestCase):
    DEFAULT_ROW = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "example",
        "status": "candidate",
        "source_profile": None,
    }

    def test_feasibility_ignored_when_not_viable(self):
        """--feasibility provided with --status not-viable: warns, no profile written."""
        sb, holder = _make_mock_sb(existing_row=dict(self.DEFAULT_ROW))

        with self.assertLogs(update_source.logger, level="WARNING") as cm:
            update_source.update_source(
                url="https://example.com",
                status="not-viable",
                feasibility="easy",
                sb=sb,
            )

        self.assertTrue(
            any("ignored" in msg and "not-viable" in msg for msg in cm.output),
            f"expected ignore-warning in logs, got: {cm.output}",
        )
        payload = holder.payload
        self.assertIsNotNone(payload)
        # No source_profile written (no notes either)
        self.assertNotIn("source_profile", payload)
        self.assertEqual(payload["status"], "not-viable")

    def test_profile_merge_preserves_existing_keys(self):
        """Existing source_profile keys must be preserved when merging new flags."""
        row = dict(self.DEFAULT_ROW, source_profile={"old_key": "old_value", "feasibility": "stale"})
        sb, holder = _make_mock_sb(existing_row=row)

        update_source.update_source(
            url="https://example.com",
            status="researched",
            feasibility="medium",
            pagination_hint="?page=N up to 10",
            sb=sb,
        )
        profile = holder.payload["source_profile"]
        # Old key preserved
        self.assertEqual(profile["old_key"], "old_value")
        # New keys override stale ones / added
        self.assertEqual(profile["feasibility"], "medium")
        self.assertEqual(profile["pagination_hint"], "?page=N up to 10")

    def test_profile_includes_researched_at_iso(self):
        sb, holder = _make_mock_sb(existing_row=dict(self.DEFAULT_ROW))
        update_source.update_source(
            url="https://example.com",
            status="researched",
            feasibility="easy",
            sb=sb,
        )
        profile = holder.payload["source_profile"]
        researched_at = profile.get("researched_at")
        self.assertIsInstance(researched_at, str)
        # ISO-8601 with timezone offset (datetime.isoformat with tzinfo)
        self.assertRegex(
            researched_at,
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2}|Z)$",
        )

    def test_only_provided_hints_written(self):
        """Missing optional flags must NOT appear (not even as null) in payload."""
        sb, holder = _make_mock_sb(existing_row=dict(self.DEFAULT_ROW))
        update_source.update_source(
            url="https://example.com",
            status="researched",
            feasibility="easy",
            card_selector_hint=".event-card",
            # pagination_hint, date_format_hint, notes intentionally omitted
            sb=sb,
        )
        profile = holder.payload["source_profile"]
        self.assertEqual(profile["feasibility"], "easy")
        self.assertEqual(profile["card_selector_hint"], ".event-card")
        self.assertIn("researched_at", profile)
        # Omitted flags must not be present at all
        self.assertNotIn("pagination_hint", profile)
        self.assertNotIn("date_format_hint", profile)
        self.assertNotIn("notes", profile)


if __name__ == "__main__":
    unittest.main()
