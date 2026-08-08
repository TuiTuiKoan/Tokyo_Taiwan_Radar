---
description: "建立 admin-qa-cleanup 隔離 worktree，並從 live evidence 重整剩餘 Admin Reports QA cleanup spec"
agent: Engineer
---

# Admin QA Cleanup Bootstrap

本 prompt 的單一任務是建立或確認尚未開始修改的 Admin QA cleanup 隔離 worktree，保全既有
audit artifact，依最新 `origin/main` 與唯讀 operational evidence 重整剩餘工作，並建立一份
execution-ready 的 successor spec。完成後停在下一個明確批准閘門，不實作 T-A，也不執行
任何 production mutation。若先前 invocation 已留下 dirty docs，依 fail-closed 規則停止，
不在本 prompt 內恢復或合併 partial run。

啟動本 prompt 即授權：建立本地 branch/worktree、複製已知 baseline、執行唯讀查詢、建立或
更新 docs spec、執行文件驗證。啟動本 prompt 不授權：程式實作、commit、push、deploy、
workflow dispatch、workflow/variable 變更、maintenance lock 操作、migration apply、
production reset、report settlement、manual annotation dispatch、GPT run 或任何 live DB write。

## 固定識別

* Predecessor spec：`docs/specs/active/admin-reports-204-cleanup/`
* Successor spec slug：`admin-qa-cleanup`
* Successor spec：`docs/specs/active/admin-qa-cleanup/`
* Branch：`feat/admin-qa-cleanup`
* Worktree：`ttr-admin-qa-cleanup-worktree`
* Landing target：`origin/main`
* Canonical path：
  `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree`

使用者口語中的 `/admin-qa-cleanup` 指這個 successor workstream。實際路徑必須遵循
`ttr-<slug>-worktree` 慣例。不得重新建立已移除的
`ttr-admin-reports-204-cleanup-worktree` 或 `feat/admin-reports-204-cleanup`。

## 權威來源與已知交接

新 session 不得依賴先前對話或 invocation 前的 `/memories/session/plan.md`。本次 rebaseline 的
權威順序是：live repository 與 production read-only evidence、checked-in predecessor spec、
checked-in tests。舊 session memory 只能當線索，不能當完成或 mutation 證據。

以下是待重新查證的交接事實，不是免驗證真值：

* 舊 cleanup worktree 與 branch 已通過防護後移除，無同名 remote branch。
* Predecessor spec 應維持 `status: active`，landing target 應為 `branch: origin/main`。在
  final docs-only archive 另行批准前，不得移動或刪除 predecessor spec。
* `tasks.md` 於 2026-08-06 曾觀測到 60 項完成、39 項未完成。必須重新計數並回報差異。
* G-P、G-P.1 與 Lane R 已交付；T-P 已退休。Proposal 內把 G-P / T-P 描述成未來 delivery
  的文字可能已過時。
* T-A 仍要求 T-P deployed，但 T-P 已退休。必須查證 Lane R 是否正式取代 T-P；證據不足時
  標為 blocker，不得實作 T-A。
* 原始 204-row JSONL 已遺失，不得重建或冒充原 artifact。
* 保全的 Lane O baseline source：
  `/Users/flyingship/Development/Tokyo Taiwan Radar/tmp/publication-policy/20260731T025527Z/lane-o-pre-gp1-baseline.json`
* Baseline 預期為 1,379 bytes、mode `0400`，SHA-256：
  `495453151f78ca18b9c8ec7c71709f9359339a3dde7bc04126ae57426f970dad`
* Predecessor `notes.md` 在 final archive 前必須 byte-for-byte 不變。

## Required Steps

### Step 1：讀取規則並保護 main worktree

1. 先讀 `.github/copilot-instructions.md`、`.github/instructions/git.instructions.md`、
   `.github/instructions/scraper.instructions.md`、`.github/skills/agents/engineer/SKILL.md` 與
   predecessor spec 的 `proposal.md`、`tasks.md`、`notes.md`。另讀 `docs/specs/README.md`、
   `docs/specs/_template/proposal.md` 與 `docs/specs/_template/tasks.md`。
2. 以 `/Users/flyingship/Development/Tokyo Taiwan Radar` 為 main repository root。先執行
   `git fetch origin --prune`，不得假設本 prompt 撰寫時的 SHA 仍是最新。
3. 顯示 main worktree status，但不得碰觸、stash、clean、stage、commit、還原或重排其中任何
   WIP。後續所有 spec 讀寫與 validation 都在 canonical worktree 內完成，只有以下 main-root
   例外：worktree 建立/盤點、`.git/info/exclude` idempotent append、baseline 與 ignored
   `scraper/.env` 的唯讀存取，以及 main WIP pre/post preservation check。

### Step 2：依 fail-closed state matrix 建立 worktree

先取得 `git worktree list --porcelain`、canonical path 狀態、local branch、remote branch、
各自 SHA、upstream、ahead/behind、ancestry，以及任何 rebase/merge operation state。

只允許下列狀態：

1. NEW：canonical path、local branch、remote branch 都不存在。以最新 `origin/main` 為明確
   base，建立 `feat/admin-qa-cleanup` 與 canonical worktree。
2. INTERRUPTED NEW：canonical path 與 remote branch 不存在，local branch 存在且 SHA
   **完全等於** `origin/main`，且未掛載於任何 worktree。掛載 existing local branch，不使用
   `-b`。
3. CLEAN CONTINUING：canonical path 是 registered worktree，branch 精確為
   `feat/admin-qa-cleanup`，worktree clean、無 operation in progress，且 HEAD 完全等於
   `origin/main`。只驗證後繼續。

任何其他狀態立即 STOP，包括：path 存在但未註冊、canonical path 掛錯 branch、branch 掛載
於其他 path、remote branch 已存在、local/remote 分歧、ahead/behind 非零、非 ancestor、dirty
docs-only partial run、rebase/merge/cherry-pick/revert/bisect in progress。不得自動 reset、rebase、
搬移、force-add、刪除、覆寫或恢復 partial run；只回報 exact state 與另行 recovery approval需求。

成功建立或確認後：

* 驗證 path、branch、HEAD 與 `origin/main` 一致，且 status clean
* 將 `ttr-admin-qa-cleanup-worktree/` idempotently 加入 main repository `.git/info/exclude`
* 再次確認 main worktree 的原有 WIP bytes 與 status 未被本流程改動

### Step 3：保全 Lane O baseline

1. 不輸出 baseline 內容。使用 `lstat` 檢查 source path 是 non-symlink regular file，並驗證
   size、mode 與 SHA-256。任一不符立即 STOP，不得猜測或重建。
2. Destination 固定為新 worktree 的
   `tmp/publication-policy/20260731T025527Z/lane-o-pre-gp1-baseline.json`。
3. 只在新 worktree 內建立父目錄。使用逐 component `lstat` 拒絕任何 source/destination
   parent symlink。
4. Destination 已存在時，必須以 `lstat` 證明它是 non-symlink regular file；不得覆寫，只能
   驗證。其他 leaf type 一律 STOP。
5. Destination 不存在時，在 destination directory 以 `mktemp` 原子建立 temporary regular
   file，使用 `cp -p` 將 source 複製到該 temporary file，並在 publish 前完成 mode、size、
   SHA 與 `cmp` 驗證。再以同 filesystem hard link 將 temporary file發布為 destination；
   destination 在 publish 時若已存在，hard link 必須以 `EEXIST` 失敗並 STOP。不得使用可能
   覆寫既有 leaf 的 `cp`、`mv` 或 follow-symlink 操作。無論成功或失敗都只清理本次 temporary
   file，不動 source 或既有 destination。
6. Publish 後重新 `lstat` destination，證明它是 non-symlink regular file；驗證 source 與
   destination 都是 mode `0400`、1,379 bytes、SHA 相符，且 `cmp` 完全一致。
7. 使用 `git check-ignore` 證明 destination 仍是 ignored/untracked；若不是立即 STOP。
8. Main root 的 source 是長期保全副本，不得刪除。Successor worktree 的 destination 是執行期
   audit copy；未來移除 worktree 前仍須再次做 unique-artifact preflight。

### Step 4：重新盤點 predecessor spec

1. 記錄 predecessor `notes.md` SHA-256；完成前再次驗證不變。
2. 查詢最新 `origin/main` 與相關 release history。對每個聲稱 delivered 的 SHA 驗證是否為
   `origin/main` ancestor；短 SHA 不可解析或證據不足時標為 `INCONCLUSIVE`，不得自行打勾。
3. 重新計數全部 checkbox，將每個未完成項分類為：
   * live evidence 已滿足但 ledger 未同步
   * 等待自然 scheduled run 或外部條件
   * 可執行的 docs/read-only task
   * 待核准的 tools-only implementation
   * 待 artifact-bound 核准的 production mutation
   * 過時、互斥或 prerequisite 矛盾
4. 明確解決或保留為 blocker：
   * proposal 的 G-P/T-P 未來式與 tasks 的 G-P/G-P.1 delivered、T-P retired、Lane R delivered
     是否矛盾
   * T-A 是否由 Lane R 取代 retired T-P prerequisite
   * predecessor `branch` metadata 是否仍指向已刪除 branch
5. Checkbox、歷史 row count、舊 worktree、舊 session memory 或 proposal 敘述都不能單獨作為
   完成證據。
6. Predecessor `proposal.md`、`tasks.md`、`notes.md` 全部唯讀。開始前記錄三者 SHA-256，完成前
   逐一證明 unchanged。任何 stale metadata、pointer 或 checkbox 修正都只寫入 successor
   transfer map 的建議欄，不修改 predecessor。

### Step 5：收集唯讀 operational evidence

只允許 read-only GitHub / Supabase 查詢，確認：

* exact G-P、G-P.1、Lane R 與其他 prerequisite SHAs 的落地狀態
* Lane O 是否已有 exact G-P.1 後的自然 scheduled run 證據
* maintenance row 是否 inactive，RPC 是否回傳 false
* workflow 與 repository variable 目前狀態
* pure-publication errors、pending reports 與 fresh queue 的 exact paginated counts

查詢前先以非秘密資訊驗證 effective Supabase project ref 精確為
`cjtndektjjpvvjofdvzr`，且 Git remote / GitHub API repository identity 精確為
`TuiTuiKoan/Tokyo_Taiwan_Radar`；任一不符立即 STOP。Repository variable 查詢只允許
`ERROR_RECOVERY_LIVE`、`QA_HEARTBEAT_LIVE`、`REFETCH_THIN_LIVE`，每個只回報 `absent`、
`true` 或 `non-true`，不得列出 raw value 或其他 variables。Workflow query 必須先從
predecessor spec 與 checked-in workflows 建立 exact cleanup-related allowlist，不得列舉或修改
無關 workflows。

每個 count 都要記錄 query timestamp、filters、pagination completeness 與 exact-count evidence。
新 count 不授權 mutation。不得 dispatch workflow、切換 variable、取得 lock、執行 reset、觸發
GPT、close report、寫 field correction 或修改 production row。四象限 auth evidence 若需要真正
write attempt，標為 `APPROVAL REQUIRED`，不得用 production 寫入模擬。不得輸出 secrets。

若既有 read-only query tooling 需要 credentials，只能由短生命週期 Python process 先以
`python-dotenv` 的 explicit absolute `dotenv_path` 直接讀取 main root ignored
`scraper/.env`，並使用 `override=False`，再呼叫既有唯讀 query function。不得複製或修改 env
檔、不得 shell `source`、不得執行 `env` / `printenv`，也不得記錄任何 secret value；只回報
query result、filters、pagination 與 timestamp。

### Step 6：建立 successor spec

在 `docs/specs/active/admin-qa-cleanup/` 建立 `proposal.md` 與 `tasks.md`：

1. 依 repository templates 的 spec 內容結構建立文件，同時遵守全域 Markdown frontmatter
   規則。`proposal.md` frontmatter 必須包含：
   * `slug: admin-qa-cleanup`
   * 非空字串 `title` 與 `description`
   * `status: active`
   * `branch: feat/admin-qa-cleanup`
   * `created` 精確等於 invocation 當日的 `YYYY-MM-DD`
   * `tags: [scraper, tooling]`
2. `proposal.md` 不得包含 `worktree` key。因 frontmatter 已有 `title`，正文不得使用 H1，第一個
   content heading 必須為 `## What`。
3. `tasks.md` 也必須有只含非空字串 `title` 與 `description` 的 YAML frontmatter，沿用 tasks
   template 的 checklist 結構；正文不得使用 H1，第一個 content heading 必須為 `## Tasks`。
4. Successor spec 只包含 live rebaseline 後仍有效的未完成工作、prerequisites、evidence、scope、
   verification、STOP conditions 與 approval gates。
5. 已交付工作只用簡短 predecessor audit references，不複製全部歷史實作步驟。
6. 加入 predecessor-to-successor transfer map，逐項說明原未完成 checkbox 被移轉、已滿足、退休、
   blocked 或需另行批准。回報重新計數後的 `N`，不要強迫維持歷史 39。Predecessor 的 stale
   metadata、pointer 或 checkbox 只列為建議修正，不在本 prompt 寫回。
7. Predecessor spec 不得修改、archive、刪除或移動。
8. Successor spec 必須明說：它是未完成工作的新 execution tracker；predecessor 只保留 audit
   history 與尚未取得 final archive approval 的證據。
9. 不得建立程式實作、migration、workflow、production manifest 或 apply script。

### Step 7：驗證並停止

執行：

* Successor `proposal.md` 與 `tasks.md` frontmatter YAML parse。Assert proposal 的 `slug`、
   `status`、`branch`、`created`、`tags` 精確值，`title` / `description` 為非空字串，無
   `worktree` key，第一個 content heading 是 `## What`；assert tasks frontmatter key set 精確為
   `title` / `description`、兩者皆為非空字串，第一個 content heading 是 `## Tasks`
* Markdown / prompt diagnostics
* `git diff --check` 與 `git diff --cached --check`；cached diff 必須為空
* 一般 `git diff --check` 不涵蓋 untracked files。對每個 untracked successor file 執行等價的
   UTF-8-aware read-only validator，逐一驗證 valid UTF-8、EOF LF、無 trailing whitespace、無 tab
   character、無 `<<<<<<<` / `=======` / `>>>>>>>` conflict-marker line；任一不符都是 FAIL
* 將 `git diff --name-only`、`git diff --cached --name-only` 與
   `git ls-files --others --exclude-standard` 合併後做 path-scope assertion。非 ignored change set
   必須精確等於 `docs/specs/active/admin-qa-cleanup/proposal.md` 與
   `docs/specs/active/admin-qa-cleanup/tasks.md`，兩者都必須是 untracked；不得有 tracked 或 staged
   change
* Predecessor `proposal.md`、`tasks.md`、`notes.md` SHA-256 unchanged proof
* Baseline destination mode、size、SHA、`cmp` 與 ignored proof
* Worktree path、branch、base SHA、ahead/behind、status
* Main worktree pre/post status proof，確認原 WIP 未被修改

完成後停止。不得 commit、push、rebase、deploy、移除 worktree或執行任何 T-A / production
implementation。成功狀態是 `DRAFT READY FOR REVIEW`：worktree 刻意只包含兩個已驗證的
untracked successor files。下一個批准閘門必須先做 successor draft review 與 docs-only commit；
在 worktree 恢復 clean 且取得 committed successor spec SHA / digest 前，不得開始 T-A。

之後的 tools-only slice 必須在另一個明確 invocation 中綁定：committed successor spec digest、
exact allowed paths/functions/tests、fake client / blocked-network test contract，以及獨立 Tester
要求。不得由本 prompt 推定批准。

## Required Protocol

* 全程 fail closed；任何 evidence mismatch、state drift、secret exposure risk 或 parallel-session
  scope overlap 都停止並回報。
* 本 prompt 對本 invocation 明確縮限 Engineer 的 generic lifecycle：不得更新 Engineer
   `history.md` / `SKILL.md` / agent files，不得依 generic spec tracking 規則 commit checkbox，
   不得 commit、push、deploy，也不得呼叫 Architect、Plan Critic、Tester 或其他 handoff。
   Engineer 的其餘安全、domain 與 read-before-write 規則繼續適用。
* 不得使用 `--no-verify`、`-D`、`worktree remove --force`、`reset --hard` 或 repo-wide stash。
* 不得以 dry-run、read-only query、test PASS、worktree 建立或本 prompt invocation 描述成
  production approval。
* 若執行期間 `origin/main` 前進，先停止寫入並重新 fetch。因本 prompt 禁止 rebase，回報 drift
  後停止，不在同一 invocation 自動追上。

## Response Format

回報：

1. Worktree path、branch、base SHA、ahead/behind、clean/dirty
2. Baseline source/destination、size、mode、SHA、`cmp` 與 ignored 驗證
3. 重新計數後全部 `N` 項未完成工作的分類與 evidence timestamp
4. Predecessor 矛盾、未寫回的建議修正、successor transfer map 與三檔 unchanged proof
5. Read-only operational evidence，以及所有 `INCONCLUSIVE` / `APPROVAL REQUIRED` 項目
6. 文件驗證、diagnostics、scope assertion 與 main WIP preservation 結果
7. `DRAFT READY FOR REVIEW` 狀態、下一個 docs-only review/commit gate，以及 worktree clean 後才可
   提出的最小 tools-only slice、exact allowlist、STOP boundary 與所需批准
