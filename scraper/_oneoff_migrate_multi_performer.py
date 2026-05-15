"""
_oneoff_migrate_multi_performer.py — Migrate performer multi-value pollution to performers[].

Finds all active movie events where the `performer` field contains a separator
character (、, , ，, ×, ／, /) and migrates them:
  1. Split performer → performers[] (deduped, stripped)
  2. Clear performer, performer_zh, performer_en
  3. Delete matching field_corrections rows for performer_zh / performer_en
     (so enrich_person_names can rebuild them cleanly)
  4. Update events table

Usage:
    python _oneoff_migrate_multi_performer.py --dry-run   # inspect only
    python _oneoff_migrate_multi_performer.py --execute   # write to DB + re-enrich

After --execute, automatically runs:
    python annotator.py --enrich-person-names
to populate performers_zh/en via eiga.com + Wikipedia lookup.

Safety rules:
- Never touches annotation_status='reviewed' events.
- Aborts if > 20 events found (requires --force to override).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SEP_RE = re.compile(r"[、,，×／/]")

MAX_SAFE = 20  # Pause threshold — require --force if count exceeds this


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    return create_client(url, key)


def _split_performer(raw: str) -> list[str]:
    """Split a multi-value performer string into individual names."""
    parts = [p.strip() for p in _SEP_RE.split(raw) if p.strip()]
    return list(dict.fromkeys(parts))  # dedup, preserve order


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate multi-value performer fields to performers[]")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Print affected events without writing (default)")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Actually write to DB and trigger re-enrich")
    parser.add_argument("--force", action="store_true", default=False,
                        help="Override the MAX_SAFE=20 threshold")
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        logger.info("=== DRY-RUN mode (pass --execute to write) ===")
    else:
        logger.info("=== EXECUTE mode ===")

    sb = _supabase_client()

    # Fetch all active movie events with non-null performer
    res = (
        sb.table("events")
        .select("id,source_name,name_ja,performer,performers,performer_zh,performer_en,annotation_status")
        .eq("is_active", True)
        .contains("category", ["movie"])
        .not_.is_("performer", "null")
        .execute()
    )
    all_events = res.data or []

    # Filter: performer contains separator AND not reviewed
    affected = [
        e for e in all_events
        if _SEP_RE.search(e.get("performer") or "")
        and e.get("annotation_status") != "reviewed"
    ]

    if not affected:
        logger.info("No events with multi-value performer found. Nothing to do.")
        return

    logger.info("=== Events to migrate: %d ===", len(affected))
    for ev in affected:
        raw = ev["performer"]
        parts = _split_performer(raw)
        logger.info(
            "  [%s] %-24s | performer=%r → %s",
            ev["id"][:8],
            (ev.get("source_name") or "")[:24],
            raw,
            parts,
        )
        if ev.get("performer_zh") or ev.get("performer_en"):
            logger.info(
                "    performer_zh=%r  performer_en=%r  (will be cleared + FC deleted)",
                ev.get("performer_zh"),
                ev.get("performer_en"),
            )

    if len(affected) > MAX_SAFE and not args.force:
        logger.error(
            "ABORT: %d events exceed safety threshold MAX_SAFE=%d. "
            "Re-run with --force to override.",
            len(affected),
            MAX_SAFE,
        )
        sys.exit(1)

    if dry_run:
        logger.info("Dry-run complete. Pass --execute to apply changes.")
        return

    # --- Execute ---
    migrated = 0
    for ev in affected:
        eid = ev["id"]
        raw = ev["performer"]
        parts = _split_performer(raw)

        # 1. Delete field_corrections for performer_zh / performer_en (allow re-enrich)
        fc_types = ["performer_zh", "performer_en"]
        for field in fc_types:
            del_res = (
                sb.table("field_corrections")
                .delete()
                .eq("event_id", eid)
                .eq("field_name", field)
                .execute()
            )
            deleted = len(del_res.data or [])
            if deleted:
                logger.info("  [%s] deleted FC lock for %s", eid[:8], field)

        # 2. Update events table
        updates = {
            "performers": parts,
            "performer": None,
            "performer_zh": None,
            "performer_en": None,
        }
        sb.table("events").update(updates).eq("id", eid).execute()
        migrated += 1
        logger.info(
            "  ✓ [%s] performer=%r → performers=%s (performer/zh/en cleared)",
            eid[:8], raw, parts,
        )

    logger.info("Migration complete: %d/%d events updated.", migrated, len(affected))

    # 3. Trigger enrich_person_names to rebuild performers_zh/en
    logger.info("\nTriggering: python annotator.py --enrich-person-names ...")
    script_dir = Path(__file__).parent
    result = subprocess.run(
        [sys.executable, "annotator.py", "--enrich-person-names"],
        cwd=str(script_dir),
        capture_output=False,
    )
    if result.returncode != 0:
        logger.error("annotator.py --enrich-person-names exited with code %d", result.returncode)
    else:
        logger.info("enrich_person_names completed successfully.")


if __name__ == "__main__":
    main()
