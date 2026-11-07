#!/usr/bin/env python3
"""Guard the lane 2 approval file in pull requests (issue #569, plan critique G3/G21).

Spec: docs/specs/active/agent-autonomy/proposal.md §9.

docs/specs/active/agent-autonomy/lane2-approved.yml is the user's approval list
for the lane 2 runner. Approval means "the user merged a PR that changed only
this file". Two things can go wrong, and the PR Tier workflow flags both:

  mixed    the PR changes the approval file AND other files, so a weekly review
           of "fix #xyz" can carry an approval line the user never looked at
  invalid  the PR changes only the approval file, but it does not parse or does
           not match the schema; the runner would fail closed on it

The PR Tier workflow runs this file from the default branch under workflow_run.
It reads file names and the approval file's text as data (yaml.safe_load) and
never executes the PR's code, so a PR cannot change how it is checked.

Usage:
    python3 scripts/ci/lane2_approval.py status --files-json files.json --expected N
        prints none | only | mixed
    python3 scripts/ci/lane2_approval.py validate FILE
        prints JSON {"ok": bool, "errors": [...]}
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys

LANE2_PATH = "docs/specs/active/agent-autonomy/lane2-approved.yml"

TOP_KEYS = {"version", "paused", "resume_after", "entries"}
ENTRY_REQUIRED = {"issue", "type", "scope", "files", "risk", "week"}
ENTRY_OPTIONAL = {"suggested", "answer", "judgement"}
ENTRY_TYPES = {"implement"}
RISKS = {"low", "medium", "high"}
WEEK_RE = re.compile(r"\d{4}-W(0[1-9]|[1-4]\d|5[0-3])")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# proposal §9 "runner 的界線": an approval can never widen these.
FORBIDDEN_PREFIXES = (
    ".github/workflows/",
    ".claude/",
    "scripts/claude/",
    "scripts/ci/",
    ".codex/",
    ".agents/",
    ".github/agents/",
    ".github/instructions/",
    ".github/skills/agents/",
    "docs/specs/active/agent-autonomy/",
    "supabase/migrations/",
)
FORBIDDEN_FILES = (
    "scripts/sync_ai_adapters.py",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
)


def _entries(pages: list) -> list:
    out = []
    for page in pages:
        out.extend(page if isinstance(page, list) else [page])
    return out


def touch_status(pages: list, expected: int | None = None) -> str:
    """none | only | mixed for the PR files API response (`--paginate --slurp`).

    A rename into or out of the approval path counts as touching it. A list that
    may be truncated (short, or not matching changed_files) is never "only".
    """
    names: list[str] = []
    for entry in _entries(pages):
        if not isinstance(entry, dict):
            continue
        for key in ("filename", "previous_filename"):
            value = entry.get(key)
            if isinstance(value, str):
                names.append(value)
    touched = LANE2_PATH in names
    if not touched:
        return "none"
    others = [n for n in names if n != LANE2_PATH]
    complete = expected is not None and len(_entries(pages)) == expected
    if others or not complete:
        return "mixed"
    return "only"


def _forbidden(path: str) -> bool:
    if path in FORBIDDEN_FILES or path.startswith(FORBIDDEN_PREFIXES):
        return True
    name = path.rsplit("/", 1)[-1]
    return name == ".env" or name.startswith(".env.")


def validate_data(data) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top level must be a mapping"]
    unknown = set(data) - TOP_KEYS
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)}")
    missing = TOP_KEYS - set(data)
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")
    if "version" in data and (data["version"] != 1 or isinstance(data["version"], bool)):
        errors.append("version must be 1")
    if "paused" in data and not isinstance(data["paused"], bool):
        errors.append("paused must be true or false")
    ra = data.get("resume_after")
    if ra is not None and not isinstance(ra, _dt.date) and not (isinstance(ra, str) and DATE_RE.fullmatch(ra)):
        errors.append("resume_after must be null or a date YYYY-MM-DD")
    entries = data.get("entries")
    if "entries" in data and not isinstance(entries, list):
        errors.append("entries must be a list")
        entries = []
    seen: set[int] = set()
    for i, entry in enumerate(entries or []):
        where = f"entries[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be a mapping")
            continue
        issue = entry.get("issue")
        if isinstance(issue, int) and not isinstance(issue, bool):
            where = f"entries[{i}] (#{issue})"
        unknown = set(entry) - ENTRY_REQUIRED - ENTRY_OPTIONAL
        if unknown:
            errors.append(f"{where}: unknown keys {sorted(unknown)}")
        missing = ENTRY_REQUIRED - set(entry)
        if missing:
            errors.append(f"{where}: missing keys {sorted(missing)}")
        if "issue" in entry:
            if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
                errors.append(f"{where}: issue must be a positive integer")
            elif issue in seen:
                errors.append(f"{where}: issue listed twice")
            else:
                seen.add(issue)
        if "type" in entry and entry["type"] not in ENTRY_TYPES:
            errors.append(f"{where}: type must be one of {sorted(ENTRY_TYPES)}")
        if "scope" in entry and not (isinstance(entry["scope"], str) and entry["scope"].strip()):
            errors.append(f"{where}: scope must be a non-empty string")
        if "files" in entry:
            files = entry["files"]
            if not isinstance(files, list) or not files or not all(isinstance(f, str) and f.strip() for f in files):
                errors.append(f"{where}: files must be a non-empty list of paths")
            else:
                bad = [f for f in files if _forbidden(f)]
                if bad:
                    errors.append(f"{where}: files include forbidden paths {bad}")
        if "risk" in entry and entry["risk"] not in RISKS:
            errors.append(f"{where}: risk must be one of {sorted(RISKS)}")
        if "week" in entry and not (isinstance(entry["week"], str) and WEEK_RE.fullmatch(entry["week"])):
            errors.append(f"{where}: week must look like 2026-W46")
        if "judgement" in entry and not isinstance(entry["judgement"], bool):
            errors.append(f"{where}: judgement must be true or false")
        for key in ("suggested", "answer"):
            if key in entry and entry[key] is not None and not isinstance(entry[key], str):
                errors.append(f"{where}: {key} must be a string or empty")
    return errors


def validate_text(text: str) -> list[str]:
    try:
        import yaml
    except ImportError:
        return ["PyYAML is not available on the runner; cannot validate (fail closed)"]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]
    return validate_data(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--files-json", required=True)
    st.add_argument("--expected", type=int, required=True)
    va = sub.add_parser("validate")
    va.add_argument("file")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        with open(args.files_json, encoding="utf-8") as handle:
            data = json.load(handle)
        print(touch_status(data if isinstance(data, list) else [], args.expected))
    else:
        try:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            errors = [f"cannot read approval file: {exc}"]
        else:
            errors = validate_text(text)
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
