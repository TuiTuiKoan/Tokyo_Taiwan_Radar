#!/usr/bin/env python3
"""Static inventory of code that can write the `events` table (japan-scope-gate #402).

Scans scraper/*.py (AST), web/**/*.ts(x) (regex) and .github/workflows/*.yml, and maps each
workflow to the scraper modules it can reach through `python <script>.py` steps and local
imports. It is a pre-apply checklist aid, not proof: dynamic imports, `python -c` snippets,
shell-outs and anything outside this repository (launchd, Dashboard, other services) are not seen.

    python3 scripts/inventory_events_writers.py            # markdown
    python3 scripts/inventory_events_writers.py --json
    python3 scripts/inventory_events_writers.py --workflows    # one name per line, for shell loops

Reachability over-approximates: a workflow is listed when it can import a module that writes
`events`, even if the step never calls that code path. For a pause list that is the safe side.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "scraper"
WRITE_METHODS = {"insert", "update", "upsert", "delete"}
SQL_WRITE = re.compile(r"\b(update|insert\s+into|delete\s+from)\s+(public\.)?events\b", re.I)
PY_STEP = re.compile(r"python3?\s+(?:-u\s+)?([A-Za-z0-9_./-]+\.py)")
WEB_WRITE = re.compile(
    r"""\.from\(\s*["']events["']\s*\)(?:(?!\.from\().){0,400}?\.(insert|update|upsert|delete)\(""", re.S
)


def _is_events_table_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"table", "from_"}
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "events"
    )


def _chain_reaches_events(expr: ast.AST, events_names: set[str]) -> bool:
    while True:
        if _is_events_table_call(expr):
            return True
        if isinstance(expr, ast.Call):
            expr = expr.func
        elif isinstance(expr, ast.Attribute):
            expr = expr.value
        elif isinstance(expr, ast.Name):
            return expr.id in events_names
        else:
            return False


def scan_python(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    events_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _chain_reaches_events(node.value, set())
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    writes, rpcs, sql = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in WRITE_METHODS and _chain_reaches_events(node.func.value, events_names):
                writes.append({"line": node.lineno, "op": node.func.attr})
            if node.func.attr == "rpc" and node.args and isinstance(node.args[0], ast.Constant):
                rpcs.append(str(node.args[0].value))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_WRITE.search(node.value):
            sql.append({"line": node.lineno})
    return {"writes": writes, "rpcs": sorted(set(rpcs)), "sql": sql}


def local_imports(path: Path, modules: dict[str, Path]) -> set[str]:
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
        for name in names:
            if name in modules:
                found.add(name)
    return found


def module_table() -> dict[str, Path]:
    modules = {p.stem: p for p in SCRAPER.glob("*.py")}
    modules.update({f"sources.{p.stem}": p for p in (SCRAPER / "sources").glob("*.py")})
    return modules


def reachable(entry: str, modules: dict[str, Path], graph: dict[str, set[str]]) -> set[str]:
    seen, todo = set(), [entry]
    while todo:
        current = todo.pop()
        if current in seen or current not in modules:
            continue
        seen.add(current)
        todo.extend(graph.get(current, ()))
    return seen


def scan_workflows(modules: dict[str, Path]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        entries = sorted({Path(m).stem for m in PY_STEP.findall(wf.read_text(encoding="utf-8")) if Path(m).stem in modules})
        if entries:
            out[wf.name] = entries
    return out


def scan_web() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "web").rglob("*.ts*")):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        ops = sorted({m.group(1) for m in WEB_WRITE.finditer(text)})
        if ops:
            rows.append({"file": str(path.relative_to(ROOT)), "ops": ops, "maintenance_lock": "maintenanceLock" in text or "admin_reports_maintenance" in text})
    return rows


def build() -> dict:
    modules = module_table()
    scans = {name: scan_python(path) for name, path in modules.items()}
    graph = {name: local_imports(path, modules) for name, path in modules.items()}
    writers = {n for n, s in scans.items() if s["writes"] or s["sql"]}
    workflows = {}
    for wf, entries in scan_workflows(modules).items():
        reach = set().union(*(reachable(e, modules, graph) for e in entries))
        workflows[wf] = {"entries": entries, "writers": sorted(reach & writers)}
    return {
        "python_writers": {
            n: {"file": str(modules[n].relative_to(ROOT)), **scans[n]} for n in sorted(writers)
        },
        "rpc_callers": {n: s["rpcs"] for n, s in sorted(scans.items()) if s["rpcs"]},
        "workflows": workflows,
        "web_writers": scan_web(),
        "not_covered": [
            "python -c / heredoc snippets, dynamic imports, shell-outs",
            "launchd job scripts/launchd/com.ttr.home-ip-scrape.plist (weekly, runs main.py --source …)",
            "Dashboard SQL, other machines and external services (user statement only)",
            "database functions: only confirm_scope_report (098) and apply_scope_cleanup (103) were found to write events",
        ],
    }


def render_markdown(data: dict) -> str:
    lines = ["# events writer inventory", "", "## Workflows that can reach a scraper module writing `events`", ""]
    lines += ["| workflow | entry scripts | writer modules reached |", "| --- | --- | --- |"]
    for wf, info in data["workflows"].items():
        if info["writers"]:
            lines.append(f"| `{wf}` | {', '.join(info['entries'])} | {', '.join(info['writers'])} |")
    quiet = [wf for wf, info in data["workflows"].items() if not info["writers"]]
    lines += ["", "Workflows with python steps but no reachable events writer: " + (", ".join(f"`{w}`" for w in quiet) or "none"), ""]
    lines += ["## Python modules that write `events` directly", "", "| module | calls (line:op) | raw SQL lines |", "| --- | --- | --- |"]
    for name, info in data["python_writers"].items():
        calls = ", ".join(f"{w['line']}:{w['op']}" for w in info["writes"]) or "-"
        sql = ", ".join(str(s["line"]) for s in info["sql"]) or "-"
        lines.append(f"| `{info['file']}` | {calls} | {sql} |")
    lines += ["", "## Web routes and actions that write `events`", "", "| file | ops | references the maintenance lock |", "| --- | --- | --- |"]
    for row in data["web_writers"]:
        lines.append(f"| `{row['file']}` | {', '.join(row['ops'])} | {'yes' if row['maintenance_lock'] else '**no**'} |")
    lines += ["", "## Not covered by this scan", ""] + [f"- {item}" for item in data["not_covered"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--workflows", action="store_true", help="workflow file names that can reach an events writer")
    args = parser.parse_args(argv)
    data = build()
    if args.workflows:
        print("\n".join(wf for wf, info in data["workflows"].items() if info["writers"]))
        return 0
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render_markdown(data), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
