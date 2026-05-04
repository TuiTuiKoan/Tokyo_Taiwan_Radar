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
- **Promotion checklist (auto_generate → implemented)**: When promoting an auto-generated scraper, these 5 steps must ALL be completed:
  1. PR merged — `scraper/sources/<name>.py` exists in repo.
  2. `scraper/main.py` — import + `SCRAPERS` registration confirmed.
  3. `research_sources` row — `status = 'implemented'`.
  4. **`research_sources.scraper_source_name = '<scraper key>'`** — MUST be filled manually; `auto_generate` does NOT write this. Omitting it causes `/admin/sources` to show 0 events and disables Run Scraper (backend JOINs `scraper_runs` by this key).
  5. Smoke-test: `python main.py --dry-run --source <key>` returns events.
- **Identify source_name from a problem event**: Never guess from the event title — always query the DB:
  ```python
  sb.table('events').select('source_name,source_id,source_url').eq('id', '<uuid>').execute()
  ```
- **`start_date` / `end_date` must be `datetime.datetime`, NOT `datetime.date`**: `dedup_events` in `base.py` calls `.date()` on `start_date`. Passing a bare `date` object raises `AttributeError: 'datetime.date' object has no attribute 'date'`. Always use `datetime(y, m, d)` when constructing dates in scrapers.
- **`category` must be `list[str]`, NOT a bare string**: The DB column is `text[]`. Passing `category="movie"` raises `malformed array literal` at write time. Always use `category=["movie"]`. This fails silently at compile time and only surfaces on DB upsert.
- **Sub-events — always look up parent UUID via `get_event_id_by_source()`**: When setting `parent_event_id` on a sub-event, call `database.get_event_id_by_source(source_name, source_id) -> str | None` to retrieve the parent's UUID. Never assume the UUID in the scraper or depend on insertion order. Example:
  ```python
  from scraper.database import get_event_id_by_source
  parent_uuid = get_event_id_by_source("taiwanshi", parent_source_id)
  Event(..., parent_event_id=parent_uuid)
  ```
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

## Date Extraction — General Rules

Rules that apply to ALL scrapers when constructing `raw_description` and `start_date`/`end_date`.

### `開催日時:` prefix — complete format when end_date is known
When a scraper already knows `end_date` AND `end_date ≠ start_date`, the `開催日時:` prefix in `raw_description` **must** include the full date range:
```
開催日時: YYYY年MM月DD日〜YYYY年MM月DD日
```
Writing only the start date (`開催日時: YYYY年MM月DD日`) tells GPT there is a single day → SINGLE-DAY RULE fires → `end_date` is set to `start_date`, discarding the correct value already held by the scraper.

Note: `annotator.py`'s `annotation.get("end_date") or event.get("end_date")` fallback is **blind to non-null wrong values** — it only activates when GPT returns `null`. If GPT returns a non-null but incorrect `end_date` (e.g. same as `start_date` via SINGLE-DAY RULE), the scraper's correct value is silently discarded.

### Year anchor for date-less news scrapers
When a news-type scraper (`google_news_rss`, `prtimes`, `nhk_rss`, etc.) cannot extract a complete date from the article (i.e. the article only mentions a month/day or no date at all), embed the RSS `pub_date` as a year anchor in `raw_description`:
```
（記事配信日: YYYY年MM月DD日）
```
Insert this before the article body text. Without a year anchor, GPT may infer the wrong year (e.g. guessing 2024 when the correct year is 2026).

### N日間 duration keywords
`annotator.py` SYSTEM_PROMPT Rule 10 covers `N日間` → `end_date = start_date + (N-1)` days, but scrapers should also attempt self-resolution rather than defaulting to `end_date = start_date`:
```python
import re
from datetime import timedelta

m = re.search(r'(\d+)日間', raw_description)
if m:
    n = int(m.group(1))
    end_date = start_date + timedelta(days=n - 1)
```
Similarly, `N週間` → `N × 7` days. Apply BEFORE falling back to `end_date = start_date`.

### annotator `or event.get("end_date")` fallback — blind spot
The pattern `annotation.get("end_date") or event.get("end_date")` only rescues the scraper's value when GPT returns `null`. When GPT returns a **non-null wrong value** (most commonly SINGLE-DAY RULE: `end_date = start_date`), the `or` branch is never reached — the wrong value is written to DB. Fix: always embed the correct date range in `raw_description` (see § `開催日時:` prefix above) so GPT never needs to fall back to SINGLE-DAY RULE in the first place.

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

---

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
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`.
  - `location_name` = the venue name captured from `場所：`.
  - `location_address` = search the surrounding text with `_ADDR_RE` (matches `〒` or prefecture+city+street pattern). If a real address is found AND it differs from the venue name, use it; otherwise set `None`. **NEVER set `location_address = location_name`** — identical values are flagged by `auto_qa_address_is_venue_name` and violate the Sub-Venue Parent Address Rule (sub-spaces like `SC 広場` need the parent building's address, not the sub-space name).
  - Fall back to `card.prefecture` for `location_address` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.

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

## Thin Pointer Article Detection — General Rule (all scrapers)

任何 scraper 遇到「薄內容指引文」時，應主動抓取外部 ref URL 補充 `raw_description`。

**偵測條件**（兩者同時成立）：
1. `len(body_text) < N`（各 scraper 自行設定閾值，koryu 使用 600 chars）
2. body_text 包含**非本站**的外部 HTTP URL

**處理流程**：
1. 提取外部 URL（正則排除本站 domain）
2. 呼叫 `fetch_ref_text(ref_url)` — 已在 `base.py` 實作，直接 import 使用
3. 追加到 raw_description：`[参照ページ ({ref_url})]:\n{ref_text}`
4. `date_prefix` 改用 `記事投稿日:` 而非 `開催日時:` — 避免 GPT 把文章發布日當活動日

**薄內容指引文的典型特徵**：
- 組織公告：「弊社は XX イベントを後援します。詳細は URL をご確認ください。」
- 新聞式 RSS 摘要：只有標題＋一句描述＋原文連結
- 公募通知：只說明有公募，所有細節在外部網站

**通用函數**：`from .base import fetch_ref_text`
- `fetch_ref_text(url, max_chars=3000)` — requests + BeautifulSoup，selector 優先序：`main` > `article` > `body`
- 回傳 `None` 表示失敗或內容 < 200 chars

**Annotator-side thin content detection（`annotator.py`）**：
- Playwright 文章 fetch 觸發條件：`not start_date` **OR** `len(raw_description) < 400 chars`
- 常數：`_GNEWS_THIN_DESC_CHARS = 400`
- 實作：inner 函數 `_gnews_needs_article_fetch(e)` — `gnews_needs_fetch` 計數與 per-event trigger 統一使用此函數
- 適用來源：目前僅 `google_news_rss`（使用 Playwright 跟進 Google News redirect）
- **注意**：手動修正 start_date 後重新 annotate 時，若 raw_desc 仍短，fetch 仍會觸發 → 確保 GPT 看到完整文章
- **原則**：「start_date 有值」不代表「描述足夠豐富」，薄內容偵測邏輯應在 scraper 和 annotator 兩層都套用

### Thin Content Detection — Applicability Matrix

| Source | Scraper-side fix | Annotator-side fallback | Reason |
|--------|-----------------|------------------------|--------|
| google_news_rss | pub_date anchor + Playwright (in annotator) | ✅ `_GNEWS_THIN_DESC_CHARS=400`, Playwright | RSS snippet only; Google redirect URL |
| koryu | `fetch_ref_text()` for pointer articles | — (scraper handles) | Pointer articles < 600 chars + external URL |
| nhk_rss | pub_date anchor + `fetch_ref_text(article_url)` | ✅ `_NHK_THIN_CHARS=400`, requests-based | RSS snippet always < 200 chars |
| doorkeeper | N/A | N/A | API returns full description |
| connpass | N/A | N/A | API returns full description |
| iwafu | N/A | N/A | Visits detail page |
| arukikata | N/A | N/A | Fetches full article (BS4) |
| peatix | N/A | N/A | Visits detail page (Playwright) |
| taiwan_cultural_center | N/A | N/A | Visits detail page (Playwright) |
| hakusuisha | `skip_tags` HTMLParser + **8000 char limit** in `_fetch_detail_text_fallback()` | ✅ thin-content rescue when `source_name == "hakusuisha"` and `日時` absent in `raw_description` | JS/nav content consuming 2000-char budget; `■日時:` typically appears after char 2000; raised from 4000→8000 (commit `a0292a2`) |
| taioan_dokyokai | N/A | N/A | Visits detail page (Playwright) |
| taiwan_kyokai | N/A | N/A | Visits detail page (Playwright) |
| taiwan_festival_tokyo | N/A | N/A | Structured widget, not article-based |
| ide_jetro | N/A | N/A | date_prefix fix sufficient |

**Rule**: Only apply thin-content detection when the scraper stores a snippet (RSS/headline) and the full content lives at a separate URL. API-based and detail-page-visiting scrapers are inherently complete.

## Auto-generated Scraper Date Accuracy

auto_generate が生成した `FIELD_SELECTORS["date"]` が指すセレクタは、**記事公開日（publication date）** を指している場合がある。プロモーション審査時に必ず確認すること。

### 確認ステップ
1. listing page の HTML を実際に開き、`FIELD_SELECTORS["date"]` のセレクタが何を取得するか確認する（`span.note`、`.date`、`time[datetime]` 等）。
2. 取得した値が「記事公開日」か「活動日」かを目視確認（`YYYY.MM.DD` 形式は公開日の可能性が高い）。
3. 活動日が detail page の `日時：` / `開催日時：` ラベルに存在する場合は、listing page の selector を使わずに detail page から抽出すること。

### 活動日が detail page にある場合の実装パターン
```python
# _extract_event_dates(detail_text, card_year) パターン（hakusuisha.py を参照）
# 対応パターン1: 2026年3月20日・21日（同月 ・ 複数日）
# 対応パターン2: 2025年11月23日...／24日（同月 ／ 複数日）
# 対応パターン3: 2026年1月10日 / 2026年1月11日（完全日付2つ）
```

### `raw_description` プレフィックスルール
- `日時` ラベルあり → `開催日時: YYYY年MM月DD日` プレフィックス（GPT annotator への明確なシグナル）
- `日時` ラベルなし（公告・お知らせ文）→ `（記事投稿日: YYYY年MM月DD日）` 年号アンカー

### 対象
`auto_generate` で生成されたすべての scraper のプロモーション前に `FIELD_SELECTORS["date"]` を人工審査すること。Playwright ベースのスクレーパー（detail page を訪問する）でも、listing page の date selector が残っている場合は要確認。

Reference incident: 2026-05-04 hakusuisha `FIELD_SELECTORS["date"] = "span.note"` → 記事公開日を取得（活動日ではない）（commit `b3708e1`）。
### Auto-generated Scraper — Body Text Limit

**Rule**: auto-generated scraper の `body.inner_text()` および HTTP fallback のスライス上限は **最低 8000 字元** を使うこと。4000 字元では nav / header ノイズに予算を消費され、イベント本文の `■日時:` / `会場:` / `主催:` が切り捨てられる。

```python
# ❌ 4000 は nav のある site では不足
full_description = body.inner_text()[:4000]

# ✅ 8000 以上を推奨
full_description = body.inner_text()[:8000]
```

Incident: `hakusuisha.py` — nav menu が 2000+ 字消費し、`■日時：` を截斷点の外に押し出した（commit `a0292a2`）。

### Self-injected Prefix Interference

**Rule**: scraper が `raw_description` 先頭に `開催日時: YYYY年MM月DD日` 等のプレフィックスを追加する**前に**、日時/会場/主催の regex 抽出を完了させること。

**問題**：`_JITSU_RE = re.compile(r"日時[:：]")` は `開催日時:` にもマッチする。scraper が自己注入したプレフィックスを先に検索すると、group(1) がプレフィックスの日付テキスト（時間なし）になり、後続の `_TIME_RE` が正文の時間 (`HH:MM〜HH:MM`) を永遠に見つけられなくなる。

```python
# ❌ Bad: プレフィックスを先に加えてから検索
raw_description = f"開催日時: {date_str}\n\n{full_description}"
m = _JITSU_RE.search(raw_description)  # → マッチするのはプレフィックスの "開催日時:"

# ✅ Good: 検索を先に行い、プレフィックスは最後に加える
m = _JITSU_RE.search(full_description)  # または _TIME_RE で直接時間を検索
# ... 抽出完了後 ...
raw_description = f"開催日時: {date_str}\n\n{full_description}"
```

代替解法：`日時[：:]` の代わりに `[■◆●▼]\s*日時[：:]` で検索（行頭の記号を要求）するか、`_TIME_RE`（`\d{1,2}:\d{2}` を含む時刻パターン）で full_description を直接検索して前綴を回避する。

Incident: `hakusuisha.py` — `_JITSU_RE.search()` が `開催日時: 2026年4月26日` プレフィックスにマッチし、`_TIME_RE` が正文の `14:00〜16:00` を見つけられなかった（commit `a0292a2`）。
---

## Auto-Generate Scraper — Date Field Accuracy Check

`FIELD_SELECTORS["date"]` が正確なイベント開催日を返すか検証する手順：

1. ブラウザで listing ページを開き、カード上の日付テキスト要素を inspect
2. その日付が「記事投稿日」「更新日」「公開日」のラベルに付いていれば ⚠️ 要注意
3. detail ページの本文に `日時：` / `開催日：` / `期間：` ラベルがあればそちらを使う
4. 修正パターン：
   - `_JITSU_RE = re.compile(r"[■◆●▼]?\s*日時[：:]\s*(.{5,150})", re.MULTILINE)`
   - `_FULL_YMD_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")`
   - `_END_DAY_RE = re.compile(r"[・/／]\s*(\d{1,2})日")`
   - 参照実装：`scraper/sources/hakusuisha.py` の `_extract_event_dates()`
5. `end_date` も同時に設定すること（「・DD日」パターンで終了日が取れる場合が多い）

---

## 学術場地括弧地址模式

日本學術研討會的 `location_name` 有時包含完整郵遞區號地址於括號中：
```
南山大学 Q棟103教室 (〒466-8673 名古屋市昭和区山里町18)
```
scraper 的 `_extract_venue()` 應優先識別 `[（(](〒\d{3}-\d{4}...)` 模式，提取為 `location_address` 並從 `location_name` 中去除括號部分。
已實作：`scraper/sources/taiwanshi.py` 作為參考實作。

## note.com RSS 截斷處理

note.com RSS `<description>` 約在 140 字截斷，可能只有「続きをみる」。
當 `plain_desc == ""` 時，`_parse_item()` 應 fallback 至 HTTP GET 文章頁，
解析 `<script type="application/ld+json">` 的 `description` 欄位（~280 字）。
已實作：`scraper/sources/note_creators.py` → `_fetch_json_ld_description()` helper。
無需 Playwright，標準 `requests.get()` 即可。

---

## koryu-specific
- **location_address fallback**: `_extract_location_address()` searches for `所在地/住所` sections. When absent (common for 後援-type posts), set `location_address = None` — **do NOT fall back to the venue name**. The annotator will fill the address via PARENT VENUE ADDRESS RULE. Old pattern `or (venue if venue else None)` was removed (commit `9d6e0fc`) because it echoed venue name as address, blocking annotator correction.
- **404 on old koryu URLs**: When a koryu event page returns 404, `main_text` will be a redirect message with no venue section. `_extract_venue` returns `None`, so `location_address` is also `None`. This is acceptable — the event is stale.
- **Single-day end_date**: Always set `end_date = start_date` at the end of `_extract_event_fields`. Taiwan Kyokai events are single-day ceremonies/lectures.
- **Publish-date false positive**: The page body starts with the article publish date (`2026年4月20日`) before the actual event content. Do NOT rely solely on the generic `YYYY年MM月DD日` fallback — it will pick up the publish date if no structured `日時：` field exists.
- **DOW-qualified date extraction**: Dates like `5月16日（土）` (with day-of-week) are actual event dates. Extract these BEFORE the generic fallback, then infer the year from the nearest `20XX年` in the text.
- **後援公告の prose 日付 (`（後援）` 始まりの title)**：後援公告ページには `日時:` ラベルがない。正しい活動日は body text 中の `MM月DD日（曜日）に開催` という prose パターンに年号なしで出現する。`日時：` / `時間：` / DOW-qualified 全て失敗したら、`r'(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝][）)]\s*に開催'` を検索し、年号は pub_date から推定する（月が pub_date より大幅に前なら翌年）。この prose 検索は generic `YYYY年MM月DD日` fallback より **前に** 実施すること。
  ```python
  m = re.search(
      r'(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝][）)]\s*に開催',
      body_text,
  )
  if m:
      month, day = int(m.group(1)), int(m.group(2))
      pub_dt = _parse_date(item["pub_date_str"])
      year = pub_dt.year if pub_dt else datetime.now().year
      if pub_dt and month < pub_dt.month - 1:
          year += 1
      start_date = datetime(year, month, day)
  ```
- **`開催日時:` 前置語の正確性**：Scraper が `raw_description` の先頭に `開催日時: YYYY年MM月DD日` を前置する場合、その日付は **必ず正しい活動日** を使うこと。この前置語は GPT annotator への強烈なシグナルであり、誤った日付を前置すると GPT は body 中の正確な日付を無視し、誤日付が DB に書き込まれる。
- **Priority order for date extraction**: `日時：` field → `時間：` field (with date) → DOW-qualified `月\d+日（曜日）` → `に開催` prose pattern → generic `YYYY年MM月DD日` fallback (last resort, high risk of matching publish date).
- **指引文（pointer article）偵測と ref URL 抓取**：koryu.py は「薄內容指引文偵測」パターンの**最初の実装例**。汎用 `fetch_ref_text()` は `base.py` に昇格済み（→ 上記 § *Thin Pointer Article Detection — General Rule* 参照）。koryu 固有の実装詳細：
  - 閾値：`_THIN_BODY_CHARS = 600`
  - 外部 URL 判定：`_EXT_URL_RE = re.compile(r'https?://(?!(?:www\.)?koryu\.or\.jp)[^\s）)]+')`
  - import：`from .base import BaseScraper, Event, fetch_ref_text`（`requests`・`BeautifulSoup` は koryu.py 内で直接 import 不要）
  - `date_prefix` = `記事投稿日: {pub_date_str}`（`開催日時:` は使わない）
  - 適用場景：公募公告（コンテスト）、後援公告、簡短通知類記事。これらの category/venue/date はすべて ref URL 側にある。

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
        # Exception: Taiwan-venue events targeting Japanese visitors are in scope
        if TAIWAN_FOR_JAPANESE_KW.search(body):
            return True
        return False
    return bool(JAPAN_LOCATION_KW.search(body))  # Stage 3: Japan city present
```
**Critical**: Stage 2 (Taiwan-venue exclusion) MUST come before Stage 3 (Japan-keyword check).
Reversing the order causes false positives: a Taiwan-held event mentioning Japanese travel companies
(e.g. 近畿日本ツーリスト → triggers 近畿 keyword) passes Stage 3 before Stage 2 can reject it.

**`TAIWAN_FOR_JAPANESE_KW` exception list** (current): `日本人向け`, `日本語対応`, `日本から参加`, `日本から`, `日本発`, `ファムトリップ`, `日台交流ツアー`.
Events matching this exception should be categorized as `tourism` and/or `taiwan_japan`. Their `location_address` must use the real Taiwan address — do NOT convert to Japanese format. Future additions: `台湾ツアー`, `訪台`, `台湾研修`, `台湾旅行`.

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

## rightscube-specific
- **Homepage + /movies/ 雙頁爬取**：`/movies/` 目錄頁只列出常規放映作品；特集上映系列（如 taiwan-filmake）只出現在 homepage。爬蟲必須同時抓 homepage + /movies/ 目錄，再對 slug 去重。
- **Unicode Bold Math section 標題**：section 標題（如 `𝗧𝗛𝗘𝗔𝗧𝗘𝗥`）使用 Unicode Mathematical Bold Sans-Serif 字元（U+1D5D4+）。字串比對前必須用 `_normalize_bold_math()` 轉換成 ASCII；不轉換則 `== "THEATER"` 永遠為 False。
  ```python
  _BOLD_MATH_RANGES = [
      (0x1D400, 0x1D419, ord('A')),  # bold uppercase
      (0x1D41A, 0x1D433, ord('a')),  # bold lowercase
      (0x1D5D4, 0x1D5ED, ord('A')),  # bold sans uppercase
      (0x1D5EE, 0x1D607, ord('a')),  # bold sans lowercase
  ]
  def _normalize_bold_math(text: str) -> str:
      result = []
      for ch in text:
          cp = ord(ch)
          for start, end, base in _BOLD_MATH_RANGES:
              if start <= cp <= end:
                  ch = chr(base + (cp - start))
                  break
          result.append(ch)
      return "".join(result)
  ```
- **`<span><a>` 包裝下的 sibling 日期文字**：劇場連結結構為 `<span><a href="...">劇場名</a></span>｜5/17(日)・5/24(日)`。日期文字是 `a.parent.next_sibling`（即 `<span>` 的下一個兄弟文字節點），**不是** `a.next_sibling`（= None，因為 `<a>` 在 `<span>` 內部）。
- **沒有 THEATER section 的電影應跳過**：DVD 專售或非戲院作品不含 THEATER section → 先確認 section 存在再產生 child events；若 section 缺失則只產生 parent event。
- **venue_key 派生規則（production contract，勿修改）**：SNS domain（x.com / twitter.com / instagram.com）→ URL path 第一段；CDN 平台 host（jimdofree.com / thebase.in 等）→ subdomain；一般域名 → 去掉 TLD 的 domain，lowercase，非英數字換為 `-`。此規則決定 `source_id` 後綴，變更會造成 duplicate 插入而非更新現有記錄。

## annotator.py ↔ types.ts 同步守則（Three-Location Sync Rule）

每次在 `web/lib/types.ts` 新增 `Category` 型別時，**必須同時更新三個地方**：

1. `scraper/annotator.py` → `VALID_CATEGORIES` 列表
2. `scraper/annotator.py` → SYSTEM_PROMPT 第 2 條 categories 列表（單行逗號分隔）
3. `scraper/annotator.py` → SYSTEM_PROMPT 分類定義清單（每個新分類需加定義行）

**違反後果**：GPT 無法選用新分類，被迫選最近似的舊分類（例如 `tv_program` 不存在時選 `movie`）。

**驗證命令**：
```python
# 確認 VALID_CATEGORIES 與 types.ts 一致
# types.ts CATEGORIES array vs annotator.py VALID_CATEGORIES
# 所有出現在 types.ts 中的值都必須出現在 VALID_CATEGORIES
```

**已知遺漏（2026-05-04 修正）**：tv_program, drama, documentary, tea_alcohol, exhibition, folklore, literature, parenting, scholarship, taiwan_mandarin, healthcare — 這 10 個分類在 types.ts 存在多月但 annotator.py 未同步，導致 gguide_tv 電視節目被標為 movie。

---

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
- **gguide_tv ↔ Annotator 分類注意事項**：
  - `_genre_to_category()` 已正確產生 `["tv_program"]` 初始分類；annotator 透過 `_inject_keyword_categories` 的 `_TV_PROGRAM_KEYWORDS` 確保 tv_program 注入
  - `放送: [channel]` + `ジャンル: [genre]` 是 gguide_tv 的固定 raw_description 格式標記（`_TV_PROGRAM_KEYWORDS = frozenset(["放送:", "放送：", "ジャンル:", "ジャンル："])`）
  - 映画 genre（`ジャンル: 映画`）的 TV 廣播 → 保留 `movie` + 加 `tv_program`；其他 genre（バラエティ/ドラマ/ドキュメンタリー 等）→ 只有 `tv_program`，絕不單獨用 `movie`
  - `_inject_keyword_categories` 邏輯：含 TV markers → 加 `tv_program`；同時若有 `movie` 且非「ジャンル: 映画」→ 移除錯誤的 `movie`

## DeepL Tracking
- Add `self._deepl_chars_used: int = 0` to `BaseScraper.__init__`.
- Increment `self._deepl_chars_used += len(text)` at every DeepL API call.
- `main.py` reads `getattr(scraper, "_deepl_chars_used", 0)` when writing to `scraper_runs`.

## CLI Module 入口 — `load_dotenv()` 必要性
- **任何有獨立 CLI 入口（`-m module` / `if __name__ == '__main__'`）的 Python module 必須在頂部加 `load_dotenv()`**。
- `main.py` 已有 `load_dotenv`，但子 module（如 `auto_scraper/generate.py`）以 `python -m auto_scraper.generate` 直接執行時，不會繼承 `main.py` 的 `load_dotenv` 呼叫。
- CI 用 GitHub Actions secret 注入 env var，load_dotenv 為 no-op，不受影響。
- **Pattern**：
  ```python
  try:
      from dotenv import load_dotenv
      load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # scraper/.env
  except ImportError:
      pass
  ```
- **根因**：`python -m auto_scraper.generate --source-id <id>` 本機崩潰 `KeyError: SUPABASE_URL`（commit `d94fc80` 修復）。

## Supabase SDK — JSONB Field Rules
- **JSONB 欄位（`jsonb`、`jsonb[]`）必須傳 Python `list`/`dict`**，不可用 `json.dumps()` 先序列化。Supabase Python SDK 自動序列化 native types；手動 `json.dumps()` 造成雙重編碼，欄位存入 `"[{...}]"` 字串而非 JSONB 陣列。前端 `.map()` 等 Array 操作會因此 crash。
- **受影響欄位（目前）**：`record_links`（`jsonb[]`）、`secondary_source_urls`（`text[]`，同規則）。新增 JSONB 欄位時務必確認傳入型別。
- **診斷**：若前端出現 `.map is not a function` 或 `.filter is not a function`，優先確認 DB 欄位中儲存的是字串還是陣列（在 Supabase Dashboard 直接 SELECT 該欄位）。
- **反例（bug pattern）**：`_event_to_row()` 中 `"record_links": json.dumps(links)` → 存入 `"[{...}]"` 字串。
- **正例（correct pattern）**：`"record_links": links` （直接傳 Python list）。

## enrich_addresses.py
- **Purpose**: GPT-4o-mini batch-fills `location_address` / `location_address_zh` / `location_address_en` for events that have `location_name` set but `location_address = NULL`.
- **Skipped sources**: `gguide_tv` (TV broadcast, no physical address) and events with `location_name ILIKE '%オンライン%'` are excluded by default.
- **Output is AI-generated, NOT verified**: GPT-4o-mini can hallucinate street numbers for new or renamed venues. Known failure: MoN Takanawa filled with `東京都港区高輪4-10-30` instead of correct `東京都港区高輪2-21-2` (2026-05-01).
- **Post-run audit**: After running `enrich_addresses.py`, manually spot-check records from high-profile partner venues (SSFF, TAICCA, TCC) against the organizer's official access page (`会場・アクセス` section).
- **Verification source**: For SSFF, use `shortshorts.org/2026/ja/schedule/` Venue access section. For other venues, search the organizer's official site for the address.
- **Direct DB fix**: When a wrong address is found, correct it directly via Supabase SDK UPDATE — no code change or commit needed (data-only correction).

## auto_generate Pipeline

### Eligibility Check
- `generate.py` `_check_eligibility()` accepts **both `'researched'` and `'recommended'` statuses**. `recommended` sources (highest confidence, GitHub Issue created) are valid targets.
- If a source returns "not eligible" unexpectedly, check `research_sources.status` first — it may be `'recommended'` if the researcher used `--create-issue`.

### 403 / Headless Fallback
- Some WordPress/UIkit sites return **403 to headless Playwright** but serve full static HTML to `requests`. Signs: sandbox shows 0 events, `card_selector` not found in rendered DOM.
- When `auto_generate` fails with 0 events, immediately test `requests.get(url)` manually before retrying with Playwright.
- If static HTML is complete → write the scraper manually with `requests + BeautifulSoup`. Attach a `Retry` adapter to `requests.Session` (see § BaseScraper Contract).

### Annual-Subdomain URLs (e.g. TIFF)
- Sites like TIFF use `YYYY.tiff-jp.net` — hardcoded year must be replaced with dynamic resolution before promotion:
  ```python
  def _resolve_base_url() -> str:
      r = requests.head("https://www.tiff-jp.net", allow_redirects=True, timeout=10)
      m = re.search(r"(https://\d{4}\.tiff-jp\.net)", r.url)
      if m:
          return m.group(1)
      return f"https://{datetime.now().year}.tiff-jp.net"
  ```
- Mark any URL containing a 4-digit year as "needs annual review" in the spec.

### Taiwan Keyword Filter
- auto_generate specs for keyword-search sources (e.g. TIFF `?s=台湾`) may return non-Taiwan results. Always add a `_TAIWAN_KW` client-side filter in the generated scraper during promotion review.

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

## `name_ja_locked` — protect structured titles from annotator overwrite

**Problem**: Annotator GPT always rewrites `name_ja`, even when the scraper already populated it from a precise structured source field (e.g. academic paper `題目:`, official film programme titles). GPT tends to truncate the subtitle or append generic suffixes like「に関する講演会」.

**Solution**: Set `name_ja_locked=True` on the `Event` when `name_ja` is extracted from a definitive structured field. The annotator will preserve the existing `name_ja` unchanged, while still generating `name_zh`, `name_en`, `description_*`, and `category` normally.

**When to use**:
- Academic sub-events where `name_ja` = structured `題目:` / paper title with full subtitle (e.g. `taiwanshi` scraper)
- Film sub-events from official programme PDFs with definitive Japanese titles
- Any event where the raw source provides the official Japanese title as a discrete field — not inferred from free-text description

**When NOT to use**:
- Events where the source only provides a vague or generic title and annotator enrichment is desirable
- Parent events (usually fine to let annotator improve the title)

**Implementation**:
```python
# In the scraper, set name_ja_locked=True when name_ja comes from a structured field:
Event(
    name_ja=r["title"],          # from 題目: field — precise and definitive
    raw_title=r["title"],
    name_ja_locked=True,         # protect from annotator overwrite
    ...
)
```
Requires `supabase/migrations/034_name_ja_locked.sql` to be applied.

**DB fix for already-misannotated events** (if annotator has already run):
```python
# Restore raw_title → name_ja for all affected sub-events
events = sb.table('events').select('id,name_ja,raw_title').like('source_id','<source>_%_sub%').eq('is_active', True).execute().data
for e in [x for x in events if x['name_ja'] != x['raw_title']]:
    sb.table('events').update({'name_ja': e['raw_title']}).eq('id', e['id']).execute()
```

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
  - `台湾出展|輸出|進出|販路|海外展示|海外販売`- **Taiwan venue exception (`_JAPAN_VISITOR_KW`)**: If `_TAIWAN_VENUE_RE` matches but `body_text` or `title` contains a Japanese-visitor keyword (`日本人向け`, `ファムトリップ`, `日台交流ツアー`, `日本発`, `日本から` etc.), do NOT skip — the event targets Japanese visitors and is in scope. Categorize as `tourism` and/or `taiwan_japan`. Use the real Taiwan address as `location_address`.- **When a PR TIMES article is missing, check in order**:
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
- **`start_date` must NOT fall back to pubDate**: RSS `<description>` is a short snippet (often just the article title) — it never contains event dates. `pubDate` is the article publish date, completely unrelated to when the event takes place. If no date pattern is found in the description, return `None`. (Fixed in commit `9510a05`; 40 events with wrong pub_date fallback were deactivated.) The annotator handles date extraction by fetching the full article body via Playwright — see engineer `SKILL.md § Annotator — google_news_rss 文章補抓`.
- `source_id`: `gnews_{md5(url)[:12]}` — stable across runs; `url` is guid if real article URL, else `<link>` tag value
- **`_STALE_DAYS = 21`**: Skip entries older than 21 days (based on pubDate). Google News redirect URLs (`news.google.com/rss/articles/...`) expire within ~2–3 weeks — any link older than 21 days is likely dead. The previous value of 60 was too long.
- Google `<guid>` may contain real article URL; prefer it over `<link>` tag when it starts with `http` and does not contain `news.google.com`
- **Google News redirect URL decoding**: Use `googlenewsdecoder.new_decoderv1(url, interval=0)` to decode `news.google.com/rss/articles/...` URLs server-side. Add `time.sleep(_DECODE_SLEEP)` (1.0 s) after each call. Add `googlenewsdecoder>=0.1.6` to `requirements.txt`. Do NOT attempt base64 decoding of the URL path (it is encrypted protobuf, not base64) and do NOT use `requests.get()` directly (returns HTTP 400 with JavaScript redirect).
- **RSS description href is also a Google News URL**: The `<a href>` inside `<description>` HTML points to `news.google.com/rss/articles/...` — NOT the original article. A "non-google.com" filter on this href yields zero results. Always decode the RSS `<link>` URL with `googlenewsdecoder`, not the description href.
- **`_is_yahoo_aggregation()` filter**: Skip articles whose title ends with `「- Yahoo!ニュース」`. Yahoo news aggregation pages are duplicates of the source article AND their redirect URLs expire faster. Check: `title.endswith("- Yahoo!ニュース")` or equivalent strip+suffix check.
- **Query precision**: Use `"台湾映画 上映会"` (not `"台湾映画 上映"`) to filter out pure news articles that report on upcoming release dates without being event listings.
- **`_clean_title_for_dedup()`**: strips the `- Source Name` or `｜Source Name` suffix that Google News appends to RSS article titles. `Event.name_ja` is set to the cleaned title (improves in-scraper `dedup_events` key matching). `raw_title` always retains the original full title including the suffix. Apply cleaning before constructing the `Event` object.
- **`_NEWS_SOURCES` member**: `merger.py` uses Pass 2 (date-range + location-overlap) — NOT name similarity — to merge google_news_rss events into official primaries. This is intentional: article titles don't match event names. Never add `google_news_rss` to Pass 1 name-similarity matching.
- **Within-source dedup**: handled by `merger.py` Pass 0 (name_ja similarity ≥ 0.85), which explicitly includes `start_date=NULL` events. Pass 1 skips same-source pairs, so Pass 0 is the only dedup layer for gnews-vs-gnews.

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

`scraper/merger.py` runs after every scraper cycle to deduplicate cross-source events. Four detection passes:

### Pass 0 — Within-source google_news_rss dedup
- Runs **before** Pass 1. Fetches all active `google_news_rss` events, **including those with `start_date=NULL`**.
- Pairs events with `name_ja` similarity ≥ 0.85 (`SequenceMatcher` on normalised names).
- Primary selection rules (in order): (1) non-null `start_date` preferred over null; (2) tie → longer `raw_description` wins.
- Secondary: `is_active=False`; `source_url` appended to primary's `secondary_source_urls`.
- **Why needed**: `source_id` for gnews is `gnews_{md5(url)[:12]}` — different articles about the same event have different IDs, so in-scraper dedup misses them. Pass 1 explicitly skips same-source pairs, so Pass 0 must handle this case first.
- **Debug tip**: when investigating gnews duplicates, check Pass 0 log first to confirm whether the pair was detected.
- Print output format: `Done: N pair(s)/orphan(s) merged (Pass 0+1+2+3).`

### Pass 1 — Name similarity (same start_date group)
- Groups all active events by `start_date` (YYYY-MM-DD).
- Within each group, pairs events from different sources with name similarity ≥ 0.85 (`SequenceMatcher` on normalised names).
- Lower `SOURCE_PRIORITY` number wins as primary (strict `<`). Current order: `taiwan_cultural_center` (1) → … → `taiwan_matsuri` (6) → … → `iwafu` (11) → `ide_jetro` (13).
- **`_richness_score()` tiebreaker**: when two events have the **same** `SOURCE_PRIORITY`, the one with the higher richness score is chosen as primary. Scoring (0–10): `official_url` (+1), `start_date` (+1), `end_date` (+1), `location_address` (+1), `location_name` (+1), `raw_description` +1 per 200 chars (capped at 5). Never rely on iteration order to decide primary — always use richness when priorities are equal.
- **annotator pubDate trap**: annotator may fill `start_date` from the article publish date (`pubDate`) rather than the actual event date. If after merging the primary's `start_date` looks like a recent news publish date (not an event date), reset `start_date = NULL` and re-run annotator.

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

**Pass 3 must run after Pass 0+1+2** (so parent merge results are already settled). Print output format: `Done: N pair(s)/orphan(s) merged (Pass 0+1+2+3).`

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
- **`is_active` has exactly three legitimate write sources**:
  1. Admin manually disables a specific event via the admin page.
  2. `merger.py` deactivates a duplicate secondary event.
  3. Scraper or admin sets `is_active=False` when an event's `source_url` is **permanently broken** (DNS failure, 404, domain expired). Do not attempt to preserve these events — a dead source URL means the event can no longer be verified or updated.
  Any other bulk UPDATE setting `is_active = False` is an error. Verify against these three sources before executing.
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

## auto-scraper Phase 2 — LLM CSS selector hallucination

GPT-4o invents plausible-looking CSS classes that look reasonable but are NOT in the sample HTML. The most common fabrications: `.event-card`, `.event-list-item`, `.c-event-list__item-title`, `.post-list-item`. Each hallucination wastes ~30s Playwright sandbox + ~$0.04 LLM cost.

**Defenses (in `scraper/auto_scraper/generate.py`)**:
1. SYSTEM_PROMPT hard rule: "ONLY use CSS classes/IDs that appear VERBATIM in the sample HTML." List common LLM fabrications explicitly. Prefer tag selectors (`article`, `li`) over inventing classes.
2. Pre-sandbox `_validate_selectors_against_html()` using BeautifulSoup (~50ms): confirm `card_selector` matches ≥ 1 element AND `field_selectors.title` / `field_selectors.date` resolve within the first card. Validation failures feed back into the LLM retry loop with explicit error.
3. Researcher's `--card-selector-hint` is the most effective defense — batch e2e on 2026-05-02 showed Phase 2 success rate **17% without hint vs success with hint**. `researcher.agent.md` enforces hint-filling for `feasibility=easy`.

**Generalisable rule**: For any LLM-generated artifact that references real-world data (CSS selectors, file paths, function names, URLs, env var names), add a fast pre-validation step that confirms the reference exists. LLM grounding > LLM trust.

## auto-scraper Phase 2 — Optional-but-critical spec field fallbacks

`spec_schema.json` declares `detail_link_selector` with default `""`. The LLM frequently leaves it empty even though the field is critical: an empty value makes the generated scraper set `source_url = page.url` (the listing URL), which never matches `source_id_url_pattern`, causing every card to be skipped → 0 events.

**Fix (in `scraper/auto_scraper/template.py.j2`)**: When `DETAIL_LINK_SELECTOR == ""`, grab the first `<a href>` inside the card element. Verified: Artist Cafe Fukuoka 0 → 12 events.

**Generalisable rule**: For any optional spec field whose absence breaks the scraper, the **template** (not the LLM) must implement a sensible fallback. Do not expect the LLM to read between the lines of the schema. When adding new optional fields to `spec_schema.json`, ask: "What does the template do when the LLM leaves this empty?" If the answer is "crash" or "skip everything", write a fallback in the template before merging the schema change.
