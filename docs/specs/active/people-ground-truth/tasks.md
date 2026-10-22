# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit（即使只改這一行）。
過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:people-ground-truth` label，不寫進本檔；進度看 TTR Roadmap 看板。

- [x] 0. 量測 baseline：只在 `person_name_lookup.py` 加計數 log（第 4 節的計數名稱）、不改行為，先合併。不阻塞後續里程碑，但里程碑 5 合併前要累積至少 7 天
- [x] 1. spec 定稿：兩輪評審（Claude Haiku、Codex）已完成並修訂；使用者核准設計
- [ ] 2. migration（暫定 `102_people.sql`）與 store：兩張表、NFKC CHECK、RLS、REVOKE、GRANT、交易內 read-back；`normalize_name_ja` 與 store 寫入規則；本機用 supabase-py 實測第 4 節驗收四項；使用者核准後套用 production 並唯讀確認
- [ ] 3. 單一人名與電影路徑改為 DB 優先：verified 優先、外部查詢三種狀態、eiga 姓名比對、歧義、negative／ambiguous cache、離線模式、計數
- [ ] 4. `people_admin.py set`／`show`／`reset-unverified`
- [ ] 5. 接上 `annotator.py`：第 5 節的 verified 覆寫步驟與四種端到端測試；修既有測試
- [ ] 6. eval stage 3：`--warm-people`、凍結快照與 schema 驗證、離線零 HTTP、明確 skip、人名覆蓋率；放進週排程
- [ ] 7. `people_admin.py propagate`（只產生 dry-run 計畫）
- [ ] 8. 量測：與里程碑 0 的 baseline 比較外部請求數，註明 #361 是否已合併，記入 `notes.md`
