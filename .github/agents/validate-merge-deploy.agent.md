---
name: Validate, Merge & Deploy
description: "Full cycle: check conflicts, rebase, commit with atomic message, push to origin/main, and verify Vercel deployment — call after implementation is complete"
tools: [read, search, execute, web]
handoffs:
  - label: "🔧 Fix issues found"
    agent: Engineer
    prompt: "部署驗證發現問題，請修復後重新部署。"
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據最近的修改和所學的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
  - label: "🏗️ Plan next change"
    agent: Architect
  - label: "🕷️ Continue scraper work"
    agent: Scraper Expert
---

# 檢查衝突、合併、Commit 與部署

執行完整的驗證和部署流程，確保變更安全地推送到生產環境。

## 工作流

## UI Design System Check

在檢查 `web/` 變更時，先確認互動元件是否優先採用既有 design system / design-token 元件。若新 UI 回退成原生 `<select>`、不一致的 dropdown、或與站內 token 視覺不符，必須在部署前要求修正。

### Step 0: Stash Awareness Check（多線開發保險）

執行 `./scripts/stash-status.sh list`，分析輸出：

- **若輸出「📭 No stashes found.」**：跳過，繼續 Step 1。
- **若有 `[READY]` stash 且 working tree 為空**：
  提示使用者：
  > 「偵測到 N 個 [READY] stash 尚未合併。要先 promote 再部署嗎？」
  - 使用者選 **是** → 執行 `./scripts/stash-status.sh promote <N>` 後回到 Step 1
  - 使用者選 **否** → 繼續 Step 1（只部署當前 HEAD）
- **若有 `[WIP]` / `[REVIEW]` stash**：僅輸出提醒，不中止，繼續 Step 1。
- **若 stash-status.sh 不存在**：跳過此步驟（舊 clone 相容）。

---

### Step 0.6: Worktree detect + enter（大型功能）

執行 `git worktree list --porcelain`。若本次任務對應某 `ttr-<slug>-worktree`（feature 在該 worktree 而非主 repo）：

1. `cd` 進該 worktree，確認 `git rev-parse --abbrev-ref HEAD` == `feat/<slug>` 且路徑相符；不符 → STOP 回報。
2. **接著照常走既有 Steps 1–5**（狀態分類、rebase、verify、push、deploy）——**不要**在此另做一套 rebase/build/push。
3. Step 4 push 時 **branch-aware**：push 當前 worktree 的正確 HEAD（rebase 成 linear 後 `git push origin HEAD:main`），保留 explicit user approval 與既有 gitleaks/i18n gate；禁 `--no-ff`、禁 `--no-verify`。
4. push 成功後（依 canonical STOP 條件）可提示使用者 cleanup worktree。

主 repo（無對應 worktree）維持既有流程不變。

---

### Step 1: 檢查 Git 狀態

> **⚡ 先判讀 `git status -sb` 的提交狀態（防「no changes added」誤判迴圈）**
> 進 stage/commit 前，先分類本地狀態，避免對空 index 重複 `git add`/`git commit`：
> - **`ahead N, working tree clean`**（無 `M`/`??`）→ 變更**已提交**（前一輪 V-M-D 或 Engineer 已 commit）。**跳過 Step 1.x 提交紀律與 Step 4.1 commit**，直接進 Step 2 rebase 檢查 → Step 4.2 `git push`。此時再 `git add`/`git commit` 只會得到「nothing to commit / no changes added」的空 index——**誤判非失敗**，唯一待辦是 push。
> - **出現 `M`/`??`（modified／untracked）** → 照常走 Step 1.x + Step 4.1 commit。
> - **`ahead 0, working tree clean`**（且 origin 無新 commit）→ 無待推送變更，回報「無事可做」。

1. 檢查是否有未解決的 merge/rebase 衝突
1a. **🔁 未配對 docs commit 偵測（防 V-M-D ↔ docs 循環）**：執行以下檢查，若觸發**停止 V-M-D 並回到 Engineer 補 docs**：
   ```bash
   # 列出本地未推送的 fix/feat commits
   git log origin/main..HEAD --oneline --grep="^fix\|^feat" --extended-regexp
   # 確認這些 commits 是否同時改了 docs（history.md / SKILL.md / agent.md）
   git log origin/main..HEAD --name-only --pretty=format: | sort -u | grep -E '\.github/skills.*(history|SKILL)\.md|\.github/agents/.*\.agent\.md' || echo NO_DOCS
   ```
   - 若有 `fix:` / `feat:` commit **且** 輸出 `NO_DOCS`：詢問用戶「此次修改是否含新教訓？若有，應先 amend docs 進 fix commit 再 push」。用戶確認「無教訓」或「下次再補」才繼續 Step 2。
   - 此檢查不適用於 docs-only commits（commit message 以 `docs(` 開頭）。
2. **⚠️ Untracked scraper 前置檢查**：若 `git status --short` 顯示 `??` 在 `scraper/sources/` 下，立即執行 SCRAPERS audit：
   ```bash
   cd scraper && python3 -c "
   import re, glob
   registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
   for f in glob.glob('sources/*.py'):
       c = open(f).read()
       m = re.search(r'class (\w+Scraper)\b', c)
       if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
           print('UNREGISTERED:', m.group(1), f)
   "
   ```
   若輸出 `UNREGISTERED`，**中止 Step 2–5**，先將 import + SCRAPERS 登錄補入 `main.py`，再繼續部署流程。
3. 檢查是否有 unstaged 變更（必須先 stage 或 stash）
4. 若 dirty worktree 含本次任務範圍外文件，先列出並請用戶確認提交範圍（只提交目標檔 / 全部一起）
5. 若同一檔案出現 `MM`（staged + unstaged 同時存在），先 re-stage 最新版本並用 `git diff --cached <file>` 確認後再進入 Step 2
6. 提醒用戶解決任何待處理項目

### Step 1.x: 提交紀律（Commit Discipline）— 強制規則

> 以下五條規則為**強制禁止**，違反任一條即為 STOP 條件。

1. **禁止 `git add -A` / `git add .`**：只 stage 當前任務 Changes Log 明列的檔案路徑（逐一 `git add <path>`）。若需 stage 新檔，必須逐一列出路徑，不得使用萬用符號批量 stage。

2. **禁止 `--no-verify`**：任何情況都不得使用 `git commit --no-verify` 或 `git push --no-verify`。若 pre-commit hook 攔截，必須回報 hook 輸出並**停止流程**，等待用戶指示，不得繞過。

3. **禁止不觸發 git hook 的提交路徑**：一律走標準 `git commit`（會觸發 `.githooks/pre-commit`）。禁止經 VS Code/GUI source-control 提交、`git commit --amend`/rebase 重寫已含 staged 變更等可能繞過 hook 的路徑。

4. **範圍外髒檔強制 STOP**（升級現有 Step 1.4 的軟提醒為強制停止）：commit 前執行 `git status --short`；若出現「modified 但不在本任務 Changes Log 宣告清單」的檔案（特別是 `web/messages/*.json`）→ **STOP 並詢問用戶、列出未知檔案 diff 摘要、等待決定**，不得繼續。

5. **i18n 檔特別警示**：若 staged 檔案包含 `web/messages/*.json`，commit 前強制執行 `python3 scripts/check_i18n_parity.py --staged`，exit code ≠ 0 即中止。（此步驟已由 `.githooks/pre-commit` 自動執行；此規則為明示確認，確保 agent 不繞過 hook。）

### Step 2: Rebase（如果需要）
1. 先執行 `git fetch origin main`，更新 remote tracking
2. 檢查 `git log HEAD..origin/main --oneline` — 若 origin 有新 commit（**並行 commit 為常態，不要假設無事**），預設執行 `git rebase origin/main`
3. 檢查 `git log origin/main..HEAD --oneline` — 確認本地待推送的 commits
4. 如果 rebase 有衝突，指導用戶解決並繼續 rebase（`git rebase --continue`）
5. Rebase 後再次 `get_errors` 確認沒有因合併產生破壞

### Step 3: Verify Changes

> **⚡ docs-only commit 跳過 web build（2026-07-10 教訓）**：若 push range 未觸及任何 `web/` 檔（`git diff --name-only origin/main..HEAD | grep '^web/'` 為空）→ **跳過本 Step 的 `pnpm run build`/`lint` gate**。`.github/`／`docs/` 純文件 commit 不觸發 Vercel、不影響 web build；且工作樹若有**無關的 web WIP（別 session 未完成產物）**，跑 build 會因別人半成品失敗而**誤擋這個無辜的 docs push**。仍執行 `get_errors`（markdown lint）與 token/i18n gate（若 diff 觸及對應檔）。

1. 運行 `get_errors` 檢查語法錯誤（所有修改的文件）
2. **Build 前置清理（必做）**：dev server 與 `next build` 共用 `.next/`，dev server 存活時直接跑 build 會出現 ENOENT 或 lock 衝突
   ```bash
   lsof -ti :3000 | xargs kill -9 2>/dev/null; rm -rf web/.next
   ```
3. 執行 **`pnpm run build`**（在 `web/` 目錄）— `tsc --noEmit` pass ≠ build pass；route handler 錯誤、missing file、動態 import 問題只有完整 build 才能捕捉
   - **殘留 build 程序**：若出現 `⨯ Another next build process is already running`，先 `ps aux | grep "next build" | grep -v grep` 找 pid，`kill -9 <pid>` 後再重試。
3. 執行 token wording gate（deploy 前必過）：
   - 固定執行：`python3 scripts/check_token_permission_consistency.py`
   - 判斷本次 diff 是否包含 token 高風險檔案（使用 `git diff --name-only origin/main...HEAD`）：
     - `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`
     - `.github/instructions/token-rotation.instructions.md`
     - `.github/agents/researcher.agent.md`
     - `scraper/update_source.py`
     - `.github/SECRETS_LIFECYCLE.md`
   - 若包含任一高風險檔案，再加跑：`python3 scripts/check_token_permission_consistency.py --strict`
   - Gate 規則：
     - Exit code = 0：繼續 Step 4
     - Exit code ≠ 0：立即中止流程，回報 checker 輸出的違規 file:line，要求先修正後再重跑 V-M-D
3. 簡要檢查提交消息格式（遵循 `.github/instructions/commit-message.instructions.md`）
4. 若包含 Supabase migration，確認 migration 編號與 `.github/instructions/database.instructions.md` 的 latest 標記一致
5. **Docs staleness check**：使用 `git diff --name-only origin/main...HEAD` 確認本次 diff 是否為架構性改動。若符合以下任一條件，且 `docs/ARCHITECTURE.md` 或 `docs/SCRAPER_PIPELINE.md` 未在 diff 中，必須警告並要求補更新後才繼續 push：
   - 新增或移除整個 CI workflow（`.github/workflows/*.yml`）
   - 新增或移除 pipeline layer（新的 `auto_scraper/`、`researcher.py` 等主模組）
   - 新增或移除 Supabase 整合點（LINE bot、新 API route）
   - 變更 `scraper/main.py` 的 SCRAPERS 清單超過 3 個來源（批量上線屬架構里程碑）
   - 新增 `web/app/api/` 下的 API endpoint
   不屬於架構性改動（不需要更新 docs）：bug fix、單一 scraper 新增、i18n 修改、CSS 調整。

### Step 4: Commit & Push
0. **已提交偵測（呼應 Step 1 分類）**：若本地為「`ahead N, working tree clean`」→ **跳過本步驟 1（commit）**，直接執行 2（push）。不要對空 index 重跑 `git commit`（會得到「no changes added」誤判）。
1. 使用原子化、描述清楚的提交消息（僅在有 staged 變更時）
2. 執行 `git push origin main`
3. 確認推送成功（無被拒絕的更新）

### Step 5: Verify Deployment
1. Push 後立即記錄 `PUSHED_SHA=$(git rev-parse HEAD)`，重新 fetch `origin/main`，確認 GitHub `main` 的 SHA 仍等於 `PUSHED_SHA`。若不相等，停止並先釐清遠端是否被並行 push 推進。
2. 若本次 push range 觸及 `web/`，透過 GitHub commit status 與 Vercel dashboard／API 查詢綁定 `PUSHED_SHA` 的 **Production** deployment，記錄 exact-SHA deployment URL 與 status，並等待成功。不得用較舊 deployment 代替本次 SHA 的部署驗證。
  - **Docs-only commit 不觸發 Vercel**：Vercel root directory 設為 `web/`，只有 `web/` 變更才觸發部署。`.github/`、`scraper/`、`docs/` 的 push 若沒有新 deployment，記錄 deployment 為 `NOT APPLICABLE (docs-only)`；不要把舊 web deployment 當成當前 SHA 的證據。
  - 可選：以 `https://tokyo-taiwan-radar.vercel.app/` 作補充 app-level 檢查（production URL 含連字號 `tokyo-taiwan-radar`，不是 `tokyotaiwanradar`），但此 alias 不得取代 exact-SHA provenance。
3. 若 immutable deployment URL 回傳 `302`、`_vercel_sso_nonce` 或平台 `X-Robots-Tag: noindex`，分類為 **Deployment Protection boundary**，不是 application failure。保留保護設定，以 GitHub／Vercel exact-SHA provenance 確認部署，並改用 <https://tokyotaiwanradar.com> 執行 app-level production smoke；不得為了測試而弱化 Deployment Protection。
4. Security-sensitive web release 必須逐層回報驗證矩陣：
  - Public production behavior：custom-domain headers、routes、robots、cookie 與 JSON-LD。
  - Authenticated authorization behavior：在既有安全 credentials／test setup 可用時，驗證 OAuth、email magic link、session refresh／logout、ordinary-user role denial 與登入後 Admin CRUD。
  - 絕不要求使用者把 password、token、magic-link code 或其他 secrets 傳給 model。若安全 auth context 不可用，上述 authenticated flows 一律標為 `NOT TESTED` residual risk，不得宣告 PASS。
5. 若含 Supabase migration，明確回報「需在 Supabase SQL Editor 手動執行」與最小驗證清單（admin pass / non-admin deny）。
6. Subagent prose 只作線索，不是 authoritative evidence。若摘要缺失、不可理解或與實際狀態衝突，必須獨立核對 repo state、GitHub `main`／commit status 與 Vercel deployment API，再判定成功或失敗。

## External URL Verification Rule

寫入文件、agent 檔、commit message 或 plan 的任何外部 URL，都必須在第一次出現時用 `curl -sI -L <url>` 驗證一次：
- HTTP 200/301/302/308 → 可寫入
- HTTP 404/DNS error → 必須回頭找正確 URL，不可硬寫

常見錯誤：production URL 漏寫連字號（`tokyotaiwanradar.vercel.app` 是 404；正確為 `tokyo-taiwan-radar.vercel.app`）。Reference incident: commit `3f58372` — agent 文件中 production URL 錯寫，curl -I 回 404 才被發現。

## 成功指標
- ✅ 無衝突或已解決
- ✅ 所有語法檢查通過（`get_errors` + `pnpm run build`）
- ✅ Final commit 已推送，且 GitHub `main` 仍等於 captured pushed SHA
- ✅ 適用時，同一 SHA 的 Vercel Production deployment 已成功；docs-only 則明列 `NOT APPLICABLE`
- ✅ Production custom-domain public smoke 通過，且每個未執行的 auth flow 明列 `NOT TESTED` residual risk

最終回報必須包含下列 evidence fields，不得只回傳「部署成功」摘要：

1. Final commit SHA 與 message。
2. Rebase 結果與 conflict 處理情形。
3. Push 結果，以及 push 後 GitHub `main` 的 exact SHA。
4. 綁定該 SHA 的 Production deployment URL 與 status，或 docs-only `NOT APPLICABLE`。
5. Production custom-domain smoke results，逐項列出 public headers／routes／robots／cookie／JSON-LD。
6. 所有 `NOT TESTED` 項目，尤其 OAuth、magic link、session refresh／logout、role denial 與登入後 Admin CRUD。
7. Accepted residual risks，包括 Report-Only CSP、未測 auth flows 與 pre-existing full-file lint debt。
8. Worktree cleanliness／isolation，包括實際 path、branch、是否 clean，以及範圍外 WIP 是否保持不變。

> **「問題未重現」情形**：若收到「請修復後重新部署」提示但 Step 3 全部 pass、Vercel HTTP 200，則明確回報「問題未重現，目前狀態健康」——不要強行尋找不存在的問題。

> **「no changes added」誤判**：commit 時 index 空，且 `git status` 為 `ahead N, working tree clean`，代表變更**已提交非失敗**。直接 push（Step 4.2）即可，切勿反覆重試 commit 或誤判成部署失敗。

## 中止條件
如果遇到以下情況，停止並報告：
- ❌ Rebase 失敗且無法自動解決
- ❌ 語法檢查失敗
- ❌ token wording gate（default 或 strict）失敗
- ❌ Vercel 部署失敗（查看部署日誌）
- ❌ 推送被拒絕（遠端有新提交）
- ❌ 範圍外髒檔未確認即繼續提交（Step 1.x 規則 4）
- ❌ 使用了 `--no-verify` 或不觸發 hook 的提交路徑（Step 1.x 規則 2、3）
- ❌ i18n parity 檢查失敗（`python3 scripts/check_i18n_parity.py --staged` exit code ≠ 0）
