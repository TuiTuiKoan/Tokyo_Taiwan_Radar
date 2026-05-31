"""Seed authoritative venues into venues table with pre-flight conflict checks.

Usage:
  python scraper/_oneoff_seed_authoritative_venues.py --dry-run
  python scraper/_oneoff_seed_authoritative_venues.py
"""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from collections import Counter
from typing import Any

from dotenv import load_dotenv

from database import _get_client


SEED_DATA: list[dict[str, Any]] = [
    {
        "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター",
        "canonical_name_zh": "台北駐日經濟文化代表處 台灣文化中心",
        "canonical_name_en": "Taiwan Cultural Center, Taipei Economic and Cultural Representative Office in Japan",
        "address": "東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "港区",
        "aliases": [
            "台湾文化センター",
            "台北駐日経済文化代表処台湾文化センター",
            "台湾文化中心",
        ],
        "homepage": "https://www.taiwanembassy.org/jp_ja/post/84095.html",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "平日 10:00〜17:00 / 土日祝休館",
    },
    {
        "canonical_name_ja": "ユーロライブ",
        "canonical_name_zh": "ユーロライブ",
        "canonical_name_en": "Euro Live",
        "address": "東京都渋谷区円山町1-5 KINOHAUS 2F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "渋谷区",
        "aliases": ["EURO LIVE", "ユーロライブ（渋谷）"],
        "homepage": "https://eurolive.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シネ・ヌーヴォ",
        "canonical_name_zh": "シネ・ヌーヴォ",
        "canonical_name_en": "Cine Nouveau",
        "address": "大阪府大阪市西区九条1-20-24",
        "prefecture": "大阪府",
        "prefectures": ["大阪府"],
        "city": "大阪市",
        "aliases": ["シネヌーヴォ", "CINE NOUVEAU"],
        "homepage": "https://www.cinenouveau.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "新文芸坐",
        "canonical_name_zh": "新文藝坐",
        "canonical_name_en": "Shin-Bungeiza",
        "address": "東京都豊島区東池袋1-43-5 マルハン池袋ビル3F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "豊島区",
        "aliases": ["しんぶんげいざ"],
        "homepage": "https://www.shin-bungeiza.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "京都シネマ",
        "canonical_name_zh": "京都電影院",
        "canonical_name_en": "Kyoto Cinema",
        "address": "京都府京都市下京区烏丸通四条下ル水銀屋町620 COCON KARASUMA 3F",
        "prefecture": "京都府",
        "prefectures": ["京都府"],
        "city": "京都市",
        "aliases": ["KYOTO CINEMA"],
        "homepage": "https://www.kyotocinema.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "福岡アジア美術館",
        "canonical_name_zh": "福岡亞洲美術館",
        "canonical_name_en": "Fukuoka Asian Art Museum",
        "address": "福岡県福岡市博多区下川端町3-1 リバレインセンタービル7F",
        "prefecture": "福岡県",
        "prefectures": ["福岡県"],
        "city": "福岡市",
        "aliases": ["FAAM"],
        "homepage": "https://faam.city.fukuoka.lg.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "9:30〜19:30（金・土は20:00まで）/ 水曜休館",
    },
    {
        "canonical_name_ja": "東京都写真美術館",
        "canonical_name_zh": "東京都寫真美術館",
        "canonical_name_en": "Tokyo Photographic Art Museum",
        "address": "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "目黒区",
        "aliases": ["TOP Museum"],
        "homepage": "https://topmuseum.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "10:00〜18:00（木・金曜日は20:00まで）/ 月曜休館",
    },
    {
        "canonical_name_ja": "東京国際映画祭",
        "canonical_name_zh": "東京國際影展",
        "canonical_name_en": "Tokyo International Film Festival",
        "address": None,
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "千代田区",
        "aliases": ["TIFF", "東京国際映画祭2026"],
        "homepage": "https://2025.tiff-jp.net/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "大阪アジアン映画祭",
        "canonical_name_zh": "大阪亞洲電影節",
        "canonical_name_en": "Osaka Asian Film Festival",
        "address": None,
        "prefecture": "大阪府",
        "prefectures": ["大阪府"],
        "city": "大阪市",
        "aliases": ["OAFF"],
        "homepage": "https://oaff.jp/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "横浜国際舞台芸術ミーティング",
        "canonical_name_zh": "橫濱國際表演藝術會議",
        "canonical_name_en": "Yokohama International Performing Arts Meeting",
        "address": None,
        "prefecture": "神奈川県",
        "prefectures": ["神奈川県"],
        "city": "横浜市",
        "aliases": ["YPAM"],
        "homepage": "https://ypam.jp/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "台灣國際紀錄片影展",
        "canonical_name_zh": "台灣國際紀錄片影展",
        "canonical_name_en": "Taiwan International Documentary Festival",
        "address": None,
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": None,
        "aliases": ["TIDF"],
        "homepage": "https://www.tidf.org.tw/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "道の駅まえばし赤城",
        "canonical_name_zh": "前橋赤城道路休息站",
        "canonical_name_en": "Roadside Station Maebashi Akagi",
        "address": "群馬県前橋市田口町36番地",
        "prefecture": "群馬県",
        "prefectures": ["群馬県"],
        "city": "前橋市",
        "aliases": ["道の駅 まえばし赤城", "まえばし赤城"],
        "homepage": "https://maebashi-akagi.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "あまや座",
        "canonical_name_zh": "あまや座",
        "canonical_name_en": "Amayaza",
        "address": "茨城県那珂市瓜連1724-2",
        "prefecture": "茨城県",
        "prefectures": ["茨城県"],
        "city": "那珂市",
        "aliases": ["あまや座", "amayaza"],
        "homepage": "https://amaya-za.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "ミッドランドシネマ 名古屋空港",
        "canonical_name_zh": "中部名古屋機場米德蘭影城",
        "canonical_name_en": "Midland Cinema Nagoya Airport",
        "address": "愛知県西春日井郡豊山町豊場南長廻間1 エアポートウォーク名古屋2F",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "西春日井郡豊山町",
        "aliases": ["ミッドランドシネマ名古屋空港", "ミッドランドシネマ 名古屋空港"],
        "homepage": "https://www.midland-cinema.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "劇場オープン時間等、日によって異なります",
    },
    {
        "canonical_name_ja": "御成座",
        "canonical_name_zh": "御成座",
        "canonical_name_en": "Onariza",
        "address": "秋田県大館市御成町1丁目11-22",
        "prefecture": "秋田県",
        "prefectures": ["秋田県"],
        "city": "大館市",
        "aliases": ["御成座", "Onariza"],
        "homepage": "http://onariza.oodate.or.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "高田世界館",
        "canonical_name_zh": "高田世界館",
        "canonical_name_en": "Takada Sekaikan",
        "address": "新潟県上越市本町6丁目4-21",
        "prefecture": "新潟県",
        "prefectures": ["新潟県"],
        "city": "上越市",
        "aliases": ["高田世界館", "Takada Sekaikan"],
        "homepage": "https://shintomiza.whitesnow.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "八丁座",
        "canonical_name_zh": "八丁座",
        "canonical_name_en": "Hatchobori",
        "address": "広島県広島市中区胡町6-26 福屋八丁堀本店8F",
        "prefecture": "広島県",
        "prefectures": ["広島県"],
        "city": "広島市",
        "aliases": ["八丁座", "Hatchobori", "サロンシネマ", "サロンシネマ1・2"],
        "homepage": "https://johakyu.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "サロンシネマ",
        "canonical_name_zh": "沙龍影城",
        "canonical_name_en": "Salon Cinema",
        "address": "広島県広島市中区八丁堀16-10 タカタビル8F",
        "prefecture": "広島県",
        "prefectures": ["広島県"],
        "city": "広島市",
        "aliases": ["サロンシネマ", "サロンシネマ1・2", "Salon Cinema"],
        "homepage": "https://johakyu.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "109シネマズ港北",
        "canonical_name_zh": "109影城港北",
        "canonical_name_en": "109 Cinemas Kohoku",
        "address": "神奈川県横浜市都筑区中川中央1-31-1 ノースポート・モール6F",
        "prefecture": "神奈川県",
        "prefectures": ["神奈川県"],
        "city": "横浜市",
        "aliases": ["109シネマズ港北", "109 Cinemas Kohoku"],
        "homepage": "https://109cinemas.net/kohoku/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "109シネマズ富谷",
        "canonical_name_zh": "109影城富谷",
        "canonical_name_en": "109 Cinemas Tomiya",
        "address": "宮城県富谷市大清水1丁目33-1 イオンモール富谷 別棟",
        "prefecture": "宮城県",
        "prefectures": ["宮城県"],
        "city": "富谷市",
        "aliases": ["109シネマズ富谷", "109 Cinemas Tomiya"],
        "homepage": "https://109cinemas.net/tomiya/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "松本シネマセレクト",
        "canonical_name_zh": "松本電影選",
        "canonical_name_en": "Matsumoto Cinema Select",
        "address": "長野県松本市深志3-10-18",
        "prefecture": "長野県",
        "prefectures": ["長野県"],
        "city": "松本市",
        "aliases": ["松本シネマセレクト", "松本シネマセレクト（長野）", "ＮＰＯ松本シネマセレクト"],
        "homepage": "https://www.cinema-select.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマつくば",
        "canonical_name_zh": "United Cinemas 筑波",
        "canonical_name_en": "United Cinemas Tsukuba",
        "address": "茨城県つくば市小野崎字177-1 iiasつくば3F",
        "prefecture": "茨城県",
        "prefectures": ["茨城県"],
        "city": "つくば市",
        "aliases": ["ユナイテッド・シネマつくば", "ユナイテッドシネマ つくば", "united_cinemas_tsukuba"],
        "homepage": "https://www.unitedcinemas.jp/tsukuba/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマ豊橋",
        "canonical_name_zh": "United Cinemas 豐橋",
        "canonical_name_en": "United Cinemas Toyohashi",
        "address": "愛知県豊橋市藤沢町141 ホリデイ・スクエア内",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "豊橋市",
        "aliases": ["ユナイテッド・シネマ豊橋", "ユナイテッドシネマ 豊橋", "united_cinemas_toyohashi"],
        "homepage": "https://www.unitedcinemas.jp/toyohashi/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマ橿原",
        "canonical_name_zh": "United Cinemas 橿原",
        "canonical_name_en": "United Cinemas Kashihara",
        "address": "奈良県橿原市十市町1222-1 ツインゲート橿原内",
        "prefecture": "奈良県",
        "prefectures": ["奈良県"],
        "city": "橿原市",
        "aliases": ["ユナイテッド・シネマ橿原", "ユナイテッドシネマ 橿原", "united_cinemas_kashihara"],
        "homepage": "https://www.unitedcinemas.jp/kashihara/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "上田映劇",
        "canonical_name_zh": "上田映劇",
        "canonical_name_en": "Ueda Eigeki",
        "address": "長野県上田市中央2丁目12-30",
        "prefecture": "長野県",
        "prefectures": ["長野県"],
        "city": "上田市",
        "aliases": ["上田映劇", "uedaeigeki", "UEDA EIGEKI"],
        "homepage": "https://www.uedaeigeki.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シエマ",
        "canonical_name_zh": "シエマ",
        "canonical_name_en": "CIEMA",
        "address": "佐賀県佐賀市松原2丁目14-16 セントラルプラザ3F",
        "prefecture": "佐賀県",
        "prefectures": ["佐賀県"],
        "city": "佐賀市",
        "aliases": ["シエマ", "ciema", "CIEMA"],
        "homepage": "http://ciema.info",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "OYAMA Cinema ROBLE",
        "canonical_name_zh": "OYAMA Cinema ROBLE",
        "canonical_name_en": "OYAMA Cinema ROBLE",
        "address": "栃木県小山市中央町3-7-1 ロブレ7F",
        "prefecture": "栃木県",
        "prefectures": ["栃木県"],
        "city": "小山市",
        "aliases": ["OYAMA Cinema ROBLE", "ロブレ", "ロブレ5"],
        "homepage": "https://www.ginsee.jp/roble/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "宇都宮ヒカリ座",
        "canonical_name_zh": "宇都宮ヒカリ座",
        "canonical_name_en": "Utsunomiya Hikariza",
        "address": "栃木県宇都宮市江野町7-13 プラザヒカリビル5F",
        "prefecture": "栃木県",
        "prefectures": ["栃木県"],
        "city": "宇都宮市",
        "aliases": ["宇都宮ヒカリ座", "ヒカリ座"],
        "homepage": "https://www.ginsee.jp/hikariza/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シネプラザサントムーン",
        "canonical_name_zh": "Cineplaza Suntomoon",
        "canonical_name_en": "Cineplaza Suntomoon",
        "address": "静岡県駿東郡清水町伏見52-1 サントムーン柿田川内",
        "prefecture": "静岡県",
        "prefectures": ["静岡県"],
        "city": "駿東郡清水町",
        "aliases": ["シネプラザサントムーン", "シネプラザ サントムーン"],
        "homepage": "https://cineplaza.net",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
]

_AUTHORITY_COLUMNS = (
    "is_authoritative",
    "is_multi_venue",
    "homepage",
    "prefectures",
)


def _distinct_non_empty(values: list[str | None]) -> list[str]:
    return sorted({(v or "").strip() for v in values if (v or "").strip()})


# ── Address normalisation helpers ────────────────────────────────────────────

_STREET_NUM_RE = re.compile(r"\d+(?:-\d+)+")


def _normalize_addr(addr: str) -> str:
    """NFKC-normalise (collapses full-width spaces/digits) and strip."""
    return unicodedata.normalize("NFKC", addr or "").strip()


def _street_prefix(addr: str) -> str:
    """Return the address truncated at the end of the street number (番地),
    discarding building name / floor details.

    Examples:
      '東京都港区虎ノ門1-1-12 虎ノ門ビル2階'  →  '東京都港区虎ノ門1-1-12'
      '福岡県福岡市博多区下川端町3-1 リバレイン7F・8F'  →  '福岡県福岡市博多区下川端町3-1'
    """
    a = _normalize_addr(addr)
    m = _STREET_NUM_RE.search(a)
    return a[: m.end()].strip() if m else a


def _addresses_compatible(a: str, b: str) -> bool:
    """Return True when *a* and *b* describe the same physical location.

    Handles:
    - Full-width characters (\u3000, ２, etc.) via NFKC normalisation
    - Missing prefecture prefix (e.g. '港区虎ノ門1-1-12' vs '東京都港区虎ノ門1-1-12')
    - Differing building/floor detail (shorter = less detail is OK)
    - 7F vs 7F・8F (both truncated to same street prefix)
    """
    pa, pb = _street_prefix(a), _street_prefix(b)
    if not pa or not pb:
        return _normalize_addr(a) == _normalize_addr(b)
    # Exact street match, or one is a suffix of the other (missing prefecture prefix)
    return pa == pb or pa.endswith(pb) or pb.endswith(pa)


def _merge_aliases(existing: list[str] | None, incoming: list[str] | None, canonical: str) -> list[str]:
    merged = {(a or "").strip() for a in (existing or []) + (incoming or []) if (a or "").strip()}
    merged.discard(canonical)
    return sorted(merged)


def _get_event_rows_for_seed(sb, row: dict[str, Any]) -> list[dict[str, Any]]:
    names = [row["canonical_name_ja"]] + (row.get("aliases") or [])
    name_rows = (
        sb.table("events")
        .select("id,location_name,location_address,is_active")
        .in_("location_name", names)
        .execute()
        .data
        or []
    )
    return name_rows


def _has_conflict(seed_row: dict[str, Any], event_rows: list[dict[str, Any]]) -> tuple[bool, list[str], list[str]]:
    seed_address = (seed_row.get("address") or "").strip()
    # Only consider active events — inactive gnews/secondhand events often carry stale addresses
    active_rows = [r for r in event_rows if r.get("is_active", True)]
    db_addresses = _distinct_non_empty([r.get("location_address") for r in active_rows])
    if not db_addresses:
        return False, db_addresses, []
    if not seed_address:
        return False, db_addresses, []
    # Use street-level normalised comparison instead of exact string match
    conflicts = [a for a in db_addresses if not _addresses_compatible(a, seed_address)]
    return len(conflicts) > 0, db_addresses, conflicts


def _is_missing_authority_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("column" in msg or "schema cache" in msg) and "venues" in msg and any(c in msg for c in _AUTHORITY_COLUMNS)


def _assert_authority_columns_ready(sb) -> None:
    try:
        (
            sb.table("venues")
            .select("is_authoritative,is_multi_venue,homepage,prefectures")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        if not _is_missing_authority_column_error(exc):
            raise
        print(
            "[ERROR] venues authority migration 未套用：缺少欄位 "
            "is_authoritative/is_multi_venue/homepage/prefectures。"
        )
        print("[ERROR] 請先套用 supabase/migrations/076_venues_authority.sql 後再重跑。")
        raise SystemExit(2)


def run(dry_run: bool) -> None:
    sb = _get_client()
    _assert_authority_columns_ready(sb)
    stats = Counter(insert=0, update=0, skip=0, conflict=0)

    skip_keys: set[str] = set()
    for row in SEED_DATA:
        matches = _get_event_rows_for_seed(sb, row)
        has_conflict, db_addresses, conflicts = _has_conflict(row, matches)
        if not has_conflict:
            continue
        stats["conflict"] += 1
        stats["skip"] += 1
        skip_keys.add(row["canonical_name_ja"])
        example_ids = [m["id"][:8] for m in matches if (m.get("location_address") or "").strip() in conflicts][:5]
        print(
            "[WARN conflict]",
            row["canonical_name_ja"],
            "seed=",
            row.get("address"),
            "db=",
            db_addresses,
            "event_ids=",
            example_ids,
        )

    for row in SEED_DATA:
        canonical = row["canonical_name_ja"]
        if canonical in skip_keys:
            print(f"[SKIP] {canonical} (pre-flight conflict)")
            continue

        existing = (
            sb.table("venues")
            .select("id,aliases")
            .eq("canonical_name_ja", canonical)
            .limit(1)
            .execute()
            .data
            or []
        )

        payload = dict(row)
        payload["aliases"] = _merge_aliases(
            existing[0].get("aliases") if existing else None,
            payload.get("aliases") or [],
            canonical,
        )

        action = "update" if existing else "insert"
        stats[action] += 1

        if dry_run:
            print(f"[DRY-RUN {action}] {canonical} aliases={len(payload['aliases'])}")
            continue

        sb.table("venues").upsert(payload, on_conflict="canonical_name_ja").execute()
        print(f"[APPLY {action}] {canonical}")

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(
        f"[{mode}] done | insert={stats['insert']} update={stats['update']} "
        f"skip={stats['skip']} conflict={stats['conflict']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed authoritative venues with conflict-safe pre-flight check")
    parser.add_argument("--dry-run", action="store_true", help="Show planned writes without DB mutation")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(args.dry_run)


if __name__ == "__main__":
    main()
