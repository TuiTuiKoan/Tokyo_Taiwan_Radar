#!/usr/bin/env python3
"""Audit the TTR Roadmap board's 主題 field against docs/specs/board-themes.json.

Rules, for every OPEN issue on the board:

* an issue with a label in `exempt.labels`, or whose number is in `exempt.issues`, is skipped and only listed;
* a `spec:<slug>` label whose slug is in the map decides the theme (derived, not typed by hand);
* an issue with no spec label and no theme needs a human decision;
* a theme that differs from the mapped one, a spec missing from the map, two specs that map to
  different themes, and a theme that is not in the theme list are reported, never changed.

The default run only reads. `--apply --yes` sets the theme on the *derived* rows only (a spec in the
map, no theme yet). It never edits issues or labels and never changes the board schema; the only write
is `gh project item-edit` for a theme that the map already decides.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SPEC_PREFIX = "spec:"
DEFAULT_MAP = Path(__file__).resolve().parents[1] / "docs" / "specs" / "board-themes.json"


class AuditError(Exception):
    """A problem the user can fix; reported without a traceback, exit status 2."""


def validate_map(mapping: dict) -> None:
    themes = mapping.get("themes", {})
    for slug, theme in mapping.get("specs", {}).items():
        if theme not in themes:
            raise AuditError(f"spec {slug!r} maps to theme {theme!r}, which is not in the theme list")
    for key in mapping.get("exempt", {}).get("issues", {}):
        if not str(key).isdigit():
            raise AuditError(f"exempt.issues key {key!r} must be an issue number")


def spec_labels(item: dict) -> list[str]:
    return [name for name in item["labels"] if name.startswith(SPEC_PREFIX)]


def audit_items(items: list[dict], mapping: dict) -> dict:
    validate_map(mapping)
    themes, specs = mapping["themes"], mapping["specs"]
    report = {"derive": [], "mismatch": [], "unmapped_spec": [], "ambiguous": [], "needs_decision": [], "unknown_theme": [], "exempt": [], "ok": 0}
    exempt_labels = set(mapping.get("exempt", {}).get("labels", []))
    exempt_issues = {int(k): v for k, v in mapping.get("exempt", {}).get("issues", {}).items()}
    seen_specs: set[str] = set()
    for item in sorted((i for i in items if i["state"] == "OPEN"), key=lambda i: i["number"]):
        row = {k: item[k] for k in ("number", "title", "url", "item_id")}
        theme = item["theme"]
        labels = spec_labels(item)
        if item["number"] in exempt_issues or exempt_labels & set(item["labels"]):
            reason = exempt_issues.get(item["number"]) or "label: " + ", ".join(sorted(exempt_labels & set(item["labels"])))
            report["exempt"].append({**row, "reason": reason})
            continue
        if theme is not None and theme not in themes:
            report["unknown_theme"].append({**row, "theme": theme})
            continue
        if not labels:
            if theme is None:
                report["needs_decision"].append({**row, "labels": item["labels"]})
            else:
                report["ok"] += 1
            continue
        unmapped = [label for label in labels if label[len(SPEC_PREFIX):] not in specs]
        for label in unmapped:
            report["unmapped_spec"].append({**row, "spec": label})
        mapped = {specs[label[len(SPEC_PREFIX):]] for label in labels if label[len(SPEC_PREFIX):] in specs}
        seen_specs.update(label[len(SPEC_PREFIX):] for label in labels)
        if unmapped:
            continue
        if len(mapped) > 1:
            report["ambiguous"].append({**row, "specs": labels, "themes": sorted(mapped)})
            continue
        expected = next(iter(mapped))
        if theme is None:
            report["derive"].append({**row, "theme": expected, "specs": labels})
        elif theme != expected:
            report["mismatch"].append({**row, "theme": theme, "expected": expected, "specs": labels})
        else:
            report["ok"] += 1
    report["unused_map_specs"] = sorted(slug for slug in specs if slug not in seen_specs)
    return report


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def link(row: dict) -> str:
    return f"[#{row['number']}]({row['url']})"


def section(title: str, rows: list[str], empty: str = "沒有。") -> list[str]:
    return ["", f"## {title}", "", *(rows or [empty])]


def render_report(report: dict) -> str:
    lines = [f"# 看板主題稽核（正常 {report['ok']} 個）"]
    lines += section(
        "可由對照表推導、尚未設定主題（`--apply --yes` 才會寫入）",
        [f"- {link(r)} {cell(r['title'])} → **{r['theme']}**（{', '.join(r['specs'])}）" for r in report["derive"]],
    )
    lines += section(
        "主題與對照表不一致（不會自動改，需要人判斷）",
        [f"- {link(r)} {cell(r['title'])}：目前 {r['theme']}，對照表為 {r['expected']}（{', '.join(r['specs'])}）" for r in report["mismatch"]],
    )
    lines += section(
        "兩個 spec 對應到不同主題（需要人判斷）",
        [f"- {link(r)} {cell(r['title'])}：{', '.join(r['specs'])} → {' / '.join(r['themes'])}" for r in report["ambiguous"]],
    )
    lines += section(
        "spec 標籤不在對照表（需要先決定這個 spec 的主題，再更新 `board-themes.json`）",
        [f"- {link(r)} {cell(r['title'])}：{r['spec']}" for r in report["unmapped_spec"]],
    )
    lines += section(
        "需要決定：沒有 spec 標籤、也沒有主題",
        [f"- {link(r)} {cell(r['title'])}（{', '.join(r['labels']) or '無標籤'}）" for r in report["needs_decision"]],
    )
    lines += section(
        "主題不在主題清單（拼錯或舊選項）",
        [f"- {link(r)} {cell(r['title'])}：{r['theme']}" for r in report["unknown_theme"]],
    )
    lines += section(
        "豁免（資訊）：不需要主題，也不會被稽核",
        [f"- {link(r)} {cell(r['title'])}：{cell(r['reason'])}" for r in report["exempt"]],
    )
    lines += section(
        "對照表中目前沒有開放 issue 的 spec（資訊）",
        [f"- {slug}" for slug in report["unused_map_specs"]],
    )
    return "\n".join(lines) + "\n"


def parse_nodes(nodes: list[dict]) -> list[dict]:
    items = []
    for node in nodes:
        content = node.get("content") or {}
        if "number" not in content:
            continue
        items.append(
            {
                "number": content["number"],
                "title": content.get("title", ""),
                "state": content.get("state", ""),
                "url": content.get("url", ""),
                "labels": [label["name"] for label in (content.get("labels") or {}).get("nodes", [])],
                "theme": (node.get("theme") or {}).get("name"),
                "item_id": node["id"],
            }
        )
    return items


def gh(*args: str, stdin: str | None = None) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, input=stdin, check=False)
    except OSError as error:
        raise AuditError(f"cannot run gh ({error})")
    if done.returncode != 0:
        raise AuditError(f"gh failed: {done.stderr.strip()[:300]}")
    return done.stdout


def graphql(query: str, variables: dict) -> dict:
    out = json.loads(gh("api", "graphql", "--input", "-", stdin=json.dumps({"query": query, "variables": variables})))
    if "errors" in out:
        raise AuditError(json.dumps(out["errors"], ensure_ascii=False)[:300])
    return out["data"]


def load_board(board: dict) -> tuple[list[dict], dict]:
    """Read every item through GraphQL (`gh project item-list` mangles the field's JSON key)."""
    project = next(
        (p for p in json.loads(gh("project", "list", "--owner", board["owner"], "--format", "json"))["projects"] if p["number"] == board["project"]),
        None,
    )
    if project is None:
        raise AuditError(f"project {board['project']} of {board['owner']} not found")
    fields = json.loads(gh("project", "field-list", str(board["project"]), "--owner", board["owner"], "--format", "json"))["fields"]
    field = next((f for f in fields if f["name"] == board["field"]), None)
    if field is None:
        raise AuditError(f"the board has no field named {board['field']!r}; was it renamed again?")
    nodes, cursor = [], None
    query = """query($p:ID!,$c:String,$n:String!){ node(id:$p){ ... on ProjectV2 { items(first:100, after:$c){ pageInfo{hasNextPage endCursor}
      nodes{ id content{ ... on Issue { number title state url labels(first:30){ nodes{ name } } } }
             theme: fieldValueByName(name:$n){ ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }"""
    while True:
        data = graphql(query, {"p": project["id"], "c": cursor, "n": board["field"]})["node"]["items"]
        nodes += data["nodes"]
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    meta = {"project_id": project["id"], "field_id": field["id"], "option_ids": {o["name"]: o["id"] for o in field["options"]}}
    return parse_nodes(nodes), meta


def apply_derived(rows: list[dict], runner, project_id: str, field_id: str, option_ids: dict[str, str]) -> None:
    """Set the derived theme on each row; `runner` receives the gh arguments (injected so tests make no calls)."""
    missing = sorted({r["theme"] for r in rows if r["theme"] not in option_ids})
    if missing:
        raise AuditError(f"the board has no option for theme(s) {missing}; add the option first")
    for row in rows:
        runner(["project", "item-edit", "--id", row["item_id"], "--project-id", project_id, "--field-id", field_id,
                "--single-select-option-id", option_ids[row["theme"]]])


def has_findings(report: dict) -> bool:
    return any(report[key] for key in ("derive", "mismatch", "unmapped_spec", "ambiguous", "needs_decision", "unknown_theme"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="path to board-themes.json")
    parser.add_argument("--items-json", help="read items from a file instead of the live board (offline; cannot be combined with --apply)")
    parser.add_argument("--apply", action="store_true", help="set the theme on the derived rows (needs --yes)")
    parser.add_argument("--yes", action="store_true", help="confirm --apply")
    parser.add_argument("--strict", action="store_true", help="exit 1 when there are findings")
    args = parser.parse_args()
    try:
        if args.apply and args.items_json:
            raise AuditError("--apply needs the live board; it cannot be combined with --items-json")
        if args.apply and not args.yes:
            raise AuditError("--apply writes to the board; add --yes to confirm")
        mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
        validate_map(mapping)
        if args.items_json:
            items, meta = json.loads(Path(args.items_json).read_text(encoding="utf-8")), None
        else:
            items, meta = load_board(mapping["board"])
        report = audit_items(items, mapping)
        sys.stdout.write(render_report(report))
        if args.apply:
            apply_derived(report["derive"], lambda call: gh(*call), **meta)
            print(f"\n已寫入 {len(report['derive'])} 個主題。")
    except AuditError as error:
        print(f"board_audit: {error}", file=sys.stderr)
        return 2
    return 1 if args.strict and has_findings(report) else 0


if __name__ == "__main__":
    sys.exit(main())
