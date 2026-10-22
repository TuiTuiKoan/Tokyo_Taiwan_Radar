from __future__ import annotations

import importlib.util
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
