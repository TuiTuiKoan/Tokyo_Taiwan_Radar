# Plan Critic History

新條目加在頂部。格式：日期 / 錯誤 / 修正 / 教訓。

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
