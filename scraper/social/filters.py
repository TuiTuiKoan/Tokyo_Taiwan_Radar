"""Rule-based pre-filter for social posts (no LLM cost).

This is a cost filter, not the publication gate: it only decides whether a
post is worth sending down the pipeline. Dates and venues are extracted by the
annotator, and whether an event goes live is decided after annotation (spec
social-sources D5).

Known misses, accepted for the trial: "12月5日〜7日" yields only the first
date, and a bare "12/5" with no weekday marker is ignored.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# Reasons a post is dropped or held back (keys of RunReport.dropped).
DROP_EMPTY = "empty"
DROP_REPOST = "repost"
DROP_INJECTION = "injection_suspected"
DROP_PAST = "past_event"
DROP_RECAP = "recap"
DROP_NO_SIGNAL = "no_event_signal"
INSUFFICIENT_NO_DATE = "no_future_date"
INSUFFICIENT_NO_PLACE = "no_place"
INSUFFICIENT_OVER_CAP = "over_account_cap"

VERDICT_KEEP = "keep"
VERDICT_DROP = "drop"

JST = timezone(timedelta(hours=9))

# A date this many days before "today" still counts as current (events that
# started yesterday and run for a while).
PAST_GRACE_DAYS = 1
# A date without a year is read as the occurrence nearest to the publish date,
# within this window. 180 days back matches the repo's prose-date rule
# (scraper.instructions.md), so "12月20日に開催しました" posted in January
# resolves to last December, not next.
YEARLESS_BACK_DAYS = 180
YEARLESS_AHEAD_DAYS = 185

_WEEKDAY_CHARS = "月火水木金土日一二三四五六"
_WEEKDAY_INDEX = {"月": 0, "一": 0, "火": 1, "二": 1, "水": 2, "三": 2, "木": 3, "四": 3,
                  "金": 4, "五": 4, "土": 5, "六": 5, "日": 6}
_WEEKDAY_TAIL = r"(?:\s*[（(]\s*([" + _WEEKDAY_CHARS + r"])[^）)]{0,6}[）)])?"

_FULL_DATE = re.compile(r"(?<!\d)(20\d{2})\s*[年/.\-]\s*(\d{1,2})\s*[月/.\-]\s*(\d{1,2})(?:\s*日)?(?!\d)")
_MONTH_DAY_KANJI = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日" + _WEEKDAY_TAIL)
# M/D only when followed by a weekday marker, so "1/2 size" or "3/4" are ignored.
_MONTH_DAY_SLASH = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})\s*[（(]\s*([" + _WEEKDAY_CHARS + r"])[^）)]{0,6}[）)]")

# A date right next to one of these is a deadline or on-sale date, not the event.
_NON_EVENT_BEFORE = re.compile(r"(?:締切|〆切|締め切り|発売|受付開始|予約開始|申込開始|販売開始|截止|開賣)\s*[:：は]?\s*$")
_NON_EVENT_AFTER = re.compile(
    r"^(?:\s*[（(][^）)]{0,8}[）)])?\s*(?:\d{1,2}[:：時]\d{0,2}分?\s*)?"
    r"(?:まで|〆切|締切|締め切り|発売|より(?:予約|受付|販売|申込)|から(?:予約|受付|販売|申込)|截止|開賣)"
)

_EVENT_SIGNAL = re.compile(
    r"開催|イベント|参加|申込|申し込み|予約|上映|講演|講座|展示|展覧|個展|祭|フェス|ライブ|公演|"
    r"ワークショップ|トーク|交流会|読書会|マルシェ|市集|活動|報名|座談|分享會|展覽|放映|演出|"
    r"入場|チケット|定員|会場|\bevent\b|\bticket|\bworkshop\b|\bscreening\b|\bregister\b|\brsvp\b",
    re.IGNORECASE,
)
_RECAP_SIGNAL = re.compile(
    r"レポート|レポ[^ー]|ご報告|開催しました|終了しました|ありがとうございました|無事に?終|"
    r"圓滿落幕|圆满落幕|活動回顧|活動紀錄|感謝.{0,6}參與|\brecap\b|thank you for (?:coming|joining)",
    re.IGNORECASE,
)
_PREFECTURES = (
    "北海道|青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|東京|神奈川|新潟|富山|石川|福井|"
    "山梨|長野|岐阜|静岡|愛知|三重|滋賀|京都|大阪|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|"
    "香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄|横浜|名古屋|神戸|札幌|仙台|那覇"
)
# A place name counts only with address-like context, so an organisation name
# such as 「東京台湾の会」 or an @mention is not read as a venue.
_PLACE_SIGNAL = re.compile(
    r"会場|場所|開催地|地點|地点|地址|住所|〒\s*\d{3}|オンライン|線上|线上|\bonline\b|\bzoom\b|"
    r"(?:" + _PREFECTURES + r")(?:都|道|府|県)?[^\s、。]{0,6}(?:市|区|町|村|駅|ホール|会館|センター)|"
    r"(?:^|\n)\s*[＠@]\s*[^\sA-Za-z0-9_@＠][^\s]+|"
    r"(?:\bin|＠|@)\s*(?:" + _PREFECTURES + r")",
    re.IGNORECASE,
)


def to_jst_date(moment: datetime) -> date:
    """Calendar date in Japan for an aware (or naive-UTC) datetime."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(JST).date()


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve_yearless(month: int, day: int, posted: date, weekday: Optional[int]) -> Optional[date]:
    """Occurrence of month/day nearest to ``posted``; a weekday marker wins."""
    candidates = [d for d in (_safe_date(posted.year + off, month, day) for off in (-1, 0, 1)) if d]
    if not candidates:
        return None
    in_window = [
        d for d in candidates
        if -YEARLESS_BACK_DAYS <= (d - posted).days <= YEARLESS_AHEAD_DAYS
    ]
    if weekday is not None:
        # A written weekday is stronger evidence than nearness, so it may pick
        # a year outside the window.
        matching = [d for d in candidates if d.weekday() == weekday]
        if matching:
            return min(matching, key=lambda d: abs((d - posted).days))
    pool = in_window or candidates
    return min(pool, key=lambda d: abs((d - posted).days))


def _is_non_event_date(text: str, start: int, end: int) -> bool:
    return bool(_NON_EVENT_BEFORE.search(text[max(0, start - 10):start]) or _NON_EVENT_AFTER.match(text[end:end + 24]))


def find_dates(text: str, posted_at: datetime) -> list[date]:
    """Event-date candidates in ``text``, in order of appearance.

    Dates written without a year are resolved against the post's publish date
    (Japan time). Deadlines and on-sale dates are left out.
    """
    if not text:
        return []
    posted = to_jst_date(posted_at)
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []

    def overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < end and start < span[1] for start, end in taken)

    for m in _FULL_DATE.finditer(text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            taken.append(m.span())
            if not _is_non_event_date(text, m.start(), m.end()):
                found.append((m.start(), d))

    for pattern in (_MONTH_DAY_KANJI, _MONTH_DAY_SLASH):
        for m in pattern.finditer(text):
            if overlaps(m.span()):
                continue
            month, day = int(m.group(1)), int(m.group(2))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            weekday = _WEEKDAY_INDEX.get(m.group(3)) if m.group(3) else None
            d = _resolve_yearless(month, day, posted, weekday)
            if d:
                taken.append(m.span())
                if not _is_non_event_date(text, m.start(), m.end()):
                    found.append((m.start(), d))

    found.sort(key=lambda item: item[0])
    result: list[date] = []
    for _, d in found:
        if d not in result:
            result.append(d)
    return result


def has_future_date(dates: list[date], today: date) -> bool:
    cutoff = today - timedelta(days=PAST_GRACE_DAYS)
    return any(d >= cutoff for d in dates)


def has_place_signal(text: str) -> bool:
    return bool(_PLACE_SIGNAL.search(text or ""))


def has_event_signal(text: str) -> bool:
    return bool(_EVENT_SIGNAL.search(text or ""))


def has_recap_signal(text: str) -> bool:
    return bool(_RECAP_SIGNAL.search(text or ""))


def classify_post(text: str, posted_at: datetime, today: date, *, is_repost: bool = False) -> tuple[str, str]:
    """Return ``(verdict, reason)`` for a post's own text.

    VERDICT_KEEP means "worth enriching and checking for completeness";
    reason is "" unless the verdict is VERDICT_DROP.
    """
    body = (text or "").strip()
    if not body:
        return VERDICT_DROP, DROP_EMPTY
    if is_repost:
        return VERDICT_DROP, DROP_REPOST
    dates = find_dates(body, posted_at)
    future = has_future_date(dates, today)
    if dates and not future:
        return VERDICT_DROP, DROP_PAST
    if not future and has_recap_signal(body):
        return VERDICT_DROP, DROP_RECAP
    if not future and not has_event_signal(body):
        return VERDICT_DROP, DROP_NO_SIGNAL
    return VERDICT_KEEP, ""


def completeness_gap(text: str, posted_at: datetime, today: date) -> str:
    """"" when ``text`` has a future date and a place signal, else the gap."""
    if not has_future_date(find_dates(text or "", posted_at), today):
        return INSUFFICIENT_NO_DATE
    if not has_place_signal(text or ""):
        return INSUFFICIENT_NO_PLACE
    return ""
