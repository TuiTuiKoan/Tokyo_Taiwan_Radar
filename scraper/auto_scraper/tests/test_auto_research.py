"""Offline tests for `auto_scraper.auto_research` (Layer B Phase 1b).

All external side effects are mocked: no real OpenAI / Playwright / Supabase.
Tests run in <5s and write only into per-test temporary directories.

Run with::

    cd scraper && python -m pytest auto_scraper/tests/test_auto_research.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make `scraper/` importable.
_THIS_DIR = Path(__file__).resolve().parent
_SCRAPER_DIR = _THIS_DIR.parent.parent
if str(_SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRAPER_DIR))

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

from auto_scraper import auto_research  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ASSESSMENT = {
    "taiwan_relevance_score": 0.85,
    "feasibility": "easy",
    "card_selector_hint": "li.article",
    "title_selector_hint": "h3",
    "date_selector_hint": ".date",
    "notes": "Test mock — Taiwan cultural center listing page.",
    "update_frequency": "monthly",
    "taiwan_evidence": ["台湾", "台灣文化"],
    "pagination_hint": "",
    "date_format_hint": "",
    "detail_link_selector_hint": "",
}


def _make_row(**overrides) -> dict:
    row = {
        "id": 99,
        "name": "Test Source",
        "url": "https://example.com/events",
        "status": "candidate",
        "url_verified": True,
        "agent_category": "cultural",
        "reason": "Taiwan cultural events in Japan",
        "source_profile": {},
        "auto_research_attempted_at": None,
    }
    row.update(overrides)
    return row


def _make_sb(row: dict | None) -> tuple[MagicMock, MagicMock]:
    """Build a mock Supabase client that captures update() calls."""
    sb = MagicMock()
    holder = MagicMock()
    holder.update_payload = None
    holder.update_id = None

    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(data=row)

    def _update(payload):
        holder.update_payload = payload
        upd_chain = MagicMock()

        def _eq(col, val):
            holder.update_id = (col, val)
            exec_mock = MagicMock()
            exec_mock.execute.return_value = MagicMock(data=[{}])
            return exec_mock

        upd_chain.eq.side_effect = _eq
        return upd_chain

    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value.single.return_value = select_chain
    table_mock.update.side_effect = _update
    sb.table.return_value = table_mock
    return sb, holder


def _write_assessment(tmp: Path, assessment: dict) -> Path:
    """Write assessment dict to a temp JSON file and return its path."""
    p = tmp / "assessment.json"
    p.write_text(json.dumps(assessment), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Eligibility tests
# ---------------------------------------------------------------------------


class EligibilityTests(unittest.TestCase):
    def test_eligibility_rejects_non_candidate(self):
        """Row with status='implemented' must raise AssessError."""
        row = _make_row(status="implemented")
        with self.assertRaises(auto_research.AssessError) as ctx:
            auto_research._check_eligibility(row)
        self.assertEqual(ctx.exception.status, "ineligible")
        self.assertIn("candidate", ctx.exception.message)

    def test_eligibility_rejects_unverified_url(self):
        """Row with url_verified=False must raise AssessError."""
        row = _make_row(url_verified=False)
        with self.assertRaises(auto_research.AssessError) as ctx:
            auto_research._check_eligibility(row)
        self.assertEqual(ctx.exception.status, "ineligible")
        self.assertIn("url_verified", ctx.exception.message)


# ---------------------------------------------------------------------------
# Cooldown tests
# ---------------------------------------------------------------------------


class CooldownTests(unittest.TestCase):
    def test_cooldown_within_7_days(self):
        """auto_research_attempted_at 2 days ago → still within cooldown."""
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        row = _make_row(auto_research_attempted_at=recent)
        self.assertTrue(auto_research._within_cooldown(row))

    def test_cooldown_outside_7_days(self):
        """auto_research_attempted_at 10 days ago → cooldown expired."""
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        row = _make_row(auto_research_attempted_at=old)
        self.assertFalse(auto_research._within_cooldown(row))


# ---------------------------------------------------------------------------
# Assessment / promotion tests (via mock_llm)
# ---------------------------------------------------------------------------


class AssessmentTests(unittest.TestCase):
    def test_mock_llm_promotes_to_researched(self):
        """score=0.85 + feasibility=easy → patch['status']='researched'."""
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            assessment_file = _write_assessment(
                Path(tmp), {**VALID_ASSESSMENT, "taiwan_relevance_score": 0.85, "feasibility": "easy"}
            )
            opts = auto_research.ResearchOptions(
                source_id=99,
                mock_llm=assessment_file,
                dry_run=False,
                create_issue=False,
            )
            with patch.object(auto_research, "_fetch_sample_html", return_value="<html></html>"):
                rc = auto_research.run(opts, sb=sb)

        self.assertEqual(rc, 0)
        self.assertIsNotNone(holder.update_payload)
        self.assertEqual(holder.update_payload["status"], "researched")
        self.assertEqual(holder.update_payload["auto_research_status"], "assessed")

    def test_mock_llm_demotes_to_not_viable(self):
        """score=0.15 → patch['status']='not-viable'."""
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            assessment_file = _write_assessment(
                Path(tmp),
                {
                    **VALID_ASSESSMENT,
                    "taiwan_relevance_score": 0.15,
                    "taiwan_evidence": [],
                },
            )
            opts = auto_research.ResearchOptions(
                source_id=99,
                mock_llm=assessment_file,
                dry_run=False,
                create_issue=False,
            )
            with patch.object(auto_research, "_fetch_sample_html", return_value="<html></html>"):
                rc = auto_research.run(opts, sb=sb)

        self.assertEqual(rc, 0)
        self.assertIsNotNone(holder.update_payload)
        self.assertEqual(holder.update_payload["status"], "not-viable")
        self.assertEqual(holder.update_payload["auto_research_status"], "not-viable")

    def test_mock_llm_stays_candidate(self):
        """score=0.55 → status unchanged (stays 'candidate')."""
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            assessment_file = _write_assessment(
                Path(tmp), {**VALID_ASSESSMENT, "taiwan_relevance_score": 0.55}
            )
            opts = auto_research.ResearchOptions(
                source_id=99,
                mock_llm=assessment_file,
                dry_run=False,
                create_issue=False,
            )
            with patch.object(auto_research, "_fetch_sample_html", return_value="<html></html>"):
                rc = auto_research.run(opts, sb=sb)

        self.assertEqual(rc, 0)
        self.assertIsNotNone(holder.update_payload)
        self.assertEqual(holder.update_payload["status"], "candidate")
        self.assertEqual(holder.update_payload["auto_research_status"], "assessed")

    def test_dry_run_no_db_write(self):
        """dry_run=True → sb.table().update() is never called."""
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            assessment_file = _write_assessment(
                Path(tmp), {**VALID_ASSESSMENT, "taiwan_relevance_score": 0.85}
            )
            opts = auto_research.ResearchOptions(
                source_id=99,
                mock_llm=assessment_file,
                dry_run=True,
                create_issue=False,
            )
            with patch.object(auto_research, "_fetch_sample_html", return_value="<html></html>"):
                rc = auto_research.run(opts, sb=sb)

        self.assertEqual(rc, 0)
        # No DB write should have occurred
        self.assertIsNone(holder.update_payload)


if __name__ == "__main__":
    unittest.main()
