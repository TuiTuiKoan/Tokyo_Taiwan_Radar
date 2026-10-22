"""
enrich_addresses.py — Fill a missing or vague location_address for upcoming
events from data we already hold, without calling an LLM.

Lookup order:
  1. venue_registry — the authoritative venues table.
  2. Other events with the same location_name, when they agree on exactly one
     street-level address.

Events neither step resolves are listed and left alone. The former web-search
path used gpt-4o-search-preview, which OpenAI retired around 2026-08-20; it was
removed in 2026-10 (#318).

Usage:
    python enrich_addresses.py [--dry-run] [--source SOURCE_NAME] [--limit N]

Skips: gguide_tv (TV channels), events whose location_name contains オンライン,
pure publication records, and events whose location_address is locked in
field_corrections.
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

from annotator import _to_trad
from db_paging import fetch_all
from publication_rules import is_pure_publication_in_db, partition_pure_publications
from venue_registry import lookup_venue_for_location

load_dotenv()

JST = timezone(timedelta(hours=9))
IN_BATCH = 50

SKIP_SOURCES = {"gguide_tv"}
SKIP_VENUE_KEYWORDS = ["オンライン", "電視頻道", "online", "Online"]

VAGUE_ADDRESS_VALUES = frozenset({
    '東京', '大阪', '京都', '名古屋', '福岡', '神奈川', '埼玉', '千葉',
    '東京都', '大阪府', '京都府', '神奈川県', '愛知県', '兵庫県',
    '東京都内', '大阪府内', '全国',
})

# Prefecture-only or city/ward-only — e.g. "福岡県", "福岡市", "渋谷区"
_VAGUE_GEO_RE = re.compile(r'^[^\s]{2,10}[都道府県市区]$')


def is_vague(address: str | None) -> bool:
    """True when the address is missing or lacks a street-level part."""
    addr = (address or "").strip()
    return not addr or addr in VAGUE_ADDRESS_VALUES or bool(_VAGUE_GEO_RE.match(addr))


def _normalize_venue(name: str) -> str:
    """Strip city prefix before ｜ separator.
    '東京六本木｜EX THEATER ROPPONGI' → 'EX THEATER ROPPONGI'
    """
    if '｜' in name:
        return name.split('｜', 1)[1].strip()
    return name


def fetch_candidates(sb, today: str, source: str | None = None) -> list[dict]:
    """Active, upcoming events that name a venue but lack a specific address."""
    def query():
        q = (
            sb.table("events")
            .select("id, location_name, location_address, source_name, event_form, start_date, end_date")
            .eq("is_active", True)
            .not_.is_("location_name", None)
            .or_(f"end_date.gte.{today},and(end_date.is.null,start_date.gte.{today})")
            .order("id")
        )
        return q.eq("source_name", source) if source else q

    return [
        e for e in fetch_all(query)
        if is_vague(e.get("location_address"))
        and e["source_name"] not in SKIP_SOURCES
        and not any(kw in (e["location_name"] or "") for kw in SKIP_VENUE_KEYWORDS)
    ]


def registry_address(venue_name: str) -> dict | None:
    """Address of the authoritative venue matching the name, if specific."""
    for name in dict.fromkeys((venue_name, _normalize_venue(venue_name))):
        venue, _ = lookup_venue_for_location(name)
        if not venue or venue.get("is_multi_venue"):
            continue
        addr = (venue.get("address") or "").strip()
        if not is_vague(addr):
            return {"location_address": addr}
    return None


def build_sibling_map(rows: list[dict]) -> dict[str, dict]:
    """Map location_name → address patch when its events agree on one address.

    Names whose events carry two or more different specific addresses are
    left out: a chain or a multi-site label must not be guessed.
    """
    by_name: dict[str, dict[str, dict]] = {}
    for r in rows:
        addr = (r.get("location_address") or "").strip()
        if is_vague(addr):
            continue
        entry = by_name.setdefault(r["location_name"], {}).setdefault(addr, {"location_address": addr})
        for lang in ("zh", "en"):
            key = f"location_address_{lang}"
            if r.get(key) and key not in entry:
                entry[key] = r[key]
    return {name: next(iter(addrs.values())) for name, addrs in by_name.items() if len(addrs) == 1}


def fetch_sibling_map(sb, names: list[str]) -> dict[str, dict]:
    rows: list[dict] = []
    for i in range(0, len(names), IN_BATCH):
        batch = names[i:i + IN_BATCH]
        rows.extend(fetch_all(lambda: (
            sb.table("events")
            .select("id, location_name, location_address, location_address_zh, location_address_en")
            .in_("location_name", batch)
            .not_.is_("location_address", None)
            .order("id")
        )))
    return build_sibling_map(rows)


def resolve(event: dict, sibling_map: dict[str, dict]) -> tuple[dict, str] | None:
    """Return (address patch, method) for one candidate, or None."""
    venue = event["location_name"]
    patch = registry_address(venue)
    if patch:
        return patch, "registry"
    patch = sibling_map.get(venue)
    if patch:
        return dict(patch), "sibling"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", help="Limit to a specific source_name")
    parser.add_argument('--limit', type=int, default=0,
                        help='Max events to process (0=unlimited)')
    args = parser.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    today = datetime.now(JST).date().isoformat()

    candidates, publications = partition_pure_publications(fetch_candidates(sb, today, args.source))
    if publications:
        print(f"Skipped {len(publications)} pure publication events (no venue by policy)")

    if args.limit > 0:
        candidates = candidates[:args.limit]

    print(f"Found {len(candidates)} upcoming events to enrich (dry_run={args.dry_run})")
    if not candidates:
        print("\nDone. updated=0 unresolved=0 skipped=0")
        return

    # ── FC lock batch check ──────────────────────────────────────────────────
    protected_ids: set[str] = set()
    candidate_ids = [e['id'] for e in candidates]
    for i in range(0, len(candidate_ids), IN_BATCH):
        fc_res = sb.table('field_corrections').select('event_id') \
            .in_('event_id', candidate_ids[i:i + IN_BATCH]) \
            .eq('field_name', 'location_address').execute().data or []
        protected_ids.update(r['event_id'] for r in fc_res)
    print(f"FC-protected (skip): {len(protected_ids)}")

    sibling_map = fetch_sibling_map(sb, sorted({e["location_name"] for e in candidates}))

    updated = 0
    skipped = 0
    unresolved: list[dict] = []

    for e in candidates:
        if e['id'] in protected_ids:
            skipped += 1
            continue

        found = resolve(e, sibling_map)
        if not found:
            unresolved.append(e)
            continue
        patch, method = found
        print(f"[{e['id'][:8]}] {e['source_name']} | {e['location_name']!r} → {patch['location_address']} ({method})")

        if args.dry_run:
            updated += 1
            continue
        if is_pure_publication_in_db(sb, e["id"]):
            print(f"  → [SKIP] pure publication (re-check): {e['id'][:8]}")
            skipped += 1
            continue
        if patch.get("location_address_zh"):
            patch["location_address_zh"] = _to_trad(patch["location_address_zh"])
        sb.table("events").update(patch).eq("id", e["id"]).execute()
        # Registry addresses stay unlocked so a later registry fix still flows
        # through; an address copied from another event is locked like a manual
        # fill so re-annotation does not blank it again.
        if method == "sibling":
            sb.table('field_corrections').upsert({
                'event_id': e['id'],
                'field_name': 'location_address',
                'corrected_value': json.dumps(patch["location_address"], ensure_ascii=False),
            }, on_conflict='event_id,field_name').execute()
        updated += 1

    if unresolved:
        print(f"\nUnresolved ({len(unresolved)}) — no registry venue and no agreeing sibling event:")
        for e in unresolved:
            print(f"  https://tokyotaiwanradar.com/ja/events/{e['id']} | {e['location_name']!r}")

    print(f"\nDone. updated={updated} unresolved={len(unresolved)} skipped={skipped}")


if __name__ == "__main__":
    main()
