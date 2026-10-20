#!/usr/bin/env python3
"""
Enum parity checker — event_form and category vocabularies across web, scraper,
DB migrations and i18n. Shared by the pre-commit hook and scripts/tests.

web/lib/types.ts (EVENT_FORMS, CATEGORIES) is the reference. Every other copy is
maintained by hand, and the annotator silently strips an unknown event_form to
["other"], so drift does not fail loudly at runtime. This script is the check.

Sources are read as plain text (ast / regex / json) so the hook needs nothing
beyond the standard library — annotator.py is never imported.

Not covered: the live database. A migration file can be correct while
production has not applied it (2026-06-04 incident); verify that separately.

Modes:
  (default)   Read the working tree under --root (default: repo root)
  --staged    Read the git index (pre-commit use); exits 0 without checking
              unless a watched path is staged

Exit codes:
  0  All sources agree
  1  Drift detected, or a source could not be parsed
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> repo root

TYPES_TS = "web/lib/types.ts"
ANNOTATOR = "scraper/annotator.py"
DATABASE = "scraper/database.py"
TAXONOMY = "scraper/taxonomy.md"
MIGRATIONS_DIR = "supabase/migrations"
LOCALE_FILES = ["web/messages/ja.json", "web/messages/zh.json", "web/messages/en.json"]
ROUTE_FILES = [
    f"web/app/api/{scope}/{name}/route.ts"
    for scope in ("admin", "account")
    for name in ("extract-from-image", "annotate-event")
]
ROUTE_JOINS = ["${EVENT_FORMS.join(", "${CATEGORIES.join("]

WATCHED_PREFIXES = (MIGRATIONS_DIR + "/", "web/messages/")
WATCHED_FILES = {TYPES_TS, ANNOTATOR, DATABASE, TAXONOMY, *ROUTE_FILES, "scripts/check_enum_parity.py"}

# Declared, intentional differences from the types.ts reference. Each needs a reason.
PROMPT_EVENT_FORM_OMITTED = {
    "publication": (
        "assigned in code by publication sources and _finalize_publication_update(), "
        "never chosen by the model"
    ),
}
CATEGORIES_EXTRA_RE = re.compile(r"^group_[a-z_]+$")  # filter-UI group headings
CATEGORY_DESC_EXTRA = {"noEvents"}  # empty-state copy; "<category>_long" keys are also allowed

CONSTRAINT_ADD = "ADD CONSTRAINT events_event_form_check"
PROMPT_LIST_RE = re.compile(r"EVENT FORM RULES:.*?Pick one or more from:\n(.*?)\nDecision guides:", re.S)
TAXONOMY_DEF_RE = re.compile(r'^\s*- "([a-z_]+)"(?: \([^)]*\))? =', re.M)


class ParseError(Exception):
    pass


class TreeReader:
    def __init__(self, root: Path):
        self.root = root

    def read(self, rel: str) -> str:
        path = self.root / rel
        if not path.is_file():
            raise ParseError(f"{rel}: file not found")
        return path.read_text(encoding="utf-8")

    def migrations(self) -> list[str]:
        base = self.root / MIGRATIONS_DIR
        return sorted(f"{MIGRATIONS_DIR}/{p.name}" for p in base.glob("*.sql")) if base.is_dir() else []


class IndexReader:
    def __init__(self, root: Path):
        self.root = root

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=self.root)

    def read(self, rel: str) -> str:
        result = self._git("show", f":0:{rel}")
        if result.returncode != 0:
            raise ParseError(f"{rel}: not in the git index")
        return result.stdout

    def migrations(self) -> list[str]:
        out = self._git("ls-files", "--", f"{MIGRATIONS_DIR}/*.sql").stdout
        return sorted(line for line in out.splitlines() if line)

    def staged_paths(self) -> list[str]:
        out = self._git("diff", "--cached", "--name-only", "--diff-filter=ACMDR").stdout
        return [line for line in out.splitlines() if line]


def ts_const_array(text: str, name: str, rel: str) -> list[str]:
    match = re.search(rf"export const {name}\b[^=]*=\s*\[(.*?)\]", text, re.S)
    if not match:
        raise ParseError(f"{rel}: could not find `export const {name} = [...]`")
    return re.findall(r'"([a-z_]+)"', match.group(1))


def py_constant(text: str, name: str, rel: str) -> list[str]:
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call) and getattr(value.func, "id", None) in ("frozenset", "set"):
                value = value.args[0]
            try:
                return list(ast.literal_eval(value))
            except ValueError as exc:
                raise ParseError(f"{rel}: {name} is not a literal list") from exc
    raise ParseError(f"{rel}: could not find top-level {name}")


def prompt_event_forms(text: str) -> list[str]:
    match = PROMPT_LIST_RE.search(text)
    if not match:
        raise ParseError(f"{ANNOTATOR}: could not find the EVENT FORM RULES 'Pick one or more from:' list")
    return re.findall(r"[a-z_]+", match.group(1))


def latest_constraint(reader) -> tuple[str, list[str]]:
    for rel in reversed(reader.migrations()):
        text = reader.read(rel)
        pos = text.rfind(CONSTRAINT_ADD)
        if pos < 0:
            continue
        match = re.search(r"ARRAY\[(.*?)\]", text[pos:], re.S)
        if not match:
            raise ParseError(f"{rel}: {CONSTRAINT_ADD} has no ARRAY[...] list")
        return rel, re.findall(r"'([a-z_]+)'", match.group(1))
    raise ParseError(f"{MIGRATIONS_DIR}: no migration contains {CONSTRAINT_ADD}")


def taxonomy_definitions(text: str) -> list[str]:
    begin, end = text.find("<!-- PROMPT:BEGIN -->"), text.find("<!-- PROMPT:END -->")
    if begin < 0 or end < begin:
        raise ParseError(f"{TAXONOMY}: PROMPT:BEGIN / PROMPT:END markers not found")
    return TAXONOMY_DEF_RE.findall(text[begin:end])


def locale_keys(text: str, section: str, rel: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"{rel}: invalid JSON ({exc})") from exc
    block = data.get(section)
    if not isinstance(block, dict):
        raise ParseError(f"{rel}: no top-level `{section}` object")
    return list(block)


def diff(label: str, expected: set[str], actual: list[str], allowed_extra=lambda v: False) -> list[str]:
    dupes = sorted({v for v in actual if actual.count(v) > 1})
    missing = sorted(expected - set(actual))
    extra = sorted(v for v in set(actual) - expected if not allowed_extra(v))
    parts = []
    if missing:
        parts.append(f"missing {missing}")
    if extra:
        parts.append(f"extra {extra}")
    if dupes:
        parts.append(f"duplicate {dupes}")
    return [f"{label}: {', '.join(parts)}"] if parts else []


def check(reader) -> list[str]:
    errors: list[str] = []

    def guarded(fn):
        try:
            fn()
        except ParseError as exc:
            errors.append(f"parse error — {exc}")

    types_text = reader.read(TYPES_TS)
    forms_ref = ts_const_array(types_text, "EVENT_FORMS", TYPES_TS)
    cats_ref = ts_const_array(types_text, "CATEGORIES", TYPES_TS)
    errors += diff(f"event_form · {TYPES_TS} EVENT_FORMS", set(forms_ref), forms_ref)
    errors += diff(f"category · {TYPES_TS} CATEGORIES", set(cats_ref), cats_ref)
    forms, cats = set(forms_ref), set(cats_ref)

    def annotator():
        text = reader.read(ANNOTATOR)
        errors.extend(diff(f"event_form · {ANNOTATOR} VALID_EVENT_FORMS", forms,
                           py_constant(text, "VALID_EVENT_FORMS", ANNOTATOR)))
        errors.extend(diff(f"event_form · {ANNOTATOR} SYSTEM_PROMPT 'Pick one or more from' list",
                           forms - set(PROMPT_EVENT_FORM_OMITTED), prompt_event_forms(text)))
        errors.extend(diff(f"category · {ANNOTATOR} VALID_CATEGORIES", cats,
                           py_constant(text, "VALID_CATEGORIES", ANNOTATOR)))

    def database():
        errors.extend(diff(f"event_form · {DATABASE} _VALID_EVENT_FORMS", forms,
                           py_constant(reader.read(DATABASE), "_VALID_EVENT_FORMS", DATABASE)))

    def migration():
        rel, values = latest_constraint(reader)
        errors.extend(diff(f"event_form · {rel} events_event_form_check", forms, values))

    def taxonomy():
        errors.extend(diff(f"category · {TAXONOMY} PROMPT block definitions", cats,
                           taxonomy_definitions(reader.read(TAXONOMY))))

    def locales():
        desc_extra = CATEGORY_DESC_EXTRA | {f"{c}_long" for c in cats}
        for rel in LOCALE_FILES:
            text = reader.read(rel)
            errors.extend(diff(f"event_form · {rel} eventForm.*", forms, locale_keys(text, "eventForm", rel)))
            errors.extend(diff(f"category · {rel} categories.*", cats, locale_keys(text, "categories", rel),
                               allowed_extra=lambda v: bool(CATEGORIES_EXTRA_RE.match(v))))
            errors.extend(diff(f"category · {rel} categoryDesc.*", cats, locale_keys(text, "categoryDesc", rel),
                               allowed_extra=lambda v: v in desc_extra))

    def routes():
        for rel in ROUTE_FILES:
            text = reader.read(rel)
            for join in ROUTE_JOINS:
                if join not in text:
                    errors.append(f"{rel}: prompt no longer builds the list with {join}...) — do not hand-write the enum")

    for step in (annotator, database, migration, taxonomy, locales, routes):
        guarded(step)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this repo)")
    parser.add_argument("--staged", action="store_true", help="check the git index instead of the working tree")
    args = parser.parse_args(argv)

    if args.staged:
        reader = IndexReader(args.root)
        staged = reader.staged_paths()
        if not any(p in WATCHED_FILES or p.startswith(WATCHED_PREFIXES) for p in staged):
            return 0
    else:
        reader = TreeReader(args.root)

    try:
        errors = check(reader)
    except ParseError as exc:
        errors = [f"parse error — {exc}"]

    if errors:
        print("\nenum parity: drift from web/lib/types.ts detected" + (" — commit blocked!" if args.staged else ""))
        for err in errors:
            print(f"  {err}")
        print("\n  Update every copy in the same commit. Intentional differences are declared at the")
        print("  top of scripts/check_enum_parity.py, each with its reason.")
        if args.staged:
            print("  To bypass (use with caution): git commit --no-verify")
        return 1

    if not args.staged:
        print("enum parity: OK (event_form and category copies match web/lib/types.ts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
