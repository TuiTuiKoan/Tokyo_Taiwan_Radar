# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit（即使只改這一行）。
過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:supabase-advisor-hardening` label，不寫進本檔；進度看 TTR Roadmap 看板。

- [x] M0 建立 `ttr-supabase-advisor-hardening-worktree`（`feat/supabase-advisor-hardening`），spec 與 production before-image 進 repo
- [x] M1 Plan Critic 評審存檔（`plan-critique-1.md`），依評審修訂計畫
- [ ] M2 `106_advisor_security_hardening.sql` 與本機 PostgreSQL 測試
- [ ] M3 `107_rls_initplan_policy_cleanup.sql` 與本機 PostgreSQL 測試（改寫前後可見列數相同）
- [ ] M4 更新 `database.instructions.md`，推 feature branch 並開 PR
- [ ] M5 使用者在 SQL Editor dry-run 後套用 106、107；advisor read-back 與 `database.instructions.md` 標記 APPLIED
- [ ] M6 使用者開啟外洩密碼保護；advisor read-back
