---
description: "以 live 證據對帳 workstream-tracking ledger 的 worktree 拓撲，補回缺漏的 .git/info/exclude 條目，並將已退役工作線正式關帳"
agent: Architect
---

# Ledger Topology Reconcile

本 prompt 的單一任務是讓 `workstream-tracking` ledger 重新等於 live 拓撲：補上 `.git/info/exclude`
缺漏條目、把 2026-08-09 已退役的三個 worktree 正式關帳、補登記從未被記錄的 worktree，並修正
數個已過期或已為假的斷言。

本 prompt **不做**任何功能實作、worktree 建立或刪除、remote mutation、DB write 或部署。

## 授權邊界

啟動本 prompt 即授權：唯讀 git 查詢、讀取 spec 與 prompt 檔案、**建立本 prompt 專屬的隔離
worktree 與其 branch**、對 `.git/info/exclude` 做 idempotent append、更新
`docs/specs/active/workstream-tracking/` 內的兩份檔案、更新 session memory。

**不授權**：程式實作、建立或刪除**本 prompt 專屬以外**的 worktree/branch、`--force`／`-D`／
`git clean`／無 `--autostash` 的 `git stash`、remote ref 變更、production DB write、deploy、
workflow dispatch、移動或刪除其他 spec。

commit 與 push 各需使用者明確批准，不得自行執行。

**主工作樹一律唯讀**。主工作樹經常有其他 session 的未提交 WIP；本 prompt 只以 `git -C` 讀取它的
狀態作為 ledger 事實，不得在其中編輯、stage、stash、clean 或還原任何東西。

## 固定識別

* Spec slug：`workstream-tracking`（governance-only，最終落在 `origin/main`）
* Main repository root（**唯讀**）：`/Users/flyingship/Development/Tokyo Taiwan Radar`
* 本 prompt 專屬 worktree：
  `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile`
* 本 prompt 專屬 branch：`agents/ledger-topology-reconcile`
* 唯二可編輯的 ledger 檔（**在專屬 worktree 內，必須用絕對路徑**）：
  * `…Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile/docs/specs/active/workstream-tracking/tasks.md`
  * `…Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile/docs/specs/active/workstream-tracking/proposal.md`
* 退役證據封存：`~/ttr-wip-archive/20260810-tier1-manifest`

`docs/specs/active/workstream-tracking/` 這兩個檔名在**每一個** worktree 內都有副本，主工作樹也有一份。
**只能編輯上列專屬 worktree 內的路徑**；grep 時務必限定該路徑，否則會命中別的副本並得出錯誤結論。
主工作樹那一份是唯讀參照，不得修改。

## 權威來源與已知交接

新 session 不得依賴先前對話或既有 session memory。權威順序是：live git 狀態、封存證據、
checked-in spec。以下是**待重新查證的交接事實，不是免驗證真值**——本 repo 常有 3 個以上
session 平行寫入，數字在數小時內就會失效（2026-08-12 當天同一 session 內 dirty 就從 4 漂到 5）。

### 已退役工作線（2026-08-09，同一次操作、同一份封存）

| Worktree | Branch | 退役時 tip |
|---|---|---|
| `ttr-security-hardening-worktree` | `feat/security-hardening-report-only-csp` | `e450c6b4` |
| `ttr-event-report-writer-safety-worktree` | `fix/event-report-writer-safety` | `18cd501b` |
| `ttr-taiwan-expo-japan-worktree` | `feat/taiwan-expo-japan` | `28e6fcb6` |

三者皆以 plain `git worktree remove` + `git branch -d` 移除（exit 0），`git cherry` 對 local 與
origin main 皆為空，無 remote branch。封存 manifest 於 2026-08-12 重驗 103/103 digest PASS。

`feat/security-hardening-report-only-csp` 的交付即 `e450c6b4`
（`fix(web): harden structured data and response headers`），已是 `origin/main` 祖先，導入了
report-only CSP builder、baseline security headers 與 security-header smoke test。
**不得重建**該 branch 或 worktree。

### ledger 已知漂移（需 live 重查後修正）

> 下列只是**漂移類型範例**，不是待辦清單。具體名稱與數字必須全部以 Step 1 的 live 結果重新推導。
> 實例：本 prompt 初版曾列 `ttr-publication-date-parser-worktree` 為「live 存在但未記載」；
> 兩天後另一個 session 已把該工作線正常完工並關閉 worktree 與 branch，交付落在 `751c6b61`
> （`fix(scraper): harden publication date parsing for hanmoto and ndl`）。
> **這是正常結案，不是事故**，不需要追查，也不需要為它補結案紀錄——它整個生命週期都落在兩次
> ledger 快照之間，從未進過 ledger。教訓在於：具名提示會過期，照舊提示執行會寫入錯的內容。

漂移類型：

* **拓撲總數不符**。ledger 宣稱 10；2026-08-12 實測 9；2026-08-14 實測 11。三個不同數字，
  充分證明計數不可作驗收門檻。
* **有 worktree 完全未被 ledger 記載**（見下方命名慣例段）。
* **有 worktree 已消失但 ledger 仍列為存在**。
* **spec 狀態標註與實際目錄不符**（例：admin-qa-cleanup 曾被三處標為「未建立」）。
* **已勾選却為假的斷言**。G4 曾宣稱 `.git/info/exclude` 已補齊且「8 個 basename 全數排除」，
  實測缺 2 個。同一行上還混有另一個獨立的過期事實（主工作樹 dirty 數），修正時不可整行刪掉。
* `docs/specs/parked/` 不存在，只有 `active/` 與 `archive/`。不得硬編三態路徑。

### 兩種 worktree 命名慣例並存（待決策）

ledger 只認舊慣例，完全未記載新慣例：

| 慣例 | 位置 | Branch 前綴 | 相對 repo root |
|---|---|---|---|
| 舊 | `<repo>/ttr-<slug>-worktree` | `feat/`、`chore/` | 巢狀，需 exclude 條目 |
| 新 | `<repo>.worktrees/<slug>` | `agents/` | 外部 sibling，不適用 exclude |

2026-08-14 實測新慣例已有三個正式註冊的 worktree：`agent-handoff-and-worktree-cleanup`、
`anomaly-detection-workflow-integration`、`mobile-ssh-agent-remote-development`。

另外 `<repo>.worktrees/agents-vscode-performance-issues` 目錄存在、內有 `.git`，但
**未出現於 `git worktree list`**。需判定它是殘留、進行中，還是註冊已被 prune；
在取得使用者指示前**不得刪除、不得 prune、不得 re-add**。

## Required Steps

### Step 0：建立隔離 worktree（所有編輯都在其中進行）

本 repo 目前有兩種 worktree 命名慣例並存：

| 慣例 | 位置 | Branch | 是否會弄髒主工作樹 |
|---|---|---|---|
| 舊 | `<repo>/ttr-<slug>-worktree` | `feat/<slug>` | 會（巢狀，需 exclude 條目） |
| 新 | `<repo>.worktrees/<slug>` | `agents/<slug>` | 不會（位於 repo root 外） |

**本 prompt 採用新慣例**，因為它建在 repo root 之外，永遠不會出現在主工作樹的 untracked 清單，
也不需要 exclude 條目。

先取得 `git worktree list --porcelain`、目標路徑狀態、local/remote branch 與各自 SHA，再依狀態分流：

| 狀態 | 動作 |
|---|---|
| 路徑與 branch 都不存在 | `git worktree add '<worktree path>' -b agents/ledger-topology-reconcile origin/main` |
| branch 存在、未掛載 | `git worktree add '<worktree path>' agents/ledger-topology-reconcile`（不加 `-b`） |
| 已是註冊 worktree 且 clean | 只驗證 path/branch/HEAD 後直接使用 |
| 路徑存在但未註冊 | **STOP**，回報後等待指示，不得 `-f` |
| 其他任何分歧 | **STOP** |

建立後 `cd` 進去，確認 branch 與 HEAD 正確且 `git status --porcelain` 為空。
**此後所有 ledger 編輯都在這個 worktree 內完成。**

注意兩個容易踩到的點：

* **建立這個 worktree 本身會改變你要記錄的拓撲**。Step 3 必須把它一併登記進 ledger，不能只記錄
  Step 1 取證當下的狀態。
* `.git/info/exclude` 位於 **common git dir**（`git rev-parse --git-common-dir` 指回主 `.git`），
  因此在本 worktree 內修改它會即時對整個 repo 生效，不需要回到主工作樹。

### Step 1：以既有 audit 實作取證（不得另寫一份 inventory）

1. 先讀 `.github/instructions/git.instructions.md`、上列兩份 ledger 檔，以及
   `.github/prompts/workstream-audit.prompt.md`。
2. `git fetch origin --prune`（唯讀），取得 `origin/main` 與本地 `HEAD`。
3. 執行 `tasks.md` **Phase 0 區塊內的 canonical 查證指令**，不要自寫臨時腳本。保留每個 worktree 的
   完整 registered path、physical path、path class、branch、ahead/behind、dirty。
4. 另外取得 `.git/info/exclude` 內容、以及所有**實際存在**的 spec 狀態目錄下的 spec 清單。

STOP 條件：security-hardening 的 ref／worktree／路徑重新出現；`e450c6b4` 不再是 `origin/main`
祖先；有 rebase／merge／cherry-pick 進行中。遇到即停止並回報，不自行修復。

### Step 2：補回 `.git/info/exclude`（獨立前置，與 ledger 編輯分開）

此檔在 common git dir，於本 worktree 內修改即對整個 repo 生效。
**只需要處理位於 repo root 內的巢狀 worktree**；`<repo>.worktrees/` 底下的在 root 之外，
不會出現在主工作樹 untracked 清單，不需要也不適用 exclude 條目。

以 Step 1 的實測結果推導「位於 repo root 內、但不在 exclude 內」的 worktree 集合，逐一 idempotent append：

```bash
grep -qxF 'ttr-<slug>-worktree/' .git/info/exclude || echo 'ttr-<slug>-worktree/' >> .git/info/exclude
```

2026-08-14 實測 repo root 內的 7 個巢狀 worktree 已全數涵蓋，因此本步驟**可能是 no-op**。
不要預設一定有缺漏，也不要沿用任何舊清單；一律以執行當下推導出的集合為準，並回報實際補了幾行。

此檔為 local-only，永不進 commit。本步驟修的是 live 曝險（平行 session 的 `git add -A` 會把未排除的
worktree 掃進 index），與 Step 3 的文件修正是兩件事，不可合併。

### Step 3：對帳 ledger

只編輯固定識別列出的兩個絕對路徑。全部套用：

1. 依 Step 1 證據刷新 Snapshot 基準、註冊路徑拓撲表、「未納入編號的工作線」表與三方對照表。
   整批刷新，不是只改一列。
2. 補登記 live 存在但 ledger 未記載的 worktree，含 branch 與 path class。**包括 `<repo>.worktrees/`
   底下的全部項目**；它們位於 repo root 外，不適用 exclude，但仍是正式註冊的 worktree，必須入帳。
   同時移除 ledger 中已不存在的 worktree。
3. **對兩種命名慣例作出明確記載與建議**：在 proposal 的三維度模型與路徑身分段補上
   `<repo>.worktrees/<slug>` + `agents/<slug>` 這組慣例，並列出它相對舊慣例的差異
   （不污染主工作樹 untracked 清單、不需 exclude）。**只提出建議，不自行改寫
   `git.instructions.md` 的命名規則**；是否正式改規範由使用者決定。
4. 把未註冊的 `<repo>.worktrees/` 目錄（如 `agents-vscode-performance-issues`）列入治理缺口，
   標明待判定，不執行任何刪除或 prune。
5. 三個已退役 worktree 合併成**一筆**結案紀錄：共用封存路徑、各自 branch 與 tip、`e450c6b4` 為
   security 交付 commit、非強制刪除、cherry 為空。並從現行拓撲、停滞清單、缺 spec 清單、
   G2 與 G3 待辦中移除這三者。
6. 修正 spec 狀態標註與實際目錄不符之處（如 admin-qa-cleanup 的「未建立」）。
7. 修正 G4 那個為假的 `- [x]` 與過期的 dirty 數；保留同一行上另一個獨立事實，不得整行刪除。
8. 把 proposal 內對 external registration 的現在式敘述改為「當時觀測 + 已退役結果」。保留
   「worktree 身分需完整 registered path 證據」這條通則，它仍然有效。
9. `docs/specs/security-hardening-plan-RECOVERED.md` 不得修改。它是歷史 Round 1／Round 2 邊界，
   不是 active worktree 主張。

### Step 4：以雙向一致性驗收

驗收是集合相等，不是字串搜尋，也不是數字比對：

1. ledger 內每一個 worktree 斷言 → 都能對應一個 live 註冊。
2. 每一個 live 註冊 → 都出現在 ledger 內。
3. 每個已退役 worktree → 只出現在結案紀錄一次，且不出現在任何「現行／待決」區塊。
4. 沒有任何未勾選或現在式項目宣稱已退役 worktree 仍待決定。
5. spec inventory 涵蓋所有實際存在的狀態目錄，並雙向回報目錄位置與 frontmatter `status` 的落差。
6. 計數與 ahead/behind 只作**有日期的敘述**，不得作為驗收門檻。
7. `git diff --check` 乾淨；Markdown 連結與 frontmatter 仍有效。

不需要 scraper run、web build、DB 查詢或部署。

### Step 5：commit 與 push（各需明確批准）

在**本 prompt 的 worktree 內**操作，不要回主工作樹提交。

1. 只 stage 兩個核准的 ledger 檔，確認 `git diff --cached --name-only` 恰好只有這兩個。
   因為在隔離 worktree 內，這裡不會有其他 session 的 WIP 可夾帶。
2. 提交後先與最新 `origin/main` 對齊：`git fetch origin main` 然後
   `git rebase origin/main`（本 worktree clean，不需要 autostash）。
3. 以 `git log origin/main..HEAD --oneline` 確認**只有自己的 commit**，再請使用者批准。
4. 批准後推送：`git push origin HEAD:main`。
5. 推送後用 `git ls-remote origin refs/heads/main` 對照本地 SHA 驗證，不要只信 push 輸出。
6. 全程不得碰主工作樹的 WIP；結束時確認主工作樹的 dirty 檔案與開始時相同。

### Step 6：回報但不執行的交接事項

明列且不動手：G4 的 9 筆 open Dependabot 漏洞、工作線 B 與 C、仍存活 worktree 的 G3 去留決定。
本次對帳不得成為延後這些事項的理由。

## 已知陷阱

先讀 `tasks.md` 的「操作教訓」段落。特別注意：

* worktree 路徑含空白（`Tokyo Taiwan Radar`），`awk '{print $2}'` 只會取到 `Tokyo`。
* `Development`／`development` 是 Git lexical registration 分裂，解析到同一 inode，兩者在文字證據中
  不可互換；也不可用 `registered_path != physical_path` 當偵測條件。
* basename 只能顯示用，不能支撐 containment 結論。
* `grep -c` 命中 0 時 exit code 為 1，會中斷 `&&` 鏈，需 `|| true`。
* zsh 的 `[ "$a" \> "$b" ]` 不支援字串比較。
* `cmd && echo '(空=乾淨)'` 不論有無輸出都會印，是無效驗證。
* ledger 檔在多個 worktree 內有同名副本，相對路徑 grep 會命中錯的那份。

## 期望產出

1. `.git/info/exclude` 已補齊（local-only，不進 commit），並回報補了哪幾行。
2. 兩份 ledger 檔就地更新，內容等於 live 拓撲，且三個已退役 worktree 只以單一結案紀錄存在。
3. 一份雙向一致性驗收結果，含明確 PASS／FAIL。
4. 一個 scope 只含兩個 docs 檔的 atomic commit 提案，附建議 commit message，等待批准。
5. 交接清單：G4 漏洞、B／C 線、其餘 G3 決定。

完成後停止。不啟動 security Round 2；若日後要做，另建 `docs/specs/active/security-round2/`
與 `ttr-security-round2-worktree`（branch `feat/security-round2`），不得復用已退役的名稱。
