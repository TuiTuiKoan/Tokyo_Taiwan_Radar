"""
Daily automated research: discovers new Taiwan-related event sources in Japan.

Searches across universities, media, government, think tanks, and social media.
Outputs a structured report and sends a LINE notification.

Usage:
    python researcher.py                  # full research run
    python researcher.py --test-line      # test LINE notification only
"""

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