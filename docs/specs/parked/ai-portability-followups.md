---
slug: ai-portability-followups
title: ai-portability 後續項目（CI 接線、hook 繞過強化、production 寫入邊界、角色重新設計、維護）
status: parked
branch:
created: 2026-10-13
tags: [tooling, governance, ai, hardening]
---

# ai-portability 後續項目

## 來源與搬移理由

這份清單原本是 `docs/specs/active/ai-portability/tasks.md` 末段「後續項目」（L187–205，共 19 條），依 plan §4 第 4 項、§8.2 原則 6 明確列為「不在本 campaign」的範圍。campaign 的最後一顆 commit `6b404ea3a4b029cf9c157d9773442b40d7fee5a8` 已進入 origin/main；結案稽核（Close Campaign agent）因該檔仍有 19 條未勾選而回報 HOLD。為讓 campaign 結案時 `tasks.md` 的未完成項歸零，這 19 條改由本 parked spec 追蹤。

- 內容取自上述 commit 的 `tasks.md` L187–205；可用 `git show 6b404ea3a4b029cf9c157d9773442b40d7fee5a8:docs/specs/active/ai-portability/tasks.md | sed -n '187,205p' | shasum -a 256` 重算，預期 `ab5d37fafa5d249ce2dec613992759ce33d1c4f53f8cfaad26791901b2593f89`。
- 19 條逐字搬入，只改位置；每條仍是未完成項目，搬移不代表任何一條已處理。
- 下列五個分組標題是搬移時新增，不在原文；組內保持原順序。
- 條目中的 `notes.md §…`、`plan §…` 等章節引用，指的是 `docs/specs/active/ai-portability/` 內的同名檔案；該目錄若已依 `docs/specs/README.md` 歸檔，改到 `docs/specs/archive/` 下對應子目錄查。
- 檔末「搬移後新增」小節的項目是搬移之後才加入的，不在原 19 條內。該小節的兩項已於 2026-10-13 處理並標為 `[x]`；第二項裡「`ai` scope 是否列入」的決定不是文件錯字，已拆成一條新的未完成項。因此全檔 `^- \[ \] ` 共 20 條（原 19 條加上拆出的 1 條）。原 19 條的排序 digest 以該小節之前的內容重算：`sed '/^## 搬移後新增/,$d' docs/specs/parked/ai-portability-followups.md | grep '^- \[ \] ' | LC_ALL=C sort | shasum -a 256`，預期 `c2388828dc3d64cd5821e61ca680cd1473ffee59541a35ce50c40cb0f0c9408c`。

## ① CI 接線

- [ ] 把 `sync --check` 與新 pytest 接進 CI／githook（目前無）

## ② hook 繞過強化

- [ ] 字元層混淆偵測（`$'\x67it'`、`g''it`、變數拼接）
- [ ] `xargs`／`env VAR=… git` 深層遞迴
- [ ] 裸 `git stash`
- [ ] `--no-verify`
- [ ] 經變數間接引用的 `source "$F"`／`. "$f"`
- [ ] `$VAR` 在 guarded 命令參數位置
- [ ] 敏感路徑的父目錄遞迴搜尋與 symlink／alias 偵測（plan §7 規則 7 邊界）
- [ ] `find -exec`、git alias（`git -c alias.x=…`、既有 alias）、`uv run`／`npx` 等未解包的包裝動詞

## ③ production 寫入邊界

- [ ] script 介面的 production 寫入（`update_source.py`、`qa_auto_fix.py` 等）
- [ ] SQL 函式副作用偵測（plan §7 規則 9 殘餘風險）
- [ ] （H-C1 ⑤）Supabase CLI Management APIs（`secrets`、`functions`、`storage`、`projects`、`branches`、`config` 等會改 production 設定的子命令）不在規則 9 範圍
- [ ] （H-C1 ⑩）claude.ai 帳號層 Supabase MCP 連接器（`mcp__claude_ai_Supabase__execute_sql`、`apply_migration`、`deploy_edge_function` 等）不在規則 9 範圍；評估 `permissions.ask`／deny

## ④ 角色重新設計

- [ ] X1–X4 裁決後的 Phase B′／C′
- [ ] reviewer 改投影為 readonly（plan §6 X2）。注意：reviewer 本文以 Bash 查 Supabase 與執行 git，plan 的 readonly 角色（無 Bash）不適用，需另定角色（notes.md §4.9）
- [ ] reviewer 重新定位（H-B1 使用者新增）：功能 1（爬蟲健康）、2（Skills 新鮮度）已由 `monthly_health_check.yml` 的自動報告與 weekly-review 涵蓋，功能 4（結案檢核）與 campaign-closer 互補，只有功能 3（agent scope 分析）獨有；決定保留、縮減、併入他角色或退役，並同步 X2（notes.md §4.10）
- [ ] 受限角色本文的「After Fixing Any Error」寫檔指示（H-B1 f1）：tester L39–40、plan-critic L96–97、lianbu-spokesperson L133–134 要求更新 history.md／SKILL.md，但投影後工具層無 Edit／Write（lianbu 也無 Bash）。B 暫以 `AGENTS.md` 說明「教訓以文字回報，交 Update History, Skill, Agent 或使用者寫入」；後續改寫三檔本文，並考慮為 plan-critic、lianbu 補 update-history handoff（notes.md §4.9）

## ⑤ 維護

- [ ] 升級 Claude Code 後重跑 B-0／C-0 的 fixture（本 campaign 不做自動化）
- [ ] （H-A1 F5）把 `scraper/researcher.py`／`scraper/update_source.py` 的研究資料目錄移出 legacy 名稱 `.copilot-tracking/research/`，並同步 researcher agent／SKILL、`git.instructions.md` 例外句與 runbook L299 註記。理由：目錄名看似可清除的 legacy scratch；路徑以腳本位置推算，每個 worktree 各有一份（主工作樹的 profile 在其他 worktree 看不到）。需改 `scraper/**`，另案處理

## 清單邊界說明

直接寫的 `source .env`／`. .env` 由規則 7 層 3 拒絕，`Edit`／`Write` 寫 `.env*` 由規則 7 工具層拒絕，皆已在第一批範圍內，不列後續項。

## 搬移後新增（非原有 19 條）

下列兩項不是從 `tasks.md` 搬來的原文，而是 2026-10-13 在 V-M-D 推送並驗證 `f6c2dad2d7c898174504b1a58be684c0e97c9021` 時確認的文件錯誤；先前只散見於 `notes.md` §4.32，沒有任何清單追蹤。兩者都在 `.github/agents/validate-merge-deploy.agent.md`，行號為 `f6c2dad2` 當時的行號。處理時請依 `.github/instructions/git.instructions.md` 另開或指定 worktree，不要依賴 `ai-portability` 的 campaign worktree 仍然存在。兩項已於 2026-10-13 在 campaign `closeout-audit-multirange` 處理，見各條。

- [x] 修正「docs-only commit 不觸發 Vercel」的宣稱：L134 該半句、L174、L196、L204。實測兩次 docs-only push（`86fdc143`、`f6c2dad2`）各產生 1 個 Production deployment 且皆為 success（後者 deployment id `7025806771`），成因未調查。修正要精準：「docs-only 跳過本機 `pnpm run build`」的判斷不變，只改 Vercel 的部分，改為以 exact-SHA 實查 deployment，不再預設記為 `NOT APPLICABLE`。另在 `.github/skills/agents/engineer/history.md` 補一則更正（該檔 append-only，L174 的舊條目不改）（notes.md §4.32）。**已處理（2026-10-13）**：V-M-D Step 3 保留跳過本機 build 的判斷，Step 5 改為每次 push 都以 exact-SHA 實查，查無才記 `NONE FOUND (non-web push)`；`engineer/history.md` 已補更正條目。實測又多了兩次（`87c2b557` deployment id `7032193512`、`6672b320` deployment id `7033673184`），共四次非 web push 都產生 Production deployment，成因仍未調查。
- [x] 同檔 L155 引用不存在的 `.github/instructions/commit-message.instructions.md`：改指向 `.github/instructions/git.instructions.md` 的 Commit message conventions，或補建該檔；同時決定 `ai` scope 是否加入 `git.instructions.md` 的 scope 清單（目前列 `scraper`／`web`／`db`／`ci`／`agents`，本 campaign 的 commit 都用 `docs(ai)`／`chore(ai)`）（notes.md §4.32）。**引用已修正（2026-10-13）**：改指向 `git.instructions.md` § Commit message conventions，未補建該檔。scope 的決定拆在下一條。
- [ ] （自上一條拆出）決定 `ai` scope，以及近期 history 已在用但未列出的 scope（例如 `governance`、`skills`、`deps`、`evaluation`），是否列入 `.github/instructions/git.instructions.md` 的 scope 清單（目前列 `scraper`／`web`／`db`／`ci`／`agents`）。這是慣例決定，不是文件錯字，未在 2026-10-13 的處理內做出
