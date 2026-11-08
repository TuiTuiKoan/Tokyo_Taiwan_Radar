#!/usr/bin/env python3
"""Pick zero-output scraper issues that still need a source-diagnose comment.

Used by .github/workflows/source-diagnose.yml (scheduled mode). Read-only:
lists open issues labelled ``scraper`` + ``auto-fix`` via `gh api` (REST) and
prints ``<source>:<issue>`` lines, oldest issue first, at most ``--limit``.

An issue is a target when its title looks like ``<source_name>：…0 產出…`` and
none of its comments starts with the ``<!-- source-diagnose -->`` marker.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

MARKER = "<!-- source-diagnose -->"
TITLE_RE = re.compile(r"^([a-z0-9_]+)[：:]")
SOURCE_RE = re.compile(r"^[a-z0-9_]+$")


def select_targets(issues: list[dict], has_diagnosis: dict[int, bool], limit: int = 5) -> list[tuple[str, int]]:
    """Return ``[(source, issue_number)]`` for issues that need a diagnosis."""
    picked: list[tuple[str, int]] = []
    seen_sources: set[str] = set()
    for issue in sorted(issues, key=lambda i: i["number"]):
        if len(picked) >= limit:
            break
        if "pull_request" in issue:
            continue
        title = issue.get("title", "")
        m = TITLE_RE.match(title)
        if not m or "0 產出" not in title:
            continue
        source = m.group(1)
        if not SOURCE_RE.match(source) or source in seen_sources:
            continue
        if has_diagnosis.get(issue["number"], False):
            continue
        seen_sources.add(source)
        picked.append((source, issue["number"]))
    return picked


def _gh_json(path: str) -> list[dict]:
    out = subprocess.run(
        ["gh", "api", "--paginate", path], check=True, capture_output=True, text=True
    ).stdout
    # --paginate concatenates JSON arrays: "[...][...]"
    items: list[dict] = []
    dec = json.JSONDecoder()
    pos = 0
    while pos < len(out):
        while pos < len(out) and out[pos].isspace():
            pos += 1
        if pos >= len(out):
            break
        obj, pos = dec.raw_decode(out, pos)
        items.extend(obj)
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    issues = _gh_json(f"repos/{args.repo}/issues?state=open&labels=scraper,auto-fix&per_page=100")
    has: dict[int, bool] = {}
    for issue in issues:
        comments = _gh_json(f"repos/{args.repo}/issues/{issue['number']}/comments?per_page=100")
        has[issue["number"]] = any(c.get("body", "").lstrip().startswith(MARKER) for c in comments)
    for source, number in select_targets(issues, has, args.limit):
        print(f"{source}:{number}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
