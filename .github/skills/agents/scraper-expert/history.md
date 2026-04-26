# Scraper Expert Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 — cine_marine + taiwan_faasai: two new scrapers implemented

**cine_marine (横浜シネマリン):**
- Listing page structure: each film entry is `<h2>` (date) + `<h3><a>` (title+URL) + `<div class="content_block">` (details) within a single `.entry-content` article.
- Taiwan filter applied only to `content_block` text (not full film page) to avoid false positives from sidebar that lists all current films.
- Source name: `cine_marine` (from `CineMarineScraper` via `_scraper_key`).

**taiwan_faasai (台湾發祭 Taiwan Faasai):**
- Annual 3-day free outdoor festival in Ueno Park.
- TLS issue: `verify=False` required, `InsecureRequestWarning` suppressed.
- Source ID: `taiwan_faasai_{year}` — stable per year.

---


**Error (morc_asagaya):** All 24 film pages matched Taiwan filter because every page contains a site-wide `section#tp_info` with "台湾巨匠傑作選2024" promotion links. Initial implementation applied `get_text()` to the entire page including this section.

**Fix (morc_asagaya):** Added `soup.select('#tp_info')[...].decompose()` before keyword search. Result: 0 events (correct — no Taiwan films on screen).

**Error (shin_bungeiza):** `_parse_nihon_date_only` used `p.find_previous("h2")` to find the start date. Because `p.nihon-date` is the first child in its container, `find_previous` returned an h2 from a prior film block → wrong date (e.g. 5/6 instead of 5/8).

**Fix (shin_bungeiza):** Rewrote to iterate `parent.children`, collecting h2 elements that appear after the `p`. First h2 → start date (M/D format). Last h2 → end date (day-only, same month with wrap guard).

**Lesson (generalizable):** When an element is the first sibling in its container, `find_previous()` crosses container boundaries. Always iterate `parent.children` for sibling-relative navigation. Also: site-wide banners can pollute keyword filters — inspect false-positive pages to identify the offending section and exclude it.

---
## 2026-04-26 — workflow: push step was missing from post-change checklist

**Error:** After implementing cinemart_shinjuku scraper (Phase 4 docs complete), task_complete was called without committing or pushing. The feature branch had to be created and pushed manually in a follow-up turn.

**Fix:** Added Step 5 (git commit & push) to `## Mandatory Post-Change Checklist` in `SKILL.md`, and added Phase 5 (Commit & Push) to `scraper-expert.agent.md`.

**Lesson:** Every scraper session must end with a commit + push to a feature branch before calling task_complete. → Added to SKILL.md Step 5 and agent.md Phase 5.

---
## 2026-04-26 — taiwanshi: date/venue regex misses non-standard separators

**Error:** 2 posts had `date parse failed` warnings; 1 post had `venue=None`. Affected: `場所：` label, `会場　` (full-width space only, no colon), and `日時： 2025 年10月4 日` (spaces within date).

**Root cause:** Initial regex assumed `日時[：:]` (colon required) and `会場[：:]` (colon required), missing: (a) full-width space separator `日時　`, (b) `場所：` label instead of `会場：`, (c) OCR/copy-paste spacing within the date `2025 年10月4 日`.

**Fix:** Extended date regex separator to `[：:\s\u3000]*` and date component matches to `\s*年\s*...\s*月\s*...\s*日`. Extended venue regex to `(?:会場|場所)[\uff1a:\u3000 \t]+`.

**Lesson:** Japanese blog posts use inconsistent separators after label words. Always allow `[：:\s\u3000]*` (colon or any whitespace) as the separator between a label (`日時`, `会場`, `場所`) and its value. Also allow `\s*` between digit groups and kanji connectors in date fields. → Added to `## taiwanshi-specific` in SKILL.md.

---
## 2026-04-26 — ifi: URL injected into location_address from venue map link

**Error:** `location_address` contained `https://www.u-tokyo.ac.jp/campusmap/...` appended after the venue name.

**Root cause:** IFI appends a campus map URL on the line immediately after the venue name in `inner_text`. `_extract_info()` captured it as part of the venue value.

**Fix:** Filter venue lines with `not ln.strip().startswith("http")` before building `location_name`/`location_address`.

**Lesson:** Academic sites frequently append map/registration URLs directly below venue names without a visual separator. Always filter HTTP lines from venue extraction.

---
## 2026-04-26 — tokyonow: API keyword search returns 0 for Japanese terms

**Error:** `GET /wp-json/tribe/events/v1/events?search=台湾` returns 0 results even when Taiwan events exist on the site.

**Root cause:** The Tribe Events v1 WordPress plugin `search` parameter only matches English title/slug fields — it does not index Japanese text.

**Fix:** Full-page scan strategy — paginate all future events with `start_date=<today>&per_page=50`, apply local `_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]` filter on stripped title + description.

**Lesson:** Do not assume REST API `search` parameters support Japanese full-text search. Always test a known Japanese keyword against a known Japanese event before relying on server-side filtering. Fall back to full-scan + local filter when the API returns 0 unexpectedly.

---
## 2026-04-25 — koryu: Taiwan-office events leaking into DB (wrong location_address)

**Error:** `_scrape_detail()` never called `_is_tokyo_venue()`. The function existed but was dead code. As a result, events organised by koryu’s Taiwan offices (台北・台中・高雄) were ingested alongside Tokyo events. One event showed `location_address='台北'` even though the title clearly said 台中. 8 bad events accumulated in the DB.

**Root cause:** The koryu.or.jp DNN CMS renders a breadcrumb in the `<main>` inner text as a run-on string: `お知らせイベント・セミナー情報台北`. The trailing kanji (`台北`, `台中`, `東京`) is the office/category tag assigned in the CMS. Taiwan-office events were not filtered because no code checked this tag.

**Fix:**
1. Added `_TAIWAN_OFFICE_TAGS = {'台北', '台中', '高雄', '台南', '桃園', '新竹', '基隆', '嘉義'}` constant.
2. Added `_extract_office_tag(body_text)` that regex-extracts the tag after `イベント・セミナー情報\s*([\u4e00-\u9fa5]{1,6})`.
3. In `_scrape_detail`: if `office_tag in _TAIWAN_OFFICE_TAGS` → return None.
4. DB: hard-deactivated (`is_active=False`) all 8 Taiwan-location koryu events.

**Lesson:**
- After adding a geographic filter, ALWAYS audit existing DB rows with `eq('source_name','koryu')` and deactivate any that would have been blocked.
- DNN CMS breadcrumb text is part of `main.inner_text()` — location/office tags from the breadcrumb can pollute venue/address extraction if not stripped or checked first.
- `_is_tokyo_venue()` was defined but never called — dead utility functions should either be wired up or deleted. Prefer wiring them up and adding a test to confirm.

---

**Error (1 — direct URL accessible):** Deactivated events (`is_active=False`) were still accessible via direct URL. The event detail page had no `is_active` check — it fetched by ID regardless of status.

**Error (2 — card title truncation bypass):** `_BLOCKED_TITLE_PATTERNS` only checked `card_title` from search-result card text. If the card title was truncated and didn't contain both "リアル脱出ゲーム" AND "名探偵コナン", the filter would pass. No second check was done on the actual h1 title after loading the detail page.

**Fix:**
1. Hard deleted all 7 Conan events from DB (iwafu_1133807, 1133810, 1134057–1134061).
2. `web/app/[locale]/events/[id]/page.tsx`: Added `if (!event.is_active) notFound()` — inactive events now return HTTP 404.
3. `scraper/sources/iwafu.py`: Added `_BLOCKED_SERIES = re.compile(r"名探偵コナン")` checked on both card title (pre-load) and h1 title (post-load). Extended `_BLOCKED_TITLE_PATTERNS`.

**Lesson:**
- Inactive events remain accessible by direct URL unless detail page returns `notFound()` for `!is_active`. Always add this guard.
- Title blocks must check BOTH card title (pre-load) AND h1 title (post-load). Card titles can be truncated.
- For permanently blocked IP series, use `_BLOCKED_SERIES` with just the IP name. Simpler and catches all title variants.
- When an IP series is confirmed non-Taiwan-themed, prefer hard delete over deactivation to prevent URL resurrection.

---
## 2026-04-25 — iwafu/koryu/peatix: location_address stored as generic prefecture name ("東京") instead of real venue

**Error:** Three scrapers were writing useless generic values to `location_address`:
- **iwafu**: `_scrape_detail()` set `location_address = card.get("prefecture")` which was always `"東京"` (or `"東 京"` with space). The detail page contains `場所：中野区役所…` but was never parsed.
- **koryu**: `_extract_location_address()` only finds `所在地/住所` sections; when absent, `location_address` stayed `None` even though `_extract_venue()` had already extracted a useful venue name.
- **peatix**: CSS selectors `.venue-address` / `[class*='address']` miss the address on many events. No regex fallback existed.

**Fix:**
- `iwafu.py` `_scrape_detail()`: Added `re.search(r'場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)', main_text)` regex before the `card.prefecture` fallback. Sets both `location_name` and `location_address` to the captured venue.
- `koryu.py` `_scrape_detail()`: Changed `location_address = _extract_location_address(body_text)` → `_extract_location_address(body_text) or (venue if venue else None)`.
- `peatix.py` location block: Added regex fallback on `page_text` — `LOCATION\n<name>` for venue name, `〒NNN-NNNN` or `東京都...` for address.
- `scraper/backfill_locations.py` (new): One-off script to re-visit iwafu/koryu source URLs and apply the new extraction logic to existing DB rows. Supports `--dry-run`.

**Lesson:**
- When a detail page contains a structured `場所：` or `会場：` label, always prefer that over the card-level prefecture. Parse it with a regex before falling back to coarser data.
- For scrapers where the main location field may be absent, use the venue name as an `or` fallback for `location_address` — partial info is better than `None` or a bare prefecture.
- CSS selectors on JS-heavy pages (Peatix) are unreliable for location; always add a `page_text` regex fallback.
→ Added to SKILL.md (`iwafu-specific`, `koryu-specific`) and `peatix/SKILL.md` (Location Extraction section).

---

## 2026-04-25 — location/address/hours displayed in Japanese on zh/en locale

**Error:** `location_name`, `location_address`, and `business_hours` had no localized variants in the DB schema. The event detail page always showed the Japanese original regardless of the visitor's locale (e.g., "高知県立牧野植物園", "午前9時から午後5時" displayed to English/Chinese visitors).

**Root cause:** DB schema had only single-language columns for these three fields. The annotator extracted them from Japanese source text and stored only Japanese. No `_zh`/`_en` variants existed.

**Fix:**
1. `supabase/migrations/010_localized_location.sql` — Added 6 new columns: `location_name_zh`, `location_name_en`, `location_address_zh`, `location_address_en`, `business_hours_zh`, `business_hours_en`.
2. `scraper/annotator.py` — Updated GPT schema in `SYSTEM_PROMPT` to request the 6 new fields. Updated `update_data` and sub-event rows to populate them.
3. `web/lib/types.ts` — Added 6 fields to `Event` interface. Added three helper functions: `getEventLocationName(event, locale)`, `getEventLocationAddress(event, locale)`, `getEventBusinessHours(event, locale)` — all fall back to the Japanese original.
4. `web/app/[locale]/events/[id]/page.tsx` — Import and use the three new helpers instead of raw `event.location_name`, `event.location_address`, `event.business_hours`.
5. DB fix: reset `f463ad3d` (iwafu_1062563) to pending and re-annotated after migration.

**Lesson:**
- Any field that a non-Japanese visitor reads should have `_zh`/`_en` variants. Apply the same `_ja/_zh/_en` pattern to location, address, and hours — not just name and description.
- Always check: does the event detail page display anything sourced from Japanese-only source text without a locale helper?
- When adding new localized columns, the annotator's `update_data` must include ALL new fields (with `_str()`/`_loc()` cleaning). The GPT schema must explicitly request them.

---

## 2026-04-25 — AdminEditClient: null name_zh/name_en converted to "" on save → title disappears

**Error:** When an event has `name_zh = null` (or GPT returned `null`), the admin edit form initializes the field with `event.name_zh ?? ""`, converting `null` to `""`. On save, `""` is written to the DB. The `getEventName` function used `??` which does NOT fall back on empty strings (`"" ?? fallback → ""`), so the event title disappeared in the zh/en locale.

Additionally, events with `annotation_status = 'annotated'` but empty strings in `name_zh`/`name_en`/`description_zh`/`description_en` (e.g. `iwafu_1062563` — 【高知県立牧野植物園】こんこん山花さんぽ) showed no title or description because the DB contained `""` instead of `null`.

**Root causes (two bugs interacting):**
1. `AdminEditClient.tsx`: `const payload = { ...form }` sends `""` for every empty name/description field, converting `null → ""` in the DB.
2. `web/lib/types.ts` `getEventName`/`getEventDescription`: used `??` instead of `||`, so `""` did not trigger fallback to next locale.

**Fix:**
1. `web/lib/types.ts`: Changed `??` → `||` in `getEventName` and `getEventDescription` so empty strings fall back to the next locale.
2. `web/components/AdminEditClient.tsx`: Added `nullify` helper in `handleSave` — converts `""` to `null` for name/description fields before PATCH. `name_ja` falls back to `event.raw_title` if empty.
3. Direct DB fix for `f463ad3d` (iwafu_1062563): cleared `""` → `null`, reset `annotation_status = 'pending'`, re-ran `annotator.py` → produced proper `name_zh = '春花漫步'`, `name_en = 'Spring Flower Walk'`.

**Lesson:**
- Admin form fields that represent nullable DB columns should send `null` (not `""`) when empty. Wrap empty strings with `|| null` in the save payload.
- `??` and `||` have different semantics: `??` only catches `null`/`undefined`; `||` also catches `""` and `0`. Use `||` for locale fallback chains where GPT might return empty string.
- After annotator bugs produce empty strings for existing events, you must manually reset those events to `pending` and re-run `annotator.py`. The `_str()` helper in annotator prevents recurrence for future runs only.

---

## 2026-04-25 — iwafu: 6 more Conan events survived after _GLOBAL_TOUR_PATTERNS fix

**Error:** When `_GLOBAL_TOUR_PATTERNS` was added to `iwafu.py`, it only prevented **future** scraper runs from re-inserting matching events. The 6 existing DB rows (`iwafu_1134057` through `iwafu_1134061` + `iwafu_1133807`) were already in the DB with `is_active=True` and were unaffected. They continued to appear in the admin backend.

**Fix:**
1. Queried for all `%コナン%` events, deactivated all 6 remaining ones via targeted `update().eq("id", ...)` calls.
2. Added `_BLOCKED_TITLE_PATTERNS` regex in `iwafu.py` with pattern `リアル脱出ゲーム.*名探偵コナン` — checked in `_scrape_detail` **before** the page load (fast-reject). This blocks any new source_id variants of the same series (e.g. new tour stops) regardless of description wording.

**Lesson:**
- Fixing the scraper filter does NOT retroactively remove existing DB records. After adding a filter, always run a DB audit to deactivate any already-stored events that match the new rule.
- For well-known IP series that run global tours (anime collabs, game IPs), add the series name to `_BLOCKED_TITLE_PATTERNS` so all future venue variants are blocked at title level — before the detail page is fetched. Description-only filters can miss series with identical descriptions.
- Pattern for querying all events from a false-positive series: `sb.table("events").select("id,source_id").ilike("raw_title", "%<keyword>%")`.

---

## 2026-04-25 — taiwan_kyokai: end_date always null; publish-date used instead of event date

**Error (1 — end_date null):** `_extract_event_fields` in `taiwan_kyokai.py` never set `result["end_date"]`, leaving a comment "we keep only start_date for now". All single-day events had `end_date=None`, causing them to remain in "active" listings indefinitely (the web filter keeps events where `end_date IS NULL` OR `end_date >= today`).

**Error (2 — wrong start_date):** For pages where the event date lacks a year (e.g. `今年は5月16日（土）に執り行われます`), the generic fallback regex `YYYY年MM月DD日` found the page's **publish date** at the top of the body (`2026年4月20日`) instead of the actual event date (`5月16日`). The publish date appears prominently on taiwan-kyokai.or.jp pages just below the title.

**Fix:**
1. Added DOW-qualified date extraction step in `_extract_event_fields` — searches for `\d{1,2}月\d{1,2}日（[月火水木金土日][曜]?[日]?）` and infers year from nearest `20XX年` in text. Runs BEFORE the generic fallback, so `今年は5月16日（土）` is preferred over the bare `2026年4月20日` publish date.
2. Added single-day end_date rule at the bottom of `_extract_event_fields`: `if result["start_date"] and not result["end_date"]: result["end_date"] = result["start_date"]`. Taiwan Kyokai events are all single-day.
3. Direct DB fixes: `taiwan_kyokai_news-260420-2` start/end → 2026-05-16; `taiwan_kyokai_news-260217` end_date → 2026-04-12.

**Lesson:**
- **Always set `end_date = start_date` at end of `_extract_event_fields` for single-day sources.** Never leave it with a "for now" comment.
- On japan-kyokai-style sites, the page body starts with the **publish date** (`YYYY年MM月DD日`) before the actual event body. Never rely on the generic year-qualified date fallback alone.
- Dates with day-of-week markers `（土）（日）etc.` are almost always actual event dates. Prioritize these over bare `YYYY年MM月DD日` patterns when no structured `日時：` field is present.

---

## 2026-04-25 — annotator: leading ：colon included in location_name

**Error:** GPT extracted `会場：台北世界貿易センター１F（...）` and included the label separator `：` as the first character of `location_name`, producing `：台北世界貿易センター１F（...）` in the DB and on the web UI.

**Fix:** Added `_loc()` helper in `annotator.py` that calls `.lstrip("：；:; \u3000")` on all `location_name` and `location_address` values before writing to DB. Also did a direct DB fix for `koryu_4899`.

**Lesson:** Always strip leading `：；:;` and full-width space (`　`) from GPT-extracted location strings. GPT occasionally includes the Japanese label separator when the source text uses `会場：〇〇` or `場所：〇〇` patterns. Apply `_loc()` to both `location_name` and `location_address`.

---

## 2026-04-25 — iwafu: global-tour event passed Taiwan filter (コナン脱出ゲーム)

**Error:** `iwafu_1133810` (リアル脱出ゲーム×名探偵コナン) was collected because the description contained `台湾など世界各地で開催`. The event is a Japan/world-wide tour and has no Taiwan theme; the Tokyo instance is culturally identical to the Osaka and Nagoya instances.

**Fix:** Added `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py`. Any detail page whose `title + description` matches patterns like `台湾など世界各地|全国各地.*台湾` is rejected in `_scrape_detail()` before an Event is returned. Set `iwafu_1133810` to `is_active=False` in DB.

**Lesson:** "Being held in Taiwan (among many other cities)" does NOT make an event Taiwan-related. Only accept events where Taiwan is the theme or a primary focus, not just one venue on a global tour. Add `_GLOBAL_TOUR_PATTERNS` reject guard wherever iwafu full-text is searched by keyword 台湾.

---

## 2026-04-25 — arukikata: duplicate class caused old code to shadow new code

**Error:** `replace_string_in_file` on docstring-only line caused the old class body to remain appended after the new class in the same file. Python silently uses the **last** definition, so the old (broken) `_parse_article` ran instead of the new one. Symptoms: dry-run returned old buggy results even after editing.

**Fix:** Used `wc -l` to detect the file was 615 lines instead of ~292; used `head -n 292 > /tmp && mv` to truncate to the correct end.

**Lesson:** After a large structural rewrite using `replace_string_in_file`, always verify the file has the expected line count with `wc -l`. If it's unexpectedly large, a duplicate class body is likely still present.

---

## 2026-04-25 — arukikata: keyword search strategy misses articles

**Error:** `?s=台湾+東京+イベント` search only returned 29 results; articles 362618 and 323275 were not among them — each requires a different keyword combination.

**Fix:** Switched to **WordPress sitemap monitoring**: `wp-sitemap-posts-webmagazine-2.xml` (605 entries) contains both target articles with `lastmod` timestamps. Filter by `lastmod >= today - 90 days`.

**Lesson:** For WordPress editorial sites, always check for `wp-sitemap-posts-{type}-{page}.xml` first. Sitemap monitoring is more comprehensive and stable than keyword search for low-frequency sources. The sitemap with the highest page number contains the newest articles.

---

## 2026-04-25 — Doorkeeper Tokyo filter false positive (中央区)

**Error:** `中央区` was included in `_TOKYO_MARKERS` in `doorkeeper.py`.
This matched 神戸市中央区, causing a Kobe event to pass the Tokyo location filter.

**Fix:** Removed all ward names that are not geographically unique to Tokyo from `_TOKYO_MARKERS`.
Kept only `東京都`, `東京`, and 23-ward names that are exclusive to Tokyo prefecture.

**Lesson:** Never add bare ward names like `中央区`, `南区`, `北区`, `西区` to a Tokyo marker set —
they appear in Osaka, Kobe, Nagoya, and many other cities.
The safest Tokyo markers are `東京都` and `東京` as substring matches.
Individual ward names are only safe if they are provably unique to Tokyo (e.g. `渋谷区`, `豊島区`).

---

## 2026-04-25 — Connpass API v1 → v2 migration (403 on v1)

**Observation:** Connpass API v1 (`/api/v1/event/`) now returns HTTP 403 for all requests,
including those from fixed IPs. The platform has fully migrated to v2 which requires an `X-API-Key` header.

**Implementation decision:** Built `ConnpassScraper` against v2 API.
If `CONNPASS_API_KEY` is not set, scraper logs a WARNING and returns `[]` — pipeline continues uninterrupted.

**Lesson:** API v1 is dead. Do not reference v1 endpoints in any future Connpass code.
The v2 key must be obtained via the Connpass help page: https://connpass.com/about/api/
Their ToS also explicitly prohibits non-API scraping (Playwright/curl), so the API key is mandatory.
