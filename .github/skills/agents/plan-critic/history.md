# Plan Critic History

新條目加在頂部。格式：日期 / 錯誤 / 修正 / 教訓。

---

## 2026-08-02 — 建議「歸檔補年月前綴」，卻沒查 slug 由誰決定，害計畫採用會靜默改名的做法

**錯誤：** 批評 workstream-status-automation 計畫時，正確抓到「`docs/specs/archived/` 目錄不存在，實際是 `archive/`」，
但順手依 `docs/specs/README.md` 的 `archive/$(date +%Y-%m)-<slug>` 規約，要求 Architect 補上年月前綴。
Architect 照做，寫進修訂版 A1.1。下一輪才查出 `build-specs-snapshot.ts` 的 `listSpecsForStatus()` 是以
`loadSpecFromDir(status, entry.name, full)` 呼叫，**slug 直接取自目錄名稱**，且全檔從不讀 frontmatter 的 `slug:`（`data.slug` 零命中）。
因此加前綴會讓看板 slug 變成 `2026-08-<slug>`、詳情頁網址失效、frontmatter 與看板顯示值永久不一致。
更諷刺的是，repo 內唯一的歸檔實例 `archive/feedback-loop/` **根本沒有日期前綴**——README 規約與實況本來就矛盾，而我只採信了 README。

**修正：** 第 2 輪 critique 第 4.1 節自我更正，改建議歸檔不加前綴（與 `archive/feedback-loop` 一致）並同步修 README，
且要求驗收新增不變量「frontmatter `slug` == 目錄名稱」。

**教訓：**
1. **建議任何命名／路徑規約前，先追消費該名稱的 parser 實際讀哪個欄位。** 目錄名、frontmatter 欄位、URL 參數可能來自不同來源；
   假設「改目錄名只是搬檔案」會製造靜默改名。與 2026-05-30 的「prompt 文字 ≠ enforced 邏輯」是同一種錯：**規約文件 ≠ enforced 行為**。
2. **README 等規約文件本身也可能與 repo 實況矛盾**，引用前先找一個既有實例對照。本次只要看一眼 `archive/` 目錄就能發現沒有前綴。
3. 抓到「路徑錯誤」是對的，但**順帶追加的規約要求要獨立驗證**——主結論正確不代表附帶建議也正確。

## 2026-05-31 — 批評誤導 Architect 重造輪子：叫他「抽出 page.tsx 既有 marker 邏輯為新 helper」

**錯誤：** 批評 Unit 2 地區模型缺口時（正確抓到東京/online/overseas 不在 prefecture 陣列），建議 Architect「從首頁 page.tsx 抽出 marker 過濾邏輯，新建共用 helper」。Architect 據此在 v3 計畫的 2-pre 新增 `web/lib/analytics/locationFilter.ts`。下一輪 grep 才發現：(1) 該邏輯**早已不在 page.tsx**，(2) **已存在 `web/lib/locationMarkers.ts`** export `LOCATION_KEYS` + `matchesLocation()`（正是要新建的東西），(3) AdminEventTable.tsx 還另有一份。新建 locationFilter.ts 等於**第三份平行實作**——與我自己「消除平行實作分歧」的訴求矛盾。

**修正：** 下一輪 critique 第 4/5/6 段建議刪除 locationFilter.ts，改 `import { LOCATION_KEYS, matchesLocation } from "@/lib/locationMarkers"` + regionPrefectures.matchesCity，零新過濾 helper。

**教訓：**
1. **建議「抽出既有邏輯為新 helper」前，必先 grep 是否已有共用模組**（搜 `matchesLocation`、`LOCATION_*`、`*_MARKERS`）。假設「邏輯在 X 檔」而不查證，會把 Architect 推向重造輪子。
2. **「復用」型批評本身也要驗證復用標的存在且 API 對得上**，不能只說「抽出來共用」就交差——要指名實際檔案路徑與 export 名。
3. 抓到「缺口」是對的，但**開的藥方（新建檔）可能比病更糟**；先找既有解再決定是否真要新檔。

---

## 2026-05-30 — 重大誤判：以為「LOCATION GATE 會自動停用事件」（連錯兩輪）

**錯誤：** 批評 note_creators 計畫時，第 1 輪把「re-annotate 會觸發 LOCATION GATE 把台灣活動 is_active=false」標為 🔴 blocker，主導計畫改「不走 pending」。第 2 輪又引 annotator.py L586 當「FC 鎖定→gate 強制豁免」，反過來主導計畫改「FC-first-then-annotate」。第 3 輪實際讀 code 才發現：LOCATION GATE 全文（L571-586）在 `SYSTEM_PROMPT` 內（給 GPT 的指示），主事件 `update_data`（L1497-1557）**根本不含 is_active**；全 scraper 只有 merger.py（去重）會設 is_active=false。**沒有任何 code 依 gate 停用事件**——gate 的 is_active=false 只落在 selection_reason。

**修正：** 第 3 輪 critique 建議 1 移除計畫所有「LOCATION GATE 刪活動」立論；FC-first 的正確理由改為「防 GPT re-annotate 覆寫結構欄位 + 自動生成三語」。功能設計不變，只改 justification。

**教訓：**
1. **prompt 文字 ≠ enforced 邏輯**。看到 SYSTEM_PROMPT 裡寫「set is_active=false」不代表 code 真的會停用。斷言「某行為會發生」前，**必須追到實際寫 DB 的 `update_data` / `.update()`**，確認該欄位真的被寫入。
2. **誤判會跨輪複利**：第 1 輪的錯誤前提被計畫採納後，第 2 輪在錯誤地基上「優化」，越走越遠。每輪應重新質疑**上一輪自己的假設**，而非只檢查 Architect 的修訂。
3. 區分「軟風險」（admin 看 selection_reason 後可能手動停用）與「硬風險」（code 自動停用）。前者不該標 🔴 blocker。

---

## 2026-05-30 — 批評犯事實錯誤：誤稱 `price_amount` 欄位不存在

**錯誤：** 第 1 輪批評 note_creators 計畫時，僅憑一次 `grep base.py` 的截斷結果就斷言「base.py 無 price_amount 欄位」，標為 🟡 並寫入 critique。Architect 採信後把此錯誤敘述寫進 plan.md L54。第 2 輪查 `database.py` L118 `if event.price_amount is not None:` 才發現 `price_amount` 確為 Event 欄位與 DB 欄。

**修正：** 第 2 輪 critique「建議 3」更正事實，建議同時設 `price_amount=43000` + `price_currency='NTD'`，並記錄此為 critic 第 1 輪誤導。

**教訓：** 斷言「某欄位不存在」前，**禁止只看單一檔案的 grep 截斷結果**——欄位可能定義在別處或被 maxResults 截掉。應交叉驗證：(1) dataclass 定義檔、(2) database.py row build（哪些欄位被寫入 DB）、(3) migration。「不存在」是高風險斷言，須三處皆無才可下。

---

## 2026-05-26 — 成功攔截 Architect 過度工程（5 Phase → 3 Phase）

**情境：** Architect 為「co_organizers / sponsors 跨來源抓取」需求設了 5 Phase 計畫：OCR 強化 + 新 `enrich_organizers.py` 腳本（~200 行）+ annotator prompt 強化 + daily CI step + 手動 DB patch。

**Plan Critic 介入：** 質疑「complexity vs value」比值——立刻跑 SQL 量化候選池：

```sql
SELECT count(*) FROM events 
WHERE is_active AND raw_description ~ '共催' AND co_organizers='{}';
-- 結果：2 個事件
```

整個 579 active events 中只有 2 個共催遺漏。為 2 個事件建 daily CI pipeline 屬**典型過度工程**。

**建議：** 砍掉 Phase 1（`enrich_organizers.py`）+ Phase 3（daily CI 整合），只保留 Phase 4 手動 DB patch + Phase 2 annotator prompt + Phase 0 OCR prompt。

**結果：** 使用者接受。實際只推 3 個輕量 commits（`280fdc4` + `e54b925` + DB direct patch），省 ~200 行新檔 + CI step 維護成本。

**Lesson（已上 SKILL）：**
1. **遇到「批次處理 / daily CI / backfill」字眼，第一動作必為 SQL 量化候選池**。`< 20` 一律建議「prompt-only 或手動修」。
2. **不要只看計畫複雜度評分，要算 ROI**：複雜度 medium × 受益 < 15 個事件 = 比值失衡。
3. **第二意見不只是審美**：跑數據能否定看似合理的工程化方案，這是 Plan Critic 不可被取代的角色。

Architect SKILL.md 已新增「規模量化先於工具化」Guard。
