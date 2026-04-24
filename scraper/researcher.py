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

    # Fetch known URLs to skip (only when writing to DB)
    known_urls: dict[str, str] = {}
    if sb:
        known_urls = _get_known_urls(sb)
        logger.info("Known URLs to skip: %d", len(known_urls))

    # Run 5 parallel agents
    logger.info("Launching %d CategoryAgents in parallel...", len(SEARCH_CATEGORIES))
    results = run_all_agents(ai, known_urls)
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


