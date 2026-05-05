"""
exclusions_maintenance.py — Daily maintenance for source_exclusions.

1. Mark rules as 'expired' when expires_at <= now().
2. Mark rules as 'stale_no_hits' when last_matched_at < now() - 90 days
   AND created_at < now() - 90 days (avoid disabling brand new rules).

Outputs JSON summary on stdout for CI consumption + LINE notify.
Designed to run in CI via GitHub Actions after backlog_health.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

logger = logging.getLogger(__name__)

UTC = timezone.utc
STALE_DAYS = 90


def _get_sb():
    load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def run() -> dict:
    sb = _get_sb()
    now = datetime.now(tz=UTC)
    cutoff_stale = (now - timedelta(days=STALE_DAYS)).isoformat()

    expired_ids: list[str] = []
    stale_ids: list[str] = []

    # 1. Expired rules
    try:
        exp_resp = (
            sb.table("source_exclusions")
            .select("id,source_name,pattern,expires_at")
            .is_("auto_disabled_at", "null")
            .not_.is_("expires_at", "null")
            .lte("expires_at", now.isoformat())
            .execute()
        )
        for row in exp_resp.data or []:
            sb.table("source_exclusions").update(
                {
                    "auto_disabled_at": now.isoformat(),
                    "auto_disabled_reason": "expired",
                }
            ).eq("id", row["id"]).execute()
            expired_ids.append(row["id"])
    except Exception as exc:
        logger.warning("expired sweep failed: %s", exc)

    # 2. Stale rules — created > 90d ago AND no hits in last 90d
    try:
        stale_resp = (
            sb.table("source_exclusions")
            .select("id,source_name,pattern,last_matched_at,created_at")
            .is_("auto_disabled_at", "null")
            .lt("created_at", cutoff_stale)
            .or_(f"last_matched_at.is.null,last_matched_at.lt.{cutoff_stale}")
            .execute()
        )
        for row in stale_resp.data or []:
            sb.table("source_exclusions").update(
                {
                    "auto_disabled_at": now.isoformat(),
                    "auto_disabled_reason": "stale_no_hits",
                }
            ).eq("id", row["id"]).execute()
            stale_ids.append(row["id"])
    except Exception as exc:
        logger.warning("stale sweep failed: %s", exc)

    summary = {
        "expired": len(expired_ids),
        "stale": len(stale_ids),
        "total_disabled": len(expired_ids) + len(stale_ids),
    }
    return summary


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = run()
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
