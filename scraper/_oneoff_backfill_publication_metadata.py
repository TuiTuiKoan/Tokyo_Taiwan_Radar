"""One-off backfill for publication metadata.

Scope:
    - active publication events from all publication sources
    - NDL OpenSearch periodical/article rows get a bracketed periodical label

This script mirrors the publication metadata rules used by annotator.py so the
same logic can be applied to existing rows and future re-annotations.

Default mode is dry-run. Use --apply to write updates and lock them through
field_corrections.
"""

from __future__ import annotations

import argparse
from collections import Counter
import time

from annotator import (
    _fetch_ndl_publication_context,
    _fetch_publication_page_description,
    _get_supabase,
    _PERIODICAL_LABEL_EN,
    _PERIODICAL_LABEL_JA,
    _PERIODICAL_LABEL_ZH,
    _PUBLICATION_PREFIX_EN,
    _PUBLICATION_PREFIX_JA,
    _PUBLICATION_PREFIX_ZH,
    _lock_fields_via_corrections,
    _prefix_publication_name,
    _to_trad,
)

TARGET_SOURCES = ("ndl_opensearch", "hanmoto", "kawade_rss", "eslite_spectrum")

_PUBLICATION_PLACEHOLDER_JA = "新刊のご購入は各販売チャネルでお願いします"
_PUBLICATION_PLACEHOLDER_ZH = "新書購買請洽各通路"
_PUBLICATION_PLACEHOLDER_EN = "Please check each sales channel to purchase this new book."


def _chunked(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _with_retry(fetch_fn, *, label: str):
    last_exc = None
    for attempt in range(3):
        try:
            return fetch_fn()
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(1)
    raise RuntimeError(f"{label} failed after 3 attempts: {last_exc}") from last_exc


def _compact_text(value: str | None) -> str:
    return "".join((value or "").split())


def _fetch_candidates(sb, sources: list[str], event_ids: list[str] | None, limit: int | None) -> list[dict]:
    rows = _with_retry(
        lambda: (
            sb.table("events")
            .select(
                "id,source_name,name_ja,name_zh,name_en,organizer,location_name,location_address,business_hours,price_info,description_ja,description_zh,description_en,raw_description,is_active,event_form,annotation_status,source_url,official_url"
            )
            .eq("is_active", True)
            .in_("source_name", sources)
            .execute()
            .data
            or []
        ),
        label="fetch publication candidates",
    )
    if event_ids:
        wanted = set(event_ids)
        rows = [row for row in rows if row["id"] in wanted]
    if limit is not None:
        rows = rows[:limit]
    return rows


def _build_update(event: dict) -> dict:
    source_name = event.get("source_name") or ""
    update: dict = {}

    context = _fetch_ndl_publication_context(event.get("source_url")) if source_name == "ndl_opensearch" else {}
    publication_text_ja = (context.get("publication_label_ja") or _PUBLICATION_PLACEHOLDER_JA).strip()
    publication_text_zh = (context.get("publication_label_zh") or _PUBLICATION_PLACEHOLDER_ZH).strip()
    publication_text_en = (context.get("publication_label_en") or _PUBLICATION_PLACEHOLDER_EN).strip()
    raw_desc = (event.get("raw_description") or "").strip()
    publication_page_url = (event.get("official_url") or event.get("source_url") or "").strip() or None
    if publication_page_url:
        fetched_desc = _fetch_publication_page_description(publication_page_url)
        if fetched_desc:
            raw_desc = fetched_desc

    update["event_form"] = ["publication"]
    update["location_name"] = publication_text_ja
    update["location_name_zh"] = publication_text_zh
    update["location_name_en"] = publication_text_en
    if raw_desc:
        update["description_ja"] = raw_desc
        update["description_zh"] = _to_trad(raw_desc)
        update["description_en"] = raw_desc

    if context.get("is_periodical"):
        current_name_ja = (event.get("name_ja") or "").strip()
        current_name_zh = (event.get("name_zh") or "").strip()
        current_name_en = (event.get("name_en") or "").strip()

        if current_name_ja:
            update["name_ja"] = _prefix_publication_name(
                current_name_ja,
                prefix=_PUBLICATION_PREFIX_JA,
                periodical_label=_PERIODICAL_LABEL_JA,
            )
        if current_name_zh or publication_text_ja:
            update["name_zh"] = _prefix_publication_name(
                current_name_zh or publication_text_ja,
                prefix=_PUBLICATION_PREFIX_ZH,
                periodical_label=_PERIODICAL_LABEL_ZH,
            )
        if current_name_en or publication_text_en:
            update["name_en"] = _prefix_publication_name(
                current_name_en or publication_text_en,
                prefix=_PUBLICATION_PREFIX_EN,
                periodical_label=_PERIODICAL_LABEL_EN,
            )

        update["location_address"] = None
        update["location_address_zh"] = None
        update["location_address_en"] = None
        update["business_hours"] = None
        update["business_hours_zh"] = None
        update["business_hours_en"] = None
        if not event.get("price_info") or event.get("price_info") in {
            _PUBLICATION_PLACEHOLDER_JA,
            _PUBLICATION_PLACEHOLDER_ZH,
            _PUBLICATION_PLACEHOLDER_EN,
        }:
            update["price_info"] = None
        if raw_desc:
            update["description_ja"] = f"掲載誌：{publication_text_ja}\n\n{raw_desc}".strip()
            update["description_zh"] = f"刊載期刊：{publication_text_zh}\n\n{_to_trad(raw_desc)}".strip()
            update["description_en"] = f"Published in: {publication_text_en}\n\n{raw_desc}".strip()
    else:
        update["location_address"] = publication_text_ja
        update["location_address_zh"] = publication_text_zh
        update["location_address_en"] = publication_text_en
        update["business_hours"] = publication_text_ja
        update["business_hours_zh"] = publication_text_zh
        update["business_hours_en"] = publication_text_en
        if not event.get("price_info"):
            update["price_info"] = publication_text_zh
        if event.get("name_ja"):
            update["name_ja"] = _prefix_publication_name(
                event.get("name_ja"),
                prefix=_PUBLICATION_PREFIX_JA,
            )
        if event.get("name_zh"):
            update["name_zh"] = _prefix_publication_name(
                event.get("name_zh"),
                prefix=_PUBLICATION_PREFIX_ZH,
            )
        if event.get("name_en"):
            update["name_en"] = _prefix_publication_name(
                event.get("name_en"),
                prefix=_PUBLICATION_PREFIX_EN,
            )

    if source_name == "ndl_opensearch" and context.get("organizer") and not event.get("organizer"):
        update["organizer"] = context["organizer"]

    return {k: v for k, v in update.items() if v != event.get(k)}


def run(*, apply_changes: bool, sources: list[str], event_ids: list[str] | None, limit: int | None) -> dict:
    sb = _get_supabase()
    rows = _fetch_candidates(sb, sources, event_ids, limit)

    protected_fields: dict[str, set[str]] = {}
    protected_values: dict[tuple[str, str], str] = {}
    if rows:
        fc_rows = _with_retry(
            lambda: (
                sb.table("field_corrections")
                .select("event_id,field_name,corrected_value")
                .in_("event_id", [row["id"] for row in rows])
                .execute()
                .data
                or []
            ),
            label="fetch publication field_corrections",
        )
        for row in fc_rows:
            protected_fields.setdefault(row["event_id"], set()).add(row["field_name"])
            protected_values[(row["event_id"], row["field_name"])] = row.get("corrected_value") or ""

    planned: list[tuple[dict, dict]] = []
    for row in rows:
        update = _build_update(row)
        if not update:
            continue
        blocked_fields = protected_fields.get(row["id"], set())
        for repair_field in ("location_name", "location_address", "business_hours"):
            if repair_field not in blocked_fields:
                continue
            locked_value = protected_values.get((row["id"], repair_field), "")
            if _compact_text(locked_value) == _compact_text(_PUBLICATION_PLACEHOLDER_ZH) and _compact_text(update.get(repair_field)) == _compact_text(_PUBLICATION_PLACEHOLDER_JA):
                blocked_fields = set(blocked_fields)
                blocked_fields.discard(repair_field)
        safe_update = {key: value for key, value in update.items() if key not in blocked_fields}
        if safe_update:
            planned.append((row, safe_update))

    print("publication_metadata_backfill", flush=True)
    print(f"candidate_total={len(rows)}", flush=True)
    print(f"protected_event_total={len(protected_fields)}", flush=True)
    print(f"planned_total={len(planned)}", flush=True)
    print("by_source:", flush=True)
    for source_name, count in Counter(row["source_name"] for row, _ in planned).most_common():
        print(f"  {source_name}: {count}", flush=True)
    if not apply_changes:
        print("dry_run_only=true", flush=True)
        return {"planned_total": len(planned), "updated_total": 0}

    updated_total = 0
    for index, (row, update) in enumerate(planned, start=1):
        sb.table("events").update(update).eq("id", row["id"]).execute()
        lockable_update = {key: value for key, value in update.items() if value is not None}
        if lockable_update:
            _lock_fields_via_corrections(sb, row["id"], lockable_update)
        updated_total += 1
        if index % 25 == 0 or index == len(planned):
            print(f"updated {index}/{len(planned)}", flush=True)

    print(f"updated_total={updated_total}", flush=True)
    return {"planned_total": len(planned), "updated_total": updated_total}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill publication metadata from source pages")
    parser.add_argument("--apply", action="store_true", help="Write updates and lock them")
    parser.add_argument("--source", action="append", choices=sorted(TARGET_SOURCES), help="Limit to source(s)")
    parser.add_argument("--event-id", action="append", help="Limit to one or more event ids")
    parser.add_argument("--limit", type=int, help="Limit candidate count after filtering")
    args = parser.parse_args()
    run(
        apply_changes=args.apply,
        sources=args.source or list(TARGET_SOURCES),
        event_ids=args.event_id,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()