#!/usr/bin/env python3
"""
Campaign disposition backfill — replace the `## Worktree disposition` section of a
campaign close-out record with the values from the recovery capsule, and verify a
record against that capsule.

The close-out record is written before the worktree is removed, so its disposition
section says `pending`. After removal the closer writes the final section to a
scratch file and runs apply mode. If the run is interrupted, re-running it is safe:
a section that already passes verification is left untouched.

Standard library only. Never runs git and never touches the network; the caller
feeds the record (`git show origin/main:<record> |` for --verify).

Modes:
  --record PATH --block FILE --capsule FILE
      Apply. The section runs from the `## Worktree disposition` heading to the first
      heading after it — a `###` subsection such as `### Gates at the close-out
      audit`, or the next `## ` — or to end of file. Subsections are not part of it
      and are kept as they are. Headings inside fenced code blocks are ignored.
      Everything outside the section is kept byte for byte. The block file is the
      whole new section, starting with the heading line and containing no other
      heading (a `###` in it is rejected with exit 2).
        section contains `pending`            -> replace, print the diff, applied
        no `pending`, verification passes      -> already_applied, file untouched
        anything else                          -> unexpected_state (exit 3)
      The record after replacement must pass verification, otherwise nothing is
      written (exit 2).
  --verify --capsule FILE < record
      Read the record from stdin and check only the disposition section, as bounded
      above: no `pending`, disposition `remove`, `decided at` equal to the capsule's
      decided_at, and the six freshness rows matching the capsule. Text outside the
      section, subsections included, may contain `pending` legitimately and is not
      inspected. The freshness table must therefore come before the first `###`,
      as the README template places it.

Both modes also scan the subsections of `## Worktree disposition` (from the first
`###` to the next `## `, fences skipped) for a freshness table: a table row whose
first cell is `Freshness value` or one of the six row labels (`branch tip`,
`ahead of ...`, `behind ...`, `dirty count`, `ignored artifact set`,
`path identity`). Prose and other tables there do not count. A table inside a
subsection means the record departs from the template; apply would leave it
behind next to the new one and verify would not see it, so apply reports
unexpected_state (exit 3, nothing written) and verify fails. The 2026-10-13
senses-taxonomy record departs from the template this way.

Capsule format: one `key: value` per line. Blank lines and lines starting with `#`
are skipped; any other line that is not `key: value` is an error. Keys read here
(each must appear exactly once, non-empty):
  decided_at            YYYY-MM-DDTHH:MM:SSZ, the decision time
  branch_tip            full SHA
  ahead                 commits ahead of origin/main
  behind                commits behind origin/main
  dirty_count           dirty file count
  ignored_artifact_set  the leading text of the record's row, e.g. `none` or `3`
  path_identity         e.g. `canonical, directory ttr-x-worktree, branch feat/x`
  record                repository-relative record path (apply mode only; the
                        --record path must end with it)
Other keys (consented_at, registered_path, physical_path, branch,
ignored_artifact, t_c, b_c, ...) are allowed and not read.

A freshness row matches when its cell, with backticks removed, starts with the
capsule value and the next character does not continue a word or path. So
`behind: 1` matches "`1`; origin/main advanced ..." but not "12".

Exit codes:
  0  applied, already_applied, or verify passed
  1  verify failed
  2  input error: unreadable file, missing or duplicated heading, malformed or
     incomplete capsule, invalid block file, record path mismatch
  3  unexpected_state: the section has no `pending` and does not pass verification
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HEADING = "## Worktree disposition"
PENDING_RE = re.compile(r"\bpending\b")
ATX_HEADING_RE = re.compile(r"^(#{1,6})(?:[ \t]|$)")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
KEY_LINE_RE = re.compile(r"^([a-z][a-z0-9_]*):[ \t]*(.*?)[ \t]*$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DISPOSITION_RE = re.compile(r"^`?([A-Za-z_]+)`?")
DECIDED_AT_RE = re.compile(r"decided at\s+`?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)`?")
CONTINUES_RE = re.compile(r"[A-Za-z0-9_./-]")

FRESHNESS_ROWS = {
    "branch tip": "branch_tip",
    "ahead of origin/main": "ahead",
    "behind origin/main": "behind",
    "dirty count": "dirty_count",
    "ignored artifact set": "ignored_artifact_set",
    "path identity": "path_identity",
}
VERIFY_KEYS = ("decided_at", *FRESHNESS_ROWS.values())
APPLY_KEYS = (*VERIFY_KEYS, "record")

SUBSECTION_TABLE_REASON = (
    "six-value table found inside a `###` subsection; the table must precede the first subsection"
)

EXIT_OK = 0
EXIT_VERIFY_FAILED = 1
EXIT_INPUT_ERROR = 2
EXIT_UNEXPECTED_STATE = 3


class InputError(Exception):
    pass


def read_text(path: str, what: str) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {what} {path}: {exc}") from exc


def parse_capsule(text: str, required: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, list[str]] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY_LINE_RE.match(line)
        if not match:
            raise InputError(f"capsule line {lineno} is not `key: value`: {line!r}")
        values.setdefault(match.group(1), []).append(match.group(2))
    capsule: dict[str, str] = {}
    for key in required:
        found = values.get(key, [])
        if not found:
            raise InputError(f"capsule is missing key `{key}`")
        if len(found) > 1:
            raise InputError(f"capsule key `{key}` appears {len(found)} times")
        if not found[0]:
            raise InputError(f"capsule key `{key}` is empty")
        capsule[key] = found[0]
    if not TIMESTAMP_RE.match(capsule["decided_at"]):
        raise InputError(f"capsule decided_at is not YYYY-MM-DDTHH:MM:SSZ: {capsule['decided_at']!r}")
    return capsule


def unfenced(lines: list[str]):
    """(index, line without line ending) for lines outside fenced code blocks."""
    fence: str | None = None
    for index, line in enumerate(lines):
        bare = line.rstrip("\r\n")
        match = FENCE_RE.match(bare)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield index, bare


def heading_lines(lines: list[str]) -> list[tuple[int, int]]:
    """(index, level) of every ATX heading outside fenced code blocks."""
    found: list[tuple[int, int]] = []
    for index, bare in unfenced(lines):
        heading = ATX_HEADING_RE.match(bare)
        if heading:
            found.append((index, len(heading.group(1))))
    return found


def find_section(text: str) -> tuple[int, int, int]:
    """Character offsets of the disposition section: (start, end, whole_end).

    [start, end) runs from its heading to the first heading after it (a `###`
    subsection or the next `## `); [end, whole_end) holds its subsections, up to
    the next heading of level 1 or 2."""
    lines = text.splitlines(keepends=True)
    headings = heading_lines(lines)
    starts = [i for i, level in headings if level == 2 and lines[i].rstrip() == HEADING]
    if not starts:
        raise InputError(f"record has no `{HEADING}` heading")
    if len(starts) > 1:
        raise InputError(f"record has {len(starts)} `{HEADING}` headings")
    start_line = starts[0]
    following = [i for i, _ in headings if i > start_line]
    end_line = following[0] if following else len(lines)
    parents = [i for i, level in headings if i > start_line and level <= 2]
    whole_end_line = parents[0] if parents else len(lines)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return offsets[start_line], offsets[end_line], offsets[whole_end_line]


def is_freshness_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    first = plain(stripped[1:].split("|", 1)[0]).lower()
    return (
        first == "freshness value"
        or first in FRESHNESS_ROWS
        or first.startswith("ahead of")
        or first.startswith("behind")
    )


def subsection_problems(subsections: str) -> list[str]:
    lines = subsections.splitlines(keepends=True)
    if any(is_freshness_row(bare) for _, bare in unfenced(lines)):
        return [SUBSECTION_TABLE_REASON]
    return []


def plain(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.replace("`", "")).strip()


def leading_match(cell: str, expected: str) -> bool:
    actual, wanted = plain(cell), plain(expected)
    if not actual.startswith(wanted):
        return False
    rest = actual[len(wanted):]
    return rest == "" or not CONTINUES_RE.match(rest)


def verify_section(section: str, capsule: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if PENDING_RE.search(section):
        problems.append("section contains `pending`")

    body = section.splitlines()[1:]
    first = next((line.strip() for line in body if line.strip()), "")
    disposition = DISPOSITION_RE.match(first)
    if not disposition or disposition.group(1) != "remove":
        problems.append(f"disposition is not `remove`: {first[:60]!r}")

    decided = DECIDED_AT_RE.search(section)
    if not decided:
        problems.append("no `decided at <timestamp>` in section")
    elif decided.group(1) != capsule["decided_at"]:
        problems.append(f"decided at {decided.group(1)} != capsule {capsule['decided_at']}")

    cells: dict[str, list[str]] = {}
    for line in body:
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        parts = stripped[1:-1].split("|")
        if len(parts) < 2:
            continue
        key = FRESHNESS_ROWS.get(plain(parts[0]).lower())
        if key:
            cells.setdefault(key, []).append(parts[1])
    for label, key in FRESHNESS_ROWS.items():
        found = cells.get(key, [])
        if len(found) != 1:
            problems.append(f"row `{label}` appears {len(found)} times")
        elif not leading_match(found[0], capsule[key]):
            problems.append(f"row `{label}` is {plain(found[0])!r}, capsule {capsule[key]!r}")
    return problems


def write_atomically(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_block(path: str) -> str:
    block = read_text(path, "block file")
    lines = block.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != HEADING:
        raise InputError(f"block file must start with the line `{HEADING}`")
    others = [level for index, level in heading_lines(lines) if index != 0]
    if any(level >= 3 for level in others):
        raise InputError("block file contains a `###` subsection heading; subsections stay in the record")
    if others:
        raise InputError("block file contains another `## ` heading")
    return block.rstrip("\r\n") + "\n"


def apply(record_path: str, block_path: str, capsule: dict[str, str]) -> int:
    record = Path(record_path)
    wanted = capsule["record"].strip("/")
    resolved = record.resolve().as_posix()
    if resolved != wanted and not resolved.endswith("/" + wanted):
        raise InputError(f"--record {record_path} does not end with capsule record {wanted}")

    text = read_text(record_path, "record")
    block = load_block(block_path)
    start, end, whole_end = find_section(text)
    old = text[start:end]

    misplaced = subsection_problems(text[end:whole_end])
    if misplaced:
        print("result=unexpected_state")
        for problem in misplaced:
            print(f"reason={problem}")
        return EXIT_UNEXPECTED_STATE

    if not PENDING_RE.search(old):
        problems = verify_section(old, capsule)
        if problems:
            print("result=unexpected_state")
            for problem in problems:
                print(f"reason={problem}")
            return EXIT_UNEXPECTED_STATE
        identical = old.rstrip("\r\n") + "\n" == block
        print("result=already_applied")
        print(f"block_identical={'yes' if identical else 'no'}")
        return EXIT_OK

    new = block + ("\n" if end < len(text) else "")
    problems = verify_section(new, capsule)
    if problems:
        detail = "; ".join(problems)
        raise InputError(f"block file does not pass verification, nothing written: {detail}")

    updated = text[:start] + new + text[end:]
    write_atomically(record, updated)
    sys.stdout.writelines(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{wanted}",
            tofile=f"b/{wanted}",
        )
    )
    print("result=applied")
    return EXIT_OK


def verify(text: str, capsule: dict[str, str]) -> int:
    start, end, whole_end = find_section(text)
    problems = verify_section(text[start:end], capsule) + subsection_problems(text[end:whole_end])
    if problems:
        print("verify=fail")
        for problem in problems:
            print(f"reason={problem}")
        return EXIT_VERIFY_FAILED
    print("verify=pass")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill or verify the Worktree disposition section of a campaign close-out record.",
    )
    parser.add_argument("--record", help="close-out record to edit (apply mode)")
    parser.add_argument("--block", help="file holding the new section, heading included (apply mode)")
    parser.add_argument("--capsule", required=True, help="recovery capsule (key: value lines)")
    parser.add_argument("--verify", action="store_true", help="verify the record read from stdin")
    return parser


def main(argv: list[str] | None = None, stdin: str | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify and (args.record or args.block):
        parser.error("--verify reads the record from stdin; do not pass --record or --block")
    if not args.verify and not (args.record and args.block):
        parser.error("apply mode needs --record and --block")
    try:
        if args.verify:
            capsule = parse_capsule(read_text(args.capsule, "capsule"), VERIFY_KEYS)
            if stdin is None:
                try:
                    stdin = sys.stdin.buffer.read().decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise InputError(f"record on stdin is not UTF-8: {exc}") from exc
            return verify(stdin, capsule)
        capsule = parse_capsule(read_text(args.capsule, "capsule"), APPLY_KEYS)
        return apply(args.record, args.block, capsule)
    except InputError as exc:
        print(f"error={exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
