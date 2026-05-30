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

# Sources whose start_date legitimately reflects publish date (often January
# placeholder) — skip January placeholder guard in missing_date detection.
PUBLISH_DATE_SOURCES = frozenset({"note_creators", "google_news_rss", "prtimes", "nhk_rss", "walkerplus"})

# Sources that legitimately produce thin metadata (news/article feeds) — skip
# missing_organizer detection (organizer is rarely available for these).
THIN_CONTENT_SOURCES = frozenset({"note_creators", "google_news_rss", "prtimes", "nhk_rss", "walkerplus"})

# Rule 6: addresses that do NOT require location_prefectures.
_TAIWAN_ADDR_RE = re.compile(
    r'台北|台中|台南|高雄|台湾|基隆|新竹|桃園|彰化|嘉義|花蓮|宜蘭|台東|台灣'
)
_ONLINE_ADDR_RE = re.compile(r'^オンライン$|^online$|^zoom$', re.IGNORECASE)

# Max raw_description length considered "thin content".
THIN_CONTENT_MAX_LEN = 50

QA_TYPES = (
    "auto_qa_simplified_zh",
    "auto_qa_missing_address",
    "auto_qa_missing_hours",
    "auto_simplified_chinese",
    "auto_qa_same_work_duplicate",
    "auto_qa_performer_ai_translation_marker",
    "auto_qa_performer_multi_value_pollution",
    "auto_qa_performer_zh_equals_katakana",
    "auto_qa_missing_date",
    "auto_qa_missing_organizer",
    "auto_qa_thin_content",
    "auto_qa_missing_location_name",
    "auto_qa_missing_category",
    "auto_qa_missing_title",
    "auto_qa_missing_prefectures",
)

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
    "苏范荡荣虑蜡"
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
    "归当录"
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
    "踪"
    "辅辆辩"
    "迁递逻遗"
    "邮邻郑"
    "酱酿释"
    "钟钢钱铁铜铝银锁锋错镇镜长"
    "闭闲阅闸门"
    "险雾"
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

    Filters: skips human-reviewed events (annotation_status='reviewed') and only
    scans events created in the last 30 days — stops perpetual re-flagging of
    historical events that admins have already reviewed/accepted.
    """
    import json as _json
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,name_zh,description_zh,selection_reason,annotation_status,created_at")
        .eq("is_active", True)
        .eq("annotation_status", "annotated")
        .gte("created_at", thirty_days_ago_iso)
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


def _detect_performer_ai_marker(sb) -> list[dict]:
    """Flag movie events where performer_zh or performer_en still contains
    AI翻譯 / AI Translation marker — indicating lookup pipeline did not fix them.

    Filters: skips human-reviewed events and only scans events created in the
    last 30 days to prevent perpetual re-flagging.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,performer,performer_zh,performer_en")
        .eq("is_active", True)
        .neq("annotation_status", "reviewed")
        .gte("created_at", thirty_days_ago_iso)
        .contains("category", ["movie"])
        .or_("performer_zh.like.%AI翻譯%,performer_en.like.%AI Translation%")
        .execute()
        .data
    )
    reports = []
    for row in rows:
        bad = []
        if "AI翻譯" in (row.get("performer_zh") or ""):
            bad.append(f"performer_zh={row['performer_zh']!r}")
        if "AI Translation" in (row.get("performer_en") or ""):
            bad.append(f"performer_en={row['performer_en']!r}")
        if bad:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_performer_ai_translation_marker",
                "details": (
                    f"performer AI翻譯 marker 未清除: {'; '.join(bad)} "
                    f"source={row.get('source_name', '?')}"
                ),
            })
    return reports


def _detect_performer_multi_value(sb) -> list[dict]:
    """Flag movie events where performer field still contains separator chars
    — indicates the field was not split to performers[] array.

    Filters: skips human-reviewed events and only scans events created in the
    last 30 days to prevent perpetual re-flagging.
    Sentinel skip: skips events where FC.performer='' (lock-empty) and
    events.performer IS NULL — field already cleaned and locked.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,performer")
        .eq("is_active", True)
        .neq("annotation_status", "reviewed")
        .gte("created_at", thirty_days_ago_iso)
        .contains("category", ["movie"])
        .not_.is_("performer", "null")
        .execute()
        .data
    )
    reports = []
    import re as _re
    _SEP = _re.compile(r"[、,，×／/]")

    # Build sentinel set: event_ids where FC.performer='' sentinel is in place
    candidate_ids = [row["id"] for row in rows]
    sentinel_ids: set[str] = set()
    if candidate_ids:
        skip_skipped = 0
        for i in range(0, len(candidate_ids), 200):
            chunk = candidate_ids[i : i + 200]
            fc_rows = (
                sb.table("field_corrections")
                .select("event_id,corrected_value")
                .in_("event_id", chunk)
                .eq("field_name", "performer")
                .execute()
                .data or []
            )
            for fc in fc_rows:
                if fc.get("corrected_value") == "":
                    sentinel_ids.add(fc["event_id"])
                    skip_skipped += 1
        if skip_skipped:
            import logging as _logging
            _logging.getLogger(__name__).info(
                "_detect_performer_multi_value: skip by sentinel=%d, skip by archived=0 (pre-filtered by is_active)",
                skip_skipped,
            )

    newly_reported = 0
    for row in rows:
        if row["id"] in sentinel_ids:
            continue
        pf = row.get("performer") or ""
        if _SEP.search(pf):
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_performer_multi_value_pollution",
                "details": (
                    f"performer 含分隔符（未拆解到 performers[]）: performer={pf!r} "
                    f"source={row.get('source_name', '?')}"
                ),
            })
            newly_reported += 1

    import logging as _logging
    _logging.getLogger(__name__).info(
        "_detect_performer_multi_value: newly reported=%d, skip by sentinel=%d",
        newly_reported, len(sentinel_ids),
    )
    return reports


def _detect_performer_zh_katakana(sb) -> list[dict]:
    """Flag events where performer_zh equals performer (katakana unchanged)
    and performer contains ・ — indicates name lookup silently failed."""
    rows = (
        sb.table("events")
        .select("id,source_name,performer,performer_zh")
        .eq("is_active", True)
        .not_.is_("performer", "null")
        .not_.is_("performer_zh", "null")
        .execute()
        .data
    )
    reports = []
    for row in rows:
        pf = row.get("performer") or ""
        pf_zh = row.get("performer_zh") or ""
        # performer_zh equals performer AND performer contains ・ (katakana foreign name)
        if pf and pf_zh == pf and "\u30fb" in pf:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_performer_zh_equals_katakana",
                "details": (
                    f"performer_zh = performer (lookup 失敗): performer={pf!r} "
                    f"source={row.get('source_name', '?')}"
                ),
            })
    return reports


def _detect_missing_date(sb) -> list[dict]:
    """Flag active annotated/reviewed events with missing or placeholder
    start_date. Review-only — no auto-fix.

    A start_date in January is treated as a Contentful placeholder and flagged,
    EXCEPT for publish-date sources whose January dates may be legitimate.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,start_date,annotation_status")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        start_date = row.get("start_date")
        source_name = row.get("source_name")
        if start_date is None:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_date",
                "details": f"start_date missing/placeholder (value={start_date!r}); source={source_name}",
            })
            continue
        try:
            month = datetime.fromisoformat(start_date).month
        except (ValueError, TypeError):
            continue
        if month == 1 and source_name not in PUBLISH_DATE_SOURCES:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_date",
                "details": f"start_date missing/placeholder (value={start_date!r}); source={source_name}",
            })
    return reports


def _detect_missing_organizer(sb) -> list[dict]:
    """Flag active annotated/reviewed events with null organizer. Review-only.

    Organizer is NEVER auto-filled (Organizer Non-Hallucination Guard) — this
    detector only surfaces the gap for human review. Thin-content sources are
    skipped because they rarely expose organizer data.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,organizer")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .is_("organizer", "null")
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        source_name = row.get("source_name")
        if source_name in THIN_CONTENT_SOURCES:
            continue
        reports.append({
            "event_id": row["id"],
            "report_type": "auto_qa_missing_organizer",
            "details": f"organizer is null; source={source_name}",
        })
    return reports


def _detect_thin_content(sb) -> list[dict]:
    """Flag recent active events with thin metadata. Review-only.

    Hits when raw_description is short/missing, or when start_date, location_name
    and organizer are all null.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select(
            "id,source_name,source_url,raw_description,start_date,"
            "location_name,organizer,created_at"
        )
        .eq("is_active", True)
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        raw = row.get("raw_description")
        raw_len = len(raw) if raw else 0
        reasons = []
        if raw is None or raw_len < THIN_CONTENT_MAX_LEN:
            reasons.append("thin_raw")
        if (
            row.get("start_date") is None
            and row.get("location_name") is None
            and row.get("organizer") is None
        ):
            reasons.append("triple_null")
        if reasons:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_thin_content",
                "details": (
                    f"thin content [{','.join(reasons)}]: raw_len={raw_len}; "
                    f"source={row.get('source_name')}; url={row.get('source_url')}"
                ),
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

    # 3. Missing location_name (skip online/TV events and gguide_tv source)
    if not event.get("location_name"):
        source_nm = event.get("source_name") or ""
        name_ja_val = event.get("name_ja") or ""
        if (
            source_nm != "gguide_tv"
            and not any(kw in name_ja_val for kw in ADDRESS_SKIP_KEYWORDS)
        ):
            findings.append((
                "auto_qa_missing_location_name",
                f"会場名欠落 source={source_nm}",
            ))

    # 4. Missing category (category is array; report if None or empty list)
    cat = event.get("category")
    if cat is None or cat == []:
        findings.append((
            "auto_qa_missing_category",
            "カテゴリ未設定",
        ))

    # 5. Missing title (name_ja is NULL — rare but fatal)
    if not event.get("name_ja"):
        findings.append((
            "auto_qa_missing_title",
            f"name_ja 欠落 source={event.get('source_name')}",
        ))

    # 6. Has location_address but missing location_prefectures (region filter broken)
    #    Grace period: skip events created within the last 3 days
    #    (backfill_location_prefectures.py may not have run yet).
    loc_addr_val = event.get("location_address") or ""
    loc_prefs_val = event.get("location_prefectures") or []
    if loc_addr_val.strip() and not loc_prefs_val:
        # Skip non-Japan addresses — Taiwan events have no prefecture
        if _TAIWAN_ADDR_RE.search(loc_addr_val):
            pass
        # Skip 'オンライン' — Online Guard violation handled separately
        elif _ONLINE_ADDR_RE.match(loc_addr_val.strip()):
            pass
        else:
            created_at_str = event.get("created_at")
            skip_grace = False
            if created_at_str:
                created_dt = _parse_ts(created_at_str)
                if created_dt and (datetime.now(timezone.utc) - created_dt).days <= 3:
                    skip_grace = True
            if not skip_grace:
                findings.append((
                    "auto_qa_missing_prefectures",
                    f"location_prefectures 欠落（区域フィルタ無効）addr={loc_addr_val[:80]}",
                ))

    return findings


def run(dry_run: bool = False) -> dict:
    sb = _supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=QA_WINDOW_DAYS)).isoformat()

    res = (
        sb.table("events")
        .select(
            "id, updated_at, created_at, source_name, name_ja, name_zh, description_zh, "
            "category, location_name, location_name_zh, location_address, location_address_zh, "
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
    for item in _detect_performer_ai_marker(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_performer_multi_value(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_performer_zh_katakana(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_missing_date(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_missing_organizer(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_thin_content(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))

    # Dedup against latest auto_qa reports for each event/type.
    #
    # Global detectors above (`_detect_simplified_chinese`,
    # `_detect_performer_*`, `_detect_same_work_duplicate`,
    # `_detect_missing_hours`) may emit candidates for events OUTSIDE the
    # 14-day initial scan. We must fetch `updated_at` for ALL candidate
    # event ids so `skipped_resolved_unchanged` works for old events too.
    candidate_ids = sorted({c[0] for c in candidates})
    latest_reports = _latest_auto_qa_reports(sb, candidate_ids)
    event_updated_at: dict[str, datetime | None] = {
        ev["id"]: _parse_ts(ev.get("updated_at")) for ev in events
    }
    missing_ids = [eid for eid in candidate_ids if eid not in event_updated_at]
    if missing_ids:
        for i in range(0, len(missing_ids), 200):
            chunk = missing_ids[i : i + 200]
            res = (
                sb.table("events")
                .select("id,updated_at")
                .in_("id", chunk)
                .execute()
            )
            for row in res.data or []:
                event_updated_at[row["id"]] = _parse_ts(row.get("updated_at"))
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
    _FIX_FIELDS = (
        "name_zh", "description_zh",
        "location_name_zh", "location_address_zh",
        "business_hours_zh", "organizer_zh",
    )
    rows = (
        sb.table("events")
        .select("id," + ",".join(_FIX_FIELDS) + ",selection_reason,annotation_status")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .execute()
        .data
    )

    fixed_count = 0
    for row in rows:
        update: dict[str, Any] = {}

        for field in _FIX_FIELDS:
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
