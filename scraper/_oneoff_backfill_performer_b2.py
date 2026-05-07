"""
Phase B-2: GPT performer backfill for events with lecture/performance forms.

Idempotent — skips events that already have performer set.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

LECTURE_FORMS = {"lecture", "performance", "screening_with_talk", "workshop", "conference"}

SYSTEM = (
    "あなたは日本語イベント情報から主な登壇者・出演者名を1人だけ抽出するアシスタントです。\n"
    "ルール：\n"
    "1. 名前はイベント説明文中に実際に登場する人物のみ。推測・補完禁止。\n"
    "2. 複数名いる場合は最初に言及された1名のみ返す。\n"
    "3. 演奏者・講演者・映画監督（登壇する場合のみ）・ゲストが対象。映画のみの上映会（トークなし）はnull。\n"
    "4. 肩書き・敬称を名前に含めない。\n"
    '5. 結果はJSON: {"performer": "名前"} または {"performer": null}\n'
)


def _lock_field(event_id: str, field_name: str, value: str | None) -> None:
    sb.table("field_corrections").upsert(
        {
            "event_id": event_id,
            "field_name": field_name,
            "corrected_value": str(value) if value is not None else "",
            "corrected_by": None,
        },
        on_conflict="event_id,field_name",
    ).execute()


def main() -> None:
    rows = (
        sb.table("events")
        .select("id,source_name,raw_title,event_form,performer,raw_description")
        .eq("is_active", True)
        .execute()
        .data
    )

    candidates = [
        e for e in rows
        if not e.get("performer")
        and bool(set(e.get("event_form") or []) & LECTURE_FORMS)
        and len(e.get("raw_description") or "") >= 200
    ]

    logger.info("Phase B-2: %d candidates", len(candidates))
    updated = 0
    skipped = 0

    for e in candidates:
        eid = e["id"]
        title = e.get("raw_title", "")
        desc = (e.get("raw_description") or "")[:1500]

        try:
            resp = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"タイトル: {title}\n\n{desc}"},
                ],
                temperature=0,
                max_tokens=80,
                response_format={"type": "json_object"},
            )
            performer = json.loads(resp.choices[0].message.content).get("performer")
        except Exception as ex:
            logger.warning("GPT error %s: %s", eid[:8], ex)
            skipped += 1
            continue

        if not performer:
            logger.info("  null  %s | %s", eid[:8], title[:45])
            skipped += 1
            continue

        # Sanity: reject if suspiciously long or contains digits/dates
        if len(performer) > 20 or re.search(r"\d", performer):
            logger.warning("  SANITY FAIL %s → %r", eid[:8], performer)
            skipped += 1
            continue

        sb.table("events").update({"performer": performer}).eq("id", eid).execute()
        _lock_field(eid, "performer", performer)
        logger.info("  ok   %s → %r | %s", eid[:8], performer, title[:45])
        updated += 1

    logger.info("Phase B-2 done: %d updated, %d skipped/null", updated, skipped)

    # Final fill rate
    total = sb.table("events").select("id", count="exact").eq("is_active", True).execute().count
    filled = (
        sb.table("events")
        .select("id", count="exact")
        .eq("is_active", True)
        .not_.is_("performer", "null")
        .execute()
        .count
    )
    logger.info("performer fill rate: %d/%d = %.1f%%", filled, total, filled / total * 100)


if __name__ == "__main__":
    main()
