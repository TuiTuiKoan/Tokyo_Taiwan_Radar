#!/usr/bin/env python3
"""Seed authoritative organizers — Wave 2 Phase D (reviewed seed, dry-run first).

Seeds the first batch of *high-confidence, unambiguous* commercial-brand
organizers (chain bookstores / retail) into ``organizers`` with
``is_authoritative = true`` so the registry resolver (batch-4
``annotator._apply_organizer_registry``) can override event-topic LLM inference.

⛔ SCOPE — this batch is CODE-ONLY: the default mode is ``--dry-run`` and NO
row is ever written unless ``--apply`` is passed AND migration 095 has been
applied. The real seed is production gate 2C; do NOT run ``--apply`` here.

Graceful degradation (migration 095 not yet applied)
----------------------------------------------------
``organizers.is_authoritative`` ships in migration 095. Before it is applied
the schema-compatibility pre-flight detects the missing column and the dry-run
still shows the full seed plan, flagging every entry ``需先 apply 095``. The
``--apply`` path refuses to run until the column exists (fail closed).

Pre-flight (always runs in dry-run)
-----------------------------------
1. canonical/alias collision — the same key mapping to >1 canonical entity
   inside the seed list is rejected (fail closed; never seed an ambiguous key).
2. existing type conflict — an ``organizers`` row already carrying a *different*
   non-null ``organizer_type`` is flagged and the entry is rejected for apply.
3. evidence missing — an entry with neither ``homepage`` nor ``notes`` is
   flagged (authoritative rows should carry provenance).
4. schema compatibility — ``is_authoritative`` presence (see above).

The seed list is intentionally extensible: ``--manifest`` may point at a
batch-1 ``audit_organizers.py`` JSON manifest to surface additional A1
(department / mall / bookstore / retail) candidates *for human review only*.
Candidates are printed, never auto-seeded — the final list is confirmed by a
human at gate 2C.

Usage::

    python seed_authoritative_organizers.py                 # dry-run (default)
    python seed_authoritative_organizers.py --manifest /tmp/organizer_audit_*.json
    python seed_authoritative_organizers.py --apply         # gate 2C ONLY
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv

from database import _get_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Canonical storage vocabulary (10 values) — mirrors migration 095 CHECK.
CANONICAL_TYPES = frozenset([
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media",
    "individual", "unknown",
])

# --------------------------------------------------------------------------- #
# Core high-confidence seed list (batch-5).                                    #
# Chain bookstores / retail brands whose legal-operating identity is           #
# unambiguously ``commercial_brand``. Branch-name spellings surfaced by the    #
# batch-1 audit are recorded as aliases so per-branch event rows resolve to    #
# the one canonical entity.                                                    #
# --------------------------------------------------------------------------- #
SEED_DATA: list[dict[str, Any]] = [
    {
        "canonical_name_ja": "紀伊國屋書店",
        "canonical_name_zh": "紀伊國屋書店",
        "canonical_name_en": "Kinokuniya",
        "organizer_type": "commercial_brand",
        "is_authoritative": True,
        "aliases": ["紀伊国屋書店", "KINOKUNIYA", "Books Kinokuniya"],
        "homepage": "https://www.kinokuniya.co.jp/",
        "notes": "連鎖書店（株式会社紀伊國屋書店）— 營利零售，legal identity commercial_brand。",
    },
    {
        "canonical_name_ja": "誠品書店",
        "canonical_name_zh": "誠品書店",
        "canonical_name_en": "Eslite Bookstore",
        "organizer_type": "commercial_brand",
        "is_authoritative": True,
        "aliases": ["誠品", "eslite", "Eslite"],
        "homepage": "https://www.eslite.com/",
        "notes": "連鎖書店／零售品牌（誠品）— commercial_brand。誠品生活日本橋為分店（venue 已 seed）。",
    },
    {
        "canonical_name_ja": "株式会社有隣堂",
        "canonical_name_zh": "有隣堂",
        "canonical_name_en": "Yurindo Co., Ltd.",
        "organizer_type": "commercial_brand",
        "is_authoritative": True,
        "aliases": ["有隣堂", "有鄰堂", "YURINDO"],
        "homepage": "https://www.yurindo.co.jp/",
        "notes": (
            "連鎖書店（株式会社有隣堂）— commercial_brand。Wave 1 已於 event 層"
            "（eslite_spectrum / 50c83c11）以 FC 鎖定 commercial_brand，此處建立 entity authority。"
        ),
    },
    {
        "canonical_name_ja": "蔦屋書店",
        "canonical_name_zh": "蔦屋書店",
        "canonical_name_en": "TSUTAYA BOOKS",
        "organizer_type": "commercial_brand",
        "is_authoritative": True,
        "aliases": [
            "TSUTAYA", "TSUTAYA BOOKS",
            "代官山 蔦屋書店", "代官山蔦屋書店",
            "奈良 蔦屋書店", "奈良蔦屋書店",
            "京都 蔦屋書店", "京都蔦屋書店",
            "梅田 蔦屋書店", "梅田蔦屋書店",
            "すみだ 蔦屋書店", "すみだ蔦屋書店",
        ],
        "notes": (
            "連鎖書店／零售品牌（蔦屋書店 / CCC）— commercial_brand。Wave 1 已修正"
            "『奈良 蔦屋書店』event 由 cultural_institution → commercial_brand，此處建立 entity authority。"
        ),
        "homepage": "https://store.tsite.jp/",
    },
]

# Audit-manifest cohorts / keyword signals that suggest a chain-retail entity
# worth human review for a future seed batch (never auto-seeded).
_CANDIDATE_COHORTS = frozenset(["A1"])
_CANDIDATE_KEYWORD_SIGNALS = frozenset(["dept", "mall", "bookstore", "retail"])


# --------------------------------------------------------------------------- #
# Pure helpers (no DB) — directly unit-testable.                               #
# --------------------------------------------------------------------------- #
def _keys_of(entry: dict[str, Any]) -> list[str]:
    """Canonical + aliases, trimmed, non-empty."""
    raw = [entry.get("canonical_name_ja")] + list(entry.get("aliases") or [])
    return [(k or "").strip() for k in raw if (k or "").strip()]


def check_alias_collisions(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return ``{key: [canonicals…]}`` for every key mapping to >1 canonical.

    A canonical name or alias that resolves to two different seed entities is
    ambiguous; the registry would fail closed on it, so it must never be seeded.
    """
    key_to_canons: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        canonical = (entry.get("canonical_name_ja") or "").strip()
        if not canonical:
            continue
        for key in _keys_of(entry):
            key_to_canons[key].add(canonical)
    return {k: sorted(c) for k, c in key_to_canons.items() if len(c) > 1}


def _merge_aliases(existing: list[str] | None, incoming: list[str] | None, canonical: str) -> list[str]:
    merged = {(a or "").strip() for a in (existing or []) + (incoming or []) if (a or "").strip()}
    merged.discard(canonical)
    return sorted(merged)


def validate_seed_types(entries: list[dict[str, Any]]) -> list[str]:
    """Return canonical names whose seed ``organizer_type`` is not canonical.

    Guards against a typo in ``SEED_DATA`` writing an illegal type that
    migration 095's CHECK would later reject.
    """
    bad = []
    for entry in entries:
        t = entry.get("organizer_type")
        if not (isinstance(t, str) and t in CANONICAL_TYPES):
            bad.append(entry.get("canonical_name_ja") or "<unnamed>")
    return bad


# --------------------------------------------------------------------------- #
# DB-touching helpers (read-only in dry-run).                                  #
# --------------------------------------------------------------------------- #
def check_schema_ready(sb: Any) -> bool:
    """True when ``organizers.is_authoritative`` exists (migration 095 applied).

    Graceful: on the pre-095 schema the column is missing and the probe query
    raises; we log at debug and return False so dry-run can flag it.
    """
    try:
        sb.table("organizers").select("id,is_authoritative").limit(1).execute()
        return True
    except Exception as exc:
        logger.debug(
            "organizers.is_authoritative absent (migration 095 not applied): %s", exc
        )
        return False


def fetch_existing_organizer(sb: Any, canonical: str) -> dict[str, Any] | None:
    """Return the existing ``organizers`` row for ``canonical`` (or None).

    Selects only pre-095 columns so the probe works on any schema version.
    """
    try:
        rows = (
            sb.table("organizers")
            .select("id,canonical_name_ja,aliases,organizer_type")
            .eq("canonical_name_ja", canonical)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:
        logger.debug("existing organizer lookup failed for %r: %s", canonical, exc)
        return None


def evaluate_entry(
    sb: Any, entry: dict[str, Any], collision_keys: set[str]
) -> dict[str, Any]:
    """Run per-entry pre-flight and compute the before/after seed plan.

    ``rejected`` is True when the entry has an alias collision or an existing
    type conflict — those must not be seeded (fail closed). ``evidence_missing``
    is advisory (flagged, not rejected).
    """
    canonical = entry["canonical_name_ja"]
    seed_type = entry["organizer_type"]
    existing = fetch_existing_organizer(sb, canonical)

    existing_type = existing.get("organizer_type") if existing else None
    type_conflict = (
        existing_type
        if (existing_type and existing_type != seed_type)
        else None
    )
    evidence_missing = not (entry.get("homepage") or entry.get("notes"))
    collides = sorted(k for k in _keys_of(entry) if k in collision_keys)

    merged_aliases = _merge_aliases(
        existing.get("aliases") if existing else None,
        entry.get("aliases"),
        canonical,
    )

    before = {
        "exists": bool(existing),
        "organizer_type": existing_type,
        "aliases": list(existing.get("aliases") or []) if existing else None,
        # is_authoritative deliberately not selected (absent pre-095).
    }
    after = {
        "organizer_type": seed_type,
        "is_authoritative": True,
        "aliases": merged_aliases,
    }
    return {
        "canonical": canonical,
        "action": "update" if existing else "insert",
        "before": before,
        "after": after,
        "type_conflict": type_conflict,
        "evidence_missing": evidence_missing,
        "collisions": collides,
        "rejected": bool(collides) or bool(type_conflict),
    }


def build_payload(entry: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Construct the upsert payload (apply path only)."""
    payload: dict[str, Any] = {
        "canonical_name_ja": entry["canonical_name_ja"],
        "canonical_name_zh": entry.get("canonical_name_zh"),
        "canonical_name_en": entry.get("canonical_name_en"),
        "organizer_type": entry["organizer_type"],
        "is_authoritative": True,
        "aliases": plan["after"]["aliases"],
    }
    if entry.get("homepage"):
        payload["homepage"] = entry["homepage"]
    if entry.get("notes"):
        payload["notes"] = entry["notes"]
    return payload


# --------------------------------------------------------------------------- #
# Optional audit-manifest candidate discovery (human review only).            #
# --------------------------------------------------------------------------- #
def load_manifest_candidates(manifest_path: str) -> list[dict[str, Any]]:
    """Return A1 / chain-retail candidate entities from an audit JSON manifest.

    These are suggestions for a human to confirm at gate 2C — never auto-seeded.
    """
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    seeded_keys = {k for e in SEED_DATA for k in _keys_of(e)}
    candidates: list[dict[str, Any]] = []
    for ent in manifest.get("entities") or []:
        cohorts = set(ent.get("cohorts") or [])
        kw = set((ent.get("keyword_signals") or {}).keys())
        if not (cohorts & _CANDIDATE_COHORTS or kw & _CANDIDATE_KEYWORD_SIGNALS):
            continue
        canonical = ent.get("canonical")
        if canonical in seeded_keys:
            continue  # already covered by the core list
        candidates.append({
            "canonical": canonical,
            "aliases": ent.get("aliases") or [],
            "distinct_meaningful_types": ent.get("distinct_meaningful_types") or [],
            "cohorts": sorted(cohorts),
            "keyword_signals": sorted(kw),
            "event_count": ent.get("event_count"),
        })
    return candidates


# --------------------------------------------------------------------------- #
# Orchestration.                                                               #
# --------------------------------------------------------------------------- #
def run(dry_run: bool = True, manifest_path: str | None = None) -> dict[str, Any]:
    sb = _get_client()

    bad_types = validate_seed_types(SEED_DATA)
    if bad_types:
        raise SystemExit(f"[ERROR] seed entries carry non-canonical organizer_type: {bad_types}")

    collisions = check_alias_collisions(SEED_DATA)
    collision_keys = set(collisions)
    schema_ready = check_schema_ready(sb)
    plans = [evaluate_entry(sb, e, collision_keys) for e in SEED_DATA]

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== seed_authoritative_organizers [{mode}] — {len(SEED_DATA)} core entries ===")
    if not schema_ready:
        print("[SCHEMA] organizers.is_authoritative 不存在 → 需先 apply migration 095（gate 2B）。")
        print("[SCHEMA] dry-run 仍顯示完整 seed 計畫；--apply 會被拒絕直到 095 落地。")
    else:
        print("[SCHEMA] organizers.is_authoritative 就緒（migration 095 已套用）。")

    if collisions:
        print(f"[PRE-FLIGHT collision] {len(collisions)} 個 key 對映多 canonical（fail closed）：")
        for key, canons in sorted(collisions.items()):
            print(f"    - {key!r} → {canons}")
    else:
        print("[PRE-FLIGHT collision] 無 canonical/alias collision。")

    seedable = 0
    for plan in plans:
        flags = []
        if plan["collisions"]:
            flags.append(f"collision={plan['collisions']}")
        if plan["type_conflict"]:
            flags.append(f"type_conflict(existing={plan['type_conflict']})")
        if plan["evidence_missing"]:
            flags.append("evidence_missing")
        if not schema_ready:
            flags.append("需先 apply 095")
        status = "REJECT" if plan["rejected"] else "OK"
        if not plan["rejected"]:
            seedable += 1
        before = plan["before"]
        after = plan["after"]
        before_desc = (
            f"exists type={before['organizer_type']} aliases={len(before['aliases'] or [])}"
            if before["exists"] else "not present"
        )
        print(
            f"[{status} {plan['action']}] {plan['canonical']}\n"
            f"    before: {before_desc}\n"
            f"    after : type={after['organizer_type']} is_authoritative=True "
            f"aliases={len(after['aliases'])}"
            + (f"\n    flags : {', '.join(flags)}" if flags else "")
        )

    if manifest_path:
        try:
            candidates = load_manifest_candidates(manifest_path)
        except Exception as exc:
            print(f"[MANIFEST] 讀取失敗 {manifest_path}: {exc}")
            candidates = []
        print(f"\n[MANIFEST] {len(candidates)} 個 A1／零售候選（人工確認 gate 2C，非本批 seed）：")
        for c in candidates[:30]:
            print(
                f"    - {c['canonical']} events={c['event_count']} "
                f"types={c['distinct_meaningful_types']} cohorts={c['cohorts']} "
                f"kw={c['keyword_signals']}"
            )

    print(
        f"\n[{mode}] summary | core={len(SEED_DATA)} seedable={seedable} "
        f"rejected={len(SEED_DATA) - seedable} schema_ready={schema_ready}"
    )

    applied = 0
    if not dry_run:
        if not schema_ready:
            raise SystemExit(
                "[ERROR] 拒絕 apply：organizers.is_authoritative 不存在，請先套用 migration 095（gate 2B）。"
            )
        for entry, plan in zip(SEED_DATA, plans):
            if plan["rejected"]:
                print(f"[SKIP apply] {plan['canonical']} (pre-flight rejected)")
                continue
            payload = build_payload(entry, plan)
            sb.table("organizers").upsert(payload, on_conflict="canonical_name_ja").execute()
            applied += 1
            print(f"[APPLY {plan['action']}] {plan['canonical']}")
        print(f"[APPLY] wrote {applied} authoritative organizer row(s).")

    return {
        "core": len(SEED_DATA),
        "seedable": seedable,
        "rejected": len(SEED_DATA) - seedable,
        "schema_ready": schema_ready,
        "collisions": collisions,
        "plans": plans,
        "applied": applied,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed authoritative organizers with conflict-safe pre-flight (dry-run default)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write authoritative rows (gate 2C ONLY; refused until migration 095 is applied).",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional audit_organizers.py JSON manifest for A1/retail candidate suggestions.",
    )
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(dry_run=not args.apply, manifest_path=args.manifest)


if __name__ == "__main__":
    main()
