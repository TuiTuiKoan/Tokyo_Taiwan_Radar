# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-04-28 — Agent handoff 功能實現：.prompt.md vs .agent.md 混淆
**錯誤：** 設計了兩個工作流（update-history 和 validate-deploy），創建了 `.prompt.md` 文件並在 6 個 agent 的 `handoffs:` 中引用，但 handoff 按鈕在 VS Code 中沒有出現。

**根本原因：** VS Code Copilot Chat 的 `handoffs:` frontmatter 中的 `agent:` 字段**必須指向 `.agent.md` 文件的 name**，不能指向 `.prompt.md` 文件。`.prompt.md` 文件是獨立的 `/` 命令任務，不是 agent。

**修復方法：**
1. 刪除 `.github/prompts/update-history-skill-agent.prompt.md` 和 `validate-merge-deploy.prompt.md`
2. 創建 `.github/agents/update-history-agent.agent.md` 和 `.github/agents/validate-merge-deploy.agent.md`
3. 設置 `user-invocable: false`（只通過 handoff 調用，不在 agent 選擇器中顯示）
4. 在 6 個主要 agent 的 handoff 中添加 `prompt:` 字段（預填中文指令）

**Lesson：**
1. **Custom agents 有三種引用方式**：
   - `.prompt.md` → 通過 `/` 命令或 `/prompts` 調用，獨立任務
   - `.agent.md` → 通過 agent 選擇器調用或作為 handoff 目標，持久化角色
   - Handoff 中的 `agent:` 只能指向 `.agent.md` 文件，不能指向 prompt

2. **Handoff 完整格式**：
   ```yaml
   handoffs:
     - label: "按鈕文字"
       agent: AgentNameFromFile
       prompt: "預填指令"
       send: false  # 可選，false=用戶點擊後需手動發送
       model: "Claude Sonnet 4.5 (copilot)"  # 可選
   ```

3. **工作流設計需考慮調用方式**：若需通過 handoff 按鈕一鍵調用，必須建立 `.agent.md`；若僅作偶發任務，`.prompt.md` 足夠。

---
## 2026-04-28 — Reviewed 活動缺翻譯：annotator 永久跳過 reviewed 狀態導致翻譯缺漏
**錯誤：** 11 個活動被標記為 `reviewed` 後，`name_zh` / `name_en` 仍為 NULL。後台顯示活動標題為空白，前台無法正確顯示語言版本。

**根本原因：** `annotator.py` 的 query 一律排除 `annotation_status = 'reviewed'`（line 276: `.neq("annotation_status", "reviewed")`），導致這些活動**永遠不會再被 AI 翻譯**，即使翻譯欄位是空的。

**修復（三層防護，Option C）：**
1. **DB 緊急修復**：把 11 筆缺漏活動改回 `pending`，手動執行 `python annotator.py`，完成後確認 0 筆缺漏。
2. **annotator.py `--fix-reviewed` 旗標**：新增模式，只查詢 `reviewed + name_zh/name_en IS NULL` 的活動，補齊翻譯欄位，完成後維持 `annotation_status = "reviewed"`（不降級，不覆蓋 category / 日期）。
3. **scraper.yml CI 步驟**：`python main.py` 之後加 `python annotator.py --fix-reviewed`，每日自動掃描修復。
4. **AdminEventTable 紅色徽章**：每列若 `name_zh` 或 `name_en` 為 NULL，顯示 `⚠ name_zh / name_en` 提醒管理員。

**Lesson：**
1. **設計 annotation_status 保護規則時，必須同時考慮「已 reviewed 但翻譯未完整」的邊界狀況**。
2. 事件審核前應確認所有關鍵翻譯欄位已填齊。
3. 規則已寫入 SKILL.md §Reviewed Event Translation Guard。

---
## 2026-04-28 — 翻譯大規模回歸：scraper commit 意外洗掉 web/messages
**錯誤：** commit `1d3cd1c`（標題：fix scraper expand taiwan_matsuri）在修改 scraper 的同時，把 `web/messages/zh/en/ja.json` 覆蓋成舊版快照，將之前四、五個翻譯 commit 的成果全部洗掉。受害清單：
- `categories` 遺失：`competition`、`indigenous`、`history`、`urban`、`workshop`、全部 `group_*` 群組標籤（5 個）
- `categories` 標籤值還原為舊版：`performing_arts` en/ja、`geopolitics` en/ja
- `filters` 遺失：`timeModeAll`、`locationOnline`
- `admin` 遺失：`source`、`annotationLabel`、`annotationStatusLabel`、`scrapedAt`、`filterAnnotatedShort/ReviewedShort/ErrorShort/PendingShort`、`selectAll`、`bulkHide/Show`、`bulkForceRescrape`、`forceRescrapeOn/Off/Queued`、`statsTotalEventsLabel`、`statsActiveCount`、`statsPendingLabel`、`statsUsersLabel/Desc`、`statsReportsLabel/Desc`、`pendingSummaryInactiveOnly`、`bulkCommonCategories/Hint`

**根本原因：** AI 在大 context 中同時持有新舊版翻譯快照，將舊版本作為整份 JSON 輸出，覆蓋了所有中間的增量改動。

**修復：** 以 Python 腳本從 `b5a574a` / `65b90ca` / `471b66d` commit 取回正確值，逐一 merge 回三個語言檔案，並以 assert 驗證後 push。

**Lesson：**
1. **Scraper / non-web commit 絕不應修改 `web/messages/*.json`**
2. 翻譯 key 只增不減；刪除 key 前必須確認 codebase 無任何引用
3. 規則已寫入 SKILL.md §i18n Regression Prevention

---
## 2025-05-04 — Session 61b5118d 效率復盤：三個高工具數反模式
**觀察：** session `61b5118d` 共 54 回合、945 次工具呼叫，平均 17.5 次/回合（正常 < 12）。
分析出三個反模式：
1. **URL + 隱含大範圍**：貼 URL + 「請檢查類似狀況」→ 全域掃描（T04 61 tools, T12 68 tools）
2. **「請繼續做 XXX」連發**：同類爬蟲拆成 7 輪分別要求，每輪重新載入 context（T08–T14）
3. **問題 + 修正 + 規則更新三合一**：每個 bug 立即觸發 fix + history + skill 三連寫（T21→T22 71 tools）

**改善規則（已寫入 `session-analytics/SKILL.md`）：**
1. 指定明確範圍：「僅修這個 event，規則稍後批次更新」
2. 一次列出全部任務：「建 A、B、C 三個爬蟲，按順序，每完成告訴我」
3. 累積再批次：「先修 bug，我說『批次更新 skill』時再一次整理」

**Lesson：** 提示模式本身就是可優化的成本來源。每月 `--days 30` 確認效率趨勢，高峰 session 用 `--verbose` 定位回合後，對照三個反模式判斷原因。

---
## 2026-04-26 — AdminEventTable filter label/style regressions repeated across multiple commits
**Error:** Three UI fixes (`tFilters("search")` search label, `tFilters("category")` category label, `bg-gray-50` category button) were re-introduced and re-regressed multiple times because later commits modifying the same file for unrelated reasons (bulk-toggle refactor, reannotate label rename) overwrote the corrected lines with default values.
**Fix:** Re-applied the three fixes; added protected-invariants rule to `engineer/SKILL.md`; added regression entry to `engineer/history.md`.
**Lesson:** Files with frequently-touched UI logic accumulate "sticky regressions". The architect plan for any `AdminEventTable.tsx` change must explicitly mention the protected invariants as a check item.

---
## 2026-04-26 — Online canonical form corrected: location_address must be 'オンライン', not NULL
**Error:** Previous session established `location_address = NULL` as the canonical form for online events. This was wrong: it caused online events to appear in the `tokyo` admin filter (which treats NULL address as "Tokyo"), and `other_japan` filtering relied solely on `location_name` to exclude online events, creating fragile single-point-of-failure logic. The `AdminEventTable.tsx` `other_japan` filter had no online exclusion at all, meaning online events would appear there too.

**Fix:**
1. New canonical form: `location_name = 'オンライン'`, `location_address = 'オンライン'`. Both columns set. DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
2. `peatix.py`: all 3 places that set `location_address = None` for online events changed to `= 'オンライン'`.
3. `connpass.py` + `doorkeeper.py`: `_normalize_location_address()` now returns `'オンライン'` instead of `None`.
4. `AdminEventTable.tsx`: added `if (addr.includes('オンライン')) return false` to `other_japan` filter.
5. `page.tsx`: updated comment; filter logic unchanged (still queries `location_name`).
6. DB: patched 7 peatix online events (`location_address = 'オンライン'`, zh/en translations set).

**Lesson:** `location_address = NULL` must not be used as a sentinel for "online" — NULL means "unknown/unset", not "online". Scrapers must always set `location_address = 'オンライン'` for online events. Any filter that gates on `location_address IS NOT NULL` will mis-classify events if online events have NULL address. Updated "Online Location Standard" rule in SKILL.md.

---
## 2026-04-26 — Online location filter broken: queried wrong column + scrapers lacked normalization
**Error:** The `location=online` filter in `page.tsx` queried `location_address ILIKE '%オンライン%'`. After the correct normalization (online events should have `location_address = NULL`), the filter returned 0 results. Additionally:
1. Several peatix events had `location_name = 'オンライン（Zoom）'` with non-null address — the `(Zoom)` suffix was not canonicalized and the address was not cleared.
2. `connpass.py` and `doorkeeper.py` had no online detection at all — API fields `place`/`venue_name` containing 'オンライン' were passed through without normalization.
3. `other_japan` filter excluded online via `location_address NOT ILIKE '%オンライン%'` which also failed once addresses became NULL.

**Fix:**
1. `page.tsx`: online filter → `location_name ILIKE '%オンライン%'`; other_japan exclusion → `location_name NOT ILIKE '%オンライン%'`.
2. `peatix.py`: added final canonicalize step after all fallbacks: if `location_name` matches online marker → `'\u30aa\u30f3\u30e9\u30a4\u30f3'`, address = None.
3. `connpass.py` + `doorkeeper.py`: added `_ONLINE_RE`, `_normalize_location_name()`, `_normalize_location_address()` helpers.
4. DB: cleared address for 7 active peatix events with online markers.

**Lesson:** The canonical online event representation is **`location_name = '\u30aa\u30f3\u30e9\u30a4\u30f3'`, `location_address = None`**. Any query filtering for online events must check `location_name`, not `location_address`. All scrapers must normalize their output before building the Event object. Added “Online Location Standard” rule to SKILL.md.

---
## 2026-04-26 — Peatix online event incorrectly assigned a physical address (×2 errors in same session)
**Error:** Event `05aefbdf` (周美花講演) is a hybrid/online event. Peatix renders its LOCATION block as a single line `"LOCATION\n\nOnline event"` — no second group. The scraper's primary regex (`LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})`) requires two groups separated by a blank line, so it didn't match. All CSS and regex fallbacks then ran, finding:
1. A campus name from the description body text → `location_name = '桜美林大学新宿キャンパス'`
2. `東京都新宿区` from the description → `location_address`

In the same session, the previous turn had wrongly "verified" and patched this same event with the full campus address `東京都新宿区百人町3-23-1`, compounding the error.

**Fix:**
1. Added `is_confirmed_online` guard in Peatix scraper: detect `LOCATION\n\n(Online event|オンライン|…)` FIRST, set the flag, and skip ALL subsequent address fallbacks.
2. Fixed final body-text online fallback to set `location_address = None` (was `'オンライン'`).
3. Patched DB event `05aefbdf`: `location_name='オンライン'`, all address fields `None`.

**Lesson:** When a Peatix LOCATION block contains an online marker, it must **immediately short-circuit all address extraction**. Address fallbacks must never run against the event description body — venue names mentioned in prose ("会場…桜美林大学") are conditional/secondary and must not become `location_address`. Added rule to SKILL.md under Online Events.

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.
