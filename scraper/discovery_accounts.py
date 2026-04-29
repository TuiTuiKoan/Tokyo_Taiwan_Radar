"""
Daily account discovery for Tokyo Taiwan Radar.

Discovers Taiwan-related accounts on note.com (creators) and Peatix (organizer groups)
that regularly post events in Japan. Discovered accounts are stored in
research_sources (status='candidate') for human review in the admin UI.

After an admin marks an account as 'implemented' at /admin/sources:
  - note.com creators → note_creators.py picks them up automatically
  - Peatix organizers → peatix.py scrapes their group pages directly

Search strategy:
  4 tasks rotate daily via DISCOVERY_SLOT env var (0-3):
    Slot 0 (Mon): note.com — community events / Taiwan-Japan 交流
    Slot 1 (Tue): note.com — culture & arts
    Slot 2 (Wed): note.com — food & lifestyle
    Slot 3 (Thu): Peatix — Taiwan-focused organizer groups
  Slot derived from (ISO weekday - 1) % 4 when env var not set.

Usage:
    python discovery_accounts.py                # run today's slot
    python discovery_accounts.py --slot 3       # override to Peatix slot
    python discovery_accounts.py --dry-run      # run without saving to DB or LINE
    python discovery_accounts.py --dry-run --slot 0
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

# Current year — used in search queries so they don't need manual updates
_THIS_YEAR = datetime.now(JST).year

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

PEATIX_ORGANIZER_SCHEMA = """{
  "organizers": [
    {
      "name": "Organizer / group display name",
      "peatix_group_id": "the group ID or slug from peatix.com/group/{id}",
      "event_focus": "What kind of Taiwan events they organize (1 phrase)",
      "reason": "Why this organizer is a reliable source for Taiwan events in Japan (1-2 sentences)"
    }
  ]
}"""

# Slots 0-2: note.com  |  Slot 3: Peatix
NOTE_SEARCH_TASKS = [
    {
        "id": "community_events",
        "slot": 0,
        "label": "🗓️ 台日交流・コミュニティ活動",
        "platform": "note",
        "query": f"site:note.com 台湾 日台交流 イベント 告知 {_THIS_YEAR}",
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
        "slot": 1,
        "label": "🎭 台湾文化・アート",
        "platform": "note",
        "query": f"site:note.com 台湾 文化 アート 展示 上映 日本 {_THIS_YEAR}",
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
        "slot": 2,
        "label": "🍜 台湾グルメ・ライフスタイル",
        "platform": "note",
        "query": f"site:note.com 台湾 フェス グルメ 料理 イベント 東京 大阪 {_THIS_YEAR}",
        "system_prompt": (
            "You are a research analyst finding note.com creators who announce Taiwan food festivals, "
            "gourmet events, or lifestyle events in Japan. "
            "Search note.com for accounts that post about Taiwan food or lifestyle events in Japanese cities. "
            "Return ONLY note.com creator account slugs (not individual article URLs). "
            "Do NOT return kuroshio2026 or nichitaikouryu — they are already registered."
        ),
    },
]

PEATIX_TASK = {
    "id": "peatix_organizers",
    "slot": 3,
    "label": "🎫 Peatix 台湾活動主催者",
    "platform": "peatix",
    "query": f"site:peatix.com 台湾 イベント 主催 グループ {_THIS_YEAR}",
    "system_prompt": (
        "You are a research analyst finding Peatix organizer groups that regularly host "
        "Taiwan-related cultural events in Japan (festivals, film screenings, exchange events, "
        "concerts, art exhibitions, food events). "
        "Search peatix.com for groups or organizers whose event pages focus on Taiwan content. "
        "Return ONLY Peatix group IDs or slugs from URLs like peatix.com/group/{id}. "
        "Do NOT return individual event URLs. "
        "Prioritize organizers with 3+ Taiwan events in their history."
    ),
}

# Already-registered static note.com creators — never re-insert
STATIC_CREATOR_IDS = frozenset(["kuroshio2026", "nichitaikouryu"])

SLOT_COUNT = 4  # 3 note slots + 1 peatix slot


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
    platform: str = "note"  # "note" or "peatix"
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
    """Verify a note.com creator exists by checking their RSS feed."""
    import requests as _req
    rss_url = f"https://note.com/{creator_id}/rss"
    try:
        resp = _req.get(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0)"},
            timeout=12,
            allow_redirects=True,
        )
        if resp.status_code == 200 and "<rss" in resp.text[:500]:
            logger.debug("Verified note.com creator: %s", creator_id)
            return True
        logger.debug("note.com/%s RSS returned %d — skipping", creator_id, resp.status_code)
        return False
    except Exception as exc:
        logger.debug("RSS check failed for %s: %s", creator_id, exc)
        return False


def _verify_peatix_group(group_id: str) -> bool:
    """Verify a Peatix group page exists and is reachable."""
    import requests as _req
    group_url = f"https://peatix.com/group/{group_id}/events"
    try:
        resp = _req.get(
            group_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0)"},
            timeout=12,
            allow_redirects=True,
        )
        if resp.status_code == 200 and "peatix" in resp.text[:2000].lower():
            logger.debug("Verified Peatix group: %s", group_id)
            return True
        logger.debug("Peatix group %s returned %d — skipping", group_id, resp.status_code)
        return False
    except Exception as exc:
        logger.debug("Peatix group check failed for %s: %s", group_id, exc)
        return False


# ---------------------------------------------------------------------------
# ID extraction helpers
# ---------------------------------------------------------------------------

def _extract_creator_id(raw: str) -> str | None:
    """Extract a valid note.com creator slug from GPT output."""
    raw = raw.strip()
    m = re.match(r"https?://note\.com/([A-Za-z0-9_]{2,}?)/?$", raw)
    if m:
        return m.group(1)
    m2 = re.match(r"^[A-Za-z0-9_]{2,32}$", raw)
    if m2:
        return raw
    return None


def _extract_peatix_group_id(raw: str) -> str | None:
    """Extract a valid Peatix group ID/slug from GPT output."""
    raw = raw.strip()
    m = re.match(r"https?://peatix\.com/group/([A-Za-z0-9_-]{2,}?)(?:/.*)?$", raw)
    if m:
        return m.group(1)
    m2 = re.match(r"^[A-Za-z0-9_-]{2,60}$", raw)
    if m2 and not raw.startswith("http"):
        return raw
    return None


# ---------------------------------------------------------------------------
# GPT search tasks
# ---------------------------------------------------------------------------

def _run_note_task(task: dict, client: OpenAI, known_ids: set[str]) -> DiscoveryResult:
    """Run one note.com GPT search task."""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    skip_ids = STATIC_CREATOR_IDS | known_ids
    skip_hint = (
        f"\nDo NOT suggest these already-known creators: {', '.join(sorted(skip_ids)[:20])}\n"
        if skip_ids else ""
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
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        creators: list[DiscoveredCreator] = []
        for item in data.get("creators", []):
            raw_id = item.get("note_creator_id") or item.get("url") or ""
            creator_id = _extract_creator_id(raw_id)
            if not creator_id or creator_id in STATIC_CREATOR_IDS:
                continue
            creators.append(DiscoveredCreator(
                name=item.get("name") or creator_id,
                creator_id=creator_id,
                url=f"https://note.com/{creator_id}",
                event_focus=item.get("event_focus") or "",
                reason=item.get("reason") or "",
                platform="note",
                is_new=creator_id not in known_ids,
            ))
        return DiscoveryResult(
            task_id=task["id"],
            creators=creators,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
    except Exception as exc:
        logger.error("note task [%s] failed: %s", task["id"], exc)
        return DiscoveryResult(task_id=task["id"], error=str(exc))


def _run_peatix_task(task: dict, client: OpenAI, known_urls: set[str]) -> DiscoveryResult:
    """Run the Peatix organizer GPT search task."""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    skip_hint = (
        f"\nDo NOT suggest these already-known group IDs/URLs: {', '.join(sorted(known_urls)[:20])}\n"
        if known_urls else ""
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
                        f"Find up to 5 Peatix organizer groups (return their group ID or slug "
                        f"from peatix.com/group/{{id}}, not individual event URLs).\n\n"
                        f"Respond ONLY as valid JSON matching this schema:\n{PEATIX_ORGANIZER_SCHEMA}"
                    ),
                },
            ],
        )
        usage = response.usage
        text = (response.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        creators: list[DiscoveredCreator] = []
        for item in data.get("organizers", []):
            raw_id = item.get("peatix_group_id") or item.get("url") or ""
            group_id = _extract_peatix_group_id(raw_id)
            if not group_id:
                continue
            url = f"https://peatix.com/group/{group_id}"
            creators.append(DiscoveredCreator(
                name=item.get("name") or group_id,
                creator_id=group_id,
                url=url,
                event_focus=item.get("event_focus") or "",
                reason=item.get("reason") or "",
                platform="peatix",
                is_new=url not in known_urls,
            ))
        return DiscoveryResult(
            task_id=task["id"],
            creators=creators,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
    except Exception as exc:
        logger.error("Peatix task failed: %s", exc)
        return DiscoveryResult(task_id=task["id"], error=str(exc))


# ---------------------------------------------------------------------------
# Verification + dedup
# ---------------------------------------------------------------------------

def _verify_and_dedup(
    result: DiscoveryResult,
) -> tuple[list[DiscoveredCreator], list[DiscoveredCreator]]:
    """Verify all creators in a single result and return (new_verified, all_verified)."""
    seen_ids: set[str] = set()
    all_verified: list[DiscoveredCreator] = []
    new_verified: list[DiscoveredCreator] = []

    for creator in result.creators:
        if creator.creator_id in seen_ids:
            continue
        seen_ids.add(creator.creator_id)

        if creator.platform == "note":
            creator.url_verified = _verify_note_creator(creator.creator_id)
        else:
            creator.url_verified = _verify_peatix_group(creator.creator_id)

        if not creator.url_verified:
            continue

        all_verified.append(creator)
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
        if creator.platform == "note":
            agent_category = "note_creator"
            profile = {
                "platform": "note.com",
                "creator_id": creator.creator_id,
                "categories": ["taiwan_japan"],
            }
        else:
            agent_category = "peatix_organizer"
            profile = {
                "platform": "peatix",
                "group_id": creator.creator_id,
                "categories": ["taiwan_japan"],
            }

        row = {
            "name": creator.name,
            "url": creator.url,
            "agent_category": agent_category,
            "category": "taiwan_japan",
            "status": "candidate",
            "event_types": creator.event_focus or "台灣相關活動",
            "scraping_feasibility": "easy",
            "frequency": "weekly",
            "reason": creator.reason,
            "url_verified": True,
            "source_profile": profile,
            "first_seen_at": now,
            "last_seen_at": now,
        }

        try:
            sb.table("research_sources").upsert(row, on_conflict="url").execute()
            inserted += 1
            logger.info(
                "Upserted [%s] %s (%s)", creator.platform, creator.creator_id, creator.name
            )
        except Exception as exc:
            logger.warning("Failed to upsert %s: %s", creator.creator_id, exc)

    return inserted


# ---------------------------------------------------------------------------
# LINE notification
# ---------------------------------------------------------------------------

def _build_line_message(
    new_verified: list[DiscoveredCreator],
    slot: int,
    task_label: str,
    total_tokens_in: int,
    total_tokens_out: int,
    dry_run: bool,
) -> str:
    today = datetime.now(JST).strftime("%Y/%m/%d")
    prefix = "[DRY RUN] " if dry_run else ""
    lines = [
        f"{prefix}🔍 帳號發現 Slot {slot} — {today}",
        f"タスク: {task_label}",
        f"新規候補: {len(new_verified)} 件",
        f"(tokens: in={total_tokens_in:,} out={total_tokens_out:,})",
    ]

    if new_verified:
        lines.append("")
        for creator in new_verified[:10]:
            platform_icon = "📝" if creator.platform == "note" else "🎫"
            lines.append(f"{platform_icon} @{creator.creator_id} — {creator.name}")
            if creator.event_focus:
                lines.append(f"  {creator.event_focus}")

    lines.append("")
    lines.append("👉 /admin/sources で確認・status を implemented に変更するとスクレイパーに追加されます")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slot resolution
# ---------------------------------------------------------------------------

def _resolve_slot(slot_arg: str | None) -> int:
    """Resolve which slot to run.

    Priority:
      1. --slot CLI argument
      2. DISCOVERY_SLOT environment variable
      3. (ISO weekday - 1) % SLOT_COUNT  (Mon=0 … Thu=3, Fri-Sun repeat 0-2)
    """
    if slot_arg is not None:
        return int(slot_arg) % SLOT_COUNT
    env_slot = os.environ.get("DISCOVERY_SLOT", "").strip()
    if env_slot.isdigit():
        return int(env_slot) % SLOT_COUNT
    # Derive from weekday: Mon=1→0, Tue=2→1, Wed=3→2, Thu=4→3, Fri=5→0, ...
    weekday = datetime.now(JST).isoweekday()  # 1=Mon … 7=Sun
    return (weekday - 1) % SLOT_COUNT


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False, slot_arg: str | None = None) -> None:
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

    slot = _resolve_slot(slot_arg)

    # Select today's task
    if slot == 3:
        task = PEATIX_TASK
    else:
        task = NOTE_SEARCH_TASKS[slot]

    logger.info("Slot %d — running task: %s", slot, task["label"])

    # Load known IDs/URLs from DB to avoid re-inserting
    known_note_ids: set[str] = set()
    known_peatix_urls: set[str] = set()
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
                .select("url,agent_category,source_profile")
                .in_("agent_category", ["note_creator", "peatix_organizer"])
                .execute()
            )
            for row in rows.data or []:
                ac = row.get("agent_category") or ""
                profile = row.get("source_profile") or {}
                if ac == "note_creator":
                    cid = profile.get("creator_id") or ""
                    if not cid:
                        from sources.note_creators import _extract_creator_from_url
                        cid = _extract_creator_from_url(row.get("url") or "") or ""
                    if cid:
                        known_note_ids.add(cid)
                elif ac == "peatix_organizer":
                    known_peatix_urls.add(row.get("url") or "")
            logger.info(
                "Loaded %d known note IDs, %d known peatix URLs from DB",
                len(known_note_ids), len(known_peatix_urls),
            )
        except Exception as exc:
            logger.warning("Could not load known accounts from DB: %s", exc)
    else:
        logger.info("[DRY RUN] Skipping DB load — all discovered accounts treated as new")

    # Run the task
    if task["platform"] == "peatix":
        result = _run_peatix_task(task, client, known_peatix_urls)
    else:
        result = _run_note_task(task, client, known_note_ids)

    logger.info(
        "Task [%s]: %d account(s) returned%s",
        task["id"], len(result.creators),
        f" (error: {result.error})" if result.error else "",
    )

    # Verify + dedup
    logger.info("Verifying accounts...")
    new_verified, all_verified = _verify_and_dedup(result)
    logger.info("Verified: %d total, %d new", len(all_verified), len(new_verified))

    # Upsert to DB
    if not dry_run and sb and new_verified:
        inserted = _upsert_creators(sb, new_verified)
        logger.info("Inserted %d new candidate account(s) to research_sources", inserted)
    elif dry_run:
        logger.info("[DRY RUN] Would insert %d new account(s):", len(new_verified))
        for c in new_verified:
            icon = "📝" if c.platform == "note" else "🎫"
            logger.info("  %s @%s — %s (%s)", icon, c.creator_id, c.name, c.event_focus)

    # LINE notification
    msg = _build_line_message(
        new_verified, slot, task["label"],
        result.tokens_in, result.tokens_out, dry_run,
    )
    if not dry_run:
        from line_notify import send_line_message
        send_line_message(msg)
    else:
        print("\n--- LINE message preview ---")
        print(msg)
        print("--- end ---\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Daily account discovery for Tokyo Taiwan Radar"
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without DB writes or LINE")
    parser.add_argument("--slot", type=str, default=None, help="Override slot (0-3)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, slot_arg=args.slot)
