#!/usr/bin/env python3
"""Classify a pull request into a merge tier from its changed file paths.

Spec: docs/specs/active/pr-flow-tiering/proposal.md, "三個分層".

    0  auto-merge: only documentation that nothing builds or runs
    1  one-click: a single scraper source with its own skill and tests
    2  full review: everything else

The PR Tier workflow runs this file from the default branch under
workflow_run. It reads file names only and never executes the PR's code, so
a PR cannot change how it is classified.

Usage:
    python3 scripts/ci/pr_tier.py --files-json files.json --expected N
        files.json is `gh api --paginate --slurp repos/O/R/pulls/N/files`.
        N is the PR's changed_files. A list that is short, or a PR at the
        API's 3000-file limit, is tier 2 because the list may be truncated.
    python3 scripts/ci/pr_tier.py < paths.txt
        One path per line, for local checks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from fnmatch import fnmatchcase

# fnmatch's "*" also matches "/", so "docs/*" covers every file below docs/.
TIER0_INCLUDE = (
    "docs/*",
    ".github/skills/*/history.md",
)
# docs/specs and docs/architecture feed the admin specs page at web build time.
TIER0_EXCLUDE = (
    "docs/specs/*",
    "docs/architecture/*",
)
SOURCE_RE = re.compile(r"scraper/sources/([a-z0-9_]+)\.py")
NOT_A_SOURCE = frozenset({"base", "__init__"})
API_FILE_LIMIT = 3000


def _safe(path: str) -> bool:
    parts = path.split("/")
    if not path or path.startswith("/") or any(ord(ch) < 0x20 or ch == "\x7f" for ch in path):
        return False
    return "" not in parts and ".." not in parts and "." not in parts


def _tier0(path: str) -> bool:
    return any(fnmatchcase(path, p) for p in TIER0_INCLUDE) and not any(fnmatchcase(path, p) for p in TIER0_EXCLUDE)


def _source_stems(paths: list[str]) -> set[str]:
    stems = set()
    for path in paths:
        match = SOURCE_RE.fullmatch(path)
        if match and match.group(1) not in NOT_A_SOURCE:
            stems.add(match.group(1))
    return stems


def _tier1_paths(stem: str) -> tuple[str, ...]:
    dashed = stem.replace("_", "-")
    return (
        f"scraper/sources/{stem}.py",
        f".github/skills/sources/{stem}/*",
        f".github/skills/sources/{dashed}/*",
        f"scraper/tests/test_{stem}*.py",
    )


def classify(paths: list[str]) -> int:
    """Return the highest tier any path needs; anything unrecognised is tier 2."""
    paths = [p.strip() for p in paths if p.strip()]
    if not paths or not all(_safe(p) for p in paths):
        return 2
    stems = _source_stems(paths)
    tier1 = _tier1_paths(next(iter(stems))) if len(stems) == 1 else ()
    tier = 0
    for path in paths:
        if _tier0(path):
            continue
        if any(fnmatchcase(path, p) for p in tier1):
            tier = max(tier, 1)
        else:
            return 2
    return tier


def classify_api_files(pages: list, expected: int) -> int:
    """Classify the PR files API response; any sign of an incomplete list is tier 2."""
    entries = []
    for page in pages:
        entries.extend(page if isinstance(page, list) else [page])
    if expected <= 0 or expected >= API_FILE_LIMIT or len(entries) != expected:
        return 2
    paths = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
            return 2
        paths.append(entry["filename"])
        if isinstance(entry.get("previous_filename"), str):
            paths.append(entry["previous_filename"])
    return classify_exact(paths)


def classify_exact(paths: list[str]) -> int:
    """Like classify, but without trimming: API file names are taken as they are."""
    if not paths or any(p != p.strip() for p in paths):
        return 2
    return classify(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--files-json")
    parser.add_argument("--expected", type=int)
    args = parser.parse_args(argv)
    if args.files_json is not None:
        if args.expected is None:
            parser.error("--files-json needs --expected")
        with open(args.files_json, encoding="utf-8") as handle:
            data = json.load(handle)
        print(classify_api_files(data if isinstance(data, list) else [], args.expected))
    else:
        print(classify(sys.stdin.read().splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
