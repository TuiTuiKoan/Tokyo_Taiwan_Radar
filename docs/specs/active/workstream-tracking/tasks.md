# Tasks

本檔是工作線盤點的**權威持久位置**。所有數字都是快照，不是真值。

---

## Snapshot 基準

* 觀測日期：**2026-10-20**（對帳後同日退役 `ledger-topology-reconcile`，已反映）
* `origin/main`：`f1a519fe`（docs(agents): add iwafu-taiwan-relevance-gate campaign close-out record）
* 註冊拓撲：1 main + 17 linked（共 18；計數只描述本次快照）
* repo 實體根目錄已由 `/Users/flyingship/Development/Tokyo Taiwan Radar` 搬到
  `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar`（`pwd -P`）；舊路徑現為 symlink
* 下次更新時請一併更新本區塊，否則勾選狀態會腐化

---

## Phase 0: 重新查證（每次開始前必做）

- [x] 執行下方查證指令，回報與 snapshot 的差異
- [x] 就地更新本檔數字與 Snapshot 基準
- [x] Worktree 註冊路徑拓撲有重大差異，已同步更新 [proposal.md](./proposal.md)

```bash
cd '/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar' && git fetch origin main -q
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
`--porcelain` 的完整註冊字串；basename 只在其他摘要表中作顯示用途。2026-10-20 觀測。

| Path class | Registered path | Physical path (`pwd -P`) | Branch |
|---|---|---|---|
| canonical main | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar` | `main` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree` | `feat/ai-harness` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-iwafu-gate-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-iwafu-gate-worktree` | `fix/iwafu-taiwan-relevance-gate` |
| external（root 外） | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/vscode-session-recovery-guide` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/vscode-session-recovery-guide` | `agents/vscode-session-recovery-guide` |
| external（root 外） | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/web-based-financial-workshop-slides` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/web-based-financial-workshop-slides` | `agents/web-based-financial-workshop-slides` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `feat/admin-qa-cleanup` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-authoritative-venue-repair-worktree` | `feat/authoritative-venue-repair` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | `feat/evaluation-framework` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `feat/japan-scope-gate` |
| symlink-alias 註冊（root 內，小寫 `development`） | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `feat/publication-policy` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/agent-handoff-and-worktree-cleanup` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/agent-handoff-and-worktree-cleanup` | `agents/agent-handoff-and-worktree-cleanup` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/anomaly-detection-workflow-integration` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/anomaly-detection-workflow-integration` | `agents/anomaly-detection-workflow-integration` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/error-resolution-guide` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/error-resolution-guide` | `agents/error-resolution-guide` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/ledger-topology-reconciliation` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/ledger-topology-reconciliation` | `agents/ledger-topology-reconciliation` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/mobile-ssh-agent-remote-development` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/mobile-ssh-agent-remote-development` | `agents/mobile-ssh-agent-remote-development` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/publication-policy-workflow-rebuild` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/publication-policy-workflow-rebuild` | `agents/publication-policy-workflow-rebuild` |
| symlink-alias 註冊（root 外） | `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo` | `agents/tokyo-taiwan-radar-agents-repo` |

repo 根目錄已搬到 `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar`。
`/Users/flyingship/Development/Tokyo Taiwan Radar` 與
`/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees` 現為 symlink（2026-09-10 建立，
指向 `3-TTR/` 下的實體目錄）；小寫 `/Users/flyingship/development/...` 因 macOS 檔案系統不分大小寫，
解析到同一個 symlink（`Development`／`development` 兩條 symlink 皆為 device `16777231`、
inode `625519038`；實體目錄 inode `553836739`）。因此 14 個 linked worktree 的 Git 註冊字串仍是
搬移前的舊路徑，`pwd -P` 全部落在 `3-TTR/` 下；它們是**同一套實體 repo 的 lexical alias**，
不是第二套目錄。只有 `ttr-ai-harness-worktree`、`ttr-iwafu-gate-worktree` 與
`3-TTR/Tokyo Taiwan Radar.worktrees/` 下兩個 worktree 以新路徑註冊。

此狀態下 canonical classifier 以字串前綴判定，舊路徑註冊者會被列為 `external`；
上表依 `pwd -P` 的 containment 重新分類，並標明註冊字串是否為 alias。

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

### 2026-10 campaign worktree 退役

`ttr-v8-worktree`（`feat/event-intake-wizard`）、`ai-portability`、`closeout-audit-multirange`
等 campaign worktree 已於 2026-10-14 前後退役，且皆不在現行拓撲。各自的證據（退役 tip、
exclude 重建、殘留檢查）以 `docs/evaluation/campaigns/2026-10-14-*.md` 的 close-out record 為準，
本檔不複製。治理對帳用的 `agents/ledger-topology-reconcile`（tip `4e4d42cd`，已是 `origin/main` 祖先）
於 2026-10-20 push 並部署後以非強制 `git worktree remove` + `git branch -d` 退役，recovery capsule 在本機
`~/.ai-notes/ttr/`，無 close-out record（docs-only，無出貨行為）。`ai-portability` spec 已於 2026-10-20 歸檔為
`docs/specs/archive/2026-10-ai-portability/`。

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

需決定是否納入 A–E 或另立編號。2026-10-20 觀測；ahead/behind 為 `HEAD...origin/main`。

| Worktree | ahead/behind | dirty | 判讀 |
|---|---|---|---|
| `agent-handoff-and-worktree-cleanup` | 0/95 | 0 | external alias；待決定治理歸屬 |
| `anomaly-detection-workflow-integration` | 0/97 | 0 | external alias；待決定治理歸屬 |
| `error-resolution-guide` | 0/84 | 0 | external alias；新登記，待決定治理歸屬 |
| `ledger-topology-reconciliation` | 0/89 | 0 | external alias；待判定與本次治理線的關係 |
| `mobile-ssh-agent-remote-development` | 0/97 | 0 | external alias；待決定治理歸屬 |
| `publication-policy-workflow-rebuild` | 0/84 | 0 | external alias；新登記，名稱疑與 `publication-policy` 相關，待判定 |
| `tokyo-taiwan-radar-agents-repo` | 0/89 | 0 | external alias；待決定治理歸屬 |
| `vscode-session-recovery-guide` | 0/78 | 0 | external（3-TTR.worktrees）；新登記，待決定治理歸屬 |
| `web-based-financial-workshop-slides` | 0/61 | 0 | external（3-TTR.worktrees）；新登記，待決定治理歸屬 |
| `ttr-ai-harness-worktree` | 0/1 | 4 | 進行中（`feat/ai-harness`，dirty 為活躍編輯）；無 matching spec |
| `ttr-iwafu-gate-worktree` | 0/0 | 0 | `fix/iwafu-taiwan-relevance-gate`；close-out record 已在 `origin/main`，退役待 campaign-closer |
| `ttr-evaluation-framework-worktree` | 0/99 | 0 | 待同步 |
| `ttr-japan-scope-gate-worktree` | 11/158 | 16 | 活躍且 dirty，規模不小 |

---

## 三方對照：工作線 ↔ worktree ↔ spec

| 工作線 | Worktree | ahead/behind | dirty | Spec |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree` | 0/91 | 0 | `active/admin-qa-cleanup` |
| A（predecessor） | 已移除 | — | — | `admin-reports-204-cleanup`（保留 active） |
| B | `ttr-publication-policy-worktree`（alias 註冊） | 0/98 | 0 | `active/publication-policy` |
| C | **無** | — | — | **無** |
| D | publication worktree + 無歸屬 backlog | — | — | **無** |
| E（venue repair） | `ttr-authoritative-venue-repair-worktree` | 1/132 | 0 | `active/authoritative-venue-repair` |
| 未編號 | `ttr-evaluation-framework-worktree` | 0/99 | 0 | `active/evaluation-framework` |
| 未編號 | `ttr-japan-scope-gate-worktree` | 11/158 | 16 | 無 matching spec |
| 未編號 | `ttr-ai-harness-worktree` | 0/1 | 4 | 無 matching spec（計畫在本機 `~/.ai-notes/ttr/`） |
| 未編號 | `ttr-iwafu-gate-worktree` | 0/0 | 0 | 無 matching spec |
| 未編號 | 其餘 9 個 `agents/*` worktree（見上表） | 見上表 | 0 | 無 matching spec |
| —（主工作樹） | `Tokyo Taiwan Radar` | 2/1（本地領先未推送） | 0 | `active/workstream-tracking`（governance-only） |

### Spec 狀態 inventory（2026-10-20）

實際存在的狀態目錄為 `docs/specs/active/`（18 個 spec）、`docs/specs/archive/`
（2 個 spec 目錄：`2026-10-ai-portability`、`feedback-loop`，另有 8 個單檔 spec）與
`docs/specs/parked/`（1 個單檔：`ai-portability-followups.md`）。目錄位置與 frontmatter
`status` 不一致者如下：

| Spec 目錄 | Frontmatter `status` |
|---|---|
| `active/japan-open-data-integration` | `done` |
| `active/merger-multi-signal-pass4` | `parked` |
| `active/report-prototype-gap-fix` | `done` |
| `active/tier1-data-completion` | `done` |
| `active/works-entity-for-films-and-tours` | `done` |
| `archive/feedback-loop` | `active` |

其餘 active spec 與 `archive/2026-10-ai-portability`（`archived`）相符；archive／parked 單檔
spec 不帶 `proposal.md`，未逐一核對 frontmatter。這是雙向 inventory，不把 frontmatter
狀態硬編成不存在的第三個實體目錄。

---

## 治理缺口

### G1: prompt 版控

- [x] 三個 prompt 納入版控（`7598b411`）

### G2: Linked worktree 缺 matching spec 目錄

17 個 linked worktree 中，只有 `ttr-admin-qa-cleanup`、`ttr-authoritative-venue-repair`、
`ttr-evaluation-framework`、`ttr-publication-policy` 四個有同 slug 的 active spec；
`ledger-topology-reconcile`（原指定 `workstream-tracking`）已於 2026-10-20 退役，不再計入。其餘 13 個需依規則生效時間與
工作狀態分流（2026-10-20 觀測）：

- [ ] `ttr-japan-scope-gate-worktree` 補建 spec 或明確指定既有 spec
- [ ] `ttr-ai-harness-worktree`、`ttr-iwafu-gate-worktree` 確認 spec 或 grandfathered 身分
      （後者的 close-out record 已落地，應走退役而非補 spec）
- [ ] 9 個 `agents/*` worktree（`agent-handoff-and-worktree-cleanup`、
      `anomaly-detection-workflow-integration`、`error-resolution-guide`、
      `ledger-topology-reconciliation`、`mobile-ssh-agent-remote-development`、
      `publication-policy-workflow-rebuild`、`tokyo-taiwan-radar-agents-repo`、
      `vscode-session-recovery-guide`、`web-based-financial-workshop-slides`）分別確認 spec 或 grandfathered 身分

### G3: 停滯 worktree 去留

2026-08-14 的唯一停滯項 `ttr-v8-worktree`（`feat/event-intake-wizard`）已於 2026-10-14
退役，證據見 `docs/evaluation/campaigns/2026-10-14-event-intake-wizard.md`。目前無待決停滯項；
日後出現時，決定前必須查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

### G4: 其他

- [x] 2026-10-20 重新以 live registered path、physical containment 與 symlink alias 對帳：
      repo root 內 8 個 linked worktree basename 均已在 `.git/info/exclude`
      （`ttr-admin-qa-cleanup`、`ttr-ai-harness`、`ttr-authoritative-venue-repair`、
      `ttr-deps-security`、`ttr-evaluation-framework`、`ttr-iwafu-gate`、`ttr-japan-scope-gate`、
      `ttr-publication-policy`），本次 append 0 行；`<repo>.worktrees/` 的 external worktree 不適用
      exclude。主工作樹 dirty 0（但本地領先 `origin/main` 2 個未推送 commit）。
- [ ] Dependabot 8 個依賴漏洞中 6 筆已 `fixed`（PR #304，2026-10-20），剩 #87、#89 共 2 筆 `open`
      （均為刻意不處理，已於 2026-10-22 列為另案待辦，見「G4 另案待辦」）。**性質上不屬於工作線盤點**，僅暫置於此；建議另立資安維護歸屬

#### G4 依賴維護：固定驗收集合（2026-10-20 重查 8 筆；21:17 複查 6 筆 `fixed`、2 筆 `open`）

以 alert identity 作終局判定，不以 alert 總數代替。2026-08-10 的舊集合（#45–#63，9 筆：
`sharp`、`postcss`、`nanoid`、`brace-expansion`、`js-yaml`）現已全部 `fixed`，不再追蹤。

| Alert | package | severity | first patched | 來源鏈 | 處置 |
|---|---|---|---|---|---|
| #74 | `js-yaml` 4.x | high | 4.3.2 | eslint（dev） | **已 fixed**（PR #304）：override `js-yaml@4 ^4.3.2` |
| #75 | `js-yaml` 3.x | high | 3.15.2 | gray-matter（runtime） | **已 fixed**（PR #304）：override `js-yaml@3 ^3.15.2` |
| #86 | `source-map-js` | high | 1.2.2 | postcss | **已 fixed**（PR #304）：override `source-map-js ^1.2.2` |
| #83 | `brace-expansion` 1.x | medium | 1.1.21 | minimatch 3 ← eslint（dev） | **已 fixed**（PR #304）：override `brace-expansion@1 ^1.1.21` |
| #84 | `dompurify` | low | 3.4.16 | mermaid | **已 fixed**（PR #304）：override `dompurify ^3.4.16` |
| #88 | `dompurify` | low | 3.4.16 | mermaid | **已 fixed**（PR #304）：同 #84 |
| #87 | `katex` | low | 0.18.2 | mermaid（要求 `^0.16.47`） | **不處理**：修補版跨 mermaid 的相依範圍，PR #258（mermaid 12.1.0）仍要求 `^0.16.47`；等 mermaid 放寬再升 |
| #89 | `sprintf-js` | medium | **無** | gray-matter → js-yaml 3 → argparse 1.x | **不處理**：無修補版；僅建置期讀自家 markdown。可選解法是換掉 gray-matter |

全 8 筆 manifest 皆為 `web/pnpm-lock.yaml`。六筆 `fixed_at` 皆為 2026-10-20T11:31–11:34Z（PR #304 merge 後約 30 分鐘由 GitHub 重新掃描轉入）。

#### G4 進度（2026-10-20）

- [x] 分支 `chore/deps-security-2026-10`（自 `origin/main` 新建；舊 `chore/deps-security` 的 PR #216 已 merge，
      該分支落後 114 commit 不再使用）commit `7ac3831f` 調整 5 條 overrides，lockfile 僅 51 行變動
- [x] 本機 `registry.npmjs.org` 已可連（HTTP 200）；先前的 proxy 阻擋已解除。**注意**：lockfile 須帶
      `--registry https://registry.npmjs.org/` 重生，否則 `~/.npmrc` 的 Microsoft proxy 會把 232 筆
      resolution 改寫成 `ms-feed-25` tarball URL 與 sha1 integrity，這種 lockfile 不可 commit
- [x] 本機驗證：`pnpm install --frozen-lockfile` 通過；`pnpm audit` 剩 `braces`（#85，已 auto_dismissed，無修補版）、
      `sprintf-js`、`katex`；`pnpm lint` 改動前後同為 218 problems（164 errors），為既有問題；
      `prebuild`、compile、TypeScript 通過，`next build` 在靜態頁產生階段因本 worktree 缺 Supabase 環境變數失敗
      （環境因素，需由 CI／Vercel 確認）
- [x] 使用者 push 分支並開 PR #304；Vercel 與 gitleaks 通過，PR 於 2026-10-20 merge
- [x] merge 後以 `gh api repos/:owner/:repo/dependabot/alerts` 確認 #74、#75、#83、#84、#86、#88 皆為 `fixed`（2026-10-20 21:17 複查）
- [x] 2026-10-22 遠端 `chore/deps-security`、`chore/deps-security-2026-10` 已刪除；repo 已開啟
      `delete_branch_on_merge`（之後 merge 的 PR head 分支自動刪除）
- [x] #87、#89 決定**另案處理**（不 dismiss、不接受風險結案），見下方待辦

#### G4 另案待辦：#87 katex、#89 sprintf-js（2026-10-22 決定）

兩者皆為間接依賴，目前攻擊面小（Mermaid 圖來自自家 spec，不是使用者輸入；gray-matter 只在建置時讀自家檔案），
alert 維持 `open`，待下列條件成立時處理：

- [ ] **#87 katex（low）**：等 mermaid 新版把 katex 範圍放寬到 `>=0.18.2` 後升級 mermaid。
      觀察點：PR #258（mermaid 11.16.1 → 12.1.0）目前仍要求 `katex ^0.16.47`，merge 它並不會修掉 #87。
      不用 override 強制跨版本（mermaid 對 katex 0.18 的相容性未驗證）
- [ ] **#89 sprintf-js（medium，無修補版）**：把 `web/scripts/build-specs-snapshot.ts` 的 `gray-matter`
      換成不經 `js-yaml@3 → argparse@1 → sprintf-js` 的 frontmatter 解析（例如直接用 `yaml` 套件）。
      換掉後可一併移除 `overrides` 裡的 `js-yaml@3`。需先確認 snapshot 輸出逐位元組不變
- [ ] 任一項處理後，以 `gh api repos/:owner/:repo/dependabot/alerts` 確認對應 alert 轉 `fixed`

### G5: Worktree 註冊路徑與外部 sibling 治理

- [x] 保存 19 個 worktree（2026-10-20 對帳當時；其後 `ledger-topology-reconcile` 與 `ttr-deps-security-worktree` 相繼退役，現為 17 個；完整計數對帳另交 `ledger-topology-reconcile` skill） 的完整 registered path、physical path 與 path class 證據
- [x] 證明 `Development`／`development` 路徑解析到同一個 symlink／同一套實體 repo
- [ ] 另案決定是否把 14 個以搬移前舊路徑（含小寫 `development`）註冊的 linked worktree
      正規化為 `3-TTR/` 實體路徑（`git worktree repair` 屬變更操作，需批准）
- [ ] 決定是否把 `<repo>.worktrees/<slug>` + `agents/<slug>` 正式納入命名規則；
      此慣例不污染主工作樹 untracked 清單，也不需要 exclude。注意現有慣例文字寫死舊根路徑，
      搬移後需一併更新
- [ ] `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/agents-vscode-performance-issues`
      目錄存在且含 `.git`（內容停在 2026-06-11），但未註冊（`.git/worktrees/` 無對應項）；
      其 gitdir 指向 `/Users/flyingship/development/Tokyo Taiwan Radar/.git/worktrees/agents-vscode-performance-issues`，
      該目標不存在。待判定是殘留、進行中或 registration 已失效；未經批准不得 delete、prune 或 re-add

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
