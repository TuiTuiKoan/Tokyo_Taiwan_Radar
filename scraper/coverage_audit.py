"""Weekly keyword coverage audit (spec coverage-audit Phase B).

Two subcommands, run by two jobs in .github/workflows/scraper-quality.yml:

    python coverage_audit.py db --out coverage-known.json
        production job: select-only, never touches external content.
        Writes known PR TIMES keys plus mis-capture counts.

    python coverage_audit.py probe --known coverage-known.json \
        --summary summary.md --comment comment.md --repo OWNER/REPO --run-url URL
        no-secrets job: queries the PR TIMES keyword API, classifies each
        release with the scraper's own verdict functions, fetches at most
        MAX_BODY_FETCHES bodies, and renders the report.

Decisions are made only by the public verdict functions
(prtimes.title_verdict / body_verdict); this module adds no filter rules of
its own. It may import prtimes I/O helpers and constants.

No LLM calls, no database writes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from taiwan_keywords import compound_only

JST = ZoneInfo("Asia/Tokyo")

PROBE_KEYWORDS = ("日台", "日中台", "台日", "台湾")
CONTROL_KEYWORD = "台湾"
PROBE_PAGES = 2
PAGE_LIMIT = 40
MIN_AGE_HOURS = 48
MAX_BODY_FETCHES = 20
MISFIRE_DAYS = 28
MISFIRE_SOURCES = ("prtimes", "google_news_rss")

# #724 (Phase A) merge time; compound-only events are counted from here.
PHASE_A_MERGED_AT = "2026-11-22T13:14:16+00:00"

# Literal copy of annotator.RELEVANCE_GATE_REASON: importing annotator pulls in
# playwright and supabase. tests/test_coverage_audit.py asserts they match.
RELEVANCE_GATE_REASON = "auto-deactivated: annotator Taiwan relevance gate"

COUNTED_PREFIXES = ("out_of_scope:", "admin confirmed irrelevant", RELEVANCE_GATE_REASON)
ATTRIBUTION_PREFIXES = ("manually deactivated by admin",)
EXCLUDED_PREFIXES = (
    "merged",
    "news article merged",
    "same-work_id",
    "manual_merge",
    "duplicate:",
    "grandchild duplicate",
    "orphan sub-event",
    "pre_migration_044_legacy",
    "auto-deactivated: blank or placeholder title",
    "admin reported wrong",
    "data_corruption",
)

TITLE_DISPLAY_MAX = 120
TITLE_PARAM_MAX = 60
REASON_DISPLAY_MAX = 80
COMMENT_MAX = 60000
PRTIMES_HOST = "prtimes.jp"

_RELEASE_PATH_IDS_RE = re.compile(r"/(\d{9})\.(\d{9})\.html$")


# --------------------------------------------------------------------------- keys

def release_key_from_url(url: str | None) -> tuple[int, int] | None:
    """(release_id, company_id) from a PR TIMES release URL or path."""
    if not url:
        return None
    try:
        path = urllib.parse.urlsplit(url).path
    except ValueError:
        return None
    m = _RELEASE_PATH_IDS_RE.search(path)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def known_from_rows(rows: Iterable[dict]) -> dict[str, list]:
    keys: set[tuple[int, int]] = set()
    source_ids: set[str] = set()
    for row in rows:
        for field in ("source_url", "official_url"):
            value = row.get(field)
            if value and PRTIMES_HOST in value:
                key = release_key_from_url(value)
                if key:
                    keys.add(key)
        if row.get("source_name") == "prtimes" and row.get("source_id"):
            source_ids.add(str(row["source_id"]))
    return {"release_keys": sorted([list(k) for k in keys]), "source_ids": sorted(source_ids)}


def release_identity(rel: dict) -> tuple[tuple[int, int] | None, set[str]]:
    """Keys under which a PR TIMES API release may already be stored."""
    from sources.prtimes import _build_source_id

    rid = rel.get("release_id")
    path = rel.get("release_url", "") or ""
    key = release_key_from_url(path)
    if key is None and str(rid or "").isdigit() and str(rel.get("company_id") or "").isdigit():
        key = (int(rid), int(rel["company_id"]))
    ids = {_build_source_id(rid, rel.get("company_id"), path), f"prtimes_{rid}"}
    return key, ids


def is_known(rel: dict, known: dict) -> bool:
    key, ids = release_identity(rel)
    keys = {tuple(k) for k in known.get("release_keys", [])}
    return (key is not None and key in keys) or bool(ids & set(known.get("source_ids", [])))


# ------------------------------------------------------------------- mis-capture

def classify_deactivation(row: dict) -> str:
    """'active' | 'counted' | 'attribution' | 'excluded' | 'unclassified'."""
    if row.get("is_active"):
        return "active"
    reason = (row.get("deactivated_reason") or "").strip()
    if reason.startswith(COUNTED_PREFIXES):
        return "counted"
    if reason.startswith(ATTRIBUTION_PREFIXES):
        return "attribution"
    if reason.startswith(EXCLUDED_PREFIXES):
        return "excluded"
    return "unclassified"


def misfire_stats(rows: Iterable[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for source in MISFIRE_SOURCES:
        stats[source] = {"total": 0, "counted": 0, "attribution": 0, "excluded": 0, "unclassified": {}}
    for row in rows:
        source = row.get("source_name")
        if source not in stats:
            continue
        bucket = stats[source]
        bucket["total"] += 1
        kind = classify_deactivation(row)
        if kind == "unclassified":
            reason = (row.get("deactivated_reason") or "(null)").strip()[:REASON_DISPLAY_MAX]
            bucket["unclassified"][reason] = bucket["unclassified"].get(reason, 0) + 1
        elif kind != "active":
            bucket[kind] += 1
    return stats


def compound_stats(rows: Iterable[dict]) -> dict[str, Any]:
    selected = [r for r in rows if r.get("source_name") in MISFIRE_SOURCES and compound_only(r.get("raw_title") or "")]
    counted = [r for r in selected if classify_deactivation(r) == "counted"]
    return {
        "since": PHASE_A_MERGED_AT,
        "total": len(selected),
        "counted": len(counted),
        "event_ids": sorted(r["id"] for r in selected if r.get("id"))[:50],
    }


# ------------------------------------------------------------------------- probe

def jst_now() -> datetime:
    return datetime.now(JST).replace(tzinfo=None)


def classify_release(rel: dict, known: dict, now: datetime) -> tuple[str, datetime | None]:
    """Title-level and window classification of one API release.

    Returns (category, released_at). category is one of:
    'known', 'title:<reason>', 'too_new', 'too_old', 'needs_body'.
    """
    from sources.prtimes import LOOKBACK_DAYS, _parse_released_at, title_verdict

    released = _parse_released_at(rel.get("released_at", "") or "")
    if is_known(rel, known):
        return "known", released
    ok, reason = title_verdict(rel.get("title", "") or "")
    if not ok:
        return f"title:{reason}", released
    if released is not None:
        if released > now - timedelta(hours=MIN_AGE_HOURS):
            return "too_new", released
        if released < now - timedelta(days=LOOKBACK_DAYS):
            return "too_old", released
    return "needs_body", released


def classify_body(title: str, body_text: str) -> str:
    """'candidate' | 'body:<reason>' | 'undetermined' (no body)."""
    from sources.prtimes import body_verdict

    if not (body_text or "").strip():
        return "undetermined"
    ok, reason = body_verdict(title, body_text)
    return "candidate" if ok else f"body:{reason}"


def fetch_releases(session, keyword: str) -> list[dict]:
    from sources.prtimes import _API_URL, _HEADERS

    releases: list[dict] = []
    for page in range(1, PROBE_PAGES + 1):
        url = f"{_API_URL}?keyword={urllib.parse.quote(keyword)}&page={page}&limit={PAGE_LIMIT}"
        resp = session.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        batch = (resp.json().get("data") or {}).get("release_list") or []
        releases.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
        time.sleep(1)
    return releases


def run_probe(known: dict, session, fetch_body, now: datetime) -> dict:
    """Probe every keyword; fetch_body(url) -> body_text (or "" on failure)."""
    from sources.prtimes import _PR_BASE

    per_keyword: dict[str, dict] = {}
    seen: dict[str, dict] = {}
    for keyword in PROBE_KEYWORDS:
        info: dict[str, Any] = {"releases": 0, "categories": Counter(), "oldest": None, "newest": None, "error": None}
        try:
            releases = fetch_releases(session, keyword)
        except Exception as exc:  # recorded, never retried
            info["error"] = type(exc).__name__
            per_keyword[keyword] = info
            continue
        for rel in releases:
            category, released = classify_release(rel, known, now)
            info["releases"] += 1
            info["categories"][category.split(":")[0] if category.startswith("title:") else category] += 1
            if category.startswith("title:"):
                info["categories"][category] += 1
            if released:
                info["oldest"] = min(filter(None, [info["oldest"], released]))
                info["newest"] = max(filter(None, [info["newest"], released]))
            path = rel.get("release_url", "") or ""
            if category == "needs_body" and path and path not in seen:
                seen[path] = {
                    "title": rel.get("title", "") or "",
                    "url": _PR_BASE + path,
                    "keyword": keyword,
                    "released": released.isoformat(sep=" ", timespec="minutes") if released else None,
                    "result": None,
                }
        per_keyword[keyword] = info

    fetched = 0
    for item in seen.values():
        if fetched >= MAX_BODY_FETCHES:
            item["result"] = "undetermined"
            continue
        fetched += 1
        item["result"] = classify_body(item["title"], fetch_body(item["url"]))
    return {"keywords": per_keyword, "items": list(seen.values()), "body_fetches": fetched}


# ------------------------------------------------------------------------ render

def safe_title(title: str, limit: int = TITLE_DISPLAY_MAX) -> str:
    from ingest_url import _URL_IN_TEXT, escape_md

    text = " ".join((title or "").split())
    text = _URL_IN_TEXT.sub("", text).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return escape_md(text)


def safe_prtimes_url(url: str) -> str | None:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https" or (parts.hostname or "").lower() != PRTIMES_HOST:
        return None
    if not _RELEASE_PATH_IDS_RE.search(parts.path):
        return None
    return urllib.parse.urlunsplit(("https", PRTIMES_HOST, parts.path, "", ""))


def one_click_link(repo: str, title: str, url: str) -> str:
    """New-issue link that opens a url-intake preview (never an approval)."""
    plain = " ".join((title or "").split())
    from ingest_url import _URL_IN_TEXT

    plain = _URL_IN_TEXT.sub("", plain).strip()[:TITLE_PARAM_MAX]
    query = urllib.parse.urlencode(
        {"title": f"url-intake: {plain}", "labels": "url-intake", "body": url},
        quote_via=urllib.parse.quote,
    )
    return f"https://github.com/{repo}/issues/new?{query}"


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return "—"


def render_report(known: dict, probe: dict, repo: str, run_url: str, today: str) -> tuple[str, str]:
    """(full run summary markdown, issue comment markdown)."""
    items = probe["items"]
    candidates = [i for i in items if i["result"] == "candidate"]
    body_filtered = [i for i in items if (i["result"] or "").startswith("body:")]
    undetermined = [i for i in items if i["result"] == "undetermined"]

    lines = [f"## 覆蓋稽核週報 {today}", ""]
    lines.append("### 漏抓（prtimes 探測）")
    lines.append("")
    lines.append("| 探測詞 | 取得 | 涵蓋發布日 | 已收錄 | 標題過濾 | 太新(<48h) | 超過回溯 | 需看正文 | 錯誤 |")
    lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for keyword, info in probe["keywords"].items():
        c = info["categories"]
        label = f"{keyword}（對照組）" if keyword == CONTROL_KEYWORD else keyword
        lines.append(
            f"| {label} | {info['releases']} | {_fmt_dt(info['oldest'])}～{_fmt_dt(info['newest'])} | "
            f"{c.get('known', 0)} | {c.get('title', 0)} | {c.get('too_new', 0)} | {c.get('too_old', 0)} | "
            f"{c.get('needs_body', 0)} | {info['error'] or ''} |"
        )
    reasons = Counter()
    for info in probe["keywords"].values():
        for k, v in info["categories"].items():
            if k.startswith("title:"):
                reasons[k[6:]] += v
    if reasons:
        lines.append("")
        lines.append("標題過濾原因：" + "、".join(f"`{k}` {v}" for k, v in sorted(reasons.items())))
    lines.append("")
    lines.append(
        f"正文判斷 {probe['body_fetches']} 筆（上限 {MAX_BODY_FETCHES}）：漏抓候選 {len(candidates)}、"
        f"正文過濾 {len(body_filtered)}、未判定 {len(undetermined)}。"
    )
    lines.append("")
    candidate_lines: list[str] = []
    if candidates:
        candidate_lines.append("#### 漏抓候選（請人工判斷；收錄請點「開預覽」，核准仍需自己貼 `url-intake:approved`）")
        candidate_lines.append("")
        for item in candidates:
            url = safe_prtimes_url(item["url"])
            if not url:
                continue
            link = one_click_link(repo, item["title"], url)
            candidate_lines.append(
                f"- {safe_title(item['title'])}（{item['keyword']}，{item['released'] or '日期不明'}） "
                f"[原文]({url}) · [開預覽]({link})"
            )
        candidate_lines.append("")
    else:
        candidate_lines.append("本週沒有漏抓候選。")
        candidate_lines.append("")
    lines.extend(candidate_lines)

    lines.append(f"### 亂抓（過去 {MISFIRE_DAYS} 天新增）")
    lines.append("")
    lines.append("| 來源 | 判定不相關 / 新增 | 待人工歸因 | 去重或清理 | 未分類 |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    misfire = known.get("misfire", {})
    for source in MISFIRE_SOURCES:
        m = misfire.get(source, {})
        uncls = sum((m.get("unclassified") or {}).values())
        lines.append(
            f"| {source} | {m.get('counted', 0)} / {m.get('total', 0)} | {m.get('attribution', 0)} | "
            f"{m.get('excluded', 0)} | {uncls} |"
        )
    uncls_lines = []
    for source in MISFIRE_SOURCES:
        for reason, count in sorted((misfire.get(source, {}).get("unclassified") or {}).items()):
            uncls_lines.append(f"- {source}：`{safe_title(reason, REASON_DISPLAY_MAX)}` × {count}")
    if uncls_lines:
        lines.append("")
        lines.append("未分類的停用原因：")
        lines.extend(uncls_lines)
    comp = known.get("compound", {})
    lines.append("")
    lines.append(
        f"只靠複合詞（日中台／日台／台日）收進來的事件，自 Phase A 合併起：判定不相關 "
        f"{comp.get('counted', 0)} / {comp.get('total', 0)}。"
    )
    for event_id in comp.get("event_ids", [])[:20]:
        lines.append(f"- https://tokyotaiwanradar.com/ja/events/{event_id}")
    lines.append("")
    lines.append(f"完整執行紀錄：{run_url}")
    summary = "\n".join(lines) + "\n"

    comment = summary
    if len(comment) > COMMENT_MAX:
        comment = comment[:COMMENT_MAX] + f"\n\n…（已截斷，完整內容見 {run_url}）\n"
    return summary, comment


# --------------------------------------------------------------------------- CLI

def cmd_db(args: argparse.Namespace) -> int:
    from supabase import create_client

    from db_paging import fetch_all

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    known_rows = fetch_all(
        lambda: client.table("events")
        .select("id,source_name,source_id,source_url,official_url")
        .or_("source_url.ilike.*prtimes.jp*,official_url.ilike.*prtimes.jp*,source_name.eq.prtimes")
        .order("id")
    )
    since = (datetime.now(timezone.utc) - timedelta(days=MISFIRE_DAYS)).isoformat()
    fields = "id,source_name,raw_title,is_active,deactivated_reason"
    recent = fetch_all(
        lambda: client.table("events").select(fields)
        .in_("source_name", list(MISFIRE_SOURCES)).gte("created_at", since).order("id")
    )
    since_a = fetch_all(
        lambda: client.table("events").select(fields)
        .in_("source_name", list(MISFIRE_SOURCES)).gte("created_at", PHASE_A_MERGED_AT).order("id")
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **known_from_rows(known_rows),
        "misfire": misfire_stats(recent),
        "compound": compound_stats(since_a),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print(f"known release keys={len(payload['release_keys'])} source_ids={len(payload['source_ids'])}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    import requests

    from sources.prtimes import _UA, _fetch_detail

    with open(args.known, encoding="utf-8") as fh:
        known = json.load(fh)
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    def fetch_body(url: str) -> str:
        body_text, _desc = _fetch_detail(url, session)
        time.sleep(1)
        return body_text

    probe = run_probe(known, session, fetch_body, jst_now())
    today = datetime.now(JST).strftime("%Y-%m-%d")
    summary, comment = render_report(known, probe, args.repo, args.run_url, today)
    with open(args.summary, "w", encoding="utf-8") as fh:
        fh.write(summary)
    with open(args.comment, "w", encoding="utf-8") as fh:
        fh.write(comment)
    errors = [k for k, v in probe["keywords"].items() if v["error"]]
    if len(errors) == len(PROBE_KEYWORDS):
        print("all probe keywords failed", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_db = sub.add_parser("db")
    p_db.add_argument("--out", required=True)
    p_probe = sub.add_parser("probe")
    p_probe.add_argument("--known", required=True)
    p_probe.add_argument("--summary", required=True)
    p_probe.add_argument("--comment", required=True)
    p_probe.add_argument("--repo", required=True)
    p_probe.add_argument("--run-url", required=True)
    args = parser.parse_args(argv)
    return cmd_db(args) if args.cmd == "db" else cmd_probe(args)


if __name__ == "__main__":
    sys.exit(main())
