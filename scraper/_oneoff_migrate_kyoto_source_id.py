"""
一次性遷移腳本：kyoto_cinema source_id 從 movie_id-based 改為 name_ja hash-based。
用法：
  python _oneoff_migrate_kyoto_source_id.py          # dry-run（只顯示，不改 DB）
  python _oneoff_migrate_kyoto_source_id.py --execute # 實際執行
"""
import hashlib
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(".env")
from supabase import create_client

from sources._cinema_base import _normalize_film_title

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
DRY_RUN = "--execute" not in sys.argv


def make_new_source_id(name_ja: str) -> str:
    normalized = _normalize_film_title(name_ja)
    h = hashlib.md5(f"kyoto_cinema:{normalized}".encode()).hexdigest()[:12]
    return f"kyoto_cinema_{h}"


# 取出所有 kyoto_cinema 事件
events = (
    sb.table("events")
    .select("id,source_id,name_ja,start_date,end_date,business_hours,is_active")
    .eq("source_name", "kyoto_cinema")
    .execute()
    .data
)

# 依 name_ja 分組
groups: dict[str, list[dict]] = defaultdict(list)
for e in events:
    groups[e["name_ja"]].append(e)

merges = []
for name_ja, group in groups.items():
    if len(group) <= 1:
        continue
    new_sid = make_new_source_id(name_ja)
    # 選 primary：最早 start_date 的那筆
    group.sort(key=lambda x: x["start_date"] or "")
    primary = group[0]
    secondaries = group[1:]
    merges.append((primary, secondaries, new_sid))

print(f"=== {'DRY RUN' if DRY_RUN else 'EXECUTE'} ===")
print(f"總共 {len(events)} 筆 kyoto_cinema 事件，{len(merges)} 組需合併")
for primary, secondaries, new_sid in merges:
    print(f"  片名: {primary['name_ja']}")
    print(f"  新 source_id: {new_sid}")
    print(f"  Primary: {primary['id']} (start={primary['start_date']})")
    for s in secondaries:
        print(f"  Secondary(→merge): {s['id']}")

if not DRY_RUN:
    for primary, secondaries, new_sid in merges:
        # 更新 primary source_id
        sb.table("events").update({"source_id": new_sid}).eq("id", primary["id"]).execute()
        # 標記 secondary 為 merged
        for s in secondaries:
            sb.table("events").update(
                {
                    "merged_into_event_id": primary["id"],
                    "is_active": False,
                }
            ).eq("id", s["id"]).execute()
    print("完成。")
else:
    print("（dry-run，未改 DB）")
