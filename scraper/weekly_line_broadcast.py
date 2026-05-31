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
1.五感　2.文藝　3.生活　4.體驗
5.學術　6.社會　7.科技　8.旅遊

💡 輸入編號或分類名稱可客製化推播
切換語言：輸入「日本語」或「English」""",
    "ja": """━━━━━━━━━━━━━━━━━━
📂 カテゴリ
1.台湾五感　2.文化・芸術　3.ライフスタイル　4.体験
5.学術　6.社会　7.テクノロジー　8.観光

💡 番号またはカテゴリ名を入力でカスタマイズ配信
言語切替：「中文」または「English」と入力""",
    "en": """━━━━━━━━━━━━━━━━━━
📂 Categories
1.Senses　2.Arts　3.Lifestyle　4.Experience
5.Academic　6.Society　7.Tech　8.Tourism

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
            "id,name_zh,name_ja,name_en,start_date,end_date,category,source_name,location_name,location_address,location_prefectures"
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
        "=== WEEKLY SELECTION (exactly 10 events, starting within next 21 days) ===\n"
        "Follow these MANDATORY slot rules — ALL must be satisfied if matching events exist:\n"
        "1. 五感: fill ≥2 slots; prefer movie/performing_arts/art first within the group.\n"
        "   Fallback to 知識交流 if no 五感 events exist.\n"
        "2. 生活風格: fill ≥1 slot.\n"
        "   Fallback to 知識交流 if no 生活風格 events exist.\n"
        "3. 知識交流: fill ≥1 slot.\n"
        "   Fallback to 社會 if no 知識交流 events exist.\n"
        "4. 社會: fill ≥1 slot.\n"
        "   Fallback to 五感 if no 社會 events exist.\n"
        "5. 台灣華語 slot (MANDATORY): include ≥1 event that teaches or promotes Taiwan Mandarin (華語)\n"
        "   or Taiwanese (台語) language — e.g. 語言交流, 語文, 華語会話. Skip only if none exist.\n"
        "6. 國際政治講座 slot (MANDATORY): include ≥1 event with category 'geopolitics' or a\n"
        "   lecture/academic event with political or international-relations theme. Skip if none exist.\n"
        "7. 品牌消費・設計 slot (MANDATORY when available): if ANY events with category 'retail' exist,\n"
        "   MUST include ≥1 of them — these are rare and high-value. Skip only if none exist.\n"
        "8. CITY DIVERSITY (aim): include events from ≥3 distinct cities OUTSIDE Tokyo if possible.\n"
        "   Prefer 大阪, 福岡, 京都, 名古屋, etc. Use location_address to determine city.\n"
        "Fill remaining slots with the best available events across any group.\n\n"
        f"=== MONTHLY SELECTION (exactly 10 events, starting {month_start.strftime('%m/%d')} – {month_end.strftime('%m/%d')}) ===\n"
        "Rules for monthly selection:\n"
        "- No category restriction — pick the 10 most noteworthy events by scale and duration.\n"
        "- Prefer: large-venue exhibitions, long-running shows (end_date far from start_date),\n"
        "  ticketed concerts, stage performances, high-profile screenings with guest talks.\n"
        "- Up to 50% overlap with last week's monthly section is acceptable (promotional period is long).\n"
        "- EXCLUDE events with category 'tv_program'.\n\n"
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

# Taiwan city address prefixes → show [台灣]/[台湾]/[Taiwan]
_TAIWAN_ADDRESS_PREFIXES = (
    "台北市", "臺北市", "新北市", "台中市", "臺中市", "台南市", "臺南市",
    "高雄市", "桃園市", "新竹市", "新竹縣", "基隆市", "嘉義市", "嘉義縣",
    "宜蘭縣", "花蓮縣", "台東縣", "臺東縣", "屏東縣", "南投縣", "彰化縣",
    "雲林縣", "苗栗縣", "澎湖縣", "金門縣", "連江縣",
)
_TAIWAN_LABEL: dict[str, str] = {"zh": "台灣", "ja": "台湾", "en": "Taiwan"}
# Prefixes added to TV event names in DB — strip from broadcast titles to avoid duplication
# with the [電視節目]/[TV Program]/[テレビ番組] city-slot label
_TV_NAME_PREFIXES: dict[str, str] = {"zh": "【電視節目】", "en": "【TV Program】", "ja": "【テレビ番組】"}

# Sub-section headers for 活動/電影/新書出版/線上/電視 grouping (used in nearterm section and listing output)
_TYPE_GROUP_HDRS: dict[str, tuple[str, str, str, str, str]] = {
    "zh": ("【活動】", "【電影】", "【新書出版】", "【線上活動】", "【電視節目】"),
    "ja": ("【活動】", "【映画】", "【新刊書籍】", "【オンライン】", "【テレビ番組】"),
    "en": ("【Events】", "【Films】", "【New Books】", "【Online】", "【TV Programs】"),
}


def _group_by_type(events: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Split events into (regular, film, books, online, tv) groups, preserving order within each group."""
    tv: list[dict] = []
    online: list[dict] = []
    film: list[dict] = []
    books: list[dict] = []
    regular: list[dict] = []
    for e in events:
        if e.get("source_name") == "gguide_tv":
            tv.append(e)
        elif (e.get("location_name") or "").strip() == "オンライン":
            online.append(e)
        elif "movie" in (e.get("category") or []):
            film.append(e)
        elif "books_media" in (e.get("category") or []):
            books.append(e)
        else:
            regular.append(e)
    return regular, film, books, online, tv


def _city_label(event: dict, lang: str) -> str:
    """Return a bracketed city label for every event, including Tokyo.

    Detection order:
    0. source_name == 'gguide_tv' → TV program label
    1. location_name == 'オンライン' → online label
    2. location_address starts with '東京都'/'東京' → '[東京]'
    3. location_address starts with a known non-Tokyo prefix → use _PREF_LABEL
    4. location_prefectures[0] fallback when location_address is absent
    5. Still nothing → no label
    """
    # TV program events
    if event.get("source_name") == "gguide_tv":
        tv_labels = {"zh": "電視節目", "en": "TV Program", "ja": "テレビ番組"}
        label = tv_labels.get(lang, "テレビ番組")
        return f"[{label}]"
    # Online events get a language-appropriate label
    if (event.get("location_name") or "").strip() == "オンライン":
        online_labels = {"zh": "線上", "en": "Online", "ja": "オンライン"}
        label = online_labels.get(lang, "オンライン")
        return f"[{label}]"
    addr = (event.get("location_address") or "").strip()
    if addr:
        # Tokyo
        if addr.startswith(_TOKYO_PREFIXES):
            label = _TOKYO_LABEL.get(lang) or _TOKYO_LABEL["ja"]
            return f"[{label}]"
        # Taiwan address
        if addr.startswith(_TAIWAN_ADDRESS_PREFIXES):
            label = _TAIWAN_LABEL.get(lang) or _TAIWAN_LABEL["zh"]
            return f"[{label}]"
        # Check known non-Tokyo prefectures
        for pref, labels in _PREF_LABEL.items():
            if addr.startswith(pref):
                label = labels.get(lang) or labels["ja"]
                return f"[{label}]"
    # Fallback: use location_prefectures array
    prefs = event.get("location_prefectures") or []
    if prefs:
        pref = prefs[0]
        if pref in ("東京都", "東京"):
            label = _TOKYO_LABEL.get(lang) or _TOKYO_LABEL["ja"]
            return f"[{label}]"
        for known_pref, labels in _PREF_LABEL.items():
            if pref == known_pref:
                label = labels.get(lang) or labels["ja"]
                return f"[{label}]"
        # Strip suffix and use raw prefecture short name
        short = pref.rstrip("都道府県")
        return f"[{short}]"
    return ""


def _build_message(
    weekly_events: list[dict],
    monthly_events: list[dict],
    lang: str,
    base_url: str,
    today: datetime,
    nearterm_events: list[dict] | None = None,
) -> str:
    name_col = f"name_{lang}"

    date_label = today.strftime("%Y/%m/%d")
    headers = {
        "zh": (f"🗓 東京台灣雷達「一週偵測」 {date_label}", "【小霧精選】", "【下個月不可錯過】"),
        "ja": (f"🗓 東京台湾レーダー「今週のスキャン」 {date_label}", "【レンブ厳選】", "【来月の注目】"),
        "en": (f'🗓 Tokyo Taiwan Radar "Weekly Scan" {date_label}', "【Bubu's Picks】", "【Don't Miss Next Month】"),
    }
    h_title, h_week, h_month = headers[lang]

    # Header shows: broadcast Friday (next Friday on or after today) → broadcast Friday + 7 days
    days_to_fri = (4 - today.weekday()) % 7  # 0 if today is already Friday
    broadcast_fri = today + timedelta(days=days_to_fri)
    nearterm_start_label = broadcast_fri.strftime("%-m/%-d")
    nearterm_end_label = (broadcast_fri + timedelta(days=7)).strftime("%-m/%-d")
    nearterm_range = f"{nearterm_start_label}–{nearterm_end_label}"
    nearterm_hdrs: dict[str, str] = {
        "zh": f"─ 本週・下週全部活動（{nearterm_range}）─",
        "ja": f"─ 今週・来週の全イベント（{nearterm_range}）─",
        "en": f"─ All Events {nearterm_range} ─",
    }

    lines = [h_title, "", h_week]

    tv_pfx = _TV_NAME_PREFIXES.get(lang, "")

    def _title(e: dict) -> str:
        """Get display title, stripping redundant TV prefix if city label covers it."""
        raw = e.get(name_col) or e.get("name_zh") or e.get("name_ja") or e.get("name_en") or "?"
        if tv_pfx and raw.startswith(tv_pfx) and e.get("source_name") == "gguide_tv":
            return raw[len(tv_pfx):]
        return raw

    for e in weekly_events[:10]:  # AI selection capped at 10
        title = _title(e)
        date_str = _format_date(e.get("start_date"))
        url = f"{base_url}/{lang}/events/{e['id']}"
        city = _city_label(e, lang)
        prefix = f"{city}" if city else ""
        lines.append(f"• {prefix}{title}　{date_str}")
        lines.append(f"  {url}")

    if nearterm_events:
        lines.extend(["", nearterm_hdrs[lang]])
        h_ev, h_film, h_book, h_on, h_tv = _TYPE_GROUP_HDRS[lang]
        regular, film_evts, book_evts, online_evts, tv_evts = _group_by_type(nearterm_events)
        for group_hdr, group in [(h_ev, regular), (h_film, film_evts), (h_book, book_evts), (h_on, online_evts), (h_tv, tv_evts)]:
            if not group:
                continue
            lines.append(group_hdr)
            for e in group:
                title = _title(e)
                date_str = _format_date(e.get("start_date"))
                url = f"{base_url}/{lang}/events/{e['id']}"
                city = _city_label(e, lang)
                prefix = f"{city}" if city else ""
                lines.append(f"• {prefix}{title}　{date_str}")
                lines.append(f"  {url}")

    if monthly_events:
        lines.extend(["", h_month])
        for e in monthly_events:
            title = _title(e)
            start = _format_date(e.get("start_date"))
            end = _format_date(e.get("end_date"))
            date_str = f"{start}–{end}" if end and end != start else start
            url = f"{base_url}/{lang}/events/{e['id']}"
            city = _city_label(e, lang)
            prefix = f"{city}" if city else ""
            lines.append(f"• {prefix}{title}（{date_str}）")
            lines.append(f"  {url}")

    lines.append("")
    lines.append(CATEGORY_LIST_FOOTER[lang])
    return "\n".join(lines)


def _multicast(user_ids: list[str], message: str, token: str, image_url: str | None = None) -> bool:
    """Send message to up to 500 users per batch.

    If image_url is provided, sends an image message followed by the text message
    in a single API call (LINE supports up to 5 messages per request).
    image_url must be a public HTTPS URL (e.g. Supabase Storage public URL).
    """
    if not user_ids:
        return True
    messages: list[dict] = []
    if image_url:
        messages.append({
            "type": "image",
            "originalContentUrl": image_url,
            "previewImageUrl": image_url,
        })
    messages.append({"type": "text", "text": message})
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
                "messages": messages,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("LINE multicast failed (%d): %s", resp.status_code, resp.text[:200])
            return False
    return True


def _generate_weekly_content(sb, ai, today: datetime) -> tuple[list[dict], list[dict], list[dict]]:
    """Fetch events and run AI selection.

    Returns (weekly_events, monthly_events, nearterm_events).
    nearterm_events: all active annotated events from today (send_date, Fri) through today+9 (next Sun)
    that are NOT already in the curated weekly top-10 — listed for exhaustive near-term reference.
    """
    events = _fetch_upcoming_events(sb)
    logger.info("Fetched %d upcoming events", len(events))
    if not events:
        return [], [], []
    selected = _ai_select_events(ai, events, today)
    event_map = {e["id"]: e for e in events}
    weekly_ids: list[str] = selected.get("weekly", [])
    monthly_ids: list[str] = selected.get("monthly", [])
    weekly_events = [event_map[i] for i in weekly_ids if i in event_map]
    weekly_id_set = {e["id"] for e in weekly_events}
    monthly_events = [event_map[i] for i in monthly_ids if i in event_map and i not in weekly_id_set]

    # Near-term exhaustive list: all events from today (Fri) through today+9 (next Sun)
    # that are not already in the curated top-10 picks — includes gguide_tv (TV programs)
    nearterm_end = today + timedelta(days=9)
    nearterm_start_iso = today.date().isoformat()
    nearterm_end_iso = nearterm_end.date().isoformat()
    # Fetch gguide_tv events separately for near-term (excluded from AI selection pool)
    tv_res = (
        sb.table("events")
        .select("id,name_zh,name_ja,name_en,start_date,end_date,category,source_name,location_name,location_address,location_prefectures")
        .eq("is_active", True)
        .is_("parent_event_id", "null")
        .eq("source_name", "gguide_tv")
        .in_("annotation_status", ["annotated", "reviewed"])
        .gte("start_date", nearterm_start_iso)
        .lte("start_date", nearterm_end_iso + "T23:59:59Z")
        .order("start_date")
        .execute()
    )
    tv_events = tv_res.data or []
    nearterm_pool = events + [e for e in tv_events if e["id"] not in event_map]
    nearterm_events = sorted(
        [
            e for e in nearterm_pool
            if (e.get("start_date") or "")[:10] >= nearterm_start_iso
            and (e.get("start_date") or "")[:10] <= nearterm_end_iso
            and e["id"] not in weekly_id_set
        ],
        key=lambda e: e.get("start_date") or "",
    )

    logger.info(
        "AI selected: %d weekly, %d monthly; nearterm additional: %d",
        len(weekly_events), len(monthly_events), len(nearterm_events),
    )
    return weekly_events, monthly_events, nearterm_events


def run_generate_draft() -> None:
    """Generate this week's broadcast content and save as a draft announcement.

    Runs on Thursday 09:00 JST in CI. Does NOT send anything.
    The draft can be edited in the admin UI before sending.
    """
    today = datetime.now(JST)
    base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyotaiwanradar.com")
    sb = _get_supabase()
    ai = _get_openai()

    # send_date = the Friday this draft will be auto-sent (draft day is Thursday)
    send_date = today + timedelta(days=1)

    weekly_events, monthly_events, nearterm_events = _generate_weekly_content(sb, ai, send_date)
    if not weekly_events and not monthly_events:
        logger.warning("No events found — draft not created")
        return

    slug = f"weekly-{send_date.strftime('%Y-%m-%d')}"
    date_str = send_date.strftime('%Y/%m/%d')
    title_zh = f"🗓 東京台灣雷達「一週偵測」 {date_str}"
    title_ja = f"🗓 東京台湾レーダー「週間巡回」 {date_str}"
    title_en = f"🗓 Tokyo Taiwan Radar 'Weekly Scan' {date_str}"
    body_zh = _build_message(weekly_events, monthly_events, "zh", base_url, send_date, nearterm_events)
    body_ja = _build_message(weekly_events, monthly_events, "ja", base_url, send_date, nearterm_events)
    body_en = _build_message(weekly_events, monthly_events, "en", base_url, send_date, nearterm_events)
    weekly_monthly_ids = {e["id"] for e in weekly_events + monthly_events}
    all_event_ids = list(weekly_monthly_ids) + [
        e["id"] for e in nearterm_events if e["id"] not in weekly_monthly_ids
    ]

    # Upsert the announcement (slug is UNIQUE — safe to re-run)
    sb.table("announcements").upsert(
        {
            "slug": slug,
            "type": "weekly_broadcast",
            "title_zh": title_zh,
            "title_ja": title_ja,
            "title_en": title_en,
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
        .select("id, slug, title_zh, body_zh, body_ja, body_en, cover_image_url")
        .eq("type", "weekly_broadcast")
        .is_("published_at", "null")
    )
    if draft_slug:
        q = q.eq("slug", draft_slug)
    else:
        q = q.order("created_at", desc=True).limit(1)
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
        image_url = draft.get("cover_image_url") or None
        success = _multicast(user_ids, msg, token, image_url=image_url)
        if success:
            sent_total += len(user_ids)
            logger.info(
                "Sent %s broadcast to %d subscribers%s",
                lang.upper(), len(user_ids),
                " (with image)" if image_url else "",
            )

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
    weekly_events, monthly_events, nearterm_events = _generate_weekly_content(sb, ai, today)
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
                msg = _build_message(weekly_events, monthly_events, lang, base_url, today, nearterm_events)
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
        msg = _build_message(weekly_events, monthly_events, "zh", base_url, today, nearterm_events)
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
        msg = _build_message(weekly_events, monthly_events, lang, base_url, today, nearterm_events)
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
