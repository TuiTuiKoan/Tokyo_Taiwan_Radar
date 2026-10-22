from __future__ import annotations

import importlib.util
import json
import subprocess
import sys

import pytest


@pytest.fixture(scope="module")
def tier(root):
    path = root / "scripts" / "ci" / "pr_tier.py"
    spec = importlib.util.spec_from_file_location("pr_tier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TIER0 = [
    ["docs/weekly_review/2026-10-25.md"],
    ["docs/monthly_review/2026-10.md"],
    ["docs/ARCHITECTURE.md", "docs/SCRAPER_PIPELINE.md"],
    [".github/skills/agents/architect/history.md"],
    [".github/skills/scraper-expert/history.md", "docs/evaluation/annotator/2026-11-01-monthly.md"],
]

TIER1 = [
    ["scraper/sources/iwafu.py"],
    ["scraper/sources/iwafu.py", "scraper/tests/test_iwafu_relevance.py", ".github/skills/sources/iwafu/SKILL.md"],
    ["scraper/sources/taiwan_cultural_center.py", ".github/skills/sources/taiwan-cultural-center/history.md"],
    ["scraper/sources/peatix.py", "docs/weekly_review/2026-10-25.md"],
]

TIER2 = [
    [],
    ["docs/specs/active/pr-flow-tiering/tasks.md"],
    ["docs/architecture/system-map.json"],
    ["docs/README.md", "web/app/page.tsx"],
    [".github/workflows/pr-tier.yml"],
    ["scripts/ci/pr_tier.py"],
    ["scripts/claude/_policy.py"],
    [".claude/settings.json"],
    ["AGENTS.md"],
    [".github/skills/agents/architect/SKILL.md"],
    [".github/instructions/git.instructions.md"],
    ["supabase/migrations/100_x.sql"],
    ["scraper/annotator.py"],
    ["scraper/sources/base.py"],
    ["scraper/sources/__init__.py", "scraper/sources/iwafu.py"],
    ["scraper/sources/iwafu.py", "scraper/sources/peatix.py"],
    ["scraper/sources/iwafu.py", "scraper/main.py"],
    ["scraper/sources/iwafu.py", "scraper/tests/test_peatix_price_fallback.py"],
    ["scraper/sources/iwafu.py", ".github/skills/sources/peatix/SKILL.md"],
    [".github/skills/sources/iwafu/SKILL.md"],
    ["docs/../web/app/page.tsx"],
    ["/docs/x.md"],
    ["docs//x.md"],
    ["./docs/x.md"],
    ["docs/specsfoo/x.md", "web/x.ts"],
]


@pytest.mark.parametrize("paths", TIER0)
def test_tier0(tier, paths):
    assert tier.classify(paths) == 0


@pytest.mark.parametrize("paths", TIER1)
def test_tier1(tier, paths):
    assert tier.classify(paths) == 1


@pytest.mark.parametrize("paths", TIER2)
def test_tier2(tier, paths):
    assert tier.classify(paths) == 2


def test_blank_lines_are_ignored(tier):
    assert tier.classify(["", "docs/x.md", "  "]) == 0


def test_rename_old_name_counts(tier):
    # The workflow passes both filename and previous_filename; moving a file out of web/ is not docs-only.
    assert tier.classify(["docs/moved.md", "web/app/moved.md"]) == 2


def test_cli_reads_stdin(root):
    script = root / "scripts" / "ci" / "pr_tier.py"
    out = subprocess.run([sys.executable, str(script)], input="docs/a.md\nweb/b.ts\n", capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "2"


def _files(*names, previous=None):
    entries = [{"filename": n, "status": "modified"} for n in names]
    if previous:
        entries[0]["previous_filename"] = previous
        entries[0]["status"] = "renamed"
    return entries


def test_api_docs_only_is_tier0(tier):
    assert tier.classify_api_files([_files("docs/a.md", "docs/b.md")], expected=2) == 0


def test_api_pages_are_flattened(tier):
    assert tier.classify_api_files([_files("docs/a.md"), _files("docs/b.md")], expected=2) == 0


def test_api_short_list_is_tier2(tier):
    # The API returned fewer entries than changed_files: the rest might be web/.
    assert tier.classify_api_files([_files("docs/a.md")], expected=2) == 2


def test_api_file_limit_is_tier2(tier):
    names = [f"docs/{i}.md" for i in range(3000)]
    assert tier.classify_api_files([_files(*names)], expected=3000) == 2


def test_api_rename_from_web_is_tier2(tier):
    assert tier.classify_api_files([_files("docs/moved.ts", previous="web/app/moved.ts")], expected=1) == 2


def test_api_malformed_entries_are_tier2(tier):
    assert tier.classify_api_files([[{"name": "docs/a.md"}]], expected=1) == 2
    assert tier.classify_api_files([["docs/a.md"]], expected=1) == 2
    assert tier.classify_api_files([], expected=0) == 2


def test_api_names_are_not_trimmed(tier):
    assert tier.classify_api_files([_files(" docs/a.md")], expected=1) == 2


@pytest.mark.parametrize("name", ["docs/a\nb.md", "docs/a\rb.md", "docs/a\tb.md", "docs/a\x00b.md", "docs/a\x7fb.md"])
def test_control_characters_are_tier2(tier, name):
    assert tier.classify([name]) == 2


def test_cli_files_json(root, tmp_path):
    script = root / "scripts" / "ci" / "pr_tier.py"
    data = tmp_path / "files.json"
    data.write_text(json.dumps([_files("docs/a.md")]), encoding="utf-8")
    run = lambda n: subprocess.run([sys.executable, str(script), "--files-json", str(data), "--expected", str(n)], capture_output=True, text=True, check=True).stdout.strip()
    assert run(1) == "0"
    assert run(2) == "2"
