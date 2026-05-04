"""
AI-powered event annotator using OpenAI GPT-4o-mini.

Processes events with annotation_status='pending' in the database:
  1. Sends raw_title + raw_description to GPT-4o-mini
  2. Extracts structured fields (dates, location, pricing, categories)
  3. Translates name + description into ja/zh/en
  4. Detects sub-events and creates child rows
  5. Updates the event row with annotation_status='annotated'

Usage:
    python annotator.py          # Annotate all pending events
    python annotator.py --all    # Re-annotate ALL events
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from playwright.sync_api import sync_playwright, Browser, TimeoutError as PWTimeout
from supabase import create_client, Client

from category_feedback import load_corrections, build_feedback_prompt
from selection_reason_feedback import load_sr_corrections, build_sr_feedback_prompt
from movie_title_lookup import lookup_movie_titles
from person_name_lookup import (
    PersonInfo,
    extract_katakana_names,
    lookup_person_names,
    lookup_single_person,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google News article fetcher
# ---------------------------------------------------------------------------
_GNEWS_ARTICLE_MAX_CHARS = 4000
_GNEWS_FETCH_TIMEOUT_MS = 20_000


def _fetch_gnews_article_text(gnews_url: str, browser: "Browser") -> str | None:
    """Follow a Google News redirect URL and return the article body text.

    Returns None on any error (timeout, paywall, bad redirect, etc.).
    The returned text is truncated to _GNEWS_ARTICLE_MAX_CHARS to stay within
    GPT token limits.
    """
    page = None
    try:
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "ja,en;q=0.9"})
        page.goto(gnews_url, timeout=_GNEWS_FETCH_TIMEOUT_MS, wait_until="domcontentloaded")
        # Wait briefly for JS redirect to resolve
        page.wait_for_timeout(3000)
        final_url = page.url
        # If we're still on google.com, the redirect didn't resolve
        if "google.com" in final_url:
            logger.debug("gnews fetch: redirect did not resolve for %s", gnews_url[:80])
            return None
        # Try common article body selectors in priority order
        for selector in ["article", "main", ".article-body", ".entry-content", ".post-content", "body"]:
            try:
                el = page.query_selector(selector)
                if el:
                    text = el.inner_text().strip()
                    if len(text) > 200:  # meaningful content threshold
                        return text[:_GNEWS_ARTICLE_MAX_CHARS]
            except Exception:
                continue
        return None
    except PWTimeout:
        logger.debug("gnews fetch: timeout for %s", gnews_url[:80])
        return None
    except Exception as e:
        logger.debug("gnews fetch: error for %s: %s", gnews_url[:80], e)
        return None
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Valid categories (must match web/lib/types.ts)
# ---------------------------------------------------------------------------
VALID_CATEGORIES = [
    "movie", "performing_arts", "senses", "retail", "nature",
    "tech", "tourism", "lifestyle_food", "books_media", "gender", "geopolitics",
    "art", "lecture", "taiwan_japan", "business", "academic", "competition",
    "indigenous", "history", "urban", "workshop", "report",
]

# News-source movie title enrichment helpers
# raw_title of news articles often contains the movie title in 「」/『』brackets.
_NEWS_MOVIE_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})
_BRACKET_TITLE_RE = re.compile(r"[\u300c\u300e]([^\u300d\u300f]+)[\u300d\u300f]")

# Prefecture extraction — mirrors web/app/[locale]/events/[id]/page.tsx extractPrefecture()
_PREFECTURE_RE = re.compile(
    r"^(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県]{2,4}[都道府県])"
)

def _extract_prefecture(address: str | None) -> str | None:
    """Return prefecture name (e.g. '東京', '大阪') from a Japanese address, or None."""
    if not address:
        return None
    m = _PREFECTURE_RE.match(address)
    if not m:
        return None
    full = m.group(1)
    if full == "北海道":
        return "北海道"
    if full in ("大阪市", "大阪府"):
        return "大阪"
    if full in ("京都市", "京都府"):
        return "京都"
    return full.rstrip("都道府県")

# Regex for deterministic venue extraction from raw_description
# before GPT annotation — matches 会場：/場所：label lines.
_VENUE_LABEL_RE = re.compile(r'(?:会場|場所)[：:]\s*(.+)')
_PREF_ADDR_INLINE_RE = re.compile(
    r'((?:東京都|大阪府|京都府|神奈川県|愛知県|福岡県|兵庫県|埼玉県|千葉県|'
    r'北海道|宮城県|広島県|静岡県|茨城県|岡山県|新潟県|長野県|栃木県|'
    r'群馬県|滋賀県|岐阜県|奈良県|熊本県|石川県)[^\n]{5,80})'
)


def _extract_venue_from_raw(text: str) -> dict:
    """Extract location_name and location_address from raw_description text.

    Handles the common pattern in Japanese event pages:
        会場：白水出版センター
        東京都豊島区高田1-10-10

    Returns a dict with zero, one, or both of:
        {"location_name": "...", "location_address": "..."}
    """
    if not text:
        return {}
    result: dict = {}
    m = _VENUE_LABEL_RE.search(text)
    if not m:
        return {}
    venue_line = m.group(1).strip()
    # Strip inline hybrid/online suffix
    venue_name = re.split(
        r'[、,]?\s*(?:および|及び|Google Meet|またはGoogle|Zoom|オンライン)',
        venue_line,
    )[0].strip()
    # Remove trailing note in brackets e.g. "（教室は未定）"
    venue_name = re.sub(r'\s*[（(][^）)]{1,30}[）)]$', '', venue_name).strip()
    if venue_name:
        result["location_name"] = venue_name
    # Look for prefecture-prefixed address in the ~300 chars after 会場 line
    rest = text[m.end():]
    addr_m = _PREF_ADDR_INLINE_RE.search(rest[:300])
    if addr_m:
        result["location_address"] = addr_m.group(1).strip()
    return result


def _extract_hours_from_raw(text: str) -> str | None:
    """Deterministically extract business hours from raw_description.

    Looks for time patterns near a 日時 label. Only extracts when confidence
    is high (HH:MM or H〜H時 patterns). Returns None rather than guessing
    ambiguous patterns like '午後２時'.
    """
    if not text:
        return None
    _TIME = r'\d{1,2}:\d{2}'
    # Range: 10:00〜16:00 or 10:00-16:00 or 10:00～16:00
    m = re.search(rf'({_TIME})\s*[〜~～\-]\s*({_TIME})', text)
    if m:
        return f"{m.group(1)}〜{m.group(2)}"
    # Hour-only range: 11〜17時 or 11～17時
    m2 = re.search(r'(\d{1,2})\s*[〜~～]\s*(\d{1,2})時', text)
    if m2:
        return f"{m2.group(1)}:00〜{m2.group(2)}:00"
    # Single time right after 日時 label (e.g. 日時：2026年4月25日（土）22:00)
    m3 = re.search(r'日時[：:][^\n]{0,80}?(\d{1,2}:\d{2})', text)
    if m3:
        return m3.group(1)
    return None


# Bracket pairs used by GPT when wrapping movie titles in descriptions.
_TITLE_BRACKETS = [
    ("\u300a", "\u300b"),  # \u300a\u300b Chinese double angle
    ("\u300c", "\u300d"),  # \u300c\u300d Japanese corner
    ("\u300e", "\u300f"),  # \u300e\u300f Japanese white corner
    ("\u2018", "\u2019"),  # \u2018\u2019 English single curly
    ("\u201c", "\u201d"),  # \u201c\u201d English double curly
    ("'", "'"),            # '' ASCII straight single
    ('"', '"'),            # "" ASCII straight double
]


def _replace_title_in_desc(desc: str, old_titles: list[str], new_title: str) -> str:
    """Replace bracketed old movie title references in a description.

    Only replaces when the old title is wrapped in a recognized bracket pair,
    to avoid accidental partial-word substitutions.
    """
    result = desc
    for old in old_titles:
        if not old or old == new_title:
            continue
        for open_b, close_b in _TITLE_BRACKETS:
            old_bracketed = f"{open_b}{old}{close_b}"
            if old_bracketed in result:
                result = result.replace(old_bracketed, f"{open_b}{new_title}{close_b}")
    return result

# ---------------------------------------------------------------------------
# GPT System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert event data analyst specializing in Taiwan-related cultural events in Japan.

LANGUAGE RULE — CRITICAL: ALL *_zh fields (name_zh, description_zh, location_name_zh, location_address_zh, business_hours_zh, selection_reason.zh, and sub-event zh fields) MUST be written in Traditional Chinese (繁體中文). NEVER use Simplified Chinese (简体字). This applies to every single zh field without exception.

Given the raw title and description of an event (usually in Japanese), extract structured data and translate into three languages.

CRITICAL DATE EXTRACTION RULES:
1. You MUST extract dates from ALL parts of the text: title, body, headers, and footers.
2. Look for date patterns like: 2025年10月8日, 10/8, 10月8日, 2025-10-08, etc.
3. If the event spans multiple days (e.g., "10/8 and 10/10"), start_date = first date, end_date = last date.
4. SINGLE-DAY RULE: If only one date is mentioned — or if you judge the event to be a single-day occurrence — set end_date = start_date exactly. NEVER leave end_date null when start_date is known.
5. end_date MUST NOT be null if any date can be found anywhere in the text. Try harder to find dates.
6. If the title contains a date like "（10/8・10/10）", extract those dates even if the body is vague.
7. When the year is not explicitly stated, infer it from context. If unclear, assume the nearest future occurrence.
8. For ongoing exhibitions/screenings with a date range (e.g., "4月5日〜6月30日"), use the full range.
9. JUDGMENT: Use your reasoning to decide if an event is single-day vs multi-day. A concert, one-time screening, or one-time talk = single day (end_date = start_date). An exhibition, festival, or course = may span many days.
10. DURATION KEYWORDS: When the description explicitly states a duration like "N日間" (e.g., "6日間", "3日間"), compute end_date = start_date + (N-1) days. "1日間" = single day. "N週間" = N×7 days. This OVERRIDES the single-day default. Example: start_date=2026-02-25, "6日間" → end_date=2026-03-02.

OTHER RULES:
1. If the description mentions multiple separate events/sessions with different dates (e.g., a film screening series with individual dates), list them as sub_events.
   ALSO: if the description lists 3+ distinct venue locations in **different cities/prefectures** each with a specific address (e.g., a food fair with restaurants across Tokyo, Kyoto, and Osaka), list each venue as a sub-event with its own location_name, location_address, and business_hours; use the same start_date/end_date as the parent.
2. Categories must be from this list: movie, performing_arts, senses, retail, nature, tech, tourism, lifestyle_food, books_media, gender, geopolitics, art, lecture, taiwan_japan, business, academic, competition, indigenous, history, urban, workshop, report
   - "taiwan_japan" = Taiwan-Japan bilateral relations, diplomacy, civil exchange, friendship events between Taiwan and Japan
   - "business" = business, investment, commerce, startups, corporate events, trade, entrepreneurship
   - "competition" = contests, competitions, awards, championships, public calls for entries (コンテスト, 大会, 選手権, 公募, コンクール)
   - "academic" = academic research, seminars, symposiums, papers, university events, scholarly conferences
   - "indigenous" = events related to Taiwan's indigenous peoples (原住民族), tribal culture, indigenous arts or languages (アミ族, パイワン族, タイヤル族, etc.)
   - "history" = historical events, exhibitions on history, cultural heritage, archives, museums, war memory, historical figures
   - "workshop" = hands-on workshops, experience classes, craft workshops, cooking classes, pottery, weaving, tea ceremony, atelier sessions (体験, ワークショップ, 手作り, クラフト)
   - "movie" = film screenings, movie events, documentary showings, film festivals. IMPORTANT: any event with 上映, 映画, film, screening, cinema in its title or description MUST include "movie" as a category, even if it also involves talks or other elements.
   - "performing_arts" = LIVE stage performances ONLY: concerts, theater, dance, opera. NOT for film screenings. For Asia/Japan tour events (アジアツアー, 日本ツアー), only use if the Tokyo show is confirmed a live performance.
   - "senses" = art exhibitions, photography, design shows, creative/visual experiences. NOT for film screenings or book-only events.
   - "lifestyle_food" = food, cooking, tea ceremony, restaurants, cafes, lifestyle events. Do NOT add taiwan_japan just because the food is Taiwanese — use taiwan_japan only when the event emphasizes bilateral exchange.
   - "books_media" = books, literature, publishing, authors, readings, book launch events, media, journalism. FORMULA: when title contains 著者名+『書名』 (author + book in 『』) OR ブックサロン/刊行記念/出版記念 → ALWAYS add books_media + lecture + academic. Then add geopolitics if political/policy content, history if historical content, taiwan_japan ONLY if explicitly about Japan-Taiwan bilateral topic.
   - "lecture" = talks, presentations, lectures, panels, Q&A sessions. MANDATORY when title/description contains any of: トークイベント, トークショー, 講演会, 講演, 講座, シンポジウム, 勉強会, 例会, 基調講演, 映後座談, セッション, 研究会. Also ALWAYS add lecture when movie + トーク/座談 co-occur.
   - "geopolitics" = Taiwan political history, cross-strait relations, Taiwan identity/sovereignty, Taiwan Strait crisis, Japan-Taiwan national security strategy, government/public policy (移民政策, 給食政策, デジタル政府). Add alongside history or academic for relevant films, books, talks. Trigger keywords: 危機, 海峡, 独立, 民主化, 移民政策, インド太平洋, 日台関係 (security/policy sense), 主権, 国際フォーラム.
   - "history" = historical events, Taiwan colonial era, war memory. MANDATORY for: films/docs about colonial-era or war-era Taiwan (日本統治, 戦没者, 同化, 傷痕); historical figures (李登輝, 蒋介石); photo exhibitions of historical Taiwan. Keywords: 戦没, 植民地, 統治, 秘録, 同化, 傷痕, 歴史.
   - "taiwan_japan" = Taiwan-Japan BILATERAL relations ONLY. Use for: formal diplomatic/exchange events; Taiwanese diaspora in Japan (台湾系移住民); Taiwan veteran memorials (台湾出身戦没者); academic research on bilateral topics. DO NOT USE for: Taiwan food events, Taiwan concerts/tours, Taiwan children's books, Taiwan tourism promotion seminars, general Taiwan cultural events without explicit bilateral focus.
   - "report" = event reports/recaps (only if the text IS a report about a past event, not an upcoming event)
   - An event can have multiple categories
3. Translate the event name and a concise summary description into all three languages (ja, zh, en).
4. The description should be a clean, concise summary (2-4 sentences), NOT a copy of the raw text.
5. Extract location, address, business hours, and pricing from the text if available.

NAME WRITING RULES — CRITICAL:
- name_ja: copy the raw_title as-is. Do NOT rewrite, shorten, or "improve" it. The scraper's original title is the source of truth. Your name_ja output is only used for sub-events (the parent's name_ja is always preserved from the scraper).
- name_zh and name_en: translate name_ja faithfully. A reader who sees ONLY the title must understand what kind of event it is.
- If the raw_title is a generic term alone (e.g., "オフ会", "ライブ", "上映会"), prepend context in name_zh/name_en to make them self-explanatory.
- SUB-EVENT name_ja / description_ja: use the ORIGINAL Japanese text from the raw description. Movie titles must use the Japanese release title exactly as written. Person names must use the original Japanese notation (katakana/kanji). NEVER translate Chinese/Taiwanese person names into Japanese or invent katakana readings.
- SUBTITLE RULE — CRITICAL: When the raw_title or name_ja contains a subtitle separator (――, ──, ―, —, ：, : used as structural separator), the FULL title including the complete subtitle MUST appear in name_zh and name_en. NEVER truncate the subtitle. Example: "台湾の地方選挙と基層社会――80年代以降の桃園県観音･新屋地区を例として" → name_zh must include "以80年代以降的桃園縣觀音・新屋地區為例", name_en must include "A Case Study of Guanyin and Xinwu Districts, Taoyuan, since the 1980s".
6. LOCATION ADDRESS RULE: If the raw location_address looks like a venue/shop name (no street number, 丁目, 番地, or postal code 〒), use your knowledge to provide the real Japanese address (都道府県＋区＋丁目番地). Example: "青山・月見ル君想フ" → "東京都港区南青山3-10-33". If you genuinely don't know the address, keep it as-is. NEVER fabricate an address — only fill in if you are confident.
   NOTE: Events held IN Taiwan are allowed and welcome. Do NOT force-convert Taiwan addresses to Japanese format. For Taiwan venues, fill location_address with the real Taiwanese address (e.g. "台北市中山區小民生東路3段1號") and set location_name accordingly. The tourism category applies when the event is designed to attract Japanese visitors to Taiwan.
7. For pricing: is_paid=false if free/無料/免費, is_paid=true if there's a fee, null if unknown.

ORGANIZER EXTRACTION RULES:
1. organizer: the primary entity hosting the event. Look for fields like 主催, 主辦, presented by, 主催者. Single string, original-language official name (e.g. "台北駐日経済文化代表処 台湾文化センター"). Do NOT include role labels like "主催:" in the value.
2. co_organizers: array of 共催 / 協力 / 後援 entities. Each entry is the original-language name. Empty array if none mentioned.
3. sponsors: array of 協賛 / 贊助 / sponsor entities. Empty array if none mentioned.
4. NEVER fabricate organizer names. If 主催 is not explicitly stated and cannot be safely inferred from the venue's official role (e.g. an exhibition at a museum is hosted by that museum), set organizer = null.
5. organizer_type: classify the primary organizer into one or more of:
   - "government" — central/local government bodies (外交部, 文化部, 都道府県, 市役所)
   - "semi_official" — TECRO offices, Taiwan Cultural Center, JICA-style 外郭団体
   - "cultural_institution" — museums, galleries, foundations, public theaters
   - "academic" — universities, research institutes, scholarly societies
   - "commercial_brand" — for-profit companies running brand events
   - "independent_venue" — independent cinemas, bookstores, live houses, cafés
   - "civic_group" — NPOs, alumni/diaspora associations, student clubs
   - "media" — publishers, newspapers, broadcasters
   - "unknown" — when organizer cannot be classified with confidence
   Multiple types are allowed (e.g. a university press conference = ["academic","media"]). When organizer is null, set organizer_type = ["unknown"].

EVENT FORM RULES:
event_form is the structural shape of the event, distinct from category (which is the topic).
Pick one or more from:
  exhibition, screening, lecture, performance, market, workshop,
  conference, networking, screening_with_talk, tour, competition, other
Decision guides:
- A film screening followed by a talk = ["screening_with_talk"] (NOT screening + lecture).
- Pure exhibition = ["exhibition"]; exhibition with opening lecture = ["exhibition","lecture"].
- 食フェス / 物産展 / 美食祭 / マルシェ = ["market"].
- 学会大会 with multiple paper sessions = ["conference"]; single 講演会 = ["lecture"].
- 体験講座 / ワークショップ / 手作り教室 / クラフト = ["workshop"].
- Trade show / business summit = ["conference"].
- LIVE concert, theater, dance = ["performance"].
- 交流会 / オフ会 / 懇親会 = ["networking"].
- ツアー / 巡迴 / 街歩き = ["tour"].
- コンテスト / コンクール / 公募 = ["competition"].
- If genuinely none apply = ["other"]. NEVER leave event_form empty.

LANGUAGE RULES:
1. primary_language: the language the event will primarily be conducted in.
   - "ja" — primarily Japanese (default for events in Japan unless stated otherwise)
   - "zh" — primarily Chinese / Mandarin / Taiwanese
   - "en" — primarily English
   - "mixed" — bilingual or trilingual format explicitly advertised (e.g. 日中通訳付き shown as a featured format, not a side support)
2. has_japanese_support: true if the event provides Japanese assistance (subtitle 字幕, simultaneous interpretation 同時通訳, consecutive interpretation 逐次通訳, bilingual handout 配布資料) when primary_language != "ja". Set false if primary_language="ja". Set null if unclear.
3. has_english_support: same logic for English. Most Japan-domestic events default to false. Only set true when explicitly advertised.
4. NEVER guess. If the source text gives no language signal at all, set primary_language=null and both support flags=null.

Respond with valid JSON matching this schema:
{
  "name_ja": "Japanese event name",
  "name_zh": "Traditional Chinese event name",
  "name_en": "English event name",
  "description_ja": "Japanese summary (2-4 sentences)",
  "description_zh": "Traditional Chinese summary (2-4 sentences)",
  "description_en": "English summary (2-4 sentences)",
  "category": ["senses"],
  "start_date": "2026-01-15T00:00:00" or null,
  "end_date": "2026-01-15T00:00:00" or null,
  "location_name": "venue name in Japanese (original)" or null,
  "location_name_zh": "venue name in Traditional Chinese" or null,
  "location_name_en": "venue name in English" or null,
  "location_address": "full address (original Japanese format)" or null,
  "location_address_zh": "address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is" or null,
  "location_address_en": "address in English (romanized city/area names; keep street number as-is)" or null,
  "business_hours": "opening hours in Japanese (original)" or null,
  "business_hours_zh": "opening hours in Traditional Chinese" or null,
  "business_hours_en": "opening hours in English" or null,
  "is_paid": false or true or null,
  "price_info": "price details" or null,
  "location_url": "official website URL of the venue, extracted from the text only — NEVER infer or hallucinate; set null if not explicitly stated" or null,
  "organizer": "primary host name in original language" or null,
  "co_organizers": ["co-host name", "..."],
  "sponsors": ["sponsor name", "..."],
  "organizer_type": ["semi_official"],
  "event_form": ["screening_with_talk"],
  "primary_language": "ja" or "zh" or "en" or "mixed" or null,
  "has_japanese_support": false or true or null,
  "has_english_support": false or true or null,
  "selection_reason": {
    "ja": "1-2文の日本語で、このイベントが台湿関連である理由と選定理由",
    "zh": "1-2句繁體中文，說明此活動與台灣的關聯及收錄原因",
    "en": "1-2 sentences in English explaining why this event is Taiwan-related and was selected"
  },
  "sub_events": [
    {
      "name_ja": "sub-event name in Japanese",
      "name_zh": "sub-event name in Traditional Chinese (繁體中文)",
      "name_en": "sub-event name in English",
      "description_ja": "brief description in Japanese",
      "description_zh": "brief description in Traditional Chinese (繁體中文)",
      "description_en": "brief description in English",
      "start_date": "2026-02-01T00:00:00",
      "end_date": "2026-02-01T00:00:00",
      "category": ["movie"],
      "location_name": "venue" or null,
      "location_address": "address" or null,
      "business_hours": "hours" or null,
      "is_paid": false or true or null,
      "price_info": "price" or null,
      "organizer": "host name" or null,
      "co_organizers": [],
      "sponsors": [],
      "organizer_type": ["unknown"],
      "event_form": ["other"],
      "primary_language": "ja" or "zh" or "en" or "mixed" or null,
      "has_japanese_support": false or true or null,
      "has_english_support": false or true or null
    }
  ]
}"""


def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _get_openai() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")
    return OpenAI(api_key=api_key)


def _annotate_one(client: OpenAI, raw_title: str, raw_description: str, feedback_prompt: str = "", sr_feedback_prompt: str = "") -> dict:
    """Send raw event data to GPT-4o-mini and return structured annotation."""
    system_content = SYSTEM_PROMPT + feedback_prompt + sr_feedback_prompt
    user_content = f"Raw Title: {raw_title or '(no title)'}\n\nRaw Description:\n{raw_description or '(no description)'}"

    # Truncate very long descriptions to stay within token limits
    if len(user_content) > 20000:
        user_content = user_content[:20000] + "\n\n[... truncated ...]"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )

    usage = response.usage  # may be None in rare cases
    text = response.choices[0].message.content
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        # Retry once with higher token budget
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=6000,
        )
        usage = response.usage
        return json.loads(response.choices[0].message.content), usage


def _validate_categories(cats: list) -> list[str]:
    """Filter to only valid category strings."""
    return [c for c in cats if isinstance(c, str) and c in VALID_CATEGORIES] or ["senses"]


VALID_ORGANIZER_TYPES = frozenset([
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media", "unknown",
])
VALID_EVENT_FORMS = frozenset([
    "exhibition", "screening", "lecture", "performance", "market", "workshop",
    "conference", "networking", "screening_with_talk", "tour", "competition", "other",
])
VALID_PRIMARY_LANGUAGES = frozenset(["ja", "zh", "en", "mixed"])


def _validate_organizer_types(vals) -> list[str]:
    return [v for v in (vals or []) if isinstance(v, str) and v in VALID_ORGANIZER_TYPES]


def _validate_event_forms(vals) -> list[str]:
    out = [v for v in (vals or []) if isinstance(v, str) and v in VALID_EVENT_FORMS]
    return out or ["other"]


def _validate_primary_language(val) -> str | None:
    return val if isinstance(val, str) and val in VALID_PRIMARY_LANGUAGES else None


def _validate_bool_or_none(val):
    return val if isinstance(val, bool) else None


_LECTURE_KEYWORDS = frozenset([
    # Japanese
    "座談", "講座", "座談会", "座談會",
    "トークイベント", "トークショー", "講演会", "講演",
    "シンポジウム", "勉強会", "例会", "基調講演",
    "映後座談", "セッション", "研究会", "フォーラム",
    # Combined patterns handled in injection below
])

_GEOPOLITICS_KEYWORDS = frozenset([
    "危機", "海峡", "独立", "民主化", "移民政策",
    "インド太平洋", "日台関係", "主権", "国際フォーラム",
    "給食政策", "デジタル政府", "行政×AI", "公共政策",
    "安全保障", "防衛",
])

_HISTORY_KEYWORDS = frozenset([
    "戦没", "植民地", "統治", "秘録", "同化", "傷痕",
    "アーカイブ", "慰霊", "戦争", "戦前", "戦後",
    "日本統治", "総督府", "霧のごとく", "大濛",
])


def _inject_keyword_categories(categories: list[str], text: str) -> list[str]:
    """Inject missing categories based on keyword signals in the event text.

    Rules derived from analysis of 69 admin corrections in category_corrections:
    - lecture: almost always missing when talk/panel keywords appear (+29 corrections)
    - geopolitics: missing for Taiwan political/policy topics (+18 corrections)
    - history: missing for colonial/war-era Taiwan events (+16 corrections)
    """
    cats = list(categories)
    # lecture: any talk/panel/seminar keyword triggers this
    if "lecture" not in cats and any(kw in text for kw in _LECTURE_KEYWORDS):
        cats.append("lecture")
    # lecture: also inject when movie + talk co-occur (上映会＋トーク pattern)
    if "lecture" not in cats and ("movie" in cats or "上映" in text) and (
        "トーク" in text or "座談" in text or "講演" in text
    ):
        cats.append("lecture")
    # geopolitics: Taiwan political/policy topics
    if "geopolitics" not in cats and any(kw in text for kw in _GEOPOLITICS_KEYWORDS):
        cats.append("geopolitics")
    # history: colonial/war-era Taiwan
    if "history" not in cats and any(kw in text for kw in _HISTORY_KEYWORDS):
        cats.append("history")
    return cats


def _load_default_organizer_map(sb: "Client") -> dict[str, dict[str, str]]:
    """Load per-source fallback organizer from research_sources (migration 039).

    Returns {scraper_source_name: {"organizer": ..., "organizer_type": ...}}.
    Returns an empty dict on any error (e.g. migration not yet applied).
    """
    try:
        res = (
            sb.table("research_sources")
            .select("scraper_source_name,default_organizer,default_organizer_type")
            .execute()
        )
        result: dict[str, dict[str, str]] = {}
        for row in res.data or []:
            key = row.get("scraper_source_name")
            org = row.get("default_organizer")
            if key and org:
                result[key] = {
                    "organizer": org,
                    "organizer_type": row.get("default_organizer_type") or "",
                }
        return result
    except Exception:
        return {}


def annotate_pending_events(re_annotate_all: bool = False, fix_translations: bool = False, fix_reviewed: bool = False, event_id: str | None = None, limit: int | None = None) -> None:
    """Fetch pending events from DB, annotate with AI, and update."""
    sb = _get_supabase()
    ai = _get_openai()
    annotation_start = time.time()

    # Load category feedback from admin corrections (for few-shot examples in AI prompt)
    corrections = load_corrections(sb)
    feedback_prompt = build_feedback_prompt(corrections)
    if corrections:
        logger.info("Loaded %d category corrections as few-shot examples", len(corrections))

    # Load selection_reason corrections for few-shot guidance (P3.3 — migration 040).
    sr_corrections = load_sr_corrections(sb)
    sr_feedback_prompt = build_sr_feedback_prompt(sr_corrections)
    if sr_corrections:
        logger.info("Loaded %d selection_reason correction examples", len(sr_corrections))

    # Load full event_id → corrected_category map so the annotator can
    # apply human corrections directly and skip AI category prediction.
    # This ensures re-annotation never overwrites manually corrected categories.
    all_corrections_res = sb.table("category_corrections").select("event_id,corrected_category").execute()
    human_category_map: dict[str, list[str]] = {
        r["event_id"]: r["corrected_category"]
        for r in (all_corrections_res.data or [])
        if r.get("corrected_category")
    }
    if human_category_map:
        logger.info("Loaded %d human-corrected category overrides", len(human_category_map))

    # Load field-level corrections (migration 038b — P1).
    # Builds: event_id → set of DB column names that must NOT be overwritten by AI.
    # Falls back to empty dict when the table doesn't exist yet (pre-migration).
    human_field_map: dict[str, set[str]] = {}
    try:
        fc_res = sb.table("field_corrections").select("event_id,field_name").execute()
        for r in (fc_res.data or []):
            eid_fc = r.get("event_id")
            fname = r.get("field_name")
            if eid_fc and fname:
                human_field_map.setdefault(eid_fc, set()).add(fname)
        if human_field_map:
            logger.info("Loaded field corrections for %d events", len(human_field_map))
    except Exception as fc_err:
        logger.debug("field_corrections table not available (run migration 038b): %s", fc_err)
    # Used as fallback when GPT returns organizer=null.
    _default_org_map = _load_default_organizer_map(sb)
    if _default_org_map:
        logger.info("Loaded %d source default organizers", len(_default_org_map))

    # Fetch events to annotate
    # Always exclude 'reviewed' events — they are human-confirmed and must not be
    # overwritten by AI even when --all is used.
    # Exception: --fix-reviewed specifically targets reviewed events missing translations.
    if event_id:
        # --id: process a single specific event regardless of its annotation_status.
        # Never process reviewed events — they are human-confirmed.
        query = (
            sb.table("events")
            .select("*")
            .eq("id", event_id)
            .neq("annotation_status", "reviewed")
        )
    elif fix_reviewed:
        # --fix-reviewed: fill translation fields for reviewed events that have name_zh or name_en missing.
        # Does NOT touch category or status — reviewed status is preserved.
        query = (
            sb.table("events")
            .select("*")
            .eq("annotation_status", "reviewed")
            .or_("name_zh.is.null,name_en.is.null")
        )
    else:
        query = sb.table("events").select("*").neq("annotation_status", "reviewed")
        if re_annotate_all:
            # --all: re-annotate all active non-reviewed events regardless of status.
            # Exclude sub-events (parent_event_id IS NOT NULL) — they are created by the
            # annotator itself and must not be re-processed as root events (would produce
            # grandchild events with source_id like gnews_xxx_sub1_sub1).
            query = query.eq("is_active", True).is_("parent_event_id", "null")
        elif fix_translations:
            # --fix-translations: re-annotate active events missing zh/en fields.
            # Exclude sub-events for the same reason as --all.
            query = query.eq("is_active", True).is_("parent_event_id", "null").or_(
                "name_zh.is.null,name_en.is.null,description_zh.is.null,description_en.is.null"
            )
        else:
            # default: process all pending events regardless of is_active.
            # Sub-events are always upserted as 'annotated' by the annotator, so
            # pending sub-events should not exist in practice. The filter is a safety net.
            query = query.eq("annotation_status", "pending").is_("parent_event_id", "null")

    result = query.order("created_at", desc=True).execute()
    events = result.data
    if events and limit is not None:
        events = events[:limit]

    if not events:
        logger.info("No pending events to annotate.")
        return

    logger.info("Found %d events to annotate", len(events))

    # Accumulate usage for scraper_runs logging
    total_tokens_in = 0
    total_tokens_out = 0
    events_ok = 0
    field_protect_hits: int = 0  # P4 #5: count of fields protected by field_corrections table

    # Count how many google_news_rss events need article fetch.
    # Fetch when start_date is missing (original case) OR raw_description is
    # thin (< _GNEWS_THIN_DESC_CHARS) — thin means the scraper only captured
    # a headline with no article body, leaving GPT without enough context for
    # dates, location, and categories.
    _GNEWS_THIN_DESC_CHARS = 400

    def _gnews_needs_article_fetch(e: dict) -> bool:
        if e.get("source_name") != "google_news_rss":
            return False
        if not e.get("start_date"):
            return True
        return len(e.get("raw_description") or "") < _GNEWS_THIN_DESC_CHARS

    gnews_needs_fetch = sum(1 for e in events if _gnews_needs_article_fetch(e))
    # Launch a single Playwright browser for all google_news_rss article fetches
    # to avoid per-event browser startup overhead.
    _pw_context = None
    _pw_browser: "Browser | None" = None
    if gnews_needs_fetch > 0:
        logger.info(
            "Launching Playwright browser for %d google_news_rss article fetch(es)",
            gnews_needs_fetch,
        )
        _pw_context = sync_playwright().start()
        _pw_browser = _pw_context.chromium.launch()

    for i, event in enumerate(events, 1):
        eid = event["id"]
        raw_title = event.get("raw_title") or event.get("name_ja") or ""
        raw_desc = event.get("raw_description") or event.get("description_ja") or ""

        # ── Deterministic venue pre-extraction ─────────────────────────────
        # Extract 会場：/場所：lines from raw_description before GPT runs.
        # Fills the gap when scrapers leave location_name = None but embed
        # venue info in the body text (e.g. hakusuisha, some koryu events).
        _venue_pre = _extract_venue_from_raw(raw_desc)
        _pre_location_name: str | None = event.get("location_name") or _venue_pre.get("location_name")
        _pre_location_address: str | None = event.get("location_address") or _venue_pre.get("location_address")
        _pre_hours: str | None = _extract_hours_from_raw(raw_desc)
        # hakusuisha thin-content rescue: if raw_description contains no
        # 日時 keyword and pre-extraction found nothing, re-fetch via HTTP
        # fallback with improved skip-tags parser (4000 char budget).
        if (
            event.get("source_name") == "hakusuisha"
            and not _pre_location_name
            and not _pre_hours
            and "日時" not in (raw_desc or "")
        ):
            _fallback_url = event.get("source_url") or ""
            if _fallback_url:
                try:
                    from sources.hakusuisha import (
                        _fetch_detail_text_fallback as _haku_fb,
                    )
                    _rescued = _haku_fb(_fallback_url)
                    if _rescued and len(_rescued) > 200:
                        raw_desc = _rescued
                        _venue_pre = _extract_venue_from_raw(raw_desc)
                        _pre_location_name = (
                            event.get("location_name")
                            or _venue_pre.get("location_name")
                        )
                        _pre_location_address = (
                            event.get("location_address")
                            or _venue_pre.get("location_address")
                        )
                        _pre_hours = _extract_hours_from_raw(raw_desc)
                        logger.info(
                            "hakusuisha thin-content rescue applied for %s",
                            event["id"][:8],
                        )
                except Exception as _haku_exc:
                    logger.debug(
                        "hakusuisha thin-content rescue failed for %s: %s",
                        event.get("id", "")[:8],
                        _haku_exc,
                    )
        # ───────────────────────────────────────────────────────────────────

        # For google_news_rss events, fetch the full article body when:
        #   (a) start_date is missing — GPT needs article text to find dates
        #   (b) raw_description is thin (< _GNEWS_THIN_DESC_CHARS) — the scraper
        #       only captured a headline; GPT can't extract dates/location/category
        #       from a single line even if start_date was set (possibly wrong).
        # raw_description in DB is intentionally NOT updated — the fetched text
        # is only used for this annotation pass.
        if _gnews_needs_article_fetch(event) and _pw_browser is not None:
            source_url = event.get("source_url", "")
            logger.info("  → Fetching article body from %s", source_url[:80])
            article_text = _fetch_gnews_article_text(source_url, _pw_browser)
            if article_text:
                logger.info("  → Article fetched (%d chars), replacing raw_desc for GPT", len(article_text))
                raw_desc = article_text
            else:
                logger.info("  → Article fetch failed, proceeding with original raw_desc")

        logger.info("[%d/%d] Annotating: %s", i, len(events), raw_title[:60])

        try:
            annotation, usage = _annotate_one(ai, raw_title, raw_desc, feedback_prompt, sr_feedback_prompt)
            if usage:
                total_tokens_in += usage.prompt_tokens or 0
                total_tokens_out += usage.completion_tokens or 0

            # Validate and sanitize
            categories = _validate_categories(annotation.get("category", []))
            categories = _inject_keyword_categories(categories, raw_title + " " + raw_desc)

            # Override with human-corrected category if one exists — this takes
            # priority over AI prediction and keyword injection.
            if eid in human_category_map:
                human_cats = human_category_map[eid]
                if human_cats != categories:
                    logger.info("  → Applying human-corrected category: %s (AI predicted: %s)",
                                human_cats, categories)
                categories = human_cats

            # P0 field-protection: in normal re-annotation mode (not --all / --id),
            # preserve non-null DB values that were already set — either by a scraper
            # or by admin via confirm-report partial field correction.
            # Rationale: when admin corrects field A but leaves field B for re-annotation,
            # annotation_status becomes 'pending'. Annotator re-runs and overwrites A
            # (admin correction lost) unless we check for existing non-null values first.
            _protect = not re_annotate_all and event_id is None

            # P1 field-protection: honour field_corrections table (migration 038b).
            # Any (event_id, field_name) pair in human_field_map was explicitly corrected
            # by an admin and must NEVER be overwritten by AI output.
            _human_protected: set[str] = human_field_map.get(eid, set())

            def _ai_or_existing(fname: str, ai_val: Any) -> Any:
                """Use AI value for null DB fields; keep DB value when protect mode active.
                Always defer to human_field_map entries regardless of protect mode."""
                nonlocal field_protect_hits
                if fname in _human_protected:
                    # Human explicitly corrected this field — never overwrite
                    field_protect_hits += 1
                    return event.get(fname)
                if _protect:
                    existing = event.get(fname)
                    if existing is not None:
                        return existing
                return ai_val

            # Helper: convert empty-string GPT outputs to None so that
            # the web fallback chain (ja→zh→en) works correctly.
            def _str(val: Any) -> str | None:
                return val if isinstance(val, str) and val.strip() else None

            # Helper: clean location strings — GPT sometimes includes the label
            # separator (e.g. "会場：" → "：台北…"). Strip any leading ：；:; chars.
            def _loc(val: Any) -> str | None:
                s = _str(val)
                if s:
                    s = s.lstrip("：；:; \u3000")
                return s or None

            # GPT-4o-mini occasionally outputs Simplified Chinese characters in
            # location_address_zh even when instructed to use Traditional Chinese
            # (e.g. "东京都千代田区" instead of "東京都千代田區"). Apply a targeted
            # character-level substitution for the most common offenders in Japanese
            # GPT-4o-mini occasionally outputs Simplified Chinese characters
            # even when instructed to use Traditional Chinese. Apply a targeted
            # character-level substitution for the most common offenders so ALL
            # *_zh fields are always Traditional Chinese.
            _SIMP_TO_TRAD = str.maketrans({
                # Location-related (from production scan 2026-04-26)
                "东": "東", "区": "區", "内": "內", "园": "園",
                "来": "來", "长": "長", "进": "進", "实": "實",
                "诺": "諾", "厅": "廳", "络": "絡", "设": "設",
                "联": "聯", "馆": "館", "门": "門", "发": "發",
                "会": "會",
                # Description-related (from production scan 2026-05-02)
                "个": "個", "记": "記", "构": "構", "传": "傳",
                "经": "經", "验": "驗", "弥": "彌", "脆": "脆",
                "与": "與", "对": "對",
                # Additional common GPT simplified outputs
                "这": "這", "说": "說", "时": "時", "问": "問",
                "关": "關", "现": "現", "变": "變", "还": "還",
                "单": "單", "层": "層", "达": "達",
                "让": "讓", "认": "認", "为": "為", "总": "總",
                "辑": "輯", "视": "視", "历": "歷", "强": "強",
                "调": "調", "节": "節", "约": "約", "运": "運",
                "动": "動", "办": "辦", "报": "報", "导": "導",
                "环": "環", "义": "義", "务": "務", "战": "戰",
                "组": "組", "织": "織", "国": "國", "际": "際",
                "临": "臨", "产": "產", "业": "業", "属": "屬",
                "创": "創", "据": "據", "体": "體", "点": "點",
                "击": "擊", "继": "繼", "续": "續", "阅": "閱",
                "读": "讀", "开": "開", "艺": "藝", "术": "術",
                "观": "觀", "众": "眾", "场": "場", "举": "舉",
                "行": "行",  # 行 is same in both — skip
                "声": "聲", "乐": "樂", "画": "畫", "获": "獲",
                "奖": "獎", "选": "選", "赛": "賽", "参": "參",
                "团": "團", "电": "電", "影": "影",  # 影 same — skip
                "热": "熱", "爱": "愛", "岛": "島",
                "独": "獨", "虑": "慮", "忆": "憶", "仅": "僅",
                "尝": "嘗", "试": "試", "谈": "談", "请": "請",
                "龙": "龍", "丰": "豐", "华": "華", "灵": "靈",
                "纪": "紀", "录": "錄", "极": "極", "标": "標",
                "准": "準", "规": "規", "模": "模",  # 模 same — skip
                "细": "細", "带": "帶", "广": "廣", "庆": "慶",
                "响": "響", "惊": "驚", "显": "顯", "难": "難",
                "类": "類", "宝": "寶", "贵": "貴", "丽": "麗",
                "尽": "盡", "挡": "擋",
                # Additional chars found in 1e375d6c full-simplified event (2026-05-02)
                "将": "將", "断": "斷", "湾": "灣", "览": "覽",
                "间": "間", "气": "氣", "坛": "壇", "静": "靜",
                "满": "滿", "简": "簡", "洁": "潔", "优": "優",
                "连": "連",  # 系: skip — valid trad in 系統/系列
                "志": "志",  # same — skip
                "份": "份",  # same — skip
                "沉": "沉",  # same — skip
                "品": "品",  # same — skip
                "释": "釋", "迹": "跡", "坛": "壇", "态": "態",
                "仪": "儀", "宫": "宮", "奇": "奇",  # same — skip
                "壮": "壯", "汇": "匯", "灯": "燈", "蕴": "蘊",
                "韵": "韻", "须": "須", "恳": "懇",
                # Common GPT outputs: general vocabulary
                "统": "統", "种": "種", "学": "學", "数": "數",
                "编": "編", "价": "價", "乡": "鄉", "网": "網",
                "绍": "紹", "预": "預", "称": "稱", "评": "評",
                "议": "議", "论": "論", "结": "結", "处": "處",
                "应": "應", "集": "集",  # 集 same — skip
                # 着: skip — valid trad as particle (保持着)
                "乐": "樂", "欢": "歡",
            })
            # Remove identity mappings (same char in both)
            _SIMP_TO_TRAD = {k: v for k, v in _SIMP_TO_TRAD.items() if k != v}
            _SIMP_TO_TRAD = str.maketrans(_SIMP_TO_TRAD)

            def _to_trad(val: str | None) -> str | None:
                """Normalize any Simplified Chinese chars to Traditional."""
                if not val:
                    return val
                return val.translate(_SIMP_TO_TRAD)

            def _loc_zh(val: Any) -> str | None:
                """Clean location string and normalize Simplified→Traditional chars."""
                s = _loc(val)
                return _to_trad(s)

            if fix_reviewed:
                # --fix-reviewed mode: only write translation fields; preserve
                # annotation_status='reviewed', category, dates, and all other
                # human-confirmed fields.
                update_data: dict[str, Any] = {
                    "name_zh": _to_trad(_str(annotation.get("name_zh"))),
                    "name_en": _str(annotation.get("name_en")),
                    "description_zh": _to_trad(_str(annotation.get("description_zh"))),
                    "description_en": _str(annotation.get("description_en")),
                    "annotation_status": "reviewed",  # keep reviewed — do NOT downgrade
                    "annotated_at": datetime.utcnow().isoformat(),
                }
                # Remove keys whose value is None so we don't clobber existing data
                update_data = {k: v for k, v in update_data.items() if v is not None or k == "annotation_status"}
                # Fill business_hours from raw_description if currently null.
                # Deterministic extraction only — safe to apply to reviewed events.
                if not event.get("business_hours"):
                    _rh = _extract_hours_from_raw(event.get("raw_description") or "")
                    if _rh:
                        update_data["business_hours"] = _rh
            else:
                update_data: dict[str, Any] = {
                    # name_ja is NEVER overwritten by GPT (2026-05-02 policy).
                    # Always preserve the scraper's original title.
                    # GPT's name_ja is only consumed for sub-events.
                    "name_ja": event.get("name_ja") or raw_title,
                    "name_zh": _to_trad(_str(annotation.get("name_zh"))),
                    "name_en": _str(annotation.get("name_en")),
                    "description_ja": _str(annotation.get("description_ja")),
                    "description_zh": _to_trad(_str(annotation.get("description_zh"))),
                    "description_en": _str(annotation.get("description_en")),
                    "category": categories,
                    # Scraper-set dates take precedence over GPT inference.
                    # GPT fills in only when the scraper found no date at all.
                    "start_date": event.get("start_date") or annotation.get("start_date"),
                    "end_date": event.get("end_date") or annotation.get("end_date"),
                    # Scraper-set location/hours/paid take precedence over GPT inference.
                    # GPT only fills in when the scraper left the field empty.
                    "location_name": _loc(event.get("location_name")) or _loc(_pre_location_name) or _loc(annotation.get("location_name")),
                    "location_address": _loc(event.get("location_address")) or _loc(_pre_location_address) or _loc(annotation.get("location_address")),
                    "business_hours": event.get("business_hours") or _pre_hours or annotation.get("business_hours"),
                    "is_paid": event.get("is_paid") if event.get("is_paid") is not None else annotation.get("is_paid"),
                    "price_info": annotation.get("price_info") or event.get("price_info"),
                    "organizer": (
                        _str(annotation.get("organizer"))
                        or event.get("organizer")
                        or (_default_org_map.get(event.get("source_name") or "", {}).get("organizer"))
                    ),
                    "co_organizers": [s for s in (annotation.get("co_organizers") or []) if isinstance(s, str)],
                    "sponsors": [s for s in (annotation.get("sponsors") or []) if isinstance(s, str)],
                    "organizer_type": (
                        _validate_organizer_types(annotation.get("organizer_type", []))
                        if (annotation.get("organizer_type") or ["unknown"]) != ["unknown"]
                        else (
                            [_default_org_map[event.get("source_name") or ""]["organizer_type"]]
                            if (
                                event.get("source_name") in _default_org_map
                                and _default_org_map[event.get("source_name") or ""].get("organizer_type")
                                and not _str(annotation.get("organizer"))
                                and not event.get("organizer")
                            )
                            else _validate_organizer_types(annotation.get("organizer_type", []))
                        )
                    ),
                    "event_form": _validate_event_forms(annotation.get("event_form", [])),
                    "primary_language": _validate_primary_language(annotation.get("primary_language")),
                    "has_japanese_support": _validate_bool_or_none(annotation.get("has_japanese_support")),
                    "has_english_support": _validate_bool_or_none(annotation.get("has_english_support")),
                    "annotation_status": "annotated",
                    "annotated_at": datetime.utcnow().isoformat(),
                }

            # Localized location/hours fields added in migration 010.
            # Kept separate so the primary update above never fails on old DB schemas.
            localized_location_data: dict[str, Any] = {
                "location_name_zh": _loc_zh(annotation.get("location_name_zh")),
                "location_name_en": _loc(annotation.get("location_name_en")),
                "location_address_zh": _loc_zh(annotation.get("location_address_zh")),
                "location_address_en": _loc(annotation.get("location_address_en")),
                "business_hours_zh": _to_trad(_str(annotation.get("business_hours_zh"))),
                "business_hours_en": _str(annotation.get("business_hours_en")),
            }
            # Only send non-null values; in protect mode also skip fields where DB
            # already has a non-null value (admin-corrected localized location fields).
            # Also skip any field in _human_protected (explicitly corrected by admin).
            localized_location_data = {
                k: v for k, v in localized_location_data.items()
                if v is not None
                and k not in _human_protected
                and not (_protect and event.get(k) is not None)
            }

            # Ensure end_date is not null when start_date exists (skip in fix_reviewed mode)
            if not fix_reviewed and update_data.get("start_date") and not update_data.get("end_date"):
                update_data["end_date"] = update_data["start_date"]

            # location_url: scraper value first, then GPT-extracted from text.
            # Added conditionally so null never overwrites an admin-entered value.
            if not fix_reviewed:
                _loc_url = event.get("location_url") or _str(annotation.get("location_url"))
                if _loc_url:
                    update_data["location_url"] = _loc_url

            # Try to include selection_reason (column may not exist yet)
            selection_reason = annotation.get("selection_reason")
            if selection_reason:
                # If AI returned a multilingual dict, JSON-encode it
                if isinstance(selection_reason, dict):
                    selection_reason = json.dumps(selection_reason, ensure_ascii=False)
                update_data["selection_reason"] = selection_reason

            sb.table("events").update(update_data).eq("id", eid).execute()
            events_ok += 1
            logger.info("  ✓ annotated (categories: %s)", categories)

            # Apply localized location/hours fields separately — columns were added
            # in migration 010 and may not exist on older DB schemas.
            if localized_location_data:
                try:
                    sb.table("events").update(localized_location_data).eq("id", eid).execute()
                except Exception as loc_err:
                    logger.warning("  ⚠ localized location update skipped (run migration 010): %s", loc_err)

            # Handle sub-events
            sub_events = annotation.get("sub_events", [])
            # Pre-fetch existing sub-events to preserve name_ja on re-annotation
            # (same preservation policy as parent events — GPT may rewrite katakana to kanji).
            existing_subs_res = sb.table("events").select(
                "source_id,name_ja,raw_title"
            ).eq("parent_event_id", eid).execute()
            _existing_subs = {e["source_id"]: e for e in (existing_subs_res.data or [])}

            for j, sub in enumerate(sub_events):
                sub_cats = _validate_categories(sub.get("category", categories))
                sub_cats = _inject_keyword_categories(sub_cats, sub.get("name_ja", "") + " " + (sub.get("description_ja") or ""))
                sub_start = sub.get("start_date")
                sub_end = sub.get("end_date") or sub_start

                sub_source_id = f"{event['source_id']}_sub{j+1}"
                _prev = _existing_subs.get(sub_source_id)
                # Preserve existing name_ja/raw_title on re-annotation
                sub_name_ja = (_prev["name_ja"] if _prev else None) or sub.get("name_ja", "")
                sub_raw_title = (_prev["raw_title"] if _prev else None) or sub.get("name_ja", "")

                sub_row = {
                    "source_name": event["source_name"],
                    "source_id": sub_source_id,
                    "source_url": event["source_url"],
                    "original_language": event.get("original_language", "ja"),
                    "name_ja": sub_name_ja,
                    "name_zh": _to_trad(sub.get("name_zh")),
                    "name_en": sub.get("name_en"),
                    "description_ja": sub.get("description_ja"),
                    "description_zh": _to_trad(sub.get("description_zh")),
                    "description_en": sub.get("description_en"),
                    "category": sub_cats,
                    "start_date": sub_start,
                    "end_date": sub_end,
                    "location_name": sub.get("location_name") or update_data["location_name"],
                    "location_address": sub.get("location_address") or update_data["location_address"],
                    "business_hours": sub.get("business_hours") or update_data["business_hours"],
                    "is_paid": sub.get("is_paid") if sub.get("is_paid") is not None else update_data["is_paid"],
                    "price_info": sub.get("price_info") or update_data["price_info"],
                    "organizer": _str(sub.get("organizer")) or update_data.get("organizer"),
                    "co_organizers": [s for s in (sub.get("co_organizers") or []) if isinstance(s, str)],
                    "sponsors": [s for s in (sub.get("sponsors") or []) if isinstance(s, str)],
                    "organizer_type": _validate_organizer_types(sub.get("organizer_type", [])) or update_data.get("organizer_type", []),
                    "event_form": _validate_event_forms(sub.get("event_form", [])),
                    "primary_language": _validate_primary_language(sub.get("primary_language")) or update_data.get("primary_language"),
                    "has_japanese_support": _validate_bool_or_none(sub.get("has_japanese_support")),
                    "has_english_support": _validate_bool_or_none(sub.get("has_english_support")),
                    "is_active": True,
                    "parent_event_id": eid,
                    "raw_title": sub_raw_title,
                    "raw_description": sub.get("description_ja"),
                    "annotation_status": "annotated",
                    "annotated_at": datetime.utcnow().isoformat(),
                    # Inherit parent's scraped_at so the admin クロール日時 column
                    # shows a meaningful value instead of NULL for sub-events.
                    "scraped_at": event.get("scraped_at"),
                }

                sb.table("events").upsert(
                    sub_row, on_conflict="source_name,source_id"
                ).execute()

                # Also try localized location fields for sub-events (migration 010)
                sub_loc = {k: v for k, v in {
                    "location_name_zh": _loc_zh(sub.get("location_name_zh")) or localized_location_data.get("location_name_zh"),
                    "location_name_en": _loc(sub.get("location_name_en")) or localized_location_data.get("location_name_en"),
                    "location_address_zh": _loc_zh(sub.get("location_address_zh")) or localized_location_data.get("location_address_zh"),
                    "location_address_en": _loc(sub.get("location_address_en")) or localized_location_data.get("location_address_en"),
                    "business_hours_zh": _str(sub.get("business_hours_zh")) or localized_location_data.get("business_hours_zh"),
                    "business_hours_en": _str(sub.get("business_hours_en")) or localized_location_data.get("business_hours_en"),
                }.items() if v is not None}
                if sub_loc:
                    try:
                        # Get the upserted sub-event id
                        sub_result = sb.table("events").select("id").eq("source_name", event["source_name"]).eq("source_id", f"{event['source_id']}_sub{j+1}").single().execute()
                        if sub_result.data:
                            sb.table("events").update(sub_loc).eq("id", sub_result.data["id"]).execute()
                    except Exception:
                        pass  # migration 010 not applied yet, skip silently

                logger.info("  + sub-event %d: %s", j + 1, sub.get("name_ja", "")[:50])

            # After all sub-events are created, aggregate prefecture names and
            # update parent event's location_prefectures (migration 012).
            # Only write when 2+ distinct prefectures are found.
            if sub_events and not fix_reviewed:
                prefectures = sorted({
                    p for sub in sub_events
                    if (p := _extract_prefecture(sub.get("location_address")))
                })
                if len(prefectures) >= 2:
                    try:
                        sb.table("events").update(
                            {"location_prefectures": prefectures}
                        ).eq("id", eid).execute()
                        logger.info("  → location_prefectures: %s", prefectures)
                    except Exception as lp_err:
                        logger.warning(
                            "  ⚠ location_prefectures update skipped (run migration 012): %s", lp_err
                        )

        except Exception as exc:
            logger.error("  ✗ annotation failed: %s", exc)
            sb.table("events").update({
                "annotation_status": "error",
            }).eq("id", eid).execute()

        # Rate limiting — avoid hitting OpenAI too fast
        time.sleep(0.5)

    # Close Playwright browser if it was opened for google_news_rss fetches
    if _pw_browser is not None:
        try:
            _pw_browser.close()
        except Exception:
            pass
    if _pw_context is not None:
        try:
            _pw_context.stop()
        except Exception:
            pass

    # -------------------------------------------------------------------
    # Write scraper_runs record
    # GPT-4o-mini pricing: $0.15 / 1M input tokens, $0.60 / 1M output tokens
    # -------------------------------------------------------------------
    cost = (total_tokens_in * 0.15 + total_tokens_out * 0.60) / 1_000_000
    try:
        sb.table("scraper_runs").insert({
            "source": "annotator",
            "events_processed": events_ok,
            "openai_tokens_in": total_tokens_in,
            "openai_tokens_out": total_tokens_out,
            "cost_usd": round(cost, 6),
            "duration_seconds": int(time.time() - annotation_start),
            "notes": f"re_annotate_all={re_annotate_all}, fix_translations={fix_translations}, fix_reviewed={fix_reviewed}, total={len(events)}, field_protect_hits={field_protect_hits}",
        }).execute()
        logger.info(
            "scraper_runs logged: %d events, %d in / %d out tokens, $%.6f",
            events_ok, total_tokens_in, total_tokens_out, cost,
        )
    except Exception as exc:
        logger.warning("Could not write scraper_runs (table may not exist yet): %s", exc)

    logger.info("Annotation complete.")


def enrich_movie_titles() -> None:
    """Look up official zh/en movie titles from eiga.com and overwrite all
    AI-translated names.

    Strategy:
    - Query ALL movie events where annotation_status != 'reviewed'.
      eiga_com is exempt — it already has native original-title parsing.
    - For news-source events (google_news_rss / prtimes / nhk_rss):
        extract the movie title from 「…」/『…』 brackets in raw_title.
    - For all other sources: use name_ja (fallback: raw_title).
    - If eiga.com returns an official title → overwrite name_zh AND name_en,
      even if they already contain a GPT translation.
    - 'reviewed' events are never touched.
    - Does NOT change annotation_status.
    """
    sb = _get_supabase()

    res = (
        sb.table("events")
        .select(
            "id,name_ja,raw_title,name_zh,name_en,"
            "description_zh,description_en,annotation_status,source_name"
        )
        .contains("category", ["movie"])
        .neq("annotation_status", "reviewed")
        .neq("source_name", "eiga_com")
        .execute()
    )
    events = res.data or []
    logger.info(
        "enrich_movie_titles: %d candidate events (excluding eiga_com + reviewed)",
        len(events),
    )

    patched = 0
    for event in events:
        source = event.get("source_name", "")

        # News sources: extract title from 「…」/『…』 brackets in raw_title.
        # raw_title is often a plain news headline (no brackets), so fall back
        # to name_ja before giving up.
        if source in _NEWS_MOVIE_SOURCES:
            raw = event.get("raw_title") or ""
            m = _BRACKET_TITLE_RE.search(raw)
            if not m:
                m = _BRACKET_TITLE_RE.search(event.get("name_ja") or "")
            title = m.group(1).strip() if m else ""
        else:
            title = event.get("name_ja") or event.get("raw_title") or ""

        if not title:
            continue

        name_zh, name_en = lookup_movie_titles(title)
        if not name_zh and not name_en:
            continue

        old_name_zh = event.get("name_zh") or ""
        old_name_en = event.get("name_en") or ""

        update: dict[str, Any] = {}
        if name_zh:
            update["name_zh"] = name_zh
        if name_en:
            update["name_en"] = name_en

        # Also fix description fields that still reference the old (wrong) title.
        # For news sources we additionally try replacing the Japanese lookup title
        # that appears in brackets in the description.
        if name_zh:
            desc_zh = event.get("description_zh") or ""
            if desc_zh:
                old_refs_zh = (
                    [old_name_zh, title]
                    if source in _NEWS_MOVIE_SOURCES
                    else [old_name_zh]
                )
                new_desc_zh = _replace_title_in_desc(desc_zh, old_refs_zh, name_zh)
                if new_desc_zh != desc_zh:
                    update["description_zh"] = new_desc_zh

        if name_en:
            desc_en = event.get("description_en") or ""
            if desc_en:
                new_desc_en = _replace_title_in_desc(desc_en, [old_name_en], name_en)
                if new_desc_en != desc_en:
                    update["description_en"] = new_desc_en

        sb.table("events").update(update).eq("id", event["id"]).execute()
        patched += 1
        logger.info(
            "  ✓ %s/%s [%s] → zh=%r en=%r desc_zh_fixed=%s desc_en_fixed=%s",
            source, event["id"][:8], title[:40], name_zh, name_en,
            "description_zh" in update, "description_en" in update,
        )

    logger.info("enrich_movie_titles: patched %d/%d events", patched, len(events))


_PERSON_FIX_PROMPT = """你是翻譯校對專家。以下中文描述中的人名可能是從日文片假名音譯而來的錯誤翻譯。
請根據正確名單，將描述中的錯誤音譯人名替換為正確的中文名。

規則：
- 只修改人名，不要改動其他任何內容（包括標點、格式、用詞）
- 如果描述中已經使用了正確的中文名，不要改動
- 如果找不到需要修改的人名，原樣返回描述
- 只輸出修正後的描述，不要加任何說明

正確名單：
{mapping}

描述：
{desc}"""


def _fix_person_names_gpt(
    client: OpenAI, desc: str, name_mappings: list[tuple[str, str, str]]
) -> str | None:
    """Use GPT-4o-mini to replace wrong phonetic person names in desc_zh.

    name_mappings: list of (role, ja_name, correct_zh_name) tuples.
    Returns the fixed description, or None if no change.
    """
    mapping_lines = "\n".join(
        f"- {role}：{zh_name}（日文：{ja_name}）"
        for role, ja_name, zh_name in name_mappings
    )
    prompt = _PERSON_FIX_PROMPT.format(mapping=mapping_lines, desc=desc)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=len(desc) + 200,
        )
        fixed = response.choices[0].message.content.strip()
        return fixed if fixed != desc else None
    except Exception as exc:
        logger.warning("_fix_person_names_gpt error: %s", exc)
        return None


def enrich_person_names() -> None:
    """Look up official Chinese/English names for people in ALL events
    and fix wrong phonetic translations in descriptions.

    Strategy:
    - Movie events (excl. eiga_com): use eiga.com movie page to get
      structured cast/crew list, then look up each via Wikipedia.
    - Non-movie events: extract katakana foreign names (with ・) from
      raw_description, look up each via eiga.com person search + Wikipedia.
    - In description_zh: use GPT-4o-mini to replace wrong phonetic
      translations with correct Chinese names.
    - In description_en: direct-replace katakana names with English names.
    - 'reviewed' events are never touched.
    - Does NOT change annotation_status.
    """
    sb = _get_supabase()
    client = _get_openai()

    res = (
        sb.table("events")
        .select(
            "id,name_ja,raw_title,raw_description,name_zh,name_en,"
            "description_zh,description_en,annotation_status,source_name,category"
        )
        .neq("annotation_status", "reviewed")
        .neq("source_name", "eiga_com")
        .execute()
    )
    events = res.data or []
    logger.info(
        "enrich_person_names: %d candidate events (excluding eiga_com + reviewed)",
        len(events),
    )

    patched = 0
    for event in events:
        source = event.get("source_name", "")
        categories = event.get("category") or []
        is_movie = "movie" in categories

        # --- Resolve person names based on event type ---
        people: dict[str, "PersonInfo"] = {}

        if is_movie:
            # Movie events: structured lookup via eiga.com movie page
            if source in _NEWS_MOVIE_SOURCES:
                raw = event.get("raw_title") or ""
                m = _BRACKET_TITLE_RE.search(raw)
                if not m:
                    m = _BRACKET_TITLE_RE.search(event.get("name_ja") or "")
                title = m.group(1).strip() if m else ""
            else:
                title = event.get("name_ja") or event.get("raw_title") or ""
            if title:
                people = lookup_person_names(title)
        else:
            # Non-movie events: extract katakana names from text
            raw_desc = event.get("raw_description") or ""
            raw_title = event.get("raw_title") or event.get("name_ja") or ""
            text = f"{raw_title}\n{raw_desc}"
            katakana_names = extract_katakana_names(text)
            for name in katakana_names:
                info = lookup_single_person(name)
                if info:
                    people[name] = info

        if not people:
            continue

        update: dict[str, Any] = {}

        # Fix desc_zh using GPT (phonetic translations can't be string-matched)
        desc_zh = event.get("description_zh") or ""
        if desc_zh:
            zh_mappings = [
                (info.role or "人物", ja_name, info.name_zh)
                for ja_name, info in people.items()
                if info.name_zh
            ]
            if zh_mappings:
                fixed_zh = _fix_person_names_gpt(client, desc_zh, zh_mappings)
                if fixed_zh:
                    update["description_zh"] = fixed_zh

        # Fix desc_en with direct replacement
        desc_en = event.get("description_en") or ""
        if desc_en:
            new_desc_en = desc_en
            for ja_name, info in people.items():
                if ja_name in new_desc_en and info.name_en:
                    new_desc_en = new_desc_en.replace(ja_name, info.name_en)
            if new_desc_en != desc_en:
                update["description_en"] = new_desc_en

        if update:
            sb.table("events").update(update).eq("id", event["id"]).execute()
            patched += 1
            logger.info(
                "  ✓ person names fixed: %s/%s [cat=%s] desc_zh=%s desc_en=%s persons=%s",
                source, event["id"][:8], ",".join(categories),
                "description_zh" in update, "description_en" in update,
                list(people.keys()),
            )

    logger.info("enrich_person_names: patched %d/%d events", patched, len(events))


def propagate_source_organizer(dry_run: bool = False) -> None:
    """Propagate organizer from the plurality non-null value per source_name.

    For each source_name that has at least one event with organizer set:
      1. Count non-null organizer values across all events of that source.
      2. Use the most common value (plurality).
      3. Update all events with same source_name AND organizer IS NULL.
         Includes reviewed events — organizer is a factual field; no annotation_status reset.

    This is idempotent. Run after scraping new sources or when quality
    checks reveal organizer gaps.
    """
    sb = _get_supabase()

    # Fetch all events with source_name + organizer (any status, active or not)
    res = (
        sb.table("events")
        .select("id,source_name,organizer,annotation_status")
        .limit(10000)
        .execute()
    )
    rows = res.data or []

    # Build plurality organizer per source_name
    from collections import Counter
    source_org_counter: dict[str, Counter] = {}
    for r in rows:
        src = r.get("source_name")
        org = r.get("organizer")
        if src and org:
            source_org_counter.setdefault(src, Counter())[org] += 1

    plurality: dict[str, str] = {
        src: counter.most_common(1)[0][0]
        for src, counter in source_org_counter.items()
    }

    # Find events missing organizer
    targets = [
        r for r in rows
        if r.get("source_name") in plurality and not r.get("organizer")
    ]

    logger.info(
        "propagate_source_organizer: %d sources with organizer data, %d events to update (dry_run=%s)",
        len(plurality), len(targets), dry_run,
    )

    if dry_run:
        for r in targets[:20]:
            logger.info(
                "  would set id=%s source=%s organizer=%s",
                r["id"], r.get("source_name"), plurality[r["source_name"]],
            )
        if len(targets) > 20:
            logger.info("  ... and %d more", len(targets) - 20)
        return

    updated = 0
    for r in targets:
        src = r["source_name"]
        org = plurality[src]
        sb.table("events").update({"organizer": org}).eq("id", r["id"]).execute()
        updated += 1

    logger.info("propagate_source_organizer: updated %d events", updated)


def backfill_tier1_events(limit: int = 50, dry_run: bool = False) -> None:
    """Reset already-annotated events that lack Tier 1 fields back to 'pending'
    so the next annotate pass fills organizer/event_form/language columns.

    Selection: annotation_status='annotated' AND organizer IS NULL.
    Filtering done in Python to avoid Postgres array null semantics.
    """
    sb = _get_supabase()
    res = (
        sb.table("events")
        .select("id,organizer,organizer_type")
        .eq("annotation_status", "annotated")
        .limit(5000)
        .execute()
    )
    rows = res.data or []
    candidates = [
        r for r in rows
        if not r.get("organizer")
    ]
    target = candidates[:limit]
    logger.info(
        "backfill_tier1: %d annotated events scanned, %d missing Tier 1, %d targeted (dry_run=%s)",
        len(rows), len(candidates), len(target), dry_run,
    )
    if dry_run:
        for r in target:
            logger.info("  would reset id=%s", r["id"])
        return

    for r in target:
        sb.table("events").update({"annotation_status": "pending"}).eq("id", r["id"]).execute()

    if target:
        annotate_pending_events(limit=limit)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "Usage: python annotator.py [options]\n\n"
            "Options:\n"
            "  --all                   Re-annotate all events (not just pending)\n"
            "  --fix-translations      Fix only zh/en translation fields\n"
            "  --fix-reviewed          Re-translate reviewed events without resetting status\n"
            "  --enrich-movie-titles   Look up movie titles via eiga.com\n"
            "  --enrich-person-names   Look up person names for all events\n"
            "  --backfill-tier1        Reset annotated events lacking Tier 1 fields back to pending and re-annotate\n"
            "  --propagate-source-organizer  Propagate organizer from plurality value per source_name to events with organizer=null (safe for reviewed events)\n"
            "  --id <uuid>             Operate on a single event by id\n"
            "  --limit <N>             Limit number of events processed (default 50 for backfill-tier1)\n"
            "  --dry-run               Print actions without writing to DB\n"
        )
        sys.exit(0)

    re_all = "--all" in sys.argv
    fix_tr = "--fix-translations" in sys.argv
    fix_rev = "--fix-reviewed" in sys.argv
    enrich_movies = "--enrich-movie-titles" in sys.argv
    enrich_people = "--enrich-person-names" in sys.argv
    backfill_tier1 = "--backfill-tier1" in sys.argv
    propagate_org = "--propagate-source-organizer" in sys.argv
    dry_run_flag = "--dry-run" in sys.argv
    event_id_arg = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--id"), None)
    limit_arg_str = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--limit"), None)
    limit_arg = int(limit_arg_str) if limit_arg_str else 50
    if backfill_tier1:
        backfill_tier1_events(limit=limit_arg, dry_run=dry_run_flag)
    elif propagate_org:
        propagate_source_organizer(dry_run=dry_run_flag)
    elif enrich_movies:
        enrich_movie_titles()
    elif enrich_people:
        enrich_person_names()
    else:
        annotate_pending_events(re_annotate_all=re_all, fix_translations=fix_tr, fix_reviewed=fix_rev, event_id=event_id_arg)

