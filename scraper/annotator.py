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
from pathlib import Path
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
# Simplified → Traditional Chinese character-level conversion table.
# GPT-4o-mini occasionally outputs SC chars even when instructed to use TC.
# This table is applied to ALL *_zh fields after GPT returns.
# ---------------------------------------------------------------------------
_SIMP_TO_TRAD_RAW = {
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
    # SC chars found by production audit scan (2026-05-05)
    "识": "識",
    "药": "藥", "讲": "講", "谱": "譜", "购": "購",
    "绘": "繪", "们": "們", "该": "該", "课": "課",
    "谁": "誰", "谢": "謝", "谋": "謀", "词": "詞",
    "误": "誤", "诚": "誠", "诉": "訴", "诊": "診",
    "讨": "討", "训": "訓",
    "检": "檢", "样": "樣", "档": "檔", "桥": "橋",
    "梦": "夢", "楼": "樓",
    "浅": "淺", "测": "測", "浏": "瀏", "涂": "塗",
    "渐": "漸",
    "线": "線", "练": "練", "终": "終",
    "绪": "緒", "缘": "緣", "缩": "縮",
    "肤": "膚", "脑": "腦", "脸": "臉", "腊": "臘",
    "范": "範", "荡": "蕩",
    "补": "補", "装": "裝",
    "车": "車", "轮": "輪", "软": "軟", "输": "輸",
    "辞": "辭", "边": "邊",
    "辅": "輔", "辆": "輛", "辩": "辯",
    "队": "隊", "阶": "階", "阳": "陽",
    "陆": "陸", "陈": "陳", "随": "隨", "隐": "隱",
    "页": "頁", "顺": "順", "领": "領", "颗": "顆",
    "题": "題", "颜": "顏", "额": "額",
    "风": "風", "饭": "飯", "饮": "飲",
    "龄": "齡", "齿": "齒", "龟": "龜",
    "迁": "遷", "递": "遞", "逻": "邏", "遗": "遺",
    "邮": "郵", "邻": "鄰",
    "酱": "醬", "酿": "釀",
    "钟": "鐘", "钢": "鋼", "钱": "錢",
    "铁": "鐵", "铜": "銅", "铝": "鋁", "银": "銀",
    "锁": "鎖", "锋": "鋒", "错": "錯",
    "镇": "鎮", "镜": "鏡",
    "闭": "閉", "闲": "閒", "闸": "閘",
    "险": "險", "雾": "霧",
    "驾": "駕", "骗": "騙", "骤": "驟",
    "鱼": "魚", "鲜": "鮮", "鸟": "鳥", "鸡": "雞", "鸣": "鳴",
    "踪": "蹤", "买": "買",
}
# Remove identity mappings (same char in both) and build translation table
_SIMP_TO_TRAD = str.maketrans({k: v for k, v in _SIMP_TO_TRAD_RAW.items() if k != v})


def _to_trad(val: str | None) -> str | None:
    """Normalize any Simplified Chinese chars to Traditional."""
    if not val:
        return val
    return val.translate(_SIMP_TO_TRAD)


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
    "movie", "performing_arts", "senses", "tea_alcohol", "drama", "documentary",
    "retail", "nature", "tech", "tourism", "lifestyle_food", "books_media",
    "gender", "parenting", "geopolitics", "art", "lecture", "taiwan_japan",
    "scholarship", "business", "academic", "competition", "indigenous", "folklore",
    "history", "urban", "workshop", "literature", "tv_program", "exhibition",
    "taiwan_mandarin", "healthcare", "report",
]


def _check_category_sync() -> None:
    """Verify VALID_CATEGORIES matches web/lib/types.ts at startup.

    Raises SystemExit(1) if types.ts exists and has categories not in
    VALID_CATEGORIES — prevents silent category stripping during annotation.
    Skipped silently when types.ts is not found (CI / standalone execution).
    """
    ts_path = Path(__file__).resolve().parent.parent / "web" / "lib" / "types.ts"
    if not ts_path.exists():
        return  # CI or standalone — skip
    ts_text = ts_path.read_text(encoding="utf-8")
    m = re.search(r'export type Category\s*=\s*([\s\S]*?);', ts_text)
    if not m:
        logger.warning("_check_category_sync: could not parse Category type from types.ts")
        return
    ts_cats = set(re.findall(r'"(\w+)"', m.group(1)))
    valid = set(VALID_CATEGORIES)
    missing = ts_cats - valid
    extra = valid - ts_cats
    if missing:
        logger.error(
            "VALID_CATEGORIES out of sync with types.ts! "
            "Missing from annotator: %s  — add them to VALID_CATEGORIES and SYSTEM_PROMPT.",
            sorted(missing),
        )
        raise SystemExit(1)
    if extra:
        logger.warning(
            "VALID_CATEGORIES has entries not in types.ts (may be intentional): %s",
            sorted(extra),
        )


# News-source movie title enrichment helpers
# raw_title of news articles often contains the movie title in 「」/『』brackets.
_NEWS_MOVIE_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})
_BRACKET_TITLE_RE = re.compile(r"[\u300c\u300e]([^\u300d\u300f]+)[\u300d\u300f]")

# Sources where raw_title is a news article headline rather than an event name.
# For these sources, GPT is permitted to propose a rewritten name_ja extracted
# from the article body (e.g., the actual movie title or event name).
_HEADLINE_REWRITE_SOURCES: frozenset[str] = frozenset({
    "google_news_rss", "nhk_rss", "prtimes", "walkerplus",
    # note_creators: note.com articles by creators; raw_title is the blog post title,
    # not the event name. GPT should extract the actual film/event name from the body.
    "note_creators",
})

# Pattern matching slot identifiers used in academic conference programs.
# When raw_title matches, GPT may extract the actual presentation title
# from the 題目：line in raw_description.
_SLOT_TITLE_RE = re.compile(
    r'^(第\d+報告|第\d+講演?|基調講演|特別講演|招待講演|総合討論|パネルディスカッション)\s*$'
)

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


# ---------------------------------------------------------------------------
# Deterministic performer extraction from raw_title / raw_description
# ---------------------------------------------------------------------------
# Strip common Japanese honorifics / role labels appended to person names.
_HONORIFIC_RE = re.compile(
    r'[\s\u3000]*'
    r'(?:氏|さん|先生|博士|教授|監督|氏を迎え|さんを迎え|を迎えて?|による|講師|ゲスト|スピーカー|アーティスト)'
    r'[^\S\n]*$'
)
# Match patterns like: 「料理研究家・田中花子氏を迎え」
# Match 「<role>・<name>氏を迎え」 — lookahead stops name before honorific.
_PERFORMER_INTRO_RE = re.compile(
    r'(?:'
    r'料理研究家|シェフ|作家|著者|詩人|翻訳者|写真家|映画監督|演出家|振付家|音楽家|ミュージシャン'
    r'|アーティスト|研究者|学者|評論家|キュレーター|デザイナー|歌手|俳優|女優'
    r'|講師|スピーカー|ゲスト|ゲスト講師|ゲストスピーカー'
    r')'
    r'[・：:\s]*'
    r'([\u4e00-\u9fff]{2,5}?)'
    r'(?=氏|さん|先生|による|を迎え|が登壇|がトーク|にご登場)',
    re.UNICODE,
)
# Match 「〜氏を迎え」, 「〜さんを迎え」 — name before honorific+action
# Restrict to pure kanji ([\u4e00-\u9fff]{2,6}) to avoid capturing
# context phrases like 「交流のあった萩原健太」 or 「評論家の龍應台」.
_MUKAE_RE = re.compile(
    r'(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,5})'
    r'(?:氏|さん|先生)(?:をお?迎え|をゲストに迎え|による|が登壇|がトーク|にご登場)',
    re.UNICODE,
)
# Match 「<name>　｜<role>」 pattern, e.g. 「前田知里　｜植物民族学研究家」
# Covers individual organizer-presenter events where the person is listed as
# 「<org>　<name>　｜<professional title>」 (common in Peatix お話会 events).
# Role must end with a profession suffix (家/者/師/士/督) to filter non-names.
_PIPE_ROLE_RE = re.compile(
    r'([\u4e00-\u9fff]{2,6})'
    r'[\s\u3000]*[｜|][\s\u3000]*'
    r'[\u4e00-\u9fff]+(?:家|者|師|士|督)',
    re.UNICODE,
)


def _extract_performer_from_raw(raw_title: str, raw_description: str) -> str | None:
    """Deterministically extract a single personal performer name from raw text.

    Tries:
    1. 「<role>・<name>氏」 pattern in title (most reliable).
    2. 「<name>氏を迎え」 pattern in title.
    3. 「<name>　｜<role>」 pattern — individual organizer-presenter events.
    4. Same patterns in first 500 chars of description.

    Returns bare name without honorifics, or None.
    Deliberately conservative: only returns when high-confidence.
    Not called for events where performer was already set by the scraper or GPT.
    """
    for text in (raw_title or "", (raw_description or "")[:1500]):
        if not text:
            continue
        m = _PERFORMER_INTRO_RE.search(text)
        if m:
            return _HONORIFIC_RE.sub("", m.group(1)).strip()
        m2 = _MUKAE_RE.search(text)
        if m2:
            return _HONORIFIC_RE.sub("", m2.group(1)).strip()
        m3 = _PIPE_ROLE_RE.search(text)
        if m3:
            return _HONORIFIC_RE.sub("", m3.group(1)).strip()
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

TAIWAN RELEVANCE GATE — CRITICAL:
Before extracting any data, judge whether this event has a DIRECT, EXPLICIT Taiwan connection.
A direct connection means: Taiwanese artist/author/performer/director is the primary subject OR the event explicitly features Taiwan culture/products/identity as its main theme.
REJECT (set is_active=false in your mind; write selection_reason explaining why it is marginal) if:
  - The Taiwan link is only "this tour includes Taiwan" or "the author was inspired by Asia"
  - The event is a book launch where Taiwan appears only as a passing reference in the description
  - The event is a Japanese TV programme that once covered Taiwan
  - SOURCE=bookandbeer: apply STRICT standard. The event MUST feature a Taiwanese author, a book about Taiwan/Taiwan-Japan relations, or an explicit Taiwan cultural theme. A book merely mentioning Taiwan incidentally does NOT qualify.

LANGUAGE RULE — CRITICAL: ALL *_zh fields (name_zh, description_zh, location_name_zh, location_address_zh, business_hours_zh, selection_reason.zh, and sub-event zh fields) MUST be written in Traditional Chinese (繁體中文). NEVER use Simplified Chinese (简体字). This applies to every single zh field without exception.

Given the raw title and description of an event (usually in Japanese), extract structured data and translate into three languages.

CRITICAL DATE EXTRACTION RULES:
1. You MUST extract dates from ALL parts of the text: title, body, headers, and footers.
2. Look for date patterns like: 2025年10月8日, 10/8, 10月8日, 2025-10-08, etc.
3. If the event spans multiple days (e.g., "10/8 and 10/10"), start_date = first date, end_date = last date.
4. SINGLE-DAY RULE: If only one date is mentioned — or if you judge the event to be a single-day occurrence — set end_date = start_date exactly. NEVER leave end_date null when start_date is known.
5. end_date MUST NOT be null if any date can be found anywhere in the text. Try harder to find dates.
6. If the title contains a date like "（10/8・10/10）", extract those dates even if the body is vague.
7. When the year is not explicitly stated, infer it from context. If the raw description begins with （記事配信日: YYYY-MM-DD）, use that year as the reference year for all year-ambiguous dates (e.g. "4月12日" → YYYY-04-12). If no year anchor is present, assume the nearest future occurrence relative to the current year.
8. For ongoing exhibitions/screenings with a date range (e.g., "4月5日〜6月30日"), use the full range.
9. JUDGMENT: Use your reasoning to decide if an event is single-day vs multi-day. A concert, one-time screening, or one-time talk = single day (end_date = start_date). An exhibition, festival, or course = may span many days.
10. DURATION KEYWORDS: When the description explicitly states a duration like "N日間" (e.g., "6日間", "3日間"), compute end_date = start_date + (N-1) days. "1日間" = single day. "N週間" = N×7 days. This OVERRIDES the single-day default. Example: start_date=2026-02-25, "6日間" → end_date=2026-03-02.

OTHER RULES:
1. If the description mentions multiple separate events/sessions with different dates (e.g., a film screening series with individual dates), list them as sub_events.
   ALSO: if the description lists 3+ distinct venue locations in **different cities/prefectures** each with a specific address (e.g., a food fair with restaurants across Tokyo, Kyoto, and Osaka), list each venue as a sub-event with its own location_name, location_address, and business_hours; use the same start_date/end_date as the parent.
   ALSO: if event_form is "conference" and the description lists 3 or more distinct named presentations/reports (報告, 発表, セッション) with individually named presenters (発表者, 報告者, 登壇者), generate a sub-event for each presentation. Use the same start_date/end_date and venue as the parent, set business_hours to that session's time slot (e.g. "12:30～13:50"), and put the presenter's name in both the "performer" string and the "performers" array. The sub-event name_ja should be the presentation title.
   EXCEPTION — DO NOT create sub_events for a single-film cinema screening (movie category) that simply has multiple show-time slots. For example, '4/25(土)～5/1(金)10:00、5/2(土)～8(金)14:40' is ONE film with two show-time windows — use start_date = first date, end_date = last date, put the slot details in business_hours. Sub_events in this context are for DIFFERENT FILMS in a series or DIFFERENT PHYSICAL VENUES, not different show times of the same film.
   EXCEPTION — DO NOT create sub_events when the article is a report/recap. If the raw_title contains レポート, レポ, 報告, 記録, アーカイブ, or recap (case-insensitive), the article is a post-event report and describes a single completed event — return sub_events: [] always. Treat the report as one event and extract its single set of fields (date, performer, etc.) from the body.
2. Categories must be from this list: movie, performing_arts, senses, tea_alcohol, drama, documentary, retail, nature, tech, tourism, lifestyle_food, books_media, gender, parenting, geopolitics, art, lecture, taiwan_japan, scholarship, business, academic, competition, indigenous, folklore, history, urban, workshop, literature, tv_program, exhibition, taiwan_mandarin, healthcare, report
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
   - "tv_program" = TV broadcasts, television programs. MANDATORY for any event from a TV broadcast source (look for 放送: / ジャンル: markers in raw_description). A TV drama should have BOTH tv_program AND drama. A TV movie broadcast should have BOTH tv_program AND movie.
   - "drama" = serialized dramatic works: TV dramas, stage drama series, web dramas. For TV drama broadcasts, always pair with tv_program.
   - "documentary" = documentary films or TV documentary programs. For TV documentaries, pair with tv_program.
   - "tea_alcohol" = tea culture, wine, sake, cocktail events, tasting events, tea ceremony workshops, bar/pub events featuring Taiwanese beverages
   - "exhibition" = museum exhibitions, gallery shows, permanent/special exhibitions at a specific venue with defined dates. Distinct from "art" (which covers visual art broadly) and "senses" (creative experiences)
   - "folklore" = folk customs, festivals, folk religion, temple events, traditional crafts rooted in folk traditions
   - "literature" = literary events: poetry readings, literary salons, writer residencies, literary translation. Distinct from "books_media" (publishing/media industry)
   - "parenting" = parenting, childcare, family-oriented events, children's education, parent-child workshops
   - "scholarship" = scholarships, grants, funding opportunities, study-abroad programs
   - "taiwan_mandarin" = Mandarin/Taiwanese language learning events, Chinese language classes, language exchange
   - "healthcare" = health, medical, public health, wellness events
   - An event can have multiple categories
3. Translate the event name and a concise summary description into all three languages (ja, zh, en).
4. The description should be a clean, concise summary (2-4 sentences), NOT a copy of the raw text.
5. Extract location, address, business hours, and pricing from the text if available.

NAME WRITING RULES — CRITICAL:
- name_ja: copy the raw_title as-is. Do NOT rewrite, shorten, or "improve" it. The scraper's original title is the source of truth. Your name_ja output is only used for sub-events (the parent's name_ja is always preserved from the scraper).
- name_zh and name_en: translate name_ja faithfully. A reader who sees ONLY the title must understand what kind of event it is.
- If the raw_title is a generic term alone (e.g., "オフ会", "ライブ", "上映会"), prepend context in name_zh/name_en to make them self-explanatory.
- SUB-EVENT name_ja / description_ja: use the ORIGINAL Japanese text from the raw description. Movie titles must use the Japanese release title exactly as written. Person names must use the original Japanese notation (katakana/kanji). NEVER translate Chinese/Taiwanese person names into Japanese or invent katakana readings.
  CRITICAL — DO NOT INFER MOVIE TITLES: If a sub-event's title is a descriptive location/action phrase (e.g., "早稲田大学での上映会", "○○会館上映会", "熊本市での上映イベント") and the specific film title does NOT appear directly adjacent to that sub-event's mention in the raw text, use the descriptive phrase as name_ja. Do NOT replace it with a film title inferred from another part of the article. Only use a film title as name_ja when that exact title is explicitly written next to THIS sub-event's description.
- SUBTITLE RULE — CRITICAL: When the raw_title or name_ja contains a subtitle separator (――, ──, ―, —, ：, : used as structural separator), the FULL title including the complete subtitle MUST appear in name_zh and name_en. NEVER truncate the subtitle. Example: "台湾の地方選挙と基層社会――80年代以降の桃園県観音･新屋地区を例として" → name_zh must include "以80年代以降的桃園縣觀音・新屋地區為例", name_en must include "A Case Study of Guanyin and Xinwu Districts, Taoyuan, since the 1980s".
- NEWS HEADLINE REWRITE RULE (applies only to: google_news_rss, nhk_rss, prtimes, walkerplus):
  When raw_title is a news article headline describing an event rather than naming it
  (e.g. "台湾映画 17日那覇で上映会", "台湾人アーティストが個展開催"), extract the actual
  event name from the article body and use it as name_ja.
  Examples:
    "日本の植民地支配へ抵抗描く 台湾映画 17日那覇で上映会" → find film title in body
    → name_ja: "映画『一八九五』上映会・シンポジウム"
  If no specific event/film name can be identified in the body, keep raw_title as-is.
- ACADEMIC SLOT REWRITE RULE (applies when raw_title is "第N報告", "第N講演", "基調講演", etc.):
  The raw_title is a program slot identifier, not the presentation title.
  Extract the actual title from the "題目：TITLE" line in raw_description and use it as name_ja.
  Example: raw_title="第1報告", raw_description contains "題目：台湾植民地戦争における..."
  → name_ja: "台湾植民地戦争における日本軍の出征儀礼と凱旋儀礼"
  If no 題目 line exists, keep raw_title.
6. LOCATION ADDRESS RULE:
   - COPY-FIRST: If raw_description contains an explicit address line (〒, 丁目, 番地, or a full prefecture+city+street string), copy it verbatim.
   - DEFAULT-NULL: If no explicit address appears in the raw text, set location_address = null. Do NOT use your training knowledge to infer or guess a venue's street address — LLM address knowledge is unreliable and produces plausible-looking but incorrect street numbers.
   - ALLOWED EXCEPTION: Only fill from knowledge for these globally famous fixed-address landmarks with well-known addresses: 国立新美術館, 東京都美術館, 国立国会図書館, 台湾文化センター（台北駐日経済文化代表処）, 東京国際フォーラム, 東京都写真美術館. For all other venues, leave null and let the downstream address enrichment pipeline fill it.
   - NEVER echo the venue name as the address. If you cannot find a real street address, return null.
   PARENT VENUE ADDRESS RULE: When location_name contains a sub-space appended after a parent facility
   (e.g. "○○S.C. 森のまち広場", "○○ビル2階 大会議室", "○○ホール内 スタジオA"),
   the correct location_address is the PARENT FACILITY's address, not the sub-space itself.
   Examples:
     "流山おおたかの森S.C. 森のまち広場" → address for 流山おおたかの森S.C. = "千葉県流山市おおたかの森西1-1-3"
     "肥後銀行本店ビル2階 大会議室"     → address for 肥後銀行本店ビル
   ALSO: location_address MUST NEVER be identical to location_name.
   If they would be the same (address lookup failed), keep location_address null instead of
   echoing the venue name.
   COLLECTION ATTRIBUTION NOTE: In museum exhibit descriptions, text like "○○美術館蔵"
   or "○○博物館蔵" indicates the collection owner of an artwork, NOT the event venue.
   Do NOT use collection attribution text as location_name or location_address.
   For yebizo (東京都写真美術館) events, the venue is always 東京都写真美術館,
   regardless of where the artworks in the collection come from.

   NOTE: Events held IN Taiwan are allowed and welcome. Do NOT force-convert Taiwan addresses to Japanese format. For Taiwan venues, fill location_address with the real Taiwanese address (e.g. "台北市中山區小民生東路3段1號") and set location_name accordingly. The tourism category applies when the event is designed to attract Japanese visitors to Taiwan.
7. For pricing: is_paid=false if free/無料/免費, is_paid=true if there's a fee, null if unknown.

PERFORMER EXTRACTION RULES:
1. performer: a SINGLE real personal name (person, not organization) who is the primary guest performer, speaker, lecturer, or artist of the event.
   - Extract from patterns like: 「料理研究家・田中花子氏を迎え」, 「ゲスト：田中花子」, 「田中花子さんによる」, 「講師：田中花子」, 「田中花子　｜植物民族学研究家」.
   - Return the bare name only — NO honorifics (氏, さん, 先生, 教授, 監督, アーティスト, etc.).
   - If the event has multiple performers (e.g., a festival with 10 artists) or the performer is an organization, return null.
   - Return null for exhibitions, food markets, and large festivals where no single person is prominently featured.
   - Return null when the named person IS an organizational entity acting as organizer (not a speaker). EXCEPTION: if an individual person is listed with a professional title in the format 「<name>　｜<role>」 (e.g. 「前田知里　｜植物民族学研究家」), they are both the organizer AND the primary speaker — extract their name.
2. performer must be a person name ≥2 characters. Never return a place name, brand, or phrase.
3. performers: array of ALL named performers, speakers, or featured artists at this event.
   - Each entry is a bare personal name (no honorifics, no roles, no organization names).
   - Include everyone who is a named guest/speaker/artist, even if there are multiple.
   - ACADEMIC EXCEPTION: For academic conferences (学会大会, 研究大会, シンポジウム, 国際会議, 研究集会, 部会), include ALL named research presenters (発表者, 報告者, 登壇者, 基調講演者) in the performers array — even if there are 5 or more. Each individual's name that appears in the raw text as a presenter should be listed.
   - Return [] (empty array) if no specific person is named, or for food markets/large festivals.
   - Examples: ["林廉恩", "一青窈"], ["蘇紫雲"], []

ORGANIZER EXTRACTION RULES:
1. organizer: the primary entity hosting the event. Look for fields like 主催, 主辦, presented by, 主催者. Single string, original-language official name (e.g. "台北駐日経済文化代表処 台湾文化センター"). Do NOT include role labels like "主催:" in the value.
   CINEMA DISTRIBUTOR FALLBACK: For film screenings where 主催 is NOT stated, 配給 (distributor) may be used as organizer — the distributor is the entity responsible for the screening in Japan. Do NOT include "配給：" in the value (strip the label).
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
  conference, networking, screening_with_talk, tour, competition, tasting, broadcast, other
Decision guides:
- SCREENING RESTRICTION: "screening" and "screening_with_talk" are ONLY for events where a film, documentary, anime, or video work is actually projected/screened. DO NOT use them for lectures, tastings, launch parties, or other events even if they discuss media.
- TV broadcast (テレビ放送, 放映, 番組) = ["broadcast"]. NEVER use "screening" for TV programs — screening is for cinema/theater projection only.
- A film/documentary/anime screening followed by a Q&A or talk = ["screening_with_talk"] (NOT screening + lecture).
- Pure film screening with no talk = ["screening"].
- Pure exhibition = ["exhibition"]; exhibition with opening lecture = ["exhibition","lecture"].
- 食フェス / 物産展 / 美食祭 / マルシェ = ["market"].
- 試飲会 / 品嚐会 / テイスティング / 試食会 / 飲み比べ (tasting as the main activity) = ["tasting"].
- 学会大会 with multiple paper sessions = ["conference"]; single 講演会 / 講座 / セミナー = ["lecture"].
- 体験講座 / ワークショップ / 手作り教室 / クラフト / ハンズオン = ["workshop"].
- Trade show / business summit = ["conference"].
- LIVE concert, theater, dance = ["performance"].
- 交流会 / オフ会 / 懇親会 / launch party / ローンチイベント = ["networking"].
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
  "performer": "bare personal name (no honorifics) of the single primary guest/speaker/artist — in original language (usually Japanese)" or null,
  "performer_zh": "Traditional Chinese name of the performer. If the Chinese name is explicitly stated in the source text, use it exactly as written. If you must infer or transliterate from the Japanese name (not stated in source), append「（AI翻譯）」e.g. '黃以文（AI翻譯）'" or null,
  "performer_en": "English/romanized name of the performer. If explicitly in source: use as-is. If inferred/transliterated: append ' (AI Translation)' e.g. 'Huang Yi-wen (AI Translation)'" or null,
  "performers": ["bare name 1", "bare name 2"] or [],
  "performers_zh": ["Traditional Chinese name 1", "name 2"] or [],
  "performers_en": ["English name 1", "name 2"] or [],
  "director": "bare personal name (no honorifics) of the director/filmmaker — in original language" or null,
  "director_zh": "Traditional Chinese name of the director. If explicitly in source: use as-is. If inferred: append「（AI翻譯）」" or null,
  "director_en": "English/romanized name of the director. If explicitly in source: use as-is. If inferred: append ' (AI Translation)'" or null,
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
      "has_english_support": false or true or null,
      "performer": "bare personal name of the primary presenter/performer" or null,
      "performers": ["list of all named presenters/performers for this session"] or []
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
    "conference", "networking", "screening_with_talk", "tour", "competition",
    "tasting", "broadcast", "other",
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

_TV_PROGRAM_KEYWORDS = frozenset(["放送:", "放送：", "ジャンル:", "ジャンル："])


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
    # tv_program: TV broadcast markers (gguide_tv raw_description pattern)
    if "tv_program" not in cats and any(kw in text for kw in _TV_PROGRAM_KEYWORDS):
        cats.append("tv_program")
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
    _check_category_sync()
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

    # Validate human_category_map: strip categories not in VALID_CATEGORIES
    _valid_set = set(VALID_CATEGORIES)
    _cc_cleaned = 0
    for _cc_eid, _cc_cats in list(human_category_map.items()):
        _invalid = [c for c in _cc_cats if c not in _valid_set]
        if _invalid:
            cleaned = [c for c in _cc_cats if c in _valid_set]
            logger.warning(
                "category_corrections %s has invalid categories %s — stripping (kept: %s)",
                _cc_eid[:8], _invalid, cleaned or ["senses"],
            )
            human_category_map[_cc_eid] = cleaned or ["senses"]
            _cc_cleaned += 1
    if _cc_cleaned:
        logger.warning("Cleaned %d category_corrections entries with invalid categories", _cc_cleaned)

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
            # Sub-events with annotation_status='pending' are created by scrapers
            # that set parent_event_id ahead of time. Include them so they get
            # annotated. Annotator-created sub-events are already 'annotated' and
            # are safe from re-processing (they won't match this pending filter).
            query = query.eq("annotation_status", "pending")

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
        # If this is a sub-event, fetch parent for field inheritance.
        _parent_event: dict | None = None
        if event.get("parent_event_id"):
            _pr = sb.table("events").select(
                "id,name_ja,name_zh,name_en,"
                "location_name,location_address,location_name_zh,location_name_en,"
                "location_address_zh,location_address_en,"
                "business_hours,business_hours_zh,business_hours_en,"
                "organizer,organizer_type,co_organizers,sponsors,performer,performers"
            ).eq("id", event["parent_event_id"]).execute()
            _parent_event = _pr.data[0] if _pr.data else None
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

        # Universal year-anchor injection:
        # Any raw_description that lacks 「記事配信日:」 risks GPT guessing the wrong year.
        # Two failure classes:
        #   (a) Description has NO 4-digit year at all (e.g. "5月8日（金）公開") — GPT
        #       falls back to training-data knowledge, which can be a past year.
        #   (b) Description has a MISLEADING 4-digit year referring to a DIFFERENT country's
        #       release (e.g. "2025年11月に公開を迎えた台湾国内での興行収入") — GPT uses
        #       that year for the Japan premiere date instead.
        # Fix: unconditionally inject scraped_at as year anchor for ALL sources when
        # scraped_at is available and 記事配信日: is not already present.
        # This covers gnews/nhk_rss/prtimes/walkerplus (previous fix) PLUS cinema scrapers
        # like uplink_cinema that embed Taiwan-release years in their descriptions.
        # Reference incidents:
        #   2026-05-06 — 0d33b617 (gnews 熊本チップ・オデッセイ) hallucinated 2024-04-01.
        #   2026-05-07 — dded67a6 (uplink_cinema 霧のごとく大濛) hallucinated 2025-05-08
        #     because "2025年11月に公開を迎えた台湾国内での興行収入" misled GPT into
        #     thinking the Japan premiere was also 2025.
        if (
            event.get("scraped_at")
            and "記事配信日:" not in (raw_desc or "")
        ):
            _scraped_dt = str(event["scraped_at"])[:10]  # e.g. "2026-04-28"
            raw_desc = f"（記事配信日: {_scraped_dt}）\n\n" + (raw_desc or "")
            logger.debug("  → Injected scraped_at year anchor: %s", _scraped_dt)

        # For sub-events: add parent event name as translation reference context.
        if _parent_event:
            _parent_ctx = (
                "\n\n[Parent event context — use for name translation reference only]\n"
                f"Parent name (JA): {_parent_event.get('name_ja') or ''}\n"
                f"Parent name (ZH): {_parent_event.get('name_zh') or ''}\n"
                f"Parent name (EN): {_parent_event.get('name_en') or ''}\n"
                f"Parent location: {_parent_event.get('location_name') or ''}\n"
            )
            raw_desc = (raw_desc or "") + _parent_ctx

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

            # _SIMP_TO_TRAD and _to_trad() are now module-level — see top of file.
            # _loc_zh remains here as it depends on _loc() which is defined locally.
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
                # name_ja policy: preserve scraper's original title (2026-05-02).
                # Exception 1 — news headline sources (google_news_rss, nhk_rss, etc.):
                #   raw_title is a news headline, not an event name. GPT may propose
                #   a rewritten name_ja that reflects the actual event name from the body.
                # Exception 2 — slot identifier titles ("第N報告", "基調講演", etc.):
                #   GPT extracts the actual presentation title from 題目：lines.
                _original_name_ja = event.get("name_ja") or raw_title
                _gpt_name_ja = _str(annotation.get("name_ja"))
                if event.get("source_name") in _HEADLINE_REWRITE_SOURCES and _gpt_name_ja:
                    _final_name_ja = _gpt_name_ja
                elif _SLOT_TITLE_RE.match(_original_name_ja or "") and _gpt_name_ja:
                    _final_name_ja = _gpt_name_ja
                else:
                    _final_name_ja = _original_name_ja
                update_data: dict[str, Any] = {
                    "name_ja": _final_name_ja,
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
                    "organizer": _ai_or_existing("organizer", (
                        # Non-hallucination guard: discard GPT organizer if the name
                        # doesn't appear anywhere in the source text. This prevents
                        # few-shot contamination (e.g. category_corrections examples
                        # that contain an organizer name bleeding into unrelated events).
                        # Reference incident: 2026-05-06 — セシリアママ appeared in
                        # category_corrections few-shot examples and was hallucinated
                        # onto 8 unrelated Peatix events whose raw text had no such name.
                        _str(annotation.get("organizer"))
                        if (
                            _str(annotation.get("organizer"))
                            and _str(annotation.get("organizer")) in (
                                (raw_title or "") + " " + (event.get("raw_description") or "")
                            )
                        )
                        else None
                    ) or (_default_org_map.get(event.get("source_name") or "", {}).get("organizer"))),
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
                # Performer: DB existing value (if protected) → deterministic regex → GPT.
                # Never overwrite a field_corrections-protected value.
                if "performer" not in _human_protected:
                    _gpt_performer = _str(annotation.get("performer"))
                    _regex_performer = _extract_performer_from_raw(
                        raw_title or "", event.get("raw_description") or ""
                    )
                    _final_performer = (
                        event.get("performer")  # scraper-set or previously annotated
                        or _gpt_performer       # GPT extracted
                        or _regex_performer     # deterministic fallback
                    )
                    if _final_performer:
                        update_data["performer"] = _final_performer

                # performers array (multi-speaker support)
                if "performers" not in _human_protected:
                    _gpt_performers = annotation.get("performers")
                    if isinstance(_gpt_performers, list) and _gpt_performers:
                        _valid_performers = [
                            p for p in _gpt_performers
                            if isinstance(p, str) and p.strip()
                        ]
                        if _valid_performers:
                            update_data["performers"] = _valid_performers

                # Sync performer → performers[] when performers[] would be empty.
                # This ensures UI can always read performers[] without falling back to performer.
                _existing_performers = event.get("performers") or []
                _incoming_performers = update_data.get("performers") or []
                if (
                    update_data.get("performer")
                    and not _existing_performers
                    and not _incoming_performers
                    and "performers" not in _human_protected
                ):
                    update_data["performers"] = [update_data["performer"]]

                # Performer translations
                if update_data.get("performer"):
                    _perf_zh = _to_trad(_str(annotation.get("performer_zh")))
                    _perf_en = _str(annotation.get("performer_en"))
                    if _perf_zh:
                        update_data["performer_zh"] = _perf_zh
                    if _perf_en:
                        update_data["performer_en"] = _perf_en

                # Performers array translations
                _gpt_performers_zh = annotation.get("performers_zh")
                if isinstance(_gpt_performers_zh, list) and _gpt_performers_zh:
                    update_data["performers_zh"] = [_to_trad(s) if isinstance(s, str) else s for s in _gpt_performers_zh]
                _gpt_performers_en = annotation.get("performers_en")
                if isinstance(_gpt_performers_en, list) and _gpt_performers_en:
                    update_data["performers_en"] = _gpt_performers_en

                # Director (from GPT)
                if "director" not in _human_protected:
                    _gpt_director = _str(annotation.get("director"))
                    if _gpt_director:
                        update_data["director"] = _gpt_director
                        _dir_zh = _to_trad(_str(annotation.get("director_zh")))
                        _dir_en = _str(annotation.get("director_en"))
                        if _dir_zh:
                            update_data["director_zh"] = _dir_zh
                        if _dir_en:
                            update_data["director_en"] = _dir_en

                # Sub-event parent inheritance:
                # - If sub-event has no location, or same location as parent → inherit all location fields
                # - Regardless of location → inherit organizer/performer if not set
                if _parent_event:
                    _sub_has_own_loc = bool(update_data.get("location_name"))
                    _parent_loc_name = _parent_event.get("location_name")
                    _same_loc = (
                        _sub_has_own_loc
                        and _parent_loc_name
                        and update_data["location_name"] == _parent_loc_name
                    )
                    if not _sub_has_own_loc or _same_loc:
                        for _lf in (
                            "location_name", "location_address",
                            "location_name_zh", "location_name_en",
                            "location_address_zh", "location_address_en",
                            "business_hours", "business_hours_zh", "business_hours_en",
                        ):
                            if not update_data.get(_lf):
                                update_data[_lf] = _parent_event.get(_lf)
                    for _pf in ("organizer", "organizer_type", "co_organizers", "sponsors", "performer"):
                        if not update_data.get(_pf):
                            update_data[_pf] = _parent_event.get(_pf)

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
                # If AI returned a multilingual dict, normalize zh to Traditional Chinese
                if isinstance(selection_reason, dict):
                    if "zh" in selection_reason and selection_reason["zh"]:
                        selection_reason["zh"] = _to_trad(selection_reason["zh"])
                    selection_reason = json.dumps(selection_reason, ensure_ascii=False)
                update_data["selection_reason"] = selection_reason

            # P1 field-protection: restore DB values for any field in field_corrections.
            # _ai_or_existing() was defined but never wired into update_data construction.
            # This post-processing step closes the gap: after GPT fills update_data,
            # we overwrite protected fields with the known-correct DB value so that
            # human corrections (name_zh, name_en, description_zh, description_en, etc.)
            # are never silently replaced by AI output.
            _NEVER_PROTECT = {"annotation_status", "annotated_at"}
            for _pf in _human_protected:
                if _pf in update_data and _pf not in _NEVER_PROTECT:
                    _db_val = event.get(_pf)
                    if _db_val is not None:
                        update_data[_pf] = _db_val
                        field_protect_hits += 1
                    else:
                        del update_data[_pf]
                        field_protect_hits += 1

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
            # Never create grandchild events: if this event is itself a sub-event
            # (has parent_event_id), skip sub-event creation entirely.
            if event.get("parent_event_id"):
                sub_events = []
            # Report/recap articles must never generate sub-events.
            # The article describes a single completed event; sub-events would be
            # phantom duplicates of segments already described in the report body.
            _REPORT_RE = re.compile(r"レポート|レポ|報告|記録|アーカイブ|recap", re.IGNORECASE)
            if sub_events and _REPORT_RE.search(event.get("raw_title", "") or ""):
                logger.debug(
                    "  ⚑ Skipping sub_events for report/recap article %s",
                    event.get("source_id"),
                )
                sub_events = []
            # Defense-in-depth guard for the first-run race condition:
            # When a cinema series page is scraped for the first time, the parent
            # event isn't in DB yet, so _get_parent_uuid returns None and film-index
            # sub-events (e.g. ks_cinema_slug_2) get parent_event_id=None.
            # Without this guard the annotator would create _sub1 for each show-time
            # period in the schedule.  We detect this by checking if source_id ends
            # in _{digit} with a cinema-source prefix — those are always series sub-films,
            # not top-level events that legitimately spawn sub-events.
            import re as _re
            _cinema_sources = {"ks_cinema"}
            if (event.get("source_name") in _cinema_sources
                    and _re.search(r"_\d+$", event.get("source_id", ""))
                    and not event.get("parent_event_id")):
                logger.debug(
                    "  ⚑ Skipping sub_events for cinema series film sub-event %s "
                    "(parent_event_id not yet set — first-run race condition)",
                    event.get("source_id"),
                )
                sub_events = []
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
                    "performer": _str(sub.get("performer")),
                    "performers": [p for p in (sub.get("performers") or []) if isinstance(p, str)],
                    "performer_zh": _str(sub.get("performer_zh")),
                    "performer_en": _str(sub.get("performer_en")),
                    "director": _str(sub.get("director")),
                    "director_zh": _str(sub.get("director_zh")),
                    "director_en": _str(sub.get("director_en")),
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
            "description_zh,description_en,selection_reason,"
            "annotation_status,source_name,parent_event_id,"
            "performer,director"
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
            _title_from_raw = bool(m)
            if not m:
                m = _BRACKET_TITLE_RE.search(event.get("name_ja") or "")
            # Guard: for sub-events of news articles, reject bracket titles
            # derived from GPT-generated name_ja — they may be hallucinated.
            # Sub-event name_ja is produced from thin context (a single
            # descriptive sentence); GPT may infer a plausible-sounding
            # film title from an unrelated part of the article.
            # Only trust brackets found in raw_title (scraper-captured text).
            # Reference incident: 2026-05-05 d18339d5 gnews_sub3 → 月老 hallucination.
            if m and not _title_from_raw and event.get("parent_event_id"):
                logger.warning(
                    "  ⚠ skipping enrich for news sub-event %s — bracket title "
                    "derived from GPT name_ja (unreliable); raw_title has no brackets "
                    "[name_ja=%r]",
                    event["id"][:8], (event.get("name_ja") or "")[:60],
                )
                continue
            title = m.group(1).strip() if m else ""
        else:
            title = event.get("name_ja") or event.get("raw_title") or ""

        if not title:
            continue

        name_zh, name_en = lookup_movie_titles(title)

        # Fallback: check works table for canonical titles + inherit performer/director
        works_performer = None
        works_director = None
        if not name_zh or not name_en or not event.get("performer") or not event.get("director"):
            w_res = sb.table("works").select("title_zh,title_en,cast_summary,director").eq("title_ja", title).limit(1).execute()
            if w_res.data:
                w_row = w_res.data[0]
                if not name_zh:
                    name_zh = w_row.get("title_zh")
                if not name_en:
                    name_en = w_row.get("title_en")
                if name_zh or name_en:
                    logger.info("  works fallback for %r → zh=%r en=%r", title, name_zh, name_en)
                works_performer = w_row.get("cast_summary")
                works_director = w_row.get("director")

        if not name_zh and not name_en:
            logger.warning(
                "  ⚠ eiga.com lookup returned no titles for movie event %s/%s [%s]",
                source, event["id"][:8], title[:60],
            )
            continue

        old_name_zh = event.get("name_zh") or ""
        old_name_en = event.get("name_en") or ""

        update: dict[str, Any] = {}
        if name_zh:
            update["name_zh"] = name_zh
        if name_en:
            update["name_en"] = name_en
        if not event.get("performer") and works_performer:
            update["performer"] = works_performer
        if not event.get("director") and works_director:
            update["director"] = works_director

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

        # Fix selection_reason — replace old titles in all three languages
        sr_raw = event.get("selection_reason") or ""
        if sr_raw and (name_zh or name_en):
            try:
                sr = json.loads(sr_raw) if isinstance(sr_raw, str) else sr_raw
                if isinstance(sr, dict):
                    sr_changed = False
                    if name_zh and sr.get("zh"):
                        for old_ref in ([old_name_zh, title] if source in _NEWS_MOVIE_SOURCES else [old_name_zh]):
                            if old_ref and old_ref != name_zh and old_ref in sr["zh"]:
                                sr["zh"] = sr["zh"].replace(old_ref, name_zh)
                                sr_changed = True
                    if name_en and sr.get("en"):
                        if old_name_en and old_name_en != name_en and old_name_en in sr["en"]:
                            sr["en"] = sr["en"].replace(old_name_en, name_en)
                            sr_changed = True
                    if name_zh and sr.get("ja"):
                        if old_name_zh and old_name_zh != name_zh and old_name_zh in sr["ja"]:
                            sr["ja"] = sr["ja"].replace(old_name_zh, name_zh)
                            sr_changed = True
                    if sr_changed:
                        update["selection_reason"] = json.dumps(sr, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        sb.table("events").update(update).eq("id", event["id"]).execute()
        _lock_fields_via_corrections(sb, event["id"], update)
        patched += 1
        logger.info(
            "  ✓ %s/%s [%s] → zh=%r en=%r desc_zh=%s desc_en=%s sr=%s",
            source, event["id"][:8], title[:40], name_zh, name_en,
            "description_zh" in update, "description_en" in update,
            "selection_reason" in update,
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


_PERSON_FIX_PROMPT_EN = """You are a translation proofreader. The English description below may contain
incorrect English transliterations of person names that were derived from
Japanese katakana (e.g. "Koo Kuan-Dong" should be "Ko Chen-tung").

Replace any wrong transliterations with the canonical English name listed below.

Rules:
- Only modify person names. Do NOT change anything else (punctuation, wording, formatting).
- If the description already uses the correct English name, do not change anything.
- If no incorrect name is found, return the description unchanged.
- Output only the corrected description, with no explanation or preamble.

Canonical names:
{mapping}

Description:
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


def _fix_person_names_gpt_en(
    client: OpenAI, desc: str, name_mappings: list[tuple[str, str, str]]
) -> str | None:
    """Use GPT-4o-mini to replace wrong English transliterations in desc_en.

    Direct katakana string replacement does NOT work for description_en,
    because GPT translation already converted katakana to English
    transliterations (e.g. クー・チェンドン → "Koo Kuan-Dong"). The katakana
    string is no longer present in desc_en, so str.replace silently fails.
    Use GPT to find and correct wrong English transliterations instead.

    name_mappings: list of (role, ja_name, correct_en_name) tuples.
    Returns the fixed description, or None if no change.
    """
    mapping_lines = "\n".join(
        f"- {role}: {en_name} (Japanese: {ja_name})"
        for role, ja_name, en_name in name_mappings
    )
    prompt = _PERSON_FIX_PROMPT_EN.format(mapping=mapping_lines, desc=desc)

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
        logger.warning("_fix_person_names_gpt_en error: %s", exc)
        return None


def _lock_fields_via_corrections(
    sb: "Client", event_id: str, fields: dict[str, Any]
) -> None:
    """Persist auto-enrich corrections to field_corrections so future
    re-annotation passes will skip these fields (annotator P1 protection).

    Without this lock, transient lookup failures during a future CI run
    could let GPT output overwrite a known-correct value (e.g. eiga.com
    official Chinese title) with a phonetic GPT direct-translation.

    Idempotent — uses upsert on the (event_id, field_name) unique key.
    Safe no-op if the field_corrections table doesn't exist (pre-038b).
    """
    if not fields:
        return
    rows = [
        {
            "event_id": event_id,
            "field_name": fname,
            "corrected_value": str(fvalue) if fvalue is not None else "",
            "corrected_by": None,
        }
        for fname, fvalue in fields.items()
    ]
    try:
        sb.table("field_corrections").upsert(
            rows, on_conflict="event_id,field_name"
        ).execute()
    except Exception as exc:
        logger.debug(
            "field_corrections lock skipped for %s (table missing or error): %s",
            event_id[:8], exc,
        )


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
                    update["description_zh"] = _to_trad(fixed_zh)

        # Fix desc_en using GPT — direct katakana replacement is futile
        # because GPT already transliterated names to English in desc_en
        # (e.g. クー・チェンドン → "Koo Kuan-Dong"). See _fix_person_names_gpt_en.
        desc_en = event.get("description_en") or ""
        if desc_en:
            en_mappings = [
                (info.role or "person", ja_name, info.name_en)
                for ja_name, info in people.items()
                if info.name_en
            ]
            if en_mappings:
                fixed_en = _fix_person_names_gpt_en(client, desc_en, en_mappings)
                if fixed_en:
                    update["description_en"] = fixed_en

        if update:
            sb.table("events").update(update).eq("id", event["id"]).execute()
            # Lock the corrected fields via field_corrections so future
            # re-annotation passes won't clobber them with fresh GPT output
            # (which would re-introduce phonetic katakana transliterations).
            _lock_fields_via_corrections(sb, event["id"], update)
            patched += 1
            logger.info(
                "  ✓ person names fixed: %s/%s [cat=%s] desc_zh=%s desc_en=%s persons=%s",
                source, event["id"][:8], ",".join(categories),
                "description_zh" in update, "description_en" in update,
                list(people.keys()),
            )
        elif people:
            # People found but no fix applied. desc_en may still contain
            # wrong transliterations that GPT considered already-correct,
            # OR there was a transient OpenAI failure. Surface this for
            # the auto-QA dashboard.
            logger.warning(
                "  ⚠ person names found but no description fix applied: %s/%s persons=%s",
                source, event["id"][:8], list(people.keys()),
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


def post_batch_enrich(event_ids: list[str], *, dry_run: bool = False) -> dict:
    """Run enrichment pipelines on specific events after a batch write.

    Must be called by all _oneoff_*.py / batch fix scripts after writing to DB.

    Covers:
      1. Movie title lookup via eiga.com — overwrites GPT translations with
         official Chinese/English titles. Only for movie-category events.

    For person name enrichment, run separately after this function:
        python annotator.py --enrich-person-names

    Respects field_corrections — will NOT overwrite locked values.
    Idempotent — safe to call multiple times.

    Args:
        event_ids: List of event UUIDs to enrich.
        dry_run: If True, log actions without writing to DB.

    Returns:
        {"movie_patched": int, "skipped_protected": int}
    """
    if not event_ids:
        return {"movie_patched": 0, "skipped_protected": 0}

    sb = _get_supabase()

    # --- Movie title enrichment ---
    movie_patched = 0
    skipped_protected = 0

    res = (
        sb.table("events")
        .select(
            "id,name_ja,raw_title,name_zh,name_en,"
            "description_zh,description_en,selection_reason,"
            "annotation_status,source_name,parent_event_id,category,"
            "performer,director"
        )
        .in_("id", event_ids)
        .contains("category", ["movie"])
        .neq("annotation_status", "reviewed")
        .neq("source_name", "eiga_com")
        .execute()
    )
    movie_events = res.data or []
    logger.info("post_batch_enrich: %d movie events to check", len(movie_events))

    for event in movie_events:
        source = event.get("source_name", "")

        # Extract title (same logic as enrich_movie_titles)
        if source in _NEWS_MOVIE_SOURCES:
            raw = event.get("raw_title") or ""
            m = _BRACKET_TITLE_RE.search(raw)
            _title_from_raw = bool(m)
            if not m:
                m = _BRACKET_TITLE_RE.search(event.get("name_ja") or "")
            if m and not _title_from_raw and event.get("parent_event_id"):
                logger.info("  skip news sub-event %s (bracket from name_ja)", event["id"][:8])
                continue
            title = m.group(1).strip() if m else ""
        else:
            title = event.get("name_ja") or event.get("raw_title") or ""

        if not title:
            continue

        name_zh, name_en = lookup_movie_titles(title)

        # Fallback: check works table for canonical titles + inherit performer/director
        works_performer = None
        works_director = None
        if not name_zh or not name_en or not event.get("performer") or not event.get("director"):
            w_res = sb.table("works").select("title_zh,title_en,cast_summary,director").eq("title_ja", title).limit(1).execute()
            if w_res.data:
                w_row = w_res.data[0]
                if not name_zh:
                    name_zh = w_row.get("title_zh")
                if not name_en:
                    name_en = w_row.get("title_en")
                if name_zh or name_en:
                    logger.info("  works fallback for %r → zh=%r en=%r", title, name_zh, name_en)
                works_performer = w_row.get("cast_summary")
                works_director = w_row.get("director")

        if not name_zh and not name_en:
            logger.warning("  ⚠ eiga.com lookup returned nothing for %s [%s]", event["id"][:8], title[:40])
            continue

        # Check field_corrections — don't overwrite locked values
        fc_res = (
            sb.table("field_corrections")
            .select("field_name")
            .eq("event_id", event["id"])
            .in_("field_name", ["name_zh", "name_en"])
            .execute()
        )
        locked_fields = {r["field_name"] for r in (fc_res.data or [])}

        old_name_zh = event.get("name_zh") or ""
        old_name_en = event.get("name_en") or ""

        update: dict[str, Any] = {}
        if name_zh and "name_zh" not in locked_fields:
            update["name_zh"] = name_zh
        if name_en and "name_en" not in locked_fields:
            update["name_en"] = name_en
        if not event.get("performer") and works_performer:
            update["performer"] = works_performer
        if not event.get("director") and works_director:
            update["director"] = works_director

        if not update:
            skipped_protected += 1
            logger.info("  skip %s (fields already locked)", event["id"][:8])
            continue

        # Also fix description fields that reference old (wrong) titles
        if name_zh and "name_zh" in update:
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

        if name_en and "name_en" in update:
            desc_en = event.get("description_en") or ""
            if desc_en:
                new_desc_en = _replace_title_in_desc(desc_en, [old_name_en], name_en)
                if new_desc_en != desc_en:
                    update["description_en"] = new_desc_en

        # Fix selection_reason — replace old titles in all three languages
        sr_raw = event.get("selection_reason") or ""
        if sr_raw and (name_zh or name_en):
            try:
                sr = json.loads(sr_raw) if isinstance(sr_raw, str) else sr_raw
                if isinstance(sr, dict):
                    sr_changed = False
                    if name_zh and sr.get("zh"):
                        for old_ref in ([old_name_zh, title] if source in _NEWS_MOVIE_SOURCES else [old_name_zh]):
                            if old_ref and old_ref != name_zh and old_ref in sr["zh"]:
                                sr["zh"] = sr["zh"].replace(old_ref, name_zh)
                                sr_changed = True
                    if name_en and sr.get("en"):
                        if old_name_en and old_name_en != name_en and old_name_en in sr["en"]:
                            sr["en"] = sr["en"].replace(old_name_en, name_en)
                            sr_changed = True
                    if name_zh and sr.get("ja"):
                        # ja text may reference the Chinese original title
                        if old_name_zh and old_name_zh != name_zh and old_name_zh in sr["ja"]:
                            sr["ja"] = sr["ja"].replace(old_name_zh, name_zh)
                            sr_changed = True
                    if sr_changed:
                        update["selection_reason"] = json.dumps(sr, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        if dry_run:
            logger.info("  [DRY RUN] would patch %s: %s", event["id"][:8], update)
        else:
            sb.table("events").update(update).eq("id", event["id"]).execute()
            _lock_fields_via_corrections(sb, event["id"], update)
            movie_patched += 1
            logger.info(
                "  ✓ movie enrich %s → zh=%r en=%r sr_fixed=%s",
                event["id"][:8], update.get("name_zh"), update.get("name_en"),
                "selection_reason" in update,
            )

    logger.info(
        "post_batch_enrich: done. movie_patched=%d skipped_protected=%d",
        movie_patched, skipped_protected,
    )
    return {"movie_patched": movie_patched, "skipped_protected": skipped_protected}


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


def backfill_performer_i18n() -> None:
    """Backfill performer_zh/en and director_zh/en for events that have
    performer/director but are missing translations.

    Three-layer strategy:
    1. Pure kanji names → performer_zh = performer (direct copy), performer_en = GPT romanize
    2. Works table → inherit cast_summary if available
    3. Katakana/latin names → GPT translate both zh and en

    AI-translated values get annotation markers:
    - zh: append "（AI翻譯）"
    - en: append "(AI translated)"
    - Direct copies (kanji→zh) and works-inherited values: no marker
    """
    import re as _re

    sb = _get_supabase()
    client = _get_openai()

    _KANJI_RE = _re.compile(r'^[\u4e00-\u9fff\u3000-\u303f\s、，,・\-－―]+$')

    # ── Fetch candidates ──
    res = sb.table("events").select(
        "id,performer,performer_zh,performer_en,"
        "director,director_zh,director_en,work_id"
    ).eq("is_active", True).not_.is_("performer", "null").or_(
        "performer_zh.is.null,performer_en.is.null"
    ).execute()
    perf_events = res.data or []

    dir_res = sb.table("events").select(
        "id,director,director_zh,director_en,work_id"
    ).eq("is_active", True).not_.is_("director", "null").or_(
        "director_zh.is.null,director_en.is.null"
    ).execute()
    dir_events = [e for e in (dir_res.data or []) if not e.get("director_zh") or not e.get("director_en")]

    logger.info("backfill_performer_i18n: %d performer candidates, %d director candidates",
                len(perf_events), len(dir_events))

    # ── Collect names needing GPT translation ──
    # Separate into: kanji-only (zh=copy, en=GPT) vs non-kanji (both=GPT)
    kanji_names: list[tuple[str, str, str]] = []    # (event_id, field_prefix, name)
    nonkanji_names: list[tuple[str, str, str]] = []  # (event_id, field_prefix, name)

    for e in perf_events:
        name = (e.get("performer") or "").strip()
        if not name:
            continue
        if _KANJI_RE.match(name):
            kanji_names.append((e["id"], "performer", name))
        else:
            nonkanji_names.append((e["id"], "performer", name))

    for e in dir_events:
        name = (e.get("director") or "").strip()
        if not name:
            continue
        if _KANJI_RE.match(name):
            kanji_names.append((e["id"], "director", name))
        else:
            nonkanji_names.append((e["id"], "director", name))

    # ── Layer 1: Pure kanji → zh = direct copy ──
    patched = 0
    for eid, prefix, name in kanji_names:
        update: dict[str, Any] = {}
        update[f"{prefix}_zh"] = name  # kanji IS Chinese — direct copy, no marker
        # en will be filled by GPT batch below
        if update:
            sb.table("events").update(update).eq("id", eid).execute()
            _lock_fields_via_corrections(sb, eid, update)
            patched += 1
            logger.info("  ✓ kanji %s %s_zh=%r", eid[:8], prefix, name)

    logger.info("backfill_performer_i18n: Layer 1 (kanji→zh) patched %d", patched)

    # ── Collect all names needing GPT romanization/translation ──
    # kanji names need en only; non-kanji names need both zh and en
    gpt_tasks: list[dict] = []

    for eid, prefix, name in kanji_names:
        gpt_tasks.append({"id": eid, "prefix": prefix, "name": name, "need_zh": False})

    for eid, prefix, name in nonkanji_names:
        gpt_tasks.append({"id": eid, "prefix": prefix, "name": name, "need_zh": True})

    if not gpt_tasks:
        logger.info("backfill_performer_i18n: no GPT tasks needed")
        return

    # ── GPT batch translation ──
    # Process in chunks of 20
    CHUNK = 20
    gpt_patched = 0
    for i in range(0, len(gpt_tasks), CHUNK):
        chunk = gpt_tasks[i:i + CHUNK]

        # Build prompt
        lines = []
        for idx, task in enumerate(chunk):
            if task["need_zh"]:
                lines.append(f'{idx}. "{task["name"]}" → zh + en')
            else:
                lines.append(f'{idx}. "{task["name"]}" → en only')

        prompt = (
            "Translate the following person names. For each:\n"
            "- 'zh + en': provide Traditional Chinese name AND English/romanized name\n"
            "- 'en only': provide English/romanized name only (the name is already Chinese)\n\n"
            "Rules:\n"
            "- For Taiwanese/Chinese persons: use their known Chinese name for zh\n"
            "- For Japanese persons: romanize using Hepburn (family name first)\n"
            "- For katakana foreign names (e.g. クー・チェンドン): look up the real Chinese/English name\n"
            "- Keep stage names / band names as-is in both languages\n"
            "- If multiple names separated by 、 or ,: translate each, keep same separator\n\n"
            "Return JSON array: [{\"idx\": 0, \"zh\": \"...\", \"en\": \"...\"}, ...]\n"
            "If 'en only', omit zh field.\n\n"
            + "\n".join(lines)
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a person name translator specializing in East Asian names."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
            # Handle bare [...] or {"results"|"translations"|"data"|...: [...]}
            if isinstance(raw, list):
                results = raw
            else:
                results = next((v for v in raw.values() if isinstance(v, list)), None)
            if not isinstance(results, list):
                logger.warning("  GPT returned unexpected format: %s", type(raw))
                continue
        except Exception as exc:
            logger.error("  GPT batch error: %s", exc)
            continue

        for item in results:
            idx = item.get("idx")
            if idx is None or idx >= len(chunk):
                continue
            task = chunk[idx]
            eid = task["id"]
            prefix = task["prefix"]

            update: dict[str, Any] = {}

            # zh translation (only for non-kanji names)
            zh_val = _to_trad(item.get("zh", "")).strip() if item.get("zh") else ""
            if zh_val and task["need_zh"]:
                update[f"{prefix}_zh"] = f"{zh_val}（AI翻譯）"

            # en translation (for all)
            en_val = (item.get("en") or "").strip()
            if en_val:
                update[f"{prefix}_en"] = f"{en_val} (AI translated)"

            if update:
                sb.table("events").update(update).eq("id", eid).execute()
                _lock_fields_via_corrections(sb, eid, update)
                gpt_patched += 1
                logger.info("  ✓ gpt %s %s → zh=%r en=%r",
                            eid[:8], prefix,
                            update.get(f"{prefix}_zh", "—"),
                            update.get(f"{prefix}_en", "—"))

    logger.info("backfill_performer_i18n: GPT patched %d/%d tasks", gpt_patched, len(gpt_tasks))
    logger.info("backfill_performer_i18n: total done (kanji_zh=%d, gpt=%d)", patched, gpt_patched)


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
            "  --backfill-performer-i18n  Backfill performer_zh/en and director_zh/en translations\n"
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
    backfill_perf_i18n = "--backfill-performer-i18n" in sys.argv
    dry_run_flag = "--dry-run" in sys.argv
    event_id_arg = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--id"), None)
    limit_arg_str = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--limit"), None)
    limit_arg = int(limit_arg_str) if limit_arg_str else 50
    if backfill_tier1:
        backfill_tier1_events(limit=limit_arg, dry_run=dry_run_flag)
    elif propagate_org:
        propagate_source_organizer(dry_run=dry_run_flag)
    elif backfill_perf_i18n:
        backfill_performer_i18n()
    elif enrich_movies:
        enrich_movie_titles()
    elif enrich_people:
        enrich_person_names()
    else:
        annotate_pending_events(re_annotate_all=re_all, fix_translations=fix_tr, fix_reviewed=fix_rev, event_id=event_id_arg)

