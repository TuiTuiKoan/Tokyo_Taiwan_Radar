"""One-off backfill: populate organizer_zh / organizer_en for existing events.

Prerequisites:
  1. Migration 058 must be applied first (ALTER TABLE events ADD COLUMN organizer_zh/en).
  2. Run from the project root:
       source .venv/bin/activate
       python scraper/_oneoff_backfill_organizer_i18n.py

Three-stage pipeline:
  Stage A: _KNOWN_ORGANIZER_MAP → deterministic, FC-locked
  Stage B: Pure-kanji organizer → direct copy to organizer_zh (no FC lock)
  Stage C: Remaining kana organizers → GPT batch translate (marked AI翻譯, no FC lock)
"""
import os
import re
import sys
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client
from annotator import _lock_fields_via_corrections, _KNOWN_ORGANIZER_MAP

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_KANJI_RE = re.compile(r"^[\u4e00-\u9fff\s・（）()\-\d、]+$")


def main() -> None:
    sb = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    # --- Stage A: KNOWN_ORGANIZER_MAP ---
    known_patched = 0
    for org_ja, (org_zh, org_en) in _KNOWN_ORGANIZER_MAP.items():
        rows = (
            sb.table("events")
            .select("id")
            .eq("organizer", org_ja)
            .is_("organizer_zh", "null")
            .execute()
            .data
        )
        for e in rows:
            sb.table("events").update(
                {"organizer_zh": org_zh, "organizer_en": org_en}
            ).eq("id", e["id"]).execute()
            _lock_fields_via_corrections(
                sb, e["id"], {"organizer_zh": org_zh, "organizer_en": org_en}
            )
            known_patched += 1
    log.info("Stage A (KNOWN_ORGANIZER_MAP): patched %d events", known_patched)

    # --- Stage B: Pure-kanji organizer → zh direct copy ---
    rows = (
        sb.table("events")
        .select("id,organizer")
        .not_.is_("organizer", "null")
        .is_("organizer_zh", "null")
        .execute()
        .data
    )
    kanji_patched = 0
    for e in rows:
        org = e["organizer"]
        if _KANJI_RE.match(org):
            sb.table("events").update({"organizer_zh": org}).eq(
                "id", e["id"]
            ).execute()
            kanji_patched += 1
    log.info("Stage B (kanji direct-copy): patched %d events", kanji_patched)

    # --- Stage C: GPT batch translate remaining ---
    remaining = (
        sb.table("events")
        .select("id,organizer")
        .not_.is_("organizer", "null")
        .is_("organizer_zh", "null")
        .execute()
        .data
    )
    if not remaining:
        log.info("Stage C: no remaining events — skipped")
    else:
        from openai import OpenAI

        client = OpenAI()
        unique_orgs = list({e["organizer"] for e in remaining})
        log.info("Stage C: %d unique organizers need GPT translation", len(unique_orgs))

        prompt_lines = [f'{i}. "{org}"' for i, org in enumerate(unique_orgs)]
        prompt = (
            "Translate these Japanese organization names to Traditional Chinese and English.\n"
            "Return JSON object with key 'results' containing an array: "
            '[{"idx": 0, "zh": "...", "en": "..."}]\n'
            "Rules:\n"
            "- For well-known orgs (universities, museums, govt), use official names\n"
            "- For company names (株式会社etc), translate the entity type, keep brand name\n"
            "- All zh MUST be Traditional Chinese (繁體中文)\n\n"
            + "\n".join(prompt_lines)
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You translate Japanese organization names.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
            results = (
                raw
                if isinstance(raw, list)
                else next((v for v in raw.values() if isinstance(v, list)), [])
            )

            org_map: dict[str, tuple[str, str]] = {}
            for item in results:
                idx = item.get("idx")
                if idx is not None and idx < len(unique_orgs):
                    org_map[unique_orgs[idx]] = (
                        item.get("zh", ""),
                        item.get("en", ""),
                    )

            gpt_patched = 0
            for e in remaining:
                org = e["organizer"]
                if org in org_map:
                    zh, en = org_map[org]
                    upd: dict[str, str] = {}
                    if zh:
                        upd["organizer_zh"] = f"{zh}（AI翻譯）"
                    if en:
                        upd["organizer_en"] = f"{en} (AI translated)"
                    if upd:
                        sb.table("events").update(upd).eq("id", e["id"]).execute()
                        gpt_patched += 1
            log.info("Stage C (GPT): patched %d events", gpt_patched)
        except Exception as exc:
            log.error("Stage C GPT error: %s", exc)

    # --- Final count ---
    final = (
        sb.table("events")
        .select("id", count="exact")
        .not_.is_("organizer", "null")
        .is_("organizer_zh", "null")
        .eq("is_active", True)
        .execute()
    )
    log.info("Final: %d active events still missing organizer_zh", final.count)


if __name__ == "__main__":
    main()
