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
