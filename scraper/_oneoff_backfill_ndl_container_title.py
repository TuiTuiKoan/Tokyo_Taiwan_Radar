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

    python _oneoff_backfill_ndl_container_title.py            # read-only report
    python _oneoff_backfill_ndl_container_title.py --apply    # requires approval
"""

from __future__ import annotations

import argparse
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
from dotenv import load_dotenv
from supabase import create_client

from _oneoff_backfill_publication_metadata import (
    PHYSICAL_LOCATION_RE,
    POSTER_POLLUTION_REPAIRS,
    PUBLICATION_LOCATION_MARKERS,
)
from publication_rules import is_pure_publication_record
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

load_dotenv(Path(__file__).with_name(".env"))

USER_AGENT = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
DETAIL_LABEL = "掲載誌名"
PAGE_SIZE = 500
REQUEST_DELAY = 1.0
MAX_ATTEMPTS = 4
TIMEOUT = 30

SELECT_COLUMNS = (
    "id,source_name,source_id,source_url,event_form,location_name,"
    "raw_title,name_ja,raw_description,description_ja"
)

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


def apply_plan(sb, plan: dict[str, Any]) -> str:
    """Compare-and-set on the exact raw_description this plan was built from."""
    query = sb.table("events").update(
        {"raw_description": plan["planned_raw_description"]}
    ).eq("id", plan["event_id"])
    query = apply_cas_filter(query, "raw_description", plan["current_raw_description"])
    if not query.execute().data:
        return "cas_miss"
    read_back = (
        sb.table("events")
        .select("raw_description")
        .eq("id", plan["event_id"])
        .single()
        .execute()
        .data
    )
    if (read_back or {}).get("raw_description") != plan["planned_raw_description"]:
        raise RuntimeError(f"{plan['event_id']}: read-back does not match the planned value")
    return "applied"


def print_report(plans: list[dict[str, Any]], *, applied: dict[str, str] | None) -> None:
    for plan in plans:
        print(f"--- {plan['event_id']}  [{plan['status']}]")
        print(f"    source_url          : {plan['source_url']}")
        print(f"    location_name       : {plan['location_name']!r}")
        print(f"    raw_description len : {plan['current_raw_description_length']}")
        print(f"    container_title     : {plan['container_title']!r} (via {plan['retrieved_via']})")
        print(f"    planned raw_description: {plan['planned_raw_description']!r}")
        if applied is not None:
            print(f"    write result        : {applied.get(plan['event_id'], 'skipped')}")
    counts = {
        status: 0
        for status in ("planned", "needs_review", "already_present", "unavailable")
    }
    for plan in plans:
        counts[plan["status"]] += 1
    print()
    print(f"cohort: {len(plans)}")
    for status, count in counts.items():
        print(f"  {status}: {count}")
    if applied is None:
        print("writes performed: 0 (dry-run)")
    else:
        print(f"writes performed: {sum(1 for value in applied.values() if value == 'applied')}")
        print(f"cas misses: {sum(1 for value in applied.values() if value == 'cas_miss')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the planned raw_description values (default: read-only dry-run)",
    )
    args = parser.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    cohort = select_cohort(fetch_rows(sb))

    plans: list[dict[str, Any]] = []
    try:
        for row in cohort:
            plans.append(plan_row(row))
    except TransientFetchError as exc:
        print_report(plans, applied=None)
        print(f"\nABORTED before completing the cohort — network fault, not 'unavailable': {exc}")
        return 2

    applied: dict[str, str] | None = None
    if args.apply:
        applied = {
            plan["event_id"]: apply_plan(sb, plan) for plan in applicable_plans(plans)
        }
    print_report(plans, applied=applied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
