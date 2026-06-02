from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

PLATFORM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Netflix", re.compile(r"(?:Netflix|ネットフリックス)")),
    ("Amazon Prime Video", re.compile(r"(?:Amazon\s*Prime\s*Video|Prime\s*Video|アマゾンプライムビデオ)")),
    ("U-NEXT", re.compile(r"(?:U[- ]?NEXT|ユーネクスト)")),
    ("Hulu", re.compile(r"(?:Hulu|フールー)")),
    ("Disney+", re.compile(r"(?:Disney\+|ディズニープラス)")),
    ("ABEMA", re.compile(r"(?:ABEMA|アベマ)")),
    ("Lemino", re.compile(r"Lemino")),
    ("FOD", re.compile(r"(?:FOD|FODプレミアム)")),
    ("TELASA", re.compile(r"TELASA")),
    ("dTV", re.compile(r"(?:dTV|dアニメストア)")),
    ("DMM TV", re.compile(r"DMM\s*TV")),
    ("WOWOW", re.compile(r"(?:WOWOW|WOWOWオンデマンド)")),
]

FEE_RE = re.compile(r"(有料|有償|課金|都度課金|レンタル|購入|視聴料|料金|価格|\d{2,5}\s*円)")

PRICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"((?:視聴料金|配信料金|料金|価格)\s*[:：]?\s*[^\n。]{1,60})"),
    re.compile(r"((?:レンタル|購入)\s*\d{2,5}\s*円(?:（税込）)?)"),
    re.compile(r"((?:\d{2,5}\s*円(?:（税込）)?\s*(?:で)?\s*(?:レンタル|購入)))"),
    re.compile(r"((?:有料配信|都度課金|有料|見放題(?:対象)?))"),
]

BUSINESS_HOURS_RE = re.compile(
    r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*から[^\n。]{0,40}配信"
)

PERFORMERS_RE = re.compile(r"演じたのは[『「]?([^」』、,\n。]{2,30})[』」]?(?:。|で|が)")


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _is_blank_str(v: object) -> bool:
    return not isinstance(v, str) or not v.strip()


def _is_missing_field(event: dict, field_name: str) -> bool:
    v = event.get(field_name)
    if field_name in {"location_name", "business_hours", "price_info"}:
        return _is_blank_str(v)
    if field_name == "is_paid":
        return v is None
    if field_name in {"event_form", "performers"}:
        return not isinstance(v, list) or len(v) == 0
    return v is None


def _extract_platform(text: str) -> str | None:
    for label, rx in PLATFORM_PATTERNS:
        if rx.search(text):
            return label
    if "配信" in text:
        return "オンライン配信"
    return None


def _extract_price_info(text: str) -> str | None:
    cands: list[str] = []
    for rx in PRICE_PATTERNS:
        for m in rx.finditer(text):
            phrase = re.sub(r"\s+", " ", m.group(1)).strip(" ：:\u3000")
            if phrase:
                cands.append(phrase)
    if not cands:
        return None
    cands = sorted(set(cands), key=lambda x: (-len(x), x))
    return cands[0]


def _extract_business_hours(text: str) -> str | None:
    m = BUSINESS_HOURS_RE.search(text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        dt = datetime(y, mo, d, tzinfo=JST)
    except ValueError:
        return None
    return f"{dt.year}年{dt.month}月{dt.day}日から配信中"


def _extract_performers(text: str) -> list[str] | None:
    m = PERFORMERS_RE.search(text)
    if not m:
        return None
    name = m.group(1).strip()
    name = re.sub(r"(さん|氏|ちゃん|くん)$", "", name).strip()
    if not name:
        return None
    if len(name) < 2 or len(name) > 24:
        return None
    if re.search(r"\d|https?://|配信|作品|映画|ドラマ", name):
        return None
    if re.search(r"[、,・/&]|\s{2,}", name):
        return None
    return [name]


def _serialize_fc_value(v: object) -> str:
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return str(v)
    if v is None:
        return ""
    return str(v)


def _build_update_payload(event: dict) -> dict:
    raw = event.get("raw_description") or ""
    payload: dict = {}

    if _is_missing_field(event, "location_name"):
        platform = _extract_platform(raw)
        if platform:
            payload["location_name"] = platform

    if _is_missing_field(event, "price_info"):
        price_info = _extract_price_info(raw)
        if price_info:
            payload["price_info"] = price_info

    if _is_missing_field(event, "is_paid") and FEE_RE.search(raw):
        payload["is_paid"] = True

    if _is_missing_field(event, "business_hours"):
        bh = _extract_business_hours(raw)
        if bh:
            payload["business_hours"] = bh

    if _is_missing_field(event, "event_form"):
        payload["event_form"] = ["broadcast"]

    if _is_missing_field(event, "performers"):
        perf = _extract_performers(raw)
        if perf:
            payload["performers"] = perf

    return payload


def _missing_required_fields(event: dict) -> list[str]:
    required = ["location_name", "business_hours", "is_paid", "price_info", "event_form"]
    return [f for f in required if _is_missing_field(event, f)]


def _parse_ids(*, cli_ids: list[str], ids_file: str | None) -> set[str]:
    ids: set[str] = set()
    for value in cli_ids:
        v = value.strip()
        if v:
            ids.add(v)

    if ids_file:
        with open(ids_file, "r", encoding="utf-8") as f:
            raw = f.read()
        for token in re.split(r"[\s,]+", raw):
            token = token.strip()
            if token:
                ids.add(token)

    return ids


def run(*, apply: bool, days: int, limit: int, target_ids: set[str] | None = None) -> None:
    sb = _supabase_client()

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        sb.table("events")
        .select(
            "id,name_ja,raw_title,raw_description,updated_at,"
            "location_name,business_hours,is_paid,price_info,event_form,performers"
        )
        .eq("source_name", "google_news_rss")
        .eq("is_active", True)
        .gte("updated_at", since.isoformat())
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    if target_ids:
        row_ids = {str(r.get("id")) for r in rows if r.get("id")}
        missing_ids = sorted(target_ids - row_ids)
        rows = [r for r in rows if r.get("id") in target_ids]
        logger.info(
            "ID filter applied: requested=%d, matched_in_window=%d, missing_in_window=%d",
            len(target_ids),
            len(rows),
            len(missing_ids),
        )
        if missing_ids:
            logger.info("ID filter missing_ids(sorted)=%s", ",".join(missing_ids))

    scanned = len(rows)
    semantic_hits = 0
    candidates: list[dict] = []

    for e in rows:
        raw = e.get("raw_description") or ""
        has_platform = _extract_platform(raw) is not None
        has_fee = FEE_RE.search(raw) is not None
        if not (has_platform and has_fee):
            continue
        semantic_hits += 1

        missing = _missing_required_fields(e)
        if not missing:
            continue

        payload = _build_update_payload(e)
        candidates.append(
            {
                "id": e["id"],
                "title": e.get("name_ja") or e.get("raw_title") or "",
                "missing": missing,
                "payload": payload,
            }
        )

    logger.info("Scanned: %d", scanned)
    logger.info("Platform+fee semantic hits: %d", semantic_hits)
    logger.info("Candidates: %d", len(candidates))

    candidate_ids_sorted = sorted(c["id"] for c in candidates)
    logger.info("Candidate event_ids(sorted)=%s", ",".join(candidate_ids_sorted) if candidate_ids_sorted else "")
    for event_id in candidate_ids_sorted:
        logger.info("Candidate event_id=%s", event_id)

    auto_payload_items = sorted(
        ((c["id"], sorted(c["payload"].keys())) for c in candidates if c["payload"]),
        key=lambda x: x[0],
    )
    if not auto_payload_items:
        logger.info("Auto payload summary none")
    for event_id, field_names in auto_payload_items:
        logger.info(
            "Auto payload summary event_id=%s fields=%s",
            event_id,
            ",".join(field_names),
        )

    for c in candidates:
        logger.info(
            "Candidate %s | missing=%s | payload=%s | title=%s",
            c["id"][:8],
            ",".join(c["missing"]),
            json.dumps(c["payload"], ensure_ascii=False),
            c["title"][:60],
        )

    if not apply:
        with_payload = sum(1 for c in candidates if c["payload"])
        manual_review = len(candidates) - with_payload
        logger.info(
            "DRY-RUN summary: candidates=%d, auto_payload=%d, manual_review=%d",
            len(candidates),
            with_payload,
            manual_review,
        )
        return

    updated_events = 0
    fc_upserts = 0
    skipped_no_payload = 0
    updated_event_ids: list[str] = []

    for c in candidates:
        payload = c["payload"]
        if not payload:
            skipped_no_payload += 1
            continue

        sb.table("events").update(payload).eq("id", c["id"]).execute()
        updated_events += 1
        updated_event_ids.append(c["id"])

        for field_name, field_value in payload.items():
            sb.table("field_corrections").upsert(
                {
                    "event_id": c["id"],
                    "field_name": field_name,
                    "corrected_value": _serialize_fc_value(field_value),
                    "corrected_by": None,
                },
                on_conflict="event_id,field_name",
            ).execute()
            fc_upserts += 1

    logger.info(
        "APPLY summary: scanned=%d, candidates=%d, updated_events=%d, field_corrections_upserts=%d, remaining_manual_review=%d",
        scanned,
        len(candidates),
        updated_events,
        fc_upserts,
        skipped_no_payload,
    )
    logger.info("Applied event_ids(sorted)=%s", ",".join(sorted(updated_event_ids)) if updated_event_ids else "")
    for event_id in sorted(updated_event_ids):
        logger.info("Applied event_id=%s", event_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--limit", type=int, default=1500)
    parser.add_argument("--id", action="append", default=[], help="Target event_id (repeatable)")
    parser.add_argument("--ids-file", type=str, default=None, help="Path to file containing event_id list")
    args = parser.parse_args()

    run(
        apply=bool(args.apply),
        days=args.days,
        limit=args.limit,
        target_ids=_parse_ids(cli_ids=args.id, ids_file=args.ids_file),
    )
