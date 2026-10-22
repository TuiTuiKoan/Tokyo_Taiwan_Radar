#!/usr/bin/env python3
"""
LLM caller guard — every OpenAI call goes through the shared clients
(llm-cost-reset, #363). Shared by the pre-commit hook and scripts/tests.

The shared clients record each call in public.llm_usage and turn a retired
model or bad key into a failed step (#319). A direct client bypasses both,
which is how gpt-4o-search-preview failed silently for two months and why the
weekly report under-counted spend about 4x. So:

- scraper: only scraper/llm_client.py may construct OpenAI(...) / AsyncOpenAI(...).
  Everything else calls llm_client.get_client("<group>.<name>").
- web: only web/lib/llm/openai.server.ts may reference api.openai.com.
  Routes call openaiChat({ caller: "web.<name>", ... }).

Exempt: scraper/_oneoff_*.py (one-time scripts, not scheduled) and test files.
Standard library only.

Modes:
  (default)   Scan the working tree under --root (default: repo root)
  --staged    Scan only staged scraper/web files, read from the git index

Exit codes:
  0  No direct callers
  1  Direct callers found
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCRAPER_ALLOWED = "scraper/llm_client.py"
WEB_ALLOWED = "web/lib/llm/openai.server.ts"

# No space before "(": a call never has one, prose like "calling OpenAI (offline)" does.
_SDK_CLIENT = re.compile(r"\b(?:Async)?OpenAI\(")
_API_HOST = "api.openai.com"


def _exempt(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (
        name.startswith("_oneoff_")
        or "/tests/" in rel
        or name.startswith("test_")
        or ".test." in name
        or "/node_modules/" in rel
    )


def violation(rel: str, text: str) -> str | None:
    """Return a message when this file calls OpenAI without the shared client."""
    if _exempt(rel):
        return None
    if rel.startswith("scraper/") and rel.endswith(".py") and rel != SCRAPER_ALLOWED:
        for lineno, line in enumerate(text.splitlines(), 1):
            if _SDK_CLIENT.search(line) and not line.lstrip().startswith("#"):
                return f"{rel}:{lineno}: constructs an OpenAI client; use llm_client.get_client(\"<group>.<name>\")"
    if rel.startswith("web/") and rel.endswith((".ts", ".tsx")) and rel != WEB_ALLOWED:
        for lineno, line in enumerate(text.splitlines(), 1):
            if _API_HOST in line:
                return f"{rel}:{lineno}: calls {_API_HOST} directly; use openaiChat() from @/lib/llm/openai.server"
    return None


def _working_tree_files(root: Path) -> list[tuple[str, str]]:
    out = []
    for base, pattern in (("scraper", "*.py"), ("web/app", "*.ts*"), ("web/lib", "*.ts*"), ("web/components", "*.ts*")):
        for path in (root / base).rglob(pattern):
            rel = path.relative_to(root).as_posix()
            if not _exempt(rel):
                out.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    return out


def _staged_files(root: Path) -> list[tuple[str, str]]:
    names = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.split()
    out = []
    for rel in names:
        if not (rel.startswith("scraper/") or rel.startswith("web/")) or _exempt(rel):
            continue
        blob = subprocess.run(["git", "show", f":{rel}"], cwd=root, capture_output=True, text=True)
        if blob.returncode == 0:
            out.append((rel, blob.stdout))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument("--staged", action="store_true")
    args = ap.parse_args(argv)

    files = _staged_files(args.root) if args.staged else _working_tree_files(args.root)
    problems = [msg for rel, text in files if (msg := violation(rel, text))]
    if problems:
        print("LLM caller guard: OpenAI calls must go through the shared clients (#363):", file=sys.stderr)
        for msg in problems:
            print(f"  {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
