"""
enrich_addresses.py — Fill a missing or vague location_address for upcoming
events from data we already hold, without calling an LLM.

Candidates: upcoming events whose address address_quality.grade_address() grades
town, region, empty or not_address. Addresses outside Japan are left alone.

Lookup order:
  1. venue_registry — the authoritative venues table. Its address is accepted at
     street or town level: an authoritative address was checked by a person, and
     a park or a campus may have no lot number.
  2. Other events with the same location_name, when independent evidence agrees
     on exactly one street address (see sibling_vote). Copies are not evidence.

Events neither step resolves are listed and left alone. The former web-search
path used gpt-4o-search-preview, which OpenAI retired around 2026-08-20; it was
removed in 2026-10 (#318).

Nothing is locked in field_corrections any more. annotator keeps an event's
current address, and an address cleared later (a force re-scrape) is filled again
by the next daily run. A lock would also stop a later venue fix from arriving.

Usage:
    python enrich_addresses.py [--dry-run] [--source SOURCE_NAME] [--limit N]

Skips: gguide_tv (TV channels), events whose location_name contains オンライン,
pure publication records, and events whose location_address is locked in
field_corrections.
"""

import argparse
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

from address_quality import NEEDS_FIX, STREET, TOWN, address_key, grade_address, normalize_address
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
    """The rule used before the address grader (kept for the audit's comparison).

    True when the address is missing or is only a prefecture, city or ward.
    """
    addr = (address or "").strip()
    return not addr or addr in VAGUE_ADDRESS_VALUES or bool(_VAGUE_GEO_RE.match(addr))


def needs_address(address: str | None) -> bool:
    """True when the address is not street-level (and not outside Japan)."""
    return grade_address(address) in NEEDS_FIX


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
        if needs_address(e.get("location_address"))
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
        if grade_address(addr) in (STREET, TOWN):
            return {"location_address": addr}
    return None


# An auto-lock is written in the same request as the event row; allow some slack.
AUTO_LOCK_WINDOW_SECONDS = 60
_PREF_NAMES_RE = re.compile(r"北海道|東京都|(?:京都|大阪)府|[^\s\d]{2,3}県")
SIBLING_COLUMNS = (
    "id, location_name, location_address, location_address_zh, location_address_en, "
    "source_name, created_at, raw_description"
)


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _squash(text: str | None) -> str:
    return re.sub(r"\s+", "", normalize_address(text))


def _verbatim(row: dict) -> bool:
    """The event's own source text contains its address."""
    address = _squash(row.get("location_address"))
    return bool(address) and address in _squash(row.get("raw_description"))


def sibling_vote(row: dict, lock: dict | None) -> bool:
    """True when this event's address is independent evidence for its venue.

    Either the address appears verbatim in the event's own source text, or it is
    the value the scraper delivered: an auto-lock written with the event (within
    AUTO_LOCK_WINDOW_SECONDS), not JSON-quoted, with the same address key. Values
    without such evidence are mostly model output or copies from other events,
    and do not vote. (venue-ground-truth plan-critique-2 B2.)
    """
    address = row.get("location_address")
    key = address_key(address)
    if key is None or len(_PREF_NAMES_RE.findall(normalize_address(address))) > 1:
        return False
    if _verbatim(row):
        return True
    if not lock or lock.get("corrected_by") or lock.get("report_id"):
        return False
    value = lock.get("corrected_value") or ""
    if value.startswith('"'):
        return False  # json.dumps copy lock written by enrich_addresses or its old web search
    locked_at, created_at = _ts(lock.get("created_at")), _ts(row.get("created_at"))
    if not locked_at or not created_at:
        return False
    if abs((locked_at - created_at).total_seconds()) > AUTO_LOCK_WINDOW_SECONDS:
        return False
    return address_key(value) == key


def build_sibling_map(rows: list[dict], locks: dict[str, dict] | None = None) -> dict[str, dict]:
    """Map location_name → address patch when independent evidence agrees.

    A name qualifies when every street-level address among its events has the
    same address key, and that key is backed by either one event whose own text
    contains the address, or votes from two events from two sources. A chain or a
    multi-site label, whose events carry two different addresses, is never guessed.
    """
    locks = locks or {}
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("location_name"):
            by_name.setdefault(r["location_name"], []).append(r)

    result: dict[str, dict] = {}
    for name, events in by_name.items():
        keys = {address_key(e.get("location_address")) for e in events} - {None}
        if len(keys) != 1:
            continue
        voters = [e for e in events if sibling_vote(e, locks.get(e["id"]))]
        from_text = any(_verbatim(e) for e in voters)
        if not from_text and (len(voters) < 2 or len({e.get("source_name") for e in voters}) < 2):
            continue
        # The most common spelling among the voters; ties go to the fuller text.
        spellings = Counter(normalize_address(e["location_address"]) for e in voters)
        best = max(spellings, key=lambda a: (spellings[a], len(a)))
        source = next(e for e in voters if normalize_address(e["location_address"]) == best)
        patch = {"location_address": source["location_address"].strip()}
        for lang in ("zh", "en"):
            field = f"location_address_{lang}"
            value = next((e.get(field) for e in [source, *voters] if e.get(field)), None)
            if value:
                patch[field] = value
        result[name] = patch
    return result


def fetch_sibling_map(sb, names: list[str]) -> dict[str, dict]:
    rows: list[dict] = []
    for i in range(0, len(names), IN_BATCH):
        batch = names[i:i + IN_BATCH]
        rows.extend(fetch_all(lambda: (
            sb.table("events")
            .select(SIBLING_COLUMNS)
            .in_("location_name", batch)
            .not_.is_("location_address", None)
            .order("id")
        )))
    locks: dict[str, dict] = {}
    ids = [r["id"] for r in rows]
    for i in range(0, len(ids), IN_BATCH):
        for lock in fetch_all(lambda: (
            sb.table("field_corrections")
            .select("event_id, corrected_value, corrected_by, report_id, created_at")
            .in_("event_id", ids[i:i + IN_BATCH])
            .eq("field_name", "location_address")
            .order("event_id")
        )):
            locks[lock["event_id"]] = lock
    return build_sibling_map(rows, locks)


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
        updated += 1

    if unresolved:
        print(f"\nUnresolved ({len(unresolved)}) — no registry venue and no independent sibling evidence:")
        for e in unresolved:
            print(f"  https://tokyotaiwanradar.com/ja/events/{e['id']} | {e['location_name']!r}")

    print(f"\nDone. updated={updated} unresolved={len(unresolved)} skipped={skipped}")


if __name__ == "__main__":
    from observability import init_sentry

    init_sentry("enrich_addresses")
    main()
