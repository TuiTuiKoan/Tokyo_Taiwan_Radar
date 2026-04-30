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
# ---------------------------------------------------------------------------
SEARCH_CATEGORIES = [
    {
        "id": "university",
        "label": "🏫 大學",
        "query_ja": "台湾 イベント セミナー 大学 東京 2026",
        "query_en": "Taiwan event seminar university Tokyo 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan-Japan academic exchange. "
            "Search the web for Japanese university departments, research centers, or student groups "
            "that regularly organize Taiwan-related lectures, seminars, or cultural events in Tokyo. "
            "Focus on finding pages that have a regularly updated public event listing — not just a single article."
        ),
    },
    {
        "id": "media",
        "label": "📰 媒體",
        "query_ja": "台湾 文化 イベント メディア ウェブマガジン 東京 2026",
        "query_en": "Taiwan cultural event media web magazine Tokyo 2026",
        "system_prompt": (
            "You are a research analyst specializing in Japanese media covering Taiwan. "
            "Search the web for Japanese online media, magazines, or platforms that regularly "
            "feature or list Taiwan-related cultural events in Japan. "
            "Prioritize sources with scrapable event listing pages."
        ),
    },
    {
        "id": "government",
        "label": "🏛️ 政府機關",
        "query_ja": "台湾 交流 イベント 公的機関 財団法人 東京 2026",
        "query_en": "Taiwan exchange event government foundation Tokyo 2026",
        "system_prompt": (
            "You are a research analyst specializing in Japan-Taiwan governmental and public exchange. "
            "Search the web for Japanese government agencies, public foundations, or official bodies "
            "that organize Taiwan-related events or cultural exchange programs. "
            "Look for pages with a structured events calendar or listing."
        ),
    },
    {
        "id": "thinktank",
        "label": "🔬 智庫・研究機構",
        "query_ja": "台湾 研究 シンポジウム シンクタンク 講演会 東京 2026",
        "query_en": "Taiwan research symposium think tank lecture Tokyo 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan-focused policy and academic institutions. "
            "Search the web for Japanese think tanks, research institutes, or NPOs that regularly hold "
            "Taiwan-related symposia, lectures, or study meetings. "
            "Prioritize organizations with public event calendars."
        ),
    },
    {
        "id": "social",
        "label": "💬 社群",
        "query_ja": "台湾 コミュニティ 交流会 東京 2026 connpass doorkeeper",
        "query_en": "Taiwan community meetup Tokyo 2026 connpass doorkeeper",
        "system_prompt": (
            "You are a research analyst specializing in grassroots Taiwan communities in Japan. "
            "Search the web for community groups, meetup organizers, or event series that regularly "
            "hold Taiwan-related social events or exchange meetups in Tokyo. "
            "Check platforms like Connpass, Doorkeeper, or dedicated community sites."
        ),
    },
    {
        "id": "performing_arts_search",
        "label": "🎭 表演・映画",
        "query_ja": "台湾 コンサート 公演 映画 上映 東京 2026 チケット eplus pia",
        "query_en": "Taiwan concert performing arts film screening Japan 2026 ticket",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan performing arts and cinema events in Japan. "
            "Search the web for websites, ticketing platforms, or event listing pages that regularly "
            "feature Taiwan-related concerts, theater or dance performances, or film screenings in Japan. "
            "Check major ticketing platforms (eplus.jp, pia.jp, ticket.rakuten.co.jp, l-tike.com), "
            "cinema listing sites (cinematoday.jp, filmarks.com), and venue websites. "
            "Also look for Taiwan artist agency pages, Taiwan film distributor sites operating in Japan, "
            "or film festival pages (台湾映画祭, etc.). "
            "Prioritize pages with a structured and regularly updated event listing."
        ),
    },
    {
        "id": "senses_research",
        "label": "🧬 五感研究",
        "query_ja": "台湾 五感 体験 研究 論文 食文化 香り 感覚 アート 2025 2026 jstage OR cinii",
        "query_en": "Taiwan five senses sensory experience research paper academic publication 2025 2026",
        "system_prompt": (
            "You are a research analyst specializing in academic publications on Taiwan sensory culture. "
            "Search academic databases (J-STAGE at jstage.jst.go.jp, CiNii at ci.nii.ac.jp, "
            "Google Scholar, ResearchGate, and Taiwan scholarly databases) for recent journal articles, "
            "conference papers, or research reports related to Taiwan sensory experiences (五感体験), "
            "including food culture, scent or aroma events, tactile art, sound art, or multisensory "
            "cultural programming originating from or about Taiwan. "
            "Also search for new publications from Taiwan academic groups or universities on "
            "sensory culture or cross-cultural sensory studies. "
            "Return pages with a publication list or index, not individual article pages."
        ),
    },
    {
        "id": "fukuoka",
        "label": "🍜 福岡・九州",
        "query_ja": "台湾 イベント 文化交流 公演 展示 福岡 九州 2026",
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
    {
        "id": "hokkaido",
        "label": "🏔️ 北海道・東北",
        "query_ja": "台湾 イベント 文化交流 展示 公演 北海道 札幌 東北 仙台 2026",
        "query_en": "Taiwan cultural event exhibition performance Hokkaido Sapporo Tohoku Sendai 2026",
        "system_prompt": (
            "You are a research analyst specializing in Taiwan cultural events in Hokkaido and Tohoku, Japan. "
            "Search the web for websites, organizations, or platforms that regularly list Taiwan-related "
            "cultural events (exhibitions, concerts, film screenings, festivals, lectures) in Hokkaido "
            "(especially Sapporo) or Tohoku prefectures (Sendai and surroundings). "
            "Include the Sapporo International Art Festival (SIAF), local Taiwan community groups, "
            "the Sendai Consulate area if any Taiwan-organized events exist, "
            "and ticketing platforms like Peatix or Connpass for these regions. "
            "Focus on sources with a structured and regularly updated event listing."
        ),
    },
]

# ---------------------------------------------------------------------------
# 4-slot daily schedule (Layer 1 — 4 runs per day at 06/12/18/24 JST)
# RESEARCH_SLOT env var (0–3) selects which categories to run this slot.
# Each slot runs 2–3 categories; all 9 categories complete within a day.
# ---------------------------------------------------------------------------
SLOT_SCHEDULE: dict[int, list[str]] = {
    0: ["university", "fukuoka"],                             # 06:00 JST
    1: ["media", "government"],                              # 12:00 JST
    2: ["thinktank", "hokkaido"],                            # 18:00 JST
    3: ["social", "performing_arts_search", "senses_research"],  # 24:00 JST (00:00+1)
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
      "category": "university|media|government|thinktank|social",
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


