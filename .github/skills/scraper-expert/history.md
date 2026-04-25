# Scraper Expert Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 — confirm-report.ts stranded events + irrelevant false positives documented

**問題 1: 87 個事件被卡死 (stranded)**
`confirm-report.ts` 在三種確認路徑中誤設 `is_active=false + annotation_status=pending`：
- wrongCategory（無提供正確分類時）
- wrongDetails（需重新標記時）
- irrelevant（標記不相關時）

由於 annotator 查詢條件是 `is_active=True AND pending`，這些事件永遠不會被處理。

**修正:**
1. `confirm-report.ts` wrongCategory/wrongDetails 路徑: 移除 `is_active=false`，只設 `annotation_status=pending`
2. `confirm-report.ts` irrelevant 路徑: 改設 `annotation_status=annotated`（不是 pending）
3. 立即補救: 重新啟用 87 個卡死事件（57 個套用人工修正分類並設 annotated；29 個不相關重新關閉）

**問題 2: 57 個有人工修正的事件分類會被 annotator 覆寫**
`annotator.py` 直接以 AI 預測的分類覆寫 `category` 欄位，不看 `category_corrections` 表的人工修正。
`_PROTECTED_FIELDS` 只保護 scraper upsert，不保護 annotator 重新標記。

**修正:**
1. `annotator.py`: 在 AI 預測分類後，立即用 `human_category_map` 覆蓋（從 `category_corrections` 表全量讀取）
2. 立即補救: 直接把 57 個有修正紀錄的 pending 事件套用正確分類並設為 `annotated`

**問題 3: 36 個 irrelevant 報告模式整理（詳見 SKILL.md `Irrelevant event patterns` 章節）**
- Peatix: 活字設計系列、和芬折衷對話、人生計劃研討會、日本廚師食譜影片、自助講座
- eplus: KNOCK OUT MONKEY 等日本樂團、日本音樂節
- iwafu: 日本傳統工藝祭、日本神社花祭、スプリング・ジャパン（日本航空公司）

**教訓:**
- `is_active=false` 與 `annotation_status=pending` 絕對不能同時設定
- 正確規則: `is_active=false → status=annotated`；`status=pending → is_active=true`
- annotator 必須在 AI 預測後套用 `category_corrections` 人工修正，不可覆寫

---
## 2026-04-26 — category not protected: human corrections overwritten by scraper

**問題:** `category` 欄位不在 `_PROTECTED_FIELDS`，因此每次爬蟲執行都會以 AI 預測值覆寫人工修正的分類。分析 65 筆 `category_corrections` 紀錄後發現明顯的 AI 系統性偏差。

**修正:**
1. `database.py`: 將 `category` 加入 `_PROTECTED_FIELDS` — 已標記事件的分類永久保留，不被爬蟲覆寫。
2. `SKILL.md`: 新增 `AI category classification — known biases` 區段，記錄從 65 筆 corrections 分析出的系統性偏差。

**65 筆 corrections 的模式分析:**

AI 最常漏掉 (under-predict):
- `lecture` (+27) — 幾乎所有有 talk/panel 的活動都需要
- `geopolitics` (+16) — 台灣政治、歷史、移民政策議題
- `history` (+14) — 歷史人物（李登輝等）、殖民時代、戰後台灣
- `books_media` (+12) — 書名在 『』 中的活動
- `senses` (+9) — 藝術展覽
- `lifestyle_food` (+7) — 台灣茶會、料理活動
- `movie` (+6) — 上映会常被遺漏（只標了 `lecture`）
- `workshop` (+6) — 體驗型/手作活動

AI 最常過度預測 (over-predict):
- `taiwan_japan` (-18) — 被誤用為「這是台灣相關活動」，應限於日台雙邊交流主題
- `academic` (-4) — 不是所有講座都是學術研究
- `performing_arts` (-4) — 只限現場表演；亞洲巡演不算

**教訓:**
- `category` 必須是 `_PROTECTED_FIELDS` 的一部分。
- few-shot examples (category_corrections) 是改善 AI 分類的主要機制，但在標記完成後保護才是根本。
- `taiwan_japan` 是最常見的誤用分類，需在 annotator prompt 明確定義。

---## 2026-04-26 — DB 「回到過去」：爬蟲 upsert 覆寫手動修正的欄位

**現象:** 全部爬蟲執行後，手動修正的 `location_name`、`location_address`、`name_ja` 等欄位被被覆寫為爬蟲新抜取的原始值。用戶需要重新對這些活動執行標註程序。

**根本原因:** `database.py` 的 `_event_to_row()` 包含 `location_name`、`location_address`、`name_ja`、`raw_description` 等欄位。`upsert_events()` 對所有 `is_active=True` 的事件執行 `ON CONFLICT DO UPDATE`，完全覆寫這些欄位，不論 `annotation_status` 是否為 `annotated`。

**被覆寫的欄位:** `name_ja`, `raw_title`, `raw_description`, `location_name`, `location_address`, `category` (部分保護), `start_date`, `end_date`, `is_paid`, `source_url`

**安全手動修正的欄位（爬蟲不會覆寫）:** `annotation_status`, `name_zh/en`, `description_ja/zh/en`, `location_name_zh/en`, `location_address_zh/en`, `selection_reason`

**教訓:**
- 手動修正 `location_name`、`location_address`、`name_ja` 等欄位，下次爬蟲執行後就會被覆寫。**永久修正請更改爬蟲抽取邏輯，而不是直接修改 DB。**
- 第一次遇到這種情況時，先將 DB patch 當临時應急措施，並同步更改爬蟲將未來茇取的資料就是正確的。
- `is_active=False` 的事件有保護（upsert 完全跳過），但 `is_active=True` 沒有任何保護。
→ 新增 `database.py upsert — which fields get overwritten` 區段到 SKILL.md。

---
## 2026-04-26 — peatix: 桃園区民活動センター triggered 桃園 keyword match

**Error:** 2 peatix events ("スピーチ勉強会" speech practice sessions) were scraped because their venue was 桃園区民活動センター (Nakano, Tokyo). `桃園` is in `TAIWAN_KEYWORDS` as Taoyuan (Taiwan city), but here it refers to a Tokyo neighborhood. The events have zero Taiwan content — the annotator GPT hallucinated a Taiwan-Japan exchange justification in `selection_reason`.

**Fix:**
1. `peatix.py`: Added `_TAIWAN_KW_NO_TAOYUAN` guard (same pattern as `台東区` guard): skip if `桃園区` in page text and no other Taiwan keyword matches.
2. Hard deleted 2 existing DB records (source_ids: `427efc7af975bcb8`, `90ef94417ec7daa7`).

**Lesson:**
- Any Taiwan city/region name that shares characters with a Tokyo ward/neighborhood requires a guard. Same mechanism as `台東区`.
- The annotator GPT will hallucinate Taiwan relevance even when none exists — the scraper keyword filter is the last line of defense before DB insertion.
- When adding a new Taiwan place name to `TAIWAN_KEYWORDS`, check if the same string appears as a Tokyo neighborhood or ward name.
→ Added `桃園区 false positive` and `General rule` to SKILL.md (`Peatix-specific`).

---
## 2026-04-26 — eplus/iwafu: 神韻 (Shen Yun) appeared as Taiwan events

**Error:** 13 events titled "神韻2026日本公演" were scraped by eplus (12 sessions) and iwafu (1), and annotated as Taiwan-related. 神韻 is a US-based Falun Gong performing arts group; it mentions 台湾 only because Japan tour venues include Taipei. It has **no connection to Taiwanese culture**.

**Fix:**
1. `eplus.py`: Added `_BLOCKED_TITLE_RE = re.compile(r"神韻")` — checked on card title before Event is appended.
2. `iwafu.py`: Added `神韻` to `_BLOCKED_SERIES` — checked on both card title (pre-load) and h1 title (post-load).
3. Hard deleted all 13 existing records from DB.

**Lesson:**
- Shen Yun (神韻) is a well-known false positive. It tours Japan extensively, searches for 台湾 return its events, but it is NOT a Taiwan-cultural event.
- eplus has no detail-page load. All filtering must happen at card-parse time via `_BLOCKED_TITLE_RE`.
- When a non-Taiwan series appears in multiple sources, block it in ALL affected scrapers simultaneously.
→ Added `eplus-specific` section and updated `iwafu-specific` in SKILL.md.

---
## 2026-04-26 — waseda_taiwan: DOW removal collapses date-time separator

**Error:** `YYYY/M/DD（土）HH:MM` after `re.sub(..., "", raw)` produced `YYYY/M/DDHH:MM` — date parse failed with "Invalid date".

**Fix:** Replace DOW annotations with `" "` (space) instead of `""` (empty string).

**Lesson:** Any DOW removal regex must preserve spacing between adjacent date and time digits. Use `re.sub(r"[（(][月火水木金土日・祝]+[）)]", " ", raw)`. → Added to SKILL.md (`waseda_taiwan-specific` and generalized rule).

---
## 2026-04-26 — jats: Stop labels don't work for special chars without trailing delimiter

**Error:** `location_name` captured the full venue text including a form URL (`■参加登録フォーム https://...`) because the stop pattern `\s+■[\s：:]` didn't match `\s+■参加`.

**Fix:** For single-char / short special-char stop labels (`■`, `●`, `※`, `http`), use `\s+CHAR` without requiring a trailing space/colon.

**Lesson:** `_extract_after_label` stop labels need two modes: (1) word stops → `\s+WORD[\s：:]`, (2) char stops → `\s+CHAR`. → Added to SKILL.md (`jats-specific`).

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
