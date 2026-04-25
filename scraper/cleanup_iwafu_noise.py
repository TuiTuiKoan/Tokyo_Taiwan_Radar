"""One-time script: strip UI noise from existing iwafu events in DB.

Run once after deploying the _strip_iwafu_noise fix in sources/iwafu.py.
Safe to delete after execution.

Usage:
    cd scraper && python cleanup_iwafu_noise.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

from sources.iwafu import _strip_iwafu_noise

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

res = (
    sb.table("events")
    .select("id, raw_description, description_ja")
    .eq("source_name", "iwafu")
    .execute()
)
rows = res.data
print(f"Found {len(rows)} iwafu events in DB")

updated = 0
for row in rows:
    orig_raw = row["raw_description"] or ""
    orig_desc = row["description_ja"] or ""

    new_raw = _strip_iwafu_noise(orig_raw)
    new_desc = _strip_iwafu_noise(orig_desc)

    if new_raw != orig_raw or new_desc != orig_desc:
        sb.table("events").update(
            {
                "raw_description": new_raw or None,
                "description_ja": new_desc or None,
            }
        ).eq("id", row["id"]).execute()
        updated += 1
        print(f"  Cleaned {row['id'][:8]}…")

print(f"Done. Updated {updated}/{len(rows)} rows.")
