#!/usr/bin/env python3
"""One-off: clean up multi-person performer values locked in field_corrections.

Scans field_corrections for performer-series fields whose corrected_value
contains multi-person separators (e.g. '柯震東、宋芸樺、王淨'), then:
- For non-reviewed events: sets events.<field>=NULL and FC.corrected_value=""
- For reviewed events: reports only (no write)

Usage:
  python _oneoff_cleanup_performer_fc_pollution.py [--dry-run] [--reviewed-only]
"""
import re
import sys
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

DRY_RUN = "--dry-run" in sys.argv
REVIEWED_ONLY = "--reviewed-only" in sys.argv

# Canonical field whitelist — must match qa_auto_fix handle_performer_multi_value_split
PERFORMER_FIELDS = frozenset({
    "performer",
    "performer_zh",
    "performer_en",
    "performers_zh",
    "performers_en",
})


def _check_field_consistency() -> None:
    """Fail-fast if qa_auto_fix uses different field set."""
    import ast
    import pathlib
    src = pathlib.Path("qa_auto_fix.py").read_text(encoding="utf-8")
    # Extract field names used in handle_performer_multi_value_split lock_empty calls
    found = set(re.findall(r'lock_empty.*?field_name\s*=\s*["\'](\w+)["\']', src))
    if not found:
        # fallback: grep for known performer field pattern
        found = set(re.findall(r'"(performer(?:_zh|_en|s_zh|s_en)?)"', src))
    missing_from_script = PERFORMER_FIELDS - found
    extra_in_script = found - PERFORMER_FIELDS
    if missing_from_script or extra_in_script:
        print("⚠ Field consistency mismatch:")
        if missing_from_script:
            print(f"  In PERFORMER_FIELDS but not in qa_auto_fix: {missing_from_script}")
        if extra_in_script:
            print(f"  In qa_auto_fix but not in PERFORMER_FIELDS: {extra_in_script}")
        # Non-fatal: print warning but continue
    else:
        print(f"✓ Field whitelist consistent with qa_auto_fix: {PERFORMER_FIELDS}")


_check_field_consistency()

_MULTI_SEP_RE = re.compile(r"[、,，×／/]")

# Full paginated scan of field_corrections (performer fields only)
all_fc = []
offset = 0
while True:
    rows = (
        sb.table("field_corrections")
        .select("id,event_id,field_name,corrected_value")
        .in_("field_name", list(PERFORMER_FIELDS))
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    if not rows:
        break
    all_fc.extend(rows)
    if len(rows) < 1000:
        break
    offset += 1000

print(f"\nFC rows in performer fields: {len(all_fc)}")

# Filter: corrected_value contains multi-person separators
polluted = [r for r in all_fc if _MULTI_SEP_RE.search(r.get("corrected_value") or "")]
print(f"Polluted FC rows (multi-value): {len(polluted)}")

if not polluted:
    print("Nothing to clean.")
    sys.exit(0)

# Fetch annotation_status for each event
event_ids = list({r["event_id"] for r in polluted})
ev_status = {}
chunk_size = 100
for i in range(0, len(event_ids), chunk_size):
    chunk = event_ids[i : i + chunk_size]
    rows = (
        sb.table("events")
        .select("id,annotation_status")
        .in_("id", chunk)
        .execute()
        .data or []
    )
    for e in rows:
        ev_status[e["id"]] = e["annotation_status"]

reviewed_list = []
cleaned = 0

for fc in polluted:
    eid = fc["event_id"]
    fname = fc["field_name"]
    cv = fc["corrected_value"]
    status = ev_status.get(eid, "unknown")

    if status == "reviewed":
        reviewed_list.append(fc)
        if REVIEWED_ONLY or DRY_RUN:
            print(f"  [reviewed] {eid[:8]} {fname}={cv!r} — skip (reviewed)")
        continue

    if REVIEWED_ONLY:
        continue

    if DRY_RUN:
        print(f"  [would clean] {eid[:8]} {fname}={cv!r} → NULL + sentinel ''")
        continue

    # Write: events.<field> = NULL
    sb.table("events").update({fname: None}).eq("id", eid).execute()
    # Write: FC.corrected_value = "" (lock-empty sentinel)
    sb.table("field_corrections").update({"corrected_value": ""}).eq("id", fc["id"]).execute()
    print(f"  ✓ cleaned {eid[:8]} {fname}")
    cleaned += 1

print(f"\nSummary:")
print(f"  Cleaned (non-reviewed): {cleaned}")
print(f"  Reviewed (skipped): {len(reviewed_list)}")
if reviewed_list:
    print("  Reviewed events needing manual review:")
    for fc in reviewed_list:
        print(f"    {fc['event_id'][:8]} {fc['field_name']}={fc['corrected_value']!r}")
