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

## iwafu-specific
- **Global-tour false positive**: If description contains `台湾など世界各地` / `全国各地.*台湾` etc., the event is a nationwide/global tour where Taiwan is just one stop. Reject it — it is NOT a Taiwan-themed event. The `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py` implements this guard.
- **Title-level block**: Known IP series (e.g. `リアル脱出ゲーム×名探偵コナン`) must be blocked by `_BLOCKED_TITLE_PATTERNS` in `_scrape_detail` **before** the page load — this catches all tour stops as new source_ids appear. Add new entries here when a series is confirmed non-Taiwan-themed.
- **Permanent IP series block**: For series where ALL events are non-Taiwan-themed (e.g. `名探偵コナン`), add the IP name to `_BLOCKED_SERIES`. Checked on BOTH card title (pre-load, fast-reject) AND h1 title (post-load). Card titles from search results can be truncated, so the pre-load check alone is not sufficient.
- Taiwan relevance criterion: Taiwan must be the **theme or primary focus**, not just one venue on a multi-city tour.
- **After adding a scraper filter, always audit the DB**: run `ilike("raw_title", "%keyword%")` to find existing records that should also be deactivated. The filter only prevents future inserts.
- **Hard delete vs deactivation**: If an IP series is confirmed permanently non-Taiwan-themed, hard delete (`table.delete().eq("id", eid)`) rather than just deactivating. Deactivated events remain accessible via direct URL unless the event page also checks `is_active`.
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`. Set BOTH `location_name` and `location_address` to the captured value. Fall back to `card.prefecture` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.

## eiga_com-specific
- **Per-theater granularity**: One event per theater per movie. `source_id = eiga_com_{movie_id}_{theater_id}`. Each daily run upserts and updates `end_date` to the last date in the current week's schedule.
- **URL flow**: `/movie/{id}/theater/` → area links `/movie-area/{id}/{pref}/{area}/` → `div.movie-schedule[data-theater]` + `.more-schedule a.icon.arrow` → `/movie-theater/{id}/{pref}/{area}/{theater_id}/` (address).
- **`a.icon.arrow` is the all-schedule link**: The `.more-schedule` div has 3 links — copy (`/mail/`), print (`/print/`), all-schedule (bare `/{theater_id}/`). Always use `a.icon.arrow`; the first `a[href*='/movie-theater/']` is the `/mail/` link.
- **Address extraction**: Use `table.theater-table th:contains("住所") + td` on the theater page. Call `a_tag.decompose()` on all `<a>` children before `get_text()` to strip "映画館公式ページ". Never use page-wide address regex — JS code can contain `東京都` fragments.
- **Fallback event**: If no area links found, emit one movie-level event with `source_id = eiga_com_{movie_id}` and `location_name=None`.

## koryu-specific
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


## google_news_rss-specific
- Fetches 4 Google News RSS queries; Taiwan-filtered; `category: ["report"]` (annotator refines)
- `start_date` extracted from description text; fallback to pubDate — DO NOT set to null
- `source_id`: `gnews_{md5(url)[:12]}` — stable across runs; `url` is guid if real article URL, else `<link>` tag value
- Skip entries older than 60 days (based on pubDate)
- Google `<guid>` may contain real article URL; prefer it over `<link>` tag when it starts with `http` and does not contain `news.google.com`

## nhk_rss-specific
- Fetches NHK news category RSS feeds (cat4=international, cat7=culture/science); Taiwan-filtered; `category: ["report", "books_media"]`
- `start_date` extracted from description text; fallback to pubDate
- `source_id`: `nhk_{md5(url)[:12]}`
- Skip entries older than 90 days
- 0 events is a valid dry-run result when no Taiwan news appears in today's NHK feeds

## Cinema scraper pattern

Applies to: `cineswitch_ginza`, `uplink_cinema`, `human_trust_cinema`, and any future single-venue cinema scraper.

**Standard strategy:**
1. Fetch listing page → parse movie cards (title, URL, optional end date from "M/D まで" or similar label)
2. Fetch each detail page → extract **production country** (`制作国` / `国` field, or `（YEAR／COUNTRY／...）` span)
3. Taiwan filter: `country` contains `台湾` or `Taiwan` — do not rely solely on title keywords (金馬奨 winner may be non-TW)
4. `start_date = today` (currently showing); `end_date` from listing label when available
5. `source_id`: URL slug or numeric post ID — never a timestamp

**Country field extraction patterns by site:**

| Source | Location | Selector / Pattern |
|--------|----------|--------------------|
| cineswitch_ginza | Detail page `.movie_detail` table | `th:contains("制作国") + td` |
| uplink_cinema (joji) | Detail page `<span class="small">` | `（YEAR年／...／COUNTRY／...）` — split by `／` |
| human_trust_cinema | Detail page `.movie-info` table | `th:contains("製作国") + td` |

**Taiwan filter fallback:** If country extraction fails, check full `description` text for `台湾` / `台灣` / `Taiwan` as a secondary gate.

**`start_date` rule for currently-showing movies:** Use `datetime.now()` (today). Do NOT use the movie's release date (`劇場公開日`) as `start_date` unless the movie is not yet showing.

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.

## Mandatory Post-Change Checklist

**Every time a scraper is modified or a new scraper is added, you MUST complete ALL of the following before returning. No exceptions.**

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
| Other sources | No dedicated SKILL yet — add rule here instead |

### 4. dry-run validation — always run before finishing
```bash
cd scraper && python main.py --dry-run --source <source_name> 2>&1 | head -80
```
Confirm: `start_date` populated, no unhandled exceptions, events count is non-zero (or zero for an expected reason).
