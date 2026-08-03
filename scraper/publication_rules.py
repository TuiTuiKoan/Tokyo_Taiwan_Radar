from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PUBLICATION_NULL_FIELDS = (
    "location_address",
    "location_address_zh",
    "location_address_en",
    "business_hours",
    "business_hours_zh",
    "business_hours_en",
    "location_prefectures",
)

# Cleared for exact-pure rows like PUBLICATION_NULL_FIELDS, but deliberately NOT
# part of it: these carry no empty-sentinel field_correction contract.
PUBLICATION_VENUE_NAME_FIELDS = (
    "location_name",
    "location_name_zh",
    "location_name_en",
)

_NDL_PERIODICAL_FAMILY = "R000000004"
_PUBLISHER_TYPE_MARKERS_RE = re.compile(
    r"^(?:株式会社|有限会社|合同会社|一般社団法人|一般財団法人|公益社団法人|公益財団法人|\(株\)|㈱)"
    r"|(?:株式会社|有限会社|合同会社)$"
)
_IDENTITY_CLEAN_RE = re.compile(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+")
_DENIED_HOST_SUFFIXES = (
    "ndlsearch.ndl.go.jp",
    "ndl.go.jp",
    "hanmoto.com",
    "amazon.co.jp",
    "amazon.com",
    "rakuten.co.jp",
    "books.rakuten.co.jp",
    "kinokuniya.co.jp",
    "honto.jp",
    "bookwalker.jp",
    "7net.omni7.jp",
    "shopping.yahoo.co.jp",
    "google.com",
    "google.co.jp",
    "bing.com",
    "duckduckgo.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
    "wikipedia.org",
    "note.com",
)
_DENIED_PATH_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")


@dataclass(frozen=True)
class PublisherUrlValidation:
    accepted: bool
    canonical_url: str | None
    reason: str
    evidence: tuple[str, ...] = ()


def _record_value(record: object, field: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(field)
    return getattr(record, field, None)


def normalize_event_forms(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = value
    elif isinstance(value, (set, frozenset)):
        values = sorted(value, key=str)
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        canonical = item.strip()
        if not canonical or canonical in seen:
            continue
        normalized.append(canonical)
        seen.add(canonical)
    return normalized


def is_pure_publication_record(record: object) -> bool:
    return normalize_event_forms(_record_value(record, "event_form")) == ["publication"]


def partition_pure_publications(rows: Iterable[Any]) -> tuple[list[Any], list[Any]]:
    """Split enrichment candidates into (physical, pure_publication) rows.

    Pure publications have no venue and no opening hours, so every location /
    address / prefecture / geocode enrichment must drop them at candidate stage.
    """
    physical: list[Any] = []
    publications: list[Any] = []
    for row in rows:
        (publications if is_pure_publication_record(row) else physical).append(row)
    return physical, publications


def is_pure_publication_in_db(sb: Any, event_id: str) -> bool:
    """Re-read event_form immediately before a write (TOCTOU guard).

    Candidate queries can go stale, and enrichment write helpers can be called
    directly, so the PUBLICATION_NULL_FIELDS policy is re-verified per write.
    """
    rows = (
        sb.table("events")
        .select("event_form")
        .eq("id", event_id)
        .limit(1)
        .execute()
        .data
    ) or []
    return bool(rows) and is_pure_publication_record(rows[0])


def is_ndl_periodical_article(record: object) -> bool:
    if not is_pure_publication_record(record):
        return False
    if _record_value(record, "source_name") != "ndl_opensearch":
        return False

    for field in ("record_family", "ndl_record_family", "publication_record_family"):
        if str(_record_value(record, field) or "").strip().upper() == _NDL_PERIODICAL_FAMILY:
            return True

    urls: list[str] = []
    for field in ("source_url", "official_url"):
        value = _record_value(record, field)
        if isinstance(value, str):
            urls.append(value)
    record_links = _record_value(record, "record_links")
    if isinstance(record_links, list):
        for link in record_links:
            if isinstance(link, Mapping) and isinstance(link.get("url"), str):
                urls.append(link["url"])
    return any(_NDL_PERIODICAL_FAMILY in url.upper() for url in urls)


def normalize_publisher_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = _PUBLISHER_TYPE_MARKERS_RE.sub("", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or None


def canonicalize_publisher_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return None
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def _normalized_identity(value: str | None) -> str:
    normalized = normalize_publisher_name(value)
    if not normalized:
        return ""
    return _IDENTITY_CLEAN_RE.sub("", unicodedata.normalize("NFKC", normalized).casefold())


def _host_is_denied(host: str) -> bool:
    return any(host == denied or host.endswith(f".{denied}") for denied in _DENIED_HOST_SUFFIXES)


def validate_publisher_homepage(
    candidate_url: str | None,
    publisher_name: str | None,
    *,
    page_title: str | None = None,
    page_text: str | None = None,
    aliases: tuple[str, ...] | list[str] = (),
) -> PublisherUrlValidation:
    canonical_url = canonicalize_publisher_url(candidate_url)
    if canonical_url is None:
        return PublisherUrlValidation(False, None, "invalid-url")

    parsed = urlsplit(canonical_url)
    host = parsed.hostname or ""
    if _host_is_denied(host):
        return PublisherUrlValidation(False, canonical_url, "denied-host")
    if parsed.path.casefold().endswith(_DENIED_PATH_SUFFIXES):
        return PublisherUrlValidation(False, canonical_url, "document-url")
    if any(token in parsed.path.casefold() for token in ("/search", "/affiliate", "/redirect")):
        return PublisherUrlValidation(False, canonical_url, "denied-path")

    identities = {
        identity
        for identity in (_normalized_identity(publisher_name), *(_normalized_identity(alias) for alias in aliases))
        if len(identity) >= 3
    }
    if not identities:
        return PublisherUrlValidation(False, canonical_url, "publisher-name-unavailable")

    title_identity = _normalized_identity(page_title)
    body_identity = _normalized_identity(page_text)
    domain_identity = _IDENTITY_CLEAN_RE.sub("", host.removeprefix("www.").split(".", 1)[0].casefold())
    evidence: list[str] = []
    if any(identity in title_identity for identity in identities):
        evidence.append("title")
    if any(identity in body_identity for identity in identities):
        evidence.append("body")
    if any(identity in domain_identity or domain_identity in identity for identity in identities if len(domain_identity) >= 3):
        evidence.append("domain")
    if not evidence:
        return PublisherUrlValidation(False, canonical_url, "publisher-identity-unverified")
    return PublisherUrlValidation(True, canonical_url, "accepted", tuple(evidence))


def validated_registry_homepage(
    publisher_name: str | None,
    homepage_url: str | None,
    *,
    aliases: tuple[str, ...] | list[str] = (),
) -> str | None:
    """Return a canonical homepage URL only when it passes strict validation.

    Registry homepage backfills must be deterministic and must not emit marketplace,
    search, redirect, or document URLs.
    """
    result = validate_publisher_homepage(
        homepage_url,
        publisher_name,
        # We only have registry metadata in writer/annotator paths. Feeding the
        # normalized publisher name as a title hint still enforces URL/host/path
        # deny-lists while requiring publisher-name consistency.
        page_title=publisher_name,
        aliases=aliases,
    )
    if not result.accepted:
        return None
    return result.canonical_url
