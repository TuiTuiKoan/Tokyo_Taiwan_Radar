"""
一次性遷移腳本：eurospace source_id 從 numeric-id-based 改為 name_ja hash-based。

舊格式：eurospace_{w_id}
新格式：eurospace_{md5(normalized_title)[:12]}（make_film_source_id）

用法：
  python _oneoff_migrate_eurospace_source_id.py          # dry-run（預設，不改 DB）
  python _oneoff_migrate_eurospace_source_id.py --apply  # 實際執行
"""
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(".env")
from supabase import create_client  # noqa: E402

from sources._cinema_base import make_film_source_id  # noqa: E402

SOURCE_NAME = "eurospace"
SLUG = "eurospace"

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
APPLY = "--apply" in sys.argv


def _new_sid(name_ja: str) -> str:
    return make_film_source_id(SLUG, name_ja)


def _merged_fields(group: list[dict]) -> dict:
    """保留最早 start_date、最新 end_date、最新 business_hours。"""
    starts = [e["start_date"] for e in group if e.get("start_date")]
    ends = [e["end_date"] for e in group if e.get("end_date")]
    bh_candidates = [e for e in group if e.get("business_hours")]
    bh_src = max(bh_candidates, key=lambda x: x.get("end_date") or "", default=None)
    return {
        "start_date": min(starts) if starts else group[0].get("start_date"),
        "end_date": max(ends) if ends else group[0].get("end_date"),
        "business_hours": bh_src["business_hours"] if bh_src else group[0].get("business_hours"),
    }


def main() -> None:
    events = (
        sb.table("events")
        .select(
            "id,source_id,name_ja,start_date,end_date,business_hours,"
            "is_active,merged_into_event_id"
        )
        .eq("source_name", SOURCE_NAME)
        .execute()
        .data
    )

    groups: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        name_ja = e.get("name_ja") or e.get("source_id") or ""
        groups[_new_sid(name_ja)].append(e)

    rename_only: list[tuple[str, dict]] = []
    merge_groups: list[tuple[str, dict, list[dict]]] = []
    for new_sid, group in groups.items():
        if len(group) == 1:
            ev = group[0]
            if ev["source_id"] != new_sid:
                rename_only.append((new_sid, ev))
            continue
        ordered = sorted(group, key=lambda x: (x.get("start_date") is None, x.get("start_date") or ""))
        merge_groups.append((new_sid, ordered[0], ordered[1:]))

    total_secondary = sum(len(s) for _, _, s in merge_groups)

    print(f"=== {'APPLY' if APPLY else 'DRY RUN'} : {SOURCE_NAME} (slug={SLUG}) ===")
    print(f"總事件 {len(events)} 筆")
    print(f"純改名（單筆 source_id 更新）{len(rename_only)} 筆")
    print(f"需合併群組 {len(merge_groups)} 組，將停用次要事件 {total_secondary} 筆")
    print(f"mapping 總筆數：primary={len(rename_only) + len(merge_groups)}、secondary={total_secondary}")

    for new_sid, primary, secondaries in merge_groups:
        mf = _merged_fields([primary] + secondaries)
        print(f"\n  片名: {primary.get('name_ja')!r}")
        print(f"  新 source_id: {new_sid}")
        print(f"  Primary(保留): {primary['id']} (old={primary['source_id']}) "
              f"→ start={mf['start_date']} end={mf['end_date']}")
        for s in secondaries:
            print(f"  Secondary(→停用,merged_into primary): {s['id']} (old={s['source_id']})")

    if not APPLY:
        print("\n（dry-run，未改 DB）")
        return

    for new_sid, ev in rename_only:
        sb.table("events").update({"source_id": new_sid}).eq("id", ev["id"]).execute()

    for new_sid, primary, secondaries in merge_groups:
        mf = _merged_fields([primary] + secondaries)
        sb.table("events").update({"source_id": new_sid, **mf}).eq("id", primary["id"]).execute()
        for s in secondaries:
            sb.table("events").update(
                {"merged_into_event_id": primary["id"], "is_active": False}
            ).eq("id", s["id"]).execute()

    print("完成。")


if __name__ == "__main__":
    main()
