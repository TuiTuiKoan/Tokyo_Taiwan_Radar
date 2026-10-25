---
title: TIFF 2026 權威場館新增 Tasks
description: 4 筆 venue insert 的里程碑；細項開 issue（spec:authoritative-venue-repair）
---

## Milestones

- [x] M1 官方來源與 TIFF 2026 venues API 複核、production 唯讀預查（2026-10-25）
- [x] M2 seed 修正、唯讀 plan builder 與 focused tests
- [x] M3 Tester PASS（2026-10-25，commit 1138d139：17 focused、1575 全套件）
- [ ] M4 PR 合併到 `origin/main`（使用者按合併），確認 exact SHA
- [ ] M5 唯讀 plan 與 capture，顯示 manifest SHA-256
- [ ] M6 Gate 2 批准（綁定 manifest SHA-256）後 apply、逐筆讀回、第二次 apply noop
- [ ] M7 `scrape-now.yml`（`sources: tiff`）補跑並驗收入庫與 `location_*`
- [ ] M8 在 #341 回報、在 #339 註明 4 筆已完成
