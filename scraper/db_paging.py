"""Read every row of a Supabase query past PostgREST's 1000-row cap.

PostgREST returns at most 1000 rows per request, so an unpaged select over a
large table is silently truncated (the monthly cost sum in the weekly report
once came out smaller than a single week, #322).

Pass a factory, not a query: postgrest-py's .range() appends offset/limit
params, so reusing one builder for several pages sends duplicates. Give the
query a stable order (e.g. .order("id")) so pages do not overlap or skip.

    rows = fetch_all(lambda: sb.table("scraper_runs").select("source").order("id"))
"""

from __future__ import annotations

from typing import Any, Callable

PAGE_SIZE = 1000


def fetch_all(make_query: Callable[[], Any], page_size: int = PAGE_SIZE) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = make_query().range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size
