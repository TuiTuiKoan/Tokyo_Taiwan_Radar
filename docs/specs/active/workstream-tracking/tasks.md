# Tasks

本檔是工作線盤點的**權威持久位置**。所有數字都是快照，不是真值。

---

## Snapshot 基準

* 觀測日期：**2026-08-08**
* `origin/main`：`5d6e4a43`（docs(agents): require worktree confirmation before implementation）
* 註冊拓撲：1 main + 5 canonical child + 3 case-split registration + 1 external
* 下次更新時請一併更新本區塊，否則勾選狀態會腐化

---

## Phase 0: 重新查證（每次開始前必做）

- [x] 執行下方查證指令，回報與 snapshot 的差異
- [x] 就地更新本檔數字與 Snapshot 基準
- [x] Worktree 註冊路徑拓撲有重大差異，已同步更新 [proposal.md](./proposal.md)

```bash
cd '/Users/flyingship/Development/Tokyo Taiwan Radar' && git fetch origin main -q
export GIT_OPTIONAL_LOCKS=0

git --no-pager log origin/main --oneline -1

# 完整路徑是證據。不可先 basename，也不可只看 pwd -P。
canonical_root=$(pwd -P)
wt_file="${TMPDIR:-/tmp}/ttr-worktrees.$$"
git worktree list --porcelain | sed -n 's/^worktree //p' > "$wt_file"
while IFS= read -r p; do
      physical_path=$(cd "$p" && pwd -P) || {
            printf 'UNREACHABLE registered=%s\n' "$p"
            continue
      }
      if [[ "$physical_path" == "$canonical_root" ]]; then
            path_class=canonical-main
      elif [[ "$physical_path" == "$canonical_root/"* ]]; then
            if [[ "$p" == "$physical_path" ]]; then
                  path_class=canonical-child
            else
                  path_class=case-split-registration
            fi
      else
            path_class=external
      fi
      branch_name=$(git -C "$p" branch --show-current 2>/dev/null)
      ahead_behind=$(git -C "$p" rev-list --left-right --count HEAD...origin/main 2>/dev/null | tr '\t' '/')
      dirty_count=$(git -C "$p" status --porcelain=v1 --untracked-files=all 2>/dev/null | wc -l | tr -d ' ')
      printf 'class=%s\nregistered=%s\nphysical=%s\nbranch=%s ahead/behind=%s dirty=%s\n\n' \
            "$path_class" "$p" "$physical_path" "$branch_name" "$ahead_behind" "$dirty_count"
done < "$wt_file"
rm -f "$wt_file"

find docs/specs/active -mindepth 1 -maxdepth 1 -type d -print | sort
git status --short -- .github/prompts/
```

---

## Worktree 註冊路徑拓撲

Git 的 registered path 與檔案系統 physical path 是兩種不同證據。下表保留 Git
`--porcelain` 的完整註冊字串；basename 只在其他摘要表中作顯示用途。

| Path class | Registered path | Physical path (`pwd -P`) | Branch |
|---|---|---|---|
| canonical main | `/Users/flyingship/Development/Tokyo Taiwan Radar` | `/Users/flyingship/Development/Tokyo Taiwan Radar` | `main` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `feat/admin-qa-cleanup` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `feat/authoritative-venue-repair` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `feat/evaluation-framework` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-event-report-writer-safety-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-event-report-writer-safety-worktree` | `fix/event-report-writer-safety` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `feat/japan-scope-gate` |
| case-split registration | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `feat/publication-policy` |
| case-split registration | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-taiwan-expo-japan-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-taiwan-expo-japan-worktree` | `feat/taiwan-expo-japan` |
| case-split registration | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-v8-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-v8-worktree` | `feat/event-intake-wizard` |
| external | `/Users/flyingship/development/ttr-security-hardening-worktree` | `/Users/flyingship/Development/ttr-security-hardening-worktree` | `feat/security-hardening-report-only-csp` |

大小寫兩條 repo parent path 在目前檔案系統解析到相同 device/inode：
`/Users/flyingship/Development` 與 `/Users/flyingship/development` 都是
device `16777233`、inode `535486743`；兩條 `Tokyo Taiwan Radar` 都是 inode
`553836739`。這證明前三筆是 Git lexical registration drift，不是重複實體目錄。
`security-hardening` 的 physical path 則在 repo root 之外。

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
- [x] 長期展區排除 — `ab3bbfde`
- [x] 詳情頁區塊標題「出版情報」— `ab3bbfde`
- [x] 後台出版社標籤 — `admin.publisher` / `admin.publisherUrl` / `admin.publisherPlaceholder`（`ab3bbfde`）
- [ ] dashboard error 卡片（無歸屬）
- [ ] 後台重置按鈕（無歸屬）
- [ ] 架構頁 service_role 標示（無歸屬）
- [ ] i18n 標籤統一（無歸屬）

前三項已於 `ttr-publication-policy-worktree` 交付（`ab3bbfde`，8 檔 `+191/−6`），
含兩個純函式 seam（`getOrganizerSectionTitleKey`／`getOrganizerFieldLabelKeys`）與測試。

---

## 工作線 E：ABCD 以外

- [x] Eslite identity migration
- [x] Hybrid `70cf7002` 場地／報名 URL 分離
- [x] F-1 詳情頁隱藏會場列（`831871e0`）
- [ ] Authoritative venue repair（進行中）
- [ ] F-2 `container_title` 專屬欄位（需 migration）
- [x] 決策閘門規則寫入 `SKILL.md`（`335e462a`）
- [x] Worktree 確認閘門已進入 `origin/main`（`5d6e4a43`）

---

## 未納入編號的工作線

需決定是否納入 A–E 或另立編號。

| Worktree | ahead/behind | dirty | 判讀 |
|---|---|---|---|
| `ttr-japan-scope-gate-worktree` | 11/7 | 16 | 活躍，規模不小 |
| `ttr-evaluation-framework-worktree` | 0/12 | 0 | 待同步 |
| `ttr-event-report-writer-safety-worktree` | 0/66 | 0 | 停滯 |
| `ttr-taiwan-expo-japan-worktree` | 0/40 | 0 | 停滯；case-split registration |
| `ttr-v8-worktree` | 0/127 | 3 | 嚴重停滯；case-split registration |
| `ttr-security-hardening-worktree` | 0/74 | 0 | 停滯；external registration |

---

## 三方對照：工作線 ↔ worktree ↔ spec

| 工作線 | Worktree | ahead/behind | dirty | Spec |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree` | 0/0 | 0 | **未建立** |
| A（predecessor） | 已移除 | — | — | `admin-reports-204-cleanup`（保留 active） |
| B | `ttr-publication-policy-worktree`（case-split） | 3/0 | 0 | `publication-policy` |
| C | **無** | — | — | **無** |
| D | publication worktree + 無歸屬 backlog | — | — | **無** |
| E（venue repair） | `ttr-authoritative-venue-repair-worktree` | 11/12 | 0 | **未建立** |
| 未編號 | japan-scope-gate | 11/7 | 16 | 無 |
| 未編號 | evaluation-framework | 0/12 | 0 | `evaluation-framework` |
| 未編號 | event-report-writer-safety | 0/66 | 0 | 無 |
| 未編號 | taiwan-expo-japan（case-split） | 0/40 | 0 | 無 |
| 未編號 | v8 / event-intake-wizard（case-split） | 0/127 | 3 | 無 |
| 未編號 | security-hardening（external） | 0/74 | 0 | 無 |
| —（主工作樹） | `Tokyo Taiwan Radar` | 0/0 | 1 | `workstream-tracking`（governance-only） |

位於 `docs/specs/active/`、但無 dedicated linked worktree 的 spec 目錄（14，含
grandfathered、frontmatter status 漂移與 governance-only）：
`admin-report-workflow`、`admin-reports-204-cleanup`、`autoresearch-auto-scraper`、
`bauhaus-design-system`、`japan-open-data-integration`、`market-positioning-strategy`、
`merger-multi-signal-pass4`、`product-c-opportunity-radar`、`report-prototype-gap-fix`、
`seo-polish`、`spec-architecture-dashboard`、`tier1-data-completion`、
`works-entity-for-films-and-tours`、`workstream-tracking`。

---

## 治理缺口

### G1: prompt 版控

- [x] 三個 prompt 納入版控（`7598b411`）

### G2: Linked worktree 缺 matching spec 目錄

9 個 linked worktree 中有 7 個沒有 `docs/specs/active/` 下的同 branch spec 目錄。
依狀態分流，不把 grandfathered 停滯 branch 一律判成新規則違規。

- [ ] `ttr-authoritative-venue-repair-worktree`（ahead 11）補建 spec
- [ ] `ttr-japan-scope-gate-worktree`（ahead 11）補建 spec 或明確指定既有 spec
- [ ] `ttr-admin-qa-cleanup-worktree` 的 successor spec 待其 prompt 執行時建立
- [ ] event-report-writer-safety、taiwan-expo-japan、v8、security-hardening 先走 G3
      去留判定；未決定繼續前不追建 spec

### G3: 停滯 worktree 去留

落後幅度持續擴大（2026-08-06 → 08-08 各 +2），rebase 成本只會更高。

- [ ] `ttr-v8-worktree`（behind 127，dirty 3；case-split registration）
- [ ] `ttr-security-hardening-worktree`（behind 74；external registration）
- [ ] `ttr-event-report-writer-safety-worktree`（behind 66）
- [ ] `ttr-taiwan-expo-japan-worktree`（behind 40；case-split registration）

決定前必須查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

### G4: 其他

- [x] `.git/info/exclude` 補上 `ttr-admin-qa-cleanup-worktree/`，並清除兩個已不存在的
      殘留項目（`ttr-admin-reports-204-cleanup-worktree/`、`ttr-organizer-authority-wave2-worktree/`）。
      刪除前已驗證兩者皆無目錄、無 worktree 註冊、無對應分支。
      目前實體位於 project root 內的 8 個 linked worktree basename 全數排除。
      `security-hardening` 位於 project root 外，不適用該 exclude；主工作樹目前 dirty 1
      是使用者的 tracked `README.md`，不是 linked worktree untracked noise
- [ ] Dependabot 回報 9 個依賴漏洞（8 high、1 moderate），與本專案工作無關但需處理。
      **性質上不屬於工作線盤點**，僅暫置於此；建議另立資安維護歸屬

#### G4 依賴維護：固定驗收集合（2026-08-10 重查，9 筆皆 `open`）

以 alert identity 作終局判定，不以 alert 總數代替。

| Alert | GHSA | package | severity | first patched |
|---|---|---|---|---|
| #45 | GHSA-f88m-g3jw-g9cj | `sharp` | high | 0.35.0 |
| #50 | GHSA-3jxr-9vmj-r5cp | `brace-expansion` | high | 1.1.16 |
| #51 | GHSA-r28c-9q8g-f849 | `postcss` | high | 8.5.18 |
| #53 | GHSA-mh99-v99m-4gvg | `brace-expansion` | high | 5.0.8 |
| #54 | GHSA-rgw5-rvv9-x895 | `brace-expansion` | high | 5.0.9 |
| #60 | GHSA-fxqj-rqcc-2cmp | `postcss` | medium | 8.5.23 |
| #61 | GHSA-5p4m-2wfm-xmqj | `js-yaml` | high | 4.3.1 |
| #62 | GHSA-5p4m-2wfm-xmqj | `js-yaml` | high | 3.15.1 |
| #63 | GHSA-2v37-7h3g-55p8 | `nanoid` | high | 3.3.17 |

全 9 筆 manifest 皆為 `web/pnpm-lock.yaml`。

#### G4 Phase 1：PR #205 驗證於本機環境受阻

- [ ] PR #205（`chore(deps)`，minor-and-patch group，15 updates）尚未驗證，**未 merge**

已確認的事實：

- exact `baseRefOid` `ebf3daae`、`headRefOid` `ec8a26c4`，changed files 僅
  `web/package.json`、`web/pnpm-lock.yaml`，符合 scope 限制
- dependency-file drift gate `ebf3daae..origin/main` 輸出為空，main 對這兩個檔案零漂移，
  不需 `@dependabot rebase`

阻擋原因為**本機 registry 不可達**，不是 PR 本身缺陷，也不構成 `BLOCKED_BY_UPSTREAM`：

- 本機 npm registry 被 `~/.npmrc`、`/usr/local/etc/npmrc`、`/opt/homebrew/etc/npmrc`
  設為 `https://packagefeedproxy.microsoft.io/npm/`；repo 未追蹤任何 `.npmrc`，
  CI 與 Vercel 實際使用的目標 registry 是公開 npm
- 該 proxy 對較新版本回 404（`electron-to-chromium@1.5.402`、`node-releases@2.0.53`、
  `nanoid@3.3.18`、`postcss@8.5.26`），較舊版本（如 `electron-to-chromium@1.5.350`）則正常
- **控制組證明屬環境問題**：`origin/main` 自己的 lockfile 走同一 proxy 亦
  `ERR_PNPM_FETCH_404` 失敗，與 PR #205 無關
- `registry.npmjs.org` 在 sandbox 內外皆不可達（`Recv failure: Socket is not connected`）

因此 9 筆 identity 現況一律為 `OPEN`，無任何一筆可判為 `FIXED` 或 `BLOCKED_BY_UPSTREAM`。
未使用 `dismissed`、未 ignore audit、未降低 audit level。

下一步需先恢復對目標 registry 的存取（移除本機 proxy 設定或改用可達公開 npm 的環境），
再重跑 Phase 1B 完整驗證。

### G5: Worktree 註冊路徑漂移

- [x] 保存 10 個 worktree 的完整 registered path、physical path 與 path class 證據
- [x] 證明 `Development`／`development` 解析為相同 inode，不是兩套實體 repo
- [ ] 另案決定是否將 publication-policy、taiwan-expo-japan、v8 的 Git lexical
      registration 正規化為 canonical `Development` 路徑
- [ ] 另案決定 security-hardening 應搬回 project root，或正式 grandfather 為 external

本次只更新證據，不授權 `git worktree move`、remove/re-add、repair 或手改 `.git/worktrees`。

---

## 操作教訓

### Worktree 確認閘門（已寫入 `SKILL.md`，`335e462a`；agent 指示 `5d6e4a43`）

任何功能實作前必須由使用者明確指定 worktree；主工作樹只處理治理、盤點、文件、spec
維護與狀態對帳。Small change 也不得自行落在主工作樹。這取代先前「主工作樹 dirty
時才改走 owning worktree」的條件式建議。

2026-08-06 實證：21 小時殘留 `index.lock`、他人 commit 落在同一分支差點被夾帶推送、
rebase 前需備份 11 個他人 WIP 檔。2026-08-08 又發現跨四天的 11 檔 agent 教訓 WIP
長期懸在主工作樹，因此改為無條件確認閘門。

### 完整 registered path 才是 worktree 身分證據

`basename "$path"` 只能作顯示，不能作 inventory identity 或 root-containment 判斷。
稽核必須同時保存：

1. `git worktree list --porcelain` 的 registered path，辨識 Git lexical drift。
2. `cd "$path" && pwd -P` 的 physical path，辨識同 inode alias 與 project 外 placement。
3. Branch、ahead/behind、dirty，避免同名目錄或 relocation 後把工作線對錯。

只看 registered path 會把大小寫 alias 誤判成兩套目錄；只看 physical path 會抹掉 Git
保存的小寫 registration；只看 basename 則兩種問題都看不見。

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
* macOS 路徑解析可能不分大小寫，但 Git 仍保存原始 lexical registration；
      `Development` 與 `development` 不可在文字證據中互換
* Worktree 可以註冊在 project root 外；以 basename 或 `.git/info/exclude` 推定 containment
      會把 external worktree 誤報為 nested
* zsh 的 `[ "$a" \> "$b" ]` 不支援字串比較，噴 `condition expected`；改用 `sort`
* `grep -c` 命中 0 時 exit code 為 1，會中斷 `&&` 鏈；需加 `|| true`
* `cmd && echo '(空=乾淨)'` 不論有無輸出都會印，是**無效驗證**
* `ln -sfn <src> <dir>` 若 target 已是實體目錄，會在其中建立巢狀連結

---

## Verification

- [x] Phase 0 查證指令已重跑，數字已更新
- [x] 三方對照表與 live 狀態一致
- [x] 完整 registered path、physical path 與 path class 已保留
- [x] 治理缺口各有明確建議與所需批准
- [x] 未執行任何 worktree/branch/spec 變更或 production 寫入
