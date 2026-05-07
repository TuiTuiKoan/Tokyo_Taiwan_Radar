"""
auto_qa.py — Automated translation & address quality checks.

Scans recent events and inserts pending rows into `event_reports` so that
admins can review/fix anomalies via /admin/reports.

Detectors:
  1. auto_qa_simplified_zh   — Simplified Chinese chars in any *_zh field
                               (name_zh, description_zh, location_name_zh,
                                location_address_zh)
  2. auto_qa_missing_address — Has location_name but location_address is empty
                               (skips online / TV / pure-katakana venues)

Dedup: skips events that already have a pending event_report of the same
auto_qa type (no spam re-creation across runs).

Scope: only events with is_active=true and created_at within the last
QA_WINDOW_DAYS (default 14) — keeps the run cheap and focused on fresh data.

Usage:
    python auto_qa.py            # live run
    python auto_qa.py --dry-run  # report, no writes
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from collections import defaultdict as _defaultdict
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QA_WINDOW_DAYS = 14

# Matches the char list maintained in copilot-instructions Step 5,
# extended with chars seen in real anomaly samples. Only chars that are
# unambiguously simplified-only (NOT valid in Traditional Chinese or
# Japanese) belong here, to avoid false positives.
SIMP_RE = re.compile(
    r"[东来这发会说时问门关对长进现与实变内还单层达诺厅络设联馆园乐欢艺师"
    r"丰个为产业亲见开闭难纪员体让历观书写报场属层听处声证识请赞动务区团圆"
    r"岛带帮当录张归态总职护扩续齐奖将断湾览间气坛静满简洁优连释迹仪壮汇灯"
    r"蕴韵须恳构传经验弥记调节约运办导环义战组织国际临创据点击继阅读"
    r"画获选赛参电热爱独虑忆仅尝试谈龙华灵极标准规细广庆响惊显类宝贵丽尽挡"
    r"统种学数编价乡网绍预称评议论结应"
    r"药讲谱购绘们该课谁谢谋词误诚诉诊讨训"
    r"检样档桥梦楼浅测浏涂渐线练终绪缘缩"
    r"肤脑脸腊范荡补装车轮软输辞边辅辆辩"
    r"队阶阳陆陈随隐页顺领颗题颜额风饭饮"
    r"龄齿龟迁递逻遗邮邻酱酿"
    r"钟钢钱铁铜铝银锁锋错镇镜闲闸险雾"
    r"驾骗骤鱼鲜鸟鸡鸣踪]"
)

ZH_FIELDS = ("name_zh", "description_zh", "location_name_zh", "location_address_zh", "business_hours_zh")

ADDRESS_SKIP_KEYWORDS = (
    "オンライン", "online", "Online",
    "電視", "テレビ", "tv", "TV",
    "Zoom", "zoom", "YouTube", "youtube",
    "配信", "ライブ配信",
)

# Vague city names that provide no useful address information — skip missing_address check.
VAGUE_CITY_NAMES = frozenset([
    '東京', '大阪', '京都', '名古屋', '福岡', '札幌', '仙台',
    '横浜', '神戸', '広島', '岡山', '北海道', '沖縄', '埼玉', '千葉', '神奈川',
])

# Keywords indicating an overseas (non-Japan) venue — skip missing_address check.
OVERSEAS_KEYWORDS = (
    'スイス', 'フランス', 'アメリカ', 'ドイツ', 'イギリス',
    'ニューヨーク', 'パリ', 'ロンドン', 'ベルリン', '台湾', '香港',
)

QA_TYPES = ("auto_qa_simplified_zh", "auto_qa_missing_address", "auto_qa_missing_hours", "auto_simplified_chinese", "auto_qa_same_work_duplicate")

# Precise SC-only char set for the broad auto_simplified_chinese detector.
# Only chars that are unambiguously simplified-only (different glyph in TC).
SC_ONLY = set(
    "药讲谱识购专让设证评达运选进过还适连远这该请说话谈读论"
    "间问关开动办对书学习时现经统场备产温术节历难声变热实"
    "见观规计认记议讨训诉诊试课调谁谢谋诚诺误词"
    "条来极构检样标档桥梦楼概欢歼残毕毙"
    "汇济浅测浏浓涂涌渐满灾灵点烂"
    "爱独环电疗痴瘫"
    "线练组细织终结绍绩绪编缘缩总绘"
    "联职肤脑脸腊"
    "苏范荡荣蒙虑蜡"
    "补装裤"
    "车轮软输辑辞边"
    "队阶阳际陆陈随隐"
    "页顺须领颗题颜额风饭饮馆"
    "龙龟齿龄"
    "仅从们价优传伤体"
    "创刚则划"
    "厂厅压厌"
    "单卖卫"
    "团围国图"
    "块坚坛坝坟"
    "处复够头夺奋奖"
    "宝审宪寻导寿将"
    "尘尝尽层岁岛"
    "币师帮广库应废"
    "归当录征"
    "忆忧怀态恶惊惧"
    "战扩扰护报拥择挡挤"
    "损携摄撑"
    "无旧显晓暂"
    "杂权"
    "沟泪浑"
    "猎献猪环"
    "盘监确碍"
    "积称税稳"
    "签简类粮纠纤纪纯纱纲纳纷纸"
    "罗罚"
    "艰艺"
    "虏蚀"
    "赏赐赖赚赛赞赠赶"
    "踪蹈"
    "辅辆辩"
    "迁递逻遗"
    "邮邻郑"
    "酱酿释"
    "钟钢钱铁铜铝银锁锋错镇镜长"
    "闭闲阅闸门"
    "险雾零"
    "驾骗骤"
    "鱼鲜鸟鸡鸣"
)


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _has_simplified(text: str | None) -> bool:
    if not text:
        return False
    return bool(SIMP_RE.search(text))


def _is_online_or_tv(name: str | None) -> bool:
    if not name:
        return False
    return any(kw in name for kw in ADDRESS_SKIP_KEYWORDS)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _latest_auto_qa_reports(sb, event_ids: list[str]) -> dict[str, dict[str, dict[str, str | None]]]:
    """Map event_id/report_type to the latest auto_qa event_report row."""
    if not event_ids:
        return {}
    out: dict[str, dict[str, dict[str, str | None]]] = {}
    # Supabase JS-py: chunk to avoid 1000-row in() limit
    for i in range(0, len(event_ids), 200):
        chunk = event_ids[i : i + 200]
        res = (
            sb.table("event_reports")
            .select("event_id, report_types, status, created_at, confirmed_at")
            .in_("event_id", chunk)
            .in_("status", ["pending", "confirmed", "dismissed"])
            .execute()
        )
        for row in res.data or []:
            event_map = out.setdefault(row["event_id"], {})
            created_at = row.get("created_at")
            created_dt = _parse_ts(created_at)
            for t in row.get("report_types") or []:
                if t not in QA_TYPES:
                    continue
                prev = event_map.get(t)
                prev_created = _parse_ts(prev.get("created_at") if prev else None)
                if prev is None or (created_dt and prev_created and created_dt > prev_created) or (
                    prev is not None and prev_created is None and created_dt is not None
                ):
                    event_map[t] = {
                        "status": row.get("status"),
                        "created_at": created_at,
                        "confirmed_at": row.get("confirmed_at"),
                    }
    return out


def _detect_missing_hours(sb) -> list[dict]:
    """Flag reviewed events with null business_hours but extractable time
    info in raw_description. Human-review only — no auto-fix."""
    import re as _re
    _TIME_RE = _re.compile(r'\d{1,2}:\d{2}')
    rows = (
        sb.table("events")
        .select("id,source_name,raw_description")
        .eq("is_active", True)
        .eq("annotation_status", "reviewed")
        .is_("business_hours", "null")
        .not_.is_("raw_description", "null")
        .execute()
        .data
    )
    reports = []
    for row in rows:
        raw = row.get("raw_description") or ""
        if _TIME_RE.search(raw):
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_hours",
                "details": (
                    f"business_hours is null but raw_description contains time pattern; "
                    f"source={row['source_name']}"
                ),
            })
    return reports


def _detect_simplified_chinese(sb) -> list[dict]:
    """Scan ALL active, annotated/reviewed events for SC chars in zh fields.

    Uses the precise SC_ONLY char set with threshold ≥2 to avoid false positives.
    Also checks selection_reason.zh (JSON-parsed).
    """
    import json as _json
    rows = (
        sb.table("events")
        .select("id,source_name,name_zh,description_zh,selection_reason")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .execute()
        .data
    )
    reports = []
    for row in rows:
        bad_fields = []
        total_sc = 0

        for field in ("name_zh", "description_zh"):
            val = row.get(field) or ""
            n = sum(1 for c in val if c in SC_ONLY)
            if n > 0:
                bad_fields.append(field)
                total_sc += n

        sr = row.get("selection_reason")
        if sr:
            try:
                sr_dict = _json.loads(sr) if isinstance(sr, str) else sr
                zh_val = sr_dict.get("zh", "")
                n = sum(1 for c in zh_val if c in SC_ONLY)
                if n > 0:
                    bad_fields.append("selection_reason.zh")
                    total_sc += n
            except (ValueError, TypeError, AttributeError):
                pass

        if total_sc >= 2:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_simplified_chinese",
                "details": (
                    f"簡體字偵測({total_sc}字) fields={','.join(bad_fields)} "
                    f"source={row.get('source_name', '?')}"
                ),
            })
    return reports


def _detect_same_work_duplicate(sb) -> list[dict]:
    """Detect active news events with same work_id + date (≤14 days) + location
    that were NOT auto-merged by merger Pass 5 (e.g. location overlap failed).
    These require human review to decide if they are truly the same screening.
    """
    _NEWS = frozenset({"google_news_rss", "prtimes", "nhk_rss", "walkerplus"})

    rows = (
        sb.table("events")
        .select("id,source_name,name_ja,start_date,location_name,work_id")
        .eq("is_active", True)
        .in_("source_name", list(_NEWS))
        .not_.is_("work_id", "null")
        .not_.is_("start_date", "null")
        .execute()
        .data
    )

    # Group by work_id
    by_work: dict = _defaultdict(list)
    for ev in rows:
        by_work[ev["work_id"]].append(ev)

    reports = []
    reported_pairs: set = set()

    for work_id_key, group in by_work.items():
        if len(group) < 2:
            continue
        for i, ev_a in enumerate(group):
            for j in range(i + 1, len(group)):
                ev_b = group[j]
                pair_key = tuple(sorted([ev_a["id"], ev_b["id"]]))
                if pair_key in reported_pairs:
                    continue

                # Date check: ≤ 14 days apart
                try:
                    diff = abs((
                        _date.fromisoformat(ev_a["start_date"][:10])
                        - _date.fromisoformat(ev_b["start_date"][:10])
                    ).days)
                except (ValueError, TypeError):
                    continue
                if diff > 14:
                    continue

                # Only report pairs that location overlap FAILED (otherwise Pass 5 would catch)
                # — i.e. different location OR null location on both
                # If location overlap passes → Pass 5 handles it automatically
                # We want to surface pairs that Pass 5 SKIPPED
                loc_a = ev_a.get("location_name") or ""
                loc_b = ev_b.get("location_name") or ""

                # Report all ≤14-day same-work pairs (Pass 5 already merged overlapping ones)
                reported_pairs.add(pair_key)
                note = (
                    f"同 work_id={work_id_key[:8]} 兩筆 news 事件日期差 {diff} 天，"
                    f"可能重複。A=[{ev_a['id'][:8]}] {(ev_a.get('name_ja') or '')[:40]} "
                    f"loc={loc_a[:20]} date={ev_a['start_date'][:10]}; "
                    f"B=[{ev_b['id'][:8]}] {(ev_b.get('name_ja') or '')[:40]} "
                    f"loc={loc_b[:20]} date={ev_b['start_date'][:10]}"
                )
                # Report on the lower-quality event (no location = lower quality)
                target_id = ev_a["id"] if not loc_a else ev_b["id"]
                reports.append({
                    "event_id": target_id,
                    "report_type": "auto_qa_same_work_duplicate",
                    "details": note,
                })
    return reports


def detect(event: dict) -> list[tuple[str, str]]:
    """Return list of (report_type, admin_note) detected for one event."""
    findings: list[tuple[str, str]] = []

    # 1. Simplified Chinese in any *_zh field
    bad_fields = [f for f in ZH_FIELDS if _has_simplified(event.get(f))]
    if bad_fields:
        sample = next((event[f] for f in bad_fields if event.get(f)), "")
        findings.append((
            "auto_qa_simplified_zh",
            f"簡體字偵測 fields={','.join(bad_fields)} sample={sample[:80]}",
        ))

    # 2. Has location_name but no location_address (skip online / TV / multi-city)
    loc_name = event.get("location_name") or ""
    loc_addr = event.get("location_address") or ""
    loc_prefs = event.get("location_prefectures") or []
    if (
        loc_name.strip()
        and not loc_addr.strip()
        and not _is_online_or_tv(loc_name)
        and event.get("source_name") != "gguide_tv"
        and loc_name.strip() not in VAGUE_CITY_NAMES
        and not any(kw in loc_name for kw in OVERSEAS_KEYWORDS)
        and len(loc_prefs) < 2  # skip multi-city events (no single venue address)
    ):
        findings.append((
            "auto_qa_missing_address",
            f"地址缺失 venue={loc_name[:80]}",
        ))

    return findings


def run(dry_run: bool = False) -> dict:
    sb = _supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=QA_WINDOW_DAYS)).isoformat()

    res = (
        sb.table("events")
        .select(
            "id, updated_at, source_name, name_zh, description_zh, "
            "location_name, location_name_zh, location_address, location_address_zh, "
            "location_prefectures"
        )
        .eq("is_active", True)
        .gte("created_at", since)
        .execute()
    )
    events = res.data or []
    logger.info("Scanning %d events (last %d days)", len(events), QA_WINDOW_DAYS)

    # Build candidate findings
    candidates: list[tuple[str, str, str]] = []  # (event_id, type, note)
    for ev in events:
        for t, note in detect(ev):
            candidates.append((ev["id"], t, note))
    for item in _detect_missing_hours(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_simplified_chinese(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_same_work_duplicate(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))

    # Dedup against latest auto_qa reports for each event/type
    latest_reports = _latest_auto_qa_reports(sb, list({c[0] for c in candidates}))
    event_updated_at = {ev["id"]: _parse_ts(ev.get("updated_at")) for ev in events}
    in_run_seen: dict[str, set[str]] = {}

    new_rows: list[dict] = []
    skipped_pending = 0
    skipped_resolved_unchanged = 0
    for event_id, t, note in candidates:
        if t in in_run_seen.get(event_id, set()):
            continue

        last = latest_reports.get(event_id, {}).get(t)
        if last:
            if last.get("status") == "pending":
                skipped_pending += 1
                continue

            handled_at = _parse_ts(last.get("confirmed_at") or last.get("created_at"))
            updated_at = event_updated_at.get(event_id)
            if handled_at and updated_at and updated_at <= handled_at:
                skipped_resolved_unchanged += 1
                continue

        new_rows.append({
            "event_id": event_id,
            "report_types": [t],
            "status": "pending",
            "admin_notes": note,
        })
        # Track in-memory so a second finding of same type/event in this run is skipped
        in_run_seen.setdefault(event_id, set()).add(t)

    counts: dict[str, int] = {t: 0 for t in QA_TYPES}
    for r in new_rows:
        counts[r["report_types"][0]] = counts.get(r["report_types"][0], 0) + 1

    summary = {
        "scanned": len(events),
        "candidates": len(candidates),
        "skipped_existing": skipped_pending,
        "skipped_resolved_unchanged": skipped_resolved_unchanged,
        "inserted": len(new_rows),
        "by_type": counts,
    }

    if dry_run:
        logger.info("DRY RUN summary: %s", summary)
        for r in new_rows[:20]:
            logger.info("  + %s %s — %s", r["event_id"][:8], r["report_types"][0], r["admin_notes"])
        return summary

    if new_rows:
        # Insert in chunks of 100 to keep payloads small
        for i in range(0, len(new_rows), 100):
            sb.table("event_reports").insert(new_rows[i : i + 100]).execute()
    logger.info("auto_qa summary: %s", summary)
    return summary


def fix_simplified(dry_run: bool = False) -> dict:
    """Auto-fix Simplified Chinese chars in all active annotated/reviewed events.

    Applies the same _SIMP_TO_TRAD conversion used by annotator.py.
    Does NOT change annotation_status — events remain annotated/reviewed.
    """
    from annotator import _to_trad, _lock_fields_via_corrections

    sb = _supabase_client()
    rows = (
        sb.table("events")
        .select("id,name_zh,description_zh,selection_reason,annotation_status")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .execute()
        .data
    )

    fixed_count = 0
    for row in rows:
        update: dict[str, Any] = {}

        for field in ("name_zh", "description_zh"):
            val = row.get(field) or ""
            if val:
                converted = _to_trad(val)
                if converted != val:
                    update[field] = converted

        # Fix selection_reason.zh
        sr = row.get("selection_reason")
        if sr:
            import json as _json
            try:
                sr_dict = _json.loads(sr) if isinstance(sr, str) else sr
                zh_val = sr_dict.get("zh", "")
                if zh_val:
                    converted_zh = _to_trad(zh_val)
                    if converted_zh != zh_val:
                        sr_dict["zh"] = converted_zh
                        update["selection_reason"] = _json.dumps(sr_dict, ensure_ascii=False)
            except (ValueError, TypeError, AttributeError):
                pass

        if update:
            if dry_run:
                logger.info("  [DRY] %s: would fix %s", row["id"][:8], list(update.keys()))
            else:
                sb.table("events").update(update).eq("id", row["id"]).execute()
                _lock_fields_via_corrections(sb, row["id"], update)
                logger.info("  ✓ fixed+locked SC chars: %s fields=%s", row["id"][:8], list(update.keys()))
            fixed_count += 1

    logger.info("fix_simplified: %s %d/%d events", "would fix" if dry_run else "fixed", fixed_count, len(rows))
    return {"scanned": len(rows), "fixed": fixed_count}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fix", action="store_true", help="Auto-fix Simplified Chinese chars instead of just reporting")
    args = parser.parse_args()
    if args.fix:
        fix_simplified(dry_run=args.dry_run)
    else:
        run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
