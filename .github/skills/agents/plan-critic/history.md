# Plan Critic History

新條目加在頂部。格式：日期 / 錯誤 / 修正 / 教訓。

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
