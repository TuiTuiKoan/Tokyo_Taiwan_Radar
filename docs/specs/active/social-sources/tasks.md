# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:social-sources` label。

- [x] M1 `scraper/social/` 核心（對象載入、前置過濾、連結補資料、X 與臉書抓取層、管線）、`social_dryrun.py` 與單元測試；不註冊、不寫 DB（#746，2026-11-22 合併）
- [ ] M2 零成本驗證 → 隔離 auto-research／auto-generate 與後台最小支援 → `social-dryrun.yml` 以真實資料試跑兩週，指標寫入 `notes.md`（需使用者新增 secrets、設定花費上限、接受條款風險）
- [ ] M3a 標註後上線閘門、merger 優先序 101 與同來源去重（必須先於 M3b）
- [ ] M3b 註冊進 `SCRAPERS`；抓取 job 不帶 production 憑證；`source_expectations.json`
- [ ] M3c `last_post_id` 回寫
- [ ] M4 後台來源頁管理社群來源；創作者頁「加入抓取來源」
- [ ] M5 auto-research 反查既有單位的粉專與 X 帳號，寫入 candidate
- [ ] M6 雙週稽核報表與來源自動停抓
- [ ] M7 圖片辨識補資料、連結集合頁往下一層
- [ ] M8 盤點：成本、命中率、誤上線與重複上線筆數
