"""
Scraper for Taiwan-related books via NDL OpenSearch API.

Strategy:
  1. Fetch NDL OpenSearch API (https://ndlsearch.ndl.go.jp/api/opensearch)
      with title="台湾" and a rolling from=YYYY-MM-DD server-side filter.
      A short from= window makes NDL return results in publication-date
      descending order, so recently published books are not pushed out of
      the _MAX_RESULTS=500 window by relevance ranking.
  2. Paginate via &idx= (1-based offset) up to 500 results total
  3. Skip periodical issues client-side via link suffix -iNNNNN
  4. Taiwan relevance filter on title + description (client-side)
    5. source_id: ndl_{trailing digits of dc:identifier} or ndl_{md5(link)[:12]}
    6. start_date = end_date = publication date (UTC midnight)
    7. For book-publication records, map dc:publisher to organizer and dc:creator to performer.
    8. Capture the bibliographic container (journal) title from the dc:description
       element labelled '掲載誌：' into raw_description.
"""

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event, dedup_events, is_jpro_placeholder_date

logger = logging.getLogger(__name__)

SOURCE_NAME = "ndl_opensearch"
NDL_API = "https://ndlsearch.ndl.go.jp/api/opensearch"

# Dynamic params built per-run (from= computed at runtime)
_BASE_PARAMS: dict[str, str] = {
    "title": "台湾",
    "cnt": "100",
}

NS = {
    "dc":      "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}

_MAX_RESULTS = 500
_PAGE_SIZE = 100
# A short from= window makes NDL sort by publication date descending, keeping
# recent new releases inside the _MAX_RESULTS=500 window instead of being
# pushed out by relevance ranking under a large window.
_LOOKBACK_DAYS = 90
_REQUEST_DELAY = 1.0

TAIWAN_KEYWORDS = [
    "台湾", "臺灣", "Taiwan", "台北", "台南", "台中", "高雄",
    "客家", "原住民", "原住民族", "閩南", "ホーロー", "台語",
    "minnan", "hakka",
]

# NDL labels the container title with a full-width colon; the half-width form is
# accepted defensively.
CONTAINER_TITLE_LABEL = "掲載誌"
_CONTAINER_TITLE_LABEL_RE = re.compile(rf"^{CONTAINER_TITLE_LABEL}[：:]?\s*")
CONTAINER_TITLE_PREFIX = "掲載誌: "


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _strip_null(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s.replace("\x00", "")


def _parse_issued_date(value: str) -> Optional[date]:
    """Parse a complete dcterms:issued / dc:date value 'YYYY-MM-DD'.

    Incomplete values ('YYYY' or 'YYYY-MM') are rejected so a partial date is
    never padded into a fabricated publication day.
    """
    value = value.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    value = value.replace("．", ".")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _get_text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip().replace("\x00", "")


def _container_title(item: ET.Element) -> Optional[str]:
    """Return the journal container title from the '掲載誌：…' dc:description.

    An item may carry several dc:description elements (e.g. '出版タイプ： VoR');
    only the one labelled 掲載誌 holds the bibliographic container title.
    dcndl:seriesTitle is a book-series title and is deliberately never used.
    """
    for el in item.findall("dc:description", NS):
        text = _strip_null(_get_text(el)) or ""
        if text.startswith(CONTAINER_TITLE_LABEL):
            value = _CONTAINER_TITLE_LABEL_RE.sub("", text).strip()
            if value:
                return value
    return None


class NdlOpensearchScraper(BaseScraper):
    SOURCE_NAME = "ndl_opensearch"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        from_date = (date.today() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        offset = 1  # NDL uses 1-based idx

        while offset <= _MAX_RESULTS:
            params = dict(_BASE_PARAMS)
            params["from"] = from_date
            params["idx"] = str(offset)
            try:
                resp = requests.get(
                    NDL_API,
                    params=params,
                    headers={"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"},
                    timeout=20,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
            except Exception as exc:
                logger.warning("ndl_opensearch: request failed at offset %d: %s", offset, exc)
                break

            channel = root.find("channel")
            if channel is None:
                logger.warning("ndl_opensearch: no <channel> at offset %d", offset)
                break

            items = channel.findall("item")
            if not items:
                break

            for item in items:
                title_raw = _get_text(item.find("title"))
                link_raw = _get_text(item.find("link"))
                description_raw = _get_text(item.find("description"))

                # Skip periodical issues (link ends in -iNNNNN = newspaper issue)
                if re.search(r"-i\d+$", link_raw):
                    continue

                # Taiwan filter (client-side)
                if not _is_taiwan(f"{title_raw} {description_raw}"):
                    continue

                # Publication date: dcterms:issued → dc:date (complete YYYY-MM-DD only)
                issued_date: Optional[date] = None

                issued_el = item.find("dcterms:issued", NS)
                if issued_el is not None and issued_el.text:
                    issued_date = _parse_issued_date(issued_el.text)

                if issued_date is None:
                    dc_date_el = item.find("dc:date", NS)
                    if dc_date_el is not None and dc_date_el.text:
                        issued_date = _parse_issued_date(dc_date_el.text)

                # source_id: prefer trailing digits from dc:identifier, else md5(link)
                identifier_el = item.find("dc:identifier", NS)
                identifier_text = _get_text(identifier_el)
                id_digits = re.search(r"(\d{8,})\s*$", identifier_text)
                if id_digits:
                    source_id = f"ndl_{id_digits.group(1)}"
                elif link_raw:
                    source_id = f"ndl_{hashlib.md5(link_raw.encode()).hexdigest()[:12]}"
                else:
                    continue  # no stable ID possible

                publisher_el = item.find("dc:publisher", NS)
                organizer = _strip_null(_get_text(publisher_el)) or None
                creator_el = item.find("dc:creator", NS)
                performer = _strip_null(_get_text(creator_el)) or None
                container_title = _container_title(item)

                start_dt: Optional[datetime] = None
                if issued_date is not None:
                    start_dt = datetime(
                        issued_date.year, issued_date.month, issued_date.day,
                        tzinfo=timezone.utc,
                    )
                if is_jpro_placeholder_date(start_dt):
                    start_dt = None

                raw_desc = _strip_null(description_raw) or ""
                if organizer:
                    raw_desc = f"出版社: {organizer}\n\n{raw_desc}".strip()
                if performer:
                    raw_desc = f"著者: {performer}\n\n{raw_desc}".strip()
                if container_title:
                    raw_desc = f"{CONTAINER_TITLE_PREFIX}{container_title}\n\n{raw_desc}".strip()

                events.append(Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=_strip_null(link_raw) or NDL_API,
                    original_language="ja",
                    name_ja=_strip_null(title_raw) or None,
                    raw_title=_strip_null(title_raw) or None,
                    raw_description=raw_desc or None,
                    start_date=start_dt,
                    end_date=start_dt,
                    location_name=None,
                    location_address=None,
                    location_prefectures=[],
                    category=["books_media"],
                    event_form=["publication"],
                    name_ja_locked=True,
                    organizer=organizer,
                    performer=performer,
                ))

            if len(items) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
            time.sleep(_REQUEST_DELAY)

        result = dedup_events(events)
        logger.info("ndl_opensearch: %d events after dedup", len(result))
        return result
