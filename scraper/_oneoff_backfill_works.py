"""Backfill 月老 and 大濛 works after migration 048 is applied. Run once, then delete.

Usage:
    cd scraper && source ../.venv/bin/activate
    python _oneoff_backfill_works.py            # apply
    python _oneoff_backfill_works.py --dry-run  # preview
"""
from __future__ import annotations
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env")

from supabase import create_client  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

WORKS = [
    {
        "payload": {
            "work_type": "film",
            "original_title": "月老",
            "title_ja": "赤い糸 輪廻のひみつ",
            "title_en": "Till We Meet Again",
            "title_zh": "月老",
            "director": "ギデンズ・コー",
            "cast_summary": "クー・チェンドン、ビビアン・ソン、ワン・ジン",
            "release_year": 2021,
            "country": "TW",
            "description": (
                "台湾稀代のヒットメーカー ギデンズ・コーが描く、"
                "月老（縁結びの神）と輪廻転生をモチーフにしたラブストーリー。"
            ),
        },
        "event_ids": [
            "f970e4e3-b909-4a61-aee6-98f6dd64a708",  # shin_bungeiza 5/8~14
            "4a8772ec-f9d8-43c1-8d2c-b2b9c2764cf0",  # cinemart_shinjuku 5/28
        ],
    },
    {
        "payload": {
            "work_type": "film",
            "original_title": "大濛",
            "title_ja": "霧のごとく",
            "title_en": "A Foggy Tale",
            "title_zh": "大濛",
            "release_year": 2024,
            "country": "TW",
            "description": "金馬奨5部門受賞の台湾映画。",
        },
        "event_ids": [
            "dec5031b-856e-48a2-b7e9-6e8438d435e4",  # cinemart_shinjuku 5/8
            "d201c261-1440-4ca1-8a28-5ab117d29e42",  # taioan_dokyokai 5/10
        ],
    },
]


def upsert_work(payload: dict) -> str:
    title = payload["original_title"]
    existing = (
        sb.table("works")
        .select("id")
        .eq("original_title", title)
        .limit(1)
        .execute()
    )
    if existing.data:
        wid = existing.data[0]["id"]
        if DRY_RUN:
            print(f"  [dry-run] work '{title}' already exists → {wid}")
            return wid
        sb.table("works").update(payload).eq("id", wid).execute()
        print(f"  updated existing work '{title}' → {wid}")
        return wid
    if DRY_RUN:
        print(f"  [dry-run] would INSERT work '{title}'")
        return "<new>"
    inserted = sb.table("works").insert(payload).execute()
    wid = inserted.data[0]["id"]
    print(f"  inserted work '{title}' → {wid}")
    return wid


def assign(event_id: str, work_id: str) -> None:
    if DRY_RUN:
        print(f"    [dry-run] would link event {event_id} → work {work_id}")
        return
    sb.table("events").update({"work_id": work_id}).eq("id", event_id).execute()
    print(f"    linked event {event_id} → work {work_id}")


def main() -> None:
    print(f"Backfill works (dry_run={DRY_RUN})")
    for entry in WORKS:
        title = entry["payload"]["original_title"]
        print(f"\nProcessing work: {title}")
        wid = upsert_work(entry["payload"])
        for eid in entry["event_ids"]:
            assign(eid, wid)
    print("\nDone." if not DRY_RUN else "\nDone (dry-run, no writes).")


if __name__ == "__main__":
    main()
