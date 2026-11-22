# Tasks

本檔只放里程碑。細項、評審意見與 bug 開 GitHub issue，貼 `spec:venue-ground-truth` label；進度看 TTR Roadmap 看板。

- [x] Phase A：地址量尺、唯讀稽核腳本、單元測試、基準（不改既有行為）— PR #709
- [ ] Phase A 驗收：使用者看過抽查樣本，判錯的列補進測試（人類關卡，#708）
- [ ] 使用者決定：auto_qa 排除的來源是否需要地址；#339 的去向（#708）
- [ ] Phase B：`enrich_addresses` 改用量尺；每週摘要加場地缺口清單；`daily_quality_metrics` 加街道級比率
- [ ] Phase C：查明並修正 `kokuchpro` 的地址空白（#707）；列出「場地名不是場地」的清單
- [ ] 後段設計定案並再送評審（出處欄位、機器驗證的寫入路徑、共識條件）
- [ ] Phase D：出處欄位 migration、#371 第 2 類、回填 manifest（寫入需使用者核准）
- [ ] Phase E：依剩餘量決定 #366 的 web search

## Verification

基準值（2026-11-22，`audit_venue_addresses.py`，不含 auto_qa 排除的來源）：全部 80.9%、即將舉辦 81.1%、近 60 天新進 84.4%。

- [ ] 即將舉辦事件的街道級比率達到 95%
- [ ] 近 60 天新進事件的街道級比率達到 92%

目標值在使用者決定排除來源的範圍後重訂。
