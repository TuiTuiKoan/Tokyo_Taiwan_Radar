# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit（即使只改這一行）。
過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:llm-cost-reset` label，不寫進本檔；進度看 TTR Roadmap 看板。

- [x] M0 建立 `ttr-llm-cost-reset-worktree`（`feat/llm-cost-reset`），spec 進 repo，11 張 issue 貼上 `spec:llm-cost-reset`
- [x] M1 #318：移除 researcher 與 discovery_accounts（含 workflow）、移除 qa_auto_fix 的 OpenAI 備援、enrich_addresses 改為只查 registry 與其他事件；dry-run 驗證
- [x] M2 #319：`llm_client.py` 的錯誤分類與 `LLMConfigError`，scraper 14 個呼叫點改走它；模擬 404 時 step 失敗；週報標出連續兩週 0 產出的來源
- [x] M3 #363 schema：`llm_usage`、`llm_pricing`、`llm_cost_daily`、`llm_cache` migration，經使用者核准後套用到 production
- [x] M4 #363 紀錄：`llm_client` 寫入 `llm_usage`；web 6 個呼叫點改走 `openai.server.ts`；CI 檢查禁止直接建立 client
- [x] M5 #322、#320：報表分頁與改讀 `llm_cost_daily`、預算檢查修正、account API 每人限流；依 caller 群組選 API key（使用者建 project 與 secrets，#320 保持開啟到設定完成）
- [x] M6 #317：enrich_poster 只處理新圖、查清 applied=0，dry-run 有寫入後恢復每日執行（2026-10-23 dry-run 沒有正確寫入，使用者裁決退役）
- [ ] M7 #360、#321、#361：enrich_location 已嘗試標記、qa_heartbeat 規則分類與 cinemaclair 快取、每日 pipeline 去重
- [ ] M8 #323、#362：移除 DeepL；降低 annotator 重標注量且 golden set 不退步
- [ ] M9 對帳：連續兩週週報的 OpenAI 成本與 dashboard 差距在一成以內，推 feature branch 並開 PR
