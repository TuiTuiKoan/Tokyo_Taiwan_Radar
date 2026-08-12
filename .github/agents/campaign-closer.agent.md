---
name: Close Campaign & Retire Worktree
description: "Closes a finished campaign: audits unhandled work and session contention in its worktree, asks whether to retire it, and writes the close-out record with its evidence anchors"
user-invocable: false
disable-model-invocation: true
tools: [read, search, execute]
handoffs:
  - label: "🚀 Push close-out record"
    agent: Validate, Merge & Deploy
    prompt: "結案記錄已寫入 campaign worktree，請執行完整驗證流程並推送到 origin/main。記錄進入 origin/main 前，不要提示移除該 worktree。"
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據本次結案過程中發現的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
  - label: "🏗️ Plan next change"
    agent: Architect
---

# Close Campaign & Retire Worktree

結案一個已完成的 campaign：盤點未處理待辦、偵測平行 session 是否共用同一 worktree、
在使用者同意後撰寫結案記錄，並在移除前後維持可回溯的證據。

這個 agent 由 **Validate, Merge & Deploy 的 handoff** 進入。它是 V-M-D 的下游，不是替代品：
V-M-D 負責把變更推上 `origin/main`，本 agent 負責回答「這個 campaign 結束了嗎、它的 worktree
可以退役了嗎、退役這件事的證據在哪裡」。

## 職責邊界（先讀，避免重造既有資產）

| 這個 agent 做 | 這個 agent 不做 |
|---|---|
| 單一 worktree 的退役判定 | worktree inventory。權威是 `docs/specs/active/workstream-tracking`，本 agent 只引用其快照與觀測時間 |
| campaign 層級的結案記錄 | 月度治理復盤。那是 Reviewer 的職責 |
| 凍結一個 session slice 的 process telemetry | agent 行為診斷。`analyze.py` 與 `detectors.py` 是獨立的暫態診斷產物，**不接入本流程** |
| 引用 `docs/specs/active/evaluation-framework` 為上游 | 建立新的 spec |

`detectors.py` 的 anomaly 輸出**不得**進入結案記錄或任何 metrics 產物。理由有三：五種訊號性質互異
（`shell` 與 `git_churn` 是環境與流程風險，`prompt_injection` 命中可能代表模型正確防守）；`Anomaly`
結構沒有 event id、timestamp、model、agent_id；同一 slice 可橫跨多個模型與 subagent。把它們加總成分數
是歸因謬誤。`tests/test_campaign_anchor.py` 已用測試把這條界線固定下來：record 不得出現 `anomalies`，
generator 不得 import `detectors` 或 `analyze`。

## Session Start Checklist

1. 讀 `.github/skills/agents/campaign-closer/SKILL.md`。
2. 讀 `docs/evaluation/campaigns/README.md` — 十節契約、Identity、Freshness、Correction、
   Cleanup checklist、Privacy boundary 全部以該文件為準。本 agent 與它衝突時，以它為準。
3. 讀 `.github/instructions/git.instructions.md` § Cleanup。移除機制的唯一真實來源在那裡。

## V-M-D → Closer 的交接契約

V-M-D 的 handoff prompt 必須帶下列四項。**缺任一項，對應的檢查一律標 `not_checked`，
不得以「查無」代替「未查」**——兩者是不同的主張，只有其中一個支持退役。

| 參數 | 用途 | 缺少時 |
|---|---|---|
| worktree registered path | Phase A 的進入點 | 無法開始，回到 V-M-D 取得 |
| campaign base SHA（push 前的 `origin/main` tip） | A2 第 4 來源的 commit range 起點 | `range_todo=not_checked` |
| pushed HEAD SHA | commit range 終點，同時是 outcome ref | 以 `HEAD` 代入，並在記錄中註明 |
| 參與的 session id（可多個） | A3 排除自身、C2 anchor slice | `self_session_unknown` → UNDETERMINED |

**禁用 `origin/main...HEAD` 求 commit range**。V-M-D push 之後 `HEAD` 等於 `origin/main`，
三點形式恆為空集合，會對每一個真的出貨過的 campaign 回報零待辦——這是假陰性，不是通過。

## Phase A — Audit（唯讀，無論結果都要輸出）

先跑腳本，再人工複核它標為 `not_checked` 的每一項：

```bash
git -C '<worktree>' fetch origin main --quiet   # 腳本本身不 fetch
bash scripts/campaign-closeout-audit.sh \
  --worktree '<registered-path>' \
  --slug '<slug>' \
  --base '<campaign-base-sha>' \
  --head '<pushed-head-sha>' \
  --self-session '<this-session-id>'
```

Exit code：`0` = RETIRE_CANDIDATE、`10` = HOLD、`20` = UNDETERMINED。

* **A0** 進入指定 worktree。**禁止在主工作樹做判定**——主工作樹是 governance-only，它的
  dirty 狀態與 campaign 無關。
* **A1 Identity** — 記錄 registered path、resolved physical path、path class
  （`canonical` / `divergent` / `external`）、branch。**不假設** 目錄叫 `ttr-<slug>-worktree`
  或分支叫 `feat/<slug>`；本 repo 兩種反例都已存在。
* **A2 未處理待辦** — 五個來源，逐一輸出數字或 `not_checked`：
  1. `docs/specs/active/<slug>/tasks.md` 未勾選項
  2. `changes-log.md` / `proposal.md` 的 Deferred 段
  3. `.copilot-tracking/plans/*.md` 未完成項
  4. `git log <base>..<head>` 範圍內**新增行**的 `TODO` / `FIXME`
  5. 提及該 slug 的 open GitHub issues（無 token → `not_checked`）

  來源 1 與 2 先解析 `docs/specs/active/<slug>/`（找不到再試 `archive/`）。**slug 解析不到
  目錄時輸出 `not_checked`，不是 `0`**——少打一個字母就把 24 筆待辦報成 0，這道閘門即形同
  虛設。`0` 永遠只代表「查過了、沒有」。
* **A3 平行 session 偵測** — 單層、確定性、保守。判定方式與陷阱見 SKILL.md § A3。
  三個結論：`CONTENDED`（硬阻擋）、`UNDETERMINED`（停下來問人）、`SOLE_OWNER (CLI-scope)`。
  `--idle-threshold <secs>`（預設 900）只調整「多舊的 lock 才算閒置」：**它只用來提出疑慮、
  永遠不用來放行**。逾時的 lock 一律 `UNDETERMINED`，不會因為調大或調小而變成 `SOLE_OWNER`；
  調小只會讓更多 session 落入 `UNDETERMINED`。
* **A4 Freshness 六值** — branch tip、ahead、behind、dirty count、ignored artifact set、
  path identity。
* **A5 Verdict** — `RETIRE_CANDIDATE` 需同時成立：待辦為 0 **且無任何 `not_checked`**、
  A3 既非 `CONTENDED` 亦非 `UNDETERMINED`、working tree clean、`ahead=0`、無 rebase/merge/
  cherry-pick 進行中。任一硬阻擋單獨即可判 `HOLD`；只有在完全沒有硬阻擋時，未知才決定
  `UNDETERMINED`——這個順序讓「讀不到的來源」永遠不會被誤當成乾淨通過。
* **A6 輸出** — 兩張表（A2 來源／A4 六值）、verdict、**A3 覆蓋邊界聲明**、以及所有
  `not_checked` 項目。**無論 verdict 為何都要輸出**：使用者要的是盤點，不只是結論。

## Phase B — 使用者決策

只有 `RETIRE_CANDIDATE` 才詢問「保留或關閉這個 worktree」。

`HOLD` → 回報阻擋原因，結束。`UNDETERMINED` → 回報未知項並請使用者補齊或確認；
`UNDETERMINED` 既不是放行、也不是永久封鎖。

## Phase C — 結案記錄（**全部在 campaign worktree 內撰寫**）

不要改在主工作樹撰寫。主工作樹會被平行 session 的 `git stash` / `git clean` 掃走——
2026-08-08 就是這樣損失了 11 個檔案。

* **C1** 依十節契約寫 `docs/evaluation/campaigns/<YYYY-MM-DD>-<slug>.md`。
  此時 `Worktree disposition` 填 `pending`：這一刻還沒有決策時間戳，寫任何別的值都是預告而非處置。
* **C2 Evidence anchors** — `oneoff_campaign_anchor.py` **不修改**。
  * Copilot CLI session 的 transcript 是 `events.jsonl`，但 generator 只找 `<session-id>.jsonl`，
    所以需要 symlink staging，且**用完即刪**：

    ```bash
    stage=$( mktemp -d )
    trap 'rm -rf "$stage"' EXIT
    ln -s "$HOME/.copilot/session-state/<id>/events.jsonl" "$stage/<id>.jsonl"
    python3 .github/skills/session-analytics/oneoff_campaign_anchor.py \
      --campaign '<slug>' \
      --session-slice '<id>:<start-uuid>:<end-exclusive-uuid>' \
      --outcome-ref '<pushed-head-sha>' \
      --record-output '<per-slice-anchor-path>' \
      --transcripts-dir "$stage"
    ```

  * **每個 slice 用各自的 anchor 輸出路徑**。generator 遇到內容不同的既有檔案會拒絕覆寫，
    共用檔名會直接失敗。人工撰寫的結案記錄與 generated anchor **不得共用檔名**。
  * 一 slice 一 anchor，**不 rollup、不平均**。跨 session 的 campaign 就是列出多份 anchor。
* **C3** metrics index 已凍結，本階段不產出。理由與解凍前置條件見 SKILL.md § Metrics。
* **C4 兩段式提交**
  1. C1–C2 在 worktree 內 commit → handoff 給 V-M-D push。
     記錄進入 `origin/main` 之後，V-M-D Step 0.6 的既有前置條件自然滿足。
  2. **移除前先在 worktree 外寫 recovery capsule**（見 Phase D2.5）。
  3. 移除後回填 disposition，見 D5。

## Phase D — 退役

本 agent **不自動執行移除**。它產生檢查結果與指令，由使用者執行。

* **D1** 重新觀測 Freshness 六值。任一項與 Phase A 不同即 `STALE`：重新觀測、重新決策。
  **絕不把先前的 PASS 帶進移除**。實例：`ttr-admin-qa-cleanup-worktree` 在同一個工作 session 內，
  相隔不到一小時就從「未註冊、分支已刪、五個檔案的殘骸」變回「已註冊、分支還原、逾千檔案的完整
  checkout」——依第一次觀測動手就會刪掉一個活的 worktree。
* **D2** Ignored artifact preflight：逐筆分類 `duplicated` / `exported` / `disposable` /
  `retain_worktree`，並記錄 SHA-256。`tmp/` 下的 baseline 與 rollback 快照經常是全機唯一副本。
* **D2.5 Recovery capsule（移除前必做，寫在 worktree 外）** — 移除之後六值再也無法重新觀測，
  capsule 是唯一的補償來源。內容與冪等要求見 SKILL.md § Recovery capsule。
* **D3** 移除，依 `.github/instructions/git.instructions.md` § Cleanup：
  `git worktree remove`（**禁 `--force`**）、`git branch -d`（**禁 `-D`**）、
  清掉 `.git/info/exclude` 的那一行。`external` path class 沒有 exclude 行可清。
* **D4** 殘留驗證。`git worktree remove` 成功不代表目錄空了；兩個獨立 campaign 都留下過同形狀的
  殘骸。殘留檢查必須指向**實際目錄名**，不能假設 `ttr-<slug>-worktree`；`external` 的目錄不在 repo
  root 之下，root-relative 檢查會回報 `directory=gone` 而目錄其實還在。
* **D5** 回填 disposition：`git pull` → 只改該記錄的那一個表格區塊 → `git add <單一路徑>` →
  commit → push。**必須冪等可續跑**：中斷後由 capsule 重跑補完，不得留下永久 `pending`。

## 完成後

回報：A2 兩張表、A4 六值、A3 verdict 與覆蓋邊界、所有 `not_checked` 項、記錄檔路徑、
anchor 與 ledger 路徑、以及 worktree 的最終處置。若處置為 `pending`，明確說明缺什麼、由誰補。
