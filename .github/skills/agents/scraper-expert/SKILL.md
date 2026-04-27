---
name: scraper-expert
description: BaseScraper contract, field rules, documentation protocol, and per-source conventions for the Scraper Expert agent
applyTo: .github/agents/scraper-expert.agent.md
---

# Scraper Expert Skills

Read this at the start of every session before writing any scraper.

## Documentation Protocol (Phase 4 — mandatory)

After every new source or bug fix, create/update these files **before committing**:

### New source checklist

| File | Action |
|------|--------|
| `.github/skills/<source_name>/SKILL.md` | **Create** — platform profile, field mappings, Taiwan filter, date extraction, troubleshooting |
| `.github/skills/<source_name>/history.md` | **Create** — initial implementation decisions |
| `.github/skills/agents/scraper-expert/SKILL.md` | **Update** — add `## <source_name>-specific` section (3–5 key rules) |
| Supabase `research_sources` | **Update** status → `implemented` |

### Bug fix checklist

| File | Action |
|------|--------|
| `.github/skills/agents/scraper-expert/history.md` | **Prepend** new entry (date, error, fix, lesson) |
| `.github/skills/<source_name>/history.md` | **Prepend** new entry |
| `scraper-expert/SKILL.md` | **Add/update** rule if lesson is universal |
| Per-source `SKILL.md` | **Add/update** rule if lesson is source-specific |

### Per-source SKILL.md template

```markdown
---
name: <source_name>
description: Platform rules, <key_feature>, and troubleshooting for the <source_name> scraper
applyTo: scraper/sources/<source_name>.py
---

# <Source Display Name> Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | ... |
| API/Rendering | ... |
| Auth required | No |
| Rate limit | ... |
| Source name | `<source_name>` |
| Source ID format | `<source_name>_{stable_id}` |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | ... |
| `start_date` | ... |
| `location_name` | ... |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + ...` |

## Taiwan Relevance Filter

...

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| ... | ... | ... |

## oaff-specific

1. **WP REST API over HTML scraping**: Use `/wp-json/wp/v2/posts?categories=8&per_page=100` — returns all editions without needing to discover year-specific URLs.
2. **Three date formats**: 2024 uses `M/D(曜) HH:MM　venue`; 2025+ uses `M月D日（曜）HH:MM／venue`. Always infer year from slug prefix via `re.search(r"(\d{4})", slug)`.
3. **source_id = `oaff_{wp_post_id}`**: Use the WP integer post ID (not slug) for stable dedup.
4. **0 events is expected when festival not running**: OAFF runs in March and Aug–Sep. Returning 0 between seasons is correct.
5. **Venue delimiter varies**: Both `/`, `／`, and `　` (full-width space) appear as delimiters between time and venue name across editions.

## Pending Rules

<!-- Added automatically by confirm-report -->
```

### history.md entry format

```markdown
## YYYY-MM-DD — <source>: <short description>

**Error:** What went wrong.

**Root cause:** Why it happened.

**Fix:** What was changed.

**Lesson:** What to remember.
```

## BaseScraper Contract
- Every scraper must extend `BaseScraper` and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — derive from URL slug or platform ID, never from title or list position.
- Always set `start_date` explicitly. Never fall back silently to the page's publish/update date.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date is found in the page body.

## Geographic Scope — All of Japan（全日本）
- **NEVER add a Tokyo-only location filter** unless the source itself is physically Tokyo-only (e.g. a single venue).
- Events in Osaka, Kyoto, Fukuoka, Sapporo, Nagoya, Sendai, Hiroshima and all other prefectures are **in scope**.
- API scrapers that accept a `prefecture=` or region param must either omit it (nationwide) or iterate all prefectures.
- Connpass `prefecture=tokyo` was removed 2026-04-26 — do NOT re-add it.
- Doorkeeper has no location filter — keep it that way.
- The Taiwan relevance gate (`_TAIWAN_KEYWORDS`) is the only required filter; location is irrelevant to inclusion.

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

## ifi-specific
- **Low yield**: IFI has ~1–2 Taiwan events per year. 0 results on dry-run is expected.
- **Upcoming events only**: Scrape `/event/` (upcoming) only — do NOT paginate `/old-event/`. Past events are not re-ingested.
- **URL in venue**: `会場：` value often has a map URL on the next line. Always filter out lines starting with `http` before setting `location_name`/`location_address`.
- **Single-day events**: Always set `end_date = start_date`.
- **Title selector**: `h1.module_title-01` is the event title. `<h1>` at page top always reads `"イベント"` — do NOT use it.

## tokyocity_i-specific
- **Fixed venue**: All events are held at KITTE 地下1階, 東京都千代田区丸の内2-7-2. Hardcode `location_address = "東京都千代田区丸の内2-7-2 KITTE地下1階"` regardless of what `場所` row contains.
- **h1 is useless**: The `<h1>` always reads `"イベント"`. Use `h2.cap-lv1` for the actual event title.
- **Listing-page date typos**: WordPress editors sometimes enter wrong year in the date range (e.g., `2026/5/8～2025/5/10`). Always use `期間` from the detail-page table, not the listing-page date snippet.
- **0 results = normal**: Tokyo City i has ~2–5 Taiwan events per year. Dry-runs returning 0 are expected.
- **is_paid = False**: All Tokyo City i events are free admission — hardcode `False`, do not attempt to infer.

## tokyonow-specific
- **API keyword search broken**: `search=台湾` on the Tribe Events v1 API returns 0 — it does not index Japanese. Always use full-page scan + local `_TAIWAN_KEYWORDS` filter.
- **0 results = correct**: Tokyo Now typically has 0 Taiwan events at any given time. A dry-run returning 0 is expected behaviour, not a scraper error.
- **source_id stability**: Use `ev["id"]` (numeric WordPress post ID from the API response), NOT anything derived from the URL slug or title. The slug can change; the numeric ID is permanent.
- **Date format**: API returns `"YYYY-MM-DD HH:MM:SS"` without timezone. Parse with `datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)`. Do NOT use `fromisoformat()`.
- **台東 false positive**: `台東区` is a Tokyo ward. Do NOT add `台東` or `台東区` to `_TAIWAN_KEYWORDS`.

## tuat_global-specific
- **Filter on title only**: Taiwan appears as `（台湾）` in the researcher's affiliation within the title (e.g. `/ 国立陽明交通大学（台湾）`). Filter `_TAIWAN_KEYWORDS` on title only.
- **All info on listing page**: Each event's `<table>` already contains title, date, and venue — no need to fetch detail pages.
- **Date format uses full-width colon**: `"2026.4.15（14：00～15：30）"` — match `HH：MM` with `[：:]` to handle both full-width and ASCII colon.
- **LOOKBACK_DAYS = 60**: Events older than 60 days are skipped. Low yield (~1–3 Taiwan events/year) is normal.
- **Venue may have Zoom line**: Take first line of venue cell as `location_name`; join all non-http lines as `location_address`.

## jinf-specific
- **Correct page is `/meeting`**: `/event`, `/lecture` return 404. The upcoming events list is at `https://jinf.jp/meeting`.
- **`meetingbox` div not `<li>` or `<article>`**: Upcoming events are `<div class="meetingbox">` elements. Do NOT query for list items.
- **`【場　所】` has full-width space**: The label uses U+3000 between 場 and 所. Use both `場　所` and `場所` in fallback extraction.
- **`source_id` = form ID**: Use the numeric ID from `/meeting/form?id=NNNN` as the stable dedup key. Do NOT hash the title.
- **Filter on full box text**: Taiwan may appear only in speaker affiliations (`台湾元行政院副院長`), not in the title. Filter on full `box_text`, not just the title element.

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

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.

## Mandatory Post-Change Checklist

**Every time a scraper is modified or a new scraper is added, you MUST complete ALL of the following before returning. No exceptions.**

### 1. history.md — always update on bug fix or unexpected behaviour
- File: `.github/skills/agents/scraper-expert/history.md`
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
- File: `.github/skills/agents/scraper-expert/SKILL.md` (this file)
- If the lesson is source-specific: add a `## <source>-specific` subsection or extend the existing one.
- If the lesson is universal (applies to all scrapers): add it under `## BaseScraper Contract` or `## Registration`.
- Never duplicate a rule that already exists.

### 3. Per-source SKILL.md — update if a platform rule changed
| Modified source | Platform SKILL to update |
|-----------------|--------------------------|
| `peatix.py` | `.github/skills/sources/peatix/SKILL.md` |
| `taiwan_cultural_center.py` | `.github/skills/sources/taiwan_cultural_center/SKILL.md` |
| `connpass.py` or `doorkeeper.py` | `.github/skills/sources/community-platforms/SKILL.md` |
| `iwafu.py` | `.github/skills/sources/iwafu/SKILL.md` |
| `koryu.py` | `.github/skills/sources/koryu/SKILL.md` |
| `taioan_dokyokai.py` | `.github/skills/sources/taioan_dokyokai/SKILL.md` |
| `taiwan_kyokai.py` | `.github/skills/sources/taiwan_kyokai/SKILL.md` |
| `ide_jetro.py` | `.github/skills/sources/ide_jetro/SKILL.md` |
| `taiwan_festival_tokyo.py` | `.github/skills/sources/taiwan_festival_tokyo/SKILL.md` |
| `arukikata.py` | `.github/skills/sources/arukikata/SKILL.md` |
| `tuat_global.py` | `.github/skills/sources/tuat_global/SKILL.md` |
| `jinf.py` | `.github/skills/sources/jinf/SKILL.md` |

### 4. dry-run validation — always run before finishing
```bash
cd scraper && python main.py --dry-run --source <source_name> 2>&1 | head -80
```
Confirm: `start_date` populated, no unhandled exceptions, events count is non-zero (or zero for an expected reason).
