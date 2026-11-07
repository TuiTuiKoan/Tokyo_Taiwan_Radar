評審者：Claude plan-critic（與撰寫者同一模型家族；codex 不在此環境）

# Plan Critique 2：agent-autonomy Phase D5（lane2 核准車道、#563 production log 擷取、母 issue 收尾）

評審範圍：`proposal.md` §9、`lane2-runner-prompt.md`、`lane2-approved.yml`；背景讀了 `plan-critique-1.md`、`heartbeat-prompt-v2.md`、`notes.md` §4–§6、`scripts/ci/pr_tier.py`、`pr-tier.yml`、`source-diagnose.yml`、`zero-output-recovery.yml`。另外，worktree 裡已經有 #563 與母 issue 收尾的草稿：commit `6027da7` 改了兩個 workflow；`scripts/ci/prod_log_excerpt.py`、`scripts/ci/parent_rollup.py` 和它們的測試還沒追蹤進 git。我直接讀了這些草稿，兩支測試共 14 個在本機通過（沒有留下 cache）。全程唯讀。

## 總評：go with changes（lane2 runner 在 G1、G2 處理前不要建立排程；#563 和母 issue 收尾修完 G13、G14、G16 就可以出）

方向對。94 張 issue 沒有自動車道，裡面有 production 正在出錯的 bug（#540、#554）。「使用者核准的範圍」確實是缺的那一塊。把核准放進 main 上的檔案，比用 label 或留言強，這點判斷正確。

但 proposal 的核心安全主張「agent 冒充不了的核准管道」**在技術上不成立**。這個管道和「合併到 main」是同一道防線，而這道防線目前只靠提示詞與 hooks 擋 `git push`，沒有擋到合併或直接寫 main 的 API（G1）。另外，runner 的提示詞如果由 agent 用 `create_trigger` 建立，之後 agent 就能改掉它，連核准檢查一起刪除（G2）。這兩點不處理，等於讓使用者以為「沒合併就不會動」，實際上不是。

其餘多是正確性與負擔問題：
- 被拒絕的條目會隔天重做（G6）；
- 同一個 label 混用，造成上限與停止條件誤判（G7）；
- 提案量與消化量不對稱（G8）；
- migration 和 web 同一張 PR 合併，會讓 production 壞掉（G9）；
- #563 的 60 行截斷，正好切掉最關鍵的「scraped N / logged N」那幾行。已用實際 log 驗證：midland_cinema 的段落有 195 行（G13）；
- #381 母 issue 列了 30 個來源，只有 16 張子 issue，「子 issue 全關」不等於母 issue 完成（G16）。

| 面向 | 評分 | 依據 |
| --- | --- | --- |
| 商業主軸對齊 | 🟡 | 解開的 issue 包含資料面 bug（#540、#554、#404），屬優先序第 1、4 項；但 runner 本身是治理工具，價值取決於使用者週審能不能消化 |
| 複雜度 vs 價值 | high / medium-high | 1 個新排程 agent、1 個核准檔、2 支腳本與測試、2 個 workflow 修改，加上提議的 guard；觸及「權限與防線」「花錢」兩個關卡。複雜度約 5 level（跨 3 個以上檔案、workflow 權限、PR Tier Guard、secrets 邊界、新排程） |
| 優先順序 | 🟡 | D1 的四個 workflow 在 Actions 上還沒實際跑過（notes §6 NOT TESTED）。在未驗證的自動化上再疊一條車道，出事時很難判斷是哪一層。#563 和母 issue 收尾可以先出；lane2 應等 D1 第一次排程的證據寫進 notes 之後再建排程 |
| 復用 | 🟢／🟡 | #563 復用 `dryrun_evidence.clean_code`、parent_rollup 只信 bot marker，這些做得好；guard 不應另開 workflow，應併進 `pr-tier.yml` 和 `pr_tier.py`（G3） |

---

## Findings

### G1【blocker】「檔案在 main＝使用者合併過」不成立：合併與直接寫 main 都沒有技術防線
- **問題**（已實測）：
  1. `gh api repos/.../branches/main` 回 `protected: false`；唯一的 ruleset「TuiTuiKoan manager」是 `enforcement: disabled`。
  2. 雲端 agent 以 TuiTuiKoan 身分操作，而且有 workflow 寫入權限：PR #565 由雲端 session（commit 帶 `Claude-Session` trailer）推上去，內含 4 個 `.github/workflows/*.yml` 的修改。
  3. #565 的 `merged` 事件是 `actor=TuiTuiKoan`、`performed_via_github_app=none`，和 proposal 舉證 label 不可信的那筆紀錄長得一模一樣。agent 合併的 PR 在 API 上同樣無法和使用者合併區分。
  4. `scripts/claude/_policy.py` 只解析 `git push`。`gh pr merge`、`gh api -X PUT repos/.../pulls/N/merge`、`gh api -X PUT repos/.../contents/<path>`（不經 PR、直接 commit 到 main）都沒有規則。hooks 的 matcher 是 `Bash|Monitor` 和 `Read|Grep|Write|Edit|NotebookEdit`，heartbeat 使用的 GitHub MCP 工具（`mcp__github__*` 的 merge／create_or_update_file／push_files 這類）完全不經過 hooks。

  結論：被 prompt injection 的 agent 可以一個 API 呼叫把條目寫進 main，或把自己的提案 PR 合併。這和「貼 approved label」是同一類偽造，只是動作更「禁止」一點。
- **建議**：
  - D5-a 與 `lane2-approved.yml` 檔頭改寫成照實的說法：「核准管道與『合併到 main』是同一道防線；只要 agent 能合併，production 部署本來就已失守，所以 lane2 沒有降低門檻，但也不比它強」。不要寫「冒充不了」。
  - 開 issue（`spec:agent-autonomy`），附 patch 交使用者套用（屬「權限與防線」關卡）：
    - (a) bash guard 要求核准或阻擋 `gh pr merge`，以及 `gh api` 用 PUT／POST／PATCH／DELETE 打 `pulls/*/merge`、`merges`、`contents/`、`git/refs`、`git/commits`、`rulesets`、`branches/*/protection` 的呼叫；
    - (b) 新增 `mcp__github__.*` 的 PreToolUse matcher，擋 merge、寫檔、推檔類工具；
    - (c) 由使用者決定是否在 main 開「require pull request」ruleset（會擋掉 Contents API 直接寫和 `git push main`，代價是使用者自己也要走 PR）。
  - **在 (a)(b) 套用前不建立 lane2 排程。** 理由：lane2 會讓 agent 每天在有合併能力的 session 裡讀大量外部 issue 內容，攻擊面比 heartbeat 大。

### G2【major】runner 由 agent 以 `create_trigger` 建立，任何 agent 之後都能改掉它的提示詞與頻率
- **問題**：notes §5 實測「Agents can only update routines they created」，heartbeat 因為是使用者用 HTTP API 建的，所以 agent 改不了，這其實是一道防線。§9 反過來刻意讓 agent 建立，理由是「之後 agent 才能自己更新提示詞」。核准檢查（只讀 main、只做條目範圍）完全寫在提示詞裡，能改提示詞就能拿掉核准。`update_trigger` 也能把頻率調高，而「提高排程頻率」是人類關卡。
- **建議**：由使用者建立 routine，提示詞只放一段固定文字：「`git fetch origin main`，讀 `origin/main:docs/specs/active/agent-autonomy/lane2-runner-prompt.md` 並照做；讀不到就停止並在 #528 通知」。這樣提示詞的權威副本在 main 上，修改走 tier 2 PR（使用者合併），使用者不必每次貼文字，agent 也無法在 main 之外改它。同時把 `lane2-runner-prompt.md` 加進 runner 的禁止路徑（見 G4）。

### G3【major】核准檔的來源檢查：guard 必要但放錯地方；runner 只看「最後一次變更」不夠
- **夾帶路徑**：任何 tier 2 PR（lane2 實作 PR、D 系列 PR、互動 session 的 PR）都能順手改 `lane2-approved.yml`。使用者週審看的是「修 #xyz」，不會看到這一行。heartbeat PR 一旦夾帶這個檔，會從 tier 1 變成 tier 2，但使用者仍可能一鍵合併。
- **guard 用 `pull_request` 觸發會失效**：`pull_request` 跑的是 PR 自己版本的 workflow 檔，PR 可以同時改掉 guard 本身。標題檢查 `approve(lane2):` 沒有意義，因為標題也是 agent 寫的。
- **runner 只看「該檔最後一次變更」也不夠**：先有一次夾帶，之後再有一次合規的提案 PR，最後一次變更是合規的，但夾帶進來的條目仍然留在檔案裡。
- **runner 讀的不一定是 main**：`git show origin/main:` 讀的是 session 內的 remote-tracking ref。同一個 session 裡被注入的 agent 可以 `git update-ref` 改掉它。
- **建議**：
  - guard 併進 `pr-tier.yml`。它用 workflow_run 從 default branch 執行，PR 改不了它，而且已經有 `pull-requests: write`。`pr_tier.py` 多輸出一個 `approval_mixed` 旗標：檔案清單同時含 `lane2-approved.yml` 和其他檔 → 貼 `lane2-approval-mixed` label 並留言警告。只做「只改這個檔」的檢查，不檢查標題。
  - runner 改成**逐條**檢查來源：`git blame origin/main -- <檔>` 找出每條條目所在行的 commit → `gh api repos/.../commits/<sha>/pulls` → 該 PR 必須已合併、檔案清單只有這個檔、帶 `lane2-proposal` label。任一條不符 → 整份停用、在 #528 通知、本日不實作（fail closed，不是跳過那一條）。使用者直接 commit 到 main 的變更也視為不合規（和 agent 用 Contents API 寫入無法區分），文件請使用者一律走 PR 編輯。
  - 讀檔改用 REST：`gh api repos/.../contents/<path>?ref=main`，並和本地 `origin/main` 的 blob SHA 比對，不一致就停止。
  - 在 `pr_tier` 的測試加一條回歸測試：`lane2-approved.yml` 必須判為 tier 2，防止日後改 `TIER0_EXCLUDE` 時誤放成 tier 0。
  - 結論：guard 加上逐條來源檢查，足以防住「經 PR 夾帶」；防不住 G1 的直接合併或直接寫入。

### G4【major】runner 白名單包含治理相關路徑
- **問題**：`scripts/**` 只排除 `scripts/claude/`，所以下列都在可改範圍：
  - `scripts/ci/pr_tier.py`：決定 Tier 0 自動合併；
  - `scripts/ci/*.py`：由帶 `issues: write` 的 workflow 從 default branch 執行；
  - `scripts/sync_ai_adapters.py`：投影各 agent 的 `tools:` 白名單。

  `docs/**` 包含 `docs/specs/active/agent-autonomy/**`，裡面是 heartbeat 和 runner 提示詞的權威副本。`.github/skills/**` 包含 `.github/skills/agents/**`，是其他 agent（含 plan-critic、tester）的規則。這些都是「權限與防線」或 agent 行為本身。PR 雖然是 tier 2，但非專業使用者看到「修 #xyz」時不會察覺 `pr_tier.py` 也被改了。
- **建議**：
  - 禁止路徑加上 `scripts/ci/**`、`scripts/sync_ai_adapters.py`、`.codex/`、`.agents/`、`CLAUDE.md`、`.github/copilot-instructions.md`、`.github/skills/agents/**`、`docs/specs/active/agent-autonomy/**`。可改的 skills 只留 `.github/skills/sources/**`。
  - 明寫「禁止路徑優先於條目的 files」：使用者核准的條目也不能放寬禁止路徑。
  - 依賴清單（`scraper/requirements.txt`、`web/package.json` 與 lockfile）只有在條目明列、而且 risk 標 medium 以上時才可以改。

### G5【major】runner 界線只依 #561 的路徑清單，這個清單不完整，而且會漂移
- **問題**：
  1. `pull_request` 事件使用 PR 版本的 workflow 檔。任何同 repo 的 PR 只要新增或修改一個 workflow，在裡面引用 `secrets.SUPABASE_SERVICE_ROLE_KEY`，PR 一開出就會以 production 權限執行，不必碰 #561 列的任何檔。`push` 觸發也一樣：推 branch 就會跑，連 PR 都不用開。runner 提示詞「不能改 `.github/workflows/`」只是文字，而 token 確實有 workflow 寫入權限（G1 第 2 點）。#561 修好現有 workflow，擋不住新增的 workflow。
  2. 提示詞裡那份路徑清單是手抄的，日後 workflow 的 `paths` 一改就會漂移。
  3. `web/**` 的 server 端程式使用 `SUPABASE_SERVICE_ROLE_KEY`（`web/proxy.ts`、`web/app/actions/profile.ts` 等）。如果 Vercel 的 Preview 環境設了 production 的 service role key，任何推上去的 branch 都會在 preview 以 production 權限執行。這點 NOT TESTED：我看不到 Vercel 設定。
- **建議**：
  - #561 的範圍擴大成根本修法（附 patch 交使用者）：production secrets 移到 GitHub Environment `production`，deployment branch policy 只允許 `main`，需要的 workflow 宣告 `environment: production`。這樣任何 branch 或 PR 的執行都拿不到 secrets，路徑清單也就不需要了。
  - 請使用者確認 Vercel Preview 環境變數不含 production 的 service role key（人類關卡）。
  - 在根本修法完成前，runner 在實作當下從 main 的 `.github/workflows/*.yml` 現場算出「帶 `pull_request` 觸發而且引用非 GITHUB_TOKEN secrets 的 paths」，不用手抄清單。

### G6【major】被使用者拒絕的條目，隔天會被重新實作
- **問題**：實作模式第 1 步只排除「issue 已關閉」和「已有 open PR」。使用者關閉 lane2 PR、不合併，就是拒絕；但隔天 issue 仍 open、也沒有 open PR，runner 會照同一條條目再做一次。要到「連續 2 張關閉未合併」才會停下，而這時整條車道都停了。另外，PR 合併後如果沒有關掉 issue（例如條目本來就是「第一步」），條目也會被重做。
- **建議**：條目有「消耗」語意：只要已經有任何 PR（open、merged 或 closed）的 commit 帶 `Lane2-Approved: …` trailer，或 head 是 `lane2/issue-<n>`，而且建立時間晚於該條目的核准 commit，條目就視為已消耗。要重做，必須在下週提案中寫成新條目（新的 blame commit）。週五提案順便移除已消耗的條目。

### G7【major】提案 PR 和實作 PR 共用 `lane2` label，上限與停止條件會算錯
- **問題**：提案模式第 6 步也貼 `lane2`。結果：
  - open 的提案 PR 會佔掉「open lane2 PR 上限 3」的一個名額；
  - 停止條件「最近關閉的 2 張 lane2 PR 都沒有合併」會把使用者關掉的提案 PR 算進去。使用者關一張提案、再拒絕一張實作，車道就停了。
- **建議**：提案 PR 改貼 `lane2-proposal`（同時是 G3 來源檢查的條件），實作 PR 才貼 `lane2`。上限和停止條件只數 `lane2`。

### G8【major】量與節奏：提案 8、消化 3，積壓每週 +5；週六是否實作，提示詞和 proposal 說法不一致
- **問題**：
  - 實作 PR 要等下一個週六才會合併，加上 open 上限 3，每週最多只能實作 3 筆。提案每週最多 8 筆，已核准但未實作的條目每週累積約 5 筆。這些條目會在核准 2–3 週後才被實作，那時程式碼和情況可能都變了，使用者核准的 decision 也可能已經不成立。
  - proposal 寫「週日到週四實作」，提示詞寫「非週五就是實作模式」，所以週六也會實作。
  - 使用者負擔：週審要處理 heartbeat 最多 7 張、lane2 3 張 tier 2（含 web）、提案 4–8 筆決策，再加上 D 系列 PR。對非專業使用者來說，D4 的「≤90 分鐘」目標很難達成。
- **建議**：
  - 每週提案數改成「3 減去仍未消耗的已核准條目數」，最少 1、最多 4；前兩週固定 ≤3。
  - 實作日只留週日、週一、週二三次，其他日子不啟動，可以省配額；把提示詞和 proposal 統一成同一套說法。
  - lane2 的 web PR 在 body 第一段放 Vercel preview 連結，並寫「要點哪裡、應看到什麼」，讓使用者用驗證行為代替讀 diff。

### G9【major】`supabase/migrations/**` 在白名單內，合併後 web 會先部署、migration 還沒套用
- **問題**：同一張 PR 如果含 migration 和使用新欄位的 web 程式碼，合併後 Vercel 立刻部署 production，但 migration apply 是人類關卡，要另外執行。在這段空窗裡 production 頁面會出錯，repo 和 DB 的 schema 也會不一致。目前 workflow 沒有自動套用 migration（已 grep），所以這個空窗一定存在。
- **建議**：第一輪不開放 `supabase/migrations/**`（最小範圍試做）。之後若要開放，規則是「migration 單獨一張 PR，套用並確認後，才實作依賴它的程式」，並寫進條目的 decision。

### G10【major】需要人類判斷的決策題，預先填好建議答案就等於被蓋章
- **問題**：提案模式要求「每次至少 1 筆 needs-human 決策題，附建議答案」，條目的 decision 也直接寫成「答：…」。使用者沒細看就合併，agent 的答案就成了「人類判斷」。這正是 AGENTS.md 人類關卡「範圍判斷、分類定義」要防的情況。
- **建議**：
  - 欄位拆成 `suggested:`（agent 填）和 `answer:`（預設空白）。
  - 屬於「範圍判斷、分類定義、annotation／ground truth」的條目，`answer` 空白時 runner 跳過不做。
  - 其他技術性的 decision 可以預填 `answer`，維持低負擔。
  - 這類條目每週 ≤1 筆。

### G11【major】與 heartbeat 的衝突：同一張 issue、同一個檔、同一段時間
- **問題**：
  - lane2 實作沒有「同檔跳過」，heartbeat 有（v2 第 3 步會查所有 open PR 的檔案）。lane2 可以改 `scraper/sources/x.py`、`scraper/main.py`、`base.py`、`_cinema_base.py`，而這些檔正是 heartbeat PR 的基底，先合併的一方會讓另一方衝突。
  - 已核准條目的 issue 如果之後被貼上 `auto-fix`（例如 #459、#460 曾經在 auto-fix 和 needs-human 之間切換），兩條車道同一天都會取件。各自的「已有 open PR」檢查都還沒看到對方的 PR，結果就是重複 PR（#488／#526 的重演）。
  - 時間：lane2 在 06:07 UTC 執行，heartbeat 在 05:00 和 09:00 UTC，05:00 那次可能還沒跑完。
  - 配額：heartbeat 每天 6 次，加上 lane2 的實作（web 改動可能很長），都用同一個訂閱的配額。
- **建議**：
  - lane2 實作照搬 heartbeat 的同檔跳過，push 前再查一次 open PR。
  - lane2 跳過帶 `auto-fix` 的 issue；heartbeat v2 第 3 步加一句「main 上 `lane2-approved.yml` 列出的 issue 不取件」。
  - 排程改到 07:07 UTC 左右，避開 heartbeat 的 05:00 和 09:00。
  - 14 天盤點時把 lane2 的配額單獨記錄。

### G12【minor】source-intake 的兩段核准：evaluate 段不需要核准，而且在 sandbox 做不出什麼結果
- **問題**：evaluate 只在 issue 留言、不寫程式。AGENTS.md 允許 agent 自己留言，所以它本來就不在人類關卡內。現行設計下，新來源最快要 3 週：W1 提 evaluate → 核准 → 評估 → W2 提 implement → 核准 → 實作 → W3 合併。而 runner 連不到外部網站，researcher 規則要求的網站結構、更新頻率都只能寫 NOT TESTED，評估價值很低。
- **建議**：
  - evaluate 不需要核准，每天最多 1 張。WebFetch 在 routine 裡能不能用是 NOT TESTED，先試一次；不能用就只做原始碼和 issue 內容層面的評估，並明寫缺什麼。
  - implement 段保留核准，而且 decision 必須含「此來源在範圍內嗎」，答案依 G10 由使用者親手填。
  - implement 的 PR 會改 `main.py` 的 SCRAPERS，合併後就會每天寫入 production，所以 PR body 必須附 pr-dryrun-evidence 的 head 側筆數。

### G13【major】#563 只保留前 60 行，會切掉最關鍵的結果行
- **問題**：`prod_log_excerpt.excerpt()` 超過 60 行時只留前 59 行。但每個來源段落的結論都在尾端：`scraped N events`、`database: Skipped N already-scraped`、`logged N events to scraper_runs`、`scraper failed:`。我用 2026-11-06 的 log（job 127719940367）實測：
  - `MidlandCinemaScraper` 段落去掉 httpx 雜訊後還有 195 行，結論在第 193–195 行（scraped 1、logged 1）。midland_cinema 正是 #381 的來源之一，這條證據會被截掉。
  - PeatixScraper 69 行，也超過上限。
  - prtimes 只有 17 行，所以草稿用 prtimes 做的驗證沒有暴露這個問題。
- **建議**：
  - 改成「前 15 行加最後 40 行，中間標示省略」，或一律保留符合 `scraped \d+ events|logged \d+ events|scraper failed|Skipped \d+ |Skipping ` 的行。
  - 測試加一個 200 行的段落，斷言結尾三行都在輸出裡。
  - `InsecureRequestWarning` 和 `warnings.warn(` 這類行也加進 `_NOISE`。

### G14【major】#563 帶 token 的步驟和跑 scraper 的步驟在同一個 job，前一步可以竄改後一步
- **問題**：「Diagnose sources (no token)」步驟會用 Playwright 處理外部網頁，而且在可寫的 workspace 裡執行 dispatch 指定 ref 的程式碼。它可以：
  - 改寫 `scripts/ci/prod_log_excerpt.py` 或 `dryrun_evidence.py`；
  - 寫入 `$GITHUB_ENV`、`$GITHUB_PATH`，讓後面的步驟執行假的 `gh` 或 `python3`；
  - 直接改 `report.md`。

  後面的「Production log excerpts」和「Post diagnosis」步驟帶 `GH_TOKEN`（`issues: write`），並且執行 workspace 裡的這些檔。後果不只是洗版：被竄改的步驟可以用 `github-actions[bot]` 的身分在任何 issue 留下 `<!-- source-diagnose -->` 留言，而 heartbeat v2（F2）只信任這類留言，等於把外部內容洗成可信指令。「留言步驟才帶 token」這個做法（F15）在同一個 job 內是不夠的；#563 又多加了一個帶 token、執行 repo 腳本的步驟。
- **建議**：照 D-c（pr-dryrun-evidence）已採用的模式拆 job。
  - `diagnose` job：只有 `contents: read`，把 dry-run 的摘要 JSON 上傳成 artifact。
  - `report` job：`needs: diagnose`，checkout `ref: main` 並 sparse `scripts/ci`，持有 `actions: read` 和 `issues: write`。它下載 artifact，只把內容當資料解析（重新跑一次 `clean`），再抓 production log、組合留言。
  - key 到 class 的對應不要 import `main`，改在 report job 用 `ast` 解析 main 上的 `scraper/main.py`，或在 diagnose job 輸出成 JSON 一起上傳。

### G15【minor】#563 的其他問題
- `status=success` 會排除當天 job 失敗的 run。但 job 失敗多半是後段步驟（merger、標注）造成的，scrape 段的 log 仍然有效，而失敗那幾天往往正是最有資訊的。建議改成 `status=completed`，並在 label 標出 conclusion。
- 留言長度上限是 65,536 字元。最壞情況是 5 個來源 × 3 次 run × 60 行 × 300 字元，遠超過上限；`gh issue comment` 失敗時，failure 步驟會貼「診斷失敗」，連 dry-run 的診斷一起丟掉。batch 每次只送 1 個來源，所以通常不會發生，但手動 dispatch 會。建議組合留言時設 60,000 字元的預算，超出就先截 production log 的部分。
- class 對應那段失敗時用 `|| true` 靜默吞掉，結果完全沒有 log 段落，也沒有任何說明。建議寫一行「（無法對應 scraper class，略過 production log）」。
- log 貼進 issue 後會永久保存（Actions log 預設保存 90 天）。secrets 已被遮罩，但 production log 裡的 URL、路徑也會跟著永久留存，可以接受，但要在 PR body 寫明。

### G16【major】母 issue 收尾：「子 issue 全關」不等於母 issue 完成
- **問題**（已實測）：
  - #381 內文列了 30 個來源，有「母 issue：#381」的子 issue 只有 16 張（#475–#479、#497–#501、#507–#512）。hankyu_kobe、hankyu_umeda、hanshin_*、midland_cinema、nhk_rss、otto、stranger、taiwanshi（#506）等來源，要嘛沒有子 issue，要嘛掛在別的 issue 下面，沒有寫「母 issue：#381」。
  - #367 列了 10 個來源，子 issue 9 張（tokyo_now 已退役）。ciema 同時出現在兩個母 issue 的清單裡。

  `parent_rollup.decide()` 只看子 issue，所以 16 張關完就會貼 `ready-to-close`，但 #381 的完成條件是「每個來源都有預期設定或對應 issue」。週審的使用者會照 label 關掉一張其實沒完成的母 issue。
- **建議**：
  - parent_rollup 從母 issue 內文擷取來源 key：取 `[a-z0-9_]+` 的 token，再和 main 上 `scraper/main.py` 的 SCRAPERS key（用 ast 解析）取交集。
  - 每個 key 必須符合下列其中之一：(a) 有一張已關閉的子 issue；(b) 有任何一張標題以 `<key>：` 開頭的已關閉 issue；(c) 已在 `source_expectations.json` 登記。這些都不需要 secrets。
  - 有任何 key 不符合 → 不貼 label；留言列出「仍未結論的來源」，每個 key 只提醒一次（marker 帶 key 清單的 hash）。
  - 測試用 #381 的實際內文做 fixture。

### G17【minor】`ready-to-close` 不會自己失效
- **問題**：貼上 label 之後，如果有子 issue 被重開（例如 heartbeat v2 依 F12 重開復發的來源），或新增了子 issue，label 仍然留著。
- **建議**：每次執行時，如果母 issue 帶 `ready-to-close` 但有 open 的子 issue → 移除 label，並留言一次「#n 重開，已撤回 ready-to-close」。

### G18【minor】停止條件只能停、不能恢復，緊急開關也不在使用者手上
- **問題**：「最近 2 張關閉未合併」一旦成立就會一直成立，因為車道停了就不會再有新的 PR 合併。結果是永久停止，只能改提示詞才能恢復（而依 G2，提示詞應該只有使用者能改）。另外，G3 的來源檢查失敗也應該觸發停止，而不只是跳過。
- **建議**：
  - `lane2-approved.yml` 加 `paused: false` 和 `resume_after: <日期>` 兩個欄位。停止條件只計算 `resume_after` 之後的 PR；`paused: true` 時立即停止。這兩個欄位都在使用者的管道內，也是使用者在 GitHub 網頁就能操作的緊急開關。
  - revert 偵測改看 PR timeline 或 commit body 的 `This reverts commit`，不只比對標題。

### G19【minor】雲端 session 的 `gh api --paginate` 在第 2 頁會失敗（已實測）
- **問題**：`gh api --paginate "repos/.../issues?state=open&per_page=100"` 第 1 頁回 100 筆，第 2 頁回 403。原因是 Link header 用 `repositories/{id}/…`，被 proxy 拒絕；手動加 `&page=2` 則正常（目前 open 共 136 筆，含 PR）。runner 要從 134 張 issue 裡挑候選、查「有沒有 open PR 指向它」，資料會被靜默截斷，造成漏選或重複 PR。heartbeat v2 的盤點也受同樣影響。
- **建議**：兩份提示詞都明寫「不要用 `--paginate`；用 `&page=N` 迴圈，直到回傳少於 per_page」。這是 sandbox 限制，Actions 上的 `--paginate` 正常，parent-rollup 不受影響。

### G20【minor】提案模式讀取 public issue 內容，要過濾作者
- **問題**：任何人都能在 issue 留下開頭是 `<!-- lane2-evaluate -->` 的留言，附上一段「建議的 implement 條目」。提案 agent 會把它抄進 YAML，使用者再蓋章。「你先前已留言『超出範圍，停下』」的判斷也可以被偽造。
- **建議**：只採用作者是 repo owner（`TuiTuiKoan`）的 marker 留言。issue 內文與他人留言只當症狀，不當條目內容，並在 PR body 標示來源。

### G21【minor】讓非專業使用者在網頁上編 YAML，要有容錯
- **問題**：刪條目時很容易刪錯縮排、留下孤立的 `-`。改 decision 時容易打壞引號。
- **建議**：
  - runner 解析失敗或 schema 不符（未知欄位、type 不是 implement／evaluate、issue 不是數字）時 fail closed：本日不實作，在提案 PR 或 #528 留言指出第幾行。
  - `pr_tier` 的 `approval_mixed` 檢查順便用 `yaml.safe_load` 驗證，失敗就貼 `lane2-approval-invalid`。
  - 檔頭加一段「刪除整個條目要從 `- issue:` 刪到下一個 `- issue:` 之前」。

### G22【nit】
- `proposed: <日期> #PR`：開 PR 之前不知道 PR 編號，需要 commit 兩次。改寫週次 `2026-W46` 即可，來源用 blame 追（G3）。
- lane2 的 docs-only 實作 PR（例如 `docs/evaluation/**`）會被判為 tier 0 並自動合併（作者＝owner），和「下個週六一起審」的說法不符。應在 proposal 寫明，或讓條目的 files 不得只有 tier 0 路徑。
- 提案 PR 開出後，agent 不得再推 commit 到該分支：使用者在網頁上改完、到按合併之間，如果有新 commit，合併的就不是他看過的版本。需要修改時關閉並重開。
- 提示詞的 Co-Authored-By 是 `Claude <noreply@anthropic.com>`。依本 session 的 attribution 規則應該寫明模型，heartbeat 也一樣，這是一致性問題。

---

## AGENTS.md 人類關卡檢查

- **合併到 main**：設計上沒有違反，但這道防線本身是虛的（G1）。lane2 把「合併」從部署關卡擴大成「核准關卡」，負荷變重，防線卻沒有補強。必須先補 hooks 和 MCP 的規則。
- **權限與防線**：#563 加 `actions: read`、parent-rollup 用 `issues: write`，都以 tier 2 PR 交使用者，成立。runner 白名單碰到 `scripts/ci/**`、`sync_ai_adapters.py`、agent skills，等於讓 agent 間接改到防線（G4）。
- **production 資料寫入**：runner 不執行寫入，但 G5 的路徑（新增或修改 workflow、Vercel preview）可以繞過 production 寫入關卡。這不是 D5 造成的，但 D5 會讓 agent 每天開出更多改 web 和 scraper 的 PR，放大風險。
- **花錢與排程頻率**：建立排程前要求核准，正確。但由 agent 建立的排程，之後頻率可以被 agent 改（G2）。
- **需要人類判斷的輸入**：預填答案會讓關卡變成蓋章（G10）；source-intake 的「範圍判斷」必須由使用者親手作答（G12）。
- **不可逆動作、對外發布**：沒有觸及。

## 更簡單的做法

- guard 不開新 workflow，併進 `pr-tier.yml` 和 `pr_tier.py`：少一個檔、少一組權限，而且 PR 改不了它（G3）。
- evaluate 不走核准（G12），可以少一整輪週期。
- runner 的提示詞放在 main 上，由使用者建立的 routine 讀取（G2）：使用者以後不必再貼文字，防線也更強。
- 第一輪不開放 `supabase/migrations/**`（G9），實作日只排三天（G8）。
- #563 和 parent-rollup 和 lane2 互不依賴，可以先單獨出 PR，不必等 lane2。

---

## 建議採用的修改清單

依順序：

1. **先開 issue 並附 patch 交使用者（權限與防線關卡）**，lane2 排程在這之前不建立：
   - bash guard 擋 `gh pr merge`，以及 `gh api` 寫入方法打 `pulls/*/merge`、`merges`、`contents/`、`git/refs`、`git/commits`、`rulesets`、`branches/*/protection`；`mcp__github__.*` 的 merge 和寫檔類工具新增 PreToolUse matcher（G1）。
   - #561 擴大為「production secrets 移到只允許 `main` 的 Environment」，並請使用者確認 Vercel Preview 不含 service role key（G5）。
   - 由使用者決定 main 是否開「require pull request」ruleset（G1）。
2. **proposal §9 改寫**：
   - D5-a 照實描述「與合併 main 同一道防線」（G1）。
   - runner 改為使用者建立的 routine，提示詞固定為「讀 main 上的提示詞檔」（G2）。
   - 實作日統一為週日、週一、週二；每週提案 ≤3–4 筆（G8）。
   - 第一輪移除 `supabase/migrations/**`（G9）。
   - evaluate 不需核准（G12）。
3. **`lane2-approved.yml` schema**：
   - 加 `paused`、`resume_after`（G18）；
   - decision 拆成 `suggested` 和 `answer`，人類判斷類的條目 `answer` 空白就跳過（G10）；
   - `proposed` 改成週次（G22）；
   - 檔頭補編輯說明（G21）。
4. **`lane2-runner-prompt.md`**：
   - 逐條 blame 來源檢查，用 REST 讀檔並比對 blob SHA，不符就整份停用並通知（G3）；
   - 禁止路徑加上 G4 的清單，並寫明禁止路徑優先於條目；
   - #561 的路徑在實作當下從 main 的 workflows 算出（G5）；
   - 條目消耗語意（G6）；
   - `lane2-proposal` label 分流（G7）；
   - 同檔跳過、跳過 `auto-fix` 的 issue、push 前再查一次 open PR、排程改到 07:07 UTC（G11）；
   - 不用 `--paginate`（G19）；
   - 只信任 owner 寫的 marker 留言（G20）；
   - YAML 解析失敗時 fail closed（G21）；
   - 提案 PR 開出後不再推 commit（G22）。
5. **heartbeat v2 補兩行**：main 上 `lane2-approved.yml` 列出的 issue 不取件（G11）；不用 `--paginate`（G19）。
6. **`pr_tier.py` 和 `pr-tier.yml`**：
   - `approval_mixed` 和 YAML 驗證，貼 label 並留言（G3、G21）；
   - 回歸測試：`lane2-approved.yml` 必須是 tier 2（G3）。
7. **#563（`source-diagnose.yml`、`prod_log_excerpt.py`）**：
   - 截斷改成「前段加尾段」或保留關鍵行，用 200 行的 fixture 測試（G13）；
   - 拆成 diagnose 和 report 兩個 job，report job checkout main、artifact 只當資料、key 到 class 的對應不 import `main`（G14）；
   - 改 `status=completed` 並標出 conclusion、設 60,000 字元預算、對應失敗時明寫（G15）。
8. **parent-rollup**：
   - 以母 issue 內文的來源 key 對照子 issue、`<key>：` 標題的 issue 與 expectations，有未結論的 key 就不貼 label，改為列出（G16）；
   - 有子 issue 重開時撤回 label（G17）；
   - 用 #381 的實際內文當測試 fixture。
9. **驗收補充**：
   - lane2 第一次排程前，notes 必須記錄 D1 四個 workflow 第一次在 Actions 上執行的結果（優先順序）；
   - 14 天盤點加上 lane2 配額、已消耗與未消耗的條目數、被拒條目數。

## 交給 Architect 的教訓

未寫入檔案，交 Update History, Skill, Agent 寫入：
- 評審「誰能做某動作」的核准設計時，必查 branch protection 和 ruleset 的實際狀態（`gh api .../branches/main`、`.../rulesets`），以及 hooks 是否涵蓋 `gh api` 寫入方法和 MCP 工具。不能只看提示詞和 `git push` 規則。
- 評審 log 擷取或截斷時，必用 production 實際 log 找出最長的段落來驗證；用最短的樣本驗證，會看不出截斷問題。
- 評審「母 issue 由子 issue 完成」的設計時，必比對母 issue 內文的清單和實際子 issue 的數量。

建議下一步：交 Architect 依上面的清單修訂 §9、runner 提示詞和 YAML schema（Opus high）；第 1 項的 patch 和 #563、parent-rollup 的修正交 Engineer（Sonnet medium）。本報告需由使用者或 Engineer 存檔到 `docs/specs/active/agent-autonomy/plan-critique-2.md`。
