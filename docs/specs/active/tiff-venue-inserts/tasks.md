---
title: TIFF 2026 權威場館新增 Tasks
description: 4 筆 venue insert 的里程碑；細項開 issue（spec:authoritative-venue-repair）
---

## Milestones

- [x] M1 官方來源與 TIFF 2026 venues API 複核、production 唯讀預查（2026-10-25）
- [x] M2 seed 修正、唯讀 plan builder 與 focused tests
- [x] M3 Tester PASS（2026-10-25，commit 1138d139：17 focused、1575 全套件）
- [x] M4 PR #474 合併（2026-10-25），origin/main `a21f6291`
- [x] M5 唯讀 plan 與 capture：manifest SHA-256 `bff577bd1d37da71a31caeff6793ec83abf705ea9f6c833baa158b31fbb09846`
- [x] M6 Gate 2 批准後 apply：mutation_count=4，讀回一致，第二次 apply noop
- [x] M7 scrape-now（sources: tiff）run 40211211252：10 筆入庫，location_* 與場館一致
- [x] M8 已在 #341 回報並關閉、在 #339 註明扣除
