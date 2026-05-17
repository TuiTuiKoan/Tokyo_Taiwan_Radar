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
- **`.tw` ドメインの SSL 証明書エラー (Missing Subject Key Identifier)**: 台湾政府サイト（`startupterrace.tw` 等）は TLS 証明書に Subject Key Identifier 拡張が欠落しており、`requests` のデフォルト `verify=True` が `SSLCertVerificationError` を raise する。該当サイトには `verify=False` + `warnings.simplefilter("ignore")` を使う helper `_get()` を定義すること。
  ```python
  def _get(url: str) -> requests.Response:
      """GET with SSL verification disabled (cert missing SKI extension)."""
      with warnings.catch_warnings():
          warnings.simplefilter("ignore")
          return requests.get(url, headers=_HEADERS, timeout=15, verify=False)
  ```
  (Incident: startup_terrace `99d9fde`, 2026-05-17.)
- **`start_date`/`end_date` must use `tzinfo=timezone.utc`**: Never pass JST-aware datetimes (`tzinfo=_JST` / `timezone(timedelta(hours=9))`). Supabase stores datetimes in UTC, so `2026-05-08T00:00:00+09:00` → `2026-05-07T15:00:00+00:00` — the calendar date regresses by one day on Vercel's UTC server. Use `datetime(y, m, d, tzinfo=timezone.utc)` to preserve the date. Audit after every fix: `grep -rn "tzinfo=_JST\|tzinfo=JST" scraper/sources/`. (Incidents: Stranger `b7dc34f`, shin_bungeiza `bcb6142`.)
- **Strip null bytes from all scraped text**: Before writing any string to `raw_description`, `name_ja`, or speaker fields, call `.replace("\x00", "")`. Null bytes (`\u0000`) can appear in web-scraped text and cause Postgres error `22P05: unsupported Unicode escape sequence`. (Incident: taiwan_prism.py `c7e9b73` — `×\u0000栖来ひかり` in speakers field broke all 13 events.)
- **`parent_event_id` must be a real UUID, never a source_id string**: `parent_event_id` is a `uuid` column. Passing a source_id string (e.g. `f"scraper_{year}"`) causes Postgres `22P02`. Use `database.get_event_id_by_source(SOURCE_NAME, parent_source_id)` to resolve the UUID. On the **first run**, if parent and sub-events are in the same batch, the parent UUID does not yet exist — `get_event_id_by_source()` returns `None`. Plan for a second run or manual patch to backfill `parent_event_id`. (Incident: taiwan_prism `c7e9b73`)
- **List-page / search-card `location_name` ≠ actual venue (multi-page scrapers):** When a platform shows events on a search/list page AND has a separate detail page, the list card may display the **admin/managing branch** (e.g. `新宿教室`) rather than the **actual venue** (e.g. `立川サテライト教室`). Always fetch the detail page to extract the real `location_name`. Pattern to look for on detail page: table row `備考` → `「会場名」` bracket pattern; fall back to card branch only if the detail page yields nothing. (Incident: `asahiculture` `da3ac31`, 2026-05-15.)
- **Multi-classroom scrapers: detect online courses BEFORE resolving physical address.** Platforms like 朝日カルチャーセンター serve both in-person (classroom) and online courses. If `"オンライン" in raw_title or "オンライン" in location_name`, set `location_name = "オンライン"`, `location_address = None` and skip `CLASSROOM_ADDRESS_MAP` lookup entirely. Failure to check causes the course's managing classroom address to be written to DB even though the event is online-only. (Incident: asahiculture `d617e8c4`, 2026-05-15.)
  ```python
  _is_online = "オンライン" in raw_title or "オンライン" in (detail["location_name"] or "")
  if _is_online:
      location_name, location_address = "オンライン", None
  else:
      location_name = detail["location_name"] or card_branch
      location_address = detail["location_address"] or CLASSROOM_ADDRESS_MAP.get(location_name)
  ```
- **Use `re.findall()` for start/end date ranges, never `re.search()`:** Strings like `"2026/04/07火～2026/06/16火"` contain two full dates. `re.search()` stops at the first match, silently dropping `end_date`. Use `re.findall(pattern, text)` then take `matches[0]` as `start_date` and `matches[-1]` as `end_date`. Single-day events have `len(matches) == 1` → `end_date = None`. (Incident: `asahiculture_8759178`, 2026-05-15.)
- **Keyword-filtered description scan silently hides structured fields:** If `_fetch_detail*` only collects paragraphs containing Taiwan keywords (`台湾/Taiwan`), any structured field in a non-keyword section — lecturer `<h3>`, schedule table, venue `備考` row — will never be captured. Always scan the full detail page with separate passes for each structured field type (table rows, headings) **independent of keyword filtering**. (Incident: `asahiculture` performer `村山 秀太郎` extracted as `"記"`, 2026-05-15.)
- **`location_address ≠ location_name` rule (ALL scrapers):** `location_address` must NEVER equal `location_name`. When a scraper has a single combined "location" field, parse it: venue name → `location_name`, street address (using `_ADDR_RE`: `〒` or prefecture+city+street pattern) → `location_address`. If no real street address can be extracted, set `location_address = None`. This is enforced by `auto_qa_address_is_venue_name` detector. Also note: `_ai_or_existing()` in annotator preserves non-null DB values, so a scraper writing the wrong value cannot be corrected by the annotator.
- **Fixed-venue scrapers (cinema, gallery, theater) MUST set `organizer=` and `organizer_type=["commercial_brand"]`:** `location_name` is stored in DB and shown in the venue column, but it does NOT appear in the admin event card. The 🏢 venue line in the event card is powered by the `organizer` field. A fixed-venue scraper that sets only `location_name` without `organizer` produces events that look venue-less in the admin list. Correct pattern (see `kyoto_cinema.py`, `kino_shinsaibashi.py`, `sakurazaka.py`):
  ```python
  location_name="シネマ・クレール 丸の内１・２",
  location_address="岡山市北区丸の内１丁目５−１",
  organizer="シネマ・クレール",
  organizer_type=["commercial_brand"],
  ```
  (Incident: `cinemaclair.py` and `human_trust_cinema.py` missing `organizer=`, 2026-05-15.)
- **Never restrict geographic scope**: The project covers all of Japan（全日本）. Regional keyword filters (e.g. `_TOKYO_KANTO_KEYWORDS`) must never be added to any scraper.
- **Date-parser helper functions must have exhaustive return paths**: Any `_extract_dates()` / `_parse_*_date()` helper must have an explicit `return` on every branch — never rely on Python's implicit `None`. A function that falls through returns `None`, and callers that do `start, end = helper()` will raise `TypeError: cannot unpack non-iterable NoneType object` — this is silently swallowed by outer try-except, causing the entire page's events to be dropped with **no ERROR log**. Add `return None, None` as the final fallback. (Incident: peatix `_extract_peatix_dates`, commit `2a9540c`, 7 days of silent 0 events.)
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
- **⚠ Rewriting main.py drops all registrations**: When adding a new scraper, NEVER regenerate the full imports+SCRAPERS block from scratch — always append to the existing list. In commit `045d1fa`, adding WasedaICL by rewriting main.py silently dropped 24 scrapers that ran without error for weeks (`6a83c64` restored them). SCRAPERS count before any commit: `python3 -c "import re; print(len(re.findall(r'\\w+Scraper\\(\\)', open('scraper/main.py').read())))"` — if count drops vs prior commit, something was lost.
- **Source removal procedure (3-step atomically)**: When removing a scraper entirely:
  1. Remove `import` from `main.py`
  2. Remove `ScrapeClass()` from `SCRAPERS` in `main.py`
  3. Hard delete existing DB records: `sb.table('events').delete().eq('source_name', '<source_name>').execute()`
  All 3 steps must happen in the same session. Missing step 3 leaves stale data visible in production.
- **Promotion checklist (新規スクレイパー完成時 — auto_generate 問わず全件適用)**: 新しい scraper ファイルを作成した時点で、以下 5 ステップを **同一 session** で完了すること。ファイル作成 ≠ 完成。
  1. `scraper/sources/<name>.py` 作成・dry-run 確認済み。
  2. `scraper/main.py` — import + `SCRAPERS` 登録済み（下記 SCRAPERS audit で確認）。
  3. `research_sources` row — `status = 'implemented'`。
  4. **`research_sources.scraper_source_name = '<scraper key>'`** — 手動で必ず入力。`auto_generate` も Researcher も書かない。省略すると `/admin/sources` のイベント数が 0 になり、「今すぐ実行」ボタンも非表示になる（backend が `scraper_runs` を source_name で JOIN するため）。
  5. 下記 **Combined Post-Build Audit** を実行し ALL CLEAR を確認。
  - **⚠ 必須在同一個 session で全 5 ステップを完了すること。** 途中で session を切ると研究状態が中断し、`research_sources` 未登録のまま scraper が CI に入る。
  - **`update_source.py` は `researched`/`not-viable` のみ対応。** `implemented` ステータスは `update_source.py` で設定できない — Supabase SDK で直接 upsert する必要がある:
    ```python
    sb.table("research_sources").upsert({
        "url": "<listing_url>",
        "name": "<display name>",
        "status": "implemented",
        "scraper_source_name": "<source_key>",
        "scraping_feasibility": "medium",  # or easy/hard
        "agent_category": "event_listing",
    }, on_conflict="url").execute()
    ```

## ⚡ Combined Post-Build Audit — 新規 scraper 完成後に必ず実行

**新しい scraper ファイルを作成・編集するたびに、task_complete 前に必ずこのコマンドを実行し、両方 ALL CLEAR を確認すること。**

```bash
cd scraper && python3 -W ignore - << 'AUDIT'
import re, glob, os, sys
from dotenv import load_dotenv; load_dotenv('.env')
from supabase import create_client

errors = []

# ── 1. SCRAPERS registration audit ──────────────────────────────────────────
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        errors.append(f'❌ UNREGISTERED in main.py: {m.group(1)} ({f})')
if not any('UNREGISTERED' in e for e in errors):
    print('✅ SCRAPERS: all registered')

# ── 2. research_sources.scraper_source_name audit ───────────────────────────
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
rows = sb.table('research_sources').select('name,scraper_source_name,status').eq('status','implemented').execute().data
missing = [r for r in rows if not r['scraper_source_name']]
if missing:
    for r in missing:
        errors.append(f'❌ scraper_source_name NULL: "{r["name"]}" (status=implemented)')
else:
    print('✅ research_sources: all implemented rows have scraper_source_name')

# ── Result ───────────────────────────────────────────────────────────────────
if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print('🎉 ALL CLEAR — safe to commit')
AUDIT
```

**出力例（正常）:**
```
✅ SCRAPERS: all registered
✅ research_sources: all implemented rows have scraper_source_name
🎉 ALL CLEAR — safe to commit
```

**エラー例（未対応時）:**
```
❌ UNREGISTERED in main.py: TsutayaPortalScraper (sources/tsutaya_portal.py)
❌ scraper_source_name NULL: "蔦屋書店ポータル（台湾キーワード横断検索）" (status=implemented)
```
- **`meta.json` に `source_name` / `class_name` がない場合は `generated.py` 先頭を直接確認する**: `auto_scraper/runs/{id}/meta.json` に `source_name` が含まれていない場合がある。その場合は `auto_scraper/runs/{id}/generated.py` の先頭数行を読んで `class XxxScraper(BaseScraper):` を探す。クラス名から `source_name` は snake_case 変換で導ける（`BookAndBeerScraper` → `bookandbeer`）。
- **auto-scraper feature branch は生成後 24 時間以内にマージする**: `SCRAPERS` リストは全員が同じ行/ブロックを編集するため、放置するほど conflict が深刻化。長期放置 → 複数の scraper 追加コミットが main に積まれ → マージ時に手動解決が必要になる（commit `7cedc68` の Artist Cafe 衝突事例）。
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

## WordPress RSS — `<strong>` Strip 後空格問題

**Rule**: WordPress RSS の `<description>` を BeautifulSoup で parse すると、`<strong>` 等の inline タグ除去後に数字の間に空白が挿入される（例：`"2026 年 1 月 31 日"`）。日付 regex では `\d` と漢字の間を `\s*` で繋ぐこと。

```python
# ✅ 正確：\s* で tag-strip artifact を吸収
_DATE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")

# ❌ 誤り：スペース固定 or スペースなし — WordPress 環境では失敗する
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
```

**適用範囲**：WordPress 6.x 以降の全 RSS ベース scraper。`get_text()` / `get_text(strip=True)` を問わず発生する。

Reference incident: 2026-05-12 — `nittai_toumonkai.py`（WordPress 6.9.4）の `<description>` で `2026 年 1 月 31 日` 形式を確認。

## venue regex 負向前瞻 — `(?!<後綴詞>)` 誤匹配防止

**Rule**: `会場`、`場所`、`開催場所` 等の venue キーワード regex に負向前瞻を追加して複合語の誤マッチを防ぐ。

```python
# ✅ 正確：会場受付 を venue として拾わない
_VENUE_RE = re.compile(r"会場(?!受付)[：:]\s*(.+)")

# ❌ 誤り：会場受付 も venue として抽出してしまう
_VENUE_RE = re.compile(r"会場[：:]\s*(.+)")
```

**要注意の複合語一覧**：`会場受付`、`会場費`、`会場変更`、`会場案内`
各 regex 追加時に上記複合語を検討し、必要に応じて `(?!受付|費|変更|案内)` を付与すること。

Reference incident: 2026-05-12 — `nittai_toumonkai.py` で `会場受付` が venue name として誤抽出。

## Venue / 日時ラベル抽出 — セパレーター量詞と `get_text` 使い分け

### セパレーター文字クラスは `+`（1 回以上）にする

venue・日時ラベル（`会場`、`場所`、`開催場所`、`日時` 等）の後ろに続くセパレーター文字クラスは必ず `+` にする。`*` を使うと本文中の同名の一般名詞（例：`称揚する場所」...`）にマッチしてゴミテキストを venue として取得してしまう。

```python
# ✅ 正確：セパレーターが最低 1 文字必要
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]+([^\n]{3,60})")

# ❌ 誤り：セパレーターなし（0 回）でもマッチ → 本文中の一般名詞に誤マッチ
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]*([^\n]{3,60})")
```

### `get_text("\n")` と `get_text(" ")` の使い分け

| 用途 | 推奨 | 理由 |
|------|------|------|
| venue・日時（構造依存、`[^\n]` を使う regex） | `get_text("\n", strip=True)` | HTML ブロック境界が `\n` に変換され `[^\n]` がブロック内で停止する |
| 日付・概要・キーワード判定（改行不要） | `get_text(" ", strip=True)` | 1 行テキストで regex が扱いやすい |

両バリアントを変数として保持するのが安全：

```python
full_text    = soup.get_text(" ",  strip=True).replace("\x00", "")  # 日付・概要用
full_text_nl = soup.get_text("\n", strip=True).replace("\x00", "")  # venue・日時用

mv = _VENUE_RE.search(full_text_nl)   # ✅ [^\n] がブロック境界で停止
md = _DATE_RE.search(full_text)        # ✅ 改行なし 1 行テキストで日付 regex
```

`get_text(" ")` のみで venue regex を走らせると、会場行と次のセクション（プログラム・講師情報 etc.）が 1 行に結合されるため、`[^\n]{3,60}` が 60 文字まで次のセクションを取り込む。

Reference incident: 2026-05-15 — `snet_taiwan.py` で `場所` が本文に誤マッチ（量詞 `*` 修正）後も `get_text(" ")` によりプログラム情報が混入（`get_text("\n")` 導入で解決）。

## 全形数字 — `unicodedata.normalize("NFKC")` 事前変換

**Rule**: 日本語ウェブページの数字は全角（`２０２６年`）で記述されている場合がある。parse 前に `unicodedata.normalize("NFKC", text)` で半角に統一すること。

```python
import unicodedata

def _fw_to_ascii(self, text: str) -> str:
    """全形数字・記号を半形に変換する。"""
    return unicodedata.normalize("NFKC", text)

# parse pipeline
text = self._fw_to_ascii(raw_text)
m = _DATE_RE.search(text)  # \d が全角を拾い損ねない
```

**適用範囲**：全角数字が出現しうる全 scraper（特に団体サイト・勉強会系）。`BeautifulSoup.get_text()` は全角のまま返すため変換は必須。

Reference incident: 2026-05-12 — `nittai_toumonkai.py` 本文に `２０２６年` が出現。

## Jimdo / 一部 CMS — URL パス encoding 不統一 → `unquote(href)`

**Rule**: Jimdo, 一部の WordPress, FC2 等のCMSは、`<a href>` の日本語パスをあるページでは URL-encode し、別のページでは生の日本語文字で出力する。比較・重複排除を行う前に `unquote()` で正規化すること。

```python
from urllib.parse import unquote, urljoin

href = a.get("href", "")
normalized = unquote(href)  # %E3%83%96%E3%83%AD%E3%82%B0 → ブログ
full_url = urljoin(base_url, normalized)
```

**注意**：`urljoin` は encode 済み URL も未 encode URL も正しく処理するが、比較は必ず decode 後に行うこと（`/ブログ/` と `/%E3%83%96%E3%83%AD%E3%82%B0/` は同一 URL だが文字列比較では不一致）。

Reference incident: 2026-05-12 — `tsudoi_osaka.py`（Jimdo CMS）の href に encoding 不統一が確認された。

## POST 検索フォームサイト — `requests.post` + 302 追跡

大学・機関サイトの検索機能は GET パラメータでなく POST body を使うことが多い。

**必須確認**：ブラウザ devtools の Network タブまたは `curl -v` でフォームの `method` 属性を確認する。

```python
# ✅ POST 検索 — Cookie なし、302 自動追跡
resp = requests.post(
    "https://www.wuext.waseda.jp/course/search-list/",
    data={"keyword": "台湾", "page": 1},
    allow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30,
)

# ❌ GET パラメータは無視される（POST フォームサイト）
resp = requests.get("https://www.wuext.waseda.jp/course/search-list/?keyword=台湾")
```

**規則**:
- POST フォームサイトは Cookie なしで動作することが多い（まず試す）。セッション Cookie が必要な場合のみ `requests.Session()` を使う。
- `allow_redirects=True` で 302 を自動追跡する。
- `form[method="post"]` サイトへの GET リクエストは検索結果でなくデフォルトページを返す。結果が 0 件の場合は必ず POST を試すこと。

Reference incident: 2026-05-13 — `wuext_waseda.py` で `?keyword=台湾` GET が無視され 0 件。POST に変更で正常動作。

## 大学・機関サイト — コンテンツコンテナと台湾フィルタ

### 本文コンテナの特定

大学・機関サイトの detail ページは固有の `id` または `class` を持つコンテンツコンテナを使う。

```python
# ✅ 早稲田エクステンション: id="course"
content = soup.find(id="course") or soup.find("main") or soup

# ❌ find('body') はナビゲーション・サイドバー・フッターを含む — キーワード判定が不正確
content = soup.find("body")
```

**手順**:
1. `curl -s <url> | grep -E 'id=|class=' | head -30` でコンテナ候補を列挙する。
2. ブラウザ devtools で実際のコンテンツ div を確認する。
3. `id` を優先し、なければ `class` セレクターを使う。`find('main')` は最終手段。

**要注意のサイト別コンテナ例**:
- 早稲田エクステンション（wuext_waseda）: `id="course"`
- 朝日カルチャーセンター（asahiculture）: `div.course-detail` / `備考` `th/td` row

### 台湾フィルタは詳細ページ本文まで検索する

大学講座・機関イベントはタイトルに「台湾」を含まず、本文のみで台湾を言及する場合が多い（例: 「緊迫する世界状勢と現代地政学」「台湾有事」を内容で扱う）。

```python
_TAIWAN_KEYWORDS = ("台湾", "台北", "台中", "高雄", "台南", "日台", "台日", "中華民国")

def _is_taiwan_content(self, title: str, detail_soup) -> bool:
    """タイトルまたは詳細ページ本文に台湾キーワードが含まれるか判定する。"""
    if any(kw in title for kw in _TAIWAN_KEYWORDS):
        return True
    content = detail_soup.find(id="course") or detail_soup
    body_text = content.get_text(" ", strip=True)
    return any(kw in body_text for kw in _TAIWAN_KEYWORDS)
```

**規則**:
- 詳細ページ取得が価格・日付抽出と兼用できる場合は必ず本文フィルタを有効にする。
- タイトルのみフィルタは教育・学術系サイトでは収録漏れが多い。
- `_TAIWAN_KEYWORDS` は最低限 `台湾` `日台` `台日` を含めること。

Reference incident: 2026-05-13 — `wuext_waseda.py` でタイトルのみフィルタにより「緊迫する世界状勢と現代地政学」等が脱落。

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

### On-Demand / Viewing Period — detail page date extraction

When a listing table cell has only a term name (e.g. `2025年度 冬期 全4回`) with no explicit date range,
the actual start/end dates are often embedded in the **detail page body** as `(YYYY/MM/DD)` or `YYYY年MM月DD日`.

**Priority order for on-demand / date-less courses:**
1. **Tier 1**: Parse explicit date range from listing column (e.g. `07月04日～07月25日`)
2. **Tier 2**: Extract `(YYYY/MM/DD)` or `YYYY年MM月DD日` from detail page body — take earliest as `start_date`, latest as `end_date`
3. **Tier 3**: Term fallback (`春期`→4/1, `夏期`→7/1, `秋期`→10/1, `冬期`→1/1 of next calendar year)

```python
_DETAIL_DATE_PARENS_RE = re.compile(r"\((\d{4})/(\d{1,2})/(\d{1,2})\)")

def _extract_detail_dates(detail_soup):
    text = (detail_soup.find(id="course") or detail_soup).get_text(" ", strip=True)
    found = []
    for m in _DETAIL_DATE_PARENS_RE.finditer(text):
        found.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc))
    found.sort()
    return (found[0], found[-1] if len(found) > 1 else None) if found else (None, None)
```

**Always try detail page dates before term fallback** — term fallback yields `YYYY-01-01` / `YYYY-04-01`
which shows as "日期未定" on the web UI and misleads users.

Reference incident: 2026-05-14 — wuext_waseda event `30bdfc30`「台湾と日本―興味の台湾案内」
had `start_date=2026-01-01` (term fallback). Actual viewing period `(2025/11/26)～(2026/04/30)`
was in the detail body. Fixed in commit `bacd4cd`.

### annotator `or event.get("end_date")` fallback — blind spot
The pattern `annotation.get("end_date") or event.get("end_date")` only rescues the scraper's value when GPT returns `null`. When GPT returns a **non-null wrong value** (most commonly SINGLE-DAY RULE: `end_date = start_date`), the `or` branch is never reached — the wrong value is written to DB. Fix: always embed the correct date range in `raw_description` (see § `開催日時:` prefix above) so GPT never needs to fall back to SINGLE-DAY RULE in the first place.

## Contentful CDA — 年度系列展日期 slug Fallback

**問題**：Contentful 年度系列展使用 `scheduleStartsOn=YYYY-01-01` 作為財年佔位符。  
**偵測**：`start_date.month == 1 and start_date.day == 1`  
**修復**：從 URL slug 末尾提取真實日期：
```python
slug_m = re.search(r"/(\d{4}-\d{2}-\d{2})$", slug)
if slug_m and start_date and start_date.month == 1 and start_date.day == 1:
    start_date = self._parse_date(slug_m.group(1))
```
**驗證**：乾跑後確認無事件 start_date 為 Jan 1。

Reference incident: 2026-05-05 — event 6a91a4ce (アジア美術の歩き方 東アジア編) scheduleStartsOn=2026-01-01 為佔位符，真實日期 2026-04-18 在 slug 末尾 (commit a1e58a9)。

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

**Auto-generated scraper 的 detail_url 補全規則**（spec_to_code template 生成的 `_extract_cards` 模式）：
```python
# ✅ 必須同時處理兩種相對路徑形式
if detail_url and detail_url.startswith("/"):
    detail_url = f"{BASE_URL}{detail_url}"
elif detail_url and not detail_url.startswith("http"):
    detail_url = f"{BASE_URL}/{detail_url}"  # document-relative path
```
只處理 `/` 前導的版本無法捕捉 `cinema/2026/event/...` 這類 document-relative URL，會讓 source_url 儲存為相對路徑並讓 detail page 開啟失敗（`raw_description = None`）。**Incident**: `cine_gallery.py` 事件 `cdf5e555`（2026-05-14，[scraper-expert/history.md]）。

## BeautifulSoup 多行文字提取 — `separator="\n"`

**Rule**: 任何需要保留行結構的文字提取（排程、場次、地址、時間表等），必須使用 `separator="\n"`。

```python
# ✅ 正確：保留行結構
text = element.get_text(separator="\n", strip=True)

# ❌ 錯誤：連續 inline 元素的文字直接拼接，時間/場次資訊擠在一起
text = element.get_text(strip=True)
```

**Incident**: `gguide_tv.py` 排程文字缺 `separator="\n"`，時間資訊擠在一起（commit `a895e07`）。

## Cinema scraper — `end_date` と `business_hours` 完全規則

> **適用対象**: 全ての cinema scraper（`category=["movie"]` を持つ全 scraper）

### 分類ごとの実装パターン

日本の電影院 scraper は**3タイプ**に分類される。タイプごとに `end_date` と `business_hours` の取得戦略が異なる。

---

#### Type 1: 票務平台分離型（例: starcat_cinema）

**特徴**: 主サイト（eiga.starcat.co.jp）は映画情報・あらすじのみ。場次時間と排片日程は**別の票務平台**（starcat-ticket.com など）に存在する。

**`end_date` 規則**: 日本の映画館は毎週木曜日に翌週（金曜〜木曜）の上映スケジュールを発表する。したがって:
- `end_date` = 票務スケジュール内のその映画の**最後の日（当週木曜）**
- `_build_ticket_schedule()` は `dict[str, tuple[str, Optional[datetime]]]` を返す: `(business_hours_str, last_date_utc)`
- 上映スケジュールに未登場の映画（未公開または上映終了）: `end_date = None`
- 每次 CI 実行で `end_date` は自動延伸（滚动视窗）

**`business_hours` 規則**: `_build_ticket_schedule(ticket_url)` から取得。形式: `M/DD(曜): HH:MM〜HH:MM`（複数日は `\n` 区切り）

**`raw_description` 前綴必須規則（SINGLE-DAY RULE 防止）**:
```python
# end_date が start_date と異なる場合、必ず完整な期間範囲を前綴に入れる
if start_date and schedule_end and schedule_end != start_date:
    date_prefix = f"上映期間: {start_date.year}年{start_date.month}月{start_date.day}日〜{schedule_end.year}年{schedule_end.month}月{schedule_end.day}日"
# ❌ NG: "2026年5月15日(金)より公開" のみ → annotator SINGLE-DAY RULE → end_date = start_date
```

**参考実装**: `starcat_cinema.py` — `TICKET_SCHEDULE_URLS` + `_build_ticket_schedule()` + `_lookup_schedule_entry()` + `_lookup_end_date()` + `_lookup_business_hours()`

---

#### Type 2: 排片表嵌入型（例: shin_bungeiza, cinemart_shinjuku, ks_cinema, rightscube）

**特徴**: 映画詳細ページ内に上映スケジュール（日付 + 時刻）が直接含まれる。

**`end_date` 規則**: `max(dates in schedule)` — スケジュール内の最終日
```python
end_date = max(parsed_dates, default=None)
```

**`business_hours` 規則**: HTML スケジュール要素から直接抽出。常見容器:
- `div.schedule-program` (shin_bungeiza)
- `div.schedule-table` / `table.schedule` (各映画館)
- `dl.showtime` / `ul.times` (単館映画館)
- `p.nihon-date` + `div.program` 組合せ (shin_bungeiza パターン)

日付ヘッダー（`<h2>` / `<p class="nihon-date">`）と上映時刻（`<div class="schedule-program">`）が**別要素**の場合は両者を組み合わせる:
```python
business_hours = "\n".join(
    f"{date_label}: {' '.join(times)}"
    for date_label, times in schedule_map.items()
)
```

---

#### Type 3: 上映中リスト型（例: cineswitch_ginza, human_trust_cinema, uedaeigeki）

**特徴**: 現在上映中 / 近日公開映画のカード一覧ページ。詳細な場次時間は別ページまたは別プラットフォームに存在する。

**`end_date` 規則**: カードに `"M/D まで"` / `"〜M/D"` / `"終映日：M/D"` / `"※M/D で上映終了"` ラベルがある場合はそこから解析。ない場合は `None`（推測禁止）。

**`business_hours` 規則**: リストページに場次時間がない場合は `None`。ただし詳細ページに時刻がある場合は詳細ページを取得して抽出する（コスト対効果を考慮すること）。

---

### 共通禁止事項

1. **`end_date = start_date` は禁止**: `end_date` を設定する場合、少なくとも `start_date + 1日` でなければならない。`start_date` と同じ値は scraper 内で検出して `None` に戻すこと。
2. **空文字列 `business_hours = ""` 禁止**: 場次が取得できない場合は `None` を設定。空文字列は DB に不要なデータを残す。
3. **推測による `end_date` 禁止**: 「通常2〜3週間上映」などの仮定で `end_date` を算出してはいけない。ソースから取得できない場合は `None`。
4. **視覚上に場次時間があるのに `business_hours = None` は scraper bug**: サイトを目視確認して時刻要素のセレクタを追加すること。
5. **`event_form=["screening"]` 必須**: 全 cinema scraper は `event_form=["screening"]` を設定すること。DB check constraint（migration 047）の valid 値: `'exhibition','screening','lecture','performance','market','workshop','conference','networking','screening_with_talk','tour','competition','tasting','broadcast','study_abroad','other'`。`"film_screening"` は **DB に存在しない**（constraint エラー）。（Incident: `kyoto_cinema`・`sakurazaka`・`kino_shinsaibashi`・`human_trust_cinema` で `"film_screening"` を誤設定 → constraint 違反、commit で revert）

### JST ISO datetime パース規則

一部 CMS（TTCG など）は `data-date="2026-05-15T00:00:00+09:00"` のような JST-aware ISO 文字列を出力する。**`.replace("+09:00", "")` パターンは禁止** — JST offset を除去しても naive datetime が生成されるだけで UTC 変換にならない。

```python
# ✅ 正確：JST-aware parse → UTC midnight
dt_jst = datetime.fromisoformat(data_date)  # 2026-05-15 00:00:00+09:00
start_date = datetime(dt_jst.year, dt_jst.month, dt_jst.day, tzinfo=timezone.utc)

# ❌ 誤り：offset を strip した naive datetime になる
start_date = datetime.fromisoformat(data_date.replace("+09:00", ""))
```

Incident: `human_trust_cinema` commit `7849021`。

### Annotator SINGLE-DAY RULE 防護

`raw_description` に**単一の日付**しか含まれない場合、annotator は `end_date = start_date` と設定する（SINGLE-DAY RULE）。Cinema scraper では以下を守ること:

- `raw_description` の前綴に**必ず上映期間全体**を記載する: `上映期間: YYYY年M月D日〜YYYY年M月D日`
- Type 1 scraper で `end_date` が取得できた場合は前綴を期間表示に置き換える（単日 `より公開` 記述のまま放置しない）
- **Type 3 で `end_date` が取得不可の場合は date prefix を入れない**: サイトに end_date 情報がない場合に `"上映開始: YYYY年M月D日"` を入れると SINGLE-DAY RULE が発動し `end_date=start_date` に上書きされる。`start_date` はフィールドに正しく格納済みなので raw_description に繰り返す必要はない。（Incident: `human_trust_cinema` commit `7849021`）

### 稽核表 ghost エントリ防止

稽核表に新行を追加する前に、ファイルの実在を確認すること:
```bash
ls scraper/sources/<name>.py
```
不存在のファイルを稽核表に記載すると後続の修復作業で混乱を招く。（Incident: `ciemarine` 行 — ファイル不存在のまま記載されていたため削除）

### 現況稽核表（2026-05-15 時点）

| Scraper | Type | `end_date` | `business_hours` | 状態 |
|---------|------|-----------|-----------------|------|
| cinemart_shinjuku | 2 | ✅ max(dates) | ✅ cineticket.jp | 完全準拠 |
| shin_bungeiza | 2 | ✅ h2 dates max | ✅ schedule-program | 完全準拠 |
| starcat_cinema | 1 | ✅ 木曜末日 | ✅ starcat-ticket.com | 完全準拠 |
| rightscube | 2 | ✅ THEATER区段 | ✅ business_hours_text | 完全準拠 |
| ks_cinema | 2 | ✅ 表格期間 | ✅ schedule_text (commit `23e417f`) | 完全準拠 |
| kino_shinsaibashi | 3 | ✅ 終映日 | ❌ None（JS 驅動，Type 3 可） | 完全準拠（`screening` + prefix, commit `544bbc4`） |
| kyoto_cinema | 3 | ✅ 終映日M/D | ❌ None（Type 3 可） | 完全準拠（`screening` + prefix, commit `e91f5cd`） |
| cineswitch_ginza | 3 | ✅ M/D まで | ❌ None（Type 3 可） | 完全準拠（UTC fix, commit `e91f5cd`） |
| theater_enya | 3 | ✅ 期間文字 | ❌ None（Type 3 可） | 完全準拠（UTC fix, commit `e91f5cd`） |
| cinewind | 2 | ✅ YYYY/M/D | ❌ None（Type 2, 追加調査要） | UTC 修正済み（commit `e91f5cd`） |
| ciema | 2/3 | ✅ 週表頭 | ❌ None（Type 3 可） | 完全準拠（UTC fix, commit `e91f5cd`） |
| cinemadict | 2 | ✅ 完整期間（UTC fix） | ✅ date_text HH:MM（commit `544bbc4`） | 完全準拠 |
| ycam_cinema | 2 | ✅ 節目期間 | ❌ None（Type 2, 追加調査要） | UTC 修正済み（commit `e91f5cd`） |
| sakurazaka | 3 | ✅ 上映中/予定 | ❌ None（Type 3 可） | 完全準拠（`screening`, commit `e91f5cd`） |
| uedaeigeki | 2 | ✅ 上映日程 | ❌ None（Type 2, 追加調査要） | UTC + prefix 修正済み（commit `e91f5cd`） |
| human_trust_cinema | 3 | ❌ None（サイト非公開, JS-driven） | ❌ None（同上） | UTC+event_form 完了（commit `7849021`→revert）, end_date はサイト制限 |
| theater_kino | 2 | ✅ 静的HTML | ❌ None（Type 2, 追加調査要） | UTC + prefix 修正済み（commit `e91f5cd`） |

**新規 cinema scraper 作成時は、上記稽核表に行を追加すること。**

**Incidents:**
- shin_bungeiza（commit `1ffb98e`）— `_parse_nihon_date_only()` が `<h2>` 日付のみ取得し `<div class="schedule-program">` の場次時間を無視。
- starcat_cinema（2026-05-15）— 主サイトに場次なし → `starcat-ticket.com` から別途取得。`end_date=None` が annotator SINGLE-DAY RULE で `start_date` に上書きされた。

---

## auto_qa 地名關鍵字設計規則

- `TAIWAN_VENUE_KEYWORDS` 必須使用完整行政單位名（`台北市`、`新北市`），禁用裸縮寫（`台北`、`新北`）以避免日本地名假陽性
- 新增關鍵字前：`grep -rn "<keyword>" scraper/sources/` 確認不在任何已知日本地名中
- 假陽性無法靠 dismiss 解決：dedup 邏輯在 `updated_at > confirmed_at` 時重新觸發；根治需修正關鍵字

Reference incident: 2026-05-05 — `'新北'` 匹配大阪市 `新北島`，event 371cf624 (GRAFFYHALL) 連續三次 auto_qa_taiwan_venue (commit 6b7174a)。

## Performer Job Title Guard

**Rule**: `performer` 欄位只能填**人名**，不可填職稱/職業描述。

下列詞彙單獨出現時必須視為職稱並設 `performer = null`：
- 日語職稱：`シェフ`、`料理人`、`講師`、`先生`、`司会`、`ゲスト`、`ホスト`、`演者`、`指揮者`、`伴奏者`
- 中文職稱：`主廚`、`老師`、`講師`、`主持人`

**判斷規則**：
1. `performer` 字串若**只含**職稱詞且無可辨識人名（CJK 人名 ≥ 2 字、或拉丁姓名）→ 設 null
2. `_extract_performer_from_raw()` 的 role list regex 命中後，必須確認後方緊跟的是人名而非獨立職稱

**Regex guard 範例**（加在 `_extract_performer_from_raw` 最後）：
```python
_JOB_TITLE_ONLY_RE = re.compile(
    r"^(シェフ|料理人|講師|先生|司会|ゲスト|ホスト|演者|指揮者|伴奏者|主廚|老師|主持人)$"
)
if _JOB_TITLE_ONLY_RE.fullmatch(candidate.strip()):
    return None
```

Reference incident: 2026-05-08 — 湾.味(ワンウェイ) 台湾料理体験会 `performer='シェフ'` 應為 null。

## ZERO_EVENT_OK_SOURCES — 偶發性 scraper 零事件豁免

**Rule**: 合法情況下絕大多數時間返回 0 events 的 scraper，必須加入 `health_check.py` 的 `ZERO_EVENT_OK_SOURCES` 集合，避免 CI 每日觸發假「missing」警告。

**加入標準**（三項全符合）：
1. Scraper 邏輯已驗證正確（dry-run 通過、已 commit）
2. 台灣相關內容為**偶發性**（年 0–3 次，如藝廊特展、部分影院）
3. 0 events 是預期行為，不代表爬蟲失敗

**反模式**：不應因「通常有 0 events」就忽略加入此集合——遺漏會導致每次 CI 都需人工確認雜訊。

**實作位置**：`scraper/health_check.py` → `ZERO_EVENT_OK_SOURCES: set[str]`

Reference incident: 2026-05-08 — `whitestone_gallery` 加入 `ZERO_EVENT_OK_SOURCES`（台灣藝術家展覽為偶發性）。

## organizer_zh/en FC 跨事件污染偵測

**Rule**: `organizer_zh`/`organizer_en` 若含有在 `raw_title + raw_description` 中**完全找不到**的內容，即為 FC 跨事件污染（cross-event field_corrections pollution）。

**污染機制**：annotator 的 few-shot context 中，若前一事件的 FC 資料帶入了 `organizer_zh/en`，GPT 可能將該值套用到當前事件——即使兩者完全無關。`annotation_status = annotated` 不會重新觸發驗證，因此污染可長期潛伏。

**偵測查詢**（定期執行）：
```sql
SELECT id, organizer_zh, organizer_en, source_name
FROM events
WHERE organizer_zh IS NOT NULL
  AND raw_description NOT ILIKE '%' || split_part(organizer_zh, ' ', 1) || '%'
  AND raw_title NOT ILIKE '%' || split_part(organizer_zh, ' ', 1) || '%'
LIMIT 50;
```

**修正流程**：確認污染後，手動設 `organizer_zh/en` 正確值，並在 `field_corrections` 鎖定 `organizer`、`organizer_zh`、`organizer_en`、`performer`（避免再次被 annotator 覆寫）。

Reference incident: 2026-05-08 — `fe03288b`/`b8621ee9`（湾.味 台湾料理体験会）`organizer_zh/en` 含上田村振興会・普門寺資料，與 raw_description 完全無關。

## Frontend Client Component — UTC 日期表示一貫性ルール

**Rule**: DB に保存された timestamp は UTC。Next.js の client component で `new Date(dateStr)` を使う場合、ブラウザの TZ が UTC でなければ `getDate()` / `getMonth()` は**ローカル時間**で評価される。JST（UTC+9）では `UTC 15:00` が翌日 `00:00` に見えて日付が 1 日ずれる。

**修正パターン**:

```typescript
// ✅ 正確：UTC 日付として取り出す
const d = new Date(dateStr)
const day = d.getUTCDate()       // getDate() ではなく getUTCDate()
const month = d.getUTCMonth() + 1
const year = d.getUTCFullYear()

// ✅ toLocaleDateString も timeZone: "UTC" 必須
d.toLocaleDateString("ja-JP", { timeZone: "UTC", month: "short", day: "numeric" })

// ❌ 誤り：ブラウザ TZ に依存
const day = d.getDate()
d.toLocaleDateString("ja-JP", { month: "short", day: "numeric" })
```

**対象**: client component 内で `Date` オブジェクトを生成・操作する全コード。SSR（Node.js は UTC 環境）との整合性のために必須。

**根本原因**: 爬蟲が JST 時間を `+00:00` として保存（tzinfo=timezone.utc）しているため、DB の `2026-06-13T00:00:00+00:00` は実際には JST `2026-06-13 09:00`（問題なし）だが、scraper によっては深夜値（`15:00 UTC = 翌日 00:00 JST`）が混入する可能性がある。Client side では常に UTC で読む実装が最も安全。

Reference incident: 2026-05-12 — `EventListClient.tsx` / `MovieWorksList.tsx` の `getDate()` が JST ブラウザで 1 日ずれ → `getUTCDate()` + `{ timeZone: "UTC" }` に修正。

**Rule**: 聚合站 scraper（ftip、prtimes、gnews、walkerplus 等）的 `source_url` 必須**永遠保留**聚合站自身的 URL。從文章中提取的第一方主辦方 URL 存入 `official_url`，不可覆寫 `source_url`。

**正確分工**：
- `source_url` = 聚合站頁面 URL（`https://www.ftip-japan.org/NNN`、`https://prtimes.jp/...`）— 資料溯源憑證
- `official_url` = 提取的第一方官方 URL（活動官網、Facebook event 頁、主辦方網站）；無法提取時為 `None`

**常見提取模式**（ftip content 中的 `公式サイト` 格式）：
```python
_OFFICIAL_URL_RE = re.compile(
    r"公式サイト\s+(https?://\S+|[\w.-]+\.\w{2,}(?:/\S*)?)",
    re.IGNORECASE,
)

def _extract_official_url(self, content: str) -> str | None:
    m = _OFFICIAL_URL_RE.search(content)
    if not m:
        return None
    url = m.group(1)
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("。、）")
```

**✅ 正確模式**：
```python
source_url = rss_link          # 聚合站 URL，永遠保留
official_url = self._extract_official_url(content)  # None 是合法值
```

**❌ 反模式**（已廢棄）：
```python
# 用官方 URL 覆蓋 source_url — 破壞資料溯源 audit trail
source_url = self._extract_official_url(content) or rss_link
```

Reference incidents:
- 2026-05-10 commit `ab771e2` — `ftip.py` 首次修正誤以「官方 URL 較有資訊量」讓 `source_url` 指向 `www.taiwanprism.com`，破壞 FTIP audit trail
- 2026-05-10 commit `7c34788` — 更正為正確模式：`source_url=ftip-japan.org/699`、`official_url=taiwanprism.com`，DB 事件 `023dcbec` 同步修正

## M/D~D 多日範圍 — end_date 提取與跨月防護

**Rule**: 日期字串含 `~`（如 `8/30~31`）表示多日活動，必須同時提取 `start_date` 和 `end_date`。

**實作範例**：
```python
_END_DAY_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})~(\d{1,2})(?![/])"  # M/D~D — (?![/]) 防止跨月假匹配
)

def _parse_date_range(self, text: str, year: int) -> tuple[date | None, date | None]:
    m = _END_DAY_RE.search(text)
    if m:
        month, start_day, end_day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(year, month, start_day), date(year, month, end_day)
    return None, None
```

**跨月防護**：`(?![/])` 確保 `~` 後面不接 `/`。若接 `/`（跨月，如 `3/10~5/31`），跳過 end_date 提取，避免把月份誤解為日數。

**正確/錯誤案例**：
- `8/30~31` → start=8/30, end=8/31 ✅
- `3/10~5/31` → `(?![/])` 命中，不提取 end_date ✅（正確放棄）
- 無 `~` → 僅提取 start_date，end_date=None ✅

Reference incident: 2026-05-10 — `ftip.py` 事件 `023dcbec`（台湾光譜 `8/30~31`）start_date 回退到 RSS pubDate，end_date 未設定（commit `ab771e2`）。

## location_address 硬編碼城市名 — 反模式

**Rule**: 以城市名（`"東京都"`、`"大阪"`、`"京都"`）作為全國性組織的 `location_address` fallback 是反模式，**必須禁止**。

**為何危險**：
1. GPT annotator 信任 scraper 提供的非 null `location_address`（`_ai_or_existing()` 只在值為 null 時才詢問 GPT）
2. 錯誤城市名寫入 DB 後，即使活動實際在其他縣市，`location_prefectures` 也會被錯誤推斷
3. 讓使用者在地圖/篩選功能中看到錯誤地點

**正確做法**：
```python
# ✅ 正確：無法確定地址時設 None
location_address = self._extract_venue_address(content) or None

# ❌ 錯誤：以組織所在城市作為全國活動的 fallback
location_address = "東京都"  # 全國性組織的活動可能在任何地方
```

**例外**（允許硬編碼）：scraper 專屬於**單一地點**的場館（固定影院、固定展覽館）時，可硬編碼該場館地址。

Reference incident: 2026-05-10 — `ftip.py` `location_address = "東京都"` 導致台湾光譜（京都活動 `〒603-8163 京都府...`）被錯誤標為東京（commit `ab771e2`）。

## note_creators レポート記事・結果発表 — report カテゴリ自動注入パターン

**Rule**: note_creators 來源的レポート記事には必ず三つの問題が発生する。検出時は以下の三点を一括修正し、FC 鎖定すること。

**三重問題（全件に発生）：**
1. **`start_date` = 記事公開日（≠ 活動日）**：記事が公開された日が自動的に `start_date` に入り、実際の開催日（1〜数ヶ月前）と異なる。本文中の「〇月〇日開催」「〇月〇日に参加」等から正しい日付を特定すること。
2. **`location` = 主催者の日本拠点**：主催者が日本に拠点を持つ場合、annotator がその住所を location として設定する。実際の活動場所（特に台灣で開催の場合）を確認し、`location_address` / `location_prefectures` を null に修正。
3. **接頭辭 + `report` category 欠如**：`annotator.py` の `_REPORT_TRIGGER_RE` が自動注入する（commit `1e00933` + `d0eb93e` 以降）。検知キーワード：レポート・レポ・報告・記録・アーカイブ・recap・行ってきた・観てきた・見てきた・鑑賞レポ・**結果発表**。注入時 ja 名称がすでに `【...】` で始まる場合は `【レポート】` を重ねない（`_inject_report_prefix` の二重括弧ガード）。既存 annotated events には Supabase SQL で `report` を追加後 `python annotator.py --backfill-report-prefix` を実行。

**FC 鎖定対象**（計 9 項）：`start_date`、`location_name`、`location_address`、`location_prefectures`、`name_ja`、`name_zh`、`name_en`、`categories`

**自動化範囲（annotator.py commit `1e00933` 以降）**：`report` category 注入 + 三語接頭辭注入は自動処理。`start_date` / `location` の修正は **human review 必須**。

Reference incident: 2026-05-10 — event `a7a05be6`（台湾薬膳文化体験レポート）`start_date=2026-05-08`（記事日）→ 修正後 `2026-04-21`（活動日）；`location_name=台湾華語文学習センター大阪弁天町`（主催者拠点）→ 修正後 `台北医学大学`（活動場所、台灣）。

## RSS/Podcast scraper-specific
- **Normalize `&amp;` in RSS link text before regex**: RSS `<link>` text nodes may contain HTML-entity-encoded `&amp;` even after XML parsing (double-encoded by the origin server). `item.find("link").text` can return `"...?uid=4&amp;pid=103701"`. Any regex on the raw text will miss `&pid=`. Always normalize: `link = link_raw.replace("&amp;", "&")` before extraction. Apply to both `source_url` construction and any `_extract_pid()`-style function. (Incident: rti_jp 0 events, 2026-05-14.)
- **XML Element truth value — always use `is not None`**: `if element:` on an `xml.etree.ElementTree` Element is always `True` (DeprecationWarning since Python 3.8). Write `element is not None and element.text` instead.
- **`STALE_DAYS` guard for podcast/RSS scrapers**: For scrapers that loop over a curated list of program IDs, check the latest episode's `pubDate` before iterating all items. If it exceeds `STALE_DAYS` (e.g. 90), the program is discontinued — skip to avoid a full-page fetch that returns 0 events:
  ```python
  STALE_DAYS = 90
  latest_pub = _parse_pubdate(items[0].find("pubDate").text)
  if latest_pub and (now - latest_pub).days > STALE_DAYS:
      logger.info("rti_jp: id=%s latest episode %dd old — discontinued", pid, age)
      continue
  ```
- **`LOOKBACK_DAYS` must match broadcast frequency**: Weekly programs → 14d is sufficient. Monthly programs → 60d minimum. If a program's cadence is unknown, default to 60d.

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

**note.com creator 追加手順（2 ステップ必須）**：
1. `CREATOR_META` に `{"slug": "<creator_slug>", "category": "<category>", "location": "<prefecture>"}` を追加
2. DB `research_sources` の対応行を `status=implemented` に更新（`scraper_source_name = 'note_creators'` も確認）
事前確認：`python main.py --dry-run --source note_creators 2>&1 | grep "events found"` で件数増加を確認してから commit。

---

## enrich_location.py — GPT Output Guard

`enrich_location.py` 使用 GPT 補充缺少的地址。接收 GPT 回傳後，寫入 DB **前**必須套用以下 guard：

1. **Identical address guard（Rule 6）**：`if addr.strip() == venue_name.strip(): skip + log warning`。`address == venue_name` 是提取失敗的確定標誌（GPT 只是複製了場地名）。
2. **Sub-venue address rule（Rule 7）**：子場地（如 `○○ビル2階`、`○○カフェ（寺内）`）需用**親設施的地址**，不得用子場地名作為 address。
3. **SELECT `location_name`**：query 必須 SELECT `location_name`，才能執行 identical address guard。
4. **雙重防護原則**：SYSTEM_PROMPT 規則（讓 GPT 返回 null）+ 程式碼 guard（兜底攔截）都必須存在；不能只靠 GPT 自律。

```python
# enrich_location.py — 寫入前 guard 範例
if location_address and location_address.strip() == (location_name or "").strip():
    logger.warning("SKIP: address == venue_name for event %s (%s)", eid, location_address)
    continue
```

Reference incident: 2026-05-05 — GPT extracted `仙六屋カフェ` from `会場：仙六屋カフェ` as address → identical guard added (commit `628e3e7`).

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

## Shopify サイト共通注意事項

- **`<a href>` は絶対 URL**: Shopify は `href` にフルドメイン付きの絶対 URL を出力する（例: `https://placebymethod.com/pages/slug`）。相対パス regex（`r"^/pages/"`）では 0 件になる。必ずドメインを含む regex を使うこと:
  ```python
  # ❌ 相対パス前提 — Shopify では 0 件
  soup.find_all("a", href=re.compile(r"^/pages/"))

  # ✅ フル URL にマッチ
  soup.find_all("a", href=re.compile(r"example\.com/pages/"))
  ```
- **一覧ページのアンカー `parent.get_text()` にタイトル/日付が含まれないことがある**: Shopify の展覧会一覧は各リンク要素の親に情報が入っていない構造が多い。全 slug を取得 → 個別ページを visit → 情報抽出するアプローチを採ること。
- **JSON API パターン（別方式）**: `/collections/event/products.json?limit=20&page={n}` で全展示品を列挙し空ページまでページネーション（`transit_store.py` 参照）。

(Incident: placebymethod.com, 2026-05-11 — `^/pages/` regex で 0 件 → `placebymethod\.com/pages/` に修正)

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

## annotator.py ↔ types.ts 同步守則（Three-Location Sync Rule + Startup Guard）

每次在 `web/lib/types.ts` 新增 `Category` 型別時，**必須同時更新三個地方**：

1. `scraper/annotator.py` → `VALID_CATEGORIES` 列表
2. `scraper/annotator.py` → SYSTEM_PROMPT 第 2 條 categories 列表（單行逗號分隔）
3. `scraper/annotator.py` → SYSTEM_PROMPT 分類定義清單（每個新分類需加定義行）

**違反後果**：GPT 無法選用新分類，被迫選最近似的舊分類（例如 `tv_program` 不存在時選 `movie`）。更嚴重的是，re-annotation 時 `_validate_categories()` 會靜默剝離不在 `VALID_CATEGORIES` 中的分類，默認回退為 `["senses"]`——造成**靜默資料遺失**。

### 自動防護機制（2026-05-05 新增）

1. **`_check_category_sync()` 啟動守衛**：annotator.py 啟動時自動讀取 `web/lib/types.ts`，比對 VALID_CATEGORIES。若有遺漏，`SystemExit(1)` 終止執行。CI/standalone 環境（types.ts 不存在）靜默跳過。
2. **`human_category_map` 驗證**：載入 `category_corrections` 表後，每筆記錄的分類都會對 VALID_CATEGORIES 驗證。無效分類被剝離並記錄 `logger.warning`。全部無效時回退為 `["senses"]`。

### 第二資料路徑警告
`category_corrections` 是 annotator 之外的第二條分類資料路徑。此表由 Admin UI 手動修正寫入，**不經過 VALID_CATEGORIES 驗證**（已在程式碼層修復）。新增分類時除了同步上述三處，也須確認既有 `category_corrections` 記錄不含已廢棄的分類值。

**驗證命令**：
```bash
cd scraper && python3 -c "
from annotator import VALID_CATEGORIES
import re
ts = open('../web/lib/types.ts').read()
ts_cats = re.findall(r'^\s*\| \"(\w+)\"', ts, re.MULTILINE)
missing = [c for c in ts_cats if c not in VALID_CATEGORIES]
print('Missing from VALID_CATEGORIES:', missing or 'ALL CLEAR')
"
```

**已知遺漏（2026-05-04 修正）**：tv_program, drama, documentary, tea_alcohol, exhibition, folklore, literature, parenting, scholarship, taiwan_mandarin, healthcare — 這 10 個分類在 types.ts 存在多月但 annotator.py 未同步，導致 gguide_tv 電視節目被標為 movie。

**Ghost category 事件（2026-05-05 修正）**：`category_corrections` 表中 10 筆記錄含無效分類 `culture`，36 筆事件面臨 re-annotation 時分類被靜默剝離的風險。修復後新增啟動守衛與 category_corrections 驗證。

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
- **keyword= URL パラメータはサーバー側でフィルタされないサイトがある**（例: bookandbeer）。dry-run で台湾キーワードが実際にヒットするか確認。ヒット率 0% の場合はクライアント側フィルタの実装が必要。
- **書店・著者イベントの false positive**：著者の所属欄に「台湾大学」「淡江大学」等が含まれる場合、台湾キーワードが著者略歴から来ている可能性がある。`_AUTHOR_BIO_RE` パターン（大学名）を除去してから再判定する 3 段階フィルタが有効：①タイトルに台湾キーワード → 即通過、②説明冒頭 500 字に 2 件以上 → 著者略歴パターン除去後に再判定、③除去後にキーワードなし → 除外。

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
- **⚠ 申込表單 URL 禁止填入 `location_url`**：Google Forms（`forms.gle/...`）、Peatix、Connpass 等**申込/登録表單 URL** 絕對不能填入 `location_url`。`location_url` 語義是「會場的官方 URL」（大学キャンパスページ、施設公式サイト等）。申込表單屬於 `source_url` 或 `official_url` 的責任範圍。DB 手動修正時若發現 `location_url` 含申込表單 → 設為 `null`。

Reference incident: `0d97e51c`（2025年台湾史研究会3月例会）`location_url='https://forms.gle/BwseMtpymDKQY4W47'`（申込表單）→ `null` 手動修正（2026-05-07）。

## event_form — lecture vs conference 區分規則

`event_form` 陣列的學術事件類型選擇：

| 情境 | 正確值 |
|---|---|
| 單一登壇者による講演・発表 | `['lecture']` |
| 複数の登壇者（2 件以上の報告）がある学術例会・研究会 | `['conference']` |
| シンポジウム・学会大会 | `['conference']` |

**判斷基準**：
- 「第1報告：〇〇」「第2報告：〇〇」のように**複数の報告**がある → `conference`
- 台湾史研究会・台湾研究フォーラム等の**月例会**は通常 `conference`（複数報告が標準形式）
- 単一演講でゲスト1名のみ → `lecture`

Reference incident: `0d97e51c` `event_form=['lecture']` → `['conference']`（2報告あり、2026-05-07 修正）。

## performers[] 批次回填驗證規則

批次回填 `performers[]` 時的必須驗證步驟：

**跨年度混入リスク**：source_name + 月份 で候補を絞ると、異なる年の同月イベントが混在し、performers が誤ったイベントに書き込まれる。

```python
# ❌ 危険：同月の別年イベントを混入させるパターン
candidates = sb.table('events').select('id,performers,raw_description').eq('source_name', 'taiwanshi').execute().data
# 2025-03 の回 と 2026-03 の回 が両方マッチしてしまう

# ✅ 安全：start_date の年月まで絞り込む
candidates = (
    sb.table('events').select('id,performers,raw_description')
    .eq('source_name', 'taiwanshi')
    .gte('start_date', '2025-03-01')
    .lt('start_date', '2025-04-01')
    .execute().data
)
```

**回填前の必須確認（人工）**：
1. 各イベントの `raw_description` を確認し、書き込もうとする performers 名が実際に記載されているか照合する。
2. 氏名が一致しない場合は当該イベントをスキップし、source_url を再確認する。
3. 回填後は `field_corrections` にロックし、re-annotation で上書きされないよう保護する。

Reference incident: `0d97e51c`（2025年3月例会）に `['陳志剛', '福田真郷']`（2026年3月例会の報告者）が誤って書き込まれた（2026-05-07 修正）。


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

## Movie Title Lookup Pattern

`scraper/movie_title_lookup.py` provides `lookup_movie_titles(name_ja)` → `tuple[str | None, str | None, str | None]`.

**Return value (3-tuple):** `(name_zh, name_en, official_url)` — all three may be `None` if not found.

```python
# ✅ CORRECT — always unpack as 3-tuple
name_zh, name_en, official_url = lookup_movie_titles(name_ja)
# or if official_url not needed:
name_zh, name_en, _ = lookup_movie_titles(name_ja)

# ❌ WRONG — causes ValueError: too many values to unpack
name_zh, name_en = lookup_movie_titles(name_ja)
```

**When to call:**
- Every cinema scraper that sets `category=["movie"]` must call `lookup_movie_titles(name_ja)` before constructing `Event()`.
- If `lookup_movie_titles` returns a non-None `official_url`, use it as `Event(official_url=official_url)`.

**Exemptions (skip `lookup_movie_titles` for):**
- Events whose `source_id` ends in `_sub\d+` (sub-events): they inherit translations from parent
- Events with `name_ja_locked=True` in DB (already manually verified)

**`official_url` from lookup:** When eiga.com finds the movie, the third tuple value is the eiga.com movie page URL. This is a valid `official_url` for the event — use it instead of constructing a Google search fallback.

**For Taiwan-produced films not found on eiga.com:** Check GHFF (`goldenhorse.org.tw/film/about/archive/`) — see `§ 台湾映画の権威ソース優先順位`.

---

## Cinema scraper Vision OCR pattern

Use when showtimes / business_hours are only available in a **schedule image** (JPEG/PNG), not in HTML.

**Pattern: 2-pass scrape + single Vision OCR call**

```python
# 1st pass — collect candidates (no Event() yet)
candidates: list[dict] = []
for movie in listing_movies:
    if is_taiwan_relevant(movie):
        candidates.append({"title": movie.title, ...})

# OCR step — single call for all candidates
schedule_map: dict[str, str] = {}
if candidates:
    img_url = _fetch_schedule_image_url()  # dynamic URL from schedule page
    if img_url:
        schedule_map = _ocr_schedule_showtimes(img_url, [c["title"] for c in candidates])

# 2nd pass — generate Event() with showtimes
for c in candidates:
    bh = _match_schedule(schedule_map, c["title"])  # exact → substring fallback
    event = Event(..., business_hours=bh)
```

**Graceful fallback rule:** `_ocr_schedule_showtimes()` must always return `{}` (empty dict) when:
- `OPENAI_API_KEY` is not set
- Any exception occurs (`except Exception: return {}`)

Never let Vision errors break the scrape. Events without OCR showtimes get `business_hours=None`.

**Dynamic URL fetch:** Schedule image URLs change weekly. Always fetch the schedule page HTML and extract the current `<a href="/img/i*.jpg">` link — never hardcode the JPEG URL.

**Prompt design for schedule OCR:**
- Provide the target title list explicitly; do NOT ask GPT to find all movies
- Request JSON output: `{"films": [{"title": "...", "showtimes": "HH:MM / HH:MM"}]}`
- Use `response_format={"type": "json_object"}` to prevent markdown wrapping
- Use `"detail": "high"` for image_url input to improve OCR accuracy
- Cost: `gpt-4o` Vision ≈ \$0.005/run for a weekly schedule image

Reference: `cinemaclair.py` commit `33dc715` (2026-05-15).

---

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
- **TCC location_name 幻覚パターン（`東京・京都`）**: annotator が東京のみの TCC 展覧会に `東京・京都` を設定することがある。raw_description に京都への言及がないのに `location_name` に `京都` が含まれていれば幻覚。修正手順：① raw_description で会場を直接確認 → ② `location_name='台湾文化センター'` に修正 → ③ `field_corrections` にロック。Reference incident: 2026-05-15 `dbfac7c9`（剪花・綻放 切り絵展）。
- **海報 OCR で co_organizer を補完**: TCC のイベントは HTML テキストに `主催` のみ記載されるが、海報（`image_url`）には `共催`・`協力` が記載されていることが多い。`image_url` が取得済みなら GPT-4o Vision OCR で追加情報を抽出し、`co_organizers`・`sponsors` を補完 → `field_corrections` にロック。
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

## waseda_icl-specific

1. **WP REST API, NOT Cloudflare-blocked**: `waseda.jp/folaw/icl/` allows `/wp-json/wp/v2/posts?search=台湾`. Main `waseda.jp` domain is blocked — do not confuse them.
2. **Skip `_REPORT_RE` posts**: Posts containing `【開催報告】` or `が開催されました` are event summaries published AFTER the event — skip them or you get stale past-event dates.
3. **Two-stage filter is mandatory**: API `search=` has broad recall; `_TAIWAN_TITLE_RE` on title is the precision gate. Body-only Taiwan mentions (bibliography, references) must not pass.
4. **0 events is almost always correct**: ~1–2 genuine Taiwan events per year. Never inflate keywords to increase counts.
5. **No overlap with `waseda_taiwan`**: Different institutions, different WP sites, different post IDs. Merger will not deduplicate them.

## walkerplus-specific

Walker+ (walkerplus.com) — KADOKAWA 運営の全国イベントリストサイト。

- **対象カテゴリ**: `eg0117`（グルメ・フードフェス）、`eg0118`（物産展・観光フェア）、`eg0107`（美術展・博物展）。台湾関係イベントが多いのは `eg0117`/`eg0118`。
- **台湾キーワードフィルタはカード title のみ**: Walker+ には台湾キーワードで絞り込む検索 API が存在しない。分類ページ（`/event_list/{category}/{page}.html`）を全ページ取得し、カード title で台湾キーワードを照合する（URL クエリパラメータでの絞り込み不可）。
- **分页 URL パターン**: 第1ページは `/event_list/{category}/`（`.html` 不要）、第2ページ以降は `/event_list/{category}/{page}.html`。
- **`source_id`**: `walkerplus_{area+event_code}`（例: `walkerplus_ar0313e462812`）— URL path の area+event code 部分。stable across runs。
- **`m-articleset--3` は 3 インスタンスある**: `#0` と `#1` は `.m-detail__contents` 内（本文）。`#2` は `.l-main` 直下（「関連イベント」ウィジェット）。`raw_description` の `p` タグ抽出は必ず `.m-detail__contents` スコープに限定すること。スコープを外すと関連イベントウィジェットの説明文が混入する。
  ```python
  # ✅ 正しい
  content = soup.select_one(".m-detail__contents")
  paras = content.select("p") if content else []

  # ❌ NG — #2 インスタンスまで抜けてしまう
  paras = soup.select(".m-articleset--3 p")
  ```
- **場地リンクの順序**: `.m-detailheader__period[場所]` セクションのリンクは `[地域, 都道府県, 市区町村, 施設名]` の順序。**最後のリンク = `location_name`（施設名）、中間リンクを結合 = `location_address`**。`location_name` を `location_address` にコピーしてはいけない。
  ```python
  links = venue_section.select("a")
  if links:
      location_name = links[-1].get_text(strip=True)
      location_address = "".join(a.get_text(strip=True) for a in links[1:-1]) or None
  ```
- **Detail page selectors**:
  - タイトル: `h1.m-detailheader-heading__ttl`
  - 開催日: `p.m-detailheader__text`（日付範囲テキスト、`〜` 区切り）
  - 場所/時間: `.m-detailheader__period` 区画、`.m-detailheader__icon` のラベルテキスト（「場所」「開催時間」）で判別
- **Crawl-delay**: 1 秒（`time.sleep(1)`）。KADOKAWA 系サイトはレート制限が厳しい。
- **`scraper_source_name = 'walkerplus'`**: `research_sources` 行をこのキーで登録しないと `/admin/sources` で 0 件表示になる。

## stranger-specific

Stranger cinema（東京墨田区）は Eigaland プラットフォームの JSON API を使用。

- **Taiwan filter は `countries` 配列で判定**: `movieDetail.countries` に `"台湾"` または `"台灣"` が含まれるか確認。タイトルやあらすじのキーワード検索は使わない（`仙台湾` 誤検知を防ぐ）。
- **`synopsis` は base64 エンコード HTML**: `base64.b64decode(b64).decode("utf-8")` → HTMLParser でタグ除去してプレーンテキスト化する。
- **1 映画 = 1 Event**: 90 日ループで `movieId` ごとに `min_date`/`max_date` を収集してから detail API を呼ぶ。1 日 1 Event を作ると 90 件になるため注意。
- **`openDate` は公開日（リリース日）であり上映日ではない**: 上映日は `listByDomainAndDate?date=YYYY-MM-DD` のクエリ日付から得る。
- **`official_url` は映画の公式サイト**: `detail.officialPageUrl` が映画の公式サイト URL（会場サイトではない）。

---

## Annotator — Performer / Director Field Rules

Rules for `performer`, `performer_zh`, `performer_en`, `director`, `director_zh`, `director_en` fields in `annotator.py`.

### `_MUKAE_RE` — 迎えパターン完全性

`_MUKAE_RE` lookahead は以下 3 種の敬語形式をすべて網羅すること：

| パターン | 例 |
|---|---|
| `をお迎え` | 〇〇氏をお迎えして |
| `を迎え` | 〇〇を迎えるトーク |
| `をゲストに迎え` | 一青窈氏をゲストに迎え |

新しい「迎え」形式が出現したら即座に追加する。Lookahead の片方だけを更新するミスを防ぐため、変更時は 3 パターン全件をテストすること。

Reference incident: `一青窈氏をゲストに迎え` が捕捉不能 → `をゲストに迎え` 追加（commit `6c2f1ab`）。

### `_PERFORMER_INTRO_RE` — separator は `*`（0 個以上）

```python
# ✅ 正しい：直連もマッチする
_PERFORMER_INTRO_RE = re.compile(
    r"(?P<role>絵本作家|映画監督|俳優|写真家|...)\s*(?P<name>[^\s、。]+)",
    # 角色詞と人名の間に分隔符なしの直連が常見 → \s* (0個以上)
)

# ❌ 間違い：直連が漏れる
_PERFORMER_INTRO_RE = re.compile(r"(?P<role>...)[\s・]+(?P<name>...)")
#                                                   ^^ + は1個以上 → 直連 NG
```

日本語の慣例として「絵本作家林廉恩氏」のように角色詞と人名を空白なしで直連するケースが頻出する。separator regex は必ず `*`（0個以上）を使用する。

Reference incident: `絵本作家林廉恩氏` が無マッチ → separator `+` → `*` に変更（commit `fe8b273`）。

### AI 翻訳マーカー — 言語別サフィックス規則

`performer_*` / `director_*` 欄位に AI 翻訳サフィックスを追加する際は、**フィールドの言語に合わせる**こと：

| フィールド | 正しいサフィックス |
|---|---|
| `performer_zh` / `director_zh` | `（AI翻譯）`（繁体中文） |
| `performer_en` / `director_en` | `(AI Translation)`（英語） |
| `performer` / `name_ja` | `（AI翻訳）`（日本語） |

言語不一致（例：`performer_en` に `（AI翻譯）`）はデータサイレント汚染を招く。フィールド名の末尾（`_zh` / `_en`）から言語を確認してから suffix を選択すること。

Reference incident: `bf783b90` `performer_en = 'Huang Yi-wen（AI翻譯）'`（中文サフィックス）→ `'Huang Yi-wen (AI Translation)'` に修正（commit `f07c170`）。

### performer_zh / performer_en 手動修正の 2 ステップ

手動でフィールドを修正した場合、必ず `_lock_fields_via_corrections()` を使うか、`field_corrections` テーブルも upsert してロックすること。未ロックだと re-annotation で修正値が上書きされる。

**⚠ `_zh` フィールドの SC→TC ガード**：`_lock_fields_via_corrections()` は `_zh` で終わるフィールドに自動的に `_to_trad()` を適用してから FC に書き込む（2026-05-11 commit `f7790a2` で追加）。直接 `field_corrections` テーブルに upsert する場合、`_zh` フィールドの値は手動で SC→TC 変換済みであることを確認すること。SC 値が FC に入ると、annotator P1 保護により永久に修正不能になる。

```python
# ✅ 2 ステップセットで実行
sb.table("events").update({"performer_en": "Correct Name (AI Translation)"}).eq("id", eid).execute()
sb.table("field_corrections").upsert({
    "event_id": eid,
    "field_name": "performer_en",
    "original_value": None,
    "corrected_value": "Correct Name (AI Translation)",
}, on_conflict="event_id,field_name").execute()
```

### performers[] 多語言欄位の UI helper

**フロントエンドは `getEventPerformer(event, locale)` / `getEventDirector(event, locale)` を使うこと**。`event.performer` を直接参照してはいけない。

Locale 優先序：
- `zh` → `performer_zh` → fallback → `performer`
- `en` → `performer_en` → fallback → `performer`
- `ja` → `performer` （Japanese field = base field）

Reference: `web/lib/types.ts` の `getEventPerformer` / `getEventDirector` helper（commit `3822fb8`）。

### director（導演）≠ performer（表演者）嚴格分欄規則

**導演和表演者必須分別填入不同欄位。兩者嚴禁混填。**

| 欄位 | 用途 |
|---|---|
| `director` / `director_zh` / `director_en` | 電影導演、舞台演出導演 |
| `performer` / `performer_zh` / `performer_en` | 演員、主演、表演者、講者 |
| `performers TEXT[]` | 所有具名演員/發表者的陣列 |

**商業院線映畫的額外規則：**
- `organizer` 必須為 `null`：院線（シネマート、ユーロスペース 等）是**映映場地**，不是主辦方。
- `director`：填導演（陳玉勳、侯孝賢 等）。
- `performers[]`：填主演演員陣列。
- `performer`（單一日文名）：主要主演；`performer_zh` / `performer_en`：多語言名稱。

```python
# ✅ 正確：商業院線映畫
Event(
    organizer=None,                          # 院線不是主辦方
    director="チェン・ユーシュン",            # 導演
    director_zh="陳玉勳",
    director_en="Chen Yu-hsun",
    performer=None,                           # 若填主演則用 performers[]
    performers=["ケイトリン・ファン", "ウィル・オー"],
)

# ❌ 錯誤：導演誤填至 performer
Event(
    organizer="台北駐日経済文化代表処 台湾文化センター",  # 商業映畫不應有 organizer
    performer="チェン・ユーシュン",           # 導演誤填為 performer
    director=None,                            # director 漏填
)
```

**works 表同步**：events.director 修正後，`works.director` 與 `works.cast_summary` 必須同步更新，否則 works 頁面顯示錯誤資訊。

Reference incident: `dec5031b`（大濛/霧のごとく）`performer='チェン・ユーシュン'`（導演誤填），`organizer='台北駐日経済文化代表処 台湾文化センター'`（商業映畫誤填 organizer）→ DB 手動修正（2026-05-06）。

### `_KNOWN_PERSON_MAP` — 藝名/筆名 GPT 翻譯覆寫

GPT は藝名・筆名（片假名 ↔ 非語音漢字対応）を正しく翻訳できない。`annotator.py` のモジュールレベル `_KNOWN_PERSON_MAP` に検証済みの名前を登録すること。

**GPT が失敗するケース（片假名 → 漢字が語音対応しない）：**
- `ギデンズ・コー` → ❌ `基登斯·高` → ✅ `九把刀` / `Giddens Ko`（筆名）
- `ロー・ウェイ` → ❌ `Lau Wai` → ✅ `羅維` / `Lo Wei`

**新規エントリ追加時の必須事項：**
1. **三言語同時検証**：`ja`（片假名）、`zh`（漢字名）、`en`（英語名）すべてを信頼できるソースで確認
2. **ソース優先順位**：eiga.com → 公式サイト → Wikipedia → 信頼できる第三者
3. **三つの統合ポイントを確認**：① annotation loop ② `performers[]` 配列 per-element ③ `backfill_performer_i18n()` Layer 0

**翻訳ルール（厳格適用）：**
- ラテン文字名 → そのまま保持（翻訳しない）
- CJK 漢字名で検証ソースなし → 翻訳しない（zh: 漢字コピー、en: NULL）
- 片假名音訳 → 検証ソースがある場合のみ翻訳（`_KNOWN_PERSON_MAP` or eiga.com lookup）

Reference incident: 2026-05-09 — 14 名の検証済み名前を `_KNOWN_PERSON_MAP` に登録、11 件の DB イベントを修正。

### `performers_zh[]` 機械音訳禁止ガード

**`performers_zh[]` 配列の各要素は、片假名の機械的音訳であってはならない。**

annotator が `performers[]`（片假名）を `performers_zh[]` に変換する際、音訳 mapping のない人名は `エスター・リウ → 艾絲特·劉` のような機械音訳になる。これは本名（`劉品言`）と一致しない別名であり、データ汚染となる。

**判定方法**：
- `performers_zh[i]` に `·`（中黒）が含まれ、かつ前半が 2〜3 文字で「アルファベット名の音訳漢字」（愛、艾、艾絲特 等）なら機械音訳の疑いが高い
- `performers_zh[i] == performer_zh`（単一演者）と一致しない場合も要確認

**修正パターン**：
1. GHFF / eiga.com / Wikipedia で本名を確認
2. `performers_zh[i]` を本名に書き換え
3. `field_corrections` は `performers_zh` 配列全体をまとめてロック（フィールド名: `performers_zh`）

```python
# ✅ 正しい: GHFF で確認した本名
performers_zh = ["劉品言", "林柏宏"]  # 艾絲特·劉 は誤り

# ❌ 機械音訳
performers_zh = ["艾絲特·劉", "林柏宏"]  # エスター・リウ のカタカナ音訳
```

Reference incident: 2026-05-15 — `6a0dbfb3` cinemaclair 莎莉、`performers_zh[0]='艾絲特·劉'`（機械音訳）→ `'劉品言'`（本名）に修正。

### 台湾映画の権威ソース優先順位

eiga.com に登録のない台湾映画は**金馬獎（GHFF）公式サイト**が最も信頼度の高い情報源。

**優先順位**:
1. **GHFF** (`goldenhorse.org.tw/film/about/archive/`) — 正式中文片名・英文片名・監督・出演者。金馬獎入選作品は全掲載。
2. **eiga.com** (`eiga.com/movie/search/?name=...`) — 日本公開済み映画の日本語公式情報。
3. **TAICCA 公式** / **台北電影節** / **映画公式サイト** — 金馬獎外の作品に使用。
4. **Wikipedia** — 上記が見つからない場合の補完。
5. **GPT 生成** — 最終手段。必ず上記で検証してから FC lock する。

**注意事項**:
- **漢字 1 文字違い**（`練` vs `連`、`惠` vs `慧` 等）は視覚的に気づきにくい。人名・片名は必ずコピー&ペーストで GHFF 原文と照合する。
- **ローマ字綴り**も GHFF の表記が正式（`Chien-hung` vs `Chien-hong` 等）。GPT は類似綴りを混同しやすい。
- **description_zh/en 内の片名参照も同時修正**：`name_zh` だけ直すと説明文内に旧片名が残る。`str.replace(old, new)` で一括置換してから update する。
- **works テーブルも必ず同時修正**：`works.original_title`、`works.title_zh`、`works.title_en`、`works.director` は `events` と別テーブル。片名修正時は必ず両方を update する。

Reference incident: 2026-05-15 — `6a0dbfb3` cinemaclair 莎莉。GHFF で `薩莉→莎莉`、`Sally→Salli`、`連建宏→練建宏`、`Chien-hong→Chien-hung` を確認して修正。

---

## Sub-event 啟用 — 標題同步規則

學術研討會的子事件（sub-event）以 slot 識別符（「第1報告」「第2報告」等）作為初始標題時，**啟用 `is_active=True` 前必須同步更新標題**。

**檢查流程：**
1. 查看 `raw_description` — 正確的發表題目通常在 `raw_description` 中以「発表タイトル：」或「（仮題）」形式出現。
2. 從 `raw_description` 手動提取題目，更新 `name_ja`。
3. 同步更新 `performer`（發表者姓名）。
4. 最後設 `is_active=True`。

```python
# ✅ 正確流程（DB 直接修正）
sb.table("events").update({
    "is_active": True,
    "name_ja": "台湾の「雲南菜」から見る「孤軍」と東南アジア（仮題）",
    "performer": "福田真郷",
}).eq("id", eid).execute()

# ❌ 錯誤：只啟用，不更新標題
sb.table("events").update({"is_active": True}).eq("id", eid).execute()
# → 「第2報告」這種 slot 識別符顯示在前台
```

Reference incident: `97f11903`（第2報告）`is_active=False` + `name_ja='第2報告'`（slot 識別符）→ raw_description 提取正確題目後手動修正（2026-05-06）。

---

## DB 手動修正 — business_hours 亂碼字元偵測

**kokuchpro（こくちーず）等 scraper 的時間字串可能含非標準 Unicode 分隔符。**

已知問題字元：

| 字元 | Unicode | 說明 |
|---|---|---|
| `〖` | U+3016 | LEFT BLACK LENTICULAR BRACKET（誤轉為分隔符） |
| `〗` | U+3017 | RIGHT BLACK LENTICULAR BRACKET |

**偵測與修正**：
```python
# 修正 business_hours 中的非標準分隔符
business_hours = (
    business_hours
    .replace("\u3016", "～")   # 〖 → 全形波浪號
    .replace("\u3017", "")     # 〗 → 刪除
)
```

**DB 修正驗證**：修正後確認值為 `'HH:MM～HH:MM'`（全形波浪號 U+FF5E），而非其他替代字元。

Reference incident: `622f51c1`（中村地平上映会）`business_hours='13:30〖16:30'` → `'13:30～16:30'` 手動修正（2026-05-06）。

---

## Annotator — Headline Rewrite Sources & Blog Source Guard

### `_HEADLINE_REWRITE_SOURCES` — 必須含む来源

現在の `_HEADLINE_REWRITE_SOURCES` frozenset に含めるべきソース（ニュース/ブログ/プレスリリース系）：

```python
_HEADLINE_REWRITE_SOURCES = frozenset({
    "google_news_rss",
    "nhk_rss",
    "prtimes",
    "walkerplus",
    "note_creators",  # ← ブログ源も必須
})
```

**ブログ源は必ず含める**：`note_creators` など創作プラットフォームの記事は純記事（ニュース見出し）と同様の構造を持つ。含めないと organizer 欄が GPT 幻想で汚染される。

### note_creators — thin content guard

`note_creators` の `raw_description` は RSS 截断により「続きをみる」だけになることが多い。以下の判断基準を適用する：

| 内容 | 処理 |
|---|---|
| 活動告知（日時・場所あり） | 通常収録 |
| 純介紹文・感想記事・観影報告 | `is_active = False` で非表示 |
| `raw_description` が截断のみ | annotator に渡さず先に除外検討 |

「純介紹文/觀影報告は活動資料ではない」— annotator のフィルタリングに依存せず、scraper または admin DB 操作で `is_active=False` にすること。

Reference incident: 4 件の `note_creators` 事件が純観影記事として誤収録 → `is_active=False` + organizer クリア（commit `b589fbb`）。

---

## Annotator — Collection Attribution Guard

`〇〇美術館蔵` / `〇〇所蔵` は**作品の所蔵機関標記**であり、活動場地ではない。

**問題パターン**:
```
「高雄市立美術館蔵の作品を〇〇で展示」
```
↑ GPT は `高雄市立美術館` を `location_name` に誤って抽出することがある。

**対策**:
1. SYSTEM_PROMPT に COLLECTION ATTRIBUTION NOTE を追加済み（commit `47f8184`）：「`〇〇蔵` のみの出現は所蔵元の記載であり、活動場地ではない」。
2. 固定場地の scraper（cinema、venue-specific scraper 等）は `location_name` をコード側で静的設定する。GPT の判断に委ねない。

```python
# ✅ 固定場地は静的設定
Event(
    location_name="東京都写真美術館（恵比寿ガーデンシネマ）",
    location_address="東京都目黒区三田1-13-3",
    ...
)
```

Reference incident: yebizo event `e37db12e` で `location_name='高雄市立美術館'`（台湾の美術館）が設定された → `東京都写真美術館` に修正（commit `47f8184`）。

## Playwright CI 批次容錯規則

在審核任何使用 Playwright 的 CI 批次腳本（`auto_research.py`、`annotator.py` 等）的計畫前，必須確認：

1. **`page.goto()` 必須包裝 `TimeoutError` 捕獲**：
   ```python
   from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

   def _fetch_sample_html(url: str) -> str:
       try:
           page.goto(url, timeout=30_000)
           return page.content()
       except PlaywrightTimeoutError:
           logger.warning("Playwright timeout for %s, skipping", url)
           return ""
   ```

2. **單一 URL 選止整個批次 = 達成零**：空 `sample_html` / 空 `content` 必須被視為「該筆跳過，下一筆繼續」——不可讓它摧毀整個 job。
   ```python
   # auto_research.py run() 中的 pattern
   sample_html = _fetch_sample_html(row["url"])
   if not sample_html:
       _update_status(row["id"], "error", "fetch_timeout")
       continue  # 繼續下一列
   ```

3. **CI 批次腳本的 exit code 必須反映批次整體結果**：單筆來源標記 `error` 不就是失敗；全部跳過才是失敗。若選擇類似「至少 N 筆成功」的 exit condition，必須在計畫中明確定義。

Reference incident: 2026-05-07 — commit `8029b74`：`auto_research.py` `_fetch_sample_html()` 無 try/except，`note.com/swi0881` 在 CI 逾時 → 未捕獲 `PlaywrightTimeoutError` → 整個 job exit code 1，所有後續來源全部跳過。

## Vision OCR Enrichment Pipeline（enrich_poster.py）

`scraper/enrich_poster.py` — GPT-4o Vision でイベントポスター画像から情報を抽出する enrichment pipeline。

### 前提条件

- `events.image_url` が非 NULL（migration 057 適用済み）
- `note_creators.py` など `_fetch_article_content()` を実装した scraper が `og:image` を `Event.image_url` にセット

### 実行方法

```bash
cd scraper && source ../.venv/bin/activate

# 全件処理（デフォルト最大 50 件）
python enrich_poster.py

# dry-run（DB 更新なし）
python enrich_poster.py --dry-run

# 特定イベント
python enrich_poster.py --event-id <UUID>

# 件数制限
python enrich_poster.py --max 20
```

### 動作仕様

1. **対象選択**：`image_url IS NOT NULL AND annotation_status IN ('pending', 'annotated')` のイベントを最大 N 件取得
2. **Vision 抽出**：GPT-4o Vision で画像を解析 → JSON 出力（`start_date`, `venue`, `organizer`, `confidence` per field）
3. **適用条件**：`confidence ≥ 0.8` のフィールドのみ適用
4. **FC ロック**：適用したフィールドは全て `field_corrections` に upsert（re-annotation で上書きされない）
5. **Thin Content Guard**：`raw_description < 100 字` の場合は `organizer` を非適用（date/venue のみ）— thin content 時は GPT が外部知識から organizer を hallucinate するリスク防止

### 注意事項

- **CI integration**：`scraper.yml` の annotator ステップ直後に自動実行（`python enrich_poster.py` ステップ）
- **confidence threshold は固定 0.8**：閾値を下げると thin content での false positive が増加するため変更不可
- **confidence はフィールド単位**：全体 confidence が 0.8 でも個別フィールド（venue）が 0.7 なら venue は非適用
- **Organizer Non-Hallucination Guard 適用**：Vision 抽出の organizer 値が `raw_description` に存在しない場合は棄却（thin content guard が主要防線）

Reference incident: 2026-05-07 — `note_creators.py` `_fetch_article_content()` 実装により `image_url` 取得が可能になり、Vision OCR pipeline の初回適用先が生まれた（commit `a52f5b2`）。

## WP REST API — `content` フィールド空の Elementor サイト

Elementor / Gutenberg blocks テーマの WordPress サイトでは、`/wp-json/wp/v2/<post_type>?_fields=content` の `content.rendered` が `""` で返ることがある。JavaScript 側でブロックをレンダリングするため、静的 HTML レスポンスには本文が存在しない。

**検出方法**：
```python
r = requests.get(API_URL, params={"_fields": "id,title,date,link,content", "per_page": 1})
post = r.json()[0]
print(repr(post["content"]["rendered"]))  # "" → Elementor サイト
```

**対処**：`content` フィールドは使わず `link` フィールドの URL に対して `requests.get` → `BeautifulSoup` で HTML を直接スクレーピングする。

```python
# ❌ Elementor サイトでは空
content = post["content"]["rendered"]  # ""

# ✅ detail ページを直接 fetch
r = requests.get(post["link"], headers=HEADERS, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")
full_text = soup.get_text(" ", strip=True).replace("\x00", "")
```

**コスト最適化**：詳細ページ fetch は HTTP コストが高い。**API 段階でタイトルフィルタを先に適用し、対象投稿のみ fetch する**（次セクション参照）。

Reference incident: 2026-05-14 — SNET台湾 `snet_taiwan.py`（commit `64034ec`）、Elementor テーマで `content.rendered = ""`。

## 低頻度ソース — タイトルベース 2 段階フィルタ（詳細ページ fetch 前）

年 3〜5 件程度のイベントしか含まない WP REST API ソースで、全 50〜100 投稿のうちイベント告知が少数の場合、詳細ページ fetch 前にタイトルだけで 2 段階 INCLUDE/EXCLUDE フィルタを適用すると HTTP コストを大幅削減できる。

**パターン**：
```python
_INCLUDE_RE = re.compile(r"開催のお知らせ|申込|プランニング大賞|ツアー.*ご案内|...")
_EXCLUDE_RE = re.compile(r"アカデミー.*第\d+回|受賞.*決定|講師.*派遣|...")

for post in api_posts:
    title = BeautifulSoup(post["title"]["rendered"], "html.parser").get_text()
    if not _INCLUDE_RE.search(title):
        continue    # 対象外 — fetch しない
    if _EXCLUDE_RE.search(title):
        continue    # 明示除外 — fetch しない
    event = self._fetch_and_parse(post["link"])  # ここで初めて HTTP fetch
```

**EXCLUDE の用途**：YouTube 動画シリーズ・過去活動報告・B2B 業務連絡など、タイトルが明らかにイベントではないものを事前排除する。

**INCLUDE/EXCLUDE 条件の記録**：フィルタ条件を module docstring に記録し、将来のメンテナンスで意図を失わないようにする。

Reference incident: 2026-05-14 — `snet_taiwan.py` で 66 投稿 → 5 件（シンポジウム・ツアー募集・コンテスト）に絞り込み（commit `64034ec`）。

---

## teket.jp プラットフォーム — グループ別イベント列挙

teket.jp は日本の電子チケット販売プラットフォーム。URL 構造: `https://teket.jp/{group_id}/{event_id}`。

### グループ別イベント列挙

- **`/api/events?group_id={id}` は使用不可**: group_id パラメータが無視され、全プラットフォーム (34,000+件) を返す。
- **唯一の有効手段**: `https://teket.jp/sitemap.xml` に `/{group_id}/{event_id}` 形式で全イベント URL が列挙されている。

```python
# ⚠ timeout=30 必須 — teket.jp sitemap は大容量 (34k+ URL) で 15〜20s かかる
r = requests.get("https://teket.jp/sitemap.xml", headers=_HEADERS, timeout=30)
ids = re.findall(r'https://teket\.jp/1841/(\d+)', r.text)
candidate_ids = sorted(ids, key=int, reverse=True)[:30]  # 最新 30 件
```

### イベントページ — データ取得元

| フィールド | 取得元 | 注意 |
|-----------|--------|------|
| `raw_title` | JSON-LD `name` | — |
| `start_date`/`end_date` | JSON-LD `startDate`/`endDate` | `YYYY/MM/DD HH:MM +09:00` → **date 部分のみ** → UTC midnight |
| `location_name` | page title `\| venue` サフィックス | JSON-LD `location.name` は常に `その他のホール`（無効）|
| `location_address` | OG description `[venue_name address][日時]` ブラケット内 | — |
| `image_url` | JSON-LD `image` | 相対パスは `https://teket.jp` を prepend |
| `raw_description` | full page text (script/style 除去後) | JSON-LD `description` はフェスタ名のみ（使用不可）|

### 台湾フィルタは full page text で適用

JSON-LD `description` は短すぎる（例: `爆音映画祭2026 in 松本`）。full page text には `2021年｜台湾｜カラー`・`台湾映画社` などが含まれる。

```python
for tag in soup(['script', 'style']):
    tag.decompose()
full_text = soup.get_text(' ', strip=True)
if not any(kw in full_text for kw in ('台湾', '台灣')):
    return None  # 台湾無関係 → スキップ
```

Reference incident: 2026-05-15 — `matsumoto_cinema_select.py`（teket.jp group_id=1841 ＮＰＯ松本シネマセレクト）。
