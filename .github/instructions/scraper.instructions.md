---
description: "Coding standards for scraper sources, event fields, validation, and publication policy"
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
· `art` · `lecture` · `taiwan_japan` · `business` · `academic` · `competition` · `report`

Do **not** invent new category strings. All values must exist in this list.

## Sub-events

When a single TCC page lists multiple independent programme items (e.g. different screening days), create one child `Event` per item and set `parent_event_id` to the parent's `source_id`.

## Default Fallback & Pricing Policies (預設收費政策 & 時間空白回退)

- **時間空白回退**: 當事件無 `business_hours` (場次/營業時間) 時，前端在 UI 上不應只顯示 `"—"`。
  - 若 `official_url` 或 `source_url` 存在，前端會顯示 `「請參照原始來源」` 並加上指向該 URL 的超連結。這由 [web/app/[locale]/events/[id]/page.tsx](../../web/app/%5Blocale%5D/events/%5Bid%5D/page.tsx) 中實作。
- **電影院類的預設有料 (Cinema Default Pricing Fallback)**:
  - 針對電影院類別（`event_form` 含有 `screening` 或 `screening_with_talk`，或 `category` 是 `movie`，或 `source_name` 符合電影院來源（如 `cinema`, `cinemart`, `cineswitch`, `eurospace`, `human_trust`, `bungeiza`, `cinemarine`, `morc`））：
    - 若 `is_paid` 為空，且**非**台灣文化中心（`source_name="taiwan_cultural_center"` 或 organizer 含有台灣文化中心）主辦，預設為 `is_paid = True`（有料）。
    - 若 `is_paid` 為 `True` 且 `price_info` 為空白，預設為 `price_info = "有料"`，避免前台因沒有票價顯示留空或破圖。

## Publication Policy Invariant (Phase 3)

- 純出版紀錄只能由 exact invariant 判定：`event_form` 正規化後必須嚴格等於 `['publication']`。
- 純出版紀錄是 metadata-only：不得用 `books_media` 類別、`hanmoto` 來源名、或標題前綴取代判定。
- 純出版七欄保持 intentional null，並以 `field_corrections` empty sentinel 鎖定：`location_address`、`location_address_zh`、`location_address_en`、`business_hours`、`business_hours_zh`、`business_hours_en`、`location_prefectures`。
- 保留真實 DB 價格（`is_paid`、`price_info`、`price_amount`）；pure publication 價格只在 UI／JSON-LD 隱藏，不得納入 NULL／清除政策。`location_name` 與 `location_url` 也不屬於上述七欄。
- `publisher/organizer` 對純出版仍是必填語意，不可因 pure 判定而跳過 missing organizer QA。
- mixed records（例如 `['publication', 'lecture']`）必須保留 physical event 行為，不得套用 pure skip。
- 任何 scraper/backfill 若寫入 `event_form=['publication']`，必須同步 DB writer whitelist（`_VALID_EVENT_FORMS`）與對應測試。

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
