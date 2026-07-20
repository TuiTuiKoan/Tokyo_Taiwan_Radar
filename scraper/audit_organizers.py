#!/usr/bin/env python3
"""
Organizer Authority — Phase A audit manifest (READ-ONLY).

Scans every active event and groups the primary organizer, each co-organizer,
and each sponsor by a *normalized exact name* so a human can review entity
identity before any registry seed. This tool NEVER writes to the database — it
only emits a JSON + CSV manifest (to --out-dir, default /tmp).

Normalization (deliberately conservative — "normalized exact name", NOT the
aggressive fuzzy clustering in merger._normalize which strips year/subtitle
suffixes and all internal whitespace):
  - NFKC (unifies full-width / half-width, e.g. （ＡＢＣ） -> (ABC))
  - trim
  - strip leading/trailing wrapping brackets / quotes
  - collapse internal whitespace runs to a single space
  - casefold (Latin case-insensitive; CJK unaffected)

The most common raw spelling in a group is the canonical candidate; other raw
spellings are recorded as aliases. Keyword lists are used ONLY for candidate
discovery (which entities a human should look at first) and never assign a
final organizer_type.

Priority cohorts:
  A1  department store / mall / bookstore chain / retail brand candidates
  A2  organizers of active event_form=market events (named entity vs
      organizer-null reported separately)
  A3  cultural_institution vs independent_venue boundary (same name carries
      both types)
  A4  same name across multiple types, alias-link candidates (containment),
      and parallel co/sponsor type-array cardinality mismatches

Usage:
    python audit_organizers.py                     # dry-run manifest to /tmp
    python audit_organizers.py --out-dir .         # write manifest to cwd
    python audit_organizers.py --top 30            # more console samples
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import database  # noqa: E402  (service-role client; READ-ONLY usage here)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Canonical storage vocabulary (10 values). Used only to distinguish
# "meaningful" types from null/unknown when detecting drift — NOT to classify.
CANONICAL_TYPES = frozenset([
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media",
    "individual", "unknown",
])
_MEANINGFUL = CANONICAL_TYPES - {"unknown"}

# --- Keyword cohorts (CANDIDATE DISCOVERY ONLY — never final classification) --
_KW_DEPT = [
    "高島屋", "髙島屋", "三越", "伊勢丹", "大丸", "松坂屋", "そごう", "西武",
    "阪急", "阪神", "近鉄", "京王", "小田急", "東武", "名鉄", "百貨店", "百貨",
]
_KW_MALL = [
    "パルコ", "PARCO", "ルミネ", "LUMINE", "アトレ", "atre", "丸井", "マルイ",
    "OIOI", "ラゾーナ", "ららぽーと", "LaLaport", "イオン", "AEON", "モール",
    "ショッピング", "アウトレット", "商業施設", "テラスモール",
]
_KW_BOOKSTORE = [
    "蔦屋", "TSUTAYA", "紀伊國屋", "紀伊国屋", "ジュンク堂", "丸善", "有隣堂",
    "誠品", "三省堂", "未来屋書店", "くまざわ", "文教堂", "書店", "ブックセンター",
]
_KW_RETAIL = [
    "ストア", "STORE", "ショップ", "SHOP", "専門店", "セレクトショップ",
]
# Informational only — corporate legal form is a weak signal and does NOT
# trigger A1 by itself (many civic groups / presses are also 株式会社).
_KW_CORP_FORM = [
    "株式会社", "有限会社", "合同会社", "(株)", "(有)", "Inc", "Ltd", "LLC", "Corp",
]

_WRAP_OPEN = set("「『《〈【〔｛（(【[{＜<“‘\"'`")
_WRAP_CLOSE = set("」』》〉】〕｝）)]}＞>”’\"'`")


def _norm_key(name: str | None) -> str:
    """Conservative 'normalized exact name' key (see module docstring)."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).strip()
    prev = None
    while prev != s and s:
        prev = s
        if s and s[0] in _WRAP_OPEN:
            s = s[1:].strip()
        if s and s[-1] in _WRAP_CLOSE:
            s = s[:-1].strip()
    s = re.sub(r"[\s\u3000\u00a0]+", " ", s)
    return s.casefold()


def _kw_hits(raw_forms: list[str]) -> dict[str, list[str]]:
    """Return {signal: [matched keywords]} across all raw spellings of an entity."""
    joined = " ".join(raw_forms).lower()
    out: dict[str, list[str]] = {}
    for signal, kws in (
        ("dept", _KW_DEPT), ("mall", _KW_MALL),
        ("bookstore", _KW_BOOKSTORE), ("retail", _KW_RETAIL),
        ("corp_form", _KW_CORP_FORM),
    ):
        hits = [k for k in kws if k.lower() in joined]
        if hits:
            out[signal] = hits
    return out


def _fetch_all_active_events(sb) -> list[dict[str, Any]]:
    """Paginated fetch of all active events (PostgREST caps at 1000/req)."""
    cols = (
        "id,organizer,organizer_type,co_organizers,co_organizer_types,"
        "sponsors,sponsor_types,event_form,source_name,source_url"
    )
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (
            sb.table("events").select(cols)
            .eq("is_active", True)
            .order("id")
            .range(offset, offset + 999)
            .execute()
            .data or []
        )
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def _iter_entities(ev: dict[str, Any]):
    """Yield (raw_name, role, type_value) for every organizer entity in one event.

    - primary: organizer (single string) -> every value in organizer_type[]
    - co:      co_organizers[i] -> co_organizer_types[i]
    - sponsor: sponsors[i]      -> sponsor_types[i]
    """
    org = (ev.get("organizer") or "").strip()
    if org:
        otypes = ev.get("organizer_type") or []
        if otypes:
            for t in otypes:
                yield org, "primary", t
        else:
            yield org, "primary", None

    for names_col, types_col, role in (
        ("co_organizers", "co_organizer_types", "co"),
        ("sponsors", "sponsor_types", "sponsor"),
    ):
        names = ev.get(names_col) or []
        types = ev.get(types_col) or []
        for i, nm in enumerate(names):
            nm = (nm or "").strip()
            if not nm:
                continue
            t = types[i] if i < len(types) else None
            yield nm, role, t


def _card(x) -> int:
    """COALESCE(cardinality(x), 0) — None and [] both -> 0."""
    return len(x or [])


def build_manifest(events: list[dict[str, Any]], sample_urls: int) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    market_null_events: list[str] = []

    for ev in events:
        eid = ev.get("id")
        src = ev.get("source_name")
        url = ev.get("source_url")
        forms = set(ev.get("event_form") or [])
        is_market = "market" in forms

        if is_market and not (ev.get("organizer") or "").strip():
            market_null_events.append(eid)

        for raw, role, t in _iter_entities(ev):
            key = _norm_key(raw)
            if not key:
                continue
            g = groups.get(key)
            if g is None:
                g = groups[key] = {
                    "normalized_key": key,
                    "raw_forms": Counter(),
                    "roles": set(),
                    "types_by_role": defaultdict(Counter),
                    "event_ids": set(),
                    "sources": set(),
                    "evidence": [],
                    "market_primary_count": 0,
                }
            g["raw_forms"][raw] += 1
            g["roles"].add(role)
            g["types_by_role"][role][t if t is not None else "(null)"] += 1
            if eid:
                g["event_ids"].add(eid)
            if src:
                g["sources"].add(src)
            if role == "primary" and is_market:
                g["market_primary_count"] += 1
            if url and len(g["evidence"]) < sample_urls and all(
                url != e["source_url"] for e in g["evidence"]
            ):
                g["evidence"].append({"event_id": eid, "source_url": url})

    # Finalize entity records + cohort tagging.
    entities: list[dict[str, Any]] = []
    for key, g in groups.items():
        raw_forms_sorted = g["raw_forms"].most_common()
        canonical = raw_forms_sorted[0][0]
        aliases = [{"name": n, "count": c} for n, c in raw_forms_sorted[1:]]
        all_types = set()
        for role_ctr in g["types_by_role"].values():
            all_types.update(role_ctr.keys())
        distinct_meaningful = sorted(t for t in all_types if t in _MEANINGFUL)

        kw = _kw_hits([n for n, _ in raw_forms_sorted])
        cohorts: list[str] = []
        if any(s in kw for s in ("dept", "mall", "bookstore", "retail")):
            cohorts.append("A1")
        if g["market_primary_count"] > 0:
            cohorts.append("A2")
        if "cultural_institution" in all_types and "independent_venue" in all_types:
            cohorts.append("A3")
        if len(distinct_meaningful) >= 2:
            cohorts.append("A4-multitype")
        # cross-role divergence: entity plays >=2 roles and meaningful types differ
        if len(g["roles"]) >= 2:
            role_meaningful = {
                role: sorted(t for t in ctr if t in _MEANINGFUL)
                for role, ctr in g["types_by_role"].items()
            }
            nonempty = [tuple(v) for v in role_meaningful.values() if v]
            if len(set(nonempty)) >= 2:
                cohorts.append("A4-crossrole")

        entities.append({
            "normalized_key": key,
            "canonical": canonical,
            "aliases": aliases,
            "n_raw_forms": len(raw_forms_sorted),
            "roles": sorted(g["roles"]),
            "event_count": len(g["event_ids"]),
            "sources": sorted(g["sources"]),
            "types_by_role": {
                role: dict(ctr) for role, ctr in g["types_by_role"].items()
            },
            "distinct_meaningful_types": distinct_meaningful,
            "keyword_signals": kw,
            "market_primary_count": g["market_primary_count"],
            "cohorts": cohorts,
            "evidence": g["evidence"],
        })

    entities.sort(key=lambda e: (-e["event_count"], e["normalized_key"]))

    # Alias-link candidates (A4 alias-collision proxy): containment between two
    # distinct normalized keys of named entities with DIFFERENT meaningful type
    # sets. Exact-name grouping cannot produce a literal shared alias, so this
    # surfaces likely same-entity naming inconsistencies for human review only.
    alias_candidates: list[dict[str, Any]] = []
    review_pool = [
        e for e in entities
        if e["event_count"] >= 2 or e["cohorts"] or e["distinct_meaningful_types"]
    ]
    keys = [e["normalized_key"] for e in review_pool]
    by_key = {e["normalized_key"]: e for e in review_pool}
    for a in keys:
        if len(a) < 3:
            continue
        for b in keys:
            if a == b or len(b) <= len(a):
                continue
            if a in b:
                ta = set(by_key[a]["distinct_meaningful_types"])
                tb = set(by_key[b]["distinct_meaningful_types"])
                if ta and tb and ta != tb:
                    alias_candidates.append({
                        "shorter": by_key[a]["canonical"],
                        "shorter_types": sorted(ta),
                        "longer": by_key[b]["canonical"],
                        "longer_types": sorted(tb),
                    })
        if len(alias_candidates) >= 200:
            break

    # Parallel-array cardinality mismatch events (A4 mismatch; cross-ref A.5).
    mismatch_events: list[dict[str, Any]] = []
    for ev in events:
        co_mm = _card(ev.get("co_organizers")) != _card(ev.get("co_organizer_types"))
        sp_mm = _card(ev.get("sponsors")) != _card(ev.get("sponsor_types"))
        if co_mm or sp_mm:
            roles = []
            if co_mm:
                roles.append("co")
            if sp_mm:
                roles.append("sponsor")
            mismatch_events.append({"event_id": ev.get("id"), "roles": roles})

    return {
        "entities": entities,
        "alias_link_candidates": alias_candidates,
        "market_null_events": market_null_events,
        "mismatch_events": mismatch_events,
    }


def _cohort_counts(entities: list[dict[str, Any]]) -> Counter:
    c: Counter = Counter()
    for e in entities:
        for tag in e["cohorts"]:
            c[tag] += 1
    return c


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default="/tmp",
                        help="Directory for JSON + CSV manifest (default /tmp).")
    parser.add_argument("--sample-urls", type=int, default=3,
                        help="Evidence source_urls to keep per entity (default 3).")
    parser.add_argument("--top", type=int, default=20,
                        help="Console sample rows per cohort (default 20).")
    args = parser.parse_args()

    sb = database._get_client()
    logger.info("Fetching active events (paginated)…")
    events = _fetch_all_active_events(sb)
    logger.info("Active events fetched: %d", len(events))

    manifest = build_manifest(events, args.sample_urls)
    entities = manifest["entities"]
    counts = _cohort_counts(entities)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, f"organizer_audit_{ts}.json")
    csv_path = os.path.join(args.out_dir, f"organizer_audit_{ts}.csv")

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "generated_at": ts,
            "active_events": len(events),
            "entity_count": len(entities),
            "cohort_counts": dict(counts),
            "alias_link_candidate_count": len(manifest["alias_link_candidates"]),
            "market_null_event_count": len(manifest["market_null_events"]),
            "parallel_array_mismatch_active_event_count": len(manifest["mismatch_events"]),
            "parallel_array_mismatch_note": (
                "active-scope only; authoritative table-wide scan lives in "
                "_oneoff_repair_organizer_type_arrays.py (Phase A.5)"
            ),
            **manifest,
        }, fh, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "normalized_key", "canonical", "n_raw_forms", "event_count",
            "roles", "distinct_meaningful_types", "cohorts",
            "market_primary_count", "keyword_signals", "sources",
            "sample_source_urls",
        ])
        for e in entities:
            w.writerow([
                e["normalized_key"], e["canonical"], e["n_raw_forms"],
                e["event_count"], "|".join(e["roles"]),
                "|".join(e["distinct_meaningful_types"]),
                "|".join(e["cohorts"]), e["market_primary_count"],
                ";".join(f"{k}:{','.join(v)}" for k, v in e["keyword_signals"].items()),
                "|".join(e["sources"]),
                " ".join(ev["source_url"] for ev in e["evidence"]),
            ])

    # ---- Console summary ----
    logger.info("=" * 72)
    logger.info("ORGANIZER AUDIT MANIFEST  (READ-ONLY — no DB writes)")
    logger.info("  active events        : %d", len(events))
    logger.info("  distinct entities    : %d", len(entities))
    logger.info("  JSON manifest        : %s", json_path)
    logger.info("  CSV manifest         : %s", csv_path)
    logger.info("-" * 72)
    logger.info("COHORT COUNTS")
    for tag in ("A1", "A2", "A3", "A4-multitype", "A4-crossrole"):
        logger.info("  %-14s : %d", tag, counts.get(tag, 0))
    logger.info("  %-14s : %d", "alias-link cand", len(manifest["alias_link_candidates"]))
    logger.info("  %-14s : %d", "market-null ev", len(manifest["market_null_events"]))
    logger.info("  %-14s : %d (active-scope; Phase A.5 = full table)",
                "parallel mm ev", len(manifest["mismatch_events"]))

    def _show(tag: str) -> None:
        rows = [e for e in entities if tag in e["cohorts"]][: args.top]
        logger.info("-" * 72)
        logger.info("%s — top %d by event_count", tag, len(rows))
        for e in rows:
            logger.info(
                "  [%2d ev] %-30s roles=%s types=%s kw=%s",
                e["event_count"], e["canonical"][:30], ",".join(e["roles"]),
                ",".join(e["distinct_meaningful_types"]) or "-",
                ",".join(e["keyword_signals"].keys()) or "-",
            )

    for tag in ("A1", "A2", "A3", "A4-multitype", "A4-crossrole"):
        _show(tag)

    if manifest["alias_link_candidates"]:
        logger.info("-" * 72)
        logger.info("ALIAS-LINK CANDIDATES (containment; review-only) — top %d",
                    min(args.top, len(manifest["alias_link_candidates"])))
        for c in manifest["alias_link_candidates"][: args.top]:
            logger.info("  '%s' %s  ⊂  '%s' %s",
                        c["shorter"][:24], c["shorter_types"],
                        c["longer"][:24], c["longer_types"])


if __name__ == "__main__":
    main()
