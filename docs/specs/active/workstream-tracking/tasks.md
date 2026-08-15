# Tasks

本檔是工作線盤點的**權威持久位置**。所有數字都是快照，不是真值。

---

## Snapshot 基準

* 觀測日期：**2026-08-14**
* `origin/main`：`3b04a6d3`（docs(git): reconcile exclude block instead of deleting a line）
* 註冊拓撲：1 main + 5 canonical child + 8 external（共 14；計數只描述本次快照）
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
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/agent-handoff-and-worktree-cleanup` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/agent-handoff-and-worktree-cleanup` | `agents/agent-handoff-and-worktree-cleanup` |
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/anomaly-detection-workflow-integration` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/anomaly-detection-workflow-integration` | `agents/anomaly-detection-workflow-integration` |
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile` | `agents/ledger-topology-reconcile` |
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconciliation` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconciliation` | `agents/ledger-topology-reconciliation` |
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/mobile-ssh-agent-remote-development` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/mobile-ssh-agent-remote-development` | `agents/mobile-ssh-agent-remote-development` |
| external | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo` | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo` | `agents/tokyo-taiwan-radar-agents-repo` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `feat/admin-qa-cleanup` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `feat/authoritative-venue-repair` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-deps-security-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-deps-security-worktree` | `chore/deps-security` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `feat/evaluation-framework` |
| canonical child | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `feat/japan-scope-gate` |
| external（case-split lexical alias） | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `feat/publication-policy` |
| external（case-split lexical alias） | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-v8-worktree` | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-v8-worktree` | `feat/event-intake-wizard` |

大小寫兩條 repo parent path 在目前檔案系統解析到相同 device/inode：
`/Users/flyingship/Development` 與 `/Users/flyingship/development` 都是
device `16777229`、inode `535486743`；兩條 `Tokyo Taiwan Radar` 都是 inode
`553836739`。2026-08-14 的 canonical `pwd -P` 保留小寫字串，因而把後兩筆分類為
`external`；inode 證據仍證明它們是 lexical alias，不是第二套實體 repo。

### 2026-08-09 Tier 1 合併結案紀錄

三個目標共用封存 `~/ttr-wip-archive/20260810-tier1-manifest`；2026-08-14 現場重驗
`tier1-post-removal-20260809T154251Z.sha256` 為 **103/103 PASS**。三者均以 plain
`git worktree remove` 與 `git branch -d`（exit 0）退役，local／`origin/main` cherry
皆為空，且沒有 remote branch：

| 已退役 worktree | Branch | 退役時 tip | 結果 |
|---|---|---|---|
| `ttr-event-report-writer-safety-worktree` | `fix/event-report-writer-safety` | `18cd501b` | 非強制移除；內容已在 main |
| `ttr-security-hardening-worktree` | `feat/security-hardening-report-only-csp` | `e450c6b4` | 非強制移除；此 tip 即 report-only CSP、baseline security headers 與 smoke test 的交付 commit，仍是 `origin/main` 祖先 |
| `ttr-taiwan-expo-japan-worktree` | `feat/taiwan-expo-japan` | `28e6fcb6` | 非強制移除；內容已在 main |

---

## 工作線 A：Admin Reports Cleanup

原 bounded campaign 已結案（Phase 0–4、Lane R、Lane A、Lane O，14 筆報告由
`error_recovery` 結案）。剩餘工作改以 successor 模式進行。

- [x] 確認舊 worktree/branch 移除**非工作遺失**：`65253c74` 是 `origin/main` 祖先；
      孤兒 `df0a2bd6`／`22324418` 僅為 amend 殘留，唯一差異 2 行措辭
- [x] Successor worktree `ttr-admin-qa-cleanup-worktree` 已建立
- [x] Successor spec `docs/specs/active/admin-qa-cleanup/` 已建立
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
| `agent-handoff-and-worktree-cleanup` | 0/6 | 0 | external；待決定治理歸屬 |
| `anomaly-detection-workflow-integration` | 0/8 | 0 | external；待決定治理歸屬 |
| `ledger-topology-reconcile` | 0/0 | 0 | external；本次治理對帳 |
| `ledger-topology-reconciliation` | 0/0 | 0 | external；待判定與本次治理線的關係 |
| `mobile-ssh-agent-remote-development` | 0/8 | 0 | external；待決定治理歸屬 |
| `tokyo-taiwan-radar-agents-repo` | 0/0 | 0 | external；待決定治理歸屬 |
| `ttr-deps-security-worktree` | 4/21 | 0 | G4 依賴維護 |
| `ttr-evaluation-framework-worktree` | 0/10 | 0 | 待同步 |
| `ttr-japan-scope-gate-worktree` | 11/69 | 16 | 活躍且 dirty，規模不小 |
| `ttr-v8-worktree` | 0/189 | 3 | 嚴重停滯；case-split lexical alias |

---

## 三方對照：工作線 ↔ worktree ↔ spec

| 工作線 | Worktree | ahead/behind | dirty | Spec |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree` | 0/2 | 0 | `active/admin-qa-cleanup` |
| A（predecessor） | 已移除 | — | — | `admin-reports-204-cleanup`（保留 active） |
| B | `ttr-publication-policy-worktree`（case-split lexical alias） | 0/9 | 0 | `active/publication-policy` |
| C | **無** | — | — | **無** |
| D | publication worktree + 無歸屬 backlog | — | — | **無** |
| E（venue repair） | `ttr-authoritative-venue-repair-worktree` | 1/43 | 0 | `active/authoritative-venue-repair` |
| 未編號 | `ttr-evaluation-framework-worktree` | 0/10 | 0 | `active/evaluation-framework` |
| 未編號 | `ttr-japan-scope-gate-worktree` | 11/69 | 16 | 無 matching spec |
| 未編號 | `ttr-v8-worktree` | 0/189 | 3 | 無 matching spec |
| G4 | `ttr-deps-security-worktree` | 4/21 | 0 | 無 matching spec |
| 未編號 | `agent-handoff-and-worktree-cleanup` | 0/6 | 0 | 無 matching spec |
| 未編號 | `anomaly-detection-workflow-integration` | 0/8 | 0 | 無 matching spec |
| 治理 | `ledger-topology-reconcile` | 0/0 | 0 | `active/workstream-tracking`（本次明確指定） |
| 未編號 | `ledger-topology-reconciliation` | 0/0 | 0 | 無 matching spec |
| 未編號 | `mobile-ssh-agent-remote-development` | 0/8 | 0 | 無 matching spec |
| 未編號 | `tokyo-taiwan-radar-agents-repo` | 0/0 | 0 | 無 matching spec |
| —（主工作樹） | `Tokyo Taiwan Radar` | 0/0 | 0 | `active/workstream-tracking`（governance-only） |

### Spec 狀態 inventory（2026-08-14）

實際存在的狀態目錄只有 `docs/specs/active/`（18 個 spec）與
`docs/specs/archive/`（1 個 spec）；不存在 `docs/specs/parked/`。目錄位置與 frontmatter
`status` 不一致者如下：

| Spec 目錄 | Frontmatter `status` |
|---|---|
| `active/japan-open-data-integration` | `done` |
| `active/merger-multi-signal-pass4` | `parked` |
| `active/report-prototype-gap-fix` | `done` |
| `active/tier1-data-completion` | `done` |
| `active/works-entity-for-films-and-tours` | `done` |
| `archive/feedback-loop` | `active` |

其餘 13 個 spec 的目錄位置與 frontmatter 相符。這是雙向 inventory，不把 frontmatter
狀態硬編成不存在的第三個實體目錄。

---

## 治理缺口

### G1: prompt 版控

- [x] 三個 prompt 納入版控（`7598b411`）

### G2: Linked worktree 缺 matching spec 目錄

13 個 linked worktree 中有 9 個沒有同 branch slug 的 active spec；本次治理 worktree
已明確指定 `workstream-tracking`，其餘 8 個仍需依規則生效時間與工作狀態分流：

- [ ] `ttr-japan-scope-gate-worktree` 補建 spec 或明確指定既有 spec
- [ ] `ttr-deps-security-worktree` 決定是否以 G4 ledger 取代 dedicated spec
- [ ] `ttr-v8-worktree` 先走 G3；未決定繼續前不追建 spec
- [ ] `agent-handoff-and-worktree-cleanup`、`anomaly-detection-workflow-integration`、
      `ledger-topology-reconciliation`、`mobile-ssh-agent-remote-development`、
      `tokyo-taiwan-radar-agents-repo` 分別確認 spec 或 grandfathered 身分

### G3: 停滯 worktree 去留

2026-08-14 仍有一筆既有停滯工作線待決定：

- [ ] `ttr-v8-worktree`（behind 189，dirty 3；case-split lexical alias）

決定前必須查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

### G4: 其他

- [x] 2026-08-14 重新以 live registered path、physical containment 與 inode alias 對帳：
      repo root 內 7 個 linked worktree basename 均已在 `.git/info/exclude`，本次 append 0 行；
      `<repo>.worktrees/` 的 external worktree 不適用 exclude。先前清除兩個已不存在殘留項目的
      結果仍保留；本次主工作樹 dirty 0。
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

#### G4 Phase 1 後續：registry 存取的長期解

短期已加入 `.github/workflows/deps-verify.yml`（手動 `workflow_dispatch` 與 `chore/deps-security`
push 觸發）作為繞道，讓驗證改在可連公開 npm 的 runner 上執行。**該 workflow 尚未取得任何執行結果**，
9 筆 alert identity 仍全數 `OPEN`。以下兩項為尚未著手的長期解：

- [ ] **B（長期）**：請 1ES feed 擁有者 ingest 缺少的版本。後端為
      `ms-feed-25.pkgs.visualstudio.com/1es-public/_packaging/npm-public/`，
      metadata 回 200 但特定版本 tarball 404，因為 packument 內根本沒有該版本
      （例：nanoid `3.3.16` present → 303；`3.3.17`、`3.3.18` absent → 404）。
      缺版含 `@types/node 26.2.0`，該版本已存在於 `origin/main` 現有 lockfile，
      因此連 main 都無法本機 clean install。
      **這是反覆性問題**：每次 Dependabot bump 都會再撞一次缺版，
      需要建立常態的 ingest 流程或自動補版機制，一次性補件無法收斂
- [ ] **C（長期）**：請裝置政策擁有者評估放行 `registry.npmjs.org`。
      攔截發生在 TLS 層而非設定層——DNS 正常、TCP 443 可連，
      但 Client Hello 之後連線即被切斷（`Recv failure: Socket is not connected`），
      裝置裝有 Microsoft Defender。因此**修改 npmrc 無效**，
      必須由裝置政策端處置

### G5: Worktree 註冊路徑與外部 sibling 治理

- [x] 保存 14 個 worktree 的完整 registered path、physical path 與 path class 證據
- [x] 證明 `Development`／`development` 解析為相同 inode，不是兩套實體 repo
- [ ] 另案決定是否將 publication-policy、v8 的 Git lexical registration 正規化為
      canonical `Development` 路徑
- [ ] 決定是否把 `<repo>.worktrees/<slug>` + `agents/<slug>` 正式納入命名規則；
      此慣例不污染主工作樹 untracked 清單，也不需要 exclude
- [ ] `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/agents-vscode-performance-issues`
      目錄存在且含 `.git`，但未註冊；其 gitdir 指標目前不可用。待判定是殘留、進行中或
      registration 已失效；未經批准不得 delete、prune 或 re-add

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
- [x] 未執行任何其他 worktree/branch/spec 變更或 production 寫入；本次只更新本治理 spec
