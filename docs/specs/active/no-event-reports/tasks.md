# Tasks

本檔只放不超過十條里程碑。過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:no-event-reports` label。

## Phase 0: 規劃

- [x] 建 `ttr-no-event-reports-worktree`（branch `feat/no-event-reports`，自 `origin/main` `af827939`）；寫 proposal（2026-11-22）
- [x] Plan Critic 評審存檔（`plan-critique-1.md`，Codex 未安裝，同一模型家族），依評審修訂：採 S1，修 B1–B4

## Phase 1: 實作（本 PR，Tier 2）

- [x] `scraper/event_report.py` 判定與測試
- [x] 收錄閘門：scraper 層與 annotator report gate
- [x] 全專案移除 `report` 分類（scraper、web、文件、skill），`sync_ai_adapters.py --check` 與 pytest 全綠
- [ ] `_oneoff_retire_event_reports.py`（預設 dry-run）與測試；推 branch、開 PR

## Phase 2: 上線（人類關卡）

- [ ] 使用者合併 PR
- [ ] 使用者看 dry-run 清單後執行 `--apply`；隔天確認 Daily Scraper 沒有產生新的活動報導
