---
name: scraper-expert
description: BaseScraper contract, field rules, and Peatix-specific conventions for the Scraper Expert agent
applyTo: .github/agents/scraper-expert.agent.md
---

# Scraper Expert Skills

Read this at the start of every session before writing any scraper.

## Geographic Scope
- **Scope is all of Japan（全日本）** — Tokyo, Osaka, Kyoto, Fukuoka, Nagoya, Sapporo, and all other regions are in scope.
- Do NOT exclude an event or source solely because it is outside Tokyo.
- Do NOT add Tokyo-specific geographic filters (e.g. `_is_tokyo_venue()`) unless the source itself is Tokyo-only by design.
- When a source covers a specific region (e.g. 福岡), note it in the SKILL.md but treat it as viable.

## BaseScraper Contract
- Every scraper must extend `BaseScraper` and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — derive from URL slug or platform ID, never from title or list position.
- Always set `start_date` explicitly. Never fall back silently to the page's publish/update date.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date is found in the page body.

## Peatix-specific
- Blocked organizer patterns live in `BLOCKED_ORGANIZER_PATTERNS` in `peatix.py` — always check before adding new title-based blocks.
- 台東区 false positive: `台東` in `TAIWAN_KEYWORDS` can match the Tokyo ward 台東区. Use `_TAIWAN_KW_NO_TAITO` guard list.

## iwafu-specific
- **Global-tour false positive**: If description contains `台湾など世界各地` / `全国各地.*台湾` etc., the event is a nationwide/global tour where Taiwan is just one stop. Reject it — it is NOT a Taiwan-themed event. The `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py` implements this guard.
- **Title-level block**: Known IP series (e.g. `リアル脱出ゲーム×名探偵コナン`) must be blocked by `_BLOCKED_TITLE_PATTERNS` in `_scrape_detail` **before** the page load — this catches all tour stops as new source_ids appear. Add new entries here when a series is confirmed non-Taiwan-themed.
- **Permanent IP series block**: For series where ALL events are non-Taiwan-themed (e.g. `名探偵コナン`), add the IP name to `_BLOCKED_SERIES`. Checked on BOTH card title (pre-load, fast-reject) AND h1 title (post-load). Card titles from search results can be truncated, so the pre-load check alone is not sufficient.
- Taiwan relevance criterion: Taiwan must be the **theme or primary focus**, not just one venue on a multi-city tour.
- **After adding a scraper filter, always audit the DB**: run `ilike("raw_title", "%keyword%")` to find existing records that should also be deactivated. The filter only prevents future inserts.
- **Hard delete vs deactivation**: If an IP series is confirmed permanently non-Taiwan-themed, hard delete (`table.delete().eq("id", eid)`) rather than just deactivating. Deactivated events remain accessible via direct URL unless the event page also checks `is_active`.
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`. Set BOTH `location_name` and `location_address` to the captured value. Fall back to `card.prefecture` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.

## koryu-specific
- **Taiwan-office filter (CRITICAL)**: koryu.or.jp manages both Japan and Taiwan offices. The DNN CMS breadcrumb in `main.inner_text()` reads `お知らせイベント・セミナー情報[OFFICE_TAG]` where `OFFICE_TAG` is e.g. `台北`, `台中`, `高雄`, `東京`. Use `_extract_office_tag(body_text)` (regex `イベント・セミナー情報\s*([\u4e00-\u9fa5]{1,6})`) and check against `_TAIWAN_OFFICE_TAGS = {"台北","台中","高雄","台南","桃園","新竹","基隆","嘉義"}`. Return `None` from `_scrape_detail` if matched — these are Taiwan-based events, not Japan events.
- **Dead filter anti-pattern**: `_is_tokyo_venue()` was historically defined but never called in `_scrape_detail`. This caused Taiwan-office events to slip in. After adding any geographic filter function, wire it up immediately and verify with a dry-run.
- **location_address fallback**: `_extract_location_address()` searches for `所在地/住所` sections. When absent (common for 後援-type posts), fall back to the venue name from `_extract_venue()`: `location_address = _extract_location_address(body_text) or (venue if venue else None)`.
- **404 on old koryu URLs**: When a koryu event page returns 404, `main_text` will be a redirect message with no venue section. `_extract_venue` returns `None`, so `location_address` is also `None`. This is acceptable — the event is stale.
- **Single-day end_date**: Always set `end_date = start_date` at the end of `_extract_event_fields`. Taiwan Kyokai events are single-day ceremonies/lectures.
- **Publish-date false positive**: The page body starts with the article publish date (`2026年4月20日`) before the actual event content. Do NOT rely solely on the generic `YYYY年MM月DD日` fallback — it will pick up the publish date if no structured `日時：` field exists.
- **DOW-qualified date extraction**: Dates like `5月16日（土）` (with day-of-week) are actual event dates. Extract these BEFORE the generic fallback, then infer the year from the nearest `20XX年` in the text.
- Priority order for date extraction: `日時：` field → `時間：` field (with date) → DOW-qualified `月\d+日（曜日）` → generic `YYYY年MM月DD日` fallback.

## DeepL Tracking
- Add `self._deepl_chars_used: int = 0` to `BaseScraper.__init__`.
- Increment `self._deepl_chars_used += len(text)` at every DeepL API call.
- `main.py` reads `getattr(scraper, "_deepl_chars_used", 0)` when writing to `scraper_runs`.

## Annotator output cleaning
- Empty strings from GPT (`""`) must be treated as `None` — use `_str()` helper that returns `None` for falsy/blank strings. Prevents empty `name_zh`/`name_en` from blocking the `||` fallback chain in `getEventName`.
- Location fields must be stripped of leading label separators — use `_loc()` helper that calls `.lstrip("：；:; \u3000")`. GPT often includes the `会場：` or `場所：` separator as the first character of `location_name`.
- Apply `_loc()` to both `location_name` and `location_address`.
- Events with existing `""` in name/description fields need manual DB reset (`null` + `annotation_status = 'pending'`) then re-run `annotator.py`. The `_str()` helper only prevents future empty strings.
- **Online event location**: When the annotator returns a location that is a URL, or contains `オンライン` / `online` / `zoom` / `teams` / `meet.google`, normalize all 6 location fields manually:
  ```python
  patch = {
      'location_name':       'オンライン',
      'location_name_zh':    '線上',
      'location_name_en':    'Online',
      'location_address':    None,   # never store a URL or meeting link as address
      'location_address_zh': None,
      'location_address_en': None,
  }
  sb.table('events').update(patch).eq('id', ev_id).execute()
  ```
  `location_address = None` for all online events — a meeting URL stored as address breaks map display and the address fallback chain.

## Admin form (web) — nullable fields
- `AdminEditClient.tsx` initializes form fields with `event.field ?? ""`, converting `null` → `""`. On save, this writes `""` to the DB — which silences the locale fallback chain in `getEventName`/`getEventDescription`.
- The `handleSave` payload uses a `nullify` helper: `const nullify = (v: string) => v.trim() || null`. All name/description fields must pass through `nullify` before the Supabase PATCH.
- `name_ja` falls back to `event.raw_title` as last resort: `form.name_ja.trim() || event.raw_title || null`.
- In `web/lib/types.ts`, `getEventName`/`getEventDescription` use `||` (not `??`) — `||` catches both `null` and `""` for the locale fallback chain.

## Event detail page (web) — inactive events
- `web/app/[locale]/events/[id]/page.tsx` must include `if (!event.is_active) notFound()` immediately after fetching the event. Without this, deactivated events remain accessible by direct URL.
- Deactivating an event in the DB is NOT sufficient to hide it from public access — the detail page must also guard against it.

## Localized location / address / hours (migration 010)
- `location_name`, `location_address`, and `business_hours` have `_zh` and `_en` variants in the DB (migration 010).
- Annotator GPT schema explicitly requests `location_name_zh`, `location_name_en`, `location_address_zh`, `location_address_en`, `business_hours_zh`, `business_hours_en`.
- `web/lib/types.ts` exposes `getEventLocationName(event, locale)`, `getEventLocationAddress(event, locale)`, `getEventBusinessHours(event, locale)` — all fall back to the Japanese original if the localized variant is null.
- Event detail page (`/events/[id]/page.tsx`) uses these helpers instead of raw field access.
- **Rule**: Any field that a non-Japanese visitor reads on the event page must have locale variants OR use a helper with Japanese fallback. Check the event detail page for raw `event.field` access when adding new DB columns.


## Location Backfill

When the DB contains events whose `location_address` is a bare prefecture name (`"東京"`, `"東京都"`, `"東　京"`, `"Tokyo"` etc.) rather than a real venue, use the backfill script to repair them:

```bash
# Preview — no DB writes
python scraper/backfill_locations.py --dry-run

# Apply
python scraper/backfill_locations.py
```

**Rules:**
- The script only updates `location_name` and `location_address` — it never touches `name_*`, `description_*`, translations, or any other field.
- After running, re-run `annotator.py` so the localized `location_name_zh/en` and `location_address_zh/en` variants are filled.
- If you add a new source that may store generic addresses, add its `SOURCE_NAME` to the `_SOURCES` list in `backfill_locations.py`.
- Generic address sentinel values are defined in `_GENERIC_ADDRESSES` — add new ones when discovered (e.g. `"大阪"` for future Osaka sources).

## kokuchpro-specific
- **Search URL scoped to 東京都** — `area-東京都` in the path reduces results from ~1100 nationwide to ~226 Tokyo-only. No additional geographic filtering needed in code.
- **ISO date from `.value-title[title]`** — card always carries ISO 8601 datetime with `+0900` offset. Parse with `datetime.fromisoformat()` and strip timezone. Do NOT parse the Japanese text fallback unless this attribute is absent.
- **hCard microformat** — detail page has `.fn.org` for venue name and `.adr` for full address. Use these instead of regex. If `.adr` is absent (online events), fall back to venue name.
- **Detail fetch cutoff** — only fetch detail pages for events within `DETAIL_CUTOFF_DAYS=60` past + future. Older events use card-level short description only.
- **`source_id` = URL slug** — either a platform-assigned MD5 hash or organizer-chosen short name. Both are stable across runs.

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.

## Mandatory Post-Change Checklist

**Every time a scraper is modified or a new scraper is added, you MUST complete ALL of the following before returning. No exceptions.**

### 0. NEW SCRAPERS ONLY — create source docs before `git commit`
> **This is the most frequently skipped step. Do it BEFORE committing.**

For any newly created `scraper/sources/<source_name>.py`:
1. Create `.github/skills/sources/<source_name>/SKILL.md` (platform profile, field mappings, date/address rules, troubleshooting)
2. Create `.github/skills/sources/<source_name>/history.md` (initial implementation decisions, any first-run surprises)
3. Add `<source_name>` row to the per-source table in Step 3 below
4. Include all three files in the **same `git commit`** as the scraper source file

Failure to do this means future agents have no platform knowledge and must re-discover rules from scratch.

### 1. history.md — always update on bug fix or unexpected behaviour
- File: `.github/skills/scraper-expert/history.md`
- Append at the TOP (newest first):
  ```
  ---
  ## YYYY-MM-DD — <short title>
  **Error:** <what went wrong>
  **Fix:** <what was changed>
  **Lesson:** <generalizable rule> → [Added to SKILL.md | Already in SKILL.md]
  ---
  ```
- Skip only if the change is purely additive with zero unexpected behaviour (e.g. adding a new source that worked perfectly on first try with no surprises).

### 2. SKILL.md — update if a new rule is discovered
- File: `.github/skills/scraper-expert/SKILL.md` (this file)
- If the lesson is source-specific: add a `## <source>-specific` subsection or extend the existing one.
- If the lesson is universal (applies to all scrapers): add it under `## BaseScraper Contract` or `## Registration`.
- Never duplicate a rule that already exists.

### 3. Per-source SKILL.md — update if a platform rule changed
| Modified source | Platform SKILL to update |
|-----------------|--------------------------|
| `peatix.py` | `.github/skills/peatix/SKILL.md` |
| `taiwan_cultural_center.py` | `.github/skills/taiwan_cultural_center/SKILL.md` |
| `connpass.py` or `doorkeeper.py` | `.github/skills/community-platforms/SKILL.md` |
| `iwafu.py` | `.github/skills/iwafu/SKILL.md` |
| `koryu.py` | `.github/skills/koryu/SKILL.md` |
| `taioan_dokyokai.py` | `.github/skills/taioan_dokyokai/SKILL.md` |
| `taiwan_kyokai.py` | `.github/skills/taiwan_kyokai/SKILL.md` |
| `ide_jetro.py` | `.github/skills/ide_jetro/SKILL.md` |
| `taiwan_festival_tokyo.py` | `.github/skills/taiwan_festival_tokyo/SKILL.md` |
| `arukikata.py` | `.github/skills/arukikata/SKILL.md` |
| `kokuchpro.py` | `.github/skills/sources/kokuchpro/SKILL.md` |

### 4. dry-run validation — always run before finishing
```bash
cd scraper && python main.py --dry-run --source <source_name> 2>&1 | head -80
```
Confirm: `start_date` populated, no unhandled exceptions, events count is non-zero (or zero for an expected reason).
