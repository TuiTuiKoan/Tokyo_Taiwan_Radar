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
- **Never restrict geographic scope**: The project covers all of Japan（全日本）. Regional keyword filters (e.g. `_TOKYO_KANTO_KEYWORDS`) must never be added to any scraper.
- **After fixing a filter bug**: Run `python main.py --source <name>` (non-dry-run) immediately after the fix. A dry-run confirms the fix works but does NOT write to DB — the data gap remains until the next CI cycle.

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


## cinema scrapers — official_url extraction
- Cinema detail pages often have an "オフィシャルサイトはこちら" or "公式サイト" anchor linking to the film's external promotional site. Extract this as `official_url`.
- Selector pattern: iterate `soup.find_all("a", href=True)`; skip hrefs that do not start with `http` and skip hrefs containing the cinema's own domain.
- Accept link texts: `オフィシャルサイト`, `公式サイト`, `official site`, `Official Site` (case-insensitive variants).
- When `official_url` is added to an existing scraper, **existing DB records are not automatically updated** — either set `force_rescrape=True` for affected events or run a targeted Supabase UPDATE. The scraper only writes `official_url` on upsert; stale rows keep `null` until they are re-upserted.

## Event detail page (web) — Google search fallback locale
- When building a Google search URL as fallback for missing `official_url`, always use `event.name_ja || event.raw_title || name` — **never the locale-specific `name` variable alone**.
- Reason: `name` resolves to the display locale (e.g. `zh` → Chinese title `大濛`); searching `大濛 公式サイト` misses the Japanese official site. Japanese titles consistently return correct results.
- Pattern: `` `https://www.google.com/search?q=${encodeURIComponent(((event as Event).name_ja || event.raw_title || name || "") + " 公式サイト")}` ``

## daimaru_matsuzakaya-specific
- **SPA with hidden JSON API**: Both daimaru.co.jp and matsuzakaya.co.jp appear as React/Vite SPAs, but all event data is served via `GET /spa_assets/events/{slug}.json`. Use `requests` only — no Playwright needed.
- **Discover API with Playwright response interception**: Run `page.on('response', ...)` filtering `content-type: application/json` to find new endpoints when brands update their SPA.
- **Store slug exceptions**: 大丸梅田店 uses slug `umedamise` (NOT `umeda`). Slugs are found in the JS bundle's React Router path definitions: `path:"/umedamise/*"`.
- **403 stores**: `daimaru/fukuoka` and `matsuzakaya/takatsuki` return 403 even via Playwright. Permanently excluded from `_STORES`.
- **source_id**: `daimaru_matsuzakaya_{slug}_{ev["id"]}` — JSON `id` (integer) is stable across daily runs.
- **Date format**: `eventStartDate` / `eventEndDate` = `"YYYYMMDDHHII"` string. Parse with `datetime.strptime(ds[:8], "%Y%m%d")`.
- **Referer header required**: `requests.get(url, headers={"Referer": page_url})` — without Referer some stores return 403.
- **Taiwan events are rare and unpredictable** (food fairs, not seasonal). 0-event dry-runs are expected.

## hankyu_umeda-specific
- **Static HTML, no Playwright**: requests + BeautifulSoup only. Page at `https://www.hankyu-dept.co.jp/honten/event/` returns full HTML.
- **Seasonal pattern**: Taiwan展（台湾ライフ等）is typically in **autumn (September–November)**. Returning 0 events during spring/summer is **correct** — do not treat it as a scraper bug.
- **source_id**: `hankyu_umeda_{slug}` where slug = last path segment of the detail URL (e.g. `taiwan_life`). SHA1 fallback `hankyu_umeda_{sha1(title+date_str)[:10]}` for events without a unique detail page.
- **Date format**: `◎M月D日（曜日）～D日（曜日）` (same-month) or cross-month variant. Three regexes: `_DATE_DIFF_MONTH`, `_DATE_SAME_MONTH`, `_DATE_SINGLE`. Year inferred from current date with Dec→Jan rollover.

## google_news_rss-specific
- Fetches 4 Google News RSS queries; Taiwan-filtered; `category: ["report"]` (annotator refines)
- `start_date` extracted from description text; fallback to pubDate — DO NOT set to null
- `source_id`: `gnews_{md5(url)[:12]}` — stable across runs; `url` is guid if real article URL, else `<link>` tag value
- Skip entries older than 60 days (based on pubDate)
- Google `<guid>` may contain real article URL; prefer it over `<link>` tag when it starts with `http` and does not contain `news.google.com`
- **`_NEWS_SOURCES` member**: `merger.py` uses Pass 2 (date-range + location-overlap) — NOT name similarity — to merge google_news_rss events into official primaries. This is intentional: article titles don't match event names. Never add `google_news_rss` to Pass 1 name-similarity matching.

## nhk_rss-specific
- Fetches NHK news category RSS feeds (cat4=international, cat7=culture/science); Taiwan-filtered; `category: ["report", "books_media"]`
- `start_date` extracted from description text; fallback to pubDate
- `source_id`: `nhk_{md5(url)[:12]}`
- Skip entries older than 90 days
- 0 events is a valid dry-run result when no Taiwan news appears in today's NHK feeds
- **`_NEWS_SOURCES` member**: same Pass 2 matching rules as `google_news_rss` above — NHK article titles do not match event names by similarity.

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

## taiwan_matsuri-specific
- **Geographic scope**: taiwan-matsuri.com hosts events all over Japan (Gunma, Kumamoto, Fukuoka, Nara, Shimane, etc.). Never add a regional keyword filter — the project covers 全日本.
- **Link discovery**: Homepage `<a href="/YYYYMM-slug/">` links include the event status in the link text (`開催中` / `イベント終了`). Skip links whose text contains `終了` to avoid re-scraping ended events.
- **`official_url` = detail page URL**: The detail page IS the official organiser page. Set `official_url=url` (same as `source_url`).
- **`is_paid=False`**: Confirmed on all events — admission is free.
- **After a bug fix**: Always run a non-dry-run (`python main.py --source taiwan_matsuri`) immediately after fixing a filter bug. A dry-run-only fix leaves the data gap until the next CI cycle.
- **Cross-source duplicates**: `taiwan_matsuri` events appear as duplicates in `iwafu`, `google_news_rss`, and other aggregators. `merger.py` handles this automatically — see `## merger.py` section below.

## taiwan_cultural_center-specific
- **Date extraction tiers**: Tier 1 (`_BODY_DATE_LABELS`) → Tier 1b (dot-day) → Tier 1.3 (unlabeled range) → Tier 1.5 (prose DOW) → Tier 2 (title slash) → Tier 3 (publish date fallback). Always add new date patterns at the correct tier before the publish-date fallback.
- **Month-only date ranges**: `期間：2026年5月～10月` is a valid date range for multi-month series. `_parse_date()` handles `YYYY年M月` (no day) → first day of month. End date is adjusted to last day of month via `calendar.monthrange`.
- **`publish date ≠ event date`**: The `.list-text.detail` field contains `日付：YYYY-MM-DD` which is the **publish date**, not the event date. It is used as Tier-3 fallback only. Always verify that `start_date` in dry-run output is NOT the publish date.
- **Location defaults to TCC**: The site rarely provides a venue field. Default is `台北駐日経済文化代表処 台湾文化センター / 東京都港区虎ノ門1-1-12 虎ノ門ビル2階`. For events held at other venues (universities, cinemas), the address appears in the body text but is not extracted — acceptable.
- **`News_Content2.aspx`**: These pages use the same Playwright-rendered structure as `News_Content.aspx`. The scraper's link collector targets `a[href*='News_Content']` which matches both.
- **連続上映企画 (film series) sub-events**: GPT-4o-mini only produces ≤2 sub-events from descriptions with 13,000+ chars, even with 20,000-char truncation limit. **Generate each screening as a separate `Event(parent_event_id=…)` in the scraper layer.** Do NOT rely on annotator sub-event extraction for series with 6+ entries. Pattern: `source_id = f"{parent_source_id}_sub{n}"`. (2026-04-29 実績: 台湾映画上映会2026 16件手動挿入)

## annotator sub-events — reliability limits

- GPT-4o-mini reliably extracts sub-events **only when there are ≤5 entries** in a compact description.
- For series with 6+ sub-events (film screening series, multi-session lectures, repeated workshops), **generate sub-events in the scraper layer**, not via annotator.
- Pattern: emit each session as a separate `Event(parent_event_id=parent_uuid, source_id=f"{parent_source_id}_sub{n}")`. Each child is annotated independently.
- The annotator truncation limit is 20,000 chars (raised from 12,000 in commit `ff2a2ac`). Even with the higher limit, dense long descriptions still cause GPT to stop early.
- If sub-events were already inserted with fewer entries than expected: delete existing subs first, then `upsert` the full corrected set.

## merger.py

`scraper/merger.py` runs after every scraper cycle to deduplicate cross-source events. Two detection passes:

### Pass 1 — Name similarity (same start_date group)
- Groups all active events by `start_date` (YYYY-MM-DD).
- Within each group, pairs events from different sources with name similarity ≥ 0.85 (`SequenceMatcher` on normalised names).
- Lower `SOURCE_PRIORITY` number wins as primary. Current order: `taiwan_cultural_center` (1) → … → `taiwan_matsuri` (6) → … → `iwafu` (11) → `ide_jetro` (13).

### Pass 2 — News-report matching (date-range + location overlap)
- Sources in `_NEWS_SOURCES = {"google_news_rss", "prtimes", "nhk_rss"}` use article titles that cannot match event names by similarity.
- A news event matches an official event when **both** conditions hold:
  - `news.start_date` falls within `[official.start_date - 90 days, official.end_date]`
    — the 90-day **lookback** (`_PRESS_RELEASE_LOOKBACK_DAYS`) covers pre-event press releases published before the event start date
  - `location_name` tokens overlap (≥1 common token of ≥2 characters)
- News events are **always secondary** (priority 100). Official events are **always primary**.
- Pass 2 catches cases where `start_date` differs (e.g. article published mid-festival or months before) and names are stylistically different.

### Merge result
- Primary: `secondary_source_urls` extended; `raw_description` enriched with secondary content (first merge only); `annotation_status` reset to `pending` for re-annotation.
- Secondary: `is_active=False`.
- Idempotent: re-running produces the same result (checks `secondary_url in existing_urls`).

### When to run manually
```bash
cd scraper && python merger.py --dry-run   # preview
cd scraper && python merger.py             # apply
```
Run after discovering a new cross-source duplicate that the merger missed. Then check `--dry-run` to confirm the pair is detected before applying.

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.
- **Periodic audit**: Occasionally cross-check `ls scraper/sources/*.py` against the `SCRAPERS` list in `scraper/main.py`. Source files not in `SCRAPERS` are silently ignored by CI — they never run. In April 2026, 8 scrapers were discovered in this state (CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper).

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
| `peatix.py` | `.github/skills/peatix/SKILL.md` |
| `taiwan_cultural_center.py` | `.github/skills/taiwan_cultural_center/SKILL.md` |
| `connpass.py` or `doorkeeper.py` | `.github/skills/community-platforms/SKILL.md` |
| Other sources | No dedicated SKILL yet — add rule here instead |

### 4. dry-run validation — always run before finishing
```bash
cd scraper && python main.py --dry-run --source <source_name> 2>&1 | head -80
```
Confirm: `start_date` populated, no unhandled exceptions, events count is non-zero (or zero for an expected reason).

## Documentation Protocol (Phase 4 — mandatory)

After every new source or bug fix, create/update these files **before committing**:

### New source checklist

| File | Action |
|------|--------|
| `.github/skills/<source_name>/SKILL.md` | **Create** — platform profile, field mappings, Taiwan filter, date extraction, troubleshooting |
| `.github/skills/<source_name>/history.md` | **Create** — initial implementation decisions |
| `.github/skills/agents/scraper-expert/SKILL.md` | **Update** — add `## <source_name>-specific` section (3–5 key rules) |
| Supabase `research_sources` | **Update** `status → implemented` AND `scraper_source_name → <source_name>` (both fields, same operation) |

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

## taiwanbunkasai-specific

1. **`name_ja` MUST include year**: Use `f"台湾文化祭{start_date.year}"` — the raw `<title>` is "台湾文化祭" (no year), giving merger similarity 0.71 vs iwafu. With year suffix = 1.000.
2. **Single-page site returns 0 or 1 events**: The site shows only the next upcoming event. Returning `[]` between events is correct behaviour, not a bug.
3. **`_VENUE_MAP` resolves 中野 / KITTE**: Raw venue text is not a valid address. Always match against `_VENUE_MAP` keywords to get canonical `location_name` + `location_address`.
4. **`merger.py SOURCE_PRIORITY["taiwanbunkasai"] = 7`**: Must be lower (higher authority) than iwafu (11) so official site wins as primary when merger detects the duplicate.
5. **`is_paid = False`**: Confirmed 入場無料 on all known editions (KITTE and 中野).

## gguide_tv-specific

1. **2-step HTTP session**: Always GET `/search/?q={kw}` first to set `_ggm-web_session` cookie before calling `/fetch_search_content/`.
2. **ebisId dedup key**: Parse `a.js-logging[data-content]` JSON → `.ebisId`; use `seen_ebis_ids` set to skip across multiple keyword searches.
3. **Year inference**: Schedule strings (`4月29日 水曜 12:00`) have no year — try current year; if result is older than `LOOKBACK_DAYS` days, try `current_year + 1` (handles Dec→Jan boundary).
4. **テレサ・テン filter**: Only keep programs where the full string `テレサ・テン` appears in the title; blocks variety shows where テレサ is a minor guest alongside other artists.
5. **`台湾ドラマ` is redundant**: All results from `台湾ドラマ` are already returned by the `台湾` keyword search — do not add it to `SEARCH_KEYWORDS`.

## livepocket-specific
- **`dl` class is `event-detail-info__list`**, not `event-detail-info`. The `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` inside the `dl`. Use `_get_dd_text(dl, label)` iterating `div.event-detail-info__block`.
- **Class name convention**: Class `LivePocketScraper` → `_scraper_key = live_pocket` (CamelCase split), conflicting with `source_name = "livepocket"`. Always use `LivepocketScraper` (lowercase `p`) so `_scraper_key = livepocket`.
- **Venue address is in a `<span>`** inside the `会場` `dd`, after the `(都道府県)` parenthetical. Split at the parenthetical match; strip map link boilerplate.
- **Taiwan filter is detail-page only**: Search results match "台湾" in performer names or venue names unrelated to Taiwan events. Always apply keyword filter on full detail page text.
- **Two duplicate `dl` blocks per page** (desktop + mobile): always use `select_one()`.

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

## Geographic Scope — All of Japan（全日本）
- **NEVER add a Tokyo-only location filter** unless the source itself is physically Tokyo-only (e.g. a single venue).
- Events in Osaka, Kyoto, Fukuoka, Sapporo, Nagoya, Sendai, Hiroshima and all other prefectures are **in scope**.
- API scrapers that accept a `prefecture=` or region param must either omit it (nationwide) or iterate all prefectures.
- Connpass `prefecture=tokyo` was removed 2026-04-26 — do NOT re-add it.
- Doorkeeper has no location filter — keep it that way.
- The Taiwan relevance gate (`_TAIWAN_KEYWORDS`) is the only required filter; location is irrelevant to inclusion.

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

## note_creators-specific

- **Dynamic account list (DB-driven)**: `NoteCreatorsScraper._load_db_creators()` queries `research_sources WHERE url LIKE 'note.com/%' AND status='implemented'`. To add a new note.com creator, insert a row with the creator root URL (`https://note.com/{creator_id}`) and set `status='implemented'`. No code change needed.
- **Static seeds always run**: The 2 hardcoded entries in `CREATOR_META` (`kuroshio2026`, `nichitaikouryu`) always run and take precedence over any matching DB row. Hardcoded metadata is richer (exact address); DB entries only need `name`.
- **`source_profile` JSONB**: Optionally store `{"location_name": "...", "location_address": "...", "categories": ["taiwan_japan"]}` in the DB row's `source_profile` column to override defaults.
- **No Taiwan filter applied**: All posts from registered creators are assumed Taiwan-related. Do NOT add a keyword filter — it would drop legitimate event-focused posts.
- **RSS feed URL**: `https://note.com/{creator}/rss` — no auth required. Template URL `https://note.com/{creator}/rss` (with literal `{creator}`) in the DB is ignored automatically by `_extract_creator_from_url` (curly braces rejected by the regex).
- **DB unavailable = graceful degradation**: When env vars are missing (dry-run on CI), `_load_db_creators()` catches the exception and returns `{}` — static creators still run normally.
- **`source_id` format**: `note_{creator}_{note_id}` where `note_id` is the article-level path segment (e.g. `n4f9a42875b82`). Stable across runs.

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

## jposa_ja-specific

- **Use RSS feeds, not the listing page**: `/jposa_ja/cat/4.html` is JS-rendered; the listing skeleton returns no event links. WordPress category RSS feeds (`/jposa_ja/category/<encoded>/feed/`) are the correct data source. Paginate with `?paged=N` (10 items/page, newest-first).
- **Most posts are diplomatic visit recaps**: ~90% of posts match patterns like `の表敬訪問を受ける` / `と面会` / `を歓迎`. Apply `_EVENT_KW` (positive) + `_SKIP_KW` (negative) title filter before fetching detail pages.
- **content:encoded has full body**: The RSS `<content:encoded>` CDATA block contains the full post HTML. Parse it with BeautifulSoup before falling back to a detail page HTTP request.
- **XMLParsedAsHTMLWarning must be suppressed**: `warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)` is required when using `html.parser` on the RSS XML.
- **Low yield is normal**: 1–3 event posts per month. `LOOKBACK_DAYS = 180` is intentional — do not reduce it.
