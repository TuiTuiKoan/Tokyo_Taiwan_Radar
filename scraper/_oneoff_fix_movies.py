#!/usr/bin/env python3
"""One-off: create works, link movie events, fix names, reactivate."""

import json
import urllib.request
import urllib.error
import os
import sys

# ── Read .env ──────────────────────────────────────────────────

os.chdir(os.path.dirname(os.path.abspath(__file__)))

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v

SUPABASE_URL = env["SUPABASE_URL"]
SRK = env["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SRK,
    "Authorization": f"Bearer {SRK}",
    "Content-Type": "application/json",
}

# ── Authoritative sources (never change name_ja) ──────────────

AUTHORITATIVE_SOURCES = {
    "ks_cinema", "taiwan_cultural_center", "shin_bungeiza",
    "cinemart_shinjuku", "cine_marine", "eurospace",
    "taioan_dokyokai", "rightscube", "iwafu",
    "livepocket", "peatix", "ssff",
}

# ── Works definitions ─────────────────────────────────────────

WORKS = [
    {"original_title": "月老", "title_ja": "赤い糸 輪廻のひみつ", "title_zh": "月老", "title_en": "Till We Meet Again", "director": "ギデンズ・コー"},
    {"original_title": "大濛", "title_ja": "霧のごとく", "title_zh": "大濛", "title_en": "A Foggy Tale", "director": None},
    {"original_title": "造山者", "title_ja": "チップ・オデッセイ 台湾の賭け", "title_zh": "造山者", "title_en": "A Chip Odyssey", "director": None},
    {"original_title": "車頂上的玄天上帝", "title_ja": "めぐる面影、今、祖父に会う", "title_zh": "車頂上的玄天上帝", "title_en": "Be with Me", "director": None},
    {"original_title": "阿嬤的夢中情人", "title_ja": "台湾ハリウッド", "title_zh": "阿嬤的夢中情人", "title_en": "Forever Love", "director": "北村豊晴・蕭力修"},
    {"original_title": "超低預算電影大作戰", "title_ja": "超低予算ムービー大作戦", "title_zh": "超低預算電影大作戰", "title_en": "Ultra-Low Budget Movie", "director": None},
    {"original_title": "看海的日子", "title_ja": "海をみつめる日", "title_zh": "看海的日子", "title_en": "A Flower in the Rainy Night", "director": None},
    {"original_title": "余燼", "title_ja": "余燼", "title_zh": "余燼", "title_en": "Embers", "director": None},
    {"original_title": "殺夫", "title_ja": "夫殺し デジタル・リマスター版", "title_zh": "殺夫", "title_en": "The Woman of Wrath", "director": None},
    {"original_title": "種土", "title_ja": "ソウル・オブ・ソイル", "title_zh": "種土", "title_en": "Soul of Soil", "director": None},
    {"original_title": "優雅的邂逅", "title_ja": "優雅な邂逅", "title_zh": "優雅的邂逅", "title_en": "An Elegant Meeting", "director": None},
    {"original_title": "萬博追踪", "title_ja": "万博追跡", "title_zh": "萬博追踪", "title_en": "Expo Traces", "director": None},
    {"original_title": "日泰小食", "title_ja": "日泰食堂", "title_zh": "日泰小食", "title_en": "Nittai Shokudo", "director": None},
    {"original_title": "XiXi，請讓我跳舞", "title_ja": "XiXi、私を踊る", "title_zh": "XiXi，請讓我跳舞", "title_en": "XiXi, Let Me Dance", "director": None},
    {"original_title": "台灣Filmake", "title_ja": "台湾Filmake——映画に恋した3つの人生", "title_zh": "台灣Filmake——愛上電影的三個人生", "title_en": "Taiwan Filmake", "director": None},
    {"original_title": "那張照片裡的我們", "title_ja": "あの写真の私たち", "title_zh": "那張照片裡的我們", "title_en": "The Photos of Us", "director": None},
    {"original_title": "愛情城事", "title_ja": "タイペイ、アイラブユー", "title_zh": "愛情城事", "title_en": "Taipei I Love You", "director": None},
    {"original_title": "鰻魚", "title_ja": "うなぎ", "title_zh": "鰻魚", "title_en": "The Eel", "director": None},
    {"original_title": "今夜不回家", "title_ja": "今夜は帰らない デジタル・リマスター版", "title_zh": "今夜不回家", "title_en": "Tonight Nobody Goes Home", "director": None},
    {"original_title": "小鎮戀曲", "title_ja": "小さな町の恋 デジタル・リマスター版", "title_zh": "小鎮戀曲", "title_en": "Small Town Love Song", "director": None},
    {"original_title": "南方時光", "title_ja": "夜明けの前に", "title_zh": "南方時光", "title_en": "Before the Bright Day", "director": None},
    {"original_title": "愛作歹", "title_ja": "宵闇の火花", "title_zh": "愛作歹", "title_en": "Silent Sparks", "director": None},
    {"original_title": "甘露水", "title_ja": "甘露水", "title_zh": "甘露水", "title_en": "Sweet Dew", "director": None},
    {"original_title": "乒乓男孩", "title_ja": "燃えるダブルス魂", "title_zh": "乒乓男孩", "title_en": "Ping Pong Boys", "director": None},
    {"original_title": "猟人兄弟", "title_ja": "猟師兄弟", "title_zh": "猟人兄弟", "title_en": "Hunter Brothers", "director": None},
    {"original_title": "深度安靜", "title_ja": "深く静かな場所へ", "title_zh": "深度安靜", "title_en": "Deep Silence", "director": None},
    {"original_title": "（真）新的一天", "title_ja": "金魚の記憶", "title_zh": "（真）新的一天", "title_en": "Fish Memories", "director": None},
    {"original_title": "我在荒野做了一場夢", "title_ja": "荒野の夢", "title_zh": "我在荒野做了一場夢", "title_en": "A Dream in the Wilderness", "director": None},
    {"original_title": "中村地平", "title_ja": "中村地平", "title_zh": "中村地平", "title_en": "Nakamura Chihei", "director": None},
    {"original_title": "腎上腺母侵", "title_ja": "Adrenal", "title_zh": "腎上腺母侵", "title_en": "Adrenal", "director": None},
    {"original_title": "ナギ日記", "title_ja": "ナギダイアリー", "title_zh": "ナギ日記", "title_en": "Nagi Diary", "director": None},
    {"original_title": "同化的傷痕", "title_ja": "同化の傷痕", "title_zh": "同化的傷痕", "title_en": "Scars of Assimilation", "director": "寺田和弘"},
    {"original_title": "人生海海", "title_ja": "人生は海のように", "title_zh": "人生海海", "title_en": "Life is Like the Sea", "director": None},
    {"original_title": "樹冠羞避", "title_ja": "木々の隙間", "title_zh": "樹冠羞避", "title_en": "Crown Shyness", "director": None},
    {"original_title": "丟包阿公到我家", "title_ja": "エイプリル", "title_zh": "丟包阿公到我家", "title_en": "April", "director": None},
    {"original_title": "雙囍", "title_ja": "ダブル・ハピネス", "title_zh": "雙囍", "title_en": "Double Happiness", "director": None},
    {"original_title": "變的東西", "title_ja": "変なもの", "title_zh": "變的東西", "title_en": "Strange Things", "director": None},
]

# ── Event → Work mapping (8-char UUID prefix → original_title) ─

EVENT_WORK_MAP = {
    # 月老
    "f970e4e3": "月老", "4a8772ec": "月老", "a3ca9766": "月老", "6649f6ba": "月老",
    "458ee8f4": "月老", "ecfd1e11": "月老", "d18339d5": "月老", "51052464": "月老",
    "428d557e": "月老", "486a1259": "月老", "fc1b0730": "月老", "00dddea1": "月老",
    "f9216cea": "月老", "52805f03": "月老", "5d9bfe04": "月老", "50f6ffd1": "月老",
    "c8e813ae": "月老", "0f7af40b": "月老", "57642851": "月老", "858c5f04": "月老",
    # 大濛
    "dec5031b": "大濛", "d201c261": "大濛", "9ffae439": "大濛", "69ab0116": "大濛",
    "b5dfa718": "大濛", "5ed76270": "大濛", "3e32895c": "大濛", "dded67a6": "大濛",
    "71f575a4": "大濛", "c6d5232a": "大濛",
    # 造山者
    "8c94aaff": "造山者", "8355f633": "造山者", "0d33b617": "造山者",
    # 車頂上的玄天上帝
    "258ea821": "車頂上的玄天上帝", "5ea925e5": "車頂上的玄天上帝",
    "a04e7ebb": "車頂上的玄天上帝", "895d9c33": "車頂上的玄天上帝",
    # 阿嬤的夢中情人
    "1b323d3f": "阿嬤的夢中情人", "2358368c": "阿嬤的夢中情人",
    "24485f3c": "阿嬤的夢中情人", "b2d203cc": "阿嬤的夢中情人",
    "678bf526": "阿嬤的夢中情人", "04160fcf": "阿嬤的夢中情人", "d9f91974": "阿嬤的夢中情人",
    # 超低預算電影大作戰
    "4d8a1b9a": "超低預算電影大作戰", "347aca1b": "超低預算電影大作戰", "eeed6811": "超低預算電影大作戰",
    # 看海的日子
    "172047f5": "看海的日子", "16c3fa42": "看海的日子",
    "6ee668d1": "看海的日子", "75eef06e": "看海的日子",
    "b891cc5e": "看海的日子", "1a62d804": "看海的日子",
    # 余燼
    "fb0468b3": "余燼", "4ca410a3": "余燼", "994c7b98": "余燼",
    # 殺夫
    "2f50b8fd": "殺夫", "fddc2ff9": "殺夫", "cb4d9a09": "殺夫",
    # 種土
    "bedd3ba4": "種土", "2cd0769d": "種土", "9084ad67": "種土", "e646c256": "種土",
    # 優雅的邂逅
    "6200fbe1": "優雅的邂逅", "3645a3ac": "優雅的邂逅", "f7ff56ca": "優雅的邂逅",
    # 萬博追踪
    "052860bb": "萬博追踪", "bae8142a": "萬博追踪",
    # 日泰小食
    "62812720": "日泰小食", "745400e9": "日泰小食",
    # XiXi，請讓我跳舞
    "e910d7f2": "XiXi，請讓我跳舞", "dc233d36": "XiXi，請讓我跳舞",
    # 台灣Filmake
    "995801cc": "台灣Filmake", "261f38e5": "台灣Filmake", "2c3e1c29": "台灣Filmake",
    "a8ea4b5c": "台灣Filmake", "0bc40eb3": "台灣Filmake", "6885927b": "台灣Filmake",
    "4bc37dd5": "台灣Filmake", "debbaa09": "台灣Filmake",
    "84cb3ff3": "台灣Filmake", "2117c91e": "台灣Filmake", "05dfa591": "台灣Filmake",
    # 那張照片裡的我們
    "688361cc": "那張照片裡的我們", "77ddb0e6": "那張照片裡的我們", "3a4cc407": "那張照片裡的我們",
    # 愛情城事
    "9c36f36d": "愛情城事",
    # 鰻魚
    "efc14238": "鰻魚",
    # 今夜不回家
    "51087eec": "今夜不回家",
    # 小鎮戀曲
    "631f68a7": "小鎮戀曲",
    # 南方時光
    "383bf73e": "南方時光",
    # 愛作歹
    "dc84fe66": "愛作歹",
    # 甘露水
    "41bd830b": "甘露水",
    # 乒乓男孩
    "401bc0fa": "乒乓男孩",
    # 猟人兄弟
    "7fcc9b53": "猟人兄弟",
    # 深度安靜
    "39c00a4e": "深度安靜",
    # （真）新的一天
    "398c815c": "（真）新的一天",
    # 我在荒野做了一場夢
    "83a05243": "我在荒野做了一場夢",
    # 中村地平
    "87fd7249": "中村地平", "622f51c1": "中村地平",
    # 腎上腺母侵
    "d9bcd861": "腎上腺母侵",
    # ナギ日記
    "74ee5ac2": "ナギ日記",
    # 同化的傷痕
    "b5e81f45": "同化的傷痕", "05aefbdf": "同化的傷痕",
    # 人生海海
    "d0d85c6e": "人生海海",
    # 樹冠羞避
    "e2aa2c15": "樹冠羞避",
    # 丟包阿公到我家
    "603fce9e": "丟包阿公到我家",
    # 雙囍
    "f7b8a599": "雙囍",
    # 變的東西
    "7334bb8c": "變的東西",
}

# ── REST API helpers ──────────────────────────────────────────


def api(method, path, data=None, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text.strip() else []
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        print(f"  !! HTTP {e.code}: {err}", file=sys.stderr)
        raise


# ── Main ──────────────────────────────────────────────────────

def main():
    stats = {"works_created": 0, "works_updated": 0, "events_linked": 0,
             "events_name_ja_fixed": 0, "events_reactivated": 0,
             "field_corrections": 0, "errors": []}

    # ── Step 1: Upsert all works ──────────────────────────────
    print("=== Step 1: Upsert works ===")

    work_rows = []
    for w in WORKS:
        row = {
            "work_type": "film",
            "original_title": w["original_title"],
            "title_ja": w["title_ja"],
            "title_zh": w["title_zh"],
            "title_en": w["title_en"],
            "director": w["director"],
            "country": "TW",
        }
        work_rows.append(row)

    # Bulk upsert
    result = api(
        "POST",
        "works?on_conflict=original_title",
        data=work_rows,
        extra_headers={"Prefer": "return=representation,resolution=merge-duplicates"},
    )
    print(f"  Upserted {len(result)} works")

    # Build original_title → work record
    title_to_work = {}
    for r in result:
        title_to_work[r["original_title"]] = r
        print(f"  [{r['id'][:8]}] {r['original_title']}")

    # Count new vs updated (check created_at vs updated_at proximity)
    stats["works_created"] = len([r for r in result if r.get("created_at") == r.get("updated_at")])
    stats["works_updated"] = len(result) - stats["works_created"]

    # ── Step 2: Fetch all movie events ────────────────────────
    print("\n=== Step 2: Fetch movie events ===")

    all_events = []
    offset = 0
    batch_size = 1000
    while True:
        batch = api(
            "GET",
            f"events?category=cs.{{movie}}&select=id,source_name,name_ja,name_zh,name_en,is_active,work_id"
            f"&order=id&limit={batch_size}&offset={offset}",
        )
        all_events.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size

    print(f"  Fetched {len(all_events)} movie events")

    # Build prefix → full event
    prefix_to_event = {}
    for ev in all_events:
        prefix = ev["id"][:8]
        prefix_to_event[prefix] = ev

    # ── Step 3: Update mapped events ──────────────────────────
    print("\n=== Step 3: Update mapped events ===")

    mapped_ids = set()
    for prefix, original_title in EVENT_WORK_MAP.items():
        ev = prefix_to_event.get(prefix)
        if not ev:
            msg = f"  !! Event {prefix} not found in movie events"
            print(msg)
            stats["errors"].append(msg)
            continue

        work = title_to_work.get(original_title)
        if not work:
            msg = f"  !! Work '{original_title}' not found"
            print(msg)
            stats["errors"].append(msg)
            continue

        full_id = ev["id"]
        mapped_ids.add(full_id)
        source = ev.get("source_name", "")

        # Build update payload
        patch = {
            "work_id": work["id"],
            "name_zh": work["title_zh"],
            "name_en": work["title_en"],
            "is_active": True,
        }

        # name_ja logic:
        # - Authoritative sources: never change
        # - google_news_rss with "上映" pattern: use work's title_ja
        # - Others: don't change
        update_name_ja = False
        if source == "google_news_rss" and ev.get("name_ja") and "上映" in ev["name_ja"]:
            patch["name_ja"] = work["title_ja"]
            update_name_ja = True

        # PATCH event
        api(
            "PATCH",
            f"events?id=eq.{full_id}",
            data=patch,
            extra_headers={"Prefer": "return=minimal"},
        )

        ja_note = f" name_ja→{work['title_ja']}" if update_name_ja else ""
        print(f"  [{prefix}] {source:25s} → {original_title}{ja_note}")
        stats["events_linked"] += 1
        if update_name_ja:
            stats["events_name_ja_fixed"] += 1

        # Upsert field_correction for name_zh
        correction = {
            "event_id": full_id,
            "field_name": "name_zh",
            "corrected_value": work["title_zh"],
        }
        api(
            "POST",
            "field_corrections?on_conflict=event_id,field_name",
            data=correction,
            extra_headers={"Prefer": "return=minimal,resolution=merge-duplicates"},
        )
        stats["field_corrections"] += 1

    # ── Step 4: Reactivate remaining movie events ─────────────
    print("\n=== Step 4: Reactivate remaining movie events ===")

    inactive_ids = [ev["id"] for ev in all_events
                    if ev["id"] not in mapped_ids and not ev.get("is_active")]
    if inactive_ids:
        # Batch update in chunks of 100 (URL length limit)
        for i in range(0, len(inactive_ids), 100):
            chunk = inactive_ids[i:i + 100]
            id_filter = ",".join(chunk)
            api(
                "PATCH",
                f"events?id=in.({id_filter})",
                data={"is_active": True},
                extra_headers={"Prefer": "return=minimal"},
            )
        stats["events_reactivated"] = len(inactive_ids)
        print(f"  Reactivated {len(inactive_ids)} inactive movie events")
    else:
        print("  No inactive movie events to reactivate")

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  Works upserted:          {len(result)} ({stats['works_created']} new, {stats['works_updated']} updated)")
    print(f"  Events linked to works:  {stats['events_linked']}")
    print(f"  Events name_ja fixed:    {stats['events_name_ja_fixed']}")
    print(f"  Events reactivated:      {stats['events_reactivated']}")
    print(f"  Field corrections:       {stats['field_corrections']}")
    if stats["errors"]:
        print(f"  Errors:                  {len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"    {err}")
    else:
        print("  Errors:                  0")
    print("=" * 50)

    # --- Post-write enrichment reminder ---
    # This script uses urllib (no pip packages), but post_batch_enrich
    # requires supabase SDK. Try importing; if venv is active it works.
    try:
        from annotator import post_batch_enrich
        all_event_ids = [ev["id"] for ev in all_events]
        summary = post_batch_enrich(all_event_ids)
        print(f"\nPost-enrichment: {summary}")
    except ImportError:
        print("\n⚠ Remember to run enrichment after this script:")
        print("  cd scraper && source venv/bin/activate")
        print("  python annotator.py --enrich-movie-titles")
        print("  python annotator.py --enrich-person-names")
    except Exception as e:
        print(f"\n⚠ post_batch_enrich failed: {e}")
        print("  Run manually:")
        print("  python annotator.py --enrich-movie-titles")
        print("  python annotator.py --enrich-person-names")


if __name__ == "__main__":
    main()
