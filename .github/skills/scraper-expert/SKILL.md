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
- **SCRAPERS registration**: Every new scraper class must be registered in `SCRAPERS` in `main.py` in the **same commit** it is created. Audit command:
  ```bash
  cd scraper && python3 -c "
  import re, glob
  registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
  for f in glob.glob('sources/*.py'):
      c = open(f).read()
      m = re.search(r'class (\w+Scraper)\b', c)
      if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
          print('UNREGISTERED:', m.group(1), f)
  "
  ```
- **Run SCRAPERS audit after ANY `main.py` change**: Not only when adding new scrapers. Any refactor or chore commit touching `main.py` risks silently dropping registrations. Run the audit and confirm "ALL CLEAR" before `git push`.
- **Source removal procedure (3-step atomically)**: When removing a scraper entirely:
  1. Remove `import` from `main.py`
  2. Remove `ScrapeClass()` from `SCRAPERS` in `main.py`
  3. Hard delete existing DB records: `sb.table('events').delete().eq('source_name', '<source_name>').execute()`
  All 3 steps must happen in the same session. Missing step 3 leaves stale data visible in production.
- **Identify source_name from a problem event**: Never guess from the event title — always query the DB:
  ```python
  sb.table('events').select('source_name,source_id,source_url').eq('id', '<uuid>').execute()
  ```
- **`start_date` / `end_date` must be `datetime.datetime`, NOT `datetime.date`**: `dedup_events` in `base.py` calls `.date()` on `start_date`. Passing a bare `date` object raises `AttributeError: 'datetime.date' object has no attribute 'date'`. Always use `datetime(y, m, d)` when constructing dates in scrapers.
- **`category` must be `list[str]`, NOT a bare string**: The DB column is `text[]`. Passing `category="movie"` raises `malformed array literal` at write time. Always use `category=["movie"]`. This fails silently at compile time and only surfaces on DB upsert.
- **`requests.Session()` must always mount HTTPAdapter with Retry**: Any scraper that creates a `requests.Session()` must attach a retry adapter in `__init__`. Without it, a single transient network blip from GitHub Actions runners raises `Max retries exceeded` and triggers Sentry — even when the target site is healthy. Required pattern:
  ```python
  from requests.adapters import HTTPAdapter
  from urllib3.util.retry import Retry

  _retry = Retry(
      total=3,
      backoff_factor=2,
      status_forcelist=[429, 500, 502, 503, 504],
      raise_on_status=False,
  )
  self._session.mount("https://", HTTPAdapter(max_retries=_retry))
  self._session.mount("http://", HTTPAdapter(max_retries=_retry))
  ```
  Backoff: 2s → 4s → 8s. Mount both `https://` and `http://`.

## Peatix-specific
- Blocked organizer patterns live in `BLOCKED_ORGANIZER_PATTERNS` in `peatix.py` — always check before adding new title-based blocks.
- 台東区 false positive: `台東` in `TAIWAN_KEYWORDS` can match the Tokyo ward 台東区. Use `_TAIWAN_KW_NO_TAITO` guard list.
- **Three-layer organizer architecture**:
  - Layer 1: keyword search (`peatix.com/search?q=...`)
  - Layer 2: hardcoded organizer list in `_ORGANIZERS` — **never remove**; serves as backup if DB changes
  - Layer 3: DB-driven dynamic load via `_load_db_organizers()` — queries `research_sources WHERE agent_category='peatix_organizer' AND status='implemented'`
- **Layer 3 expansion rule**: When extending Layer 3 to a new platform, use a platform-specific `agent_category` (e.g. `peatix_organizer`). Do NOT reuse `note_creator` or generic names.
- **Group page scraping**: `_scrape_group_events()` fetches `peatix.com/group/{group_id}/events`; `group_id` extracted from `source_profile.group_id` or URL path.
- **Validation**: `python discovery_accounts.py --dry-run --slot 3` to verify Peatix slot without DB writes.

## iwafu-specific
- **Global-tour false positive**: If description contains `台湾など世界各地` / `全国各地.*台湾` etc., the event is a nationwide/global tour where Taiwan is just one stop. Reject it — it is NOT a Taiwan-themed event. The `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py` implements this guard.
- **Title-level block**: Known IP series (e.g. `リアル脱出ゲーム×名探偵コナン`) must be blocked by `_BLOCKED_TITLE_PATTERNS` in `_scrape_detail` **before** the page load — this catches all tour stops as new source_ids appear. Add new entries here when a series is confirmed non-Taiwan-themed.
- **Permanent IP series block**: For series where ALL events are non-Taiwan-themed (e.g. `名探偵コナン`), add the IP name to `_BLOCKED_SERIES`. Checked on BOTH card title (pre-load, fast-reject) AND h1 title (post-load). Card titles from search results can be truncated, so the pre-load check alone is not sufficient.
- Taiwan relevance criterion: Taiwan must be the **theme or primary focus**, not just one venue on a multi-city tour.
- **After adding a scraper filter, always audit the DB**: run `ilike("raw_title", "%keyword%")` to find existing records that should also be deactivated. The filter only prevents future inserts.
- **Hard delete vs deactivation**: If an IP series is confirmed permanently non-Taiwan-themed, hard delete (`table.delete().eq("id", eid)`) rather than just deactivating. Deactivated events remain accessible via direct URL unless the event page also checks `is_active`.
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`. Set BOTH `location_name` and `location_address` to the captured value. Fall back to `card.prefecture` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.

## Venue / live house scrapers — management post blocklist

For scrapers on **live houses / venue sites** (e.g. moonromantic), the site publishes both public event listings and **internal venue-management posts** (rental announcements, wedding inquiries, system maintenance). These are NEVER Taiwan-related.

- **Always add `_BLOCKED_POST_PATTERNS`** at the module level for known management post types.
- Apply the block **BEFORE** the Taiwan keyword check — it avoids loading the detail page unnecessarily.
- Apply **twice**: once on `page_text` first-line (fast-reject) and once on the confirmed `title` (second-pass, catches nav-renders-first edge cases).
- Known patterns to always block for live venue sites:
  - `RENTAL` / `PRIVATE RENTAL` / `RENT` (venue hire)
  - `場所貸し` / `会場貸し` (Japanese venue rental)
  - `WEDDING` (if venue offers wedding venue hire)
- Example:
  ```python
  _BLOCKED_POST_PATTERNS = re.compile(
      r"\bRENTAL\b|PRIVATE\s+RENTAL|\bRENT\b|場所貸し|会場貸し",
      re.IGNORECASE,
  )
  ```

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

## WordPress mixed-content sites (e.g. go_taiwan)

For WordPress sites that mix Japan-hosted and Taiwan-hosted events, apply all three patterns:

**1. Listing-page 90-day pre-filter**
Before fetching any article detail, parse `<time datetime="...">` on the listing page.
Skip articles older than 90 days; stop paginating when an entire page is older than 90 days.
This reduces HTTP requests 30–40× (e.g. 220 → 6 fetches on go-taiwan.net).

**2. Three-pass Japan-event filter — apply in this order**
```python
def _is_japan_event(title: str, body: str) -> bool:
    if TAIWAN_ONLY_PATTERNS.search(title):   # Stage 1: title clearly Taiwan-only
        return False
    if TAIWAN_VENUE_KW.search(body):         # Stage 2: venue explicitly in Taiwan
        return False
    return bool(JAPAN_LOCATION_KW.search(body))  # Stage 3: Japan city present
```
**Critical**: Stage 2 (Taiwan-venue exclusion) MUST come before Stage 3 (Japan-keyword check).
Reversing the order causes false positives: a Taiwan-held event mentioning Japanese travel companies
(e.g. 近畿日本ツーリスト → triggers 近畿 keyword) passes Stage 3 before Stage 2 can reject it.

**3. Date extraction priority ladder for Japanese WordPress**
Post body typically starts with the article publish date — never take the first date naively:
1. `日時：` labeled date range
2. Weekday-annotated range (`YYYY年M月D日（曜日）〜D日（曜日）`)
3. Any labeled single date
4. Weekday-annotated single date
5. Plain date range
6. Last resort: first plain date in body (high risk of matching the publish date)

Use this ladder when the source is a Japanese WordPress blog/CMS.

## transit_store-specific
- **Shopify JSON API**: `/collections/event/products.json?limit=20&page={n}` — paginate until empty page.
- Taiwan filter: check `title` and `body_html` against Taiwan keywords.
- Date extraction: `日程[：:][^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日` regex on `body_html`.
- `source_id`: `transit_store_{product.handle}` — handle is stable across runs.

## gguide_tv-specific
- **schedule_str has two formats** — must handle both:
  - 單行：`"12:00 テレ東"` → 正規表達式可直接抓 `HH:MM <channel>`
  - 多行：`"23:45\n-\n0:00 歌謡ポップス"` → 第一行是開始時間，第二行固定是 `-`，第三行是 `H:MM <channel>`
- **`_parse_schedule()` 回傳值**：`(datetime, channel, end_time_str | None)`，三元組。單行格式 `end_time_str=None`。
- **多行格式解析規則**：
  ```python
  lines = schedule_str.strip().splitlines()
  if len(lines) >= 3 and lines[1].strip() == "-":
      start_hhmm = lines[0].strip()   # e.g. "23:45"
      end_channel = lines[2].strip()  # e.g. "0:00 歌謡ポップス"
      m = re.match(r"(\d{1,2}:\d{2})\s+(.*)", end_channel)
      end_time_str = m.group(1) if m else None
      channel = m.group(2) if m else end_channel
  ```
- **`business_hours` 格式**（三步 fallback）：
  1. list page `end_time_str` 存在 → `f"{start_hhmm}〜{end_time_str}"`
  2. `end_time_str = None` 但 `detail_text` 存在 → 用 `r"(\d{1,2}:\d{2})\s*\n[-−]\s*\n(\d{1,2}:\d{2})"` 從 detail page 提取，成功時同上格式
  3. 兩者皆無 → `business_hours = None`（不填單純開始時間）
- **`ps[2].get_text()` 必須加 `separator="\n"`**：`schedule_raw = ps[2].get_text(separator="\n", strip=True)`。不加 separator 時，HTML 子節點直接串接，多行分支永遠不觸發（commit `a895e07`）。
- **`location_name` = 實際頻道名稱**：如「歌謡ポップス」。gguide_tv 事件絕對沒有實體地址，`enrich_addresses.py` 預設 skip 此 source（依 `source_name` 判斷）。
- **UI 規則**：event detail page 的地址欄用 `event.source_name === "gguide_tv"` 偵測 TV 事件，顯示 `location_name`（頻道名）純文字，不加 Google Maps 超連結。⚠ 不要用 `location_name === "電視頻道"` 判斷——`location_name` 是可變內容欄位，已改為實際頻道名稱。
- **`end_time` fallback from detail page**：list page 格式為單行（只有開始時間）時，`end_time_str = None`。fallback 邏輯從 `detail_text` 用 `r"(\d{1,2}:\d{2})\s*\n[-−]\s*\n(\d{1,2}:\d{2})"` 補抓結束時間。
- **BeautifulSoup `get_text` 注意事項**：`get_text(strip=True)` 會直接串接子元素。有跨行結構的欄位（如時間範圍），必須用 `get_text(separator="\n")` 保留換行符。

## DeepL Tracking
- Add `self._deepl_chars_used: int = 0` to `BaseScraper.__init__`.
- Increment `self._deepl_chars_used += len(text)` at every DeepL API call.
- `main.py` reads `getattr(scraper, "_deepl_chars_used", 0)` when writing to `scraper_runs`.

## enrich_addresses.py
- **Purpose**: GPT-4o-mini batch-fills `location_address` / `location_address_zh` / `location_address_en` for events that have `location_name` set but `location_address = NULL`.
- **Skipped sources**: `gguide_tv` (TV broadcast, no physical address) and events with `location_name ILIKE '%オンライン%'` are excluded by default.
- **Output is AI-generated, NOT verified**: GPT-4o-mini can hallucinate street numbers for new or renamed venues. Known failure: MoN Takanawa filled with `東京都港区高輪4-10-30` instead of correct `東京都港区高輪2-21-2` (2026-05-01).
- **Post-run audit**: After running `enrich_addresses.py`, manually spot-check records from high-profile partner venues (SSFF, TAICCA, TCC) against the organizer's official access page (`会場・アクセス` section).
- **Verification source**: For SSFF, use `shortshorts.org/2026/ja/schedule/` Venue access section. For other venues, search the organizer's official site for the address.
- **Direct DB fix**: When a wrong address is found, correct it directly via Supabase SDK UPDATE — no code change or commit needed (data-only correction).

## Annotator CLI — `--id` 強制重新標注

- `python annotator.py --id <uuid>`：對單一 event 強制重新標注，**不限** `annotation_status`（但 `reviewed` 事件除外）。
- 使用場景：台東祭等多城市活動在首次 annotate 時規則不足，需在修正 prompt 後重新執行。
- 若不加 `--id`，annotator 只處理 `annotation_status = 'pending'` 的事件。

## `location_prefectures` — 多城市母活動都道府縣陣列

- DB 欄位：`location_prefectures text[]`（nullable，migration 012）
- **何時寫入**：annotator 子活動 loop 結束後，若聚合出 ≥ 2 個不同都道府縣，自動 UPDATE 父事件的 `location_prefectures`；單城市不寫入（維持 null）。
- **計算方式**：`_extract_prefecture(location_address)` 從每個子活動的 `location_address` 提取都道府縣名，去重後排序。
- **`_extract_prefecture()` regex 必須覆蓋兩種格式**：
  - 標準格式：`東京都`、`大阪府`、`京都府`、`北海道`
  - 市開頭格式：`大阪市`、`京都市`（省略「府」的地址，如「大阪市中央区...」）
- **Backfill**：現有多城市母活動可用 `scraper/backfill_location_prefectures.py` 補填。
- **篩選整合**：前台（`web/app/[locale]/page.tsx`）和後台（`web/components/AdminEventTable.tsx`）各地區篩選需加入 `location_prefectures.cs.{"X"}` OR 條件，否則多城市母活動無法命中地區篩選。

## Multi-City Tour De-anchoring (HQ-anchored scrapers)

For any scraper that hardcodes a fallback `location_address` to a single HQ / 駐日機構 (e.g. `taiwan_cultural_center`, `koryu`, future 駐日辦事處 sources):

- **Detect multi-city descriptions before falling back to HQ.** If the article description mentions ≥ 2 regional keywords from `東京|北海道|大阪|京都|神奈川|福岡|名古屋|愛知|仙台|札幌|広島|沖縄`, the event is a tour, not an HQ event. **`東京` must be in the list** — it appears in most multi-city tours.
- **De-anchor pattern when multi-city detected:**
  - `location_name = '・'.join(found_regions)` — list the detected cities directly (e.g. `北海道・東京・神奈川・京都・大阪`). **Never use a generic label like `全国巡回`** — it is meaningless to users.
  - `location_address = None`（清空 HQ 地址，避免錯誤錨定）
- **Downstream takes over:** Annotator splits the event into per-city sub-events, then auto-aggregates `location_prefectures` on the parent (see section above).
- **Without this de-anchor:** All tour stops display as HQ-city events, regional filters break, multi-city UI never triggers. Reference incident: 台湾映画上映会2026 (5-city tour) — fixed in commit `a2d6eea` (2026-05-01).

## Annotator NAME WRITING RULES

`annotator.py` system prompt requires the following rules for the `name_ja` / `name_zh` / `name_en` fields:

- **Titles must be self-contained**: A reader who sees only the title (without the description) must understand what the event is.
- **Generic terms must not appear alone**: When the title consists only of a generic word, it MUST be prefixed with the organiser, topic, or series context.
  - Generic words: `オフ会`, `ライブ`, `上映会`, `展示`, `イベント`, `セミナー`, `勉強会`
  - Bad: `東京オフ会` → no one knows whose fan meetup this is
  - Good: `台湾系YouTuber copochanの東京オフ会`
- **Target length**: 10–40 characters (Japanese). Avoid unnecessary padding.
- **Sub-events must also be self-contained**: A sub-event title like `CSRデー` with no parent context is rejected. Include the series or organiser name.
- **When to re-annotate**: If the DB has an existing generic title (e.g. `東京オフ会`), set `annotation_status = 'pending'` and re-run `annotator.py`.

## Annotator output cleaning
- Empty strings from GPT (`""`) must be treated as `None` — use `_str()` helper that returns `None` for falsy/blank strings. Prevents empty `name_zh`/`name_en` from blocking the `||` fallback chain in `getEventName`.
- Location fields must be stripped of leading label separators — use `_loc()` helper that calls `.lstrip("：；:; \u3000")`. GPT often includes the `会場：` or `場所：` separator as the first character of `location_name`.
- Apply `_loc()` to both `location_name` and `location_address`.
- Events with existing `""` in name/description fields need manual DB reset (`null` + `annotation_status = 'pending'`) then re-run `annotator.py`. The `_str()` helper only prevents future empty strings.

## Annotator sub-event row fields
- `sub_row` in `annotator.py` must **explicitly include `scraped_at`** inherited from the parent event: `"scraped_at": event.get("scraped_at")`. Fields omitted from `sub_row` default to `NULL` — they are not inherited automatically.
- Rule of thumb: any field that is meaningful for admin operations (e.g. `scraped_at` / クロール日時) must be carried over from parent to sub-event explicitly.
- When adding a new column to the `events` table, check whether `sub_row` in `annotator.py` also needs updating.

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

## `location_url` — 官方會場網站 URL（migration 031）

- `location_url: Optional[str] = None` in `Event` dataclass（`scraper/sources/base.py`）— 填入官方場館/會場的完整 URL（非活動頁面 URL）。
- **填寫來源**：scraper 從場館官網連結萃取，或管理員在 Admin UI 手動輸入。
- **Annotator 不填寫**：GPT 容易 hallucinate URL，`annotator.py` 的 schema 不包含 `location_url`。
- **Web 渲染**：Event detail page 以條件渲染實作——`location_url` 存在時將 `location_name` 包在 `<a href={location_url} target="_blank" rel="noopener noreferrer">` 內，並顯示 ↗ 指示符。
- **`sub_row` 繼承規則**：`annotator.py` 的 `sub_row` 不自動繼承父事件欄位。新增 `location_url` 後，若父事件有 venue URL，`sub_row` 需明確設定 `"location_url": event.get("location_url")`。
- **Seed 順序**：含 `location_url` 的 Python client seed 必須在 Supabase Dashboard 執行 migration `031` 後才能執行；否則報 `PGRST204`。


## cinema scrapers — official_url extraction
- Cinema detail pages often have an "オフィシャルサイトはこちら" or "公式サイト" anchor linking to the film's external promotional site. Extract this as `official_url`.
- Selector pattern: iterate `soup.find_all("a", href=True)`; skip hrefs that do not start with `http` and skip hrefs containing the cinema's own domain.

## Keyword filter — exclude non-article sections (関連記事 etc.)
- **Wix/SPA pages** (e.g. moonromantic) append a "関連記事" or "おすすめ" block at the bottom of every page. These sections contain links to OTHER events, including past Taiwan events.
- **Rule**: Before checking Taiwan keywords, truncate `page_text` at the first occurrence of `"関連記事"` (and similar section headers like `"関連イベント"`, `"おすすめ"` if applicable). Only scan the event's own body text.
- **Pattern**:
  ```python
  related_idx = page_text.find("関連記事")
  check_text = page_text[:related_idx] if related_idx != -1 else page_text
  if not any(kw in check_text for kw in TAIWAN_KEYWORDS):
      return None
  ```
- **⚠ DO NOT use `> 200` threshold**: The old pattern `if related_idx > 200` was incorrect — when `"関連記事"` appears before position 200 (e.g., after a short site nav), the condition falls through to `check_text = page_text` (full text), causing Taiwan keywords in the related sidebar to produce false positives. Always truncate on the marker itself using `!= -1`.
- This pattern applies to any SPA scraper that uses `page.inner_text("body")` or full-page text extraction.
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

## prtimes-specific
- **`_SEARCH_KEYWORDS` MUST NOT contain city/region names**: Keywords like `"台湾 イベント 東京"` restrict prtimes API results to articles mentioning that city. Project scope is all-Japan — always use city-free terms (`"台湾 イベント"`, `"台湾フェア"`, etc.).
- **`_EVENT_KW` must include `フェア`**: Without this, titles like「台湾フェア」have no `_EVENT_KW` match and are rejected.
- **`_TAIWAN_BASED_TITLE_RE` must be precise**: Overly broad patterns like `台湾.*?で` match Japan-held Taiwan fairs (e.g. `台湾フェア」で`). Only match explicit Taiwan-location context:
  - `台湾国内|現地|本島|の地.*?で`
  - `in 台湾` / `in Taiwan`
  - `台湾出展|輸出|進出|販路|海外展示|海外販売`
- **When a PR TIMES article is missing, check in order**:
  1. `_SEARCH_KEYWORDS` — does any keyword contain a city/region name?
  2. `_EVENT_KW` — does the event-type word (e.g. `フェア`) appear in the list?
  3. `_TAIWAN_BASED_TITLE_RE` — is the pattern falsely matching a Japan-based Taiwan event?
  4. `_TAIWAN_VENUE_RE` — is the venue filter incorrectly excluding it?
- **Referer header required**: `requests.get(url, headers={"Referer": page_url})` — without Referer some stores return 403.
- **Taiwan events are rare and unpredictable** (food fairs, not seasonal). 0-event dry-runs are expected.
- **多城市活動偵測（`_MULTI_CITY_SECTION_RE`）**: 當 PR 文章前半為商品介紹、活動行程落在後半時，固定截斷（`text[:3000]`）會漏掉多城市日程。解法：在 `_fetch_detail()` 用正則偵測「東京｜日期」/「大阪｜日期」等多城市模式，偵測到時選擇性延長（前段 2,000 字 + `---[イベント開催情報]---` 分隔標記 + 行程區塊 4,000 字），未偵測到則維持原 3,000 字上限。
- **多城市子活動補建標準流程**（偵測到漏建時）：① 手動建子活動確認資料正確 → ② 刪除手動建的子活動 → ③ 修正 scraper raw_description 邏輯 → ④ 重新抓取 + 更新 DB + 重置 `annotation_status = pending` → ⑤ 執行 `annotator.py` 自動生成正確 sub_events。不可跳過步驟 ②（保留手動建的子活動會導致重複）。

## hankyu_umeda-specific
- **Static HTML, no Playwright**: requests + BeautifulSoup only. Page at `https://www.hankyu-dept.co.jp/honten/event/` returns full HTML.
- **Seasonal pattern**: Taiwan展（台湾ライフ等）is typically in **autumn (September–November)**. Returning 0 events during spring/summer is **correct** — do not treat it as a scraper bug.
- **source_id**: `hankyu_umeda_{slug}` where slug = last path segment of the detail URL (e.g. `taiwan_life`). SHA1 fallback `hankyu_umeda_{sha1(title+date_str)[:10]}` for events without a unique detail page.
- **Date format**: `◎M月D日（曜日）～D日（曜日）` (same-month) or cross-month variant. Three regexes: `_DATE_DIFF_MONTH`, `_DATE_SAME_MONTH`, `_DATE_SINGLE`. Year inferred from current date with Dec→Jan rollover.

## google_news_rss-specific
- Fetches 4 Google News RSS queries; Taiwan-filtered; `category: ["report"]` (annotator refines)
- `start_date` extracted from description text; fallback to pubDate — DO NOT set to null
- `source_id`: `gnews_{md5(url)[:12]}` — stable across runs; `url` is guid if real article URL, else `<link>` tag value
- **`_STALE_DAYS = 21`**: Skip entries older than 21 days (based on pubDate). Google News redirect URLs (`news.google.com/rss/articles/...`) expire within ~2–3 weeks — any link older than 21 days is likely dead. The previous value of 60 was too long.
- Google `<guid>` may contain real article URL; prefer it over `<link>` tag when it starts with `http` and does not contain `news.google.com`
- **Google News redirect URLs work in real browsers only**: `requests.get()` on a `news.google.com/rss/articles/...` URL returns HTTP 400. Playwright also gets blocked by bot detection. Do NOT attempt server-side redirect resolution — leave the redirect URL as `source_url`. The URL works fine when the user clicks it in a real browser.
- **`_is_yahoo_aggregation()` filter**: Skip articles whose title ends with `「- Yahoo!ニュース」`. Yahoo news aggregation pages are duplicates of the source article AND their redirect URLs expire faster. Check: `title.endswith("- Yahoo!ニュース")` or equivalent strip+suffix check.
- **Query precision**: Use `"台湾映画 上映会"` (not `"台湾映画 上映"`) to filter out pure news articles that report on upcoming release dates without being event listings.
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

**`start_date` rule for upcoming / COMING SOON movies:** When the movie page shows "COMING SOON" or a pre-announcement article without a confirmed release date, set `start_date = null` rather than using any date on the page. Pages scraped before the official release announcement may contain only an article publication date or a vague season label — using such a date produces a wrong `start_date` that persists until the next scrape (e.g. ナギ日記: scraper set `2026-05-01`, actual release `2026-09-25`). Priority order for extracting a movie release date: `「○月○日（曜日）公開」` pattern in body → `「公開日：YYYY年MM月DD日」` labeled field → null.

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
- **Location defaults to TCC, but de-anchor for multi-city tours**: Default is `台北駐日経済文化代表処 台湾文化センター / 東京都港区虎ノ門1-1-12 虎ノ門ビル2階`. **When `description` mentions ≥ 2 regional keywords (`東京|北海道|大阪|京都|神奈川|福岡|名古屋|愛知|仙台`), set `location_name = '・'.join(found_regions)` (e.g. `北海道・東京・神奈川・京都・大阪`) and `location_address = None`** — never use a generic label like `全国巡回`. `東京` must be in the detection list. Annotator will then split into per-city sub-events and aggregate `location_prefectures` (commit `a2d6eea` + `0d900b5`, 2026-05-01).
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

### Pass 3 — Orphaned sub-event cleanup
After Pass 1/2, some sub-events are left active while their parent has been deactivated (orphaned). Pass 3 cleans these up:
1. Find all `is_active=True` sub-events whose `parent_event_id` points to an `is_active=False` parent (orphans).
2. For each orphan, find the primary parent via `secondary_source_urls contains orphan.source_url` query.
3. If the primary parent has a sub-event with `name_ja` similarity ≥ 0.85 **and** matching `start_date` → merge (deactivate orphan, keep winner per `SOURCE_PRIORITY`).
4. If no matching sub found under the primary parent → deactivate the orphan directly.

**Pass 3 must run after Pass 1+2** (so parent merge results are already settled). Print output format: `Done: N pair(s)/orphan(s) merged (Pass 1+2+3).`

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

## gguide_tv-specific
- **Source**: 番組表Gガイド (bangumi.org) — Japanese TV program listing. Uses `"台湾"` as the search keyword to fetch candidate programs, then `_is_taiwan_title()` to re-filter.
- **`tv_program` category is always first**: Every `gguide_tv` event is a TV broadcast. `_genre_to_category()` always prepends `"tv_program"` to the result. A genre-specific secondary category is appended when applicable:
  - `ドラマ` → `[tv_program, drama]`
  - `映画` → `[tv_program, movie]`
  - `音楽` → `[tv_program, performing_arts]`
  - `ドキュメンタリー` / `教養` / `報道` → `[tv_program, report]`
  - その他 → `[tv_program]`
- **User-report pattern for gguide_tv**: Most wrongCategory reports on gguide_tv events involve missing `tv_program`. When correcting a report, always ensure `tv_program` is included (the annotator does not know these are TV programs).
- **`仙台湾` false positive**: `仙台湾` = 仙台 (Sendai city) + 湾 (bay). It is a geographic bay in Miyagi Prefecture, **completely unrelated to Taiwan**. `"台湾"` appears only as a substring of `"仙台湾"`. This was scraped as Taiwan-related before the fix (2026-04-29, event id `421d763d`).
- **`_FALSE_POSITIVE_PATTERNS` guard**: `gguide_tv.py` maintains `_FALSE_POSITIVE_PATTERNS = re.compile(r"仙台湾")`. `_is_taiwan_title()` strips all false-positive substrings from the title first; if no Taiwan keyword remains in the cleaned title, the program is rejected.
- **Adding new false positives**: When a new false-positive pattern is found, add it to `_FALSE_POSITIVE_PATTERNS` with alternation: `re.compile(r"仙台湾|新パターン")`. Add a comment explaining what the pattern means.
- **General rule for substring keyword filters**: Any scraper that uses `"台湾" in text` must consider that `台湾` may appear inside unrelated Japanese words. Apply the strip-and-recheck pattern:
  ```python
  cleaned = _FALSE_POSITIVE_PATTERNS.sub("", title)
  return any(kw in cleaned for kw in _TAIWAN_KEYWORDS)
  ```

## DB Operations Safety Rules

These rules apply to any manual or scripted DB operation. Violating them has caused production incidents.

- **NEVER batch-set `is_active = False` based on `end_date < today`**. Ended events must remain `is_active = True` — users browse event history, and the frontend `FilterBar` ("顯示已結束活動" toggle) controls their visibility. `is_active` reflects **admin intent to hide**, NOT event expiry status.
- **`is_active` has exactly two legitimate write sources**:
  1. Admin manually disables a specific event via the admin page.
  2. `merger.py` deactivates a duplicate secondary event.
  Any other bulk UPDATE setting `is_active = False` is an error. Verify against these two sources before executing.
- **Reference incident**: 2026-05-01 — batch script set `end_date < today AND is_active = True → is_active = False`, deactivating 342 events. Immediate emergency revert required.

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

## maruhiro-specific
- **All data on list page**: Detail pages contain only a JPEG image. Never fetch detail pages — title, date, floor, and store name are all in `p.card-text` on the list page.
- **`start_date` must be `datetime.datetime`, NOT `datetime.date`**: `dedup_events` calls `.date()` on `start_date`. Passing a bare `date` object raises `AttributeError: 'datetime.date' object has no attribute 'date'`.
- **Taiwan events are seasonal**: Primarily Golden Week (Apr–May). 0-event dry-runs outside this period are normal.
- **source_id**: `maruhiro_{event_id}` from `data-url="/events/view/{id}"` — integer, stable across runs.
- **Store address**: Resolved from `開催店舗: {name}` in `p.card-text` via static `_STORE_ADDRESS` dict. All stores are in Saitama Prefecture.
