# Scraper Expert Error History

<!-- Append new entries at the top -->

---
## 2026-04-29 — eurospace / tokyoartbeat: category="string" instead of category=["string"]

**Error:** `malformed array literal: "movie"` (PostgreSQL code 22P02) on upsert.
The `category` column is `text[]` in Supabase. Both `eurospace.py` and `tokyoartbeat.py`
passed a bare string (`category="movie"`, `category="art"`), causing the DB to reject it.

**Fix:** Changed to list literals: `category=["movie"]`, `category=["art"]`.

**Lesson:** `Event.category` is typed `list[str]` (see `base.py` line 30). Any scraper that
hard-codes a single category must use `["value"]` not `"value"`. Bare strings silently compile
but fail at DB write time with a cryptic PostgreSQL array literal error.

---
## 2026-04-29 — maruhiro: datetime.date vs datetime.datetime type error + 15 scrapers lost from SCRAPERS

**Part 1 — Type error in dedup_events:**
`_parse_dates` in `maruhiro.py` returned `datetime.date` objects. `dedup_events` in `base.py`
calls `.date()` on `start_date`, expecting a `datetime.datetime`. Error:
`AttributeError: 'datetime.date' object has no attribute 'date'`.
Fix: changed `_parse_dates` to return `datetime.datetime(y, m, d)` instead of `date(y, m, d)`.

**Lesson:** All scrapers must return `datetime.datetime` for `start_date`/`end_date`, not bare `date`.
`dedup_events` contract requires `.date()` to be callable on the value.

**Part 2 — 15 scrapers deleted from SCRAPERS by 7aecfef:**
SCRAPERS audit (run after implementing maruhiro) revealed 15 scrapers present in `sources/` but
absent from `SCRAPERS` in `main.py`. Root cause: commit `7aecfef` ("chore: tighten workflow guards
and restore admin filters") rewrote `main.py` and omitted the imports and registrations for:
EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper,
CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper,
ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper,
GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper.
All 15 were restored, total SCRAPERS count: 56.

**Lesson:** SCRAPERS audit must run after ANY commit touching `main.py`, not only when
adding new scrapers. Run `python3 -c "import re, glob; ..."` (see SKILL.md) before `git push`.

---
## 2026-04-29 — prtimes: 川越台湾フェア and all non-Tokyo events missed (3 bugs)

**Trigger:** User reported https://prtimes.jp/main/html/rd/p/000000015.000127081.html (丸広百貨店川越店「台湾フェア」) not captured.

**Root cause 1 — Geographic restriction in `_SEARCH_KEYWORDS`:**
All 5 keywords contained `東京` (e.g. `"台湾 イベント 東京"`). The prtimes search API
only returns articles matching the full keyword string, so articles from Saitama (川越),
Osaka, Nagoya, etc. were **never returned**. Violates the project rule: "Never restrict
geographic scope".
Fix: Removed `東京` from all keywords → `["台湾 イベント", "台湾フェア", "台湾フェス", "台湾 開催", "台湾 夜市", "台湾 祭"]`.

**Root cause 2 — `_EVENT_KW` missing `フェア`:**
`_EVENT_KW` regex did not include `フェア`. A title like「台湾フェア」would have no
_EVENT_KW match and be rejected. Fix: added `フェア` to `_EVENT_KW`.

**Root cause 3 — `_TAIWAN_BASED_TITLE_RE` false positive:**
Pattern `台湾.*?で` matched `台湾フェア」で` (a Japan-held Taiwan fair) as if the event
were held IN Taiwan, causing it to be skipped. The intended purpose was to exclude
events held inside Taiwan (not Japan). Fix: tightened the regex to require explicit
Taiwan-location context only:
- `台湾国内|現地|本島|の地.*?で`
- `in 台湾 / in Taiwan`
- `台湾出展|輸出|進出|販路|海外展示|海外販売`

**Result:** dry-run: 20 → 30 events; 川越台湾フェア now first in list.

**Lesson:**
- `_SEARCH_KEYWORDS` must NEVER contain city/region names — geographic scope is all-Japan.
- `_TAIWAN_BASED_TITLE_RE` patterns must be precise; `台湾.*?で` is too broad and matches Japan-based Taiwan fairs.
- When a PR article is missing, check: (1) search keyword geography, (2) `_EVENT_KW`, (3) `_TAIWAN_BASED_TITLE_RE`, (4) venue filter `_TAIWAN_VENUE_RE`.

---
## 2026-04-29 — movie_title_lookup + PrtimesScraper registration + FukuokaNow scope fix [multiple]

**Changes (commit 3286522):**

1. **`movie_title_lookup.py`** (NEW): `lookup_movie_titles(name_ja)` → `(name_zh, name_en)` via eiga.com search. In-memory cache `_cache`; returns `(None, None)` silently on any error. Used by 8 cinema scrapers + annotator `--enrich-movie-titles` flag.

2. **`prtimes.py` geographic filter removed**: `_SEARCH_KEYWORDS` previously included `東京` scope restriction. Removed — project scope is all of Japan. Added `フェア` to `_EVENT_KW`. `PrtimesScraper` was also NOT in `SCRAPERS` — now registered.

3. **`fukuoka_now.py` scope**: Correct from the start — no regional filter added.

**Lessons:**
- Cinema scrapers should call `lookup_movie_titles(title)` before constructing `Event()` and pass `name_zh`/`name_en`. Annotator GPT fallback still applies if `(None, None)`.
- PR TIMES keywords must NEVER include city names (e.g. `東京`) — project covers 全日本.
- Every new scraper file must be added to `SCRAPERS` in the same commit. Do not defer.

---
## 2026-04-29 — Fukuoka Now scraper implemented [fukuoka_now]

**New source**: `FukuokaNowScraper` — Fukuoka's major English-language event calendar.

**Key decisions:**
- Static HTML (WordPress) — used `requests` + BeautifulSoup, no Playwright needed
- Taiwan filter on card title + tags + short description before detail page fetch
- `_is_taiwan()` only; no false-positive guard needed (site uses "Taiwan" in actual Taiwan events only)
- Venue extracted via line-by-line keyword match (City Hall, Fureai, Tenjin, etc.) — no structured `場所:` label
- 0 events in dry-run is correct: 台湾祭 in 福岡 2026 ended Feb 23; next event not yet listed

**Lesson**: For seasonal event scrapers, 0 dry-run output is valid when the annual event is between seasons. Verify by unit-testing `_parse_detail()` on the archived event URL directly.

---
## 2026-04-29 — research_sources status not updated after scraper implementation [livepocket]

**Error:** After implementing and committing `LivepocketScraper`, the `research_sources` row (id=106) was left with `status = 'researched'` instead of `implemented`. The admin Sources table showed「已深度研究」badge and a「建立爬蟲 Issue」button — implying the scraper had NOT been built.

Additionally, `scraper_source_name` was left as `null`, so the "scraper_source_name → source mapping" used by `AdminSourcesTable` to link event counts to sources could not resolve the source.

**Fix:** Manual DB update:
```python
sb.table('research_sources').update({
    'status': 'implemented',
    'scraper_source_name': 'livepocket'
}).eq('id', 106).execute()
```

**Lesson:** The new source checklist must include **both** DB fields as a single atomic step:
- `status = 'implemented'`
- `scraper_source_name = '<source_name>'` (matches `SOURCE_NAME` constant in the scraper)

Neither field alone is sufficient. Omitting `scraper_source_name` breaks event-count display in AdminSourcesTable. This step must be done in the same session as the scraper commit — not deferred.

---
## 2026-04-29 — LivePocket scraper: wrong dl selector + class name conflict [livepocket]

**Error 1: dl selector class mismatch**
Assumed `dl` class was `event-detail-info` based on the docstring in the research profile. Actual class is `event-detail-info__list`. Additionally, `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` inside the `dl` — they are NOT direct children. Using `dt.find_next_sibling("dd")` returned nothing. All 14 events had `start_date = null` on first dry-run.

**Fix:** Changed selector to `soup.select_one("dl.event-detail-info__list")` and rewrote `_get_dd_text()` to iterate `dl.select("div.event-detail-info__block")` → `block.select_one("dt")` / `block.select_one("dd")`.

**Error 2: CamelCase class name `_scraper_key` conflict**
Named the class `LivePocketScraper`. The `_scraper_key()` function in `main.py` splits on CamelCase boundaries, producing `live_pocket` — which does NOT match `source_name = "livepocket"`. Running `--source livepocket` reported "Unknown source".

**Fix:** Renamed class to `LivepocketScraper` (lowercase `p`) → `_scraper_key = livepocket`.

**Result:** 14 Taiwan events found after both fixes. `start_date` populated for all.

**Lessons:**
- Always verify `dl` class name from live HTML before writing selectors — research profiles can have stale assumptions.
- For platform names with no natural CamelCase split (e.g. "livepocket"), always use `Livepocket` (not `LivePocket`) to ensure `_scraper_key` matches `source_name`.
- Duplicate `dl` blocks exist (desktop + mobile) — always use `select_one()`.

---
## 2026-04-29: Peatix organizer Layer 3 + discovery_accounts.py daily rotation

**變更：**
- peatix.py: `_load_db_organizers()`, `_scrape_group_events()`, `scrape()` DB loop
- discovery_accounts.py: 4-slot rotation, `_run_note_task()`, `_run_peatix_task()`, `_verify_peatix_group()`
- discovery-accounts.yml: Mon-Thu daily cron, `DISCOVERY_SLOT` env var

**規則新增：**
- Layer 3 擴充到新平台時，`agent_category` 必須是平台獨立的值（`peatix_organizer` 而非通用名稱）
- `source_profile` 結構須包含 `platform` 欄位以區分來源
- discovery_accounts.py 的 `--dry-run --slot N` 組合是必要的驗證入口

**Skills folder convention（同日修正）：**
- `jats/` 和 `waseda_taiwan/` 移入 `.github/skills/sources/` 子目錄（原放在頂層，屬錯誤）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下

---
## 2026-04-29 — Peatix 三層爬取架構固化（daily review）
**新增/修改：**
- `## Peatix-specific` 新增 Three-layer organizer architecture 表格（Layer 1 keyword / Layer 2 hardcode / Layer 3 DB-driven）
- 記錄 `_load_db_organizers()` 的 `agent_category='peatix_organizer'` 查詢條件
- 記錄「Never remove Layer 2」規則（DB status 意外變更時的 backup）
**來源：** daily-skills-review（Step 4 建議）

## 2026-04-29 — iwafu docstring 誤記（東京限定と表記されていた全国スクレイパー）[iwafu]
**Error**: `iwafu.py` モジュール docstring に「Filter to events where prefecture == 東京」と記載されていたが、実コードは `cards = all_cards`（フィルターなし）で全国カバー済み。
DB candidate id=97（iwafu EN `/en/events/`）も「福岡拡張が必要」と判断されていたが、JP スクレイパーで既に全国カバーされているため重複。
**Fix**: docstring を「No prefecture filter — all regions included」に修正。DB id=97 を not-viable に更新（理由付き）。
**Lesson**: 「機能を追加する前にコードを読む」。scraper の実際の挙動（cards フィルター有無）を確認してから「拡張が必要か」を判断する。docstring とコードが乖離するリスクを防ぐため、prefecture フィルターの有無は SKILL.md に明記しておく。

---

## 2026-04-29 — SCRAPERS リスト未登録スクレイパー 8 件発見（pipeline 監査）[main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper の 8 件が `sources/*.py` として存在するが `SCRAPERS` リストに未登録のまま本番稼働していた。DB ステータスは `implemented` だったが CI では一度も実行されていなかった。
**Discovery**: `research_sources` DB の `implemented` 件数 vs `sources/` ファイル一覧と `SCRAPERS` リストの三者クロスチェックで発見。
**Fix**: `scraper/main.py` に 8 件の import と `SCRAPERS` 追記。全件 dry-run で動作確認後にコミット。
**Lesson**: DB `implemented`、ファイル存在、`SCRAPERS` 登録の三者は独立して管理される。新規スクレイパー作成時は必ず同一コミットで `SCRAPERS` に追加する。定期監査コマンド:
```bash
python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
"
```

---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:この映画は香港の食堂を舞台に、社会の変化に直面する人々の姿を描いており、台湾、香港、フランスの共同制作です。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


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

---
## 2026-04-29 — Peatix 三層爬取架構固化（daily review）
**新增/修改：**
- `## Peatix-specific` 新增 Three-layer organizer architecture 表格（Layer 1 keyword / Layer 2 hardcode / Layer 3 DB-driven）
- 記錄 `_load_db_organizers()` 的 `agent_category='peatix_organizer'` 查詢條件
- 記錄「Never remove Layer 2」規則（DB status 意外變更時的 backup）
**來源：** daily-skills-review（Step 4 建議）

## 2026-04-29 — iwafu docstring 誤記（東京限定と表記されていた全国スクレイパー）[iwafu]
**Error**: `iwafu.py` モジュール docstring に「Filter to events where prefecture == 東京」と記載されていたが、実コードは `cards = all_cards`（フィルターなし）で全国カバー済み。
DB candidate id=97（iwafu EN `/en/events/`）も「福岡拡張が必要」と判断されていたが、JP スクレイパーで既に全国カバーされているため重複。
**Fix**: docstring を「No prefecture filter — all regions included」に修正。DB id=97 を not-viable に更新（理由付き）。
**Lesson**: 「機能を追加する前にコードを読む」。scraper の実際の挙動（cards フィルター有無）を確認してから「拡張が必要か」を判断する。docstring とコードが乖離するリスクを防ぐため、prefecture フィルターの有無は SKILL.md に明記しておく。

---

## 2026-04-29 — SCRAPERS リスト未登録スクレイパー 8 件発見（pipeline 監査）[main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper の 8 件が `sources/*.py` として存在するが `SCRAPERS` リストに未登録のまま本番稼働していた。DB ステータスは `implemented` だったが CI では一度も実行されていなかった。
**Discovery**: `research_sources` DB の `implemented` 件数 vs `sources/` ファイル一覧と `SCRAPERS` リストの三者クロスチェックで発見。
**Fix**: `scraper/main.py` に 8 件の import と `SCRAPERS` 追記。全件 dry-run で動作確認後にコミット。
**Lesson**: DB `implemented`、ファイル存在、`SCRAPERS` 登録の三者は独立して管理される。新規スクレイパー作成時は必ず同一コミットで `SCRAPERS` に追加する。定期監査コマンド:
```bash
python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
"
```

---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:この映画は香港の食堂を舞台に、社会の変化に直面する人々の姿を描いており、台湾、香港、フランスの共同制作です。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


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

---
## 2026-04-29 — Peatix 三層爬取架構固化（daily review）
**新增/修改：**
- `## Peatix-specific` 新增 Three-layer organizer architecture 表格（Layer 1 keyword / Layer 2 hardcode / Layer 3 DB-driven）
- 記錄 `_load_db_organizers()` 的 `agent_category='peatix_organizer'` 查詢條件
- 記錄「Never remove Layer 2」規則（DB status 意外變更時的 backup）
**來源：** daily-skills-review（Step 4 建議）

## 2026-04-29 — iwafu docstring 誤記（東京限定と表記されていた全国スクレイパー）[iwafu]
**Error**: `iwafu.py` モジュール docstring に「Filter to events where prefecture == 東京」と記載されていたが、実コードは `cards = all_cards`（フィルターなし）で全国カバー済み。
DB candidate id=97（iwafu EN `/en/events/`）も「福岡拡張が必要」と判断されていたが、JP スクレイパーで既に全国カバーされているため重複。
**Fix**: docstring を「No prefecture filter — all regions included」に修正。DB id=97 を not-viable に更新（理由付き）。
**Lesson**: 「機能を追加する前にコードを読む」。scraper の実際の挙動（cards フィルター有無）を確認してから「拡張が必要か」を判断する。docstring とコードが乖離するリスクを防ぐため、prefecture フィルターの有無は SKILL.md に明記しておく。

---

## 2026-04-29 — SCRAPERS リスト未登録スクレイパー 8 件発見（pipeline 監査）[main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper の 8 件が `sources/*.py` として存在するが `SCRAPERS` リストに未登録のまま本番稼働していた。DB ステータスは `implemented` だったが CI では一度も実行されていなかった。
**Discovery**: `research_sources` DB の `implemented` 件数 vs `sources/` ファイル一覧と `SCRAPERS` リストの三者クロスチェックで発見。
**Fix**: `scraper/main.py` に 8 件の import と `SCRAPERS` 追記。全件 dry-run で動作確認後にコミット。
**Lesson**: DB `implemented`、ファイル存在、`SCRAPERS` 登録の三者は独立して管理される。新規スクレイパー作成時は必ず同一コミットで `SCRAPERS` に追加する。定期監査コマンド:
```bash
python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
"
```

---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:この映画は香港の食堂を舞台に、社会の変化に直面する人々の姿を描いており、台湾、香港、フランスの共同制作です。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


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

---

## 2026-04-29 — annotator: truncation limit 12K→20K でも GPT が sub-events を 2 件しか生成しない

**発見：** 台湾文化センター「台湾映画上映会2026」（16 場上映）の sub-events が 2 件しか DB に存在しない。annotator の truncation limit を 12,000→20,000 に引き上げたが、GPT-4o-mini は依然 2 件の sub-events しか返さなかった（output: 1,191 tokens）。

**根本原因：** description が 13,492 文字（旧 12,000 char truncation で切断されていた）→ truncation 修正後も GPT-4o-mini は全 16 件を抽出しなかった。入力が長く密度が高い場合、GPT が自律的に生成を打ち切る傾向がある。

**修正：** 
1. `annotator.py` truncation limit 12,000→20,000 chars（commit `ff2a2ac`）
2. `_insert_sub_events.py` で 16 件の sub-events を手動挿入（一時スクリプト、削除済み）
3. Sub-events：10 正片（5月〜10月）＋ 6 アンコール（6/7, 9/19, 10/4 @ ユーロライブ/シネ・ヌーヴォ）

**教訓：** GPT が全 sub-events を確実に生成しない場合、scraper 層で直接 sub-events を生成するほうが信頼性が高い。連続上映シリーズ（映画祭等）は scraper で各回を `Event` として生成し `parent_event_id` を設定するべき。

---

## 2026-04-28 — eiga_com: 原題から name_zh / name_en を直接抽出する

**発見：** 映画.com の映画詳細ページ（例：`/movie/82162/`）の `p.data` に「原題または英題：阿嬤的夢中情人 Forever Love」という行が存在する。スクレイパーは `name_ja`（日本語配給タイトル）しか設定していなかったため、中文・英語タイトルは AI アノテーターの推測に頼っていた。

**根本原因：** `_fetch_movie_detail()` は `p.data` から製作年・上映時間・国情報のみ使用し、`原題` 行を無視していた。

**修正：** `_ORIG_TITLE_RE` regex と `_parse_original_title()` helper を追加。
- 非 ASCII ブロック（CJK）→ `name_zh`、ASCII ブロック（英語）→ `name_en` に分離
- `_fetch_movie_detail()` の返り値を `(title, pub_date, raw_description, name_zh, name_en)` に拡張
- fallback Event と `_scrape_area_page()` の両方に `name_zh`, `name_en` を渡す

**例：**
- `原題または英題：阿嬤的夢中情人 Forever Love` → `name_zh="阿嬤的夢中情人"`, `name_en="Forever Love"`

**Lesson：**
- 映画系ソースには必ず詳細ページの「原題」「英題」「原題または英題」フィールドを確認すること。
- 原タイトルは AI より高精度 — スクレイパーで確定できる情報は AI に任せない。
- ルールを SKILL.md `## eiga_com-specific` に追記済み。

---

## 2026-04-26 — scope expanded to all of Japan（全日本）

**Change:** Removed `prefecture=tokyo` from Connpass API params; updated docstrings for Doorkeeper and Connpass; updated agent descriptions and community-platforms subagent.

**Root cause:** Scrapers were unintentionally limited to Tokyo by an API parameter. The project scope is all of Japan — Osaka, Kyoto, Fukuoka, Sapporo, etc. are all in scope.

**Fix:** `connpass.py` no longer passes `prefecture=tokyo`; `doorkeeper.py` has never had a location filter and should stay that way.

**Lesson:** Never add a prefecture/region filter to API scrapers unless the *source itself* is geographically bounded. Taiwan relevance (`_TAIWAN_KEYWORDS`) is the only required filter. → Added `## Geographic Scope` to SKILL.md.

---
## 2026-04-26 — スコープ拡張：東京限定 → 全日本

**変更内容**: ユーザー指示により対象スコープを東京から全日本（全国）に拡張。

**背景**: プロジェクト名は「Tokyo Taiwan Radar」だが、台湾関連イベントは大阪・京都・福岡・札幌等でも開催される。スクレイパーが地理フィルターで東京以外のイベントを除外することは意図しない動作。

**適用した変更**:
- `copilot-instructions.md` — プロジェクト概要を「in Japan（全日本）」に更新、Geographic Scope 注記追加
- `scraper-expert.agent.md` — description + `> **Scope**` 注記追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加

**教訓**: 地理的スコープは SKILL.md の冒頭に専用セクションとして明示すること。東京以外を除外する地理フィルターを追加する前に Geographic Scope セクションを必ず確認すること。

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
