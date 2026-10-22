---
slug: closer-auto-retire
title: closer-auto-retire 試跑紀錄
created: 2026-10-22
revision: 4
---

# 試跑紀錄

> **狀態（2026-10-22，plan.md rev.4）**：Phase 2 試跑**暫停**，§2 暫不填寫。恢復條件：pr-flow-tiering 試行結束並決定 Phase F 之後
> （plan.md §2.5 R5、§14）。恢復前先處理 plan.md §13：K1 會改變 §2.1 的環境欄位（啟動目錄改以 `lsof -a -d cwd -p "$PPID"` 量測；
> 記錄實際執行檔，Plan Critic 實測為 VS Code extension 內建的 2.1.299），K4 要求補上試跑授權範本與完整的「試跑不適用」清單。
> §1 的靜態預判仍有效，但只反映 `0099dbb5` 時的 guard；pr-flow-tiering 已改寫 `check_push`（feature branch 的 push 改為 allow），
> 恢復時要以當時的 guard 重跑 probe。

規則定稿前的實測證據。§1 是 guard 的靜態預判（已完成）；§2 是在使用者 Claude Code 設定下的實測（待填），結構對應
plan.md §8（rev.3）。

## 1. 靜態 guard 預判（Architect，2026-10-22）

**方法**：在 scratch 目錄寫 probe，`sys.path` 指向本 worktree 的 `scripts/claude/`，對每條指令字串呼叫
`_policy.evaluate_command()`，印出 `kind` 與 `rule`；以 `python3 -I` 執行。**沒有執行任何被測指令**，也沒有經過
Claude Code 的權限系統或 auto mode。共三批 66 條：第一批 47 條（rev.1 的 D1–D6 與試跑建立），第二批 16 條（rev.2 新增的
E1 檢查、B2、B3、B5、回填腳本、試跑 clone 與 Q9 的 dry-run），第三批 3 條（rev.3 的 push base 交叉驗證）。

**範圍限制**：只反映 PreToolUse guard（本 worktree HEAD `0099dbb5` docs(agents): record the ai-portability archive
lessons in history and skills 的版本）。`permissions.ask` 只涵蓋 `git push`，與 guard 的 `ask` 一致。auto mode 分類器與一般
權限提示**不在此範圍**。

### 1.1 第一批（47 條）

| 步驟 | 指令形式 | guard |
|------|---------|-------|
| D1 | `git -C '<WT>' fetch origin main --quiet` | allow |
| D1 | `git -C '<WT>' rev-parse HEAD` | allow |
| D1 | `git -C '<WT>' rev-list --left-right --count HEAD...origin/main` | allow |
| D1 | `git -C '<WT>' status --porcelain \| wc -l` | allow |
| D1 | `git -C '<WT>' status --porcelain --ignored \| grep '^!!'` | allow |
| D1 | `( cd '<WT>' && /bin/pwd -P )` | allow |
| D1 | `WT='…'` 換行 `PHYS=$( cd "$WT" && /bin/pwd -P )` | allow |
| D1 | `lsof -a -d cwd 2>/dev/null \| grep -F '<WT>'` | allow |
| D1 | `git -C '<M>' rev-list --left-right --count origin/main...main` | allow |
| D1 | `bash '<M>/scripts/campaign-closeout-audit.sh' --worktree … --slug … --base … --head … --self-session …` | allow |
| D1 | `git -C '<M>' worktree list --porcelain \| grep -c '^worktree '` | allow |
| D1 | `git -C '<M>' show <sha> \| git patch-id --stable` | allow |
| D2 | `shasum -a 256 '<WT>/tmp/<file>'` | allow |
| D2.5 | `cat > '<capsule>' <<'EOF' … EOF` | allow |
| D3a | `git -C '<M>' worktree remove '<WT>'` | allow |
| D3b | `git -C '<M>' worktree list --porcelain \| sed -n 's/^worktree //p'` | allow |
| D3b | `printf '%s\n' … \| sort -u > '<want>'` | allow |
| D3b | `grep -vE '^ttr-.*-worktree/$' '<M>/.git/info/exclude' > '<M>/.git/info/exclude.tmp'` | allow |
| D3b | `cat '<want>' >> '<M>/.git/info/exclude.tmp'` | allow |
| D3b | `mv '<M>/.git/info/exclude.tmp' '<M>/.git/info/exclude'` | allow |
| D3b | `grep -E '^ttr-.*-worktree/$' '<M>/.git/info/exclude' \| sort -u > '<have>'` | allow |
| D3b | `comm -23 '<want>' '<have>'`、`comm -13 '<want>' '<have>'` | allow |
| D3b | `git.instructions.md` § Reconciling 的整塊 one-liner | **deny `unsupported-syntax`** |
| D3c | `git -C '<M>' ls-remote --heads origin <branch>` | allow |
| D3c | `git -C '<M>' cherry origin/main <branch>` | allow |
| D3c | `git -C '<M>' fetch origin --prune` | allow |
| D3c | `git -C '<M>' push origin --delete <branch>` | **deny `git-force-push`**（使用者執行） |
| D3d | `git -C '<M>' branch -d <branch>` | allow |
| D4 | README 的 `unregistered=`／`branch=`／`exclude=`／`directory=` 四個標籤檢查 | allow |
| D4 | README 的殘留 UNIQUE 檢查迴圈（`find … \| while read …`） | allow |
| D5 | `git -C '<M>' status --porcelain`、`git -C '<M>' diff --cached --name-only` | allow |
| D5 | `git -C '<M>' pull --ff-only origin main` | allow |
| D5 | `python3 '<M>/scripts/campaign-disposition-backfill.py' --record … --block …` | allow |
| D5 | `python3 - <<'EOF' … EOF`（不含 `create_client`） | allow |
| D5 | `git -C '<M>' add '<record>'` | allow |
| D5 | `git -C '<M>' commit --only -m "$(cat <<'EOF' … EOF\n)" -- '<record>'` | allow |
| D5-push | `git -C '<M>' push origin main` | **ask `push-gate`**（依 U3 由使用者執行，agent 不呼叫） |
| D6 | `git -C '<M>' merge-base --is-ancestor <sha> origin/main && echo … \|\| echo …` | allow |
| D6 | `git -C '<M>' show origin/main:'<record>' \| grep -c 'pending'` | allow（rev.2 改用 `--verify`，見 1.2） |
| D6 | `rm '<capsule>'` | allow |
| 試跑建立 | `git -C '<M>' worktree add '<WT>' -b chore/closer-trial origin/main` | allow |
| 試跑建立 | `grep -qxF '<line>' '<M>/.git/info/exclude' \|\| echo '<line>' >> '<M>/.git/info/exclude'` | allow |

### 1.2 第二批（rev.2 新增，16 條）

| 步驟 | 指令形式 | guard |
|------|---------|-------|
| E1 | `echo "claudecode=${CLAUDECODE:-unset}"` | allow |
| E1 | `echo "project_dir=${CLAUDE_PROJECT_DIR:-unset}"` | allow |
| E1 | `/bin/pwd -P` | allow |
| Phase A | `ls -1 '<capsules dir>'` | allow |
| B3 | `git -C '<M>' branch --show-current` | allow |
| B2 | `git -C '<M>' fetch origin` | allow |
| B2 | `git -C '<M>' cherry origin/main origin/<branch>` | allow |
| B2 | `git -C '<M>' merge-base --is-ancestor <R> <tip> && echo 'remote_in_local=yes' \|\| echo 'remote_in_local=no'` | allow |
| B2 | `gh pr list --head <branch> --state open --json number,title` | allow |
| B5 | `git -C '<M>' rev-list --count <B_C>..HEAD` | allow |
| B5 | `git -C '<M>' show HEAD \| git patch-id --stable` | allow |
| D6 | `git -C '<M>' show origin/main:'<record>' \| python3 '<M>/scripts/campaign-disposition-backfill.py' --verify --capsule '<capsule>'` | allow |
| D5 | `python3 '<M>/scripts/campaign-disposition-backfill.py' --record … --block … --capsule …` | allow |
| T-C | `git clone --local '<M>' '<scratch>/d5-clone'` | allow |
| T-C | `rm -rf '<scratch>/d5-clone'` | allow |
| Q9(b) | `git -C '<M>' push --dry-run origin <branch>` | **ask `push-gate`**（Q9 裁決採 (a)，不使用） |

### 1.3 第三批（rev.3 新增，3 條）

| 步驟 | 指令形式 | guard |
|------|---------|-------|
| D1 push base | `git -C '<M>' reflog show --format='%H %gs' refs/remotes/origin/main` | allow |
| D1 push base | `git -C '<WT>' rev-parse HEAD^` | allow |
| D1 push base | `git -C '<WT>' merge-base --is-ancestor <B_C> origin/main && echo 'bc_on_main=yes' \|\| echo 'bc_on_main=no'` | allow |

另以唯讀方式確認（不是 probe）：主工作樹的 `refs/remotes/origin/main` reflog 在 2026-10-22 有連續多筆 `update by push`，
例如新值 `0099dbb5` docs(agents): record the ai-portability archive lessons in history and skills（12:23 +0900）的前一筆是
`3fe84edb` fix(agents): campaign closeout audit resolves date-prefixed archive directories（12:09 +0900）；`core.logAllRefUpdates`
為 `true`。plan.md §4.5 的 reflog 查找以此為依據，T-C 步驟 5 用這一對當已知答案。

另於本 session 實測（不是 probe）：Claude Code 的 Bash 環境中 `echo "claudecode=${CLAUDECODE:-unset}"` 輸出 `claudecode=1`。

**結論**：guard 層只擋 one-liner 與 `push --delete`，對 push 類要求核准，其餘全部放行。D3b 的拆開版、B2／B3／B5 的檢查、
回填腳本都可以由 agent 執行。

## 2. 實測（待填；對應 plan.md §8.2–§8.6）

### 2.1 環境

* Claude Code 版本：
* 協調者對話：從主工作樹 root 新開（Q10；不是產出計畫的規劃對話）。E1 三條指令的輸出：
* auto mode：開／關
* 叫用方式：主對話協調者派 closer subagent（唯一受測方式）
* 協調者的 Claude Code session id（傳給 `--self-session`）：
* 日期時間（UTC）：

### 2.2 T-A 串接情境＋第一輪（有遠端分支）

| 觀察項 | 結果 | 備註 |
|--------|------|------|
| Phase A exit code、`auto_eligible` | | |
| capsule 列表 | | |
| SendMessage 是否接回同一個 closer 實例（能否引述 Phase A 觀測值與同意時間） | | 不行 → 改用 Q1(c) |
| V-M-D Step 0.6 `cd` 之後，closer 的 `/bin/pwd -P` | | |
| V-M-D 之後的 `lsof -a -d cwd` 是否命中 | | 命中的行程與成因 |
| 背景 subagent 遇到自然出現的核准提示時的行為（Q9 (a)，agent 不發 push 類指令） | | 提示出現位置；等待／失敗／視為拒絕；沒出現記「未觀察到」 |

| 步驟 | 指令形式 | guard | 權限提示 | auto mode | rc | 備註 |
|------|---------|-------|---------|-----------|----|------|
| 建立 | worktree add、exclude 行、`__pycache__` 假檔 | | | | | |
| 建立 | 使用者推 trial-a 分支 | — | — | — | | 使用者執行 |
| D0 | E1 三條 | | | | | |
| D1 | （逐條） | | | | | |
| D2.5 | capsule heredoc | | | | | |
| D3a | `worktree remove` | | | | | |
| D3b | 拆開版逐條＋計數閘門 | | | | | |
| D3c | fetch、`ls-remote`、`cherry origin/main origin/<b>`、`merge-base`、`gh pr list` | | | | | |
| D3c | 使用者刪遠端 | — | — | — | | 使用者執行 |
| D3c 續 | `ls-remote`、`fetch --prune` | | | | | |
| D3d | `branch --show-current`、`pull --ff-only`、`merge-base`、`branch -d` | | | | | |
| D4 | 標籤檢查、`.git/worktrees/`、計數 | | | | | |

### 2.3 T-B 第二輪（沒有遠端分支）

| 觀察項 | 結果 | 備註 |
|--------|------|------|
| 放 `tmp/closer-trial.txt` 時的 `auto_eligible`（應為 no） | | |
| 刪除後的 Phase A exit code、`auto_eligible` | | |

| 步驟 | 指令形式 | guard | 權限提示 | auto mode | rc | 備註 |
|------|---------|-------|---------|-----------|----|------|
| D0–D4 | （同 2.2，逐條） | | | | | |

### 2.4 T-C scratch clone

| 項目 | 結果 | 備註 |
|------|------|------|
| 正向：沒有 rebase（計數、`HEAD^ == B_C`、patch-id） | | 預期 1／是／相同 → 通過 |
| 正向：rebase 到上游 `U` 之後（`B_C = U`） | | 預期 1／是／與 rebase 前相同 → 通過 |
| 負向：偷插 `S`，`B_C` 正確 | | 預期 2／否 → STALE |
| 負向：偷插 `S`，`B_C` 錯寫成 `S` | | 預期 1／是 → 只有 reflog 能擋，記錄此結論 |
| reflog 查找：已知推送 `0099dbb5`，預期前一筆 `3fe84edb` | | |
| reflog 查找：以錯誤 base 查 | | 預期不符 |
| D5 逐條（`branch --show-current`、status／cached、`pull --ff-only`、腳本 apply、`diff --stat`、`add`、`commit --only`、`--verify`） | | |
| 清理（`rm` capsule、`rm -rf` clone） | | |

### 2.5 決策閘門計算（plan.md §8.6）

| 項目 | 數值 |
|------|------|
| 省下的貼上次數（逐條列出後加總，不含 push） | |
| 兩輪核准提示次數合計 | |
| 改交使用者的步驟（含 D3b） | |
| D3a／D3d 是否被拒 | |
| R2 路徑可行 | |

決策：

* 固定被擋或改交使用者的步驟 →
* 是否進入 plan.md §7 Phase 3 →
* D0 規則採 R2 或 Q1(c) →
