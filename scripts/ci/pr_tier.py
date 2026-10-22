#!/usr/bin/env python3
"""Classify a pull request into a merge tier from its changed file paths.

Spec: docs/specs/active/pr-flow-tiering/proposal.md, "三個分層".

    0  auto-merge: only documentation that nothing builds or runs
    1  one-click: a single scraper source with its own skill and tests
    2  full review: everything else

The PR Tier workflow runs this file from the base branch under
pull_request_target. It reads file names only and never executes the PR's
code, so a PR cannot change how it is classified.

Usage: python3 scripts/ci/pr_tier.py < paths.txt   (one path per line; prints the tier)
"""
from __future__ import annotations

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


def _safe(path: str) -> bool:
    parts = path.split("/")
    return bool(path) and not path.startswith("/") and "" not in parts and ".." not in parts and "." not in parts


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


def main() -> int:
    print(classify(sys.stdin.read().splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
