# pr-flow-tiering — Phase B notes

## B1 `check_push` 分流實作紀錄（2026-10-22，Engineer／Fable）

### 改前／改後測試數字

| 階段 | 命令 | 結果 |
|---|---|---|
| 改前基線（未加新測試） | `python3 -m pytest scripts/claude/tests scripts/tests -q` | 504 passed |
| 加入決策表測試、程式未改 | `python3 -m pytest scripts/claude/tests/test_bash_guard.py -q` | **40 failed**, 408 passed；失敗全是 `test_push_table[R3…R12]` 的 allow 案例（現行 `check_push` 一律回 ask），所有 ask 與 deny 案例在舊程式上已通過 |
| 改後 | `python3 -m pytest scripts/claude/tests scripts/tests -q` | **615 passed** |

### 決策表 → 測試對照

測試在 `scripts/claude/tests/test_bash_guard.py` 的 `PUSH_TABLE`，參數化為 `test_push_table[<row>:<command>]`；R11（deny 列）在 `DENY` 的 `git-force-push` 區塊，由 `test_must_deny` 驗證。`test_push_table_covers_every_row_both_ways` 確認每一列都有對應案例，且依賴目的端的列（R8–R10、R12）同時有 allow 與 ask 案例。

| proposal 列 | row id | positive／negative 範例 |
|---|---|---|
| 沒有 refspec | `R1-no-refspec` | ask：`git push`、`git push origin`、`git push -uo ci.skip origin`、`git push --repo origin feat/x`（argv[0] 永遠是 repository） |
| `HEAD`／`@` | `R2-head` | ask：`HEAD`、`@`、`HEAD~1`、`@{u}`、`HEAD:HEAD`、`$(git branch --show-current)`、`"$BRANCH"` |
| 目的端是 feature branch | `R3-feature` | allow：`feat/x`、`-u origin feat/x`、`feat/x:feat/x`、`HEAD:feat/x`、`HEAD:refs/heads/feat/x`、`-uo ci.skip origin feat/x` |
| `main:feat/x` | `R4-main-src` | allow：`main:feat/x`、`refs/heads/main:feat/x` |
| 目的端是 main | `R5-main-dst` | ask：`main`、`HEAD:main`、`feat/x:main`、`x:refs/heads/main`、`heads/main` |
| 只是包含 main 字串 | `R6-substring` | allow：`feat/main-fix`、`maintenance`、`mainline`、`main:maintenance` |
| `--all`／`--branches`／`--tags`／`--follow-tags`／`refs/tags/` | `R7-bulk` | ask：各旗標、`HEAD:refs/tags/v1`、`refs/heads/*:refs/heads/*` |
| 多個 refspec | `R8-multi` | allow：`feat/x feat/y`；ask：`feat/x main`、`feat/x HEAD`；deny（DENY 區）：`feat/x :old`、`feat/x +feat/y` |
| remote 是 URL／`--repo` | `R9-url` | allow：`https://… feat/x`、`git@… feat/x`、`--repo=… origin feat/x`；ask：`https://… main`、`https://…`（無 refspec） |
| `--dry-run`／`-n` | `R10-dry-run` | allow：`-n origin feat/x`；ask：`-n origin main`、`-n origin HEAD` |
| deny 列 | DENY `git-force-push` | `--force origin feat/x`、`-fn`、`-nd`、`--force-with-lease origin feat/x`、`--delete origin feat/x`、`:feat/x`、`+feat/x`、`--all --force`、`--tags -f`、`--prune origin feat/x`、`--mirror <url>`、`bash -c 'git push -f origin feat/x'` |
| 包裝 | `R12-wrapped` | allow：`git -C . push origin feat/x`、`env X=1 git push origin feat/x`、`bash -c 'git push origin feat/x'`、`timeout 30 …`；ask：同形式推 main 或無 refspec |

### 偏離／超出決策表之處（皆往保守方向）

1. **`--no-verify` 一律 ask**（`X-no-verify`）。決策表只看目的端；但 `--no-verify` 會跳過 `.githooks/pre-push` 的 gitleaks 掃描，repo 規則是「Never `--no-verify`」。若放行推 feature branch，等於讓 agent 無聲繞過 secret 掃描。放在 `PUSH_ASK_FLAGS`，和 `--all` 等同級。
2. **`heads/main` 視為 main**。git 的 DWIM 會把 `heads/main` 解成 `refs/heads/main`；`MAIN_REFS = {"main", "refs/heads/main", "heads/main"}`，仍是完整名稱比對，不是子字串。
3. **remote 位置含變數或命令替換時 ask**（例：`git push "$R" feat/x`）。決策表說 remote 不影響目的端，但 `$R` 展開為空字串時 `feat/x` 會變成 remote、refspec 消失，目的端回到當前 branch。既有的 `_dynamic_args` 只放行 `git rev-parse`／`git branch --show-current`／`pwd` 三種替換，這些展開後文字為空，同樣落入 ask。
4. **目的端含 `~ ^ * @ : ? [` 或 `..`、或在 `refs/tags/` 下 → ask**。這些由 git 在執行期解析，hook 無法確定。
5. **短旗標群組的 `-o` 值解析修正**。舊碼 `-uo ci.skip origin` 會把 `ci.skip` 當成 positional；舊制一律 ask 所以沒差，新制下 `origin` 會被誤當成 refspec 而放行。現在 `-uo <value>` 會吃掉下一個參數（`-ofoo` 則值就在群組內）。對應測試 `R1-no-refspec:git push -uo ci.skip origin`（ask）與 `R3-feature:git push -uo ci.skip origin feat/x`（allow）。

### 改動的既有測試

- `PUSH_ASK` 清單改成由 `PUSH_TABLE` 派生；原 17 條全部保留為 ask，只有 **`git push -u origin feat/x` 從 ask 改為 allow**（R3），這正是本 Phase 的目的。
- `test_push_variants_ask` 改名為 `test_push_table`（參數化含 allow 與 ask）。
- `test_policy_never_opens_files` 的掃描清單加入 `PUSH_ALLOW`。
- `ASK_REASON` 文字改為「git push to main, or to a destination the hook cannot determine, requires explicit user approval [push-gate]」；`test_ask_payload_shape_is_valid_output` 與 `test_launcher.py::test_ask_is_forwarded` 都引用常數，不需改。
- `RULES["git-force-push"]` 的 Safer 建議從「use plain `git push`, which asks for approval」改為「push a feature branch with `git push origin <branch>` (pushes to main ask for approval)」。

### 殘餘風險（未處理）

- **短名稱的 tag**：`git push origin v1.0` 若 `v1.0` 是 tag，git 會推到 `refs/tags/v1.0`，hook 只看到 `v1.0` 不是 main → allow。決策表只要求 `refs/tags/` 前綴 ask；要收緊需改成「所有短名稱都 ask」，會把 feature branch 一起擋掉，不建議。
- **`git -c core.hooksPath=… push origin feat/x`**：`-c` 是 `GIT_OPT_ARG`，直接跳過，可用來停用本機 pre-push gitleaks 掃描後放行。與 `--no-verify` 同類，但 `-c` 的值沒有逐一檢查。遠端 GitHub push protection 仍在。
- **git alias、`$VAR` 當動詞**：既有 AGENTS.md「未涵蓋」清單已列，不變。
- 以上三項都不是本 Phase 新開的洞（舊制一律 ask 時，這些命令也只是「問一下」，而使用者在 auto mode 下通常會按 Yes）。

## B2 與 `.claude/settings.json` 的互動調查（只調查、未改檔）

環境：Claude Code `2.1.304`（`claude --version`，2026-10-22）。本 session 由主目錄啟動、以 subagent 執行，載入的是主目錄的舊 `_policy.py`（一律 ask），因此**無法在本 session 內區分「hook allow＋settings ask」與「hook ask」**；實測項目全部標為 NOT TESTED，留給使用者依下方步驟執行。

### 文件查證（WebFetch，2026-10-22，`code.claude.com/docs/en/*`）

| 問題 | 來源 | 原文（節錄） | 結論 |
|---|---|---|---|
| hook 回 `allow` 時，`permissions.ask` 還會提示嗎？ | `/permissions` § Extend permissions with hooks → Precedence among rules, hooks, and mods | "PreToolUse hook decisions don't bypass permission rules. Claude Code evaluates deny and ask rules regardless of what a PreToolUse hook returns: a matching deny rule blocks the call, and **a matching ask rule still prompts even when the hook returned `"allow"` or `"ask"`**." | **會提示**。`Bash(git push:*)` 不動的話，`git push -u origin feat/x` 仍跳核准，hook 的 allow 沒有可見效果 |
| 同上，hooks 頁 | `/hooks` § PreToolUse decision control，`permissionDecision` 欄位 | "`"allow"` skips the permission prompt, except for actions no mode auto-approves and reads from network paths. … Deny and ask rules are still evaluated regardless of what the hook returns" | 同上 |
| 規則間優先序 | `/permissions` § Manage permissions | "Rules are evaluated in order: deny, then ask, then allow. … a matching ask rule prompts even when a more specific allow rule also matches the same call." | 無法用 `permissions.allow` 替 feature branch 開例外；要放行只能**移除或收窄 ask 規則** |
| 多個 hook 回不同決定 | `/hooks` | "precedence is `deny` > `defer` > `ask` > `allow`" | 與 `_policy.combine` 一致 |
| hook `ask` 在 auto mode | `/hooks` | "A hook's `"ask"` also forces a permission prompt in auto mode: the classifier can still deny the tool call, but it can't approve the call silently." | 移除 settings ask 規則後，推 main 仍由 hook 的 ask 強制提示（ai-portability U5 在 `2.1.296` 已實測 hook ask 在 auto mode 會跳提示） |
| auto mode 分類器對推 feature branch | `/permission-modes` § Allowed by default；`/auto-mode-config` § Common boundaries | "Pushing to any branch of the repository you're working in, including the default branch. A non-default branch whose name marks it as a deploy or publication target, such as `production` or `gh-pages`, isn't covered … From v2.1.203 until v2.1.211, only routine default-branch pushes and pushes to the branch you started on or to branches Claude created were allowed by default." | 文件上分類器**預設放行**推本 repo 任何 branch（含 main）。使用者 memory 2026-10-13 記錄分類器把 `git push origin HEAD:main` 判為 Production Deploy 拒絕，與目前文件不一致；可能是版本差異或分類器依內容判斷。無論如何，主閘門是 hook 的 ask，不是分類器 |
| content-scoped ask 規則在 auto mode | `/permission-modes` § How the classifier evaluates actions；`/auto-mode-config` § Add a human checkpoint | "Ask rules that match on a command's content, such as `Bash(git push *)`, fall back to a permission prompt"；"Content-scoped ask rules … are evaluated before the classifier and always force a permission prompt, even in auto mode" | 現行 `Bash(git push:*)` 在 auto mode 一定提示，這是 2026-10-09 U3 實測的來源 |
| `Bash(git push:*)` 的覆蓋範圍 | `/permissions` § Bash rule limits；`/auto-mode-config` | "A push Claude writes another way, such as `git -C <dir> push` or `git -c <key>=<value> push`, doesn't match the rule … For a checkpoint that inspects the full command text, add a PreToolUse hook." | settings 規則只是前綴比對；完整文字檢查本來就靠 hook |
| `autoMode.*` 是否能從 project settings 設 | `/auto-mode-config` § Where the classifier reads configuration | "The classifier doesn't read `autoMode` from project settings in `.claude/settings.json` or `.claude/settings.local.json`." | 不能用 repo 內設定調整分類器；分類器相關只能留在使用者層 |

### 實測狀態

| 項目 | 狀態 | 說明 |
|---|---|---|
| hook allow＋現行 `permissions.ask` → 推 feature branch 是否提示 | **文件確認會提示；實測 NOT TESTED** | 文件三處一致陳述。本 session 無法實測（見上） |
| 移除 ask 規則後，hook allow → 推 feature branch 在 auto mode 是否不提示、分類器是否放行 | **NOT TESTED** | 需要先改 settings，超出本 Phase 權限 |
| 移除 ask 規則後，hook ask → 推 main 在 auto mode 是否仍提示 | **文件確認會；`2.1.296` 已實測（ai-portability U5）；`2.1.304` NOT TESTED** | 升版後應重跑 |
| 從子目錄啟動時無任何閘門 | 既有已知（`2.1.296`） | 不變 |

**使用者實測步驟（不改遠端）**，由 worktree 根目錄啟動 `claude`（auto mode）：

- U-B1（settings 未改）：請 agent 執行 `git push --dry-run origin feat/pr-flow-tiering`。預期：**跳出核准提示**，提示來源是 `permissions.ask`（hook 回 allow，沒有 `ttr-hook:` 字樣）。選 No。
- U-B2（settings 未改）：`git -C . push --dry-run origin feat/pr-flow-tiering`。預期：**不提示、直接執行**（`-C` 不符合 `Bash(git push:*)` 前綴，hook 回 allow）。這一條同時驗證 hook 的 allow 路徑真的生效。
- U-B3（settings 未改）：`git -C . push --dry-run origin HEAD:main`。預期：提示，且理由含 `ttr-hook: git push to main …`。選 No。
- U-B4（套用下方方案後）：重複 U-B1，預期不提示；重複 U-B3，預期仍提示。

### `.claude/settings.json` 修改方案（需使用者在 PR 上核准，agent 不自行改）

**方案 A：移除 `Bash(git push:*)`，hook 成為唯一 push 閘門。**

```json
{
  "permissions": {
    "ask": []
  },
  "hooks": { "…不變…": "" }
}
```

- 優點：最簡單；hook 已涵蓋 `-C`／`env`／`bash -c` 等變體，並以完整命令文字判斷目的端，比前綴規則準確。
- 缺點：失去第二層。hook 不存在的情境（從子目錄啟動、`--bare`、`disableAllHooks`、Claude Code 改版不再辨識 decision JSON）下，推 main 完全不提示。舊制下這些情境至少還有 settings 規則擋住直接寫成 `git push …` 的命令。

**方案 B（建議）：把 ask 規則收窄到目的端看起來是 main 的前綴形式。**

```json
{
  "permissions": {
    "ask": [
      "Bash(git push *main)",
      "Bash(git push *main *)"
    ]
  },
  "hooks": { "…不變…": "" }
}
```

- `*` 可跨空白比對（文件：`Bash(git log * main)` 匹配 `git log --oneline main`）。`Bash(git push *main)` 命中 `git push origin main`、`git push -u origin main`、`git push origin HEAD:main`、`git push origin x:refs/heads/main`；`Bash(git push *main *)` 補 `git push origin main --tags` 這類 main 後面還有參數的寫法。
- 誤殺只會多問一次（例：`git push origin domain`、`git push origin main:feat/x`），hook 仍以完整規則判斷；不會漏放 feature branch 的常見寫法（`feat/x`、`feat/main-fix` 皆不以 `main` 結尾也不含 `main `）。
- 漏網：`git push origin feat/x main` 由 hook 的 R8 接住；沒有 refspec 的 `git push` 由 hook 的 R1 接住。settings 規則在這個方案裡只是 hook 失效時的保底，不追求完整。
- 不能用 `permissions.allow` 替 feature branch 開例外（ask 優先於 allow，文件明示）。

**兩個方案都必須同步改 `scripts/tests/test_claude_settings.py`**：`PUSH_ASK_RULE`、`PUSH_COMMANDS`、`test_push_ask_rule_present`、`test_settings_exact_shape`（目前斷言 `permissions == {"ask": ["Bash(git push:*)"]}`）、`test_no_allow_rule_covers_git_push`。方案 B 下 `PUSH_COMMANDS` 應改為 `("git push origin main", "git push -u origin main", "git push origin HEAD:main")`，並新增一組「不得命中」的 feature branch 命令。

**建議順序**：先由使用者跑 U-B1～U-B3 確認文件結論在 `2.1.304` 成立，再在同一個 PR 內套用方案 B＋更新 `test_claude_settings.py`＋更新 `AGENTS.md` 第 91 行與「第一批規則」表的註記，最後跑 U-B4。

### 分類器相關的附帶觀察

- `/auto-mode-config` 明示 `permissions.ask` 是「human checkpoint」的正規機制，而 hook 是補足前綴比對不到的變體；本 repo 的設計（hook 做完整判斷、settings 做保底）與文件建議方向一致。
- proposal M2 之後要讓 agent 執行 `gh pr create`：文件說 auto mode 預設放行 PR 建立；`gh pr merge` 則被分類器「Merging a pull request no human has approved」規則擋住，這對 Tier 0 的 `gh pr merge --auto` 可能有影響，Phase D 要留意（Tier 0 是在 GitHub Actions 內執行，不經 Claude Code 分類器，應無影響；本機由 agent 執行時才會碰到）。

## B3 Phase C 修正（2026-10-22，Engineer／Fable，依 Plan Critic P1／P2）

### 已實測成立的繞過（P1）

協調者在 scratchpad 的本機 bare repo 實測：

```
git -c remote.origin.push=refs/heads/feat/x:refs/heads/main push origin feat/x
```

輸出 `f79ff12..4e8f2e5  feat/x -> main`，遠端 `main` 被更新。B1 版本的 hook 把它判為 feature push 而 allow，因為 `-c` 在 `GIT_OPT_ARG` 中被直接跳過；而 git 文件明示 refspec 省略 `:<dst>` 時，若 `remote.<repo>.push` 有設定，依該設定決定目的端。`--config-env`、`--git-dir`、`--work-tree`、`--namespace`、`--exec-path` 同樣能換掉 push 讀到的設定或 hook，`-c core.hooksPath=/dev/null` 則可關掉 gitleaks pre-push 掃描。真實 repo 目前沒有設 `remote.origin.push`、`push.default`、`pushInsteadOf`，`core.hooksPath=.githooks`。

### 修正內容（`scripts/claude/_policy.py`）

1. **push 前的 git 全域選項**：`check_git` 追蹤 `reconfigured`。`-C <path>` 與 `GIT_FLAGS`（`--no-pager`、`-P` 等）以外的任何全域選項（`-c`、`--config-env[=]`、`--git-dir[=]`、`--work-tree[=]`、`--namespace[=]`、`--exec-path[=]`、`--super-prefix[=]`）出現在 `push` 前，且 `check_push` 原本會 allow 時，改回 `ASK_PUSH`；deny 仍優先。其他子命令行為不變（`git -c clean.requireForce=false clean -d` 仍是 deny，`git -c core.pager=cat log` 仍 allow）。
2. **寫入會改變 push 行為的持久設定**：新增 `check_git_config`。`--get`／`--get-all`／`--get-regexp`／`--get-urlmatch`／`--list`／`-l`／`--show-origin`／`--show-scope`，或 `get`／`list` 子命令 → allow。`-e`／`--edit`／`edit` → ask（寫入內容無法檢查）。其餘視為寫入：跳過 `--file`／`-f`／`--blob`／`--type`／`--default`／`--comment`／`--value` 的值與所有旗標（`--global`、`--local`、`--system`、`--worktree`、`--add`、`--unset`、`--replace-all` 等），去掉 `set`／`unset`／`rename-section`／`remove-section` 動詞後，任一 positional 以 `CONFIG_GATE_RE`（不分大小寫）比對 `remote.*.push`、`remote.*.mirror`、`push.*`、`core.hookspath`、`url.*.pushinsteadof`、`url.*.insteadof`、`alias.*` 命中，或 key 是變數／替換 → `ASK_CONFIG`（新 rule `git-config-gate`，理由文字獨立於 push-gate）。`git remote add --mirror[=fetch|push]` 也 ask。
3. **未知 push 選項 ask（P2）**：`PUSH_FLAGS` 允許清單（`--verbose`、`--quiet`、`--dry-run`、`--set-upstream`、`--thin`／`--no-thin`、`--porcelain`、`--progress`／`--no-progress`、`--atomic`／`--no-atomic`、`--signed`／`--no-signed`、`--no-recurse-submodules`、`--ipv4`／`--ipv6`、`--verify`、`--no-force-with-lease`、`--no-force-if-includes`、`--`），帶值的 `--signed=*`、`--recurse-submodules=*`、`--push-option=*`、`--repo=*`、`--receive-pack=*`、`--exec=*`（值不得為空），短旗標字元 `v q n u 4 6`（`o` 吃值，`f`／`d` deny）。清單外的長選項、短旗標群組內的未知字元、單獨的 `-` → ask。既有 deny 與 `--no-verify` ask 不變；`--recurse-submodules` 不帶 `=` 視為未知（保守）。
4. **直接寫 `.git/config`（第 4 項調查）**：調查結果：B1 版本的 file guard 只比對 `.env`，`Write`／`Edit`／`NotebookEdit` 寫 `.git/config` 會 allow；bash guard 的 `check_env_file` 同樣不看 `.git/config`，`echo … >> .git/config`、`tee`、`cp`、`sed -i` 都 allow。**攔得住，且不需開檔**：新增 `GIT_CONFIG_RE`（純字串比對，`test_policy_never_opens_files` 通過），涵蓋 `.git/config`、`.git/config.worktree`、`.git/worktrees/<name>/config[.worktree]`、`.git/modules/<path>/config`；`file_decision` 對 `WRITE_TOOLS` 命中時回 `ASK_CONFIG`（`Read`／`Grep` 照常 allow）；bash guard 新增 `check_git_config_file`，對 `WRITE_REDIRECTS` 指向這些路徑，或 `WRITE_VERBS`／`sed -i`／`awk inplace` 的參數含這些路徑時回 `ASK_CONFIG`。file guard 的 launcher 輸出協定對 ask 同樣有效（`test_git_config_ask_goes_through_launcher_protocol`）。未涵蓋：`$GIT_DIR/config` 這類變數路徑、直譯器程式碼字串內的路徑（`python3 -c "open('.git/config','a')"`），與既有 `.env` 規則的字面路徑限制相同，不另列。
5. `Decision.message()` 改以 `ASK_REASONS[rule]` 取理由；`ASK_REASON`（push-gate）常數與 `ask_payload()` 預設值不變，`test_launcher.py` 無需改。

### 新增測試

- `test_bash_guard.py`：`PUSH_TABLE` 新列 `R13-global-opts`（ask 12、allow 4，含 P1 命令、`-c core.hooksPath=/dev/null`、`--config-env=…`、`--git-dir`、`--work-tree`、`--namespace`、`--exec-path`、`bash -c` 包裝；allow 含 `git -C . push origin feat/x`、`--no-pager`、`-P`）與 `R14-unknown-opts`（ask 6、allow 10，含 `--frobnicate`、`-x`、`-ux`、bare `--recurse-submodules`、`--signed=`；allow 覆蓋整張允許清單）；新 `CONFIG_TABLE` 與 `test_git_config_table[<kind>:<command>]`（ask 45、allow 32，含 `git config remote.origin.push …`、`--get remote.origin.push` allow、`user.name x` allow、shell 重導寫 `.git/config` 各形式）；`test_config_ask_payload_is_valid_output`；`DENY` 加 5 條「deny 仍優先於 global-option／unknown-option ask」；`test_push_table_covers_every_row_both_ways` 納入 R13／R14；`test_policy_never_opens_files` 掃描 `CONFIG_ASK`／`CONFIG_ALLOW`。
- `test_file_guard.py`：新 `ASK` 清單與 `test_git_config_write_asks`（Write／Edit／NotebookEdit 寫 `.git/config`、`.git/config.worktree`、`.git/worktrees/*/config[.worktree]`、`.git/modules/*/config`、相對路徑 `.git/config`，共 8 條）；`ALLOW` 加 7 條（Read／Grep `.git/config`、Write `.git/info/exclude`、`.github/config`、`web/.gitconfig`、`.git/config.bak`、`scraper/config`）；`test_git_config_ask_goes_through_launcher_protocol`。

### 改前／改後測試數字

| 階段 | 命令 | 結果 |
|---|---|---|
| B1 完成時 | `python3 -m pytest scripts/claude/tests scripts/tests -q` | 615 passed |
| 加入 Phase C 測試、程式未改 | `python3 -m pytest scripts/claude/tests/test_bash_guard.py scripts/claude/tests/test_file_guard.py -q` | **72 failed**, 547 passed：R13 ask 12、R14 ask 5（`--push-option origin feat/x` 因無 refspec 本來就 ask）、`test_git_config_table` ask 45、file guard 9、`test_config_ask_payload_is_valid_output` 1；P1 命令確認在舊碼上為 allow |
| 改後 | `python3 -m pytest scripts/claude/tests scripts/tests -q` | **747 passed**；`python3 scripts/sync_ai_adapters.py --check` 通過 |
| launcher 端到端 | `run_hook.sh bash` 餵 stdin | P1 命令 → ask JSON；`git -C . push origin feat/x` → exit 0 無輸出；`git push --frobnicate origin feat/x` → ask；`git config remote.origin.push …` → ask（git-config-gate）；`git config --get remote.origin.push` → allow |

### 刻意沒做的部分

- `git remote set-url`／`set-url --push`、`git config remote.<name>.url`／`pushurl`：改的是 remote 位置，不是目的端 ref 名稱；決策表「remote 不影響目的端」的原則保留。auto mode 分類器本身會擋 `git remote set-url`。
- `git config --remove-section remote.origin`／`--rename-section`：刪除或改名只會讓 push 設定消失，不會把 feature push 導向 main。
- 不分析 `-c` 的 key 做白名單（例如放行 `-c core.pager=cat push …`）：協調者要求一律 ask，且 push 前很少需要 `-c`。
- 未動 `proposal.md`、`tasks.md`、`critique.md`。

## B4 使用者實測 U-B1～U-B3（2026-10-22，Claude Code 2.1.304）

由使用者在 VS Code 外的 terminal，從 worktree 根目錄以 `claude --permission-mode auto` 啟動，settings 未改。

| 步驟 | 命令 | 結果 | 解讀 |
|---|---|---|---|
| U-B1 | `git push --dry-run origin feat/pr-flow-tiering` | 兩次都跳出核准提示，使用者選 No | hook 對此命令回 allow（launcher 端到端已確認），提示來自 `permissions.ask` 的 `Bash(git push:*)` |
| U-B2 | `git -C . push --dry-run origin feat/pr-flow-tiering` | 兩次都不提示，dry-run 執行，gitleaks 掃 10 個 commit 無洩漏，輸出 `* [new branch] feat/pr-flow-tiering -> feat/pr-flow-tiering`，未實際推送 | 舊版 hook 對所有 push 都 ask，因此這一條證明 session 載入的是 worktree 的新版 hook，且 hook allow 確實生效 |
| U-B3 | `git -C . push --dry-run origin HEAD:main` | 跳出核准提示，使用者選 No | 命令不以 `git push` 開頭，settings 規則比對不到，提示只可能來自 hook 的 ask |

結論：官方文件「ask 規則不受 hook allow 影響」在 2.1.304 成立。採用方案 B，並擴充為 hook 失效時的保底：

```json
"ask": [
  "Bash(git push)",
  "Bash(git push origin)",
  "Bash(git push *main)",
  "Bash(git push *main *)",
  "Bash(git push *HEAD)",
  "Bash(git push *HEAD *)"
]
```

擴充的理由：`git push`、`git push origin`、`git push -u origin HEAD` 的目的端取決於當前 branch，可能是 main。hook 本來就對它們 ask，所以 settings 多比對這些形式不會增加平常的提示次數，只在 hook 不存在時補上保底。推 feature branch 的常見寫法（`feat/x`、`HEAD:feat/x`、`main:feat/x`、`feat/main-fix`）都不會命中。

**套用方式**：協調者以 agent 身分修改 `.claude/settings.json` 時，auto mode 分類器以 `[Self-Modification]` 拒絕，連讀取該檔也被拒。這符合「agent 不得自行修改權限設定」的設計，因此 settings、`scripts/tests/test_claude_settings.py` 與 `AGENTS.md` 的對應說明做成 patch，由使用者檢查後套用並 commit。套用後跑 U-B4：重複 U-B1 應不再提示，重複 U-B3 應仍提示。

## B5 使用者實測 U-B4（2026-10-22，套用 commit `d92e1dfc` 之後）

同樣在 worktree 根目錄以 `claude --permission-mode auto` 開新 session 測試。

| 命令 | 結果 |
|---|---|
| `git push --dry-run origin feat/pr-flow-tiering` | 不提示，顯示 `Allowed by auto mode classifier`，gitleaks 掃 12 個 commit 後執行 dry-run |
| `git -C . push --dry-run origin HEAD:main` | 提示，文字為 `ttr-hook: git push to main, or to a destination the hook cannot determine, requires explicit user approval [push-gate]`，使用者選 No |
| `git push --dry-run origin HEAD:main` | 預期提示；settings 的 `Bash(git push *main)` 與 hook 都會要求核准 |

結論：推 feature branch 不再需要人工核准，推 main 仍由 hook 與 settings 兩層要求核准。
