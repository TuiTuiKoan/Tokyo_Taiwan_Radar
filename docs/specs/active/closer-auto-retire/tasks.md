# Tasks

進度真值。規格與裁決見 [plan.md](./plan.md)（rev.4），試跑證據見 [notes.md](./notes.md)。

## 目前狀態（2026-10-22）

| Phase | 狀態 |
|-------|------|
| Phase 0 worktree 確認 | 完成 |
| Phase 1 回填腳本與測試 | **已 commit**：`1ac845d4`（spec）、`6616abbf`（腳本與測試），待使用者 push |
| Phase 2 試跑（plan.md §8） | **暫停**（2026-10-22），等 pr-flow-tiering 試行結果 |
| Phase 3 規則文件（plan.md §7 #1–#6） | **暫停**（2026-10-22），同上；且必須先通過 Phase 2 的決策閘門 |

恢復條件：pr-flow-tiering（`docs/specs/active/pr-flow-tiering/`，在 `origin/main`）試行有結果後，由使用者決定是否恢復
Phase 2。恢復前先依 plan.md §11 把本分支 rebase 到當時的 `origin/main`。

---

## Phase 0：Worktree

- [x] 使用者確認在 `ttr-closer-auto-retire-worktree`（`feat/closer-auto-retire`）進行
- [x] 工作樹乾淨時 `git -C '<worktree>' fetch origin && git -C '<worktree>' rebase origin/main`（2026-10-22 V-M-D commit 後
      rebase 到 `b78510bb`，無衝突）

## Phase 1：回填腳本與測試（plan.md §4.7、§6）

- [x] 新增 `scripts/campaign-disposition-backfill.py`
  - [x] apply：`--record <path> --block <file> --capsule <file>`，只替換 `## Worktree disposition` 區塊（範圍見下方裁決）
  - [x] 三種結果：`applied`（印 diff）、`already_applied`、`unexpected_state`（exit 3）
  - [x] 重跑冪等：第二次執行為 `already_applied`，檔案逐位元不變
  - [x] verify：`--verify --capsule <file>`，從 stdin 讀記錄，只檢查 disposition 區塊
  - [x] capsule `key: value` 解析；缺鍵、重複鍵、空值、格式錯誤一律 exit 2
- [x] 使用者裁決（2026-10-22）：替換與 `--verify` 的範圍都只到 `## Worktree disposition` 之後的第一個 `###`（或下一個
      `## `，取先出現者）；`### Gates at the close-out audit` 等子節原樣保留，block 檔含 `###` 時 exit 2。
      `2026-10-13-senses-taxonomy.md` 的六值表在 `### Gates` 之後，列為舊格式例外，測試預期它 verify 失敗
- [x] 新增 `scripts/tests/test_campaign_disposition_backfill.py`（plan.md §6 列的八種情境，加上已提交記錄的實際格式）
- [x] `python3 -m pytest scripts/claude/tests scripts/tests -q` 通過
- [x] `python3 scripts/sync_ai_adapters.py --check` 無漂移
- [x] 建立 `proposal.md`、`tasks.md`
- [x] commit（V-M-D，2026-10-22：`1ac845d4` spec、`6616abbf` 腳本與測試）
- [ ] 使用者 push 到 `origin/main`，確認 Secret Scan 與部署

## Phase 2：試跑（plan.md §8）— 暫停中

- [ ] 8.2 環境：協調者對話從主工作樹 root 新開，先跑 E1 三條指令並記錄
- [ ] 8.3 T-A 串接情境＋第一輪（有遠端分支）
  - [ ] 建 `ttr-closer-trial-a-worktree`、放 `scripts/__pycache__/` 項目
  - [ ] 使用者推遠端 trial 分支
  - [ ] closer Phase A：檢查 `auto_eligible`、capsule 列表、E1 輸出
  - [ ] 同意後以 SendMessage 續用同一個 closer（Phase C 試跑只寫 capsule）
  - [ ] V-M-D 只跑 Step 0.6 第 1 點
  - [ ] 回到同一個 closer 進 Phase D：記錄 R2 可行性、cwd 外漏、核准提示
  - [ ] D1 → D2.5 → D3a → D3b → D3c（停）→ 使用者刪遠端 → D3c 續 → D3d → D4
- [ ] 8.4 T-B 第二輪（沒有遠端分支），含 `tmp/` 的 E3 負向案例
- [ ] 8.5 T-C scratch clone：B5 正向（無 rebase、rebase 後）、負向（偷插 commit）、reflog 查找、D5 全程（含本腳本 apply 與 `--verify`）
- [ ] 8.6 決策閘門：在 notes.md 逐條列出省下的貼上次數與核准提示次數，判定是否進 Phase 3

## Phase 3：規則文件（plan.md §7）— 暫停中，需通過 Phase 2 閘門

- [ ] `.github/agents/campaign-closer.agent.md`
- [ ] `.github/skills/agents/campaign-closer/SKILL.md`（含 capsule 鍵名定稿）
- [ ] 在 SKILL 與 `docs/evaluation/campaigns/README.md` 規定：`## Worktree disposition` 的 `decided at` 與六值表必須寫在
      第一個 `###` 子節之前（回填腳本只替換、只驗證這一段；2026-10-22 裁決）
- [ ] `.github/instructions/git.instructions.md`
- [ ] `docs/evaluation/campaigns/README.md`
- [ ] `.github/agents/validate-merge-deploy.agent.md`
- [ ] `AGENTS.md`
- [ ] `python3 scripts/sync_ai_adapters.py` 與 `--check`
- [ ] plan.md §10 驗證步驟與文字檢查
