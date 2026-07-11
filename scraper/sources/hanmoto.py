"""
Scraper for Taiwan-related books via 版元ドットコム (hanmoto.com).

Strategy:
    1. Load the current search UI URL for keyword=台湾 sorted by release date desc
    2. Paginate by clicking page buttons in the JS search UI (20 per page, max 3 pages)
    3. Extract ISBN, title, release date, and publisher from .bd-booklist-item-book cards
    4. source_id: hanmoto_{isbn13} or hanmoto_{md5(detail_url)[:12]}
    5. start_date = end_date = 発売日 (UTC midnight)
    6. Stop once release dates fall outside the rolling 365-day window
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from publication_rules import validate_publisher_homepage

from .base import BaseScraper, Event, dedup_events, is_jpro_placeholder_date

logger = logging.getLogger(__name__)

SOURCE_NAME = "hanmoto"
BASE_URL = "https://www.hanmoto.com/bd/search/top?keyword=%E5%8F%B0%E6%B9%BE&sdate_desc=1"
_MAX_PAGES = 3
_PAGE_SIZE = 20
_CUTOFF_DAYS = 365
_OFFICIAL_LINK_HINTS = ("書籍", "詳細", "公式", "商品", "特設", "紹介", "試し読み")
_ORGANIZER_LINK_HINTS = ("出版社", "出版元", "発行元")
_DENIED_CONTENT_PATH_FRAGMENTS = ("/search", "/cart", "/login", "/account")
_DENIED_CONTENT_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

TAIWAN_KEYWORDS = [
    "台湾", "臺灣", "Taiwan", "台北", "台南", "台中", "高雄",
    "客家", "原住民", "原住民族", "閩南", "ホーロー", "台語",
    "minnan", "hakka",
]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _strip_null(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s.replace("\x00", "")


def _parse_date(text: str) -> Optional[datetime]:
    """Parse '2024年03月15日' or '2024-03-15' to UTC midnight datetime."""
    text = text.strip()
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    return None


def _extract_isbn_from_href(href: str) -> Optional[str]:
    """Extract 13-digit ISBN from a URL path like /isbn/9784123456789."""
    m = re.search(r"/isbn/(\d{13})", href)
    if m:
        return m.group(1)
    return None


def _clean_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return text.replace("\x00", "").strip() or None


def _extract_detail_field(text: str, labels: tuple[str, ...]) -> Optional[str]:
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*[:：]?\s*(.+)", text)
        if m:
            value = _clean_text(m.group(1).splitlines()[0])
            if value:
                return value
    return None


def _extract_detail_link(text: str, labels: tuple[str, ...], base_url: str) -> Optional[str]:
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*[:：]?\s*(https?://[^\s\)）]+)", text)
        if m:
            return m.group(1).rstrip(".,、)")
        m = re.search(rf"{re.escape(label)}\s*[:：]?\s*(/[^\s\)）]+)", text)
        if m:
            return urljoin(base_url, m.group(1).rstrip(".,、)"))
    return None


def _is_external_book_content_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if not host or host.endswith("hanmoto.com"):
        return False
    if path in {"", "/"}:
        return False
    if path.endswith(_DENIED_CONTENT_SUFFIXES):
        return False
    if any(fragment in path for fragment in _DENIED_CONTENT_PATH_FRAGMENTS):
        return False
    return True


def _pick_anchor_url(label: str, url: str, hints: tuple[str, ...]) -> bool:
    if not _is_external_book_content_url(url):
        return False
    return any(hint in label for hint in hints)


def _is_external_organizer_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if not host or host.endswith("hanmoto.com"):
        return False
    if path.endswith(_DENIED_CONTENT_SUFFIXES):
        return False
    if any(fragment in path for fragment in _DENIED_CONTENT_PATH_FRAGMENTS):
        return False
    return True


def _normalize_official_url(candidate: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(candidate)
    if not cleaned:
        return None
    if not _is_external_book_content_url(cleaned):
        return None
    return cleaned


def _normalize_organizer_url(
    candidate: Optional[str],
    publisher: Optional[str],
    detail_text: str,
) -> Optional[str]:
    cleaned = _clean_text(candidate)
    name = _clean_text(publisher)
    if not cleaned or not name:
        return None
    host = (urlsplit(cleaned).hostname or "").lower().split(".")
    alias = host[0] if host else ""
    aliases: tuple[str, ...] = (alias,) if alias and alias != "www" else ()
    validation = validate_publisher_homepage(
        cleaned,
        name,
        page_title=name,
        page_text=detail_text,
        aliases=aliases,
    )
    if not validation.accepted:
        return None
    return validation.canonical_url


def _scrape_hanmoto_detail(detail_url: str) -> dict:
    """Fetch and parse book details directly using requests and BeautifulSoup."""
    import requests
    from bs4 import BeautifulSoup

    res = {
        "raw_description": "",
        "price_info": None,
        "price_amount": None,
        "performer": None,
        "image_url": None,
        "official_url": None,
        "organizer_url": None,
    }
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en-US;q=0.9",
        }
        resp = requests.get(detail_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return res

        soup = BeautifulSoup(resp.content, "html.parser")
        
        # 1. Collect rich description
        desc_parts = []
        
        # 內容介紹
        kaisetsu = soup.select_one(".book-kaisetsu-section")
        if kaisetsu:
            txt = kaisetsu.get_text("\n", strip=True)
            if txt:
                desc_parts.append(f"【内容紹介】\n{txt}")
                
        # 目次/目錄
        toc = soup.select_one(".book-toc-section")
        if toc:
            txt = toc.get_text("\n", strip=True)
            if txt:
                desc_parts.append(f"【目次】\n{txt}")
                
        # 作者簡介
        profiles = soup.select_one(".book-author-profiles-section")
        if profiles:
            txt = profiles.get_text("\n", strip=True)
            if txt:
                desc_parts.append(f"【著者プロフィール】\n{txt}")
                
        main_el = soup.select_one("main") or soup.select_one("#content") or soup.body
        if not desc_parts and main_el:
            fallback_text = main_el.get_text("\n", strip=True)
            if fallback_text:
                desc_parts.append(fallback_text)

        if main_el:
            link_lines: list[str] = []
            seen_links: set[str] = set()
            for anchor in main_el.select("a[href]"):
                href = anchor.get("href") or ""
                href = href.strip()
                if not href:
                    continue
                absolute_url = urljoin(detail_url, href)
                if not absolute_url.startswith("http"):
                    continue
                if absolute_url in seen_links:
                    continue
                seen_links.add(absolute_url)
                label = _clean_text(anchor.get_text(" ", strip=True)) or absolute_url
                link_lines.append(f"{label}: {absolute_url}")

                if (
                    res["organizer_url"] is None
                    and any(hint in label for hint in _ORGANIZER_LINK_HINTS)
                    and _is_external_organizer_url(absolute_url)
                ):
                    res["organizer_url"] = absolute_url
                if (
                    res["official_url"] is None
                    and _pick_anchor_url(label, absolute_url, _OFFICIAL_LINK_HINTS)
                    and not any(hint in label for hint in _ORGANIZER_LINK_HINTS)
                ):
                    res["official_url"] = absolute_url

            if link_lines:
                desc_parts.append("【関連リンク】\n" + "\n".join(link_lines))

        if desc_parts:
            res["raw_description"] = "\n\n".join(desc_parts)

        # 2. Price info and numerical amount
        price_sec = soup.select_one(".book-price-section")
        if price_sec:
            price_text = price_sec.get_text(" ", strip=True)
            if price_text:
                res["price_info"] = price_text
                # extract numerical price_amount
                nums = re.findall(r"\d[\d,]*", price_text)
                if nums:
                    m_body = re.search(r"本体\s*(\d[\d,]*)[円yen]?", price_text, re.IGNORECASE)
                    if m_body:
                        res["price_amount"] = float(m_body.group(1).replace(",", ""))
                    else:
                        res["price_amount"] = float(nums[0].replace(",", ""))

        # 3. Performer
        authors_sec = soup.select_one(".book-authors-section")
        if authors_sec:
            authors_text = authors_sec.get_text(" ", strip=True)
            if authors_text:
                cleaned = re.sub(r"^(著者|作者|編者|訳者|著|編|訳)\s*[:：]?\s*", "", authors_text)
                res["performer"] = cleaned

        # 4. Image URL (cover)
        img_el = soup.select_one("img.book-image")
        if img_el and img_el.get("src"):
            res["image_url"] = urljoin(detail_url, img_el.get("src"))

    except Exception as exc:
        logger.debug("hanmoto details fetch failed: %s", exc)

    return res


# CSS selector for book cards (confirmed 2026-06)
_CARD_SEL = ".bd-booklist-item-book"


class HanmotoScraper(BaseScraper):
    SOURCE_NAME = "hanmoto"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=_CUTOFF_DAYS)).date()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page.set_extra_http_headers({"Accept-Language": "ja,en-US;q=0.9"})

            for page_num in range(1, _MAX_PAGES + 1):
                if page_num == 1:
                    try:
                        page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
                    except PWTimeout:
                        logger.warning("hanmoto: initial page timeout")
                        break
                    except Exception as exc:
                        logger.warning("hanmoto: initial navigation error: %s", exc)
                        break
                else:
                    btn = page.query_selector(f".page-item-page{page_num} button")
                    if btn is None:
                        logger.debug("hanmoto: no page-%d button, stopping", page_num)
                        break
                    btn.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except PWTimeout:
                        pass  # proceed with whatever loaded

                try:
                    page.wait_for_selector('.bd-booklist-item-book [data-content-name="title"]', timeout=15000)
                except PWTimeout:
                    logger.warning("hanmoto: book titles did not load on page %d", page_num)
                    break

                cards = page.query_selector_all(_CARD_SEL)
                if not cards:
                    break

                page_exhausted = False
                for card in cards:
                    try:
                        # Title
                        title_el = card.query_selector('[data-content-name="title"]')
                        title = title_el.inner_text().strip() if title_el is not None else ""
                        title = _strip_null(title) or ""

                        # Link and ISBN
                        link_el = card.query_selector('a[href*="/bd/isbn/"]')
                        href = link_el.get_attribute("href") if link_el is not None else ""
                        href = href or ""
                        if href and not href.startswith("http"):
                            href = f"https://www.hanmoto.com{href}"

                        isbn = _extract_isbn_from_href(href) or ""

                        # source_id
                        if isbn and len(isbn) == 13 and isbn.isdigit():
                            source_id = f"hanmoto_{isbn}"
                        elif href:
                            source_id = f"hanmoto_{hashlib.md5(href.encode()).hexdigest()[:12]}"
                        else:
                            continue

                        # Client-side Taiwan filter (title only; server already filtered)
                        if not _is_taiwan(title):
                            continue

                        detail_text = ""
                        performer = None
                        price_info = None
                        price_amount = None
                        image_url = None
                        official_url = None
                        organizer_url_candidate = None

                        detail_url = None
                        if link_el is not None:
                            href = link_el.get_attribute("href") or ""
                            if href:
                                detail_url = urljoin("https://www.hanmoto.com", href)

                        if detail_url:
                            detail_res = _scrape_hanmoto_detail(detail_url)
                            detail_text = detail_res["raw_description"]
                            performer = detail_res["performer"]
                            price_info = detail_res["price_info"]
                            price_amount = detail_res["price_amount"]
                            image_url = detail_res["image_url"]
                            official_url = detail_res["official_url"]
                            organizer_url_candidate = detail_res["organizer_url"]

                        detail_text = _clean_text(detail_text) or ""
                        if not performer:
                            performer = _extract_detail_field(detail_text, ("著者", "作者", "編者", "訳者"))
                        if not official_url:
                            official_url = _extract_detail_link(
                                detail_text,
                                ("書籍詳細", "商品ページ", "公式サイト", "詳細ページ"),
                                "https://www.hanmoto.com",
                            )
                        if not organizer_url_candidate:
                            organizer_url_candidate = _extract_detail_link(
                                detail_text,
                                ("出版社サイト", "出版社", "出版元サイト"),
                                "https://www.hanmoto.com",
                            )
                        if not price_info:
                            price_info = _extract_detail_field(detail_text, ("定価", "価格", "本体価格"))

                        # Publication date — find span containing '発売' + year pattern
                        date_text = ""
                        for span in card.query_selector_all("span"):
                            txt = span.inner_text()
                            if ("発売" in txt or "登録" in txt) and re.search(r"\d{4}年", txt):
                                date_text = txt
                                break
                        start_dt = _parse_date(date_text)
                        if start_dt is None:
                            start_dt = _parse_date(detail_text)
                        end_dt = start_dt

                        # Recency cutoff: since sorted by release date desc,
                        # stop pagination once we hit books older than _CUTOFF_DAYS
                        if start_dt is not None and start_dt.date() < cutoff_date:
                            page_exhausted = True
                            break

                        if is_jpro_placeholder_date(start_dt):
                            start_dt = None
                        # Publisher
                        pub_el = card.query_selector('[data-content-name="imprint"]')
                        publisher = pub_el.inner_text().strip() if pub_el is not None else None
                        publisher = _clean_text(publisher)
                        normalized_official_url = _normalize_official_url(official_url)
                        normalized_organizer_url = _normalize_organizer_url(
                            organizer_url_candidate,
                            publisher,
                            detail_text,
                        )
                        if normalized_official_url and normalized_official_url == normalized_organizer_url:
                            normalized_official_url = None

                        normalized_price_info = _clean_text(price_info)

                        source_url = _strip_null(href) or BASE_URL

                        events.append(Event(
                            source_name=SOURCE_NAME,
                            source_id=source_id,
                            source_url=source_url,
                            original_language="ja",
                            name_ja=_strip_null(title) or None,
                            raw_title=_strip_null(title) or None,
                            raw_description=detail_text or None,
                            start_date=start_dt,
                            end_date=end_dt,
                            location_name=None,
                            location_address=None,
                            location_prefectures=[],
                            category=["books_media"],
                            event_form=["publication"],
                            name_ja_locked=True,
                            organizer=publisher,
                            organizer_url=normalized_organizer_url,
                            official_url=normalized_official_url,
                            performer=_clean_text(performer),
                            is_paid=True if normalized_price_info else None,
                            price_info=normalized_price_info,
                            price_amount=price_amount,
                            image_url=image_url,
                            location_url=None,
                        ))
                    except Exception as exc:
                        logger.debug("hanmoto: card parse error: %s", exc)
                        continue

                if page_exhausted or len(cards) < _PAGE_SIZE:
                    break

            browser.close()

        result = dedup_events(events)
        logger.info("hanmoto: %d events after dedup", len(result))
        return result
