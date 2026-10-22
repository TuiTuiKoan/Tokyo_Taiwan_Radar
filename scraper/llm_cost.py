"""OpenAI cost for reports, read from the llm_cost_daily view (#322, #363).

Every OpenAI call is one public.llm_usage row since 2026-10-22 (LEDGER_START);
llm_cost_daily prices them per JST day, caller and model from llm_pricing.
scraper_runs.cost_usd only ever covered the annotator and researcher, so the
reports under-counted about four times; nothing here reads it.

Days are JST dates, end exclusive. Rows are paged (db_paging.fetch_all), so a
long window is not cut at PostgREST's 1000-row cap.

    rows = llm_cost.fetch_rows(sb, date(2026, 10, 1), date(2026, 11, 1))
    s = llm_cost.summarize(rows)
    s["total"], s["by_caller"], s["unpriced_calls"]
"""

from __future__ import annotations

from datetime import date

from db_paging import fetch_all

LEDGER_START = date(2026, 10, 22)


def fetch_rows(
    sb, start_day: date, end_day_exclusive: date, *, caller_prefix: str | None = None
) -> list[dict]:
    """llm_cost_daily rows with start_day <= day < end_day_exclusive, optionally one caller family."""

    def query():
        q = (
            sb.table("llm_cost_daily")
            .select("day,caller,model,calls,errors,cost_usd,unpriced_calls")
            .gte("day", start_day.isoformat())
            .lt("day", end_day_exclusive.isoformat())
        )
        if caller_prefix:
            q = q.like("caller", f"{caller_prefix}%")
        return q.order("day").order("caller").order("model")

    return fetch_all(query)


def summarize(rows: list[dict]) -> dict:
    """Total cost, cost per caller (largest first), calls, errors and unpriced calls."""
    by_caller: dict[str, float] = {}
    calls = errors = unpriced = 0
    for r in rows:
        caller = r.get("caller") or "unknown"
        by_caller[caller] = by_caller.get(caller, 0.0) + float(r.get("cost_usd") or 0)
        calls += int(r.get("calls") or 0)
        errors += int(r.get("errors") or 0)
        unpriced += int(r.get("unpriced_calls") or 0)
    return {
        "total": sum(by_caller.values()),
        "by_caller": dict(sorted(by_caller.items(), key=lambda kv: (-kv[1], kv[0]))),
        "calls": calls,
        "errors": errors,
        "unpriced_calls": unpriced,
    }


def window_cost(
    sb, start_day: date, end_day_exclusive: date, *, caller_prefix: str | None = None
) -> dict:
    return summarize(fetch_rows(sb, start_day, end_day_exclusive, caller_prefix=caller_prefix))


def coverage_note(start_day: date) -> str | None:
    """A note for windows that begin before the ledger existed, else None."""
    if start_day >= LEDGER_START:
        return None
    return (
        f"費用紀錄從 {LEDGER_START.isoformat()} 開始；之前的費用只在 OpenAI dashboard，"
        "此處偏低。"
    )
