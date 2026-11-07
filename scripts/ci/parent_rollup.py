#!/usr/bin/env python3
"""Find parent issues whose child issues are all closed (agent-autonomy proposal §9).

Child issues point at their parent with a line "母 issue：#N" (written by the
heartbeat when it splits a multi-source tracking issue, e.g. #367, #381).
When every child of an open parent is closed, the parent gets one summary
comment and the ready-to-close label; the user closes it at the weekly
review. Nothing is closed here (user decision 2026-11-07).

Only children with at least one label count: labels can only be set by
collaborators and the heartbeat, so an outsider's issue that mentions
"母 issue：#381" can neither block nor trigger a rollup.

Usage:
    parent_rollup.py --issues all_issues.json --output actions.json
        all_issues.json: issues (open and closed) with number, title, state,
        state_reason, body, labels, pull_request.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dryrun_evidence import clean_code  # noqa: E402

MARKER = "<!-- parent-rollup -->"
READY_LABEL = "ready-to-close"
PARENT_RE = re.compile(r"母\s*issue\s*[：:]\s*#(\d+)")
REASON = {"completed": "完成", "not_planned": "不處理", "duplicate": "重複"}


def _title(text: object) -> str:
    """Issue title for a table cell: no fence, HTML, mention, pipe or link syntax.

    Intraword underscores (source keys) do not start emphasis in GFM, so they stay.
    """
    return re.sub(r"[|*\[\]~]", "", clean_code(text, 60))


def _labels(issue: dict) -> set[str]:
    return {lbl.get("name") for lbl in issue.get("labels") or [] if isinstance(lbl, dict)}


def children_by_parent(issues: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for issue in issues:
        if issue.get("pull_request") or not _labels(issue):
            continue
        m = PARENT_RE.search(issue.get("body") or "")
        if m and int(m.group(1)) != issue.get("number"):
            out.setdefault(int(m.group(1)), []).append(issue)
    return out


def comment_body(parent: int, children: list[dict]) -> str:
    lines = [MARKER, f"#{parent} 的 {len(children)} 張子 issue 已全部關閉，貼上 `{READY_LABEL}`，"
             "請在週審時確認後關閉這張母 issue（本 job 不會自己關）。", "",
             "| 子 issue | 結局 |", "| --- | --- |"]
    for c in sorted(children, key=lambda x: x["number"]):
        reason = REASON.get(c.get("state_reason") or "", c.get("state_reason") or "關閉")
        lines.append(f"| #{c['number']} {_title(c.get('title'))} | {reason} |")
    lines += ["", "若還有沒拆成子 issue 的項目，移除 label 並留言即可；本 job 不會再貼第二次。"]
    return "\n".join(lines) + "\n"


def decide(issues: list[dict]) -> list[dict]:
    by_number = {i.get("number"): i for i in issues if isinstance(i.get("number"), int)}
    actions = []
    for parent, children in sorted(children_by_parent(issues).items()):
        p = by_number.get(parent)
        if not p or p.get("pull_request") or p.get("state") != "open" or READY_LABEL in _labels(p):
            continue
        if children and all(c.get("state") == "closed" for c in children):
            actions.append({"parent": parent, "children": sorted(c["number"] for c in children),
                            "comment": comment_body(parent, children)})
    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issues", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    actions = decide(json.loads(args.issues.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"parents ready to close: {len(actions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
