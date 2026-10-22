---
title: pr-flow-tiering Phase D 資安審查
reviewer: Codex（codex-cli 0.160.0，`codex exec -s read-only`）
reviewed: commit 710a40aa 的 .github/workflows/pr-tier.yml 與 scripts/ci/pr_tier.py（pull_request_target 版本）
date: 2026-10-22
---

> 以下為 Codex 原始報告，未經修改，審查對象是第一版設計。協調者回應與改版內容在文末。

## 結論：修正後合併

`pull_request_target` 的核心做法大致安全：workflow 以 base branch 的程式分類，沒有 checkout 或執行 PR head；但檔案清單可能被 GitHub API 靜默截斷，導致含非文件改動的 PR 被誤判為 Tier 0，這是合併前應先修的 **P1**。此外，owner PR 的 auto-merge 可能在後續新增 commit 後仍然有效，也應修正或確認符合預期。

### 1. `pull_request_target`、注入與權限

- **無問題 — 未 checkout 或執行 PR 程式碼。** [workflow 第 31–46 行](/.github/workflows/pr-tier.yml#L31) checkout 明確指定 `pull_request.base.sha`，並以 `persist-credentials: false` 關閉持久憑證；分類器從 base checkout 執行。其餘 PR 資料只用檔名 API 回應。
- **無問題 — 未見 PR 欄位插入 shell 程式碼。** PR 編號、repo 名稱和 tier 透過 `env` 傳入；標題沒有使用。檔名由 `gh api --jq` 寫入檔案後交給 Python，不會被當 shell 命令解析。可用標題 `$(touch /tmp/pwned)` 或檔名 `docs/$(touch /tmp/pwned).md` 重現檢查：字串不會進入 `run:` 程式文字。
- **P2 — Token 權限偏寬。** [第 15–18 行](/.github/workflows/pr-tier.yml#L15) 對所有 job 授予 `contents: write`、`pull-requests: write`、`issues: write`。只有 auto-merge 步驟需要寫入權限；可將讀檔／分類與標籤／auto-merge 分成 job，或使用步驟級權限，減少遭 workflow／action 漏洞利用時的權限範圍。`contents: write`、`pull-requests: write` 看起來是 `gh pr merge --auto` 和標籤操作所需；`issues: write` 用於 issue 標籤。

### 2. Tier 0 分類繞過與特殊檔案

- **P1 — API 檔案數上限可能造成 Tier 0 誤判。** [workflow 第 44–46 行](/.github/workflows/pr-tier.yml#L44) 對最多 3,000 個檔案的 PR files API 分頁讀取，但超過 API 支援的總數時，GitHub 可能回傳不完整清單；程式沒有驗證檔案清單完整性。重現：PR 包含 `docs/a.md` 及至少 3,000 個 `web/...` 檔案；若 API 回傳部分結果只含 docs，分類器會輸出 `0`，繼而開啟 auto-merge。需明確拒絕超限 PR，或以能完整列舉變更的資料來源核實清單。
- **無問題 — 大小寫、Unicode、空白與換行不會把非 docs 路徑變成 Tier 0。** [分類器第 36–43、64–78 行](/scripts/ci/pr_tier.py#L36) 使用大小寫敏感的 `fnmatchcase`，並以 `/` 分隔路徑；例如 `Docs/a.md`、`docs/../web/a.ts`、`web/a\n docs/b.md` 都不會被分類為 0。前後空白會在第 66 行被去除，但去除後仍須匹配整條允許路徑；單一檔名中的換行也不會由按行解析安全表示，通常會導致保守拒絕或改變拆分結果，不會把 `web/` 改成 `docs/`。不過 API 以 JSON 回應、jq 再輸出逐行文字；這種傳輸格式有換行路徑歧義，宜改用 JSON/可靠分隔格式，避免錯誤解析。
- **無問題 — rename 的舊路徑有納入分類。** [workflow 第 45 行](/.github/workflows/pr-tier.yml#L45) 輸出 `filename` 與 `previous_filename`；測試也有覆蓋 `docs/moved.md` 加 `web/app/moved.md` 的情況。
- **無問題 — symlink、submodule、二進位與刪除不會僅憑檔案類型降級。** 分類器只看路徑，不讀內容；只要變更路徑不是允許的 docs/history 路徑就落入 Tier 2。刪除及 rename 也以 API 路徑判斷，刪除 `web/...` 仍是 Tier 2。前提是 API 清單完整；這正是上述 P1 風險。
- **P2 — Tier 0 不驗證 PR 變更的檔案狀態或內容。** 例如在 `docs/` 建立指向 repo 其他路徑的 symlink，分類依然是 Tier 0；它本身不會改變 workflow 執行，但可能被後續會跟隨 symlink 的文件處理工具解讀。這較像白名單政策風險，建議明確限定允許的文件類型或排除 symlink。

### 3. Gitleaks 與 auto-merge 時序

- **無問題（依設計背景所述規則）— auto-merge 不會因本 workflow 提前完成而跳過 required check。** `gh pr merge --auto` 是設定自動合併；若 ruleset 確實要求 gitleaks，GitHub 應等待該 required check 通過。此判斷依 proposal 所述設定；這次唯讀審查無法查看 GitHub 端實際 ruleset。
- **P1 — 新 commit 可能沿用已啟用的 auto-merge。** `synchronize` 事件會重新分類並重新貼標籤，但 workflow 沒有在 PR 從 Tier 0 升級時撤銷已排定的 auto-merge。若 owner 開了 Tier 0 PR，之後追加非文件改動，分類 job 會改成 Tier 2，然而既有 auto-merge 設定可能仍在；gitleaks 通過後仍可能自動合併。重現：owner 開 `docs/a.md` PR → workflow 啟用 auto-merge → push `web/app/page.tsx` → workflow 改貼 Tier 2 → required gitleaks 綠燈。應在每次同步時確認／撤銷不再符合 Tier 0 的 auto-merge，或採用能綁定最新 head SHA 的合併閘門。

### 4. PR 類型與開啟者

- **無問題 — fork PR 與 Dependabot PR 被跳過。** [第 26–28 行](/.github/workflows/pr-tier.yml#L26) 限定同 repo head，並排除 `dependabot[bot]`。代價是這些 PR 不會得到 tier label；與 workflow 註解及提案描述一致。
- **無問題 — draft 不會開啟 auto-merge。** [第 63–67 行](/.github/workflows/pr-tier.yml#L63) 明確排除 draft。`ready_for_review` 會再觸發 workflow。
- **無問題 — 非 owner 開的 PR 不會被自動合併。** 只有 `user.login == github.repository_owner` 才執行 auto-merge；其他同 repo 開啟者仍會被分類、貼標籤。

### 5. Tier 0 docs 白名單對 build、部署與執行的影響

- **P2 — 白名單比 proposal 的排除條件更廣。** [分類器第 23–30 行](/scripts/ci/pr_tier.py#L23) 對 `docs/*` 使用全目錄匹配，只排除 `docs/specs/*` 與 `docs/architecture/*`。搜尋 `web/`、`scraper/`、`.github/workflows` 的實際讀取點，未發現這些程式把其他 `docs/` 檔案讀入 build 或執行；已找到的動態讀取集中於 `docs/specs/` 與 `docs/architecture/system-map.json`，符合明示排除。排查範圍內沒有足以判為 P1 的既有讀取路徑。
- 仍有維護性風險：未來若 workflow／build script 新增讀取 `docs/` 其他子目錄，分類器不會自動察覺。建議採窄白名單（例如明確列出週報、月報等目錄），或為「新增 docs 消費端必須同步更新 tier 規則」建立檢查。
- `.github/skills/**/history.md` 目前只允許固定一層子目錄（例如 `.github/skills/agents/history.md`）；而測試範例包含同層 `SKILL.md` 結構。這是 Tier 0 漏放行問題，會導致分類到 Tier 2，屬保守誤分類，不會造成不安全的 Tier 0 合併。

### 6. 其他風險

- **P2 — 舊 tier label 移除錯誤被忽略。** [第 58–61 行](/.github/workflows/pr-tier.yml#L58) 對移除標籤一律 `|| true`。例如權限或 API 故障使 `tier:0` 未移除，PR 可能同時保留舊 `tier:0` 與新 `tier:2` 標籤；若後續自動化只看 `tier:0`，會有錯誤路由風險。應在移除失敗時讓 job 失敗，或在最後驗證標籤唯一性。
- **P2 — Tier 1 分類規則比 proposal 描述寬。** 分類器只要求檔案落在來源檔、對應 skill 目錄或同 stem 測試檔；不要求 PR 同時包含該來源的 skill 與測試。測試明確允許僅改 `scraper/sources/iwafu.py` 為 Tier 1。這會讓標籤宣稱比實際驗證強，但 Tier 1 不會自動合併，風險低於 Tier 0。
- **P2 — 分類失敗時不會設定新 tier label。** API/分類步驟失敗會中止 job，舊 label 可能留存。若其他流程以 label 作決策，應確保失敗狀態不會被當作有效分類。

整體而言，PR head 未執行與 shell 注入防護方向正確，特殊路徑一般也採保守降級；合併前應優先修正 API 截斷造成 Tier 0 誤判，以及 Tier 0 升級後殘留 auto-merge 的問題。
---

# 協調者回應（Claude Opus 5.5，2026-10-22）

| 批評 | 嚴重度 | 處理 | 說明 |
|---|---|---|---|
| files API 超過 3000 個檔案會截斷，可能誤判 Tier 0 | P1 | 採納 | 分類程式改讀 API 的 JSON，檔案數必須等於 PR 的 `changed_files` 且少於 3000，否則判為 Tier 2。測試涵蓋短少清單、3000 上限、格式錯誤。 |
| auto-merge 開啟後，追加非文件 commit 仍可能沿用 | P1 | 採納，改設計 | 改成不使用 GitHub auto-merge。觸發改為 Secret Scan 對 PR 成功之後的 `workflow_run`，同樣從 default branch 執行；合併以 `--match-head-commit` 綁定被掃描的 commit。新 commit 會讓舊的合併被 GitHub 拒絕，並觸發新的掃描與新的判斷。repo 因此不需要開啟 `allow_auto_merge`。 |
| JSON 轉成逐行文字有換行歧義 | P2 | 採納 | 改成直接把 JSON 交給 Python；路徑含任何控制字元一律 Tier 2，API 檔名不做 trim。 |
| token 權限偏寬 | P2 | 採納 | 拆成兩個 job：`classify` 只有 `contents: read`、`pull-requests: read`；`act` 才有寫入權限，且不 checkout 任何程式碼。 |
| 移除舊 label 的錯誤被忽略 | P2 | 採納 | 只移除實際存在的 tier label，失敗就讓 job 失敗，不再 `|| true`。 |
| `.github/skills/**/history.md` 只允許一層子目錄 | P2 | 駁回 | `fnmatchcase` 的 `*` 會比對 `/`，`.github/skills/agents/architect/history.md` 已由測試證實判為 Tier 0。 |
| docs 下的 symlink 仍判 Tier 0 | P2 | 接受為殘餘風險 | files API 不提供檔案模式。repo 內沒有程式會跟隨 docs 下的 symlink 執行；記錄在 proposal。 |
| Tier 1 比 proposal 描述寬 | P2 | 接受 | Tier 1 只貼 label、不自動合併，寬一點只影響提示，不影響安全。 |
| 分類失敗時舊 label 留存 | P2 | 接受 | 新設計只在分類成功後才改 label；失敗會在 Actions 顯示紅燈。 |
| docs 白名單日後可能漏排除新的消費端 | P2 | 接受 | 目前只有 `docs/specs/` 與 `docs/architecture/` 被 build 讀取，已排除。新增 docs 消費端時要同步更新 `pr_tier.py`，寫進 proposal。 |
