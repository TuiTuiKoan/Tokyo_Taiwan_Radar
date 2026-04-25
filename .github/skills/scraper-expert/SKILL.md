---
name: scraper-expert
description: BaseScraper contract, field rules, and Peatix-specific conventions for the Scraper Expert agent
applyTo: .github/agents/scraper-expert.agent.md
---

# Scraper Expert Skills

Read this at the start of every session before writing any scraper.

## BaseScraper Contract
- Every scraper must extend `BaseScraper` and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — derive from URL slug or platform ID, never from title or list position.
- Always set `start_date` explicitly. Never fall back silently to the page's publish/update date.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date is found in the page body.

## Peatix-specific
- Blocked organizer patterns live in `BLOCKED_ORGANIZER_PATTERNS` in `peatix.py` — always check before adding new title-based blocks.
- 台東区 false positive: `台東` in `TAIWAN_KEYWORDS` can match the Tokyo ward 台東区. Use `_TAIWAN_KW_NO_TAITO` guard list.

## DeepL Tracking
- Add `self._deepl_chars_used: int = 0` to `BaseScraper.__init__`.
- Increment `self._deepl_chars_used += len(text)` at every DeepL API call.
- `main.py` reads `getattr(scraper, "_deepl_chars_used", 0)` when writing to `scraper_runs`.

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.

## After a Scraper Bug
1. Append an entry to `.github/skills/scraper-expert/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
