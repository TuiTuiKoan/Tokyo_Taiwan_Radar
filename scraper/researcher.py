"""
Daily automated research: discovers new Taiwan-related event sources in Japan.

Uses gpt-4o-search-preview (real web search) with 5 parallel CategoryAgents,
one per domain. Each agent searches independently, then results are merged,
Playwright-verified, and reported via LINE.

Usage:
    python researcher.py                  # full research run
    python researcher.py --dry-run        # run without saving to DB or LINE
    python researcher.py --test-line      # test LINE notification only
"""

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

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
]

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
    def __init__(self, category: dict, client: OpenAI):
        self.category = category
        self.client = client

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
                            f"Also provide 2-3 recent Taiwan-related news bullets and top trend keywords.\n\n"
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


def run_all_agents(client: OpenAI) -> list[CategoryResult]:
    """Run all 5 CategoryAgents in parallel."""
    agents = [CategoryAgent(cat, client) for cat in SEARCH_CATEGORIES]
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


def _format_line_message(report: dict, results: list[CategoryResult]) -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    cost = (total_in * 30 + total_out * 60) / 1_000_000  # search-preview pricing

    verified_sources = [s for s in report.get("top_sources", []) if s.get("url_verified")]
    unverified = [s for s in report.get("top_sources", []) if not s.get("url_verified")]

    lines = [
        "📡 Tokyo Taiwan Radar — 每日研究報告",
        f"日期：{today}",
        f"模型：gpt-4o-search-preview × {report.get('agents_run', 5)} agents",
        f"費用：${cost:.4f} USD",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"✅ 已驗證來源 ({len(verified_sources)})",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    icons = {"university": "🏫", "media": "📰", "government": "🏛️", "thinktank": "🔬", "social": "💬"}
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

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━",
                  "在 /admin/research 查看完整報告 + 建立爬蟲 Issue"])
    return "\n".join(lines)


def run_research(dry_run: bool = False) -> None:
    logger.info("Starting daily research (dry_run=%s)...", dry_run)
    ai = _get_openai()
    sb = None if dry_run else _get_supabase()

    # Run 5 parallel agents
    logger.info("Launching %d CategoryAgents in parallel...", len(SEARCH_CATEGORIES))
    results = run_all_agents(ai)
    report = merge_results(results)

    verified = sum(1 for s in report["top_sources"] if s.get("url_verified"))
    logger.info(
        "Research complete: %d total sources, %d verified, %d agents failed",
        len(report["top_sources"]), verified, report["agents_failed"],
    )

    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    cost = (total_in * 30 + total_out * 60) / 1_000_000

    if dry_run:
        logger.info("Dry run — skipping DB write and LINE notification")
        logger.info("Report preview: %s", json.dumps(report, ensure_ascii=False, indent=2)[:500])
        return

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
    try:
        sb.table("scraper_runs").insert({
            "source": "researcher",
            "events_processed": len(report["top_sources"]),
            "openai_tokens_in": total_in,
            "openai_tokens_out": total_out,
            "cost_usd": round(cost, 6),
            "notes": f"gpt-4o-search-preview × {len(SEARCH_CATEGORIES)} agents, {verified} verified",
        }).execute()
    except Exception:
        pass

    # Send LINE
    msg = _format_line_message(report, results)
    send_line_message(msg)
    logger.info("Daily research complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if "--test-line" in sys.argv:
        send_line_message("✅ Tokyo Taiwan Radar LINE 通知測試成功！")
        print("Test message sent.")
    elif "--dry-run" in sys.argv:
        run_research(dry_run=True)
    else:
        run_research()


import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from supabase import create_client

from line_notify import send_line_message

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Search categories
# ---------------------------------------------------------------------------
SEARCH_CATEGORIES = [
    {
        "id": "university",
        "label": "🏫 大學",
        "query_ja": "台湾 イベント セミナー 大学 東京 2026",
        "query_en": "Taiwan event seminar university Tokyo 2026",
        "description": "日本の大学で開催される台湾関連イベント・講座・研究会",
    },
    {
        "id": "media",
        "label": "📰 媒體",
        "query_ja": "台湾 文化 イベント メディア 東京 2026",
        "query_en": "Taiwan cultural event media Tokyo 2026",
        "description": "メディアプラットフォームで紹介される台湾関連イベント",
    },
    {
        "id": "government",
        "label": "🏛️ 政府機關",
        "query_ja": "台湾 交流 イベント 政府 公的機関 東京 2026",
        "query_en": "Taiwan exchange event government Tokyo 2026",
        "description": "政府・公的機関が主催・後援する台湾関連イベント",
    },
    {
        "id": "thinktank",
        "label": "🔬 智庫・研究機構",
        "query_ja": "台湾 研究 シンポジウム シンクタンク 東京 2026",
        "query_en": "Taiwan research symposium think tank Tokyo 2026",
        "description": "シンクタンク・研究機関が開催する台湾関連の講演・シンポジウム",
    },
    {
        "id": "social",
        "label": "💬 社群",
        "query_ja": "台湾 コミュニティ 交流会 東京 Facebook グループ",
        "query_en": "Taiwan community event Tokyo Facebook group Twitter",
        "description": "SNS・コミュニティで発信される台湾関連の交流イベント",
    },
]

# ---------------------------------------------------------------------------
# GPT prompt for source analysis
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """You are a research analyst specializing in Taiwan-related cultural events in Japan.

Given the following search results, analyze and identify the top 5 most promising NEW event source websites that:
1. Regularly publish Taiwan-related events in Tokyo/Japan
2. Have scrapable event listings (not just news articles)
3. Are NOT already in our existing scraper sources: peatix.com, taiwanculturalcenter (roc-taiwan.org/jp), taioan-dokyokai

For each source, provide:
- name: Website/organization name
- url: Main events page URL
- category: university | media | government | thinktank | social
- event_types: What kind of events they post (lectures, exhibitions, screenings, etc.)
- frequency: How often they post (daily/weekly/monthly)
- scraping_feasibility: easy | medium | hard (based on whether it's static HTML or needs JS rendering)
- reason: 1-2 sentence explanation of why this source is valuable

Also provide:
- news_summary: 3-5 bullet points of recent Taiwan-related news in Japanese media
- trend_keywords: Top 5 trending keywords related to Taiwan in Japan right now
- category_suggestions: Any suggestions for new event categories based on recent trends

Respond in valid JSON:
{
  "top_sources": [...],
  "news_summary": [...],
  "trend_keywords": [...],
  "category_suggestions": [...]
}"""


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


def _search_with_gpt(client: OpenAI) -> dict:
    """Use GPT to simulate web research across all categories."""
    search_context = ""
    for cat in SEARCH_CATEGORIES:
        search_context += f"\n### {cat['label']} ({cat['id']})\n"
        search_context += f"Search query (JA): {cat['query_ja']}\n"
        search_context += f"Search query (EN): {cat['query_en']}\n"
        search_context += f"Description: {cat['description']}\n"

    today = datetime.now(JST).strftime("%Y-%m-%d")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": f"Today is {today}. Research Taiwan-related event sources in Japan across these categories:\n{search_context}\n\nProvide your analysis as JSON.",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4000,
    )

    usage = response.usage
    text = response.choices[0].message.content
    result = json.loads(text)
    result["_usage"] = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }
    return result


def _format_line_message(report: dict) -> str:
    """Format the research report as a LINE message."""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    lines = [
        f"📡 Tokyo Taiwan Radar — 每日研究報告",
        f"日期：{today}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📌 Top 5 新爬蟲來源建議",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    icons = {"university": "🏫", "media": "📰", "government": "🏛️", "thinktank": "🔬", "social": "💬"}

    for i, src in enumerate(report.get("top_sources", [])[:5], 1):
        icon = icons.get(src.get("category", ""), "📎")
        feasibility = {"easy": "⭐⭐⭐", "medium": "⭐⭐", "hard": "⭐"}.get(
            src.get("scraping_feasibility", ""), "?"
        )
        lines.extend([
            f"",
            f"{i}. {icon} {src.get('name', '?')}",
            f"   {src.get('url', '?')}",
            f"   活動類型: {src.get('event_types', '?')}",
            f"   發佈頻率: {src.get('frequency', '?')}",
            f"   可行性: {feasibility}",
            f"   理由: {src.get('reason', '')}",
        ])

    # News summary
    news = report.get("news_summary", [])
    if news:
        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "📰 台灣相關新聞摘要", "━━━━━━━━━━━━━━━━━━━━"])
        for item in news:
            lines.append(f"• {item}")

    # Trend keywords
    keywords = report.get("trend_keywords", [])
    if keywords:
        lines.extend(["", f"🔑 趨勢關鍵字: {', '.join(keywords)}"])

    # Category suggestions
    suggestions = report.get("category_suggestions", [])
    if suggestions:
        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "🏷️ 分類標籤建議", "━━━━━━━━━━━━━━━━━━━━"])
        for s in suggestions:
            lines.append(f"• {s}")

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "在 VS Code 中使用 @Architect 規劃新爬蟲"])

    return "\n".join(lines)


def run_research() -> None:
    """Run the full daily research pipeline."""
    logger.info("Starting daily research...")
    ai = _get_openai()
    sb = _get_supabase()

    # Step 1: Research with GPT
    logger.info("Running GPT research across %d categories...", len(SEARCH_CATEGORIES))
    report = _search_with_gpt(ai)
    logger.info("Research complete: %d sources found", len(report.get("top_sources", [])))

    # Step 2: Save to DB
    usage = report.pop("_usage", {})
    try:
        sb.table("research_reports").insert({
            "report_type": "source_discovery",
            "content": report,
        }).execute()
        logger.info("Report saved to research_reports table")
    except Exception as exc:
        logger.warning("Could not save report to DB (table may not exist): %s", exc)

    # Step 3: Log to scraper_runs for cost tracking
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    cost = (tokens_in * 0.15 + tokens_out * 0.60) / 1_000_000
    try:
        sb.table("scraper_runs").insert({
            "source": "researcher",
            "events_processed": len(report.get("top_sources", [])),
            "openai_tokens_in": tokens_in,
            "openai_tokens_out": tokens_out,
            "cost_usd": round(cost, 6),
            "notes": f"daily research, {len(SEARCH_CATEGORIES)} categories",
        }).execute()
    except Exception:
        pass

    # Step 4: Send LINE notification
    msg = _format_line_message(report)
    send_line_message(msg)

    logger.info("Daily research complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if "--test-line" in sys.argv:
        send_line_message("✅ Tokyo Taiwan Radar LINE 通知測試成功！")
        print("Test message sent.")
    else:
        run_research()