#!/usr/bin/env python3
"""
Enrich an OCR-created event by searching for its official web page.
Usage: python enrich_ocr_event.py --event-id <uuid>
"""
import argparse
import logging
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"}


def _ddg_search(query: str, max_results: int = 5) -> list[str]:
    """Search DuckDuckGo HTML and return list of result URLs."""
    url = "https://html.duckduckgo.com/html/"
    try:
        r = requests.post(url, data={"q": query}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        urls = []
        for a in soup.select("a.result__url"):
            href = a.get("href", "")
            if href and href.startswith("http") and "duckduckgo.com" not in href:
                urls.append(href)
                if len(urls) >= max_results:
                    break
        logger.info("DDG search '%s' → %d results", query[:60], len(urls))
        return urls
    except Exception as e:
        logger.warning("DDG search failed: %s", e)
        return []


def _fetch_page_text(url: str, timeout: int = 20000) -> str:
    """Fetch page text via Playwright, return up to 8000 chars."""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "ja,en;q=0.9"})
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            text = page.evaluate("document.body.innerText")
            browser.close()
            return (text or "")[:8000]
    except Exception as e:
        logger.warning("Playwright fetch failed for %s: %s", url, e)
        return ""


def _score_page(text: str, name_ja: str, location_name: str) -> int:
    """Score how likely a page is the official event page."""
    score = 0
    name_words = [w for w in re.split(r"[\s　]+", name_ja) if len(w) >= 2]
    for w in name_words:
        if w in text:
            score += 2
    if location_name and location_name in text:
        score += 3
    # Boost pages that look like event/info pages
    for kw in ["開催", "会場", "主催", "チケット", "入場", "日時"]:
        if kw in text:
            score += 1
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", required=True)
    args = parser.parse_args()

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # 1. Fetch event from DB
    row = (
        sb.table("events")
        .select("id,name_ja,location_name,start_date,source_url")
        .eq("id", args.event_id)
        .single()
        .execute()
        .data
    )

    if not row:
        logger.error("Event %s not found", args.event_id)
        return

    name_ja = row.get("name_ja") or ""
    location_name = row.get("location_name") or ""
    start_date = (row.get("start_date") or "")[:10]
    year = start_date[:4] if start_date else ""

    if not name_ja:
        logger.warning("Event %s has no name_ja, skipping enrich", args.event_id)
        return

    # 2. Build search queries (try progressively broader)
    queries = []
    if location_name:
        queries.append(f'"{name_ja}" {year} {location_name}')
    queries.append(f'"{name_ja}" {year} 公式')
    queries.append(f"{name_ja} {year}")

    candidate_urls: list[str] = []
    for q in queries:
        urls = _ddg_search(q)
        for u in urls:
            if u not in candidate_urls:
                candidate_urls.append(u)
        if len(candidate_urls) >= 5:
            break
        time.sleep(1)  # polite delay

    if not candidate_urls:
        logger.warning("No search results for '%s'", name_ja)
        return

    # 3. Fetch and score each candidate
    best_url = None
    best_text = ""
    best_score = -1

    for url in candidate_urls[:5]:
        logger.info("Fetching %s", url)
        text = _fetch_page_text(url)
        if not text:
            continue
        score = _score_page(text, name_ja, location_name)
        logger.info("  score=%d  len=%d", score, len(text))
        if score > best_score:
            best_score = score
            best_url = url
            best_text = text
        time.sleep(0.5)

    # 4. Update DB
    if best_url and best_score >= 2:
        update_payload = {
            "raw_description": best_text,
            "source_url": best_url,
            "official_url": best_url,
            "annotation_status": "pending",  # ensure annotator picks it up
        }
        sb.table("events").update(update_payload).eq("id", args.event_id).execute()
        logger.info(
            "Enriched event %s with URL %s (score=%d)", args.event_id, best_url, best_score
        )
    else:
        logger.warning(
            "No good match found (best_score=%d) — skipping DB update", best_score
        )


if __name__ == "__main__":
    main()
