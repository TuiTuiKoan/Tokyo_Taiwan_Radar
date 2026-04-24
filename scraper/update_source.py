"""
CLI helper for @Researcher agent: update a research_sources row after deep research.

Usage:
    python update_source.py --url <url> --status researched
    python update_source.py --url <url> --status not-viable

Status values:
    researched   — deep research complete, source profile written, ready for Issue
    not-viable   — deep research revealed the source is not suitable for scraping
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

logger = logging.getLogger(__name__)

VALID_STATUSES = {"researched", "not-viable"}
CANDIDATES_DIR = Path(__file__).parent.parent / ".copilot-tracking" / "research" / "candidates"


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


def update_source(url: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got: {status!r}")

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

    sb.table("research_sources").update({
        "status": status,
        "last_seen_at": now,
    }).eq("url", url).execute()

    logger.info("Updated '%s' (%s) → %s", name, url, status)

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
    args = parser.parse_args()

    update_source(args.url, args.status)
