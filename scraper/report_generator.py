"""
report_generator.py — 台湾関連イベント月次レポート生成器

Usage:
    python report_generator.py --month 2026-05 [--format markdown]

Output:
    scraper/reports/YYYY-MM_taiwan_japan_events.md
"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")

# ---------------------------------------------------------------------------
# Category display name (Japanese)
# ---------------------------------------------------------------------------
CATEGORY_JA = {
    "movie": "映画",
    "lecture": "講座",
    "lifestyle_food": "ライフスタイル・グルメ",
    "history": "歴史・文化遺産・ルーツ",
    "academic": "学術・研究",
    "geopolitics": "社会・政治・国際関係",
    "performing_arts": "音楽・演劇",
    "senses": "台湾の感性・アイデンティティ",
    "taiwan_japan": "台日交流",
    "books_media": "書籍・メディア",
    "tv_program": "テレビ番組",
    "workshop": "体験・ワークショップ",
    "art": "アート",
    "retail": "ブランド・ショッピング",
    "tech": "テクノロジー",
    "business": "ビジネス",
    "gender": "ジェンダー",
    "competition": "スポーツ・コンテスト",
    "report": "レポート",
    "tourism": "観光",
    "nature": "風土・果物・SDG",
    "indigenous": "先住民文化",
    "urban": "建築・まちづくり",
    "literature": "文学",
    "exhibition": "展覧会",
    "taiwan_mandarin": "台湾華語",
    "drama": "連続ドラマ",
    "healthcare": "医療・ケア",
    "documentary": "ドキュメンタリー",
    "parenting": "親子・子育て",
    "tea_alcohol": "お茶・お酒",
}

# ---------------------------------------------------------------------------
# Broadcast exclusion — sources and categories excluded from client reports
# ---------------------------------------------------------------------------
_BROADCAST_SOURCES: frozenset[str] = frozenset({"gguide_tv"})
_BROADCAST_CATEGORIES: frozenset[str] = frozenset({"tv_program", "drama"})

# Organizer name aliases: raw DB string → canonical display name
_ORGANIZER_ALIASES: dict[str, str] = {
    "台北駐日経済文化代表処 台湾文化センター": "台湾文化センター",
    "台湾駐日本代表処 台湾文化センター": "台湾文化センター",
    "台北駐大阪経済文化弁事処 台湾文化センター": "台湾文化センター大阪",
    "台北駐大阪経済文化弁事処台湾文化センター": "台湾文化センター大阪",
}

# ---------------------------------------------------------------------------
# URL → short domain name
# ---------------------------------------------------------------------------
_DOMAIN_ALIAS = {
    "prtimes.jp": "prtimes",
    "news.google.com": "gnews",
    "nhk.or.jp": "nhk",
    "walkerplus.com": "walkerplus",
    "arukikata.co.jp": "arukikata",
}


def _url_to_source_name(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        host = host.removeprefix("www.")
        for key, alias in _DOMAIN_ALIAS.items():
            if key in host:
                return alias
        # return base domain (e.g. "peatix.com")
        return host
    except Exception:
        return url[:40]


def _is_broadcast(event: dict) -> bool:
    """Return True if the event is TV/broadcast content to exclude from client reports."""
    if event.get("source_name") in _BROADCAST_SOURCES:
        return True
    cats = set(event.get("category") or [])
    return bool(cats) and cats.issubset(_BROADCAST_CATEGORIES)


def _group_by_title(rows: list[dict]) -> list[dict]:
    """Group media-coverage rows by event title, summing counts across all screenings."""
    grouped: dict[str, dict] = {}
    for row in rows:
        name = row.get("name_ja") or "(無題)"
        if name not in grouped:
            grouped[name] = {"name_ja": name, "media_count": 0, "media_source_names": set()}
        grouped[name]["media_count"] += row.get("media_count") or 0
        src_names = row.get("media_source_names") or []
        if isinstance(src_names, list):
            grouped[name]["media_source_names"].update(src_names)
    result = sorted(grouped.values(), key=lambda x: x["media_count"], reverse=True)
    for r in result:
        r["media_source_names"] = sorted(r["media_source_names"])
    return result


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------
def _get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Data fetch helpers
# ---------------------------------------------------------------------------
PAGE_SIZE = 1000


def _fetch_all(sb, table: str, select: str, filters=None):
    """Fetch all rows with pagination."""
    rows = []
    offset = 0
    while True:
        q = sb.table(table).select(select)
        if filters:
            for method, *args in filters:
                q = getattr(q, method)(*args)
        chunk = q.range(offset, offset + PAGE_SIZE - 1).execute().data
        rows.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def _base_filters():
    """Common filter list for active+annotated/reviewed events."""
    return [
        ("eq", "is_active", True),
        ("in_", "annotation_status", ["annotated", "reviewed"]),
    ]


def _month_range(month: str) -> tuple[str, str]:
    """Return (start_date_inclusive, end_date_exclusive) for a YYYY-MM month string."""
    year, mo = int(month[:4]), int(month[5:7])
    start = f"{year:04d}-{mo:02d}-01"
    if mo == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{mo + 1:02d}-01"
    return start, end


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_section1(sb, month: str) -> str:
    """月次概要"""
    start_d, end_d = _month_range(month)

    # All active+annotated/reviewed events in the month
    month_events = _fetch_all(
        sb, "events",
        "id,source_name,created_at,has_chinese_support",
        [
            ("eq", "is_active", True),
            ("in_", "annotation_status", ["annotated", "reviewed"]),
            ("gte", "start_date", start_d),
            ("lt", "start_date", end_d),
        ],
    )
    month_events = [e for e in month_events if e.get("source_name") not in _BROADCAST_SOURCES]
    total = len(month_events)

    month_start = start_d
    new_events = [e for e in month_events if (e.get("created_at") or "") >= month_start]
    existing_events = total - len(new_events)

    chinese_support = sum(1 for e in month_events if e.get("has_chinese_support"))

    source_counter: Counter = Counter(e.get("source_name", "(unknown)") for e in month_events)
    top5_sources = source_counter.most_common(5)

    lines = [
        "## 1. 月次概要\n",
        f"- **対象月**: {month}",
        f"- **イベント総数**: {total} 件 (active + annotated/reviewed)",
        f"- **当月新規**: {len(new_events)} 件 / **既存**: {existing_events} 件",
        f"- **中国語サポートあり**: {chinese_support} 件",
        "",
        "### データソース Top 5\n",
        "| ソース | 件数 |",
        "|--------|------|",
    ]
    for src, cnt in top5_sources:
        lines.append(f"| {src} | {cnt} |")
    lines.append("")
    return "\n".join(lines)


def build_section2(month_events: list) -> str:
    """カテゴリ分布"""
    cat_counter: Counter = Counter()
    for e in month_events:
        for cat in (e.get("category") or []):
            cat_counter[cat] += 1

    lines = [
        "## 2. カテゴリ分布\n",
        "| カテゴリ | 表示名 | 件数 |",
        "|----------|--------|------|",
    ]
    for cat, cnt in cat_counter.most_common():
        ja_name = CATEGORY_JA.get(cat, cat)
        lines.append(f"| {cat} | {ja_name} | {cnt} |")
    lines.append("")
    return "\n".join(lines)


def build_section3(month_events: list) -> str:
    """都道府県分布 Top 10"""
    pref_counter: Counter = Counter()
    for e in month_events:
        for pref in (e.get("location_prefectures") or []):
            pref_counter[pref] += 1

    total_pref = sum(pref_counter.values())
    tokyo_cnt = pref_counter.get("東京都", 0) or pref_counter.get("東京", 0)
    tokyo_pct = round(tokyo_cnt / total_pref * 100, 1) if total_pref else 0

    lines = [
        "## 3. 都道府県分布 Top 10\n",
        f"（東京集中率: {tokyo_pct}%）\n",
        "| 順位 | 都道府県 | 件数 |",
        "|------|----------|------|",
    ]
    for rank, (pref, cnt) in enumerate(pref_counter.most_common(10), 1):
        lines.append(f"| {rank} | {pref} | {cnt} |")
    lines.append("")
    return "\n".join(lines)


def build_section4(sb, month_events: list) -> str:
    """主催者 Top 10 — JOIN organizers, fallback to organizer text"""
    # Collect event IDs for this month
    event_ids = [e["id"] for e in month_events]

    # Fetch organizer_id for each event in this month
    org_rows = []
    chunk_size = 100
    for i in range(0, len(event_ids), chunk_size):
        chunk = event_ids[i : i + chunk_size]
        r = sb.table("events").select("id,organizer_id,organizer").in_("id", chunk).execute()
        org_rows.extend(r.data)

    # Load organizers table (canonical_name_ja keyed by id)
    try:
        organizer_rows = _fetch_all(sb, "organizers", "id,canonical_name_ja")
        org_name_map = {r["id"]: r["canonical_name_ja"] for r in organizer_rows}
    except Exception:
        org_name_map = {}

    org_counter: Counter = Counter()
    for row in org_rows:
        oid = row.get("organizer_id")
        if oid and oid in org_name_map:
            name = org_name_map[oid]
        else:
            name = row.get("organizer") or None
        if name:
            name = _ORGANIZER_ALIASES.get(name, name)
            org_counter[name] += 1

    lines = [
        "## 4. 主催者 Top 10\n",
        "| 順位 | 主催者 | 件数 |",
        "|------|--------|------|",
    ]
    for rank, (name, cnt) in enumerate(org_counter.most_common(10), 1):
        lines.append(f"| {rank} | {name} | {cnt} |")
    lines.append("")
    return "\n".join(lines)


def build_section5(sb, month: str) -> str:
    """メディア露出 Top 10 — grouped by title across all screenings"""
    start_d, end_d = _month_range(month)

    rows: list[dict] = []
    try:
        r = sb.table("event_media_coverage").select(
            "event_id,name_ja,start_date,media_count,media_urls,media_source_names"
        ).gte("start_date", start_d).lt("start_date", end_d).order("media_count", desc=True).execute()
        rows = _group_by_title(r.data)[:10]
    except Exception:
        # Fallback: query events table directly
        raw = _fetch_all(
            sb, "events",
            "id,name_ja,start_date,secondary_source_urls",
            [
                ("eq", "is_active", True),
                ("in_", "annotation_status", ["annotated", "reviewed"]),
                ("gte", "start_date", start_d),
                ("lt", "start_date", end_d),
            ],
        )
        raw = [e for e in raw if (e.get("secondary_source_urls") or [])]
        flat: list[dict] = []
        for e in raw:
            urls = e.get("secondary_source_urls") or []
            flat.append({
                "name_ja": e.get("name_ja", "(無題)"),
                "media_count": len(urls),
                "media_source_names": sorted({_url_to_source_name(u) for u in urls}),
            })
        rows = _group_by_title(flat)[:10]

    lines = [
        "## 5. メディア露出 Top 10（作品・活動別）\n",
        "| 順位 | イベント名 | メディア数 | ソース |",
        "|------|-----------|-----------|--------|" ,
    ]
    for rank, row in enumerate(rows, 1):
        name = (row.get("name_ja") or "(無題)")[:40]
        cnt = row.get("media_count") or 0
        src_names = row.get("media_source_names") or []
        src_display = ", ".join(sorted(src_names)) if isinstance(src_names, list) else str(src_names)
        lines.append(f"| {rank} | {name} | {cnt} | {src_display} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main report assembler
# ---------------------------------------------------------------------------

def generate_report(month: str, fmt: str = "markdown") -> str:
    sb = _get_client()
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Pre-fetch month events (used by multiple sections)
    start_d, end_d = _month_range(month)
    month_events = _fetch_all(
        sb, "events",
        "id,source_name,created_at,has_chinese_support,category,location_prefectures,organizer_id,organizer",
        [
            ("eq", "is_active", True),
            ("in_", "annotation_status", ["annotated", "reviewed"]),
            ("gte", "start_date", start_d),
            ("lt", "start_date", end_d),
        ],
    )
    month_events = [e for e in month_events if not _is_broadcast(e)]

    # Build header
    year, mo = month.split("-")
    header = "\n".join(
        [
            f"# 台湾関連イベント月次レポート — {year}年{mo}月\n",
            f"生成日時: {now}  ",
            f"データ基準: active + annotated/reviewed イベント  ",
            f"対象月: {month}\n",
            "---\n",
        ]
    )

    s1 = build_section1(sb, month)
    s2 = build_section2(month_events)
    s3 = build_section3(month_events)
    s4 = build_section4(sb, month_events)
    s5 = build_section5(sb, month)

    return header + s1 + s2 + s3 + s4 + s5


def main():
    parser = argparse.ArgumentParser(description="台湾関連イベント月次レポート生成器")
    parser.add_argument("--month", required=True, help="対象月 (YYYY-MM 形式, 例: 2026-05)")
    parser.add_argument(
        "--format", default="markdown", choices=["markdown"], help="出力形式 (現在は markdown のみ)"
    )
    args = parser.parse_args()

    # Validate month format
    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        print(f"ERROR: --month must be YYYY-MM format, got: {args.month!r}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating report for {args.month} ...", flush=True)
    content = generate_report(args.month, args.format)

    # Write output
    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{args.month}_taiwan_japan_events.md"
    out_path.write_text(content, encoding="utf-8")

    print(f"Report written to: {out_path}")
    print(f"Size: {len(content)} chars, {content.count(chr(10))} lines")


if __name__ == "__main__":
    main()
