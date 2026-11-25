# Tasks

本檔只放不超過十條里程碑。過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:research-team` label。

- [x] 報告產生器與驗證（`scripts/research/render_report.py`，含測試）
- [x] 角色卡與 `/deep-research` 入口（skill、prompt、同步 wrapper）
- [ ] quick 深度試跑一個真實議題，Artifact 發布成功，結果記在 `notes.md`
- [ ] 使用者用自己的議題跑一次 standard，回饋報告是否可用
- [ ] 依回饋決定：角色是否獨立成 agent 檔、是否搬到獨立 repo、是否改用 Workflow 腳本做固定編排

## Verification

- [ ] `python3 -m pytest scripts/tests/test_research_report.py -q` 全綠；`python3 scripts/sync_ai_adapters.py --check` exit 0
