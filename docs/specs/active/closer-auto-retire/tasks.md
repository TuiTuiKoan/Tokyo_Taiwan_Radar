# Tasks

本檔只放里程碑。規格與裁決見 [plan.md](./plan.md)（rev.4），試跑證據見 [notes.md](./notes.md)。
細項、評審意見與待辦開 issue，貼 `spec:closer-auto-retire` label；進度看 TTR Roadmap 看板。

## 目前狀態（2026-10-22）

Phase 1 已完成。Phase 2–3 自 2026-10-22 暫停，恢復條件與恢復前必修見
[#345](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/345)。

## 里程碑

- [x] 建立 `spec:closer-auto-retire` label（2026-10-22）
- [x] Phase 0：在 `ttr-closer-auto-retire-worktree`（`feat/closer-auto-retire`）進行，使用者已確認；rebase 到 `origin/main`
- [x] Phase 1：`scripts/campaign-disposition-backfill.py` 與測試（plan.md §4.7、§6）。替換與 `--verify` 只到
      `## Worktree disposition` 之後的第一個 `###`；`2026-10-13-senses-taxonomy.md` 列為舊格式例外（2026-10-22 裁決）
- [ ] Phase 1 推上 `origin/main`，確認 Secret Scan 與部署
- [ ] Phase 2：試跑（plan.md §8）通過 §8.6 決策閘門 — 暫停中
- [ ] Phase 3：規則文件改寫（plan.md §7）與 `sync_ai_adapters.py --check` — 暫停中，需先通過 Phase 2
- [ ] 首次真實退役 pilot：D5 回填在主工作樹完成（plan.md §4.7）
