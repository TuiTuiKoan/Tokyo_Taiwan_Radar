"""
Weekly note.com creator discovery for Tokyo Taiwan Radar.

Searches for note.com creators that post Taiwan-related cultural events or
community announcements in Japan. Discovered accounts are stored in
research_sources (status='candidate') for human review in the admin UI.

After an admin marks an account as 'implemented' at /admin/sources,
note_creators.py will automatically include it on the next scraper run.

Search strategy:
  - 3 thematic search queries (community events / culture / Taiwan-Japan)
  - gpt-4o-search-preview performs real web search
  - Playwright verifies each returned note.com creator RSS feed exists
  - Dedup against existing research_sources rows

Usage:
    python discovery_accounts.py                # run weekly discovery
    python discovery_accounts.py --dry-run      # run without saving to DB or LINE
"""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Search configuration
# ---------------------------------------------------------------------------

CREATOR_SCHEMA = """{
  "creators": [
    {
      "name": "Creator display name",
      "note_creator_id": "the slug from note.com URL (e.g. kuroshio2026)",
      "event_focus": "What kind of Taiwan content they post (1 phrase)",
      "reason": "Why this creator is a good source for Taiwan events in Japan (1-2 sentences)"
    }
  ]
}"""

# Three angles to maximise discovery coverage
SEARCH_TASKS = [
    {
        "id": "community_events",
        "label": "🗓️ 台日交流・コミュニティ活動",
        "query": "site:note.com 台湾 日台交流 イベント 告知 2026",
        "system_prompt": (
            "You are a research analyst finding note.com creators who regularly announce "
            "Taiwan-Japan community events in Japan (meetups, exchange parties, study groups). "
            "Search note.com for accounts that post event announcements about Taiwan-related "
            "gatherings or community events in Japanese cities. "
            "Return ONLY note.com creator account slugs (not individual article URLs). "
            "Do NOT return kuroshio2026 or nichitaikouryu — they are already registered."
        ),
    },
    {
        "id": "culture_arts",
        "label": "🎭 台湾文化・アート",
        "query": "site:note.com 台湾 文化 アート 展示 上映 日本 2026",
        "system_prompt": (
            "You are a research analyst finding note.com creators who post about Taiwan cultural "
            "events in Japan — art exhibitions, film screenings, performances, cultural festivals. "
            "Search note.com for accounts that regularly report on Taiwan cultural happenings in Japan. "
            "Return ONLY note.com creator account slugs (not individual article URLs). "
            "Do NOT return kuroshio2026 or nichitaikouryu — they are already registered."
        ),
    },
    {
        "id": "food_lifestyle",
        "label": "🍜 台湾グルメ・ライフスタイル",
        "query": "site:note.com 台湾 フェス グルメ 料理 イベント 東京 大阪 2026",
        "system_prompt": (
            "You are a research analyst finding note.com creators who announce Taiwan food festivals, "
            "gourmet events, or lifestyle events in Japan. "
            "Search note.com for accounts that post about Taiwan food or lifestyle events in Japanese cities. "
            "Return ONLY note.com creator account slugs (not individual article URLs). "
            "Do NOT return kuroshio2026 or nichitaikouryu — they are already registered."
        ),
    },
]

# Already-registered static creators — never re-insert
STATIC_CREATOR_IDS = frozenset(["kuroshio2026", "nichitaikouryu"])

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredCreator:
    name: str
    creator_id: str
    url: str
    event_focus: str
    reason: str
    url_verified: bool = False
    is_new: bool = True  # False if already in research_sources


@dataclass
class DiscoveryResult:
    task_id: str
    creators: list[DiscoveredCreator] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# URL verification
# ---------------------------------------------------------------------------

def _verify_note_creator(creator_id: str) -> bool:
    """Verify a note.com creator exists by checking their RSS feed (no Playwright needed)."""
    import requests as _req
    rss_url = f"https://note.com/{creator_id}/rss"
    try:
        resp = _req.get(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0)"},
            timeout=12,
            allow_redirects=True,
        )
        # RSS returns 200 with XML content for valid creators
        if resp.status_code == 200 and "<rss" in resp.text[:500]:
            logger.debug("Verified note.com creator: %s", creator_id)
            return True
        logger.debug(
            "note.com/%s RSS returned %d — skipping", creator_id, resp.status_code
        )
        return False
    except Exception as exc:
        logger.debug("RSS check failed for %s: %s", creator_id, exc)
        return False


# ---------------------------------------------------------------------------
# Creator ID extraction
# ---------------------------------------------------------------------------

def _extract_creator_id(raw: str) -> str | None:
    """
    Extract a valid note.com creator slug from GPT output.

    Handles:
      - full URL: https://note.com/kuroshio2026 or https://note.com/kuroshio2026/
      - bare slug: kuroshio2026
    Rejects article URLs and template placeholders.
    """
    raw = raw.strip()

    # Full URL pattern — extract slug
    m = re.match(r"https?://note\.com/([A-Za-z0-9_]{2,}?)/?$", raw)
    if m:
        return m.group(1)

    # Bare slug pattern — alphanumeric + underscore only
    m2 = re.match(r"^[A-Za-z0-9_]{2,32}$", raw)
    if m2:
        return raw

    return None


# ---------------------------------------------------------------------------
# GPT search
# ---------------------------------------------------------------------------

def _run_search_task(task: dict, client: OpenAI, known_ids: set[str]) -> DiscoveryResult:
    """Run one GPT search task and return discovered creators."""
    today = datetime.now(JST).strftime("%Y-%m-%d")

    skip_ids = STATIC_CREATOR_IDS | known_ids
    skip_hint = (
        f"\nDo NOT suggest these already-known creators: {', '.join(sorted(skip_ids)[:20])}\n"
        if skip_ids
        else ""
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-search-preview",
            messages=[
                {"role": "system", "content": task["system_prompt"]},
                {
                    "role": "user",
                    "content": (
                        f"Today is {today}.\n"
                        f"Search query: {task['query']}\n"
                        f"{skip_hint}"
                        f"Find up to 5 note.com creator accounts (return their creator ID slugs, "
                        f"not article URLs).\n\n"
                        f"Respond ONLY as valid JSON matching this schema:\n{CREATOR_SCHEMA}"
                    ),
                },
            ],
        )

        usage = response.usage
        text = (response.choices[0].message.content or "{}").strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        raw_creators = data.get("creators", [])

        creators: list[DiscoveredCreator] = []
        for item in raw_creators:
            raw_id = item.get("note_creator_id") or item.get("url") or ""
            creator_id = _extract_creator_id(raw_id)
            if not creator_id:
                logger.debug("Skipping unparseable creator ID: %r", raw_id)
                continue

            if creator_id in STATIC_CREATOR_IDS:
                logger.debug("Skipping static creator: %s", creator_id)
                continue

            creator = DiscoveredCreator(
                name=item.get("name") or creator_id,
                creator_id=creator_id,
                url=f"https://note.com/{creator_id}",
                event_focus=item.get("event_focus") or "",
                reason=item.get("reason") or "",
                is_new=creator_id not in known_ids,
            )
            creators.append(creator)

        return DiscoveryResult(
            task_id=task["id"],
            creators=creators,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )

    except Exception as exc:
        logger.error("Search task [%s] failed: %s", task["id"], exc)
        return DiscoveryResult(task_id=task["id"], error=str(exc))


# ---------------------------------------------------------------------------
# Verification + dedup
# ---------------------------------------------------------------------------

def _verify_and_dedup(
    results: list[DiscoveryResult],
) -> tuple[list[DiscoveredCreator], dict[str, DiscoveredCreator]]:
    """
    Flatten all results, verify RSS feeds, and dedup by creator_id.

    Returns:
      (new_verified, all_verified_map)
      - new_verified: creators not yet in research_sources
      - all_verified_map: {creator_id: DiscoveredCreator} for all verified creators
    """
    seen_ids: set[str] = set()
    all_verified: dict[str, DiscoveredCreator] = {}
    new_verified: list[DiscoveredCreator] = []

    for result in results:
        for creator in result.creators:
            if creator.creator_id in seen_ids:
                continue
            seen_ids.add(creator.creator_id)

            creator.url_verified = _verify_note_creator(creator.creator_id)
            if not creator.url_verified:
                continue

            all_verified[creator.creator_id] = creator
            if creator.is_new:
                new_verified.append(creator)

    return new_verified, all_verified


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def _upsert_creators(sb, new_verified: list[DiscoveredCreator]) -> int:
    """Upsert verified new creators to research_sources. Returns count inserted."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for creator in new_verified:
        row = {
            "name": creator.name,
            "url": creator.url,
            "agent_category": "note_creator",
            "category": "taiwan_japan",
            "status": "candidate",
            "event_types": creator.event_focus or "台灣相關活動・コミュニティ告知",
            "scraping_feasibility": "easy",
            "frequency": "weekly",
            "reason": creator.reason,
            "url_verified": True,
            "source_profile": {
                "platform": "note.com",
                "creator_id": creator.creator_id,
                "categories": ["taiwan_japan"],
            },
            "first_seen_at": now,
            "last_seen_at": now,
        }

        try:
            sb.table("research_sources").upsert(row, on_conflict="url").execute()
            inserted += 1
            logger.info("Upserted note creator: %s (%s)", creator.creator_id, creator.name)
        except Exception as exc:
            logger.warning("Failed to upsert %s: %s", creator.creator_id, exc)

    return inserted


# ---------------------------------------------------------------------------
# LINE notification
# ---------------------------------------------------------------------------

def _build_line_message(
    new_verified: list[DiscoveredCreator],
    total_tokens_in: int,
    total_tokens_out: int,
    dry_run: bool,
) -> str:
    today = datetime.now(JST).strftime("%Y/%m/%d")
    prefix = "[DRY RUN] " if dry_run else ""
    lines = [
        f"{prefix}🔍 note.com 帳號發現 — {today}",
        f"新增候選創作者：{len(new_verified)} 件",
        f"(tokens: in={total_tokens_in:,} out={total_tokens_out:,})",
    ]

    if new_verified:
        lines.append("")
        for creator in new_verified[:10]:
            lines.append(f"• @{creator.creator_id} — {creator.name}")
            if creator.event_focus:
                lines.append(f"  {creator.event_focus}")

    lines.append("")
    lines.append("👉 /admin/sources で確認・status を implemented に変更するとスクレイパーに追加されます")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Load known creator IDs from DB (to avoid re-inserting)
    known_ids: set[str] = set()
    sb = None
    if not dry_run:
        try:
            from supabase import create_client
            sb = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )
            rows = (
                sb.table("research_sources")
                .select("url,source_profile")
                .eq("agent_category", "note_creator")
                .execute()
            )
            for row in rows.data or []:
                profile = row.get("source_profile") or {}
                cid = profile.get("creator_id") or ""
                if cid:
                    known_ids.add(cid)
                else:
                    # Fallback: extract from URL
                    from sources.note_creators import _extract_creator_from_url
                    cid = _extract_creator_from_url(row.get("url") or "")
                    if cid:
                        known_ids.add(cid)
            logger.info("Loaded %d known note.com creator IDs from DB", len(known_ids))
        except Exception as exc:
            logger.warning("Could not load known creators from DB: %s", exc)
    else:
        logger.info("[DRY RUN] Skipping DB load — all discovered creators treated as new")

    # Run all search tasks
    results: list[DiscoveryResult] = []
    for task in SEARCH_TASKS:
        logger.info("Running search task: %s", task["label"])
        result = _run_search_task(task, client, known_ids)
        results.append(result)
        found = len(result.creators)
        logger.info(
            "Task [%s]: %d creator(s) returned%s",
            task["id"],
            found,
            f" (error: {result.error})" if result.error else "",
        )

    # Verify + dedup
    logger.info("Verifying RSS feeds...")
    new_verified, all_verified = _verify_and_dedup(results)
    logger.info(
        "Verified: %d total, %d new", len(all_verified), len(new_verified)
    )

    # Compute token totals
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)

    # Upsert to DB
    if not dry_run and sb and new_verified:
        inserted = _upsert_creators(sb, new_verified)
        logger.info("Inserted %d new candidate creator(s) to research_sources", inserted)
    elif dry_run:
        logger.info("[DRY RUN] Would insert %d new creator(s):", len(new_verified))
        for c in new_verified:
            logger.info("  • @%s — %s (%s)", c.creator_id, c.name, c.event_focus)

    # LINE notification
    msg = _build_line_message(new_verified, total_in, total_out, dry_run)
    if not dry_run:
        from line_notify import send_line_message
        send_line_message(msg)
    else:
        print("\n--- LINE message preview ---")
        print(msg)
        print("--- end ---\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover Taiwan-related note.com creators")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving to DB or LINE")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
