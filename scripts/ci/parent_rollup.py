#!/usr/bin/env python3
"""Reminders for parent issues whose sources all have a conclusion (agent-autonomy §9).

A parent tracking issue (e.g. #367, #381) lists source keys in its body, and
child issues point back at it with a line "母 issue：#N". "Every child is
closed" is not the same as "the parent is done": #381 lists 30 sources but
only 16 children say "母 issue：#381" (plan-critique-2 G16). So a parent is
ready only when

  * every child issue is closed, and
  * every source key in its body (intersected with the registered scrapers
    in scraper/main.py) has a conclusion: a closed issue titled "<key>：…",
    or an entry in scraper/source_expectations.json.

Actions (the workflow posts each at most once, keyed by the marker):
  ready       comment + add ready-to-close. The parent is never closed here;
              the user closes it at the weekly review (decision 2026-11-07).
  unresolved  all children closed but some sources still open: comment listing them.
  withdraw    the parent has ready-to-close but a child reopened or a source
              lost its conclusion: comment + remove the label (G17).

Only children with at least one label count (labels can only be set by
collaborators and the heartbeat), so an outsider's issue that mentions
"母 issue：#381" can neither block nor trigger anything.

Usage:
    parent_rollup.py --issues all.json --main scraper/main.py \
        --expectations scraper/source_expectations.json --output actions.json
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dryrun_evidence import clean_code  # noqa: E402

READY_LABEL = "ready-to-close"
PARENT_RE = re.compile(r"母\s*issue\s*[：:]\s*#(\d+)")
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
REASON = {"completed": "完成", "not_planned": "不處理", "duplicate": "重複"}


def scraper_keys(main_py: str) -> set[str]:
    """Source keys of SCRAPERS in scraper/main.py, without importing it.

    Mirrors main._scraper_key: drop a trailing "Scraper", snake_case the rest.
    """
    keys: set[str] = set()
    for node in ast.walk(ast.parse(main_py)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCRAPERS"
                                                for t in node.targets):
            for elt in getattr(node.value, "elts", []):
                if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                    name = re.sub(r"Scraper$", "", elt.func.id)
                    keys.add(re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
    return keys


def _labels(issue: dict) -> set[str]:
    return {lbl.get("name") for lbl in issue.get("labels") or [] if isinstance(lbl, dict)}


def _title(text: object) -> str:
    """Issue title for a table cell: no fence, HTML, mention, pipe or link syntax.

    Intraword underscores (source keys) do not start emphasis in GFM, so they stay.
    """
    return re.sub(r"[|*\[\]~]", "", clean_code(text, 60))


def _hash(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:10]


def children_by_parent(issues: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for issue in issues:
        if issue.get("pull_request") or not _labels(issue):
            continue
        m = PARENT_RE.search(issue.get("body") or "")
        if m and int(m.group(1)) != issue.get("number"):
            out.setdefault(int(m.group(1)), []).append(issue)
    return out


def body_keys(body: str, known: set[str]) -> list[str]:
    seen: list[str] = []
    for tok in TOKEN_RE.findall(body or ""):
        if tok in known and tok not in seen:
            seen.append(tok)
    return seen


def unresolved_keys(keys: list[str], issues: list[dict], expectations: dict) -> list[str]:
    concluded = {k for k in keys if k in expectations}
    for issue in issues:
        if issue.get("pull_request") or issue.get("state") != "closed" or not _labels(issue):
            continue
        title = issue.get("title") or ""
        for k in keys:
            if title.startswith(f"{k}："):
                concluded.add(k)
    return [k for k in keys if k not in concluded]


def _marker(kind: str, digest: str) -> str:
    return f"<!-- parent-rollup:{kind}:{digest} -->"


def _child_table(children: list[dict]) -> list[str]:
    lines = ["| 子 issue | 結局 |", "| --- | --- |"]
    for c in sorted(children, key=lambda x: x["number"]):
        reason = REASON.get(c.get("state_reason") or "", c.get("state_reason") or "關閉")
        lines.append(f"| #{c['number']} {_title(c.get('title'))} | {reason} |")
    return lines


def decide(issues: list[dict], known: set[str], expectations: dict) -> list[dict]:
    by_number = {i.get("number"): i for i in issues if isinstance(i.get("number"), int)}
    actions = []
    for parent, children in sorted(children_by_parent(issues).items()):
        p = by_number.get(parent)
        if not p or p.get("pull_request") or p.get("state") != "open":
            continue
        open_children = sorted(c["number"] for c in children if c.get("state") != "closed")
        keys = body_keys(p.get("body") or "", known)
        missing = unresolved_keys(keys, issues, expectations)
        labelled = READY_LABEL in _labels(p)

        if labelled and (open_children or missing):
            marker = _marker("withdraw", _hash(open_children, missing))
            body = [marker, f"撤回 `{READY_LABEL}`：#{parent} 還沒完成。"]
            if open_children:
                body.append("重開或新增的子 issue：" + "、".join(f"#{n}" for n in open_children))
            if missing:
                body.append("仍未結論的來源：" + "、".join(f"`{k}`" for k in missing))
            actions.append({"parent": parent, "action": "withdraw", "marker": marker,
                            "comment": "\n\n".join(body) + "\n"})
            continue
        if labelled or open_children:
            continue
        if missing:
            marker = _marker("unresolved", _hash(missing))
            body = [marker,
                    f"#{parent} 的 {len(children)} 張子 issue 都已關閉，但內文列的來源還有 {len(missing)} 個沒有結論"
                    "（沒有已關閉的「<來源>：」issue，也不在 `scraper/source_expectations.json`）：",
                    "、".join(f"`{k}`" for k in missing),
                    "所以先不貼 ready-to-close。這些來源有結論後會自動再檢查。"]
            actions.append({"parent": parent, "action": "unresolved", "marker": marker,
                            "comment": "\n\n".join(body) + "\n"})
            continue
        closed_state = sorted((c["number"], c.get("closed_at")) for c in children)
        marker = _marker("ready", _hash(closed_state, keys))
        lines = [marker,
                 f"#{parent} 的 {len(children)} 張子 issue 都已關閉，內文列的 {len(keys)} 個來源也都有結論，"
                 f"貼上 `{READY_LABEL}`。請在週審時確認後關閉這張母 issue（本 job 不會自己關）。", ""]
        lines += _child_table(children)
        lines += ["", "若還有沒處理的項目，移除 label 並留言即可；同一個狀態不會再貼第二次。"]
        actions.append({"parent": parent, "action": "ready", "marker": marker,
                        "comment": "\n".join(lines) + "\n"})
    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issues", type=Path, required=True)
    ap.add_argument("--main", type=Path, required=True, help="scraper/main.py of the default branch")
    ap.add_argument("--expectations", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    known = scraper_keys(args.main.read_text(encoding="utf-8"))
    expectations = json.loads(args.expectations.read_text(encoding="utf-8")).get("sources", {})
    actions = decide(issues, known, expectations)
    args.output.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"registered scrapers: {len(known)}; parent actions: {len(actions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
