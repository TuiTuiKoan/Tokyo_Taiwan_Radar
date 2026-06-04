"""One-off reset + re-annotate for publication sources stuck in error.

Scope:
    - source_name in: ndl_opensearch, hanmoto, kawade_rss
  - annotation_status = error
  - is_active = true
  - skip any event that has field_corrections rows

Default mode is dry-run. Use --apply to reset selected rows to pending and
re-run the annotator only for the selected event ids.
"""

from __future__ import annotations

import argparse
from collections import Counter

from annotator import _get_supabase, annotate_pending_events

TARGET_SOURCES = ("ndl_opensearch", "hanmoto", "kawade_rss")
ANNOTATE_CHUNK_SIZE = 50
QUERY_CHUNK_SIZE = 200


def _chunked(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _fetch_candidates(sb, sources: list[str]) -> list[dict]:
    rows = (
        sb.table("events")
        .select("id,source_name,name_ja,name_en,annotation_status,is_active,created_at")
        .in_("source_name", sources)
        .eq("annotation_status", "error")
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return rows


def _load_protected_event_ids(sb, event_ids: list[str]) -> set[str]:
    protected_ids: set[str] = set()
    for chunk in _chunked(event_ids, QUERY_CHUNK_SIZE):
        rows = (
            sb.table("field_corrections")
            .select("event_id,field_name")
            .in_("event_id", chunk)
            .execute()
            .data
            or []
        )
        for row in rows:
            event_id = row.get("event_id")
            if event_id:
                protected_ids.add(event_id)
    return protected_ids


def _fetch_status_rows(sb, event_ids: list[str]) -> list[dict]:
    rows: list[dict] = []
    for chunk in _chunked(event_ids, QUERY_CHUNK_SIZE):
        rows.extend(
            (
                sb.table("events")
                .select(
                    "id,source_name,name_ja,name_zh,name_en,location_name,location_address,business_hours,price_info,annotation_status"
                )
                .in_("id", chunk)
                .execute()
                .data
                or []
            )
        )
    return rows


def _restore_pending_to_error(sb, event_ids: list[str]) -> None:
    for chunk in _chunked(event_ids, QUERY_CHUNK_SIZE):
        sb.table("events").update({"annotation_status": "error"}).in_("id", chunk).eq(
            "annotation_status", "pending"
        ).execute()


def _print_summary(label: str, rows: list[dict], protected_ids: set[str]) -> None:
    by_source = Counter(row["source_name"] for row in rows)
    print(label)
    print(f"candidate_total={len(rows)}")
    for source_name, count in sorted(by_source.items()):
        print(f"  {source_name}: {count}")
    print(f"protected_skip_total={len(protected_ids)}")


def _print_post_run(rows: list[dict], expected_ids: set[str]) -> None:
    by_status = Counter(row.get("annotation_status") or "<null>" for row in rows)
    missing_name_zh = sum(1 for row in rows if not row.get("name_zh"))
    missing_name_en = sum(1 for row in rows if not row.get("name_en"))
    publication_text = "新書購買請洽各通路"
    templated_location = sum(1 for row in rows if row.get("location_name") == publication_text)
    templated_address = sum(1 for row in rows if row.get("location_address") == publication_text)
    templated_hours = sum(1 for row in rows if row.get("business_hours") == publication_text)
    templated_price = sum(1 for row in rows if row.get("price_info") == publication_text)
    print("post_run_summary")
    for status, count in sorted(by_status.items()):
        print(f"  status[{status}]={count}")
    print(f"  missing_name_zh={missing_name_zh}")
    print(f"  missing_name_en={missing_name_en}")
    print(f"  template_location_name={templated_location}/{len(rows)}")
    print(f"  template_location_address={templated_address}/{len(rows)}")
    print(f"  template_business_hours={templated_hours}/{len(rows)}")
    print(f"  template_price_info={templated_price}/{len(rows)}")

    remaining_errors = [row for row in rows if row.get("annotation_status") == "error"]
    if remaining_errors:
        print("remaining_error_ids=")
        for row in remaining_errors:
            print(f"  {row['id']} | {row.get('source_name')} | {row.get('name_ja') or ''}")

    missing_ids = sorted(expected_ids - {row["id"] for row in rows})
    if missing_ids:
        print("missing_rows_after_run=")
        for event_id in missing_ids:
            print(f"  {event_id}")


def run(*, apply_changes: bool, sources: list[str], event_ids: list[str] | None, limit: int | None) -> None:
    sb = _get_supabase()
    rows = _fetch_candidates(sb, sources)
    if event_ids:
        wanted = set(event_ids)
        rows = [row for row in rows if row["id"] in wanted]
    if limit is not None:
        rows = rows[:limit]

    protected_ids = _load_protected_event_ids(sb, [row["id"] for row in rows]) if rows else set()
    runnable_rows = [row for row in rows if row["id"] not in protected_ids]
    runnable_ids = [row["id"] for row in runnable_rows]

    _print_summary("publication_error_reset", rows, protected_ids)
    if protected_ids:
        print("protected_skip_ids=")
        for row in rows:
            if row["id"] in protected_ids:
                print(f"  {row['id']} | {row.get('source_name')} | {row.get('name_ja') or ''}")
    if runnable_ids:
        print("runnable_ids=")
        for row in runnable_rows:
            print(f"  {row['id']} | {row.get('source_name')} | {row.get('name_ja') or ''}")

    if not apply_changes:
        print("dry_run_only=true")
        return

    if not runnable_ids:
        print("apply_skipped=true")
        return

    for chunk in _chunked(runnable_ids, QUERY_CHUNK_SIZE):
        sb.table("events").update({"annotation_status": "pending"}).in_("id", chunk).eq(
            "annotation_status", "error"
        ).execute()

    try:
        for chunk in _chunked(runnable_ids, ANNOTATE_CHUNK_SIZE):
            annotate_pending_events(event_ids=chunk)
    except Exception:
        _restore_pending_to_error(sb, runnable_ids)
        print("restored_pending_to_error=true")
        raise

    post_rows = _fetch_status_rows(sb, runnable_ids)
    _print_post_run(post_rows, set(runnable_ids))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset + re-annotate publication error events")
    parser.add_argument("--apply", action="store_true", help="Reset selected rows to pending and re-annotate")
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(TARGET_SOURCES),
        help="Limit to one or more publication sources",
    )
    parser.add_argument("--event-id", action="append", help="Limit to one or more specific event ids")
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