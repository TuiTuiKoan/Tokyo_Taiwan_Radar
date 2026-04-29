---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。Commit `fix(scraper): replace hardcoded 2026 in discovery queries with dynamic _THIS_YEAR`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `web/components/AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，且 `getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位偵測 Peatix 主辦者，不再依賴硬寫 ID 列表

**教訓：** 每次在 `discovery_accounts.py` 新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。這是一個 **paired-file rule**：`discovery_accounts.py` 的 agent_category 定義 ↔ `AdminSourcesTable.tsx` 的 SOURCE_TYPE_LABELS。
