---
applyTo: "scraper/**"
---

# Scraper — Coding Instructions

## Architecture

All scrapers live in `scraper/sources/` and extend `BaseScraper` from `scraper/sources/base.py`.
Register every new scraper in `scraper/main.py` → `SCRAPERS = [...]`.

## Event dataclass fields (base.py)

| Field | Notes |
|-------|-------|
| `source_name` | snake_case, unique per source |
| `source_id` | stable across runs — primary dedup key for upsert |
| `source_url` | canonical URL of the event page |
| `original_language` | `"ja"` \| `"zh"` \| `"en"` |
| `raw_title` | original scraped text — **never overwrite** |
| `raw_description` | original scraped text — **never overwrite** |
| `start_date` / `end_date` | Python `datetime`; same value when single-day |
| `category` | `list[str]` — values from canonical list only |
| `parent_event_id` | set on child/sub-events; leave `None` otherwise |

## Date extraction rules

- Always prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when you have a date that may not appear in the description body — this ensures the AI annotator always sees the date.
- TCC uses a 4-tier extraction order: body labels (`日時:` / `会期:`) → prose date (`MM月DD日(曜)`) → title slash (`M/DD(曜)`) → publish date fallback.
- `_parse_date()` must strip parenthetical day-of-week markers `（月）` / `(土・祝)` before `strptime`.
- For end dates with only a day number (e.g. `〜5日`), inject the year and month from `start_date`.
- Prose date year inference: accept dates up to 180 days before publish date (covers レポート/recap articles).

## Report / recap detection

When `raw_title` contains `レポート|レポ|報告|記録|アーカイブ|recap` (case-insensitive), auto-add `"report"` to `category`.

## Category values (canonical)

`movie` · `performing_arts` · `senses` · `retail` · `nature` · `tech`
· `tourism` · `lifestyle_food` · `books_media` · `gender` · `geopolitics`
· `art` · `lecture` · `report`

Do **not** invent new category strings. All values must exist in this list.

## Sub-events

When a single TCC page lists multiple independent programme items (e.g. different screening days), create one child `Event` per item and set `parent_event_id` to the parent's `source_id`.

## selection_reason format

Always a JSON string: `'{"ja":"…","zh":"…","en":"…"}'`

## Testing

```bash
# Dry run (no DB writes, JSON printed to stdout):
cd scraper && python main.py --dry-run --source taiwan_cultural_center
cd scraper && python main.py --dry-run --source peatix

# Annotate all pending events:
cd scraper && python annotator.py --all
```

## Environment

Secrets in `scraper/.env`:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`
- `DEEPL_API_KEY`

## Adding a new source

1. Create `scraper/sources/<source_name>.py`, extend `BaseScraper`, implement `scrape() → list[Event]`
2. Set `SOURCE_NAME = "<source_name>"` as a class attribute
3. Add to `SCRAPERS` list in `scraper/main.py`
4. Test with `--dry-run --source <source_name>`
5. Verify `start_date` is populated (not falling back to publish date)
