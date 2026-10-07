# Notes — ai-portability

執行證據與分類帳。只往後追加；既有段落不改寫。每段標明日期、執行者與工具版本。未實測的項目一律寫 NOT TESTED，不得寫成 PASS。

## 1. Phase 0 session（2026-10-06）

| 項目 | 值 |
|---|---|
| 執行者 | Engineer（Claude Code `2.1.290`，模型 Claude Opus 5.5 `claude-opus-5-5`） |
| 工作目錄 | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree` |
| 依據 | `~/.ai-notes/ttr/phase0-engineer-prompt.md`、`~/.ai-notes/ttr/handoff.md`（裁決 1–13）、`plan.md` §4 |
| `plan-rev6.md` SHA-256 | `6943c073620e29530581988a79c47e8da84ee34f6ce3edecf2e7511695487bbc`（與指定值相符，未 STOP） |

- 本 session 一開始以 Claude Haiku 4.5 啟動；只讀了檔案就被使用者中斷，改用 Opus 5.5 從頭執行。Haiku 階段沒有任何寫入。
- 本 session 未執行 `sync_ai_adapters.py`、測試、commit、push 或任何 production DB 操作，也未修改本目錄以外的檔案。
- `git fetch origin` 是 Step 0 指定的動作；它只更新 remote-tracking refs（`refs/remotes/origin/*`，含 4 個新的遠端分支）。

## 2. Worktree 閘門與 Step 0 證據

### 2.1 Worktree 確認閘門（plan §4 2a）

使用者在 Phase 0 prompt 中明確指定實作 worktree 為 `ttr-ai-portability-worktree`（CONTINUING）。核對結果：

| 檢查 | 結果 |
|---|---|
| `git worktree list --porcelain` 中的本 worktree | `worktree /Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree`、`HEAD 565c1479642761d35162e76a7f337b377596a56d`、`branch refs/heads/feat/ai-portability` |
| `pwd -P`／`git branch --show-current` | 與上列路徑、`feat/ai-portability` 相符 |
| 本 worktree `git status --short` | 無輸出（乾淨） |
| 主工作樹 `git -C "<主工作樹>" --no-pager status --short` | 無輸出（無他人 WIP）；主工作樹 branch `main`，HEAD `4e5f1f13dac393a5eccd790e5d2181b4adc84d44` |
| `.git/info/exclude` | 第 15 行有 `ttr-ai-portability-worktree/` |

觀察（不處理，屬其他 worktree，範圍外）：`git worktree list` 另有登記在 `/Users/flyingship/Development/Tokyo Taiwan Radar/…`、`/Users/flyingship/development/Tokyo Taiwan Radar/…` 與 `…/Tokyo Taiwan Radar.worktrees/…` 的 worktree。

### 2.2 Step 0 漂移檢查（plan §4 2b；§8.2 #1）

| 項目 | 值 |
|---|---|
| HEAD | `565c1479642761d35162e76a7f337b377596a56d`（docs(ai): add Claude Code migration runbook）＝ 預期值 |
| 工作樹 | 乾淨 |
| fetch 前本機快取的 origin/main | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| `git fetch origin` | exit 0；FETCH_HEAD mtime `2026-10-06T12:08:21+09:00`（`03:08:21Z`）；`ed09bece..3087f6ab main -> origin/main` |
| fetch 後 origin/main（Phase 0 remote baseline） | `3087f6abd14953fe57f2d002a506e9cecc27ce1d`（docs(weekly_review): 2026-10-04 weekly review） |
| `git merge-base HEAD origin/main` | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| `ed09bece` 是 origin/main 的祖先 | 是（`git merge-base --is-ancestor` exit 0）；origin/main 的 reflog 兩筆皆為 `fetch origin: fast-forward` |
| `git rev-list --left-right --count HEAD...origin/main` | `1	2`（ahead 1／behind 2） |
| `ed09bece..origin/main` | `3087f6ab docs(weekly_review): 2026-10-04 weekly review`、`0787e874 chore(deps): bump next from 16.3.3 to 16.3.6 in /web (#281)` |
| 這 2 個 commit 改到的檔案 | `docs/weekly_review/2026-10-04.md`、`web/package.json`、`web/pnpm-lock.yaml` |
| 與本 campaign 路徑重疊 | 無（`git diff --name-only ed09bece origin/main -- AGENTS.md CLAUDE.md .github .claude .agents scripts docs/specs docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md docs/evaluation/campaigns` 無輸出） |
| `origin/main..HEAD` | `565c1479 docs(ai): add Claude Code migration runbook` |

**判定**：預期內的主幹前進，**不是非預期漂移**。HEAD 符合預期、工作樹乾淨、`ed09bece` 仍是祖先且為 fast-forward、新增 commit 不碰本 campaign 的任何路徑。Campaign base 維持 `ed09bece`，未 rebase、未改 base。§8.2 #1 已取得證據，未 STOP。Phase A preview 或 merge-back 前，依 `git.instructions.md` 在乾淨工作樹上 `git rebase origin/main`，屆時另記當時的 remote baseline。

## 3. Phase 0 查證（只查、只記錄）

### 3.1 A2：全部 agent frontmatter 的 legacy 路徑

範圍：`.github/agents/**/*.agent.md` 共 16 檔（含 `subagents/` 3 檔）。只擷取第一組 `---` 之間的 frontmatter，再以 `rg -i '/memories|copilot-tracking|session memory|memory tool|session plan|plan\.md'` 過濾。

| 檔案 | frontmatter 行 | 內容（handoff `prompt`） |
|---|---|---|
| `.github/agents/architect.agent.md` | L7、L10 | `/memories/session/plan.md`、`/memories/session/plan-critique.md` |
| `.github/agents/designer.agent.md` | L7 | `/memories/session/design.md` |
| `.github/agents/plan-critic.agent.md` | L7、L10 | `/memories/session/plan-critique.md`、`/memories/session/plan.md` |

其他 13 檔的 frontmatter 無命中。從 generated 端交叉確認：`rg -n '/memories|copilot-tracking' .claude/agents` 只命中 `.claude/agents/architect.md` L11–12、`designer.md` L11、`plan-critic.md` L11–12（共 5 行，與上表一一對應）。

**結論**：A2 預期集合 `{architect, plan-critic, designer}` **不需調整**，與 plan §5 A1「已查證的 frontmatter 內命中」完全一致。

### 3.2 A1 語意補查與 architect SKILL

命令：

```bash
rg -n -i 'session memory|/memories|copilot-tracking' AGENTS.md CLAUDE.md .github/agents .github/prompts .github/instructions .github/skills/agents .github/copilot-instructions.md
```

共 45 行命中，全部對應到 plan §5 的 A1 表或 A3 表，**沒有表外的新命中**：

| 檔案 | 命中行 | plan 對應 | Phase 0 分類 |
|---|---|---|---|
| `AGENTS.md` | 54 | A1 | active（對照表，補註 legacy） |
| `.github/agents/architect.agent.md` | 7、10、80、1168、1173、1175 | A1 | active |
| `.github/agents/plan-critic.agent.md` | 7、10、21、31、37、101、105 | A1 | active |
| `.github/agents/designer.agent.md` | 7、115、120 | A1 | active |
| `.github/agents/researcher.agent.md` | 19、103、142、156 | A1 | active |
| `.github/agents/campaign-closer.agent.md` | 88 | A1 | active |
| `.github/agents/scraper-expert.agent.md` | 192 | A1 | active（staging 排除，標 legacy） |
| `.github/skills/agents/designer/SKILL.md` | 506 | A1 | active |
| `.github/skills/agents/researcher/SKILL.md` | 51 | A1 | active |
| `.github/instructions/git.instructions.md` | 138、141 | A1（L136–149 整段） | active |
| `.github/prompts/authoritative-venue-repair.prompt.md` | 13、14、361 | A1 | active |
| `.github/prompts/admin-qa-cleanup.prompt.md` | 36；38、138 | A1 | 36 active；38、138 為限制句，符合新契約，不改 |
| `.github/prompts/weekly-review.prompt.md` | 123（Step 3 標題）、125 | A1（裁決 4 刪除 Step 3） | active |
| `.github/prompts/workstream-audit.prompt.md` | 21；16 | A1 | 21 active；16 為限制句，不改 |
| `.github/prompts/ledger-topology-reconcile.prompt.md` | 18；47 | A1 | 18 active；47 為限制句，不改 |
| `.github/skills/agents/engineer/history.md` | 310、1822、1825、1828、1831、1832 | A3 | historical（6 處；L1822–1832 旁加 superseded 註記） |

`CLAUDE.md`、`.github/copilot-instructions.md` 無命中。`weekly-review.prompt.md` L123 是 L125 所屬的 Step 3 標題，plan A1 表列 L125，刪除 Step 3 時一併處理。

architect SKILL：

```bash
rg -n -i '/memories|\.copilot-tracking|copilot-tracking|session memory|memory tool' .github/skills/agents/architect/SKILL.md
```

無輸出，exit 1。**結論**：與 plan §5 註記一致，A1 不改 `.github/skills/agents/architect/SKILL.md`。

本節是 Phase 0 的基線查證，不是 A-R1 的完整分類帳。A-R1 仍須在 Phase A 依 plan §5「驗證」的三條 negative search（含 `docs`、`.claude`、`.agents` 範圍）與語意同義詞補查重做並分類。

### 3.3 `admin-qa-cleanup/proposal.md` L237（plan §5 A3）

已讀 `docs/specs/active/admin-qa-cleanup/proposal.md` 全文（529 行）。L237–238 原文：

> \* Replace the ephemeral `/memories/session/plan.md` authority pointer with this
>   committed successor spec after its docs-only gate

**結論：尚未完成取代，需要補狀態**（plan A3 判準：「若該句已是已完成取代則不改，否則補狀態」）。依據：

1. L237 位於 L231–241「Suggested future predecessor corrections are limited to a separately approved docs-only reconciliation or final archive」清單內，是**未來式的待辦建議**，不是宣稱 `/memories` 為本 spec 權威的 active 句。
2. 它要取代的指標仍在前任 spec：`admin-reports-204-cleanup/tasks.md` L8「權威計畫 `/memories/session/plan.md`」、`admin-reports-204-cleanup/proposal.md` L18「The authoritative design lives at `/memories/session/plan.md`」。
3. 本 worktree、`origin/main`（`3087f6ab`）與 `feat/admin-qa-cleanup`（`4de6d08c`）三處的這兩個 spec 目錄內容相同（`git diff --stat HEAD feat/admin-qa-cleanup -- …` 無輸出），L237 文字一致。

**需在 H-A1 由使用者決定的事項（F3）**：同一清單 L240–241 寫明「Keep predecessor `proposal.md`, `tasks.md`, and `notes.md` unchanged until that approval」。plan A3 預定在 Phase A 改寫前任 `tasks.md` L8 與 `proposal.md` L18，但 plan 只引用了「`notes.md` bytes 不得變動」（前任 proposal L18），沒有提到 admin-qa-cleanup 對前任 `proposal.md`／`tasks.md` 的凍結。因此 Phase A 動到前任這兩檔之前，須由使用者在 H-A1 明確認定：本次改寫就是 L233 所說「另行核准的 docs-only reconciliation」，且只限權威指標一項。

- 若認定：Phase A 改寫前任 L8、L18，並在 L237 旁補狀態，指向 Phase A commit（`tasks.md` 記錄 SHA）。
- 若不認定：Phase A 不改前任兩檔，L237 維持原文；A-R7 對 `admin-reports-204-cleanup` 無法依 A3 表通過，須由使用者另行決定該列的處理方式（plan §8.2 原則 2：分流沒涵蓋就 STOP 回報，不臨場加新設計）。

Phase 0 不做任何決定，也未修改這兩個 spec。另注意 R7：`feat/admin-qa-cleanup` 在 `ttr-admin-qa-cleanup-worktree` 仍為 active，若兩邊都改 L237 附近，日後 merge 可能產生文字衝突。

### 3.4 `supabase --help`（規則 9 依據）

已安裝：`/opt/homebrew/bin/supabase`，`2.90.0`（CLI 提示有 `v2.119.0` 可升級；未升級）。只執行 `--help`，未執行任何會連線或寫入的子命令。以下分類**只依 help 文字**，runtime 行為 NOT TESTED。

**會改變資料庫或 migration history 的子命令**：

| 子命令 | help 文字摘要 | 預設目標（依 help） |
|---|---|---|
| `db push` | Push new migrations to the remote database；有 `--dry-run`、`--include-all`、`--include-seed`、`--include-roles` | `--linked`（default true） |
| `db query [sql]` | Execute a SQL query against the local or linked database；`-f` 讀 SQL 檔；`--linked` 經 Management API | `--local`（default true） |
| `db reset` | Resets the local database；`--linked` 會重設 linked project | `--local`（default true） |
| `migration up` | Apply pending migrations；`--linked`、`--db-url` | `--local`（default true） |
| `migration down` | Resets applied migrations up to the last n versions | `--local`（default true） |
| `migration repair` | Repair the migration history table（`--status applied｜reverted`） | `--linked`（default true） |
| `migration squash` | Squash migrations；`--linked` 會改 linked project 的 migration history | `--local`（default true） |
| `seed buckets` | Seed buckets declared in `[storage.buckets]`；`seed --linked` 作用於 linked project | `--local`（default true） |
| `db schema declarative sync --apply` | 產生 migration，`--apply` 套用到 local database | local |
| `db schema declarative generate --reset` | 產生前重設 local database | local |
| `db start --from-backup` | 由備份啟動 local Postgres | local |

**依 help 判定為讀取或只寫本機檔案**：`db diff`、`db dump`（`-f` 寫本機檔）、`db pull`（寫本機 migration 檔）、`db advisors`、`db lint`、`migration list`、`migration fetch`（寫本機 migration 檔）、`migration new`（本機檔）、`inspect db *`。

**`supabase db diff` 只讀的結論**：help 中沒有任何把差異套用到目標資料庫的旗標；`--linked`／`--db-url`／`--from`／`--to` 只指定比較來源。它對本機有兩個副作用：`-f` 會在 `supabase/migrations/` 新增 migration 檔、`-o` 會寫輸出檔；比較時需要本機 shadow database（Docker）。結論：**依 help 文字，對目標資料庫為只讀**，可留在 must-allow；實際執行行為 NOT TESTED（本 session 未執行，需 Docker 與 link）。

**需在 H-C1 由使用者決定的事項（F4；Phase 0 不設計）**：

1. `supabase db query` 可對 local、linked 或 `--db-url` 指定的資料庫執行**任意 SQL（含寫入）**。plan §7 規則 9 的明確阻擋只寫了 `db push` 與「Phase 0 列舉的其他寫入型子命令（如 `db reset`、`migration up`）」，psql 的 SQL 檢查也只套在 `psql` 上。`db query` 應歸入哪一類（整個 deny，或比照 psql 的單一 SQL 字串檢查並拒絕 `-f`），需在 H-C1 決定。
2. `db push` 與 `migration repair` 依 help **預設就作用在 linked project**；其他寫入型子命令預設是 local，加 `--linked` 或 `--db-url` 才作用在遠端。規則 9 只看子命令名稱或也看目標旗標，需在 H-C1 決定。
3. 全域旗標 `--yes`（answer yes to all prompts）會略過 CLI 自身的確認提示，與上列寫入型子命令合用時更危險。
4. `db pull`：help 未說明是否會寫入 remote 的 migration history table。**未查證**，Phase C 實作前須以官方文件或 disposable 專案確認，未確認前不得歸類為只讀。
5. Management APIs（`secrets`、`functions`、`storage`、`projects`、`branches`、`config`、`postgres-config`、`network-bans`、`network-restrictions`、`ssl-enforcement`、`domains`、`backups`、`encryption`、`sso`、`vanity-subdomains`、`orgs`）中有會改 production 設定的子命令，但不屬於規則 9（prod-db）的範圍。本 campaign 不涵蓋，依 plan §8 列為殘餘風險候選，是否列入 `tasks.md` 後續項由使用者決定。

### 3.5 Phase 0 驗證（prompt 第 6 步）

| 檢查 | 命令 | 結果 |
|---|---|---|
| tracked 變更的 whitespace | `git diff --check` | 無輸出，exit 0（Phase 0 沒有改任何 tracked 檔） |
| 新檔 whitespace | 逐檔 `git diff --no-index --check /dev/null <file>`（一般 `git diff --check` 不涵蓋 untracked） | `proposal.md`、`tasks.md`、`notes.md`、`plan.md`、`plan-critique-1.md`、`plan-critique-5.md`、`plan-critique-6.md` 無問題。`plan-critique-2.md` L39、44、49、54、59、64 與 `plan-critique-3.md` L3 有 trailing whitespace（行尾兩個空白，是 Markdown 的強制換行）；`plan-critique-4.md` 檔尾多一個空行。`plan-critique-5.md`、`plan-critique-6.md` 無結尾換行（`--check` 不報）。以上都是來源檔原有的位元組，依「原樣複製、不改寫」保留。H0（2026-10-06）使用者選擇方案 A：維持原樣，不加 `.gitattributes`、不正規化 |
| 變動範圍 | `git status --porcelain`、`git ls-files --others --exclude-standard` | 只有 `docs/specs/active/ai-portability/` 下 10 個新檔；無 tracked 修改、無 `MM` |
| secret | `gitleaks dir docs/specs/active/ai-portability --no-banner --redact -c .gitleaks.toml` | `no leaks found`，exit 0 |
| secret（備援） | 遮罩輸出的 regex 掃描：`github_pat_`、`gh*_`、`sk-`、`sk-ant-`、JWT、私鑰標頭，以及 `SUPABASE_*`／`OPENAI_*`／`GITHUB_TOKEN` 等賦值行 | 0 命中；字面提到 `.env`／`GITHUB_TOKEN` 的行皆為規則 7 的政策討論 |

whitespace 例外的影響：`.githooks/pre-commit` 只做 agent `tools:` 清理、i18n parity、gitleaks staged 掃描與 migration 編號，不檢查 whitespace；V-M-D agent 與 `.github/workflows/` 也沒有對 commit 範圍跑 `--check`（`rg -n 'diff --check'` 查證）。Phase A 的 A-R8 只檢查 Phase A 的 diff，不會再碰到這些已提交的檔案。

## 4. 後續 phase 的證據

（Phase A 起往下追加：A-R1 分類帳、A-R3 frontmatter-diff、A-R5 冪等字典、B-0／C-0 spike 結果與 `claude --version`。）

### 4.1 Phase A session（2026-10-06）

| 項目 | 值 |
|---|---|
| 執行者 | Engineer（Claude Code `2.1.291`，模型 Claude Opus 5.5 `claude-opus-5-5`）；system prompt 為 `.claude/agents/engineer.md` wrapper |
| 工作目錄 | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree` |
| 依據 | `~/.ai-notes/ttr/phaseA-engineer-prompt.md`（由 `~/.ai-notes/ttr/start-phaseA.sh` 指向；腳本本身未在工具內執行，因為它會 `exec claude` 開新的互動 session）、`plan.md` §1、§2、§4、§5、§8 |
| `plan.md` SHA-256 | `6943c073620e29530581988a79c47e8da84ee34f6ce3edecf2e7511695487bbc`（與指定值相符，未 STOP） |
| Claude Code 版本 | Phase 0 為 `2.1.290`，本次 `2.1.291`。B-0／C-0 尚未執行，沒有需要重跑的 fixture |

### 4.2 Worktree 閘門與 Step 0（Phase A）

| 檢查 | 結果 |
|---|---|
| `git worktree list --porcelain` 中的本 worktree | `worktree …/ttr-ai-portability-worktree`、`HEAD 256e8b9bc2eef018762997db48c74085180fc3df`、`branch refs/heads/feat/ai-portability` |
| `pwd -P`／`git branch --show-current` | 與上列路徑、`feat/ai-portability` 相符 |
| 本 worktree `git status --porcelain` | 無輸出（乾淨） |
| 主工作樹 `git -C "<主工作樹>" --no-pager status --short` | 無輸出（無他人 WIP）；branch `main`，HEAD `4e5f1f13dac393a5eccd790e5d2181b4adc84d44` |
| `.git/info/exclude` | 第 15 行有 `ttr-ai-portability-worktree/` |
| HEAD | `256e8b9b`（docs(ai): add ai-portability spec skeleton）＝ 預期值 |
| fetch 前本機快取的 origin/main | `3087f6abd14953fe57f2d002a506e9cecc27ce1d`（＝ Phase 0 remote baseline） |
| `git fetch origin` | exit 0；worktree FETCH_HEAD mtime `2026-10-06T16:37:15+09:00`（`07:37:15Z`）；`3087f6ab..2c142c24 main -> origin/main` |
| fetch 後 origin/main（Phase A remote baseline） | `2c142c2464b428e3785007952808d725110e709e`（docs(google_news_rss): record unpinned-dependency outage lesson） |
| `git merge-base HEAD origin/main` | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| `ed09bece` 是 origin/main 的祖先 | 是（`git merge-base --is-ancestor` exit 0）；origin/main reflog 最新三筆皆為 `fetch origin: fast-forward` |
| `git rev-list --left-right --count HEAD...origin/main` | `2	5`（ahead 2／behind 5） |
| `ed09bece..origin/main` | `2c142c24`、`19fd072f test(cleanup): make staging-competitor fixture immune to inode reuse`、`a7ae4693 fix(scraper): pin googlenewsdecoder/selectolax to unbreak Daily Scraper`、`3087f6ab`、`0787e874`（後兩個 Phase 0 已記錄） |
| 這 5 個 commit 改到的檔案 | `.github/skills/sources/google_news_rss/{SKILL,history}.md`、`docs/weekly_review/2026-10-04.md`、`scraper/requirements.txt`、`scraper/sources/google_news_rss.py`、`scraper/tests/test_cleanup_admin_reports.py`、`web/package.json`、`web/pnpm-lock.yaml` |
| 與 Phase 0 所用 campaign 路徑過濾重疊 | `.github/skills/sources/google_news_rss/SKILL.md`、`history.md`（Phase 0 時無重疊） |
| 重疊檔的 legacy 內容 | 以 `git show origin/main:<file>` 逐檔 `grep -i -E '/memories\|copilot-tracking\|session memory\|memory tool\|session plan'`：無命中 |

**判定**：預期內的主幹前進，**不是非預期漂移**。HEAD 符合預期、工作樹乾淨、`ed09bece` 仍是祖先且為 fast-forward。新出現的重疊只在 `.github/skills/sources/google_news_rss/`：這兩檔不是 Phase A 的目標檔、不含 legacy 路徑，對 A-R1 的 negative search 與 Phase A 的編輯都沒有影響（內容是 Daily Scraper 停擺的修復紀錄）。Campaign base 維持 `ed09bece`，未 rebase、未改 base。此判定與 Phase 0 的「路徑過濾無輸出」不同，已在 H-A1 呈報，使用者可推翻。

### 4.3 R1 前測（`/context`，資訊性）

使用者在本 session 開頭、尚未給任何指示前執行 `/context`，輸出留在本 session 對話中。Memory files 段：

| Type | Path | Tokens |
|---|---|---|
| Project | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/CLAUDE.md` | 189 |
| Project | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/AGENTS.md` | 3.2k |

同一輸出：模型 `claude-opus-5-5`；Custom agents 來源 `.claude/agents/`，16 個。

**結果**：前測載入的是 **worktree 版** `CLAUDE.md`、`AGENTS.md`，與 Phase 0 session 的觀察一致；plan §3 R1 所述「載入主工作樹版本」在本次前測**未出現**。R1 後測（Phase A commit 後由使用者在 worktree 新 session 執行 `/context`）：NOT TESTED。本項為資訊性，不阻擋 B。

### 4.4 H-A1 前查證（只查、只記錄，Phase A 未動任何目標檔）

**Negative search 基線**（plan §5「驗證」三條命令，Phase A 修改前）：NS1 共 90 行（扣除 `docs/specs/active/ai-portability/` 22 行後 68 行）；NS2 36 行；NS3 36 行。完整分類帳在修改後的 A-R1 重做。

**F5：`.copilot-tracking/research/` 是 scraper 腳本的 I/O 介面，不只是 Copilot scratch**（plan A1 未涵蓋）

| 證據 | 內容 |
|---|---|
| `scraper/researcher.py` L339、L574、L671 | `CANDIDATES_DIR = …/.copilot-tracking/research/candidates`；建立目錄並寫入 `<slug>.json` |
| `.github/workflows/researcher.yml` L79 | CI 執行 `python researcher.py`（候選檔寫在 runner 上，不回到本機） |
| `scraper/update_source.py` L14、L40–41、L60–80、L245–248 | `--create-issue` 從 `SOURCES_DIR = …/.copilot-tracking/research/sources` 找 profile 放進 GitHub Issue 內文；找不到只記 warning，Issue 內文變成最簡版 |
| `scraper/update_source.py` L256–272 | 更新後刪除 `CANDIDATES_DIR` 內對應的候選 JSON |
| 主工作樹 `.copilot-tracking/research/`（唯讀列目錄） | `candidates/` 0 檔、`sources/` 133 檔、`research-log.md`、`subagents/`、`2026-05-25/` |
| `research-log.md` | `scraper/`、`web/`、`scripts/`、`.github/workflows/` 都沒有程式讀取 |

影響：plan A1 要把 `researcher.agent.md` L19、L103、L142、L156 與 `researcher/SKILL.md` L51 改到 `docs/specs/active/<slug>/research/` 或 `~/.ai-notes/ttr/research/`。照字面改寫會讓 profile 與 `update_source.py --create-issue` 脫鉤（Issue 內文退化、只有 warning），Step 0 也會指向腳本從不寫入的目錄。`scraper/**` 不在 Allowed paths。依 plan §8.2 原則 2，此情況未被分流涵蓋，交 H-A1 決定。

**F6：`authoritative-venue-repair/tasks.md` L9 是 A3 表以外的權威句**

- L9 原文：「`/memories/session/plan.md` 保存完整架構、UUID allowlist、production protocol 與 STOP 條件。」plan A3 表只列同 spec 的 `proposal.md` L50、L183。
- L25「[x] 建立 `/memories/session/plan.md` 並獨立重讀驗證」是已勾選的歷史步驟，分類 historical，不改。
- 內容實際所在：`.github/prompts/authoritative-venue-repair.prompt.md`（自稱「新 session 的完整初始架構真值」；含 46 處完整 UUID、Production repair tool contract、多處 STOP 條件）；`proposal.md` 只含部分 UUID（L131–136）。A3 表把 L50 改寫為「`proposal.md`＋`tasks.md`」會漏掉這份 prompt。
- 同一語意補查（`memories|session memory|session plan|copilot-tracking|memory tool`）在其他 active spec 只多命中 `workstream-tracking/proposal.md` L25（「Why」段的敘述句，不是權威宣稱），分類 historical，不改。

**F7：`plan-critic.agent.md` L102 與 L105 語意相連**

L102「`create_file` 例外只限寫入批評報告」沒有 legacy 路徑，所以不在 plan 的行號清單內；但 L105 改成「不寫檔，以文字回報」後，L102 的例外會與之矛盾。交 H-A1 決定是否一併改寫。

**R7 觀察（他線分支與 A3 目標行的重疊）**

| 分支 | 與本 HEAD 的關係 | A3 目標檔差異 |
|---|---|---|
| `feat/admin-qa-cleanup`（`4de6d08c`） | 是 HEAD 的祖先（已併入） | 無 |
| `feat/publication-policy`（`a09208d8`） | 是 HEAD 的祖先（已併入） | 無 |
| `feat/authoritative-venue-repair`（`3f7c00f6`，merge-base `e8f756c0`） | 已分岔 | `proposal.md` 新增段在約 L124–150 與 L176–178 之後；`tasks.md` 新增段在約 L331。都不碰 `proposal.md` L50、L183 與 `tasks.md` L9；日後合併時文字衝突風險低，但仍是 R7 的實例 |

**其他基線**：`shellcheck 0.11.0 scripts/campaign-closeout-audit.sh` 無輸出、exit 0（修改前）。`.github/prompts/weekly-review.prompt.md` 以外沒有任何檔案引用 weekly-review 的步驟編號。

### 4.5 H-A1 決定（使用者，2026-10-07）

| 項目 | 決定 |
|---|---|
| a. A1 措辭（含新 state 契約句、handoff `prompt`、`AGENTS.md` L54、`git.instructions.md` 契約表） | 全部核准 |
| b. A3 權威句改寫與 historical 標註措辭 | 全部核准 |
| c. runbook 措辭表套用方式 | 核准；L295 加「工具層（Phase B 投影目標）」避免在 B 之前寫成既成事實（C-R11）；L268 的註記放在 code block 後；L299 依 F5；A-R1／A-R2 PASS 後勾 L403 |
| Step 0 判定 | 核准：預期內主幹前進（§4.2） |
| F3 | 使用者先要求看原文；Engineer 呈上 `admin-reports-204-cleanup` `tasks.md` L8、`proposal.md` L18 與 `admin-qa-cleanup` `proposal.md` L13–16、L231–241、`tasks.md` L12–13、L182、L338、L349 原文，並因後繼 spec 三處宣告前任為「immutable audit history」而把建議由選項 1 改為選項 2。**決定：選項 2**——前任三檔與 L237 零 diff；A-R7 範圍修訂為 4 個 spec；前任兩句在分類帳記為 historical（凍結的 audit history），由 admin-qa-cleanup 的 final reconciliation（其 `tasks.md` L349）處理 |
| F5 | **(a)**：`.copilot-tracking/research/{candidates,sources}/` 視為腳本 I/O 介面保留並加註；`research-log.md` 改到 `~/.ai-notes/ttr/research/`。使用者追問是否需要修理、是否記待辦 → 已在 `tasks.md`「後續項目」新增一條（理由：目錄名看似可清除；路徑以腳本位置推算，各 worktree 各一份） |
| F6 | **(a)**：`authoritative-venue-repair` 的 `proposal.md` L50、L183 與 `tasks.md` L9 三處改寫，權威指向 `.github/prompts/authoritative-venue-repair.prompt.md`＋`proposal.md`＋`tasks.md` |
| F7 | 核准：`plan-critic.agent.md` L102 一併改為「不執行檔案修改工具，批評以文字回傳」 |

### 4.6 Phase A 驗證證據（2026-10-07，Claude Code `2.1.291`）

一次性腳本都放在 session scratchpad（`gen_digest.py`、`cmp_digest.py`、`frontmatter_diff.py`、`hit_union.py`），未進 repo。

**A-R1 分類帳**（plan §5 三條 negative search＋語意同義詞 `session[ _-]memory|memories|copilot[-_ ]tracking|session[ -]plan|plan\.md`，範圍 `AGENTS.md CLAUDE.md .github/copilot-instructions.md .github/agents .github/prompts .github/instructions .github/skills .claude .agents`；NS1 另含 `docs`）。聯集為 **37 檔、99 行**（`hit_union.py`，修改後、寫入本節前）。`CLAUDE.md`、`.github/copilot-instructions.md`、`.agents/` 無命中。

| 檔案 | 行 | 分類 | 說明 |
|---|---|---|---|
| `AGENTS.md` | 54 | active，符合新契約 | 對照表左欄標「legacy 路徑，僅供閱讀舊檔」 |
| `.github/agents/architect.agent.md` | 7、10、80、1168、1173、1175 | active，符合新契約 | 新路徑 `docs/specs/active/<slug>/plan.md`／`~/.ai-notes/ttr/plan.md` |
| `.github/agents/plan-critic.agent.md` | 7、10、21、31、101 | active，符合新契約 | 同上；L37、L102、L105 改為以文字回傳，已無路徑字樣 |
| `.github/agents/researcher.agent.md` | 19、103、142 | active，腳本介面（F5） | `.copilot-tracking/research/{candidates,sources}/` 為 `scraper/researcher.py`／`update_source.py` 的 I/O，非 session state |
| `.github/agents/researcher.agent.md` | 156 | active，符合新契約 | log 改寫 `~/.ai-notes/ttr/research/`；舊 log 標 legacy 只讀 |
| `.github/agents/campaign-closer.agent.md` | 88 | active，legacy 唯讀檢查 | 不新增，新待辦指向來源 1 |
| `.github/agents/scraper-expert.agent.md` | 192 | active，legacy 標註 | staging 排除 |
| `.github/instructions/git.instructions.md` | 140、143、147、149 | active，符合新契約 | 新契約表（L140 為通用檔名 `plan.md`）、legacy 列、F5 例外、gitignore 說明 |
| `.github/prompts/admin-qa-cleanup.prompt.md` | 38、138 | active，限制句 | 「舊 session memory 只能當線索」，符合新契約，不改 |
| `.github/prompts/ledger-topology-reconcile.prompt.md` | 18／47 | active，符合新契約／限制句 | L18 新措辭；L47 不改 |
| `.github/prompts/workstream-audit.prompt.md` | 21／16 | active，符合新契約／限制句 | L21 新措辭；L16 不改 |
| `.github/skills/agents/researcher/SKILL.md` | 51 | active，腳本介面（F5） | 同 researcher agent |
| `.github/skills/agents/plan-critic/SKILL.md` | 93 | active，符合新契約 | 「不重複 plan.md 全文」，通用檔名 |
| `.claude/agents/architect.md`、`plan-critic.md` | 各 11、12 | active（generated） | 建議提示為新路徑（同義詞 `plan.md` 命中）；與 canonical 一致，`--check` exit 0 |
| `docs/evaluation/campaigns/README.md` | 286 | active，legacy 唯讀檢查 | 標籤 `legacy_tracking_plans` |
| `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` | 303 | active，腳本介面（F5） | Researcher 列註記 |
| `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` | 241–243、270 | historical | 被移除對象清單與搜尋樣式，已加註「非現行規範」 |
| `docs/specs/active/publication-policy/proposal.md` | 119 | historical 標註（權威已改寫） | L118 權威改為 proposal＋tasks＋changes-log |
| `docs/specs/active/publication-policy/tasks.md` | 10／14 | historical 標註／historical | L8–9 權威已改寫；L14 為已勾選的歷史步驟 |
| `docs/specs/active/authoritative-venue-repair/proposal.md` | 50、183 | historical 標註（權威已改寫，F6） | 指向 prompt＋proposal＋tasks |
| `docs/specs/active/authoritative-venue-repair/tasks.md` | 10／26 | historical 標註（F6）／historical | L9–10 權威已改寫；L26 為已勾選的歷史步驟 |
| `docs/specs/active/spec-architecture-dashboard/proposal.md` | 51 | historical 標註（權威已改寫） | 指向 proposal＋tasks |
| `docs/specs/active/admin-reports-204-cleanup/proposal.md`、`tasks.md` | 18、8 | historical（F3 選項 2） | 凍結的 audit history；由 admin-qa-cleanup final reconciliation（其 tasks L349）處理；本 Phase 零 diff |
| `docs/specs/active/admin-qa-cleanup/proposal.md` | 237 | historical（F3 選項 2） | 後繼 spec 的未來待辦清單項，不改 |
| `.github/skills/agents/engineer/history.md` | 310、1822、1827、1830、1833、1834／1824 | historical／historical 標註 | 原文不改；L1824 為新增 superseded 註記 |
| `.github/skills/scraper-expert/history.md` | 102、116 | historical | 已補「非規範」標註 |
| `.github/skills/agents/architect/history.md` | 1004 | historical | 歷史敘述中的 `plan.md` |
| `.github/skills/agents/plan-critic/history.md` | 53 | historical | 歷史敘述中的 `plan.md` |
| `.github/skills/session-analytics/tests/test_campaign_anchor.py`、`fixtures/synthetic_{anomalies,non_anomalies}.jsonl` | 654、22、17 | historical（測試資料） | plan §5：不動 |
| `docs/evaluation/annotator/2026-05-18-baseline-v2.md` | 7 | historical | 下一行已加標註 |
| `docs/specs/security-hardening-plan-RECOVERED.md` | 1／77、444、450 | historical 標註／historical | L1 banner 涵蓋全檔（含未被搜尋樣式命中的 `/memories/repo/` L146、L445、L448） |
| `docs/specs/active/ai-portability/`（notes、plan、proposal、tasks） | 全目錄 | historical／meta | 本 campaign 自身的計畫與證據，描述被移除對象；整個目錄一併分類，涵蓋本節之後新增的行 |

**A-R2**：active guidance 目標檔（`AGENTS.md`、`.github/agents`、`.github/prompts`、`.github/instructions`、`.github/skills/agents/*/SKILL.md`、`.claude`）剩下的命中只有：標 legacy 的行、限制句、新契約路徑、F5 腳本介面（使用者 H-A1 核准的分類）。沒有任何一行要求寫入 Copilot-only state。**PASS**。

**A-R3**（`frontmatter_diff.py`：以 `sync_ai_adapters.parse_frontmatter` 讀 HEAD 版與工作版，各自移除 `handoffs[*].prompt` 後逐 key 比對）：

| 檔案 | keys | 非 prompt 差異 | handoffs／改動的 prompt |
|---|---|---|---|
| `architect.agent.md` | description, handoffs, name | 無 | 5／2 |
| `campaign-closer.agent.md` | description, disable-model-invocation, handoffs, name, tools | 無 | 3／0 |
| `designer.agent.md` | description, handoffs, name | 無 | 4／1 |
| `plan-critic.agent.md` | description, handoffs, name | 無 | 2／2 |
| `researcher.agent.md` | description, handoffs, name | 無 | 4／0 |
| `scraper-expert.agent.md` | agents, description, handoffs, name | 無 | 4／0 |

6 檔全 PASS，exit 0。`git diff -U0` 的 hunk 只落在預定行（architect 7、10、80、1168、1173、1175；closer 88；designer 7、115、120；plan-critic 7、10、21、31、37、101–102、105；researcher 19、103、142、156；scraper-expert 192）。四個 UNDECIDED 中，reviewer 零 diff；architect、researcher、scraper-expert 只有 legacy prose（架構師另有兩個 handoff `prompt`），權限 metadata 不變。

**A-R4**：`rg -n "/memories/|copilot-tracking" .claude .agents` 無輸出（exit 1）。**PASS**。

**A-R5**（`gen_digest.py` 遍歷 `.claude/{agents,commands,skills}` 與 `.agents/skills` 全部檔案）：sync 前 163 檔；第一次 `sync`（`generated 163 files`，exit 0）與第二次 `sync` 的字典 `a=163 b=163 only_a=0 only_b=0 changed=0`。`python3 scripts/sync_ai_adapters.py --check` exit 0（A1 後與 A3 後各跑一次）。**PASS**。

**A-R6**：sync 前後字典差異只有 `.claude/agents/{architect,designer,plan-critic}.md`；`git status --porcelain -- .claude .agents` 同樣只有這 3 檔。⊆ 預期集合。**PASS**。

**A-R7**（依 F3 選項 2 修訂為 4 個 spec）：publication-policy（tasks L8–10、proposal L118–119）、authoritative-venue-repair（proposal L50、L183；tasks L9–10，F6）、spec-architecture-dashboard（proposal L51）已改寫為 checked-in 權威，舊路徑標 historical。admin-reports-204-cleanup 三檔 SHA-256 與修改前相同：`notes.md` `aeec5084…eef7`、`proposal.md` `826c1576…0480`、`tasks.md` `9b550651…ad70`；admin-qa-cleanup 零 diff。**PASS（修訂後範圍）**。

**A-R8**：`git diff --check` 無輸出、exit 0；無 untracked 檔；`git diff --name-only HEAD` 共 32 個路徑，逐一比對 proposal.md 的 Allowed paths（含 plan §4 擴充）全部在內。**PASS**。

**A-R9**：runbook 舊句以 `rg -c` 檢查皆為 0（`| 修改檔案 |` 表頭、Architect／Plan Critic 與 Reviewer 的「禁止」格、`只寫研究輸出 | 禁止`、L315、L316、L333、L334 原句）；13 條新註記各 ≥1。L403 已勾選。**PASS**。

**`scripts/campaign-closeout-audit.sh`**：`shellcheck` 0.11.0 無輸出、exit 0；`bash -n` exit 0。scratchpad disposable fixture（路徑含空格）：有 `.copilot-tracking/plans/p.md`（2 個未勾選）→ `legacy_tracking_plans=2  (legacy .copilot-tracking/plans/*.md unchecked items; read-only)`；無目錄 → `legacy_tracking_plans=0  (no legacy .copilot-tracking/plans directory)`。計數邏輯未變。repo 內沒有其他程式解析舊標籤 `tracking_plans=`。

**R1**：前測已取證（§4.3）；後測 NOT TESTED（待 Phase A commit 後使用者執行 `/context`）。資訊性，不阻擋 B。

### 4.7 Phase B session（2026-10-07）

| 項目 | 值 |
|---|---|
| 執行者 | Engineer（Claude Code `2.1.292`，模型 Claude Opus 5.5 `claude-opus-5-5`）；session 以 `--agent engineer` 啟動（system prompt 為 `.claude/agents/engineer.md` wrapper） |
| 工作目錄 | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree` |
| 依據 | `~/.ai-notes/ttr/phaseB-engineer-prompt.md`、`plan.md` §1、§2、§3、§6、§8、§8.1、§8.2 |
| `plan.md` SHA-256 | `6943c073620e29530581988a79c47e8da84ee34f6ce3edecf2e7511695487bbc`（與指定值相符，未 STOP） |
| Claude Code 版本 | Phase A 為 `2.1.291`，本次 `2.1.292`。B-0／C-0 尚未執行，沒有需要重跑的 fixture |

#### R1 後測（`/context`，資訊性）

使用者在本 session 開頭、尚未給任何指示前執行 `/context`（Phase A commit `ecfb7347` 之後的新 session，位於 worktree）。Memory files 段：

| Type | Path | Tokens |
|---|---|---|
| Project | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/CLAUDE.md` | 189 |
| Project | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/AGENTS.md` | 3.3k |

同一輸出：模型 `claude-opus-5-5`；Custom agents 來源 `.claude/agents/`，16 個。

佐證（唯讀）：worktree 與主工作樹的 `CLAUDE.md` 位元組相同（403 bytes）；`AGENTS.md` 不同（worktree 7276 bytes，主工作樹 7158 bytes），只有 worktree 版含 Phase A 加的「legacy 路徑」字樣（`grep -c` 1 對 0）。前測 3.2k → 後測 3.3k 與 Phase A 對 `AGENTS.md` L54 的增補一致。

**結果**：前測與後測都載入 **worktree 版**，一致；plan §3 R1 所述「載入主工作樹版本」在兩次實測都未出現。資訊性項目，已勾選 `tasks.md`。

#### Worktree 閘門（Phase B）

| 檢查 | 結果 |
|---|---|
| `git worktree list --porcelain` 中的本 worktree | `worktree …/ttr-ai-portability-worktree`、`HEAD ecfb73472e718785a64e6c505a4915fd2e8f08b5`、`branch refs/heads/feat/ai-portability` |
| `pwd -P`／`git branch --show-current` | 與上列路徑、`feat/ai-portability` 相符 |
| 本 worktree `git status --porcelain` | 無輸出（乾淨） |
| 主工作樹 `git -C "<主工作樹>" --no-pager status --short` | 無輸出（無他人 WIP）；branch `main`，HEAD `4e5f1f13dac393a5eccd790e5d2181b4adc84d44` |
| `.git/info/exclude` | 第 15 行有 `ttr-ai-portability-worktree/` |

#### Step 0 漂移檢查（Phase B）— **STOP：非預期漂移**

| 項目 | 值 |
|---|---|
| HEAD | `ecfb73472e718785a64e6c505a4915fd2e8f08b5`（chore(ai): remove legacy Copilot state paths）＝ 預期值 |
| 工作樹 | 乾淨 |
| fetch 前本機快取的 origin/main | `2c142c2464b428e3785007952808d725110e709e`（＝ Phase A remote baseline） |
| `git fetch origin` | 成功；worktree FETCH_HEAD mtime `2026-10-07T14:41:40+09:00`（`05:41:40Z`）；`2c142c24..67846c18 main -> origin/main`（另更新 `origin/claude/remove-connpass-doorkeeper`） |
| fetch 後 origin/main（Phase B remote baseline） | `67846c183c761350687081774f3435df5e5003aa`（docs(researcher): document research exclusion list and migration 097） |
| `git merge-base HEAD origin/main` | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| `ed09bece`、`2c142c24` 是 origin/main 的祖先 | 是（`git merge-base --is-ancestor` 皆 exit 0）；origin/main reflog 最新四筆皆為 `fetch origin: fast-forward` |
| `git rev-list --left-right --count HEAD...origin/main` | `3	8`（ahead 3／behind 8） |
| `2c142c24..origin/main` | `67846c18`、`d391915e feat(researcher): add research exclusion list; retire Doorkeeper events`、`c23b27ac chore(scraper): remove Connpass and Doorkeeper sources`（作者 `Claude`，2026-10-06） |

**與 Phase B 路徑的重疊**（`git diff --name-only 2c142c24 origin/main -- scripts/sync_ai_adapters.py .github/agents .claude .agents AGENTS.md CLAUDE.md scripts/tests`）：

| 檔案 | 上游變更 | 對 Phase B 的影響 |
|---|---|---|
| `.github/agents/subagents/scraper-community-platforms.agent.md` | **刪除**（`c23b27ac`，78 行） | 這是 plan §6 角色表 full 列「3 個 scraper subagent」之一，屬 12 個受管 agent。Phase B 預定在此檔加 `claude-role`，rebase 時會成為 modify/delete 衝突 |
| `.claude/agents/community-platforms-scraper.md` | **刪除**（generated wrapper） | wrapper 數 16 → 15 |
| `.github/agents/scraper-expert.agent.md`（UNDECIDED） | frontmatter `agents:` 移除 `Community Platforms Scraper`（L7）；本文 L88、L92 移除對應分派行 | `agents:` 屬 plan §1 表列的權限 metadata。B-R5 擴充以 A commit `ecfb7347` 為零 diff 基準；rebase 後此檔必然與 `ecfb7347` 不同（差異來自上游，不是 B） |
| `.github/agents/researcher.agent.md`（UNDECIDED） | 本文 L115（origin/main 版 L115–116）：移除 Connpass、Doorkeeper，新增「不得提案 `scraper/research_exclusions.py` 所列平台」（`67846c18`） | 同上：rebase 後與 `ecfb7347` 不同 |
| `AGENTS.md` | 角色路由表刪除 Community Platforms Scraper 列 | Phase B 也要改 `AGENTS.md`（角色權限說明） |
| `.claude/skills/community-platforms/SKILL.md`、`.agents/skills/community-platforms/SKILL.md` | 刪除（對應 `.github/skills/sources/community-platforms/SKILL.md` 刪除） | B-R5 的 skills 零 diff 以 HEAD 為基準，本身不受影響 |

數量（`git ls-tree`）：HEAD 有 agent source 16、wrapper 16；origin/main 為 15、15。

衝突模擬（只在記憶體內，未改 ref、index 或工作樹）：`git merge-tree --write-tree --name-only --messages origin/main HEAD` exit 0，tree `63b59a09…`，自動合併 `researcher.agent.md`、`scraper-expert.agent.md`、`researcher/SKILL.md`、`AGENTS.md`，**目前沒有文字衝突**；合併後 agent source 15、wrapper 15。執行後 `git status --porcelain` 仍為空、HEAD 仍為 `ecfb7347`。

**判定：非預期漂移，STOP**。與 Phase 0、Phase A 的判定不同，這次上游 commit 直接改到 Phase B 的目標：

1. 受管 agent 少一個：plan 與 prompt 寫死的「16 個 wrapper」「12 個受管 agent」「3 個 scraper subagent」「B-R3：數量 = 16」「測試 6：`== 16`」在 origin/main 上不成立（應為 15／11／2）。
2. 四個 UNDECIDED 中的 `scraper-expert`、`researcher` 被上游修改，其中 `scraper-expert` 改的是權限 metadata（`agents:`）。B-R5 擴充「相較 A commit 零 diff」的基準在 rebase 後需要重新定義。
3. 若照現行 base 做 B，merge-back rebase 時 `scraper-community-platforms.agent.md` 會出現 modify/delete 衝突，且寫死 16 的測試會失敗。

plan §8.2 原則 2：分流沒涵蓋的情況一律 STOP 回報，不臨場加新設計。本 session 未 rebase、未改 base，未進入 H-B1、B-0 或任何實作；除本段與 `tasks.md` 的 R1 勾選外，沒有修改任何 repo 檔案。

**使用者決定（2026-10-07，STOP 後）：選項 1**。內容：

1. 先把本段證據（`notes.md` §4.7、`tasks.md` R1 勾選）做成只含文件的 commit（rebase 需要乾淨工作樹，且禁用 `git stash`）。
2. 在乾淨工作樹上 `git rebase origin/main`（`67846c18`），重跑 `sync --check`，重記 Step 0。
3. Phase B 參數改為 15 個 wrapper／11 個受管 agent／2 個 scraper subagent；B-R5 擴充的零 diff 基準改為 rebase 後的 A commit；上游對 `scraper-expert`、`researcher` 的修改記為上游來源，不是 B。
4. 修訂裁決 6：campaign base `ed09bece` 保留為歷史紀錄；rebase 後實際 merge-base 為 `67846c18`。
5. 完成後進入 H-B1。

另一選項（不 rebase、以 16 個 agent 做 B、merge-back 時再處理）未採用。
