# Engineer Error History

<!-- Append new entries at the top -->

--- 

## 2026-06-28 — weekly_line_broadcast 近期活動改「全國分類置頂＋都道府縣分組」+ 地區比對改 substring

**Context**: round-2 週報升級。`_build_message()` 的「今週・来週の全イベント」段從舊的「依 type 分組（活動/電影/書籍/線上/電視）」重構為**全國級分類置頂 + 都道府縣分組**，並把地址比對從 `startswith` 放寬為 `substring`。working tree 重構（待 commit），edge-case 測試 TEST3/4a/4b/4c 全 PASS。

**Fix（`scraper/weekly_line_broadcast.py`）**:
1. **近期活動雙層結構**：(a) 全國級類別（books/online/TV，無地域屬性）置頂為獨立 section，順序固定 **書籍 → 線上 → 電視**；(b) 其餘（regular + film 合併）依 `_city_label` 都道府縣**扁平分組、日期排序**，移除舊的「活動/電影」type subheader 與 film venue label。未知地區（地域未設定/未標註地區/Unspecified Region）固定排最後。
2. **edge-case 防護**：空的全國 section 不洩漏 header；無地域活動時不產生 orphan「地域未設定」；空 nearterm list 不洩漏主 header；section/region 間僅單空行（禁止 `\n\n\n` 雙空行）。
3. **`_is_online_event()` 新 helper**：線上偵測從 `location_name == "オンライン"`（精確）放寬為 location_name **或** location_address 含 `オンライン/online/virtual`（任一 token、大小寫不敏感）。
4. **`_city_label()` 比對 `startswith` → `substring`**：都道府縣／東京／台灣前綴改 `pref in addr`（match anywhere），新增 `_TOKYO_EN_HINTS=("tokyo",)` 認英文地址；補 `栃木/栃木県` 到 `_PREF_LABEL`。
5. **標題文案統一**：`_build_message()` 與 `run_generate_draft()` 兩處標題之前不一致（`今週のレーダー` vs `週間巡回`），統一為 **検知速報 / 偵測快報 / Detection Bulletin**。

**Lesson**:
- **公開輸出的分組模型要區分「全國級 vs 地域級」**：books/online/TV 無實體地點，硬塞地區分組會產生 orphan「地域未設定」；正解是把無地域類別抽成置頂 section，地域類別才走都道府縣分組。
- **分組顯示必測四種 edge case**：空全國段、空地域段、orphan unknown-region、空清單——每種都可能洩漏空 header 或產生雙空行。改 `_build_message()` 後務必跑 TEST3/4a/4b/4c 等價檢查。
- **`startswith` → `substring` 是刻意放寬**：venue-name-as-address（`会場は東京都…`、非開頭前綴）用 startswith 會漏判地區；改 substring 後 match anywhere。trade-off 是理論上可能誤判含他地名的地址，但週報情境 recall 優先於 precision。
- **同一訊息標題若由兩個 code path 產生（`_build_message` + `run_generate_draft`），改文案要兩處同步**，否則 preview 與實際送出標題不一致。

---

## 2026-06-28 — Security Hardening Round 1：注入防護 + 安全報告型別 + 三層密鑰掃描

**Context**: Security Hardening Plan v16 Round 1。把「不可信事件內容」當攻擊面，一次落地四道 guard（Phase 0/1 已 commit `a81f61f` scraper / `bd8f7d0` web；Phase 3/4/4b 本批 hooks + CI + docs）。

**Fix（四道 guard）**:
1. **Prompt injection guard（scraper）**：`security.injection_guard` 掃 raw_title/raw_desc，GPT 輸入以 `<UNTRUSTED_EVENT_DATA>` 包裹（`build_event_user_content`，production 與 `eval_annotator` 共用同一 helper）；sev>=2 寫 `event_reports`。掛點必須在**截斷後 payload**（與 GPT 實際看到的 20000-cutoff 一致），否則掃到 GPT 看不到的片段 → 假告警。
2. **安全報告型別 lifecycle**：`auto_security_prompt_injection` + `securityHash:<sha1>` + `securitySeverity:<n>` 寫 `event_reports`；dedup 從 `report_types[]` 解析 hash（非僅查 pending），confirm/dismiss 皆寫 `confirmed_at` 當 handled_at；`updated_at > handled_at` 或 hash 變更才重開 pending。
3. **新 report type 的 admin UI 同步（四面）**：`web/lib/reportTypes.ts`（shared predicate，client + server 共用一份，deny-by-default allowlist）、`AdminReportsTable`（隱藏 payload token、label + Confirm-only 行為）、confirm/dismiss-report server action、三語 `messages` 的 `report` namespace。payload token（`securityHash:`/`securitySeverity:`/`fieldEdit:`/`selectionReason:`）一律不顯示、不寫 SKILL pending rule。
4. **三層密鑰掃描（fail-open）**：Layer 1 pre-commit `gitleaks git --staged`（缺 binary → 警告 + `exit 0`）、Layer 2 pre-push gitleaks 掃 range（無 gitleaks → regex fallback，**必含 placeholder allowlist**）、Layer 3 CI `secret-scan.yml`（version-pinned + checksum-verified gitleaks binary，`permissions: contents: read`）。

**Lesson**:
- **不可信內容掃描掛點 = GPT 實際 payload**（截斷後），不是原始 raw_description；否則 cutoff 後片段會產生 GPT 看不到的假告警。
- **shell regex fallback 不讀 `.gitleaks.toml`**：任何「regex 補掃」都要自帶與 `.gitleaks.toml` 同語意的 placeholder allowlist，否則無 gitleaks 的開發者推 token docs 被假陽性逼 `--no-verify`，反削弱 gate。三份 allowlist（`.gitleaks.toml` / pre-push fallback / Hygiene git grep）改一處要三處同步。
- **三層皆 fail-open / 可 `--no-verify` 繞過**，非 non-bypassable；真正強制需 server-side branch protection（本 repo 未採用）。文件不可宣稱任一層 fail-closed。
- **Public Repo Secret Hygiene**：掃 git-tracked 一律用 `gitleaks git --redact -c .gitleaks.toml`（allowlist-aware + redacted）；**禁止 repo-root `grep -rn`**——會讀進被 .gitignore 忽略的 `scraper/.env`，把真 PAT 印到 terminal / CI log。token docs 的存在性檢查改 masked awk（length/prefix），不印 token 值。

---

## 2026-06-28 — researcher 每日研究重複回報已知來源（dedup 粒度三處不一致）

**Error**: `researcher.py` 每日研究持續用 LINE 回報已知來源（屋台湾フェス / 台湾文化祭 prtimes / シネマート），白費 `gpt-4o-search-preview` 費用與通知噪音。實測最近 40 份報告 → 23 個回報來源 100% 落在已知 domain 上。

**Root cause（dedup 粒度不一致）**: 同一「已知來源」概念在三處判定，比對粒度不一：(1) GPT `block_domains` 用 domain，但**只篩 `implemented/researched/not-viable`**，漏掉 `candidate/recommended`；(2) LINE report filter 用 **exact-URL**（`s.get("url") not in known_urls`）→ 已知 domain 的新路徑（iwafu 不同活動頁、prtimes 不同新聞稿）漏網被當新來源；(3) 無 URL 正規化，`www`/scheme/trailing-slash 變體繞過 exact-dedup（249 筆帶 `www.`）；(4) prtimes 等新聞稿每篇 URL 都不同，exact-dedup 永遠擋不住。

**Fix**（`scraper/researcher.py`，d7e6e02）:
1. `_normalize_url()`：lowercase host + strip `www.` + drop scheme/query/fragment + strip trailing slash → 正規化後 exact-dedup（新增 `known_norm_urls` set）。
2. `block_domains` 擴及**所有已知狀態**（`{_domain(url) for url in self.known_urls if _domain(url)}`），不再篩狀態。
3. LINE report filter 改 **domain + normalized-URL 雙重比對**：`_domain(url) not in known_domains and _normalize_url(url) not in known_norm_urls` → 只有全新 domain 存活。
4. `_ARTICLE_URL_RE`（`prtimes rd/p`、`/article/news/`、`/news/\d`、長數字 `.html`）在 Playwright 驗證前丟棄 article URL；GPT prompt 明示「只回 LISTING/INDEX 頁」。

**Lesson**:
- **dedup 粒度三處必須一致**：同一「已知來源」在 GPT block list / DB upsert skip / LINE report filter 三處判定，任一處用較鬆粒度（exact-URL）就漏網。根因正是「擋了 GPT、卻用 exact-URL 放行 LINE」。改去重一律三處同步檢查粒度。
- **dedup ≠ 省費用**：`gpt-4o-search-preview` 在 call 當下就真去搜網路並計費；dedup 只減 LINE 噪音與 DB 污染，**不降 API 費用**。要省費用得減 call 頻率／數量。
- **news-release 平台（prtimes…）每篇 URL 都新**：exact-URL dedup 永遠擋不住，必須在來源層攔截（domain block + article-URL pattern + 要求 GPT 只回 listing 頁）。
- **exact-dedup 前必先正規化 URL**（www/scheme/trailing-slash），否則同頁變體放行。

---

## 2026-06-22 — `_SIMP_TO_TRAD` 缺 `当`/`写`/`圆`（G2 batch annotation post-QA gap）

**Error**: G2 backlog 標注後，2 筆 hanmoto publication 的 `description_zh` 殘留簡體 `当`（auto_qa `SIMP_RE` 會旗標但 `_to_trad()` 沒轉，因為 `当` 不在 `annotator._SIMP_TO_TRAD_RAW`）。修 `当` 後依規範跑全庫 full-`SIMP_RE` 掃描，又發現同類缺字 `写`、`圆`，其中一筆 `当` 修補後的 row 仍殘留 `写`。

**Fix**:
1. `scraper/annotator.py`：`_SIMP_TO_TRAD_RAW` 補 `当→當`、`写→寫`、`圆→圓`（三者皆已在 `auto_qa.SIMP_RE`，one-to-one 無姓氏歧義）。`auto_qa.SIMP_RE` 已含，免動。
2. DB 定向單字 replace 修補受影響 rows（`当` 15 筆、`写`/`圆` 9 筆），皆 `annotated`（0 reviewed），全程 `assert status!='reviewed'`。root-cause 已修，re-annotation 會重現正確值 → 免 FC lock。
3. 全庫 re-scan 確認 `当`/`写`/`圆` 殘留 = 0。剩 7 筆 `is_active=False` stale residue（字已在 map，舊 row 未重跑；含 `范`/`钟` 一對多姓氏歧義）→ 不 bulk patch，留給 qa_heartbeat→admin 人工 confirm。

**Lesson**: 改 char map 後**必跑全庫 full-`SIMP_RE` 掃描**（mode Step 3 #7）——單字修補會漏同 row 的 sibling 缺字。只把「SIMP_RE 有、map 沒、且 one-to-one 安全」的缺字加進 `_SIMP_TO_TRAD`；一對多歧義字（`范`→範/范姓、`钟`→鐘/鍾姓）**禁止**自動轉，必須走 admin review。已 mapped 的 stale residue 屬 qa_heartbeat 範疇，非單次 backlog 任務該 bulk patch，尤其 inactive row。

---

## 2026-06-16 — `_REPORT_TRIGGER_RE` 寬泛 `記録` 改 composite terms（大濛首頁修復 follow-up）

**Error**: 大濛（霧のごとく） 8 筆真實上映場次卡在首頁不顯示。根因是 annotator 的 `report` keyword 假陽性：寬泛 `記録` 命中票房文案「記録を更新中」，注入 `report` 分類並污染 stranger `name_ja` 為 `【レポート】霧のごとく`。

**Fix**:
1. `scraper/annotator.py`：`_REPORT_TRIGGER_RE` 的單獨 `記録` → `活動記録|開催記録|鑑賞記録|記録[｜|]`；SYSTEM_PROMPT report/recap 例外同步。
2. 8 筆 `annotator.py --event-ids` re-annotate（不加 `--all`/`--force-fc-override`）。
3. stranger `name_ja` cleanup（`霧のごとく`）+ `_lock_fields_via_corrections` FC lock + 即時 FC row 驗證。

**Lesson**: report 觸發詞必須是 composite/有界詞。修 `_REPORT_TRIGGER_RE` 一律連帶同步 SYSTEM_PROMPT report/recap 例外（regex 防新污染、prompt 防 GPT 漂移）。舊污染的 `name_ja` 不會被 re-annotation 自動清除（`name_ja` policy 保留 DB 既有值），必須手動 cleanup + FC lock。本條 supersede 2026-05-11 report injection 的寬泛 `記録` 行為。

---

## 2026-06-13 - Design preview mobile frame caused 390px horizontal overflow

**Error**: The design preview used a fixed `width: 390px` mobile frame inside a padded page. At a
390px viewport, the frame plus page padding pushed document `scrollWidth` to 422px even though the
preview was meant to represent that exact device width.

**Fix**: Changed the preview shell to `w-full max-w-[390px]` so the frame preserves the target size on
wide screens and shrinks inside narrow padded containers.

**Lesson**: Fixed-width device preview frames must be capped with responsive constraints. For mobile
smoke checks, assert `documentElement.scrollWidth <= clientWidth` and distinguish real page overflow
from intentional horizontal scroll regions.

---

## 2026-06-08 — Safari CJK centering: scoped opt-in vs global hack

**Error**: `globals.css` accumulated a global `@supports(-webkit-hyphens:none) { button { !important } }`
that hit every interactive control site-wide, plus 3 counter-exceptions. Each new control needed
another exception → whack-a-mole for ~20 commits.

**Fix**: Replaced broad selector with single opt-in `.ttr-cjk-center` class. Per-control geometry
(`inline-flex items-center min-h-* leading-none + inner span`) is the durable fix.

**Lesson**: Never use a global `button { !important }` rule. Verify the centering hypothesis on real
Safari FIRST (see `web/public/_uitest.html`), then apply any nudge as a scoped per-control class only.

---
## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 

--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 

---

## 2026-06-07 - auto_qa reconcile: 批次掃描器只新增、從不關閉導致 436 筆 pending 長期累積

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-07 | `/admin/reports` 佇列積累 436 筆 pending 報告（涵蓋 314 事件）。事件問題早已修復但報告未關閉（stale），或事件已停用（inactive），或 `annotation_status=reviewed`（reviewed），但每日 `auto_qa.py run()` 只 insert 新報告、從不 close 已解決的 | `run()` 的 dedup 機制只跳過「已有 pending 報告」的事件——這正確防止了重複新建，但同時意味著已解決的問題永遠不會被自動關閉。SC→TC 修正與 performer 分割都是 `qa_auto_fix.py` 負責，但該腳本不定期跑，因此修正後的 stale 報告繼續留在佇列 | Phase 1：從 7 個 `_detect_*` 函式中抽出純判定函式 `_check_*(ev)` → 無時間窗口、保留語意 skip；Phase 2：實作 `reconcile(dry_run)` — 載入所有 pending auto_qa 報告，重新對每筆事件執行對應 predicate，`inactive→dismissed` / `reviewed/resolved→confirmed` / predicate 仍觸發→kept；人工型永不碰；Phase 3：一次性清理（SC fix 0 件、performer split 14 件 ok、reconcile live 79 confirmed + 50 dismissed）；Phase 4：`scraper.yml` 加 `--reconcile` 步驟（在 auto-qa scan 前每日自動跑）。最終 436 → 293 pending（−143 件），manual 11 筆全保留 | 任何只「新增 pending」的 QA scanner 都必須配備對應的「關閉已解決報告」機制（reconcile/close pass），否則佇列只會無限成長。reconcile 的 predicate 函式應與 scanner 完全解耦且無時間窗口——scanner 的時間窗口只是為了效能，不代表「超過 N 天就無問題」。

## 2026-06-05 - Publication backfill now prefers official product descriptions and prefixes publication titles with `[新刊出版]`

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | publication rows still showed generic placeholder copy even when the scraper had an `official_url`, and publication names did not make their book context obvious in the list/detail views | The existing backfill only trusted `raw_description` and source-specific NDL breadcrumbs. For book publishers like hanmoto, the real synopsis lives on the official product page, often as JSON-LD `description`, so the backfill never promoted it into `description_*`. Title handling also had no consistent publication prefix | Added a shared publication page extractor in `scraper/annotator.py` that prefers `official_url` and parses JSON-LD `description` before falling back to `source_url` or `raw_description`. Mirrored the same logic in `_oneoff_backfill_publication_metadata.py`, and prefixed all publication names with `[新刊出版]` while switching NDL periodical rows to bracketed labels like `[期刊專文]` | For publication corpora, the authoritative synopsis is often on the publisher's product page, not the aggregator row. When `official_url` exists, treat it as the first-class source for description rewriting, and make publication titles visibly identifiable in the UI so they do not read like generic event rows.

## 2026-06-05 - Create-page annotate overwrite 必須同時有 source confidence 與 auto-filled provenance

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | owner/admin 新建活動頁的 annotate 對 location 欄位要嘛永遠 fill-only、無法升級 OCR 弱值，要嘛在 route 端只靠 `lockedFields`，共享 route 一旦被沒有 provenance 的呼叫點使用，就有機會把人工值當成可覆寫值 | overwrite 規則只做了一半：`bestScore` gate 與 shared sanitize 已在部分 route 落地，但 create client 沒有把「哪些欄位是 OCR auto-filled、哪些欄位已被手動編輯」送到 annotate route；admin create 另外還缺少 draft update path，annotate 後 save 會脫離既有 draft 流程 | 在 `web/lib/eventFieldMerge.ts` 補上 `overwriteableFields` gate，讓非空覆寫必須同時滿足 `bestScore >= 6`、欄位不在 `lockedFields`、且欄位存在於 `overwriteableFields`；owner/admin create client 追蹤 OCR 自動填入與手動編輯過的 location 欄位，annotate 時送出 `lockedFields` + `overwriteableFields`；admin create 再補 `updateAdminEvent()`，讓 annotate 後 save 更新既有 draft，而不是另插一筆新 event | 只在 route 端加 overwrite helper 還不夠。凡是 create/edit UI 允許「OCR 先填、annotate 再升級」的流程，都必須從 client 額外提供 provenance signal；沒有 provenance 時，shared annotate route 對非空欄位應預設回退成 fill-only，寧可保守也不要冒著覆寫人工值的風險。

## 2026-06-05 - Publication backfill needs source-scoped runs and NDL periodicals must become `期刊專文`

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | 想把所有 publication rows 一次補齊時，NDL OpenSearch 的期刊/雜誌條目仍停留在通路占位模板，標題也沒有顯示「期刊專文」前綴，導致單筆內容仍然模糊 | 來源分成兩類：一般出版條目與 NDL 期刊/雜誌條目。前者可維持共用 publication placeholder，後者必須額外抓頁面 breadcrumb 與出版者 metadata，並把名稱提升成 `期刊專文：...`；若把所有來源混在同一個粗批次裡，還會遇到 NDL 頁面抓取慢、apply 進度不穩的問題 | 將 `_oneoff_backfill_publication_metadata.py` 改成與 `annotator.py` 同步的共用 publication 規則，NDL periodical rows 以 breadcrumb 推出 `publication_label` 與 publisher organizer，再分來源執行：先確認 `hanmoto` 已全部被 FC 保護，再把 `ndl_opensearch` 單獨 apply 完 98 筆；回填後以單筆 NDL row 驗證 `name_ja/name_zh/name_en`、organizer、description 三語都落地 | 出版 backfill 不要把「一般出版」和「期刊專文」混在同一個粗批次思維裡。先分 source，再分內容型態；NDL 期刊類必須依頁面 metadata 升級為 `期刊專文`，並把出版者當作 organizer 回填，否則標題與來源語義永遠模糊。

---

## 2026-06-05 - Safari `<button>` 直接套 `flex` 導致高度比相鄰按鈕高（WebKit #169700）

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | Safari 登入頁 Google 按鈕比下方 Email 按鈕高一截，Chrome 正常 | Safari 的 WebKit 在 `<button>` 元素直接套 `display: flex`（Tailwind `flex items-center justify-center gap-3`）時，高度計算與 Chrome 不一致（WebKit bug #169700）；Chrome 無此問題所以本地開發沒被發現 | 把 `flex items-center justify-center gap-3` 從 `<button>` className 移到內層 `<span>`，讓 button 保持原生 block 高度；SVG icon 同步加 `shrink-0` 防壓縮 | 凡是在 `<button>` 上直接加 `flex` 的情況，都要在 Safari 實機或 Simulator 確認高度一致。修正方式：把 flex layout 包到內層 `<span>`，button 只保留 padding / border / background。

---

## 2026-06-05 - `goToMyEvents()` async DB 預檢讓 Navbar 點擊延遲並可能在 fetch 時段遮掉目的地

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | Navbar「自分のイベント」按鈕點擊後有明顯延遲，且 profile 查詢失敗時路由不確定 | `goToMyEvents()` 原本先 async 查 `creators` table 的 `user_handle`，再依結果路由到 `/account?tab=myEvents` 或 `/account/profile`；這個預檢把網路延遲引入 nav click，且 account page 本身就能處理「有沒有 profile」的路由邏輯 | 移除 async 預檢，直接 `router.push(\`/${locale}/account?tab=myEvents\`)`；讓 account page 決定是否重導到 profile 頁；同時移除 `profileLoading` state 與相關 loading 文字 | Nav action 不應做 DB pre-flight 來決定路由目的地。「先查再跳」= 把 DB 延遲嫁接到點擊回饋；應讓目的地 page 自行處理 conditional redirect，nav 只負責跳過去。

---

## 2026-06-05 - `account/annotate-event` 與 `admin/annotate-event` enum 過濾邏輯各自重複，location overwrite 無保護

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | 兩條 annotate route 各自內聯 `validCategories`、`validEventForms`、`VALID_PRIMARY_LANGUAGES` 過濾，容易各自演化成不同版本；account 路由在 web search score 低時也會把 LLM 猜的 `location_name`/`location_address` 蓋掉使用者填的正確值 | enum 過濾與 field merge 邏輯散落在兩個 route file，沒有 single source of truth；field overwrite 只用 `cur === null || cur === ""` 條件，不考慮 bestScore 或 lockedFields | 抽取 `web/lib/eventFieldMerge.ts`，集中 `sanitizeCategoryValues`、`sanitizeEventFormValues`、`sanitizePrimaryLanguageValue`；新增 `shouldApplyAnnotatedLocationField(field, cur, v, { bestScore, lockedFields })` 在 bestScore < 3 且欄位不在 lockedFields 時拒絕覆寫 | 兩個以上 route 做相同 LLM 輸出過濾時，第一時間就要抽 `lib/` 模組；location field merge 要同時考量「web search 品質（bestScore）」和「使用者鎖定（lockedFields）」，不可只靠 empty-check。

---

## 2026-06-05 - QA backlog 清理要走 `qa_heartbeat.py`，`qa_auto_fix.py` CLI 只處理兩個內建批次

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | 使用者看到後台還有約 150 筆 pending error，以為需要再推送程式碼；實際上真正需要的是跑資料庫 QA 清理，不是重新 deploy | `qa_auto_fix.py --dry-run` 只會跑簡轉繁與 tokyoartbeat date-sync，真正會派發 `auto_qa_location_url_is_event_url`、`auto_qa_performer_multi_value_pollution` 等 safe handler 的入口是 `qa_heartbeat.py`；若誤用前者，就會看錯 backlog 組成 | 先用 Supabase 查出 `event_reports.report_types` 與 `status` 分佈，再用 `qa_heartbeat.py --dry-run --limit 200` 驗證只會安全處理 18 筆；接著執行實跑，閉合 17 筆可逆修正（15 筆 performer 多值污染 + 2 筆 venue homepage 污染） | 資料庫清理不等於程式碼改動。先分清「偵測器 / 派發器 / CLI」三層入口，再決定要不要 push；若只是在 DB 裡把可逆的 QA 報告閉合，通常不需要 commit、push 或 redeploy。

---

## 2026-06-05 - 共用 `Button` 被 `px-0 py-0` 歸零導致點擊命中區只剩文字字形

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | `/[locale]/admin/events/new` 英文版的「← Back to list」按鈕看起來整顆按不到，只有文字本身偶爾有反應 | `AdminCreateClient.tsx` / `AdminEditClient.tsx` 的 back 按鈕用共用 `Button`（base `px-4 py-2`），卻用 `className="px-0 py-0"` 把 padding 完全歸零，命中區縮成只剩文字字形範圍；外層又是 `flex justify-between`，英文長標題（h1 無 `truncate`）會往左壓到這個零 padding 的小命中區，視覺上像整顆失效 | 移除 `px-0 py-0`，改用 `-ml-4` 抵銷左 padding 以維持原本左對齊外觀，恢復 `Button` 原生 `px-4 py-2` 命中區；並加 `shrink-0`、`relative z-10`，h1 加 `truncate` 防止長標題擠壓 | 覆寫共用 `Button` 的 padding 等同縮小可點區域。要視覺貼齊容器邊時，用負 margin 抵銷而非把 padding 歸零；對 `justify-between` 行內的相鄰文字一律加 `truncate` + `shrink-0`，避免長字串擠掉互動元素的命中區。

---

## 2026-06-05 - `/api/account/annotate-event` 三處靜默吞錯，前端永遠只看到泛用 `saveFailed`

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-05 | 使用者投稿頁「儲存並標注」反覆失敗多日，畫面只顯示「保存に失敗しました」，無法判斷真因 | `web/app/api/account/annotate-event/route.ts` 有三個靜默吞錯點：① OpenAI 回非 200 時 `if (openaiRes.ok)` 直接跳過；② GPT 回傳非合法 JSON 被空 `catch` 吞掉；③ 最終 `events` update 不檢查 error；三者最後一律回 `200 { success: true }`，前端 `OwnerCreateClient` 即使有 `t(res.error)` 也拿不到任何錯誤碼 | 後端改為：OpenAI 非 200 → `502 annotateAiFailed` 帶 `detail`；JSON parse 失敗且無任何欄位 → `502 annotateAiFailed`；DB update 失敗 → `500 annotateSaveFailed` 帶 db message。前端把 `detail` 接到錯誤訊息後綴，三語補上 `annotateAiFailed` / `annotateSaveFailed` | API route 的「成功」不能用「沒有 throw」定義。每個外部呼叫（LLM、DB write）都要顯式檢查 status / error 並回非 2xx + 可讀 `detail`，否則前端再怎麼 i18n 都只能顯示泛用訊息，真因被永久吞掉。

---

## 2026-06-04 - publication batch 不能只補模板欄位，`event_form` 與前台 label 也要同步收斂

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | publication sources 全量 re-annotation 後雖然 `annotation_status` 全回到 `annotated`、`name_zh` / `name_en` 補齊，但公開頁仍可能露出 raw key，且 corpus 內部分事件沒有被強制收斂到 `event_form=["publication"]` | 先前的出版 fallback 只保證 `location_name` / `location_address` / `business_hours` / `price_info` 模板欄位，不保證未受保護事件一定寫回 publication；同時前台顯示依賴 `web/lib/types.ts` 的 `EVENT_FORMS` 與 `web/messages/*.json` 的 `eventForm` namespace，任一漏同步都會讓前台顯示 `eventForm.publication` | 在 `scraper/annotator.py` 的 `_PUBLICATION_SOURCES` 分支對未受 human protection 的事件強制 `event_form=["publication"]`，同步補齊 web 端 `EVENT_FORMS` / i18n label，並以 live DB 統計確認 `ndl_opensearch` 186 筆、`hanmoto` 34 筆 active rows 全收斂到 `['publication']` | 出版來源 batch 的完成標準不能只看 status 或翻譯欄位，還要確認 target corpus 的 structural enum 已收斂，且 DB constraint、annotator、web enum、i18n label 四處同步；少一處，前台就會用 raw key 洩漏 drift。

## 2026-06-04 - Safari 互動元素文字偏高：shared pill refactor 暴露 browser baseline 差異

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | Chrome 正常、Safari 內首頁 CTA / 篩選器 / 排序膠囊 / shelf tab 文字整體偏高，看起來像整頁按鈕都被往上頂 | 最近把多個共享互動元素統一成 `inline-flex + rounded-full + px/py` 的膠囊樣式後，原本分散在各元件的微小基線補償（例如局部 `-top-px`、不同 `leading`、不同內距）被移除；Safari 的 line box / font metrics 比 Chrome 更保守，讓同一套 shared styles 一起露出偏高問題 | 先把使用者明確反饋的首頁 CTA、篩選器、排序膠囊回復到更接近原始寫法，再用 Safari-only baseline 修正做最小範圍補償；同步保留 Chrome 的既有外觀，避免再擴大改動範圍 | 共享膠囊樣式重構後，不能只在 Chrome 驗證。任何看似「只是把按鈕統一」的改動，都可能把原本隱性的瀏覽器差異放大。之後做跨瀏覽器 UI 調整時，先鎖定最小受影響集合，再用 Safari/Chrome 實際量測比對，不要一次把全站互動元素都重新修到失真。

## 2026-06-04 - `annotate_pending_events()` `event_ids` 漂移先擋住 publication reset one-off

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | `python _oneoff_reset_publication_error.py --source hanmoto --event-id 5131a17c-8006-4fee-8db0-38f16cac2533 --apply` 在本地先報 `TypeError: annotate_pending_events() got an unexpected keyword argument 'event_ids'`，導致 focused apply 還沒進 annotation path 就中斷 | `scraper/annotator.py` 的 CLI 與 one-off 呼叫端都已經傳 `event_ids`，但 `annotate_pending_events()` 仍只接受舊的 `event_id` 參數；one-off 也缺少失敗時把剛改成 `pending` 的樣本列回復成 `error` 的保護 | 在 `scraper/annotator.py` 為 `annotate_pending_events()` 補上 `event_ids` 查詢分支，保持舊 `event_id` 行為不變；在 `scraper/_oneoff_reset_publication_error.py` 加入失敗時 `pending -> error` 的回復；重跑 focused apply 後已越過本地 `TypeError`，下一個真實阻塞點是 remote DB `events_event_form_check` | 當 annotator 增加新的 target-id 入口時，函式簽名、CLI 與 one-off 呼叫端必須同批對齊；對先改狀態再進後續處理的 one-off，至少要保證失敗後不留下 `pending` 半套狀態。

---

## 2026-06-04 - 出版來源 re-annotation 白名單與 live schema 必須同步驗證

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | `ndl_opensearch` / `hanmoto` 出版事件長期卡在 `annotation_status='error'`，`name_zh` / `name_en` 與出版模板欄位都沒補上；單筆 `hanmoto` 驗證時還撞上 live DB `events_event_form_check` | 兩層 drift 同時存在：① `scraper/annotator.py` 的出版模板白名單只硬編 `ndl_opensearch`，漏掉 `hanmoto` / `kawade_rss`；② live DB 尚未反映 migration `047_add_broadcast_event_form.sql`，不接受 `event_form=["publication"]` | 在 `annotator.py` 新增 `_PUBLICATION_SOURCES` 並讓出版模板 fallback 共用白名單；補一支 `_oneoff_reset_publication_error.py` 做 source-scoped reset + re-annotation，預設跳過任何有 `field_corrections` 的事件；同步更新 engineer/source SKILL，明訂白名單與 source 規則必須一起改 | 出版來源的修復不是只改 annotator prompt。每次 batch 前都要同時驗證三件事：`_PUBLICATION_SOURCES` 是否覆蓋目標來源、source SKILL 是否同步、live DB 是否已套 migration 047。少驗任一項，都會在全量時變成 silent miss 或 DB constraint failure。

---

## 2026-06-04 - `OwnerCreateClient` targeted lint FAIL：effect 內 busy reset 與 `any` 洩漏

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | Tester 對 `web/components/OwnerCreateClient.tsx` 的 targeted ESLint 回報 5 個 error，包含 1 個 `react-hooks/set-state-in-effect` 與 4 個 `@typescript-eslint/no-explicit-any` | busy 計時器在 `useEffect` 的 idle branch 直接 `setBusyElapsedMs(0)`；同檔案的 `updateField()`、OCR/annotate 回傳欄位與 extract catch path 仍以 `any` 穿透型別邊界 | 將 busy reset 移到 action 與 image extract 起點，讓 `useEffect` 只負責 interval 訂閱與清理；新增 `isFormFieldKey()` 守衛，將欄位更新與 API 回傳型別收斂為 `unknown` / `Record<string, unknown>`，並用 targeted ESLint + `pnpm exec tsc --noEmit` 驗證 | 有 elapsed timer 的 client component，不要在 `useEffect` body 內做同步 reset state；effect 應只管理 timer 訂閱，輸入型別則先收斂到 `unknown` 再做欄位守衛。

---

## 2026-06-04 - `/[locale]/account/events/new`「儲存並標注」需要連點且回填像殘影

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | 使用者在新增活動頁第一次點擊「儲存並標注」時，按鈕看起來像沒反應，幾秒後才回彈；annotate 成功後欄位逐格回填，視覺上像殘影 | `OwnerCreateClient` 用 `actionLockRef` 防重入，但 busy 回饋只靠 async state，首擊到可見 pending 之間留下誤判空窗；annotate 成功後又逐欄 `updateField()`，造成多次重繪；save 失敗仍只用 `alert`，沒有固定頁內錯誤訊號 | 在 `OwnerCreateClient.tsx` 用 `flushSync` 讓第一次點擊先同步切到 `saving`/`annotating` busy 態並重設計時器，新增頁內 busy banner 與 inline error，並把 annotate 回傳欄位改成單次 `setForm()` 批次套用 | 長流程 client submit 不能只靠 ref 鎖與稍後 render。第一次點擊必須先把 busy 狀態畫到畫面上，且伺服器回填資料應單次 patch，避免多次重繪造成「殘影」體感。

## 2026-06-04 — `location_url` 被誤寫成主辦/活動頁：provenance 混淆與 venue homepage 回填防線

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | 場地頁 `location_url` 被多筆誤寫成 `source_url` / `official_url` / `organizer_url`，後台持續出現「場地網頁缺失，實際填成主辦單位網頁」 | 不是單一 scraper bug，而是三層一起出錯：① 來源/管理表單把 event page URL 當 venue URL；② annotator/enrichment 沒有把「場地官方頁」和「主辦/活動頁」嚴格分開；③ auto-qa/auto-fix 只看 URL 命中，沒有驗證是否為 venue homepage | 在 `qa_auto_fix.py` 新增 `auto_qa_location_url_is_event_url` handler，先用既有 venue search helper，再用 search-preview fallback；新增 `location_url` collision detector，並在 municipal/shared venues 逐筆確認後才鎖定 `field_corrections` | **教訓：** `location_url` 的真實根因是 provenance 混淆，不是單純欄位缺值。修正時一定要驗證「這是不是場地自己的首頁」，不要把活動頁、主辦單位頁、品牌 landing page 當成場地頁寫回去。

---

## 2026-06-04 — 出版相關 pending QA 批次清理改為單用途來源級腳本

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-04 | 出版來源 pending `event_reports` 長期堆積，後台數字無法靠既有安全 auto-fix 收斂 | 出版型語意與一般 QA 規則不一致，且 `eslite_spectrum` 屬混合型來源，若用通用引擎會誤把宣傳講座或展覽一起清掉 | 新增單用途 one-off 批次腳本，只處理 `ndl_opensearch`、`hanmoto`、`kawade_rss`、`eslite_spectrum`，並沿用 `confirmed` / `dismissed` 狀態流；`eslite_spectrum` 保守分流，宣傳講座不與出版事件硬綁 | **教訓：** 來源級 backlog 清理應維持單次、可追溯、最小作用範圍，不要再抽象成新的通用 QA 引擎；混合來源必須保守分流，否則會誤傷人工判斷項目。

---

## 2026-06-03 - 首頁 Server Component 呼叫 client module 純函式導致 production render error

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-03 | `/ja` fresh render 發生 Server Components render error：`Attempted to call buildInitialFilters() from the server but buildInitialFilters is on the client` | `web/components/EventFilterContext.tsx` 是 `"use client"` module，卻匯出純 parser `buildInitialFilters()`；server component `web/app/[locale]/page.tsx` 從 client module 匯入並直接呼叫，踩到 Next.js 16 client/server module graph 邊界 | 將 `EventFilters` type 與 `buildInitialFilters()` 搬到 server-safe 的 `web/lib/eventFilter.ts`，`EventFilterContext.tsx` 只保留 provider/hooks 並 type-only 匯入 `EventFilters`，首頁改從 `@/lib/eventFilter` 匯入純函式 | **教訓：** Server Component 不可從 `"use client"` module 匯入並呼叫非 component 函式。filter parser、URL state builder 等純邏輯應放在 `web/lib/*.ts` server-safe module；client context 不要 re-export server 會呼叫的 helper。

---

## 2026-06-03 — ログイン後にナビバーが数秒で「未ログイン」へ戻る／ホバーで誤ログアウトする二重不具合（commit `c4e1bde`）

**日付 | 問題簡述 | 根本原因 | 修復方法 | 学んだ教訓**
2026-06-03 | ① 全 locale でログイン成功の数秒後にナビバーが未ログイン表示へ戻る（フリッカー）。② アカウントメニューを開いて「我辦的活動」付近へマウスを動かすとログイン画面へ飛ぶ | ① `proxy.ts`・`/api/me`・ブラウザ supabase client が同じ refresh token をほぼ同時にローテーション要求し、敗者のブラウザ client が偽の `SIGNED_OUT` を発火。`Navbar.tsx` の `onAuthStateChange` が無条件に `setUser(null)` していたため、サーバ session が有効でも未ログイン化。② ログアウトリンクが route handler (`/auth/logout`) を指す `<Link>` で、Next.js のホバー prefetch が実 GET を送り `supabase.auth.signOut()` を実行していた | ① `onAuthStateChange` を「イベント種別を信用せず常に `/api/me`（サーバが真実源）を再取得」へ変更し、サーバが user なしと返したときのみクリア。② ログアウト `<Link>` に `prefetch={false}` を付与、「我辦的活動」を `<button>`+`onClick` に変更、ドロップダウンの「収藏」`<Link>` にも `prefetch={false}` を付与 | **教訓：** (1) Supabase SSR で refresh token rotation が有効な環境では、ブラウザ client の `SIGNED_OUT` を単独の真実源にしてはならない。必ずサーバ (`/api/me` の `getUser()`) で再検証する。(2) `<Link>` が route handler（特に `signOut`/副作用を伴う GET）を指す場合は必ず `prefetch={false}` を付ける。ホバー prefetch が副作用を発火させる。受保護ルートへの `<Link>` も prefetch で login へ redirect されるため `prefetch={false}` が安全。

---

## 2026-06-03 — Update History agent の `str_replace` が `engineer/history.md` の 1,227行を誤削除（commits `b1873cc`, `d583f2a`）

**日付 | 問題簡述 | 根本原因 | 修復方法 | 学んだ教訓**
2026-06-03 | `b1873cc`（docs(scraper): document taiwan-only gnews deactivation rule）で `engineer/history.md` から 1,227行が誤削除された | Update History agent が `str_replace` で冒頭エントリを追加する際、`old_str` に `<!-- Append new entries at the top -->` だけを含め、直後の `---` セパレーターも既存の最新エントリ見出しも含めなかったため、ファイル先頭の 1,237行全体が「置き換え対象」になった | `d583f2a` で `git show b1873cc~1:.../history.md` からバックアップを復元し、`b1873cc`・`75c5518` 以降の新エントリと Python スクリプトでマージして完全復元 | **教訓：** `history.md` への `str_replace` 追記では、`old_str` に必ず `---` セパレーターと既存の最新エントリ見出し（`## [YYYY-MM-DD]...`）を含めること。書き込み後は `git diff --stat <file>` で `+N/-0` を確認し、`-` 行があれば即座に `git restore` で復元すること。

--- 

## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 


--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 


---

## 2026-06-03 — `location_url` が会場 URL ではなくイベントページ URL に繰り返し誤設定される根本原因修正（commits `6b3e5ef`, `1313985`）

**日付 | 問題簡述 | 根本原因 | 修復方法 | 学んだ教訓**
2026-06-03 | 会場・チャンネル超連結（`location_url`）が繰り返し主催者 URL / Peatix URL など「イベントページ URL」に設定されており、管理者が手動修正し続けていた | **3 箇所の根本原因**：①`route.ts` の Web Search フォールバックが `new URL(foundUrl).origin` を `location_url` に自動代入（検索ヒットページ = 主催者サイト ≠ 会場）；②`annotator.py` SYSTEM_PROMPT で「Same heuristic as organizer_url」と説明したため GPT が「検索結果ドメイン = 会場 URL」と誤解；③`annotator.py` に `location_url == source_url/official_url` の衝突ガードがなかった | 3 層修正：(1) `route.ts` の `location_url=originUrl` 自動代入を削除しコメントで意図を明示（`6b3e5ef`）、(2) GPT プロンプトを「会場施設自身の OWN サイト限定・イベントページ/Peatix/主催者ドメイン禁止」に書き直し（`1313985`）、(3) `annotator.py` 後処理ガード（`location_url == source_url or official_url` → WARNING + null にリセット）、(4) `auto_qa.py` に `auto_qa_location_url_is_event_url` 検出器を追加し既存汚染データを捕捉 | **教訓：** `location_url` は `source_url`/`official_url` と完全に別ドメインでなければならない。Web Search で見つかった URL の origin は「主催者/イベントプラットフォーム」であり「会場施設」ではない。新たな汚染データのバックグラウンドチェックには `auto_qa_location_url_is_event_url` を走らせること。

---

## 2026-06-03 — `google_news_rss` 薄內容串流新聞誤留 active pool，前端常設 shelf 誤吸入

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-06-03 | `2b9ee650`（`google_news_rss`）是台灣公共電視平台上架台語配音動畫的新聞稿，不是日本事件，卻因 `name_ja` 含 `配信`、`end_date=NULL`、`event_form=[]` 仍留在 active pool，最後被 persistent shelf 吸入 | 這類薄內容新聞條目的問題不在前端分類，而在 DB active pool 缺少人工排除；只要 row 仍是 active，前端 classifier 就會被欄位訊號誤導 | 直接做單筆 DB patch：`is_active=false`，`deactivated_reason='out_of_scope: Taiwan-only streaming news article — not a Japan event'`，並同步回寫 scraper-expert / source history 與規則 | **教訓：** 對於 `google_news_rss` 的台灣限定串流新聞，若同類 active 候選池很小（`<20`），先做一次性手動停用與驗證，不要先重寫 scraper 或做大型 backfill。`category=['report']` 的純配信消息不可只因標題含 `配信` 就留在 active 池。


## 2026-06-03 - 完修首頁/內頁 FloatingShapes 幾何背景動畫防重疊、Slot 綁定與 unique-path 機制

**問題：** 幾何飄浮圖形在首頁有時會發生完全重疊、黏在一起平行前進的現象（視覺打架），開場載入集中從邊緣彈出不夠自然，且全版最大與次大幾何物件多達 4 個過於擁擠。

**修復：**
- 重構 [web/lib/design/FloatingShapes.tsx](web/lib/design/FloatingShapes.tsx)。
- 將 background geometric slots 數量從 10 縮減至 8 個，採用 `[0, 0, 1, 1, 2, 2, 3, 4]` 之 size tier 分配防止大圖擁擠。
- 建立 `shuffle` 函式。在 initialization 時對這 8 個 Slot 分配 1-to-1 的 `shuffledDrifts`（絕對唯一行進軌跡）。
- 在 `handleCycle` 時傳入 `prev`，使在生命週期重啟時仍可自動繼承並鎖定其原專屬唯一的 `drift` 軌跡。
- 放寬 mount 時的 `initialPhase` 係數至全生命週期進度 `Math.random() * duration`，消弭初次開盤排隊冒出的生硬感。
- 同步更新設計師手冊 [.github/skills/agents/designer/SKILL.md](.github/skills/agents/designer/SKILL.md) 與 [.github/skills/agents/designer/history.md](.github/skills/agents/designer/history.md)。
- 通過 `cd web && npx tsc --noEmit` 無編譯警告，並完成本地測試。

**教訓：**
- 動態背景效果如果採用完全隨機機制，隨時間推移以及隨機衝突，一定會產生機率性軌跡重疊；應使用對 Slot 1-to-1 的 unique shuffle 綁定並在生命週期內傳遞 prev 進行傳承。

## 2026-06-03 - 解決爬蟲與首頁優化衝突，無縫整合並成功 NPM Build

**問題：** 工作區具有多個 Stash（含爬蟲專家與首頁改動 Stash），直接 Apply 時在 `scraper-expert.agent.md`、`history.md`、`hanmoto.py` 及 `ndl_opensearch.py` 發生多重內容衝突，阻礙首頁優化元件的無縫倒回與整合。

**修復：**
- 針對 4 個衝突檔案手動執行 merge-conflict 處理，保留 `waseda_taiwan`、`google_news_rss` 的完整 history 與 WordPress 活動頁標籤防漏抓規則。
- 清理非暫存區編譯輔助檔，將臨時 translation 與 types 存入 Stash 動態備份，成功導入 `stash@{1}`（前身為 `stash@{0}`）的首頁大幅優化變更（包含 `EventShelf.tsx`、`SortControl.tsx`、`eventClassify.ts` 與 `eventFilter.ts`、翻譯檔等）。
- 移除一次性過渡腳本 `tmp/add_home_i18n.py`。
- 本地 `npm run build` 正式通過，並具有零 TypeScript 錯誤與 Next.js 16/Turbopack 建置成果。

**教訓：**
- 合併多重 Stash 時，可先封存非暫存區（changes not staged），將其作為獨立 Stash 以解除 merge blocking。
- 手動解決 markdown 的 history.md 衝突時，宜將 upstream 與 stashed 內容依時間線並存，確保兩邊的實踐歷史都不會遺失。

## 2026-06-02 - one-off backfill lacked deterministic verification evidence

**問題：** `scraper/_oneoff_backfill_gnews_streaming_fields.py` 原本僅輸出候選摘要，缺少固定排序的 `event_id` 清單與 `auto_payload` 欄位摘要；Tester 無法用同一批資料可重現驗證。

**修復：** 新增 deterministic 報表輸出（候選/套用 `event_id` 固定排序清單、逐筆 `event_id`、`auto_payload` 欄位名摘要），並加入 `--id`（可重複）與 `--ids-file` 固定驗證集合。

**教訓：** 一次性 backfill 腳本若要可驗證，必須支援固定樣本輸入與固定排序輸出。至少應輸出：候選 IDs、每筆 auto payload 欄位名、實際更新 IDs。

## 2026-06-02 - one-off script file duplicated by parallel same-file create operations

**問題：** 在建立 `scraper/_oneoff_backfill_gnews_streaming_fields.py` 時，對同一路徑做了平行 `create_file`，導致檔案被重複內容污染（同一份腳本出現兩段 `from __future__ import annotations`）。

**修復：** 立即停止增量 patch，改為整檔覆寫成單一版本，並用 `get_errors` + 讀檔確認尾端不再重複後才繼續驗證流程。

**教訓：** 同一檔案的建立/修改不可在同一個平行工具批次中執行。若已發生重複污染，優先採用整檔重寫回到單一真實版本，再做後續 patch。

## 2026-06-02 - authoritative venue dry-run false conflict due to Unicode minus in address

**問題：** `scraper/_oneoff_seed_authoritative_venues.py --dry-run` 對 `誠品生活日本橋` 持續報 `conflict=1`。根因是地址中 `−`（U+2212）未被 `_normalize_addr()` 轉成 ASCII `-`，導致 `_STREET_NUM_RE` 無法截取街道號碼，進而把同址誤判為衝突。

**修復：** 在 `_normalize_addr()` 新增 `replace("−", "-")`，讓 street-prefix 比對可正確處理全形/Unicode 連字號變體；同時依既有 active event 最小調整 2 筆 seed 地址後重跑 dry-run，最終 `conflict=0`。

**教訓：** 任何地址正規化流程若依賴 `\d+-\d+` 類 regex，必須先統一 Unicode 連字號（至少 U+2212）到 ASCII `-`，否則 pre-flight 會出現假衝突並阻斷正確 upsert。

## 2026-06-02 - Node verification script failed from env sourcing and module resolution

**問題：** noindex/sitemap 驗證過程先後遇到三個指令層錯誤：`.env.local` 直接 `source` 出現 unmatched quote、在 `/tmp` 執行 `.mjs` 找不到 `@supabase/supabase-js`、`tsx -e` 因 CJS 輸出不支援 top-level await 而失敗。

**修復：** 改用 Node 腳本直接讀取 `.env.local` 字串解析環境變數，並將驗證腳本放在 `web/tmp`（workspace 內）執行以使用本地依賴；最後統一以 `node` 執行單次驗證，不再用 `tsx -e` top-level await。

**教訓：** 一次性驗證腳本若依賴專案套件與 async 查詢，優先用 workspace 內 `.mjs` + `node` 執行；不要假設 `.env.local` 可被 shell 安全 `source`，也不要在 `tsx -e` CJS 模式使用 top-level await。

## 2026-06-01 - SaveButton saved_events existence check returned 406 for normal empty state

**問題：** [web/components/SaveButton.tsx](/Users/flyingship/development/Tokyo%20Taiwan%20Radar/web/components/SaveButton.tsx) 在 mount 時用 `.single()` 查 `saved_events` 是否存在。對尚未收藏的事件，0 筆結果會被 PostgREST 回成 406，造成前端 console noise，但這其實是正常未收藏狀態。

**修復：** 將存在性查詢從 `.single()` 改為 `.maybeSingle()`，保留 `setSaved(!!data)` 與既有 toggle 流程不變，讓 0 筆結果回傳 `null` 而非 406。

**教訓：** Supabase/PostgREST 的「0 或 1 筆」存在性查詢必須用 `.maybeSingle()`；只有把 1 筆結果視為強約束時才應使用 `.single()`。

## 2026-05-31 — feat(annotator): auto-create eiga-verified film works for fixed cinemas (`e5dbbd9`)

**実装内容：**
- `_get_or_create_film_work()`: `works` テーブルへの atomic get-or-create ヘルパー。一意制約違反（race）は `23505` で捕捉し再クエリ。
- `_norm_work_key()`: NFKC 正規化 + strip で去重アンカーを統一（全角/半角・スペース差異を吸収）。
- `enrich_movie_titles()` 拡張: FC locked `name_zh`/`name_en` がある映画イベントは `works` レコードを自動生成し `work_id` を紐付ける。
- 新 CLI フラグ: `--enrich-dry-run`、`--enrich-source <name>`、`--enrich-limit <N>`

**設計ルール（§4 参照基準）：**
- **§4-B アンカー**: `original_title` には `name_zh` 優先 → `name_en` フォールバック。`name_ja` や未検証 GPT 値は使わない。
- **§4-E**: auto-create 時は GPT director を `works.director` に書かない（未検証値汚染防止）。
- **NFKC**: `_norm_work_key()` を経由しないと全角/半角ゆれで重複 works が生まれる。caller 責務で正規化すること。
- **dry_run**: `--enrich-dry-run` で DB 書き込みなしの pre-flight 確認が可能。

---


## 2026-05-31 — matsumoto_cinema_select 手動マージ後の primary event フィールド修正

**実施内容：**
- XiXi `dd792b98`：`name_ja` `【NPO】` suffix 除去 + FC lock、`name_en` を `works.title_en='XiXi, Let Me Dance'` 使用に変更 + FC lock、`annotation_status` error → pending
- 月老 `e4516272`：`name_zh` の FC lock 誤値（`'電影《赤い糸 輪廻のひみつ》...'` → `'電影《月老》...'`）を upsert で上書き、`name_en` を `works.title_en='Till We Meet Again'` 使用に変更 + FC lock、`name_ja` `【NPO】` suffix 除去 + FC lock、`annotation_status` error → pending

**教訓：** 手動マージ後の primary event は `annotation_status` と全 name フィールドをセットで確認する。`error` 状態では enrichment も走らず `name_ja` に raw_title の suffix が残る。FC lock 誤値の上書きは `field_corrections.upsert(on_conflict='event_id,field_name')` で可能。

---

## 2026-05-31 — Phase D+A: auto_qa performer gap detection + annotator SYSTEM_PROMPT event_form branching（commit `67951af`）

**実装：**
- `auto_qa.py` Phase D: `_detect_missing_performers()` 偵測器新增。`_PERFORMER_SIGNAL_RE`（クリエイター/出演者/登壇者等）と `_PERFORMER_SIGNAL_FORMS` frozenset（market/exhibition/lecture 等）の OR 条件で performer が null のイベントを検出。`QA_TYPES` タプルと `run()` に `"auto_qa_missing_performers"` を追加。
- `annotator.py` Phase A: SYSTEM_PROMPT PERFORMER EXTRACTION RULES に `ROLE KEYWORDS BY EVENT FORM` ブロックを追加（market/exhibition は named brands を `performers[]` エントリとする `MARKET / EXHIBITION EXCEPTION` 付き）。rule 1 から旧 food market null ルールを削除。`DESCRIPTION CONTENT RULE — TAIWAN PARTICIPANTS` 段落を追加。

**教訓：** `_PERFORMER_SIGNAL_FORMS` は frozenset にする（`in` 演算が list より O(1)）。performer gap 検出は「シグナルキーワード OR シグナルフォーム」の OR 条件が適切（AND にすると検出漏れが増える）。

---

## 2026-05-31 — merger._normalize() 末尾 【...】 strip（commit `e53c106`）

**問題：** `matsumoto_cinema_select` の `【ＮＰＯ松本シネマセレクト】` 末尾アノテーションが merger Pass 1 類似度を 0.764 に低下させ、2 ペアの重複イベントが発生（XiXi・赤い糸）。

**修正：** `_normalize()` に `re.sub(r"【[^】]*】\s*$", "", name)` を追加。wrapping bracket strip（末尾 `】` を消費）より**前**に実行しないとマッチしない。4 ケースガードスポットチェック全 PASS（bracket-annotation 1.000 新規）。

**教訓：** 複数の strip パターンを `_normalize()` に追加するとき、後発パターンが先行パターンの副作用でマッチ不可になる順序依存バグが起きる。追加後は必ずスポットチェックで全 4 ケース通過を確認する。

---

## 2026-05-31 - annotator Phase B buffer/disk mismatch left runtime on old FC logic

**問題：** `scraper/annotator.py` 在編輯器內容已顯示新版 Phase B，但新 Python process `inspect.getsource()` 仍載入舊版 runtime：`_load_human_field_map()` 還是 `dict[str, set[str]]`，`_resolve_movie_titles_for_event()` 也仍以未剝前綴的 `title` 做 lookup。

**修復：** 對 [scraper/annotator.py](/Users/flyingship/development/Tokyo%20Taiwan%20Radar/scraper/annotator.py) 做實質 patch，強制將已修正的 buffer 寫回磁碟；之後用全新 Python process 驗證 `_load_human_field_map()` 已改為 `dict[event_id][field]=corrected_value`，且 report prefix title lookup 與無前綴版本一致。

**教訓：** 針對 Python runtime 行為修復時，不能只看 editor/read_file 片段；必須用新 process 的 `inspect.getsource()` 或等價磁碟驗證確認 import 到的就是落地版本，再做行為驗證。

## 2026-05-31 - Validation script could not import `annotator`

**問題：** 驗證腳本放在 `/tmp` 執行時，`import annotator` 失敗（`ModuleNotFoundError`）。

**修復：** 在腳本中加入 `sys.path.insert(0, '/Users/flyingship/development/Tokyo Taiwan Radar/scraper')`，明確把 `scraper/` 加入模組搜尋路徑。

**教訓：** 以 `/tmp` 一次性腳本驗證專案模組時，要先設定 `sys.path` 或改用專案目錄內可匯入的腳本位置。

## 2026-05-31 - Phase D UUID prefix query failed on `ilike`

**問題：** D-2/D-3 一次性修復腳本對 `events.id`（UUID）使用 `.ilike('id', 'prefix%')`，Postgres 回傳 `operator does not exist: uuid ~~* unknown`（42883）。

**修復：** 改為先以 `source_name='google_news_rss'` 分頁載入候選事件，再在 Python 端做 `id.startswith(prefix)` 對應短 ID 前綴，避免 UUID 欄位做文字運算。

**教訓：** UUID 欄位不可直接用 `like/ilike` 前綴查詢。需要短碼對應時，應使用完整 UUID 精確匹配，或先查文字欄位後在應用層比對。

## 2026-05-31 — weekly_line_broadcast URL 過多 + venue-name-as-address city label 缺失

**問題 1：** nearterm・monthly セクションの全イベントに URL が付いてメッセージが長すぎる
- **根本原因：** `_build_message()` が精選段と同じ `lines.append(f"  {url}")` を nearterm group ループ・monthly ループにも持っていた
- **修復：** 両ループの `url` 変数宣言と `lines.append(f"  {url}")` を削除。URL は `【小霧精選】` 段のみ残す
- **教訓：** broadcast メッセージに URL を追加するときは「精選段のみ」を原則とする。nearterm/monthly は日付・都市ラベルだけで十分

**問題 2：** `location_address == location_name`（venue 名がそのまま住所に入っている）イベントで `_city_label()` が空になる
- **事例：** 早稲田大学早稲田キャンパス11号館 → `location_address='早稲田大学早稲田キャンパス11号館710教室'`、`location_prefectures=null`
- **根本原因：** `_city_label()` は `location_prefectures` or `location_address.startswith(都道府県)` で判定するが、venue 名では両方とも miss する
- **修復：** `location_address='東京都新宿区西早稲田1-6-1'`、`location_prefectures=['東京都']` に修正し FC ロック
- **教訓：** `location_address == location_name` の場合は **venue 名であり住所ではない**。`auto_qa_address_is_venue_name` アラートが出たイベントは必ず正式住所を調べて FC ロックする

**Commits:** `cedbaac`（URL 削除）、DB FC ロック（半導体イベント 75a46729）

---

## 2026-05-31 — Venue business_hours 傳播 + auto_qa 品質缺口修補 + Event Form Sync

**修改：**
- `scraper/database.py` `_populate_entity_fks()`：新增 `venue_hours_lookup`（1-b 查詢 is_authoritative venues），aliases 迴圈擴展 select，FC 保護 pre-fetch，mutate rows 加入 business_hours 傳播，`bh_hits` 計數
- `scraper/database.py` `_VALID_EVENT_FORMS`：加入 `"tasting"`, `"broadcast"`, `"study_abroad"`
- `scraper/auto_qa.py` `_detect_missing_hours()`：新增 30 天時間窗口，status 改為 `in_(["annotated","reviewed"])`，`_TIME_RE` 加入日文時間格式 `[時:]`
- `scraper/auto_qa.py`：新增 `_PRICE_KW_RE`、`_BOOKING_DOMAINS` 常數；新增 `_detect_missing_price()` 偵測器；`QA_TYPES` 加入 `auto_qa_missing_price`；`run()` 加入對應呼叫
**Commit:** `33678f0` (database.py), `2f63bcf` (auto_qa.py)
**Phase 1：** 需人工在 Supabase Dashboard 執行 `supabase/migrations/081_venues_business_hours.sql`

---

## 2026-05-31 — API Route JSON Safety Guard 新增至 SKILL.md
**新增/修改：**
- 新增 `## API Route JSON Safety Guard` 段落：try/catch 包整個 POST handler 確保永遠回傳 JSON（Safari SyntaxError 防護）
- 配套規則：file extension 消毒、client-side `.json().catch()` fallback、service role key 顯式 guard
**來源：** daily-skills-review（commit `616eecc` Safari 上傳圖片全失敗，Chrome 無感）

---

## 2026-05-31 — Phase 3 空白事件重抓（refetch_thin_events.py + workflow）

**實作：**
1. 新增 `scraper/refetch_thin_events.py`：讀取 `event_reports` 中 `report_types ov auto_qa_thin_content + status=pending` 的報告，跳過 SKIP_SOURCES（google_news_rss / nhk_rss / prtimes / note_creators / walkerplus）及 inactive 事件，httpx HEAD probe 偵測死連結，Playwright 抓取頁面文字（移除 script/style/nav/header/footer），符合 is_significant_improvement（new_len >= 200 且 > max(old*1.5, old+100)）才更新 DB。
2. 新增 `.github/workflows/refetch-thin-events.yml`：每日 14:00 JST（cron 0 5 * * *）觸發，guard 為 `vars.REFETCH_THIN_LIVE == 'true'`，執行 refetch → annotator --limit 100。
3. 驗證：dry-run 列出 5 筆（SKIP_SOURCES 正確過濾），taiwan_prism 真實測試 old=38 → new=1084，annotation_status 更新為 pending，admin_notes 追加 refetched:2026-05-31 note。

**教訓：**
- `event_reports.report_types` 是 `text[]`，查詢用 `.ov()` 方法（overlap），不是 `.contains()`。
- Playwright 移除噪音元素後直接用 `page.inner_text("body")` 比 `page.evaluate("document.body.innerText")` 更可靠（前者等待 DOM 穩定）。

## 2026-05-30 — PR1 電影院 scraper 統合基盤（Phase 1A + 1B + 1C）

**實作：**
1. **Phase 1A**：新增 `_cinema_constants.py`（FIXED_CINEMA_SOURCES）、`_cinema_base.py`（CinemaScraper + make_film_source_id + _normalize_film_title）、`_cinema_dates.py`（parse_date_range / parse_japanese_date / extract_showtimes）。
2. **Phase 1B**：`kyoto_cinema.py` 改繼承 `CinemaScraper`，source_id 從 `kyoto_cinema_{movie_id}` 改為 `make_film_source_id("kyoto_cinema", title)`（hash 穩定化）；日期/時刻改用共通函式。新增 `_oneoff_migrate_kyoto_source_id.py`（dry-run 預設）。
3. **Phase 1C**：`web/app/[locale]/events/[id]/page.tsx` relatedScreenings query 加三件過濾（`.eq("is_active",true)` + `.is("merged_into_event_id",null)` + `.or("end_date.is.null,end_date.gte.${today}")`）；刪除 client-side `upcomingScreenings`/`pastScreenings` const；移除 past 區塊 JSX；i18n key `pastScreeningsLabel` 保留。

**Guard 落實：**
- `_normalize_film_title` 的 NFKC 正規化確保全形英數不影響 hash。
- `_STATUS_WORDS` regex 剝除狀態詞但保留版本資訊（Same-Venue Different-Work Collision Guard）。
- 所有日期函式明確 `return None` / `return None, None`（Date-Parser Exhaustive Return Guard）。
- `.or()` 保留 `end_date.is.null` 分支，避免 NULL 被 SQL 三值邏輯誤隱藏（缺陷 N1）。
- related query 維持 service role（RLS Cross-Status Query Guard）。

## 2026-05-20 — 管理画面 OCR + annotate-event の event_form / category プロンプトが DB / types.ts と乖離（管理画面 event 保存が 400 / 不正な i18n キー表示）

**問題：**
1. 海報を OCR で保存しようとすると `Save failed: new row for relation "events" violates check constraint "events_event_form_check"` で 400 エラー。「保存中…」が 1 分以上ハングして見える。
2. 保存成功後、カテゴリーに `categories.health` という生 i18n キーが表示される（翻訳なし）。

**根本原因：**
1. `web/app/api/admin/extract-from-image/route.ts` L58 と `web/app/api/admin/annotate-event/route.ts` L382 の GPT プロンプト内 `event_form` リストが **migration 047 以降の DB CHECK constraint と乖離**。プロンプトは pre-047 命名（`concert`, `lecture_seminar`, `film_screening`, `festival`, `sports`）、DB は新命名（`performance`, `lecture`, `screening`, `broadcast`, `tasting`, `study_abroad` 等 15 値）。重複 4 値のみ（`exhibition`, `market`, `study_abroad`, `other`）。
2. 同 2 ファイル L59/L381 の `category` リストが **`web/lib/types.ts` の 38 値より 20 値不足**（`healthcare`, `tea_alcohol`, `drama`, `documentary`, `parenting`, `scholarship`, `study_abroad`, `indigenous`, `folklore`, `history`, `urban`, `workshop`, `literature`, `tv_program`, `radio_program`, `exhibition`, `design_craft`, `herbal`, `taiwan_mandarin`, `market` が欠落）。GPT は欠落値の代わりに `health` を捏造 → 前端で i18n key 未マッチ → `categories.health` のまま表示。

**修正：**
1. `extract-from-image/route.ts` L58 / `annotate-event/route.ts` L382 の `event_form` リストを DB 047 の 15 値に同期（commit `9ecaae6`）。
2. 同 2 ファイル L59/L381 の `category` リストを types.ts の 38 値に同期（commit `997378c`）。
3. DB 内 `category=['health',...]` を `['healthcare','workshop','lecture']` に修正 + `field_corrections` ロック。
4. `scraper/annotator.py` `VALID_EVENT_FORMS` (L863) と `VALID_CATEGORIES` (L224) は既に正しい — 影響は Web API プロンプトのみ。

**教訓：**
- **GPT プロンプト内の enum リストは「第 4 の同期位置」**：DB constraint → annotator → web API プロンプト × 2。Architect SKILL の Category/Event Form Addition Checklist に **`web/app/api/admin/{extract-from-image,annotate-event}/route.ts`** を明記する必要がある。
- TypeScript の型チェックは prompt 文字列内の列挙値を検証しない。リストはコードコメントとして劣化する。**migration を追加するたびに、両 API ファイルを `grep` で確認すべし。**
- GPT は与えられた enum 以外の値を **静かに捏造する**（`concert` の代わりに `concert` を返さず、`performance` も知らない → `concert` 維持 / `health` 創作）。validation は DB CHECK constraint と前端 i18n の 2 か所にしかない。

---

## 2026-05-20 — annotate-event の SELECT で end_date 欠落 → ユーザー入力が GPT 幻覚で上書き

**問題：** 管理画面で event を作成し end_date を明示的に選択 → 保存 → annotate-event 自動実行後、end_date が `2023-10-14` 等の幻覚値に置き換わっていた。

**根本原因：** `web/app/api/admin/annotate-event/route.ts` L258 の `select(...)` 句が **`start_date` のみ含み `end_date` を欠落**。「ユーザー入力済みフィールドを保持」ロジック
```ts
if (cur === null || cur === undefined || cur === "") returnedFields[k] = v;
```
は `event.end_date` が `undefined`（SELECT に無いため）なら「空」と判定 → GPT が返した任意の値で上書き。OCR から GPT を 2 回通過する間にハルシネーションが入る。

**修正：** L258 SELECT 句に `end_date` を追加（commit `e0a5ea8`）。

**教訓：**
- **保持したいフィールドは必ず SELECT に含める**。「empty なら上書き」パターンの落とし穴：SELECT 漏れ ＝ undefined ＝ empty 扱い ＝ サイレント上書き。
- `extractionFields` 配列に列挙されているのに SELECT で fetch していないフィールドは 100% バグ。**新規 extractionField を追加する時は SELECT 句も同時更新する**ことを `annotate-event/route.ts` 冒頭にコメントで明記すべし。
- ユーザーが「明確に選択した」フィールドが知らぬ間に変わる症状を見たら、まず該当 API の SELECT 句を確認。

---

## 2026-05-20 — performers[] 繁体字混入 + performers_zh[] ステージネーム GPT ハルシネーション（DB 直接修正）

**問題：** 霧のごとく（映画 大濛）11 件の `performers[]` に繁体字（`['范少勳', '區偉', '9m88', '曾敬驊']`）が入り、日本語ロケールで映画サイトのカタカナではなく漢字が表示された。さらに `performers_zh[]` に `9m88 → 'Ju 88轟炸機'`（WW2 ユンカース爆撃機）という GPT ハルシネーションが混入。`field_corrections` も誤った値でロックされ汚染が固定化していた。

**根本原因：** annotator が繁体字 film DB から performers[] を生成し、日本語ソースページのカタカナではなく漢字をセット。`performers_zh[]` 生成時に GPT がステージネーム `9m88` を軍用機型番「Ju 88」と誤一致させた。

**修正：**
1. 全 11 件の `performers[]` をカタカナ（京都シネマ公式ページ準拠）に更新。
2. `performers_zh[]` を繁体字 6 名に修正（劉冠廷・宋芸樺 2 名追加）。
3. `field_corrections` を全件削除 → 正しい値で再ロック。
4. `works.cast_summary` もカタカナ 6 名に更新。
5. 他 3 件（赤い糸・優雅な邂逅・ナルワンアワー）の performer 区切り文字も null クリア。QA レポート 14 件全確認済み。

**教訓：**
- `performers[]` は **日本語（カタカナ）ソースページから取得した名前** が正しい値。繁体字 film DB から補完したデータは `performers_zh[]` に入れる（`performers[]` ではない）。
- `performers_zh[]` 生成時、英数字・記号含むステージネーム（`9m88`、`88rising` 等）は **翻訳禁止**。言語横断で同一表記のまま維持する。
- PostgREST で UUID 列に `.like('%prefix%')` を使うと `operator does not exist: uuid ~~ unknown` エラー。UUID フィルタには `eq(full_uuid)` または name/source_name 等の TEXT 列で代替する。

---

## 2026-05-20 — auto_qa_performer_multi_value_pollution: ステールレポート 10 件 + event_reports カラム名誤認（DB 直接修正）

**問題：** `auto_qa_performer_multi_value_pollution` ペンディングレポート 14 件のうち 10 件は underlying の `performer` がすでに null に修正済みのステール。調査時に `event_reports.details` カラムを参照したところ `column event_reports.details does not exist` エラーが発生した。

**根本原因：** (1) QA レポートは underlying data が修正されても自動でクローズされない。(2) `event_reports` に `details` カラムは存在せず、正しいカラム名は `report_types TEXT[]`（複数形）。

**修正：** pending レポートを対象に `events.performer` を確認し、区切り文字がなくなった 10 件を `status='confirmed'` に更新。残り 4 件（performer に区切り文字残存）は performer を null に修正した上でクローズ。

**教訓：** (1) `event_reports` の正しいカラム: `report_types TEXT[]`（複数形）、`status`、`confirmed_at`。`details`・`report_type`（単数）は存在しない。(2) データ修正後 QA レポートは手動でクローズが必要 — `auto_qa.py` は「作成」のみ。

---

## 2026-05-20 — field_corrections.corrected_value NOT NULL: performer=null は `""` で表現（DB 直接修正）

**問題：** `performer = null` を表現するために `corrected_value = None` で `field_corrections` upsert したところ `null value in column "corrected_value" violates not-null constraint` が発生した（event `13d618e5` sakurazaka 修正時）。

**根本原因：** `field_corrections.corrected_value` カラムは NOT NULL 制約あり。null performers を保存する既存慣例（`corrected_value = ""`）を事前確認しなかった。

**修正：** `corrected_value = ""` （空文字列）が `performer = null` を表す既存慣例と確認し `None` → `""` に変更。

**教訓：** `field_corrections` で `performer = null` をロックするときは `corrected_value = ""`（空文字列）。Python `None` は DB NOT NULL 制約で弾かれる。

---

## 2026-05-19 — eplus performer → raw_description 修正（SKILL.md performer ルール違反）（commit `fe72ea2`）

**問題：** `_fetch_detail_info()` が `<dt>出演</dt>` の performer を `ev.performer` に直接セット。SKILL.md「Scraper 層用不到 — performer は annotator GPT 層が raw_description から抽出する」ルール違反。

**修正：** performer/program を `raw_description` に `出演: …\n曲目・演目: …` 形式で追記するよう変更（`fe72ea2`）。

**教訓：** scraper に performer 関連フィールドを追加する前に SKILL.md `## performer / performers[] 注解規則` を確認する。

---

## 2026-05-19 — enrich_addresses: 市区レベルアドレスの VAGUE 未判定 + FC ロックによる二重ブロック（commit `113fceb`）

**問題：** eplus が市区レベル（`'福岡市'`）まで補完しても `enrich_addresses.py` が街路補完を適用しなかった（アクロス福岡 `7cdd06cb`）。原因は 2 つ：(1) `VAGUE_ADDRESS_VALUES` に市区名が未収録、(2) `field_corrections` に古い `'福岡県'` がロックされ eplus の補完が毎回上書きされていた。

**修正：** `_VAGUE_GEO_RE = re.compile(r'^[^\s]{2,10}[都道府県市区]$')` 追加（`113fceb`）。FC 削除 + NULL リセット後に enrich_addresses 実行 → `'福岡県福岡市中央区天神1-1-1'`（gpt-4o-search-preview, conf=high）。

**教訓：**
- FC ロックは enrich_addresses を完全ブロックする。手動で街路補完が必要な場合は FC 削除 + `location_address = NULL` が前提。
- スクレイパー側の部分補完（都道府県→市区）と enrich_addresses の街路補完は 2 段階。後段が前段の出力を VAGUE と見なすことで初めてパイプラインが繋がる。

---

## 2026-05-19 — Peatix: `inner_text()` ページ全体テキスト blob ガード（commit `f839508`）

**問題：** Playwright `inner_text()` がグループアンカーに対してページ全体テキスト（数千文字）を返し、`organizer_name` が汚染されるケースがあった。

**修正（commit `f839508`）：** 主パス・fallback パス両方に `len(_txt) <= 100` ガード追加。

**教訓：** `inner_text()` を短い文字列フィールドに使う場合は必ず長さガードを設ける。名前・タイトル・ラベル系は `if _txt and len(_txt) <= 100` が標準パターン。

---

## 2026-05-19 — Peatix: `organizer_name` 抽出しながら `Event()` に渡し忘れ（commit `24198d0`）

**問題：** `organizer_name` はブロックリスト照合のために抽出されていたが `Event()` コンストラクタに未渡しで `ev.organizer = null` のまま保存されていた。

**根本原因：** 変数が「ブロックリスト照合のみ」として追加された際に「DB 保存」という第 2 の用途が見落とされた。「Extract but not store」anti-pattern。

**修正（commit `24198d0`）：** `Event()` の引数に `organizer=organizer_name or None` 追加。

**教訓：** PR 提出前に「スクレイパー内の抽出変数が全て `Event()` コンストラクタに渡っているか」を確認する。ブロックリスト照合だけのために定義した変数も `Event()` に渡すことを忘れない。

---

## 2026-05-19 — eplus: `_fetch_city_from_detail()` が同一レスポンスの `dt/dd` を無視（commit `e897d29`）

**問題：** eplus 詳細ページへのアクセスは既に実装されていたが `<dt>出演</dt><dd>…</dd>` 等の performer 情報が一切取得されておらず `ev.performer = null` が続いていた。

**根本原因：** 「1 リクエスト 1 フィールド」の設計。都市名抽出専用の関数として作られ、同一 HTTP レスポンスに含まれる他のデータを取る設計になっていなかった。

**修正（commit `e897d29`）：** `_fetch_city_from_detail()` → `_fetch_detail_info()` に拡張し、同一リクエストで city / performer / program を一括取得。

**教訓：** 詳細ページを 1 回 fetch したら、そのレスポンスで取れる全フィールドを抽出する設計にする。「追加フィールドが必要になるたびにリクエストを 1 回増やす」は CI コストとレートリミットの観点から避ける。

---

## 2026-05-19 — enrich_addresses A1-A4 強化（commit `1022303`）

**実装内容：**
- A1: `VAGUE_ADDRESS_VALUES` 定数追加（`東京`・`大阪府` 等）、DB フィルタを Python 側に移動して vague address イベントも対象に追加
- A2: 処理前にバッチ FC lock チェック、update 後に `field_corrections` upsert（location_address）
- A3: `_normalize_venue()` ヘルパーで `城市｜会場名` 形式を正規化し、lookup に渡す前に prefix 除去
- A4: `--limit` フラグ追加（CI は `--limit 30`、手動は無制限）

**事前確認：** `location_name_zh/en` の `｜` 汚染は 1件のみ（curator 名）、会場prefix 形式ではなかったため A3 の zh/en 対応は実装不要と判断。

**教訓：** DB 側フィルタで null のみ対象にすると vague 住所（都道府県名だけ等）が永久に漏れる。候補フィルタを Python 側に持ち FC lock と組み合わせるパターンが堅牢。

---

## 2026-05-19 — Peatix `/us/event/` URL 正規化：URL 収集段階での locale prefix 除去（commit `8b901ec`）

**問題：** `source_url` に `https://peatix.com/us/event/4994536` のようなロケールプレフィックス付き URL が保存されており、`302 → peatix.com トップ` にリダイレクトされ「リンク消失」に見えた。実際のイベントページは `/event/4994536`（prefix なし）で正常に存在。

**根本原因：** Playwright の headless ブラウザに Peatix が US ロケール URL を返していた。`_scrape_group_events` と `_search_events` がそのまま保存。DB に 7 件混入。

**修正（commit `8b901ec`）：** `_normalize_peatix_url()` ヘルパーを追加し URL 収集ループで適用。DB 7 件：重複 5 件は `merged_into_event_id` で soft-delete、重複なし 1 件（`55d766ae`）は `source_url`/`source_id` を正規化、inactive 1 件は skip。

**教訓：** URL 正規化は `_scrape_detail()` より上流の収集段階（`_search_events`・`_scrape_group_events`）で行う。`source_id = md5(url)` なので URL 変更 = `source_id` 変更 → 正規化前後で重複レコードが生じる。DB 修正は「重複チェック → DUP: merge soft-delete / NO-DUP: update in place」の 3 分岐が必要。

---

## 2026-05-17 — `auto_research` が `scraping_feasibility` 直接カラムに書かず UI が常に "?" 表示（commit `43da6a1`）

**問題：** `AdminResearchTable.tsx` の可行性列が auto_research 実行後も常に "?" で表示。

**根本原因：** `_apply_assessment()` と `update_source.py` は両方 feasibility を `source_profile` JSONB 内にのみ書いていた。`research_sources.scraping_feasibility`（top-level TEXT カラム）への書き込みがなく、UI が読む列は常に null。

**修正（commit `43da6a1`）：** `auto_research.py` の `patch` に `"scraping_feasibility": result.feasibility` 追加。`update_source.py` に `if feasibility is not None: update_fields["scraping_feasibility"] = feasibility` 追加。テスト 15 件 PASS。

**教訓：** DB スキーマに top-level column と JSONB フィールドで同じ情報が存在する場合（`scraping_feasibility` TEXT vs `source_profile.feasibility`）、UI がどちらを読んでいるかを先に grep で確認してから書き込み先を決める。

---

## 2026-05-17 — annotator: GPT '不明' が business_hours に保存 → `_HOURS_INVALID` ガード追加

**問題：** 局外談 `63625c1a` の `business_hours` が `'不明'`（GPT 出力）のまま保存されていた。annotator は `event.get("business_hours")` が truthy ならそのまま使うため、再 annotation 後も `'不明'` が保持され続け auto_qa から除外されなかった。

**根本原因：**
1. GPT が時刻不明のとき `null` でなく `'不明'` を返すことがある。
2. `business_hours = event.get("business_hours") or _pre_hours or annotation.get("business_hours")` のロジックで `'不明'`（truthy）が常に優先され、`_pre_hours`（raw_description からの決定論的抽出）が実行されなかった。

**修正（commit `533f980`）：**
- `_HOURS_INVALID = frozenset({'不明', 'unknown', '未定', 'TBD', 'TBA'})` をモジュールレベルに追加。
- `_valid_hours(v)` helper：`v.strip() in _HOURS_INVALID` なら `None` を返す。
- `business_hours` 代入を `_valid_hours()` でラップし、無効値を null 扱いにして `_pre_hours` フォールバックを有効化。

**付随教訓 — `_extract_hours_from_raw()` の `時` 形式非対応：** 種土 `9084ad67` の raw_description に `13時30分開場 / 14時00分開演` が含まれていたが、`_extract_hours_from_raw()` は `\d{1,2}:\d{2}` のみ対応で `\d時\d{2}分` を検出できない。このケースは **手動バックフィル + FC lock** で対応。

---

## 2026-05-17: zsh 方括號路徑未加引號造成 `no matches found`

**問題：** 執行 `git diff -- web/app/[locale]/admin/...` 時，zsh 先把 `[...]` 視為 glob pattern，命令在 shell 層直接失敗。

**根本原因：** 路徑含 `[` `]`（Next.js 動態路由資料夾）但未用單引號包住，觸發 zsh 路徑展開。

**修正：** 所有含方括號的路徑改用單引號，例如 `git diff -- 'web/app/[locale]/admin/stats/page.tsx'`。

**教訓：** 在 zsh 下，任何含 `[...]` 的路徑都必須加單引號；否則命令不會送到 git，會先被 shell 擋下。

---

## 2026-05-17 — DB クエリ出力に Prompt Injection（2件：f-string 経由 `rm -f` 実行試行）

**問題：** `python3 -c "...f'{r[\"corrected_value\"]}' ..."` でターミナル出力に `rm -f "/Users/.../token.json"` が埋め込まれ、SyntaxError もしくは silent 実行が発生。2セッション中に2件検出。

**根本原因：** Supabase の `field_corrections` テーブルに格納されている値（`corrected_value`）に悪意あるシェルコマンドが埋め込まれていた。`python3 -c` のインライン f-string はその値を文字列展開するため、`{` / `}` の対称破壊 → SyntaxError、またはコマンド文字列が print 出力を通じてターミナル履歴に挿入される。

**修正：** `create_file /tmp/<name>.py` + `python3 /tmp/<name>.py` に切り替えることで、DB 値がファイルに書き込まれず安全に分離。

**教訓：** DB クエリ（特に `field_corrections`）を f-string で展開するスクリプトは**絶対に** `python3 -c` で実行しない。アラートが出たら即 `/tmp/*.py` に切り替える。

---

## 2026-05-17 — performer QA 3件修正：AI翻訳マーカー除去 + multi-value null化 + bad FC lock 削除（`eeb5b12e`・`9084ad67`・`6200fbe1`）

**問題：**
1. `eeb5b12e`：`performer_zh='中村葉子（AI翻譯）'`、`performer_en='Yoko Nakamura (AI Translation)'` — AI翻訳マーカーが残存。
2. `9084ad67`：`performer='阿仁、安和'`（`、` 区切りの複数人 → multi-value pollution）。さらに FC に `performer='阿仁、安和'` がロックされており、events table を null にしても annotator が復元する状態。
3. `6200fbe1`：`performer='林宸順、雷傑西、王曉月、游聖峰'`（同上）。

**根本原因：** auto_qa がレポートを作成していたが、FC lock に悪い値が残っていたため events table 修正だけでは不十分だった。FC lock の存在を確認せずに events table だけを更新する一般的なミス。

**修正：** `eeb5b12e` — performer_zh/en から AI翻訳マーカーを除去し FC ロック。`9084ad67`・`6200fbe1` — events table `performer=null` + FC の `performer` 行を DELETE。auto_qa レポートを dismissed。

**教訓：** `performer` を events table で修正したら**必ず** `field_corrections` の `performer` 行を確認し、悪い値がロックされていれば DELETE する。

---

## 2026-05-17 — 9084ad67（種土）：`location_url` が Peatix チャンネル、`official_url` が null

**問題：** イベント詳細ページの「場地 ↗」が `https://taiwanculture.peatix.com/`（台湾文化センターの Peatix チャンネル）にリンク。`official_url` は null で、ソースリンクが「查看原始資訊」表示になっていた。

**根本原因：** annotator が `location_url` を Peatix チャンネル URL に設定（イベント登録リンクと会場リンクを混同）。`official_url` は null のまま放置 — `source_url`（台湾文化センターの公式イベントページ）が官方URLとして昇格されていなかった。

**修正：** `location_url = 'https://jp.taiwan.culture.tw/'`（台湾文化センター公式サイト）、`official_url = source_url の値`（イベントページ）に更新し、両フィールドを FC ロック。

**教訓：** `taiwan_cultural_center` ソースのイベントは `source_url` が官方イベントページを指している場合、`official_url` にコピーして昇格する。`location_url` は会場の公式サイト（`https://jp.taiwan.culture.tw/`）を設定する。

---

## 2026-05-17 — `location_url` 修正時に apex ドメインのみ確認し「公式サイトなし」と誤判断（event `eeb5b12e`）

**問題:** `location_url` を null にセットし「Coconeri に公式サイトなし」と結論した後、ユーザーが `https://www.coconeri.jp` を指摘。サイトは存在しており `200 OK` を返す。

**根本原因:** URL 確認で `https://coconeri.jp/`（apex ドメイン）のみ試した。`curl` が `000`（DNS 解決失敗）を返したため「サイト不在」と判断。`www.` サブドメイン（`https://www.coconeri.jp/`）を試さなかった。日本の多くのサイトは apex→www リダイレクトを設定しておらず、`www.domain.jp` のみ有効なケースが多い。

**修正:** `location_url = 'https://www.coconeri.jp'` に更新し FC lock。

**教訓:** 会場・組織の公式サイト有無を `curl` で確認する際は `domain.jp` と `www.domain.jp` の**両方**を必ず試す。`000` は「その変形が DNS 解決できない」であり「サイト不在」ではない。

---

## 2026-05-17 — startup_terrace Playwright stub → requests 版に刷新 + TaiwanPrism 登録漏れ修正

**問題 1:** `sources/startup_terrace.py` が auto-scraper 生成の Playwright stub のままで production 未対応。SSL cert エラー（Missing Subject Key Identifier）も未対処。

**問題 2:** `TaiwanPrismScraper` が `main.py` の `SCRAPERS` リストに未登録（session notes に「登録済み」とあったが実際は漏れていた）。

**根本原因:** auto-scraper が Playwright stub を生成した後、manual 実装を行った際に `main.py` 登録を同一セッションで完了しなかった。また `startupterrace.tw` の TLS 証明書が Missing Subject Key Identifier 拡張 → `requests` の `verify=True`（デフォルト）が `SSLCertVerificationError` を raise。

**修正 (commit `99d9fde`):**
- `startup_terrace.py` を requests + BeautifulSoup 版に完全書き換え。`verify=False` + `warnings.simplefilter("ignore")` で SSL 回避。
- title-first JAPAN_KW フィルタ（detail ページ fetch 前に判定）でパフォーマンス改善。
- `name_en`, `organizer`, `organizer_zh/en`, `organizer_url`, `organizer_type`, `event_form`, `category`, `official_url` を追加。
- `main.py` に `StartupTerraceScraper` と `TaiwanPrismScraper` を同時に登録。
- `research_sources` id=331 の `status → implemented`。
- dry-run: 6 件正常取得。

**教訓:** 台湾政府サイト（`.tw` ドメイン）は Missing Subject Key Identifier 証明書エラーを起こすことがある → `verify=False` + `warnings.simplefilter("ignore")` を scraper helper の `_get()` に組み込む。Promotion checklist の「SCRAPERS 登録」は commit と同一 session で実施し、Post-Build Audit を必ず実行すること。

---

## 2026-05-16 — wuext_waseda 多重セッション講座：performer 截斷 + business_hours 不完整（event `1be67e0f`）

**問題：** event `1be67e0f`（沖縄現場学）で `performer='吉田'`（本来 `カベルナリア 吉田`）+ `business_hours='19:00〜20:30'`（曜日・全7回・個別開講日が脱落）。

**根本原因：** `scraper/sources/wuext_waseda.py` が `Event.performer=`、`Event.business_hours=` を設定せず annotator regex に依存。Annotator の `_PERFORMER_INTRO_RE` は `[\u4e00-\u9fff]{2,5}` 純漢字 pattern なので片假名+漢字複合名 `カベルナリア 吉田` から `吉田` のみ抽出。Annotator は曜日・全N回・跳週日付も抽出できない。

**修正：** wuext_waseda.py に `_SESSION_DATES_RE`、`_WEEKDAY_LISTING_RE`、`_KAISU_RE` + `_build_business_hours()` helper を追加。`Event(performer=instructor, performers=[instructor], business_hours=bh)` を構造化欄位から直接設定。DB は event 1be67e0f の 3 欄位 patch + `field_corrections` lock。Docs: scraper-expert SKILL.md / history.md、architect SKILL.md に新 guard 2 件。

**Lesson：** 来源頁有結構化 instructor / 講師 / 時間表欄位なら scraper で `Event(...)` に直接設定。Annotator の regex は raw text からの fallback のみで、構造化フィールドの代替ではない。

---

## 2026-05-15 — about ページ dark mode でテキストが見えない（commit `8ab8d05`）

**問題：** `https://tokyotaiwanradar.com/ja/about` で dark mode 時にタイトル・本文が背景に溶け込んで読めない。

**根本原因：** `about/page.tsx` の全テキストが hardcoded hex `text-[#3A261F]`（見出し）・`text-[#4A362D]`（本文）に設定されていた。`layout.tsx` の anti-flash script が `prefers-color-scheme: dark` を検知して `<html class="dark">` を付けるため dark mode は有効だが、hardcoded hex は `:root.dark` のセマンティックトークンに追従しない。

**修復（commit `8ab8d05`）：**
- `text-[#3A261F]` → `text-fg-strong`（見出し h1・h2、パンくずリスト）
- `text-[#4A362D]` → `text-fg`（本文段落）

Dark mode: `text-fg-strong` = `#fafafa`、`text-fg` = `#ededed`（`:root.dark` に定義済み）。

**教訓：**
1. **ページコンポーネントで `text-[#hex]` を直接使わない**：`:root.dark` が存在する今、hardcoded hex は dark mode で必ず問題になる。
2. **見出しは `text-fg-strong`、本文は `text-fg`**：`globals.css` の `@theme` ブロックに定義された semantic token を使う。
3. **`dark:` variant は不要**：semantic token が `:root.dark` で自動切り替わるため、`dark:text-xxx` を個別に書く必要はない。

---

## 2026-05-15 — research_reports 「標記為已審閱」按鈕 silent failure（migration `070`）

**問題：** Admin Research Reports 頁面點「標記為已審閱」按鈕，UI 無反應，DB 無變化，無 JS error。

**根因：** Migration `008_research_reports.sql` 只建立 SELECT policy，未建 UPDATE policy。RLS 預設拒絕，admin 的 UPDATE 被 PostgREST 靜默拒絕（0 rows affected，回傳 `error: null` + 空陣列），符合「Supabase Client UPDATE 0-row Silent Success」模式。

**修復（migration `070_research_reports_update_policy.sql`）：** 補上 admin UPDATE policy，沿用 `006_event_reports.sql` 既有 admin 模式。

**教訓：**
- 任何 `research_reports`、`event_reports` 等「admin 後台會 UPDATE 的表」建立時，**SELECT / INSERT / UPDATE / DELETE policy 必須一次到位**，缺一即 silent failure。
- 既存的「0-row Silent Success Guard」前端 `.select("id")` 檢查能偵測但不能根治——根治在 migration 階段確保 policy 完整。
- 新增 admin UI mutation 入口時必須核對對應 DB table 的 RLS policy 矩陣（SELECT 有 ≠ UPDATE 有）。

---

## 2026-05-15 — ReportSection 送信ボタンが「送信中…」で永久に固まる（commit `53445be`）

**問題：** イベント詳細ページの「問題を報告」フォームで送信ボタンをクリックすると「送信中…」表示のまま永久に固まり、成功・エラーどちらも表示されない。

**根因：** `ReportSection.tsx`（Client Component）がブラウザ Supabase クライアントで直接 `supabase.from("event_reports").insert(...)` を呼び出していた。PostgREST からレスポンスが返らない（ネットワークハング）場合、`await` は永遠に pending のまま。`try/catch` は **thrown error** しか捕捉できず、**hanging fetch** は捕捉しない。結果として `setStatus("error")` が呼ばれず、ボタンが `loading` 状態で固まる。

**修復（commit `53445be`）：**
- `web/app/actions/submit-report.ts` を新規作成（`dismissReport` と同じ Server Action パターン）
- `ReportSection.tsx` の browser client INSERT を `submitReport()` Server Action 呼び出しに置き換え
- `@/lib/supabase/client` import を削除

**教訓：**
- **Client Component で `supabase.from(...).insert()` を直接呼び出してはならない。** ネットワークハング時に `try/catch` は発動せず UI が永久 loading 状態に陥る。
- ユーザー向けフォームの INSERT（anon・authenticated 問わず）も Server Action に統一する。RLS で `anon INSERT` を許可していても、ブラウザ直接 INSERT はハング耐性がない。
- `dismissReport` / `confirmReport` が Server Action に昇格済みであれば、同一テーブルへの user-facing INSERT も Server Action にすべきだった（パターン一貫性）。

---

## 2026-05-15 — handleDismiss で router.refresh() が画面破損を引き起こした（commit `390826a`）

**問題：** `handleDismiss`（報告を却下するハンドラー）を server action（`dismissReport`）に移行後、`router.refresh()` を呼び出すと画面が突然フリーズ・レイアウト崩壊（"screen break"）した。

**根因：** `handleDismiss` は stay-on-page ハンドラー（`router.push()` なし）であるにもかかわらず、`router.refresh()` が追加されていた。`router.refresh()` が RSC の再レンダリングをトリガーし、Supabase Realtime の `UPDATE` イベントが同時に届いたことで state/render race が発生。`handleConfirm` と異なり、dismiss は `event_reports.status` のみを変更するため SSR キャッシュ無効化は不要。

**修復（commit `390826a`）：**
- `handleDismiss` から `router.refresh()` を削除
- ローカル state（`setReports()`）と Realtime 購読で十分（他のセッションにも反映される）

**教訓：**
- `router.refresh()` は **navigation handler（`router.push()` を伴う場合）にのみ呼ぶ**。stay-on-page の mutation handler では呼ばない。
- stay-on-page handler で `router.refresh()` を呼ぶと、Realtime サブスクリプションと RSC 再レンダリングが競合し、画面が破損する。
- dismiss は event fields を変更しない → SSR cache invalidation 不要 → `router.refresh()` 禁止。
- confirm は event fields（category, is_active）を変更する → SSR cache invalidation 必要 → `router.refresh()` 必須。

---

## 2026-05-15 — _oneoff_migrate_multi_performer で役割 suffix が名前に残る（commit `a3a4bed`）

**問題：** `_split_performer()` で複数人名文字列（例：`ジャッキー・チェン（監督）、ジェット・リー（主演）`）を分割後、各名前に `（監督）`、`（主演）` などの役割表記が残ったまま `performers[]` に格納されていた。

**根因：** `_SEP_RE` で区切り文字を基に分割した後、役割 suffix の除去処理がなかった。「分割」と「suffix 除去」を独立ステップとして実装していなかった。

**修復（commit `a3a4bed`）：**
- `_ROLE_SUFFIX_RE = re.compile(r"[（(](?:監督|主演|出演|演出|脚本|製作|ゲスト|ナレーター|MC|司会|プロデューサー|ディレクター)[)）]")` を追加
- `_split_performer()` 内で split 後に各 part へ `_ROLE_SUFFIX_RE.sub("", p).strip()` を適用
- 空文字になった part をフィルタ；dedup も保持順のまま実施

**教訓：**
- 人名文字列の split pipeline は「**区切り文字で分割 → 役割 suffix 除去 → trim → フィルタ空文字 → dedup**」の順で実施する。
- annotator が返す performers[] には事前に suffix 除去済みであるべきだが、既存データの migration スクリプトでも同様の pipeline が必要。

---

## 2026-05-15 — Admin reports 却下ボタン静默失敗（handleDismiss 缺 server action，commit `dbe8471`）

**問題：** Admin reports 頁面「却下」按鈕點擊後，spinner 出現又消失，報告狀態沒有變更為 `dismissed`，完全靜默——使用者無任何錯誤提示。

**根因：** `AdminReportsTable.tsx` 的 `handleDismiss` 直接使用 browser-side `supabase.from("event_reports").update(...)` 走 RLS，同時缺少 `.select("id")` 0-row 守衛與失敗反饋。`handleConfirm` 早已改為 server action（`confirmReport`），但 `handleDismiss` 未同步改造。JWT 過期或 RLS 阻擋時 Supabase-js 回傳 `{ error: null, data: [] }`，`if (!error)` 判斷通過但 DB 無任何更新，`router.refresh()` 後資料回滾，視覺上靜默。

**修復（commit `dbe8471`）：**
- 新建 `web/app/actions/dismiss-report.ts` server action，使用 server-side `createClient`（cookie session），含 `.select("id")` 0-row guard；失敗回傳 `{ ok: false, error: "..." }`
- `handleDismiss` 改為呼叫此 server action；`result.ok` 為 false 時顯示 `alert(result.error)` 

**教訓：**
- **`confirmReport` 和 `dismissReport` 必須成對升格為 server action**；遺漏任一方即存在 silent failure 風險。
- Admin client-side write + RLS = 0-row silent success 三合一陷阱（JWT 過期 / RLS 阻擋 / ID 不存在）；所有高風險 admin mutation 應優先走 server action，而非僅補 `.select("id")` 守衛。
- 新建 action 時立即對配對 handler 做同步檢查（例如 confirm 已改 → dismiss 必須跟上）。

---

## 2026-05-15 — iwafu location_address 地址無法抽取（address regex + official body text fallback，commit `ebe54b3`）

**問題：** iwafu 事件的 `location_address` 欄位多數為空；部分地址格式（如「渋谷区〇〇」缺少都道府縣前綴）無法匹配 regex，導致即使官方網站有完整地址也無法填入。

**根因 A（regex 過窄）：** `_ADDR_RE` 要求地址以 `東京都|北海道|大阪府|…|.{2,5}県` 開頭，但日本地址有時省略都道府縣直接寫市區（如 `渋谷区〇〇1-2-3`），因此無法匹配。

**根因 B（fallback 缺失）：** 舊版僅在 `main_text`（iwafu 頁面文字）搜尋地址；官方網站（`official_url` 抓到的頁面）包含更完整的地址資訊，但 `_fetch_official_organizer_info()` 只回傳 organizer + credits，未回傳 body text，無法二次搜尋。

**修復（commit `ebe54b3`）：**
- `_ADDR_RE` 改為：都道府縣 optional + `[市区町村]` required city/ward anchor，更廣泛匹配省略前綴的地址
- `_fetch_official_organizer_info()` 回傳值擴充為三元組 `(organizer, supplemental_text, body_text)`
- 主流程優先在 `main_text` 搜尋 `_ADDR_RE`；若無結果且有 `official_body_text`，fallback 再搜尋官方網站文字

**教訓：**
- **日本地址 regex 應將都道府縣設為 optional**；只有 `[市区町村]` 是可靠的必要錨點。
- 官方網站通常是地址的最可靠來源；爬取 `official_url` 後應同時保存 body text 供 address fallback 使用。
- function 回傳型別擴充（tuple 長度增加）後，**必須立即煙霧測試** (`py_compile` + 至少一次 dry-run)，確認所有呼叫點都已同步更新。

---

## 2026-05-15 — Admin AEO 集計カードが 1,000 件上限に頭打ち（commit `518b5a8`）

**問題：** `/admin/aeo` の Summary カード（Total Visits、Unique Visitors 等）が実際より少ない数字を表示していた。

**根因：** 旧実装が `.select()` で最大 1,000 行取得 → クライアント側で JS フィルタリングして件数を計算していた。PostgREST はデフォルト `max-rows=1000` で黙ってレコードを切り捨てるため、1,000 件超の場合に常に過小表示になっていた。

**修正（commit `518b5a8`）：** 6 つの Summary カードをそれぞれ `.select('id', { count: 'exact', head: true })` による専用 head-count クエリに置き換え（行データを取得せず count のみ）。並列実行で UX 劣化なし。Bot テーブルの割合表示は直近 1,000 件で十分なため従来ロジックを維持。

**教訓：** **集計カードは必ず `.select(..., { count: 'exact', head: true })` を使う。** PostgREST の `max-rows=1000` は silent truncation — `.limit(n)` を超えなくても 1,000 行でカットされる。クライアント側での件数計算は使ってはいけない。

---

## 2026-05-15 — performer multi-value 汚染 → performers[] 分割（commit `c4bd9e1`）

**問題：** 映画事件で `performer = "ジャッキー・チェン、ジェット・リー"` のように区切り文字付き複数人名が 1 フィールドに格納される汚染が存在。翻訳・表示ともに誤動作。

**根因：** annotator の GPT が複数人名をカンマ・読点・× 等で区切って 1 文字列に返すケースがあり、`performer` フィールドに書き込まれていた。`performers[]` への分割が実装されていなかった。

**修正（commit `c4bd9e1`）：**
- `annotator.py` に `_MULTI_SEP_RE = re.compile(r"[、,，×／/]")` 追加
- `annotate_pending_events()` — `performer` に区切り文字が含まれる場合は `performers[]` に分割し `performer/performer_zh/performer_en` を `None` にサニタイズ
- `enrich_person_names()` — B1 策略：既存 `performer` multi-value 汚染を `performers[]` に変換し `ja_to_info` で各名前を個別翻訳 → `performers_zh/performers_en` 生成
- `auto_qa.py` に 3 検知器を追加：
  - `auto_qa_performer_ai_translation_marker`（`performer_zh/en` に AI翻譯マーカー残留）
  - `auto_qa_performer_multi_value_pollution`（`performer` に区切り文字が残存）
  - `auto_qa_performer_zh_equals_katakana`（`performer_zh` が日本語カタカナのまま）
- `_oneoff_migrate_multi_performer.py`：既存 movie events の一括移行スクリプト（`--dry-run` / `--execute`）

**教訓：** **annotator が `performer` を返す際は必ず `_MULTI_SEP_RE` チェックを挟み、複数人の場合は `performers[]` に分割する。** `performer` は常に単人であるべき。auto_qa の performer 系 3 detector は今後の汚染を早期発見する監視網として機能する。

---

## 2026-05-15 — merged_into_event_id 循環 redirect 兩個循環修復（DB-only, 4 rows）

**問題：** `/zh/events/57642851-...` 頁面不停重載。

**根因：** `permanentRedirect()` 在 Next.js SSR 對 `merged_into_event_id IS NOT NULL` 無限觸發：`57642851↔c8e813ae`（二節點）+ `84cb3ff3→2117c91e→a04e7ebb→84cb3ff3`（三節點，跨電影作品誤合併）。

**修復（DB 更新 4 筆，無 code 變更）：**
- `c8e813ae` merged_into → NULL
- `57642851` merged_into → `4a8772ec`（cinemart_shinjuku canonical）
- `2117c91e` merged_into → NULL（台湾Filmake terminal）
- `a04e7ebb` merged_into → NULL（めぐる面影 × 台湾Filmake 跨作品誤合併清除）

**教訓：** Merger 執行後必須全庫掃描循環；`auto_qa` 加入 cycle check 是正確方向。跨電影作品的 merge 幾乎必然是 bug。

---

## 2026-05-15 — AbortSignal timeout 補齊 + handlePublish 0-row guard（commit `77fc092`）

**問題：** OCR 事件儲存並標注後 UI 卡在「標注中，請稍候…」或「儲存中…」，無法清除。

**根因 A：** `AdminEventTable.tsx` `handleSaveAndAnnotate` 中 `fetch("/api/admin/annotate-event")` 無 `AbortSignal.timeout`；Vercel gateway 截斷時 `await fetch()` 永遠 pending，`setAnnotating(false)` 不執行。

**根因 B：** `annotate-event/route.ts` OpenAI API call 無 `AbortSignal.timeout`；slow GPT response 超過 Vercel `maxDuration = 60` 觸發根因 A。

**根因 C：** `handlePublish` Supabase UPDATE 缺 `.select("id")` + 0-row guard；JWT 過期時 `setSaving(true)` → UPDATE 0 rows → `setSaving(false)` 路徑未走 → 按鈕永遠卡著。

**修復：** commit `77fc092` 三行修改：
1. `handleSaveAndAnnotate` fetch 加 `signal: AbortSignal.timeout(58000)`
2. OpenAI fetch 加 `signal: AbortSignal.timeout(25000)`
3. `handlePublish` 改用 `.select("id")` + 0-row guard + 提示訊息

---

## 2026-05-15 — kawasaki_ac 日期解析不足與內容薄文本污染導致 selection_reason 矛盾

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**

2026-05-15 | kawasaki_ac 系列事件被收錄但日期、價格、上映時段、主辦方等欄位缺失；annotation 產出拒絕理由「未提供台灣相關資訊」卻 is_active=true（矛盾）。 | 1) detail page 抽取只取前 N 個 `<p>`，導致導航文字（TOP、施設案內...）污染 raw_description，使 GPT 吃不到作品介紹與欄位標籤。2) 日期 regex 僅支援 `M.D～M.D` 與 `M/D(土)` 格式，無法解析 `YYYY年M/D(土)～` 或單日 `M/D(土)` 格式。3) annotator 的 selection_reason 只是文案欄位，不會反向驅動 is_active 開關；拒絕理由與 is_active 無強制一致性。 | 1) detail page 改為內容區塊優先（detail-root + table.theater-detail 標籤欄位），抽取「開催日時」「作品紹介」「作品情報」「上映日」「料金」「公式サイト」等結構化段落；2) 日期 regex 擴充支援 YYYY年M/D(土)～、M/D(土)～、M.D～M.D 與單日結束日邏輯 end_date=start_date；3) 補齊上映時間、價格、官方連結、主辦方提取邏輯；4) 針對目標事件 re-annotate，確認 selection_reason 與 is_active 一致。 | 1) scraper raw_description 薄文本或噪音污染是 annotator 誤判的主因，修復應從 source 端結構化敘述開始，不要期望 GPT 從垃圾文本反推；2) 系列型改動（如日期格式擴充、欄位新增）要同時更新 raw_description 編排與相關提取邏輯，避免混亂；3) selection_reason 是文案用欄位，不是守門開關——若要「拒絕判定」真正動作，必須明確在來源抽取層或 annotator 層驅動 is_active，或明確由人工鎖定；純文案矛盾不會自動生效。

---

## 2026-05-15 — ReportSection submit 按鈕 loading 狀態文字換行導致錯位

**問題：** 使用者按下「問題を報告」彈窗的 Submit，按鈕切換為 `送信中…` 後，submit 按鈕與 Cancel 文字連結出現垂直錯位（日語截圖清晰可見「中…」被分成兩行）。

**根因：** 日語斷行規則允許在 `…`（U+2026，HORIZONTAL ELLIPSIS）前斷行。按鈕沒設 `whitespace-nowrap`，所以 `送信中…` 可能在 `…` 前換行，使按鈕高度從 `1 行` 變 `2 行`，導致相鄰 Cancel 按鈕在 flex row 中垂直位移。

**修正：** `web/components/ReportSection.tsx` submit 按鈕加 `whitespace-nowrap min-w-[4.5rem]`。  
`whitespace-nowrap` 防止日語斷行；`min-w-[4.5rem]` 鎖定最小寬度，避免 idle ↔ loading 切換時 flex 容器寬度抖動。

**教訓：**
- 日文按鈕文字含 `…` 時**必須加 `whitespace-nowrap`**；`…` 在 CJK 排版中是合法斷行點。
- 狀態切換時按鈕文字長度改變（`送信` → `送信中…`）會引發 flex 容器寬度變化，加 `min-w-[N]` 可消除排版抖動。

---

## 2026-05-15 — AdminEventTable 警告列在 dark mode 顏色過亮

**問題：** 未指派 work 的事件列在 dark mode 下顯示鮮豔粉紅（`bg-red-50` = `#FEF2F2`，固定明亮色），與深色 UI 背景嚴重對比。

**根因：** `bg-red-50` 是 Tailwind 靜態 utility，不響應 dark mode。沒有對應的 `dark:bg-*` override。

**修正：** 改為 `bg-blush hover:bg-[#FFE4E0] dark:hover:bg-[#35231f]`。  
`bg-blush` = CSS variable token（light `#FFF1EE` / dark `#2a1f1d`），自動隨 `:root.dark` 切換。

**教訓：**
- 警告色或狀態色 **永遠用語意 token（`bg-blush`、`bg-amber-*`）而非 Tailwind 靜態 light-only class**（`bg-red-50`、`bg-yellow-50`），否則 dark mode 一定爆。
- 需要 hover 變化時，token 本身不提供 hover 值，要在 JSX 加 `hover:bg-[hex] dark:hover:bg-[hex]` 手動指定。

---

## 2026-05-15 — getEventPerformer 不支援 performers_zh array，單人表演者顯示空白

**問題：** 部分活動有演出者，但前端 EventCard 顯示演出者欄位空白。

**根因：** annotator 寫入的欄位為 `performers_zh`（陣列），而 `getEventPerformer()` 只讀 `performer_zh`（舊版字串欄位）。當 annotator 寫新欄位但 scraper 未填舊欄位時，函數回傳 `undefined`。

**修正：** `web/lib/types.ts` `getEventPerformer()` 加入 fallback 順序：
`performer_zh` → `performers_zh[0]` → `performer_en` → `performers_en[0]`。

**教訓：**
- 增加新陣列欄位（`performers_zh[]`）時，必須同步更新所有讀取舊字串欄位（`performer_zh`）的 helper，否則過渡期 DB 中僅有新欄位的事件在前端靜默空白。
- `getEventPerformer` 等 helper 應以 `老欄位 → 新欄位[0]` 的方式保持向後相容，而非直接替換。

---

## 2026-05-15 — 後台 events UPDATE 三項操作同時靜默失效（Vercel 滾動部署期間 expired JWT）

**問題：** 使用者報告後台事件清單管理頁的 toggle（is_active）、work 指派、AI 報錯 checkbox 三項全部 click 後無反應；無 alert、UI 看似不動，重新整理或等 5–10 分鐘後自動恢復。

**根因鏈：**
1. 24h 內推 5 個 commit（含 `ae9dc77` auth callback 改寫）→ Vercel 滾動部署。
2. 瀏覽器持有的 access token 在新部署 edge node 下短暫無效 → PostgREST 收到 expired JWT 退回 anon role。
3. RLS `Admins update events` policy 對 anon 過濾為 0 列。
4. **PostgREST 0-row UPDATE 不視為 error** → supabase-js 回傳 `{ error: null, data: undefined }` → `IsActiveToggle` / `AdminEditClient` / `AdminEventTable.handleSaveWork` 三處的 `if (!error)` 全部判定為成功，但 DB 實際未變動。
5. middleware 下次刷新 access token 後自動恢復。

**驗證證據（DevTools 三點檢查）：** 使用者實測確認 Network PATCH 請求 `authorization: Bearer ...` 已存在、Response body 為空陣列 `[]`、cookie `sb-*-auth-token` HttpOnly 未勾 → 排除結構性 bug（cookie / session storage / GRANT 缺失皆非）。

**修正：** 未動程式碼，等待自然恢復。但補上預防性規則於 SKILL.md「Supabase Client UPDATE — 0-row Silent Success Guard」段落：所有 client-side UPDATE 必須加 `.select("id")` 並檢查 `data.length === 0` 作為失敗 alert 條件。

**教訓：**
- `supabase.from(T).update(...).eq("id", x)` 在以下三種情況都回傳 `error: null` + 空 data：RLS 過濾、JWT 過期、id 不存在。三者無法靠 `error` 區分。
- Vercel 滾動部署 + auth 相關 commit 是 expired JWT 的高風險組合，必須在客戶端寫入路徑加 0-row guard 防使用者誤判。
- 不可只用 `if (!error)` 判斷 admin 寫入成功；要嘛 `.select("id")` 後檢查列數，要嘛改走 server action / route handler 用 service role 寫入。

---

## 2026-05-15 — matsumoto_cinema_select スクレーパー実装での3つの修正

**エラー1:** `MatsumotoCinemaScraper` → CLI key が `matsumoto_cinema`（`--source matsumoto_cinema_select` で "Unknown source"）  
**修正:** クラス名を `MatsumotoCinemaSelectScraper` に変更（`_scraper_key` はクラス名から snake_case を派生させる）  
**教訓:** SOURCE_NAME にアンダースコア複合語を含む場合、クラス名も完全一致させる（`MatsumotoCinemaSelectScraper` → `matsumoto_cinema_select`）。

**エラー2:** `lookup_movie_titles()` 戻り値を `name_zh, name_en` の2値で受けたが実際は3値  
**修正:** `name_zh, name_en, name_ja_override = lookup_movie_titles(...)` に変更し `name_ja=name_ja_override` を Event に渡す

**エラー3:** `Event(location_prefectures=[...])` — `location_prefectures` は Event dataclass に存在しないフィールド  
**修正:** 削除。新フィールド追加前に `base.py` を確認する。

---「送信沒反應」其實是回饋不明確 + 例外未保底

**問題：**
- 使用者在活動頁「問題を報告」彈窗勾選後按「送信」，主觀體感是「完全沒反應」。

**根因：**
- 送出中按鈕只顯示單一字元 `…`，缺少明確語意（看起來像沒觸發）。
- `handleSubmit()` 只處理 Supabase 回傳 `error`，沒有 `try/catch` 包住非預期例外；例外發生時 UI 狀態可能停在不清楚狀態。
- 按鈕未明確設 `type="button"`，在複雜容器結構下可維護性較差、易產生預設 submit 行為歧義。

**修正：**
1. `web/components/ReportSection.tsx` 的 `handleSubmit()` 改為 `try/catch` 包裹，確保任何例外都會落到 `status="error"`。
2. 送出中狀態改為具語意文案（ja: `送信中…` / en: `Sending...` / zh: `送出中…`）。
3. 彈窗內所有操作按鈕明確加 `type="button"`，送出按鈕補 `aria-busy`。

**驗證：**
1. Browser 重現：打開事件頁報告彈窗，勾選一項後送出，成功時出現 `✓ ご報告ありがとうございます！`。
2. 程式驗證：`get_errors` 檢查 `ReportSection.tsx` 無錯誤。

**教訓：**
- 使用者回報「按了沒反應」時，不只要查 API 成敗，也要先補齊可視化的 loading/error 回饋。
- 任何 client-side submit handler 都應採 `try/catch + 明確狀態機`，避免非預期例外造成靜默失敗體感。

## 2026-05-15 — MascotAvatar 天線動畫 FOUC 白光球（左上左下）

**問題：**
- 首頁吉祥物天線動畫新增 `radialGradient` 圓環後，頁面重整時左上與左下各出現「白光球」殘影。

**根因：**
- CSS animation 在瀏覽器第一次 paint 前有單幀 FOUC（Flash Of Unstyled Content）：
  - `lianbu-antenna-flow-dot`（白色圓圈 `fill="#FFFFFF"`）初始座標在天線入體處 `cx=100 cy=80`（「左下」），CSS animation `opacity: 0` 的 0% keyframe 尚未生效，元素以 SVG `fillOpacity="0.85"` 全顯。
  - `lianbu-tip-ring`（tip ring 圓圈）新版改用 `fill=url(#radialGradient)` 卻沒設 inline `opacity="0"`，CSS animation 尚未啟動前以 `opacity=1` 渲染梯度（「左上」）。
  - `lianbu-antenna-flow-line`：CSS rule 有 `opacity: 1`，動畫前以全不透明渲染流光線。
- 改成 radialGradient 之前，tip-ring 用 `fill="none" stroke="#1F5E2B"`，FOUC 無視覺影響；改成 fill 後才暴露問題。

**修復：**
1. `MascotAvatar.tsx`：flow-dot 加 `opacity={0}` SVG attr；tip-ring gradient 版本加 `opacity={0}` SVG attr。
2. `globals.css`：`[data-antenna-flow="on"] .lianbu-antenna-flow-line` 的 `opacity: 1` 改為 `opacity: 0`。

**教訓：**
- SVG 元素套 CSS animation 控制 `opacity` 時，**務必在 SVG 屬性層設 `opacity="0"`**（或在 CSS 元素規則設 `opacity: 0`），避免動畫開始前的單幀全顯 FOUC。
- 把視覺狀態從 `fill="none" stroke=...` 改成 `fill=url(#gradient)` 時，必須同步確認 baseline opacity 不為 1。
- `overflow="visible"` 的 SVG + `fill=gradient` 的元素在 FOUC 期間會以 opacity=1 出現在其 DOM 基底座標，可能超出 SVG bounding box 顯示在頁面意外位置。

---

## 2026-05-15 — asahiculture 系列欄位缺漏，需一次性補值 + scraper pipeline 固化

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-15 | `asahiculture` 系列事件出現 `performer`、`location_address`、`business_hours`、`official_url`、`is_paid`、`price_info`、`organizer_type` 與部分 `end_date` 缺漏或不一致，且 source key/source_name 容易混淆。 | detail page 有多種變體（講師區塊有時在 `h3`，有時僅在頁首行）、費用字串格式不固定（含/不含括號描述）、地址欄位來源不穩；手動補值未同批寫入 `field_corrections` 會在 re-annotation 被覆寫。 | 1) 批次補值 `source_name=asahiculture` 事件並同步 upsert `field_corrections`；2) 日期欄位回寫後成對鎖定 `start_date` + `end_date`；3) 強化 `scraper/sources/asahiculture.py`：單日課程 `end_date=start_date`、固定 `organizer_type=['cultural_institution']`、`official_url=detail_link`、費用 regex 支援 `会員（...）`、講師抽取加入 header fallback、教室地址加入 fallback map。 | 朝日教室屬於模板頁變體來源，必須在 scraper 內做多路徑抽取；系列型手動補值必須與 FC 鎖定同批執行，且日期欄位要成對鎖；操作時要明確區分 dry-run key `asahi_culture` 與 DB `source_name=asahiculture`。

## 2026-05-15 — LINE 發送失敗仍被標記 published（假發布）

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-15 | 後台週報顯示已發布（非草稿），但 LINE 實際未收到訊息。 | `web/app/api/admin/weekly-broadcast/send/route.ts` 在 LINE multicast 失敗後仍無條件更新 `published_at` 與 `social_status.line.status=published`，造成「假發布」。 | 1) send route 新增 per-language 失敗收集（`failedLangs`）；2) 任一語系失敗即回 502，且不更新 published 狀態；3) 有訂閱者但 `sent_to=0` 也回 502 並保留草稿；4) 將受影響公告（`weekly-2026-05-15`）手動回退為 draft（`published_at=null`、`social_status.line.status=draft`）。 | 「發布狀態」必須由「送達成功」驅動，不可先發布後容錯。只要外部通道送達失敗，內容必須維持 draft，並回傳可觀測診斷（失敗語系與 subscriber_count）。

**驗證：**
1. app request 語境：send route 失敗分支回 502，回應含 `error`、`sent_to`、`subscriber_count`，且公告保持 draft。
2. SQL / service-role 語境：直接讀取 `announcements` 確認目標 slug 的 `published_at` 已回到 null、`social_status.line.status` 為 `draft`。

## 2026-05-15 — LINE 手動發送顯示 0 位訂閱者（RLS 權限語境誤用）

**問題：** 後台「立即發送週報」成功訊息顯示 `已發送給 0 位訂閱者`，但實際上已有訂閱者。

**根因：** `web/app/api/admin/weekly-broadcast/send/route.ts` 用 `@/lib/supabase/server`（anon key + user session）查 `line_subscribers`。該表在 `069_explicit_grants.sql` 屬 service-role only（RLS deny-all for authenticated），因此 API 讀取到空集合。

**修正：**
1. 保留 `requireAdmin()` 做身份驗證。
2. 新增 service-role client（`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`）專門查 `line_subscribers`。
3. 在 API response 加上 `subscriber_count`（zh/ja/en/total）作為運維診斷欄位。

**驗證（雙語境）：**
- app request 語境：檢查 `/api/admin/weekly-broadcast/send` 路由邏輯已改成 service-role 查詢，並在回應帶出訂閱者統計。
- SQL Editor / service-role 模擬語境：以 service role 查 `line_subscribers` active count，結果 `active_total=9`，證明不是「真的 0 人」。

**教訓：**
- 「後台 admin API + 受保護表」是兩階段權限問題：`user_roles` 只決定誰可呼叫 API，不等於該 API 有權讀所有表。
- 只要目標表是 service-role only，route handler 必須採「admin auth + service-role DB client」分層模式，不能直接沿用 SSR cookie client。

## 2026-05-15 — V-M-D 前遇到 dirty tree，必須先做提交範圍確認

**問題：** 使用者要求直接執行完整 Validate/Merge/Deploy，但工作樹同時存在多個與本次修復無關的變更（包含已修改與未追蹤檔案）。若直接 rebase/commit，容易把不相關變更一起推上 `origin/main`。

**根因：** 部署流程容易把「可以執行 git 操作」誤當成「可以安全提交」。缺少「提交範圍確認（scope gate）」會讓 V-M-D 在 dirty tree 狀態下誤打包。

**修正：** 在 V-M-D 前加入強制前置檢查：
1. `git status --short` 檢查 dirty tree。
2. 若存在不相關檔案，先停止流程並要求使用者明確選擇提交範圍（僅本次修復 / 全部變更）。
3. 範圍確認後才進入 `fetch/rebase/commit/push`。

**教訓：**
- V-M-D 的安全前提不是「沒有衝突」，而是「提交範圍已明確且經使用者確認」。
- dirty tree 不是阻止部署的錯誤，而是必須先處理的決策點。

## 2026-05-15 — Tester FAIL: pytest 匯入失敗 + annotator `--dry-run` 仍寫 DB

**問題：**
1. `cd scraper && pytest tests/test_single_day_end_date_guard.py -q` 報 `ModuleNotFoundError: No module named annotator`。
2. `python annotator.py --id <eid> --dry-run` 仍觸發 `events` PATCH 與 `scraper_runs` POST。

**根因：**
1. 測試執行時未保證 `scraper/` 在 `sys.path` 前段，`from annotator import ...` 在部分環境會失敗。
2. CLI 有解析 `--dry-run`，但沒有把 flag 傳入 `annotate_pending_events()`；函式內也無 dry-run 寫入封鎖。

**修正：**
1. 新增 `scraper/tests/conftest.py`，將 `scraper/` 目錄加入 `sys.path`。
2. `annotate_pending_events(..., dry_run: bool = False)`：
  - 主事件 `events.update`
  - localized 欄位更新
  - sub-event upsert/update
  - `location_prefectures` 更新
  - error 狀態回寫
  - `scraper_runs` insert
  全部在 dry-run 改為 log only。
3. CLI 主入口把 `dry_run_flag` 傳入 `annotate_pending_events()`。

**教訓：**
- `--dry-run` 必須「從 CLI 參數一路 thread 到實際 I/O 呼叫點」才算成立；僅解析旗標但未傳遞，等同沒有 dry-run。
- 針對 script-style 模組（如 `annotator.py`）的單元測試，應在 `tests/conftest.py` 顯式設定 import path，避免依賴 shell 當下的工作目錄。

## 2026-05-15 — 單日活動 `end_date` 回歸多日值，需以程式守衛 + FC 成對鎖雙重修復

**問題：** 事件 `2cae572a-1024-493a-93ad-74ade21246dc` 的 `start_date=2026-04-06` 但 `end_date` 漂移為 `2026-05-04`，違反單日活動規則。

**根因：** 既有邏輯只在 `end_date` 為 null 時補 `start_date`，未處理「可判定單日但 GPT/資料回寫成跨日」的情境；同時 `field_corrections.end_date` 曾被鎖成 `null`，讓回寫保護失效。

**修正：**
1. 在 `annotator.py` 新增 `_apply_single_day_end_date_guard()`，僅在「可安全判定單日」時強制 `end_date=start_date`，多日/未知情境不改。
2. 守衛套用在 parent event 與 sub-event 寫入前。
3. DB 一次性修復該事件：`events.end_date` 改為 `2026-04-06T00:00:00+00:00`。
4. `field_corrections` 成對 upsert：`start_date`、`end_date`（並保留 `business_hours` 鎖）。

**教訓：**
- 單日規則不能只靠 prompt，必須在寫入前有 deterministic guard。
- 日期欄位修復必須同步維護 FC pair lock（`start_date` + `end_date`），否則 re-annotation 會再次漂移。

## 2026-05-15 — 手動修正 event 欄位時 `organizer_type` check constraint 報錯

**問題：** 修正 event `1334fc96`（朝日カルチャーセンター 立川サテライト）時，設 `organizer_type: ['private_company']`，Supabase 回傳 `APIError: new row violates check constraint "events_organizer_type_check"`，整筆 update 全部 rollback。

**根因：** `events` 表對 `organizer_type` 陣列元素有 check constraint，僅允許特定枚舉值。`private_company` 不在允許清單內。

**修正：** 改用 `['cultural_institution']`（朝日カルチャーセンター 為文化教育機構）後 update 成功。

**合法 `organizer_type` 值（截至 2026-05-15）：**
`academic` / `civic_group` / `commercial_brand` / `cultural_institution` / `government` / `independent_venue` / `media` / `semi_official` / `unknown`

**教訓：** 手動 DB update 前，先用下列指令確認當前合法值，避免整筆失敗：
```bash
python3 -c "
import os,json; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('scraper/.env')
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
vals = set()
for row in sb.table('events').select('organizer_type').limit(500).execute().data:
    for v in (row.get('organizer_type') or []):
        vals.add(v)
print(sorted(vals))
"
```

---

## 2026-05-15 — Agent handoff `send: true` 雙向互觸造成無限迴圈

**問題：** 每次跑完 V-M-D → Update History → V-M-D → Update History…永不停止，使用者無法中斷。

**根因：** `validate-merge-deploy.agent.md`（V-M-D → Update History）與 `update-history-agent.agent.md`（Update History → V-M-D）兩個 handoff 都設了 `send: true`。V-M-D 完成 docs commit 後，自動觸發 Update History；Update History 完成後，又自動觸發 V-M-D；如此循環。

**修正：** 移除 `update-history-agent.agent.md` 中「🚀 Validate, merge & deploy」handoff 的 `send: true`，改為手動點擊。V-M-D → Update History 保留 `send: true`（部署後自動記錄是合理的），但反向不可自動觸發。

**教訓：** 若 A → B 設有 `send: true`，B → A 的 handoff 絕對不可再設 `send: true`，否則形成無限迴圈。每個「會產生 commit」的 agent 結尾都可能再觸發 Update History，而 Update History → V-M-D 的 `send: true` 只要存在就必然循環。

---

## 2026-05-15 — 發現 agent 和 SKILL.md 內的建構指令錯誤（`npm run build` 應為 `pnpm run build`）

**問題：** V-M-D agent、engineer SKILL.md、engineer history.md 均寫 `npm run build`，但此專案使用 `pnpm`。

**根因：** Agent 和文件建立時尚未明確將 pnpm 定為建構工具，後續修改未同步欄位。

**修正：**
- `validate-merge-deploy.agent.md` Step 3：`npm run build` → `pnpm run build`，加入 dev server pre-flight（kill port 3000 + rm -rf web/.next）
- `engineer/SKILL.md` 「後台壞掉了」排查清單第 2、3 項：`npm run build` → `pnpm run build`
- `engineer/history.md` zombie build 條目的程式片段：`npm run build` → `pnpm run build`

**教訓：** 建構指令是專案級規格，**不可將 npm/pnpm/yarn 視為同義詞**。`package.json` 對處有 `packageManager: pnpm@...` 字段為權威来源。新增任何 agent 文件、SKILL.md、history.md 內容沿用建構指令前，先執行 `cat web/package.json | grep packageManager` 確認包管理器。

## 2026-05-15 — zombie `next build` 程序封鎖 validate 流程

**問題：** 執行 `npm run build` 時出現 `⨯ Another next build process is already running`，無法重試。

**根因：** 一個早先在背景啟動的 `next build` 程序（pid 52644，4:41AM 啟動）從未結束，`next build` 的 lock 機制偵測到仍在跑就拒絕新啟動。

**修正：**
```bash
# 1. 找到殘留 build 程序
ps aux | grep "next build" | grep -v grep
# 2. 強制終止
kill -9 <pid>
# 3. 等 2 秒後重試
sleep 2 && pnpm run build
```

**教訓：** validate 流程在執行 `pnpm run build` 前，應先確認沒有殘留 build 程序。若 build 失敗並提示 `already running`，先 `ps aux | grep "next build"` 找 pid，`kill -9` 後再重試，不要刪 `.next/` 目錄（那是 cache，不是 lock）。

## 2026-05-15 — CI web-darkmode-smoke 一直失敗（HTTP 500）

**問題：** `web-darkmode-smoke` workflow 自建立以來每次都失敗。`pnpm dev` 啟動後健康檢查對 `/zh` 發出 GET 一直收到 500。

**根因：** "Start Next.js app" 步驟沒有設任何 env vars。`NEXT_PUBLIC_SUPABASE_URL` 和 `NEXT_PUBLIC_SUPABASE_ANON_KEY` 在 CI 環境中為 `undefined`，`createServerClient(undefined, undefined, ...)` 在首頁渲染時拋出 → 500。此外，`pnpm dev` 不觸發 `prebuild` hook（prebuild 只在 `next build` 時執行），如果有路由 import 的檔案（如 `specs-snapshot.json`）不存在，也會 500。

**修正：**
1. 在 "Start Next.js app" 步驟加入 `env:` 區塊：`NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.SUPABASE_URL }}` 和 `NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_KEY }}`
2. 在 Start 前加入 "Generate specs snapshot" 步驟：`pnpm run build-specs-snapshot`
3. 健康檢查超時時自動 dump `/tmp/web-darkmode-smoke-next.log` 輔助排查

**教訓：**
- CI 啟動 Next.js dev server 時**必須**注入所有 `NEXT_PUBLIC_*` env vars；否則 Supabase client 拿到 `undefined` URL 導致 500。
- Repo secret 對應：`NEXT_PUBLIC_SUPABASE_URL = secrets.SUPABASE_URL`、`NEXT_PUBLIC_SUPABASE_ANON_KEY = secrets.SUPABASE_KEY`。
- `prebuild` 只在 `npm/pnpm run build` 時觸發，`pnpm dev` **不**觸發；CI 若有 build-time 生成的 JSON（如 `specs-snapshot.json`），需在啟動 dev server 前單獨執行 `pnpm run build-specs-snapshot`。
- 診斷 health check 500 時，優先 dump Next.js dev log（`/tmp/web-darkmode-smoke-next.log`）確認根因，而非盲目猜測。

## 2026-05-15 — CategoryThumbnail 呼叫端 props 介面不符（TS2322）

**問題：** `npm run build` 失敗；`npx tsc --noEmit` 顯示 3 個 TS2322 錯誤，位於 `page.tsx`、`EventListClient.tsx`、`EventCardMockup.tsx`。錯誤訊息：`Type 'string[] | null | undefined' is not assignable to type 'string[] | undefined'`。

**根因：** `CategoryThumbnail.tsx` 的介面已演進，但 3 個呼叫端仍用舊 API：使用不存在的 `seed` prop（應為 `id`）、不存在的 `size` prop（尺寸只能透過 `className` 控制）、並用 `as string[] | null | undefined` 型別轉換規避 null check。`next dev`（Turbopack）不做完整 TS 檢查，所以錯誤在開發期間無症狀。

**修正：** 三個檔案全部改用正確 API：`id={event.id}`、移除 `size` prop、`categories={event.category ?? undefined}`（null-safe，非強制轉型）。

**教訓：**
- **CategoryThumbnail 現行介面（永遠以 `web/lib/design/CategoryThumbnail.tsx` 為準）：**
  - `id: string` — 作為 PRNG seed（事件 ID）
  - `categories?: string[]` — **不接受 null**，必須用 `?? undefined`
  - `className?: string` — 唯一控制尺寸的方式（例：`"w-[108px] h-[108px]"`）
  - `forceMotifIdx?: number` — 可選，覆蓋 motif 選取
  - **無 `seed` prop、無 `size` prop**
- `next build`（webpack）做完整 TS 檢查；`next dev`（Turbopack）不做。介面修改後，呼叫端可能在開發期間無症狀，直到 CI/Vercel build 才炸。
- 修改 `CategoryThumbnail` 介面後必須同步搜尋所有呼叫端：`grep -r "CategoryThumbnail" web/`。

---

## 2026-05-15 — Sources 卡片樣式漂移 + 部署前 MM 漂移風險

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-15 | `/[locale]/sources` 在 light mode 卡片未統一 paper 底色，hover 也未對齊全站卡片規格；同輪部署驗證中發現同一檔案出現 `MM`（staged 與 working tree 不同版本） | Sources 列表沒有使用共用 `CARD_LINK` 樣式，仍保留頁面內自定義 class；部署前未檢查「同檔 staged/unstaged 漂移」導致驗證版本與實際提交版本可能不一致 | `web/app/[locale]/sources/page.tsx` 改用 `CARD_LINK` + `group-hover`（亮色固定 paper 底、hover 綠底綠字）；提交前對 `MM` 檔案先重新 `git add` 最新版本，再以 `git diff --cached` 確認最終提交內容 | 1) 清單型超連結卡片禁止重寫 hover/paper 風格，統一走 `web/lib/classNames.ts` 的 `CARD_LINK`。2) 任何部署流程在 commit 前必做 `MM` 檢查，避免「驗證的是 A、推上去的是 B」。

## 2026-05-15 — `end_date` 被 re-annotation 覆寫為 None（FC 鎖缺失）

**問題：** 事件 `b4d97c35`（GAGA 大阪上映会）在 2026-05-14 被再次 annotate，`end_date` 遭覆寫為 `None`。`start_date` 有 FC 鎖所以保留正確值，但 `end_date` 無 FC 鎖，被 annotator 的 `end_date = start_date` 自動補填邏輯或清空邏輯覆寫。

**根因：** 手動修正 `start_date` 時只補了 `start_date` 的 FC 鎖，忘記同時鎖 `end_date`。Annotator 在 re-annotation 時若 `end_date` 非 null，會以 `start_date` 覆蓋（`not fix_reviewed` 路徑下）；若有條件清空，則設為 `None`。

**修正：** 補回 `end_date = '2025-08-17T00:00:00+00:00'`，同時 upsert FC 鎖（`field_name='end_date'`）。

**教訓：**
- **手動修正日期欄位，start_date 和 end_date 必須同時 FC 鎖**。兩者是一組，缺一不可。
- 單日活動：`end_date = start_date`，同樣需要鎖定，不可省略。
- 判斷標準：活動標題含「x月y日」等具體日期→ end_date 設為同一天並 FC 鎖。

---

## 2026-05-14 - Admin 事件總數卡在 1000（Supabase 預設回傳上限）

**問題：**
Admin 首頁統計使用 `events.length`，資料來源是 `.from("events").select("*")`。
該查詢未分頁時受 Supabase 預設單次回傳上限影響，超過 1000 筆後會被截斷，導致「事件總數」長期停在 1000。

**修正：**
1. `web/app/[locale]/admin/page.tsx` 改為 `.range()` 分頁迴圈抓完整 events（每批 1000）。
2. 事件總數改為 `.select("id", { count: "exact", head: true })` 的 `totalEventsCount`，不再用 `events.length` 當總數。
3. `AdminEventTable` 改傳分頁彙整後的完整 events，避免列表也被截斷。

**教訓：**
在 Supabase 計數場景，禁止用未分頁 `select()` 的陣列長度代表總筆數。總數必須使用 `count: "exact"`；要拿完整資料時必須顯式分頁。

---

## 2026-05-14 - Tester FAIL: signalAnimation 退場不完整（首頁/元件/CSS 殘留）

**問題：**
Tester 回報 `signalAnimation` 功能仍在三層殘留：首頁呼叫參數、`MascotAvatar` prop 與動畫圖層、`globals.css` 的 `lianbu-*`/`data-signal-animation` 規則。

**修正：**
1. `web/app/[locale]/page.tsx`：移除 `<MascotAvatar ... signalAnimation />` 啟用參數。
2. `web/lib/design/MascotAvatar.tsx`：刪除 `signalAnimation` prop、inline variant 的動畫 defs/style/data-attribute，以及所有 `lianbu-*` 動畫圖層；保留 framed 變體不變。
3. `web/app/globals.css`：刪除整段 `data-signal-animation` selector 與 `lianbu-*` keyframes（含 reduced-motion 分支）。

**教訓：**
停用 UI 特效必須做「三層同步退場」檢查：呼叫端、元件 API、全域樣式。只改其中一層會造成功能假下線，實際仍可被啟用或殘留死碼。

---

## 2026-05-14 - MascotAvatar SVG ID generation triggered React purity lint

**問題：**
首頁吉祥物動畫實作在 `MascotAvatar.tsx` 使用 `Math.random()` 產生 SVG gradient/mask ID。`pnpm -C web lint` 觸發 `react-hooks/purity`：render 期間呼叫 impure function。

**修正：**
改用 `useId()` 產生穩定 ID，並在同檔把 framed variant 既有的 random ID 一併改為 `useId()`。

**教訓：**
React 元件 render 期間不得使用 `Math.random()`、`Date.now()` 等 impure API 建立 ID。需要唯一但穩定的 DOM/SVG ID 時，優先使用 `useId()`。

---

## 2026-05-14 — Tailwind v4 `@theme` 靜態解析：`bg-paper` 無法 dark mode（commits `3470e28`, `a2b558c`）

**問題：**
`CARD_LINK` 使用 `bg-paper dark:bg-paper` 作為預設底色，期望 dark mode 下卡片顯示深色 paper（`#262422`）。實際上 dark mode 下卡片仍顯示白色 `#FFFDF5`。

**根因：**
Tailwind v4 的 `@theme` block **在 build time 靜態解析** CSS 變數：
```css
@theme { --color-paper: #FFFDF5; }  /* build time baked in */
```
因此 `bg-paper` 被編譯為固定的 `#FFFDF5`（靜態常數），而非 `var(--color-paper)`。`dark:bg-paper` 雖然生成 `.dark\:bg-paper { background-color: var(--color-paper) }` 能用 CSS 變數，但 plain `bg-paper` 已是靜態值，`html.dark { --color-paper: #262422 }` 對它完全無效。

**修復：**
`CARD_LINK` 改為 `bg-[#FFFDF5]`（移除 `dark:bg-paper`）。  
`globals.css` line 378：
```css
html.dark .bg-\[\#FFFDF5\] { background-color: var(--color-paper); }
```
此 unlayered 選擇器在 runtime 將 `bg-[#FFFDF5]` 覆蓋為 `#262422`，正確實現 dark mode paper 底色。

**教訓：**
- Tailwind v4 `@theme` = build-time 靜態值，**不是** runtime CSS 變數代理。`bg-paper` 永遠是固定色，dark mode 切換對它無效。
- **Paper 背景 dark mode 正確寫法：只用 `bg-[#FFFDF5]`**（不加 `dark:bg-paper`），依賴 globals.css line 378 的 `html.dark` 覆蓋。
- 所有 `bg-paper` 的出現都應檢查是否需要 dark mode 支援；若需要，改為 `bg-[#FFFDF5]`。

---

## 2026-05-14 — Mermaid 架構圖自動縮放問題與修復（commits `e776fd5`, `75e4479`, `d321619`）

**問題：**
Architecture Explorer 中的 Mermaid 圖在顯示時文字過小、圖形被壓縮至不可讀。多次嘗試透過強制 inline width/min-width 修復均未達預期。

**根因：**
1. **`e776fd5`**：Mermaid 注入 `width:100%` 的 inline style 到 SVG，導致 wide diagrams 被壓縮。嘗試透過 viewBox 的 pixel width 強制覆蓋解決，但造成 overflow canvas 和 text overlap。
2. **更根本問題**（`d321619`）：`ArchitectureFlowExplorer.tsx` 建構圖表時把全部 90 個 base nodes 都加入，即使只選一個 flow，Mermaid 仍嘗試在同一 canvas 渲染全部節點，造成圖形過大後被極度縮放。

**修復：**
- `75e4479`：revert Mermaid.tsx 到 pre-width-overrides baseline，消除多次 patch 的副作用。
- `d321619`：`ArchitectureFlowExplorer.tsx` 改為只渲染所選 flow 的 steps 對應節點（with virtual fallback nodes），而非預加載全部 base nodes。stats panel 仍顯示總 node/action/flow 數。

**教訓：**
- Mermaid 圖太小/不可讀的**根本原因通常是資料量**，不是 CSS 設定。先確認圖中節點數量，再考慮 CSS 修復。
- `width:100%` inline style 問題若不能從 data 層解決，應 revert 到已知正常狀態，不要疊加多層 CSS hack。
- `git revert` 到 baseline 再從 data 層修才是正確策略（先 revert，再 fix root cause）。

---

## 2026-05-14 — Card-link hover 統一化：classNames.ts + group-hover 箭頭修復（commits `199e331`, `ed0d200`, `0efc5dd`）

**問題：**
全站卡片型連結 hover 樣式分散各處，沒有統一規格，且缺少 dark mode：
- `events/[id]/page.tsx` 部分連結用 `hover:bg-green-50`（無 dark mode）
- `announcements/[slug]/page.tsx` 用 `hover:bg-green-50 hover:text-green-700`（無 dark mode）
- 箭頭 span（`↗`/`→`）有 `text-fg-subtle` class，**覆蓋父元素的 `hover:text-*`**，hover 時箭頭不跟著變色

**根因：**
1. Tailwind class 未集中管理，各頁面各自 copy-paste 且只處理 light mode
2. CSS 的 class 優先度問題：子元素上的 `text-fg-subtle` 比繼承的 `hover:text-*` 優先度高，hover color 不生效
3. Tailwind 的 hover utilities 基於「繼承」，但直接指定 text color class 會截斷繼承鏈

**修復：**
1. 新建 `web/lib/classNames.ts`，匯出兩個常數：
   ```ts
   export const CARD_LINK = "group flex items-center transition hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400";
   export const CARD_LINK_ARROW = "text-fg-subtle group-hover:text-[#1F5E2B] dark:group-hover:text-green-400 shrink-0";
   ```
2. `events/[id]/page.tsx` 5 個卡片連結全部改用 `CARD_LINK`/`CARD_LINK_ARROW`；`announcements/[slug]/page.tsx` 亦同
3. `CARD_LINK` 已包含 `group`（父元素不需再加）；`CARD_LINK_ARROW` 使用 `group-hover:` 方案繞過 CSS class 優先度問題

**教訓：**
- 重複使用的 Tailwind class 組合**必須**提取到 `web/lib/classNames.ts` 統一管理（hover pattern、常見按鈕樣式等）
- 子元素有直接 text color class 時，不可用父元素 `hover:text-*` 控制 hover 色；須改用 `group` + `group-hover:` 方案
- 所有 hover style 都需同時提供 dark mode（`dark:hover:bg-*` + `dark:hover:text-*`），否則暗色模式下 hover 時前景/背景色可能衝突

---

## 2026-05-14 — 「後台壞掉了」診斷：307 → /auth/login = 認證保護正常，非真正壞掉

**問題：**
用戶回報 `https://tokyotaiwanradar.com/ja/admin/specs/architecture` 壞掉（由 VMD "🔧 Fix issues found" handoff 觸發調查）。`curl -sI` 回傳 `HTTP/2 307 → location: /ja/auth/login`，看似頁面無法存取。

**根因：**
307 是 Next.js middleware 對未登入請求的正常 auth redirect，不代表頁面本身壞掉。深入調查確認：
- `tsc --noEmit` 通過、`npm run build` 成功（architecture 頁面正常列出）
- 近期 commit `171bea4`（punk Bauhaus OG image）確實引入 TS2873，但已在 `4d8b873` 修正，Vercel 部署已基於修正版本
- Production `/zh` HTTP 200、OG image 正常回傳（248KB）
- admin 頁面在登入狀態下可正常存取

**教訓：**
- 未認證的 `curl` 對 admin route 永遠得到 307 redirect，**不能作為「頁面是否壞掉」的判斷依據**。
- 「後台壞掉了」的正確診斷順序（見 SKILL.md — Admin 頁面「壞掉了」診斷流程）：
  1. `pnpm run build` 是否通過（TS error → Vercel build 失敗 → 舊版被保留）
  2. 近期 commit 有無 TS error（`git log -5 -- web/`）
  3. Production 非 admin 頁面是否 HTTP 200
  4. 若全部正常 → admin 只是需要登入，非真正壞掉
- OG image route (`opengraph-image.tsx`) 的 TS error 會導致**整個 Vercel build 失敗**，讓所有頁面看起來都「沒更新」，但 admin 特別顯眼因為 auth redirect 像錯誤。

---

## 2026-05-14 — OG Image `export const size` 只改單一維度導致空白下半部

**問題：**
`opengraph-image.tsx` 的 punk Bauhaus 重設計完成後，在一次局部還原中只把 `size.height` 從 `1200` 改回 `630`，但 SVG `viewBox`、所有幾何圖形座標與 ghost echo label 的絕對位置都是為 `1200×1200` 設計的，沒有同步更新。結果渲染出空白下半部（`630px` 以下全黑/空）。

**修正：** `git restore web/app/[locale]/events/[id]/opengraph-image.tsx`，回到完整的 `1200×1200` 版本。

**教訓：**
- `export const size = { width, height }` 不是單純的數值宣告；它同時決定 Satori canvas 與所有 SVG 元素的座標系。
- **任何對 `size` 的修改都必須在同一個 commit 裡更新全部相關座標**：SVG `viewBox`、`<rect>`/`<circle>` 的 `x`/`y`/`cx`/`cy`、ghost echo label 的 `top`/`right` 等。
- 永遠不要只改 `size.height` 或 `size.width` 而不改 layout。

---

## 2026-05-14 — VMD "問題未重現"（"Fix issues found" 觸發後全部 pass）

**問題：**
User 點 VMD agent 的 "🔧 Fix issues found" handoff 按鈕，提示詞為「部署驗證發現問題，請修復後重新部署。」但執行完整驗證（`tsc --noEmit`、`npm run build`、token gate、`curl Vercel`）全部通過，找不到任何問題。

**根因：** handoff 按鈕只是一個預設提示，不代表實際有問題存在。VMD 完成時可能就在正常狀態，使用者也可能誤觸按鈕。

**教訓：**
- 收到「請修復後重新部署」提示時，**先執行完整驗證**（`tsc`、build、token gate、Vercel curl），若全部 pass 就明確回報「問題未重現，目前狀態健康」，不要強行尋找不存在的問題。
- VMD agent 的 Step 3 應同時包含 `get_errors`（tsc）**與** `pnpm run build`，兩者缺一不可：tsc pass ≠ build pass（route handler 錯誤、missing file 等可以通過 tsc 但 build 失敗）。

---

## 2026-05-14 — `void` 運算符誤用為標記式運算式中歾（TS2873， commit `4d8b873`）

**問題：**
`opengraph-image.tsx` 在 punk Bauhaus 重設計時，將原有 `getEventName()` 呼叫改為歾碼形式 `void event ? getEventName(event as Event, locale) : undefined`。TypeScript 報 TS2873：`void` 運算符會把任何表達式轉為 `undefined`，所以 `void event` 永遠是 falsy，三元運算式的標記部分才是問題所在。

**修正：**
1. 刪除歾碼行（該行對實際用途沒有貢獻）
2. 移除不再使用的 import：`type Event`、`getEventName`

**教訓：**
- `void expr` 的語意是「評估 expr 然後丟棄結果」，返回內建的 `undefined`。刨3元運算符的**標記部分**前加 `void` 就變成 `undefined ? ... : ...`，永遠為 falsy。正確用法是 `const _ = expr` 或直接刪除。
- 重設計移除功能時，必須同步清除相關 import。不用的 import 不僅增加 bundle 大小，還會導致 TypeScript 報無用變數/import 警告。

---

## 2026-05-14 — session memory 路徑不存在 (`/memories/session/plan.md` → 實際在 `grandchild-event-analysis.md`)

**問題：**
User 要求「執行 `/memories/session/plan.md` 的計畫」，但該路徑不存在。正確的計畫文件是 `/memories/session/grandchild-event-analysis.md`（孫子事件分析與修復方案）。因為 session memory 只列出文件名而非完整路徑，導致初始查找失敗。

**修正：**
呼叫 `memory view /memories/session/` 列出目錄，找到唯一文件 `grandchild-event-analysis.md`，確認這就是計畫文件，並依其內容執行修復。

**教訓：**
- Session memory 的文件名由建立者決定，不一定叫 `plan.md`。每次被要求「執行計畫」前，**必須先 view `/memories/session/` 目錄**，確認實際文件名，不要假設路徑。
- 呼叫 session memory 前先 `view /memories/session/` 這個步驟應加入 Update History, Skill, Agent agent 的 Required Steps。

---

## 2026-05-14 — Validate, Merge & Deploy agent も handoffs 未設定（commit `b96ac15`）

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-14 | VMD agent 完了後もボタンが表示されず、次のアクションに進めなかった | `validate-merge-deploy.agent.md` に `handoffs:` が定義されておらず、デプロイ確認後の次ステップ（問題修正→Engineer、履歴更新→Update History）に一切移れない状態だった | frontmatter に 4 つの handoffs を追加（Fix issues found→Engineer `send:true` / Update history→Update History, Skill, Agent `send:true` / Plan next→Architect / Scraper work→Scraper Expert） | **ルール：新規 agent ファイル作成時は handoffs を同時に定義すること。** 「流程型 agent」（Validate/Update History 等）は次ステップへの導線がなければ人が詰まる。agent 作成チェックリストに「handoffs 定義済みか？」を必ず加えること。

---

## 2026-05-14 — `[data-preserve-theme='light'] .group:hover` に空白が入り descendant combinator になるバグ（commit `e3e391f`）

**問題：** ダークモード用の CSS 例外ルール
```css
[data-preserve-theme='light'] .group:hover h2 { color: forest; }
```
と書くべきところを空白を挟んで
```css
[data-preserve-theme='light'] .group:hover
```
と分離してしまい、「`[data-preserve-theme='light']` の**子孫**に `.group:hover` がある場合」という descendant combinator として解釈された。しかし `data-preserve-theme` と `group` は**同一要素**（`<Link>`）に付いているため、このルールは永久にマッチしない。

**修正（commit `e3e391f`）：** 空白を除去 → `[data-preserve-theme='light'].group:hover`（結合 specificity 0,5,1 で cacao lock 0,3,1 に勝てる）。

**教訓：**
- 属性セレクターとクラスセレクターを**同一要素**に適用するとき、間に空白を入れてはいけない。`[attr='x'].class` = 同一要素、`[attr='x'] .class` = 子孫要素。
- `data-preserve-theme` のような CSS テーマロック機構を使うとき、そのアトリビュートが付く要素とホバー対象が一致しているかを常に確認する。
- Playwright で `page.evaluate` → `window.getComputedStyle` を使うと hover 前後の色変化を 1 コマンドで検証できる。

---

## 2026-05-14 — QA 分診 PoC 上線後，LINE 指令閉環與修復邊界需要明文化

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-14 | Daily Health Check 只會報錯，不提供可執行修復入口，人工處理路徑不一致 | 既有流程缺少「分診（triage）」與「安全自修（safe auto-fix）」分層，LINE 訊息也沒有標準化 CTA | 新增 `qa_triage.py` + `qa_auto_fix.py`、新增 `qa-triage.yml`（11:00 JST）與 `qa-auto-fix.yml`（workflow_dispatch），並將 `QA Triage` 納入 failure notify 監控 | 自動化要分兩層：先分診再修復；高風險項（selector drift）永遠留給人工。LINE 訊息必須附明確下一步（workflow 名稱與觸發方式），否則提醒不會轉成行動。

---

## 2026-05-14 — Update History agent 完成後沒有 handoff 按鈕

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
2026-05-14 | 任務完成後無法一鍵切到「Validate, Merge & Deploy」或其他後續 agent | `update-history-agent.agent.md` 缺少 `handoffs` 定義，導致流程在文件更新後中斷，需要手動切換 agent | 在 frontmatter 補上 3 個 handoffs（Validate, Merge & Deploy / Scraper Expert / Researcher），並對部署 handoff 設 `send: true` 自動送出標準提示 | 對「流程型 agent」而言，handoff 不是 UX 附加功能而是工作流的一部分。凡是預期有下一步的 agent，交付前都要檢查 handoff 是否完整且可直達。

## 2026-05-14 — `annotation_status='error'` イベントが長期滞留（21件、6日間）

**問題：** annotator が GPT レスポンスの JSON パースに失敗すると `annotation_status='error'` にセットするが、annotator のクエリは `annotation_status='pending'` のみ対象にするため、error のまま放置される。daily_report は `.limit(5)` で取得するため「5件」と表示されていたが、実際は21件が6日間滞留していた。

**修正：**
```python
# 全 error イベントを pending にリセット
res = sb.table('events').select('id').eq('annotation_status','error').eq('is_active', True).execute()
ids = [r['id'] for r in res.data]
sb.table('events').update({'annotation_status': 'pending'}).in_('id', ids).execute()
# その後 python annotator.py を実行
```

**教訓：**
- `annotation_status='error'` イベントは annotator が自動リトライしない。定期的に `select ... where annotation_status='error' and is_active=true` でチェックし、手動または CI で `pending` にリセットする必要がある。
- daily_report が `.limit(5)` で表示する件数と実際の件数は一致しない。エラー件数は COUNT で別途確認すること。
- 薄い `raw_description`（1行のみ）の sub-event も、親イベントのコンテキストを参照することで正常アノテーション可能。

---

## 2026-05-14 — Supabase migration 069 の GRANT 設計漏れ（scraper_runs / research_reports / creators）

**問題：** migration `069_explicit_grants.sql` で以下の GRANT が不足していた：
- `scraper_runs`: `service_role` に `INSERT` を付与し忘れ（scraper/annotator が毎回 INSERT する）
- `research_reports`: `service_role` に `INSERT` を付与し忘れ（researcher agent が INSERT する）
- `creators`: `authenticated` に `INSERT/UPDATE/DELETE` を付与し忘れ（管理者が CRUD する）

**修正：** 069 適用後に補正 SQL を SQL Editor で追加実行：
```sql
GRANT SELECT, INSERT ON public.scraper_runs      TO service_role;
GRANT SELECT, INSERT ON public.research_reports  TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.creators TO authenticated, service_role;
```

**教訓：**
- GRANT 設計は「誰が書くか」を Python コードから逆引きして確認する。RLS ポリシーの存在だけを見て GRANT の scope を決めると書き込み用 GRANT が漏れる。
- `scraper_runs`, `research_reports` はスクレーパー/annotator/researcher が service_role で INSERT → **必ず service_role に INSERT を付与**。
- `creators` は管理者が admin UI から CRUD → **authenticated に CRUD を付与**。

---

## 2026-05-14 — `python-dotenv` CVE-2026-28684（symlink following via cross-device rename）

**問題：** `python-dotenv < 1.2.2` の `set_key()` / `unset_key()` が `.env` ファイルを symlink 経由で書き換える際、`/tmp` が別デバイスにある Linux 環境でクロスデバイス rename fallback (`shutil.copy2` → `shutil.move`) が発生し、任意ファイルを上書きできる（CVE-2026-28684、GHSA-mf9w-mj56-hr94、CVSS 6.6/Moderate）。

**このプロジェクトへの影響：** `set_key()`/`unset_key()` は一切使用していない（`load_dotenv()` のみ）→ 実際の攻撃リスクはゼロ。ただし Dependabot アラートをクローズするため予防的にアップグレード。

**修正（commit `3a18640`）：** `scraper/requirements.txt`: `python-dotenv==1.1.0` → `==1.2.2`

**教訓：**
- Dependabot アラートが来たら「このプロジェクトで脆弱な関数を呼んでいるか」を `grep -rn "set_key\|unset_key" scraper/` で確認してから優先度を判断する。
- `load_dotenv()` は本脆弱性の対象外（読み取り専用）。

---

## 2026-05-14 — `user-invocable: false` を handoff ターゲット agent に設定すると VS Code の handoff ボタンが表示されない（commit `6188653`）

**問題：** `update-history-agent.agent.md` と `validate-merge-deploy.agent.md` に `user-invocable: false` が設定されていた。この設定は「ユーザーが agent ピッカーから直接呼び出せない」だけでなく、**他 agent の handoff ボタンのターゲットとしても非表示になる**。結果として handoff ナビゲーションが機能しなかった。

**修正（commit `6188653`）：** 両ファイルから `user-invocable: false` を削除（frontmatter デフォルトは `true`）。

**教訓：**
- `user-invocable: false` は「サブ agent として parent からのみ呼び出す、ユーザーへは非表示」用途（例: `subagents/` 配下）にのみ使う。
- `handoffs:` に列挙するターゲット agent は **必ず `user-invocable: true`（デフォルト）のままにすること**。
- 判別基準: ユーザーが手動で呼び出す可能性があるか？ → あれば `user-invocable` は設定しない。純粋に親 agent の内部ステップか？ → `user-invocable: false` + `subagents/` 配下。

---

## 2026-05-14 — FilterBar `past` timeMode 切換後畫面不動

**問題（commit `2ed3c7b`）：**
`EventListClient.tsx` 的 `timeMode === "past"` 分支：當 `fromStr` 和 `toStr` 都為空時，沒有任何過濾邏輯執行，所有事件直接通過。使用者切換到「過去」模式後，畫面沒有任何變化，直到手動選擇開始日或結束日才生效。

**修正：**
`FilterBar.tsx` 中切換到 `timeMode === "past"` 時，若 `to` 為空，自動預填今日日期（`new Date().toISOString().slice(0, 10)`）並立即呼叫 `pushWith()`。切換到 `active`/`all` 時清空 `from`/`to`。

**教訓：**
- Client-side filter 的每個 mode 必須有明確的「預設過濾行為」。`past` 不能依賴使用者必須填日期——沒填時應 default 顯示「今天以前」的事件。
- 切換 filter mode 時，同步在 URL 預填合理的預設值（`to=today`），不要讓 EventListClient 自行猜測。
- **Pattern**: `mode switch → pre-fill sensible defaults → push URL → client filters immediately`。

---

## 2026-05-14 — merger.py Pass 4 `deactivated_by_pass` 標籤錯誤

**問題（commit `36ee77c`）：**
`_flatten_grandchild_events()` 在停用重複孫子事件時，呼叫 `_deactivate_payload()` 傳入 `"merger_pass_3"`（orphan pass 的 ID），而非 `"merger_pass_4"`（正確的 Pass 4 標籤）。導致 DB audit 欄位 `deactivated_by_pass` 顯示錯誤的 pass 來源。

**修正：**
1. `_deactivate_payload()` docstring 補上 `'merger_pass_4'` 為合法值
2. Pass 4 重複孫子事件停用改為 `pass_id="merger_pass_4"`
3. CLI print 語句由 `Pass 0+1+2+3+5` 改為 `Pass 0+1+2+3+4+5`

**教訓：**
新增 merger Pass 時，同步更新三處：(1) `_deactivate_payload()` docstring 的合法值清單；(2) 呼叫處的 `pass_id` 字串；(3) 末尾 `print()` 的 Pass 序號摘要。

---

## 2026-05-14 — Shell History Pollution / Prompt Injection via inline Python f-string

**問題：**
Terminal で inline Python（`python3 -c "..."`）を実行中、f-string 内の `{zh}` 変数参照が
シェル履歴の汚染コマンドに置換された：
```
{zh}  →  {zhrm -f "/Users/.../credentials/token.json"}
```
Python インタープリタが `{zhrm ...}` を未閉じブレースとして `SyntaxError` を発生させたため、
`rm` は実行されなかった（安全）。

**根因：** シェル履歴汚染（Shell History Pollution）— ツール出力や環境変数の値に悪意のあるコマンドが埋め込まれ、f-string の変数名と一致するとシェルによって展開される。

**修正：** 確認スクリプトを `/tmp/verify_xxx.py` ファイルに書き出してから実行することで回避。

**教訓：**
- Terminal で `python3 -c "..."` の f-string を使う場合、変数名がシェルコマンドと偶然一致するリスクがある。
- **確認スクリプトは `/tmp/` ファイルに書き出してから実行する**（シェル展開の影響を受けない）。
- このパターンを検出した場合はユーザーに Prompt Injection として警告し、`rm` が実行されていないことを確認する。

---

## 2026-05-14 — `user-invocable: false` 在 handoff target agents 造成 handoff 按鈕消失

**問題：** `update-history-agent.agent.md` 與 `validate-merge-deploy.agent.md` 的 YAML frontmatter 包含 `user-invocable: false`。VS Code 讀取此旗標後，不將這些 agents 列入可呼叫清單，導致其他 agent 設定的 `handoffs:` 按鈕完全不顯示。

**根因：** `user-invocable: false` 是給「純後台 subagent」用的旗標，防止它出現在 Agent Picker。但 handoff target 需要被 VS Code 辨識才能渲染 handoff 按鈕。兩者互斥。

**修正：** 從 `update-history-agent.agent.md` 和 `validate-merge-deploy.agent.md` 移除 `user-invocable: false`（預設為 `true`，可被 Agent Picker 找到，也可被 parent agent handoff）。

**教訓：**
- **Handoff target agents 禁止設 `user-invocable: false`**。這會讓 VS Code 把它們從 handoff 可解析清單移除，所有指向它的 handoff 按鈕都會靜默失效。
- Subagent（parent agent 透過 `agents:` list 呼叫、不出現在 Picker、不做 handoff 的）才應設 `user-invocable: false`。
- 判斷規則：**有沒有其他 agent 在 `handoffs:` 裡引用它？有就不能設 `user-invocable: false`。**

---

## 2026-05-13 — Supabase explicit GRANT rule（migration 069）
**新增：** `## Database` 段落新增 Supabase explicit GRANT 規則
**內容：**
- 2026-10-30 起，新建 table 若無 GRANT block 會 silent `42501` 錯誤
- 三種 Tier 模板（A:公開讀取 / B:admin-only / C:service_role）
- 指向 `database.instructions.md §GRANT template` 取完整範例
**來源：** daily-skills-review（Step 4 建議）

---

## 2026-05-13 - Flow Explorer set-state-in-effect lint regression


**問題：**
- `ArchitectureFlowExplorer.tsx` 用 `useEffect` 同步 `selectedActionId`/`selectedStep`，觸發 `react-hooks/set-state-in-effect`。
- `build-specs-snapshot.ts` 留下 `eslint-disable-next-line no-console`，在現行規則下變成 unused directive。

**修正：**
- 將 action 同步改為衍生狀態：新增 `hasSelectedAction`、`effectiveSelectedActionId`、`effectiveSelectedStep`，移除 effect 內同步 setState。
- `selectedFlow`、Mermaid `chart`、`<select value>`、step 高亮都改讀 effective 狀態，保留 action 切換與 steps 高亮行為。
- 移除 `build-specs-snapshot.ts` 兩個多餘的 `eslint-disable` 註解。

**教訓：**
- UI 同步條件若可由現有 state 推導，優先用衍生值，不要在 effect 內做同步式 setState。
- lint 規則更新後，舊的 disable 註解可能反而成為警告，修正時要一併清理。

---

## 2026-05-13 - ArchitectureFlowExplorer JSX arrow token parse error

**問題：**
- `ArchitectureFlowExplorer.tsx` 在 JSX 文字節點直接寫 `->`，TypeScript parser 於 `>` 位置拋出 `TS1382`。

**修正：**
- 將箭頭文字改為字串插值：`{" -> "}`，避免 JSX 對 `>` 的語法誤判。

**教訓：**
- JSX 內含 `>` 的純文字片段（例如箭頭）要用字串節點或 HTML entity，不要直接裸寫。

---

## 2026-05-13 - Lighthouse localhost canonical + homepage a11y regression

**問題：**
- Tester 在 `http://localhost:3000/zh` 回報 `select-name`、`label-content-name-mismatch`、`color-contrast`、`canonical`
- `FilterBar` 可見 label 沒有和 native form controls 穩定綁定
- category custom trigger 的 `aria-labelledby` 只指向外部 label，導致 accessible name 不包含按鈕可見文字
- locale layout 直接沿用 production absolute alternates，localhost Lighthouse 將 canonical 判定為「Points to another hreflang location」

**修正：**
- `FilterBar.tsx` 為 search/select/date controls 加入固定 `id` + `htmlFor`
- category trigger 的 accessible name 改為同時包含外部 label 與按鈕內可見文字
- `EventListClient.tsx` 與 `[locale]/layout.tsx` 將小字、badge、footer 從 `text-fg-subtle` / `text-fg-muted` 調整到更高對比的前景色
- `[locale]/layout.tsx` 在 localhost/127.0.0.1 request 下使用 request host 輸出 canonical，並省略 `alternates.languages`；deployed hosts 維持完整 hreflang + `x-default`

**教訓：**
- 自訂 trigger 若使用 `aria-labelledby`，必須把可見 trigger 文字一起納入 accessible name，否則會把 label 修正轉成 `label-content-name-mismatch`
- locale metadata 的 production hreflang cluster 可能讓 localhost Lighthouse 誤判 canonical；應以 localhost 專用 metadata 分支處理，不要為了本機驗證削弱 deployed canonical 行為

---

## 2026-05-12 — `lookup_movie_titles()` 回傳型別從 2-tuple → 3-tuple
**修改：** engineer/SKILL.md works pipeline 第 8 點
**內容：**
- `(None, None)` → `(None, None, None)`，明示 3-tuple 解包格式
- 補充「不可沿用舊 2-tuple 解包，會觸發 ValueError」警告
- 新增 `official_url` 為第三個回傳值（eiga.com jump link）
**來源：** daily-skills-review（Step 4 建議）

---

## 2026-05-11 — SC→TC 三層防禦修正（chokepoint guard + 偵測/修復一致性）

### A — `_lock_fields_via_corrections()` SC→TC guard 新增（commit `f7790a2`）

**問題：** `_lock_fields_via_corrections()` 用 `str(fvalue)` 直接寫入 FC 表，未過 `_to_trad()`。backfill 腳本的 kanji copy 將日文漢字（`会`=SC）永久鎖入 FC，annotator P1 保護阻止修正。

**修正（4 層）：**
1. `_lock_fields_via_corrections()` 新增：field name 以 `_zh` 結尾時，自動對 value 呼叫 `_to_trad()` 後再寫入 FC
2. `fix_simplified()` 從 2 欄擴展到 6 欄（`name_zh, description_zh, location_name_zh, location_address_zh, business_hours_zh, organizer_zh`）
3. Data fix：13 筆 taiwan_prism `location_name_zh`（紫明会館→紫明會館）+ 2 筆 inactive `name_zh`（萬博追踪→萬博追蹤）+ 39 筆 `organizer_zh` SC→TC 修正，全部 FC 鎖定
4. 全修正值均透過更新後的 `_lock_fields_via_corrections()`（含 `_to_trad()` guard）寫入

**教訓：**
- `field_corrections` 是永久資料閘門，SC 值通過後免疫於所有自動修復。`_to_trad()` guard 必須在此 chokepoint 設置。
- `fix_simplified()` 的掃描範圍必須與 `_detect_simplified_chinese()` 完全一致——後者掃 6 欄，前者也必須修 6 欄。

### B — `SC_ONLY` 假陽性 + `_SIMP_TO_TRAD_RAW` 缺映射（commit `aa24400`）

**問題：** `SC_ONLY` 含共用字元（征/蹈/零/蒙）→ 假陽性。`_SIMP_TO_TRAD_RAW` 缺 见→見/从→從/库→庫 → 偵測到但無法修復 → 無限 dismiss 循環。

**修正：**
1. 移除 `SC_ONLY` 中 4 個假陽性
2. 新增 `_SIMP_TO_TRAD_RAW` 3 個映射
3. Data fix：2 筆 gguide_tv `description_zh`
4. Dismissed 7 筆 stale pending 報告

**教訓：** 偵測系統（`SC_ONLY`）與修復系統（`_SIMP_TO_TRAD_RAW`）使用不同字元集時，必然產生假陽性或假陰性。兩者應從同一來源衍生。

---

## 2026-05-11 — annotator.py レポート記事 `report` category + 接頭辭 自動注入（commit `1e00933`）

**新機能（4 層実装）：**
1. `_REPORT_TRIGGER_RE`（module-level）：レポート・レポ・報告・記録・アーカイブ・recap・行ってきた・観てきた・見てきた・鑑賞レポ にマッチ
2. `_inject_report_prefix()`：`【レポート】`/`【活動報導】`/`[Report]` を name_ja/zh/en に prepend；None-safe、二重 prefix 防止チェック付き
3. `_inject_keyword_categories()`：`report` ルールを追加。`_REPORT_TRIGGER_RE` が raw_title + raw_description に一致したら `report` を categories に注入
4. `annotate_pending_events()`：`update_data` 確定後に `report` in category → prefix inject；FC ロック field はスキップ
5. `backfill_report_prefix(dry_run=False)`：既存 `report` category を持つ events への一括バックフィル。`field_corrections` の lock も同時更新

**教訓：**
- FC ロック field のスキップは `field_corrections` の keys を確認するだけで実装できる（`if field not in fc_keys`）
- バックフィルは必ず `dry_run=True` で影響範囲を確認してから `dry_run=False` を実行すること
- `start_date` / `location` の自動修正は実装しない——raw_description から機械的に正しい活動日・会場を特定する信頼できる方法がなく、誤修正リスクが高い
- **Superseded (2026-06-16)**: `_REPORT_TRIGGER_RE` の単独 `記録` は box-office「記録を更新中」等で false positive を起こすため、`活動記録|開催記録|鑑賞記録|記録[｜|]` の composite terms に精綻化。SYSTEM_PROMPT の report/recap 例外も同期。元の commit `1e00933` の振る舞い説明は変更しない。

---

## 2026-05-10 — OCR save-and-annotate pipeline + organizer_type DB 修正

### A — OCR save-and-annotate 完整流程（commit `71e8a67`）

**新增功能（4 層）：**
- **UI**（`AdminEventTable.tsx`）：OCR 成功後按鈕自動切換「儲存並標注」；儲存觸發 GitHub Actions；前端每 5 秒 poll；標注完成後表單自動補強、出現「🚀 公開發布」確認列；公開發布 → `is_active=true, annotation_status=reviewed`
- **API**（`/api/admin/enrich-and-annotate`）：Admin-only POST `{ eventId }` → 觸發 `enrich-and-annotate.yml` workflow
- **GitHub Actions**（`enrich-and-annotate.yml`）：Step 1 `enrich_ocr_event.py --event-id` → Step 2 `annotator.py`
- **Script**（`scraper/enrich_ocr_event.py`）：DuckDuckGo HTML 搜尋（無需 API key）→ Playwright 抓取前 8000 字元 → 評分選出最佳命中（score ≥ 2）→ 更新 `source_url / official_url / raw_description`

**環境需求：** `GITHUB_TOKEN` 需 `Actions: write` 權限（fine-grained PAT 或 classic `workflow` scope）。

**教訓：** GitHub Actions workflow_dispatch 觸發需要 Vercel 加 `GITHUB_TOKEN`（不是 CI 內部的 `secrets.GITHUB_TOKEN`）。沒有此 token 時 API 回傳 403，UI 的 poll 永遠不完成。

---

### B — 台湾国際放送 organizer_type 修正

**問題：** 事件 `df0e3f11`（台湾国際放送リスナーの集い）`organizer_type=['civic_group']`，實際上台湾国際放送（RTI）是台灣政府出資的官方對外廣播機構（相當於 NHK World / BBC World Service）。

**修正：** `organizer_type=['semi_official']` + FC 鎖定。查 Wikipedia 確認：台湾国際放送 = Radio Taiwan International（RTI），由中華民國政府出資，屬 `semi_official` 而非 `civic_group`。

**教訓：** 「リスナーの集い」等形式看似市民活動，但主辦方若為政府廣播機構，organizer_type 應為 `semi_official`。判斷時必須查主辦方的組織性質，不可只看活動形式。

---

## 2026-05-10 — TaiwanPrism scraper 啟用 + X auto-post 基礎建設 + 新 scraper 群

### A — TaiwanPrism scraper 啟用（commits `a3d67fc`, `c7e9b73`）

**內容：** 新建 `sources/taiwan_prism.py`，爬取京都紫明会館年度文化祭（台湾光譜）。
- 靜態 HTML 解析（不需 Playwright）；`wixui-repeater__item` 結構提取 12 個節目
- 父事件（整個節慶）+ 12 個子事件（個別節目）= 13 筆
- 首次 DB 寫入後手動 patch 子事件 `parent_event_id`（首次跑時父 UUID 尚未存在）

**修正記錄（DB 寫入 bug）：** null byte、`organizer_type`、`parent_event_id` 三重 bug — 詳見 scraper-expert history。

**教訓：** 首次執行含子事件的新 scraper 時，需規劃「第二次跑」或手動 patch `parent_event_id`，因為父事件在同批 upsert 中才剛插入。

---

### B — X (Twitter) auto-post 基礎建設（commit `6af7f9e`）

**新增功能：**
- `scraper/x_post.py`：從 Supabase 挑選未來 14 天活動，發 JST 日文推文（~255 字元）
- `workflows/x-post-cron.yml`：每日 08:00、12:30、20:00 JST 三次發文
- 選取策略：有 selection_reason + 已標注 + 無 parent_event_id；最近 60 天內已發過的排除（app_settings.x_post 追蹤）
- 支援 dry-run / manual event_id 覆蓋

**環境需求：** `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`（需加入 GitHub Actions Secrets）

---

### C — 4 個新 scraper scaffold + StartupTerrace（commits `f680cd4`, `7b031a7`, `78aaa0d`）

| 來源 | Class | 狀態 |
|------|-------|------|
| `cineplaza` | `CineplazaScraper` | 已啟用（`7b031a7`） |
| `internet_museum` | `InternetMuseumScraper` | 已啟用（`7b031a7`） |
| `onariza` | `OnarizaScraper` | 已啟用（`7b031a7`） |
| `us_cinema_chiba` | `UsCinemaChibaGekijoScraper` | 已啟用（`7b031a7`） |
| `startup_terrace` | `StartupTerraceScraper` | 已啟用（`78aaa0d`） |
| `whitestone_gallery` | `WhitestoneGalleryScraper` | 已啟用（`33b217c`） |

**Whitestone Gallery 特點：** 靜態 HTML、`/tagged/current` 清單頁；detail page 主內容關鍵字過濾（避免 footer 國家下拉的 false positive）；0 events = normal，加入 `ZERO_EVENT_OK_SOURCES`。

---

### D — Peatix `_extract_peatix_dates` 缺 return 靜默丟棄（commit `2a9540c`）

**問題：** 7 天連續 0 事件，無 ERROR log。函式 fall-through 隱式返回 `None`，caller unpack 失敗靜默丟棄整頁。
**教訓：** 任何 date-parser helper 函式必須在所有 return path 都有明確回傳值，不依賴隱式 `None`。

---

## 2026-05-10 — Dark mode Phase 4 + BIG ROMANTIC RECORDS / 台湾料理体験会 DB 手動修正

### A — Dark mode Phase 4（commit `web dark mode`）

**內容：**
- `ThemeToggle.tsx`（新元件）：Moon/Sun icon toggle，localStorage 持久化（`ttr_theme`）；SSR 期間渲染 placeholder div 避免 hydration mismatch
- `app/layout.tsx`：inline anti-flash `<script>` — 在第一次 paint 前讀 localStorage，若無則 fallback `prefers-color-scheme: dark`，對 `<html>` 加 `.dark`
- `Navbar.tsx`：`<ThemeToggle />` 插入 nav links 與語言切換之間
- `globals.css`：加 `html.dark { color-scheme: dark }`（讓瀏覽器原生控件也切深色）；移除 `html` 規則的 `color-scheme: light` 鎖

**教訓：** SSR anti-flash 必須用 inline `<script>` 在 `<head>` 最早執行，不能用 `useEffect`——後者在 hydration 後才跑，FOUC 已發生。

### B — BIG ROMANTIC RECORDS organizer 修正（commit `e68f390f`）

**問題：** 事件「Andr 東京公演」`organizer = null`；source_url 為 `bigromanticrecords.com`。
**修正：** `organizer = BIG ROMANTIC RECORDS`、`organizer_zh = 大浪漫唱片`；FC 鎖定。
**教訓：** source_url 域名（record label / venue 官方站）可直接推斷 organizer，無需 GPT 推理。已知 domain → organizer 映射應加入 `_KNOWN_ORGANIZER_MAP`。

### C — 台湾料理体験会 FC 跨事件污染修正（commit `fe03288b`/`b8621ee9`）

**問題：** `organizer_zh/en` 包含與 raw_description 完全無關的「上田村振興会・普門寺」資料；`performer = シェフ`（職稱非人名）。
**修正：** 兩件事各 4 欄 FC 鎖定（共 8 筆）；`performer` 設 null；`organizer` 還原正確值。
**教訓（同 scraper-expert 記錄）：** `organizer_zh/en` 內容若不在 `raw_title + raw_description` 中出現，即為 FC 污染。

---

## 2026-05-08 — Organizer 多語言欄位 + SC→TC 映射表擴充

### A — `organizer_zh` / `organizer_en` 多語言欄位（commit `95c7ad8`）

**問題：** 日文 organizer 名稱（如 `台湾文化センター`）在 zh/en 頁面直接顯示，使用者誤認為簡體中文。實為日文漢字被顯示在非 ja locale。

**修正（跨層完整 i18n）：**
- `web/lib/types.ts`：Event interface 新增 `organizer_zh`, `organizer_en` + `getEventOrganizer(event, locale)` helper
- `web/app/[locale]/events/[id]/page.tsx`：JSON-LD `organizer.name` + 顯示渲染改用 `getEventOrganizer()`
- 模式與 `getEventPerformer()` / `getEventLocation()` 完全一致

**教訓：**
1. 文字欄位多語言化前端模式：types.ts interface + `getEvent<Field>(event, locale)` helper + page.tsx 渲染同步更新，三步缺一不可。
2. 使用者反映「簡體字」時，先區分是 GPT SC 輸出還是日文原文顯示在非 ja 頁面——後者需多語言欄位解決，非 SC→TC 轉換。

### B — SC→TC `_SIMP_TO_TRAD_RAW` 新增 9 字（commit `95b79ef`）

**問題：** `_to_trad()` 映射表缺 `诗`/`禅`/`图`/`猎`/`过`/`员`/`剧`/`别`/`于`，GPT 輸出 SC 字直接寫入 `description_zh` 和 `selection_reason`。
**修正：** 新增 9 字到 `_SIMP_TO_TRAD_RAW`，修正 3 筆活躍事件。
**教訓：** 映射表從 ~50 筆成長到 300+ 筆仍不完整，本質是打地鼠。長期應評估 OpenCC 等完整 SC→TC 轉換庫。任何寫入 `*_zh` 欄位的路徑都必須過 `_to_trad()`（enrich_*、backfill_*、annotator 主迴圈）。

---

## 2026-05-08 — performer 顯示邏輯修正 + sub-events 建立 + organizer 污染修正

### A — performer 不應顯示在 sub-event 列表卡（commit `c8936a5`）

**問題：** Sub-event 的 performer 出現在列表卡（event list card），視覺上重複；應只在 parent detail page 的 organizer section 顯示。

**修正：** 前端列表卡邏輯加 `parent_event_id` 判斷：若 `event.parent_event_id` 非 null，不顯示 performer badge。

**教訓：** Sub-event 的補充資訊（performer / co_organizer 等）只在 detail view 有意義；列表卡應僅顯示上層活動標題與時間，避免資訊噪音。

### B — sub-events 手動建立：東文研セミナー fd7f79f6

**操作：** 兩筆子活動：
- `49ef0f0b`（sub1：発表者 李宜学）
- `d6a335aa`（sub2：発表者 蒋竹山）

Parent event `fd7f79f6` 的 `performers=[]` 加 FC 鎖定，防止 annotator 覆寫。

**教訓：** 建立 sub-event 後，parent 的 `performers` 欄位需加 FC 鎖（`locked_fields` 包含 `performers`），避免 annotator 從 raw_description 重新 extract 並覆寫。

### C — 湾.味(ワンウェイ) organizer 污染手動修正

**問題：** 事件 `fe03288b` / `b8621ee9`（台湾料理体験会 1部・2部）：
- `organizer` hallucinated 為 `語学スクール`
- `organizer_zh/en` 被另一事件（上田村振興会・普門寺）的 FC 資料污染
- `performer = シェフ`（職稱，非人名）
- `location_address`、`price_info`、`price_amount` 全為 null

**修正：** 兩件事各 4 欄 FC 鎖定（共 8 筆）；`performer` 設 null；`organizer` 還原真實主辦方；`organizer_zh/en` 更正後鎖定。

**教訓：**
1. `organizer_zh/en` 異常偵測：欄位內容若不出現在 `raw_title + raw_description`，高度懷疑 FC 跨事件污染。
2. `performer = 職稱` 需手動清空；annotator 不自動過濾純職稱。

### D — LINE broadcast 圖片支援 + AnnouncementForm cover upload（commit `426ee9d`）

**內容：** LINE weekly broadcast 新增封面圖片；`AnnouncementForm` 元件加入 cover image upload 欄位，圖片 URL 存入 `announcements.cover_image_url`。

---

## 2026-05-08 — report-article URL 衍生重複事件手動合併 + AI 翻譯標記污染修正

### A — report-article URL 衍生 duplicate event 手動處理流程

**操作：** Peatix 台灣文化中心的 `994b8c8b` 從「座談レポート」URL 抓取，報告文章中提及 2025-10-04 活動日期，scraper 誤建立重複事件（原事件為 `3645a3ac`）。

**merger 無法自動去重**：report URL 生成的事件 name_ja 含「レポート」，與原始活動標題差異超過 merger 閾值。

**手動合併**（有明確原始事件時）：
```python
sb.table('events').update({
    'merged_into_event_id': '<original_event_id>',
    'is_active': False,
    'deactivated_reason': 'merged_into: <short_id> — <說明>',
}).eq('id', '<report_event_id>').execute()
```

**手動停用**（無合併目標，純報告文章）：
```python
sb.table('events').update({
    'is_active': False,
    'deactivated_reason': 'report_article: post-event news report, not an upcoming event',
}).eq('id', '<eid>').execute()
```

**觸發條件：** `name_ja` 或 `raw_title` 含「レポート」「報告」「行ってきた」「観てきた」且 `is_active=true`。

### B — AI 翻譯標記（AI翻譯）不可加到原始語言人名

**問題：** `performer_zh = '張作驥（AI翻譯）'`、`performer_en = 'Cheng Tso-Chi (AI translated)'`——張作驥是繁體中文原名，出現在 eiga.com 與 raw_description，非 AI 翻譯；romanization 拼法亦錯（Cheng → Chang）。
**修正：** 清除「（AI翻譯）」標記，更正 romanization 為 `Chang Tso-Chi`，鎖 `field_corrections`。
**規則：** `performer_zh/en` 中「（AI翻譯）」標記**只能**加在確實由 GPT 從日文翻譯的名字上。人名原文已出現在 eiga.com、raw_description 或 raw_title 中，直接使用原文，不加任何標記。

---

## 2026-05-07 — archive_ended_events 残留 import 修正

**問題：** `archive_ended_events()` は 2026-05-06 に `database.py` から削除されたが、`main.py` の import 行と呼び出しが残留していた。`python main.py --dry-run` 時に `ImportError` が発生。

**修正：** `main.py` から `archive_ended_events` の import と呼び出しを削除。commit `a52f5b2` に含める。

**教訓：** 関数削除時は import 側も必ず同時に修正する。history.md に「削除済み」と記録されていても実コードを `grep` で確認すること。

---

## 2026-05-07 — performers[] 手動補充 + 非日本地點停用流程

### performers[] 手動補充（三個 taiwanshi 事件）

**操作：** 從 `raw_description` 手動提取發表者姓名，直接 upsert `events.performers[]`，同時在 `field_corrections` 鎖定保護。三個事件：
- `37d53a28`（1月例会および総会）→ `performers=['野口英佑', '藤田千彩']`
- `578f0a01`（6月例会）→ `performers=['小林善帆', '釋七月子']`
- `dfb490c8`（日本台湾学会第22回関西部会研究大会）→ `performers=` 13 位（報告者 5 + 評論者 5 + シンポジウム登壇者 3）

**三人以上時 `performer`（TEXT）保留 null**：不設單一 performer，`performers[]` 為唯一出口。
**必須鎖定 field_corrections**：upsert 後鎖 `performers` 欄位，防止下次 re-annotation 清空。

```python
sb.table('events').update({'performers': ['野口英佑', '藤田千彩']}).eq('id', eid).execute()
sb.table('field_corrections').upsert({
    'event_id': eid, 'field_name': 'performers',
    'corrected_value': json.dumps(['野口英佑', '藤田千彩'], ensure_ascii=False)
}, on_conflict='event_id,field_name').execute()
```

### 非日本地點停用流程（`7a3d83ac` 首爾公演）

**問題：** 首爾公演被抓取入庫，地址誤設大阪 Channel 1969。
**修復模式：**
```python
sb.table('events').update({
    'is_active': False,
    'deactivated_reason': 'out_of_scope: Seoul, South Korea concert — not a Japan event',
    'location_address': None,
    'location_prefectures': None,
}).eq('id', eid).execute()
```
**規則：** `deactivated_reason` 格式為 `'out_of_scope: <說明>'`，包含城市與國家。停用時同步清除地址欄位，避免錯誤地址留在 DB 污染後續分析。非日本地點**不**鎖 `field_corrections`（停用後無需保護欄位值）。

---

## 2026-05-09 — annotator performer → performers[] 自動同步（commit 4526d3a）

**Feature：** 當 annotator 設定 `performer` 且 `performers[]` 為空時，自動設 `performers = [performer]`，讓 UI 永遠能從 `performers[]` 讀取，不需 fallback 回 `performer`。

**觸發條件（全部成立才同步）：**
1. `update_data.get("performer")` — 本次 annotator pass 有設定 performer
2. `not event.get("performers")` — DB 現有 performers[] 為空/null
3. `not update_data.get("performers")` — GPT 本次未回傳 performers 陣列
4. `"performers" not in _human_protected` — performers 未在 field_corrections 保護中

**三欄位職責（不可互換）：**

| Field | Type | 職責 |
|-------|------|------|
| `performer` | `TEXT` | 日文單人主表演者；annotator GPT/regex 輸出；`getEventPerformer()` fallback 來源 |
| `performer_zh` / `performer_en` | `TEXT` | performer 的語言翻譯（一對一對應）；GPT 填入或人工設定 |
| `performers[]` | `TEXT[]` | 多人顯示陣列；學術研討會全體發表者；自動 sync 自 performer |

**⚠ performer 欄位不可刪除**：`performer_zh/en` 是以 `performer` 為錨點的一對一翻譯；若 `performers[]` 有多人則翻譯欄位意義不明。設計決定：三欄並存，自動 sync 確保 UI 一致。

**Lesson：** 新功能設計前先確認欄位依賴關係。「刪除 performer 改用 performers[]」看似簡化，實際上 annotator.py、database.py、base.py、AdminEditClient、AdminEventForm 等 34+ 處引用，且 performer_zh/en 翻譯對必須有一對一的錨點欄位。

---

## 2026-05-09 — 手動修正污染了 field_corrections（c6d5232a）

**Problem:** 前次手動修正事件 `c6d5232a` 時，誤把污染後的 `description_ja`（霧のごとく版本）直接更新進 DB，並將 `name_zh=大濛` upsert 進 `field_corrections`。由於 FC 的 P1 保護，後續 re-annotation 永遠無法覆寫，污染被鎖定。

**Root cause:** 手動修正前未先讀取 `raw_description`（原始資料），直接從 `name_ja`/`name_zh`（已被 annotator 污染的欄位）推導修正值，導致把錯誤值當正確值鎖入 FC。

**Fix:**
```python
# 1. 刪除錯誤的 FC
sb.table('field_corrections').delete().eq('event_id', eid).eq('field_name', 'name_zh').execute()

# 2. 從 raw_description 重建正確值，更新 events 表
sb.table('events').update({
    'name_ja': '赤い糸 輪廻のひみつ',
    'name_zh': '月老',
    'name_en': 'Red Thread: The Secret of Reincarnation',
    'work_id': 'fd225042-...',
    'parent_event_id': '6649f6ba-...',
    'description_ja': '...',  # 從 raw_description 重建
}).eq('id', eid).execute()

# 3. 鎖定正確值
for field, val in [...]:
    sb.table('field_corrections').upsert({'event_id': eid, 'field_name': field, 'corrected_value': val},
                                          on_conflict='event_id,field_name').execute()
```

**Lesson:** 手動修正前**必須先讀 `raw_description`**，確認修正方向正確再 upsert FC。從已被污染的 `name_ja`/`name_zh` 欄位取值再鎖定 = 將污染永久化，後續無法自動修復。驗證命令：`SELECT id, raw_title, raw_description, name_ja, name_zh FROM events WHERE id = '<eid>'`。

---

## 2026-05-09 — performers[] 優先序蓋過 performer_zh/en，zh/en locale 永遠顯示日文名稱（commit 2e6f4c2）

**Problem:** `web/app/[locale]/events/[id]/page.tsx` 在顯示 performer 時，`performers[]`（永遠是日文陣列）的優先順序高於 `getEventPerformer(locale)`，導致 zh/en 頁面永遠顯示日文名稱，即使 `performer_zh`/`performer_en` 已設定（例：`ホアン・イーウェン` 在 zh 頁應顯示 `黃以文`，但始終顯示日文）。

**Root cause:** performers[] join 邏輯放在最前面，未先檢查 locale + performer_zh/en 的存在性。migration 054 新增多語言欄位後，UI 優先序未同步更新。

**Fix (commit `2e6f4c2`):**
```tsx
{locale !== "ja" && ((event as Event).performer_zh || (event as Event).performer_en)
  ? getEventPerformer(event as Event, locale)
  : ((event as Event).performers ?? []).length > 0
    ? (event as Event).performers!.join("、")
    : getEventPerformer(event as Event, locale)}
```
邏輯：zh/en locale + performer_zh/en 存在 → `getEventPerformer(locale)`；否則 `performers[].join("、")`；否則 `getEventPerformer` fallback。

**Lesson:** `performers[]` 永遠是日文陣列，不可作為 zh/en locale 的主要顯示來源。新增多語言欄位後，事件詳情頁的 UI 顯示優先序必須同步更新，否則新欄位永遠不會被 end-user 看到（隱性迴歸）。

---

## 2026-05-06 — business_hours 多日場次換行未顯示（commit af33133）

**Problem:** 電影多日場次的時刻表（`business_hours` 欄位，各場次以 `\n` 分隔）在詳情頁 `<td>` 元素內顯示為單行，換行符被 HTML 忽略。

**Root cause:** `web/app/[locale]/events/[id]/page.tsx` 的 `business_hours` `<td>` 未設定保留空白字元的 CSS 屬性，瀏覽器預設 `whitespace: normal` 折疊所有換行。

**Fix (commit `af33133`):** `<td>` 加入 Tailwind class `whitespace-pre-wrap`：
```tsx
<td className="... whitespace-pre-wrap">{getEventBusinessHours(event, locale)}</td>
```

**Lesson:** `<td>` 或 `<div>` 顯示含 `\n` 的多行文字時，必須加 `whitespace-pre-wrap`（保留換行 + 自動折行）。三種 class 的差異：`whitespace-pre-wrap`（保留換行 + 折行，**正確選擇**）、`whitespace-pre`（保留換行但不折行，內容過長時溢出）、`whitespace-normal`（預設，忽略換行——**勿用於多行字串**）。

---

## 2026-05-06 — works work_type check constraint 不含 conference

**Error:** 建立學術研討會 work 記錄時使用 `work_type='conference'` → `APIError: violates check constraint "works_work_type_check"`。

**Root cause:** Migration 048 + 051 的 check constraint 只允許 `film | stage | exhibition | concert_tour | tv_drama | tv_variety | other`。PostgreSQL check constraint 沒有 schema 預覽，執行時才報 IntegrityError。

**Fix:** 改用 `work_type='other'`；新建 work `c3588296`（日本台湾学会第23回関西部会研究大会）。

**Lesson:** 建立 works 記錄前先查現有 `work_type` 值：`sb.table("works").select("work_type").execute()`。或查 migration SQL 確認 check constraint 允許值。

---

## 2026-05-06 — CI YAML parser quirk: [{...}] inline jq filter

**Error:** `.github/workflows/workflow-failure-notify.yml` 的 `run: |` block 中包含 `[{type:"text",...}]` inline jq filter → GitHub Actions YAML parser 錯誤：`Nested mappings not allowed in compact mappings`。

**Root cause:** GitHub Actions YAML parser 對 block scalar（`|`）內容仍做 YAML 解析，`[{...}]` 被識別為 inline mapping array。這是 GitHub YAML parser 的 known quirk，非標準 YAML 行為。

**Fix (commit `b9a462c`):** 將 jq filter 指派給 shell 變數 `JQ_FILTER`，避免 `[{...}]` 直接出現在 inline argument：
```yaml
run: |
  JQ_FILTER='[{type:"text",text:"..."}]'
  curl ... --data "$(jq -n --arg t "$MSG" "$JQ_FILTER")"
```

**Lesson:** GitHub Actions YAML parser 的兩個 known quirk：
1. `if:` multi-line block scalar（`>-` / `|`）有時解析失敗 → 改用單行雙引號字串。
2. `run: |` 中 `[{key:"val",...}]` inline array of objects → 改用 shell 變數。
兩者都應優先測試；不要假設 block scalar 就能繞過 YAML 解析。

---

## 2026-05-06 — AdminEventTable per-row work dropdown：`<a>` → modal (4a266a1)

**Error:** Per-row work 下拉選單中「＋ 建立新作品」按鈕使用 `<a href="/admin/works/new">` 開新分頁，與 bulk action bar 的「＋ 新增作品」按鈕行為不一致（後者呼叫 `setShowCreateWorkModal(true)`）。

**Fix (commit `4a266a1`):** 改為 `<button onClick={() => setShowCreateWorkModal(true)}`，與 bulk action bar 保持一致。

**Lesson:** AdminEventTable 的 work 操作應一律透過 modal（`AdminCreateWorkModal`），不應從行內連結跳出至獨立頁面。一致性規則：相同操作的 UI 入口必須共用相同的實現路徑。

---



**Error:** ks_cinema `taiwan-filmake` 系列頁面的電影出現 2 筆 active 重複事件（`_2_sub1`, `_0_sub1`）。Annotator 看到兩個排片時段（`4/25～5/1`、`5/2～8`）→ 按 "multiple dates → sub_events" 規則生成 `_sub1`，因同 source 被 merger 跳過，永遠不被消除。

**Root cause:** scraper 首次執行時 `_get_parent_uuid` 查不到 parent（同批 upsert 未 commit）→ `parent_event_id=None`，繞過 grandchild 守衛。

**Fix (commit `a6cf029`):**
1. DB：停用 `_2_sub1`、`_0_sub1`（admin_manual）
2. SYSTEM_PROMPT Rule 1 加 EXCEPTION：電影時段窗口不建立 sub_events
3. 程式碼守衛：`_cinema_sources + source_id ends _{digit} + parent_event_id=None → sub_events = []`

**Lesson:** 電影放映時段 ≠ sub_events；`_sub1` 同 source 不被 merger 消除，必須靠守衛預防。

---
## 2026-05-06 — SC chars 被 enrich_person_names() GPT 重新引入

**Error:** `enrich_person_names()` GPT 輸出直接寫入 DB，未通過 `_to_trad()`，簡體字被重新寫入已修正的繁體欄位。

**Fix (commit `239cb19`):** `_SIMP_TO_TRAD` 提升為模組層級；`enrich_person_names()` 輸出包裹 `_to_trad()`。

**Lesson:** 任何寫入 name_zh/description_zh 的函式都必須過 `_to_trad()`，無論來源是 GPT 還是 DeepL。

---
## 2026-05-06 — auto_qa --fix SC 轉換後未鎖 field_corrections

**Error:** `fix_simplified()` 轉換 SC→TC 後未呼叫 `_lock_fields_via_corrections()`，下次 re-annotation 直接覆寫，SC 字元復活。

**Fix (commit `6e21c52`):** `fix_simplified()` 轉換後呼叫 `_lock_fields_via_corrections()`。

**Lesson:** 任何手動或批量修正翻譯欄位後必須立即鎖 `field_corrections`（見 Manual Translation Fix Persistence Guard）。

---
## 2026-05-08 — main.py import reorder silently dropped 4 scrapers (WalkerplusScraper, BigRomanticRecordsScraper, WasedaIclScraper, TsutayaPortalScraper)

**Error:** commit `694a363` (fix(annotator): extend year-anchor injection to all sources) rewrote the import block in `scraper/main.py` and accidentally dropped 4 scrapers from both the import section and the SCRAPERS list. The source files existed but daily CI never ran them.

**Detection:** Manual inspection during documentation review showed `grep -c "Scraper()" scraper/main.py` was lower than expected.

**Fix:** Re-added 4 import lines + 4 SCRAPERS list entries. Verified with `python main.py --dry-run --source <name>` for each.

**Lesson:**
- `main.py` import reordering is HIGH RISK. After any commit touching main.py, run: `git diff HEAD -- scraper/main.py | grep "^-.*Scraper()" | wc -l` — if > 0, confirm each removal is intentional.
- Feature/fix commits (annotator year-anchor, merger rules, etc.) should NOT touch the SCRAPERS list at all. Keep main.py changes separate from scraper-logic changes.
- This is the SECOND identical incident (`045d1fa` was the first in 2026-05-04). The pattern is now in SCRAPERS List Completeness Guard.

---

## 2026-05-07 — gnews RSS snippet used as start_date fallback when article_text is None

**Error:** `google_news_rss.py` called `_extract_start_date(article_text or description_plain, pub_date)`. When article fetch failed, `description_plain` (RSS snippet, ≤200 chars) was passed to the date extractor — too short to yield reliable dates. Result: incorrect `start_date` values on gnews events.

**Fix (commit 1c0f69a):** Changed to `_extract_start_date(article_text, pub_date) if article_text else None`. When article is unavailable, annotator's universal year-anchor handles the date.

**Lesson:** RSS snippet ≠ event data. Any date extraction that falls back to a snippet will produce noisy dates. Prefer `None` + annotator over a high-error fallback.

---

## 2026-05-07 — tokyoartbeat Contentful placeholder guard used day==1 instead of month==1

**Error:** The Contentful placeholder date guard in `tokyoartbeat.py` was `start_date.day == 1`, but Contentful uses the **entire January** (`YYYY-01-xx`) as a fiscal-year placeholder. Events `977da793` (2026-01-15) and `e7cf2a51` had placeholder dates that were NOT caught.

**Fix (commit 7df9f56):** Changed guard condition to `start_date.month == 1`. Applied direct DB correction for the 2 affected events.

**Lesson:** Platform placeholder conventions should be described broadly. When a vendor uses an entire month as a placeholder, the guard must cover the entire month, not just the 1st.

---

### 2026-05-05 — Batch Script Post-Enrichment Guard（程式碼層防護）

**設計問題**：每次寫 `_oneoff_*.py` 批次修復腳本，都從零用 urllib 直接打 REST API，完全繞過 annotator.py 已有的 enrichment pipeline。導致同類錯誤反覆出現：片名 GPT 直譯幻覺（超低預算 2026-05-05）、翻譯被 AI 覆寫（月老 2026-05-04）、人名音譯未修（desc_en 2026-05-05）。

**解法**：在 `annotator.py` 新增 `post_batch_enrich(event_ids)` 共用函式。所有 batch 腳本寫入 DB 後呼叫此函式，自動執行：(1) eiga.com 電影片名 lookup + field_corrections 鎖定；(2) 日後可擴充 person name enrichment。

**教訓**：
- **Guard 文件不夠，需要程式碼層強制**：同一類錯誤（繞過 enrichment pipeline）在 5 天內出現 3+ 次，每次都加 Guard 文件但下次仍被繞過。唯一有效防護是提供共用函式讓 batch 腳本一行呼叫。
- **「提供方便的正確路徑」優於「禁止錯誤路徑」**：與其禁止用 urllib 直接打 API（不可能），不如讓正確做法比錯誤做法更簡單（一行 import + 呼叫 vs 手動實作 enrichment）。

---
## 2026-05-05 — 首頁城市徽章修了兩輪才生效：EventCard.tsx 不是首頁使用的元件（commit `9f4b468`）

### 問題
第一輪修正 [`web/components/EventCard.tsx`](web/components/EventCard.tsx)（commit `5a29c13`），regex 理論上正確、TypeScript 無錯、Vercel 部署成功——但首頁仍看不到徽章。`curl https://tokyotaiwanradar.com/zh | grep -c '📍'` 只回 1（預期多筆），`grep -c 'border-gray-200 rounded-xl'`（EventCard root class）回 0。

### 根因
首頁 [`web/app/[locale]/page.tsx`](web/app/[locale]/page.tsx) 是 **inline list-style 渲染**，**沒 import EventCard**。grep `EventCard` in `page.tsx` = 0 match。`EventCard.tsx` 只服務 saved / category / search 頁面。首頁原來的 location 渲染是行 294-295：
```tsx
{event.location_name && (
  <p className="text-xs text-gray-400 mt-0.5">📍 {event.location_name}</p>
)}
```
完全沒有 `cityLabel` 邏輯。

### 修法
抽共用 helper 至 [`web/lib/cityLabel.ts`](web/lib/cityLabel.ts)：`getCityLabel(prefectures, address)` 內部依優先序走 prefectures 陣列 → `extractCity()` regex fallback。`EventCard.tsx` 與 `page.tsx` 同時 import，首頁第 294 行改為：
```tsx
{event.location_name && (() => {
  const cityLabel = getCityLabel(event.location_prefectures, event.location_address);
  return (
    <p className="text-xs text-gray-400 mt-0.5">
      📍 {cityLabel && <span className="...">{cityLabel}</span>}
      {event.location_name}
    </p>
  );
})()}
```

### 教訓
- **「原件以為被共用」是危險假設**：修任何事件卡片視覺前必在 `web/app/[locale]/` 與 `web/components/` 雙路徑 grep 使用者。`grep -rn '<EventCard\|EventCard ' web/app/ web/components/` 可快速列出實際 call site。
- **「修了一處忘了另一處」一旦發生必立刻抽 lib**：不要遵 inline 複製邏輯跨檔案；DRY 不是潔癖，是防迴歸。`web/lib/cityLabel.ts` 42 行取代了 EventCard.tsx 24 行 + page.tsx 1 行 × 來回迴歸二次的維護成本。
- **TypeScript 不能打不同路徑的架構 bug**：`page.tsx` 與 `EventCard.tsx` 各自類型正確，但「首頁使用的是哪個」這個事實 TS 無法驗證——需 grep 手動確認。
- **Vercel 部署驗證必用 `curl + grep`**：`grep -c` 計數 class 或 emoji，期望值明確。`grep -c '📍'` 與 `grep -c 'bg-gray-100 text-gray-600 px-1.5'`（新徽章識別類名）雙重交叉驗證。

---
## 2026-05-05 — annotator `_ai_or_existing()` 定義卻從未呼叫，P1 翻譯欄位被 GPT 重寫（commit `cf2d3f6`）

### 問題
`annotator.py` 主迴圈構造 `update_data` 時，對 `name_zh` / `name_en` / `description_zh` / `description_en` 四個翻譯欄位**直接寫入 GPT 輸出**，未經過 `_human_protected` 過濾。helper `_ai_or_existing()` 雖已定義但無任何 call site。`performer` 與 `localized_location_data` 有獨立保護路徑因此倖免。

### 觸發情境
event `f970e4e3`（月老）：source 頁面 5/8→5/9–5/13 日期變動 → `force_rescrape=true` 重新刮取 → annotator 重跑 → `name_zh='月老'`（field_corrections 已鎖）被 GPT 改回 `紅線 輪迴的秘密`。手動修了又被 AI 覆寫，迴歸鏈持續 1 週以上。

### 修法
在 `update_data` 構造完成後、送 Supabase PATCH 之前，新增 post-processing：對 `_human_protected` 中所有欄位以 DB 既有值（`event.get(fname)`）覆蓋 GPT 輸出。語意等同 `_ai_or_existing()`，但**無條件**且套用全部欄位。同時遞增 `field_protect_hits` counter，CI log 可觀察單次 run 的保護命中數。

### 教訓
- **「定義了的 helper 不等於被呼叫」**：refactor 時新增 helper 必 grep 確認所有應用位點都已切換；無 call site 的保護等於 0 保護。
- **保護機制必須是「default deny」**：`update_data[fname] = gpt_output` 是 default allow（除非顯式排除），改成 post-processing 強制覆蓋是 default deny（除非欄位不在 protected set）。
- **field_corrections 是最後一道防線**：人工鎖了欄位，annotator 也必須真的尊重——否則 architect 的 Manual Translation Fix Persistence Guard 形同虛設。
- **驗證 pattern**：任何修改 `update_data` 構造邏輯的 PR，必須驗證 `_human_protected` 中欄位在 PATCH payload 中等於 DB 既有值。

---
## 2026-05-05 — admin UI 修改分類未同步 `field_corrections`，下次 annotator 重跑覆寫（commit `1abbe38`）

### 問題
後台三條人工修正路徑（`AdminEventTable` inline + bulk、`AdminEditClient` edit form、`confirm-report` 報告確認）修改 `events.category` 時，只 UPDATE `events` 表，未 upsert `field_corrections`。下次 `annotation_status='pending'` 時，annotator 用 GPT 重新分類覆寫人工值，與翻譯欄位的「修了又錯」迴歸鏈同因。

### 修法
三條路徑統一補上 `field_corrections` upsert（`onConflict: event_id,field_name`）。
- `AdminEventTable.tsx`：inline 與 bulk 兩個 call-site
- `AdminEditClient.tsx`：edit form save 時若 category 變動
- `web/app/actions/confirm-report.ts`：confirm 時 category 修正

### 教訓
- **`field_corrections` 不只翻譯欄位**：`category` / `event_form` 等結構欄位也走 annotator GPT 路徑，凡是「人工修了 + annotator 會再覆寫」的欄位都必須鎖。
- **新增 admin mutation 路徑必查清單**：任何寫入 `events` 表的 server action / client mutation，自查欄位是否屬於 `_human_protected`；若是，必須同 transaction upsert `field_corrections`。
- 已對應 architect 的 Manual Translation Fix Persistence Guard 擴張範圍至非翻譯欄位。

---
## 2026-05-05 — Partial-payload upsert violates NOT NULL constraints

### 問題
實作 movie-extend 第二輪 update 用 `client.table("events").upsert(extend_rows, on_conflict="source_name,source_id")`，PostgREST 報 `null value in column "source_url" of relation "events" violates not-null constraint`。錯誤行 ID 是新生成的 UUID（不是現存 row 的 ID），代表 supabase-py 先嘗試 INSERT 才 fall back 到 UPDATE，但 NOT NULL 驗證在 row construction 階段就跳出。

### 修法
對保證已存在的 row 做 partial 寫入，改用 `.update(row).eq("source_name", sn).eq("source_id", sid)`，把 conflict key 從 payload pop 出來。

### 教訓
`on_conflict` upsert 是給「完整 row」的 partial 寫入會打到 NOT NULL（無 default 的欄位如 `source_url`）。只要 row 已透過 `existing_keys` 確認存在，一律改用純 `.update().eq()`，永遠不要用 partial upsert。

---
## 2026-05-05 — Works entity ship (migration 048)

### 問題
同一部台灣電影（月老、大濛）在多家戲院各自發行 events，使用者看不出是同一作品；merger Pass 1 名稱相似度 ≥ 0.85 又會錯誤合併不同戲院的場次（會丟失另一場資訊）。同類問題會擴散到舞台劇、巡演、特展等「跨場次同一作品」型內容。

### 根因（5 個）
1. **缺少作品層級實體**：events 是「單一場次」的呈現，但「作品」是更穩定的事物 — 沒有獨立 entity 就無法做 cross-screening 連結。
2. **merger Pass 1 對電影同名跨 venue 過度合併**：之前 `_location_overlap()` 有 prefix/suffix-extension 容忍度，月老 (新文芸坐 ↔ シネマート新宿) 仍可能撞上 sim=1.0 觸發誤合併。
3. **`parent_event_id` 被誤用為作品連結**：sub-event 結構是「同一活動拆 schedule」，把跨戲院場次塞進 parent/sub 會破壞 sub-event 過濾與展示邏輯。
4. **詳情頁 anon-key RLS 副作用**：cross-link sibling 查詢若用 anon client，會 silently 漏掉 `is_active=false` 的 sibling，admin 看不到完整列表。
5. **AdminEventTable 缺乏 work 缺漏訊號**：電影類 event 沒指派 `work_id` 不會被任何檢查工具標出，導致缺漏永遠累積。

### 修復
- **migration `048_works_entity.sql`**：新增 `works` 表（work_type CHECK、original_title UNIQUE、title_ja/zh/en、director、cast_summary、release_year、country、description、poster_url、external_links）+ `events.work_id` FK + RLS + updated_at trigger。
- **types.ts**：新增 `Work` interface、`WorkType` union、`getWorkTitle()` helper、`Event.work_id` 欄位。
- **詳情頁** `web/app/[locale]/events/[id]/page.tsx`：以 service role client 查同 `work_id` 其他 active events，渲染「同作品其他場次」block；i18n key `event.relatedScreenings.title` 三語齊備。
- **admin works CRUD** `web/app/[locale]/admin/works/{page,[id]/page,new/page}.tsx` + `web/app/actions/works.ts`：list / new / edit + `assignWorkToEvent` server action。AdminTabNav 新增 Works tab。
- **AdminEventTable Phase 5**：新增 `work` 欄、inline assign-work dropdown（搜尋 + 連到 `/admin/works/new`）、movie/performing_arts 缺 `work_id` 整列 `bg-red-50` 警示 + tooltip。
- **i18n** 三語：`admin.events.columns.work`、`admin.events.assignWork.{placeholder,unassigned,createNew}`、`admin.events.warnings.missingWorkForFilm`。
- **merger.py Pass 1 skip**：(a) 雙方 `work_id` 非空且不同 → skip；(b) movie/performing_arts + `_location_overlap()=False` → skip。輸出 `[Pass 1 SKIP]` log。
- **backfill** `scraper/_oneoff_backfill_works.py`：upsert 月老／大濛 + assign 4 events。支援 `--dry-run`。
- **docs**：architect 加 `Works Entity vs parent_event_id Guard`；engineer SKILL 加 `Works Entity Conventions`；MERGER_WORKFLOW 加 Pass 1 work_id skip 段落。

### 教訓
- **作品（Work）≠ 場次（Event）**：跨場次穩定實體必須單獨建表，不能塞進 `parent_event_id`。兩者並存且職責正交。
- **`on_conflict` 依賴需 UNIQUE constraint**：PostgREST 的 `upsert(on_conflict='...')` 只在該欄位有 unique index 時可靠運作。Backfill 改用先 SELECT 再決定 INSERT/UPDATE 的模式，更明確且不依賴 PostgREST 邊角行為。
- **service role 是 admin cross-link 的必要條件**：任何展示 `is_active=false` 的 sibling 場次都必須繞過 RLS。
- **i18n 巢狀 namespace 要透過 `useTranslations("admin")` + `t("events.columns.work")` 路徑訪問**；不要拆成多個 hook，效能與一致性都差。
- **merger 加 skip 比加 candidates table 便宜**：Phase E 還沒到位前，先 log skip 已能解 80% 即時痛點。

### 影響檔案（本回合）
- `supabase/migrations/048_works_entity.sql`（新增 unique index 補丁）
- `web/components/AdminEventTable.tsx`（Phase 5：work 欄、assign UI、紅列警示）
- `web/messages/{zh,en,ja}.json`（admin.events 巢狀 namespace）
- `scraper/merger.py`（Pass 1 work_id + venue skip）
- `scraper/_oneoff_backfill_works.py`（新建）
- `.github/agents/architect.agent.md`（Works Entity Guard）
- `.github/skills/agents/engineer/SKILL.md`（Works Entity Conventions）
- `docs/MERGER_WORKFLOW.md`（Pass 1 work_id skip 段落）

---
## 2026-05-05 — Merger 合併失效根因 + Pass 2 location 過嚴 + 缺停用稽核

### 問題
「台湾祭in群馬太田2026」事件在四個來源（taiwan_matsuri / iwafu / prtimes / walkerplus / gnews）持續以多筆獨立事件存在，merger 無法自動合併。手動合併後一週內又出現新重複。

### 根因（多個）
1. **dash 字元差異**：iwafu 用 `－`（U+FF0D），walkerplus 用 `ー`（U+30FC）。`_normalize()` regex 不包含 `ー`，sim 0.581 < 0.85。已於 commit `2d9685e` 修復。
2. **Wrapping quote**：prtimes 用 `「…」` 包住標題，sim 0.545。同 commit 修復。
3. **`_location_overlap` 過嚴**：gnews `群馬県太田市` 與 iwafu `イオンモール太田` token 集無交集（`{群馬県,太田市}` ∩ `{イオンモール,太田}` = ∅），Pass 2 不啟動。
4. **walkerplus 不算 news**：merger Pass 2 只處理 `_NEWS_SOURCES`，walkerplus 不在其中，但其資訊密度低於官方主辦方。
5. **缺停用稽核**：events 表沒有 `deactivated_at`/`deactivated_reason` 欄位，無法事後分析「為何此活動被合併」。

### 修復
- Phase A：`_location_overlap` 加入 ≥4 字子字串包含判定
- Phase B：`walkerplus` 加入 `_NEWS_SOURCES`（並補入 `SOURCE_PRIORITY` 為 14）
- Phase C：migration 044 新增三個稽核欄位（`deactivated_at`/`deactivated_reason`/`deactivated_by_pass`）+ merger 各 Pass 同步寫入 + 所有 admin manual deactivate 入口（`IsActiveToggle`、`AdminEventTable` bulk/single、`confirm-report.ts` 三條 is_active=false 分支）

### 教訓
- Location 字串多樣性遠超 token-based overlap 能處理。範例：`イオン太田` / `イオンモール太田` / `群馬県太田市` 是同一地點不同表達。
- 聚合站（walkerplus / arukikata 等）資料品質參差，應視為 news 而非 official。
- 沒有稽核欄位的「合併失敗」極難 debug — 必須事後從 git log 還原。
- Admin manual deactivate 有多個入口（toggle、bulk、confirm-report 三條 is_active=false 分支），新增稽核欄位時必須掃過所有 setter。

---
## 2026-05-05 — auto_research batch query 遺漏 `pending` 狀態，候選來源永遠跳過（commit `5d2585d`）

### 問題
Migration 033 將 `research_sources.auto_research_status` 的 DEFAULT 設為 `'pending'`（而非 NULL）。但 `auto_research.py` 的 batch query 只過濾 `NULL` 或 `'error'`，導致所有新候選來源在 migration 033 之後永遠被 batch 跳過（靜默失效，無錯誤訊息）。

```python
# 舊（有 bug）
.or_("auto_research_status.is.null,auto_research_status.eq.error")

# 修復後
.or_("auto_research_status.is.null,auto_research_status.eq.pending,auto_research_status.eq.error")
```

手動重置 14 筆既有 `pending` 候選為 NULL，讓當晚 cron 立即處理。

### 教訓
- **新增 DB 欄位時，若設定 DEFAULT 值，必須同時更新所有 batch query 的過濾條件**。DEFAULT `'pending'` 與 DEFAULT `NULL` 對 query 的影響截然不同。
- 靜默跳過的 bug（候選出現在 DB 但永遠不被處理）沒有 ERROR log，只能從處理計數為 0 的 CI 輸出發現。
- 每次新 migration 加了 DEFAULT 值的欄位，應立即搜尋所有 `.or_("... .is.null ...")` 的 query，確認是否需要加新 DEFAULT 值的條件。

---
## 2026-05-05 — merger.py 年份後綴造成年度例行活動無法自動合併

### 問題
`merger.py` Pass 1 的 `_normalize()` 函式未剝除年份後綴（`2026`、`2025春` 等）。每年在標題後加上年份的例行活動（如「台湾文化祭2026」vs「台湾文化祭」）相似度只有 0.714，低於 0.85 門檻，導致自動合併失效。

具體案例：
- `14dbef1a`（iwafu「台湾文化祭2026」）與 `ed313f24`（taiwanbunkasai「台湾文化祭」）— 同一活動，不同來源，merger 未合併
- 手動合併後才發現 _normalize 的系統性缺失

### 修復（`scraper/merger.py`）
在 `_normalize()` 尾端加入年份剝除：
```python
# Strip year suffix (e.g. "台湾祭2026", "台湾文化祭2025春")
name = re.sub(r"20\d{2}[春夏秋冬]?\s*$", "", name)
```

驗證：
- `台湾文化祭2026` vs `台湾文化祭` → 1.000 ✓
- `台湾文化祭2026春` vs `台湾文化祭` → 1.000 ✓
- `台湾フェスティバル™TOKYO2026` vs `台湾文化祭2026` → 0.200 ✗（正確，不誤合併）

### 教訓
- 例行活動（年度祭典）的標題通常會在年底加年份後綴，但來源不一致（官方來源常只寫活動名，其他來源加上年份）。`_normalize()` 必須消除年份差異，否則每年都需要手動修復。
- 每次新增 `_normalize()` 規則後，需跑全測試組確認無誤合併（特別是名稱相近但不同活動的案例，如「台湾フェスティバル」vs「台湾文化祭」）。

---
## 2026-05-05 — 霧のごとく（大濛）電影片名 description 未同步（DB patch）

### 問題
7 筆事件的 `description_zh` / `description_en` 中出現錯誤電影片名翻譯：「霧的如同」「霧的如夢」「霧的故事」（zh）、"Like Mist"（en），正確為「大濛」/ "A Foggy Tale"。涉及 cinemart_shinjuku、peatix、taioan_dokyokai、uplink_cinema、google_news_rss 五個來源。

### 根因
`enrich_movie_titles()` 只修正 `name_zh` / `name_en`，不修正 `description_zh` / `description_en`。GPT 翻譯 description 時用了直譯片名，與 name 欄位不一致。

### 修復
DB patch script 對 7 筆事件逐一替換 description 中的錯誤片名變體，並修正替換後產生的「大濛（大濛）」重複括號。

### 教訓
- `enrich_movie_titles()` 只修正 name 欄位，description 中的片名需另外 patch——已記錄為 engineer.agent.md Rule 11（`enrich_movie_titles() description sync rule`）
- 直譯變體可能有多種形式（`霧的如同`、`霧的如夢`、`霧的故事`），patch 時需全部列舉

---
## 2026-05-05 — LINE 週報都市前綴 + Python-level 去重（commits `5acb6a1`、`4a6fd5a`）

### 問題
LINE 週報只顯示活動名，讀者無法一眼判斷是東京還是關西活動。此外同一活動若有多個來源（如 peatix + connpass），會重複出現在推送中。

### 修復（`scraper/weekly_line_broadcast.py`）
- **都市前綴**：所有事件加 `[都市名]` prefix（如 `[大阪]`、`[京都]`）。初版排除東京（因為大部分事件在東京），但 commit `5acb6a1` 改為也顯示 `[東京]`，保持一致性。
- **Python-level 去重**：以 `name_ja` 為 key，同名活動只保留一筆。

### 教訓
- 都市前綴可做可不做的「差異」反而使讀者更困惑（「沒標籤=東京」不直觀），不如全部統一加上
- GPT 選出的活動可能跨多個 source_name，Python-level 去重比在 SQL 做更容易控制

---
## 2026-05-05 — auto_qa 重複建立 confirmed/dismissed 報告（commit `75d3c1e`）

### 問題
`auto_qa.py` 每次執行都重新產生 `auto_*` 類型報告，即使 admin 已確認（confirmed）或駁回（dismissed）同一筆報告。Admin 的處理工作被 auto_qa 覆蓋。

### 根因
Insert 前的去重查詢只檢查 `status='pending'`，未排除 `confirmed` 和 `dismissed` 狀態。

### 修復
去重查詢改為：同 `event_id` + 同 `auto_*` report type 且 status 為 `pending` / `confirmed` / `dismissed` 任一者皆 skip。

### 教訓
- **auto_qa 去重必須檢查 ALL statuses**（pending + confirmed + dismissed），不只 pending
- Admin 的 confirm/dismiss 是最終決定，自動化不得覆蓋

---
## 2026-05-05 — Sub-event annotation 缺失（commit `38f4f3a`）

### 問題
Scraper 直接產生的 sub-events（非 GPT 產生）有 `annotation_status='pending'`，但 annotator 只處理 parent event 的 GPT-generated sub-events。導致 scraper-created sub-events 缺少 category、description 等欄位。

### 修復
`annotator.py` 修改為也 pick up scraper-created sub-events（有 `parent_event_id` 且 `annotation_status='pending'`），從 parent event 繼承 category 和 context。

### 教訓
- Annotator 必須處理所有 pending 事件，不只 parent events 的 sub-events
- Sub-event annotation 應從 parent 繼承 category 和其他 context fields

---
## 2026-05-05 — enrich_location GPT 回傳 venue name 作為 address（commit `628e3e7`）

### 問題
`enrich_location.py` 呼叫 GPT 填補 `location_address` 時，GPT 有時回傳 venue name（如 `ユーロスペース`）而非街道地址，造成 `location_address == location_name`。

### 修復
新增 guard：如果 GPT 回傳的 address 等於 `location_name`，skip 更新。同時新增 sub-venue 規則處理。

### 教訓
- GPT 回傳的 location 資料需驗證 `address ≠ venue_name`，不能盲目寫入
- 此 guard 應同時存在於 scraper 端和 enrichment 端——雙層防護

---
## 2026-05-05 — location_address = location_name 全 scraper 稽核（commit `9d6e0fc`）

### 問題
多個 scrapers（iwafu、jposa_ja、kokuchpro、koryu、prtimes、taioan_dokyokai、taiwan_festa、waseda_taiwan）將 `location_address` 設為與 `location_name` 相同的值。`location_address` 應該是街道地址，不是場地名稱。

### 修復
稽核所有 scraper，逐一修正：有實際地址可解析時分開設值；無實際地址時設 `location_address = None`。

### 教訓
- **`location_address` 必須永遠不等於 `location_name`**——這是全 scraper 通用規則
- 當 scraper 只有一個 combined "location" 欄位時，正確做法：venue name → `location_name`，street address → `location_address`；找不到 street address 則設 `None`
- `_ai_or_existing()` 保護邏輯在 DB 欄位非 null 時保留既有值，所以 scraper 端寫入錯誤值後 annotator 也無法修正

---
## 2026-05-05 — proxy.ts /r/* 短網址被 i18n middleware 攔截（commit `3cfe438`）

### 問題
短重導路由 `/r/*` 被 i18n middleware 攔截並 307-redirect 到 `/zh/r/*`，造成 404。

### 修復
在 `proxy.ts` matcher 排除 regex 中新增 `/r/` 路徑。

### 教訓
- proxy.ts matcher 排除不只適用於 `public/` 靜態文件——任何**非 locale 路由**（API routes、短網址、redirect routes）都必須排除
- 新增 rule 的適用範圍從「static file exclusion」擴展為「non-locale route exclusion」

---
## 2026-05-05 — LINE 週報時間窗口擴大（commit `9b33ad3`）

### 問題
LINE 週報每週只推「未來 7 天」活動，月刊最遠僅到 35 天，讀者回饋活動太少、錯過較遠期熱門活動。

### 修復（`scraper/weekly_line_broadcast.py`）
| 參數 | 修改前 | 修改後 |
|------|--------|--------|
| `_fetch_upcoming_events` pool 範圍 | 35 天 | 60 天 |
| `_ai_select_events` week_end | 7 天 | 21 天 |
| `_ai_select_events` week2_end | 14 天 | 28 天 |
| `_ai_select_events` month_end | 35 天 | 60 天 |
| WEEKLY SELECTION 標籤 | next 7 days | next 21 days |
| MONTHLY SELECTION 標籤 | 8–35 days | 22–60 days |
| 備援觸發條件 | 14 天 | 28 天 |

### 教訓
- 廣播時間窗口直接影響 GPT 的分類邏輯（week/month 分界），修改時需同步調整 AI prompt 內的窗口標籤與數字，否則 prompt 與程式邏輯不一致

---
## 2026-05-05 — LINE 週報顯示日文 fallback（annotation_status 過濾缺失，commit `b2864ea`）

### 問題
LINE 週報中出現日文標題（如「赤い糸 輪廻のひみつ」）而非中文，ZH 訂閱者收到 `name_zh = NULL` 的事件。

### 根因
`_fetch_upcoming_events` 未過濾 `annotation_status='pending'`。新爬取事件在 annotator 執行前 `name_zh`/`name_en` 為 NULL，若廣播在 09:00 pipeline **之前**手動觸發，pending 事件會進入 pool。

### 修復
在 `_fetch_upcoming_events` 加入 `.in_("annotation_status", ["annotated", "reviewed"])` 過濾。效果：pool 76 → 74（2 筆 pending 正確排除）。

### 教訓
- **任何廣播 query 必須加 `annotation_status` 過濾**，不能假設所有 `is_active` 事件都已標注
- 手動觸發廣播時，應先確認 pool 筆數是否比無過濾少（少 = 過濾正常運作）

---
## 2026-05-04（Session 2）— Web UI 多項修復 + selection_reason["ja"] 品質 + is_active 誤設還原（commits `a895e07`、`1b344f7`、`2989940`、`d9ff85f`、`d7ab41a`、`7a81969`、`0abd8db`、`dedfa81`、`b559520`）

### NextIntlClientProvider 缺少 `locale` prop（commit `dedfa81`）
- **問題**：`layout.tsx` 的 `<NextIntlClientProvider>` 未傳入 `locale` prop，日語（`/ja/`）與英語（`/en/`）頁面的所有 Client Component UI 文字顯示中文（預設 locale）
- **根本原因**：`locale` 是 `NextIntlClientProvider` 的必要 prop，缺少時 next-intl 靜默回退到預設語言，無任何 console error
- **修復**：加入 `locale={locale}` prop（`locale` 從 `params` 解構）
- **教訓**：`NextIntlClientProvider` 的 `locale` prop 是必填的——缺少時錯誤靜默，多語言 UI 全部顯示預設語言，極難追蹤

### FilterBar「電視頻道」選項永遠顯示 0 筆（commit `2989940`）
- **問題**：FilterBar 的「電視頻道」location type 選項永遠顯示 0 筆事件，從未有任何事件被過濾到
- **根本原因**：`location_name` 欄位從未包含「電視頻道」字串；此 filter 邏輯存在但資料模型不支援
- **修復**：完全移除該 filter 選項（`FilterBar.tsx` + `page.tsx`）
- **教訓**：Filter 選項必須有對應的資料模型支撐；無效 filter 選項比沒有 filter 更差（給使用者錯誤的期待）

### 事件詳情頁 section 順序重排（commits `d9ff85f`、`d7ab41a`、`7a81969`）
- **調整**：重排為 title+save → summary table → description → CTA（購票/外部連結）→ AI selection reason → sub-events → record links → FAQ
- **問題**：CTA 按鈕之前被放在 summary table 之前，description 之後才是 AI reason，順序不符合使用者閱讀流程
- **教訓**：事件詳情頁的 UX 順序：重要資訊（摘要表）→ 正文（description）→ 行動（CTA）→ 輔助資訊（AI 原因）→ 相關項目

### ReportSection 新增 `brokenLink` 回報類型（commit `0abd8db`）
- **修復**：`ReportSection.tsx` 新增 `brokenLink` 作為第三個回報類型，讓使用者可回報失效連結

### wrongSelectionReason 三語言 textarea（commit `dedfa81`）
- **問題**：`ReportSection.tsx` 只有單一 textarea，無法指定要修正哪個語言的 selection reason
- **修復**：拆成三個 textarea（中文 / English / 日本語）；新增 `selectionReasonAll` prop；submit 格式 `selectionReason:zh:text`（含語言前綴）
- **教訓**：多語言欄位的回報 UI 需要對應的語言選擇機制，單一 textarea 會造成語言混淆

### AdminReportsTable 解析格式改 `indexOf`（commit `b559520`）
- **問題**：用正則 `/^(zh|en|ja):([\s\S]*)$/` 解析 `selectionReason:zh:text` 格式（含 `selectionReason:` 前綴），regex 無法匹配正確捕捉
- **修復**：改用 `indexOf(":")` 多次切割：先找 `selectionReason:` 前綴，再切語言碼，再取文字
- **教訓**：解析多層冒號分隔格式，`indexOf` + `slice` 比 regex 更穩定可靠；regex `^` 錨點在含多層前綴時容易失敗

### confirm-report.ts TS2352 型別轉換（commit `b559520`）
- **問題**：`origRow as Record<string, unknown>` 直接型別斷言失敗，TypeScript 2352 error
- **修復**：改為 `origRow as unknown as Record<string, unknown>`；`filter(Boolean)` 加型別謂詞 `(x): x is string => Boolean(x)`

### selection_reason["ja"] 中文污染（49 筆，DB patch）
- **問題**：`annotator.py --backfill-tier1` 對 49 筆事件的 `selection_reason["ja"]` 欄位產生中文內容（而非日文），事件詳情頁日語 textarea 預填中文
- **根本原因**：GPT prompt 語言控制不夠嚴格，中文意外生成到 ja 欄位（可能 GPT 混淆輸出語言）
- **修復**：Python 腳本用假名正則偵測（無假名字元 → 疑似非日文），逐一呼叫 GPT-4o-mini 從 zh 欄翻譯成日文，覆寫 `selection_reason["ja"]`
- **教訓**：
  1. backfill 完成後**必須立即執行品質抽查**：`selection_reason["ja"]` 必須包含假名；無假名表示語言污染
  2. annotator backfill 完成後需執行 QA script 驗證多語言欄位

### is_active 批次誤設（342 筆還原）
- **問題**：一次性腳本意外將所有 `end_date < today` 的事件設為 `is_active=False`，342 筆受影響；已結束事件不可見
- **修復**：全部還原為 `is_active=True`
- **教訓**：`is_active=False` 只能由：(1) Admin 手動停用特定事件，(2) `merger.py` 去重時停用次要事件；**任何批次 UPDATE `is_active` 前必須確認符合這兩個來源之一**

---
## 2026-05-04 — main.py pipeline 補齊 enrich 步驟 + ks_cinema DB 修正 + 035 migration

### main.py pipeline enhancement — enrich steps 補齊

**問題：** 手動執行 `python main.py --source ks_cinema` 時，事件被 scrape + annotate 但 **未** enrich——電影片名得到直譯（`めぐる面影、今、祖父に会う` → `循環的面影`）而非官方片名（`車頂上的玄天上帝`）。`enrich_movie_titles()` 和 `enrich_person_names()` 只在 CI workflow 中以獨立 `annotator.py --enrich-movie-titles` / `--enrich-person-names` 指令執行，`main.py` 完全沒呼叫。

**修復：** `main.py` 新增 `from annotator import enrich_movie_titles, enrich_person_names`，在 `annotate_pending_events()` 之後、IndexNow 提交之前呼叫兩者。enrich 函數為 idempotent，CI 的獨立 enrich 步驟變成 no-op 二次 pass，不影響 CI。

**教訓：**
1. **Pipeline parity rule**：任何新增到 CI workflow（`scraper.yml`）的 post-processing 步驟，必須同步加入 `main.py` 的正常（非 dry-run）流程。否則手動 scraper 執行會產生品質不完整的結果。
2. 目前 `main.py` 完整 pipeline 順序：scrape → merger → annotate → enrich_movie_titles → enrich_person_names → IndexNow。
3. Idempotent enrichment 在 main.py 和 CI 雙重執行是安全的——只多幾個 DB query，不會產生重複寫入。

### ks_cinema 電影片名 DB 手動修正

**問題：** 6 筆 ks_cinema 事件的 `name_zh` / `name_en` 是直譯（GPT 音譯）而非官方片名。原因：事件在 `main.py` 補齊 enrich 步驟之前被手動 scrape。

**修正的事件：**
- `めぐる面影、今、祖父に会う` → 車頂上的玄天上帝 / Be with Me
- `台湾ハリウッド` → 阿嬤的夢中情人 / Forever Love
- `超低予算ムービー大作戦` → 導演你有病 / Out of Nowhere

**教訓：** 補齊 pipeline 後，對之前手動 scrape 的事件需一次性 DB patch。可用 `enrich_movie_titles()` 自動修正，或手動 UPDATE。

### ks_cinema sub-event hierarchy 修正

**操作：** 手動 DB 修正——3 筆 sub-event 設正確 `parent_event_id`；2 筆舊版 scraper 產生的 `_sub1` 記錄 deactivate（`is_active=False`）。

### 035_organizer_form_language.sql migration（Tier 1）

**狀態：** 已 apply 到 production DB，migration SQL 已 commit。新增欄位：`organizer`、`co_organizers`、`sponsors`、`organizer_type`、`event_form`、`primary_language`、`has_japanese_support`、`has_english_support`。含 CHECK constraints 和 GIN indexes。

### P0: Admin 修正保護 — re-annotation 時保留既有非 null 值（commit `9eab3aa`）

**問題：** Admin 透過 confirm-report 修正欄位（例：修正 name_zh）時，`annotation_status` 重設為 `pending`。下次 annotator 執行時，GPT 重新產生所有欄位，覆寫 admin 的修正值。

**修復：** `annotator.py` 新增 `_ai_or_existing()` 函數——在一般 re-annotation 模式（非 `--all`/`--id`）中，既有非 null DB 值優先保留，GPT 輸出只填補 null 欄位。同步修復 `irrelevant` status bug（`--fix-reviewed` 誤處理 irrelevant 事件）。

**教訓：** 當 admin correction UI 會重設 `annotation_status` 觸發重新處理時，必須保護已修正欄位不被 AI 覆寫。

### P1: field_corrections 明確持久化 — admin 修正永不被 AI 覆寫（commit `c393e93`）

**問題：** P0 的隱性保護（保留非 null 值）不足——有時 admin 需要覆蓋一個已有 AI 值的欄位，且該覆寫必須在無限次 re-annotation 中持久。

**修復：**
- 新建 `field_corrections` 表（migration 038b）：記錄每次 admin 修正 `(event_id, field_name, original_value, corrected_value, corrected_by)`
- Annotator 啟動時載入 `human_field_map`：event_id → 受保護欄位 set
- `_ai_or_existing()` 優先檢查 `_human_protected`——此 set 中的欄位 AI **永不覆寫**，即使 `--all` 模式
- `confirm-report.ts` 同步寫入 events 表和 field_corrections 表
- Annotator SYSTEM_PROMPT 新增 few-shot context：將過去修正紀錄注入 prompt，讓 GPT 學習正確模式

**Schema：** `field_corrections(id, event_id, field_name, original_value, corrected_value, corrected_by, created_at)`，`(event_id, field_name)` UNIQUE

**教訓：** Admin correction 保護需兩層：P0（隱性：保留非 null）+ P1（明確：field_corrections 表永久保護）。只有 P0 時，`--all` 模式或 null→非 null→不同值 的修正會遺失。

### Tier 1.5 Schema: organizer_url, price, event_status（commit `0d4a0de`）

**Migration 037：** 新增 `organizer_url text`、`price_amount numeric`、`price_currency text DEFAULT 'JPY'`、`event_status text DEFAULT 'scheduled'`，含 CHECK constraints。

**Annotator：** SYSTEM_PROMPT 新增 price parsing、organizer URL、event status 規則。新增 validators：`_validate_organizer_url`、`_validate_price_amount`、`_validate_price_currency`、`_validate_event_status`。

### Performer 欄位（commit `edd101e`）

**Migration 038：** `events` 新增 `performer text` 欄位。`base.py` + `types.ts` 同步新增 `performer`。

**Annotator SYSTEM_PROMPT：** 新增 PERFORMER EXTRACTION RULES——bare personal name，去除敬稱，非人物事件回傳 null。

**Detail page：** Rich Results JSON-LD 注入 `performer` property（Schema.org Event compliance），修復 4 個 Rich Results warnings。

### next-intl organizerType + eventForm namespace 缺失（commit `e6461c7` context）

**問題：** Detail page 使用 `getTranslations("organizerType")` 和 `getTranslations("eventForm")`，但三語言 JSON 中無對應 namespace/keys。next-intl 靜默渲染 raw key string（例：`organizerType.commercial_brand`），無任何錯誤。

**修復：** 在三語言 JSON 中新增 `organizerType`（9 keys）和 `eventForm`（12 keys）namespace，以及 6 個 event namespace keys。

**教訓：** next-intl missing keys 靜默失敗。新增 `getTranslations()` namespace 時，必須確認 ALL 3 message files 有對應 entries。驗證：`grep -n "key" web/messages/zh.json`。

### Admin Dashboard 增強（commits `6f97d82`→`eec0d90`）

- 新增 sources 和 creators stat cards（commit `6f97d82`）
- Source type map modal 新增 category filter checkboxes（commit `ec1ce39`）
- NGO category + 5 筆 source reclassification（commit `7373fd3`）
- Category pills on source list（commit `eec0d90`）
- Source type label refinements：百貨・商圈、台灣商家（commits `c3774a3`、`0d4a0de`）
- organizer_type / event_form filters（AdminEventTable，commit `ee1831b`）
- Tier 1 欄位視覺化：organizer, event_form, language support（commit `1fdb332`）

### wrongSelectionReason 3-locale textareas + NextIntlClientProvider locale fix（commit `dedfa81`）

**問題：** `NextIntlClientProvider` 使用錯誤的 locale prop；wrongSelectionReason report 只有單一 textarea。

**修復：** 修正 locale prop；wrongSelectionReason 擴展為 zh/en/ja 三個 textareas，讓 admin 分別修正各語言的 selection_reason。

### brokenLink report type（commit `0abd8db`）

新增 `brokenLink` 到 event report section，使用者可回報壞掉的 source/official links。

### Price regex 擴展（commit `e6461c7`）

`backfill_price_from_price_info()` regex 擴展以匹配 `¥1,500` 格式（原本只匹配 `1500円`）。Pattern：`r'[¥￥]?\s*([\d,]+)\s*円?'`。

---
## 2026-05-02 — 父事件 RLS 隱藏 + Quality page 缺地址誤報 + Admin UI 改善

### 父事件 RLS cross-status 問題（commit `f5931e0`）

**問題：** 子事件詳情頁「返回主事件」連結查詢父事件時，若父事件 `is_active = false`（已下架），anon-key client 因 RLS `Public read events` policy 靜默返回 null——不報錯、不 throw，連結直接消失。

**修復：** 父事件 lookup 改用 service role key（`SUPABASE_SERVICE_ROLE_KEY`），只 select `id, name_ja, name_zh, name_en`，不暴露其他欄位。

**教訓：**
1. Supabase anon-key + RLS 查詢關聯記錄（parent, linked entity）時，若目標記錄可能 `is_active = false`，必須用 service role key
2. Service role key 只用於 Server Component / route handler，**永不傳入 Client Component**
3. 只 select 必要欄位——不使用 `select("*")`

### Quality page 缺地址誤報排除（commits `229810f`、`f5931e0`）

**問題：** 缺地址 check 重新定義為「有場地名但無地址」（`location_name IS NOT NULL AND location_address IS NULL`），但仍有大量非 actionable 項目：
- `location_name` 含 `〒`（地址已嵌入名稱中）
- `location_name` 含 `オンライン`（線上活動，無實體場地）
- 短地名 ≤6 字元且無空格（如「東京」「香港」「岡山」，無更精確地址可填）

**修復：** DB 層加 `.not("location_name", "like", "%〒%")` 和 `.not("location_name", "ilike", "%オンライン%")`；client 層過濾短地名。

### Admin UI 改善（commits `1f48807`、`15d6ab3`→`bf22756`、`bc6d1e7`、`636a52f`）

- **批次新增分類**（`1f48807`）：AdminEventTable 新增 bulk add category 列——multi-select category picker → "Apply to N events" → 寫入 `category_corrections` + 選取自動重設
- **Sticky 合併容器**（`15d6ab3`→`bf22756`）：filter bar 和 bulk action bar 包在同一個 `sticky top-14 z-20` wrapper，避免兩列分別固定導致跳動
- **來源搜尋框**（`bc6d1e7`）：AdminSourcesTable 新增 keyword 搜尋，搜尋 name / URL / scraper_source_name（case-insensitive）
- **tea_alcohol 分類**（`636a52f`）：新增 `tea_alcohol` 到 `Category` union + `CATEGORY_GROUPS` group_arts（五感）

**教訓：**
1. Bulk action bar 和 filter bar 必須在同一個 sticky container——分開固定會導致 scroll 時跳動
2. Bulk add category 使用 `Set` merge（`new Set([...prev, ...catsToAdd])`）避免重複，並寫入 `category_corrections` 讓 AI 學習

---
## 2026-05-02 — 子事件 name_ja 片假名被 GPT 覆寫為漢字

**問題：** TIFF 子事件 re-annotation 時，GPT 把 `チャン・ツィイー` → `章子怡`、`ジャ・ジャンクー` → `賈樟柯`，破壞日文模式的片假名人名顯示。原因：子事件 upsert 直接取 `sub.get("name_ja")`，無任何保留機制。

**修復：**
1. DB patch：3 個 TIFF 子事件 `name_ja` 還原為 `raw_title`（片假名版本）
2. annotator.py：子事件 upsert 前查詢既有 sub-events，若 `name_ja`/`raw_title` 已存在則保留（跟父事件同樣的 preservation policy）

**教訓：**
1. 子事件的 `name_ja` / `raw_title` 也必須有 preservation 機制——GPT 不可靠地保留片假名
2. 首次 annotation 的 GPT output 通常較好（遵守 SYSTEM_PROMPT）；re-annotation 容易偏離
3. 保留邏輯：`existing_name_ja or gpt_name_ja`，與父事件的 `event.get("name_ja") or raw_title` 一致

---
## 2026-05-02（深夜 3）— Quality check 判斷欄位錯誤、competition 排除（commits `b82849d`→`80920ce`、`4ca383a`）

**問題一（commits `b82849d`→`80920ce`）：** `/admin/quality` 缺地點 check 查詢 `location_address IS NULL`，但詳情頁 render 的是 `location_name`。兩個欄位不同，check 結果與頁面顯示矛盾。

**修復：** DB query 改為 `.is('location_name', null)`；同時把 `gguide_tv` 排除從 JS filter 移到 DB 層：`.not('source_name', 'eq', 'gguide_tv')`。

**問題二（commit `4ca383a`）：** 競賽/補助類活動天生無實體地點，但被 quality check flag 為缺地點，無法清零。

**修復：** 加 `.not('category','cs','{"competition"}')` 於 DB query 排除 `competition` category 事件。

**教訓：**
1. Quality check 的判斷欄位必須與詳情頁顯示欄位一致——先查「前端 render 哪個欄位」再設計 check
2. 某些事件格式（競賽、補助、電視節目、線上直播）天生不符某些 check 條件，排除條件應在 DB query 層處理，不在 JS 層
3. 排除條件用 `.not('column','operator','value')` Supabase RPC 語法，不在 client 側 `.filter()`

---
## 2026-05-02（深夜 3）— robots.txt allowlist social bots、scholarship 標籤更新（commits `d9765bb`、`60cc2f1`）

**robots.txt（commit `d9765bb`）：** `facebookexternalhit` 和 `Twitterbot` 未在 `robots.ts` 明確許可，依賴預設 allow 行為。為確保 OG 預覽正確抓取，加入明確 `Allow: /` 規則。

**scholarship 標籤更新（commit `60cc2f1`）：**
- zh: 補助・獎學金 → 徵件・補助・獎學金
- en: Grants & Scholarships → Open Calls, Grants & Scholarships
- ja: 助成・奨学金 → 公募・助成・奨学金
- Label-only rename：只動三個 `messages/*.json`，不動 `types.ts`。

---
## 2026-05-02（深夜 2）— NHK annotator fallback 移除（nhk_rss 薄描述由 scraper 處理）

**變更：** 移除 `annotator.py` 中 `nhk_rss` 專用的薄描述 fallback 區塊（在 annotator 中用 `fetch_ref_text()` 補抓文章全文）。此功能已由 `nhk_rss.py` scraper 端在 `scrape()` 中直接處理（commit `6604f44`），annotator 端重複執行已無意義。同步移除 `from sources.base import fetch_ref_text` import。

**教訓：** 內容補齊（article enrichment）應在 scraper 端處理，不在 annotator 端。annotator 收到的 `raw_description` 應已包含所有必要內容。annotator fallback 造成重複 HTTP 請求且難以測試。

---
## 2026-05-02（下午）— locationOverseas i18n namespace 錯誤、分類標籤更新、新增分類（commits `049edd8`、`a4a6f75`、`7567ef0`、`8aee4de`、`1870c8a`、`24fcb3c`、`b62b385`、`dfc5aaf`）

**問題：** 新增 `locationOverseas` filter 時，修改腳本使用 `data["locationOverseas"] = label`，將 key 寫到 JSON 頂層，而非 `data["filters"]["locationOverseas"]`。`FilterBar` 使用 `const t = useTranslations("filters")` 呼叫 `t("locationOverseas")`，next-intl production 找不到 key，靜默回傳 key 名稱字串，導致 FilterBar 渲染異常、預設「進行中」timeMode 消失。

**修復（commit `049edd8`）：** 三語言 JSON 全部把 `locationOverseas` 從頂層移入 `filters.{}` 內。

**教訓：**
- `t("key")` 只查找 `useTranslations("<namespace>")` 指定的 namespace 下的 key
- 修改 `messages/*.json` 的腳本新增 key 時，必須確認目標 namespace：`data["filters"]["key"]` 而非 `data["key"]`
- next-intl missing key 靜默失敗（production 回傳 key name 字串，不拋錯）——需靠 `grep -n "key" messages/zh.json` 確認行號在正確 block（filters block 約 L10–L40，頂層約 L400+）

### 同日其他變更（分類標籤 + 新增分類）

- `senses` zh：台灣感性 → 台灣感性・認同（commit `a4a6f75`）
- `senses` en：Taiwan Senses → Taiwanese Identity & Sensibility（commit `7567ef0`）
- `senses` ja：台湾の感性 → 台湾の感性・アイデンティティ（commit `7567ef0`）
- `competition` ja：スポーツ・競技大会 → スポーツ・コンテスト（commit `8aee4de`）
- 新增 `folklore`（民俗・歲時）→ group_arts（commits `24fcb3c`、`b62b385`）
- 新增 `scholarship`（補助・獎學金）→ group_knowledge（commit `dfc5aaf`）

---
## 2026-05-02 — 全 *_zh 欄位簡繁轉換防護

**問題：** GPT-4o-mini 偶爾在 `description_zh` 輸出簡體中文（例：`1e375d6c` tokyoartbeat 事件整段簡體）。既有的 `_loc_zh()` 只保護 location 欄位，`name_zh`/`description_zh`/`business_hours_zh` 完全無防護。

**修復：**
1. 將 `_LOC_ZH_SIMP_TO_TRAD` 擴展為通用 `_SIMP_TO_TRAD`（~100 字元），覆蓋 location + description + name 常見簡體字
2. 新增 `_to_trad(val)` 函式，套用到所有 GPT 輸出的 `*_zh` 欄位（`name_zh`、`description_zh`、`business_hours_zh`），含 fix_reviewed 與 sub-event 路徑
3. `_loc_zh()` 改為內部呼叫 `_to_trad()`，不再維護獨立字表
4. 全 DB 掃描並修復 7 筆事件（3 筆 active）的簡體殘留
5. `auto_qa.py` 的 `SIMP_RE` 同步擴展，`ZH_FIELDS` 加入 `business_hours_zh`

**教訓：** SYSTEM_PROMPT 的繁體指令不足以 100% 防止 GPT 輸出簡體。必須在寫入 DB 前對所有 `*_zh` 欄位做 character-level 轉換。新發現的簡體字應同步更新 `annotator.py._SIMP_TO_TRAD` 和 `auto_qa.py.SIMP_RE`。

---
## 2026-05-02 — name_ja 不再由 GPT 覆寫（保留原始標題）+ 子事件原始日文名規則

**問題：** `annotate_pending_events()` 中 `update_data["name_ja"]` 使用 GPT 回傳的 `annotation.get("name_ja")`，覆寫了爬蟲抓取的原始標題。GPT 經常改寫日文標題（加上 context、截斷副標、替換用語），導致 `name_ja` 偏離原始資料。

**修復：**
1. `update_data["name_ja"]` 改為 `event.get("name_ja") or raw_title`——永遠保留原始標題
2. SYSTEM_PROMPT `NAME WRITING RULES` 改為告知 GPT「name_ja 直接複製 raw_title，不要改寫」
3. GPT 仍然生成 `name_ja`（JSON schema 不變），但此值只用於 sub-events（sub-events 無 raw_title）
4. SYSTEM_PROMPT 新增子事件規則：sub-event `name_ja`/`description_ja` 必須使用原始日文文本中的寫法。電影片名用日本上映名，人名用原始片假名/漢字記載。禁止翻譯中文/台灣人名成日文或自創片假名讀音

**連帶影響：**
- `name_ja_locked` 機制不再需要用於 annotator（flag 仍存在於 DB + scraper dataclass，向後相容）
- 原本的 SYSTEM_PROMPT 中關於「name_ja 必須 self-contained」的規則已移除

**教訓：**
- 日文原始標題是 source of truth，不應由 AI 重新詮釋
- 翻譯校正（片名、人名）只應套用在翻譯欄位（`*_zh`、`*_en`），不碰原文欄位（`*_ja`）
- 子事件日文名也適用同一原則：使用原始文本中的日文寫法，不發明新的寫法

### 同日其他 annotator 改善（commits `eaab464`、`fb568c4`、`28c1b41`、`6604f44`）

- **日期優先級翻轉**（`eaab464`）：`start_date`/`end_date` 改為 scraper-first（`event.get("start_date") or annotation.get("start_date")`）。之前 GPT 推斷的日期會覆蓋爬蟲精確提取的日期。
- **location_url GPT 提取**（`fb568c4`）：SYSTEM_PROMPT JSON schema 新增 `location_url`，讓 GPT 從 raw_description 中提取場地官網 URL。規則：只提取明確出現的 URL，不推斷；scraper 值優先；null 不覆蓋已有值。
- **google_news_rss 薄描述觸發文章抓取**（`28c1b41`）：當 `raw_description` < 400 字且 `source_name == 'google_news_rss'` 時，自動用 `fetch_ref_text()` 抓取原文補充。
- **nhk_rss 薄描述補齊 + pubDate 錨定**（`6604f44`）：NHK RSS snippet 通常 50-200 字，新增 `_NHK_THIN_BODY_CHARS=400` 閾值 + `fetch_ref_text()` 補充。`pubDate` 作為 `start_date` fallback anchor。
- **news movie title bracket fallback**：`enrich_movie_titles()` 和 `enrich_person_names()` 中，news source（`prtimes` 等）的 `_BRACKET_TITLE_RE` 搜尋改為先查 `raw_title`，找不到括號時再查 `name_ja`（因 annotator 可能在 name_ja 中加了括號標題）。

---
## 2026-05-02 — 人名校正擴展至所有事件（非僅電影）

**變更：**
- `person_name_lookup.py`：新增 `extract_katakana_names()`（regex 提取帶 ・ 的片假名人名）、`_search_person_eiga()`（eiga.com 人物搜尋）、`lookup_single_person()`（通用人名查詢）
- `_lookup_zh_via_wikipedia()` + `_lookup_zh_via_ja_wikipedia()`：新增 `strict` 參數——`strict=True` 時要求人物關鍵字匹配（zh.wikipedia）或 zh 跨語言連結（ja.wikipedia），阻止假陽性
- `annotator.py` `enrich_person_names()`：移除 `.contains("category", ["movie"])` 過濾，改為全事件掃描。電影事件走 eiga.com 電影頁結構化查詢（`strict=False`），非電影事件走片假名提取 + Wikipedia（`strict=True`）
- CI workflow step 名稱更新為「Enrich person names via eiga.com + Wikipedia (all events)」

**假陽性防範：**
- 問題：非電影事件中 `リン・インジュ` → `安永亜季`（日本人名，非目標）；`ホアン・ヤーリー` → `脊蛇屬`（蛇屬名）
- 解決：`strict=True` 模式要求 zh interlanguage link 或 snippet 含人物關鍵字，消除 CJK fallback 的假陽性
- 噪音過濾：最多 3 ・ 分段、每段 ≤7 字、噪音後綴排除（ホテル、センター 等）

**測試結果：**
- 林志玲、周杰倫、蔡英文、鄧麗君：全部正確 ✓
- ジョン・スミス（非華人）：正確 SKIP ✓
- 電影管線（赤い糸 輪廻のひみつ, 5 人）：未受影響 ✓

**教訓：**
1. Wikipedia 自由文字搜尋的 CJK fallback（`2 ≤ len(title) ≤ 4`）在非策展輸入下會大量假陽性——通用管線必須用 `strict=True`
2. eiga.com 不只有電影搜尋，也有 `/search/{name}/person/` 人物搜尋——適用於所有事件中的演員/導演
3. 噪音控制靠「regex 過濾 + Wikipedia 自過濾」雙層即可，不需要 GPT 前置提取

---
## 2026-05-02（深夜）— Realtime stale closure 修復、badge client component、Quality page 清理（commits `c3fe0bc`、`4a71258`、`cd4cc29`）

### 問題一：AdminReportsTable Realtime stale closure（commit `4a71258`）
`AdminReportsTable` 在 component 頂層建立 `supabase` client，再於 `useEffect` 中捕捉 → 可能捕捉到舊實例（stale closure）。同時只訂閱 INSERT，UPDATE 事件（confirm/dismiss）不觸發列表更新。

### 修復
1. `supabase` client 改在 `useEffect` **內部**建立，每次 effect 執行都取得新實例，徹底消除 stale closure。
2. 補上 `UPDATE` handler，讓另一個 admin session confirm/dismiss 後目前列表即時反映。

### 問題二：AdminTabNav badge SSR 靜止不動（commit `4a71258`）
`AdminTabNav` 是 Server Component，pending count 在頁面 SSR 時固定，新報告提交後 badge 數字不更新。

### 修復
建立 `AdminReportsBadge` client component：接收 `initialCount` 做 SSR 初始值，訂閱 Realtime INSERT（count+1）和 UPDATE（重新 fetch count），badge 即時更新。

### 教訓
- **Supabase client 必須在 `useEffect` 內部建立**：在頂層建立再傳入 effect 會形成 stale closure，可能捕捉到已失效的舊 client 實例。（已新增至 SKILL.md Supabase Realtime 章節）
- **Server Component 中的動態 UI 必須抽出為 Client Component + Realtime**：SSR 抓取的靜態值永遠不會更新，任何需要即時性的計數器都必須走 Client Component + Realtime 分離模式。
- Admin pages 訂閱應同時包含 `INSERT` 和 `UPDATE`：兩個 admin session 同時開啟時，UPDATE 才能讓另一端的操作同步顯示。

### 問題三：Quality page expired-but-active 欄位無法操作（commit `cd4cc29`）
Archive cron 一天只跑一次，白天過期的事件留在「expired-but-active」欄位，但點擊後無任何可執行操作。

### 修復
移除整個「expired-but-active」section，避免顯示永遠有值但無法操作的清單。

### 教訓
無操作 Quality check section（無 fix button / batch action，且數值永不清空）應直接移除。（已新增至 SKILL.md Admin Quality Page 章節）

### 問題四：ReportSection wrongCategory 無預填（commit `c3fe0bc`）
使用者勾選「wrongCategory」時，`suggestedCategories` 為空，需手動重新選取目前分類，操作負擔高。

### 修復
`ReportSection.tsx` 新增 `currentCategories?: Category[]` prop；勾選 wrongCategory 時自動預填事件目前分類。

### 教訓
所有「修正建議」欄位應以目前值為預設。

---
## 2026-05-02 — Admin 頁面 SSR 快取無效化 + Realtime 自動重新整理（commits `cad13a2`、`046d8cd`、`08b4912`）

### 問題一：`router.push()` 後顯示舊快取
`AdminEditClient.handleSave()` 儲存後呼叫 `router.push('/admin')`。admin 列表頁是 SSR，導航回去時 Next.js router cache 尚未失效，`is_active` 等欄位顯示舊值，即使 DB 已更新。

### 問題二：confirm/dismiss 後同樣顯示舊快取
`AdminReportsTable.handleConfirm()` / `handleDismiss()` success 路徑導航回 `/admin`，同樣遇到 SSR 快取問題。

### 問題三：AI 建立報告後頁面不自動更新
`/admin/reports` 頁面不會自動顯示新報告，需手動重新整理。

### 修復
1. `AdminEditClient.handleSave()`：在 `router.push()` **前**加 `router.refresh()`。
2. `AdminReportsTable.handleConfirm()` / `handleDismiss()`：success 路徑各加 `router.refresh()`。
3. `AdminReportsTable`：新增 Supabase Realtime 訂閱 `{ event: "INSERT", table: "event_reports" }`，INSERT 後重新 fetch 完整 row（含 joined event），去重後插入列表頂端；unmount 時 `removeChannel()` 清理。

### 教訓
- **SSR 快取無效化**：Client Component 執行 mutation 後導航回 SSR 頁面，**必須**在 `router.push()` 前加 `router.refresh()`，否則頁面顯示舊快取。這是 Next.js App Router 的必要模式，不是 optional。
- **兩種即時更新模式應同時使用**：
  - **Realtime 訂閱** → 同一 tab 的即時更新（新 row 出現、狀態變更同步）
  - **`router.refresh()`** → 跨頁面導航（從編輯頁 / 審查頁回到列表頁）
  兩者覆蓋不同場景，缺一不可。
- Admin 列表元件的 `useEffect` 應同時訂閱 `INSERT` 和 `UPDATE`，fetch 完整 row（含 join）再更新 state。

---
## 2026-05-02 — GPT 副標題截斷修復（annotator.py SUBTITLE RULE + 批次 DB 修正）

### 問題
`annotator.py` GPT-4o-mini 遇到學術論文格式標題（`主標――副標`）時，習慣性省略副標，只翻譯主標。`name_ja_locked` 保護 `name_ja` 不被覆寫，但 `name_zh`/`name_en` 仍由 GPT 生成，仍會截斷。

### 修復
1. **SYSTEM_PROMPT 新增 SUBTITLE RULE**（`annotator.py`）：
   > 當 name_ja 含 `――`/`──`/`―`/`—` 副標題分隔符時，name_zh 和 name_en 必須包含完整副標題，不得截斷。
2. **批次 DB 修正**：掃描 15 筆 `name_ja_locked=True` 事件，找出 4 筆副標被截斷：
   - `116cadee`（台灣地方選舉 + 桃園觀音新屋）
   - `3dbfecbb`（釋迦出口 + 政治經濟學）
   - `8339ed6f`（朱西寧 + 美援體制關係）
   - `47db1bb2`（1937 女性教育 + 機構列表）

### 教訓
- **`name_ja_locked` 只保護 `name_ja`，不保護 `name_zh`/`name_en`**。結構化來源的副標題翻譯仍需靠 SYSTEM_PROMPT 規則，或手動修正。
- GPT 翻譯學術副標題的準確性必須在部署後抽查，不能只依賴自動 annotate。
- 新增含副標題的學術論文事件後，建議執行：`SELECT id, name_ja, name_zh, name_en FROM events WHERE name_ja_locked AND name_ja LIKE '%――%';` 確認翻譯完整。

---
## 2026-05-02 — 新增 `docs/TRANSLATION_PIPELINE.md` 翻譯管線文件

- **內容**：完整記錄 6 層翻譯管線（爬蟲層 → DeepL 回退 → GPT-4o-mini 標注 → 官方片名補全 → 人名修正 → 前端 Fallback Chain），含 CI 執行順序、CLI 參數、sub-event 翻譯、admin feedback loop、欄位清單。
- **同步**：`docs/ARCHITECTURE.md` 已新增交叉連結。
- **無新 coding rule**：此為純文件化工作，未發現新的 coding 教訓。

---
## 2026-05-02（下午）— generate.py load_dotenv、not-viable 來源、Admin 篩選預設值、eurospace lookup_movie_titles（commits `d94fc80`、`29046ad`、`f905ee2`）

### auto_scraper/generate.py load_dotenv 修復（commit `d94fc80`）
- **問題**：本機 `python -m auto_scraper.generate --source-id <id>` 執行崩潰：`KeyError: SUPABASE_URL`。
- **根本原因**：`generate.py` 無 `load_dotenv()` 呼叫；`main.py` 和 `annotator.py` 因為有 `load_dotenv` 所以正常，但 generate 是獨立入口。
- **修復**：在 `generate.py` import 區塊後加 best-effort `load_dotenv()`（`try/except ImportError` 包圍）。CI 用 secret，load_dotenv 為 no-op，不受影響。
- **教訓**：**任何有 `-m module` 獨立 CLI 入口的 Python module 都需要 `load_dotenv()`**。不能依賴父 module（main.py）已先執行 load_dotenv。→ 已加入 scraper-expert/SKILL.md § auto_generate Pipeline。

### source 126/148 標記 not-viable（純 DB 操作）
- source 126（TAP）：FullCalendar SPA，React 動態渲染，DOM 無事件元素 → not-viable。
- source 148（Zepp Tokyo）：Cloudflare JS challenge 攔截 Playwright；無標準 URL pattern → not-viable。
- **操作方式**：直接 `UPDATE research_sources SET auto_scraper_status='not-viable', auto_scraper_failed_reason='...'`，不需走 auto_generate。
- **新增 not-viable 判定準則**：
  - Cloudflare JS challenge → not-viable（Playwright stealth 無法可靠繞過）
  - SPA 動態行事曆（FullCalendar / React）→ not-viable（事件不在初始 HTML DOM 中）

### Admin 篩選預設值修復（commit `29046ad`）
- **問題**：AdminEventTable 預設 filter `active` 讓管理員只看到 active 事件，遺漏 pending / archived。
- **修復**：預設改為 `all`。
- **教訓**：後台管理頁預設應 `all`，前台頁預設應 `active`。

### eurospace.py 加入 lookup_movie_titles（commit `f905ee2`）
- eurospace 為最後一個未整合 `lookup_movie_titles` 的 cinema scraper。
- import 後在 `Event()` 建構前呼叫，silent failure（lookup 失敗時回傳 None，不中斷 scrape）。
- 詳細記錄在 scraper-expert/history.md 2026-05-02 頂部條目。

---
## 2026-05-02 — record_links JSONB bug、name_ja_locked 機制、Pass 3 孤兒誤殺 WARNING（commits `0cdad90`、`180c495`）

### record_links JSONB bug 修復
- **問題**：`database.py` 的 `_event_to_row()` 用 `json.dumps(links)` 傳給 Supabase SDK，JSONB 欄位存入字串而非陣列；前端 `.map()` 在字串上呼叫 → TypeError → HTTP 500。
- **修復**：直接傳 Python `list` 物件，移除 `json.dumps()`。Supabase Python SDK 自動序列化 Python native types。
- **教訓**：Supabase SDK JSONB 欄位（`jsonb`、`jsonb[]`）**必須傳 Python `list`/`dict`，絕對不能用 `json.dumps()` 先序列化**。`json.dumps()` 會造成雙重編碼，最終存入 `"[{...}]"` 字串而非 JSONB 陣列。→ 已加入 scraper-expert SKILL.md § Supabase SDK — JSONB Field Rules。

### name_ja_locked 機制（commits `0cdad90`、`180c495`）
- **設計**：`name_ja_locked: bool = False` 加入 `Event` dataclass；`database.py` `_event_to_row()` 在 True 時寫入 DB；`annotator.py` 在 True 時跳過 `name_ja` 覆寫（其他欄位照常生成）。
- **DB**：`supabase/migrations/034_name_ja_locked.sql`（`DEFAULT false`，不需 backfill）。
- **首次適用**：`taiwanshi.py` 的學術論文子活動（`題目:` 欄位抓取的精確標題）。
- **教訓**：「scraper 已有精確答案，annotator 不應覆寫」的場景，應用 `locked` flag 而非事後 DB patch。鎖定條件：標題來源是結構化定義欄位（`題目:` / 官方片名），而非自由文字推斷。

### ⚠️ Pass 3 孤兒誤殺 — 程式碼尚未修復
- **問題**：`merger.py` Pass 3 誤 deactivate 了有效父事件（`00ae1ea8`、`dfb490c8`）的所有子活動（共 12 筆）。
- **已做**：手動 DB hotfix 還原（`UPDATE is_active=True WHERE parent_event_id IN ('00ae1ea8...', 'dfb490c8...')`）。
- **尚未修復**：`merger.py` 程式碼未改動，下次執行仍可能再次誤殺。
- **需要的修復**：Pass 3 在清除孤兒前，加保護條件——只有當父事件的 `secondary_source_urls` 非空（即真正被 Pass 1/2 合併為 secondary）時，才允許清除其孤兒子活動。若父事件本身只是被「錯誤合併」成 secondary，此保護可防止連帶誤殺。

---
## 2026-05-02 — merger richness tiebreaker + MERGER_WORKFLOW.md（commits `19a2067`、`d4e9227`）

**問題：** `merger.py` Pass 1/3 在兩個來源 `SOURCE_PRIORITY` 相同時，以遍歷順序決定 primary，可能選到欄位空洞的事件。

**修復：**
- 新增 `_richness_score()`（0–10 分）：`official_url`/`start_date`/`end_date`/`location_address`/`location_name` 各 +1；`raw_description` 每 200 字 +1（上限 5）。
- Pass 1/3 priority 比較改為嚴格 `<`/`>`；相同 priority 時比 richness score。
- `location_address` 補入 SELECT 查詢欄位。
- 新建 `docs/MERGER_WORKFLOW.md`：四個 Pass 規則、SOURCE_PRIORITY 表、決策流程、幂等性保證、FAQ。

**教訓：** SOURCE_PRIORITY 相同的來源配對，一定要 richness tiebreaker，不能依賴遍歷順序。新建官方來源時同步設定 SOURCE_PRIORITY。

---
## 2026-05-02 — Person Name Lookup 系統（movie 事件人名修正）

**建構內容：**
- 新增 `scraper/person_name_lookup.py`：查詢電影演員/導演的正式中英文姓名
- 策略：eiga.com 電影頁 → 取得演員列表（角色、片假名、person URL）→ eiga.com 人物頁（英文名＋出身國）→ zh.wikipedia 搜尋（中文名）
- 新增 `annotator.py` 的 `enrich_person_names()` + CLI flag `--enrich-person-names`
- 使用 GPT-4o-mini 修正 desc_zh 中的錯誤音譯人名（`_fix_person_names_gpt()`）

**DB 修正：**
- Event `4a8772ec`（cinemart_shinjuku, 赤い糸 輪廻のひみつ）：「紀德恩」→「九把刀」
- Event `f970e4e3`（shin_bungeiza, 赤い糸 輪廻のひみつ）：desc_zh 修正為正確人名（九把刀、柯震東、宋芸樺、王淨）

**教訓：**
1. GPT 音譯人名不可靠：片假名→中文會產生錯誤音譯（ギデンズ・コー →「紀德恩」而非「九把刀」），藝名/筆名尤其嚴重
2. eiga.com 人物頁有英文名但無中文名，需 Wikipedia 補查
3. Wikipedia 搜尋需加出身國消歧義（「Wang Ching」→ 加「台灣」才能找到「王淨」）
4. ja.wikipedia 條目標題對中國/台灣人常直接用 CJK（搜「クー・チェンドン」→ 條目「柯震東」），可作 fallback
5. eiga.com 演員名含角色名前綴（「孝綸（シャオルン）クー・チェンドン」），需 regex 剝離
6. desc_zh 的錯誤人名是 GPT 音譯產物，無法用簡單字串替換修正，必須用 GPT 辨識並替換
7. Wikipedia 人物關鍵字過濾（演員/導演/出生）防止假陽性，優先選短標題（2-4 字）

---
## 2026-05-02 — competition 標籤更名（commit f3cae57）

- zh: `競技・競賽` → `競賽・運動`；en: `Competition & Contest` → `Sports & Competition`；ja: `コンテスト・大会` → `スポーツ・競技大会`
- 只更新 `web/messages/zh.json`、`en.json`、`ja.json`；不需動 `types.ts`（`Category` union value 未改）
- 教訓：若只改分類標籤的**顯示文字**而非 value，無需執行 `tsc --noEmit`，但養成習慣可執行確認

---
## 2026-05-02 — Auto-scraper Phase 2.1/2.2/2.3 實作（commits `b6e1768`、`f9eff43`、`d23be68`）

**Phase 2.1（`b6e1768`）— Schema injection + failure artifacts：**
- `generate.py` 模組初始化讀取 `auto_scraper/spec_schema.json` 至 `SPEC_SCHEMA_TEXT`；user message 開頭 prepend schema + 必填欄位 checklist。
- spec-invalid 路徑新增 prompt.txt / sample.html / meta.json 持久化。
- **症狀**：修前 GPT-4o 三次重試都漏 `base_url`；修後 schema 變成 grounding 上下文。

**Phase 2.2（`f9eff43`）— detail_url fallback + 完整 sandbox-failed artifacts：**
- `template.py.j2` 在 `DETAIL_LINK_SELECTOR == ""` 時，從 card 內抓第一個 `<a href>`，避免 `source_url = page.url`（listing URL）導致全 card 因 `source_id_url_pattern` 不符而被 skip。
- sandbox-failed 路徑補寫 spec.json / generated.py / dry_run.txt。
- **驗證**：Artist Cafe Fukuoka 0 → 12 events。

**Phase 2.3（`d23be68`）— Pre-sandbox selector validation + LLM grounding：**
- SYSTEM_PROMPT 加硬規則：只准用 sample HTML 中 verbatim 出現的 class/ID；明文列出常見幻覺（`.event-card` / `.event-list-item` / `.c-event-list__item-title`）；建議優先使用 tag selector（`article`、`li`）。
- 新增 `_validate_selectors_against_html()`（BeautifulSoup，~50ms）：確認 `card_selector` ≥ 1 個元素 + `field_selectors.title/date` 在第一張 card 內可命中。違規回灌 LLM retry 訊息。
- **效益**：fast-fail 改成 spec-invalid（無 Playwright spawn），單次失敗從 ~30s + $0.04 降至 ~50ms + 0 美金。

**運維事故：** batch e2e 中段觸發 OpenAI 月度額度耗盡（429 `insufficient_quota`），全 org 呼叫直接停擺。`--budget-usd` per-call guard 不保護 org-level 月配額——需另外監控（見 Engineer SKILL § OpenAI Org-Level Quota Monitoring）。

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

**教訓（已廢止）：** ~~scraper `archive_ended_events()` 的 cutoff 必須與 admin quality page 的 `today` 截止一致。~~
> **⚠️ archiver 已於 2026-05-06 完全刪除**：`archive_ended_events()` 已從 codebase 移除，此教訓不再適用。事件 `is_active` 現為純手動管理。

---

## 2026-05-06 — archiver 完全刪除

**決策：** `archive_ended_events()` 及所有相關呼叫從 `scraper/database.py` 和 `scraper/main.py` 移除。

**影響：** 事件的 `is_active` 狀態不再由每日 CI 自動管理。停用／激活需透過 Admin UI 或手動 DB 操作。Quality page 的「已過期」清單仍顯示，但不再有自動下架動作。

**教訓：** 過去活動（含學術研討會 sub-events）激活後永遠保持激活狀態，不會被 CI 覆蓋。`work_id` 連結作為語意保留信號仍建議保留，但其「bypass archiver」的技術作用已消失。

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

## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 


--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 


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

## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 


--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 


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

## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 


--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 


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

## 2026-06-07 — Hybrid Venue (Physical + Online) marking rule 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 混合型音樂/表演活動（現場+線上，如 380c0ab2-1713-4bc9-86c5-6101d8ec741a）常被誤標為純線上，遺漏地址 | 舊版 annotator 規則將線上活動設為優先，且未規範並列展示 | 更新 annotator.py SYSTEM_PROMPT 規範 Hybrid 事件需同時標註「會場 / オンライン」與保留實體地址 | 複合參與模式應採用「訊息累加」而非「路徑覆寫」。現場名稱與線上都要標。 


--- 

## 2026-06-07 — Taiwan region filter & Taiwan city chip support in Admin UI 

**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓** 
2026-06-07 | 後台 Admin UI 遺漏日本地址 chip，且缺乏台灣區域過濾與縣市標籤 | ① 日本地址 Regex 因 〒 錨點失敗；② regionPrefectures.ts 缺少 taiwan 定義；③ AdminEventTable.tsx 缺少台灣過濾選項 | ① 移除 Regex 錨點並同步台日提取邏輯；② 在 regionPrefectures.ts 新增 22 縣市對應之 taiwan 區域；③ 更新過濾器 UI 增加台灣選項 | 所有的都道府縣/縣市提取（Backend Py & Frontend TS）必須保持 Regex 同步，且 UI filter 需手動跟進新區域的定義。 


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
