"""One-off DRY-RUN backfill: restore the NDL container (journal) title into
raw_description before the publication cleanup clears location_name.

Cohort (exactly the rows whose citation would otherwise be destroyed):
  * source_name == "ndl_opensearch"
  * exact-pure publication record
  * not an audited poster-pollution row (its location_name is a poster venue,
    not a journal title)
  * location_name is a legacy physical-venue conflict, i.e. the journal title
    parked in location_name
  * that journal title is absent from description_ja, so clearing location_name
    would lose the only copy

Records are keyed by source_url, never by title: 7 of the cohort carry an
`ndl_<md5>` source_id because the source has no dc:identifier suffix, which makes
title-based identity unreliable.

Preservation-first contract: the value that must survive is already in
events.location_name — the very field the cleanup is about to clear — so
location_name is the authoritative source of the planned citation and always
appears in full. NDL is consulted only to ENRICH it with publication date and
page range, and only when the NDL value's non-numeric core matches
location_name's. An NDL value with a different non-numeric core means the row's
identity is in doubt: it is never written, and the row is reported as
needs_review for a human.

Retrieval order per row (enrichment only, never replacement):
  1. NDL OpenSearch API `title=` search, matched back on <link> == source_url,
     reading the dc:description element labelled 掲載誌.
  2. Fallback: fetch source_url and read the 掲載誌名 row of the detail page.
     Label and value live in sibling elements, so the page is parsed with
     BeautifulSoup rather than a same-line regex.

Only events.raw_description is written. description_ja/zh/en are GPT-owned and
propagate later via re-annotation; location_name, location_address and field
corrections are never touched.

Two stages, because an apply that re-plans can write a value the reviewer never
saw. Stage 1 queries NDL and writes an immutable digest-bound plan; stage 2
consumes only that plan and performs no network call at all.

    # stage 1 — read-only, produces the artifact approval binds
    python _oneoff_backfill_ndl_container_title.py --plan-output ../tmp/publication-policy/b1-plan.json

    # stage 2 — apply, consumes only that artifact
    python _oneoff_backfill_ndl_container_title.py --apply --plan ../tmp/publication-policy/b1-plan.json \
        --journal-output ../tmp/publication-policy/b1-journal.json
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup

from _oneoff_backfill_publication_metadata import (
    PHYSICAL_LOCATION_RE,
    POSTER_POLLUTION_REPAIRS,
    PUBLICATION_EXTENDED_CLEAR_FIELDS,
    PUBLICATION_LOCATION_MARKERS,
    assert_ignored_output_path,
    assert_non_production_target,
    get_supabase,
    now_iso,
    sha256,
    write_immutable_json,
)
from publication_rules import PUBLICATION_NULL_FIELDS, is_pure_publication_record
from qa_auto_fix import apply_cas_filter
from sources.ndl_opensearch import (
    CONTAINER_TITLE_LABEL,
    CONTAINER_TITLE_PREFIX,
    NDL_API,
    NS,
    SOURCE_NAME,
    _container_title,
    _strip_null,
)

USER_AGENT = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
DETAIL_LABEL = "掲載誌名"
PAGE_SIZE = 500
REQUEST_DELAY = 1.0
MAX_ATTEMPTS = 4
TIMEOUT = 30

# The projection is the behaviour contract. A column absent here cannot appear in
# a before-image, so an unexpected change to it would silently pass every gate;
# it therefore carries the acceptance inputs, not just the planning inputs.
ACCEPTANCE_COLUMNS = (
    "id",
    "source_name",
    "source_id",
    "source_url",
    "event_form",
    "raw_title",
    "name_ja",
    "raw_description",
    "description_ja",
    "description_zh",
    "description_en",
    "annotation_status",
    "updated_at",
    "price_info",
    *PUBLICATION_NULL_FIELDS,
    *PUBLICATION_EXTENDED_CLEAR_FIELDS,
)
SELECT_COLUMNS = ",".join(dict.fromkeys(ACCEPTANCE_COLUMNS))

# Compare-and-set inputs: the written column plus every field the pure-publication
# predicate and the citation identity were planned from.
CAS_COLUMNS = ("raw_description", "location_name", "source_url", "event_form")
# The only columns allowed to differ between the before-image and the read-back:
# the written field, and the trigger-maintained audit column.
APPLY_ALLOWED_DELTA_FIELDS = ("raw_description", "updated_at")
# Frozen by the B2 descoping: this release unit proves it never touched them.
DESCRIPTION_FC_FIELDS = ("description_ja", "description_zh", "description_en")

PLAN_SCHEMA = {"name": "tokyo-taiwan-radar/ndl-container-title-plan", "version": 1}
JOURNAL_SCHEMA = {"name": "tokyo-taiwan-radar/ndl-container-title-journal", "version": 1}
CITATION_SAFETY_SETS = ("safe", "pending_apply", "confirm_per_row", "unsafe")
# `plan_row()` emits four statuses and only `planned` is ever written, so "B1
# applied it" is not the same question as "is the citation safe to clear".
PLAN_CITATION_SAFETY = {
    "planned": "pending_apply",
    "already_present": "safe",
    "unavailable": "confirm_per_row",
    "needs_review": "unsafe",
}

# Citation detail NDL may contribute on top of location_name. Volume numbers are
# deliberately absent: location_name is authoritative for those.
_DATE_TOKEN_RE = re.compile(r"^\d{4}(?:[-/]\d{1,2}){0,2}$")
_PAGE_TOKEN_RE = re.compile(r"^p\.?\s*\d[\d\-\u2010\u2013\u2014,]*$", re.IGNORECASE)
# Digits and citation punctuation carry no identity: two values naming the same
# journal must compare equal once they are stripped.
_CORE_NOISE_RE = re.compile(r"[0-9\uff10-\uff19\s.,:\u3001\uff1a\-\u2010\u2013\u2014~\u301c\uff5e/]+")


class TransientFetchError(RuntimeError):
    """Network fault that exhausted its retries — never a 'not available'."""


def _http_get(url: str, params: dict[str, str] | None = None) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        time.sleep(REQUEST_DELAY * (1 if attempt == 0 else 2**attempt))
        try:
            resp = requests.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            continue
        if resp.status_code >= 500:
            last_exc = RuntimeError(f"HTTP {resp.status_code} from {url}")
            continue
        return resp
    raise TransientFetchError(f"{url}: {last_exc}")


def container_title_from_detail_html(html: str) -> str | None:
    """Read the 掲載誌名 value, which sits in a sibling element of the label."""
    lines = [
        line.strip()
        for line in BeautifulSoup(html, "html.parser").get_text("\n").split("\n")
    ]
    for index, line in enumerate(lines):
        if line != DETAIL_LABEL:
            continue
        for value in lines[index + 1 :]:
            if value:
                return _strip_null(value) or None
    return None


def lookup_via_api(row: dict[str, Any]) -> str | None:
    title = (row.get("raw_title") or row.get("name_ja") or "").strip()
    if not title:
        return None
    resp = _http_get(NDL_API, {"title": title, "cnt": "100"})
    if resp.status_code != 200:
        return None
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return None
    channel = root.find("channel")
    if channel is None:
        return None
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        if link == str(row.get("source_url") or "").strip():
            return _container_title(item)
    return None


def lookup_via_detail_page(row: dict[str, Any]) -> str | None:
    url = str(row.get("source_url") or "").strip()
    if not url:
        return None
    resp = _http_get(url)
    if resp.status_code != 200:
        return None
    return container_title_from_detail_html(resp.text)


def is_journal_title_in_location_name(row: dict[str, Any]) -> bool:
    value = str(row.get("location_name") or "").strip()
    if not value or any(marker in value for marker in PUBLICATION_LOCATION_MARKERS):
        return False
    return bool(PHYSICAL_LOCATION_RE.search(value))


def select_cohort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cohort = []
    for row in rows:
        if str(row.get("id")) in POSTER_POLLUTION_REPAIRS:
            continue
        if not is_pure_publication_record(row):
            continue
        if not is_journal_title_in_location_name(row):
            continue
        if str(row["location_name"]).strip() in (row.get("description_ja") or ""):
            continue
        cohort.append(row)
    return sorted(cohort, key=lambda row: str(row["id"]))


def _tokens(value: str | None) -> list[str]:
    return [token for token in str(value or "").split() if token]


def _is_detail_token(token: str) -> bool:
    return bool(_DATE_TOKEN_RE.match(token) or _PAGE_TOKEN_RE.match(token))


def citation_core(value: str | None) -> str:
    """The identity-bearing part of a citation: no dates, pages, digits or punctuation."""
    kept = [token for token in _tokens(value) if not _is_detail_token(token)]
    return _CORE_NOISE_RE.sub("", "".join(kept))


def is_consistent_with_location_name(location_name: str | None, retrieved: str | None) -> bool:
    """A retrieved value may enrich only when it names the same journal.

    An empty core (e.g. NDL returning the bare volume '16') makes no competing
    title claim, so it is consistent — it simply adds nothing.
    """
    retrieved_core = citation_core(retrieved)
    return not retrieved_core or retrieved_core == citation_core(location_name)


def enriched_container_line(location_name: str | None, retrieved: str | None) -> str:
    """location_name in full, plus any date/page detail NDL adds on top of it."""
    base = str(location_name or "").strip()
    if not base or not is_consistent_with_location_name(base, retrieved):
        return base
    extra = [
        token
        for token in _tokens(retrieved)
        if _is_detail_token(token) and token not in base
    ]
    return " ".join([base, *extra])


def planned_raw_description(current: str | None, container_line: str) -> str:
    prefix = f"{CONTAINER_TITLE_PREFIX}{container_line}"
    body = (current or "").strip()
    return f"{prefix}\n\n{body}".strip() if body else prefix


def fetch_rows(sb) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (
            sb.table("events")
            .select(SELECT_COLUMNS)
            .eq("source_name", SOURCE_NAME)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
        )
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def plan_row(row: dict[str, Any]) -> dict[str, Any]:
    current = row.get("raw_description")
    location_name = str(row.get("location_name") or "").strip()
    plan: dict[str, Any] = {
        "event_id": str(row["id"]),
        "source_url": row.get("source_url"),
        "location_name": row.get("location_name"),
        "current_raw_description": current,
        "current_raw_description_length": len(current or ""),
        "container_title": None,
        "retrieved_via": None,
        "planned_raw_description": None,
        "status": "unavailable",
    }
    if CONTAINER_TITLE_LABEL in (current or ""):
        plan["status"] = "already_present"
        return plan
    if not citation_core(location_name):
        return plan

    conflicting: str | None = None
    for retrieved_via, lookup in (
        ("opensearch_api", lookup_via_api),
        ("detail_page", lookup_via_detail_page),
    ):
        retrieved = lookup(row)
        if not retrieved:
            continue
        plan["container_title"] = retrieved
        plan["retrieved_via"] = retrieved_via
        if is_consistent_with_location_name(location_name, retrieved):
            conflicting = None
            break
        conflicting = retrieved

    container_line = enriched_container_line(location_name, plan["container_title"])
    plan["planned_raw_description"] = planned_raw_description(current, container_line)
    plan["status"] = "planned"
    if conflicting is not None:
        # NDL names a different journal: the row's identity is in doubt, so the
        # citation is preserved in the report but never written.
        plan["status"] = "needs_review"
    elif citation_core(location_name) not in citation_core(container_line):
        plan["status"] = "needs_review"
    return plan


def applicable_plans(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only rows whose planned value provably preserves location_name are written."""
    return [plan for plan in plans if plan["status"] == "planned"]


def projection_columns() -> list[str]:
    return [column.strip() for column in SELECT_COLUMNS.split(",") if column.strip()]


def before_image(row: dict[str, Any]) -> dict[str, Any]:
    """The full projected row, so any column change is visible to the diff."""
    return {column: deepcopy(row.get(column)) for column in projection_columns()}


def description_fc_digest(sb, event_ids: list[str]) -> dict[str, Any]:
    """Digest of the 45 machine locks the B2 descoping promises not to touch."""
    ordered = sorted({str(value) for value in event_ids if value})
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ordered), PAGE_SIZE):
        chunk = ordered[start : start + PAGE_SIZE]
        rows.extend(
            sb.table("field_corrections")
            .select("id,event_id,field_name,corrected_value,original_value,corrected_by")
            .in_("event_id", chunk)
            .in_("field_name", list(DESCRIPTION_FC_FIELDS))
            .execute()
            .data
            or []
        )
    rows.sort(
        key=lambda row: (
            str(row.get("event_id")),
            str(row.get("field_name")),
            str(row.get("id")),
        )
    )
    return {"row_count": len(rows), "sha256": sha256(rows)}


def _safety_sets(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        name: sorted(
            entry["event_id"] for entry in entries if entry["citation_safety"] == name
        )
        for name in CITATION_SAFETY_SETS
    }


def build_plan(
    rows: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    *,
    description_field_corrections: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows_by_id = {str(row["id"]): row for row in rows}
    entries = [
        {
            "event_id": plan["event_id"],
            "status": plan["status"],
            "citation_safety": PLAN_CITATION_SAFETY[plan["status"]],
            "before_image": before_image(rows_by_id[plan["event_id"]]),
            "evidence": {
                "location_name": rows_by_id[plan["event_id"]].get("location_name"),
                "source_url": rows_by_id[plan["event_id"]].get("source_url"),
                "event_form": rows_by_id[plan["event_id"]].get("event_form"),
                "annotation_status": rows_by_id[plan["event_id"]].get("annotation_status"),
                "container_title": plan["container_title"],
                "retrieved_via": plan["retrieved_via"],
            },
            "planned_raw_description": plan["planned_raw_description"],
        }
        for plan in sorted(plans, key=lambda plan: plan["event_id"])
    ]
    payload: dict[str, Any] = {
        "schema": dict(PLAN_SCHEMA),
        "digest_field": "plan_sha256",
        "stage": "plan",
        "mode": "dry-run-read-only",
        "generated_at": generated_at or now_iso(),
        "select_columns": SELECT_COLUMNS,
        "cas_columns": list(CAS_COLUMNS),
        "apply_allowed_delta_fields": list(APPLY_ALLOWED_DELTA_FIELDS),
        "description_field_correction_digest": deepcopy(description_field_corrections),
        "citation_safety_sets": _safety_sets(entries),
        # Eligible, not applied: what actually happened belongs to the journal.
        "eligible_event_ids": sorted(
            entry["event_id"] for entry in entries if entry["status"] == "planned"
        ),
        "rows": entries,
        "summary": {
            "cohort": len(entries),
            "statuses": {
                status: sum(1 for entry in entries if entry["status"] == status)
                for status in PLAN_CITATION_SAFETY
            },
        },
    }
    payload["plan_sha256"] = sha256(payload)
    return payload


def load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    digest = payload.pop("plan_sha256", None)
    if digest != sha256(payload):
        raise RuntimeError("plan digest mismatch; the approved artifact was modified")
    payload["plan_sha256"] = digest
    if payload.get("schema") != dict(PLAN_SCHEMA):
        raise RuntimeError("unsupported container-title plan schema/version")
    if payload.get("select_columns") != SELECT_COLUMNS:
        raise RuntimeError("plan projection differs from the current SELECT_COLUMNS")
    return payload


def unexpected_deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        column: {"before": before.get(column), "after": after.get(column)}
        for column in before
        if column not in APPLY_ALLOWED_DELTA_FIELDS and after.get(column) != before.get(column)
    }


def read_back(sb, event_id: str) -> dict[str, Any]:
    row = (
        sb.table("events")
        .select(SELECT_COLUMNS)
        .eq("id", event_id)
        .single()
        .execute()
        .data
    )
    if not row:
        raise RuntimeError(f"{event_id}: read-back returned no row")
    return before_image(row)


def apply_entry(sb, entry: dict[str, Any]) -> dict[str, Any]:
    """Widened CAS, then read back and allowlist-diff the whole projected row."""
    event_id = entry["event_id"]
    before = entry["before_image"]
    query = sb.table("events").update(
        {"raw_description": entry["planned_raw_description"]}
    ).eq("id", event_id)
    for column in CAS_COLUMNS:
        query = apply_cas_filter(query, column, before.get(column))
    if not query.execute().data:
        # A miss is an outcome to report: the row simply keeps location_name as
        # its only citation copy, which the journal records as unsafe.
        return {
            "event_id": event_id,
            "outcome": "cas_miss",
            "citation_safety": "unsafe",
            "after_image": None,
            "unexpected_deltas": {},
        }
    after = read_back(sb, event_id)
    if after.get("raw_description") != entry["planned_raw_description"]:
        raise RuntimeError(f"{event_id}: read-back does not match the planned value")
    deltas = unexpected_deltas(before, after)
    if deltas:
        raise RuntimeError(
            f"{event_id}: allowlist diff rejected unexpected column changes: {sorted(deltas)}"
        )
    return {
        "event_id": event_id,
        "outcome": "applied",
        "citation_safety": "safe",
        "after_image": after,
        "unexpected_deltas": {},
    }


def build_journal(
    plan: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    description_field_corrections_after: dict[str, Any],
    error: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    outcome_by_id = {result["event_id"]: result for result in results}
    sets = {name: list(values) for name, values in plan["citation_safety_sets"].items()}
    for event_id, result in outcome_by_id.items():
        if event_id in sets["pending_apply"]:
            sets["pending_apply"].remove(event_id)
        sets[result["citation_safety"]].append(event_id)
    before_digest = plan["description_field_correction_digest"]
    payload: dict[str, Any] = {
        "schema": dict(JOURNAL_SCHEMA),
        "digest_field": "journal_sha256",
        "stage": "journal",
        "mode": "apply",
        "generated_at": generated_at or now_iso(),
        "plan_sha256": plan["plan_sha256"],
        "select_columns": plan["select_columns"],
        "description_field_correction_digest_before": deepcopy(before_digest),
        "description_field_correction_digest_after": deepcopy(
            description_field_corrections_after
        ),
        "description_field_corrections_unchanged": (
            before_digest == description_field_corrections_after
        ),
        "citation_safety_sets": {name: sorted(values) for name, values in sets.items()},
        "applied_event_ids": sorted(
            result["event_id"] for result in results if result["outcome"] == "applied"
        ),
        "cas_miss_event_ids": sorted(
            result["event_id"] for result in results if result["outcome"] == "cas_miss"
        ),
        "results": sorted(deepcopy(results), key=lambda result: result["event_id"]),
        "stopped_with_error": error,
        "summary": {
            "eligible": len(plan["eligible_event_ids"]),
            "attempted": len(results),
            "applied": sum(1 for result in results if result["outcome"] == "applied"),
            "cas_misses": sum(1 for result in results if result["outcome"] == "cas_miss"),
        },
    }
    payload["journal_sha256"] = sha256(payload)
    return payload


def print_report(plans: list[dict[str, Any]]) -> None:
    for plan in plans:
        print(f"--- {plan['event_id']}  [{plan['status']}]")
        print(f"    source_url          : {plan['source_url']}")
        print(f"    location_name       : {plan['location_name']!r}")
        print(f"    raw_description len : {plan['current_raw_description_length']}")
        print(f"    container_title     : {plan['container_title']!r} (via {plan['retrieved_via']})")
        print(f"    planned raw_description: {plan['planned_raw_description']!r}")
    counts = {status: 0 for status in PLAN_CITATION_SAFETY}
    for plan in plans:
        counts[plan["status"]] += 1
    print()
    print(f"cohort: {len(plans)}")
    for status, count in counts.items():
        print(f"  {status}: {count} -> citation_safety={PLAN_CITATION_SAFETY[status]}")


def run_plan(sb, args: argparse.Namespace) -> int:
    cohort = select_cohort(fetch_rows(sb))
    plans: list[dict[str, Any]] = []
    try:
        for row in cohort:
            plans.append(plan_row(row))
    except TransientFetchError as exc:
        print_report(plans)
        print(f"\nABORTED before completing the cohort — network fault, not 'unavailable': {exc}")
        return 2

    print_report(plans)
    plan = build_plan(
        cohort,
        plans,
        description_field_corrections=description_fc_digest(
            sb, [str(row["id"]) for row in cohort]
        ),
    )
    if args.plan_output:
        target = assert_ignored_output_path(args.plan_output)
        write_immutable_json(target, plan)
        print(f"\nplan artifact: {target}")
        print(f"plan_sha256  : {plan['plan_sha256']}")
    return 0


def run_apply(sb, args: argparse.Namespace) -> int:
    if args.rehearsal:
        assert_non_production_target()
    plan = load_plan(args.plan)
    entries = [entry for entry in plan["rows"] if entry["status"] == "planned"]
    results: list[dict[str, Any]] = []
    error: str | None = None
    try:
        for entry in entries:
            results.append(apply_entry(sb, entry))
    except Exception as exc:  # journal first: a raise must not erase what was written
        error = f"{type(exc).__name__}: {exc}"

    journal = build_journal(
        plan,
        results,
        description_field_corrections_after=description_fc_digest(
            sb, [entry["event_id"] for entry in plan["rows"]]
        ),
        error=error,
    )
    if args.journal_output:
        target = assert_ignored_output_path(args.journal_output)
        write_immutable_json(target, journal)
        print(f"journal artifact: {target}")
        print(f"journal_sha256  : {journal['journal_sha256']}")
    print(
        json.dumps(
            {
                "summary": journal["summary"],
                "description_field_corrections_unchanged": journal[
                    "description_field_corrections_unchanged"
                ],
                "citation_safety_sets": journal["citation_safety_sets"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if error:
        print(f"\nSTOPPED: {error}")
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan-output",
        type=Path,
        help="stage 1: write the immutable digest-bound plan artifact",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="stage 2: write the planned raw_description values (default: read-only dry-run)",
    )
    parser.add_argument("--plan", type=Path, help="stage 2: the approved plan artifact to consume")
    parser.add_argument("--journal-output", type=Path, help="stage 2: write the apply journal")
    parser.add_argument(
        "--rehearsal",
        action="store_true",
        help="refuse to write when the resolved project ref is production",
    )
    args = parser.parse_args()
    if args.apply and not args.plan:
        parser.error("--apply requires --plan PATH; re-planning during apply is a defect")
    if args.plan and not args.apply:
        parser.error("--plan is only accepted with --apply")
    if args.apply and args.plan_output:
        parser.error("--plan-output cannot be combined with --apply")
    if args.journal_output and not args.apply:
        parser.error("--journal-output is only accepted with --apply")
    if args.rehearsal and not args.apply:
        parser.error("--rehearsal is only accepted with --apply")

    sb = get_supabase(read_only=not args.apply)
    return run_apply(sb, args) if args.apply else run_plan(sb, args)


if __name__ == "__main__":
    raise SystemExit(main())
