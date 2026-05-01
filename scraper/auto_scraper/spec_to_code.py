"""Spec → code generator and AST safety checker for Layer B auto-scrapers.

Validates a JSON spec against ``spec_schema.json``, renders ``template.py.j2``
into a Python scraper module, and statically inspects generated (or hand-edited)
code to ensure it imports only from the allowlist and contains no forbidden
calls (subprocess / eval / network libs / etc.).

TODO (Phase 1.3, deferred): wire feasibility hints back into source_profile so
the Researcher agent can flag URLs as auto-scrapable before running this tool.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Iterable

import jinja2
import jsonschema

_HERE = Path(__file__).parent
_SCHEMA_PATH = _HERE / "spec_schema.json"
_TEMPLATE_PATH = _HERE / "template.py.j2"
_ALLOWLIST_PATH = _HERE / "allowlist.txt"

_FORBIDDEN_CALLS = {
    "os.system",
    "eval",
    "exec",
    "__import__",
    "compile",
    "open",
}
_FORBIDDEN_CALL_PREFIXES = ("subprocess.",)
_FORBIDDEN_NETWORK_MODULES = {"requests", "urllib", "urllib3", "httpx", "aiohttp"}


def _load_allowlist() -> set[str]:
    text = _ALLOWLIST_PATH.read_text(encoding="utf-8")
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def render(spec: dict) -> str:
    """Validate ``spec`` and render the scraper template.

    Raises ``ValueError`` with a concrete message on schema violation.
    """
    schema = _load_schema()
    try:
        jsonschema.validate(instance=spec, schema=schema)
    except jsonschema.ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise ValueError(f"spec invalid at {path}: {exc.message}") from exc

    spec = dict(spec)
    spec.setdefault("search_keyword", "%E5%8F%B0%E6%B9%BE")
    spec.setdefault("max_pages", 5)
    spec.setdefault("detail_link_selector", "")

    fs = spec["field_selectors"]
    items = ", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in fs.items())
    spec["field_selectors_py"] = "{" + items + "}"
    spec["card_selector_py"] = json.dumps(spec["card_selector"])
    spec["detail_link_selector_py"] = json.dumps(spec["detail_link_selector"])
    spec["date_regex_py"] = json.dumps(spec["date_regex"])
    spec["source_id_url_pattern_py"] = json.dumps(spec["source_id_url_pattern"])

    env = jinja2.Environment(
        autoescape=False,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.from_string(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.render(**spec)


def _resolve_attr_chain(node: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def ast_check(code: str) -> list[str]:
    """Return a list of violation messages. Empty list = OK."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"syntax: {exc.msg} (line {exc.lineno})"]

    allowlist = _load_allowlist()
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _FORBIDDEN_NETWORK_MODULES:
                    violations.append(f"forbidden import: {alias.name}")
                    continue
                if alias.name not in allowlist and top not in allowlist:
                    violations.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level > 0:
                key = "." + module.split(".")[0] if module else "." + (node.names[0].name if node.names else "")
                if key not in allowlist:
                    violations.append(f"forbidden import: {key}")
                continue
            top = module.split(".")[0]
            if top in _FORBIDDEN_NETWORK_MODULES:
                violations.append(f"forbidden import: {module}")
                continue
            if module not in allowlist and top not in allowlist:
                violations.append(f"forbidden import: {module}")
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = _resolve_attr_chain(node.func)
            if not name:
                continue
            if name in _FORBIDDEN_CALLS:
                violations.append(f"forbidden call: {name}")
            elif any(name.startswith(p) for p in _FORBIDDEN_CALL_PREFIXES):
                violations.append(f"forbidden call: {name}")
        elif isinstance(node, ast.Attribute):
            chain = _resolve_attr_chain(node)
            if chain:
                top = chain.split(".")[0]
                if top in _FORBIDDEN_NETWORK_MODULES:
                    violations.append(f"forbidden network module: {top}")
        elif isinstance(node, ast.Name) and node.id == "__import__":
            violations.append("forbidden: dynamic import")

    seen: set[str] = set()
    out: list[str] = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _cli(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auto_scraper.spec_to_code")
    parser.add_argument("--spec", help="Path to spec JSON file")
    parser.add_argument("--out", help="Output Python file path")
    parser.add_argument("--check", help="Run AST safety check on an existing Python file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check:
        code = Path(args.check).read_text(encoding="utf-8")
        violations = ast_check(code)
        if violations:
            for v in violations:
                print(v, file=sys.stderr)
            return 1
        return 0

    if not args.spec or not args.out:
        parser.error("--spec and --out are required (or use --check)")

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    try:
        code = render(spec)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    violations = ast_check(code)
    if violations:
        for v in violations:
            print(v, file=sys.stderr)
        return 3

    Path(args.out).write_text(code, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
