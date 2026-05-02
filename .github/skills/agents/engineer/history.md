# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-05-02 — inline Python shell injection 汙染；zsh git add glob 括號失敗；分類新增 6 處協議

**問題 A：inline Python shell injection**
在終端執行 `python3 << 'PY' ... PY` 或 `python3 -c "..."` 時，shell history 汙染導致惡意片段（如 `rm -f ...`）插入 f-string，造成 SyntaxError 或非預期執行。
- **修正：** 改用 `create_file` 建立 `/tmp/<name>.py` 腳本，再執行 `python3 /tmp/<name>.py`。
- **教訓：** 一旦出現 SyntaxError 且指向 f-string 大括號，立即放棄 inline 模式，改用 `/tmp/*.py` 腳本。

**問題 B：zsh `git add` 含 `[...]` 路徑**
`git add web/app/[locale]/page.tsx` 在 zsh 中因 glob 展開失敗：`zsh: no matches found`。
- **修正：** `git add 'web/app/[locale]/page.tsx'`（單引號）
- **教訓：** 含方括號的路徑在 zsh 必須用單引號包覆，適用所有 `git add`、`cp`、`mv` 操作。

**問題 C：分類新增（`documentary`、`parenting`）6 處同步協議**
- 每次分類新增必須在**同一個 commit** 更新 6 處（Category union、CATEGORIES、CATEGORY_GROUPS、zh/en/ja.json）。
- 完成後執行 `cd web && npx tsc --noEmit`，無錯誤才能 commit。
- i18n JSON 含 CJK 字元時必須用 Python json-module 腳本編輯（不可用 `replace_string_in_file`）。

---
## 2026-05-02 — Daily Dev Report、WIP tracking、Overseas filter 實作（commits `0ee713d`、`f56c4e0`、`96834f8`、最新 commit）

**Daily Dev Report（`0ee713d`）：**
- 新增 `scraper/daily_report.py`：查詢 Supabase（`scraper_runs`、`events`、`event_reports`、`research_sources`）＋ `GIT_COMMITS` env var，輸出四個 section：昨日提交、爬蟲結果、待處理事項、安全日誌。
- 新增 `.github/workflows/daily-dev-report.yml`：每日 02:00 JST cron，`dawidd6/action-send-mail@v3` 透過 Gmail SMTP 寄送報告。
- **CI secrets 需求**：`GMAIL_USER`、`GMAIL_APP_PASSWORD`（App Password，非一般 Gmail 密碼）、`DEV_REPORT_EMAIL`。

**WIP tracking（`f56c4e0`）：**
- 新增 `.github/wip.md`：存放進行中開發項目，`## 功能名稱` = active，`## ✅ 功能名稱` = completed。
- `daily_report.py` 加入 `_read_wip_items()`：以 `Path(__file__).parent.parent / ".github" / "wip.md"` 跨目錄讀取；在「待處理事項」section 顯示「🚧 開發中項目」。

**Recently-completed WIP items（`96834f8`）：**
- `_read_wip_items()` 改回傳 `(active, recently_completed)` tuple。
- `## ✅` 項目需有 `最後更新: YYYY-MM-DD` 且落在過去 26 小時內，才顯示為「✅ 昨日完成」；超過 26 小時靜默略過。
- regex：`_WIP_DATE_RE = re.compile(r"最後更新[:\uff1a]\s*(\d{4}-\d{2}-\d{2})")` — 同時支援中文冒號（`：`）和英文冒號（`:`）。

**Overseas (Taiwan cities) filter（最新 commit）：**
- `FilterBar.tsx`：新增 `<option value="overseas">`。
- `AdminEventTable.tsx`：`filterLocation` union 加 `'overseas'`；filter 邏輯使用 16 個台灣城市 markers 做 `includes()` 比對。
- `web/app/[locale]/page.tsx`：overseas branch 用 `ilike '%城市名%'` 對 `address` 欄位比對；16 個城市依序 OR 組合。
- i18n 三語同步：`海外（台灣各城市）` / `Overseas (Taiwan Cities)` / `海外（台湾各都市）`。
- **教訓**：台灣城市名稱直接存在 `address` 欄位，不需前綴守衛；`OVERSEAS_MARKERS` 陣列在 `page.tsx` 和 `AdminEventTable.tsx` 兩處必須完全同步。

---
## 2026-05-02 — annotator google_news_rss Playwright 文章補抓（commit `9a0414a`）
- **問題**：google_news_rss 的 `raw_description` 只有 RSS snippet（通常只有標題），GPT 無法從中提取活動日期，`start_date` 永遠為 NULL。
- **修正**：在 `annotator.py` 新增 `_fetch_gnews_article_text()`，使用 Playwright 追蹤 Google News 重導向 URL 取得原始文章本文（最多 4000 字），替換 `raw_desc` 傳給 GPT。整個 run 共用一個 Playwright browser 實例；`raw_description` 欄位不寫回 DB（in-memory only）。失敗時（timeout / paywall / DNS）gracefully fallback 到原始 snippet。
- **教訓**：Playwright browser 實例應在 annotation loop 前啟動、`finally` 中關閉，不可逐事件重啟。文章文字是 annotation 輸入的暫存資料，絕不寫回 DB 原始欄位。

---
## 2026-05-02 — google_news_rss scraper start_date fallback 修正（commit `9510a05`）
- **問題**：`_extract_start_date()` 找不到日期時 fallback 使用 `pub_date`（文章發布日），與活動日期無關。Google News RSS `<description>` 永遠只有標題短文，不含活動日期，幾乎每筆都觸發 fallback。
- **修正**：`_extract_start_date()` 回傳型別改為 `Optional[datetime]`；找不到日期改回傳 `None`，不再 fallback 到 pub_date。批次效果：40 筆 start_date=pub_date 的錯誤資料被下架；1 筆原始連結失效的事件（c2c80efd）直接設為 `is_active=False`。
- **教訓**：聚合新聞來源（Google News RSS）的 pub_date ≠ 活動日期，不可作為 start_date fallback。找不到日期必須回傳 `None`；annotator 會透過 Playwright 文章補抓取得正確日期。原始連結已失效的事件直接設 `is_active=False`，不嘗試保留。

---
## 2026-05-01 — 移除無效地點篩選選項「電視節目 (tv)」（commit `2989940`）

**問題：** FilterBar 與 AdminEventTable 的 `<option value="tv">` 地點篩選選取後結果永遠為零，是無效選項。`gguide_tv` 事件 `location_name` 已改存頻道名稱，不再是「電視頻道」，與 tv 篩選邏輯不匹配。

**修正檔案（共 6 處）：**
- `web/components/FilterBar.tsx` — 移除 `<option value="tv">`
- `web/app/[locale]/page.tsx` — 移除 `sp.location === "tv"` 查詢分支
- `web/components/AdminEventTable.tsx` — 移除 tv option 及兩處 `filterLocation === "tv"` 判斷
- `web/messages/zh.json`、`en.json`、`ja.json` — 移除 `locationTv` i18n key（共 3 檔）

**教訓：** 地點篩選選項值必須對應 DB 實際存在的 `location_name`。移除某個 location option 時，需同時清理：FilterBar `<option>`、`page.tsx` 查詢分支、AdminEventTable option 與 filter 邏輯、三個 i18n 檔案的 key。

---
## 2026-05-01 — archive cutoff 與 quality page 截止日不一致（1e6cd24）

**問題：** `archive_ended_events()` cutoff = `yesterday 00:00 UTC`（1 天寬限），quality page cutoff = `today`，造成當天到期事件出現在 quality 清單但不會被自動下架，需等兩天才消失。

**根本原因：** `database.py` 的 `archive_ended_events()` 使用 `timedelta(days=1)` 寬限期，而 quality page 直接用 `today` 當截止，兩端定義不一致。

**修復：** `database.py` 移除 `timedelta(days=1)`，改為 `today 00:00 UTC`；DB 手動下架 4 筆到期事件（`b2589d75`、`78570c96`、`8c08c681`、`dec284a5`）。

**教訓：** scraper `archive_ended_events()` 的 cutoff 必須與 admin quality page 的 `today` 截止一致，否則會有「過期但不下架」的空窗期。如需寬限期，兩端必須使用相同天數。

---
## 2026-05-01 — 品質頁面誤判多城市活動為「地址缺失」

**問題：** `web/app/[locale]/admin/quality/page.tsx` 的「地址缺失」品質檢查把 `location_name` 含「・」（如「東京・京都・大阪」）的多城市活動標記為異常，造成誤報。

**根本原因：** 多城市活動格式慣例為 `城市A・城市B・城市C`，這類活動的 `location_address` 刻意設為 `null`（避免錯誤錨定到單一城市）。品質檢查邏輯沒有識別此格式，誤判為資料缺失。

**修正：** 在 missing-address 過濾器中排除 `location_name.includes('・')` 的活動。

**教訓：** 多城市活動 `location_address = null` 是正確狀態，不是錯誤。任何「地址缺失」品質檢查都必須先排除 `location_name.includes('・')` 的多城市活動。

---
## 2026-05-01 — quality page is_active=false 事件導致 404（commit `dd76445`）

**問題：** `reviewedMissing` 和 `annotatedNoCat` query 沒有 `.eq("is_active", true)`，已下架事件出現在清單，點選後 404（詳情頁只顯示 is_active 事件）。

**根本原因：** 新增 query 時只套用了主要 query 的 is_active filter，沒有同步套用到所有 section query。

**修復：** 兩個 query 都加上 `.eq("is_active", true)`。

**教訓：** Quality page 的所有 Supabase query 都必須加 `.eq("is_active", true)`，否則下架事件會出現在清單，點選後 404。

---
## 2026-05-01 — quality page 缺地址誤報：多城市 ・ filter（commit `a2fd6d6`）

**問題：** `location_name` 含 `・`（多城市格式，例如「北海道・東京・神奈川・京都・大阪」）的活動出現在缺地址清單，造成誤報。

**根本原因：** `missingAddr` filter 沒有排除多城市活動格式。多城市活動慣例是 `location_name` 用 `・` 連結城市，本身沒有單一地址。

**修復：** `missingAddr` filter 新增排除含 `・` 的 `location_name`；DB patch `一石三鳥グループ` 父活動（`466497e5`）`location_name` → `東京・京都・大阪`。

**教訓：** Quality page `missingAddr` filter 必須同時排除：「オンライン」、「電視頻道」、`gguide_tv` source、以及含 `・` 的 `location_name`（多城市活動）。

---
## 2026-05-01 — quality page 事件連結改為詳情頁（commit `9dd50f3`）

**問題：** `renderDetailTable` 中的 href 指向 `/{locale}/admin/{id}`（編輯頁），應改為 `/{locale}/events/{id}`（詳情頁）。

**根本原因：** 複製 admin 頁面連結時直接用了編輯路由，沒有考慮 quality page 是查看用途。

**修復：** 改 href 為 `/{locale}/events/{id}`，並加 `target="_blank"` 新分頁開啟。

**教訓：** Admin 後台列表頁面（quality、reports 等）的事件超連結一律指向 `/{locale}/events/{id}`（詳情頁），而非 `/{locale}/admin/{id}`（編輯頁）。

---
## 2026-05-01 — taiwan_cultural_center 多城市地點名稱改進（commit `0d900b5`）

**問題：** `location_name` 顯示模糊的「台湾文化センター（全国巡回）」，用戶期望看到具體城市列表（如「北海道・東京・神奈川・京都・大阪」）。

**根本原因：** `_MULTI_CITY_REGIONS` 偵測到多城市後，只設置通用「全国巡回」字串，沒有把偵測到的城市名列入 `location_name`。

**修復：**
1. 改為 `_found_regions = [r for r in _MULTI_CITY_REGIONS if r in _desc_check]`，然後 `"・".join(_found_regions)` 作為 `location_name`。
2. 新增 `東京` 和 `愛知` 到偵測清單（原本漏掉「東京」導致東京+大阪等場合無法觸發）。
3. DB 直接 patch event `51f7cd44` → `location_name = '北海道・東京・神奈川・京都・大阪'`。

**教訓：** 多城市偵測邏輯應直接輸出偵測到的城市列表，而非通用字串；`東京` 必須加入偵測清單（因為它出現在大多數多城市活動中）。

---
**Error**: TaiwanbunkasaiScraper fetch failed — HTTPSConnectionPool Max retries exceeded
**Fix**: Added HTTPAdapter with Retry(total=3, backoff_factor=2) to requests.Session in taiwanbunkasai.py
**Lesson**: All scrapers using requests.Session must mount HTTPAdapter with Retry at __init__ to handle transient network failures from GitHub Actions runners.

---
## 2026-05-01 — taiwan_cultural_center 多城市巡迴偵測修正（commit `a2d6eea`）

**問題：** `台湾映画上映会2026` 是跨北海道・東京・神奈川・京都・大阪 5 城市的巡迴活動，但 scraper 將 `location_address` hardcode 為東京（台湾文化センター）地址，admin 後台「住所」欄顯示東京地址，造成誤導。

**根本原因：** `taiwan_cultural_center.py` 的 location block 完全 hardcode，沒有任何多城市偵測邏輯。

**修復：**
1. **DB 補丁**：直接 patch event `51f7cd44`（台湾映画上映会2026）—— `location_name` → `台湾文化センター（全国5都市）`，`location_address` → `None`。
2. **Scraper 修正**：加入 `_MULTI_CITY_REGIONS` 偵測，description+name 中出現 ≥2 個地區 keyword 時，改用 `台湾文化センター（全国巡回）`，並清空 `location_address`：
   ```python
   _MULTI_CITY_REGIONS = ["北海道", "大阪", "京都", "神奈川", "福岡", "名古屋", "仙台"]
   if sum(1 for r in _MULTI_CITY_REGIONS if r in _desc_check) >= 2:
       location_name = "台湾文化センター（全国巡回）"
       location_address = None
   ```

**教訓：**
- 實體地址不應 hardcode 在 scraper 中；多城市活動需偵測。
- 門檻 ≥2（不用 1），避免「在東京舉辦但描述提到大阪食文化」的 false positive。
- 偵測 keyword list 應涵蓋台灣文化中心有據點的城市：北海道/大阪/京都/神奈川/福岡/名古屋/仙台。
- 多城市偵測模式可推廣至其他有固定地址 hardcode 的 scrapers。

---
## 2026-05-01 — auto_scraper Phase 2 codegen + sandbox（commit `a0606fe`）
**新增：** `## Auto-Scraper Layer B — generate.py` 段落至 engineer/SKILL.md
**內容：**
- Sandbox env allowlist（`SUPABASE_*`、`OPENAI_API_KEY` 等 secrets 絕對不傳）
- Phase 2 scope boundaries（不開 PR、不注入 SCRAPERS、不寫 events DB）
- Cleanup defence-in-depth（`try/finally` + `atexit.register` 雙重保障）
- Budget guard 常數（需定期驗證 OpenAI 定價）
- 7-day retry cooldown 機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — auto_qa anomaly detection + weekly report links (commit `2ae731b`)

**Feature:** New `scraper/auto_qa.py` scans `is_active` events from past 14 days for two anomaly types — `auto_qa_simplified_zh` (simplified Chinese chars in any `*_zh` field) and `auto_qa_missing_address` (has `location_name` but empty `location_address`, with online/TV/`gguide_tv` skipped). Findings are inserted into `event_reports` as pending rows so admins review them at `/admin/reports` (same UI as user-submitted reports). `merger.yml` runs auto_qa 3×/day after `--fix-reviewed`. `weekly_report.py` queries `event_reports` for past 7 days of `auto_qa_*` rows and appends a 🔍 自動 QA 偵測 section to the LINE message with a clickable admin link, only when total > 0. `weekly-report.yml` gained `NEXT_PUBLIC_SITE_URL` env.

**Lesson 1 — `亮` false positive:** Initial `SIMP_RE` draft included `亮`, but `亮` is identical in Traditional Chinese and Japanese (`照亮` is valid Trad). Production dry-run flagged a real Trad description. **Rule:** Only add a char to `SIMP_RE` (or `annotator._LOC_ZH_SIMP_TO_TRAD`) when the corresponding Trad/JP form is a **different glyph**. Verify via CC-CEDICT or kanji.jitenon.jp before adding.

**Lesson 2 — share the user-report queue:** Auto-detected anomalies and user-submitted reports both flow through `event_reports`. Benefits: (a) admin checks one URL; (b) `report_types text[]` allows multiple anomaly types per row; (c) existing confirm/dismiss flow handles auto-QA unchanged. Reusable pattern: future automated checks (dead links, date sanity) should also write to `event_reports` with their own `auto_*` prefix in `report_types`. Dedup against existing pending rows of the same `auto_*` type per `event_id`.

---
## 2026-05-01 — discovery-accounts cron expanded Mon-Thu → Mon-Sun (commit `c936920`)

**Change:** `.github/workflows/discovery-accounts.yml` cron schedule expanded from 4 entries (Mon-Thu) to 7 entries (Mon-Sun) at 02:00 UTC / 11:00 JST. Existing `(DAY-1) % 4` modulo logic in shell already handled all 7 days — no Python change. Slot mapping: Mon→0 / Tue→1 / Wed→2 / Thu→3 / Fri→0 / Sat→1 / Sun→2.

**Lesson — modulo wrap on cron-driven slots:** When N weekdays meet M<N slots via `(DAY-1) % M`, days M+1..N silently re-run slots 0..(N-M-1). Acceptable when those slots are idempotent (search + `skip_hint` dedup yields diminishing returns). NOT acceptable for slots that must run on a fixed cadence (e.g. Peatix slot 3 still only fires Thursdays). To break the wrap: (a) override via `DISCOVERY_SLOT` env on extra cron entries, or (b) raise `SLOT_COUNT`.

---
## 2026-05-01 — 8 scrapers missing from research_sources (no auto-registration mechanism)

**Error:** Architect audit discovered 8 scrapers in `main.py SCRAPERS` had no corresponding `research_sources` row: `prtimes`, `maruhiro`, `hankyu_umeda`, `daimaru_matsuzakaya`, `google_news_rss`, `nhk_rss`, `mot`, `transit_store`.

**Root cause:** The "new scraper checklist" listed only 3 steps (create → SCRAPERS → dry-run). Registering in `research_sources` was never documented. The `researcher.py` `known_urls` filter depends on this table to avoid re-surfacing already-implemented sources.

**Fix:**
- Manually inserted all 8 missing rows into `research_sources`.
- Added `_warn_unregistered_scrapers()` to `main.py` (non-dry-run guard): compares SCRAPERS keys against `research_sources.scraper_source_name`, emits `⚠️ WARNING` for any gap. Runs every CI cycle.
- Updated `Scraper Implementation` section in `SKILL.md` to make step 3 ("register in research_sources") explicit.

**Lesson:** "Register in research_sources" is step 3 of the new scraper checklist — as mandatory as registering in SCRAPERS. Any omission now produces a visible CI WARNING within 24 hours.

---
## 2026-05-01 — healthcare 新分類加入 group_lifestyle（commit `bd89c57`）

**變更：** 新增 `healthcare`（健康・醫療 / Health & Wellness / ヘルスケア）分類至 `group_lifestyle`。

**教訓：** Category Update Protocol 6 步驟全部完成（union + CATEGORIES + CATEGORY_GROUPS + zh/en/ja）。group_lifestyle 是此類分類的正確歸屬。

---
## 2026-05-01 — 分類標籤重命名：nature、history

**變更：**
- `nature` → 風土・水果・環境永續 / Nature, Produce & Sustainability / 風土・果物・SDG
- `history` → 歷史・文化遺產・根源 / History, Heritage & Roots / 歴史・文化遺産・ルーツ

**教訓：** i18n 標籤改名只需更新三個 `web/messages/*.json`，category key 不變，DB 資料不需異動。group labels 亦同（`group_arts`、`group_lifestyle`、`group_knowledge` 等鍵值不變，只改顯示文字）。

---
## 2026-05-01 — 分類群組大調整（commits `a07b792`, `5b66c33`）

**變更：**
- `competition`（競技・競賽）、`workshop`（體驗・工作坊）從 `group_knowledge` 移至 `group_lifestyle`
- `exhibition`（展覽）、`books_media`（書・媒體）、`tv_program`（電視節目）從 `group_knowledge` 移至 `group_lifestyle`
- `group_knowledge` 調整後只剩：`business`、`academic`、`lecture`、`taiwan_japan`

**根本原因：** 分類設計初期 `group_knowledge` 定義不夠嚴格，把生活風格類別錯誤納入。

**修復：** 僅修改 `web/lib/types.ts` 的 `CATEGORY_GROUPS` 陣列，不需動元件代碼。

**教訓：** Category 群組重組只需改 `types.ts` 的 `CATEGORY_GROUPS`，因為 `AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx` 都從 `CATEGORY_GROUPS` 讀取（三檔共用 source，不需個別修改元件代碼）。

→ 已更新 `SKILL.md § Category Update Protocol — 群組重組`

---
## 2026-05-01 — Location filter 6-region 完全重寫（commit `b8dfe2b`）

**變更：** 地點篩選器從 `tokyo / other_japan / taiwan / online / tv` 改為 `tokyo / kanto / chubu / chugoku / online / tv`，地區判斷改用 address `ilike` marker 清單：

| 選項 | marker 清單 |
|------|------------|
| tokyo | 東京各區標記，或 address 為 null（預設東京）|
| kanto | 神奈川/埼玉/千葉/茨城/栃木/群馬/山梨/東北各縣/北海道 |
| chubu | 愛知/静岡/岐阜/長野/新潟/富山/石川/福井/大阪/京都/兵庫/奈良/滋賀/和歌山/三重 |
| chugoku | 広島/岡山/鳥取/島根/山口/九州各縣/四國各縣/沖縄 |
| online | location_name 含 オンライン |
| tv | location_name 含 電視頻道 |

**根本原因：** 原 `other_japan` 選項過粗，無法區分關東、中部、中国・九州。

**修復：** 三處同步更新：
1. `FilterBar.tsx` — 選項 options + i18n keys
2. `web/app/[locale]/page.tsx` — server-side OR query（`location_address ilike`）
3. `AdminEventTable.tsx` — state 型別 union literal + marker arrays + `getFiltered` + `sourceCountMap`

**教訓：**
- Location filter 有三處必須同步：FilterBar 選項、page.tsx server query、AdminEventTable state 型別。
- `filterLocation` state 型別（union string literal）必須跟 options 精確一致，TypeScript 不報錯但未知值會導致所有事件被過濾。
- 地區判斷改用 address `ilike` marker 清單，避免 NOT 邏輯漏網。

→ 已更新 `SKILL.md § Location Filter Three-File Sync Rule`

---
## 2026-05-01 — GITHUB_TOKEN 權限描述不一致（Issues 權限口徑分裂）

**問題：** 同一 repo 內對 fine-grained PAT 權限出現多種寫法（非標準 `&` 合併寫法、`Issues: write` 兩種混用），且部分文件未明確寫出 `Metadata: read`，導致配置判讀混亂。

**修復：** 將 code + docs + agent 口徑統一為：
- Fine-grained PAT：`Issues: write + Metadata: read`
- Classic token：`repo` scope

同步更新檔案：`scraper/update_source.py`、`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`、`.github/instructions/token-rotation.instructions.md`、`.github/agents/researcher.agent.md`、`.github/SECRETS_LIFECYCLE.md`。

**教訓：**
1. 安全/權限敘述變更必須「跨層原子更新」（runtime error message + docs + agent 說明）。
2. 不可讓非標準的 `&` 分隔權限寫法與 `Issues: write + Metadata: read` 長期並存。
3. public repo 文件中的權限例子必須可直接採用最小權限原則，避免誤導開過寬權限。

---
## 2026-05-01 — Admin Tab Nav 10 頁不一致（commit `1f37bb4`）

**問題：** 10 個 admin 頁面的 tab nav 內容互不一致。有些頁面有 quality tab，有些沒有；有些有 announcements tab，有些沒有。最嚴重的是 announcements/page.tsx 只有 5 個 tab，而 admin 主頁有 10 個。

**根本原因：** 每次新增 admin 子頁面（quality、announcements 等），只在部分現有頁面加入新 tab link，沒有統一更新全部頁面。Tab nav 是手動在每個頁面各寫一份，沒有共用元件。

**修復：** 統一全部 10 頁的 tab nav 為相同順序：Events → Announcements → Reports → Stats → Quality → Research → Sources → Users → Creators → SEO-AEO。加上 `flex-wrap` 防止行溢出。

**教訓：**
- 新增 admin 子頁面時，**必須同時更新全部現有 admin 頁面的 tab nav**。
- 驗證指令：`grep -o 'admin/[a-z]*' web/app/\[locale\]/admin/*/page.tsx | sort | uniq -c` 確認每個 route 出現次數一致。
- 未來可考慮抽出 `AdminTabNav` 共用元件（每頁的 active tab 用 span vs Link 區分，需 prop 傳入 current page）。

→ 已更新 `SKILL.md` § Admin Tab Nav Sync Rule

---
## 2026-05-01 — OG Image 英文標題截斷過短（commit `47ac1ee`）

**問題：** OpenGraph 圖片中英文標題被截斷過短，只顯示部分文字。

**修復：** 增加截斷字數上限（36 → 55），並為長英文標題新增 40px 字體大小層級（原本只有 72px / 54px 兩級）。

**教訓：** OG image 截斷閾值以英文為基準（字元窄、數量多），搭配字體縮小梯級，避免硬截斷。詳見 Architect history 同日條目。

---
## 2026-05-01 — 地址補齊功能 + Quality page 缺地址誤報修正（commit `590a80a`）

**問題：** Quality page「缺地址（非線上活動）」顯示 29 筆，但其中 18 筆是 gguide_tv 電視頻道事件（NHK、BS朝日等），這些沒有實體地址，屬於誤報。

**根本原因：**
- gguide_tv 事件的 `location_name` 存的是頻道名稱（如 "NHK総合1・東京"），未統一為「電視頻道」，導致 filter 無法排除。
- Quality check 最初未考慮「無地址是合理的」情境（TV 頻道、線上活動）。
- 剩下真正缺地址的事件（如 ssff 展映）有場館名但 scraper 沒抓地址欄位。

**修復：**
1. `quality/page.tsx`：`missingAddr` filter 排除 `source_name === "gguide_tv"` 和 `location_name.includes("電視頻道")`。
2. DB 補丁：21 筆 gguide_tv 事件統一 `location_name = '電視頻道'`。
3. 新工具 `scraper/enrich_addresses.py`：用 OpenAI gpt-4o-mini 查場館地址，`confidence=high` 才寫入，支援 `--dry-run` / `--source`；執行結果：8 筆成功（ssff ×6、google_news_rss ×2）。

**教訓：**
- **Quality check 必須考慮「無地址是合理的」情境**：新增缺欄位 check 時，先列出受影響 source_name 分組統計，確認哪些來源天然就沒有該欄位。
- 診斷缺地址問題：先用 `GROUP BY source_name` 找主因，避免一律標示為「待修」。
- `enrich_addresses.py` 模式可複用：任何有 venue name 無地址的來源都適用，`confidence` 欄位防止 LLM 亂猜地址。

→ 已更新 `SKILL.md` § enrich_addresses.py — 地址補齊工具 及 § Quality Page — 缺欄位誤報排除模式

---
## 2026-05-01 — AdminReportsTable bulk confirm 被另一個 agent 意外刪除並恢復

**問題：** commit `3d45de6`（「refactor(web): remove realtime subscription and bulk confirm from AdminReportsTable」）由非 Engineer agent 執行，在移除 Realtime subscription 的同時，一併刪除了先前實作的多選批量確認功能（`selectedIds`、`bulkConfirming`、`handleBulkConfirm`、勾選框、bulk action bar）。

**根本原因：** Agent 把 bulk confirm 視為「與 Realtime 捆綁的功能」一起移除，而非獨立功能。Realtime subscription 可以拆除，但 bulk confirm 是獨立 UX 功能，不應隨之消失。

**修復（commit `4c30ab3`）：**
- 恢復 `selectedIds: Set<string>` 和 `bulkConfirming: boolean` state
- 恢復 `handleBulkConfirm(rows: ReportRow[])` sequential loop（不用 `Promise.all`，因 `handleConfirm` 內有 `setSaving`）
- 恢復每筆 pending 行的勾選框：`<div className="flex items-stretch">` 包住 checkbox label + button
- 恢復 section header 右側 bulk action bar（`bulkCancelSelect`、`bulkConfirmSelected { count }`、`bulkConfirmAll { count }`）
- 批量按鈕文字改用 i18n keys，三個 messages 檔同步新增

**教訓：**
- **AdminReportsTable bulk confirm 是受保護功能**：`selectedIds`、`bulkConfirming`、`handleBulkConfirm` 不得被任何 agent 移除，除非 PRD 明確指示。
- 移除某功能（如 Realtime）時，必須逐項確認 diff 不包含無關功能的刪除。
- 診斷方式：`git log --oneline --all | head -15` 找到刪除 commit → `git show <hash> --stat` 確認刪除內容 → 從 SKILL.md 規格重建實作。

→ 已更新 `SKILL.md` § AdminReportsTable — Protected Feature: Bulk Confirm

---
## 2026-05-01 — AdminSourcesTable i18n 修復：Filter Labels 硬編碼中文

**問題：** `AdminSourcesTable.tsx` 的「狀態」、「全部」、「來源分類」、「編輯分類對照表」都是 hardcoded 中文，未走 `t()` hook。

**根本原因：** 初次實作時只顧功能，未套 i18n，後來也沒有 lint 規則報錯，因此一直沒被發現。

**修復：** 改為 `t("sourcesFilterStatus")`、`t("sourcesFilterAll")`、`t("sourcesFilterType")`、`t("sourcesEditTypeMap")`，三個 i18n 檔（zh/en/ja）同步新增對應翻譯。

**教訓：** TSX 中任何可見文字（filter label、button、placeholder、section header）都必須走 `t()`，禁止硬編碼中文/日文。新增 admin 元件時，應在實作完功能後立即對照 TSX 全文搜尋裸字串，統一轉換。

→ 已更新 `SKILL.md` § AdminSourcesTable — i18n 規則

---
## 2026-05-01 — CI workflow 改善：merger.yml 排程 + Node.js 24 opt-in

**修改：**
1. **merger.yml 新建（commit 85049b1）**：`workflow_dispatch` 手動觸發，只跑 `python merger.py`。`scraper.yml` 同時插入 "Run merger" 步驟（位於 `main.py` 後、`annotator.py --fix-reviewed` 前）。每日 CI 管道順序確立為 `main.py → merger.py → annotator.py → annotator.py --fix-reviewed`。
2. **Node.js 24 opt-in（commit 3cd06a9）**：`scraper.yml` 和 `merger.yml` top-level 加入 `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`，消除 `actions/checkout@v4`、`actions/setup-python@v5` 的 Node.js 20 deprecation warning（GitHub 強制遷移日：2025-06-02）。
3. **merger.yml 加排程（commit 4c999cb）**：3 個 cron `01:00 / 09:00 / 16:00 UTC`（JST 10:00 / 18:00 / 01:00），每次跑完 merger 後接著跑 `annotator.py` + `annotator.py --fix-reviewed`。

**教訓：**
- 任何使用 `actions/checkout@v4` 或 `actions/setup-python@v5` 的 workflow **都需要** top-level `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`。
- merger 跑完後必須立刻跑 annotator，否則合併事件以 `pending` 狀態滯留。
- 新建共用依賴的 workflow（如 merger.yml）時，必須同步檢查 scraper.yml 的所有步驟是否也需要加入（step parity rule）。

→ 已更新 `SKILL.md` § GitHub Actions Workflow Rules

---
## 2026-05-01 — `/admin/quality` Tester 首輪 FAIL：react-hooks/static-components

**問題：** `web/app/[locale]/admin/quality/page.tsx` 在 `QualityPage` render body 內宣告 `SectionHeader` 元件與 `eventLink` JSX helper，被 ESLint `react-hooks/static-components` 規則擋下，Vercel build 失敗。

**根本原因：** Next.js 15+ / React 19 把任何 PascalCase + 回傳 JSX 的函式視為 component；component 必須在模組頂層宣告，不能寫在另一個 component 的 render 內。`eventLink` 雖為 camelCase，但被當 `<EventLink />` tag 使用時也會被誤判。

**修復：**
1. `SectionHeader` 提升至模組頂層，需要的值改透過 props 傳入。
2. `eventLink` 重新命名為 `renderEventLink`，並改以函式呼叫 `{renderEventLink(e)}` 使用，不再寫成 JSX tag。

**教訓：** 詳細規則已寫入 `.github/skills/agents/engineer/SKILL.md` § TSX Component vs Helper。實作 admin / 後台多區塊頁面時，先把可重複使用的小區塊（header、link、badge）提到模組頂層，避免後續因 lint 補修。

> 註：本次事件最終隨 Tier 1 monitoring 撤銷一同 revert（commit `cf1e0a9`），但 lint 規則本身仍適用。

---
## 2026-05-01 — AEO 實作（Phase A/B/C partial）：llms.txt、IndexNow、Aggregation Pages、監控 Dashboard

**背景：** 為提升 AI 搜尋引擎可見度（Perplexity、ChatGPT Search、Claude），實作 AEO（AI Engine Optimization）三階段：
- Phase A：AI crawler 開放、`llms.txt`、全域 JSON-LD
- Phase B：活動詳情頁 BreadcrumbList + FAQPage、sitemap x-default
- Phase C（partial）：AEO 監控（`aeo_visits` 表 + proxy.ts 偵測 + Admin Dashboard）+ IndexNow 提交 + 主題聚合頁（城市 × 6 + 分類 × 所有）

**關鍵教訓：**

1. **proxy.ts 靜態文件 307 問題**：任何新增到 `web/public/` 的靜態文件（如 `llms.txt`、`93bf67...txt`），必須同步更新 `proxy.ts` matcher 排除 regex，否則 i18n middleware 307 重導至 `/zh/<filename>`。

2. **FAQPage 必須有可見內容**：Google 要求 FAQPage 內容必須在頁面上可見，JSON-LD 本身不夠。必須同時添加 `<dl>` visible section 與 JSON-LD，缺一不可。

3. **Migration 號碼衝突處理**：若兩個 migration 分配到相同號碼，採用 `b` 後綴（如 `029b_realtime_events.sql`），並在 SQL 檔案頂部加 comment 說明衝突原因。

4. **TSX 禁止 CJK 硬編碼**：城市描述、分類描述等所有中文/日文文字必須走 `t()` hook 從 `messages/*.json` 讀取，絕不硬編碼在 `.tsx`。靜態分析不會報錯，但翻譯缺失時頁面會顯示 raw key。

5. **getTranslations namespace 靜默失敗**：使用 `tXxx("key")` 前必須確認 `messages/zh.json` 中對應 namespace 存在。Namespace 不存在時 `t()` 靜默返回 raw key string，不拋錯，難以發現。

6. **IndexNow 需兩個環境變數**：`INDEXNOW_KEY`（API key）和 `NEXT_PUBLIC_SITE_URL`（用於建構 event URL）。兩者都需加入 `.github/workflows/scraper.yml` 的 env 區塊。`upsert_events()` 改為返回 `list[str]`（新活動 UUID 列表）供 IndexNow 使用，原有呼叫方只需更新 unpack。

7. **Aggregation page i18n 命名**：城市頁用 `cities.*` namespace，分類頁用 `categoryDesc.*` namespace。必須同時更新三個 messages 文件，否則非 zh locale 的頁面顯示 raw key。

**新增文件：**
- `web/public/llms.txt` — AI engine index
- `web/app/robots.ts` — 9 個 AI crawler 規則（GPTBot, OAI-SearchBot, Anthropic-ai, Claude-Web, PerplexityBot, Google-Extended, cohere-ai, Meta-ExternalAgent, YouBot）
- `web/app/layout.tsx` — 全域 JSON-LD @graph (WebSite + SearchAction + Organization)
- `web/app/[locale]/events/[id]/page.tsx` — BreadcrumbList + FAQPage JSON-LD + 可見 `<dl>` FAQ section
- `web/app/sitemap.ts` — x-default alternates + 城市/分類頁（priority 0.7, daily）
- `supabase/migrations/029_aeo_visits.sql` — bot/ai_referral 追蹤表
- `web/proxy.ts` — BOT_PATTERNS（17）+ AI_REFERER_HOSTS（10）+ fire-and-forget logAeoVisit()
- `web/app/[locale]/admin/aeo/page.tsx` — Admin AEO Dashboard（6 summary cards + bot/AI referral tables）
- `web/public/93bf676318c36c2420ea9af290aa15a65efab2134bee2caf6f29037b06b4d9b9.txt` — IndexNow key 驗證文件
- `scraper/indexnow.py` — submit_urls(), event_urls()
- `web/app/[locale]/cities/[city]/page.tsx` — 6 城市 × 3 locales，CollectionPage + ItemList JSON-LD
- `web/app/[locale]/categories/[category]/page.tsx` — 所有分類 × 3 locales，CollectionPage + ItemList JSON-LD

---
## 2026-05-01 — AEO proxy.ts Edge Middleware 規則固化（daily review）
**新增/修改：**
- 新增 `## AEO Monitoring — proxy.ts Edge Middleware Rules` 段落
- Fire-and-forget logging rule：不能 `await`/`throw`，用 `void fetch()` + 原生 Web API
- Bot / AI referral 雙層偵測模式（BOT_PATTERNS + AI_REFERER_HOSTS，UA 優先）
- 靜態文件排除規則：`public/` 新文件必須同步加入 matcher regex
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — agent 將非遷移文件誤置 migrations/ 目錄（daily review）
**新增/修改：**
- `## Database` 段落新增 `supabase/migrations/` 只能放 `NNN_name.sql` 的明文規定
- 記錄事故案例：`027_smoke_test.sql`、`027_VALIDATION.md`、`027_VERIFICATION_REPORT.md` 被 agent 誤建於 `migrations/`
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — AdminReportsTable Realtime 自動刷新修復

**問題**：報錯審核頁面前端有 `supabase.channel().on("postgres_changes", ...).subscribe()` 訂閱，但 INSERT/UPDATE 事件從未觸發，頁面不會自動刷新。

**根本原因**：`event_reports` 資料表從未加入 `supabase_realtime` publication。Supabase Realtime 需在資料庫層先執行 `ALTER PUBLICATION supabase_realtime ADD TABLE <table_name>` 才會廣播變更；前端訂閱程式碼本身不夠。

**修復**：
1. 新建 `028_realtime_event_reports.sql`：`ALTER PUBLICATION supabase_realtime ADD TABLE event_reports;`
2. 前端訂閱改為同時處理 INSERT（新報錯）和 UPDATE（確認/忽略），跨標籤頁即時同步。
3. 抽取 `fetchRow()` helper 避免 SELECT 子句重複。

**教訓**：
- Supabase Realtime 不是「開箱即用」：前端 `.on("postgres_changes", ...)` 不夠，資料庫層必須先 `ALTER PUBLICATION supabase_realtime ADD TABLE <table>` 才有效。
- 管理頁面須同時訂閱 INSERT + UPDATE，才能跨標籤頁同步確認/忽略狀態。
- 診斷方式：Supabase Dashboard → Database → Replication，確認目標表出現在 `supabase_realtime` publication 清單中。

*(補充：2026-04-30 的「AdminReportsTable Realtime subscription」條目教訓不完整，缺少「必須先 ALTER PUBLICATION」這個關鍵步驟。)*

---
## 2026-04-30 — AdminReportsTable 多選批量確認功能

**新功能**：待審核列表支援多選批量通過操作。`selectedIds: Set<string>` + `bulkConfirming: boolean` state；`handleBulkConfirm` 以 sequential `await for` loop 逐筆呼叫現有 `handleConfirm`，完成後清空 `selectedIds`。Section header 加 bulk action bar（flex justify-between），有勾選時顯示「通過已選取 (n)」和「取消選取」按鈕。

**關鍵技術決策**：
- `handleBulkConfirm` 用 sequential loop（不是 `Promise.all`），因為 `handleConfirm` 內部有 `setSaving` state 更新，parallel 會造成 state race。
- checkbox label 用 `onClick={(e) => e.stopPropagation()}` 防止冒泡觸發行展開/收合。
- 原本 `<button className="w-full ...">` 必須重構成 `<div className="flex items-stretch"> + checkbox label + <button className="flex-1 ...">`，因為 checkbox 不可作為 button 的子元素（違反 HTML 規範）。

**教訓**：
1. 在列表行加入 checkbox 時，若整行原本是 `<button>`，必須拆成外層 `<div>` + checkbox label + `<button flex-1>`；不能把 checkbox 放在 button 內。
2. 批量操作按鈕建議放在 section header 右側（flex justify-between），比底部 footer bar 更直覺。
3. 若 bulk handler 呼叫的子函數內部有 `setSaving` state 更新，必須用 sequential loop，不可用 `Promise.all`。

---
## 2026-04-30 — AEO 優化（Phase A + B）：proxy.ts 靜態文件排除規則

**錯誤**：新增 `web/public/llms.txt` 後，`/robots.txt`、`/sitemap.xml`、`/llms.txt` 請求被 i18n middleware 307 重導向至 `/zh/robots.txt` 等路徑，回傳 404。

**原因**：`proxy.ts` middleware matcher 缺少 `robots.txt`、`sitemap.xml`、`llms.txt` 的排除規則。Next.js i18n middleware 預設對所有未排除路徑加上 locale 前綴，不區分靜態文件與動態路由。

**修復**：在 `proxy.ts` matcher 排除正規表示式中補上 `robots\\.txt`、`sitemap\\.xml`、`llms\\.txt` 等靜態文件模式。

**教訓**：任何新增到 `web/public/` 的靜態文件，必須同步在 `proxy.ts` matcher 中加入排除規則，否則 i18n middleware 會 307 重導所有請求到 locale 前綴路徑（如 `/zh/llms.txt`）。

---
## 2026-04-30 — Satori emoji 靜默失敗導致 OG image 空白

**錯誤**：`opengraph-image.tsx` 回傳 HTTP 200 + `content-type: image/png` 但 `content-length: 0`。

**原因**：Satori（`ImageResponse` 底層）完全不支援任何 emoji，包括 📅📍🇹🇼🏳️‍🌈。遇到 emoji 時靜默失敗，不拋錯，直接回傳空 PNG。

**修復**：兩輪修改——第一輪移除 CATEGORY_EMOJI map 和品牌 🇹🇼，第二輪用 Python 掃 `ord(c)>127` 找到殘留的 📅📍，全部換成純 ASCII 文字標籤（DATE/AT/FILM/ART 等）。

**教訓**：Satori OG image 中完全不能使用任何 emoji。診斷方法：`fetch(...).arrayBuffer()` 檢查 `byteLength`，0 = Satori 靜默失敗。搜尋殘留：`python3 -c "..."` 掃 `ord(c)>127`。

---
## 2026-04-30 — AdminReportsTable Realtime subscription

**新功能**：報錯審核頁面新增 Supabase Realtime subscription，訂閱 `event_reports` INSERT 事件。有新報錯時自動 fetch 完整資料（含 events join）並插入列表頂部，無需手動刷新。

**教訓**：Supabase Realtime 在 `"use client"` 元件中使用 `supabase.channel(...).on("postgres_changes", ...)` 即可，記得 `useEffect` cleanup 時呼叫 `supabase.removeChannel(channel)`。

---
## 2026-04-29 — AdminReportsTable: description 欄位缺少可編輯支援 [AdminReportsTable]

**Bug:** `description` 欄位未加入 `EDITABLE_FIELDS`，也未宣告 `TEXTAREA_FIELDS` 集合，導致問題回報審核時無法直接修改事件描述。

**Fix (4a40b9a):** 將 `description` 加入 `EDITABLE_FIELDS` Set；新增 `TEXTAREA_FIELDS` Set（含 `description`），讓 description 渲染為 `<textarea rows={3} className="resize-y ...">` 而非 `<input>`。

**Lesson:** `AdminReportsTable.tsx` 有兩個控制欄位編輯行為的 Set：`EDITABLE_FIELDS`（可編輯）和 `TEXTAREA_FIELDS`（長文字，用 textarea）。新增可編輯欄位時：加入 `EDITABLE_FIELDS`；若為長文字，**同時**加入 `TEXTAREA_FIELDS`。

---
## 2026-04-29 — AdminEventTable 日期範圍篩選器無法搜索未來活動 [AdminEventTable]

**Bug:** `filterTimeMode === "past"` 分支在 `getFiltered` 和 `sourceCountMap` 兩處都有 `isPast` 判斷（`end_date < today`），導致「搜尋特定期間」無法找到 end_date 在未來的活動。

**根本原因：** 日期範圍篩選邏輯把「過去期間」和「任意日期範圍」混在一起；且 `getFiltered` 和 `sourceCountMap` 邏輯不同步。

**Fix (7f00d4e):** 移除兩處的 `isPast` 限制，改為純粹的 from/to 日期邊界篩選；同時重命名 i18n 標籤為「搜尋特定期間」。

**Lesson:** 日期範圍篩選器的 from/to 應為純粹的日期邊界，不應附加「只搜過去」的語意。修改 `AdminEventTable` 篩選邏輯時，`getFiltered` 和 `sourceCountMap` **必須同時更新**。

---
## 2026-04-29 — AdminSourcesTable: `eventCountByType` and `typeCountMap` not applying status filter [AdminSourcesTable]

**Bug:** `typeCountMap` was added (commit `6b92c53`) with the status filter applied, but `eventCountByType` (a sibling IIFE computing active event counts per type) was NOT updated to apply the same filter. When users selected the `不適合` (not-viable) status, `typeCountMap` correctly showed 0 for all types, but `eventCountByType` still showed stale counts from all sources regardless of status — making the dropdown misleading.

Separately, `candidate`, `researched`, and `recommended` status values were added to the status `<select>` (commit `618f93a`) but the `getFilteredSources` filter logic only handled `implemented`, `not-viable`, and `has_issue`. The new status values had no guard, so selecting them showed all sources unfiltered.

**Fix (c52c737):** Extracted an identical `statusFiltered` array into `eventCountByType` (same guard logic as in `typeCountMap`). Also added explicit `candidate / researched / recommended` guards to both the `typeCountMap` status filter and the `getFilteredSources` IIFE.

**Lesson:** When two parallel IIFE/`useMemo` blocks compute counts for related UI dimensions (e.g. one counts sources-per-type, another counts events-per-type), they must apply the **identical** status-filter logic. Whenever a new filter option is added to `getFilteredSources`, grep for all sibling count computations and apply the same guard. Treat status filter guards as a **closed set** — adding `candidate` to one block requires adding it to ALL blocks in the same file that filter by status.

---
## 2026-04-29 — AdminSourcesTable 來源分類 select 顯示各分類條目數

**工作內容：**
- `AdminSourcesTable.tsx` 的「來源分類」select 每個 option 改為顯示 `{label} ({count})` 格式
- 新增 `typeCountMap` IIFE：套用狀態篩選（`filter`）但**不套用**分類篩選，計算每個分類的條目數
- `"all"` 選項不顯示數字；count 為 0 時也不顯示括號
- 邏輯與 `getFilteredSources` 中的 `peatix_organizer` / `effectiveTypeMap` 判斷保持一致

**教訓：**
- Filter dropdown 的各選項計數，應套用**其他**篩選條件（此處是狀態），但排除**自身**篩選條件（分類），才能讓使用者看到切換後的預期數量
- `"all"` 選項語意上是 total，不適合顯示數字（旁邊已有 `{filtered.length} 筆`）
- count 為 0 時不顯示括號，避免 UI 噪訊

---
## 2026-04-29 — Peatix Layer 3 擴充：新 agent_category 需同步 AdminSourcesTable

**工作內容：**
- `peatix.py` 加入 `_load_db_organizers()`、`_scrape_group_events()`，`scrape()` 加入 DB organizer 迴圈
- `discovery_accounts.py` 完整重寫為 4 槽每日輪流（slot 0-2=note.com，slot 3=Peatix 主辦者）

**教訓：**
- 每次新增 `agent_category` 到 DB（如 `peatix_organizer`）時，**同一 PR 必須**更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯，否則管理界面無法篩選新類型
- `discovery_accounts.py` 的 platform-aware upsert 依賴 `agent_category` 欄位作為路由機制：Peatix → `peatix_organizer`，note.com → `note_creator`
- 驗證入口：`python discovery_accounts.py --dry-run --slot 3`

---
## 2026-04-29 — AdminSourcesTable 分類對照表編輯器（localStorage 覆蓋層）

**新增功能：**
1. `SOURCE_TYPE_LABELS` 加入「📦 歸檔」選項（key: `"archived"`）
2. `typeOverrides` state，初始值從 `localStorage` 讀取（key: `source_type_overrides`）
3. `getFilteredSources` 改用 `effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }` — 使用者覆蓋優先
4. 新增 Modal：搜尋框、所有來源依分類→名稱排序、分類下拉、被覆蓋列綠色標示 + 「↩」還原、「儲存」/「取消」
5. 移除 `sources/page.tsx` 冗餘 `<h2>` 標題

**教訓：**
- 硬寫 ID→分類對照表需配合 localStorage 覆蓋層（`effectiveTypeMap = { ...defaultMap, ...userOverrides }`），讓管理者無需改程式碼即可重新分類
- Modal 必須區分 draft state（`draftOverrides`）與 committed state（`typeOverrides`）：取消不影響已儲存狀態
- `localStorage` key 慣例：`source_type_overrides`（snake_case，明確表示功能範圍）

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---

## 2026-04-29 — skills/engineer/ 反覆復活（stray dir）

**問題：** 子代理更新 engineer SKILL.md 時寫入 `.github/skills/engineer/SKILL.md`（舊路徑），而非 `.github/skills/agents/engineer/SKILL.md`（正確路徑）。同一 session 發生兩次。

**修復：** SKILL.md 頂部新增 `## ⚠️ CRITICAL: Canonical File Paths`，列出所有 agent 正確路徑。

**教訓：** 路徑遷移必須在 SKILL.md **頂部第一章節**加 CRITICAL 警告，否則子代理讀不到就走舊路徑。

---
## 2026-04-29 — AdminSourcesTable 分類對照表編輯器（localStorage 覆蓋層）

**新增功能：**
1. `SOURCE_TYPE_LABELS` 加入「📦 歸檔」選項（key: `"archived"`）
2. `typeOverrides` state，初始值從 `localStorage` 讀取（key: `source_type_overrides`）
3. `getFilteredSources` 改用 `effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }` — 使用者覆蓋優先
4. 新增 Modal：搜尋框、所有來源依分類→名稱排序、分類下拉、被覆蓋列綠色標示 + 「↩」還原、「儲存」/「取消」
5. 移除 `sources/page.tsx` 冗餘 `<h2>` 標題

**教訓：**
- 硬寫 ID→分類對照表需配合 localStorage 覆蓋層（`effectiveTypeMap = { ...defaultMap, ...userOverrides }`），讓管理者無需改程式碼即可重新分類
- Modal 必須區分 draft state（`draftOverrides`）與 committed state（`typeOverrides`）：取消不影響已儲存狀態
- `localStorage` key 慣例：`source_type_overrides`（snake_case，明確表示功能範圍）

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 - GitHub Actions resolver could not fetch actions/checkout@v4

**Error:** `.github/workflows/secret-rotation-reminder.yml` failed at parse/resolve stage with `Unable to resolve action actions/checkout@v4, repository or version not found`.

**Fix:** Downgraded action refs in the same workflow to resolver-friendly majors for older environments:
- `actions/checkout@v4` -> `actions/checkout@v3`
- `actions/setup-python@v5` -> `actions/setup-python@v4`

**Lesson:** If a workflow must run on older GitHub Enterprise resolvers or constrained action mirrors, prefer the latest major that is known to exist in that environment, and downgrade related core actions together to keep compatibility expectations consistent.

---
## 2026-04-28 — Multi-locale field editing: always expose all locale variants simultaneously

**Context:** `ReportSection.tsx` initially showed a single textarea pre-filled with the *current locale's* value when a user flagged a wrong field. A user pointed out that the Japanese original may be correct while only the Chinese or English translation is wrong. Showing one locale obscures which specific translation is faulty.

**Upgrade:** Changed the textarea to three stacked labeled textareas (中文 / English / 日本語), each pre-filled with the field's own locale column value. Users edit only the incorrect locale(s) and leave others unchanged.

**Type change:**
```ts
// Before
eventFields?: Partial<Record<WrongDetailField, string | null>>;
fieldEdits:   Partial<Record<WrongDetailField, string>>;

// After
eventFields?: Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string | null>>>>;
fieldEdits:   Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string>>>>;
```

**Submission format:** `fieldEdit:<field>:<locale>:<value>` — only non-empty edits are appended to `report_types`.

**Lesson:** When a UI component edits a field that maps to localized DB columns (`*_ja`, `*_zh`, `*_en`), **never show only the current locale's value**. Show all locale variants with language labels. This applies to any future correction/review UI (admin edit forms, report flows, feedback widgets). → Added to SKILL.md as **Multi-locale Edit Pattern**.

---
## 2026-04-28 — Report section: editable textarea per wrong-detail field

**Feature:** When a user checks a sub-field (name, date, venue, etc.) under "內容錯誤 / wrongDetails" in `ReportSection.tsx`, a textarea now appears pre-filled with the current localized event content. The user can edit the value before submitting; the edited text is stored as `fieldEdit:<field>:<value>` in `report_types` alongside the existing `field:<field>` entry.

**Implementation:**
- Added `eventFields?: Partial<Record<WrongDetailField, string | null>>` prop to `ReportSection`
- Added `fieldEdits: Partial<Record<WrongDetailField, string>>` state; populated on field checkbox toggle
- `toggleField()` now sets `fieldEdits[field] = eventFields?.[field] ?? ""` on check, and deletes the key on uncheck
- JSX: sub-field checkboxes moved from `<label>` wrappers to `<div>` with conditional textarea below each checkbox
- `handleSubmit` appends `fieldEdit:<field>:<value>` entries (max 500 chars each) when `edit.trim()` is non-empty
- `page.tsx`: passes `eventFields` using the locale-aware helpers `getEventName`, `getEventLocationName`, etc. already imported
- New i18n key `fieldEditHint` added to all three `messages/*.json` files

**Pattern replicated from:** `wrongSelectionReason` textarea — same pre-fill + clear-on-uncheck pattern.

**Lesson:** When reusing a textarea-on-checkbox pattern, extract the pre-fill logic into `toggle<X>()` so the JSX stays declarative. Avoid inline `onChange` that mutates state outside the toggle handler.

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.
