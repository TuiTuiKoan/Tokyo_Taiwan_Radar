"""
Daily health check for Tokyo Taiwan Radar.

Queries scraper_runs for the past 24 hours and sends a LINE alert ONLY
when issues are detected. Silent on success — no noise on healthy days.

Checks performed:
  1. Sources that failed (success=False) in the last 24 h
  2. Sources that ran 0 events (possible selector break or empty response)
  3. Active sources not present in scraper_runs at all (silent failure)
  4. google_news_rss active events with start_date but no article fetch
     (raw_description contains '（Google News）' — indicates pub_date residue
     or upstream date error that survived the 9510a05 cleanup)
  5. tokyoartbeat active events where start_date differs from the date
     embedded in source_url (upstream Contentful data was corrected after
     scrape but upsert skipped the event as already-existing)

The list of expected sources is derived from scraper_runs history (sources
seen in the past 7 days) to avoid hardcoding the SCRAPERS list here.

Usage:
    python health_check.py            # run live, alert on issues
    python health_check.py --dry-run  # print report without sending LINE
    python health_check.py --always   # send LINE even when healthy (for testing)
"""

import argparse
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# Sources that are NOT expected to run every day (skip from "missing" alerts)
# weekly_broadcast runs Thu 09:00 JST + Fri 12:00 JST only (not daily)
NON_DAILY_SOURCES: frozenset[str] = frozenset({
    "weekly_broadcast",
    # Weekly-only scrapers (run on Monday UTC only)
    "oaff", "tokyo_filmex", "tiff", "tiff_jp",
    "ifi", "waseda_icl", "tuat_global",
    "tokyo_now", "fukuoka_now", "hankyu_umeda",
    "nagano_aioiza", "maruhiro", "whitestone_gallery",
})

# Sources that legitimately return 0 events during quiet periods.
# These are NOT treated as possible selector breaks.
#   - Cinema scrapers: only emit events when a Taiwan film is currently showing.
#   - Seasonal film festivals: only active during their festival window.
ZERO_EVENT_OK_SOURCES: frozenset[str] = frozenset({
    # Cinema scrapers — 0 events = no Taiwan film on screen right now (normal)
    "cineswitch_ginza",
    "cine_marine",
    "cinemart_shinjuku",
    "ks_cinema",
    "shin_bungeiza",
    "eurospace",
    "uplink_cinema",
    "human_trust_cinema",
    "stranger",
    "united_cinemas",
    "ginsee_roble",
    "ginsee_hikariza",
    "cine_gallery",
    "kbc_cinema",
    "kino_cinema_shinsaibashi",
    "kyoto_cinema",
    "sakurazaka",
    "nagano_aioiza",
    "ttcg_umeda",
    "cinelibre_kobe",
    "kawasaki_ac",
    "midland_cinema",
    "cinemadict",
    "theater_enya",
    "starcat_cinema",
    "cinewind",
    "ycam_cinema",
    "otto",
    "amayaza",
    "theater_kino",
    "ciema",
    "acros_fukuoka",
    "whitestone_gallery",  # Occasional Taiwan artist shows; 0 events is normal
    "startup_terrace",     # Japan mission articles are occasional; 0 events is normal
    "ueda_eigeki",         # Small Nagano arthouse; Taiwan films are occasional; 0 events is normal
    "cinema_clair",        # Small Okayama arthouse; Taiwan films are occasional; 0 events is normal
    "taiwan_prism",        # Annual 2-day Kyoto festival; 0 events most of the year is normal
    # General listings with occasional Taiwan events (0 events = no Taiwan event on now)
    "tokyo_now",           # Tribe Events API; 168+ events but Taiwan ones are rare
    "tokyo_city_i",        # KITTE tourist center; ~2-5 Taiwan events/year
    "jposa_ja",            # Osaka TECO RSS; ~1-3 cultural events/month, rest are diplomatic
    # Seasonal film festivals — only active during festival period
    "oaff",
    "tokyo_filmex",
    "tiff",
    "tiff_jp",
    "ssff",
    # Weekly scrapers — 0 events on non-Monday days is expected
    "ifi",
    "waseda_icl",
    "tuat_global",
    "fukuoka_now",
    "hankyu_umeda",
    "maruhiro",
})


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def run_check(dry_run: bool = False, always_notify: bool = False) -> None:
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    today_jst = now.astimezone(JST).strftime("%Y/%m/%d")

    sb = _supabase_client()

    # ── 1. Fetch runs from the past 24 hours ──────────────────────────────
    runs_24h = (
        sb.table("scraper_runs")
        .select("source, events_processed, success, ran_at")
        .gte("ran_at", since_24h.isoformat())
        .execute()
    ).data or []

    # ── 2. Determine expected active sources (seen in past 7 days) ────────
    runs_7d = (
        sb.table("scraper_runs")
        .select("source")
        .gte("ran_at", since_7d.isoformat())
        .execute()
    ).data or []
    expected_sources: set[str] = {r["source"] for r in runs_7d} - NON_DAILY_SOURCES

    # ── 3. Classify today's runs ──────────────────────────────────────────
    ran_today: set[str] = set()
    failed: list[str] = []
    zero_events: list[str] = []

    for r in runs_24h:
        src = r["source"]
        ran_today.add(src)
        if not r.get("success", True):
            failed.append(src)
        elif r.get("events_processed", 0) == 0:
            if src not in ZERO_EVENT_OK_SOURCES:
                zero_events.append(src)

    # Sources expected to run but absent from today's runs
    missing: list[str] = sorted(expected_sources - ran_today)

    # ── 4. gnews: active events with start_date but article fetch failed ──
    # Symptom: raw_description prefix is '開催情報（Google News）:' (no real
    # domain) yet start_date is NOT NULL — the date likely came from a
    # pub_date fallback or upstream error and was never corrected.
    # Only flag genuinely suspicious cases:
    #   - start_date is in the PAST (already ended, still active) — likely pub_date residual
    #   - Ignore future-dated events: even if the date came from a short snippet,
    #     it doesn't cause user-visible harm and future dates are harder to validate.
    gnews_suspect: list[dict] = []
    try:
        today_str = now.astimezone(JST).date().isoformat()
        gnews_rows = (
            sb.table("events")
            .select("id,name_ja,start_date,source_url")
            .eq("source_name", "google_news_rss")
            .eq("is_active", True)
            .not_.is_("start_date", None)
            .lt("start_date", today_str)   # only past dates are actionable
            .like("raw_description", "開催情報（Google News）:%")
            .execute()
        ).data or []
        gnews_suspect = gnews_rows
    except Exception as exc:
        logger.warning("Check 4 (gnews date audit) failed: %s", exc)

    # ── 5. tokyoartbeat: start_date differs from date in source_url ───────
    # source_url format: .../YYYY-MM-DD  (the last path segment is the date)
    # Upstream Contentful data can be corrected after scrape; upsert skips
    # already-existing events so the stale date stays in DB.
    tab_mismatch: list[dict] = []
    try:
        tab_rows = (
            sb.table("events")
            .select("id,name_ja,start_date,source_url")
            .eq("source_name", "tokyoartbeat")
            .eq("is_active", True)
            .not_.is_("start_date", None)
            .execute()
        ).data or []
        _date_in_url = re.compile(r"/(\d{4}-\d{2}-\d{2})$")
        for row in tab_rows:
            url_m = _date_in_url.search(row.get("source_url") or "")
            if not url_m:
                continue
            url_date = url_m.group(1)
            db_date = (row.get("start_date") or "")[:10]
            if db_date and db_date != url_date:
                tab_mismatch.append(row)
    except Exception as exc:
        logger.warning("Check 5 (tokyoartbeat date audit) failed: %s", exc)

    # ── 6. Build report ───────────────────────────────────────────────────
    issues: list[str] = []

    if failed:
        issues.append("🔴 爬蟲失敗（scraper error）：")
        for src in sorted(failed):
            issues.append(f"  • {src}")

    if zero_events:
        issues.append("🟡 執行成功但 0 件活動（selector 可能壞掉）：")
        for src in sorted(zero_events):
            issues.append(f"  • {src}")

    if missing:
        issues.append("⚠️ 預期執行但今日未出現於 scraper_runs：")
        for src in missing:
            issues.append(f"  • {src}")

    if gnews_suspect:
        issues.append("🟠 gnews 活動有 start_date 但未抓到文章（可能是 pub_date 殘留）：")
        for row in gnews_suspect[:5]:  # cap to avoid message overflow
            issues.append(
                f"  • {row['id']} {(row.get('start_date') or '')[:10]}"
                f" {(row.get('name_ja') or '')[:30]}"
            )
        if len(gnews_suspect) > 5:
            issues.append(f"  …（共 {len(gnews_suspect)} 筆）")

    if tab_mismatch:
        issues.append("🟠 tokyoartbeat start_date 與 source_url 日期不符（Contentful 已更正但 DB 未同步）：")
        for row in tab_mismatch[:5]:
            url_date = re.search(r"/(\d{4}-\d{2}-\d{2})$", row.get("source_url") or "")
            issues.append(
                f"  • {row['id']} DB={( row.get('start_date') or '')[:10]}"
                f" URL={url_date.group(1) if url_date else '?'}"
                f" {(row.get('name_ja') or '')[:25]}"
            )
        if len(tab_mismatch) > 5:
            issues.append(f"  …（共 {len(tab_mismatch)} 筆）")

    has_issues = bool(issues)
    ran_count = len(ran_today)
    ok_count = ran_count - len(set(failed)) - len(set(zero_events))

    if has_issues or always_notify:
        header = (
            f"{'🚨 ' if has_issues else '✅ '}"
            f"爬蟲健康チェック — {today_jst}\n"
            f"過去24h: {ran_count} ソース実行 / {ok_count} 正常\n"
        )
        body = "\n".join(issues) if issues else "✅ すべて正常です"
        message = header + "\n" + body
    else:
        logger.info(
            "Health check PASSED: %d sources ran, all healthy — no LINE alert sent.",
            ran_count,
        )
        return

    if dry_run:
        print("\n--- LINE message preview ---")
        print(message)
        print("--- end ---\n")
    else:
        from line_notify import send_line_message
        send_line_message(message)
        logger.info("Health check alert sent via LINE.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily scraper health check")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending LINE")
    parser.add_argument("--always", action="store_true", help="Send LINE even when all healthy")
    args = parser.parse_args()
    run_check(dry_run=args.dry_run, always_notify=args.always)
