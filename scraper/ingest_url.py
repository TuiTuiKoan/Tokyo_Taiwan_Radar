#!/usr/bin/env python3
"""Single-URL intake: put one event page into the existing pipeline.

Spec: docs/specs/active/url-intake/proposal.md (v2, after plan-critique-1.md)

Subcommands — each does one kind of work, so the workflow can give each job
only the permissions it needs:

    fetch   --url-env NAME --out F   network, no credentials. NAME is an
                                     environment variable holding a URL or an
                                     issue body; the first valid URL is used.
                                     Writes a JSON payload (untrusted data).
    preview --in F                   DB read: validate the payload, look for an
                                     existing event, print a markdown preview.
    apply   --in F                   DB write: look again, insert one pending
                                     event (source_name=url_intake), print a
                                     markdown result. Annotation, enrichment and
                                     IndexNow happen in the next daily main.py run.

Exit codes: 0 ok, 1 not inserted, 2 rejected input, 3 duplicate lookup failed.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

logger = logging.getLogger("ingest_url")

SOURCE_NAME = "url_intake"
SITE = "https://tokyotaiwanradar.com"
UA = "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; +https://tokyotaiwanradar.com)"
MARKER = "<!-- url-intake -->"

MAX_URL_LEN = 2000
MAX_TITLE_LEN = 300
MAX_BODY_LEN = 8000
MIN_BODY_LEN = 200
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT = 20
PAYLOAD_VERSION = 1
PAYLOAD_KEYS = {"version", "url", "title", "body", "language", "http_status", "error", "requested_url"}

_TRACKING_PARAMS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid", "igshid", "ref_src"}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}
_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home.arpa", ".corp")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'）)\]」』]+", re.IGNORECASE)
_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[一-鿿]")
_STRIP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg")


class IntakeError(ValueError):
    """Input that must not reach the pipeline."""


class LookupFailed(RuntimeError):
    """A duplicate lookup failed; refusing to write."""


# ── URL handling ───────────────────────────────────────────────────────────

def normalize_url(raw: str) -> str:
    """Return a canonical http(s) URL or raise IntakeError."""
    url = (raw or "").strip().rstrip(".,、。")
    if not url or len(url) > MAX_URL_LEN:
        raise IntakeError("URL is empty or too long")
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise IntakeError("only http(s) URLs are accepted")
    if parts.username or parts.password:
        raise IntakeError("URLs with credentials are not accepted")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host:
        raise IntakeError("URL has no public host name")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise IntakeError("IP-address URLs are not accepted")
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        raise IntakeError("internal host names are not accepted")
    try:
        port = parts.port
    except ValueError as exc:
        raise IntakeError("invalid port") from exc
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    return urlunsplit((scheme, netloc, parts.path or "/", urlencode(query), ""))


def extract_url(text: str) -> str:
    """First valid URL in free text (an issue body). Raises IntakeError."""
    for match in _URL_IN_TEXT.finditer(text or ""):
        try:
            return normalize_url(match.group(0))
        except IntakeError:
            continue
    raise IntakeError("no valid http(s) URL found")


def source_id_for(url: str) -> str:
    return "url_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def host_of(url: str) -> str:
    host = (urlsplit(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def assert_public_host(host: str, resolver: Callable[..., list] = socket.getaddrinfo) -> None:
    """Every address the host resolves to must be globally routable."""
    try:
        infos = resolver(host, None)
    except OSError as exc:
        raise IntakeError(f"cannot resolve host {host}") from exc
    if not infos:
        raise IntakeError(f"cannot resolve host {host}")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            raise IntakeError(f"host {host} resolves to a non-public address")


# ── Fetching ───────────────────────────────────────────────────────────────

def fetch_html(url: str, session=None, resolver: Callable[..., list] = socket.getaddrinfo) -> tuple[str, str, int]:
    """GET with manual redirects; every hop is normalised and DNS-checked.

    Returns (final_url, html, status). Raises IntakeError.
    """
    import requests

    session = session or requests.Session()
    current = normalize_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        assert_public_host(urlsplit(current).hostname or "", resolver)
        try:
            resp = session.get(
                current,
                headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise IntakeError(f"request failed: {type(exc).__name__}") from exc
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise IntakeError("redirect without Location")
                current = normalize_url(urljoin(current, location))
                continue
            if not 200 <= resp.status_code < 300:
                raise IntakeError(f"HTTP {resp.status_code}")
            chunks, size = [], 0
            for chunk in resp.iter_content(65536):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise IntakeError("response is larger than 2 MB")
                chunks.append(chunk)
            raw = b"".join(chunks)
            encoding = resp.encoding if resp.encoding and resp.encoding.lower() != "iso-8859-1" else None
            html = raw.decode(encoding or resp.apparent_encoding or "utf-8", errors="replace")
            return current, html, resp.status_code
        finally:
            resp.close()
    raise IntakeError("too many redirects")


# ── Page extraction ────────────────────────────────────────────────────────

def detect_language(text: str) -> str:
    if _KANA.search(text or ""):
        return "ja"
    if _HAN.search(text or ""):
        return "zh"
    return "en"


def _clean(text: Any, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()[:limit]


def extract_page(html: str) -> dict[str, str]:
    """Title and body text from an HTML document."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    title = None
    tag = soup.find("meta", attrs={"property": "og:title"})
    if tag and isinstance(tag.get("content"), str):
        title = tag["content"]
    if not (title and title.strip()) and soup.title and soup.title.string:
        title = soup.title.string
    if not (title and title.strip()):
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""

    for t in soup(_STRIP_TAGS):
        t.decompose()
    body = ""
    for selector in ("main", "article", "body"):
        el = soup.select_one(selector)
        if el:
            body = el.get_text(" ", strip=True)
            if len(body) >= MIN_BODY_LEN:
                break
    title, body = _clean(title, MAX_TITLE_LEN), _clean(body, MAX_BODY_LEN)
    return {"title": title, "body": body, "language": detect_language(title + " " + body)}


# ── Payload (crosses the trust boundary between the two jobs) ──────────────

def validate_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("version") != PAYLOAD_VERSION:
        raise IntakeError("payload has an unexpected shape or version")
    extra = set(data) - PAYLOAD_KEYS
    if extra:
        raise IntakeError(f"payload has unexpected keys: {sorted(extra)}")
    if data.get("error") is not None:
        raise IntakeError(f"fetch failed: {_clean(data.get('error'), 200)}")
    url = normalize_url(data.get("url") if isinstance(data.get("url"), str) else "")
    title = _clean(data.get("title"), MAX_TITLE_LEN)
    body = _clean(data.get("body"), MAX_BODY_LEN)
    if not title:
        raise IntakeError("page has no title")
    if len(body) < MIN_BODY_LEN:
        raise IntakeError(f"page text is too short ({len(body)} chars); it may need JavaScript rendering")
    language = data.get("language")
    if language not in ("ja", "zh", "en"):
        language = detect_language(title + " " + body)
    requested = data.get("requested_url")
    try:
        requested = normalize_url(requested) if isinstance(requested, str) else url
    except IntakeError:
        requested = url
    return {"url": url, "requested_url": requested, "title": title, "body": body, "language": language}


def build_event(page: dict[str, Any]):
    from sources.base import Event

    return Event(
        source_name=SOURCE_NAME,
        source_id=source_id_for(page["url"]),
        source_url=page["url"],
        original_language=page["language"],
        raw_title=page["title"],
        raw_description=f"収録元: {page['url']}\n\n{page['body']}",
    )


# ── DB helpers ─────────────────────────────────────────────────────────────

def _client():
    from database import _get_client

    return _get_client()


def find_existing(client, url: str, original: str | None = None) -> list[dict[str, Any]]:
    """Events that already point at this URL. Raises LookupFailed on any error."""
    urls = sorted({u for u in (url, original) if u})
    cols = "id,name_ja,raw_title,source_name,is_active"
    queries = [client.table("events").select(cols).eq("source_name", SOURCE_NAME).eq("source_id", source_id_for(url))]
    for u in urls:
        queries += [
            client.table("events").select(cols).eq("source_url", u),
            client.table("events").select(cols).eq("official_url", u),
            client.table("events").select(cols).contains("secondary_source_urls", [u]),
        ]
    found: dict[str, dict[str, Any]] = {}
    for query in queries:
        try:
            rows = query.limit(5).execute().data or []
        except Exception as exc:
            raise LookupFailed(f"duplicate lookup failed: {type(exc).__name__}") from exc
        for row in rows:
            found[row["id"]] = row
    return list(found.values())


_QUOTED = re.compile(r"[「『“\"]([^」』”\"]{4,60})[」』”\"]")
_RUN = re.compile(r"[\w\u3040-\u30ff\u4e00-\u9fff][\w\u3040-\u30ff\u4e00-\u9fff ・\-]{5,40}")
_SITE_SUFFIX = re.compile(r"\s*[|｜]\s*[^|｜]*$")
_GENERIC = re.compile(r"^(開催のお知らせ|お知らせ|ニュース|NEWS|イベント情報)$", re.IGNORECASE)


def key_phrases(title: str, limit: int = 2) -> list[str]:
    """Distinctive phrases of a page title for a fuzzy duplicate lookup.

    Quoted names (「台湾音市 NEXT 2026」) first; otherwise the longest runs of
    the title with any trailing "| site name" removed.
    """
    title = _SITE_SUFFIX.sub("", title or "").strip()
    phrases = [m.strip() for m in _QUOTED.findall(title)]
    if not phrases:
        bare = re.sub(r"【[^】]*】", " ", title)
        phrases = sorted((m.strip() for m in _RUN.findall(bare)), key=len, reverse=True)
    # A long quoted title rarely matches verbatim elsewhere (dash and colon
    # variants); its longest segment does.
    phrases = [
        max(re.split(r"[：:―—～〜／/]+", ph), key=len).strip() if len(ph) > 20 else ph
        for ph in phrases
    ]
    out: list[str] = []
    for ph in phrases:
        if len(ph) >= 4 and not _GENERIC.match(ph) and ph not in out:
            out.append(ph)
    return out[:limit]


def _ilike_literal(text: str) -> str:
    return "%" + re.sub(r"([%_\\])", r"\\\1", text) + "%"


def find_similar(client, title: str, exclude_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Active events whose title contains a key phrase of this page's title.

    Advisory only (shown in the preview for a human to judge); a failing
    query returns what was found so far instead of aborting.
    """
    exclude_ids = exclude_ids or set()
    cols = "id,name_ja,raw_title,source_name,start_date"
    found: dict[str, dict[str, Any]] = {}
    for phrase in key_phrases(title):
        for col in ("raw_title", "name_ja"):
            try:
                rows = (
                    client.table("events").select(cols).eq("is_active", True)
                    .ilike(col, _ilike_literal(phrase)).limit(5).execute().data or []
                )
            except Exception as exc:
                logger.warning("similar-title lookup failed: %s", exc)
                continue
            for row in rows:
                if row["id"] not in exclude_ids:
                    found[row["id"]] = row
    return list(found.values())[:5]


def same_host_count(client, url: str) -> int | None:
    host = host_of(url)
    try:
        rows = client.table("events").select("source_url").eq("source_name", SOURCE_NAME).execute().data or []
    except Exception:
        return None
    return sum(1 for r in rows if host_of(r.get("source_url") or "") == host)


def event_link(event_id: str) -> str:
    return f"{SITE}/ja/events/{event_id}"


# ── Comment rendering (page text is untrusted) ─────────────────────────────

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+\-!|~])")


def escape_md(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S).replace("<!--", "").replace("-->", "")
    text = _MD_SPECIAL.sub(r"\\\1", text)
    return text.replace("@", "＠")


def _scan(text: str) -> list[str]:
    try:
        from security.injection_guard import scan_for_injection
    except Exception:
        return []
    return sorted({h.category for h in scan_for_injection(text)})


def render_preview(page: dict[str, Any], existing: list[dict[str, Any]], same_host: int | None,
                   similar: list[dict[str, Any]] | None = None) -> str:
    lines = [
        MARKER,
        "### URL intake 預覽（尚未寫入）",
        "",
        f"- **URL**：{page['url']}",
        f"- **標題**：{escape_md(page['title'])}",
        f"- **語言**：{page['language']}　**正文**：{len(page['body'])} 字",
        f"- **同網域已收錄**：{same_host if same_host is not None else '查詢失敗'} 筆（{host_of(page['url'])}）",
    ]
    hits = _scan(page["title"] + " " + page["body"])
    if hits:
        lines.append("- **注意**：正文含疑似 prompt injection 片段（" + "、".join(hits) + "），核准前請打開原頁確認")
    if similar and not existing:
        lines.append("- **可能重複**（標題相近，請人工判斷）：")
        for r in similar:
            day = str(r.get("start_date") or "")[:10] or "日期未定"
            name = escape_md((r.get("name_ja") or r.get("raw_title") or "")[:60])
            lines.append(f"  - {event_link(r['id'])}　{day}　{name}（{escape_md(r.get('source_name') or '')}）")
        lines.append("  同一場活動的話，不要核准，關閉這張 issue 即可。")
    if existing:
        lines.append("- **已收錄**：" + "、".join(event_link(r["id"]) for r in existing))
        lines += ["", "這個 URL 已經在資料庫裡，不需要核准。"]
    else:
        lines += [
            "- **已收錄**：無",
            "",
            "<details><summary>正文前 400 字</summary>",
            "",
            escape_md(page["body"][:400]),
            "",
            "</details>",
            "",
            "要收錄的話，請由 repo 擁有者在這張 issue 貼上 `url-intake:approved` label。"
            "寫入後隔天 09:00 的每日管線會完成標註。",
        ]
    return "\n".join(lines)


def render_result(result: dict[str, Any]) -> str:
    status = result["status"]
    lines = [MARKER, "### URL intake 結果", "", f"- **URL**：{result['url']}"]
    if status == "inserted":
        lines += [
            f"- **已寫入**：{result['event_url']}（`pending`）",
            "- 標註完成前，這個活動頁會顯示 404；隔天 09:00 的每日管線標註後上線，要提早可手動執行 Annotate Now workflow。",
        ]
    elif status == "duplicate":
        lines.append("- **已收錄過**：" + "、".join(event_link(i) for i in result["existing_ids"]))
    else:
        lines.append("- **沒有寫入**：可能被 source_exclusions 規則擋下，或寫入失敗；請看 workflow log")
    count = result.get("same_host_count")
    lines.append(f"- **同網域已收錄**：{count if count is not None else '查詢失敗'} 筆（{result['host']}）")
    if count and count >= 2:
        lines.append("- 這個網域已收錄 2 次以上，值得評估寫成正式來源（`source-intake`）。")
    return "\n".join(lines)


# ── Subcommands ────────────────────────────────────────────────────────────

def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        url = extract_url(os.environ.get(args.url_env, ""))
        final_url, html, status = fetch_html(url)
    except IntakeError as exc:
        # Hand the reason to the db job so it can tell the issue; exit 0 so it runs.
        Path(args.out).write_text(json.dumps({"version": PAYLOAD_VERSION, "error": str(exc)}), encoding="utf-8")
        logger.warning("fetch rejected: %s", exc)
        return 0
    page = extract_page(html)
    payload = {"version": PAYLOAD_VERSION, "url": final_url, "requested_url": url, "http_status": status, **page}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("fetched %s: title=%d chars, body=%d chars", final_url, len(page["title"]), len(page["body"]))
    return 0


def _load(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    if len(raw) > 200_000:
        raise IntakeError("payload file is too large")
    try:
        return validate_payload(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise IntakeError("payload is not JSON") from exc


def cmd_preview(args: argparse.Namespace) -> int:
    page = _load(args.inp)
    client = _client()
    existing = find_existing(client, page["url"], page.get("requested_url"))
    similar = [] if existing else find_similar(client, page["title"])
    print(render_preview(page, existing, same_host_count(client, page["url"]), similar))
    return 0


def run_apply(page: dict[str, Any], client, upsert: Callable, lookup_id: Callable) -> dict[str, Any]:
    result: dict[str, Any] = {"url": page["url"], "host": host_of(page["url"]), "status": None}
    existing = find_existing(client, page["url"], page.get("requested_url"))
    if existing:
        result.update(status="duplicate", existing_ids=[r["id"] for r in existing])
    else:
        event = build_event(page)
        upsert([event])
        event_id = lookup_id(SOURCE_NAME, event.source_id)
        if event_id:
            result.update(status="inserted", event_id=event_id, event_url=event_link(event_id))
        else:
            result["status"] = "not_inserted"
    result["same_host_count"] = same_host_count(client, page["url"])
    return result


def cmd_apply(args: argparse.Namespace) -> int:
    from database import get_event_id_by_source, upsert_events

    page = _load(args.inp)
    result = run_apply(page, _client(), upsert_events, get_event_id_by_source)
    print(render_result(result))
    return 0 if result["status"] in ("inserted", "duplicate") else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    parser = argparse.ArgumentParser(description="Single-URL intake")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--url-env", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_fetch)
    for name, func in (("preview", cmd_preview), ("apply", cmd_apply)):
        p = sub.add_parser(name)
        p.add_argument("--in", dest="inp", required=True)
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except IntakeError as exc:
        print(f"{MARKER}\nURL intake：未處理（{escape_md(str(exc))}）")
        return 2
    except LookupFailed as exc:
        print(f"{MARKER}\nURL intake：查重失敗，為避免重複寫入已中止（{exc}）")
        return 3


if __name__ == "__main__":
    sys.exit(main())
