"""Phase C-2: GPT organizer extraction for peatix events with null organizer."""
from __future__ import annotations
import json, logging, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = (
    "あなたは日本語イベント情報から主催者名を抽出するアシスタントです。\n"
    "ルール：\n"
    "1. 主催者名はテキスト中に実際に登場する団体・個人名のみ。推測・補完禁止。\n"
    "2. 「主催：」「主催者：」「企画：」「制作：」のラベル後の名称を優先。\n"
    "3. 見つからない場合はnull。\n"
    "4. 会場名・出演者名は含めない。\n"
    '5. 結果はJSON: {"organizer": "名前"} または {"organizer": null}\n'
)


def main() -> None:
    rows = (
        sb.table("events")
        .select("id,raw_title,raw_description,organizer")
        .eq("is_active", True)
        .eq("source_name", "peatix")
        .is_("organizer", "null")
        .execute()
        .data
    )
    logger.info("Phase C-2: %d candidates", len(rows))
    updated = 0
    skipped = 0

    for e in rows:
        eid = e["id"]
        title = e.get("raw_title", "")
        desc = (e.get("raw_description") or "")[:2000]

        try:
            resp = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"タイトル: {title}\n\n{desc}"},
                ],
                temperature=0,
                max_tokens=100,
                response_format={"type": "json_object"},
            )
            organizer = json.loads(resp.choices[0].message.content).get("organizer")
        except Exception as ex:
            logger.warning("GPT error %s: %s", eid[:8], ex)
            skipped += 1
            continue

        if not organizer:
            logger.info("  null  %s | %s", eid[:8], title[:50])
            skipped += 1
            continue

        # Sanity: reject if suspiciously long (> 40 chars)
        if len(organizer) > 40:
            logger.warning("  SANITY FAIL %s -> %r (too long)", eid[:8], organizer[:40])
            skipped += 1
            continue

        sb.table("events").update({"organizer": organizer}).eq("id", eid).execute()
        sb.table("field_corrections").upsert(
            {"event_id": eid, "field_name": "organizer", "corrected_value": organizer, "corrected_by": None},
            on_conflict="event_id,field_name",
        ).execute()
        logger.info("  ok   %s -> %r | %s", eid[:8], organizer, title[:50])
        updated += 1

    logger.info("Phase C-2 done: %d updated, %d skipped/null", updated, skipped)
    total = sb.table("events").select("id", count="exact").eq("is_active", True).execute().count
    filled = sb.table("events").select("id", count="exact").eq("is_active", True).not_.is_("organizer", "null").execute().count
    logger.info("organizer fill rate: %d/%d = %.1f%%", filled, total, filled / total * 100)


if __name__ == "__main__":
    main()
