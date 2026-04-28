# Scraper Expert Error History

<!-- Append new entries at the top -->

## 2026-04-28 — 赤色的線 輪迴的秘密 [shin_bungeiza] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影是台灣製作，反映了台灣的文化和故事。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-29 — 8 Unregistered Scrapers Found in SCRAPERS List Gap [main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper all had `.py` source files but were NOT included in the `SCRAPERS = [...]` list in `scraper/main.py`. This caused them to be skipped by the daily CI run despite being ready for production.

**Discovery**: Audit found via manual inspection and confirmed via `python main.py --dry-run`.

**Fix**: Added all 8 to `SCRAPERS` list and validated dry-run output:
- CineMarineScraper: 1 event (横浜シネマリン)
- EsliteSpectrumScraper: 2 events (誠品生活日本橋)
- MoonRomanticScraper: 1 event (Moon Romantic)
- MorcAsagayaScraper: 0 events (正常 — no Taiwan films today)
- ShinBungeizaScraper: 1 event (新文芸坐)
- SsffScraper: 6 events (SSFF)
- TaiwanFaasaiScraper: 1 event (台湾發祭)
- TokyoFilmexScraper: 0 events (正常 — festival in October)

**Lesson**: The sources directory and `SCRAPERS` list can drift silently. Implement monthly audit: `comm -23 <(find sources/ -name '*.py' ... ) <(grep 'Scraper()' main.py ...)`. After creating any new scraper file, registration in `SCRAPERS` must happen at commit time, not rely on CI discovery.

---

## 2026-04-29 — Google search fallback used wrong locale title [web]
**Error**: Detail page Google search URL used `name` (locale-specific) as query text. In `zh` locale, the query became `大濛 公式サイト` instead of `霧のごとく 公式サイト`, causing the Japanese official site to not appear in results.
**Fix**: Changed query to prefer `event.name_ja || event.raw_title || name` so the Japanese title is always used regardless of the viewing locale.
**Lesson**: When building Japanese-language search URLs, always use `name_ja` (or `raw_title`) as the source of the search term — never the locale-resolved display name.
---

## 2026-04-29 — Existing DB records not updated after adding official_url to cinema scrapers [cinemart_shinjuku, ks_cinema]
**Error**: After adding `official_url` extraction to `cinemart_shinjuku.py`, the existing DB event `cinemart_shinjuku_002491` (「大濛」) still had `official_url = null` because the upsert only runs on the next scraper cycle.
**Fix**: Ran a targeted Supabase UPDATE: `update({'official_url': 'https://www.afoggytale.com/'}).eq('source_id', 'cinemart_shinjuku_002491')`.
**Lesson**: When adding a new field extraction to an existing scraper, always manually update currently-active DB records or set `force_rescrape=True` for affected events. Dry-run only confirms the code works — it does NOT write to DB.
---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影以香港的食堂為背景，描繪了面對社會變遷的人們，由台湾・香港・法國共同製作。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-28 — 霧的如同 [cinemart_shinjuku] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:大濛, fieldEdit:name:en:A Foggy Tale, fieldEdit:name:ja:霧のごとく
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 台灣發祭 Taiwan Faasai 2026 [taiwan_faasai] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** lifestyle_food
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 身體化巴索里尼 - 吸引力法則 [ssff] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** performing_arts
**After (corrected):** movie
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 品嚐台灣茶，享受台灣遊戲的聚會 [kokuchpro] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** taiwan_mandarin, lifestyle_food, taiwan_japan, workshop
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 台灣電影上映會《海をみつめる日》上映暨座談會 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongDetails, wrongCategory, fieldEdit:name:zh:台灣電影放映會《看海的日子》上映暨座談會, fieldEdit:name:en:Taiwan Film Screening of 'A Flower in the Raining Night' and Talk Event, fieldEdit:name:ja:台湾映画上映会『海をみつめる日』上映＆トークイベント
**Before (AI category):** movie, lecture
**After (corrected):** movie, literature, history
**Wrong fields:** name
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 阿嬤的夢中情人 [eiga_com] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie, lecture
**After (corrected):** movie, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 甘露水 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, art, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 看海的日子（數位修復版） [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, history, literature
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


---
## 2026-04-29 — taiwan_cultural_center: month-only date range caused publish-date fallback

**Error:** `期間：2026 年5 月～10 月(全10 回)` was matched by `_BODY_DATE_LABELS` regex, but `_parse_date("2026 年5 月")` returned `None` (no day component). `start_date` fell back to publish date `2026-04-27`, `end_date = 2026-04-27` — would have been archived that evening.

**Fix:** (1) `_parse_date()`: added month-only `YYYY年M月` → day 1 of that month. (2) `_extract_event_dates_from_body()`: detect month-only `end_raw`, inject year from start, advance to last day of month via `calendar.monthrange`. (3) DB record manually corrected to `2026-05-16 / 2026-10-24`. Scraper will upsert `2026-05-01 / 2026-10-31` on next run (acceptable).

**Lesson:** `_parse_date()` must handle `YYYY年M月` (no day). Multi-month series often use month-only ranges in the structured `期間：` label. Always verify end_date won't trigger same-day archival.

---

## 2026-04-28 — 台灣文化祭2026春 [arukikata] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan, lecture
**After (corrected):** lifestyle_food, tourism, lecture, retail
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 電影《大濛》上映 [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》上映, fieldEdit:name:en:Screening of the Movie 'A Foggy Tale', fieldEdit:name:ja:映画『霧のごとく』上映
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場 x 映後座談, fieldEdit:name:en:Private screening & talk of the film 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく（大濛）』東京貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---
## 2026-04-28 — 8 個爬蟲 source 檔案存在但未加入 SCRAPERS 列表

**Error:** CineMarineScraper、EsliteSpectrumScraper、MoonRomanticScraper、MorcAsagayaScraper、ShinBungeizaScraper、SsffScraper、TaiwanFaasaiScraper、TokyoFilmexScraper 已有 source 檔案但未加入 `scraper/main.py` 的 `SCRAPERS = [...]`。CI 從未執行這些爬蟲。
**Fix:** 補充 8 個爬蟲的 import 及 SCRAPERS 列表項目。以 `--dry-run` 確認各爬蟲能執行（CineMarineScraper 1件、EsliteSpectrumScraper 2件、MoonRomanticScraper 1件、ShinBungeizaScraper 1件、SsffScraper 6件、TaiwanFaasaiScraper 1件；MorcAsagayaScraper 和 TokyoFilmexScraper 0件屬正常——當日無台灣活動）。
**Lesson:** 建立新爬蟲 source 檔案後必須在同一 commit 確認已加入 SCRAPERS。定期比對 `ls sources/*.py` 與 SCRAPERS 列表，source 檔案不在 SCRAPERS 中將被 CI 靜默略過。→ Updated "Registration" in SKILL.md.

---
## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京電影包場 x 映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 電影《霧的如同（大濛）》東京包場上映會暨映後座談 [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場上映會暨映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トーク
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---
## 2026-04-28 — merger.py Pass 2: pre-event press release not matched (start_date before event)

**Error:** `c1ba79b6` (google_news_rss, gnews_c5e4ad11f794) pointed to a prtimes.jp press release about 台湾祭in群馬太田2026 published **2026-01-15** — two months BEFORE the event start (2026-03-14). Merger Pass 2 uses `_date_in_range(news.start_date, official.start_date, official.end_date)` which returned False (`2026-01-15 < 2026-03-14`). Event was not merged; remained is_active=False with empty secondary_source_urls and prtimes content never incorporated.

**Fix:**
1. `merger.py`: Added `_PRESS_RELEASE_LOOKBACK_DAYS = 90` constant; changed `_date_in_range` to accept `lookback_days` parameter; Pass 2 now calls `_date_in_range(..., lookback_days=_PRESS_RELEASE_LOOKBACK_DAYS)` → range becomes `[start_date - 90d, end_date]`.
2. DB: Manually merged c1ba79b6 into primary `taiwan_matsuri_202603-gunmaota`:
   - Added google_news URL + direct prtimes.jp URL to `secondary_source_urls`
   - Fetched prtimes article body → appended as `別来源補足 (prtimes)` in `raw_description`
   - Set `annotation_status = 'pending'` for re-annotation with enriched content

**Lesson:** Pre-event press releases (prtimes, PR WIRE) are published weeks or months BEFORE the event start date. Merger Pass 2 must use a lookback window (currently 90 days) on `official.start_date` — NOT a strict lower bound. Also: when a google_news_rss entry links to a prtimes article, the ACTUAL rich content is at prtimes.jp — fetch that URL for the merger's raw_description supplement, not the google_news headline.

---

**Error:** `google_news_rss` 的「イオン太田で台湾グルメと台南ランタン祭イベント」（id: 1c766979）和 `taiwan_matsuri_202603-gunmaota` 是同一個活動，但 `merger.py` Pass 1 未偵測到，原因有二：
1. 名稱相似度太低（新聞報導標題 vs 官方活動名稱），不達 0.85 閾值。
2. `start_date` 不同（報導發布日 2026-03-16 vs 開幕日 2026-03-14），不在同一 `date_group`。

**Fix:**
1. 手動合併 DB：將 google_news_rss source_url 加入 `taiwan_matsuri_202603-gunmaota` 的 `secondary_source_urls`；設 google_news_rss 事件 `is_active=False`。
2. 同時發現スカイツリー2026 也有相同問題（`a5d24992`），一併合併。
3. `merger.py` 新增 **Pass 2 — News-report matching**：對 `_NEWS_SOURCES = {google_news_rss, prtimes, nhk_rss}`，以「日期在範圍內 + 地點 token 重疊」取代名稱相似度，並新增 `_location_overlap()` / `_date_in_range()` helpers。DB select 同步補加 `end_date,location_name`。

**Lesson:** 新聞/報導來源（google_news_rss、prtimes、nhk_rss）的文章標題和官方活動名稱結構不同，無法用名稱相似度合併。發現此類重複時，應先 `python merger.py --dry-run` 確認 Pass 2 能偵測，再正式執行。 → Added `## merger.py` section and Pass 2 rules to SKILL.md.

---
## 2026-04-28 — taiwan_matsuri: geographic filter + dry-run-only fix caused missed events

**Error 1 (initial version):** `_TOKYO_KANTO_KEYWORDS` filter limited scraping to venues matching `東京|スカイツリー|横浜|幕張|千葉|埼玉`. Gunma (群馬), Kumamoto (熊本), Fukuoka (福岡), Nara etc. were silently dropped — even though the project scope is all of Japan.

**Error 2 (fix commit):** The fix commit (`1d3cd1c`, April 26) removed the filter and ran `--dry-run` to confirm both Tokyo and Kumamoto were found. However, **no non-dry-run was executed after the fix.** The newly discovered events (`202603-gunmaota`, `202604-kumamoto`) were never written to DB. They remained missing until a manual run on April 28.

**Fix:** Removed `_TOKYO_KANTO_KEYWORDS` entirely. After confirming with dry-run, ran `python main.py --source taiwan_matsuri` (non-dry-run) to actually write to DB.

**Lesson 1:** Never restrict a scraper's geographic scope to a subset of Japan. The project covers all of Japan（全日本）. If the initial implementation needs a filter for testing, remove it before the first production run.

**Lesson 2:** A dry-run fix commit is incomplete. After removing a scraper bug (especially a filter bug), always follow up with a real run (`python main.py --source <name>`, no `--dry-run`) before the next CI cycle. Otherwise the fix is verified but the data gap persists until the next CI run.

---
## 2026-04-27 — eiga_com: per-theater redesign (3 address extraction bugs)

**Error 1:** `a.more-schedule a[href*='/movie-theater/']` selected the first matching link which was `/movie-theater/{id}/{pref}/{area}/{theater_id}/mail/` (the copy-to-clipboard link), not the theater detail page. `theater_id` was extracted correctly, but `_fetch_theater_address()` fetched the mail page which has no `theater-table`.

**Fix 1:** Use `a.icon.arrow[href*='/movie-theater/']` to get the "all schedule" detail link specifically.

**Lesson 1:** When multiple links share the same `href` pattern (copy/print/all-schedule), always target by CSS class (e.g. `a.icon.arrow`) not by href pattern alone. → Added to `eiga_com-specific` in SKILL.md.

**Error 2:** Page-wide regex `r'東京都[^\s<>]{5,50}'` on the area page matched JS-embedded `東京都"};params_ga4.login_status=...` instead of the actual address.

**Fix 2:** Switched to structured extraction: `table.theater-table th:contains("住所") + td` on the theater detail page.

**Lesson 2:** Never use page-wide address regex on pages with embedded JS/JSON. Use structured HTML selectors (`th`/`td` pairs) for reliable address extraction. → Added to `eiga_com-specific` in SKILL.md.

**Error 3:** `td.get_text()` included `<a>` link text "映画館公式ページ" appended to the address string.

**Fix 3:** Call `a_tag.decompose()` on all `<a>` children inside `td` before `get_text()`.

**Lesson 3:** When a `<td>` contains both text nodes and `<a>` child elements, always decompose unwanted children before `get_text()` to avoid mixing link text into field values. → Added to `eiga_com-specific` in SKILL.md.

---
## 2026-04-27 — taipei_fukuoka / yebizo: scrapers written but not registered or dry-run verified

**Error:** `taipei_fukuoka.py` and `yebizo.py` were fully written (270 and 255 lines respectively, complete `scrape()` + `Event()` return) but were left as untracked files with no entry in `scraper/main.py` → `SCRAPERS`. Running `python main.py --dry-run --source taipei_fukuoka` returned `Unknown source` — the scrapers had never been tested.

**Fix:** Added imports and class instantiations to `main.py`. Ran dry-run for both (exit 0, 3 events each). Then committed all files together.

**Lesson:** Writing a source file without registering it in `main.py` and running a dry-run means the scraper will never execute in CI, and the work is invisible until discovered manually. The commit gate is: **source file + main.py registration + dry-run pass must all be in the same commit.** Never leave an untracked source file without a companion `main.py` edit.

---
## 2026-04-25 — iwafu: Conan events re-appeared (direct URL accessible + card title bypass)

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
