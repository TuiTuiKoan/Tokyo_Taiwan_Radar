#!/usr/bin/env python3
"""Read-only issue intake for a feature kickoff.

Given a spec slug, list the open GitHub issues that carry the `spec:<slug>` label,
optional keyword candidates among issues that have no `spec:` label at all, likely
duplicates, and references between the listed issues. `--inventory` instead groups
every issue without a `spec:` label by its other labels.

The script only reads. It never labels, comments, edits or closes an issue; deciding
what an issue means and which task it maps to is the agent's and the user's job.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys

SPEC_PREFIX = "spec:"
DUPLICATE_THRESHOLD = 0.8
CONTAINED_MIN_LENGTH = 12  # a title this long, found whole inside another, is a duplicate hint
NO_LABEL = "(no label)"
FIELDS = "number,title,labels,updatedAt,url,body"


class KickoffError(Exception):
    """A problem the user can fix; reported without a traceback, exit status 2."""


def labels_of(issue: dict) -> list[str]:
    return [label["name"] for label in issue.get("labels", [])]


def has_spec_label(issue: dict) -> bool:
    return any(name.startswith(SPEC_PREFIX) for name in labels_of(issue))


def references_in(issue: dict) -> list[int]:
    return sorted({int(n) for n in re.findall(r"#(\d+)", issue.get("body") or "")})


def mentions(issue: dict, keyword: str) -> bool:
    needle = keyword.casefold()
    return needle in issue["title"].casefold() or needle in (issue.get("body") or "").casefold()


def build_report(issues: list[dict], slug: str, keywords: list[str]) -> dict:
    wanted = f"{SPEC_PREFIX}{slug}"
    covered = sorted((i for i in issues if wanted in labels_of(i)), key=lambda i: i["number"])
    candidates = sorted(
        (
            i
            for i in issues
            if not has_spec_label(i) and any(mentions(i, keyword) for keyword in keywords)
        ),
        key=lambda i: i["number"],
    )
    listed = covered + candidates
    numbers = {i["number"] for i in listed}
    duplicates = []
    for index, first in enumerate(listed):
        for second in listed[index + 1 :]:
            a, b = first["title"].casefold(), second["title"].casefold()
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            short, long_ = sorted((a, b), key=len)
            contained = len(short) >= CONTAINED_MIN_LENGTH and short in long_
            if ratio >= DUPLICATE_THRESHOLD or contained:
                duplicates.append((first["number"], second["number"], round(ratio, 2)))
    references = sorted(
        (i["number"], target)
        for i in listed
        for target in references_in(i)
        if target in numbers and target != i["number"]
    )
    return {"covered": covered, "candidates": candidates, "duplicates": duplicates, "references": references}


def inventory(issues: list[dict]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for item in sorted((i for i in issues if not has_spec_label(i)), key=lambda i: i["number"]):
        for name in labels_of(item) or [NO_LABEL]:
            groups.setdefault(name, []).append(item["number"])
    return dict(sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0])))


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def table(rows: list[dict]) -> list[str]:
    lines = ["| # | 標題 | 標籤 | 更新 |", "|---|---|---|---|"]
    for item in rows:
        lines.append(
            f"| [#{item['number']}]({item.get('url', '')}) | {cell(item['title'])} "
            f"| {cell(', '.join(labels_of(item)))} | {item.get('updatedAt', '')[:10]} |"
        )
    return lines


def render_report(report: dict, slug: str) -> str:
    lines = [f"## 涵蓋的 issue（標籤 `{SPEC_PREFIX}{slug}`）", ""]
    if report["covered"]:
        lines += table(report["covered"])
    else:
        lines.append(f"目前沒有帶 `{SPEC_PREFIX}{slug}` 標籤的開放 issue。")
    lines += ["", "## 候選：沒有任何 `spec:` 標籤、但關鍵字命中的 issue", ""]
    if report["candidates"]:
        lines += table(report["candidates"])
        lines.append("")
        lines.append("這些只是關鍵字命中，是否屬於這個功能要由人判斷；腳本不貼標籤。")
    else:
        lines.append("沒有（未指定關鍵字，或沒有命中）。")
    lines += ["", "## 疑似重複（標題相似度 ≥ %.2f，或一個標題完整出現在另一個裡；只是提示，需人工確認）" % DUPLICATE_THRESHOLD, ""]
    if report["duplicates"]:
        lines += [f"- #{a} 與 #{b}（相似度 {ratio}）" for a, b, ratio in report["duplicates"]]
    else:
        lines.append("沒有。")
    lines += ["", "## issue 之間的引用（內文提到的 `#N`，兩端都在上列時才顯示）", ""]
    if report["references"]:
        lines += [f"- #{source} 提到 #{target}" for source, target in report["references"]]
    else:
        lines.append("沒有。")
    return "\n".join(lines) + "\n"


def render_inventory(groups: dict[str, list[int]]) -> str:
    total = len({n for numbers in groups.values() for n in numbers})
    lines = [f"## 沒有 `{SPEC_PREFIX}` 標籤的開放 issue（共 {total} 個；一個 issue 有多個標籤時會重複出現在各組）", ""]
    lines += ["| 標籤 | 數量 | issue |", "|---|---|---|"]
    for name, numbers in groups.items():
        lines.append(f"| {cell(name)} | {len(numbers)} | {', '.join('#%d' % n for n in numbers)} |")
    return "\n".join(lines) + "\n"


def load_issues(path: str | None, limit: int) -> list[dict]:
    if path:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    gh = os.environ.get("FEATURE_KICKOFF_GH", "gh")
    command = [gh, "issue", "list", "--state", "open", "--limit", str(limit), "--json", FIELDS]
    try:
        done = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise KickoffError(f"cannot run gh ({error}); install the GitHub CLI or pass --issues-json")
    if done.returncode != 0:
        raise KickoffError(f"gh failed (exit {done.returncode}): {done.stderr.strip()[:300]}")
    return json.loads(done.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", help="spec slug; issues labelled spec:<slug> are the covered set")
    parser.add_argument("--keyword", action="append", default=[], help="find unlabeled issues mentioning this text (repeatable)")
    parser.add_argument("--inventory", action="store_true", help="group issues without a spec: label by their other labels")
    parser.add_argument("--issues-json", help="read issues from a file instead of calling gh (for tests)")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    if not args.slug and not args.inventory:
        parser.error("give --slug or --inventory")
    try:
        issues = load_issues(args.issues_json, args.limit)
    except KickoffError as error:
        print(f"feature_kickoff: {error}", file=sys.stderr)
        return 2
    if args.inventory:
        sys.stdout.write(render_inventory(inventory(issues)))
    else:
        sys.stdout.write(render_report(build_report(issues, args.slug, args.keyword), args.slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
