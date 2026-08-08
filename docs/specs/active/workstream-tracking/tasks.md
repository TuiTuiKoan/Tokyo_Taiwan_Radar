# Tasks

本檔是工作線盤點的**權威持久位置**。所有數字都是快照，不是真值。

---

## Snapshot 基準

* 觀測日期：**2026-08-08**
* `origin/main`：`7598b411`（docs(prompts): track admin-qa, venue-repair and workstream prompts）
* 下次更新時請一併更新本區塊，否則勾選狀態會腐化

---

## Phase 0: 重新查證（每次開始前必做）

- [ ] 執行下方查證指令，回報與 snapshot 的差異
- [ ] 就地更新本檔數字與 Snapshot 基準
- [ ] 差異重大時（例如 worktree 增減、spec 增減），同步更新 [proposal.md](./proposal.md)

```bash
cd '/Users/flyingship/Development/Tokyo Taiwan Radar' && git fetch origin main -q

git --no-pager log origin/main --oneline -1

# 所有 worktree（路徑含空白，不可用 awk $2）
git worktree list --porcelain | sed -n 's/^worktree //p' > /tmp/wt.txt
while IFS= read -r p; do
  n=$(basename "$p")
  b=$(git -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)
  ab=$(git -C "$p" rev-list --left-right --count HEAD...origin/main 2>/dev/null | tr '\t' '/')
  d=$(git -C "$p" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  printf '%-44s %-40s %-9s dirty=%s\n' "$n" "$b" "$ab" "$d"
done < /tmp/wt.txt; rm -f /tmp/wt.txt

ls docs/specs/active/
git status --short -- .github/prompts/
```

---

## 工作線 A：Admin Reports Cleanup

原 bounded campaign 已結案（Phase 0–4、Lane R、Lane A、Lane O，14 筆報告由
`error_recovery` 結案）。剩餘工作改以 successor 模式進行。

- [x] 確認舊 worktree/branch 移除**非工作遺失**：`65253c74` 是 `origin/main` 祖先；
      孤兒 `df0a2bd6`／`22324418` 僅為 amend 殘留，唯一差異 2 行措辭
- [x] Successor worktree `ttr-admin-qa-cleanup-worktree` 已建立
- [ ] Successor spec `docs/specs/active/admin-qa-cleanup/` 建立
- [ ] 重數 predecessor `tasks.md`（2026-08-06 觀測為 60 完成／39 未完成）
- [ ] 查證 Lane R 是否正式取代已退休的 T-P；證據不足時標為 blocker
- [ ] Final docs-only archive 批准後才移動 predecessor spec

**禁止**：重建 `ttr-admin-reports-204-cleanup-worktree` 或 `feat/admin-reports-204-cleanup`。
Predecessor spec 的 `notes.md` 在 archive 前必須 byte-for-byte 不變。

---

## 工作線 B：出版品 null 政策回歸

已交付：PN-1 五個 enrichment 守衛、W-1 planner 修正、phase-aware executor、
Eslite identity migration、PN-3a.0（`b4cb383f`）、F-1（`831871e0`）。

- [ ] backfill `--apply` — 16 筆 `raw_description`，**production 寫入**
- [ ] 重新標註，讓期刊名傳播到 `description_*`
- [ ] 產生新 cleanup manifest（舊的已作廢）
- [ ] **PN-3a** `fc-remove`
- [ ] **PN-3b** `event-clear` — 必須與 3a **同一窗口**（`fc-remove.after` 同時是 3b 的 before gate）
- [ ] PN-4 驗證與觀察
- [ ] PN-W1 poster 殘留 9 筆（`start_date`／`organizer`，需新 phase）
- [ ] 更新過期的 publication-policy spec ledger

每一步各自需要核准。

---

## 工作線 C：organizer 缺漏

完全未開始，無 spec、無 worktree。原始 71 筆是舊 baseline。

- [ ] 重新盤點實際筆數
- [ ] MO-1 `wuext_waseda` 補登記
- [ ] MO-2 來源預設值
- [ ] MO-3 偵測器範圍
- [ ] MO-4 平台爬蟲

---

## 工作線 D：Backlog

- [x] `organizer_type` 政策
- [x] 維持共用欄位（決議，無需實作）
- [ ] 長期展區排除 — WIP 在 publication worktree
- [ ] 詳情頁區塊標題「出版情報」— i18n key 已在上游，只缺程式碼
- [ ] 後台出版社標籤 — `admin.publisher` / `admin.publisherUrl`
- [ ] dashboard error 卡片（無歸屬）
- [ ] 後台重置按鈕（無歸屬）
- [ ] 架構頁 service_role 標示（無歸屬）
- [ ] i18n 標籤統一（無歸屬）

前三項的 WIP 為 7 檔 `+76/−6`，在 `ttr-publication-policy-worktree`。

---

## 工作線 E：ABCD 以外

- [x] Eslite identity migration
- [x] Hybrid `70cf7002` 場地／報名 URL 分離
- [x] F-1 詳情頁隱藏會場列（`831871e0`）
- [ ] Authoritative venue repair（進行中）
- [ ] F-2 `container_title` 專屬欄位（需 migration）
- [ ] 決策閘門規則寫入 `SKILL.md`

---

## 未納入編號的工作線

需決定是否納入 A–E 或另立編號。

| Worktree | ahead/behind | dirty | 判讀 |
|---|---|---|---|
| `ttr-japan-scope-gate-worktree` | 11/1 | 16 | 活躍，規模不小 |
| `ttr-evaluation-framework-worktree` | 0/6 | 0 | 待同步 |
| `ttr-event-report-writer-safety-worktree` | 0/60 | 0 | 停滯 |
| `ttr-taiwan-expo-japan-worktree` | 0/34 | 0 | 停滯 |
| `ttr-v8-worktree` | 0/121 | 3 | 嚴重停滯 |
| `ttr-security-hardening-worktree` | 0/68 | 0 | 停滯 |

---

## 三方對照：工作線 ↔ worktree ↔ spec

| 工作線 | Worktree | ahead/behind | dirty | Spec |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree` | 0/0 | 0 | **未建立** |
| A（predecessor） | 已移除 | — | — | `admin-reports-204-cleanup`（保留 active） |
| B | `ttr-publication-policy-worktree` | 0/3 | 7 | `publication-policy` |
| C | **無** | — | — | **無** |
| D | 主工作樹 + publication worktree | — | — | **無** |
| E（venue repair） | `ttr-authoritative-venue-repair-worktree` | 11/6 | 0 | **未建立** |
| 未編號 | japan-scope-gate | 11/1 | 16 | 無 |
| 未編號 | evaluation-framework | 0/6 | 0 | `evaluation-framework` |
| 未編號 | event-report-writer-safety | 0/60 | 0 | 無 |
| 未編號 | taiwan-expo-japan | 0/34 | 0 | 無 |
| 未編號 | v8 / event-intake-wizard | 0/121 | 3 | 無 |
| 未編號 | security-hardening | 0/68 | 0 | 無 |
| —（主工作樹） | `Tokyo Taiwan Radar` | 0/0 | 12 | — |

無 worktree 的 spec（12）：`admin-report-workflow`、`autoresearch-auto-scraper`、
`bauhaus-design-system`、`japan-open-data-integration`、`market-positioning-strategy`、
`merger-multi-signal-pass4`、`product-c-opportunity-radar`、`report-prototype-gap-fix`、
`seo-polish`、`spec-architecture-dashboard`、`tier1-data-completion`、
`works-entity-for-films-and-tours`。

---

## 治理缺口

### G1: prompt 版控

- [x] 三個 prompt 納入版控（`7598b411`）

### G2: 有 commit 卻無 spec

違反 Architect 的 spec ⟺ worktree 一對一規則。

- [ ] `ttr-authoritative-venue-repair-worktree`（11 commits）補建 spec
- [ ] `ttr-admin-qa-cleanup-worktree` 的 spec 待其 prompt 執行時建立

### G3: 停滯 worktree 去留

落後幅度持續擴大（2026-08-06 → 08-08 各 +2），rebase 成本只會更高。

- [ ] `ttr-v8-worktree`（behind 121，dirty 3 需先確認）
- [ ] `ttr-security-hardening-worktree`（68）
- [ ] `ttr-event-report-writer-safety-worktree`（60）
- [ ] `ttr-taiwan-expo-japan-worktree`（34）

決定前必須查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

### G4: 其他

- [x] `.git/info/exclude` 補上 `ttr-admin-qa-cleanup-worktree/`，並清除兩個已不存在的
      殘留項目（`ttr-admin-reports-204-cleanup-worktree/`、`ttr-organizer-authority-wave2-worktree/`）。
      刪除前已驗證兩者皆無目錄、無 worktree 註冊、無對應分支。
      現存 8 個 worktree 全數排除，主工作樹 `git status` 的 untracked 清單已清空
- [ ] Dependabot 回報 9 個依賴漏洞（8 high、1 moderate），與本專案工作無關但需處理。
      **性質上不屬於工作線盤點**，僅暫置於此；建議另立資安維護歸屬

---

## 操作教訓

### 決策閘門修正（尚未寫入 `SKILL.md`）

現行「small change → 不開 worktree」隱含假設主工作樹乾淨，但本 repo 經常多 session
同時寫入。建議改為：

> 若主工作樹存在其他 session 的未提交變更，即使是 small change，
> 也應在該工作線的 owning worktree 進行。

2026-08-06 實證：21 小時殘留 `index.lock`、他人 commit 落在同一分支差點被夾帶推送、
rebase 前需備份 11 個他人 WIP 檔。

### 只推自己 commit

本地分支有他人未推送 commit 時，`git push` 會**全部**送出。

```bash
git worktree add --detach "$TMPDIR/ttr-<slug>-push" origin/main
# 套用自己的 patch、提交
git push origin HEAD:main
git worktree remove "$TMPDIR/ttr-<slug>-push"
```

推送前務必 `git log origin/main..HEAD --oneline` 確認範圍。

判斷 commit 是否為上游重複：`git cherry origin/main HEAD`（`-` 前綴 = 已在上游）
或 patch-id 比對。確認重複後 rebase 會自動跳過。

### 清理 worktree 的安全順序

1. 匯出 WIP patch 備份，用 `git apply --check --reverse` 自檢
2. `git -c rebase.autoStash=true rebase origin/main`
3. 內容已在上游的 commit 會被自動跳過
4. autostash 衝突時保留雙方，解決後 `git add`
5. 確認 stash 內容已反映於工作區，才 `git stash drop`
6. 最後 `git reset` 還原為未暫存，避免下個 session 無 pathspec 的 `git commit` 誤掃

### 本 repo 實測的 shell 陷阱

* worktree 路徑含空白（`Tokyo Taiwan Radar`），`awk '{print $2}'` 只取到 `Tokyo`
* zsh 的 `[ "$a" \> "$b" ]` 不支援字串比較，噴 `condition expected`；改用 `sort`
* `grep -c` 命中 0 時 exit code 為 1，會中斷 `&&` 鏈；需加 `|| true`
* `cmd && echo '(空=乾淨)'` 不論有無輸出都會印，是**無效驗證**
* `ln -sfn <src> <dir>` 若 target 已是實體目錄，會在其中建立巢狀連結

---

## Verification

- [ ] Phase 0 查證指令已重跑，數字已更新
- [ ] 三方對照表與 live 狀態一致
- [ ] 治理缺口各有明確建議與所需批准
- [ ] 未執行任何 worktree/branch/spec 變更或 production 寫入
