#!/usr/bin/env python3
"""
Backfill location_prefectures for parent + sub events.

Three passes (order matters):
  1. Multi-aggregation for parents — if sub-event addresses span ≥2 prefectures,
     write the sorted array to the parent.
  2. Single-row pass (default ON) — for any row (parent or sub) with
     location_prefectures IS NULL and a usable own address, write [pref].
     Use --no-single to skip this pass (legacy behavior).
  3. Sub-event parent-address fallback — for sub-events with NO own address
     but whose parent has a usable address, inherit prefecture from parent
     (writes location_prefectures only; does NOT modify location_address).

Run AFTER migration 012 has been applied in Supabase Dashboard:
    cd scraper && source ../.venv/bin/activate && python backfill_location_prefectures.py [--no-single] [--dry-run]
"""
import argparse
import os
import re
import logging
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# 政令指定都市 / major cities → prefecture (used when address omits 都道府県 prefix).
# Taiwan-style city names (台北市, 桃園市, etc.) are deliberately absent so they
# never match here; the 都道府県 regex above also rejects them, returning None.
_CITY_TO_PREF: dict[str, str] = {
    # 政令指定都市
    "横浜市": "神奈川県",
    "川崎市": "神奈川県",
    "相模原市": "神奈川県",
    "名古屋市": "愛知県",
    "福岡市": "福岡県",
    "北九州市": "福岡県",
    "札幌市": "北海道",
    "仙台市": "宮城県",
    "神戸市": "兵庫県",
    "さいたま市": "埼玉県",
    "千葉市": "千葉県",
    "広島市": "広島県",
    "新潟市": "新潟県",
    "静岡市": "静岡県",
    "浜松市": "静岡県",
    "堺市": "大阪府",
    "岡山市": "岡山県",
    "熊本市": "熊本県",
    # Tokyo 23 special wards (a 23-ward address with no 都 prefix is unambiguously Tokyo).
    **{w: "東京都" for w in [
        "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
        "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
        "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
        "葛飾区", "江戸川区",
    ]},
    # 県庁所在地 (non-seirei) — capital cities of remaining prefectures.
    "青森市": "青森県", "盛岡市": "岩手県", "秋田市": "秋田県", "山形市": "山形県",
    "福島市": "福島県", "水戸市": "茨城県", "宇都宮市": "栃木県", "前橋市": "群馬県",
    "富山市": "富山県", "金沢市": "石川県", "福井市": "福井県", "甲府市": "山梨県",
    "長野市": "長野県", "岐阜市": "岐阜県", "津市": "三重県", "大津市": "滋賀県",
    "奈良市": "奈良県", "和歌山市": "和歌山県", "鳥取市": "鳥取県", "松江市": "島根県",
    "山口市": "山口県", "徳島市": "徳島県", "高松市": "香川県", "松山市": "愛媛県",
    "高知市": "高知県", "佐賀市": "佐賀県", "長崎市": "長崎県", "大分市": "大分県",
    "宮崎市": "宮崎県", "鹿児島市": "鹿児島県", "那覇市": "沖縄県",
}

# English address fallback (e.g. "4-1-1 Miyoshi, Koto-ku, Tokyo").
_EN_TO_PREF: dict[str, str] = {"tokyo": "東京都", "osaka": "大阪府", "kyoto": "京都府"}

# Strip leading noise such as `日本、` and postal code `〒xxx-xxxx ` before matching.
_PREFIX_RE = re.compile(r"^(?:日本[、,]?\s*)?(?:〒\s*\d{3}-?\d{4}[\s　]*)?")


def extract_prefecture(address: str | None) -> str | None:
    """Extract prefecture name from a Japanese or Taiwanese address string."""
    if not address:
        return None
    # Support Taiwan cities: 台北市, 台北縣, 基隆市, etc. (including 臺 variants)
    tw_re = re.compile(r"([臺台]北|新北|桃園|[臺台]中|[臺台]南|高雄|基隆|新竹|苗栗|彰化|南投|雲林|嘉義|屏東|宜蘭|花蓮|[臺台]東|澎湖|金門|連江)(市|縣|県)")
    m_tw = tw_re.search(address)
    if m_tw:
        # Return full name with suffix e.g. "台北市"
        return m_tw.group(1) + m_tw.group(2)

    address = _PREFIX_RE.sub("", address).lstrip()
    # Japan prefecture names (anchored to start after prefix removal).
    m = re.match(r"^(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県\d〒-]{2,4}[都道府県])", address)
    if m:
        full = m.group(1)
        if full in ("大阪市", "大阪府"):
            return "大阪府"
        if full in ("京都市", "京都府"):
            return "京都府"
        return full  # 北海道, 東京都, ○○府, ○○道, ○○県 — suffix already included
    # Fallback: bare 政令市 name without 都道府県 prefix.
    for city, pref in _CITY_TO_PREF.items():
        if address.startswith(city):
            return pref
    # English address fallback.
    low = address.lower()
    for k, v in _EN_TO_PREF.items():
        if k in low:
            return v
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-single", action="store_true",
                        help="Skip single-row + sub-event passes; only do multi-aggregation for parents (legacy).")
    parser.add_argument("--include-single", action="store_true",
                        help="(deprecated, kept for compat) Single-row pass is now default ON.")
    parser.add_argument("--dry-run", action="store_true", help="Print would-update counts only; no DB writes.")
    args = parser.parse_args()

    do_single = not args.no_single

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Fetch ALL sub-events with location_address (including inactive — backfill
    # historical rows so reports & roadmap reflect total fill rate, not just active).
    logger.info("Fetching sub-events...")
    subs = (
        sb.table("events")
        .select("parent_event_id,location_address")
        .not_.is_("parent_event_id", "null")
        .execute()
    )

    # Aggregate prefectures per parent
    parent_prefectures: dict[str, set[str]] = defaultdict(set)
    for s in subs.data:
        pid = s["parent_event_id"]
        pref = extract_prefecture(s["location_address"])
        if pref:
            parent_prefectures[pid].add(pref)

    # Fetch ALL parent events (parent_event_id IS NULL), regardless of is_active.
    # Filter `location_prefectures IS NULL` is enforced row-by-row below to keep
    # idempotency (we still want to emit `skipped_existing` counter for visibility).
    logger.info("Fetching parent events (all is_active states)...")
    parents = (
        sb.table("events")
        .select("id,name_ja,location_address,location_prefectures")
        .is_("parent_event_id", "null")
        .execute()
    ).data

    scanned = len(parents)
    multi_updated = 0
    single_updated = 0
    skipped_existing = 0
    skipped_no_pref = 0

    # Build parent_id → location_address map for sub-event fallback (pass 3).
    parent_addr_map: dict[str, str | None] = {p["id"]: p.get("location_address") for p in parents}

    # ----- Pass 1: parents — multi-aggregation OR own-address single-row -----
    for p in parents:
        pid = p["id"]
        name = (p.get("name_ja") or pid)[:50]
        if p.get("location_prefectures"):
            skipped_existing += 1
            continue

        agg = parent_prefectures.get(pid, set())
        new_value: list[str] | None = None
        kind = ""
        if len(agg) >= 2:
            new_value = sorted(agg)
            kind = "multi"
        elif do_single:
            own_pref = extract_prefecture(p.get("location_address"))
            if own_pref:
                new_value = [own_pref]
                kind = "single"

        if not new_value:
            skipped_no_pref += 1
            continue

        if args.dry_run:
            logger.info("  [dry-run %s] PAR %s → %s", kind, name, new_value)
        else:
            try:
                sb.table("events").update({"location_prefectures": new_value}).eq("id", pid).execute()
                logger.info("  ✓ [%s] PAR %s → %s", kind, name, new_value)
            except Exception as e:
                logger.error("  ✗ %s: %s", pid, e)
                continue

        if kind == "multi":
            multi_updated += 1
        else:
            single_updated += 1

    # ----- Pass 2 + 3: sub-events — own address, or parent-address fallback -----
    sub_own_updated = 0
    sub_parent_fallback_updated = 0
    sub_skipped_existing = 0
    sub_skipped_no_pref = 0
    sub_scanned = 0

    if do_single:
        logger.info("Fetching sub-events (full rows for backfill)...")
        sub_rows = (
            sb.table("events")
            .select("id,name_ja,parent_event_id,location_address,location_prefectures")
            .not_.is_("parent_event_id", "null")
            .execute()
        ).data
        sub_scanned = len(sub_rows)

        for s in sub_rows:
            sid = s["id"]
            name = (s.get("name_ja") or sid)[:50]
            if s.get("location_prefectures"):
                sub_skipped_existing += 1
                continue

            own_addr = s.get("location_address")
            pref = extract_prefecture(own_addr)
            kind = "sub-own"

            if not pref:
                # Parent-address fallback (do NOT modify location_address).
                parent_addr = parent_addr_map.get(s.get("parent_event_id"))
                pref = extract_prefecture(parent_addr)
                kind = "sub-parent" if pref else ""

            if not pref:
                sub_skipped_no_pref += 1
                continue

            new_value = [pref]
            if args.dry_run:
                logger.info("  [dry-run %s] SUB %s → %s", kind, name, new_value)
            else:
                try:
                    sb.table("events").update({"location_prefectures": new_value}).eq("id", sid).execute()
                    logger.info("  ✓ [%s] SUB %s → %s", kind, name, new_value)
                except Exception as e:
                    logger.error("  ✗ %s: %s", sid, e)
                    continue

            if kind == "sub-own":
                sub_own_updated += 1
            else:
                sub_parent_fallback_updated += 1

    logger.info("=" * 60)
    logger.info("Scanned parents:               %d", scanned)
    logger.info("  Multi-city updated:          %d", multi_updated)
    logger.info("  Single-city updated:         %d", single_updated)
    logger.info("  Skipped (already set):       %d", skipped_existing)
    logger.info("  Skipped (no prefecture):     %d", skipped_no_pref)
    logger.info("Scanned sub-events:            %d", sub_scanned)
    logger.info("  Own-address updated:         %d", sub_own_updated)
    logger.info("  Parent-address updated:      %d", sub_parent_fallback_updated)
    logger.info("  Skipped (already set):       %d", sub_skipped_existing)
    logger.info("  Skipped (no prefecture):     %d", sub_skipped_no_pref)
    if args.dry_run:
        logger.info("(dry-run — no DB writes)")


if __name__ == "__main__":
    # Smoke-test the extractor: Taiwan addresses must now match.
    assert extract_prefecture("桃園市中壢區") == "桃園市"
    assert extract_prefecture("台北市信義區") == "台北市"
    assert extract_prefecture("新北市板橋區") == "新北市"
    assert extract_prefecture("福岡市博多区博多駅前1-1-1") == "福岡県"
    assert extract_prefecture("横浜市西区") == "神奈川県"
    assert extract_prefecture("東京都渋谷区") == "東京都"
    assert extract_prefecture("北海道札幌市中央区") == "北海道"
    assert extract_prefecture("大阪府大阪市北区") == "大阪府"
    assert extract_prefecture("〒310-0015　茨城県水戸市宮町1丁目7") == "茨城県"
    assert extract_prefecture("日本、〒106-0045 東京都港区麻布十番") == "東京都"
    assert extract_prefecture("港区麻布十番２丁目") == "東京都"
    assert extract_prefecture("渋谷区猿楽町17-10") == "東京都"
    assert extract_prefecture("〒338-8506 さいたま市中央区上峰3-15-1") == "埼玉県"
    assert extract_prefecture("高知市五台山4200-6") == "高知県"
    assert extract_prefecture("4-1-1 Miyoshi, Koto-ku, Tokyo 135-0022") == "東京都"
    assert extract_prefecture("津市本町1-1") == "三重県"
    assert extract_prefecture("那覇市首里") == "沖縄県"
    assert extract_prefecture("オンライン") is None
    main()
