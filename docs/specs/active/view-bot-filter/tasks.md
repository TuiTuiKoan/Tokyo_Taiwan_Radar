# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:view-bot-filter` label。

- [x] 規劃與評審（proposal、plan-critique-1）
- [x] PR（#675）：`botDetect.ts`、`visitorFilter.ts`、`record-view.ts`、儀表板篩選、migration 109、測試
- [x] 套用 migration 109（2026-11-16；dryrun 與 read-back 一致：known_bot 7,446，其中美國 7,442、日本 2）
- [x] 合併 PR（2026-11-18 07:04 UTC）
- [x] 部署後執行 `backfill.sql`（2026-11-18；空窗期 441 筆中 165 筆補標為 `known_bot`，可比對卻仍未標的列為 0）
- [x] 驗收 V6（2026-11-19，部署後 24 小時，127 筆）
  - 未分類：1 筆（11-18 09:27 UTC，美國）。原因推測是 Vercel skew protection（`deploymentId`）把部署前打開的分頁導到舊版程式，其餘 126 筆都有分類
  - 日本 `suspected_bot`：0／15
  - `known_bot` 有名稱的 34 筆，同時段 `aeo_visits` 全部對得上且名稱一致；判為 `human` 的列中對得上 bot 的為 0
  - `generic:bot` 31 筆（全部美國）：不在 AEO 清單、`aeo_visits` 看不到的爬蟲，新分類規則才抓得到
  - 日夜起伏：真人 53 筆，樣本太少，暫不判定，併入兩週觀察
- [ ] 驗收 V7：儀表板預設排除 bot（使用者目視）
- [ ] 兩週觀察（至 2026-12-02）：中國、新加坡、香港新列的分類分布（首日中國 8、香港 6、新加坡 4 筆全為 `human`）；真人日夜起伏
