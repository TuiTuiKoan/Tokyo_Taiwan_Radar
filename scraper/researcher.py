"""
Daily automated research: discovers new Taiwan-related event sources in Japan.

Uses gpt-4o-search-preview (real web search) with 7 CategoryAgents that rotate
Mon–Sun (one per day). Each run searches one category, Playwright-verifies
results, upserts to research_sources, and reports via LINE.

Usage:
    python researcher.py                           # today's scheduled category
    python researcher.py --category university     # override to specific category
    python researcher.py --dry-run                 # run without saving to DB or LINE
    python researcher.py --dry-run --category social
    python researcher.py --test-line               # test LINE notification only
"""

import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from supabase import create_client

from line_notify import send_line_message

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar"

# ---------------------------------------------------------------------------
# Search categories — one agent per category
# 12 categories mapped to the site's 28 Category types (web/lib/types.ts)
# ---------------------------------------------------------------------------
SEARCH_CATEGORIES = [
    # ── Slot 0 (06:00 JST) ──────────────────────────────────────────────────
    {
        "id": "cinema_screening",
        "label": "🎬 映画・上映",
        "site_categories": ["movie", "drama"],
        "query_ja": "台湾映画 上映 映画祭 シネマ 日本 2026",
        "query_en": "Taiwan film screening cinema festival Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan cinema and film distribution in Japan. "
            "Search the web for cinemas, film festivals, streaming platforms, or distribution companies "
            "that regularly screen or distribute Taiwan films in Japan. "
            "Look for dedicated Taiwan film pages, annual festival event listings "
            "(e.g. 台湾映画祭, OAFF, 東京フィルメックス), or cinema venue event calendars. "
            "Prioritize sources with a structured and regularly updated screening schedule."
        ),
    },
    {
        "id": "art_exhibition",
        "label": "🎨 美術・展示",
        "site_categories": ["art", "exhibition", "senses", "indigenous"],
        "query_ja": "台湾 アート 展覧会 展示 ギャラリー 美術館 日本 2026",
        "query_en": "Taiwan art exhibition gallery museum Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan contemporary art and exhibitions in Japan. "
            "Search the web for museums, galleries, art centers, or cultural spaces that regularly host "
            "Taiwan-related art exhibitions, installations, or craft shows in Japan. "
            "Include public art museums (e.g. MOT, Fukuoka Asian Art Museum), "
            "Taiwan artist residency programs, and independent gallery spaces. "
            "Prioritize venues with a public event or exhibition calendar updated regularly."
        ),
    },
    {
        "id": "music_live",
        "label": "🎵 音楽・ライブ",
        "site_categories": ["performing_arts"],
        "query_ja": "台湾 アーティスト ライブ コンサート 公演 来日 日本 2026",
        "query_en": "Taiwan artist live concert performance Japan tour 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan music and live performance in Japan. "
            "Search the web for live venues, concert promoters, ticketing platforms, or fan community sites "
            "that regularly list Taiwan indie or pop artist tour dates in Japan. "
            "Check venue sites (Zepp, shibuya eggman, etc.), "
            "promoter sites (BIG ROMANTIC ENTERTAINMENT, HOLIDAY! RECORDS, etc.), "
            "and Taiwan artist agency pages. "
            "Prioritize sources with a regularly updated upcoming shows list."
        ),
    },
    # ── Slot 1 (12:00 JST) ──────────────────────────────────────────────────
    {
        "id": "food_retail",
        "label": "🍜 食・物産・ショップ",
        "site_categories": ["lifestyle_food", "retail", "nature", "tourism"],
        "query_ja": "台湾 グルメ フード イベント 物産展 フェア ショップ 日本 2026",
        "query_en": "Taiwan food gourmet fair market shop retail event Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan food culture and retail events in Japan. "
            "Search the web for websites, organizers, or platforms that regularly list Taiwan-related "
            "food festivals, night market events, tea ceremonies, restaurant promotions, "
            "department store Taiwan fairs (台湾フェア, 物産展), or Taiwan specialty shops in Japan. "
            "Also look for Taiwan agriculture or nature product events, "
            "and travel or tourism events introducing Taiwan destinations. "
            "Prioritize sources with a scheduled and regularly updated event listing."
        ),
    },
    {
        "id": "books_media",
        "label": "📚 書籍・出版・新聞・メディア",
        "site_categories": ["books_media", "literature", "tv_program"],
        "query_ja": "台湾 書籍 出版 文学 翻訳 読書会 トークイベント 新聞 共催 展覧会 日本 2026",
        "query_en": "Taiwan books publishing literature author talk newspaper co-sponsored event Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan literature, publishing, and media events in Japan. "
            "Search the web for TWO types of sources — both must have a structured, regularly updated event listing page:\n"
            "\n"
            "Type 1 — Publishers, bookstores, and literary organizations:\n"
            "Japanese publishers, bookstores, or libraries that regularly host Taiwan-related author talks, "
            "book launches, translation workshops, or reading clubs. "
            "Check: major bookstores (Kinokuniya, Tsutaya, eslite), literary festival sites, "
            "publishers specializing in Taiwan literature translations "
            "(e.g. 白水社, 河出書房新社, 岩波書店, 春秋社), "
            "and Taiwanese author Japan tour organizer pages.\n"
            "\n"
            "Type 2 — Newspaper and broadcaster event listing pages (NOT individual news articles):\n"
            "Major Japanese newspapers and broadcasters maintain dedicated event calendar pages where they "
            "list exhibitions, concerts, and cultural programs they co-sponsor or endorse. "
            "These pages list real ticketed events, not news articles. Target:\n"
            "  - 朝日新聞 event page (asahi.com/event/)\n"
            "  - 読売新聞 event page (event.yomiuri.co.jp)\n"
            "  - 毎日新聞 event page (event.mainichi.co.jp)\n"
            "  - 日本経済新聞 event page (nikkei.com/event/)\n"
            "  - 産経新聞 event / culture page\n"
            "  - Regional newspapers: 北海道新聞, 中日新聞, 西日本新聞, 河北新報, etc.\n"
            "  - NHK culture programs featuring Taiwan content\n"
            "Search specifically for Taiwan-themed exhibitions or cultural events co-sponsored by these papers. "
            "DO NOT return individual news article URLs — only event listing index pages. "
            "Prioritize sources where Taiwan-related events appear at least 2–3 times per year."
        ),
    },
    {
        "id": "tech_business",
        "label": "💻 テック・ビジネス",
        "site_categories": ["tech", "business"],
        "query_ja": "台湾 IT スタートアップ テック ビジネス 交流 セミナー 日本 2026",
        "query_en": "Taiwan IT startup tech business networking seminar Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan-Japan technology and business exchange. "
            "Search the web for organizations, platforms, or event series that regularly list "
            "Taiwan-related tech, startup, or business events in Japan. "
            "Check JETRO events, TAITRA (台湾貿易センター) Japan offices, "
            "Taiwan startup accelerators with Japan presence, "
            "IT industry associations, and tech meetup communities (Connpass, Doorkeeper). "
            "Prioritize sources with a public and regularly updated event calendar."
        ),
    },
    # ── Slot 2 (18:00 JST) ──────────────────────────────────────────────────
    {
        "id": "academic_lecture",
        "label": "🏫 学術・講演・歴史",
        "site_categories": ["academic", "lecture", "history", "taiwan_mandarin"],
        "query_ja": "台湾 大学 シンポジウム 講演会 研究 中国語 歴史 文化 日本 2026",
        "query_en": "Taiwan university symposium lecture research history language Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan-Japan academic and cultural exchange. "
            "Search the web for Japanese universities, research institutes, think tanks, NPOs, or "
            "language schools that regularly host Taiwan-related lectures, symposia, seminars, "
            "or language/cultural programs in Japan. "
            "Include Mandarin Chinese language programs tied to Taiwan culture, "
            "Taiwan studies departments, and Japan-Taiwan academic exchange organizations. "
            "Prioritize sources with a public event calendar updated regularly."
        ),
    },
    {
        "id": "geopolitics_policy",
        "label": "🏛️ 地政・政策・交流",
        "site_categories": ["geopolitics", "taiwan_japan"],
        "query_ja": "台湾 外交 政策 交流 財団法人 公的機関 シンクタンク 講演 日本 2026",
        "query_en": "Taiwan diplomacy policy exchange government foundation think tank Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Japan-Taiwan geopolitical and policy exchange. "
            "Search the web for Japanese government agencies, public foundations, official bodies, "
            "think tanks, or research institutes that regularly organize Taiwan-related policy events, "
            "diplomatic exchange programs, or public lectures on Taiwan-Japan relations. "
            "Include organizations like 日本台湾交流協会, 台湾協会, NPOs specializing in cross-strait affairs, "
            "and security/foreign policy think tanks. "
            "Look for pages with a structured events calendar or lecture listing."
        ),
    },
    {
        "id": "gender_society",
        "label": "🏳️‍🌈 ジェンダー・社会・健康",
        "site_categories": ["gender", "urban", "healthcare"],
        "query_ja": "台湾 LGBTQ ジェンダー 多様性 社会 健康 医療 福祉 イベント 日本 2026",
        "query_en": "Taiwan LGBTQ gender diversity social health welfare event Japan 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan-related gender, social, and health events in Japan. "
            "Search the web for organizations, community groups, NPOs, or platforms that regularly "
            "list Taiwan-related LGBTQ+ events, gender equality seminars, Pride-related programs, "
            "social welfare exchanges, or health and medical exchange programs between Japan and Taiwan. "
            "Taiwan is a leader in Asia for LGBTQ+ rights — look for cross-border advocacy events, "
            "queer film screenings, Taiwan Pride outreach programs, and health policy exchanges. "
            "Prioritize sources with a public event listing updated at least monthly."
        ),
    },
    # ── Slot 3 (00:00 JST) ──────────────────────────────────────────────────
    {
        "id": "community_social",
        "label": "💬 コミュニティ・交流",
        "site_categories": ["taiwan_japan", "competition", "workshop"],
        "query_ja": "台湾 コミュニティ 交流会 ワークショップ 体験 在日台湾人 日本 2026 connpass doorkeeper peatix",
        "query_en": "Taiwan community meetup workshop experience Japan 2026 connpass doorkeeper",
        "system_prompt": (
            "You are a research analyst specializing in grassroots Taiwan communities in Japan. "
            "Search the web for community groups, meetup organizers, event series, or platforms "
            "that regularly hold Taiwan-related social events, exchange meetups, language exchanges, "
            "cooking workshops, or cultural experience events in Japan. "
            "Check Connpass, Doorkeeper, Peatix, and dedicated community sites "
            "for active organizers with a history of Taiwan-related events. "
            "Also look for Taiwan alumni associations, regional friendship groups, "
            "and Taiwan cultural workshop programs. "
            "Prioritize active organizers with events in the past 3 months."
        ),
    },
    {
        "id": "kansai",
        "label": "🏯 関西（大阪・京都・神戸）",
        "site_categories": [],
        "query_ja": "台湾 イベント 文化交流 公演 展示 大阪 京都 神戸 兵庫 関西 2026",
        "query_en": "Taiwan cultural event exhibition performance Osaka Kyoto Kobe Kansai 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan cultural events in the Kansai region of Japan. "
            "Search the web for websites, organizations, or platforms that regularly list Taiwan-related "
            "cultural events (exhibitions, concerts, film screenings, festivals, lectures) in Osaka, "
            "Kyoto, Kobe, or other Kansai prefectures (Nara, Shiga, Wakayama, Mie). "
            "Include the Osaka Asian Film Festival (OAFF), Taiwan office in Osaka "
            "(台北駐大阪経済文化弁事処), Kansai Taiwan community groups, "
            "and ticketing platforms like Peatix or Connpass for this region. "
            "Focus on sources with a structured and regularly updated event listing."
        ),
    },
    {
        "id": "fukuoka",
        "label": "🍜 福岡・九州",
        "site_categories": [],
        "query_ja": "台湾 イベント 文化交流 公演 展示 福岡 九州 熊本 鹿児島 2026",
        "query_en": "Taiwan cultural event exhibition performance Fukuoka Kyushu 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan cultural events in Fukuoka and Kyushu, Japan. "
            "Search the web for websites, organizations, or platforms that regularly list Taiwan-related "
            "cultural events (exhibitions, concerts, film screenings, festivals, lectures) in Fukuoka or "
            "other Kyushu prefectures. "
            "Include the Taipei Economic and Cultural Office Fukuoka (台北駐福岡経済文化弁事処), "
            "Fukuoka Asian Art Museum (福岡アジア美術館), local Taiwan community groups, "
            "ticketing platforms like Peatix, Connpass, or cultural institutions in the region. "
            "Focus on sources with a structured and regularly updated event listing."
        ),
    },
]

# ---------------------------------------------------------------------------
# 4-slot daily schedule (12 categories × 4 slots, 3 per slot)
# RESEARCH_SLOT env var (0–3) selects which categories to run this slot.
# All 12 categories complete within one 24-hour cycle.
#
# Slot 0 (06:00 JST) — 映像・アート
# Slot 1 (12:00 JST) — 食・書籍・テック
# Slot 2 (18:00 JST) — 学術・地政・社会
# Slot 3 (00:00 JST) — コミュニティ・地域
# ---------------------------------------------------------------------------
SLOT_SCHEDULE: dict[int, list[str]] = {
    0: ["cinema_screening", "art_exhibition", "music_live"],         # 06:00 JST
    1: ["food_retail", "books_media", "tech_business"],              # 12:00 JST
    2: ["academic_lecture", "geopolitics_policy", "gender_society"], # 18:00 JST
    3: ["community_social", "kansai", "fukuoka"],                    # 00:00 JST (00:00+1)
}

# Legacy weekday schedule kept for --category CLI override reference
WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


def _resolve_slot() -> int:
    """Return the current slot (0–3) from RESEARCH_SLOT env var, else derive from JST hour."""
    env_slot = os.environ.get("RESEARCH_SLOT")
    if env_slot is not None:
        return int(env_slot) % 4
    # Fallback: derive slot from JST hour (00–05→3, 06–11→0, 12–17→1, 18–23→2)
    hour = datetime.now(JST).hour
    if hour < 6:
        return 3
    elif hour < 12:
        return 0
    elif hour < 18:
        return 1
    else:
        return 2


def _resolve_category_id(weekday: int | None = None) -> list[str]:
    """Return list of category IDs to run for the current slot."""
    slot = _resolve_slot()
    return SLOT_SCHEDULE.get(slot, ["university"])


def _schedule_summary() -> str:
    """One-line slot schedule overview."""
    cat_label = {cat["id"]: cat["label"].split()[0] for cat in SEARCH_CATEGORIES}
    parts = []
    for slot, cats in SLOT_SCHEDULE.items():
        jst_hour = [6, 12, 18, 24][slot]
        labels = "|".join(cat_label[c] for c in cats)
        parts.append(f"{jst_hour:02d}時{labels}")
    return "  ".join(parts)


SOURCE_SCHEMA = """{
  "sources": [
    {
      "name": "Website/organization name",
      "url": "Direct URL to their events listing page",
      "category": "cinema_screening|art_exhibition|music_live|food_retail|books_media|tech_business|academic_lecture|geopolitics_policy|gender_society|community_social|kansai|fukuoka",
      "event_types": "What kind of events they post",
      "frequency": "daily|weekly|monthly",
      "scraping_feasibility": "easy|medium|hard",
      "reason": "1-2 sentences why this source is valuable"
    }
  ],
  "news_summary": ["bullet 1", "bullet 2"],
  "trend_keywords": ["keyword1", "keyword2"]
}"""

EXISTING_SOURCES = "peatix.com, roc-taiwan.org/jp (Taiwan Cultural Center), taioan-dokyokai"

# Where candidate JSON files are written for @Researcher agent to pick up
CANDIDATES_DIR = Path(__file__).parent.parent / ".copilot-tracking" / "research" / "candidates"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CategoryResult:
    category_id: str
    sources: list[dict] = field(default_factory=list)
    news_summary: list[str] = field(default_factory=list)
    trend_keywords: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# URL verification with Playwright
# ---------------------------------------------------------------------------
def _verify_url(url: str) -> dict:
    """Open URL with Playwright headless Chrome and check it's a real event page."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, timeout=12000, wait_until="domcontentloaded")
            title = (page.title() or "").lower()
            text_len = len(page.inner_text("body"))
            browser.close()
            is_valid = (
                text_len > 300
                and "404" not in title
                and "not found" not in title
                and "error" not in title
                and "お探しのページ" not in title
            )
            return {"url_verified": is_valid, "url_status": 200 if is_valid else 404}
    except Exception as exc:
        logger.debug("URL verification failed for %s: %s", url, exc)
        return {"url_verified": False, "url_status": 0}


# ---------------------------------------------------------------------------
# Per-category agent
# ---------------------------------------------------------------------------
class CategoryAgent:
    def __init__(self, category: dict, client: OpenAI, known_urls: dict[str, str] | None = None):
        self.category = category
        self.client = client
        self.known_urls = known_urls or {}

    def run(self) -> CategoryResult:
        cat = self.category
        today = datetime.now(JST).strftime("%Y-%m-%d")
        logger.info("CategoryAgent[%s]: starting search", cat["id"])

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-search-preview",
                messages=[
                    {"role": "system", "content": cat["system_prompt"]},
                    {
                        "role": "user",
                        "content": (
                            f"Today is {today}.\n"
                            f"Search for: {cat['query_ja']}\n"
                            f"Also search: {cat['query_en']}\n\n"
                            f"Find up to 3 event source websites NOT already in: {EXISTING_SOURCES}\n\n"
                            + (f"SKIP these already-known URLs (do not suggest them again): {', '.join(sorted(self.known_urls.keys())[:30])}\n\n" if self.known_urls else "")
                            + f"Also provide 2-3 recent Taiwan-related news bullets and top trend keywords.\n\n"
                            f"Respond ONLY as valid JSON matching this schema:\n{SOURCE_SCHEMA}"
                        ),
                    },
                ],
                # gpt-4o-search-preview does not support response_format or temperature
            )

            usage = response.usage
            text = response.choices[0].message.content or "{}"

            # Strip markdown code fences if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            data = json.loads(text)
            sources = data.get("sources", [])

            # Playwright URL verification
            for src in sources:
                if src.get("url"):
                    verification = _verify_url(src["url"])
                    src.update(verification)
                else:
                    src["url_verified"] = False
                    src["url_status"] = 0

            verified = sum(1 for s in sources if s.get("url_verified"))
            logger.info(
                "CategoryAgent[%s]: %d sources (%d verified)",
                cat["id"], len(sources), verified,
            )

            return CategoryResult(
                category_id=cat["id"],
                sources=sources,
                news_summary=data.get("news_summary", []),
                trend_keywords=data.get("trend_keywords", []),
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
            )

        except Exception as exc:
            logger.error("CategoryAgent[%s] failed: %s", cat["id"], exc)
            return CategoryResult(category_id=cat["id"], error=str(exc))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def _get_openai() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")
    return OpenAI(api_key=api_key)


def _get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _get_known_urls(sb) -> dict[str, str]:
    """Fetch all known URLs and their statuses from research_sources table."""
    try:
        rows = sb.table("research_sources").select("url,status").execute()
        return {r["url"]: r["status"] for r in (rows.data or [])}
    except Exception as exc:
        logger.warning("Could not fetch known URLs: %s", exc)
        return {}


def _upsert_sources(sb, sources: list[dict], known_urls: dict[str, str]) -> tuple[int, int]:
    """Upsert verified sources to research_sources. Returns (new_count, skipped_count)."""
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    new_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc).isoformat()

    for src in sources:
        if not src.get("url_verified"):
            continue
        url = src.get("url", "")
        existing_status = known_urls.get(url)

        if existing_status and existing_status not in ("candidate",):
            # Higher-status rows (researched, recommended, implemented, not-viable)
            # — only bump last_seen_at, never downgrade status
            try:
                sb.table("research_sources").update({"last_seen_at": now}).eq("url", url).execute()
            except Exception:
                pass
            skipped_count += 1
            continue

        row = {
            "name": src.get("name", ""),
            "url": url,
            "agent_category": src.get("agent_category", ""),
            "category": src.get("category", ""),
            "status": "candidate",
            "scraping_feasibility": src.get("scraping_feasibility", ""),
            "event_types": src.get("event_types", ""),
            "frequency": src.get("frequency", ""),
            "reason": src.get("reason", ""),
            "url_verified": True,
            "last_seen_at": now,
        }
        if not existing_status:
            row["first_seen_at"] = now

        try:
            sb.table("research_sources").upsert(row, on_conflict="url").execute()
        except Exception as exc:
            logger.warning("Could not upsert source %s: %s", url, exc)
            continue

        # Write candidate JSON for @Researcher agent
        slug = re.sub(r"[^a-z0-9]+", "-", src.get("name", "unknown").lower()).strip("-")
        candidate_path = CANDIDATES_DIR / f"{slug}.json"
        candidate_path.write_text(json.dumps(src, ensure_ascii=False, indent=2))
        new_count += 1

    return new_count, skipped_count


def run_all_agents(client: OpenAI, known_urls: dict[str, str] | None = None) -> list[CategoryResult]:
    """Run all 5 CategoryAgents in parallel."""
    agents = [CategoryAgent(cat, client, known_urls or {}) for cat in SEARCH_CATEGORIES]
    results: list[CategoryResult] = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(agent.run): agent for agent in agents}
        for future in as_completed(futures):
            results.append(future.result())
    # Preserve original category order
    order = {cat["id"]: i for i, cat in enumerate(SEARCH_CATEGORIES)}
    return sorted(results, key=lambda r: order.get(r.category_id, 99))


def merge_results(results: list[CategoryResult]) -> dict:
    """Merge all CategoryResults into a single report dict."""
    all_sources = []
    all_news: list[str] = []
    all_keywords: list[str] = []

    for r in results:
        for src in r.sources:
            src["agent_category"] = r.category_id
        all_sources.extend(r.sources)
        all_news.extend(r.news_summary)
        all_keywords.extend(r.trend_keywords)

    # Deduplicate keywords, preserve order
    seen: set[str] = set()
    unique_keywords = [k for k in all_keywords if not (k in seen or seen.add(k))]  # type: ignore[func-returns-value]

    # Sort: verified sources first
    all_sources.sort(key=lambda s: (not s.get("url_verified", False)))

    return {
        "top_sources": all_sources,
        "news_summary": all_news[:5],
        "trend_keywords": unique_keywords[:8],
        "category_suggestions": [],
        "agents_run": len(results),
        "agents_failed": sum(1 for r in results if r.error),
    }


def _format_line_message(report: dict, results: list[CategoryResult], category: dict) -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    slot = _resolve_slot()
    jst_hours = [6, 12, 18, 24]
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    cost = (total_in * 30 + total_out * 60) / 1_000_000

    cat_labels = " + ".join(
        next(c["label"] for c in SEARCH_CATEGORIES if c["id"] == r.category_id)
        for r in results
    )

    verified_sources = [s for s in report.get("top_sources", []) if s.get("url_verified")]
    unverified = [s for s in report.get("top_sources", []) if not s.get("url_verified")]

    lines = [
        "📡 Tokyo Taiwan Radar — 每日研究報告",
        f"日期：{today}  |  Slot {slot} ({jst_hours[slot]:02d}:00 JST)",
        f"類別：{cat_labels}",
        f"模型：gpt-4o-search-preview × {len(results)} agents",
        f"費用：${cost:.4f} USD",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"✅ 已驗證來源 ({len(verified_sources)})",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    icons = {
        "university": "🏫",
        "media": "📰",
        "government": "🏛️",
        "thinktank": "🔬",
        "social": "💬",
        "performing_arts_search": "🎭",
        "senses_research": "🧬",
    }
    feasibility_stars = {"easy": "⭐⭐⭐", "medium": "⭐⭐", "hard": "⭐"}

    for i, src in enumerate(verified_sources[:5], 1):
        icon = icons.get(src.get("agent_category", src.get("category", "")), "📎")
        stars = feasibility_stars.get(src.get("scraping_feasibility", ""), "?")
        lines.extend([
            "",
            f"{i}. {icon} {src.get('name', '?')}",
            f"   {src.get('url', '?')}",
            f"   {src.get('event_types', '')} | {stars} | {src.get('frequency', '')}",
            f"   {src.get('reason', '')}",
        ])

    if unverified:
        lines.extend(["", f"⚠️ 未驗證來源 {len(unverified)} 個（URL 無效，已排除）"])

    news = report.get("news_summary", [])
    if news:
        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "📰 台灣相關新聞摘要"])
        for item in news:
            lines.append(f"• {item}")

    keywords = report.get("trend_keywords", [])
    if keywords:
        lines.extend(["", f"🔑 趨勢關鍵字: {', '.join(keywords[:6])}"])

    if report.get("agents_failed"):
        lines.extend(["", f"⚠️ {report['agents_failed']} 個 agent 執行失敗"])

    lines.extend([
        "",
        "📅 今日排程：" + _schedule_summary(),
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "在 /admin/research 查看完整報告 + 建立爬蟲 Issue",
    ])
    return "\n".join(lines)


def run_research(dry_run: bool = False, category_id: str | None = None) -> None:
    # Resolve which categories to run
    if category_id:
        category_ids = [category_id]
    else:
        category_ids = _resolve_category_id()

    slot = _resolve_slot()
    category_map = {cat["id"]: cat for cat in SEARCH_CATEGORIES}

    # Validate
    for cid in category_ids:
        if cid not in category_map:
            logger.error(
                "Unknown category_id '%s'. Valid: %s", cid, list(category_map)
            )
            return

    logger.info(
        "Starting research: slot=%d, categories=%s, dry_run=%s",
        slot, category_ids, dry_run,
    )
    ai = _get_openai()
    sb = None if dry_run else _get_supabase()

    # Fetch known URLs to skip (only when writing to DB)
    known_urls: dict[str, str] = {}
    if sb:
        known_urls = _get_known_urls(sb)
        logger.info("Known URLs to skip: %d", len(known_urls))

    # Run one agent per category in this slot
    results: list[CategoryResult] = []
    for cid in category_ids:
        category = category_map[cid]
        logger.info("Running agent: %s (%s)", cid, category["label"])
        agent = CategoryAgent(category, ai, known_urls)
        result = agent.run()
        results.append(result)

    report = merge_results(results)

    verified = sum(1 for s in report["top_sources"] if s.get("url_verified"))
    logger.info(
        "Research complete: slot=%d, %d categories, %d sources, %d verified",
        slot, len(results), len(report["top_sources"]), verified,
    )

    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    cost = (total_in * 30 + total_out * 60) / 1_000_000

    # Use first category's metadata for LINE label
    primary_category = category_map[category_ids[0]]

    if dry_run:
        verified_sources = [s for s in report["top_sources"] if s.get("url_verified")]
        logger.info(
            "Dry run — would upsert %d new sources, skip %d known",
            len(verified_sources), len(known_urls)
        )
        logger.info("Report preview: %s", json.dumps(report, ensure_ascii=False, indent=2)[:500])
        return

    # Upsert verified sources to research_sources + write candidate files
    try:
        new_count, skipped_count = _upsert_sources(
            sb,
            report["top_sources"],
            known_urls,
        )
        logger.info("research_sources: %d new candidates, %d skipped (already known)", new_count, skipped_count)
    except Exception as exc:
        logger.warning("Could not upsert research_sources: %s", exc)

    # Filter duplicate sources (already in DB before this run) out of the report.
    # known_urls was fetched before running agents, so it correctly represents
    # the pre-run state. Duplicates are silently dropped — not sent via LINE.
    report["top_sources"] = [
        s for s in report["top_sources"]
        if s.get("url") not in known_urls
    ]

    # Save to DB
    try:
        sb.table("research_reports").insert({
            "report_type": "source_discovery",
            "content": report,
        }).execute()
        logger.info("Report saved to research_reports table")
    except Exception as exc:
        logger.warning("Could not save report to DB: %s", exc)

    # Log cost to scraper_runs
    slot_label = "+".join(category_map[c]["label"].split()[0] for c in category_ids)
    try:
        sb.table("scraper_runs").insert({
            "source": f"researcher/slot{slot}",
            "events_processed": len(report["top_sources"]),
            "openai_tokens_in": total_in,
            "openai_tokens_out": total_out,
            "cost_usd": round(cost, 6),
            "notes": f"gpt-4o-search-preview × {len(results)} agents ({slot_label}), {verified} verified",
        }).execute()
    except Exception:
        pass

    # Send LINE — only if there are genuinely new verified sources
    new_verified = [s for s in report["top_sources"] if s.get("url_verified")]
    if not new_verified:
        logger.info("No new sources found this slot — skipping LINE notification.")
    else:
        msg = _format_line_message(report, results, primary_category)
        send_line_message(msg)
    logger.info("Daily research slot %d complete.", slot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Parse --category NAME or --category=NAME
    _argv = sys.argv[1:]
    _category_arg: str | None = None
    for _i, _arg in enumerate(_argv):
        if _arg == "--category" and _i + 1 < len(_argv):
            _category_arg = _argv[_i + 1]
        elif _arg.startswith("--category="):
            _category_arg = _arg.split("=", 1)[1]

    if "--test-line" in _argv:
        send_line_message("✅ Tokyo Taiwan Radar LINE 通知測試成功！")
        print("Test message sent.")
    elif "--dry-run" in _argv:
        run_research(dry_run=True, category_id=_category_arg)
    else:
        run_research(category_id=_category_arg)


