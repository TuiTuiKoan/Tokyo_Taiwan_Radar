import os, sys
_SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRAPER_DIR)
from dotenv import load_dotenv
load_dotenv(os.path.join(_SCRAPER_DIR, ".env"))
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
r = sb.table("events").select(
    "id,source_name,name_ja,start_date,source_url,annotation_status,raw_description,location_name,location_address"
).eq("is_active", True).execute()

results = []
for e in r.data:
    ln = e.get("location_name") or ""
    sn = e.get("source_name") or ""
    if e.get("location_address") is not None:
        continue
    if sn == "gguide_tv" or "オンライン" in ln or "online" in ln.lower():
        continue
    if ln != "":
        continue
    results.append(e)

for e in sorted(results, key=lambda x: x["source_name"]):
    rd = (e.get("raw_description") or "")[:100].replace("\n", " ")
    print(f"[{e['source_name']}]")
    print(f"  id:         {e['id']}")
    print(f"  name_ja:    {e.get('name_ja', '')}")
    print(f"  start_date: {(e.get('start_date') or '')[:10]}")
    print(f"  status:     {e.get('annotation_status', '')}")
    print(f"  source_url: {e.get('source_url', '')}")
    print(f"  raw_desc:   {rd}")
    print()

print(f"Total: {len(results)} events")
