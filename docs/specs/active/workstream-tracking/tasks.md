# Tasks

本檔是工作線盤點的**權威持久位置**。所有數字都是快照，不是真值。

---

## Snapshot 基準

* 觀測日期：**2026-10-25**（含本次對帳用的 `agents/ledger-topology-reconcile`）
* `origin/main`：`fc3416d6`（docs(specs): record the event detail 404 fix in japan-scope-gate）；對帳途中前進到
  `e6c65f91`（docs(evaluation): close out the scraper-zero-output campaign），期間新建的
  `ttr-tiff-venue-inserts-worktree` 已補入
* 註冊拓撲：1 main + 15 linked（共 16；計數只描述本次快照）
* 進度入口已改為 GitHub Project **TTR Roadmap** 看板（`AGENTS.md`「進度追蹤」，2026-10-22 起）；本檔只記
  worktree 與 spec 的拓撲、退役證據與治理缺口，各工作線的細項以看板 issue 為準
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
`--porcelain` 的完整註冊字串；basename 只在其他摘要表中作顯示用途。2026-10-25 觀測。

| Path class | Registered path | Physical path (`pwd -P`) | Branch |
|---|---|---|---|
| canonical main | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar` | 同左 | `main` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree` | 同左 | `feat/ai-harness` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-closer-auto-retire-worktree` | 同左 | `feat/closer-auto-retire` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-evaluation-framework-worktree` | 同左 | `fix/eval-annotator-validated` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-event-detail-404-worktree` | 同左 | `fix/event-detail-404` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-guard-detections-worktree` | 同左 | `feat/guard-detections` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ndl-relevance-publication-worktree` | 同左 | `feat/ndl-relevance-publication` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-people-ground-truth-worktree` | 同左 | `feat/people-ground-truth` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree` | 同左 | `feat/pr-flow-tiering` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-scraper-zero-output-worktree` | 同左 | `fix/scraper-zero-output` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-tiff-venue-inserts-worktree` | 同左 | `feat/tiff-venue-inserts` |
| canonical child | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-venue-data-cleanup-worktree` | 同左 | `feat/venue-data-cleanup` |
| external（root 外） | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile` | 同左 | `agents/ledger-topology-reconcile` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-admin-qa-cleanup-worktree` | `feat/admin-qa-cleanup` |
| symlink-alias 註冊（root 內） | `/Users/flyingship/Development/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-japan-scope-gate-worktree` | `docs/scope-gate-404-acceptance` |
| symlink-alias 註冊（root 內，小寫 `development`） | `/Users/flyingship/development/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-publication-policy-worktree` | `feat/publication-policy` |

「同左」表示 registered path 與 `pwd -P` 逐字相同。`ttr-evaluation-framework-worktree` 與 `ttr-japan-scope-gate-worktree`
的目錄名沿用舊工作線，branch 已換成其他 session 的新工作（分別是 `fix/eval-annotator-validated`、
`docs/scope-gate-404-acceptance`）；目錄名不能拿來推斷 branch 或 spec。

`agents/ledger-topology-reconcile` 是本次對帳的專屬 worktree，自 `origin/main` `fc3416d6` 建立，
以實體路徑註冊；本對帳 push 後依例退役。`3-TTR/Tokyo Taiwan Radar.worktrees/` 在本次建立前已不存在
（見 G5），由本次 `git worktree add` 重新建立。

repo 根目錄已搬到 `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar`。
`/Users/flyingship/Development/Tokyo Taiwan Radar` 與
`/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees` 現為 symlink（2026-09-10 建立，
指向 `3-TTR/` 下的實體目錄）；小寫 `/Users/flyingship/development/...` 因 macOS 檔案系統不分大小寫，
解析到同一個 symlink（`Development`／`development` 兩條 symlink 皆為 device `16777231`、
inode `625519038`；實體目錄 inode `553836739`）。2026-10-25 仍以搬移前舊路徑註冊的 linked worktree
剩 3 個（上表 `symlink-alias` 列，全部在 root 內），`pwd -P` 全部落在 `3-TTR/` 下；它們是
**同一套實體 repo 的 lexical alias**，不是第二套目錄。其餘 12 個 linked worktree 以新路徑註冊。
2026-10-22 表列的 5 個舊路徑註冊中，`ttr-authoritative-venue-repair-worktree` 已退役，
`ttr-evaluation-framework-worktree` 現改以實體路徑註冊（由其他 session 重新建立或 repair，經過未查證；
`feat/evaluation-framework` 本機 branch 已不存在）。

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

`ttr-iwafu-gate-worktree`（`fix/iwafu-taiwan-relevance-gate`）已於 2026-10-20 退役，證據見
`docs/evaluation/campaigns/2026-10-20-iwafu-taiwan-relevance-gate.md` 與 `443619aa`
（docs(agents): record iwafu-taiwan-relevance-gate worktree retirement）。`ttr-deps-security-worktree`
同日退役（`3c04a4ba`）。`ttr-audit-archive-resolve-worktree`（`fix/audit-archive-resolve`）於 2026-10-22
由其他 session 建立並退役，整個生命週期落在兩次 ledger 快照之間，從未進過 ledger；屬正常結案，
本檔不補記證據。

`ttr-authoritative-venue-repair-worktree`（`feat/authoritative-venue-repair`）於 2026-10-22 退役：`3f7c00f6`
rebase 為 `10770777` 經 Gate 1 推上 main，production 階段暫停，以非強制 `git worktree remove` + `git branch -d`
移除。證據見 `docs/evaluation/campaigns/2026-10-22-authoritative-venue-repair.md`；spec 歸檔為
`docs/specs/archive/2026-10-authoritative-venue-repair/`。

### 2026-10-22～25 退役與消失的 worktree

| Worktree | Branch | 結果 | 證據 |
|---|---|---|---|
| `ttr-ci-runner-pin-worktree` | `fix/ci-runner-pin` | 其他 session 退役；branch 已不存在 | 交付 `488fd7b5`（fix(ci): pin Playwright workflows to ubuntu-24.04），之後由 `864b10cd` 解除固定 |
| `ttr-pause-enrich-poster-worktree` | `fix/pause-enrich-poster` | 其他 session 退役；branch 已不存在 | 交付 `c67c1a2b`（fix(ci): pause the daily Vision OCR poster enrichment） |
| `ttr-unpin-ubuntu-runner-worktree` | `feat/unpin-ubuntu-runner` | 2026-10-25 本 session 非強制移除＋`git branch -d`（tip `cdeaca98`，`origin/main` 祖先） | 交付 `864b10cd`（fix(ci): unpin Playwright workflows from ubuntu-24.04 and bump scraper playwright） |
| `ttr-tracking-cleanup-worktree` | `feat/remove-specs-kanban` | 2026-10-25 本 session 非強制移除；`branch -d` 因非祖先被拒，經 patch-id 確認與 `c34b0f9f` 相同後由使用者 `git branch -D` | `c34b0f9f`（feat(web): remove the admin spec kanban and keep the architecture map） |
| `ttr-llm-cost-reset-worktree` | detached | 其他 session 於 2026-10-25 退役 | 本機仍留 `feat/llm-cost-reset`（tip `dd0f6866`，非 `origin/main` 祖先，`git cherry` 有 `+`；可能經 PR #391／#430 squash 合併，**未查證**）；spec 仍在 `active/llm-cost-reset` |
| person-name-eval campaign worktree | — | 2026-10-23 退役 | `docs/evaluation/campaigns/2026-10-23-person-name-eval.md` |
| `Tokyo Taiwan Radar.worktrees/agents-vscode-performance-issues`（未註冊） | — | 目錄已不存在，刪除者不明 | #352（2026-10-25 以觀測結果關閉），見 G5 |

本 session 另有 4 個在 scratchpad 的 detached 臨時 worktree（D5 回填、tester／closer 教訓、eval 拆分），
用完即以非強制 `git worktree remove` 移除，不在 repo root 內，未進過本表。
2026-10-25 對帳 `.git/info/exclude`：移除 `ttr-llm-cost-reset-worktree/`、`ttr-tracking-cleanup-worktree/`、
`ttr-unpin-ubuntu-runner-worktree/` 三行過期條目，其餘 13 行對應 13 個 live 巢狀 worktree，`comm` 雙向皆空。

### 2026-10-22 `agents/*` external worktree 合併結案紀錄

9 個 `<repo>.worktrees/<slug>` + `agents/<slug>` worktree 於 2026-10-22 由使用者要求清理。移除前逐一重驗：
HEAD 等於 branch tip、tip 是 `origin/main` 祖先、`git status --porcelain` 為空、無 rebase／merge／
cherry-pick／bisect 進行中、無 `locked`、無 stash 引用、`lsof +D` 無占用。ignored 產物只有
`__pycache__`、`.pytest_cache`、`web/node_modules`、`web/.next`、`web/next-env.d.ts`、
`web/tsconfig.tsbuildinfo`、`web/lib/specs/*.json`（皆可重建，無 `.env`）。全部以非強制
`git worktree remove` + `git branch -d` 退役（exit 0），無 remote branch；位於 repo root 外，無 exclude 行。
沒有對應 spec，也沒有出貨行為可記錄，因此不寫 close-out record。移除後 `git worktree prune --dry-run`
無輸出。

| 已退役 worktree | Branch | 退役時 tip | 註冊形態 |
|---|---|---|---|
| `agent-handoff-and-worktree-cleanup` | `agents/agent-handoff-and-worktree-cleanup` | `f2de51f6`（2026-08-12 fix(scraper): repair feedback-loop A2 zero denominator） | 舊路徑 alias |
| `anomaly-detection-workflow-integration` | `agents/anomaly-detection-workflow-integration` | `751c6b61`（2026-08-12 fix(scraper): harden publication date parsing for hanmoto and ndl） | 舊路徑 alias |
| `mobile-ssh-agent-remote-development` | `agents/mobile-ssh-agent-remote-development` | `751c6b61`（同上） | 舊路徑 alias |
| `ledger-topology-reconciliation` | `agents/ledger-topology-reconciliation` | `3b04a6d3`（2026-08-14 docs(git): reconcile exclude block instead of deleting a line） | 舊路徑 alias |
| `tokyo-taiwan-radar-agents-repo` | `agents/tokyo-taiwan-radar-agents-repo` | `3b04a6d3`（同上） | 舊路徑 alias |
| `error-resolution-guide` | `agents/error-resolution-guide` | `04fd6897`（2026-08-17 fix(web): let cancel always leave the intake wizard） | 舊路徑 alias |
| `publication-policy-workflow-rebuild` | `agents/publication-policy-workflow-rebuild` | `04fd6897`（同上） | 舊路徑 alias |
| `vscode-session-recovery-guide` | `agents/vscode-session-recovery-guide` | `30391675`（2026-09-06 docs(weekly_review): 2026-09-06 weekly review） | 新路徑 |
| `web-based-financial-workshop-slides` | `agents/web-based-financial-workshop-slides` | `1b22c7b8`（2026-09-22 perf(slides): drop the unused mermaid bundle from the workshop deck） | 新路徑 |

未註冊的同層目錄 `agents-vscode-performance-issues` 不在當時範圍；2026-10-25 已確認消失（#352，見 G5）。

---

## 工作線 A：Admin Reports Cleanup

原 bounded campaign 已結案（Phase 0–4、Lane R、Lane A、Lane O，14 筆報告由
`error_recovery` 結案）。剩餘工作改以 successor 模式進行。

- [x] 確認舊 worktree/branch 移除**非工作遺失**：`65253c74` 是 `origin/main` 祖先；
      孤兒 `df0a2bd6`／`22324418` 僅為 amend 殘留，唯一差異 2 行措辭
- [x] Successor worktree `ttr-admin-qa-cleanup-worktree` 已建立
- [x] Successor spec `docs/specs/active/admin-qa-cleanup/` 已建立
- [ ] Successor worktree 退役：2026-10-22 Close Campaign & Retire Worktree Phase A 判定
      **`HOLD:unhandled_work`**（branch tip `4de6d08c` 已是 `origin/main` 祖先，ahead 0、dirty 0，A3 `SOLE_OWNER`）。
      阻擋是 spec `tasks.md` 52 項未勾選：2026-08 只出貨 T-A0 唯讀工具（`4de6d08c`），P0／T-A1／Phase D／Phase S
      未開始。解除條件：決定 A 線續做（保留 worktree）或停做（回填已完成項、其餘移 Deferred、spec 改
      `parked`／`archive`，再重跑 Phase A）。**2026-10-22 使用者決定續做**，worktree 保留，代表卡 #349
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

`ttr-publication-policy-worktree` 2026-10-22 Close Campaign & Retire Worktree Phase A 判定 **`HOLD:unhandled_work`**
（tip `a09208d8` 已是 `origin/main` 祖先，ahead 0、dirty 0，A3 `SOLE_OWNER`）：spec `tasks.md` 10 項＋
`changes-log.md` Deferred 14 筆，與上列 B 線待辦是同一批。退役前須先決定 B 線剩餘項與 D 線 4 項無歸屬 backlog
的 owner。**移除前另需處理**：該 worktree 的 ignored `tmp/publication-policy/`（225M、53 檔）含 eslite identity
與 hybrid `70cf7002` 的 rollback 快照、phase0 baseline、PN-3a／wave1 manifest 與 b1 journal，在 `3-TTR/` 與
`~/.ai-notes` 下找不到副本，視為全機唯一副本，必須先匯出到 worktree 外；另有 ignored `scraper/.env`，需使用者
確認是否為主工作樹副本。

**2026-10-22 使用者決定 B 線續做**，worktree 保留，代表卡 #350。2026-10-25 已把 `tmp/publication-policy/`
備份到本機 `~/ttr-wip-archive/20261025-publication-policy-tmp/`（52 個檔案，實際沒有子目錄；先前寫 53 有誤），
逐檔 SHA-256 與來源一致，清單另存 `~/ttr-wip-archive/20261025-publication-policy-tmp.sha256`。`scraper/.env`
仍待使用者確認。

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
4 項無歸屬小項於 2026-10-22 開成 #351（不貼 spec label），進度以該 issue 為準。

---

## 工作線 E：ABCD 以外

- [x] Eslite identity migration
- [x] Hybrid `70cf7002` 場地／報名 URL 分離
- [x] F-1 詳情頁隱藏會場列（`831871e0`）
- [x] Authoritative venue repair 程式修正（2026-10-22：`3f7c00f6` rebase 為 `10770777` 經 Gate 1 推上 main；
      worktree 退役、spec 歸檔，結案紀錄 `docs/evaluation/campaigns/2026-10-22-authoritative-venue-repair.md`）
- [ ] Authoritative venue repair production 階段（暫停）：runbook 在 `docs/specs/parked/authoritative-venue-repair-followups.md`
      （看板 #339）；TIFF 2026 的 4 筆場館新增由 #341 另案先行
- [ ] F-2 `container_title` 專屬欄位（需 migration）
- [x] 決策閘門規則寫入 `SKILL.md`（`335e462a`）
- [x] Worktree 確認閘門已進入 `origin/main`（`5d6e4a43`）

---

## 未納入編號的工作線

2026-10-22 起新工作線一律以 spec＋看板 issue 追蹤，不再擴充 A–E 編號；下表只記 worktree 與其對應。
2026-10-25 觀測；ahead/behind 為 `HEAD...origin/main`，「獨有」為 `git cherry origin/main <branch>` 的 `+` 數
（`-` 表示內容已在上游，只是不是祖先）。所有 worktree dirty 皆為 0。

| Worktree | Branch | ahead/behind | 獨有 | 對應 spec／issue | 判讀 |
|---|---|---|---|---|---|
| `ttr-ai-harness-worktree` | `feat/ai-harness` | 20/16 | 20 | `active/ai-harness`（#426 等） | 活躍；spec 已進 `origin/main` |
| `ttr-closer-auto-retire-worktree` | `feat/closer-auto-retire` | 0/110 | 0 | `active/closer-auto-retire`（#345 暫停中） | 退役候選；有 spec，走 closer，預期因 #345 判 HOLD |
| `ttr-evaluation-framework-worktree` | `fix/eval-annotator-validated` | 2/16 | 0（2 個 `-`） | `active/evaluation-framework`（#383） | 退役候選；內容已在 main |
| `ttr-event-detail-404-worktree` | `fix/event-detail-404` | 1/16 | 1 | `active/japan-scope-gate` | 有 1 個未進 main 的 commit；main 已有 `a05c8168`（answer 404 and 308 for event detail from proxy.ts），是否取代待擁有者確認 |
| `ttr-guard-detections-worktree` | `feat/guard-detections` | 1/3 | 1 | `active/evaluation-framework`（#386） | 活躍（2026-10-25 建立） |
| `ttr-ndl-relevance-publication-worktree` | `feat/ndl-relevance-publication` | 2/16 | 2 | `active/ndl-relevance-publication` | 活躍 |
| `ttr-people-ground-truth-worktree` | `feat/people-ground-truth` | 1/62 | 1 | `active/people-ground-truth`（#392） | 有 1 個未進 main 的 commit |
| `ttr-pr-flow-tiering-worktree` | `feat/pr-flow-tiering` | 0/144 | 0 | `active/pr-flow-tiering`（#316 試行中） | 退役候選；有 spec，預期因 #316 判 HOLD |
| `ttr-scraper-zero-output-worktree` | `fix/scraper-zero-output` | 0/0 | 0 | `archive/2026-10-scraper-zero-output` | 退役候選；spec 已於 `18cbb644` 歸檔 |
| `ttr-tiff-venue-inserts-worktree` | `feat/tiff-venue-inserts` | 0/0 | 0 | `archive/2026-10-authoritative-venue-repair` 的延續（#341） | 2026-10-25 15:05 由新 session 建立，開工中 |
| `ttr-venue-data-cleanup-worktree` | `feat/venue-data-cleanup` | 1/16 | 1 | 無 spec（#371） | 有 1 個未進 main 的 commit |
| `ttr-japan-scope-gate-worktree` | `docs/scope-gate-404-acceptance` | 1/3 | 0（1 個 `-`） | `active/japan-scope-gate`（#348 已關） | 內容已在 main |
| `agents/ledger-topology-reconcile`（external） | 同左 | 0/0 | 0 | 指定 `active/workstream-tracking` | 本次對帳專屬；push 後退役 |

退役候選都屬於其他 session；退役前要重新觀測，並取得使用者決定（2026-10-25 使用者只批准 unpin-ubuntu-runner、
llm-cost-reset、tracking-cleanup 三個，其餘保留）。

---

## 三方對照：工作線 ↔ worktree ↔ spec

| 工作線 | Worktree | ahead/behind | Spec | 看板 |
|---|---|---|---|---|
| A（successor） | `ttr-admin-qa-cleanup-worktree`（alias 註冊） | 0/280 | `active/admin-qa-cleanup` | #349（續做） |
| A（predecessor） | 已移除 | — | `active/admin-reports-204-cleanup`（保留） | — |
| B | `ttr-publication-policy-worktree`（alias 註冊，小寫） | 0/287 | `active/publication-policy` | #350（續做；tmp 快照已備份） |
| C | **無** | — | **無** | — |
| D | 無（4 項無歸屬） | — | **無** | #351 |
| E（venue repair） | 已退役（2026-10-22） | — | `archive/2026-10-authoritative-venue-repair`；runbook `parked/authoritative-venue-repair-followups.md` | #339（暫停）、#341（TIFF 4 筆場館，2026-10-25 在 `ttr-tiff-venue-inserts-worktree` 開工） |
| 其他 | 見上表 | — | 見上表 | 見上表 |
| —（主工作樹） | `Tokyo Taiwan Radar` | 0/0 | `active/workstream-tracking`（governance-only） | — |

### Spec 狀態 inventory（2026-10-25）

實際存在的狀態目錄為 `docs/specs/active/`（20 個 spec）、`docs/specs/archive/`（6 個目錄：`2026-05-tier1-data-completion`、
`2026-05-works-entity-for-films-and-tours`、`2026-10-ai-portability`、`2026-10-authoritative-venue-repair`、
`2026-10-scraper-zero-output`、`feedback-loop`，另有 10 個單檔 spec）與 `docs/specs/parked/`（2 個單檔：
`ai-portability-followups.md`、`authoritative-venue-repair-followups.md`）。

相對 2026-10-22：active 新增 `ai-harness`、`closer-auto-retire`、`japan-scope-gate`、`llm-cost-reset`、
`ndl-relevance-publication`、`people-ground-truth`；`authoritative-venue-repair`、`scraper-zero-output` 與 `02ab2027`
的四個 done spec（`japan-open-data-integration`、`report-prototype-gap-fix`、`tier1-data-completion`、
`works-entity-for-films-and-tours`）移到 archive。目錄位置與 frontmatter `status` 不一致者：

| Spec 目錄 | Frontmatter `status` |
|---|---|
| `active/merger-multi-signal-pass4` | `parked` |
| `archive/feedback-loop` | `active` |

另：`active/llm-cost-reset` 的 frontmatter 是 `active`，但它的 worktree 已退役、`feat/llm-cost-reset` 只剩本機 branch，
是否歸檔由擁有者決定。其餘 active spec 與 archive 目錄的 `archived` 相符；archive／parked 單檔 spec 未逐一核對。

---

## 治理缺口

### G1: prompt 版控

- [x] 三個 prompt 納入版控（`7598b411`）

### G2: Linked worktree 缺 matching spec 目錄

2026-10-25 觀測：15 個 linked worktree 中，除 `ttr-venue-data-cleanup-worktree`（只有 #371，無 spec）外，
都對應到一個 active spec 或已歸檔的 spec（見「未納入編號的工作線」表）；目錄名與 spec slug 不一定相同
（例：`ttr-guard-detections-worktree` → `evaluation-framework`、`ttr-event-detail-404-worktree` → `japan-scope-gate`）。

- [ ] `ttr-venue-data-cleanup-worktree`：#371 是否需要 spec，或維持 issue-only（依 `AGENTS.md`，小改動可不建 spec）
- [x] `ttr-japan-scope-gate-worktree` 的 spec：`active/japan-scope-gate` 已進 `origin/main`（#348 已關）
- [x] `ttr-ai-harness-worktree` 的 spec：`active/ai-harness` 已進 `origin/main`
- [x] `ttr-closer-auto-retire-worktree` 的 spec：`active/closer-auto-retire` 已進 `origin/main`
- [x] `ttr-ci-runner-pin-worktree`、`ttr-pause-enrich-poster-worktree`：已退役，不再待決

2026-10-20 列出的 9 個 `agents/*` worktree 已於 2026-10-22 退役，`ttr-iwafu-gate-worktree` 已於 2026-10-20 退役，
兩項不再待決。

### G3: 停滯 worktree 去留

2026-08-14 的唯一停滯項 `ttr-v8-worktree`（`feat/event-intake-wizard`）已於 2026-10-14
退役，證據見 `docs/evaluation/campaigns/2026-10-14-event-intake-wizard.md`。

2026-10-22 待決停滯項（決定前必須取得使用者裁決，不得自行刪除或強制移除）：

- [x] `ttr-japan-scope-gate-worktree`（`feat/japan-scope-gate`，最後 commit 2026-08-06）：11 個 commit
      未進 `origin/main`、16 個檔案未提交、本地與遠端分岔。2026-10-22 由其他 session 續做（#348，已關）：
      rebase 後經 PR #359 合併（`b19a08e9`，migration 097 撞號改為 098 並已套用），後續 Phase 6b／6c 移到 #385，
      舊遠端 branch 與 worktree 清理在 #358；遠端 `feat/japan-scope-gate` 已刪除，該目錄現改用
      `docs/scope-gate-404-acceptance`。殘留：#358 已關，但 2026-10-25 本機 `feat/japan-scope-gate` branch 仍在，
是否刪除由擁有者決定
- [x] `ttr-authoritative-venue-repair-worktree`（`feat/authoritative-venue-repair`）：2026-10-22 使用者選擇合併；
      `10770777` 推上 main 後 worktree 退役（見上方「2026-10 campaign worktree 退役」）

查證各分支是否有未推送且未合併的 commit：

```bash
git -C <worktree> log origin/main..HEAD --oneline
git --no-pager cherry origin/main <branch>   # '-' 前綴 = 內容已在上游
```

### G4: 其他

- [x] 2026-10-25 重新以 live registered path、physical containment 與 symlink alias 對帳：
      repo root 內 14 個 linked worktree basename 均在 `.git/info/exclude`，exclude 的 ttr 區塊恰為這 14 行
      （當日先以整塊對帳移除 3 行過期條目，剩 13 行；之後新 session 建立 `ttr-tiff-venue-inserts-worktree` 時
      自行 append 1 行，見「2026-10-22～25 退役與消失的 worktree」）；`<repo>.worktrees/`
      的 external worktree 不適用 exclude。主工作樹 dirty 0，與 `origin/main` 為 0/0。
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

- [x] 保存 16 個註冊 worktree（2026-10-25 對帳當時，含 main 與本次對帳專屬 worktree）的完整
      registered path、physical path 與 path class 證據
- [x] 證明 `Development`／`development` 路徑解析到同一個 symlink／同一套實體 repo
- [ ] 另案決定是否把 3 個以搬移前舊路徑（含小寫 `development`）註冊的 linked worktree
      （admin-qa-cleanup、japan-scope-gate 目錄、publication-policy）正規化為 `3-TTR/` 實體路徑
      （`git worktree repair` 屬變更操作，需批准）。它們依序退役或重建時此項會自然消失；worktree 集中與路徑
      規則另見 #328
- [ ] 決定是否把 `<repo>.worktrees/<slug>` + `agents/<slug>` 正式納入命名規則；
      此慣例不污染主工作樹 untracked 清單，也不需要 exclude。2026-10-22 該慣例下的 9 個舊 worktree
      已全數退役，2026-10-25 現存只有本次對帳專屬的 `agents/ledger-topology-reconcile`；
      ledger-topology-reconcile prompt 寫死的舊根路徑（`/Users/flyingship/Development/Tokyo Taiwan Radar…`）
      仍經 symlink 可用，正式納入時需一併改成實體路徑。可與 #328 的集中方案一起決定
- [x] `agents-vscode-performance-issues`（未註冊、gitdir 失效的同層目錄）：2026-10-25 確認目錄已不存在，
      連上層 `3-TTR/Tokyo Taiwan Radar.worktrees/` 也一度消失（本次對帳重新建立）；`.git/worktrees/`、branch、
      `~/.Trash` 都沒有殘留，刪除者不明，刪除前是否匯出無法驗證（#352 已以觀測結果關閉）。殘留：舊路徑 symlink
      `/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees` 在上層目錄不存在時會指向空處，無害

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
