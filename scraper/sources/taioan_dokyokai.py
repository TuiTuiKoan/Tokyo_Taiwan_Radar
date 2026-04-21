"""
Scraper for 在日台湾同郷会 (Taiwanese Association in Japan) — taioan.fc2.page

WordPress site on FC2. Scrapes two categories:
  - /category/event/         → upcoming events (category left for annotator)
  - /category/活動記録/      → past activity reports (category=["report"])

Pagination: WordPress /page/N/ URL scheme, up to MAX_PAGES per category.
90-day lookback cutoff applied on publish date.
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

from .base import BaseScraper, Event
from .taiwan_cultural_center import (
    _extract_event_dates_from_body,
    _extract_prose_date_range_from_body,
    _parse_date,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://taioan.fc2.page"
MAX_PAGES = 5
CUTOFF_DAYS = 90

# (url_path, hint_category)
# hint_category seeds the category field; event posts get [] so the annotator decides.
LISTING_CATEGORIES: list[tuple[str, list[str]]] = [
    ("/category/event/", []),
    ("/category/%e6%b4%bb%e5%8b%95%e8%a8%98%e9%8c%b2/", ["report"]),
]

# This site uses ■ 日時 labels WITHOUT a colon — the date follows on the next line.
# e.g.:  ■ 日時
#          2026年05月10日（日）
#          13:00～16:15
# Also handles the colon-style used by TCC (as a superset).
_TAIOAN_DATE_LABEL = re.compile(
    r"[■●▶◆◇・]?\s*"
    r"(?:日\s*時|開催日時|日時|会期|開催期間|期間|開催日|イベント日時)"
    r"[\s：:]*\n?\s*"   # allow optional colon/newline between label and value
    r"(.{5,120})",
    re.MULTILINE,
)


def _extract_taioan_event_dates(
    text: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extended Tier 1: labeled date with optional newline between label and value.

    Handles the site's convention of placing the date on the line *after* the
    ■ 日時 label (no colon), in addition to the colon-inline style handled by TCC.
    Also strips trailing time components (e.g. "2026年3月15日14:00" → "2026年3月15日").
    """
    if not text:
        return None, None
    for m in _TAIOAN_DATE_LABEL.finditer(text):
        raw = m.group(1).strip()
        clean = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
        # Strip trailing time components e.g. "14:00" or "13:00～16:15"
        clean = re.sub(r'\s*\d{1,2}:\d{2}.*$', '', clean).strip()
        parts = re.split(r'[～~〜]|(?<=\d)\s*[–—]\s*(?=\d)', clean, maxsplit=1)
        start_raw = parts[0].strip()
        end_raw = parts[1].strip() if len(parts) > 1 else None
        start = _parse_date(start_raw)
        if start and end_raw:
            # Strip times from end_raw too
            end_raw = re.sub(r'\s*\d{1,2}:\d{2}.*$', '', end_raw).strip()
            if not re.match(r'\d{4}', end_raw):
                if re.match(r'\d{1,2}月', end_raw):
                    end_raw = f"{start.year}年{end_raw}"
                elif re.match(r'\d{1,2}日', end_raw):
                    end_raw = f"{start.year}年{start.month}月{end_raw}"
            end = _parse_date(end_raw)
        else:
            end = None
        if start:
            return start, end
    return None, None

_LOCATION_LABEL = re.compile(
    r"[■●▶◆◇・]?\s*(?:場所|会場|開催場所)\s*[：:]\s*(.{3,80})",
    re.MULTILINE,
)


def _safe_text(page: Page, selector: str) -> Optional[str]:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else None
    except Exception:
        return None


def _extract_location(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _LOCATION_LABEL.search(text)
    if not m:
        return None
    return m.group(1).strip().splitlines()[0].strip()


class TaioanDokyokaiScraper(BaseScraper):
    """Scrapes Taiwan community events from 在日台湾同郷会 (taioan.fc2.page)."""

    SOURCE_NAME = "taioan_dokyokai"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff = datetime.now() - timedelta(days=CUTOFF_DAYS)
        seen_urls: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            for cat_path, hint_category in LISTING_CATEGORIES:
                links = self._collect_links(page, cat_path, cutoff)
                logger.info("Category %s: found %d links", cat_path, len(links))
                for url in links:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    try:
                        event = self._scrape_detail(page, url, hint_category)
                        if event:
                            events.append(event)
                        time.sleep(1.0)
                    except Exception as exc:
                        logger.error("Failed to scrape %s: %s", url, exc)

            browser.close()
        return events

    def _collect_links(
        self, page: Page, cat_path: str, cutoff: datetime
    ) -> list[str]:
        """Walk paginated WordPress listing and collect article detail URLs.

        This site uses a WordPress block theme: post containers are
        .wp-block-post (not <article>), with .wp-block-post-title a for links
        and .wp-block-post-date time[datetime] for publish dates.
        Multiple .wp-block-query blocks appear (main + sidebars), so we
        deduplicate with a seen set.
        """
        links: list[str] = []
        seen: set[str] = set()

        for page_num in range(1, MAX_PAGES + 1):
            if page_num == 1:
                url = f"{BASE_URL}{cat_path}"
            else:
                url = f"{BASE_URL}{cat_path}page/{page_num}/"

            logger.info("Fetching listing page %d: %s", page_num, url)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            posts = page.query_selector_all(".wp-block-post")
            if not posts:
                logger.info("No posts found on page %d, stopping.", page_num)
                break

            page_links: list[str] = []
            stop_early = False

            for post in posts:
                # Filter: only include posts whose category term link matches
                # the listing category path (prevents sidebar widgets from leaking
                # posts from other categories onto this listing page).
                cat_links = post.query_selector_all(".wp-block-post-terms a")
                post_cats = [
                    (a.get_attribute("href") or "") for a in cat_links
                ]
                if cat_path not in " ".join(post_cats):
                    continue
                # Publish date: .wp-block-post-date time[datetime]
                time_el = post.query_selector("time[datetime]")
                pub_date_raw = time_el.get_attribute("datetime") if time_el else None
                pub_date: Optional[datetime] = None
                if pub_date_raw:
                    try:
                        pub_date = datetime.fromisoformat(pub_date_raw[:10])
                    except ValueError:
                        pass

                if pub_date and pub_date < cutoff:
                    stop_early = True
                    continue

                # Title link: .wp-block-post-title a
                a_el = post.query_selector(".wp-block-post-title a")
                if not a_el:
                    continue
                href = a_el.get_attribute("href") or ""
                if href and href not in seen:
                    seen.add(href)
                    page_links.append(href)

            links.extend(page_links)

            if stop_early or not page_links:
                break

        return links

    def _scrape_detail(
        self, page: Page, url: str, hint_category: list[str]
    ) -> Optional[Event]:
        """Visit a single article page and extract all event fields."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # --- Title ---
        name_ja = (
            _safe_text(page, "h1.wp-block-post-title")
            or _safe_text(page, ".wp-block-post-title")
            or _safe_text(page, "h1.entry-title")
            or _safe_text(page, "h1")
        )
        if not name_ja:
            logger.warning("No title found at %s, skipping.", url)
            return None

        # --- Publish date (Tier-3 fallback) ---
        pub_date: Optional[datetime] = None
        time_el = page.query_selector(".wp-block-post-date time[datetime]")
        if not time_el:
            time_el = page.query_selector("time[datetime]")
        if time_el:
            raw_dt = time_el.get_attribute("datetime") or ""
            try:
                pub_date = datetime.fromisoformat(raw_dt[:10])
            except ValueError:
                pass

        # --- Description body ---
        description_ja = (
            _safe_text(page, ".wp-block-post-content")
            or _safe_text(page, ".entry-content")
            or _safe_text(page, ".post-content")
        )

        # --- Date extraction ---
        # Tier 1: labeled date in body (■ 日時, 日時：, 開催日時：, 会期：, …)
        # Uses a site-specific regex that handles label+newline+date format.
        start_date, end_date = _extract_taioan_event_dates(description_ja)

        # Tier 1 fallback: TCC-style colon-inline labels
        if start_date is None:
            start_date, end_date = _extract_event_dates_from_body(description_ja)

        # Tier 1.3: unlabeled kanji date range e.g. "11月28日〜12月14日"
        if start_date is None:
            start_date, end_date = _extract_prose_date_range_from_body(
                description_ja, pub_date
            )

        # Tier 3: fall back to publish date so start_date is never null
        if start_date is None:
            start_date = pub_date
            end_date = pub_date

        # --- Location ---
        location_name = _extract_location(description_ja)

        # --- Stable source_id ---
        source_id = hashlib.md5(url.encode()).hexdigest()[:16]

        # --- raw_description: prepend date hint for annotator ---
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date and end_date != start_date:
                date_prefix += f" 〜 {end_date.strftime('%Y年%m月%d日')}"
            date_prefix += "\n\n"
        raw_description = date_prefix + (description_ja or "")

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=name_ja,
            description_ja=description_ja,
            raw_title=name_ja,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            is_paid=None,
            category=list(hint_category),
        )
