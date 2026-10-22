from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_llm_callers.py"


@pytest.fixture(scope="session")
def guard():
    spec = importlib.util.spec_from_file_location("check_llm_callers", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repo_has_no_direct_callers(guard):
    assert guard.main(["--root", str(ROOT)]) == 0


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("scraper/enrich_new.py", "from openai import OpenAI\nclient = OpenAI(api_key=k)\n"),
        ("scraper/sources/new_source.py", "        client = AsyncOpenAI()\n"),
        ("web/app/api/new/route.ts", 'await fetch("https://api.openai.com/v1/chat/completions", {})\n'),
    ],
)
def test_direct_callers_are_flagged(guard, rel, text):
    assert guard.violation(rel, text)


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("scraper/llm_client.py", "openai.OpenAI(api_key=key)\n"),
        ("web/lib/llm/openai.server.ts", 'const URL = "https://api.openai.com/v1/chat/completions";\n'),
        ("scraper/_oneoff_backfill_x.py", "oai = OpenAI()\n"),
        ("scraper/tests/test_x.py", "fake.OpenAI(api_key=None)\n"),
        ("web/tests/llm-usage.test.ts", '"api.openai.com"\n'),
        ("scraper/annotator.py", "llm = get_client(\"annotator.annotate\")\n# OpenAI(...) in a comment\n"),
        ("scraper/annotator.py", '"""AI-powered event annotator using OpenAI GPT-4o-mini."""\n'),
        ("scraper/auto_scraper/generate.py", 'help="Read spec.json from file instead of calling OpenAI (offline tests).",\n'),
    ],
)
def test_allowed_files_and_patterns_pass(guard, rel, text):
    assert guard.violation(rel, text) is None


def test_a_planted_direct_caller_fails_the_working_tree_scan(guard, tmp_path):
    (tmp_path / "scraper").mkdir()
    (tmp_path / "scraper" / "enrich_new.py").write_text("client = OpenAI()\n", encoding="utf-8")
    assert guard.main(["--root", str(tmp_path)]) == 1
