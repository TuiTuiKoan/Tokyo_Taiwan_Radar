"""Scraper for 東京外国語大学 アジア・アフリカ言語文化研究所（AA研 / ILCAA）events.

Listing URL : https://www.aa.tufs.ac.jp/events/page/{n}/  (n=1 is /events/)
Detail URL  : https://www.aa.tufs.ac.jp/events/detail/e{N}/
Platform    : WordPress (wp-content uploads), server-rendered HTML. No RSS feed
              is linked from the pages. 10 cards per page, ~41 pages, sorted by
              event date DESCENDING (page 1 = furthest future).
Source name : tufs_aa
Source ID   : tufs_aa_e{N}  (the site's own sequential event ID)

Why this source (#726): the AA研 hosts the 土田滋博士の台湾原住民語資料 joint
research project and events such as the 2026-06-19 小川尚義・浅井恵倫台湾資料
贈呈記念式典. TTR only learned about that event from a post-hoc Google News
article, i.e. this listing was a source gap.

Design notes
------------
* The parser is deliberately **structure-agnostic**: it does not depend on CSS
  class names. Cards are located by the detail-link pattern
  ``/events/detail/e<digits>/`` and fields by their Japanese labels
  (日時 / 場所 / 開催形態 / 使用言語 / 主催・共催). This survives theme tweaks.
* Listing walk: pages are read from 1 upward and the walk stops at the first
  page whose cards are all already over (or at MAX_PAGES).
* 非公開 (closed joint-research meetings, 共共課題研究会) are skipped at the
  listing stage — TTR only lists events the public can attend.
* Relevance is judged on the **detail page** (title + programme + related
  project), because Taiwan often appears only in the programme or the
  project name (e.g. アミ語 / アタヤル語 talks).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "tufs_aa"
BASE_URL = "https://www.aa.tufs.ac.jp"
LISTING_URL = f"{BASE_URL}/events/"
MAX_PAGES = 8  # ~10 cards/page; 8 pages covers well over 2 months ahead
REQUEST_SLEEP = 0.5

AA_VENUE_KW = ("AA研", "アジア・アフリカ言語文化研究所", "東京外国語大学", "AGORA", "プロメテウス")
TUFS_ADDRESS = "東京都府中市朝日町3-11-1 東京外国語大学"
AA_ADDRESS = "東京都府中市朝日町3-11-1 東京外国語大学アジア・アフリカ言語文化研究所"

_JST = timezone(timedelta(hours=9))
_USER_AGENT = (
    "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; +https://tokyotaiwanradar.com/)"
)

_DETAIL_RE = re.compile(r"/events/detail/e(\d+)/?")
# 2026年06月19日 / 2026年6月19日 / 2026/06/19 / 2026-06-19
_DATE_RE = re.compile(r"(\d{4})\s*(?:年|/|-)\s*(\d{1,2})\s*(?:月|/|-)\s*(\d{1,2})\s*日?")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")

# ---------------------------------------------------------------------------
# Relevance
# ---------------------------------------------------------------------------
# Explicit Taiwan markers
_TAIWAN_KW = ["台湾", "臺灣", "台灣", "Taiwan", "Formosa", "フォルモサ"]
# Formosan / Taiwanese languages and peoples — AA研's Taiwan work is mostly
# linguistic, and talk titles often name only the language.
_FORMOSAN_KW = [
    "アミ語", "アミ族", "タイヤル", "アタヤル", "セデック", "パイワン", "ブヌン",
    "ツォウ", "ルカイ", "サイシャット", "プユマ", "タオ語", "ヤミ語", "サオ語",
    "カバラン", "シラヤ", "閩南語", "台湾語", "客家",
    "Amis", "Atayal", "Seediq", "Paiwan", "Bunun", "Tsou", "Rukai",
    "Saisiyat", "Puyuma", "Kavalan", "Siraya", "Hokkien", "Hakka",
]
_ALL_KW = _TAIWAN_KW + _FORMOSAN_KW
# Case-sensitive on purpose for the Latin names: "Tsou" etc. are proper nouns,
# and lower-case matching would hit ordinary English words ("amiss").
_KW_RE = re.compile("|".join(re.escape(k) for k in _ALL_KW))


_FALSE_POSITIVE_RE = re.compile(r"仙台湾")  # Sendai Bay (see stranger-specific note)


def is_taiwan_related(text: str) -> bool:
    return bool(_KW_RE.search(_FALSE_POSITIVE_RE.sub("", text or "")))


# ---------------------------------------------------------------------------
# Parsing helpers (pure functions — unit tested)
# ---------------------------------------------------------------------------
def parse_dates(text: str) -> list[datetime]:
    """All calendar dates in *text*, in order, as JST midnight datetimes."""
    out: list[datetime] = []
    for m in _DATE_RE.finditer(text or ""):
        try:
            out.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST))
        except ValueError:
            continue
    return out


def _card_for(a_tag) -> object:
    """Climb from a detail link to the smallest ancestor that looks like a card
    (contains a date and exactly one distinct detail ID)."""
    node = a_tag
    best = a_tag
    for _ in range(8):
        node = node.parent
        if node is None or node.name in ("body", "html", "main"):
            break
        ids = {m.group(1) for m in _DETAIL_RE.finditer(" ".join(
            x.get("href", "") for x in node.find_all("a", href=True)))}
        if len(ids) > 1:
            break
        best = node
        if parse_dates(node.get_text(" ", strip=True)):
            return node
    return best


def parse_listing(html: str) -> list[dict]:
    """Return cards as dicts: {event_no, url, title, dates, is_public, text}."""
    soup = BeautifulSoup(html, "html.parser")
    cards: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = _DETAIL_RE.search(a["href"])
        if not m or "/en/" in a["href"]:
            continue
        no = m.group(1)
        if no in cards:
            continue
        card = _card_for(a)
        text = card.get_text("\n", strip=True)
        title = a.get_text(" ", strip=True)
        if not title or title in ("詳細", "詳しく見る", "more"):
            heading = card.find(["h2", "h3", "h4"])
            title = heading.get_text(" ", strip=True) if heading else title
        cards[no] = {
            "event_no": no,
            "url": f"{BASE_URL}/events/detail/e{no}/",
            "title": title,
            "dates": parse_dates(text),
            # "公開" is a substring of "非公開" — test the negative label first.
            "is_public": "非公開" not in text,
            "text": text,
        }
    return list(cards.values())


def _labeled(lines: list[str], label: str, stop_labels: tuple[str, ...]) -> str | None:
    """Value after a label line, e.g. '日時' / ':' / '2026年…' or '日時: 2026年…'.

    Takes the first value line; further lines are appended only when they are
    extra dates (multi-day events list one date per line). Anything else is
    page content, not part of the field."""
    for i, line in enumerate(lines):
        m = re.match(rf"^{re.escape(label)}\s*[:：]?\s*(.*)$", line)
        if not m:
            continue
        parts = [m.group(1).lstrip(":： ").strip()] if m.group(1).strip(":： ") else []
        for nxt in lines[i + 1 : i + 6]:
            if any(nxt.startswith(s) for s in stop_labels):
                break
            if nxt in (":", "："):
                continue
            nxt = nxt.lstrip(":： ").strip()
            if parts and not re.match(r"^\d{4}\s*[年/-]", nxt):
                break
            parts.append(nxt)
        value = " ".join(p for p in parts if p).strip()
        if value:
            return value
    return None


_FIELD_LABELS = ("日時", "場所", "開催形態", "使用言語", "主催・共催", "プログラム",
                 "関連プロジェクト", "申込", "参加費", "問い合わせ", "お問い合わせ")


def parse_detail(html: str) -> dict:
    """Extract fields from a detail page. Missing fields are None."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    h1 = root.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else None
    if not title:
        og = soup.find("meta", property="og:title")
        title = (og.get("content") or "").split("|")[0].strip() if og else None

    lines = [ln for ln in root.get_text("\n", strip=True).split("\n") if ln.strip()]
    stops = _FIELD_LABELS
    when = _labeled(lines, "日時", stops[1:])
    venue = _labeled(lines, "場所", stops)
    form = _labeled(lines, "開催形態", stops)
    lang = _labeled(lines, "使用言語", stops)
    org = _labeled(lines, "主催・共催", stops)

    dates = parse_dates(when or "")
    start = end = None
    if dates:
        start, end = min(dates), max(dates)
        times = _TIME_RE.findall(when or "")
        if times and len(set(dates)) == 1:
            sh, sm = map(int, times[0])
            start = start.replace(hour=sh, minute=sm)
            # End time "13:00-17:30" → 17:30; without one, end = start. Never
            # leave end at midnight (it would sort before start and the web
            # treats end_date < now as finished).
            eh, em = map(int, times[1]) if len(times) > 1 else (sh, sm)
            end = end.replace(hour=eh, minute=em)
            if end < start:
                end = start

    body = "\n".join(lines)
    # Cut site chrome that follows the article (related links, breadcrumbs)
    body = re.split(r"\n(?:関連イベント|最新のイベント|イベント一覧へ)\n", body)[0]

    og_img = soup.find("meta", property="og:image")
    return {
        "title": title,
        "when": when,
        "start": start,
        "end": end,
        "venue": venue,
        "form": form,
        "language": lang,
        "organizer": org,
        "body": body,
        "image_url": og_img.get("content") if og_img else None,
    }


def resolve_venue(venue: str | None, form: str | None) -> tuple[str | None, str | None]:
    """(location_name, location_address). AA研 rooms get the campus address."""
    if not venue:
        return None, None
    parts = [p.strip() for p in re.split(r"[/／]", venue) if p.strip()]
    physical = [p for p in parts if not re.search(r"オンライン|Online|Zoom", p, re.I)]
    if not physical:
        return "オンライン", None
    name = " / ".join(physical)
    if "AA研" in name or "アジア・アフリカ言語文化研究所" in name:
        return name, AA_ADDRESS
    if any(k in name for k in AA_VENUE_KW):
        return name, TUFS_ADDRESS
    return name, None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
class TufsAaScraper(BaseScraper):
    """AA研 public events filtered to Taiwan / Formosan-language topics."""

    SOURCE_NAME = SOURCE_NAME

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT, "Accept-Language": "ja"})

    def _get(self, url: str) -> str | None:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except Exception as exc:  # noqa: BLE001 — log and continue per source contract
            logger.warning("tufs_aa: fetch failed %s: %s", url, exc)
            return None

    def _upcoming_cards(self) -> list[dict]:
        today = datetime.now(_JST).replace(hour=0, minute=0, second=0, microsecond=0)
        found: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            url = LISTING_URL if page == 1 else f"{LISTING_URL}page/{page}/"
            html = self._get(url)
            if html is None:
                break
            cards = parse_listing(html)
            if not cards:
                logger.warning("tufs_aa: no cards on %s — selector drift?", url)
                break
            page_has_future = False
            for c in cards:
                last = max(c["dates"]) if c["dates"] else None
                if last is None or last >= today:
                    page_has_future = True
                    found.append(c)
            if not page_has_future:
                break
            time.sleep(REQUEST_SLEEP)
        return found

    def scrape(self) -> list[Event]:
        cards = self._upcoming_cards()
        public = [c for c in cards if c["is_public"]]
        logger.info("tufs_aa: %d upcoming cards, %d public", len(cards), len(public))

        events: list[Event] = []
        for c in public:
            time.sleep(REQUEST_SLEEP)
            html = self._get(c["url"])
            if html is None:
                continue
            d = parse_detail(html)
            title = d["title"] or c["title"]
            if not is_taiwan_related(f"{title}\n{d['body']}"):
                continue
            start = d["start"] or (min(c["dates"]) if c["dates"] else None)
            if start is None:
                logger.warning("tufs_aa: no date for %s", c["url"])
                continue
            end = d["end"] or start
            loc_name, loc_addr = resolve_venue(d["venue"], d["form"])
            if loc_name is None and d["form"] and "オンライン" in d["form"]:
                loc_name = "オンライン"

            header = f"開催日時: {start.year}年{start.month:02d}月{start.day:02d}日"
            if d["when"]:
                header += f"（{d['when']}）"
            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=f"{SOURCE_NAME}_e{c['event_no']}",
                    source_url=c["url"],
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=f"{header}\n\n{d['body']}",
                    category=["academic"],
                    start_date=start,
                    end_date=end,
                    location_name=loc_name,
                    location_address=loc_addr,
                    location_prefectures=["東京都"] if loc_addr else [],
                    organizer=d["organizer"],
                    image_url=d["image_url"],
                )
            )
        logger.info("tufs_aa: scraped %d Taiwan-related events", len(events))
        return events
