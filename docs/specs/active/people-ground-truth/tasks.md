# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit（即使只改這一行）。
過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:people-ground-truth` label，不寫進本檔；進度看 TTR Roadmap 看板。

- [ ] 0. 量測 baseline：只在 `person_name_lookup.py` 加計數 log、不改行為，先合併並跑 1–2 週每日排程
- [ ] 1. spec 定稿：Plan Critic 評審（第一輪 2026-10-23 已完成並修訂）、使用者核准設計
- [ ] 2. migration（暫定 `102_people.sql`）：`people`、`person_lookup_cache`、RLS、REVOKE、GRANT；本機 Postgres 實測寫入規則；使用者核准後套用 production 並唯讀確認
- [ ] 3. `people_admin.py set`／`show`，以及所有路徑「以日文名查 verified」（不限片假名）
- [ ] 4. 外部查詢三種狀態、eiga 姓名比對、`people` 寫入、negative／ambiguous cache、離線模式、計數；含第 9 節必測項目
- [ ] 5. 接上 `annotator.py`（enrich 對既有人名欄位先查 verified）；修既有測試
- [ ] 6. `people_admin.py propagate` 與 `reset-unverified`（預設 dry-run、備份、fail closed）
- [ ] 7. 回填：`candidates --top 200` 匯出 → 使用者確認 → `import` 匯入 verified
- [ ] 8. `--warm-people` 與凍結快照；stage 3 以 schedule／dispatch 放進每週 CI，報告人名覆蓋率
- [ ] 9. 量測：與里程碑 0 的 baseline 比較外部請求數，註明 #361 是否已合併，記入 `notes.md`
