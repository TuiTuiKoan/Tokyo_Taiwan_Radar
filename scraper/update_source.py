"""
CLI helper for @Researcher agent: update a research_sources row after deep research.

Usage:
    python update_source.py --url <url> --status researched
    python update_source.py --url <url> --status researched --create-issue
    python update_source.py --url <url> --status not-viable

Status values:
    researched   — deep research complete, source profile written, ready for Issue
    not-viable   — deep research revealed the source is not suitable for scraping

With --create-issue:
    Reads the source profile from .copilot-tracking/research/sources/<slug>.md,
    creates a GitHub Issue via the GitHub REST API, saves the issue URL to DB,
    and automatically advances status to 'recommended'.
    Requires GITHUB_TOKEN env var (classic token with repo scope, or fine-grained
    with Issues: read & write permission on the target repo).
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

logger = logging.getLogger(__name__)

VALID_STATUSES = {"researched", "not-viable"}
CANDIDATES_DIR = Path(__file__).parent.parent / ".copilot-tracking" / "research" / "candidates"
SOURCES_DIR = Path(__file__).parent.parent / ".copilot-tracking" / "research" / "sources"
GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar"


def _get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _url_to_slug(url: str) -> str:
    # Try to derive slug from the URL domain+path
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    return slug[:60]


def _find_source_profile(name: str, url: str = "") -> Path | None:
    """Find a .md profile file in SOURCES_DIR whose filename roughly matches the source name or URL."""
    if not SOURCES_DIR.exists():
        return None
    name_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    url_slug = re.sub(r"https?://", "", url)
    url_slug = re.sub(r"[^a-z0-9]+", "-", url_slug.lower()).strip("-")[:60]

    # Exact slug match (name-based)
    exact = SOURCES_DIR / f"{name_slug}.md"
    if exact.exists():
        return exact

    # Check all .md files for partial match against name OR url slug
    for f in SOURCES_DIR.glob("*.md"):
        stem = f.stem
        if (stem in name_slug or name_slug in stem or
                stem in url_slug or url_slug[:len(stem)] == stem):
            return f
    return None


def _build_issue_body(name: str, url: str, profile_path: Path | None) -> str:
    """Build GitHub Issue body from source profile markdown."""
    if profile_path and profile_path.exists():
        profile_content = profile_path.read_text(encoding="utf-8")
    else:
        profile_content = f"_Source profile not found. URL: {url}_"

    return (
        f"## 來源資訊\n\n"
        f"- **名稱**: {name}\n"
        f"- **URL**: {url}\n\n"
        f"## Source Profile\n\n"
        f"{profile_content}\n\n"
        f"## 實作步驟\n\n"
        f"1. `@Scraper Expert` 依照 profile 分析頁面結構\n"
        f"2. 建立 `scraper/sources/<name>.py` 繼承 `BaseScraper`\n"
        f"3. 加入 `scraper/main.py` 的 `SCRAPERS` 清單\n"
        f"4. `python main.py --dry-run --source <name>` 驗證\n"
        f"5. 確認 `start_date` 有正確填入\n"
    )


def create_github_issue(name: str, url: str, profile_path: Path | None) -> str:
    """Create a GitHub Issue and return the issue URL."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN env var required for --create-issue. "
            "Set a classic token with 'repo' scope or a fine-grained token with Issues: write."
        )

    title = f"feat(scraper): add {name} source"
    body = _build_issue_body(name, url, profile_path)
    labels = ["scraper", "enhancement"]

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"title": title, "body": body, "labels": labels}

    resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 201:
        issue_url = resp.json()["html_url"]
        logger.info("Created GitHub Issue: %s", issue_url)
        return issue_url
    else:
        raise RuntimeError(
            f"GitHub API error {resp.status_code}: {resp.text[:300]}"
        )


def update_source(url: str, status: str, create_issue: bool = False) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got: {status!r}")

    if create_issue and status != "researched":
        raise ValueError("--create-issue can only be used with --status researched")

    sb = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # Check the row exists
    existing = sb.table("research_sources").select("id,status,name").eq("url", url).execute()
    if not existing.data:
        logger.error("No row found in research_sources for URL: %s", url)
        sys.exit(1)

    row = existing.data[0]
    current_status = row["status"]
    name = row["name"]

    # Safety: don't downgrade implemented → not-viable etc.
    if current_status == "implemented":
        logger.warning(
            "Source '%s' is already 'implemented' — skipping update to '%s'", name, status
        )
        sys.exit(0)

    update_fields: dict = {"status": status, "last_seen_at": now}

    # Optionally create a GitHub Issue and advance to 'recommended'
    if create_issue:
        profile_path = _find_source_profile(name, url)
        if not profile_path:
            logger.warning("No source profile .md found for '%s' — Issue body will be minimal", name)
        issue_url = create_github_issue(name, url, profile_path)
        update_fields["github_issue_url"] = issue_url
        update_fields["status"] = "recommended"
        logger.info("Status auto-advanced to 'recommended' after Issue creation")

    sb.table("research_sources").update(update_fields).eq("url", url).execute()
    logger.info("Updated '%s' (%s) → %s", name, url, update_fields["status"])

    # Remove candidate JSON file if it exists
    slug = _url_to_slug(url)
    for candidate_file in CANDIDATES_DIR.glob("*.json"):
        try:
            data = json.loads(candidate_file.read_text())
            if data.get("url") == url:
                candidate_file.unlink()
                logger.info("Deleted candidate file: %s", candidate_file.name)
                break
        except Exception:
            continue
    else:
        # Also try slug-based filename
        slug_path = CANDIDATES_DIR / f"{slug}.json"
        if slug_path.exists():
            slug_path.unlink()
            logger.info("Deleted candidate file: %s", slug_path.name)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="Update research_sources status after deep research")
    parser.add_argument("--url", required=True, help="Exact URL of the source to update")
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="New status for the source",
    )
    parser.add_argument(
        "--create-issue",
        action="store_true",
        default=False,
        help=(
            "Create a GitHub Issue automatically (requires GITHUB_TOKEN env var). "
            "Only valid with --status researched. Advances status to 'recommended'."
        ),
    )
    args = parser.parse_args()

    update_source(args.url, args.status, create_issue=args.create_issue)
