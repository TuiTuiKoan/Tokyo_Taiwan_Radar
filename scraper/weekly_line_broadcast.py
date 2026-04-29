"""
Weekly LINE broadcast — sends curated Taiwan event recommendations
to all active LINE subscribers, grouped by language preference.

Usage:
    python weekly_line_broadcast.py [--dry-run]
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


def _fetch_upcoming_events(sb) -> list[dict]:
    """Fetch active events starting within the next 35 days."""
    now = datetime.now(JST)
    start_from = now.isoformat()
    start_to = (now + timedelta(days=35)).isoformat()
    res = (
        sb.table("events")
        .select(
            "id,name_zh,name_ja,name_en,start_date,end_date,category,location_name"
        )
        .eq("is_active", True)
        .is_("parent_event_id", "null")
        .gte("start_date", start_from)
        .lte("start_date", start_to)
        .order("start_date")
        .limit(80)
        .execute()
    )
    return res.data or []


def _ai_select_events(client: OpenAI, events: list[dict], today: datetime) -> dict:
    """Use GPT-4o-mini to select highlight events for weekly and monthly sections."""
    week_end = today + timedelta(days=7)
    week2_end = today + timedelta(days=14)
    month_end = today + timedelta(days=35)

    # Category group definitions (mirrors web/lib/types.ts CATEGORY_GROUPS)
    ARTS_CATS = "movie, performing_arts, art, senses, drama, indigenous, nature, urban, literature"
    LIFESTYLE_CATS = "lifestyle_food, retail, tourism"
    KNOWLEDGE_CATS = "business, academic, lecture, competition, taiwan_japan, books_media, workshop, tv_program, exhibition"
    SOCIETY_CATS = "tech, gender, geopolitics, history, taiwan_mandarin"

    prompt = (
        f"Today is {today.strftime('%Y-%m-%d')}.\n"
        f"This week: {today.strftime('%m/%d')} – {week_end.strftime('%m/%d')}\n"
        f"Next 14 days: {today.strftime('%m/%d')} – {week2_end.strftime('%m/%d')}\n"
        f"Monthly preview: {week_end.strftime('%m/%d')} – {month_end.strftime('%m/%d')}\n\n"
        "Category groups:\n"
        f"  五感 (arts): {ARTS_CATS}\n"
        f"  生活風格 (lifestyle): {LIFESTYLE_CATS}\n"
        f"  知識交流 (knowledge): {KNOWLEDGE_CATS}\n"
        f"  社會 (society): {SOCIETY_CATS}\n\n"
        "=== WEEKLY SELECTION (5–7 events starting within next 7 days) ===\n"
        "Follow these MANDATORY slot rules in order:\n"
        "1. 五感: fill ≥2 slots; prefer movie/performing_arts first within the group.\n"
        "   If NO 五感 events exist in the next 14 days, give those slots to 知識交流.\n"
        "2. 生活風格: fill ≥1 slot.\n"
        "   If NO 生活風格 events in next 14 days, give that slot to 知識交流.\n"
        "3. 知識交流: fill ≥1 slot.\n"
        "   If NO 知識交流 events in next 14 days, give that slot to 社會.\n"
        "4. 社會: fill ≥1 slot.\n"
        "   If NO 社會 events in next 14 days, give that slot to 五感.\n"
        "Fill remaining slots with the best available events across any group.\n\n"
        "=== MONTHLY SELECTION (2–3 events starting in 8–35 days) ===\n"
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
        lines.append(f"• {title}　{date_str}")
        lines.append(f"  {url}")

    if monthly_events:
        lines.extend(["", h_month])
        for e in monthly_events:
            title = e.get(name_col) or e.get("name_zh") or e.get("name_ja") or e.get("name_en") or "?"
            start = _format_date(e.get("start_date"))
            end = _format_date(e.get("end_date"))
            date_str = f"{start}–{end}" if end and end != start else start
            url = f"{base_url}/r/{e['id']}"
            lines.append(f"• {title}（{date_str}）")
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


def run_broadcast(dry_run: bool = False) -> None:
    import time
    start = time.time()
    today = datetime.now(JST)
    base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyo-taiwan-radar.vercel.app")
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")

    sb = _get_supabase()
    ai = _get_openai()

    # 1. Fetch upcoming events
    events = _fetch_upcoming_events(sb)
    logger.info("Fetched %d upcoming events", len(events))
    if not events:
        logger.warning("No upcoming events found — broadcast skipped")
        return

    # 2. AI selection
    selected = _ai_select_events(ai, events, today)
    event_map = {e["id"]: e for e in events}
    weekly_ids: list[str] = selected.get("weekly", [])
    monthly_ids: list[str] = selected.get("monthly", [])
    weekly_events = [event_map[i] for i in weekly_ids if i in event_map]
    monthly_events = [event_map[i] for i in monthly_ids if i in event_map]
    logger.info("AI selected: %d weekly, %d monthly", len(weekly_events), len(monthly_events))

    # 3. Fetch subscribers grouped by language
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
    run_broadcast(dry_run="--dry-run" in sys.argv)
