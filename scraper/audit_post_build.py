"""Audit scraper registration and implemented research-source metadata."""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

SCRAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRAPER_DIR.parent

# Connpass was removed from production as a low-value source in commit 31e1493d.
INTENTIONALLY_DISABLED_SCRAPERS = frozenset({"ConnpassScraper"})


def _registered_scraper_classes(main_path: Path) -> set[str]:
    source = main_path.read_text(encoding="utf-8")
    return set(re.findall(r"(\w+Scraper)\(\)", source))


def _concrete_scraper_classes(source_file: Path) -> set[str]:
    if source_file.stem.startswith("_"):
        return set()

    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=source_file)
    classes: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_name = node.name
        if not class_name.endswith("Scraper"):
            continue
        if class_name == "BaseScraper" or class_name.startswith("_"):
            continue
        if class_name in INTENTIONALLY_DISABLED_SCRAPERS:
            continue
        classes.add(class_name)
    return classes


def find_unregistered_scrapers(repo_root: Path = REPO_ROOT) -> list[tuple[str, Path]]:
    scraper_dir = repo_root / "scraper"
    registered = _registered_scraper_classes(scraper_dir / "main.py")
    missing: list[tuple[str, Path]] = []
    for source_file in sorted((scraper_dir / "sources").glob("*.py")):
        for class_name in sorted(_concrete_scraper_classes(source_file)):
            if class_name not in registered:
                missing.append((class_name, source_file.relative_to(repo_root)))
    return missing


def _linked_main_env(repo_root: Path) -> Path | None:
    git_marker = repo_root / ".git"
    if not git_marker.is_file():
        return None

    marker = git_marker.read_text(encoding="utf-8").strip()
    if not marker.startswith("gitdir:"):
        return None
    git_dir = Path(marker.partition(":")[2].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()

    common_dir_file = git_dir / "commondir"
    if not common_dir_file.is_file():
        return None
    common_git_dir = (git_dir / common_dir_file.read_text(encoding="utf-8").strip()).resolve()
    return common_git_dir.parent / "scraper" / ".env"


def _load_project_env(repo_root: Path = REPO_ROOT) -> None:
    candidates = [repo_root / "scraper" / ".env", _linked_main_env(repo_root)]
    for candidate in candidates:
        if candidate and candidate.is_file():
            load_dotenv(candidate)
            return


def find_implemented_sources_without_key() -> list[dict[str, Any]]:
    _load_project_env()
    from supabase import create_client

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    rows = (
        client.table("research_sources")
        .select("name,scraper_source_name,status")
        .eq("status", "implemented")
        .execute()
        .data
        or []
    )
    return [row for row in rows if not row.get("scraper_source_name")]


def main() -> int:
    errors: list[str] = []

    for class_name, source_file in find_unregistered_scrapers():
        errors.append(f"\u274c UNREGISTERED in main.py: {class_name} ({source_file})")
    if not errors:
        print("\u2705 SCRAPERS: all registered")

    try:
        missing_sources = find_implemented_sources_without_key()
    except Exception as exc:
        errors.append(f"\u274c research_sources audit failed: {exc}")
    else:
        for row in missing_sources:
            errors.append(
                "\u274c scraper_source_name NULL: "
                f'"{row["name"]}" (status=implemented)'
            )
        if not missing_sources:
            print("\u2705 research_sources: all implemented rows have scraper_source_name")

    if errors:
        for error in errors:
            print(error)
        return 1

    print("\U0001F389 ALL CLEAR \u2014 safe to commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())