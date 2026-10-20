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

### 4.8 依決定 rebase 與重記 Step 0（2026-10-07，Claude Code `2.1.292`）

| 步驟 | 結果 |
|---|---|
| 證據 commit | `3981ee21` docs(ai): record Phase B drift stop and R1 post-test（只含 `notes.md`、`tasks.md`；pre-commit gitleaks `no leaks found`） |
| rebase 前再 fetch | `git fetch origin` exit 0（`06:25:12Z`）；origin/main 仍為 `67846c183c761350687081774f3435df5e5003aa` |
| rebase 前工作樹 | `git status --porcelain` 為空 |
| `git rebase origin/main` | exit 0，4/4 無衝突；之後 `git status --porcelain` 為空 |
| `git range-diff ed09bece..3981ee21 67846c18..HEAD` | 四個 commit 全為 `=`（patch 內容不變） |

**rebase 後的 SHA 對照**

| commit | 原 SHA | rebase 後 SHA |
|---|---|---|
| docs(ai): add Claude Code migration runbook | `565c1479` | `bbcbdf4f4278a3d4d1934ff2d0ffe48411b4b0fd` |
| docs(ai): add ai-portability spec skeleton | `256e8b9b` | `0eaeef65862eac52dfb8574cbcdb7bd111802635` |
| chore(ai): remove legacy Copilot state paths（**A commit**） | `ecfb7347` | `223d8b4e4cebd4b829f682ad02857b40a5616d57` |
| docs(ai): record Phase B drift stop and R1 post-test | `3981ee21` | `15b81475d971b4c1df8bd2ac9e0dad5db3aac539` |

**重記 Step 0（rebase 後）**

| 項目 | 值 |
|---|---|
| HEAD | `15b81475d971b4c1df8bd2ac9e0dad5db3aac539` |
| origin/main（Phase B remote baseline） | `67846c183c761350687081774f3435df5e5003aa` |
| `git merge-base HEAD origin/main` | `67846c18…`（修訂後的實際 base；`ed09bece` 為歷史 campaign base，依使用者決定修訂裁決 6） |
| ahead／behind | `4	0` |
| agent source／wrapper 數 | 15／15 |
| `plan.md` SHA-256 | `6943c073…7bbc`（不變） |

**rebase 後的一致性檢查**

| 檢查 | 結果 |
|---|---|
| `python3 scripts/sync_ai_adapters.py --check`（sync 前） | exit 0 |
| `python3 scripts/sync_ai_adapters.py` | `generated 160 files`，exit 0；之後 `git status --porcelain` 為空（sync 對 committed 內容為 no-op）。160 = Phase A 的 163 − 1 個 agent wrapper − 2 個 community-platforms skill pointer |
| 四個 UNDECIDED（canonical＋wrapper）的 A diff | `git diff ecfb7347^ ecfb7347` 與 `git diff 223d8b4e^ 223d8b4e` 的 `git patch-id --stable` 相同（`223c2c16…`）：A 的修改原封不動 |
| `ecfb7347` → `223d8b4e` 在四檔上的差異 | 只有 `researcher.agent.md`（+2／−1）與 `scraper-expert.agent.md`（−3）；patch-id 與上游 `git diff 2c142c24 origin/main` 在同四檔上的 patch-id 相同（`2492d350…`）：**差異完全來自上游，不是 A 或 B** |
| `223d8b4e` → HEAD 在四檔上的差異 | 空 |
| Phase A negative search 對上游變更檔的回歸 | 以 `rg -n -i '/memories\|copilot-tracking\|session memory\|memory tool'` 掃 `2c142c24..origin/main` 新增或修改的 20 檔：命中只有 Phase A 已分類的行（行號位移：`AGENTS.md` 54→53、`researcher.agent.md` 142→143、156→157、`scraper-expert.agent.md` 192→189、`scraper/researcher.py` 339→340），無新命中 |

**Phase B 參數修訂（依使用者決定）**：wrapper 16 → **15**；受管 agent 12 → **11**；full 列的 scraper subagent 3 → **2**（peatix、tcc）；B-R3 為「數量 = 15 = `len(agent_sources)`」；B-R5 擴充的零 diff 基準由 `ecfb7347` 改為 rebase 後的 A commit **`223d8b4e`**。`plan.md` 不改（原樣存檔、SHA 固定），以本段為修訂紀錄。

### 4.9 H-B1 前查證（只查、只記錄，2026-10-07；HEAD `15b81475`）

**角色表與 Copilot 類別子集檢查**（依 plan §6，套用 §4.8 的參數修訂；`claude-role` 尚未加入）

| agent（wrapper 名） | claude-role | 預計 Claude `tools:` | Copilot `tools:` | 類別子集 |
|---|---|---|---|---|
| plan-critic | planner | Read, Grep, Glob, WebFetch, WebSearch, Bash, AskUserQuestion（ExitPlanMode 依 B-0(4)） | 未宣告 | 不受判準約束 |
| tester | tester | Read, Grep, Glob, Bash, WebFetch, WebSearch, AskUserQuestion | `[read, search, execute, web]` | {read, search, execute, web} ⊆ 同集合：PASS |
| validate-merge-deploy | vmd | Read, Grep, Glob, Bash, WebFetch, WebSearch, AskUserQuestion | `[read, search, execute, web]` | PASS |
| close-campaign-retire-worktree | closer | Read, Grep, Glob, Bash, AskUserQuestion | `[read, search, execute]` | {read, search, execute} ⊆ 同集合：PASS |
| lianbu-spokesperson | readonly | Read, Grep, Glob, WebFetch | `read_file, semantic_search, grep_search, fetch_webpage`（舊名） | {read, search, web} ⊆ {read, search, web}：PASS |
| engineer、designer、history-teller、update-history-skill-agent、peatix-scraper、tcc-scraper | full | 省略（繼承全部） | 未宣告 | 不受判準約束 |
| architect、reviewer、researcher、scraper-expert | （UNDECIDED，不加） | 不輸出 | 未宣告 | — |

受管 11（planner 1＋tester 1＋vmd 1＋closer 1＋readonly 1＋full 6）＋UNDECIDED 4 = 15。

**消費者查證（F5 型檢查：誰讀 `.github/agents` frontmatter 或 `.claude/agents`）**

`rg -l` 掃 repo（排除 `docs/`、`*.md`）找 `.github/agents`、`agent.md`、`.claude/agents`、`claude-role`、`.claude/settings`：

| 命中 | 用途 | 對 B 的影響 |
|---|---|---|
| `scripts/sync_ai_adapters.py` | generator 本身 | B 的修改對象 |
| `.githooks/pre-commit` (a) | 對 staged `.agent.md`，只在檔內出現 `vscode/getProjectSetupInfo`、`vscode/installExtension`、`execute/runInTerminal` 時，以 regex 移除 frontmatter 的 `tools:` 區塊 | 16 檔目前都沒有這些字樣，不會觸發；不碰 `claude-role`。觸發時的 `\ntools: \[.*?\]\n` 會連 vmd、closer 的 inline `tools:` 一起刪，這是既有行為，與 B 無關 |
| `web/lib/lianbu-persona.ts` L1 | 註解「規格來源：lianbu agent 檔（兩份需同步更新）」 | 指人格本文同步；只加 frontmatter `claude-role` 不需同步 |
| `.github/workflows/monthly_health_check.yml` L67、L138 | step summary 文字提到 reviewer 的兩個路徑 | reviewer 不改 |
| `web/public/202606/normativity-design/index.{zh,en}.html` | 指向 `scraper-expert.agent.md#L20-L24` 的靜態 GitHub 連結 | scraper-expert 不改 |
| `.gitignore` L39 | `.claude/settings.local.json` | B 新增的 `.claude/settings.json` 不在忽略清單內，可提交 |

`scraper/skill_scanner.py` 只掃 `.github/skills/agents/*/SKILL.md`，不讀 agent 檔。其他 `scraper/*.py`、`scripts/*.py` 對 `.github` 的引用都與 agent frontmatter 無關。沒有其他程式讀 `.claude/agents`。

**受限角色本文的寫檔指示（plan 未涵蓋）**

| agent | 位置 | 內容 | 投影後 |
|---|---|---|---|
| tester | L39–40 | 「After Fixing Any Error」：在 `tester/history.md` 頂部加條目、必要時改 `SKILL.md` | 工具層無 Edit／Write；只能經 Bash 重導（C-R11 殘餘風險，且違反 L24「Does NOT write code」的角色意圖） |
| plan-critic | L96–97 | 同上（`plan-critic/history.md`、`SKILL.md`） | 同上；與 L102「不執行檔案修改工具」本來就衝突 |
| lianbu-spokesperson | L133–134 | 同上（`lianbu-spokesperson/history.md`、`SKILL.md`） | readonly 沒有 Bash，完全無法寫 |

validate-merge-deploy L128 對 rebase 衝突是「指導用戶解決」，不需要 Edit。closer 的結案寫檔由 C-R7／裁決 12 處理。

**reviewer（X2）工具需求**：本文 L49–57 以 Bash 執行 `python` 查 Supabase（service role），L109–124 執行 `git -C … status`、`/bin/pwd`。plan 角色表的 readonly（Read、Grep、Glob、WebFetch）會讓 reviewer 無法運作；若提前投影，需要的是 tester 型白名單（含 Bash、無 Edit／Write／NotebookEdit），plan 沒有對應的角色。

**其他**

- `.claude/` 在 worktree 只有 `agents`、`commands`、`skills`，沒有任何 settings 檔。主工作樹有 gitignored 的 `.claude/settings.local.json`（156 bytes，未讀內容；只影響在主工作樹啟動的 session）。使用者層 `~/.claude/settings.json` 沒有 `permissions` 鍵（僅 `enabledPlugins`、`extraKnownMarketplaces`、`model`、`modelSettings`、`theme`），沒有放行 `git push` 的 allow 規則。
- 主工作樹 `.claude/agents` 仍是舊的 16 個 wrapper（含 `community-platforms-scraper.md`），worktree 為 15 個。B-R4 的 `/agents` 若列出 `community-platforms-scraper`，即表示載入了主工作樹的檔案（§8.2 #8：STOP，查 R2）。
- 本 session 在 auto mode 下執行（Bash 由分類器自動核准）。`permissions.ask` 在 auto mode 下是否仍跳出提示，plan 沒有寫到；B-0(6)／B-R6 的實測需涵蓋使用者平常使用的模式。
- runbook 的「Phase B agent permission matrix 已投影並有 negative tests」在 Phase A 後位於 **L410**（plan 寫 L404，為 Phase A 前行號）。
- pytest：`python3 -m pytest --version` → `pytest 9.0.3`（`python3` 為 `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python3`，Python 3.14.3）。`scripts/tests/` 尚不存在；repo 內 conftest 只在 `scraper/tests/` 與 `.github/skills/session-analytics/tests/`。

### 4.10 H-B1 決定（使用者，2026-10-07；部分）

| 項目 | 決定 |
|---|---|
| a. 角色表（§4.9，受管 11＋UNDECIDED 4） | 核准 |
| b. X2（reviewer 提前投影） | **選項 1：延期**。依裁決 2 不動 reviewer；B-R5 擴充維持四檔零 diff；「reviewer 改投影為 readonly」維持為後續項目（另註：reviewer 本文需要 Bash，plan 的 readonly 角色不適用） |
| c. `AGENTS.md` 角色工具限制段的措辭 | 核准（新段「角色工具限制（Claude Code）」置於「Skills wrappers」前；最終措辭依 B-0 結果調整，在 H-B3 再呈報） |
| d. `.claude/settings.json` 內容與 settings 測試位置 | 待決 |
| e. 使用者實測步驟草案 | 待決 |
| f1. 受限角色本文的 history.md／SKILL.md 寫檔指示 | 待決 |
| 「reviewer 去留」是否列後續項目 | 待決（Engineer 於回答使用者提問時提出） |

使用者在決定前詢問了 UNDECIDED 的套用內容、reviewer 現況、B-0(6) 涉及的 agent 與 Claude 術語；Engineer 以唯讀查證回答：`docs/monthly_review/*.md`、`docs/skill_scan/*.md` 皆由 `monthly_health_check.yml` 產生，非 reviewer 輸出；reviewer 沒有 SKILL／history 資料夾；agent 檔最後實質更新 2026-08-11（`0053daa0`）。已安裝版本的 `--permission-mode` 選項為 `acceptEdits`、`auto`、`bypassPermissions`、`manual`、`dontAsk`、`plan`（`claude --help`）。

B-0 spike 只在 session scratchpad 進行、不改 repo 檔案，因此在 d／e／f1 待決期間先執行；結果記入下一段。

### 4.11 B-0 spike 結果（2026-10-07，Claude Code `2.1.292`，模型 `claude-opus-5-5`）

**環境**：disposable fixture 在 session scratchpad `…/scratchpad/b0 spike/`（路徑含空格；不在 worktree 內）：`proj/`（`git init -b main`，一個 commit，`origin` 指向同層的本機 bare repo `remote.git`）、`proj/.claude/agents/fixture-{tester,planner,planner-exit,full,disallow,readonly}.md`、`proj/.claude/settings.json`（每個測試改寫 `permissions`；固定含一個把 PreToolUse stdin 存檔的 logging hook）。所有 `claude` 以 `env -i HOME PATH USER LOGNAME SHELL TERM LANG TMPDIR claude … < /dev/null` 啟動（本 session 會繼承 `CLAUDE_CODE_AGENT=engineer`、`CLAUDE_CODE_CHILD_SESSION=1` 等變數，`env -i` 一併清除；`ANTHROPIC_API_KEY` 亦不傳入），一律 `-p --output-format stream-json --verbose --permission-prompts none`（會跳出提示的動作自動拒絕）。push 一律 `git push --dry-run origin main` 到本機 bare remote；結束時 `git ls-remote remote.git` 為 0 筆。未對本 repo 的 origin 做任何 push。原始輸出在 `b0 spike/out/*.jsonl`、`hooklogs-{main,sub}/`（scratchpad，不進 repo）。

**文件查證（WebFetch，2026-10-07）**：`code.claude.com/docs/en/sub-agents`（frontmatter 欄位）、`/permissions`（規則語法與優先序）、`/tools-reference`（工具名）。

| 項目 | 結果 | 證據 |
|---|---|---|
| (1) subagent frontmatter 支援欄位 | **PASS**（`tools`、`disallowedTools` 實測；`permissionMode`、`hooks` 依文件） | 文件列出 `tools`、`disallowedTools`、`model`、`permissionMode`、`maxTurns`、`skills`、`mcpServers`、`hooks`、`memory`、`background`、`omitClaudeMd`、`effort`、`isolation`、`color`、`initialPrompt`、`experimental`；`tools` 可為逗號字串或 YAML list，省略時繼承全部。實測：`fixture-disallow`（`disallowedTools: Write`）的 init 工具清單少了 `Write`、其餘同 full（T0d）。`permissionMode`、`hooks` 欄位 B 不使用，未實測 |
| (2a) `tools:` 在 `claude --agent` 主執行緒 | **PASS** | init 事件的工具清單：`fixture-tester`、`fixture-planner` 都只有 `Read, Bash, WebFetch, WebSearch`（T0、T0f）；full 有 `Write`、`Edit`、`NotebookEdit` 等（T0c）。實際嘗試（acceptEdits）：tester（T1）、planner（T3）回報 `NO_WRITE_TOOL`、沒有 Write 呼叫、檔案未建立；full 對照組（T2）Write 成功建立 `w_full_main.txt` |
| (2b) `tools:` 在 subagent | **PASS**（證據為 subagent 自述＋無 Write 呼叫＋檔案不存在＋對照組） | 主 session 以 Agent 工具呼叫：tester（T4）、planner（T6）的 subagent 事件中沒有 Write 呼叫，自述工具為 `Read, Bash, WebFetch, WebSearch`，`w_tester_sub.txt`、`w_planner_sub.txt` 不存在；full 對照組（T5）subagent 呼叫 Write 成功。subagent 沒有 init 工具清單可看，這是本項證據的限制 |
| (3a) hook stdin，`--agent` 主執行緒 | **可辨識** | `agent_type` = 角色名（`fixture-tester`／`fixture-full`／`fixture-planner`），**沒有** `agent_id`（hooklogs-main，4 筆） |
| (3b) hook stdin，subagent | **可辨識** | subagent 內的呼叫有 `agent_type`（角色名）＋`agent_id`（如 `a43ead5bb2ae1f56f`）；主 session（未帶 `--agent`）的呼叫兩者皆無（hooklogs-sub，7 筆）。`CLAUDE_PROJECT_DIR` 解析為 fixture 的 `proj`（含空格路徑）。C-0(3) 仍須在 C 正式實測 |
| (4) plan mode 相容性 | **NOT TESTED**（交使用者互動實測） | `-p --permission-mode plan` 時 init 工具清單**沒有** `ExitPlanMode`（planner、planner-exit、full 皆然：T0h–T0j），非互動模式無法驗證；依 plan §8.2 #5 交使用者 |
| (5) Copilot 對 `claude-role` | **NOT TESTED**（交使用者） | — |
| (6) `permissions.ask` 語法 | **PASS：兩種都有效** | 文件：`:*` 與尾端 ` *` 等價、對話框寫空白形式。實測（allow 由 `--settings` 給、ask 放 project settings）：`Bash(git push:*)`（Q2）、`Bash(git push *)`（Q3）都讓原本會執行的 push 變成「需要核准」 |
| (6) 優先序 deny > ask > allow | **PASS** | 對照組 Q1（只有 allow）push 實際執行；Q2／Q3（allow＋ask）→ 需要核准；Q9（allow＋ask＋deny）→ `Permission to use Bash with command … has been denied.`（與 ask 的「requires approval」訊息不同）。與文件「Rules are evaluated in order: deny, then ask, then allow」一致 |
| (6) subagent 內的 Bash 是否受專案 permissions 約束 | **PASS：受約束** | 對照組 Q5（只有 allow）subagent 的 push 實際執行；Q4（allow＋project ask）subagent 的 push → 需要核准、未執行 |
| (6) `--agent` 主執行緒 | **PASS** | Q6（allow＋ask，`--agent fixture-full`）→ 需要核准 |
| (6) auto mode | **ask 在 auto mode 下仍要求核准** | Q8（auto，無任何規則）與 Q8b（auto，只有 allow）：`git push --dry-run` 由分類器放行、**沒有提示**直接執行；Q7（auto＋allow＋project ask）→ 需要核准。即使用者日常的 auto mode 下，B 的 ask 規則是 push 前唯一的提示來源 |
| (6) push 變體（auto＋project ask，V1） | **PARTIAL（如 plan 預期）** | `X=1 git push …`、`env X=1 git push …` → 需要核准（後者是 ask 規則或 auto 分類器所致，本測試無法區分）；**`git -C . push …`、`bash -c "git push …"` → 直接執行**（與文件「What a Bash rule doesn't match」一致）。依 plan 合法 carry-over 表，變體由 C-R5 處理 |
| (7) fallback | 目前不需要 | (2)(3)(6) 皆已證實；(4)(5) 待使用者 |
| (8) `/agents` 來源路徑 | **NOT TESTED**（交使用者，B-R4） | — |

**計畫未涵蓋的觀察**

1. **Grep、Glob 在 macOS 預設不存在**（文件 tools-reference：「On macOS, Linux, and WSL, Claude Code leaves Glob and Grep out of the default tool set, and Claude searches with `find` and `grep` through the Bash tool instead」）。只有在 `tools:` 列了它們**且沒有 Bash** 時才會出現。實測：保留 Bash 的 tester／planner 投影中，`Grep`、`Glob` 被靜默略過（搜尋改經 Bash）；readonly（`Read, Grep, Glob, WebFetch`，無 Bash）的 init 清單為 `Read, WebFetch, Grep, Glob`（T0g）。結論：plan 的白名單照列 `Grep`、`Glob` 無害，且對 lianbu 是必要的；Copilot「search」類別的對照仍成立。
2. **`AskUserQuestion` 在 `-p` 模式的工具清單中不存在**（含 full）。推測是非互動模式不提供；互動模式（本 session）有此工具。白名單照列。
3. **未信任的 workspace 會忽略 project settings 的 `allow`**（`Ignoring 1 permissions.allow entry from .claude/settings.json: this workspace has not been trusted …`），但 project 的 `ask`／`deny` 照常生效（Q2–Q4、Q9）。B 只用 `ask`，不受影響。
4. **`.claude/settings.local.json` 從 git 主 checkout 載入**（文件：「resolved through worktrees to the main checkout」），所以主工作樹的 `.claude/settings.local.json` 也作用於本 worktree 的 session。其內容只有兩條與 push 無關的 allow（`Bash(shasum -a 256 ~/.ai-notes/ttr/plan-rev6.md)`、`Read(//Users/flyingship/.ai-notes/ttr/**)`）；且 ask 優先於 allow，不影響 B 的 push 閘門。
5. 第一次 P1–P3（allow 放在 project settings）因第 3 點而無效，已以 Q1–Q3 重做；P1–P3 輸出保留在 scratchpad 但不作為證據。

**對 B 的 Required 的影響**

- B-R7（planner）：(2a)(2b) PASS；仍待 B-0(4) 才能判定 PASS 或 P2。
- B-R8（tester）：(2a)(2b) 兩情境 PASS → 不需 T1 carry-over。
- B-R6：ask 規則在主執行緒、`--agent`、subagent、auto mode 都會要求核准（`-p` 以自動拒絕呈現）；互動提示是否真的出現仍待使用者實測。變體 carry-over 到 C-R5。
- C-R9 的前置（B-0(3)）：兩情境都可辨識；C-0(3) 仍為正式實測。

**使用者實測用 fixture**（scratchpad `…/scratchpad/b0 user fixture/`，路徑含空格）：`proj/`（`git init -b main`、commit `37d8848`、`origin` = 同層 bare `remote.git`）；`proj/.claude/settings.json` 內容與 B 預定提交的相同（只有 `permissions.ask: ["Bash(git push:*)"]`，無 hooks）；`proj/.claude/agents/fixture-{full,planner,planner-exit}.md`；`proj/.github/agents/fixture-tester.agent.md`（含 `claude-role: tester` 與 Copilot `tools: [read, search, execute, web]`，供 B-0(5)）。

### 4.12 H-B1 決定（使用者，2026-10-07；完成）

接續 §4.10：

| 項目 | 決定 |
|---|---|
| d. `.claude/settings.json` 內容與 settings 測試位置 | 核准：`{"permissions": {"ask": ["Bash(git push:*)"]}}`（B-0(6) 已證實此語法有效）；測試放 `scripts/tests/test_claude_settings.py` |
| e. 使用者實測步驟 | 核准：寫入 `tasks.md`（B-0(4)、B-0(5)、B-R6 使用 §4.11 的使用者 fixture；B-R4 在實作後於 worktree 執行） |
| f1. 受限角色本文的 history.md／SKILL.md 寫檔指示 | 採建議：B 不改 agent 本文；教訓以文字回報，交 Update History, Skill, Agent 或使用者寫入；`AGENTS.md` 角色工具限制段加一句說明；列入 `tasks.md` 後續項目 |
| reviewer 去留 | 列入 `tasks.md` 後續項目（reviewer 重新定位） |

H-B1 完成，開始實作。

### 4.13 Phase B 實作與驗證（2026-10-07，Claude Code `2.1.292`；未 commit）

**實作**

| 檔案 | 變更 |
|---|---|
| `scripts/sync_ai_adapters.py` | 新增 `ROLE_TOOLS`、`UNDECIDED_AGENTS`、`COPILOT_TOOL_CATEGORIES`、`CLAUDE_TOOL_CATEGORIES`、`GENERIC_CLAUDE_TOOLS`、`copilot_tools()`、`role_problems()`；`agent_outputs()` 對有白名單的角色在 wrapper frontmatter 加 `tools:` 一行；`main()` 在 `--check` 時把 role 問題算入失敗，寫入模式遇到 role 問題時不寫檔、exit 1。保留 MARKER、`pinned_models()` 與既有函式，沒有第二套 generator |
| 11 個受管 agent | frontmatter 只在 `description:` 下一行新增 `claude-role`（planner：plan-critic；tester；vmd；closer；readonly：lianbu；full：engineer、designer、history-teller、update-history、scraper-peatix、scraper-tcc） |
| `.claude/agents/` | 5 個受限 wrapper 各多一行 `tools:`；full 與 UNDECIDED 的 wrapper 不變 |
| `AGENTS.md` | 新段「角色工具限制（Claude Code）」（H-B1 c 核准的措辭，含 f1 的說明句；放在「Skills wrappers」前） |
| `.claude/settings.json` | 新增，內容只有 `{"permissions": {"ask": ["Bash(git push:*)"]}}` |
| `scripts/tests/conftest.py`、`test_sync_ai_adapters.py`、`test_claude_settings.py` | 新增 |
| `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` L410 | 不勾選，加註「部分（X1–X4 延期）：11 個受管 agent 已投影；…未投影」 |

plan 文字以外的兩個實作細節（H-B3 呈報）：(1) 在 `UNDECIDED_AGENTS` 的 agent 若被加了 `claude-role`，`--check` 失敗（避免常數與 frontmatter 不一致）；(2) sync 寫入模式遇到 role 問題時不寫檔（避免把設定錯誤的 agent 寫成繼承全部工具的 wrapper）。

**驗證**

| ID | 狀態 | 證據 |
|---|---|---|
| 加 role 前的負向證據 | — | 只改 generator、尚未加 `claude-role` 時，`--check` exit 1，列出恰好 11 行 `missing claude-role …`，四個 UNDECIDED 不在其中 |
| frontmatter-diff（11 檔） | PASS | 以 `parse_frontmatter` 比較 HEAD 與工作版：每檔只多 `claude-role`，其他 key 無增減、無改值，本文 bytes 相同（`fm_diff_b.py`，scratchpad） |
| pre-commit (a) | 不會觸發 | 變更的 `.agent.md` 皆不含 `vscode/getProjectSetupInfo`、`vscode/installExtension`、`execute/runInTerminal` |
| sync／`--check` | PASS | `generated 160 files`、`--check` exit 0；連跑兩次 sync，`.claude/{agents,commands,skills}`＋`.agents/skills` 全檔 sha256 摘要相同（`25ab2b3e…`） |
| B-R1 | 待使用者 | (1)(2)(3)(6) 已記錄（§4.11）；(4)(5)(8) 為 NOT TESTED，分流已定（`tasks.md` U1、U2、U4） |
| B-R2 | **PASS** | `python3 -m pytest scripts/tests -q` → `24 passed`（pytest 9.0.3）。涵蓋 plan §6 測試 1–7：角色投影、未知 role、缺 role、UNDECIDED 加 role、寫入模式拒寫；tester 投影加 Write → `--check` 失敗（R4-3 負向）、planner 加 Write（fallback-P）→ 通過；full 套在有 Copilot `tools:` 的 agent → 失敗；未知 Copilot token → 失敗並指出 token；lianbu 舊名對照；注入 `model:` → 失敗；手改 wrapper → `changed`；冪等＋stale MARKER 檔移除＋非生成檔不動；wrapper 數 15、名稱唯一；settings 測試 5 項 |
| B-R3 | **PASS** | `agent_sources` 15、`agent_outputs` 15、磁碟上 wrapper 15、名稱唯一 |
| B-R4 | PASS-pending-user | U4 |
| B-R5 | **PASS** | `git diff --stat -- .agents .claude/skills .claude/commands` 為空、其下無未追蹤檔；`git diff --exit-code 223d8b4e -- `四個 UNDECIDED 的 canonical 與 wrapper → exit 0 |
| B-R6 | PASS-pending-user | settings 測試 PASS；B-0(6) 已證實規則在主執行緒、subagent、auto mode 都會觸發（§4.11）；互動提示待 U3。變體 carry-over 到 C-R5 |
| B-R7 | 待使用者（U1） | (2a)(2b) PASS；B-0(4) 決定 PASS 或 P2 |
| B-R8 | **PASS** | B-0(2a)(2b) 兩情境 tester 均無 Write；投影不含 Edit／Write／NotebookEdit（測試鎖定） |
| B-R9 | **PASS（已記錄）** | `claude doctor`（worktree，`env -i`）：`Running: native (2.1.292)`、`Search: OK (bundled)`、`No installation issues found.`。CLI doctor 不驗證 settings 內容；settings 的有效性由 B-0(6) 與 U3 佐證 |
| B-R10 | **PASS** | scratchpad 副本 baseline `--check` exit 0；在 tester frontmatter 注入 `model: claude-sonnet-4-5` 後 `--check` 印出 `pinned model .github/agents/tester.agent.md:5: …`，exit 1 |
| `git diff --check` | PASS | exit 0；4 個新檔以 `git diff --no-index --check` 檢查無問題 |
| diff 路徑 ⊆ Allowed paths | PASS | 25 個路徑（21 修改＋4 新增）全部落在 proposal.md Allowed paths（含 `scripts/tests/`） |
| gitleaks | PASS | `git diff HEAD`＋新檔內容經 `gitleaks stdin --redact -c .gitleaks.toml`（8.30.1）：`no leaks found` |

### 4.14 使用者實測 U1｜B-0(4) plan mode（2026-10-09，Claude Code `2.1.292`）

使用者在新終端機、使用者 fixture（`b0 user fixture/proj`）中執行，依 `tasks.md` U1。Engineer 另以唯讀方式讀取兩次的 session transcript（`~/.claude/projects/-private-tmp-…-b0-user-fixture-proj/{d19ac63c…,23d5579f…}.jsonl`）判定。

| 輪次 | agent（白名單差異） | 工具呼叫 | 結果 | `ls -lt ~/.claude/plans \| head -3` |
|---|---|---|---|---|
| 1 | `fixture-planner`（無 Write、無 ExitPlanMode） | 只有一次 Bash（`ls -la; cat -A hello.txt`） | **無法提交**：模型回覆「這次對話沒有提供 Write 和 ExitPlanMode 工具。所以我沒辦法把計畫寫進 `/Users/flyingship/.claude/plans/hello-txt-world-typed-pnueli.md`，也沒辦法正式提交核准」，改以文字列出計畫。未出現核准提示（使用者描述「計劃成功」指的是文字計畫） | 無新檔（最新仍為 Oct 4 的兩個檔） |
| 2 | `fixture-planner-exit`（無 Write、有 ExitPlanMode） | 只有一次 Bash | **無法提交**：「計畫模式要求先把計畫寫進 `/Users/flyingship/.claude/plans/hello-txt-world-cached-sky.md`，再呼叫 ExitPlanMode，而這次工作階段裡沒有可以寫檔的 Write 工具」。未出現核准提示 | 無新檔 |

兩輪都沒有改用 Bash 寫檔，也沒有修改 fixture 的任何檔案。

**判定：B-0(4) 不相容**。在此版本，plan mode 的提交流程需要 **Write**（把計畫寫入 `~/.claude/plans/<name>.md`）**與 ExitPlanMode**（兩者都必須在白名單中；未列出時 ExitPlanMode 不提供）。依 plan §6 B-0(4) 與 §8.2 #5 的分流：「不行 → fallback-P＋C-R10 planner 分支」，即 B-R7 落入 **P2**。

**計畫未涵蓋的觀察**：runbook 只以 `--permission-mode plan` 啟動 Architect（L66–67、L542–543；Architect 是 UNDECIDED，繼承全部工具，不受影響）；沒有任何文件以 plan mode 啟動 plan-critic，plan-critic 的產出依裁決 1 以文字回傳。兩輪中模型仍以文字完整產出計畫，只是無法走正式核准流程。是否仍照 plan 套用 fallback-P，交使用者決定（H-B2）。

### 4.15 H-B2 中途決定：plan-critic 與 plan mode（使用者，2026-10-09）

使用者詢問 plan mode 是否為 Claude 專屬、以及如何用 GPT 評審計畫。Engineer 依本 campaign 實際做法回答（第 2～6 輪評審皆由 GPT／Codex 以 `codex exec -s read-only -C <worktree> -o ~/.ai-notes/ttr/critique-N-codex.md -` 讀計畫檔產出，見 `~/.ai-notes/ttr/critique-6-prompt.md`），結論是跨模型評審不使用 Claude 的 plan mode（`~/.claude/plans/` 為工具私有、非權威）。

**決定**

| 項目 | 決定 |
|---|---|
| B-0(4) 不相容的處理 | **選項 2（修訂計畫，不採 plan §6 的 fallback-P）**：plan-critic 不在 plan mode 使用；planner 白名單維持 `Read, Grep, Glob, WebFetch, WebSearch, Bash, AskUserQuestion`，不加 Write、不加 ExitPlanMode |
| B-R7 通過條件 | 修訂為「plan-critic 在 `claude --agent` 主執行緒與 subagent 兩情境，工具層都沒有 Edit／Write／NotebookEdit」；原條件中的「B-0(4) 證實 plan mode 不含 Write 仍可寫私有 plan」移除。依 §4.11 B-0(2a)(2b) → **PASS**。不需 P1／P2 carry-over，C 的 C-R10 planner 分支不再是 Required（C-R9 仍依 plan） |
| `AGENTS.md` | 角色工具限制段新增「plan-critic 不在 Claude Code 的 plan mode 使用…以一般模式啟動（`claude --agent plan-critic`），讀計畫檔後以文字回傳批評」 |
| `AGENTS.md` 的 Codex 措辭 | 由「Codex 沒有工具層限制」改為「Codex 沒有依角色的工具限制，只靠各 agent 檔內文的角色規則；需要唯讀時（例如請 Codex 評審計畫），由使用者以 `codex -s read-only` 啟動」（Engineer 發現原句不精確：Codex 可在啟動時設唯讀 sandbox） |

`plan.md` 不改（原樣存檔），以本段為修訂紀錄。runbook L339「planner 角色以 Write／Edit 在 repo 內建立檔案時被拒絕（plan mode 私有 plan 檔不計…）」與本決定一致，不需修改。

### 4.16 使用者實測 U2｜B-0(5) Copilot 對 `claude-role` 的反應（2026-10-09，VS Code `1.139.1`）

| 步驟 | 結果 |
|---|---|
| 以 VS Code 開啟使用者 fixture `proj` | 一開始 agent 選單看不到「Fixture Tester」 |
| 排查 | repo、主工作樹與使用者層的 VS Code 設定都沒有改變 agent 檔探索位置的 chat 設定（預設 `.github/agents`）。Engineer 在 fixture 加入對照組 `fixture-control.agent.md`（與 Fixture Tester 相同，只少 `claude-role`） |
| 信任資料夾（離開 Restricted Mode）＋ `Developer: Reload Window` | agent 選單**同時出現** Fixture Tester 與 Fixture Control → 一開始看不到是受限模式／未重新載入所致，與 `claude-role` 無關 |
| 選 Fixture Tester，輸入「你好」 | **有回覆**（送出前跳出模型登入畫面，使用者處理後送出） |
| `claude-role` 行的編輯器診斷（警告文字） | 使用者未回報（資訊性） |

**判定：B-0(5) PASS**。Copilot 對未知欄位 `claude-role` 不會拒絕載入或執行 agent；依 plan §8.2 #6 分流「只警告 → 照計畫」，角色表維持在 agent frontmatter，不需改放 sync script。

補記（U2）：Fixture Tester 的回覆原文為「你好，我是 Fixture Tester。」，確認是以該 agent 檔的設定執行。使用者打開 `fixture-tester.agent.md` 後貼出 `claude-role: tester`、`tools: [read, search, execute, web]` 兩行，未提及波浪線或警告訊息。

### 4.17 使用者實測 U3｜B-R6 push 閘門（2026-10-09，Claude Code `2.1.292`，auto mode）

使用者在終端機以 `env -u ANTHROPIC_API_KEY claude --agent fixture-full --permission-mode auto` 於使用者 fixture 執行，回報 (a)(b) 都跳出核准提示、都選 No。Engineer 讀取 session transcript 佐證（`…-b0-user-fixture-proj/26d8abb8-3a2b-479b-86f6-b759bb09c8d4.jsonl` 與 `26d8abb8…/subagents/agent-adde86ac214d84c6f.jsonl`）：

| 情境 | transcript 證據 | 結果 |
|---|---|---|
| (a) 主執行緒（`--agent fixture-full`，auto mode） | Bash `git push --dry-run origin main` → `The user doesn't want to proceed with this tool use. The tool use was rejected …`，接著 `[Request interrupted by user for tool use]` | **出現提示，使用者拒絕**，push 未執行 |
| (b) subagent（主 session 以 Agent 工具交給 `fixture-full`；meta：`spawnDepth: 1`、`requestShape: background`） | subagent 的 Bash 為複合指令 `cd "<fixture>" && git push --dry-run origin main; echo "EXIT_STATUS=$?"` → `Permission for this tool use was denied. The tool use was rejected …`；subagent 以 SubagentHandback 回報未執行 | **出現提示，使用者拒絕**，push 未執行；ask 規則對複合指令中的 `git push` 段同樣生效 |
| 遠端狀態 | `git ls-remote remote.git` → 0 筆 | 沒有任何 push |

**判定：B-R6 的使用者證據已補齊**。純 `git push` 的核准提示在 auto mode 下的主執行緒與 subagent 都會出現 → PASS；`git -C … push`、`bash -c 'git push …'` 等變體依 plan 合法 carry-over 表由 C-R5 處理（B-0(6) V1 已證實這兩種變體會繞過）。`AGENTS.md`「在主執行緒、subagent 與 auto mode 下都已實測會觸發」的聲明與此一致，不需下修。

另：同目錄的 `db1e33fb-324c-46f3-ab64-36228d41fe06.jsonl`（11:07）是另一次 plan mode 執行（推測為 `fixture-planner` 重做），結果與 §4.14 第 1 輪相同（無 Write、無 ExitPlanMode，無法提交，未寫檔），不改變判定。

### 4.18 使用者實測 U4｜B-0(8)／B-R4，與 Claude Code 升級後重驗（2026-10-09）

**U4**：Claude Code `2.1.295` 已移除 `/agents` 精靈（輸入後顯示「The /agents wizard has been removed.」，並指向 `.claude/agents/` 與 `~/.claude/agents/`）；`claude agents` 子命令管理的是背景 session，不是 agent 定義。依 plan B-R4「`/agents`（或等價列表）」，改用等價列表：Engineer 提供 scratchpad 腳本 `u4/u4_agents.sh`（`bash -n`、shellcheck 通過；只讀，不改 worktree），使用者在新終端機執行。腳本在 worktree 啟動兩個新的 `-p` session，讀 init 事件：

| 檢查 | 結果 |
|---|---|
| session cwd | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree`（版本 `2.1.295`） |
| 載入的專案 agent | **15 個**：architect、close-campaign-retire-worktree、designer、engineer、history-teller、lianbu-spokesperson、peatix-scraper、plan-critic、researcher、reviewer、scraper-expert、tcc-scraper、tester、update-history-skill-agent、validate-merge-deploy |
| worktree wrapper 全數載入 | True（worktree 15 個；主工作樹 16 個） |
| `community-platforms-scraper`（只存在主工作樹） | **未載入** |
| `--agent tester` 的工具 | `Read, Bash, WebFetch, WebSearch`（無 Edit／Write／NotebookEdit）。主工作樹的舊 tester wrapper 沒有 `tools:`，若載入主樹會得到全部工具 → 證實載入的是 worktree 檔 |

Engineer 以同一份 `u4_report.py` 重讀 scratchpad 的 `list.jsonl`、`tester.jsonl`，結果相同。**判定：B-0(8)／B-R4 PASS**（R2 風險未出現）。

**版本變動**：B-0 spike（§4.11）在 `2.1.292`（2026-10-07）執行；U1～U4 的 transcript 與 init 事件皆為 `2.1.295`（2026-10-09，自動更新）。依 plan §8.2 原則 6，Engineer 在 commit 前以 `2.1.295` 重跑 B-0 的關鍵項目（scratchpad `b0 spike/out-2.1.295/`，同一套 `env -i` 啟動方式）：

| 項目 | `2.1.295` 結果 | 與 `2.1.292` 比較 |
|---|---|---|
| (2a) 主執行緒：tester（R-T1）、planner（R-T3） | init 工具皆為 `Read, Bash, WebFetch, WebSearch`（planner 順序不同），無 Write 呼叫、檔案未建立；full 對照組（R-T2）Write 成功 | 相同 |
| (2b) subagent：tester（R-T4）、planner（R-T6） | 無 Write 呼叫、檔案未建立；full 對照組（R-T5）subagent Write 成功 | 相同 |
| (6) 對照組 | R-Q1（只有 allow，主執行緒）、R-Q5（只有 allow，subagent）、R-Q8（auto mode、無規則）：push 皆實際執行 | 相同 |
| (6) project ask | R-Q2（主執行緒）、R-Q4（subagent）、R-Q7（auto mode）：皆「requires approval」，未執行 | 相同 |
| (6) 變體（auto＋ask，R-V1） | `X=1 git push`、`env X=1 git push` → 需要核准；`git -C . push`、`bash -c "git push"` → 直接執行 | 相同 |
| 遠端 | `git ls-remote remote.git` → 0 筆 | — |

(3) hook stdin 未重跑（屬 C-0(3) 的正式實測範圍）。`AGENTS.md` 的實測版本改寫為「`2.1.292`、`2.1.295`」。

### 4.19 H-B2／H-B3（使用者，2026-10-09）

| 核准點 | 決定 |
|---|---|
| H-B2（B-0 結果、B-R4／B-R6 使用者證據） | 核准 |
| H-B3（commit 前 diff） | 核准 commit（`chore(ai): project agent roles to Claude tool limits`，不 push） |

commit 前的最終檢查（`2.1.295`）：origin/main 重新 fetch 後仍為 `67846c18`，與 Phase B 路徑無新重疊；sync 後 `--check` exit 0；`24 passed`；B-R5 指標零 diff、四個 UNDECIDED 相較 `223d8b4e` exit 0；11 檔 frontmatter-diff 0 失敗；`git diff --check` exit 0；gitleaks `no leaks found`；變更路徑全部在 Allowed paths 內。diff：21 個檔案修改（+472／−27，含本 notes 與 tasks）、4 個新檔（`.claude/settings.json`、`scripts/tests/{conftest,test_claude_settings,test_sync_ai_adapters}.py`）。

**Phase B 狀態**：B-R1～B-R10 皆 PASS；B-R6 的 push 變體（`git -C … push`、`bash -c 'git push …'`）依合法 carry-over 表記為 PARTIAL＋Carry-over → C-R5。B-R7（依 §4.15 修訂條件）、B-R8 均為 PASS，不產生 C-R10 carry-over。runbook L410 不勾選，已加註「部分（X1–X4 延期）」。

### 4.20 Phase C session（2026-10-12）

| 項目 | 值 |
|---|---|
| 執行者 | Engineer（Claude Opus 5.5 `claude-opus-5-5`）；session 以 `--agent engineer` 啟動（`CLAUDE_CODE_AGENT=engineer`） |
| Claude Code 版本 | 本 session 執行檔 `2.1.295`（`CLAUDE_CODE_EXECPATH`）；PATH 上的 `claude --version` 為 **`2.1.296`**（session 啟動後自動更新）。C-0 spike 以 `2.1.296` 執行。B 結束時為 `2.1.295` |
| 工作目錄 | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree` |
| 依據 | `~/.ai-notes/ttr/phaseC-engineer-prompt.md`、`plan.md` §2、§3、§7、§8、§8.1、§8.2 |
| `plan.md` SHA-256 | `6943c073620e29530581988a79c47e8da84ee34f6ce3edecf2e7511695487bbc`（與指定值相符，未 STOP） |
| 工具 | Python 3.14.3（`/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python3`）、pytest 9.0.3、shellcheck 0.11.0、gitleaks 8.30.1 |

#### Worktree 閘門（Phase C）

| 檢查 | 結果 |
|---|---|
| `git worktree list --porcelain` 中的本 worktree | `worktree …/ttr-ai-portability-worktree`、`HEAD 1460aab235045542f2ae9cfb7e823d84edd61ea1`、`branch refs/heads/feat/ai-portability` |
| `/bin/pwd -P`／`git branch --show-current` | 與上列路徑、`feat/ai-portability` 相符 |
| 本 worktree `git status --porcelain` | 無輸出（乾淨） |
| 主工作樹 `git -C "<主工作樹>" --no-pager status --short` | 無輸出（無他人 WIP）；branch `main`，HEAD `4e5f1f13dac393a5eccd790e5d2181b4adc84d44` |
| `.git/info/exclude` | 第 15 行有 `ttr-ai-portability-worktree/` |

#### Step 0 漂移檢查（Phase C）

| 項目 | 值 |
|---|---|
| HEAD | `1460aab2`（chore(ai): project agent roles to Claude tool limits）＝ 預期值；工作樹乾淨 |
| fetch 前本機快取的 origin/main | `67846c183c761350687081774f3435df5e5003aa`（＝ Phase B remote baseline） |
| `git fetch origin` | exit 0（`2026-10-12T12:44:07Z`）；`67846c18..cb8266f5 main -> origin/main`（另新增遠端分支 `fix/iwafu-taiwan-relevance-gate`） |
| fetch 後 origin/main（Phase C remote baseline） | `cb8266f58a2c137ecf753ce8e71ddc5ae05c585d`（docs(weekly_review): 2026-10-11 weekly review） |
| `git merge-base HEAD origin/main` | `67846c18…`；`67846c18` 是 origin/main 的祖先 |
| ahead／behind | `5	1` |
| `67846c18..origin/main` 改到的檔案 | 只有 `docs/weekly_review/2026-10-11.md` |
| 與 Phase C 路徑重疊（`scripts/claude .claude AGENTS.md CLAUDE.md scripts/tests scripts/sync_ai_adapters.py .github/agents .githooks docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md docs/specs/active/ai-portability .github/instructions/token-rotation.instructions.md`） | 無 |

**判定**：預期內的主幹前進，不是非預期漂移。未 rebase、未改 base。

### 4.21 C-0 spike 結果（2026-10-12，Claude Code `2.1.296`，模型 `claude-opus-5-5`）

**環境**：disposable fixture 在 session scratchpad `…/scratchpad/c0 spike/`（路徑含空格；不在 worktree 內）：`proj/`（`git init -b main`、一個 commit、`origin` 指向同層本機 bare `remote.git`）、`proj/hooks/log.sh`（把 PreToolUse stdin 存檔，依參數回 exit 碼或輸出 JSON）、`proj/.claude/agents/fixture-{full,tester,search}.md`、`proj/.claude/settings.json`（每個測試以 `settings/<case>.json` 覆寫，皆保留 `permissions.ask: ["Bash(git push:*)"]`）。所有 `claude` 以 `env -i HOME PATH USER LOGNAME SHELL TERM LANG TMPDIR claude -p --output-format stream-json --verbose --include-hook-events … < /dev/null` 啟動；需要放行 Bash 的對照組以 `--settings '{"permissions":{"allow":["Bash"]}}'` 給 allow；`--permission-prompts none`（會提示的動作自動拒絕）。push 只對本機 bare remote 做 `--dry-run`；結束時 `git ls-remote remote.git` 為 0 筆。原始輸出在 scratchpad `c0 spike/out/<case>.{jsonl,err,logs}`（不進 repo）。

**文件查證（WebFetch，2026-10-12）**：`code.claude.com/docs/en/hooks`。重點：exit 0／2／其他碼的語意；`timeout` 預設 600 秒（command）；PreToolUse decision JSON 為 `hookSpecificOutput.permissionDecision`（allow／deny／ask／defer）＋`permissionDecisionReason`；多個 hook 的優先序 deny > defer > ask > allow；「Deny and ask rules are still evaluated regardless of what the hook returns」；「A hook's "ask" also forces a permission prompt in auto mode」；command 以 `sh -c` 執行；settings hooks 在 subagent 內同樣執行；`-p` 視資料夾為已信任；**新欄位 `onFailure: "block"`（需 v2.1.295 以上）**：hook 無法啟動、exit 非 0／2、逾時、輸出無效時改為阻擋。

| 項目 | 結果 | 證據（case） |
|---|---|---|
| (1) exit 2 | **PASS：阻擋** | E2：tool_result `PreToolUse:Bash hook error: [<command>]: <stderr>`，檔案未建立；stderr 會交給 Claude |
| (1) exit 1 | **PASS：不阻擋** | E1：hook `outcome: error`，命令照常執行 |
| (1) exit 127（hook 命令不存在） | **PASS：不阻擋** | E127：stderr `/bin/sh: /nonexistent/…: No such file or directory`，命令照常執行（證實 hook 經 `/bin/sh` 執行） |
| (1) 逾時（`timeout: 3`、hook sleep 15） | **PASS：不阻擋** | ET：`outcome: cancelled`、`exit_code: 1`，命令照常執行 |
| (1) exit 0＋無效 JSON（`{"hookSpecificOutput":`） | **PASS：不阻擋**（與文件一致） | EJ：命令照常執行 |
| (1) 結論 | 與文件一致，未 STOP | — |
| (2) matcher | **PASS**：`Bash`、`Read`、`Write`、`Edit`、`NotebookEdit`、`Grep`、`Glob` 精確名稱與 `Read\|Grep\|Glob\|Write\|Edit\|NotebookEdit` 組合皆命中；`*` 命中全部（含 `ToolSearch`、`Agent`、`Monitor`） | M1、M2、M3 |
| (2) stdin 頂層鍵 | `cwd`、`effort`、`hook_event_name`、`permission_mode`、`prompt_id`、`session_id`、`tool_input`、`tool_name`、`tool_use_id`、`transcript_path`；`--agent` 或 subagent 另有 `agent_type`（subagent 再加 `agent_id`）。文件列的 `scratchpad_dir` **未出現** | M1–M3、A2、A3 |
| (2) `tool_input` 欄位 | Bash：`command`、`description`；Read：`file_path`（另可有 `offset`、`limit`）；Write：`file_path`、`content`；Edit：`file_path`、`old_string`、`new_string`、`replace_all`；NotebookEdit：`notebook_path`、`cell_id`、`new_source`、`edit_mode`；Grep：`pattern`、`path`、`output_mode`、`glob`（有指定時）；Glob：`pattern`、`path`；Monitor：`command`、`description`、`timeout_ms` | 同上 |
| (2) 備註 | NotebookEdit 為 deferred 工具（需先 ToolSearch）；工具自身的前置驗證失敗（如「File has not been read yet」）時 **PreToolUse 不觸發** | M1、M3 |
| (3a) `claude --agent` 主執行緒 | **可辨識**：`agent_type` = 角色名，**無** `agent_id` | M2（`fixture-search`）、A3 的 Agent 呼叫（`fixture-full`） |
| (3b) subagent | **可辨識**：`agent_type` = subagent 名＋`agent_id` | A2（主 session 無 `--agent`）、A3（主執行緒為 `--agent fixture-full`）皆為 `fixture-tester`＋`agent_id` |
| (3) 主 session 未帶 `--agent` | 兩欄皆無 | M1、A2 的 Agent 呼叫 |
| (4) `Grep` 遍歷 gitignored dotfile | **會遍歷**：`fixture-search`（`tools: Read, Grep, Glob`，無 Bash）以父目錄為 `path` 搜尋，結果同時列出 `sub_ign/.env`（gitignored＋隱藏）與 `sub_hid/.env`（隱藏、未忽略）；`Glob` 的 `.*`、`**/.env` 也列出兩者 | M2 → 依 plan 記入規則 7 邊界（工具層 `Grep` 父目錄遞迴不涵蓋） |
| (5) `ask` JSON | **PASS：形狀生效** `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"…"}}`（exit 0）。即使 `--settings` 給了 `allow: Bash`，default（K1）、auto（K2）、`--agent`（K3）、subagent（K4）皆變成「requires approval」→ `-p` 自動拒絕、檔案未建立。互動提示是否出現：**NOT TESTED（交使用者）** | K1–K4 |
| (5) `deny` JSON | 生效：`PreToolUse:Bash hook error: <reason>` | K5 |
| (6) | 沿用 B-0(6)（§4.11、§4.18；`2.1.295` 重驗） | — |
| (7) 熱重載 | **會即時生效**：session 進行中由外部程序覆寫 `.claude/settings.json`，下一個 Bash 呼叫就改用新 hooks（舊 hook 不再觸發） | VR |
| (7) 模型以 Bash 改 `.claude/settings.json` | 即使 `allow: Bash`，Claude Code 仍要求核准（`-p` 自動拒絕） | V |
| (7) 未信任 workspace 的 `-p` | project hooks **會執行**（fixture 從未信任，所有 case 的 hook 都有觸發；與文件「`-p` treats the folder as trusted」一致） | 全部 |
| (8) `CLAUDE_PROJECT_DIR` 含空格 | **PASS**：解析為 `…/scratchpad/c0 spike/proj`；hook 的 PWD 同為專案根目錄 | E0、P1 |
| (8) plan §7 的 fail-closed 外殼字串 | launcher 存在 → 以 `bash` 執行、`$1 = probe`、`$0` 為含空格的完整路徑、命令照常（P1）；launcher 不存在 → exit 2、阻擋（tool_result `… No stderr output`）（P2） | P1、P2 |

**計畫未涵蓋的觀察（H-C1 呈報）**

1. **`onFailure: "block"`**（`2.1.296` 實測）：hook 命令不存在（F127）、exit 1（F1）、逾時（FT）→ **阻擋**（`failed／timed out; blocking because onFailure is "block"`）；但 **exit 0＋不完整 JSON（FJ）仍放行**（host 視為純文字），所以 launcher 的 output protocol 仍然必要。舊版 `2.1.292` 遇到此欄位：**整份 settings 仍有效**（hook 照常執行、`permissions.ask` 照常要求核准），只是忽略 `onFailure`（exit 1 不阻擋）（OLD_2.1.292 對照 OLD_2.1.296）。
2. **`Monitor` 工具可執行 shell 命令**：PreToolUse 以 `tool_name: "Monitor"`、`tool_input.command` 觸發，`Bash` matcher 不會命中。`-p` default 下需要核准（MON1、MON2）；**auto mode 下 `touch` 經 Monitor 直接執行**（MON4），`git push --dry-run` 經 Monitor 在 auto mode 則要求核准（MON3；是 ask 規則或分類器所致無法區分）。
3. **從子目錄啟動 session 時，repo root 的 `.claude/settings.json` 不載入**：在 `proj/sub_hid` 啟動，logging hook 未觸發（S1），`git push --dry-run origin main` 直接執行、沒有要求核准（S2）。B 的 push ask 與 C 的 hooks 都只在「從 repo（worktree）根目錄啟動」的 session 生效。
4. `Bash` 工具在 hook 之前有自己的檢查（例：`sleep 25 && …` 被 Claude Code 以 Monitor 建議擋下，hook 未觸發）。不影響本設計。

### 4.22 H-C1 前查證（只查、只記錄，2026-10-12；HEAD `1460aab2`）

| # | 項目 | 證據 | 影響 |
|---|---|---|---|
| 1 | masked awk 模板 | `token-rotation.instructions.md` L125 = `cd scraper && ` ＋模板、L196 = 兩個空白＋模板（`od -c` 確認為一般空白），模板本體與 plan §7 規則 7 2b 逐字相同（結尾 `' .env`）。**另有** canonical 來源 `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` L41：同一 awk 程式，路徑為 `scraper/.env`（engineer SKILL「Secret Scanning」要求兩檔同 commit 一致）。`docs/specs/security-hardening-plan-RECOVERED.md` L417 也有 `scraper/.env` 版（historical） | plan 的 2b 只收 `.env` 版；checklist 的 `scraper/.env` 版會被層 3 拒絕 |
| 2 | F4 `supabase db pull` | 官方 CLI 文件（`supabase.com/docs/reference/cli/supabase-db-pull`，2026-10-12）：「Optionally, a new row can be inserted into the migration history table to reflect the current state of the remote database」，範例輸出含 `Update remote migration history table? [Y/n]`；全域 `--yes` 會自動回答 yes | `db pull` 可寫遠端 migration history，不得歸只讀 |
| 3 | F4 其他 | 同一頁：`migration repair`「Repairs the remote migration history table」（`applied` 會插入紀錄）；`db push`「Pushes all local migrations to a remote database」，`--dry-run` 只列印；`db diff`「Diffs schema changes」，無套用旗標 | 與 notes §3.4 一致 |
| 4 | Supabase MCP 連接器 | 本 session 與 C-0 fixture 的 `-p` session init 工具清單都含 claude.ai 帳號層的 `mcp__claude_ai_Supabase__execute_sql`、`apply_migration`、`deploy_edge_function` 等（repo 內無 `.mcp.json`，非 repo 設定）。**未實測**（會碰 production，不測） | 規則 9 只涵蓋 `psql`／`supabase` CLI／`python -c`；MCP 是另一條 production 寫入面 |
| 5 | 版本 | spike 以 `2.1.296` 執行（B 為 `2.1.292`／`2.1.295`）；本 session 執行檔仍為 `2.1.295` | 實測版本記為 `2.1.296` |

### 4.23 H-C1 決定（使用者，2026-10-12）

使用者回覆「全部照建議」。逐項：

| # | 項目 | 決定 |
|---|---|---|
| ① | 規則 1 | 依 plan，另加 `--prune`、`--force-if-includes`（`-d` 為 `--delete` 短寫，一併涵蓋） |
| ② | 規則 3 | 沒有 `-n`／`--dry-run` 的 `git clean` 一律拒絕（涵蓋 `-c clean.requireForce=false`、`-i`） |
| ③ | 規則 7 | 模板常數 = `token-rotation` L125／L196 的 `.env` 版＋`GITHUB_TOKEN_SYNC_CHECKLIST.md` L41 的 `scraper/.env` 版；漂移測試同時讀兩檔。工具層 guard 不含 Glob（只回檔名，與 2a `ls -l` 同級） |
| ④ | 規則 8 | 依 plan，另加 bare `export`、`declare`／`typeset` 的列表與 `-p` 形式 |
| ⑤ | 規則 9（F4） | `db query` 全拒；只看子命令、不分 local／linked；`--yes` 不另設規則；`db pull` 拒絕；Management APIs 列殘餘風險＋後續項目。拒絕清單：`db push`（只放行精確 `supabase db push --dry-run`）、`db reset`、`db query`、`db pull`、`migration up/down/repair/squash`、`seed`、`db` 子命令帶 `--from-backup`／`--apply`／`--reset` |
| ⑥ | 包裝動詞 | 依 plan，另加 `timeout`、`nice`、`sudo`、`caffeinate`、`stdbuf` |
| ⑦ | §8.2 #13 | 預先核准：U5 若證實 hook `ask` 在互動模式完全不跳提示，push 變體改為 deny 並提示改用純 `git push`（純 `git push` 仍由 `permissions.ask` 把關） |
| ⑧ | settings 與測試 | 內容如 H-C1 e（`Bash\|Monitor`、`Read\|Grep\|Write\|Edit\|NotebookEdit`、`timeout: 30`、`onFailure: "block"`；guard watchdog 10 秒）；settings 測試只留 `scripts/tests/test_claude_settings.py`（改寫 Phase B 的「只含 permissions」測試），不建 `scripts/claude/tests/test_settings.py` |
| ⑨ | 子目錄啟動 | `AGENTS.md` 覆蓋聲明加「只在從 repo／worktree 根目錄啟動的 session 生效」，並更正 B 段措辭 |
| ⑩ | Supabase MCP | (i) 殘餘風險＋後續項目，`AGENTS.md` 寫明 |
| ⑪ | heredoc 餵入的 python | 套用與 `python -c` 相同的 `create_client`＋寫入方法檢查 |
| ⑫ | 使用者實測草案 | 核准，寫入 `tasks.md`（U5、U6） |

C-R9：兩情境皆可辨識（§4.21）；C-R10 不做（B-R7／B-R8 PASS，無 carry-over）。guard 不使用 agent 身分。

### 4.24 Phase C 實作與驗證（2026-10-12，Claude Code `2.1.296`；session 執行檔 `2.1.295`；未 commit）

| 項目 | 狀態 | 證據 |
|---|---|---|
| `_tokenizer.py` 預算 | PASS | 244 行（不含註解、docstring、空行），`test_tokenizer_budget` 鎖定 ≤250 |
| 實作細節（H-C2 呈報） | — | `git commit -am "$(cat <<'EOF' …)"` 納入 R3-1 例外（`-am` = `-a -m`）；launcher 以 `python3 -B -E -s` 執行（不寫 `__pycache__`）；guard 只輸出 `ask` JSON，deny 一律 exit 2 |
| C-R1 | PASS | §4.21 |
| C-R2 | PASS | `python3 -m pytest scripts/tests scripts/claude/tests -q` → `437 passed`（worktree，hooks 已加入後）；各阻擋類 ≥3 變體由測試鎖定；B-R6 三個變體回 ask |
| C-R3 | PASS | `test_launcher.py` fail-closed 矩陣（含 output protocol 10 列）全過；host timeout 由 `onFailure: "block"` 阻擋（舊版忽略此欄位 → 殘餘）；host schema 改版為殘餘 |
| C-R4 | PASS | 例外 → exit 2＋固定訊息；含空格路徑＋settings 內完整 command 字串；假 token 不出現在 stderr |
| C-R5 | PASS-pending-user | 自動：測試＋`-p` e2e（scratchpad `c1 e2e`）：`git -C . push`、`bash -c "git push"`、`env X=1 git push`（auto、`--agent`）、subagent → requires approval；force → `[git-force-push]`；遠端 0 筆。互動提示待 U5 |
| C-R6 | PASS（已記錄） | hooks 加入後 `claude doctor`：`Running: native (2.1.296)`、`Search: OK (bundled)`、`No installation issues found.` |
| C-R7 | PASS-pending-user | U6（Closer fixture 尚未準備） |
| C-R8 | PASS | `AGENTS.md`「Hooks 與 permissions（Claude Code 專屬防線）」：生效條件（根目錄啟動、四角色、兩情境）、規則表、未涵蓋清單（含規則 7 邊界、prod-db 啟發式、Supabase MCP、Copilot／Codex 不受保護） |
| C-R9 | PASS | 兩情境皆可辨識（§4.21） |
| C-R10 | 不適用 | 無 carry-over（§4.23） |
| C-R11 | PASS | `rg` 命中只有 proposal.md L109（規則原文引用）、L169（X1 引用 runbook 要求）、runbook L307 與 AGENTS.md L85（否定句「不宣稱／不代表沒有寫入能力」） |
| C-R12 | PASS | `git diff --exit-code 1460aab2 --` 四個 UNDECIDED canonical＋wrapper → exit 0 |
| hooks 自我驗證 | PASS | 加入後本 session：`git status --short`、`git diff --check`、`git log`、`sync --check`、pytest、Read 放行；`printenv HOME` → `[env-dump]` 被擋 |
| `git diff --check` | PASS | tracked 變更 exit 0；新檔逐檔 `--no-index --check` 無問題回報（HN6 的行尾空白由 `.gitattributes -whitespace` 保留，提交前再確認一次） |
| gitleaks | PASS | `git diff HEAD`＋新檔內容 `gitleaks stdin --redact -c .gitleaks.toml` → `no leaks found` |
| diff 路徑 ⊆ Allowed paths | PASS | `.claude/settings.json`、`AGENTS.md`、`scripts/claude/**`、`scripts/tests/test_claude_settings.py`、spec 目錄 |
| 尚未完成 | — | runbook L411 勾選與 L323 註記、U5 使用者 fixture、Closer fixture campaign、H-C2 呈報 |

### 4.25 H-C2 前補完（2026-10-13，`claude --version` `2.1.296`）

| 項目 | 結果 |
|---|---|
| 新檔空白檢查（重做） | 逐檔 `git diff --no-index --check /dev/null <file>` 輸出全為空；以 scratchpad 探針（行尾空白）確認檢查器有效（exit 3）；HN6 在 repo 內由 `scripts/claude/tests/fixtures/heredoc/.gitattributes`（`HN6.txt -whitespace`）豁免，其副本在 repo 外會被抓到 → 只有 HN6 是刻意保留 |
| runbook | L323 註記改為 B／C 分工與「只在根目錄啟動的 session 生效」；L411 勾選並註明覆蓋聲明（C-R2、C-R3 PASS） |
| U5 fixture | scratchpad `c2 user fixture/proj`：settings 與 5 個 hook 檔與 worktree 逐位元組相同（`cmp`）；本機 bare remote 0 筆 |
| Closer fixture | scratchpad `c3 closer fixture/Tokyo Taiwan Radar`：只複製 Closer 需要的檔（agent、wrapper、campaign-closer SKILL、session-analytics、git.instructions、campaigns README、audit 腳本、AGENTS.md、CLAUDE.md、`.gitignore`、settings 與 `scripts/claude/`）；campaign `demo-fixture`（tasks 全勾、Deferred 寫成單行 None）。origin 以 `git --git-dir=origin.git fetch` 更新（Engineer session 內不執行 `git push`）。試跑 audit：`unhandled_total=0`、`verdict=UNDETERMINED:issues_not_checked,self_session_unknown`。第一版 proposal 的 `## Deferred` 標題被計為 1 個 deferred marker（HOLD），改成單行後為 0 |

### 4.26 H-C2（使用者，2026-10-13）

使用者核准 H-C2（`settings.json` 逐行、diff 範圍、C-R 狀態、兩處 plan 以外的實作細節：`-am` 納入 R3-1 例外、launcher 以 `python3 -B` 執行）。接著進行 U5、U6（含 Closer）使用者實測。

### 4.27 使用者實測 U5、U6（四角色）（2026-10-13，Claude Code `2.1.296`）

使用者在 VS Code 終端機以 `~/.ai-notes/ttr/phaseC-u5.sh`、`phaseC-u6.sh <role>` 啟動（腳本只 `cd` 到 fixture／worktree 根目錄後 `exec env -u ANTHROPIC_API_KEY claude --agent …`；長路徑複製時曾被終端機換行切斷，改用腳本）。Engineer 讀 transcript 判定（`~/.claude/projects/<專案>/<session>.jsonl`）。

**U5**（fixture `c2 user fixture/proj`，`--agent fixture-full --permission-mode auto`，session `4246a93c`）

| 步驟 | transcript 證據 | 結果 |
|---|---|---|
| (a) `git -C . push --dry-run origin main` | `The user doesn't want to proceed with this tool use…`（使用者在提示中選 No） | PASS：hook `ask` 在 auto mode 互動實際跳出提示 |
| (b) `bash -c "git push --dry-run origin main"` | 同上 | PASS |
| (c) `env X=1 git push --dry-run origin main` | 同上 | PASS |
| (d) subagent（模型以背景 Agent 啟動 `fixture-full`，命令為 `git -C . push --dry-run`） | subagent：`Permission for this tool use was denied…`；tool_use 17:04:34.433Z → result 17:04:38.025Z（3.6 秒） | 待使用者確認是否看到提示（訊息格式與 B 的 U3 (b) 使用者拒絕時相同，無法單憑 transcript 區分自動拒絕） |
| (e) `git push --force --dry-run origin main` | `ttr-hook: blocked [git-force-push] …`，無提示 | PASS |

另一個 session `55298b17`（02:31）只重做 (a)，同樣是使用者選 No。遠端 bare repo 未被 push（皆為 `--dry-run` 且被拒）。

**U6 四角色**（worktree 根目錄）

| 角色（session） | 放行類 | 被擋類 |
|---|---|---|
| architect（`18c2caa1`） | `git status --short` 正常輸出 | `printenv HOME` → `[env-dump]` |
| engineer（`4b579bec`） | `git diff --check` 無輸出 | `git branch -D ttr-smoke-nonexistent` → `[git-branch-D]` |
| tester（`22b0222a`） | `python3 -m pytest scripts/claude/tests -q` → `411 passed` | Read `docs/<smoke 用不存在的 .env 檔>` → `[env-file-access]` |
| validate-merge-deploy（`a05723d2`） | `git log --oneline -3`、`git fetch origin main` 皆放行 | （不測 push） |

四個 session 都沒有誤擋、沒有修改任何檔案。另：10-06 的舊 engineer session `55c9e60e` 檔案 mtime 在 02:22 更新，但最後一筆內容仍為 2026-10-07（無新增對話），與本次實測無關。

**待完成**：U5 (d) 使用者確認；Closer 實測（尚無 `c3 closer fixture` 的 transcript）。

### 4.28 U5 (d) 補證與 Closer 實測（2026-10-13，Claude Code `2.1.296`）

**U5 (d)**：使用者確認 subagent 執行時跳出核准提示並選 No → **PASS**。U5 (a)～(e) 全數 PASS：hook `ask` 在 auto mode 的主執行緒與（背景）subagent 都實際跳出提示；H-C1 ⑦ 的分流（ask 不生效時變體改 deny）不需啟用。

**Closer**（`~/.ai-notes/ttr/phaseC-closer.sh`，fixture `c3 closer fixture/Tokyo Taiwan Radar` 根目錄，`--agent close-campaign-retire-worktree`，session `e8b93f7d`）

| 項目 | transcript 證據 |
|---|---|
| 使用的工具 | 只有 `Bash`、`Read`（wrapper 白名單無 Write／Edit；未嘗試 Write） |
| Phase A | 讀 agent 檔、SKILL、campaigns README、git.instructions、audit 腳本；`git fetch origin main` 後跑 audit：`UNDETERMINED`（`issues_not_checked`、`self_session_unknown`）；以 Bash 人工核對 range diff 與 Copilot session-state（zsh glob 無命中報錯一次，改 `bash -c` 重跑，hook 放行） |
| 結案紀錄寫入 | Bash：`cat > "docs/evaluation/campaigns/2026-10-13-demo-fixture.md" <<'EOF' …`（先檢查檔案不存在），100 行、十節齊全，`Worktree disposition` = `pending` |
| commit | worktree 內 `3d7760b docs: add demo-fixture campaign close-out record`（`git commit -F - <<'EOF'`）；ahead 1／behind 0；dirty 0；**未 push**（fixture origin main 仍為 `b296fe9`） |
| hook 拒絕 | 0 次（無誤擋） |

**裁決 12 判定：不需 Write，不授予**。Closer 以 Bash 完成結案紀錄寫入（plan §6 判準：「若 Closer 改用 Bash 完成寫入，記為不需 Write」）。closer 的 `ROLE_TOOLS` 與 Copilot `tools:` 不變，不需要獨立 commit。

**計畫未涵蓋的觀察（不影響 C-R7 判定）**：Closer 在使用者第二句核准前就進入 Phase C 寫紀錄並 commit。它在下一輪自承「照 agent 檔的規定，應該先等你同意再寫，這一步我做在你同意之前」。推測是把第一句提示中預先說明的未知項（「session id 未知；issues 以 --skip-issues 標 not_checked」）當成同意。這是 agent 行為規則的遵循問題，與 hooks／工具限制無關；列為 update-history-skill-agent 的教訓候選（campaign-closer 的 Phase B 閘門）。

**C-R7 判定：PASS**（使用者證據已補）：architect、engineer、tester、validate-merge-deploy（§4.27）與 Closer 皆無誤擋，預期被擋的命令都被擋，Closer 完成實際結案寫檔。

### 4.29 H-C3 前最終檢查（2026-10-13，`2.1.296`）

| 檢查 | 結果 |
|---|---|
| `python3 scripts/sync_ai_adapters.py --check` | exit 0 |
| `python3 -m pytest scripts/tests scripts/claude/tests -q` | `437 passed` |
| `git diff --check`；新檔逐檔 `--no-index --check` | exit 0；無輸出（HN6 由 `.gitattributes` 豁免） |
| gitleaks（`git diff HEAD`＋18 個新檔） | `no leaks found` |
| C-R12 | exit 0 |
| 上游漂移 | `git fetch origin` 後 origin/main = `9cb1e11e`；merge-base 仍為 `67846c18`；`67846c18..origin/main` 新增 5 個 deps commit（`scraper/requirements.txt`、`web/package.json`、`web/pnpm-lock.yaml`）＋ weekly review；與 Phase C 路徑無重疊（預期內主幹前進）；ahead／behind = `5	6`。H-PUSH 前由 V-M-D rebase |
| runbook | L323 註記更新為「使用者互動實測通過」 |
| diff 範圍 | 6 個修改＋18 個新檔，皆在 Allowed paths 內 |

### 4.30 H-C3（使用者，2026-10-13）

使用者核准 commit（回覆「commit」）。Closer 依裁決 12 判定不需 Write（§4.28），不另做獨立 commit。Phase C 以單一 commit `chore(ai): add Claude Code PreToolUse safety hooks` 提交於 `feat/ai-portability`，不 push；H-PUSH 前交 V-M-D 先 rebase 到最新 origin/main（目前 `9cb1e11e`）。

**Phase C 狀態**：C-R1～C-R12 皆 PASS（C-R10 不適用）；runbook L411 已勾選、L323 已更新。

### 4.31 教訓寫入（Update History, Skill, Agent，2026-10-13；HEAD `4c406ad8`；未 commit）

整理 Phase A／B／C 的教訓（`~/.ai-notes/ttr/update-history-BC-prompt.md` 候選 1–27），含 §4.28 指派的 Closer 教訓。證據取自本檔 §4.4、§4.7～§4.30 與 Closer fixture transcript（session `e8b93f7d`）。

**閘門與核准點**

| 項目 | 結果 |
|---|---|
| Worktree 閘門 | 路徑、branch `feat/ai-portability`、HEAD `4c406ad8` 相符；工作樹**不乾淨**（同一 session 前一輪未經 H-U1 寫入的 5 檔草稿，涵蓋候選 11–14、17、25、26）→ STOP 回報 |
| 使用者決定（2026-10-13） | 選項 A：保留草稿併入本次；保留 `campaign-closer.agent.md` 的 Phase B／C 修改；H-U1 表全部照建議 |
| H-U1 查證時的更正 | 候選 22 原句的 `git diff --name-only $(git merge-base HEAD origin/main) origin/main` 會被本 campaign 的 guard 以 `[dynamic-args]` 擋下（直接餵 `pretooluse_bash_guard.py` 實測）；改寫為 `git diff --name-only HEAD...origin/main -- <paths>`（guard 放行；本 worktree 三點 4 檔＝ merge-base 寫法 4 檔，兩點 79 檔） |
| 寫入前另行實測 | 候選 21：`bash -eo -c "echo …"` → bash 報 `-c: invalid option name`、不執行（guard 解析與 bash 一致，不是漏洞）；候選 27：`zsh -c 'echo ====='` → `==== not found`，加引號正常；bfs 對 `-dashdir` 報錯，`./-dashdir` 正常；候選 19：`scripts/claude/tests/test_bash_guard.py` L451–452 同時讀兩個來源檔 |

**落點**

| 檔案 | diff | 內容 |
|---|---|---|
| `.github/skills/agents/engineer/SKILL.md` | +43/−0 | Cross-module String Contracts（1）；worktree 條目旁的三點 diff 與不寫死數量（22、8）；Secret Scanning（19）；Database（20）；zsh 段旁（27）；Agent Frontmatter Rules（9）；新段「Claude Code harness」：寫 hook（11、12、13、15、18、21）、settings（6、16）、spike 方法（4、5、10）、交付使用者實測（23、24） |
| `.github/skills/agents/engineer/history.md` | +59/−0 | 2026-10-13 Phase C（11–14、17 與其他發現 15、16、18–24）；2026-10-09 Phase B（2–10）；2026-10-07 Phase A（1） |
| `.github/skills/agents/campaign-closer/history.md` | +51/−0 | 25、26 |
| `.github/skills/agents/campaign-closer/SKILL.md` | +32/−1 | 25（§ Phase B 同意閘門）、26（A2 逐行比對）；`ms.date` → 2026-10-13 |
| `.github/agents/campaign-closer.agent.md` | +8/−0 | 25：Phase B 加「Phase A 輸出後結束本輪」與「什麼算同意」；Phase C 加進入條件 |

**只寫 history、不寫 SKILL**：2、3、7、14、17（`AGENTS.md` 已有覆蓋聲明）。10 的「升級後重跑 fixture」已在 `AGENTS.md` 與 `tasks.md` 後續項目，不寫成規則；1 的目錄改名是 `tasks.md` 後續項目，SKILL 只寫「先查消費者」。

**不改**：`scripts/campaign-closeout-audit.sh`（26 的誤判只會多算、偏向 HOLD）；四個 UNDECIDED agent 與其 wrapper；`.claude/settings.json`、`scripts/claude/`、`scripts/sync_ai_adapters.py`；`plan.md`。

**驗證（H-U2 前）**：`python3 scripts/sync_ai_adapters.py` 後 `--check` exit 0（wrapper 無漂移）；`python3 -m pytest scripts/tests scripts/claude/tests -q` → `437 passed`；`git diff --check` exit 0；`git diff | gitleaks stdin --redact -c .gitleaks.toml` → `no leaks found`；兩份 history 皆 `−0`，唯一刪除行是 campaign-closer SKILL 的舊 `ms.date`；變更路徑只在 `.github/skills/`、`.github/agents/campaign-closer.agent.md`、本目錄；新增內容無 C-R11 禁止的「無寫入能力」措辭。

### 4.32 H-PUSH：推送證據與 rebase 前後的 SHA 對照（2026-10-13；Validate, Merge & Deploy 流程）

本節是 push 之後補記。前面各節引用的是**各自撰寫當時**的 SHA；campaign 在推送前經過兩次 rebase（§4.8、本節），這些 SHA 不會出現在 origin/main。以下為對照，查證時以最右欄為準。

**SHA 對照**（`git range-diff` 逐筆為 `=`，patch 內容在兩次 rebase 中都沒有變）

| commit | 撰寫時 | 第一次 rebase 後（§4.8） | 推送後（origin/main） |
|---|---|---|---|
| `docs(ai): add Claude Code migration runbook` | `565c1479` | `bbcbdf4f` | `1d1e3d47` |
| `docs(ai): add ai-portability spec skeleton`（H0） | `256e8b9b` | `0eaeef65` | `d2398431` |
| `chore(ai): remove legacy Copilot state paths`（A） | `ecfb7347` | `223d8b4e` | `dfcd529e` |
| `docs(ai): record Phase B drift stop and R1 post-test` | `3981ee21` | `15b81475` | `1c7f7600` |
| `chore(ai): project agent roles to Claude tool limits`（B） | `1460aab2` | — | `d71543c7` |
| `chore(ai): add Claude Code PreToolUse safety hooks`（C） | `4c406ad8` | — | `588a42b2` |
| `docs(agents): record ai-portability phase A-C lessons` | `96f18e2e` | — | `86fdc143`（完整 `86fdc1434188c49713bc37b6c7a71a9034f3b9b8`） |

B、C 與教訓 commit 是在第一次 rebase 之後才建立，所以沒有「第一次 rebase 後」欄。

**推送前**

| 項目 | 結果 |
|---|---|
| Worktree／stash | 路徑、branch `feat/ai-portability` 相符；`stash-status.sh list` 無 stash；工作樹乾淨 |
| 上游漂移 | Phase C 時的 baseline `9cb1e11e` → 推送時 `7f8e75c9030badc96d10dd52f1f0023083e606be`（behind 8：`cb8266f5` weekly review、5 個 deps、2 個 iwafu scraper fix） |
| 重疊檢查 | `HEAD...origin/main` 與 `origin/main...HEAD` 的檔案交集為空；`git merge-tree --write-tree` exit 0（tree `2c0b01c1…`） |
| Rebase | `git rebase origin/main` 7/7 無衝突；`git range-diff 67846c18..96f18e2e origin/main..HEAD` 7 筆皆 `=` |
| 範圍分類 | 不含 `web/`、`web/messages/`、`supabase/`、workflow、`scraper/main.py`；含 token 高風險檔 `.github/agents/researcher.agent.md` |

**驗證**

| 檢查 | 結果 |
|---|---|
| `sync_ai_adapters.py --check` | exit 0 |
| `pytest scripts/tests scripts/claude/tests -q` | `437 passed` |
| `check_token_permission_consistency.py` default／`--strict` | 皆 exit 0（掃描 820 檔） |
| `gitleaks git --log-opts=origin/main..HEAD` | 7 commits，`no leaks found` |
| `git diff --check origin/main...HEAD` | exit 2，只有 `plan-critique-2/3/4.md`（H0 方案 A 的已知例外，見 §3.5）；後續 commit 沒有新增 |
| `pnpm run build` | 跳過：push range 不觸及 `web/`（V-M-D Step 3 docs-only 規則） |
| Fast-forward | `HEAD...origin/main` = `7 0`；`merge-base --is-ancestor origin/main HEAD` 成立 |

**推送與部署**

| 項目 | 結果 |
|---|---|
| campaign base（push 前 origin/main tip） | `7f8e75c9030badc96d10dd52f1f0023083e606be` |
| pushed HEAD | `86fdc1434188c49713bc37b6c7a71a9034f3b9b8`；`git push origin HEAD:main`（`7f8e75c9..86fdc143`），pre-push gitleaks `no leaks found` |
| push 後 GitHub main | `git ls-remote origin refs/heads/main` = `86fdc1434188c49713bc37b6c7a71a9034f3b9b8` |
| CI | GitHub Actions `gitleaks`：`completed/success` |
| Vercel | commit status `Vercel`：`success`（"Deployment has completed"）；GitHub deployment `environment=Production`、`ref`＝推送的 SHA；URL `https://tokyo-taiwan-radar-71zjto0e5-tuituikoans-projects.vercel.app` |
| custom-domain smoke（`https://tokyotaiwanradar.com`） | `/ja`、`/zh`、`/en`、`/robots.txt`、`/sitemap.xml`、`/llms.txt` 皆 200；`/ja` headers 含 HSTS（`max-age=63072000`）、`x-content-type-options: nosniff`、`x-frame-options: DENY`、`referrer-policy: strict-origin-when-cross-origin`、`content-security-policy-report-only`；`set-cookie: NEXT_LOCALE=ja; Path=/; Secure; SameSite=lax`；`/ja` 有 4 個 `application/ld+json`；`robots.txt` 為 `Allow: /`、`Disallow: /api` |

**觀察與未測項**

- **Vercel 在 docs-only push 也建立了 Production deployment。** V-M-D 文件寫「docs-only 不觸發 Vercel」，與這次實測不符；文件修正列為後續項目，本 campaign 不改 `validate-merge-deploy.agent.md`。
- **NOT TESTED**：OAuth、email magic link、session refresh／logout、一般使用者的 role denial、登入後 Admin CRUD（沒有安全的測試 credentials）；本次未改 web 程式碼，風險未新增。
- **未評估**：`web` 的 lint 與 build 沒跑，原本就存在的 full-file lint debt 未重新評估；CSP 仍為 Report-Only。
- **與本次變更無關**：push 時 GitHub 回報預設分支有 8 個 Dependabot 漏洞（3 high、2 moderate、3 low）。
- **commit scope**：六個 commit 使用 `ai` scope，不在 `git.instructions.md` 列出的 `scraper`／`web`／`db`／`ci`／`agents` 內；各核准點已核准該訊息，未重寫。`commit-message.instructions.md`（V-M-D Step 3 引用）不存在，改依 `git.instructions.md` 判讀。

**Worktree**：推送後 branch tip `86fdc143`、ahead 0／behind 0、dirty 0、無進行中的 rebase；ignored artifact 為 `.pytest_cache/`、`scripts/**/__pycache__/`、`supabase/.temp/`（`cli-latest` 8 bytes，Phase 0 `supabase --help` 的版本標記），皆可丟；`tmp/gnews_streaming_ids.txt` 是 repo 追蹤檔，不是 artifact。結案記錄尚未進 origin/main，因此**不提示移除 worktree**（V-M-D Step 0.6）。

**後續**：交 Close Campaign & Retire Worktree。`tasks.md` 的後續項目（約 20 條）刻意保持未勾選，Closer 的 A2 預期判 `HOLD`。

**補記（2026-10-13）**：上一段所稱 `tasks.md` 的後續項目，已於 commit `f6c2dad2d7c898174504b1a58be684c0e97c9021` 逐字搬至 `docs/specs/parked/ai-portability-followups.md`（19 條與其邊界說明），`tasks.md` 該段改為指向說明，所以「A2 預期判 `HOLD`」描述的是搬移前的狀態，搬移後預期未勾選為 0。
