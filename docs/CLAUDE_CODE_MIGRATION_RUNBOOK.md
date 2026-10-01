---
title: Claude Code migration and operations runbook
description: Step-by-step runbook for migrating Tokyo Taiwan Radar from Copilot Enterprise to Claude Code
ms.date: 2026-10-01
ms.topic: how-to
---

## 執行目標

> 上一輪結論：下一個正式動作，是在乾淨的
> `feat/ai-portability` worktree 規劃三項 hardening：
> **移除 legacy state path、把角色權限轉成 Claude 工具限制、建立危險操作 hooks**。
> 上一輪只做了唯讀稽核，沒有修改任何檔案或秘密。

本 runbook 從這個結論開始，先完成三項 hardening，再建立不依賴
Copilot Enterprise 的日常操作流程。

> [!IMPORTANT]
> 這份文件是遷移操作指南，不取代 repository 內的權威規則。
> 專案規則仍以
> [AGENTS.md](../AGENTS.md)、
> [.github/copilot-instructions.md](../.github/copilot-instructions.md)、
> [.github/instructions/](../.github/instructions/)
> 與 [.github/skills/](../.github/skills/) 為準。

> [!CAUTION]
> 不要一次授權 Claude 完成規劃、實作、push、production DB write
> 與 worktree cleanup。每一個高風險邊界都必須停下來取得人工核准。

## 新 Claude Code session 的起點

### 步驟 1：進入指定 worktree

在新的 Terminal 執行：

```bash
WT="/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree"
cd "$WT"
git fetch origin main
git status --short
git branch --show-current
git rev-list --count origin/main..HEAD
git rev-list --count HEAD..origin/main
```

確認以下條件：

* branch 是 `feat/ai-portability`
* `git status --short` 沒有輸出
* ahead 是 `0`
* 若 behind 大於 `0`，只有在工作樹乾淨時才執行：

```bash
git rebase origin/main
```

若工作樹有未提交內容、ahead 大於 `0`，或正在 rebase／merge，停止操作並先盤點。
不要 stash、reset、clean 或強制覆蓋。

### 步驟 2：以 Claude Pro 啟動 Architect

Phase 0 不需要 Python virtualenv。不要先執行 `source .venv/bin/activate`。

```bash
env -u ANTHROPIC_API_KEY claude --ide \
  --agent architect \
  --permission-mode plan \
  --model sonnet \
  --name "ttr-ai-portability-plan"
```

`env -u ANTHROPIC_API_KEY` 只會對這個 Claude process 移除 API key，
讓 Claude Code 使用已登入的 Claude Pro。它不會修改父 shell，也不會影響
scraper 從 `scraper/.env` 載入 runtime secrets。

如果 Claude 仍顯示 `Detected a custom API key in your environment`，選擇
`No (recommended)`。

### 步驟 3：確認規則已載入

進入 Claude Code 後執行：

```text
/context
```

確認 Memory files 至少包含 repository root 的 `CLAUDE.md` 或 `AGENTS.md`。
若沒有載入，先停止，不要要求 Claude 修改檔案。

### 步驟 4：貼上第一個提示

```text
請完整讀取 docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md、AGENTS.md、
.github/instructions/git.instructions.md，以及 Architect agent 和 skill。

本次 campaign 是 ai-portability，已明確指定 worktree：
/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree
branch：feat/ai-portability。

先保持 plan mode，不要修改檔案。請依 runbook 的「六、目前最值得處理的三個缺口」
盤點並產出 execution-ready 計畫，順序固定為：
1. 移除 legacy state path
2. 把角色權限轉成 Claude 工具限制
3. 建立危險操作 hooks

計畫必須列出：
- 每階段所有受影響檔案
- canonical source 與 generated output 的界線
- backward compatibility 與 negative search
- 測試、adapter sync、hook simulation、rollback
- 明確的人工核准點
- in scope 與 out of scope

不得 push、不得寫 production DB、不得旋轉 secrets、不得清理其他 worktree。
```

### 步驟 5：Architect 的第一份交付物

Architect 應先交付以下內容，不能直接開始實作：

1. 三個 hardening phase 的檔案級計畫。
2. 既有 Copilot、Claude、Codex adapter 的 surface matrix。
3. 權限角色矩陣與 hook command matrix。
4. 每個 phase 的測試、negative test 與 rollback。
5. Implementation Phase 0 建立
   `docs/specs/active/ai-portability/{proposal,tasks}.md`，
   並以本 runbook 作為操作基準。

## 一、哪些東西不會因 Copilot Enterprise 被撤銷而消失

Copilot Enterprise license 只控制 Copilot 產品能力，不等於 GitHub repository、
GitHub Actions、Vercel 或其他服務的所有權。

### 可能受影響的能力

* VS Code Copilot Chat 與 Copilot SDK 存取
* Copilot Enterprise quota 與企業模型政策
* Copilot 專屬 handoff UI
* 由 Copilot host 注入的工具、session state 與互動介面

### 原則上不受影響的資產

* Git repository、branches、commits 與 worktrees
* GitHub Actions 及 workflow 內建的 `secrets.GITHUB_TOKEN`
* 個人 GitHub SSH key、fine-grained PAT 與 GitHub CLI
* Vercel Git integration 與既有 production project
* Supabase project、database schema 與 platform secrets
* OpenAI、DeepL、LINE、Anthropic 等 runtime API
* repository 內的 agents、skills、prompts、instructions 與 adapter script

### 撤銷前的所有權驗證

- [ ] GitHub 帳號、2FA、recovery email 由個人控制
- [ ] repository 至少有一個不依賴企業 SSO 的 owner／admin
- [ ] Vercel team、project 與 production domain 有個人 owner／admin
- [ ] Supabase project 有個人 owner／admin
- [ ] DNS registrar 與網域續費帳號有個人 recovery path
- [ ] GitHub Actions secrets 不依賴即將停用的企業帳號
- [ ] 本機 `GITHUB_TOKEN` 若由公司帳號簽發，已改成個人 fine-grained PAT
- [ ] 各服務的 recovery codes 已存入 password manager

### GitHub 憑證邊界

本機 PAT 與 GitHub Actions 的 `secrets.GITHUB_TOKEN` 是不同憑證：

* 本機 PAT 用於本機 API 操作，例如建立 GitHub Issue
* Actions 的 `secrets.GITHUB_TOKEN` 由 GitHub 在每次 workflow run 動態提供
* Copilot license 被撤銷，不會自動刪除 Actions token 機制

依
[GITHUB_TOKEN_SYNC_CHECKLIST.md](GITHUB_TOKEN_SYNC_CHECKLIST.md)
驗證本機 PAT 的 owner、expiry 與最小權限。

## 二、保留目前的「單一權威來源」架構

不要為 Claude 複製一套獨立且會漂移的規則。現行架構應保留：

```text
.github/agents + .github/skills + .github/prompts + .github/instructions
                                  |
                                  v
                    scripts/sync_ai_adapters.py
                         |               |
                         v               v
                     .claude/         .agents/
                    Claude Code         Codex
```

### Canonical source

以下路徑是人工維護的權威來源：

* [`.github/agents/`](../.github/agents/)
* [`.github/skills/`](../.github/skills/)
* [`.github/prompts/`](../.github/prompts/)
* [`.github/instructions/`](../.github/instructions/)
* [AGENTS.md](../AGENTS.md)

### Generated output

以下路徑由 adapter 產生，不直接編輯 generated files：

* [`.claude/agents/`](../.claude/agents/)
* [`.claude/commands/`](../.claude/commands/)
* [`.claude/skills/`](../.claude/skills/)
* [`.agents/skills/`](../.agents/skills/)

### 修改規則

1. 先修改 canonical source。
2. 執行 adapter generation。
3. 檢查 generated diff。
4. 執行 drift check。
5. canonical source 與 generated output 放在同一個 atomic commit。

```bash
python3 scripts/sync_ai_adapters.py
python3 scripts/sync_ai_adapters.py --check
```

### 不應在遷移期間進行的重構

* 不因 Copilot license 結束而刪除 `.github/`
* 不把全部 `.github/agents` 手動複製進 `.claude/agents`
* 不在 agent、skill、prompt frontmatter 寫死 `model:`
* 不把 Claude 使用者層設定提交到 repository
* 不同時重命名所有 Copilot 歷史路徑與所有 agent 名稱
* 不為了取代 GitHub CLI 而先導入 GitHub MCP

## 六、目前最值得處理的三個缺口

三個 phase 必須依序完成。每個 phase 都要獨立 commit、獨立驗證；
前一階段未通過時，不進入下一階段。

### Phase A：移除 legacy state path

#### 目標

移除 active guidance 對 Copilot-only state 的依賴，例如：

* `/memories/session/plan.md`
* `/memories/session/plan-critique.md`
* 新增 durable state 到 `.copilot-tracking/`

新的持久化契約：

| 使用情境                         | Canonical location                         |
|----------------------------------|--------------------------------------------|
| 大型、跨 session、跨多檔 campaign | `docs/specs/active/<slug>/`                 |
| 小型、本機、不可提交的臨時筆記   | `~/.ai-notes/ttr/`                          |
| Agent 對話中的暫時推理           | Claude session，不能作唯一權威狀態         |
| 歷史 Copilot scratch             | grandfather，只讀或逐步退休，不新增 durable state |

#### Architect 盤點要求

1. 對 canonical agents、skills、prompts、instructions 與 linked normative history
   搜尋 exact path 和語意等價描述。
2. 每個命中分類為 active guidance、generated output 或 historical fact。
3. active guidance 改用新的 state contract。
4. historical fact 保留時，在相鄰位置標示 historical／superseded。
5. generated output 只透過 adapter 更新。
6. 定義舊 session 或舊 spec 的 backward compatibility。

#### 驗收

```bash
rg -n \
  "/memories/session|\\.copilot-tracking" \
  AGENTS.md .github .claude .agents docs
```

驗收結果必須能解釋每一個剩餘命中：

* active guidance 不再要求寫入 Copilot-only state
* generated wrapper 與 canonical source 一致
* historical 命中清楚標示為非規範性內容
* `python3 scripts/sync_ai_adapters.py --check` 通過

#### Rollback

若新的 state contract 讓現有 agent 無法 handoff，回退本 phase 的 atomic commit。
不要用兼容 fallback 靜默寫入兩個 state location。

### Phase B：把角色權限轉成 Claude 工具限制

#### 目標

把目前只存在於自然語言的「唯讀、可執行、可編輯、可部署」角色邊界，
投影到 Claude Code 的 agent tools 與 permission policy。

#### 建議角色矩陣

| 角色類型              | 讀取／搜尋 | 執行測試 | 修改檔案 | Git mutation | Push／部署 |
|-----------------------|-------------|----------|----------|--------------|------------|
| Architect／Plan Critic | 允許        | 僅唯讀診斷 | 禁止     | 禁止         | 禁止       |
| Reviewer              | 允許        | 允許唯讀檢查 | 禁止   | 禁止         | 禁止       |
| Tester                | 允許        | 允許       | 預設禁止 | 禁止         | 禁止       |
| Engineer              | 允許        | 允許       | 允許     | worktree 內受控 | 禁止       |
| Researcher            | 允許        | 有限       | 只寫研究輸出 | 禁止      | 禁止       |
| V-M-D                 | 允許        | 允許       | 有限     | 允許且需 gate | 明確核准後 |
| Campaign Closer       | 允許        | 允許診斷   | 有限     | 只在 STOP gate 通過後 | 禁止 |

#### 設計約束

1. 權限 metadata 的 canonical source 必須位於 agent source 或單一 adapter mapping。
2. 不直接編輯 `.claude/agents/*.md`。
3. Copilot tool 名稱與 Claude tool 名稱需要明確 mapping。
4. 無法由 agent frontmatter 表達的 command-level 限制交給 hooks。
5. Agent tools 是 least privilege，不是代替人工核准。
6. 不在 source frontmatter 寫死模型。
7. 既有 Codex output 不得因 Claude mapping 而退化。

#### 驗收

* Architect agent 無法使用 Edit／Write 類工具。
* Tester 可執行測試，但不能修改產品程式碼。
* Engineer 可修改 worktree，但不能自行 push。
* V-M-D 在 push 前仍要求明確人工核准。
* 16 個 Claude agent wrappers 可正常載入。
* adapter generation idempotent。
* pinned-model negative check 仍通過。

```bash
python3 scripts/sync_ai_adapters.py
python3 scripts/sync_ai_adapters.py --check
claude doctor
```

#### Negative tests

在 disposable fixture 或無副作用測試中確認：

* Architect 嘗試建立檔案時被拒絕。
* Tester 嘗試編輯 source file 時被拒絕。
* Engineer 嘗試 push 時仍需人工批准。
* generated wrapper 被手動修改後，`--check` 會偵測 drift。

### Phase C：建立危險操作 hooks

#### 目標

使用 Claude Code project settings 與 hooks，將高風險行為從文字提醒提升為
可測試的 command gate。

建議使用：

* shared project policy：`.claude/settings.json`
* hook implementation：`scripts/claude/` 下的可測試程式
* local personal overrides：`.claude/settings.local.json`，保持 gitignored

#### 第一批需要阻擋的操作

| 類型             | 預設處理 |
|------------------|----------|
| `git push --force`／`--force-with-lease` | 阻擋 |
| `git reset --hard`                       | 阻擋 |
| `git clean -fd`／`-fdx`                  | 阻擋 |
| `git branch -D`                          | 阻擋 |
| `git worktree remove --force`            | 阻擋 |
| `git worktree add -f`                    | 阻擋 |
| 直接輸出 `.env` 全文                     | 阻擋 |
| `env`／`printenv` 洩漏敏感變數           | 阻擋或遮罩 |
| 未核准的 production DB mutation          | 阻擋並要求人工 handoff |
| shell 動態組裝或混淆危險命令             | 阻擋 |

#### 必須允許的正常操作

* `git status --short`
* `git diff --check`
* `git log --oneline`
* `git fetch origin main`
* clean worktree 上的 `git rebase origin/main`
* targeted tests、lint、type-check 與 build
* masked secret presence check
* `python3 scripts/sync_ai_adapters.py --check`

#### Hook 設計要求

1. 對 tool input 做結構化解析，不以單一寬鬆 substring 取代 parser。
2. Fail closed 時回傳可理解的拒絕原因與安全替代命令。
3. 測試 fixtures 不執行真正的 destructive command。
4. hooks 自身不得讀取或記錄 secret values。
5. 不建立隱藏 bypass flag。
6. production write approval 不能用模糊的「繼續」推定。
7. `--dangerously-skip-permissions` 仍列為禁止操作。

#### 驗收

* 每個阻擋案例都有 unit test。
* 每個允許案例都有 positive test，避免 hook 過度阻擋。
* hook rejection 不會輸出 secret 或 command 中的 secret value。
* `claude doctor` 通過。
* 新 Claude session 能載入 project settings。
* Architect、Engineer、Tester、V-M-D 各做一次 smoke test。

#### Rollback

hook 發生 false positive 時，先回退該 hook commit 或停用該單一 hook。
不要以 `--dangerously-skip-permissions` 繞過整套安全邊界。

### 三個 phase 的完成定義

- [ ] Phase A legacy active guidance negative search 通過
- [ ] Phase B agent permission matrix 已投影並有 negative tests
- [ ] Phase C destructive command hooks 有 positive／negative tests
- [ ] adapter generation 與 `--check` 均通過
- [ ] 所有修改都在 `feat/ai-portability` worktree
- [ ] 沒有 production DB write
- [ ] 沒有 secrets rotation 或 secret value diff
- [ ] 沒有清理其他 worktree
- [ ] V-M-D 前取得明確 push 核准
- [ ] push 後驗證 exact SHA

### 本 campaign 不包含的工作

* 不立即刪除所有 Copilot 文件或歷史名稱
* 不改網站或 scraper runtime 使用的 LLM
* 不輪替未洩漏的 secrets
* 不安裝 GitHub MCP 作為前置條件
* 不安裝 Vercel CLI 作為前置條件
* 不清理 19 個既有 worktree
* 不處理其他 feature branch 的 dirty files 或未合併 commits

## 七、切換前的最小清單

### 帳號與 ownership

- [ ] Claude Pro 使用個人帳號登入
- [ ] GitHub 使用個人 SSH key 與個人可控帳號
- [ ] `gh auth status` 成功
- [ ] Vercel、Supabase、DNS 都有個人 owner／admin
- [ ] 2FA 與 recovery codes 已備份

### Secrets

- [ ] `scraper/.env` 被 Git 忽略且未追蹤
- [ ] secrets 存在 password manager 的加密備份
- [ ] 沒有把 plaintext `.env` 複製到 repository 或 session artifact
- [ ] `ANTHROPIC_API_KEY` 不再從 `~/.zshrc` 全域 export，或固定以
      `env -u ANTHROPIC_API_KEY claude ...` 啟動
- [ ] Claude Code 使用 `claude.ai` OAuth，而不是 scraper runtime API key
- [ ] 完整 key 若曾公開顯示，已立即撤銷並輪替

安全檢查只能輸出 presence、length 或 prefix validity，不能輸出 secret value：

```bash
git check-ignore -v scraper/.env
git ls-files --error-unmatch scraper/.env >/dev/null 2>&1 \
  && echo "ERROR: tracked" \
  || echo "OK: not tracked"
```

### Repository portability

- [ ] root `CLAUDE.md` 能載入 `AGENTS.md`
- [ ] `scraper/`、`web/`、`supabase/` 的 nested instructions 能按路徑載入
- [ ] `.claude/agents`、`.claude/commands`、`.claude/skills` 存在
- [ ] `python3 scripts/sync_ai_adapters.py --check` 通過
- [ ] canonical sources 沒有 pinned `model:`
- [ ] 新 session 的 `/context` 顯示正確 memory files

### Dry-run migration

- [ ] 在 `feat/ai-portability` 完成 Architect plan
- [ ] Engineer 只執行已核准 phase
- [ ] Tester 使用相同 registered worktree 驗證
- [ ] V-M-D dry-run 停在 push 核准前
- [ ] 完成至少兩次穩定 Claude cycle 後才把 Copilot 降為備援

### Worktree backlog

既有 worktree cleanup 是獨立 campaign。先盤點，不在 ai-portability 中順手清理。

優先處理具有以下任一狀態的 worktree：

* dirty files
* ahead commits
* 大量 behind
* owner session 不明
* ignored artifacts 未備份

每個候選都交給 Close Campaign & Retire Worktree agent，禁止批次 force remove。

## 五、模型與費用策略

### Claude Code 與 runtime API 分離

| 用途                         | 身分／計費來源                    |
|------------------------------|-----------------------------------|
| Claude Code 日常開發         | `claude.ai` Pro OAuth             |
| scraper 或 web runtime LLM   | 專案 `.env`／platform secrets     |
| GitHub Actions               | workflow secrets 與 Actions token |
| 本機 GitHub API 操作         | 個人 SSH／PAT／GitHub CLI         |

不要把 scraper 的 `ANTHROPIC_API_KEY` 當成 Claude Code 登入憑證。
不要為了啟動 Claude Code，把 runtime key export 到全域 shell。

### 模型分工

| 工作類型                             | 建議模型 |
|--------------------------------------|----------|
| 一般規劃、實作、測試、文件           | `sonnet` |
| 高風險 migration、重大架構與複雜 review | `opus`   |
| 重複性唯讀探索                       | subagent 或較低成本模型，視方案可用性 |

使用 `sonnet`／`opus` alias。不要把完整模型名稱寫入 repository frontmatter。

### 成本控制

* Subagents 也會消耗同一份 Claude usage quota。
* 單一連續 trace 由主 agent 完成，不為每個小查詢建立 subagent。
* 大量獨立 research、build log 或 code search 才委派。
* Phase 0 使用 plan mode，避免規劃時意外進入高成本實作循環。
* API automation 使用 `--max-budget-usd`，互動式 Pro session 則以 quota 監控為主。
* 模型切換由 session 啟動參數或 `/model` 完成，不提交個人偏好。

### Privacy 檢查

Claude Code 帳號與 runtime API 可能有不同的 retention、telemetry 與組織政策。
切換前確認個人 Pro 的 data/privacy 設定。若未來處理第三方私有程式碼，
另行評估 Team／Enterprise 或具合適 retention 條款的 API。

## 三、建議的新日常操作流程

### Phase 0：治理與規劃

在主工作樹或指定 governance worktree 盤點，但不實作功能。

```bash
cd "/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar"
git fetch origin main
git status --short
git worktree list --porcelain

env -u ANTHROPIC_API_KEY claude --ide \
  --agent architect \
  --permission-mode plan \
  --model sonnet \
  --name "ttr-<slug>-plan"
```

Architect 的輸出必須包含：

* scope 與 non-goals
* affected files
* DB schema change 判定
* worktree 與 branch
* measurable acceptance
* rollback
* production write 與 push 核准點

### Phase 1：確認 worktree

依
[git.instructions.md](../.github/instructions/git.instructions.md)
確認或建立 worktree。

```bash
git worktree list --porcelain
```

規則：

* 一個大型 campaign 對應一個 dedicated worktree
* 主工作樹維持 governance-only
* worktree dirty 時不 rebase、不 stash
* 不使用 `git worktree add -f`
* 不使用 `git worktree remove --force`
* 不使用 Claude `--worktree` 取代 repository 的 worktree 契約

### Phase 2：實作

```bash
cd "<confirmed-worktree>"
git status --short
git fetch origin main

env -u ANTHROPIC_API_KEY claude --ide \
  --agent engineer \
  --permission-mode manual \
  --model sonnet \
  --name "ttr-<slug>-impl"
```

前一至兩週保持 `manual`。熟悉權限提示後，可在隔離 worktree 評估
`acceptEdits`，但 push、production DB、secret rotation 與 cleanup 仍保持 manual。

Engineer 完成時回報：

* 修改檔案
* 測試命令與結果
* 未解決風險
* git status
* commit 與 push 狀態

### Phase 3：獨立測試

使用新的 session，並指向同一 registered worktree：

```bash
cd "<confirmed-worktree>"

env -u ANTHROPIC_API_KEY claude --ide \
  --agent tester \
  --permission-mode manual \
  --model sonnet \
  --name "ttr-<slug>-test"
```

先執行 targeted validation。只有 targeted 結果要求時，才升級到完整 suite。
Tester 不修改產品程式碼；失敗項交回 Engineer。

### Phase 4：同步教訓與 adapters

只有出現可泛化的新教訓時才更新 history、skill 或 agent：

```bash
env -u ANTHROPIC_API_KEY claude \
  --agent update-history-skill-agent \
  --permission-mode manual \
  --model sonnet
```

修改 agent、skill 或 prompt 後：

```bash
python3 scripts/sync_ai_adapters.py
python3 scripts/sync_ai_adapters.py --check
```

小 typo、純 CSS 或無泛化價值的修改不寫入 history。

### Phase 5：Validate、Merge、Deploy

```bash
cd "<confirmed-worktree>"

env -u ANTHROPIC_API_KEY claude --ide \
  --agent validate-merge-deploy \
  --permission-mode manual \
  --model sonnet \
  --name "ttr-<slug>-vmd"
```

固定 gate：

1. 檢查 dirty、ahead、behind 與衝突。
2. 執行相關 tests、build、lint 與 adapter check。
3. 顯示將推送的 commits 與 target。
4. 停下來取得明確 push 核准。
5. 只做 linear fast-forward push。
6. 驗證 pushed SHA 等於 GitHub `main`。
7. 驗證 production deployment 綁定 exact SHA。
8. 執行 production custom-domain smoke test。

GitHub CLI 已足以支援目前流程。GitHub MCP 與 Vercel CLI 不是遷移前置條件。

### Phase 6：結案與 worktree 回收

```bash
env -u ANTHROPIC_API_KEY claude \
  --agent close-campaign-retire-worktree \
  --permission-mode manual \
  --model sonnet \
  --name "ttr-<slug>-close"
```

交接內容：

* registered worktree path
* campaign base SHA
* pushed HEAD SHA
* 參與的 session IDs
* ignored artifact inventory
* close-out record path

只有在 clean、無 unpushed commits、無進行中的 git operation、close-out record
已在 `origin/main`，而且 ignored artifacts 已備份時，才可移除 worktree。

### Session resume 規則

`claude -c` 或 `claude --resume` 只用於：

* 同一 campaign
* 同一 registered worktree
* 同一階段或明確延續的工作

切換 branch、worktree 或 campaign 後，開新 session 並使用 handoff contract。

### 禁止的啟動模式

* 不使用 `--bare`，因為它停用 `CLAUDE.md` 自動發現
* 不以 `--safe-mode` 作日常模式，因為它停用 agents、skills 與 customizations
* 不使用 `--dangerously-skip-permissions`
* 不用 Claude `--worktree` 繞過 repository worktree 規則

## 四、每次 agent handoff 使用固定契約

不要依賴上一個 chat 的隱含上下文。每次交接建立一個新 prompt，至少包含：

```text
Campaign:
Objective:
Registered worktree:
Branch:
Campaign base SHA:
Current HEAD SHA:
Spec or runbook:
Completed work:
Remaining work:
Allowed paths:
Out of scope:
Acceptance commands:
Production writes:
Push authorization:
Known residual risks:
Participating session IDs:
```

### 欄位規則

* `Registered worktree` 使用 `git worktree list --porcelain` 顯示的精確路徑。
* `Campaign base SHA` 是開始 campaign 時的 `origin/main` tip。
* `Current HEAD SHA` 每次 handoff 都重新取得。
* `Allowed paths` 必須是明確路徑，不寫「相關檔案」。
* `Acceptance commands` 必須可執行且能驗證真正需求。
* `Production writes` 預設為 forbidden。
* `Push authorization` 預設為 forbidden until explicit approval。
* 未驗證項目標示 `NOT TESTED`，不能改寫成 PASS。

### ai-portability 範例

```text
Campaign: ai-portability
Objective: Complete the next approved hardening phase only
Registered worktree: /Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree
Branch: feat/ai-portability
Campaign base SHA: <record at campaign start>
Current HEAD SHA: <git rev-parse HEAD>
Spec or runbook: docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md
Completed work: <phase and evidence>
Remaining work: <next unchecked phase>
Allowed paths:
  - CLAUDE.md
  - AGENTS.md
  - .github/agents/
  - .github/skills/
  - .github/prompts/
  - .github/instructions/
  - scripts/sync_ai_adapters.py
  - .claude/
  - .agents/
  - scripts/claude/
  - docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md
  - docs/specs/active/ai-portability/
Out of scope:
  - production DB writes
  - secret rotation
  - unrelated worktree cleanup
Acceptance commands:
  - python3 scripts/sync_ai_adapters.py --check
  - <targeted tests for this phase>
Production writes: forbidden
Push authorization: forbidden until explicit approval
Known residual risks: <list or none>
Participating session IDs: <ids>
```

### Handoff 品質門檻

- [ ] 接收 agent 能指出正確 worktree 與 branch
- [ ] 接收 agent 不需要猜測上一個 session 做了什麼
- [ ] 所有 completed claims 都附命令或 diff 證據
- [ ] 未完成項目與 residual risks 明確列出
- [ ] push、deployment 與 production write 狀態不含糊
- [ ] handoff 不包含 secret values

## 最終切換判定

當以下條件全部成立，Copilot Enterprise 可以降為備援：

- [ ] 三項 hardening 已合併並通過驗證
- [ ] 兩個完整 Claude campaign 已從 plan 走到 close-out
- [ ] adapters 沒有 drift
- [ ] Architect、Tester 的唯讀邊界已由工具限制驗證
- [ ] hooks 能阻擋 destructive commands 且不阻擋正常流程
- [ ] GitHub、Vercel、Supabase、DNS ownership 已確認
- [ ] Claude Pro 與 runtime API 計費已分離
- [ ] 新 session 能只靠 repository 文件與 handoff contract 繼續工作

完成切換後仍保留 canonical `.github` sources。未來若更換 Claude、Codex
或其他 host，只新增 adapter，不再複製一套規則。
