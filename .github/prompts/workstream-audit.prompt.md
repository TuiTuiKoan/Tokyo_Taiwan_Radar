---
description: "重新查證並維護全專案工作線盤點：ABCDE 五線現況、工作線↔worktree↔spec 對照、以及治理缺口"
agent: Architect
---

# Workstream Audit

本 prompt 的單一任務是**重新查證**全專案的工作線盤點，產出一份可信的現況報告：五條主要
工作線（A–E）的進度、未被納入編號體系的工作線、工作線與 worktree 與 spec 的三方對照、
以及已知的治理缺口。

啟動本 prompt 即授權：唯讀 git 查詢、唯讀 Supabase 查詢、讀取 spec 與 prompt 檔案、
更新本 prompt 檔內的 snapshot 區塊、更新 session memory。

啟動本 prompt **不授權**：程式實作、commit、push、deploy、建立或刪除 worktree/branch、
移動或刪除 spec、production DB write、workflow dispatch。任何變更動作都必須先取得明確批准。

## 最高原則：snapshot 不是真值

本文件內所有計數、SHA、ahead/behind、dirty 數都是 **2026-08-08 的觀測快照**。
這個 repo 經常有 3 個以上 session 平行寫入，數字會在數小時內失效。

開始任何分析前，**必須先重跑第 1 節的查證指令並回報差異**。發現與 snapshot 不符時，
以 live 結果為準並更新本檔，不得沿用舊數字做判斷。

---

## 1. 查證指令（先跑這段）

```bash
cd '/Users/flyingship/Development/Tokyo Taiwan Radar' && git fetch origin main -q

# origin/main
git --no-pager log origin/main --oneline -1

# 所有 worktree（注意路徑含空白，不可用 awk $2）
git worktree list --porcelain | sed -n 's/^worktree //p' > /tmp/wt.txt
while IFS= read -r p; do
  n=$(basename "$p")
  b=$(git -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)
  ab=$(git -C "$p" rev-list --left-right --count HEAD...origin/main 2>/dev/null | tr '\t' '/')
  d=$(git -C "$p" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  printf '%-44s %-40s %-9s dirty=%s\n' "$n" "$b" "$ab" "$d"
done < /tmp/wt.txt; rm -f /tmp/wt.txt

# active spec 清單
ls docs/specs/active/

# 未納版控的 prompt
git status --short -- .github/prompts/
```

已知的 shell 陷阱（本 repo 實測）：

* worktree 路徑含空白（`Tokyo Taiwan Radar`），`awk '{print $2}'` 只會取到 `Tokyo`。
* zsh 的 `[ "$a" \> "$b" ]` 不支援字串比較，會噴 `condition expected`。改用 `sort`。
* `grep -c` 命中 0 時 exit code 為 1，會中斷 `&&` 鏈。需加 `|| true`。
* `cmd && echo '(空=乾淨)'` 這種寫法不論有無輸出都會印，是無效驗證。

---

## 2. 五條工作線現況（snapshot 2026-08-08）

編號 A–E 是**任務追蹤分類**，與 worktree（git 隔離機制）和 spec（文件單位）是三個
不同維度，從未設計成一對一。

### A. Admin Reports Cleanup

原 bounded campaign 已結案（Phase 0–4、Lane R、Lane A、Lane O 完成，14 筆報告已由
`error_recovery` 結案）。

剩餘工作改以 **successor 模式** 進行，見 `.github/prompts/admin-qa-cleanup.prompt.md`。

* 舊 worktree 與 branch 已通過防護後移除，**非工作遺失**：已查證 `65253c74` 是
  `origin/main` 祖先；兩個孤兒 commit `df0a2bd6`／`22324418` 僅為 amend 殘留，
  唯一差異是 2 行措辭。
* **禁止**重建 `ttr-admin-reports-204-cleanup-worktree` 或 `feat/admin-reports-204-cleanup`。
* Predecessor spec 在 final archive 另行批准前不得移動或刪除；`notes.md` 必須 byte-for-byte 不變。

### B. 出版品 null 政策回歸

已交付：PN-1 五個 enrichment 守衛、W-1 planner 修正、phase-aware executor、
Eslite identity migration、PN-3a.0（`b4cb383f`）、F-1（`831871e0`）。

未完成，依序且各自需核准：

1. backfill `--apply` — 16 筆 `raw_description`，**production 寫入**
2. 重新標註，讓期刊名傳播到 `description_*`
3. 產生新 cleanup manifest（舊的已作廢）
4. **PN-3a** `fc-remove`
5. **PN-3b** `event-clear` — 必須與 3a **同一窗口**，因 `fc-remove.after` 同時是 3b 的 before gate
6. PN-4 驗證與觀察
7. PN-W1 poster 殘留 9 筆（`start_date`／`organizer`，需新 phase）
8. 更新過期的 spec ledger

### C. organizer 缺漏

完全未開始，無 spec、無 worktree。原始 71 筆是舊 baseline，動工前需重新盤點。

MO-1 `wuext_waseda` 補登記 → MO-2 來源預設值 → MO-3 偵測器範圍 → MO-4 平台爬蟲。

### D. Backlog

已完成：`organizer_type` 政策、維持共用欄位（決議，無需實作）。

未交付，WIP 在 `ttr-publication-policy-worktree`（7 檔 +76/−6）：

1. 長期展區排除 — `eventClassify.ts` + 測試
2. 詳情頁區塊標題「出版情報」— i18n key `event.publicationSection` 已在上游，只缺程式碼
3. 後台出版社標籤 — `admin.publisher` / `admin.publisherUrl`

無歸屬：dashboard error 卡片、後台重置按鈕、架構頁 service_role 標示、i18n 標籤統一。

### E. ABCD 以外的新工作

已完成：Eslite identity migration、hybrid `70cf7002` 場地／報名 URL 分離、F-1 詳情頁隱藏會場列。

進行中：authoritative venue repair。

未開始：F-2 `container_title` 專屬欄位（需 migration）、決策閘門規則寫入 `SKILL.md`。

---

## 3. 未納入 ABCDE 的工作線

這些有 worktree 但從未進入編號體系，**需決定是否納入追蹤**：

| Worktree | ahead/behind | 判讀 |
|---|---|---|
| `ttr-japan-scope-gate-worktree` | 11/1 | 活躍，規模不小 |
| `ttr-evaluation-framework-worktree` | 0/6 | 待同步 |
| `ttr-event-report-writer-safety-worktree` | 0/60 | 停滯 |
| `ttr-taiwan-expo-japan-worktree` | 0/34 | 停滯 |
| `ttr-v8-worktree` | 0/121 | 嚴重停滯 |
| `ttr-security-hardening-worktree` | 0/68 | 停滯 |

---

## 4. 三方對照：工作線 ↔ worktree ↔ spec

`origin/main` = `ebf3daae`（snapshot）

| 工作線 | Worktree | ahead/behind | dirty | Spec |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree` | 0/0 | 0 | **未建立** `admin-qa-cleanup` |
| A（predecessor） | 已移除 | — | — | `admin-reports-204-cleanup`（保留 active） |
| B | `ttr-publication-policy-worktree` | 0/3 | 7 | `publication-policy` |
| C | **無** | — | — | **無** |
| D | 散落：主工作樹 + publication worktree | — | — | **無** |
| E（venue repair） | `ttr-authoritative-venue-repair-worktree` | 11/6 | 0 | **未建立** |
| E（其他） | 主工作樹 + publication worktree | — | — | — |
| 未編號 | japan-scope-gate | 11/1 | 16 | 無 |
| 未編號 | evaluation-framework | 0/6 | 0 | `evaluation-framework` |
| 未編號 | event-report-writer-safety | 0/60 | 0 | 無 |
| 未編號 | taiwan-expo-japan | 0/34 | 0 | 無 |
| 未編號 | v8 / event-intake-wizard | 0/121 | 3 | 無 |
| 未編號 | security-hardening | 0/68 | 0 | 無 |
| —（主工作樹） | `Tokyo Taiwan Radar` | 1/4 | 14 | — |

**不對稱事實**：`docs/specs/active/` 有 **15 個 spec**，但只有 **10 個 worktree**，
且其中僅 3 個能與 spec 直接對應（`publication-policy`、`evaluation-framework`、
`admin-reports-204-cleanup` 的 predecessor）。

無 worktree 的 spec：`admin-report-workflow`、`autoresearch-auto-scraper`、
`bauhaus-design-system`、`japan-open-data-integration`、`market-positioning-strategy`、
`merger-multi-signal-pass4`、`product-c-opportunity-radar`、`report-prototype-gap-fix`、
`seo-polish`、`spec-architecture-dashboard`、`tier1-data-completion`、
`works-entity-for-films-and-tours`。

---

## 5. 治理缺口（需決策）

### 5.1 兩個 prompt 檔未納版控（風險最高）

```
?? .github/prompts/admin-qa-cleanup.prompt.md
?? .github/prompts/authoritative-venue-repair.prompt.md
```

任何 session 執行 `git clean -fd` 或類似清理都會**永久刪除**這兩個檔。以本 repo 平行
作業的密度，這是實際風險而非理論風險。兩者都是完整的 execution-ready prompt，
重寫成本高。

建議：納入版控。

### 5.2 兩個 worktree 有 commit 卻無 spec

* `ttr-authoritative-venue-repair-worktree`：**11 個 commit**，無 spec 目錄
* `ttr-admin-qa-cleanup-worktree`：已建立且乾淨，spec 待該 prompt 執行時建立

Architect 規則要求 spec ⟺ worktree 一對一。前者已明確違反。

建議：補建 `docs/specs/active/authoritative-venue-repair/`。

### 5.3 四個停滯 worktree 待決定去留

| Worktree | behind | dirty |
|---|---|---|
| `ttr-v8-worktree` | 121 | 3 |
| `ttr-security-hardening-worktree` | 68 | 0 |
| `ttr-event-report-writer-safety-worktree` | 60 | 0 |
| `ttr-taiwan-expo-japan-worktree` | 34 | 0 |

落後幅度持續擴大（兩天內各 +2），rebase 成本只會更高。`ttr-v8-worktree` 另有 3 個
未提交檔案需先確認。

決定去留前**必須**先查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

---

## 6. 已確立的治理教訓

### 6.1 決策閘門建議修正（尚未寫入 `SKILL.md`）

現行 Architect 規則「small change → 不開 worktree」隱含假設主工作樹是乾淨的，
但本 repo 經常有多個 session 同時寫入。建議改為：

> 若主工作樹存在其他 session 的未提交變更，即使是 small change，
> 也應在該工作線的 owning worktree 進行。

2026-08-06 實證：主工作樹遇到 21 小時殘留 `index.lock`、他人 commit 落在同一分支上
差點被夾帶推送、rebase 前需備份 11 個他人 WIP 檔。

### 6.2 只推自己 commit 的安全手法

當本地分支上有他人未推送的 commit 時，`git push` 會**全部**送出。安全做法：

```bash
git worktree add --detach "$TMPDIR/ttr-<slug>-push" origin/main
# 套用自己的 patch、提交
git push origin HEAD:main
git worktree remove "$TMPDIR/ttr-<slug>-push"
```

推送前務必 `git log origin/main..HEAD --oneline` 確認範圍。

### 6.3 清理 worktree 的安全順序

1. 匯出 WIP patch 備份，並用 `git apply --check --reverse` 自檢
2. `git -c rebase.autoStash=true rebase origin/main`
3. 內容已在上游的 commit 會被自動跳過（`skipped previously applied commit`）
4. autostash 衝突時保留雙方，解決後 `git add`
5. 確認 stash 內容已反映於工作區，才 `git stash drop`
6. 最後 `git reset` 還原為未暫存狀態，避免下個 session 無 pathspec 的 `git commit` 誤掃

---

## 7. 期望產出

1. 重跑第 1 節指令，回報與 snapshot 的差異，並就地更新本檔數字。
2. 針對第 5 節三個缺口各給明確建議與所需批准。
3. 就第 3 節的未編號工作線，建議是否納入 ABCDE 或另立編號。
4. 不執行任何變更；所有動作留待明確批准。
