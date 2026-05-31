import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# Count rows where country IS NULL
count_res = (
    sb.table("event_views")
    .select("id", count="exact", head=True)
    .is_("country", "null")
    .execute()
)
null_count = count_res.count or 0
print(f"event_views with country IS NULL: {null_count}")

if null_count == 0:
    print("Nothing to delete.")
else:
    result = sb.table("event_views").delete().is_("country", "null").execute()
    deleted = len(result.data) if result.data else "(unknown)"
    print(f"Deleted rows: {deleted}")
