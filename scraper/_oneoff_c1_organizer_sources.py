"""Phase C-1: Static organizer補完 for known sources."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

SOURCE_ORGANIZER_MAP = {
    "rightscube": "ライツキューブ",
    "ssff": "ショートショート フィルム フェスティバル & アジア",
    "tsutaya_portal": "蔦屋書店",
    "taiwan_festival_tokyo": "台湾フェスティバルTOKYO実行委員会",
    "shin_bungeiza": "新文芸坐",
}

updated = 0
for source_name, organizer in SOURCE_ORGANIZER_MAP.items():
    rows = (
        sb.table("events")
        .select("id,raw_title,organizer")
        .eq("is_active", True)
        .eq("source_name", source_name)
        .is_("organizer", "null")
        .execute()
        .data
    )
    for e in rows:
        eid = e["id"]
        sb.table("events").update({"organizer": organizer}).eq("id", eid).execute()
        sb.table("field_corrections").upsert(
            {"event_id": eid, "field_name": "organizer", "corrected_value": organizer, "corrected_by": None},
            on_conflict="event_id,field_name",
        ).execute()
        print(f"  ok {eid[:8]} [{source_name}] -> {repr(organizer)} | {e['raw_title'][:50]}")
        updated += 1

print(f"Phase C-1 done: {updated} updated")
total = sb.table("events").select("id", count="exact").eq("is_active", True).execute().count
filled = sb.table("events").select("id", count="exact").eq("is_active", True).not_.is_("organizer", "null").execute().count
print(f"organizer fill rate: {filled}/{total} = {filled/total*100:.1f}%")
