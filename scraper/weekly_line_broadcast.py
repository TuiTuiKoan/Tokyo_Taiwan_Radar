"""
Weekly LINE broadcast — sends curated Taiwan event recommendations
to all active LINE subscribers, grouped by language preference.

Usage:
    python weekly_line_broadcast.py [--dry-run]
    python weekly_line_broadcast.py [--admin-only]
    python weekly_line_broadcast.py [--generate-draft]
    python weekly_line_broadcast.py [--auto-send]

Flags:
    --dry-run         Print messages to stdout, do NOT send anything.
    --admin-only      Send ONLY to admin user(s) defined in ADMIN_LINE_USER_IDS
                      (comma-separated LINE user IDs in scraper/.env). Useful
                      for testing the real send pipeline without spamming
                      subscribers. Sends ZH version only; token still required.
    --generate-draft  Generate this week's broadcast content and save it as a
                      draft announcement in the DB (announcements.type='weekly_broadcast').
                      Does NOT send anything. Run on Thursday in CI.
    --auto-send       Check app_settings.weekly_broadcast.auto_publish. If true,
                      find the latest pending weekly_broadcast draft and send it.
                      Run on Friday noon JST in CI.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
LINE_MULTICAST_URL = "https://api.line.me/v2/bot/message/multicast"

# ---------------------------------------------------------------------------
# Category labels per language
# ---------------------------------------------------------------------------
CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "zh": {
        "movie": "電影", "performing_arts": "音樂・表演", "senses": "台灣五感",
        "retail": "品牌消費", "lifestyle_food": "生活風格", "art": "藝術",
        "lecture": "講座", "taiwan_japan": "台日交流", "books_media": "書・媒體",
        "academic": "學術", "geopolitics": "社會・政治", "gender": "性別",
        "tech": "科技", "nature": "自然", "tourism": "旅遊",
        "workshop": "工作坊", "exhibition": "展覽", "competition": "競賽",
        "indigenous": "原住民", "history": "歷史", "urban": "建築",
        "business": "商務", "report": "活動紀錄", "literature": "文學",
        "tv_program": "電視節目",
    },
    "ja": {
        "movie": "映画", "performing_arts": "音楽・舞台", "senses": "台湾五感",
        "retail": "ブランド・ショッピング", "lifestyle_food": "ライフスタイル・食",
        "art": "アート", "lecture": "講演", "taiwan_japan": "台日交流",
        "books_media": "本・メディア", "academic": "学術", "geopolitics": "社会・政治",
        "gender": "ジェンダー", "tech": "テクノロジー", "nature": "自然",
        "tourism": "観光", "workshop": "ワークショップ", "exhibition": "展示",
        "competition": "競技", "indigenous": "先住民族", "history": "歴史",
        "urban": "建築・都市", "business": "ビジネス", "report": "レポート",
        "literature": "文学", "tv_program": "テレビ番組",
    },
    "en": {
        "movie": "Movie", "performing_arts": "Music & Performing Arts",
        "senses": "Taiwan Senses", "retail": "Shopping", "lifestyle_food": "Lifestyle & Food",
        "art": "Art", "lecture": "Lecture", "taiwan_japan": "Taiwan-Japan Exchange",
        "books_media": "Books & Media", "academic": "Academic", "geopolitics": "Society & Politics",
        "gender": "Gender", "tech": "Tech", "nature": "Nature", "tourism": "Tourism",
        "workshop": "Workshop", "exhibition": "Exhibition", "competition": "Competition",
        "indigenous": "Indigenous", "history": "History", "urban": "Architecture & Urban",
        "business": "Business", "report": "Event Report", "literature": "Literature",
        "tv_program": "TV Program",
    },
}

CATEGORY_LIST_FOOTER: dict[str, str] = {
    "zh": """━━━━━━━━━━━━━━━━━━
📂 活動分類
1.電影  2.音樂・表演  3.台灣五感  4.品牌消費
5.生活風格  6.藝術  7.講座  8.台日交流
9.書・媒體  10.學術  11.社會・政治  12.性別
13.科技  14.自然  15.旅遊  16.工作坊
17.展覽  18.競賽  19.原住民  20.歷史
21.建築  22.商務  23.活動紀錄  24.文學

💡 輸入編號或分類名稱可客製化推播
切換語言：輸入「日本語」或「English」""",
    "ja": """━━━━━━━━━━━━━━━━━━
📂 イベントカテゴリ
1.映画  2.音楽・舞台  3.台湾五感  4.ショッピング
5.ライフスタイル  6.アート  7.講演  8.台日交流
9.本・メディア  10.学術  11.社会・政治  12.ジェンダー
13.テクノロジー  14.自然  15.観光  16.ワークショップ
17.展示  18.競技  19.先住民族  20.歴史
21.建築  22.ビジネス  23.レポート  24.文学

💡 番号またはカテゴリ名を入力でカスタマイズ配信
言語切替：「中文」または「English」と入力""",
    "en": """━━━━━━━━━━━━━━━━━━
📂 Event Categories
1.Movie  2.Music & Performing Arts  3.Taiwan Senses
4.Shopping  5.Lifestyle & Food  6.Art  7.Lecture
8.Taiwan-Japan Exchange  9.Books & Media  10.Academic
11.Society & Politics  12.Gender  13.Tech  14.Nature
15.Tourism  16.Workshop  17.Exhibition  18.Competition
19.Indigenous  20.History  21.Architecture  22.Business
23.Event Report  24.Literature

💡 Type a number or category name to customize your feed
Switch language: type「中文」or「日本語」""",
}


def _get_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _get_openai():
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _month_end_of(year: int, month: int) -> datetime:
    """Return the last moment of the given calendar month (JST)."""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59, tzinfo=JST)


def _next_two_months_end(ref: datetime) -> datetime:
    """Return the last moment of the calendar month after next (rel. to ref)."""
    # month+2, wrapping year
    m = ref.month + 2
    y = ref.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return _month_end_of(y, m)


def _fetch_upcoming_events(sb) -> list[dict]:
    """Fetch active, annotated events starting from now through end of month-after-next.

    Pool covers:
    - Weekly section: today → today+21 days
    - Monthly section: 1st of next month → last day of month-after-next

    Only `annotated` and `reviewed` events are included — `pending` events
    may have NULL name_zh/name_en (annotator not yet run) and would cause
    ZH/EN subscribers to receive the Japanese fallback title.
    """
    now = datetime.now(JST)
    start_from = now.isoformat()
    start_to = _next_two_months_end(now).isoformat()
    res = (
        sb.table("events")
        .select(
            "id,name_zh,name_ja,name_en,start_date,end_date,category,location_name,location_address"
        )
        .eq("is_active", True)
        .is_("parent_event_id", "null")
        .neq("source_name", "gguide_tv")
        .in_("annotation_status", ["annotated", "reviewed"])
        .gte("start_date", start_from)
        .lte("start_date", start_to)
        .order("start_date")
        .limit(80)
        .execute()
    )
    return res.data or []


def _ai_select_events(client: OpenAI, events: list[dict], today: datetime) -> dict:
    """Use GPT-4o-mini to select highlight events for weekly and monthly sections."""
    week_end = today + timedelta(days=21)
    week2_end = today + timedelta(days=28)

    # Monthly window: 1st of next month → last day of month-after-next
    next_month_num = today.month % 12 + 1
    next_month_year = today.year + (today.month // 12)
    month_start = datetime(next_month_year, next_month_num, 1, tzinfo=JST)
    month_end = _next_two_months_end(today)

    # Category group definitions (mirrors web/lib/types.ts CATEGORY_GROUPS)
    ARTS_CATS = "movie, performing_arts, art, senses, drama, indigenous, nature, urban, literature"
    LIFESTYLE_CATS = "lifestyle_food, retail, tourism"
    KNOWLEDGE_CATS = "business, academic, lecture, competition, taiwan_japan, books_media, workshop, tv_program, exhibition"
    SOCIETY_CATS = "tech, gender, geopolitics, history, taiwan_mandarin"

    prompt = (
        f"Today is {today.strftime('%Y-%m-%d')}.\n"
        f"Weekly range: {today.strftime('%m/%d')} – {week_end.strftime('%m/%d')}\n"
        f"Next 28 days: {today.strftime('%m/%d')} – {week2_end.strftime('%m/%d')}\n"
        f"Monthly preview: {month_start.strftime('%m/%d')} – {month_end.strftime('%m/%d')}\n\n"
        "Category groups:\n"
        f"  五感 (arts): {ARTS_CATS}\n"
        f"  生活風格 (lifestyle): {LIFESTYLE_CATS}\n"
        f"  知識交流 (knowledge): {KNOWLEDGE_CATS}\n"
        f"  社會 (society): {SOCIETY_CATS}\n\n"
        "TAIWAN RELEVANCE RULE — CRITICAL: Only select events with a DIRECT, EXPLICIT connection to Taiwan.\n"
        "  ACCEPT: Taiwanese artists/performers/directors, events set in Taiwan, Taiwan cultural festivals, \n"
        "          Taiwan food/products, Taiwan-Japan bilateral exchange, events explicitly promoting Taiwan.\n"
        "  REJECT: Events that only vaguely relate to Asia, events where Taiwan is mentioned as one stop\n"
        "          in a multi-country Asia tour (e.g. 'Asia tour including Taiwan'), Japanese events with\n"
        "          no Taiwanese participant, book launches about non-Taiwan topics.\n\n"
        "DEDUPLICATION RULE: Each event id MUST appear at most once across weekly + monthly combined.\n\n"
        "=== WEEKLY SELECTION (5–7 events starting within next 21 days) ===\n"
        "Follow these MANDATORY slot rules in order:\n"
        "1. 五感: fill ≥2 slots; prefer movie/performing_arts/art first within the group.\n"
        "   If NO 五感 events exist in the next 28 days, give those slots to 知識交流.\n"
        "2. 生活風格: fill ≥1 slot.\n"
        "   If NO 生活風格 events in next 28 days, give that slot to 知識交流.\n"
        "3. 知識交流: fill ≥1 slot.\n"
        "   If NO 知識交流 events in next 28 days, give that slot to 社會.\n"
        "4. 社會: fill ≥1 slot.\n"
        "   If NO 社會 events in next 28 days, give that slot to 五感.\n"
        "Fill remaining slots with the best available events across any group.\n\n"
        f"=== MONTHLY SELECTION (2–3 events starting {month_start.strftime('%m/%d')} – {month_end.strftime('%m/%d')}) ===\n"
        "Priority: large-venue events, live film screenings (movie), music performances (performing_arts), lectures, competitions.\n"
        "STRICTLY EXCLUDE events with category 'taiwan_japan' or 'tv_program'.\n\n"
        "Return ONLY JSON: {\"weekly\": [\"id1\",...], \"monthly\": [\"id1\",...]}\n\n"
        "Events:\n" + json.dumps(events, ensure_ascii=False)
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    text = response.choices[0].message.content or "{}"
    return json.loads(text)


def _format_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%-m/%-d")
    except Exception:
        return iso[:10]


# Prefecture → display city label (non-Tokyo only)
# Used to prefix event titles when the event is outside Tokyo.
_PREF_LABEL: dict[str, dict[str, str]] = {
    "大阪": {"zh": "大阪", "ja": "大阪", "en": "Osaka"},
    "大阪府": {"zh": "大阪", "ja": "大阪", "en": "Osaka"},
    "北海道": {"zh": "札幌", "ja": "札幌", "en": "Sapporo"},
    "京都": {"zh": "京都", "ja": "京都", "en": "Kyoto"},
    "京都府": {"zh": "京都", "ja": "京都", "en": "Kyoto"},
    "愛知": {"zh": "名古屋", "ja": "名古屋", "en": "Nagoya"},
    "愛知県": {"zh": "名古屋", "ja": "名古屋", "en": "Nagoya"},
    "兵庫": {"zh": "神戶", "ja": "神戸", "en": "Kobe"},
    "兵庫県": {"zh": "神戶", "ja": "神戸", "en": "Kobe"},
    "福岡": {"zh": "福岡", "ja": "福岡", "en": "Fukuoka"},
    "福岡県": {"zh": "福岡", "ja": "福岡", "en": "Fukuoka"},
    "神奈川": {"zh": "橫濱", "ja": "横浜", "en": "Yokohama"},
    "神奈川県": {"zh": "橫濱", "ja": "横浜", "en": "Yokohama"},
    "埼玉": {"zh": "埼玉", "ja": "埼玉", "en": "Saitama"},
    "埼玉県": {"zh": "埼玉", "ja": "埼玉", "en": "Saitama"},
    "千葉": {"zh": "千葉", "ja": "千葉", "en": "Chiba"},
    "千葉県": {"zh": "千葉", "ja": "千葉", "en": "Chiba"},
    "宮城": {"zh": "仙台", "ja": "仙台", "en": "Sendai"},
    "宮城県": {"zh": "仙台", "ja": "仙台", "en": "Sendai"},
    "沖縄": {"zh": "沖繩", "ja": "沖縄", "en": "Okinawa"},
    "沖縄県": {"zh": "沖繩", "ja": "沖縄", "en": "Okinawa"},
    "広島": {"zh": "廣島", "ja": "広島", "en": "Hiroshima"},
    "広島県": {"zh": "廣島", "ja": "広島", "en": "Hiroshima"},
    "静岡": {"zh": "靜岡", "ja": "静岡", "en": "Shizuoka"},
    "静岡県": {"zh": "靜岡", "ja": "静岡", "en": "Shizuoka"},
}

_TOKYO_PREFIXES = ("東京都", "東京")
_TOKYO_LABEL: dict[str, str] = {"zh": "東京", "ja": "東京", "en": "Tokyo"}


def _city_label(event: dict, lang: str) -> str:
    """Return a bracketed city label for every event with a known location_address.

    Detection order:
    1. location_address starts with '東京都'/'東京' → '[東京]'
    2. location_address starts with a known non-Tokyo prefix → use _PREF_LABEL
    3. location_address is absent → no label (avoid false positives)
    """
    addr = (event.get("location_address") or "").strip()
    if not addr:
        return ""
    # Tokyo
    if addr.startswith(_TOKYO_PREFIXES):
        label = _TOKYO_LABEL.get(lang) or _TOKYO_LABEL["ja"]
        return f"[{label}]"
    # Check known non-Tokyo prefectures
    for pref, labels in _PREF_LABEL.items():
        if addr.startswith(pref):
            label = labels.get(lang) or labels["ja"]
            return f"[{label}]"
    return ""


def _build_message(
    weekly_events: list[dict],
    monthly_events: list[dict],
    lang: str,
    base_url: str,
    today: datetime,
) -> str:
    name_col = f"name_{lang}"
    week_end = today + timedelta(days=6)

    headers = {
        "zh": ("🗓 東京台灣雷達 — 本週精選活動", "【本週活動】", "【下個月不可錯過】"),
        "ja": ("🗓 東京台湾レーダー — 今週のおすすめイベント", "【今週のハイライト】", "【来月の注目イベント】"),
        "en": ("🗓 Tokyo Taiwan Radar — Weekly Highlights", "【This Week】", "【Coming Next Month】"),
    }
    h_title, h_week, h_month = headers[lang]

    weekdays_ja = "月火水木金土日"
    if lang == "ja":
        date_range = (
            f"{today.strftime('%-m/%-d')}（{weekdays_ja[today.weekday()]}）"
            f" ～ {week_end.strftime('%-m/%-d')}（{weekdays_ja[week_end.weekday()]}）"
        )
    else:
        date_range = f"{today.strftime('%-m/%-d')} ～ {week_end.strftime('%-m/%-d')}"

    lines = [h_title, date_range, "", h_week]

    for e in weekly_events:
        title = e.get(name_col) or e.get("name_zh") or e.get("name_ja") or e.get("name_en") or "?"
        date_str = _format_date(e.get("start_date"))
        url = f"{base_url}/r/{e['id']}"
        city = _city_label(e, lang)
        prefix = f"{city}" if city else ""
        lines.append(f"• {prefix}{title}　{date_str}")
        lines.append(f"  {url}")

    if monthly_events:
        lines.extend(["", h_month])
        for e in monthly_events:
            title = e.get(name_col) or e.get("name_zh") or e.get("name_ja") or e.get("name_en") or "?"
            start = _format_date(e.get("start_date"))
            end = _format_date(e.get("end_date"))
            date_str = f"{start}–{end}" if end and end != start else start
            url = f"{base_url}/r/{e['id']}"
            city = _city_label(e, lang)
            prefix = f"{city}" if city else ""
            lines.append(f"• {prefix}{title}（{date_str}）")
            lines.append(f"  {url}")

    lines.append("")
    lines.append(CATEGORY_LIST_FOOTER[lang])
    return "\n".join(lines)


def _multicast(user_ids: list[str], message: str, token: str) -> bool:
    """Send message to up to 500 users per batch."""
    if not user_ids:
        return True
    for i in range(0, len(user_ids), 500):
        batch = user_ids[i : i + 500]
        resp = requests.post(
            LINE_MULTICAST_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "to": batch,
                "messages": [{"type": "text", "text": message}],
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("LINE multicast failed (%d): %s", resp.status_code, resp.text[:200])
            return False
    return True


def _generate_weekly_content(sb, ai, today: datetime) -> tuple[list[dict], list[dict]]:
    """Fetch events and run AI selection. Returns (weekly_events, monthly_events)."""
    events = _fetch_upcoming_events(sb)
    logger.info("Fetched %d upcoming events", len(events))
    if not events:
        return [], []
    selected = _ai_select_events(ai, events, today)
    event_map = {e["id"]: e for e in events}
    weekly_ids: list[str] = selected.get("weekly", [])
    monthly_ids: list[str] = selected.get("monthly", [])
    weekly_events = [event_map[i] for i in weekly_ids if i in event_map]
    weekly_id_set = {e["id"] for e in weekly_events}
    monthly_events = [event_map[i] for i in monthly_ids if i in event_map and i not in weekly_id_set]
    logger.info("AI selected: %d weekly, %d monthly", len(weekly_events), len(monthly_events))
    return weekly_events, monthly_events


def run_generate_draft() -> None:
    """Generate this week's broadcast content and save as a draft announcement.

    Runs on Thursday 09:00 JST in CI. Does NOT send anything.
    The draft can be edited in the admin UI before sending.
    """
    today = datetime.now(JST)
    base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyotaiwanradar.com")
    sb = _get_supabase()
    ai = _get_openai()

    weekly_events, monthly_events = _generate_weekly_content(sb, ai, today)
    if not weekly_events and not monthly_events:
        logger.warning("No events found — draft not created")
        return

    slug = f"weekly-{today.strftime('%Y-%m-%d')}"
    title_zh = f"🗓 東京台灣雷達週報 {today.strftime('%Y/%m/%d')}"
    body_zh = _build_message(weekly_events, monthly_events, "zh", base_url, today)
    body_ja = _build_message(weekly_events, monthly_events, "ja", base_url, today)
    body_en = _build_message(weekly_events, monthly_events, "en", base_url, today)
    all_event_ids = [e["id"] for e in weekly_events + monthly_events]

    # Upsert the announcement (slug is UNIQUE — safe to re-run)
    sb.table("announcements").upsert(
        {
            "slug": slug,
            "type": "weekly_broadcast",
            "title_zh": title_zh,
            "body_zh": body_zh,
            "body_ja": body_ja,
            "body_en": body_en,
            "published_at": None,
            "is_featured": False,
            "social_status": {},
        },
        on_conflict="slug",
    ).execute()

    # Resolve the announcement's UUID
    res = sb.table("announcements").select("id").eq("slug", slug).single().execute()
    ann_id = res.data["id"]

    # Replace linked events
    sb.table("announcement_events").delete().eq("announcement_id", ann_id).execute()
    if all_event_ids:
        sb.table("announcement_events").insert(
            [{"announcement_id": ann_id, "event_id": eid} for eid in all_event_ids]
        ).execute()

    logger.info(
        "Draft saved: slug=%s, weekly=%d, monthly=%d, linked_events=%d",
        slug, len(weekly_events), len(monthly_events), len(all_event_ids),
    )


def run_send_draft(draft_slug: str | None = None) -> None:
    """Find the latest pending weekly_broadcast draft and send it to all subscribers.

    If draft_slug is given, send that specific draft; otherwise pick the newest pending one.
    Marks the announcement as published after sending.
    """
    sb = _get_supabase()
    today = datetime.now(JST)
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")

    # Find draft
    q = (
        sb.table("announcements")
        .select("id, slug, title_zh, body_zh, body_ja, body_en")
        .eq("type", "weekly_broadcast")
        .is_("published_at", "null")
    )
    if draft_slug:
        q = q.eq("slug", draft_slug)
    else:
        q = q.order("created_at", ascending=False).limit(1)
    res = q.execute()

    if not res.data:
        logger.warning("No pending weekly_broadcast draft found — send skipped")
        return
    draft = res.data[0]

    # Fetch subscribers grouped by language
    subs_res = (
        sb.table("line_subscribers")
        .select("line_user_id, language_preference")
        .eq("status", "active")
        .execute()
    )
    subs = subs_res.data or []
    by_lang: dict[str, list[str]] = {"zh": [], "en": [], "ja": []}
    for s in subs:
        lang = s.get("language_preference", "zh")
        if lang in by_lang:
            by_lang[lang].append(s["line_user_id"])

    sent_total = 0
    for lang in ["zh", "ja", "en"]:
        user_ids = by_lang[lang]
        if not user_ids:
            continue
        msg = draft.get(f"body_{lang}") or draft.get("body_zh") or ""
        if not msg:
            continue
        success = _multicast(user_ids, msg, token)
        if success:
            sent_total += len(user_ids)
            logger.info("Sent %s broadcast to %d subscribers", lang.upper(), len(user_ids))

    # Mark as published
    sb.table("announcements").update({
        "published_at": today.isoformat(),
        "social_status": {"line": {"status": "published", "published_at": today.isoformat()}},
    }).eq("id", draft["id"]).execute()

    logger.info("Draft %s sent to %d subscribers total", draft["slug"], sent_total)


def run_auto_send() -> None:
    """Check app_settings.weekly_broadcast.auto_publish and send if enabled.

    Runs on Friday noon JST in CI.
    """
    sb = _get_supabase()
    res = (
        sb.table("app_settings")
        .select("value")
        .eq("key", "weekly_broadcast")
        .maybe_single()
        .execute()
    )
    setting = res.data.get("value", {}) if res.data else {}
    if not setting.get("auto_publish", False):
        logger.info("auto_publish=false — skipping auto-send")
        return
    logger.info("auto_publish=true — running send_draft")
    run_send_draft()


def run_broadcast(dry_run: bool = False, admin_only: bool = False) -> None:
    import time
    start = time.time()
    today = datetime.now(JST)
    base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyo-taiwan-radar.vercel.app")
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")

    sb = _get_supabase()
    ai = _get_openai()

    # 1. Fetch + AI-select events
    weekly_events, monthly_events = _generate_weekly_content(sb, ai, today)
    if not weekly_events and not monthly_events:
        logger.warning("No upcoming events found — broadcast skipped")
        return

    # 2. Fetch subscribers grouped by language
    subs_res = (
        sb.table("line_subscribers")
        .select("line_user_id, language_preference")
        .eq("status", "active")
        .execute()
    )
    subs = subs_res.data or []
    by_lang: dict[str, list[str]] = {"zh": [], "en": [], "ja": []}
    for s in subs:
        lang = s.get("language_preference", "zh")
        if lang in by_lang:
            by_lang[lang].append(s["line_user_id"])
    total_subs = sum(len(v) for v in by_lang.values())
    logger.info(
        "Subscribers: zh=%d, en=%d, ja=%d (total=%d)",
        len(by_lang["zh"]), len(by_lang["en"]), len(by_lang["ja"]), total_subs,
    )

    if dry_run:
        for lang in ["zh", "en", "ja"]:
            if by_lang[lang]:
                msg = _build_message(weekly_events, monthly_events, lang, base_url, today)
                logger.info("=== DRY RUN: %s message ===\n%s", lang.upper(), msg[:500])
        logger.info("Dry run complete — no messages sent")
        return

    if admin_only:
        # Send only to admins defined in ADMIN_LINE_USER_IDS (comma-separated).
        # ZH message is used regardless of the admin's actual language preference.
        raw_ids = os.environ.get("ADMIN_LINE_USER_IDS", "").strip()
        admin_ids = [uid.strip() for uid in raw_ids.split(",") if uid.strip()]
        if not admin_ids:
            logger.error(
                "--admin-only: ADMIN_LINE_USER_IDS not set in .env — nothing sent. "
                "Add: ADMIN_LINE_USER_IDS=Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            )
            return
        msg = _build_message(weekly_events, monthly_events, "zh", base_url, today)
        logger.info("=== ADMIN-ONLY: sending ZH message to %d admin(s) ===\n%s", len(admin_ids), msg[:500])
        success = _multicast(admin_ids, msg, token)
        if success:
            logger.info("Admin-only broadcast sent to: %s", admin_ids)
        return

    # 4. Send per language
    sent_total = 0
    for lang in ["zh", "en", "ja"]:
        user_ids = by_lang[lang]
        if not user_ids:
            continue
        msg = _build_message(weekly_events, monthly_events, lang, base_url, today)
        success = _multicast(user_ids, msg, token)
        if success:
            sent_total += len(user_ids)
            logger.info("Sent %s broadcast to %d subscribers", lang.upper(), len(user_ids))

    # 5. Log to scraper_runs
    duration = int(time.time() - start)
    try:
        sb.table("scraper_runs").insert({
            "source": "weekly_broadcast",
            "events_processed": len(weekly_events) + len(monthly_events),
            "success": True,
            "duration_seconds": duration,
            "notes": (
                f"weekly={len(weekly_events)}, monthly={len(monthly_events)}, "
                f"sent_to={sent_total} subscribers "
                f"(zh={len(by_lang['zh'])}, en={len(by_lang['en'])}, ja={len(by_lang['ja'])})"
            ),
        }).execute()
    except Exception as exc:
        logger.warning("Could not log to scraper_runs: %s", exc)

    logger.info("Weekly broadcast complete in %ds. Sent to %d subscribers.", duration, sent_total)


if __name__ == "__main__":
    if "--generate-draft" in sys.argv:
        run_generate_draft()
    elif "--auto-send" in sys.argv:
        run_auto_send()
    else:
        run_broadcast(
            dry_run="--dry-run" in sys.argv,
            admin_only="--admin-only" in sys.argv,
        )
