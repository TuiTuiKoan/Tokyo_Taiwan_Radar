"""
Diagnostic script: find active events in the DB with high name similarity
that have NOT already been merged by merger.py.

These are candidates that merger may have missed (e.g. different start_date,
source not in SOURCE_PRIORITY, or similarity just below the 0.85 threshold).

Usage:
    python check_duplicates.py                # threshold=0.80, top 50 pairs
    python check_duplicates.py --threshold 0.7
    python check_duplicates.py --limit 100
    python check_duplicates.py --date-window 3   # allow start_date ± N days
    python check_duplicates.py --same-date-only   # only exact start_date matches

Output: sorted table of suspicious pairs, with similarity score and URLs.
This script is READ-ONLY — it never modifies the database.
"""

import argparse
import logging
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from difflib import SequenceMatcher

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Mirror of merger.py's SOURCE_PRIORITY (for display only)
SOURCE_PRIORITY: dict[str, int] = {
    "taiwan_cultural_center": 1,
    "taiwan_kyokai": 2,
    "taioan_dokyokai": 3,
    "koryu": 4,
    "taiwan_festival_tokyo": 5,
    "taiwan_matsuri": 6,
    "taiwanbunkasai": 7,
    "peatix": 8,
    "connpass": 9,
    "doorkeeper": 10,
    "iwafu": 11,
    "arukikata": 12,
    "ide_jetro": 13,
}


def _normalize(name: str) -> str:
    name = name.replace("®", "(r)").replace("Ⓡ", "(r)")
    name = re.sub(r"[－—\-][^－—\-]{2,}[－—\-]\s*$", "", name)
    return re.sub(r"[\s\u3000\u00a0]+", "", name).lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def run(threshold: float, limit: int, date_window: int, same_date_only: bool) -> None:
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sb = create_client(url, key)

    print("Loading active events from DB…")
    res = (
        sb.table("events")
        .select("id,source_name,source_id,source_url,name_ja,start_date,secondary_source_urls")
        .eq("is_active", True)
        .not_.is_("start_date", None)
        .not_.is_("name_ja", None)
        .execute()
    )
    events = [
        ev for ev in (res.data or [])
        if "_sub" not in (ev.get("source_id") or "")
    ]
    print(f"Loaded {len(events)} active events\n")

    # Build already-merged URL set (secondary_source_urls)
    already_merged_urls: set[str] = set()
    for ev in events:
        for u in (ev.get("secondary_source_urls") or []):
            if u:
                already_merged_urls.add(u)

    # Group by date bucket
    date_groups: dict[str, list] = defaultdict(list)
    for ev in events:
        d = ev["start_date"][:10] if ev.get("start_date") else None
        if d:
            date_groups[d].append(ev)

    # All events sorted by date for cross-date window search
    all_events = sorted(events, key=lambda e: e["start_date"] or "")

    pairs: list[dict] = []
    checked: set[frozenset] = set()

    def _add_pair(a, b, sim):
        key = frozenset([a["id"], b["id"]])
        if key in checked:
            return
        checked.add(key)
        # Skip if already merged
        if (a["source_url"] in already_merged_urls or
                b["source_url"] in already_merged_urls):
            return
        # Skip same source
        if a["source_name"] == b["source_name"]:
            return
        pairs.append({
            "sim": sim,
            "a_name": a["name_ja"],
            "a_source": a["source_name"],
            "a_date": (a["start_date"] or "")[:10],
            "a_url": a.get("source_url") or "",
            "b_name": b["name_ja"],
            "b_source": b["source_name"],
            "b_date": (b["start_date"] or "")[:10],
            "b_url": b.get("source_url") or "",
        })

    if same_date_only or date_window == 0:
        # Fast path: only compare within same date bucket
        for date_key, group in date_groups.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    sim = _similarity(group[i]["name_ja"], group[j]["name_ja"])
                    if sim >= threshold:
                        _add_pair(group[i], group[j], sim)
    else:
        # Compare events within ±date_window days of each other
        for i in range(len(all_events)):
            ev_a = all_events[i]
            d_a = _date(ev_a.get("start_date"))
            if not d_a:
                continue
            for j in range(i + 1, len(all_events)):
                ev_b = all_events[j]
                d_b = _date(ev_b.get("start_date"))
                if not d_b:
                    continue
                if (d_b - d_a).days > date_window:
                    break
                sim = _similarity(ev_a["name_ja"], ev_b["name_ja"])
                if sim >= threshold:
                    _add_pair(ev_a, ev_b, sim)

    # Sort by similarity descending
    pairs.sort(key=lambda p: p["sim"], reverse=True)
    pairs = pairs[:limit]

    if not pairs:
        print(f"✅ No suspicious duplicate pairs found (threshold={threshold:.0%}, window=±{date_window}d)")
        return

    print(f"🔍 Found {len(pairs)} suspicious pair(s) (threshold={threshold:.0%}, window=±{date_window}d)\n")
    print(f"{'SIM':>5}  {'DATE-A':>10}  {'SOURCE-A':<25}  NAME-A")
    print(f"{'':>5}  {'DATE-B':>10}  {'SOURCE-B':<25}  NAME-B")
    print("-" * 100)
    for p in pairs:
        pri_a = SOURCE_PRIORITY.get(p["a_source"], 99)
        pri_b = SOURCE_PRIORITY.get(p["b_source"], 99)
        winner = "←" if pri_a <= pri_b else "→"
        print(f"{p['sim']:>4.0%}  {p['a_date']:>10}  {p['a_source']:<25}  {p['a_name'][:50]}")
        print(f"  {winner}   {p['b_date']:>10}  {p['b_source']:<25}  {p['b_name'][:50]}")
        if p["a_url"] or p["b_url"]:
            print(f"       A: {p['a_url'][:80]}")
            print(f"       B: {p['b_url'][:80]}")
        print()

    print(f"Total: {len(pairs)} pair(s) shown")
    print("\nNote: pairs where one URL is already in secondary_source_urls are excluded (already merged).")
    print("To force-merge a pair, set force_rescrape=true on the secondary event in the admin UI.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find high-similarity duplicate events in the DB (read-only)"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.80,
        help="Minimum name similarity to report (default: 0.80)"
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Maximum number of pairs to show (default: 50)"
    )
    parser.add_argument(
        "--date-window", type=int, default=3,
        help="Days tolerance between start_date of two events (default: 3)"
    )
    parser.add_argument(
        "--same-date-only", action="store_true",
        help="Only compare events with exactly the same start_date"
    )
    args = parser.parse_args()
    run(
        threshold=args.threshold,
        limit=args.limit,
        date_window=args.date_window,
        same_date_only=args.same_date_only,
    )
