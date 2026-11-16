# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:view-bot-filter` label。

- [x] 規劃與評審（proposal、plan-critique-1）
- [x] PR（#675）：`botDetect.ts`、`visitorFilter.ts`、`record-view.ts`、儀表板篩選、migration 109、測試
- [x] 套用 migration 109（2026-11-16；dryrun 與 read-back 一致：known_bot 7,446，其中美國 7,442、日本 2）
- [ ] 合併 PR（人類關卡）
- [ ] 部署後執行 `backfill.sql`（人類關卡：production 寫入）
- [ ] 驗收 V6、V7：新列有分類、儀表板預設排除 bot
- [ ] 兩週觀察：中國、新加坡、香港新列的分類分布
