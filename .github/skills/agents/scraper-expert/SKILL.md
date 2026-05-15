---
name: scraper-expert
description: BaseScraper contract, field rules, and source-specific conventions (Peatix, iwafu, cinema, prtimes, fukuoka_now, etc.) for the Scraper Expert agent
applyTo: .github/agents/scraper-expert.agent.md
---

# Scraper Expert Skills

Read this at the start of every session before writing any scraper.

## BaseScraper Contract
- Every scraper must extend `BaseScraper` and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — derive from URL slug or platform ID, never from title or list position.
- Always set `start_date` explicitly. Never fall back silently to the page's publish/update date.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date is found in the page body.
- **`start_date`/`end_date` must use `tzinfo=timezone.utc`**: Never pass JST-aware datetimes (`tzinfo=_JST` / `timezone(timedelta(hours=9))`). Supabase stores datetimes in UTC, so `2026-05-08T00:00:00+09:00` → `2026-05-07T15:00:00+00:00` — the calendar date regresses by one day. Use `datetime(y, m, d, tzinfo=timezone.utc)` to preserve the date. Audit after every scraper fix: `grep -rn "tzinfo=_JST\|tzinfo=JST" scraper/sources/`. (Incidents: Stranger `b7dc34f`, shin_bungeiza `bcb6142`.)
- **Never restrict geographic scope**: The project covers all of Japan（全日本）. Regional keyword filters (e.g. `_TOKYO_KANTO_KEYWORDS`) must never be added to any scraper.
- **After fixing a filter bug**: Run `python main.py --source <name>` (non-dry-run) immediately after the fix. A dry-run confirms the fix works but does NOT write to DB — the data gap remains until the next CI cycle.
- **New scraper checklist** — every new scraper MUST complete all 4 steps, in order:
  1. Create `scraper/sources/<name>.py` extending `BaseScraper`
  2. Register in `scraper/main.py` → `SCRAPERS` list (import + add instance)
  3. **Register in `research_sources`** — insert a row with `status='implemented'`, `scraper_source_name=<key>`, and a valid `url`. Omitting this causes CI to emit `⚠️ scraper(s) NOT registered` warnings every day until fixed.
  4. Verify: `python main.py --dry-run --source <key>` returns events cleanly
- **Sub-events — always look up parent UUID via `get_event_id_by_source()`**: When setting `parent_event_id` on a sub-event, call `database.get_event_id_by_source(source_name, source_id) -> str | None` to retrieve the parent's UUID. **Never assign a source_id string directly** — the column type is UUID and it will cause `invalid input syntax for type uuid` on upsert. Returns `None` on first run (parent not yet in DB); subsequent runs get the correct UUID. Pattern used in `taiwanshi.py` and `ks_cinema.py`. Example:
  ```python
  try:
      from database import get_event_id_by_source as _get_parent_uuid
      parent_uuid = _get_parent_uuid(SOURCE_NAME, parent_source_id)
  except (ImportError, Exception):
      parent_uuid = None
  sub_event = Event(..., parent_event_id=parent_uuid)
  ```

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
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`. Set `location_name` to the captured venue name; for `location_address`, run `_ADDR_RE` on `main_text` first, then fall back to `official_body_text` (returned as 3rd element of `_fetch_official_organizer_info`). Fall back to `card.prefecture` for `location_name` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.
- **`_ADDR_RE` must be city/ward-anchored, not prefecture-anchored**: The prefecture prefix (`東京都|...府|...県`) must be `(?:...)?` optional; `[市区町村]` is the required anchor. Reason: many official event sites omit the prefecture prefix (e.g. `港区芝公園3-2`), so a mandatory prefix silently drops valid addresses. Ref: 屋台湾フェス2026 `location_address=None` incident (2026-05-15).
- **`_fetch_official_organizer_info` returns 3-tuple**: `(organizer, supplemental_text, body_text)`. All callers must unpack 3 values. The `body_text` is used as address fallback when `main_text` has no address. If the official site fetch fails, return `(None, "", "")`.

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

## `name_ja_locked` — protect structured titles from annotator overwrite

**Problem**: Annotator GPT always rewrites `name_ja`, even when the scraper already populated it from a precise structured source field (e.g. academic paper `題目:`, official film programme titles). GPT tends to truncate the subtitle or append generic suffixes like「に関する講演会」.

**Solution**: Set `name_ja_locked=True` on the `Event` when `name_ja` is extracted from a definitive structured field. The annotator will preserve the existing `name_ja` unchanged, while still generating `name_zh`, `name_en`, `description_*`, and `category` normally.

**Language note**: `name_ja` is a field identifier, not a language constraint. A `name_ja_locked` title may legitimately be Chinese (`name_ja="台灣..."`) or English (`name_ja="Taiwan..."`) when the authoritative source uses that language. Do not correct the language.

**When to use**:
- Academic sub-events where `name_ja` = structured `題目:` / paper title with full subtitle (e.g. `taiwanshi` scraper)
- Film sub-events from official programme PDFs with definitive Japanese titles
- Any event where the raw source provides the official Japanese title as a discrete field — not inferred from free-text description

**When NOT to use**:
- Events where the source only provides a vague or generic title and annotator enrichment is desirable

## URL Handling — Relative Path Guard

**Rule**: Every `a["href"]` value that may be a relative path **must** be converted via `urljoin` before storing in `source_url` or `detail_url`.

```python
from urllib.parse import urljoin

# ✅ 正確：無論 href 是相對或絕對路徑，都透過 urljoin 轉換
source_url = urljoin(page.url, a["href"])

# ❌ 錯誤：直接存相對路徑，會產生 ../news/n*.html 等無效 URL
source_url = a["href"]
```

**Incident**: `hakusuisha.py` 的 `../news/n*.html` 直接存入 DB（commit `1b344f7`），導致 10 筆事件 source_url 404。

## BeautifulSoup 多行文字提取 — `separator="\n"`

**Rule**: 任何需要保留行結構的文字提取（排程、場次、地址、時間表等），必須使用 `separator="\n"`。

```python
# ✅ 正確：保留行結構
text = element.get_text(separator="\n", strip=True)

# ❌ 錯誤：連續 inline 元素的文字直接拼接，時間/場次資訊擠在一起
text = element.get_text(strip=True)
```

**Incident**: `gguide_tv.py` 排程文字缺 `separator="\n"`，時間資訊擠在一起（commit `a895e07`）。
- Parent events (usually fine to let annotator improve the title)

**Implementation**:
```python
Event(
    name_ja=r["title"],      # from 題目: field — precise and definitive
    raw_title=r["title"],
    name_ja_locked=True,     # protect from annotator overwrite
    ...
)
```
Requires `supabase/migrations/034_name_ja_locked.sql` to be applied (adds `name_ja_locked boolean default false`).

**DB fix for already-misannotated events** (if annotator has already run):
```python
events = sb.table('events').select('id,name_ja,raw_title').like('source_id','<source>_%_sub%').eq('is_active', True).execute().data
for e in [x for x in events if x['name_ja'] != x['raw_title']]:
    sb.table('events').update({'name_ja': e['raw_title']}).eq('id', e['id']).execute()
```

## raw_description 措辭影響 annotator SINGLE-DAY RULE

**Problem**: Annotator's `_get_end_date()` includes a SINGLE-DAY RULE that detects keywords like `「単日」`, `「開催日」` (singular form) in `raw_description` and forces `end_date = start_date`. Scraper-set multi-day events get collapsed if the description's wording triggers this rule.

**Example**: `starcat_cinema` originally used `raw_description` prefix `"上映日: YYYY年M月D日"` (singular `上映日`). Annotator detected the singular form + checked `start_date != end_date`, then interpreted this as a mismatch and overwrote `end_date = start_date`, collapsing a multi-week film run into a one-day event.

**Solution**: When `end_date > start_date` in your scraper, ensure `raw_description` uses plural or period form:
- ✅ `"上映期間: YYYY年M月D日〜YYYY年M月D日"` (plural period)
- ✅ `"開催期間: YYYY年M月D日～YYYY年M月D日"` (period)
- ✅ `"上映日程: YYYY年M月D日～YYYY年M月D日"` (schedule)
- ❌ `"上映日: YYYY年M月D日"` (singular, triggers SINGLE-DAY RULE)

**Rule**: Before setting multi-day `end_date` in a scraper, audit the `raw_description` prefix to ensure it does NOT use singular keywords that will trigger annotator's SINGLE-DAY RULE. If unsure, check `annotator.py` `_get_end_date()` for the current RULE heuristics.

## Annotator date protection — manual date fix protocol

**Problem**: `annotator.py` lines 581-582 always prefer GPT output over DB values for dates:
```python
"start_date": annotation.get("start_date") or event.get("start_date"),
"end_date": annotation.get("end_date") or event.get("end_date"),
```
If `annotation_status` is reset to `'pending'` after a manual date fix, the next annotator run will overwrite the corrected dates with whatever GPT extracts from `raw_description`.

**Root cause**: GPT extracts dates from `raw_description` free-text. Sources like `tokyoartbeat`, `gnews`, `note_creators` often lack a structured `開催日時:` header — GPT will guess from stray date mentions.

**Safe protocol for manual date correction**:

Option A — Re-annotate (safe):
1. Update `start_date`/`end_date` in DB.
2. Prepend `開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日\n\n` to `raw_description`.
3. Set `annotation_status='pending'` — annotator re-runs with the header as ground truth.

Option B — Skip re-annotation (simplest):
1. Update `start_date`/`end_date` in DB.
2. Set `annotation_status='annotated'` (NOT `'pending'`) — annotator will not touch this event again.

**Never do**: Update `start_date`/`end_date` then set `annotation_status='pending'` WITHOUT updating `raw_description`. The next annotator run will overwrite your fix.

**High-risk sources** (frequently missing `開催日時:` header in `raw_description`):
- `tokyoartbeat` — dates embedded in URL, not description
- `google_news_rss` / `nhk_rss` — article publication date ≠ event date
- `note_creators` — free-prose blog posts

**Incident**: デニス・リン展 (id: `1e375d6c`, 2026-05-02) — GPT output `2026-01-15` overwrote corrected `2026-04-10` because `raw_description` lacked the header. See `history.md` 2026-05-02.

## Annotator location protection — manual address correction rule

**Manual address correction rule**: Before overriding a GPT-generated `location_address`, verify with Google Maps. Venue names containing place names (e.g. `MoN Takanawa`, `WITH HARAJUKU HALL`) do NOT guarantee the postal address matches that place name.

**Why this matters**: GPT correctly recalls well-known venue addresses from training data. An address absent from `raw_description` does NOT mean GPT hallucinated — it may have recalled the correct postal address from knowledge.

**Protocol**:
1. Search the venue name on Google Maps (30 seconds).
2. Confirm the postal address matches what GPT generated.
3. Only override if Google Maps shows a different address.
4. After correcting, set `annotation_status='reviewed'` to lock the event.

**Incident**: MoN Takanawa (ssff events, 2026-05-02) — architect inferred address as `港区高輪4-10-30` from venue name "Takanawa". Correct address is `港区三田3-16-1` (confirmed via Google Maps). GPT's original annotation was correct. See `architect/history.md` 2026-05-02（深夜 4）.

## tokyoartbeat — raw_description must include venue header (Contentful)

**Rule**: When tokyoartbeat scraper is re-enabled, `raw_description` **must** prepend a structured venue header using data from the Contentful API. Without it, annotator GPT will hallucinate well-known venues (e.g. 東京都現代美術館, 森美術館) from training knowledge.

**Incident**: デニス・リン展 (id: `1e375d6c`, 2026-05-02) — GPT annotated venue as 東京都現代美術館 (incorrect); correct venue was Yukikomizutani, TERRADA ART COMPLEX II 1F, 品川区. `raw_description` had only an English artist bio with no location data.

**Contentful API flow**:
```
GET /entries/{event_id}  → fields.venue.sys.id (e.g. "88E9E737") + fields.openingHours
GET /entries/{venue_id}  → fields.fullName, fields.address, fields.closedDays, fields.openingHours
```

**Required header format** (prepend before body text):
```
開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日
会場: {fullName}
住所: {address}
開場時間: {openingHoursOpens}〜{openingHoursCloses}
休廊日: {closedDays}
入場料: {admissionFee}円（0 = 無料）
```

**Why GPT hallucinates**: The annotator prompt contains a LOCATION ADDRESS RULE that says "fill in if you know it". GPT over-confidently applies training knowledge to high-profile venues, even when nothing in `raw_description` confirms the location. The structured header is the only reliable ground truth.


- Empty strings from GPT (`""`) must be treated as `None` — use `_str()` helper that returns `None` for falsy/blank strings. Prevents empty `name_zh`/`name_en` from blocking the `||` fallback chain in `getEventName`.
- Location fields must be stripped of leading label separators — use `_loc()` helper that calls `.lstrip("：；:; \u3000")`. GPT often includes the `会場：` or `場所：` separator as the first character of `location_name`.
- Apply `_loc()` to both `location_name` and `location_address`.
- **`SIMP_RE` / `_SIMP_TO_TRAD` char addition rule (2026-05-01):** Only add a char when its Traditional Chinese / Japanese form is a **different glyph**. Verify each candidate via CC-CEDICT or kanji.jitenon.jp before adding. Counter-example: `亮` is identical in Trad/Simp (`照亮` is valid Traditional) — produced a false positive in `auto_qa.py` dry-run. When adding new chars, update both `annotator.py._SIMP_TO_TRAD` and `auto_qa.py.SIMP_RE`. See `history.md` 2026-05-01.

## Auto-QA findings → `event_reports` queue
- New automated content-quality checks (e.g. `scraper/auto_qa.py`) must write findings into `event_reports` with an `auto_*` prefix in `report_types[]` rather than building a separate admin queue. Both auto-detected and user-submitted reports flow through `/admin/reports` unchanged.
- Dedup against existing pending rows of the same `auto_*` type per `event_id` before insert; also dedup within a single run.
- Current `QA_TYPES` (as of 2026-05-15): `auto_qa_simplified_zh`, `auto_qa_missing_address`, `auto_qa_missing_hours`, `auto_simplified_chinese`, `auto_qa_same_work_duplicate`, `auto_qa_performer_ai_translation_marker`, `auto_qa_performer_multi_value_pollution`, `auto_qa_performer_zh_equals_katakana`. Future checks follow the same `auto_*` prefix convention.
- **performer 系 3 detector の役割**（2026-05-15, commit `c4bd9e1`）：
  - `auto_qa_performer_ai_translation_marker`：movie 事件の `performer_zh/en` に `AI翻譯` / `AI Translation` マーカーが残存 → lookup pipeline が未修正
  - `auto_qa_performer_multi_value_pollution`：`performer` フィールドに区切り文字（`、,，×／/`）が残存 → `performers[]` 分割が未実行
  - `auto_qa_performer_zh_equals_katakana`：`performer_zh` が `performer` のカタカナそのままで未翻訳
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

**`business_hours` — mandatory schedule collection**: Cinema scrapers must actively collect per-day screening times and store them in `business_hours`. Common HTML containers:
- `div.schedule-program` (shin_bungeiza)
- `div.schedule-table` / `table.schedule` (various)
- `dl.showtime` / `ul.times` (single-venue sites)

Combine date header (`<h2>` or `<p.nihon-date>`) with its following schedule block when the HTML separates them. Format: one line per date — `M/D（曜） HH:MM（note）\nM/D（曜） HH:MM`. **Do NOT return `None` for `business_hours` when schedule data is visually present on the page.** Missing screening times is always a scraper bug.

**Incident**: shin_bungeiza (commit `1ffb98e`) — `_parse_nihon_date_only()` collected date headers from `<h2>` but silently omitted the adjacent `<div class="schedule-program">` elements containing actual screening times.

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
- **`_scraper_key()` naming rule**: `main.py`'s `_scraper_key()` splits class names on CamelCase boundaries (`LivePocketScraper` → `live_pocket`). The class `SOURCE_NAME` constant must match exactly. Name the class to match: `LivepocketScraper` (not `LivePocketScraper`) so `_scraper_key()` produces `livepocket`.

## Debugging — scraper_runs diagnostics

**When checking if a scraper is running, always derive the exact `scraper_runs.source` key from `_scraper_key()` — never guess from memory.**

```bash
cd scraper && python3 -c "
import sys; sys.path.insert(0, '.')
from main import SCRAPERS, _scraper_key
for s in SCRAPERS: print(_scraper_key(s))
" | grep <partial>
```

Common traps where intuition fails:
| Class name | Actual key |
|---|---|
| `CineMarineScraper` | `cine_marine` (NOT `cinemarine`) |
| `MoonRomanticScraper` | `moon_romantic` (NOT `moonromantic`) |
| `TiffJpScraper` | `tiff_jp` (NOT `tiff`) |
| `TokyoArtBeatScraper` | `tokyo_art_beat` (NOT `tokyoartbeat`) |

**Check failure reason from DB** (commit `7e9f617`: `notes` now contains `"ExceptionType: message"`):
```python
sb.table('scraper_runs').select('ran_at,notes') \
  .eq('source', '<key>').eq('success', False) \
  .order('ran_at', desc=True).limit(5).execute()
```

**0 events ≠ not running**: `events_processed=0` with `success=True` means the scraper ran but found no Taiwan events (normal for `tokyo_city_i`, `tokyo_now` outside event season). Only `success=False` indicates a failure.



`scraper/movie_title_lookup.py` provides `lookup_movie_titles(name_ja) → (name_zh, name_en)` via eiga.com search.

- **Always call before constructing `Event()`** in cinema scrapers: `name_zh, name_en = lookup_movie_titles(title)`.
- **In-memory cache**: `_cache` deduplicates requests within a single scraper run. No DB writes.
- **Silent failure**: returns `(None, None)` on any error — never raises, never breaks scrapers.
- **Annotator fallback**: GPT-4o-mini still provides `name_zh`/`name_en` for events where lookup returns `(None, None)`.
- **Annotator enrichment**: `annotator.py --enrich-movie-titles` retroactively fills NULL `name_zh`/`name_en` fields for existing `movie` events. Only patches NULL fields — never overwrites existing values. Runs after `--fix-reviewed` step in `scraper.yml`.
- **Rate limit**: `LOOKUP_DELAY_SEC = 1.0` between requests. Do not lower.
- **Scope**: cinema scrapers only (category contains `"movie"`). Do not use for non-film events.

### Adoption status (as of 2026-05-02)

| Scraper | `lookup_movie_titles` | Weekly schedule (`business_hours`) |
|---|---|---|
| `cinemart_shinjuku` | ✅ | ✅ (`_parse_schedule_page` via cineticket.jp) |
| `ks_cinema` | ✅ | ✅ (`_parse_schedule_first_last`) |
| `cinemarine` | ✅ | ❌ (no public schedule URL found) |
| `cineswitch_ginza` | ✅ | ❌ |
| `morc_asagaya` | ✅ | ❌ |
| `shin_bungeiza` | ✅ | ✅ (`_parse_nihon_date_only` + `schedule-program` div, commit `1ffb98e`) |
| `uplink_cinema` | ✅ | ❌ |
| `human_trust_cinema` | ✅ | ❌ |
| `eurospace` | ✅ (added 2026-05-02) | ❌ |
| `tokyo_filmex` | ❌ (festival; title in multiple languages already) | ❌ (annual) |
| `ssff` | ❌ (English titles primary) | ❌ (festival) |
| `oaff` | ❌ (festival) | ❌ (annual) |

**When adding a new cinema scraper**: always add `from movie_title_lookup import lookup_movie_titles` and call `lookup_movie_titles(title)` before `Event()`. Update this table.

## person_name_lookup — multilingual person names

`scraper/person_name_lookup.py` provides person name lookup via eiga.com + zh/ja.wikipedia for **all events** (not just movies).

- **Triggered by**: `python annotator.py --enrich-person-names` (runs in CI after `--enrich-movie-titles`)
- **Target scope**: ALL events where `annotation_status != 'reviewed'` and `source_name != 'eiga_com'`
- **Structural fields sync (fixed 2026-05-07)**: `enrich_person_names()` updates `performers_en`, `performers_zh`, `director_zh`, `director_en` in addition to `description_zh/en`. Cross-reference maps (`zh_to_info`, `ja_to_info`) propagate results across fields. Updates apply only when the target field is null, empty, or contains an AI-translation marker. **Never implement a description-only enrich without also updating structural fields** — mismatched `performers_en=['中文名']` or `director_zh='幻覚音譯'` survive re-annotation because annotator's `_ai_or_existing()` preserves non-null DB values.
- **Two pipelines**:
  - **Movie events**: `lookup_person_names(title)` → eiga.com movie page → structured cast/crew list → Wikipedia (`strict=False`)
  - **Non-movie events**: `extract_katakana_names(text)` → regex extracts ・-separated katakana names → `lookup_single_person(name)` → eiga.com person search + Wikipedia (`strict=True`)
- **strict mode**: Non-movie lookups require zh interlanguage link (ja.wikipedia) or person-keyword match (zh.wikipedia) to prevent false positives (e.g. `リン・インジュ` → `安永亜季` was a false positive without strict mode)
- **Noise filtering**: max 3 ・-parts, max 7 chars/part, noise suffix exclusion (ホテル, センター, etc.)
- **Output fields**:
  - `description_zh`: GPT-corrected phonetic person names (replaces katakana-derived wrong translations with correct 中文 names)
  - `description_en`: direct katakana → English replacement
- **Silent failure**: returns empty dict / None on any error — never raises, never breaks the pipeline
- **In CI**: Step order is `--fix-reviewed` → `--enrich-movie-titles` → `--enrich-person-names` → `summarize_run.py`
- **Rule**: If you implement a new enrichment function in `annotator.py`, always add the corresponding CI step to `.github/workflows/scraper.yml` — implementation without CI registration means it never runs in production.

## prtimes-specific

- **API endpoint**: `GET https://prtimes.jp/api/keyword_search.php/search?keyword=<kw>&page=<N>&limit=40` — internal Next.js API, returns JSON. No Playwright needed.
- **No geographic restriction**: `_SEARCH_KEYWORDS` must NEVER contain city names (東京, 大阪, etc.). Project scope is all of Japan. Bad example: `"台湾 イベント 東京"`. Correct: `"台湾 イベント"`.
- **Event keyword filter**: title must contain a Taiwan KW AND an event-type KW (`_EVENT_KW`). PR releases about business/export activities are excluded by `_TAIWAN_BASED_TITLE_RE`.
- **Press release ≠ event**: Extract the actual event date from PR body (`開催日時:` / `日時:` labels), NOT the PR release date. Fallback to release date only if no event date found in body.
- **⚠️ Fallback date risks hallucination**: If start_date falls back to the PR release date AND raw_description lacks a `開催日時:` header, the annotator will also fail to extract the real event date — GPT cannot distinguish PR release date from event date in unstructured body text. Always add a `プレスリリース発信日: YYYY年MM月DD日\n開催日時: (要本文確認)\n\n` note when extracting event dates from PR body. Incident: `e45d4022`（台湾＆沖縄フードイベント, 2026-05-02）— `start_date=2026-02-25`（release date）instead of `2026-03-11`（actual event）.
- **LOOKBACK_DAYS = 90**: Skip PRs older than 90 days. PR TIMES has no end-of-event concept — ~~rely on `archive_ended_events` in main pipeline~~ (archiver deleted 2026-05-06; stale events must be deactivated manually via Admin UI).
- **Venue extraction**: `_VENUE_LABELS` regex on body text (会場: / 開催場所: etc.). Venue often in second or third paragraph.
- **`_NEWS_SOURCES` member**: `prtimes` participates in merger.py Pass 2 (date-range + location-overlap), NOT Pass 1 (name similarity). Article-style PR titles don't match event names by similarity.
- **Dry-run validation**: Run `python main.py --dry-run --source prtimes 2>&1 > /tmp/prtimes_out.txt` — expect 5–30 events per run depending on Taiwan events in the last 90 days.

## Online events — location_name must be set by scraper

- **Do NOT leave `location_name=None` for online events**: Annotator GPT does not reliably identify online events and set `location_name='オンライン'` — it depends on clear textual cues in `raw_description`. If the scraper can determine the event is online (keywords: `オンライン`、`オンデマンド`、`ウェビナー`、`ライブ配信`、`Zoom`、`YouTube`、`配信`), the scraper must set `location_name` directly.
- **Online event type vocabulary**:
  - `オンライン（ライブ配信）` — live stream (同期)
  - `オンライン（オンデマンド）` — on-demand replay (非同期)
  - `オンライン（ウェビナー）` — webinar platform (Zoom / Teams)
  - `オンライン` — generic fallback when type is unclear
- **Sources with frequent online events**: `ide_jetro` (on-demand courses), `connpass`, `doorkeeper`, `jposa_ja`. Incidents: `86efda2a`（オンデマンド講座, ide_jetro, 2026-05-02）— `location_name=null` needed manual DB fix.

## fukuoka_now-specific

- **Static HTML, no Playwright**: WordPress site, `requests` + BeautifulSoup only.
- **Seasonal pattern**: Only one confirmed annual Taiwan event — 台湾祭 in 福岡 (Jan/Feb). 0 dry-run events during spring–winter is **correct** — not a bug.
- **source_id**: `fukuoka_now_{slug}` where slug = `url.rstrip('/').split('/')[-1]`.
- **Detail page always preferred for dates**: `time[datetime]` attribute gives ISO dates. Listing page also has dates, but detail page has both start and end dates.
- **Venue**: No structured `場所:` label. Extract via line-by-line keyword match: "City Hall", "Fureai", "Tenjin", "Canal", "ACROS", "Hakata", "博多", "天神".
- **Pagination**: `/en/event/` (page 1), `/en/event/page/{N}/` (pages 2+). Stop on HTTP 404 or empty `li.c-page-sub__guide-item`.

## gguide_tv-specific
- **`location_name` must always be `'電視頻道'`**: Set this fixed canonical value regardless of the actual broadcast channel (tvk1, BS朝日1, etc.). Raw channel names stored as `location_name` cause false positives in the `other_japan` geographic filter and the quality page address check.
- **`location_address` must be `None`**: TV programmes have no physical address. Never attempt to fill `location_address`.
- **No address enrichment**: `enrich_addresses.py` must skip gguide_tv events. The `--skip-source gguide_tv` flag (or equivalent guard in the script) should prevent GPT from generating hallucinated addresses for broadcast channels.
- **DB normalization**: If older records contain raw channel names as `location_name`, run a targeted UPDATE: `UPDATE events SET location_name = '電視頻道' WHERE source_name = 'gguide_tv'` to normalize them before the filter exclusion takes effect.


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

After every new source or bug fix, complete **all** items below **before `git add`**. Skipping any item is a protocol violation.

### New source — mandatory checklist

| # | Item | File / Location |
|---|------|-----------------|
| 1 | `import` added | `scraper/main.py` |
| 2 | `SCRAPERS` entry added | `scraper/main.py` |
| 3 | SCRAPERS audit passes (zero UNREGISTERED) | run audit command |
| 4 | Per-source `SKILL.md` created | `.github/skills/sources/<source_name>/SKILL.md` |
| 5 | Per-source `history.md` created | `.github/skills/sources/<source_name>/history.md` |
| 6 | `## <source_name>-specific` section added | `.github/skills/agents/scraper-expert/SKILL.md` |
| 7 | `research_sources.status = 'implemented'` | Supabase DB |
| 8 | `research_sources.scraper_source_name = '<key>'` | Supabase DB |

> **Root cause of the ArtistcafeScraper incident (2026-05-05)**: The scraper file was created, committed, and even archived as "POC complete", but items 1–2 (import + SCRAPERS) were never done in the same session. Result: CI silently ignored the scraper for 3+ days. **Items 1–2 must be done atomically with the source file in the same commit.**

### Bug fix — mandatory checklist

| # | Item | File / Location |
|---|------|-----------------|
| 1 | History entry prepended | `.github/skills/agents/scraper-expert/history.md` |
| 2 | History entry prepended (source-specific) | `.github/skills/sources/<source_name>/history.md` |
| 3 | Universal rule added/updated | `scraper-expert/SKILL.md` (if lesson generalizes) |
| 4 | Source-specific rule added/updated | per-source `SKILL.md` (if lesson is specific) |

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

## artistcafe-specific

- **`?keyword=` ignored**: artistcafe.jp ignores `?keyword=台湾` entirely — returns all events regardless. Verified 2026-05-05 by comparing results with/without param (same 12 cards).
- **Taiwan filter is in-scraper**: `_is_taiwan(title + article_text)` must be checked after visiting each detail page. Without this, 8-14/12-17 non-Taiwan events are collected.
- **Use `article` selector for description**: `body.inner_text()` captures navigation headers. `DETAIL_CONTENT_SELECTOR = "article"` excludes nav/header.
- **Verify `?keyword=` on any new site**: Before deploying an auto-generated scraper that relies on URL keyword filtering, compare `?keyword=...` vs no-keyword response. If card counts are equal, the param is ignored.

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

## bookandbeer-specific

- **`?keyword=台湾` URL parameter is silently ignored by the server**: All events are returned regardless of keyword value. A dry-run WITHOUT keyword param returns the same event count. **Always use client-side `_is_taiwan_relevant()` filter.**
- **Author bio false positive**: 台湾大学・淡江大学 etc. may appear in `書き手` (author profile) but NOT relate to event content. Use `_AUTHOR_BIO_RE` to strip university-name occurrences before keyword count:
  ```python
  _AUTHOR_BIO_RE = re.compile(r'台湾[・・]?(?:大学|淡江|国立|師範|政治|成功|交通|中山|清華)')
  ```
- **Filter logic** (title-first, then description excerpt):
  1. Title contains any Taiwan keyword → relevant
  2. Description first 500 chars has ≥ 2 keyword occurrences AND after stripping university patterns at least one remains → relevant
  3. Otherwise → skip

## tokyoartbeat — Contentful placeholder dates (month == 1)

- **Contentful uses entire January as fiscal-year placeholder for series exhibitions**: Both `YYYY-01-01` and `YYYY-01-15` (and any `YYYY-01-xx`) have been observed as placeholders. The guard condition must be `start_date.month == 1`, **NOT** `start_date.day == 1`.
- **Slug fallback**: When `start_date.month == 1`, extract the real date from the Contentful URL slug (`/YYYY-MM-DD` suffix at the end of `fields.slug`).
- **Verification**: After each dry-run, print `(name, start_date, slug)` for all events and confirm no January start dates remain.

## google_news_rss — article fetch failure handling

- **RSS snippet must NOT be used as start_date fallback**: If `article_text` is None (HTTP error or Playwright timeout), set `start_date = None` — do NOT call `_extract_start_date(description_plain, pub_date)`. The snippet is too short for reliable date parsing.
  ```python
  # CORRECT
  start_date = _extract_start_date(article_text, pub_date) if article_text else None
  ```
- **`start_date = None` is handled by annotator's universal year-anchor**: `（記事配信日: YYYY-MM-DD）` prefix injected into raw_description ensures year correctness even when date cannot be extracted from text.
- **health_check `gnews_suspect` alert**: Only trigger for `start_date < today` (past-dated unreliable dates). Future-dated gnews events are not yet user-visible and do not require an alert.
## performer / performers[] \u6ce8\u89e3\u898f\u5247

Annotator \u5c0d\u8868\u6f14\u8005\u6b04\u4f4d\u7684\u898f\u5247\uff08migration 053/054\uff09\uff1a

- **`performer TEXT`**\uff1a\u5c0d\u4e3b\u8981\u5d50\u8cfd\u8005\uff0f\u8b1b\u8005\uff0f\u827d\u8853\u5bb6\u7684\u55ae\u4e00\u65e5\u6587\u539f\u540d\u3002
- **`performers TEXT[]`**\uff1a\u6240\u6709\u5177\u540d\u8868\u6f14\u8005\uff0f\u767c\u8868\u8005\u7684\u9663\u5217\u3002\u5b78\u8853\u7814\u8a0e\u6703\u5fc5\u9808\u5305\u542b\u5168\u90e8\u5177\u540d\u767c\u8868\u8005\uff08\u767c\u8868\u8005\uff0f\u5831\u544a\u8005\uff0f\u767b\u58c7\u8005\uff09\u3002
- **`performer_zh / performer_en`**\uff1aGPT \u586b\u5165\u7684\u5404\u8a9e\u8a00\u540d\u7a31\u3002\u82e5\u539f\u6587\u672a\u660e\u793a\u5c0d\u61c9\u8a9e\u8a00\u540d\u7a31\uff0c\u5fc5\u9808\u9644\u52a0\u300c\uff08AI\u7ffb\u8b6f\uff09\u300d\uff08\u5982 `\u9ec3\u4ee5\u6587\uff08AI\u7ffb\u8b6f\uff09`\uff09\u3002
- **Scraper \u5c64\u7528\u4e0d\u5230**\uff1a`performer` \u7531 annotator GPT \u5c64\u5585\u5165\uff0c\u4e0d\u7531 scraper \u8a2d\u5b9a\u3002Scraper \u53ea\u9700\u6b63\u78ba\u5beb\u5165 `raw_description`\uff08\u542b\u8b1b\u8005\u59d3\u540d\u3001\u8077\u7a31\u3001\u6572\u8a9e\u5f62\u5f0f\uff09\uff0c\u5f8c\u7e8c pipeline \u81ea\u52d5\u5225\u53d6\u3002