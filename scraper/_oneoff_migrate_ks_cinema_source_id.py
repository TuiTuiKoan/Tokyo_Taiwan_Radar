"""
一次性遷移腳本：ks_cinema source_id 從 url_slug-based 改為 name_ja hash-based。

舊格式：
  parent/single : ks_cinema_{url_slug}
  sub-film      : ks_cinema_{url_slug}_{film_index}
新格式：
  parent/single : ks_cinema_{md5(normalized_title)[:12]}（make_film_source_id）
  sub-film      : {parent_new_sid}_{film_index}

ks_cinema 有 parent + sub-event 結構，故與其他電影院遷移腳本不同：
  1. 頂層事件（parent_event_id IS NULL）依 name_ja 重算新 source_id，同片名多筆合併。
  2. 子事件（parent_event_id NOT NULL）source_id 改為 {primary_new_sid}_{idx}，
     並把 parent_event_id 重新指向群組 primary。
     子事件保留 _\\d+$ 結尾格式 → annotator 的 cinema sub-event 守衛不被破壞。

用法：
  python _oneoff_migrate_ks_cinema_source_id.py          # dry-run（預設，不改 DB）
  python _oneoff_migrate_ks_cinema_source_id.py --apply  # 實際執行
"""
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(".env")
from supabase import create_client  # noqa: E402

from sources._cinema_base import make_film_source_id  # noqa: E402

SOURCE_NAME = "ks_cinema"
SLUG = "ks_cinema"

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
APPLY = "--apply" in sys.argv


def _new_sid(name_ja: str) -> str:
    return make_film_source_id(SLUG, name_ja)


def _sub_index(source_id: str) -> str | None:
    """從舊子事件 source_id 取出尾端 film_index（ks_cinema_slug_2 → '2'）。"""
    tail = source_id.rsplit("_", 1)[-1]
    return tail if tail.isdigit() else None


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
            "is_active,merged_into_event_id,parent_event_id"
        )
        .eq("source_name", SOURCE_NAME)
        .execute()
        .data
    )

    top_level = [e for e in events if not e.get("parent_event_id")]
    subs = [e for e in events if e.get("parent_event_id")]

    # --- 頂層事件分組 ---
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in top_level:
        name_ja = e.get("name_ja") or e.get("source_id") or ""
        groups[_new_sid(name_ja)].append(e)

    rename_only: list[tuple[str, dict]] = []
    merge_groups: list[tuple[str, dict, list[dict]]] = []
    # top-level event id → (group_new_sid, primary_id)
    resolution: dict[str, tuple[str, str]] = {}
    for new_sid, group in groups.items():
        ordered = sorted(group, key=lambda x: (x.get("start_date") is None, x.get("start_date") or ""))
        primary = ordered[0]
        for e in group:
            resolution[e["id"]] = (new_sid, primary["id"])
        if len(group) == 1:
            if primary["source_id"] != new_sid:
                rename_only.append((new_sid, primary))
        else:
            merge_groups.append((new_sid, primary, ordered[1:]))

    # --- 子事件重算 ---
    sub_updates: list[tuple[dict, str, str]] = []  # (sub, new_sub_sid, new_parent_id)
    sub_orphans: list[dict] = []
    sub_dups: list[dict] = []
    seen_sub_sid: set[str] = set()
    for s in subs:
        pid = s.get("parent_event_id")
        idx = _sub_index(s["source_id"])
        if pid not in resolution or idx is None:
            sub_orphans.append(s)
            continue
        parent_new_sid, primary_id = resolution[pid]
        new_sub_sid = f"{parent_new_sid}_{idx}"
        if new_sub_sid in seen_sub_sid:
            sub_dups.append(s)
            continue
        seen_sub_sid.add(new_sub_sid)
        sub_updates.append((s, new_sub_sid, primary_id))

    total_secondary = sum(len(s) for _, _, s in merge_groups)

    print(f"=== {'APPLY' if APPLY else 'DRY RUN'} : {SOURCE_NAME} (slug={SLUG}) ===")
    print(f"總事件 {len(events)} 筆（頂層 {len(top_level)}、子事件 {len(subs)}）")
    print(f"頂層純改名 {len(rename_only)} 筆")
    print(f"頂層需合併群組 {len(merge_groups)} 組，將停用次要事件 {total_secondary} 筆")
    print(f"子事件改 source_id {len(sub_updates)} 筆，孤兒(略過) {len(sub_orphans)} 筆，"
          f"重複(略過) {len(sub_dups)} 筆")
    print(f"mapping 總筆數：頂層 primary={len(rename_only) + len(merge_groups)}、"
          f"頂層 secondary={total_secondary}、sub={len(sub_updates)}")

    for new_sid, primary, secondaries in merge_groups:
        mf = _merged_fields([primary] + secondaries)
        print(f"\n  片名: {primary.get('name_ja')!r}")
        print(f"  新 source_id: {new_sid}")
        print(f"  Primary(保留): {primary['id']} (old={primary['source_id']}) "
              f"→ start={mf['start_date']} end={mf['end_date']}")
        for s in secondaries:
            print(f"  Secondary(→停用,merged_into primary): {s['id']} (old={s['source_id']})")

    if sub_orphans:
        print("\n  ⚠ 孤兒子事件（parent 不在本 source 頂層或無 idx，已略過）:")
        for s in sub_orphans:
            print(f"    {s['id']} (source_id={s['source_id']}, parent={s.get('parent_event_id')})")
    if sub_dups:
        print("\n  ⚠ 重複子事件（新 sub source_id 碰撞，已略過，需人工確認）:")
        for s in sub_dups:
            print(f"    {s['id']} (source_id={s['source_id']})")

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

    for s, new_sub_sid, new_parent_id in sub_updates:
        sb.table("events").update(
            {"source_id": new_sub_sid, "parent_event_id": new_parent_id}
        ).eq("id", s["id"]).execute()

    print("完成。")


if __name__ == "__main__":
    main()
