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

Run AFTER migration 012 has been applied in Supabase Dashboard. Dry-run is the
DEFAULT (no DB writes); pass --apply to persist:
    cd scraper && source ../.venv/bin/activate && python backfill_location_prefectures.py --apply [--no-single]

NOTE: automated callers (.github/workflows/scraper.yml) must pass --apply, or the
daily backfill becomes a no-op dry-run.
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

# Formal Japanese prefectures, anchored to the START of a normalized address.
# 東京都 is listed before 京都府 so it wins the alternation (avoids the 京都
# substring pitfall). Every non-県 prefecture is enumerated explicitly, so the
# generic branch only needs 2-3 stem chars + 県 (神奈川/和歌山/鹿児島 are the
# 3-char stems) — no over-stripping via rstrip("都道府県").
_JP_PREF_RE = re.compile(
    r"^(北海道|東京都|大阪府|京都府|大阪市|京都市|[^\s都道府県\d〒-]{2,3}県)"
)

# Taiwan locality aliases (short names, incl. 臺 variants).
_TW_ALIASES = (
    r"[臺台]北|新北|桃園|[臺台]中|[臺台]南|高雄|基隆|新竹|苗栗|彰化|"
    r"南投|雲林|嘉義|屏東|宜蘭|花蓮|[臺台]東|澎湖|金門|連江"
)
# Taiwan matches ONLY when the alias sits at the normalized address START
# followed by a Taiwan suffix/delimiter (市 / 縣 / 區 / space / digit / end), OR
# when it carries an explicit 市/縣 suffix anywhere. A bare mid-string alias
# (e.g. 新北 inside 大阪府…住之江区新北島) must NOT match. Taiwan uses 區(U+5340)
# / 縣(U+7E23) whereas Japan uses 区(U+533A) / 県(U+770C), so 台東区 (Tokyo) is
# never treated as Taiwan — it is resolved earlier via _CITY_TO_PREF.
_TW_START_RE = re.compile(rf"^({_TW_ALIASES})(?:[市縣區]|[\s　]|$|[0-9０-９])")
_TW_SUFFIX_RE = re.compile(rf"({_TW_ALIASES})[市縣]")

# Bounded label / country / postal prefixes stripped before prefecture matching.
_LABEL_PREFIX_RE = re.compile(
    r"^(?:会場住所|会場所在地|開催場所|開催地|所在地|住所|会場|場所)(?:は|:|：)?[\s　、,]*"
)
_COUNTRY_PREFIX_RE = re.compile(r"^日本[、,]?[\s　]*")
_POSTAL_PREFIX_RE = re.compile(r"^〒?\s*\d{3}-?\d{4}[\s　]*")


def _normalize_address(address: str) -> str:
    """Strip stacked label / country / postal prefixes (bounded loop)."""
    s = address.strip()
    prev = None
    for _ in range(6):  # bounded: handles stacked prefixes, never loops unbounded
        if s == prev:
            break
        prev = s
        s = _LABEL_PREFIX_RE.sub("", s)
        s = _COUNTRY_PREFIX_RE.sub("", s)
        s = _POSTAL_PREFIX_RE.sub("", s)
        s = s.lstrip("　 \t、,:：")
    return s


def extract_prefecture(address: str | None) -> str | None:
    """Extract a prefecture name from a Japanese or Taiwanese address string.

    Japanese prefectures are matched FIRST (anchored, canonical forms), then
    政令市 / ward lookup, then — only as a last, restricted step — Taiwan
    aliases. This ordering ensures a Japanese address that merely contains a
    Taiwan-like substring (大阪府…新北島) resolves to 大阪府, never 新北.
    """
    if not address:
        return None

    norm = _normalize_address(address)
    if not norm:
        return None

    # 1) Formal Japanese prefecture at the start (canonical values).
    m = _JP_PREF_RE.match(norm)
    if m:
        full = m.group(1)
        if full in ("大阪市", "大阪府"):
            return "大阪府"
        if full in ("京都市", "京都府"):
            return "京都府"
        return full  # 北海道 / 東京都 / ○○県 — suffix already canonical

    # 2) Bare 政令市 / 23-ward / 県庁所在地 name without a 都道府県 prefix.
    for city, pref in _CITY_TO_PREF.items():
        if norm.startswith(city):
            return pref

    # 3) Taiwan localities — restricted (start-anchored or explicit 市/縣 suffix).
    m_tw = _TW_START_RE.match(norm) or _TW_SUFFIX_RE.search(norm)
    if m_tw:
        return m_tw.group(1).replace("臺", "台")

    # 4) English address fallback.
    low = norm.lower()
    for k, v in _EN_TO_PREF.items():
        if k in low:
            return v
    return None


def fetch_all_rows(
    sb,
    table: str,
    columns: str,
    *,
    apply_filters=None,
    order_col: str = "id",
    page_size: int = 1000,
    label: str = "",
) -> list[dict]:
    """Fetch ALL rows for a query, paginating past Supabase's ~1000-row cap.

    Supabase silently caps a single response at 1000 rows, so an unpaginated
    ``.execute()`` drops later events. This reads the exact count, then
    accumulates fixed-size pages via ``.range()`` ordered by ``order_col`` for
    stable slicing, logging per-page / exact / accumulated counts.

    ``apply_filters`` is an optional callable applied to BOTH the count-head
    request and each page request, e.g.
    ``lambda q: q.not_.is_("parent_event_id", "null")``.
    """
    tag = label or table

    count_q = sb.table(table).select(order_col, count="exact", head=True)
    if apply_filters:
        count_q = apply_filters(count_q)
    exact = count_q.execute().count
    logger.info("  [%s] exact count = %s", tag, exact)

    rows: list[dict] = []
    start = 0
    while True:
        page_q = sb.table(table).select(columns)
        if apply_filters:
            page_q = apply_filters(page_q)
        page = (
            page_q.order(order_col)
            .range(start, start + page_size - 1)
            .execute()
            .data
        ) or []
        rows.extend(page)
        logger.info(
            "  [%s] page @%d: +%d (accumulated %d)", tag, start, len(page), len(rows)
        )
        if len(page) < page_size:
            break
        start += page_size

    if exact is not None and len(rows) != exact:
        logger.warning("  [%s] accumulated %d != exact count %d", tag, len(rows), exact)
    return rows


def _verify_write(sb, event_id: str, expected: list[str]) -> None:
    """Re-read location_prefectures after a write; warn on mismatch (G2 step 7).

    This backfill only writes the events table (no field_corrections rows), so
    there is no FC row to re-read.
    """
    try:
        rb = (
            sb.table("events")
            .select("location_prefectures")
            .eq("id", event_id)
            .execute()
            .data
        )
        got = rb[0].get("location_prefectures") if rb else None
        if got != expected:
            logger.warning(
                "  read-back mismatch id=%s: wrote %s got %s", event_id, expected, got
            )
    except Exception as e:  # read-back must never abort the backfill
        logger.warning("  read-back failed id=%s: %s", event_id, e)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-single", action="store_true",
                        help="Skip single-row + sub-event passes; only do multi-aggregation for parents (legacy).")
    parser.add_argument("--include-single", action="store_true",
                        help="(deprecated, kept for compat) Single-row pass is now default ON.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Force dry-run (no DB writes). Dry-run is already the DEFAULT.")
    parser.add_argument("--apply", action="store_true",
                        help="Persist changes to Supabase. Without --apply this is a dry-run.")
    args = parser.parse_args()

    do_single = not args.no_single
    # Dry-run is the DEFAULT; writes require an explicit --apply. --dry-run still
    # forces dry-run and wins if both are given (safety-first).
    dry_run = args.dry_run or not args.apply
    if dry_run and not args.dry_run:
        logger.info("No --apply flag: DRY-RUN mode (no DB writes). Pass --apply to persist.")

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Fetch ALL sub-events with location_address (including inactive — backfill
    # historical rows so reports & roadmap reflect total fill rate, not just active).
    logger.info("Fetching sub-events (aggregation pass)...")
    subs_data = fetch_all_rows(
        sb,
        "events",
        "parent_event_id,location_address",
        apply_filters=lambda q: q.not_.is_("parent_event_id", "null"),
        label="sub-agg",
    )

    # Aggregate prefectures per parent
    parent_prefectures: dict[str, set[str]] = defaultdict(set)
    for s in subs_data:
        pid = s["parent_event_id"]
        pref = extract_prefecture(s["location_address"])
        if pref:
            parent_prefectures[pid].add(pref)

    # Fetch ALL parent events (parent_event_id IS NULL), regardless of is_active.
    # Filter `location_prefectures IS NULL` is enforced row-by-row below to keep
    # idempotency (we still want to emit `skipped_existing` counter for visibility).
    logger.info("Fetching parent events (all is_active states)...")
    parents = fetch_all_rows(
        sb,
        "events",
        "id,name_ja,location_address,location_prefectures",
        apply_filters=lambda q: q.is_("parent_event_id", "null"),
        label="parents",
    )

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

        if dry_run:
            logger.info("  [dry-run %s] PAR %s → %s", kind, name, new_value)
        else:
            try:
                sb.table("events").update({"location_prefectures": new_value}).eq("id", pid).execute()
                logger.info("  ✓ [%s] PAR %s → %s", kind, name, new_value)
                _verify_write(sb, pid, new_value)
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
        sub_rows = fetch_all_rows(
            sb,
            "events",
            "id,name_ja,parent_event_id,location_address,location_prefectures",
            apply_filters=lambda q: q.not_.is_("parent_event_id", "null"),
            label="sub-full",
        )
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
            if dry_run:
                logger.info("  [dry-run %s] SUB %s → %s", kind, name, new_value)
            else:
                try:
                    sb.table("events").update({"location_prefectures": new_value}).eq("id", sid).execute()
                    logger.info("  ✓ [%s] SUB %s → %s", kind, name, new_value)
                    _verify_write(sb, sid, new_value)
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
    if dry_run:
        logger.info("(dry-run — no DB writes; pass --apply to persist)")


if __name__ == "__main__":
    # Smoke-test the extractor: Taiwan addresses must now match.
    assert extract_prefecture("桃園市中壢區") == "桃園"
    assert extract_prefecture("台北市信義區") == "台北"
    assert extract_prefecture("新北市板橋區") == "新北"
    assert extract_prefecture("台北") == "台北"
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
