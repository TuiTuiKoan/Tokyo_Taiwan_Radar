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
from publication_rules import is_pure_publication_record
from sources._cinema_constants import FIXED_CINEMA_SOURCES

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

_PRICE_KW_RE = re.compile(
    r'[¥￥]\s*\d|円[（(]|参加費|入場料|チケット代|参加料|受講料|鑑賞料'
)
_BOOKING_DOMAINS = frozenset({
    "bookandbeer.com", "peatix.com", "loft-prj.co.jp", "eplus.jp",
    "ticket.pia.jp", "l-tike.com", "teket.jp", "passmarket.yahoo.co.jp",
})

JST = timezone(timedelta(hours=9))

# Pre-compiled patterns for _check_* pure predicate functions
_TIME_RE = re.compile(r'\d{1,2}[時:]\d{2}')
_SEP = re.compile(r"[、,，×／/]")

# A clock time (HH:MM) counts as a real EVENT time only when an event-time label
# sits within a small window of it AND no deadline / sales / publication / update
# label dominates that same window — this keeps missing-hours from firing on
# application deadlines, ticket-sale windows and article/publish timestamps.
_EVENT_TIME_LABEL_RE = re.compile(
    r'開場|開演|開始|開廷|上映|受付開始|集合|スタート|start\s*time|doors?\s*open'
)
_TIME_REJECT_CONTEXT_RE = re.compile(
    r'締切|締め切り|〆切|締切り|発売|販売|申込|申し込み|応募|受付終了|'
    r'掲載|公開日|更新|投稿|配信開始|予約開始|エントリー|deadline|until'
)

# Keyword signals that a named performer/creator should exist in the event.
_PERFORMER_SIGNAL_RE = re.compile(
    r'クリエイター|出展者|出展ブランド|デザイナー|登壇者?|講師|モデレーター'
    r'|アーティスト|出演者?|コラボ|参加クリエイター|ゲスト'
)
# event_form values that make performers[] meaningful.
_PERFORMER_SIGNAL_FORMS = frozenset({
    "market", "exhibition", "lecture", "conference",
    "performance", "workshop", "networking",
})

# Conservative evidence that a SPECIFIC named person appears in raw text: a
# middle-dot katakana full name, a name carrying a personal honorific/title, or
# an explicit "role: name" list entry. Generic role/group words alone
# (クリエイター / 出展ブランド / デザイナー …) are NOT sufficient.
_KATAKANA_FULLNAME_RE = re.compile(r'[ァ-ヶー]{2,}[・･][ァ-ヶー]{2,}')
_HONORIFIC_NAME_RE = re.compile(r'[一-龥ぁ-んァ-ヶーA-Za-z]{2,12}(?:氏|先生|教授|監督)')
_PERFORMER_LIST_RE = re.compile(
    r'(?:出演者?|登壇者?|講師|ゲスト|司会|モデレーター|演奏|パフォーマー|'
    r'アーティスト)\s*[:：]\s*[^\s、,，。\n]{2,}'
)

_TAIWAN_ADDR_RE = re.compile(
    r'台北|台中|台南|高雄|台湾|基隆|新竹|桃園|彰化|嘉義|花蓮|宜蘭|台東|台灣'
)
_ONLINE_ADDR_RE = re.compile(r'^オンライン$|^online$|^zoom$', re.IGNORECASE)

# Max raw_description length considered "thin content".
THIN_CONTENT_MAX_LEN = 50

PLACEHOLDER_TITLE_RE = re.compile(
    r"^(?:[\s\-—–_・・]*|(?:\(|（)(?:未命名|無題|無標題)(?:\)|）)|(?:未命名|無題|無標題))[\s\-—–_・]*$"
)

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
    "auto_qa_missing_price",
    "auto_qa_missing_performers",
    "auto_qa_thin_content",
    "auto_qa_missing_location_name",
    "auto_qa_missing_category",
    "auto_qa_missing_title",
    "auto_qa_missing_prefectures",
    "auto_qa_location_url_is_event_url",
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


def _is_blank_or_placeholder_title(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    if PLACEHOLDER_TITLE_RE.match(text):
        return True
    stripped = re.sub(r"[\s\-—–_・「」『』（）()【】\[\]…。，．、/]+", "", text)
    return not stripped


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


def _is_exact_pure_publication(ev: dict) -> bool:
    return is_pure_publication_record(ev)


def _should_skip_publication_venue_qa(ev: dict) -> bool:
    """Venue/hours/prefecture QA skips only exact pure publications."""
    return _is_exact_pure_publication(ev)


def _has_event_time_context(text: str | None) -> bool:
    """True iff the text contains a clock time (HH:MM) that is plausibly an
    EVENT start/open time. A time qualifies only when an event-time label
    (開場 / 開演 / 開始 / 上映 / …) appears within ±12 chars AND no deadline /
    sales / publication / update label appears in that same window. A time that
    only sits near a reject label (締切 / 発売 / 掲載 / 更新 / …), or carries no
    label at all, does not qualify. Pure and deterministic (no I/O)."""
    if not text:
        return False
    for m in _TIME_RE.finditer(text):
        window = text[max(0, m.start() - 12):m.end() + 12]
        if _EVENT_TIME_LABEL_RE.search(window) and not _TIME_REJECT_CONTEXT_RE.search(window):
            return True
    return False


def _has_named_person_candidate(text: str | None) -> bool:
    """Conservative evidence that a specific PERSON is named — a middle-dot
    katakana full name, a name carrying a personal honorific/title, or an
    explicit 'role: name' list entry. Generic role or group words without an
    accompanying name do NOT qualify. Pure and deterministic (no I/O)."""
    if not text:
        return False
    return bool(
        _KATAKANA_FULLNAME_RE.search(text)
        or _HONORIFIC_NAME_RE.search(text)
        or _PERFORMER_LIST_RE.search(text)
    )


def _has_thin_content_context(ev: dict) -> bool:
    """True when the event is a sub-event (has parent_event_id) that already
    carries enough of its own structured data — a start_date, a location_name,
    an organizer, or performers — that a short raw_description is expected rather
    than a quality defect (the parent series supplies the shared context). Pure."""
    if ev.get("parent_event_id") is None:
        return False
    return bool(
        ev.get("start_date")
        or ev.get("location_name")
        or ev.get("organizer")
        or ev.get("performers")
    )


def _check_missing_hours(ev: dict) -> str | None:
    """Return note if event has null business_hours but time pattern in raw_description."""
    # Only exact pure publications have no business hours requirement.
    if _should_skip_publication_venue_qa(ev):
        return None

    source_name = ev.get("source_name")
    category = ev.get("category") or ""
    if (
        source_name in FIXED_CINEMA_SOURCES
        or source_name == "gguide_tv"
        or "movie" in category
        or "tv_program" in category
    ):
        return None
    if ev.get("business_hours"):
        return None
    raw = ev.get("raw_description") or ""
    if not raw:
        return None
    if _has_event_time_context(raw):
        return (
            f"business_hours is null but raw_description contains time pattern; "
            f"source={source_name}"
        )
    return None


def _detect_missing_hours(sb) -> list[dict]:
    """Flag annotated/reviewed events with null business_hours but extractable time
    info in raw_description. Human-review only — no auto-fix."""
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,raw_description,category,business_hours,event_form")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .is_("business_hours", "null")
        .not_.is_("raw_description", "null")
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        note = _check_missing_hours(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_hours",
                "details": note,
            })
    return reports


def _check_simplified_chinese(ev: dict) -> str | None:
    """Return note if event has ≥2 SC-only chars in zh fields; None if resolved.

    Checks name_zh, description_zh, selection_reason.zh. Runs for reviewed events
    too — reconcile is the sole authority on whether the issue is resolved (the
    detection scan filters reviewed at the DB level).
    """
    import json as _json
    bad_fields = []
    total_sc = 0
    for field in ("name_zh", "description_zh"):
        val = ev.get(field) or ""
        n = sum(1 for c in val if c in SC_ONLY)
        if n > 0:
            bad_fields.append(field)
            total_sc += n
    sr = ev.get("selection_reason")
    if sr:
        try:
            sr_dict = _json.loads(sr) if isinstance(sr, str) else sr
            zh_val = (sr_dict.get("zh") or "") if isinstance(sr_dict, dict) else ""
            n = sum(1 for c in zh_val if c in SC_ONLY)
            if n > 0:
                bad_fields.append("selection_reason.zh")
                total_sc += n
        except (ValueError, TypeError, AttributeError):
            pass
    if total_sc >= 2:
        return (
            f"簡體字偵測({total_sc}字) fields={','.join(bad_fields)} "
            f"source={ev.get('source_name', '?')}"
        )
    return None


def _detect_simplified_chinese(sb) -> list[dict]:
    """Scan ALL active, annotated events for SC chars in zh fields.

    Uses the precise SC_ONLY char set with threshold ≥2 to avoid false positives.
    Also checks selection_reason.zh (JSON-parsed).

    Filters: skips human-reviewed events (annotation_status='reviewed') and only
    scans events created in the last 30 days — stops perpetual re-flagging of
    historical events that admins have already reviewed/accepted.
    """
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
        note = _check_simplified_chinese(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_simplified_chinese",
                "details": note,
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


def _check_performer_multi_value(ev: dict, *, sb=None) -> str | None:
    """Return note if performer field contains separator chars.

    Runs for reviewed events too (the detection scan filters reviewed at the DB
    level; reconcile is the sole authority on resolution).
    When sb is provided, checks field_corrections for sentinel lock (FC.performer='').
    When sb is None, skips sentinel check (caller must pre-filter sentinels).
    """
    pf = ev.get("performer") or ""
    if not pf:
        return None
    if not _SEP.search(pf):
        return None
    # Sentinel check: FC.performer='' means field is locked empty
    if sb is not None:
        ev_id = ev.get("id")
        if ev_id:
            fc_rows = (
                sb.table("field_corrections")
                .select("corrected_value")
                .eq("event_id", ev_id)
                .eq("field_name", "performer")
                .execute()
                .data or []
            )
            for fc in fc_rows:
                if fc.get("corrected_value") == "":
                    return None  # sentinel: locked empty
    return (
        f"performer 含分隔符（未拆解到 performers[]）: performer={pf!r} "
        f"source={ev.get('source_name', '?')}"
    )


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
        .select("id,source_name,performer,annotation_status")
        .eq("is_active", True)
        .neq("annotation_status", "reviewed")
        .gte("created_at", thirty_days_ago_iso)
        .contains("category", ["movie"])
        .not_.is_("performer", "null")
        .execute()
        .data
    )
    # Pre-fetch sentinel IDs: FC.performer='' means field is locked empty
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
            logger.info(
                "_detect_performer_multi_value: skip by sentinel=%d",
                skip_skipped,
            )
    reports = []
    newly_reported = 0
    for row in rows:
        if row["id"] in sentinel_ids:
            continue
        note = _check_performer_multi_value(row, sb=None)  # sentinels pre-filtered above
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_performer_multi_value_pollution",
                "details": note,
            })
            newly_reported += 1
    logger.info(
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


def _check_missing_date(ev: dict) -> str | None:
    """Return note if event has null or January-placeholder start_date."""
    start_date = ev.get("start_date")
    source_name = ev.get("source_name")
    if start_date is None:
        return f"start_date missing/placeholder (value={start_date!r}); source={source_name}"
    try:
        month = datetime.fromisoformat(start_date).month
    except (ValueError, TypeError):
        return None
    if month == 1 and source_name not in PUBLISH_DATE_SOURCES:
        return f"start_date missing/placeholder (value={start_date!r}); source={source_name}"
    return None


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
        note = _check_missing_date(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_date",
                "details": note,
            })
    return reports


def _check_missing_organizer(ev: dict) -> str | None:
    """Return note if event has null organizer (publisher is still required for pure publication records)."""
    source_name = ev.get("source_name")
    category = ev.get("category") or ""
    if (
        source_name in FIXED_CINEMA_SOURCES
        or source_name == "gguide_tv"
        or "movie" in category
        or "tv_program" in category
    ):
        return None
    if source_name in THIN_CONTENT_SOURCES:
        return None
    if ev.get("organizer"):
        return None
    return f"organizer is null; source={source_name}"


def _detect_missing_organizer(sb) -> list[dict]:
    """Flag active annotated/reviewed events with null organizer. Review-only.

    Organizer is NEVER auto-filled (Organizer Non-Hallucination Guard) — this
    detector only surfaces the gap for human review. Thin-content sources are
    skipped because they rarely expose organizer data.
    """
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,organizer,category,event_form")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .is_("organizer", "null")
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        note = _check_missing_organizer(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_organizer",
                "details": note,
            })
    return reports


def _check_missing_price(ev: dict) -> str | None:
    """Return note if price signals exist but is_paid/price_info are null."""
    from urllib.parse import urlparse

    source_name = ev.get("source_name") or ""
    if source_name in THIN_CONTENT_SOURCES:
        return None
    if source_name == "gguide_tv":
        return None
    if _is_exact_pure_publication(ev):
        return None

    raw = ev.get("raw_description") or ""
    official_url = ev.get("official_url") or ""
    price_in_desc = bool(_PRICE_KW_RE.search(raw))
    domain = urlparse(official_url).hostname or ""
    booking_url = any(domain.endswith(d) for d in _BOOKING_DOMAINS)
    if not (price_in_desc or booking_url):
        return None

    reason = "price_keyword" if price_in_desc else f"booking_domain:{domain}"
    return f"is_paid/price_info null but {reason}; source={source_name}"


def _detect_missing_price(sb) -> list[dict]:
    """Flag events where is_paid/price_info are null but price signals exist
    in raw_description or official_url. Review-only — no auto-fix."""
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,raw_description,official_url,event_form")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .is_("is_paid", "null")
        .is_("price_info", "null")
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        note = _check_missing_price(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_price",
                "details": note,
            })
    return reports


def _check_missing_performers(ev: dict) -> str | None:
    """Return note if event should have performers[] but it is null/empty."""
    source_name = ev.get("source_name") or ""
    parent_event_id = ev.get("parent_event_id")
    category = ev.get("category") or ""
    if parent_event_id is not None or "movie" in category or "tv_program" in category:
        return None
    if source_name in THIN_CONTENT_SOURCES:
        return None
    if ev.get("performers"):
        return None
    forms = ev.get("event_form") or []
    if not any(f in _PERFORMER_SIGNAL_FORMS for f in forms):
        return None
    raw = ((ev.get("raw_title") or "") + " " + (ev.get("raw_description") or ""))[:2000]
    if _PERFORMER_SIGNAL_RE.search(raw) and _has_named_person_candidate(raw):
        return (
            f"performers[] null but role signal in raw text; "
            f"event_form={forms}; source={source_name}"
        )
    return None


def _detect_missing_performers(sb) -> list[dict]:
    """Flag events where performers[] is empty but role-signal keywords appear
    in raw_title or raw_description, and event_form is a performer-relevant form.
    Review-only — no auto-fix."""
    thirty_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = (
        sb.table("events")
        .select("id,source_name,raw_title,raw_description,event_form,parent_event_id,category,performers")
        .eq("is_active", True)
        .in_("annotation_status", ["annotated", "reviewed"])
        .is_("performers", "null")
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        note = _check_missing_performers(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_missing_performers",
                "details": note,
            })
    return reports


def _check_thin_content(ev: dict) -> str | None:
    """Return note if event has thin metadata."""
    source_name = ev.get("source_name") or ""
    if source_name in THIN_CONTENT_SOURCES:
        return None
    if _has_thin_content_context(ev):
        return None
    raw = ev.get("raw_description")
    raw_len = len(raw) if raw else 0
    reasons = []
    if raw is None or raw_len < THIN_CONTENT_MAX_LEN:
        reasons.append("thin_raw")
    if (
        ev.get("start_date") is None
        and ev.get("location_name") is None
        and ev.get("organizer") is None
    ):
        reasons.append("triple_null")
    if reasons:
        return (
            f"thin content [{','.join(reasons)}]: raw_len={raw_len}; "
            f"source={source_name}; url={ev.get('source_url')}"
        )
    return None


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
            "location_name,organizer,parent_event_id,performers,created_at"
        )
        .eq("is_active", True)
        .gte("created_at", thirty_days_ago_iso)
        .execute()
        .data
    )
    reports = []
    for row in rows:
        note = _check_thin_content(row)
        if note:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_thin_content",
                "details": note,
            })
    return reports


def _detect_location_url_is_event_url(sb) -> list[dict]:
    """Detect events where location_url == source_url / official_url / organizer_url.

    This is the most common form of the location_url pollution bug: the annotator
    or admin UI sets location_url to the event page URL (organizer's site /
    Peatix / etc.) instead of the VENUE's own website.
    """
    rows = (
        sb.table("events")
        .select("id,source_name,source_url,official_url,organizer_url,location_url,location_name")
        .eq("is_active", True)
        .not_.is_("location_url", "null")
        .execute()
        .data
    )
    reports = []
    for row in rows:
        loc_url = (row.get("location_url") or "").rstrip("/")
        src_url = (row.get("source_url") or "").rstrip("/")
        off_url = (row.get("official_url") or "").rstrip("/")
        org_url = (row.get("organizer_url") or "").rstrip("/")
        if not loc_url:
            continue
        collision = None
        if src_url and loc_url == src_url:
            collision = "source_url"
        elif off_url and loc_url == off_url:
            collision = "official_url"
        elif org_url and loc_url == org_url:
            collision = "organizer_url"
        if collision:
            reports.append({
                "event_id": row["id"],
                "report_type": "auto_qa_location_url_is_event_url",
                "details": (
                    f"location_url と {collision} が同一 URL → 会場 URL ではなくイベントページ URL が誤設定されている; "
                    f"venue={row.get('location_name') or '?'}; url={loc_url[:120]}"
                ),
            })
    return reports


# Structurally venue-less sources (TV broadcast / news / blog feeds): these never
# have a physical venue, so venue-type QA (missing_address / missing_location_name
# / missing_prefectures) is always a false positive for them. Kept separate from
# the publication (is_pub_event) check to avoid conflating news/TV with books.
_NO_VENUE_QA_SOURCES = frozenset({
    "gguide_tv", "google_news_rss", "nhk_rss", "prtimes", "walkerplus", "note_creators",
})


def _should_skip_venue_qa(event: dict) -> bool:
    """Structural no-venue sources (TV/news/blog): skip venue-type QA
    (missing_address / missing_location_name / missing_prefectures)."""
    return event.get("source_name") in _NO_VENUE_QA_SOURCES


def detect(event: dict) -> list[tuple[str, str]]:
    """Return list of (report_type, admin_note) detected for one event."""
    findings: list[tuple[str, str]] = []

    # Only exact pure publications have no physical venue/address requirements.
    is_pub_event = _should_skip_publication_venue_qa(event)

    # Simplified-Chinese detection is emitted solely by the dedicated
    # _detect_simplified_chinese scanner (canonical type auto_simplified_chinese)
    # using the precise SC_ONLY set. detect() no longer emits the legacy
    # auto_qa_simplified_zh finding, so the same defect never produces two rows.

    # 2. Has location_name but no location_address (skip online / TV / multi-city / book publications)
    loc_name = event.get("location_name") or ""
    loc_addr = event.get("location_address") or ""
    loc_prefs = event.get("location_prefectures") or []
    if (
        not is_pub_event
        and not _should_skip_venue_qa(event)
        and loc_name.strip()
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

    # 3. Missing location_name (skip online/TV events, book publications, and gguide_tv source)
    if not event.get("location_name"):
        source_nm = event.get("source_name") or ""
        name_ja_val = event.get("name_ja") or ""
        if (
            not is_pub_event
            and not _should_skip_venue_qa(event)
            and source_nm != "gguide_tv"
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
    if _is_blank_or_placeholder_title(event.get("name_ja")) or _is_blank_or_placeholder_title(event.get("raw_title")):
        findings.append((
            "auto_qa_missing_title",
            f"title placeholder/missing source={event.get('source_name')} raw={str(event.get('raw_title') or '')[:40]!r}",
        ))

    # 6. Has location_address but missing location_prefectures (region filter broken)
    #    Grace period: skip events created within the last 3 days
    #    (backfill_location_prefectures.py may not have run yet).
    loc_addr_val = event.get("location_address") or ""
    loc_prefs_val = event.get("location_prefectures") or []
    if (
        not is_pub_event
        and loc_addr_val.strip()
        and not loc_prefs_val
        and not _should_skip_venue_qa(event)
    ):
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
            "location_prefectures, raw_title, event_form"
        )
        .eq("is_active", True)
        .gte("created_at", since)
        .execute()
    )
    events = res.data or []
    logger.info("Scanning %d events (last %d days)", len(events), QA_WINDOW_DAYS)

    # Fetch user-submitted events to filter them out of QA
    user_sub_res = (
        sb.table("events")
        .select("id")
        .eq("is_user_submitted", True)
        .execute()
    )
    user_submitted_ids = {row["id"] for row in user_sub_res.data or []}

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
    for item in _detect_missing_price(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_missing_performers(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_thin_content(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))
    for item in _detect_location_url_is_event_url(sb):
        candidates.append((item["event_id"], item["report_type"], item["details"]))

    # Filter out user-submitted events to bypass automated QA
    candidates = [c for c in candidates if c[0] not in user_submitted_ids]

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


def _sc_only_chars_in_event(ev: dict) -> set:
    """All SC_ONLY (unambiguously simplified-only) chars present across the
    event's zh fields and selection_reason.zh. Pure."""
    import json as _json

    found: set = set()
    for field in ("name_zh", "description_zh", "location_name_zh",
                  "location_address_zh", "business_hours_zh", "organizer_zh"):
        for ch in (ev.get(field) or ""):
            if ch in SC_ONLY:
                found.add(ch)
    sr = ev.get("selection_reason")
    if sr:
        try:
            sr_dict = _json.loads(sr) if isinstance(sr, str) else sr
            zh_val = (sr_dict.get("zh") or "") if isinstance(sr_dict, dict) else ""
            for ch in zh_val:
                if ch in SC_ONLY:
                    found.add(ch)
        except (ValueError, TypeError, AttributeError):
            pass
    return found


def _sc_unmapped_chars(ev: dict, mapping) -> set:
    """SC_ONLY chars in the event that have NO entry in the SC->TC conversion map
    (i.e. cannot be auto-repaired by _to_trad). Pure given a mapping."""
    return {ch for ch in _sc_only_chars_in_event(ev) if ch not in mapping}


def sc_row_is_auto_eligible(ev: dict, mapping=None) -> bool:
    """True iff the event contains at least one SC_ONLY char AND every SC_ONLY
    char it contains is present in the SC->TC conversion map (fully
    auto-repairable). An event carrying ANY unmapped SC_ONLY char is NOT
    auto-eligible and must be left for manual review — otherwise a
    detected-but-unfixable character loops through dismiss/recreate. Pure given a
    mapping; loads annotator's _SIMP_TO_TRAD_RAW lazily when mapping is None."""
    if mapping is None:
        from annotator import _SIMP_TO_TRAD_RAW as mapping
    chars = _sc_only_chars_in_event(ev)
    if not chars:
        return False
    return all(ch in mapping for ch in chars)


def fix_simplified(dry_run: bool = False) -> dict:
    """Auto-fix Simplified Chinese chars in all active annotated/reviewed events.

    Applies the same _SIMP_TO_TRAD conversion used by annotator.py.
    Does NOT change annotation_status — events remain annotated/reviewed.
    """
    from annotator import _to_trad, _lock_fields_via_corrections, _SIMP_TO_TRAD_RAW

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
    left_manual = 0
    for row in rows:
        # SC->TC gate: an event carrying ANY SC-only char that is not in the
        # conversion map cannot be fully auto-repaired — leave it for manual
        # review rather than partially fixing it (which would loop the unfixable
        # character through dismiss/recreate).
        unmapped = _sc_unmapped_chars(row, _SIMP_TO_TRAD_RAW)
        if unmapped:
            left_manual += 1
            logger.info(
                "  [MANUAL] %s: unmapped SC chars %s — left for manual review",
                row["id"][:8], "".join(sorted(unmapped)),
            )
            continue
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

    logger.info(
        "fix_simplified: %s %d/%d events (%d left for manual review)",
        "would fix" if dry_run else "fixed", fixed_count, len(rows), left_manual,
    )
    return {"scanned": len(rows), "fixed": fixed_count, "left_manual": left_manual}


def _check_annotation_error_stuck(ev: dict) -> str | None:
    """Resolution predicate for the annotation_error_stuck escalation inserted by
    error_recovery.py. Returns None (resolved) only when the event's annotation
    reached a verified-complete state (annotated or reviewed); otherwise a note
    that the error is still unresolved. G1 owns only this predicate — settlement
    (closing the row) is performed by error_recovery in G3."""
    status = ev.get("annotation_status")
    if status in ("annotated", "reviewed"):
        return None
    return f"annotation_status={status!r} is not annotated/reviewed; error unresolved"


def _reconcile_check(rt: str, ev: dict, *, sb=None) -> str | None:
    """Return note if problem still exists, None if resolved. No time-window.

    Dispatches by report_type to the appropriate predicate.
    Returns a non-None sentinel ('no_predicate_keep') for types without a predicate
    so the caller can distinguish 'resolved' from 'unknown'.
    """
    # detect()-derived 5 types — re-run detect() and look up the matching type
    _DETECT_TYPES = frozenset({
        "auto_qa_missing_address",
        "auto_qa_missing_location_name",
        "auto_qa_missing_category",
        "auto_qa_missing_title",
        "auto_qa_missing_prefectures",
    })
    if rt in _DETECT_TYPES:
        for det_t, det_note in detect(ev):
            if det_t == rt:
                return det_note
        return None  # resolved

    # annotation_error_stuck (inserted by error_recovery; settled in G3) resolves
    # only when the event's annotation reached a verified-complete state. This is
    # the ONLY type whose resolution rule reads annotation_status directly.
    if rt == "annotation_error_stuck":
        return _check_annotation_error_stuck(ev)

    # Simplified-Chinese: the canonical auto_simplified_chinese and the legacy
    # auto_qa_simplified_zh alias share one predicate so historical legacy rows
    # stay reconcilable without detect() ever emitting new legacy rows.
    if rt in ("auto_simplified_chinese", "auto_qa_simplified_zh"):
        return _check_simplified_chinese(ev)
    if rt == "auto_qa_missing_hours":
        return _check_missing_hours(ev)
    if rt == "auto_qa_missing_date":
        return _check_missing_date(ev)
    if rt == "auto_qa_missing_organizer":
        return _check_missing_organizer(ev)
    if rt == "auto_qa_missing_performers":
        return _check_missing_performers(ev)
    if rt == "auto_qa_thin_content":
        return _check_thin_content(ev)
    if rt == "auto_qa_performer_multi_value_pollution":
        return _check_performer_multi_value(ev, sb=sb)

    # Other auto_qa types without a predicate → safe default: keep pending
    return "no_predicate_keep"


# ---------------------------------------------------------------------------
# Event-report writer-safety — centralized eligibility (imported by consumers)
#
# Single source of truth for classifying an `event_reports.report_types[]`
# array BEFORE any automated writer (reconcile, qa_auto_fix, qa_heartbeat,
# refetch_thin_events) mutates the event or transitions the report. Rows are
# classified by token identity and membership in the known Auto-QA set — never
# by list length alone. Payload tokens (`field:` / `fieldEdit:` /
# `selectionReason:`) and any manual/unknown/human report type disqualify the
# whole row from every automatic writer.
#
# Consumer matrix (checked-in; asserted by
# tests/test_event_report_consumer_eligibility.py):
#
#   consumer             | reads                        | eligibility gate           | report write
#   -------------------- | ---------------------------- | -------------------------- | ------------------------
#   auto_qa.reconcile    | all pending reports          | all_known_auto_types       | close_report_exactly_one
#                        |                              |   (compound confirms only  |   confirmed / dismissed
#                        |                              |   if EVERY predicate       |
#                        |                              |   resolves; never partial) |
#   qa_auto_fix (daily + | pending SIMPLIFIED_REPORT_   | single_auto_type           | close_report_exactly_one
#     heartbeat handlers)|   TYPES / SAFE_REPORT_TYPES  |   (one known auto type)     |   confirmed
#   qa_heartbeat         | pending SAFE_REPORT_TYPES     | single_auto_type           | via qa_auto_fix handlers
#   refetch_thin_events  | pending auto_qa_thin_content  | report_types ==            | admin_notes note only,
#                        |                              |   ["auto_qa_thin_content"] |   pending CAS
#   error_recovery       | — (inserts escalation only)  | single-type INSERT;        | INSERT annotation_error_
#                        |                              |   settlement deferred G3   |   stuck (never closes)
# ---------------------------------------------------------------------------

KNOWN_AUTO_QA_TYPES = frozenset(QA_TYPES)

# Structured payload markers some report rows carry alongside a type. They are
# never Auto-QA types and must never make a row eligible for automatic writes.
PAYLOAD_TOKEN_PREFIXES = ("field:", "fieldEdit:", "selectionReason:")


def is_payload_token(token: str) -> bool:
    """True if `token` is a structured payload marker, not a report type."""
    return isinstance(token, str) and token.startswith(PAYLOAD_TOKEN_PREFIXES)


def is_known_auto_type(token: str) -> bool:
    """True only for an exact known Auto-QA type (payload tokens excluded)."""
    return isinstance(token, str) and token in KNOWN_AUTO_QA_TYPES


def _clean_report_types(report_types: list[str] | None) -> list[str]:
    return [t for t in (report_types or []) if isinstance(t, str) and t]


def classify_report_types(report_types: list[str] | None) -> str:
    """Classify a report_types[] array for automatic-writer eligibility.

    Returns one of:
      "empty"          — no usable tokens
      "single_auto"    — exactly one token, a known Auto-QA type
      "compound_auto"  — >=2 tokens, EVERY token a known Auto-QA type
      "manual"         — anything else (payload token, unknown/human type, or a
                         mix of auto + non-auto)

    Keys on token identity + membership, never on length alone: a two-element
    list is only "compound_auto" when both are known auto types.
    """
    types = _clean_report_types(report_types)
    if not types:
        return "empty"
    if any(not is_known_auto_type(t) for t in types):
        return "manual"
    return "single_auto" if len(types) == 1 else "compound_auto"


def single_auto_type(report_types: list[str] | None) -> str | None:
    """The lone known Auto-QA type, or None unless classify == 'single_auto'."""
    if classify_report_types(report_types) != "single_auto":
        return None
    return _clean_report_types(report_types)[0]


def all_known_auto_types(report_types: list[str] | None) -> list[str] | None:
    """Full type list when every token is a known Auto-QA type, else None.

    A single auto type or an all-auto compound both qualify. Any manual/unknown
    type or payload token anywhere in the list disqualifies the whole row — it
    must never be touched by reconcile (no report_types[0]-only checks).
    """
    if classify_report_types(report_types) in ("single_auto", "compound_auto"):
        return _clean_report_types(report_types)
    return None


def close_report_exactly_one(
    sb,
    report_id: str,
    *,
    status: str,
    note: str | None = None,
    dry_run: bool = False,
) -> tuple[bool, int]:
    """Transition exactly one PENDING report to `status` by full report_id.

    Compare-and-set on status='pending' so a concurrent admin action is never
    overwritten; this report-status write is the FINAL Supabase write a consumer
    performs (event + field_corrections writes happen first). The uuid column is
    always matched with .eq() — never .like(). Returns (ok, updated_count) where
    ok is True only when exactly one pending row transitioned.
    """
    if not report_id or not isinstance(report_id, str):
        return False, 0
    if status not in ("confirmed", "dismissed"):
        raise ValueError(f"close_report_exactly_one: invalid status {status!r}")
    if dry_run:
        return True, 1
    update: dict[str, Any] = {
        "status": status,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    if note is not None:
        update["admin_notes"] = note
    res = (
        sb.table("event_reports")
        .update(update)
        .eq("id", report_id)
        .eq("status", "pending")
        .execute()
    )
    rows = res.data or []
    ok = len(rows) == 1
    if not ok:
        logger.warning(
            "close_report_exactly_one: report %s expected 1 pending row, updated %d",
            report_id[:8], len(rows),
        )
    return ok, len(rows)


# Backward-compatible aliases (kept for existing call sites; delegate to the
# centralized classifiers above).
def _single_auto_report_type(report_types: list[str] | None) -> str | None:
    return single_auto_type(report_types)


def _all_auto_report_types(report_types: list[str] | None) -> list[str] | None:
    return all_known_auto_types(report_types)


def _resolve_report_disposition(
    ev: dict | None, types: list[str], *, sb=None
) -> tuple[str, str]:
    """Pure decision for one pending report given its (all-auto) types and event.

    Returns (disposition, reason) where disposition is one of
    "confirm", "dismiss", "keep".

    Single known-auto type (len == 1):
      - event deleted / inactive  → dismiss
      - otherwise run the predicate (INCLUDING reviewed events — there is no
        reviewed shortcut; the type-specific predicate is the sole authority)
      - predicate resolved         → confirm
      - predicate still fires       → keep

    Compound all-auto row (len >= 2): a deleted, inactive, reviewed, or missing
    event never auto-closes it. It confirms ONLY when EVERY type resolves; any
    unresolved (or unevaluatable) type keeps it pending for manual review. A
    compound row is never dismissed and never partially closed.
    """
    is_compound = len(types) >= 2
    if is_compound:
        if ev is None:
            return "keep", "compound: event missing, cannot resolve every type"
        notes = [_reconcile_check(rt, ev, sb=sb) for rt in types]
        if all(note is None for note in notes):
            return "confirm", "compound: every type resolved"
        return "keep", "compound: a type still fires"

    # Single known-auto type.
    if ev is None:
        return "dismiss", "event deleted"
    if not ev.get("is_active"):
        return "dismiss", "event inactive"
    note = _reconcile_check(types[0], ev, sb=sb)
    if note is None:
        return "confirm", "issue resolved"
    return "keep", "predicate still fires"


def reconcile(dry_run: bool = False) -> dict:
    """Close resolved or inactive auto_qa pending reports.

    For each pending auto_qa report (single or all-auto compound):
    - single type, event deleted / inactive → dismiss
    - single type, predicate resolved        → confirm (reviewed events run the
      predicate too; there is no reviewed shortcut)
    - single type, predicate still fires      → keep pending
    - compound row → confirm ONLY when EVERY type resolves; a deleted, inactive,
      reviewed, or missing event keeps it pending (never dismissed, never
      partially closed)
    - any manual/unknown/payload token present → skip entirely, never touched

    Manual report types (wrongCategory, irrelevant, etc.) are never touched.
    Every status transition goes through close_report_exactly_one (full
    report_id + pending CAS + exactly-one-row verification).
    """
    sb = _supabase_client()
    today = datetime.now(timezone.utc).astimezone(JST).strftime("%Y-%m-%d")
    AUTO_TYPES = frozenset(QA_TYPES)

    # 1. Paginate all pending reports
    rows: list[dict] = []
    off = 0
    while True:
        batch = (
            sb.table("event_reports")
            .select("id,event_id,report_types,admin_notes,status")
            .eq("status", "pending")
            .range(off, off + 999)
            .execute()
            .data or []
        )
        rows.extend(batch)
        if len(batch) < 1000:
            break
        off += 1000

    # 2. Separate auto (single or all-auto compound) vs manual/unknown reports
    auto_rows: list[tuple[dict, list[str]]] = []
    skipped_manual = 0
    skipped_mixed_or_unknown = 0
    for r in rows:
        types = _all_auto_report_types(r.get("report_types"))
        if types is None:
            raw_types = [t for t in (r.get("report_types") or []) if isinstance(t, str) and t]
            if len(raw_types) >= 1 and any(t not in AUTO_TYPES for t in raw_types):
                skipped_manual += 1
            else:
                skipped_mixed_or_unknown += 1
            continue
        auto_rows.append((r, types))
        # Manual/unknown rows are never touched.

    # 3. Load corresponding events (full fields for all check functions)
    eids = list({r["event_id"] for r, _types in auto_rows})
    ev_map: dict[str, dict] = {}
    for i in range(0, len(eids), 200):
        chunk = eids[i : i + 200]
        data = (
            sb.table("events")
            .select(
                "id,is_active,annotation_status,source_name,name_ja,raw_title,"
                "location_name,location_address,location_prefectures,"
                "category,start_date,organizer,business_hours,"
                "performers,performer,parent_event_id,description_zh,"
                "name_zh,location_name_zh,location_address_zh,business_hours_zh,"
                "organizer_zh,selection_reason,event_form,raw_description,source_url,created_at"
            )
            .in_("id", chunk)
            .execute()
            .data or []
        )
        for e in data:
            ev_map[e["id"]] = e

    # 4. Classify each auto report
    confirmed_ids: list[tuple[str, str, str]] = []  # (id, orig_note, reason)
    dismissed_ids: list[tuple[str, str, str]] = []
    by_reason: dict[str, int] = {
        "event_missing": 0, "inactive": 0, "reviewed": 0, "resolved": 0, "kept": 0
    }
    by_type: dict[str, dict[str, int]] = {}

    for r, types in auto_rows:
        rid = r["id"]
        eid = r["event_id"]
        orig_note = r.get("admin_notes") or ""
        ev = ev_map.get(eid)

        def _inc_all(bucket: str) -> None:
            for rt in types:
                by_type.setdefault(rt, {"confirmed": 0, "dismissed": 0, "kept": 0})[bucket] += 1

        disposition, reason = _resolve_report_disposition(ev, types, sb=sb)
        if disposition == "dismiss":
            dismissed_ids.append((rid, orig_note, reason))
            by_reason["event_missing" if reason == "event deleted" else "inactive"] += 1
            _inc_all("dismissed")
        elif disposition == "confirm":
            confirmed_ids.append((rid, orig_note, reason))
            by_reason["reviewed" if reason == "event reviewed by admin" else "resolved"] += 1
            _inc_all("confirmed")
        else:
            by_reason["kept"] += 1
            _inc_all("kept")

    # 5. Apply batch updates
    prefix = f"reconcile {today}: "

    if not dry_run:
        for rid, orig_note, reason in confirmed_ids:
            new_note = prefix + reason + (f" | {orig_note}" if orig_note else "")
            close_report_exactly_one(sb, rid, status="confirmed", note=new_note, dry_run=False)
        for rid, orig_note, reason in dismissed_ids:
            new_note = prefix + reason + (f" | {orig_note}" if orig_note else "")
            close_report_exactly_one(sb, rid, status="dismissed", note=new_note, dry_run=False)

    summary = {
        "scanned_pending": len(auto_rows),
        "confirmed": len(confirmed_ids),
        "dismissed": len(dismissed_ids),
        "kept_pending": by_reason["kept"],
        "skipped_manual": skipped_manual,
        "skipped_mixed_or_unknown": skipped_mixed_or_unknown,
        "by_reason": by_reason,
        "by_type": by_type,
    }
    logger.info("reconcile summary: %s", summary)
    if dry_run:
        import json as _json
        print("\n--- RECONCILE DRY-RUN ---")
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
        print("--- end ---\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fix", action="store_true", help="Auto-fix Simplified Chinese chars instead of just reporting")
    parser.add_argument("--reconcile", action="store_true", help="Close resolved/inactive pending auto_qa reports")
    args = parser.parse_args()
    if args.reconcile:
        reconcile(dry_run=args.dry_run)
        return
    if args.fix:
        fix_simplified(dry_run=args.dry_run)
    else:
        run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
