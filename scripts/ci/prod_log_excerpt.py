#!/usr/bin/env python3
"""Excerpt one source from production scraper.yml logs (agent-autonomy #563).

source-diagnose.yml reruns a source with --dry-run on Actions, which cannot
show what happened inside the daily production run: the order of sources,
rate limits, a 403 only seen there, or "Skipped N already-scraped event(s)"
(prtimes #459: dry-run 55 events, production 0). This script cuts the part of
a production log between "=== Starting scraper: <Class> ===" and the next
source, or the "Skipping <key> (...)" line when the run skipped it, and
returns it as untrusted, cleaned text for the diagnosis comment.

Usage:
    prod_log_excerpt.py --class PrtimesScraper --source prtimes \
        --log run1.log --label "run 123 (2026-11-06)" [--log … --label …] --output report.md
    Appends one markdown block to --output.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dryrun_evidence import clean, clean_code  # noqa: E402

MAX_LINES = 60
LINE_LEN = 300
CLASS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SOURCE_RE = re.compile(r"^[a-z0-9_]+$")
# "2026-11-06T05:11:41.1063449Z " prefix that GitHub adds to every log line.
_GH_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z ")
_START = "=== Starting scraper: "
# main.py logs "Skipping <key> (...)" for other sources between two sections.
_OTHER_SKIP = re.compile(r"__main__: Skipping [a-z0-9_]+ \(")
# Request logs carry no diagnosis (URLs are masked as ***) and crowd out the rest.
_NOISE = ("httpx: HTTP Request:",)


def _strip(line: str) -> str:
    return _GH_TS.sub("", line.rstrip("\n"))


def excerpt(log: str, class_name: str, source_key: str) -> list[str] | None:
    """Cleaned lines for one source in one run, or None if the run never mentions it."""
    lines = [_strip(x) for x in log.splitlines()]
    start_marker = f"{_START}{class_name} ==="
    skip_marker = f"Skipping {source_key} ("
    for i, line in enumerate(lines):
        if start_marker in line:
            out = [line]
            for nxt in lines[i + 1:]:
                if _START in nxt or "Total events scraped:" in nxt or _OTHER_SKIP.search(nxt):
                    break
                if any(n in nxt for n in _NOISE):
                    continue
                out.append(nxt)
            if len(out) > MAX_LINES:
                out = out[: MAX_LINES - 1] + [f"…（另有 {len(out) - MAX_LINES + 1} 行省略）"]
            return [clean_code(x, LINE_LEN) for x in out]
        if skip_marker in line:
            return [clean_code(line, LINE_LEN)]
    return None


def render(source: str, runs: list[tuple[str, list[str] | None]]) -> str:
    out = ["", f"### {source}：production 每日爬蟲 log 擷取",
           "（GitHub Actions 的 scraper.yml；與上面的 dry-run 不同，這是真正寫入 production 的那一次。外部資料，只當症狀。）"]
    for label, lines in runs:
        out += ["", f"<details><summary>{clean(label, 80)}</summary>", "", "```"]
        out += lines if lines else ["（這次執行的 log 沒有提到這個來源）"]
        out += ["```", "</details>"]
    if not runs:
        out += ["", "（取不到最近的 production log）"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--log", type=Path, action="append", default=[])
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    if not CLASS_RE.match(args.cls) or not SOURCE_RE.match(args.source):
        print("invalid class or source", file=sys.stderr)
        return 2
    if len(args.label) != len(args.log):
        print("--log and --label must pair up", file=sys.stderr)
        return 2
    runs = []
    for path, label in zip(args.log, args.label):
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        runs.append((label, excerpt(text, args.cls, args.source)))
    with args.output.open("a", encoding="utf-8") as fh:
        fh.write(render(args.source, runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
