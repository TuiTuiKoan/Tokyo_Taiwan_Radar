"""Offline tests for `auto_scraper.generate` (Layer B Phase 2).

All external side effects are mocked: no real OpenAI / Playwright / Supabase /
subprocess. Tests run in <5s and write only into a per-test ``tmp_path``.

Run with::

    cd scraper && source ../.venv/bin/activate && \\
        python -m unittest auto_scraper.tests.test_generate -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make `scraper/` importable (mirrors test_update_source_profile.py).
_THIS_DIR = Path(__file__).resolve().parent
_SCRAPER_DIR = _THIS_DIR.parent.parent
if str(_SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRAPER_DIR))

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

from auto_scraper import generate  # noqa: E402


VALID_SPEC = {
    "source_name": "example_test",
    "class_name": "ExampleTest",
    "base_url": "https://example.com",
    "search_url": "https://example.com/events",
    "card_selector": ".event-card",
    "field_selectors": {"title": ".title", "date": ".date"},
    "date_regex": r"(\d{4})-(\d{1,2})-(\d{1,2})",
    "source_id_prefix": "example_",
    "source_id_url_pattern": r"/event/(\d+)",
}


def _make_row(**overrides) -> dict:
    row = {
        "id": 42,
        "name": "Example",
        "url": "https://example.com/events",
        "status": "researched",
        "url_verified": True,
        "source_profile": {"feasibility": "easy"},
        "auto_scraper_attempted_at": None,
    }
    row.update(overrides)
    return row


def _make_sb(row: dict | None) -> tuple[MagicMock, MagicMock]:
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


class EligibilityTests(unittest.TestCase):
    def test_eligibility_rejects_non_researched(self):
        row = _make_row(status="candidate")
        sb, holder = _make_sb(row)
        opts = generate.GenerateOptions(source_id=42, skip_sandbox=True)
        rc = generate.run(opts, sb=sb)
        self.assertEqual(rc, 1)
        self.assertIsNotNone(holder.update_payload)
        self.assertEqual(holder.update_payload["auto_scraper_status"], "spec-invalid")

    def test_eligibility_rejects_hard_feasibility(self):
        row = _make_row(source_profile={"feasibility": "hard"})
        sb, holder = _make_sb(row)
        opts = generate.GenerateOptions(source_id=42, skip_sandbox=True)
        rc = generate.run(opts, sb=sb)
        self.assertEqual(rc, 1)
        self.assertEqual(holder.update_payload["auto_scraper_status"], "spec-invalid")
        self.assertIn("feasibility", holder.update_payload["auto_scraper_failed_reason"])

    def test_retry_cooldown_within_7_days(self):
        from datetime import datetime, timezone, timedelta

        recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        row = _make_row(auto_scraper_attempted_at=recent)
        sb, holder = _make_sb(row)
        opts = generate.GenerateOptions(source_id=42, skip_sandbox=True)
        rc = generate.run(opts, sb=sb)
        self.assertEqual(rc, 0)
        # No DB write happened.
        self.assertIsNone(holder.update_payload)


class HappyPathTests(unittest.TestCase):
    def test_mock_llm_happy_path_writes_artifacts(self):
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_file = tmp_path / "spec.json"
            spec_file.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            out_dir = tmp_path / "out"

            sample_events = [
                {
                    "name_ja": "Event 1",
                    "name_zh": None,
                    "name_en": None,
                    "source_url": "https://example.com/event/1",
                    "source_id": "example_1",
                    "start_date": "2026-06-01T00:00:00",
                }
            ]
            fake_stdout = "len=3\nSAMPLE_EVENTS=" + json.dumps(sample_events) + "\n"
            fake_subproc = MagicMock(returncode=0, stdout=fake_stdout, stderr="")

            with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"), \
                 patch.object(generate.subprocess, "run", return_value=fake_subproc):
                opts = generate.GenerateOptions(
                    source_id=42,
                    mock_llm=spec_file,
                    output_dir=out_dir,
                )
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 0)
            for fn in ("spec.json", "generated.py", "prompt.txt", "dry_run.txt", "meta.json", "sample.html"):
                self.assertTrue((out_dir / fn).exists(), f"missing artifact: {fn}")
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["model"], "gpt-4o")
            self.assertEqual(meta["events_found"], 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "success")
            self.assertIsNone(holder.update_payload["auto_scraper_failed_reason"])

    def test_artifact_files_written(self):
        # Same as happy path but explicit file-list assertion (per plan §7).
        row = _make_row()
        sb, _holder = _make_sb(row)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_file = tmp_path / "spec.json"
            spec_file.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            out_dir = tmp_path / "out"

            opts = generate.GenerateOptions(
                source_id=42,
                mock_llm=spec_file,
                skip_sandbox=True,
                output_dir=out_dir,
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"):
                rc = generate.run(opts, sb=sb)
            self.assertEqual(rc, 0)
            written = sorted(p.name for p in out_dir.iterdir())
            self.assertIn("spec.json", written)
            self.assertIn("generated.py", written)
            self.assertIn("dry_run.txt", written)
            self.assertIn("meta.json", written)


class BudgetTests(unittest.TestCase):
    def test_budget_exceeded_abort(self):
        row = _make_row()
        sb, holder = _make_sb(row)

        # Stub the OpenAI client to report tokens that exceed budget on first call.
        class FakeUsage:
            prompt_tokens = 1_000_000
            completion_tokens = 0

        class FakeChoice:
            message = MagicMock(content=json.dumps(VALID_SPEC))

        class FakeResp:
            usage = FakeUsage()
            choices = [FakeChoice()]

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = FakeResp()

        # Patch the import-time `from openai import OpenAI` — patch the attribute
        # at sys.modules level so OpenAI() returns our fake.
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        opts = generate.GenerateOptions(
            source_id=42,
            budget_usd=0.001,  # absurdly low
            skip_sandbox=True,
        )
        with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"), \
             patch.dict(sys.modules, {"openai": fake_openai}):
            rc = generate.run(opts, sb=sb)

        self.assertEqual(rc, 1)
        self.assertEqual(holder.update_payload["auto_scraper_status"], "budget-exceeded")
        # Ensure no further LLM calls beyond the first (no retry after over-budget).
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)


class SandboxTests(unittest.TestCase):
    def test_sandbox_failure_status(self):
        row = _make_row()
        sb, holder = _make_sb(row)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_file = tmp_path / "spec.json"
            spec_file.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            out_dir = tmp_path / "out"

            fake_subproc = MagicMock(
                returncode=1,
                stdout="",
                stderr="playwright.sync_api.Error: selector .event-card not found",
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"), \
                 patch.object(generate.subprocess, "run", return_value=fake_subproc):
                opts = generate.GenerateOptions(
                    source_id=42,
                    mock_llm=spec_file,
                    output_dir=out_dir,
                )
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "sandbox-failed")
            # Temp file must have been cleaned up.
            tmp_scraper = _SCRAPER_DIR / "sources" / "_auto_example_test.py"
            self.assertFalse(tmp_scraper.exists(), "sandbox temp file leaked")


class SchemaInjectionTests(unittest.TestCase):
    def test_schema_text_loaded(self):
        from auto_scraper.generate import SPEC_SCHEMA_TEXT
        self.assertIn("base_url", SPEC_SCHEMA_TEXT)
        self.assertIn("source_id_prefix", SPEC_SCHEMA_TEXT)


class FailureArtifactTests(unittest.TestCase):
    def test_failure_persists_artifacts(self):
        """LLM returns spec missing base_url for all 3 attempts -> failure artifacts written."""
        row = _make_row()
        sb, holder = _make_sb(row)

        bad_spec = {k: v for k, v in VALID_SPEC.items() if k != "base_url"}

        class FakeUsage:
            prompt_tokens = 100
            completion_tokens = 50

        class FakeChoice:
            message = MagicMock(content=json.dumps(bad_spec))

        class FakeResp:
            usage = FakeUsage()
            choices = [FakeChoice()]

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = FakeResp()
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            opts = generate.GenerateOptions(
                source_id=42,
                output_dir=out_dir,
                skip_sandbox=True,
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html>sample</html>"), \
                 patch.dict(sys.modules, {"openai": fake_openai}):
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "spec-invalid")
            # 3 attempts attempted
            self.assertEqual(fake_client.chat.completions.create.call_count, 3)
            # Failure artifacts present
            for fn in ("prompt.txt", "sample.html", "last_attempt_spec.json", "meta.json"):
                self.assertTrue((out_dir / fn).exists(), f"missing failure artifact: {fn}")
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "spec-invalid")
            self.assertIn("error", meta)
            # last_attempt_spec.json must contain the bad spec (missing base_url)
            last_attempt = json.loads((out_dir / "last_attempt_spec.json").read_text(encoding="utf-8"))
            self.assertNotIn("base_url", last_attempt)
            self.assertEqual(last_attempt["source_name"], "example_test")


class IgnoreCooldownTests(unittest.TestCase):
    def test_ignore_cooldown_flag(self):
        """Row in cooldown + ignore_cooldown=True -> pipeline proceeds to success."""
        from datetime import datetime, timezone, timedelta

        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        row = _make_row(auto_scraper_attempted_at=recent)
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_file = tmp_path / "spec.json"
            spec_file.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            out_dir = tmp_path / "out"

            opts = generate.GenerateOptions(
                source_id=42,
                mock_llm=spec_file,
                skip_sandbox=True,
                output_dir=out_dir,
                ignore_cooldown=True,
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"):
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 0)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "success")


class SandboxFailureArtifactTests(unittest.TestCase):
    def test_sandbox_failure_persists_full_artifacts(self):
        """Sandbox-failed path persists spec.json, generated.py, dry_run.txt
        in addition to prompt/sample/meta \u2014 the full debug bundle."""
        row = _make_row()
        sb, holder = _make_sb(row)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_file = tmp_path / "spec.json"
            spec_file.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            out_dir = tmp_path / "out"

            with patch.object(generate, "_fetch_sample_html", return_value="<html>sample</html>"), \
                 patch.object(generate, "_run_sandbox", return_value=(False, "fake stderr output", [])):
                opts = generate.GenerateOptions(
                    source_id=42,
                    mock_llm=spec_file,
                    output_dir=out_dir,
                )
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "sandbox-failed")
            for fn in ("prompt.txt", "sample.html", "spec.json", "generated.py", "dry_run.txt", "meta.json"):
                self.assertTrue((out_dir / fn).exists(), f"missing failure artifact: {fn}")
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "sandbox-failed")
            self.assertEqual((out_dir / "dry_run.txt").read_text(encoding="utf-8"), "fake stderr output")
            persisted_spec = json.loads((out_dir / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted_spec["source_name"], "example_test")


class SelectorValidationTests(unittest.TestCase):
    def test_validate_selectors_card_match(self):
        """card_selector that matches → 0 violations."""
        from auto_scraper.generate import _validate_selectors_against_html
        html = '<html><body><li class="article-list"><h2 class="t">A</h2><p class="d">2026.05.05</p></li></body></html>'
        spec = {
            "card_selector": "li.article-list",
            "field_selectors": {"title": "h2.t", "date": "p.d"},
        }
        self.assertEqual(_validate_selectors_against_html(spec, html), [])

    def test_validate_selectors_card_misses(self):
        """card_selector hallucinated → violation flagged."""
        from auto_scraper.generate import _validate_selectors_against_html
        html = '<html><body><li class="article-list">A</li></body></html>'
        spec = {
            "card_selector": ".event-card",
            "field_selectors": {"title": "h2", "date": ".date"},
        }
        violations = _validate_selectors_against_html(spec, html)
        self.assertTrue(any(".event-card" in v for v in violations))

    def test_validate_selectors_field_misses(self):
        """card matches but field selector doesn't."""
        from auto_scraper.generate import _validate_selectors_against_html
        html = '<html><body><li class="card"><h2>title</h2></li></body></html>'
        spec = {
            "card_selector": "li.card",
            "field_selectors": {"title": "h2", "date": ".date-not-here"},
        }
        violations = _validate_selectors_against_html(spec, html)
        self.assertTrue(any("date" in v for v in violations))


class SelectorValidationRetryTests(unittest.TestCase):
    def test_selector_validation_triggers_retry(self):
        """LLM returns bad selector first, good selector second → retries=1, success."""
        row = _make_row()
        sb, holder = _make_sb(row)

        sample_html = (
            '<html><body>'
            '<li class="article-list"><h2 class="t">A</h2><p class="d">2026-05-05</p>'
            '<a href="/event/1">x</a></li>'
            '<li class="article-list"><h2 class="t">B</h2><p class="d">2026-05-06</p>'
            '<a href="/event/2">x</a></li>'
            '</body></html>'
        )

        bad_spec = dict(VALID_SPEC)
        bad_spec["card_selector"] = ".event-card"  # hallucinated, not in HTML

        good_spec = dict(VALID_SPEC)
        good_spec["card_selector"] = "li.article-list"
        good_spec["field_selectors"] = {"title": "h2.t", "date": "p.d"}

        class FakeUsage:
            prompt_tokens = 100
            completion_tokens = 50

        def _make_resp(spec_payload):
            class FakeChoice:
                message = MagicMock(content=json.dumps(spec_payload))

            class FakeResp:
                usage = FakeUsage()
                choices = [FakeChoice()]

            return FakeResp()

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [
            _make_resp(bad_spec),
            _make_resp(good_spec),
        ]
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        sample_events = [
            {
                "name_ja": "Event 1",
                "name_zh": None,
                "name_en": None,
                "source_url": "https://example.com/event/1",
                "source_id": "example_1",
                "start_date": "2026-06-01T00:00:00",
            }
        ]
        fake_stdout = "len=1\nSAMPLE_EVENTS=" + json.dumps(sample_events) + "\n"
        fake_subproc = MagicMock(returncode=0, stdout=fake_stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            opts = generate.GenerateOptions(
                source_id=42,
                output_dir=out_dir,
            )
            with patch.object(generate, "_fetch_sample_html", return_value=sample_html), \
                 patch.object(generate.subprocess, "run", return_value=fake_subproc), \
                 patch.dict(sys.modules, {"openai": fake_openai}):
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 0)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "success")
            self.assertEqual(fake_client.chat.completions.create.call_count, 2)
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["retries"], 1)


class FailureMetaForensicsTests(unittest.TestCase):
    """Phase 2.4 — failure-path meta.json must record cumulative cost/retries."""

    def test_budget_exceeded_meta_records_cost_and_retries(self):
        row = _make_row()
        sb, holder = _make_sb(row)

        class FakeUsage:
            prompt_tokens = 1_000_000
            completion_tokens = 0

        class FakeChoice:
            message = MagicMock(content=json.dumps(VALID_SPEC))

        class FakeResp:
            usage = FakeUsage()
            choices = [FakeChoice()]

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = FakeResp()
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            opts = generate.GenerateOptions(
                source_id=42,
                budget_usd=0.0001,
                output_dir=out_dir,
                skip_sandbox=True,
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html></html>"), \
                 patch.dict(sys.modules, {"openai": fake_openai}):
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "budget-exceeded")
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertGreater(meta["cost_usd"], 0)
            self.assertGreaterEqual(meta["retries"], 0)

    def test_spec_invalid_meta_records_retries(self):
        row = _make_row()
        sb, holder = _make_sb(row)

        bad_spec = {k: v for k, v in VALID_SPEC.items() if k != "base_url"}

        class FakeUsage:
            prompt_tokens = 100
            completion_tokens = 50

        class FakeChoice:
            message = MagicMock(content=json.dumps(bad_spec))

        class FakeResp:
            usage = FakeUsage()
            choices = [FakeChoice()]

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = FakeResp()
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            opts = generate.GenerateOptions(
                source_id=42,
                output_dir=out_dir,
                skip_sandbox=True,
            )
            with patch.object(generate, "_fetch_sample_html", return_value="<html>sample</html>"), \
                 patch.dict(sys.modules, {"openai": fake_openai}):
                rc = generate.run(opts, sb=sb)

            self.assertEqual(rc, 1)
            self.assertEqual(holder.update_payload["auto_scraper_status"], "spec-invalid")
            meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["retries"], generate.MAX_LLM_ATTEMPTS)
            self.assertGreater(meta["cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
