"""
Scraper for 地球の歩き方 (arukikata.co.jp) — editorial articles about
Taiwan-related events in Tokyo.

Strategy: WordPress sitemap monitoring
  1. Fetch wp-sitemap-posts-webmagazine-2.xml (newest articles, up to 2605 entries)
  2. Filter entries with lastmod within past LOOKBACK_DAYS
  3. Fetch each article page and parse event fields from structured <dl>/<dt>/<dd> blocks
  4. Title filter: must contain both 東京 and 台湾 to avoid global travel noise

Dedup key: `arukikata_{article_id}` extracted from URL path number.
  e.g. https://www.arukikata.co.jp/webmagazine/362618/ → arukikata_362618
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# Sitemaps to monitor (newest-articles pages only)
SITEMAP_URLS = [
    "https://www.arukikata.co.jp/wp-sitemap-posts-webmagazine-2.xml",
]

# How far back to look for new articles (days)
LOOKBACK_DAYS = 90

# Only keep articles that mention BOTH 東京 and 台湾 in the title
_TOKYO_TAIWAN = re.compile(r"台湾.{0,30}東京|東京.{0,30}台湾", re.IGNORECASE)

# Skip recap/past-event reports
_PAST_MARKERS = re.compile(r"レポート|レポ|報告|記録|アーカイブ|recap", re.IGNORECASE)

# Article URL pattern
_ARTICLE_PATH = re.compile(r"/(webmagazine|tokuhain)/(\d+)/")

# Day-of-week stripper (from date-extraction SKILL)
_DOW = re.compile(r"[（(][^）)\d][^）)]*[）)]")

JST = timezone(timedelta(hours=9))


def _strip_dow(s: str) -> str:
    return _DOW.sub("", s).strip()


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    raw = _strip_dow(raw.strip())
    for fmt in ("%Y年%m月%d日", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_date_range(raw: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '2026年2月6日（金）～2月8日（日）※雨天決行' → (start, end)."""
    raw = raw.strip()
    # Strip trailing notes like ※雨天決行
    raw = re.sub(r"[※＊\*][^\n]*", "", raw).strip()
    # Split on range indicators
    parts = re.split(r"[～~〜]", raw, maxsplit=1)
    start = _parse_date(parts[0]) if parts else None
    if len(parts) < 2 or not start:
        return start, start

    end_raw = parts[1].strip()
    # Inject year+month if abbreviated: "2月8日" → "2026年2月8日"
    if start and not re.match(r"\d{4}年", end_raw):
        if re.match(r"\d{1,2}月", end_raw):
            end_raw = f"{start.year}年{end_raw}"
        elif re.match(r"\d{1,2}日", end_raw):
            end_raw = f"{start.year}年{start.month}月{end_raw}"
    end = _parse_date(end_raw)
    return start, end or start


def _article_id(url: str) -> Optional[str]:
    m = _ARTICLE_PATH.search(url)
    return m.group(2) if m else None


def _get_dl_map(soup: BeautifulSoup) -> dict[str, str]:
    """Extract all dt→dd pairs from <dl> blocks on the page."""
    result: dict[str, str] = {}
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True)
            val = dd.get_text(strip=True)
            if key and val:
                result[key] = val
    return result


class ArukikataScraper(BaseScraper):
    SOURCE_NAME = "arukikata"

    def scrape(self) -> list[Event]:
        cutoff = datetime.now(tz=JST) - timedelta(days=LOOKBACK_DAYS)
        candidate_urls = self._collect_recent_urls(cutoff)
        logger.info("arukikata: %d candidate articles (lastmod ≥ %s)", len(candidate_urls), cutoff.date())

        events: list[Event] = []
        for url in candidate_urls:
            try:
                event = self._parse_article(url)
                if event:
                    events.append(event)
                time.sleep(0.5)  # polite rate limit
            except Exception as exc:
                logger.warning("arukikata: failed to parse %s — %s", url, exc)

        logger.info("arukikata: returning %d events", len(events))
        return events

    # ──────────────────────────────────────────────────────────────────────

    def _collect_recent_urls(self, cutoff: datetime) -> list[str]:
        urls: list[str] = []
        for sitemap_url in SITEMAP_URLS:
            try:
                resp = requests.get(
                    sitemap_url,
                    headers={"User-Agent": "TokyoTaiwanRadar/1.0 (+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"},
                    timeout=15,
                )
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("arukikata: sitemap fetch failed %s — %s", sitemap_url, exc)
                continue

            try:
                tree = ET.fromstring(resp.content)
            except ET.ParseError as exc:
                logger.warning("arukikata: sitemap parse error %s — %s", sitemap_url, exc)
                continue

            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_el in tree.findall("sm:url", ns):
                loc_el = url_el.find("sm:loc", ns)
                lastmod_el = url_el.find("sm:lastmod", ns)
                if loc_el is None:
                    continue
                loc = loc_el.text or ""
                if not _ARTICLE_PATH.search(loc):
                    continue

                lastmod_raw = lastmod_el.text if lastmod_el is not None else ""
                if lastmod_raw:
                    try:
                        lastmod = datetime.fromisoformat(lastmod_raw)
                        if lastmod.tzinfo is None:
                            lastmod = lastmod.replace(tzinfo=JST)
                        if lastmod < cutoff:
                            continue
                    except ValueError:
                        pass  # include if we can't parse lastmod

                urls.append(loc)

        return urls

    def _parse_article(self, url: str) -> Optional[Event]:
        art_id = _article_id(url)
        if not art_id:
            return None

        resp = requests.get(
            url,
            headers={"User-Agent": "TokyoTaiwanRadar/1.0 (+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"},
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # ── Title ──────────────────────────────────────────────────────────
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title:
            title_meta = soup.find("meta", {"property": "og:title"})
            title = title_meta.get("content", "").strip() if title_meta else ""
        # Remove site name suffix
        title = re.sub(r"\s*[|｜].*$", "", title).strip()

        # ── Filter: both 東京 and 台湾 must be in title ────────────────────
        if not _TOKYO_TAIWAN.search(title):
            logger.debug("arukikata: skipping (no Tokyo+Taiwan in title): %s", title[:60])
            return None
        if _PAST_MARKERS.search(title):
            logger.debug("arukikata: skipping past-event report: %s", title[:60])
            return None

        # ── Structured fields from dl/dt/dd ────────────────────────────────
        dl_map = _get_dl_map(soup)

        # Event name (use 名称 / イベント名 if present, otherwise title)
        event_name = dl_map.get("名称") or dl_map.get("イベント名") or title

        # Publish date
        pub_date: Optional[datetime] = None
        for key in ("公開日", "更新日"):
            if key in dl_map:
                pub_date = _parse_date(dl_map[key])
                if pub_date:
                    break

        # Event dates
        start_date: Optional[datetime] = None
        end_date: Optional[datetime] = None
        for key in ("開催期間", "開催日時", "日時", "会期", "開催日"):
            if key in dl_map:
                start_date, end_date = _parse_date_range(dl_map[key])
                if start_date:
                    break

        # ── Body text (best available container) ────────────────────────
        body_el = soup.find(class_="l-post__body") or soup.find("main") or soup.find("body")
        body_text = body_el.get_text("\n", strip=True) if body_el else ""
        # Supplement with og:description
        og_desc_meta = soup.find("meta", {"property": "og:description"})
        og_desc = og_desc_meta.get("content", "").strip() if og_desc_meta else ""

        # Fallback: probe body text for full kanji dates
        if start_date is None:
            probe_text = og_desc + "\n" + body_text
            m = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)[^）\d年]{0,20}[～~〜][^）\d年]{0,10}(\d{4}年\d{1,2}月\d{1,2}日)", probe_text)
            if m:
                start_date = _parse_date(m.group(1))
                end_date = _parse_date(m.group(2))
            else:
                m2 = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", probe_text)
                if m2:
                    start_date = _parse_date(m2.group(1))
                    end_date = start_date

        # Tier 3: publish date fallback
        if start_date is None and pub_date:
            logger.info("arukikata: date not found for %s — using publish date %s", url, pub_date.date())
            start_date = pub_date
            end_date = pub_date

        # Single-day rule
        if start_date and end_date is None:
            end_date = start_date

        # ── Venue ──────────────────────────────────────────────────────────
        venue = dl_map.get("場所") or dl_map.get("会場") or dl_map.get("開催場所")
        if venue:
            venue = re.split(r"[\n\r]", venue)[0].strip()

        # Construct raw_description: date prefix + og_desc + body
        parts_desc: list[str] = []
        if start_date:
            date_str = start_date.strftime("%Y年%m月%d日")
            if end_date and end_date != start_date:
                date_str += f"〜{end_date.strftime('%Y年%m月%d日')}"
            parts_desc.append(f"開催日時: {date_str}")
        if og_desc:
            parts_desc.append(og_desc)
        if body_text:
            parts_desc.append(body_text)
        raw_desc = "\n\n".join(parts_desc) if parts_desc else ""

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=f"arukikata_{art_id}",
            source_url=url,
            original_language="ja",
            name_ja=event_name,
            raw_title=title,
            raw_description=raw_desc,
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            category=[],  # annotator will assign
        )

