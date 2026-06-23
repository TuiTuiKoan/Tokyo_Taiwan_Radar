"""
report_window.py — Side-effect-free report-window resolver.

Single source of truth for the time bounds, file key, and output path of a
weekly or monthly docs report. Everything (Supabase query bounds, git
inventory bounds, markdown metadata, output path) must be derived from the
``ReportWindow`` returned by :func:`resolve_report_window`.

This module is intentionally dependency-free (stdlib only) and has no side
effects: no Supabase, no LINE, no filesystem writes. It must never import
``docs_report.py`` so that ``monthly_health_check.py`` and ``docs_report.py``
can both rely on it without creating an import cycle.

All windows are half-open in JST: ``window_start <= t < window_end_exclusive``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class ReportWindow:
    """Resolved, immutable bounds for a single weekly/monthly report.

    Attributes:
        report_key: Stable key + filename stem (weekly: week-ending Sunday
            ``YYYY-MM-DD``; monthly: ``YYYY-MM``).
        report_type: ``"weekly"`` or ``"monthly"``.
        window_start: Inclusive JST start of the window.
        window_end_exclusive: Exclusive JST end of the window.
        display_window_start: Human-readable inclusive first day ``YYYY-MM-DD``.
        display_window_end: Human-readable inclusive last day ``YYYY-MM-DD``.
        output_relative_path: Path relative to the docs output root, e.g.
            ``weekly_review/2026-06-14.md`` or ``monthly_review/2026-06.md``.
    """

    report_key: str
    report_type: str
    window_start: datetime
    window_end_exclusive: datetime
    display_window_start: str
    display_window_end: str
    output_relative_path: str


def _parse_now_jst(now_jst: str | datetime | None) -> datetime:
    """Normalize the optional ``now`` reference into an aware JST datetime."""
    if now_jst is None:
        return datetime.now(tz=JST)
    if isinstance(now_jst, datetime):
        dt = now_jst
    else:
        dt = datetime.fromisoformat(now_jst)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def _jst_midnight(d: date) -> datetime:
    """Return JST 00:00:00 for the calendar date of ``d``."""
    return datetime(d.year, d.month, d.day, tzinfo=JST)


def _resolve_weekly(date: str | None, now: datetime) -> ReportWindow:
    if date is not None:
        anchor = datetime.fromisoformat(date).date()
    else:
        # Most recent completed Monday-Sunday week. The current week's Monday is
        # ``now - weekday`` days; the previous Sunday is one day before it.
        current_week_monday = now.date() - timedelta(days=now.weekday())
        anchor = current_week_monday - timedelta(days=1)

    # Snap the anchor to the week-ending Sunday of its Mon-Sun week so that a
    # non-Sunday ``--date`` still resolves deterministically.
    week_monday = anchor - timedelta(days=anchor.weekday())
    week_sunday = week_monday + timedelta(days=6)

    window_start = _jst_midnight(week_monday)
    window_end_exclusive = _jst_midnight(week_sunday + timedelta(days=1))
    report_key = week_sunday.strftime("%Y-%m-%d")

    return ReportWindow(
        report_key=report_key,
        report_type="weekly",
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
        display_window_start=week_monday.strftime("%Y-%m-%d"),
        display_window_end=week_sunday.strftime("%Y-%m-%d"),
        output_relative_path=f"weekly_review/{report_key}.md",
    )


def _resolve_monthly(month: str | None, now: datetime) -> ReportWindow:
    if month is not None:
        year, mon = (int(p) for p in month.split("-", 1))
        window_start = datetime(year, mon, 1, tzinfo=JST)
    else:
        # Previous complete JST calendar month relative to ``now``.
        this_month_start = datetime(now.year, now.month, 1, tzinfo=JST)
        prev_month_last_day = this_month_start - timedelta(days=1)
        window_start = datetime(prev_month_last_day.year, prev_month_last_day.month, 1, tzinfo=JST)

    # First day of the following month (exclusive end).
    if window_start.month == 12:
        window_end_exclusive = datetime(window_start.year + 1, 1, 1, tzinfo=JST)
    else:
        window_end_exclusive = datetime(window_start.year, window_start.month + 1, 1, tzinfo=JST)

    report_key = window_start.strftime("%Y-%m")
    last_day = window_end_exclusive - timedelta(days=1)

    return ReportWindow(
        report_key=report_key,
        report_type="monthly",
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
        display_window_start=window_start.strftime("%Y-%m-%d"),
        display_window_end=last_day.strftime("%Y-%m-%d"),
        output_relative_path=f"monthly_review/{report_key}.md",
    )


def resolve_report_window(
    mode: str,
    *,
    date: str | None = None,
    month: str | None = None,
    now_jst: str | datetime | None = None,
) -> ReportWindow:
    """Resolve the single canonical window for a weekly or monthly report.

    Args:
        mode: ``"weekly"`` or ``"monthly"``.
        date: Weekly week-ending Sunday key ``YYYY-MM-DD`` (weekly only).
        month: Monthly key ``YYYY-MM`` (monthly only); overrides the scheduled
            previous-complete-month default.
        now_jst: Test-only reference time (ISO 8601 or datetime). Workflows omit
            this so it defaults to the real current JST time.

    Returns:
        A fully resolved :class:`ReportWindow`.
    """
    now = _parse_now_jst(now_jst)
    if mode == "weekly":
        return _resolve_weekly(date, now)
    if mode == "monthly":
        return _resolve_monthly(month, now)
    raise ValueError(f"Unknown report mode: {mode!r} (expected 'weekly' or 'monthly')")
