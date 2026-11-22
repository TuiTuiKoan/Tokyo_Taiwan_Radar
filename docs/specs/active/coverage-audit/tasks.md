# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:coverage-audit` label。

- [x] M1 Phase C：`url-intake.yml` 的 `run_attempt` 條件與 hook 規則 `url-intake-approval`（#702）；Tier 2，使用者審核合併
- [x] M2 Phase A：`title_verdict()`／`taiwan_verdict()`、共用 `TAIWAN_TITLE_RE`、正負例測試（#701）
- [x] M3 Phase B 再評審（plan-critique-2），proposal 修訂為 v3
- [x] M4 Phase B：`coverage_audit.py`、`body_verdict`、`scraper-quality.yml` 的 `coverage-db`／`coverage-probe` job；滾動 issue；Tier 2（#724 合併後）
- [x] M5 合併後對 main dispatch，第一份週報產出，確認數字合理
- [ ] M6 四週盤點：門檻、探測詞、是否改月報，寫入 `notes.md`

第一份週報（手動執行）：https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/739#issuecomment-7079875151 。每週監控是排程任務「覆蓋稽核週報監控（coverage-audit）」，週日 10:37 JST 執行；第 4 則排程週報產生時會自動做 M6 盤點（#747 探測窗口）。
