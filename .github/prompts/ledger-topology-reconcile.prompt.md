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

啟動本 prompt 即授權：唯讀 git 查詢、讀取 spec 與 prompt 檔案、對 `.git/info/exclude` 做
idempotent append、更新 `docs/specs/active/workstream-tracking/` 內的兩份檔案、更新 session memory。

**不授權**：程式實作、建立或刪除 worktree/branch、`--force`／`-D`／`git clean`／無 `--autostash`
的 `git stash`、remote ref 變更、production DB write、deploy、workflow dispatch、移動或刪除其他 spec。

commit 與 push 各需使用者明確批准，不得自行執行。

## 固定識別

* Spec slug：`workstream-tracking`（governance-only，落在 `origin/main`）
* Main repository root：`/Users/flyingship/Development/Tokyo Taiwan Radar`
* 唯二可編輯的 ledger 檔（**必須用絕對路徑**）：
  * `/Users/flyingship/Development/Tokyo Taiwan Radar/docs/specs/active/workstream-tracking/tasks.md`
  * `/Users/flyingship/Development/Tokyo Taiwan Radar/docs/specs/active/workstream-tracking/proposal.md`
* 退役證據封存：`~/ttr-wip-archive/20260810-tier1-manifest`

這兩個 ledger 檔在多個 linked worktree 內都有同名副本。**只能編輯上列絕對路徑**；grep 時也必須
限定該路徑，否則會命中錯的副本並得出錯誤結論。

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

* 註冊拓撲總數宣稱 10，2026-08-12 實測為 9。
* `ttr-deps-security-worktree`、`ttr-publication-date-parser-worktree` 在 ledger 內 0 次提及。
* admin-qa-cleanup spec 在三處被標為「未建立」，但該目錄實際已存在。
* G4 有一個**已勾選卻為假**的斷言：宣稱 `.git/info/exclude` 已補 `ttr-admin-qa-cleanup-worktree/`
  並「8 個 basename 全數排除」，實測缺 2 個。同一行還有另一個獨立的過期事實（「dirty 1」），
  修正時不可把兩者一起整行刪掉。
* `docs/specs/parked/` 不存在，只有 `active/` 與 `archive/`。

## Required Steps

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

以 Step 1 的實測結果推導「位於 repo root 內、但不在 exclude 內」的 worktree 集合，逐一 idempotent append：

```bash
grep -qxF 'ttr-<slug>-worktree/' .git/info/exclude || echo 'ttr-<slug>-worktree/' >> .git/info/exclude
```

2026-08-12 實測缺 `ttr-admin-qa-cleanup-worktree/` 與 `ttr-publication-date-parser-worktree/`，
但**必須以執行當下的實測集合為準**。

此檔為 local-only，永不進 commit。本步驟修的是 live 曝險（平行 session 的 `git add -A` 會把未排除的
worktree 掃進 index），與 Step 3 的文件修正是兩件事，不可合併。

### Step 3：對帳 ledger

只編輯固定識別列出的兩個絕對路徑。全部套用：

1. 依 Step 1 證據刷新 Snapshot 基準、註冊路徑拓撲表、「未納入編號的工作線」表與三方對照表。
   整批刷新，不是只改一列。
2. 補登記 live 存在但 ledger 未記載的 worktree，含 branch 與 path class。
3. 三個已退役 worktree 合併成**一筆**結案紀錄：共用封存路徑、各自 branch 與 tip、`e450c6b4` 為
   security 交付 commit、非強制刪除、cherry 為空。並從現行拓撲、停滯清單、缺 spec 清單、
   G2 與 G3 待辦中移除這三者。
4. 修正 admin-qa-cleanup spec 的「未建立」（三處）。
5. 修正 G4 那個為假的 `- [x]` 與過期的 dirty 數；保留同一行上另一個獨立事實，不得整行刪除。
6. 把 proposal 內對 external registration 的現在式敘述改為「當時觀測 + 已退役結果」。保留
   「worktree 身分需完整 registered path 證據」這條通則，它仍然有效。
7. `docs/specs/security-hardening-plan-RECOVERED.md` 不得修改。它是歷史 Round 1／Round 2 邊界，
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

1. 只 stage 兩個核准的絕對路徑，並確認 `git diff --cached --name-only` 恰好只有這兩個檔，
   沒有夾帶平行 session 的 WIP。
2. 本地 `main` 通常落後 `origin/main`，無法直接 fast-forward push。二擇一並明講採用哪個：
   * `git -c rebase.autoStash=true rebase origin/main`，事後確認他人 WIP 完整還原；或
   * ledger「只推自己 commit」段的做法：以 `origin/main` 為起點開臨時 worktree，
     在其中套用變更後 `git push origin HEAD:main`。
3. push 前先 `git log origin/main..HEAD --oneline`，確認只帶自己的 commit，再請使用者批准。

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
