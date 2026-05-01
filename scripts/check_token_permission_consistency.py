#!/usr/bin/env python3
"""Check cross-file consistency for GITHUB_TOKEN permission wording.

Default mode uses a small allowlist so historical lesson logs do not fail CI.
Use --strict to disable the allowlist.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCANNED_EXTENSIONS = {".md", ".py", ".yml", ".yaml", ".txt"}
KEYWORD_RE = re.compile(
    r"GITHUB_TOKEN|--create-issue|Issues:|repo\s*scope|fine[- ]grained|classic\s+token|Metadata:",
    re.IGNORECASE,
)
ISSUES_READ_WRITE_RE = re.compile(r"Issues:\s*read\s*&\s*write", re.IGNORECASE)
FINE_GRAINED_ISSUES_WRITE_RE = re.compile(
    r"fine[- ]grained.*Issues:\s*write", re.IGNORECASE
)
METADATA_READ_RE = re.compile(r"Metadata:\s*read", re.IGNORECASE)

HISTORY_PATH_RE = re.compile(r"^\.github/skills/agents/.+/history\.md$", re.IGNORECASE)
LESSON_LINE_RE = re.compile(
    r"mixed\s+wording|do\s+not\s+use\s+mixed|do\s+not\s+allow\s+mixed|口徑分裂|`Issues:\s*read\s*&\s*write`",
    re.IGNORECASE,
)


@dataclass
class Violation:
    path: str
    line_number: int
    summary: str
    line_text: str


def run_git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "unknown git error"
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return proc.stdout


def get_repo_root(start_dir: Path) -> Path:
    output = run_git(start_dir, "rev-parse", "--show-toplevel")
    return Path(output.strip())


def tracked_files(repo_root: Path) -> list[str]:
    out = run_git(repo_root, "ls-files")
    files: list[str] = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        if Path(rel).suffix.lower() in SCANNED_EXTENSIONS:
            files.append(rel)
    return files


# Path of this script relative to repo root — always excluded to avoid
# false positives from string literals used in violation detection logic.
_SELF_PATH = "scripts/check_token_permission_consistency.py"


def is_allowlisted(path: str, line: str, strict: bool) -> bool:
    # Always skip the checker script itself (string literals are not violations).
    if path == _SELF_PATH:
        return True
    if strict:
        return False
    if HISTORY_PATH_RE.search(path):
        return True
    if ISSUES_READ_WRITE_RE.search(line) and LESSON_LINE_RE.search(line):
        return True
    return False


def check_line(path: str, line_number: int, line: str, strict: bool) -> list[Violation]:
    violations: list[Violation] = []
    if not KEYWORD_RE.search(line):
        return violations

    if ISSUES_READ_WRITE_RE.search(line) and not is_allowlisted(path, line, strict):
        violations.append(
            Violation(
                path=path,
                line_number=line_number,
                summary="Forbidden wording: 'Issues: read & write'",
                line_text=line.strip(),
            )
        )

    missing_metadata = (
        FINE_GRAINED_ISSUES_WRITE_RE.search(line)
        and not METADATA_READ_RE.search(line)
    )
    if missing_metadata and not is_allowlisted(path, line, strict):
        violations.append(
            Violation(
                path=path,
                line_number=line_number,
                summary=(
                    "Fine-grained wording mentions 'Issues: write' "
                    "without 'Metadata: read'"
                ),
                line_text=line.strip(),
            )
        )

    return violations


def scan_file(repo_root: Path, rel_path: str, strict: bool) -> list[Violation]:
    path = repo_root / rel_path
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [
            Violation(
                path=rel_path,
                line_number=0,
                summary=f"Unable to read file: {exc}",
                line_text="",
            )
        ]

    found: list[Violation] = []
    for idx, line in enumerate(lines, start=1):
        found.extend(check_line(rel_path, idx, line, strict))
    return found


def print_report(violations: list[Violation], scanned: int, strict: bool) -> None:
    mode = "strict" if strict else "default (allowlist enabled)"
    print(f"Mode: {mode}")
    print(f"Scanned files: {scanned}")

    if not violations:
        print("No token permission wording violations found.")
        return

    print(f"Violations: {len(violations)}")
    for item in violations:
        location = f"{item.path}:{item.line_number}"
        print(f"- {location}: {item.summary}")
        if item.line_text:
            print(f"  {item.line_text}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check GITHUB_TOKEN permission wording consistency across tracked files."
        )
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Disable allowlist and report every matching violation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_dir = Path(__file__).resolve().parent.parent
    try:
        repo_root = get_repo_root(start_dir)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    files = tracked_files(repo_root)
    all_violations: list[Violation] = []
    for rel_path in files:
        all_violations.extend(scan_file(repo_root, rel_path, args.strict))

    print_report(all_violations, scanned=len(files), strict=args.strict)
    return 1 if all_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
