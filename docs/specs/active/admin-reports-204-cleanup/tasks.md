---
title: Admin Reports Cleanup Tasks
description: Round 5 delivery checklist for Admin Reports cleanup
status: active
updated: 2026-07-29
---

完整設計見 [proposal.md](./proposal.md) 與權威計畫 `/memories/session/plan.md`；歷史 critique 見 [notes.md](./notes.md)。

歷史觀測值 204、237、251 僅供彙總比較，不是 apply gate。2026-07-29 09:04 JST 的 174-row 觀測是 $B_{2026-07-29}$，不是 $P_0$。未來 manifest 採動態 $P_0=A+S+M$，不保留 117、43、44 的固定執行數。

## 已交付的 audit history

* [x] Publication-policy 已交付：`feb530e`
* [x] H0 writer safety 已交付：`5457b5f2`
* [x] G1 Auto-QA predicate correctness 已交付：`a2ba5bbe`
* [x] G2 prefecture 與 pagination 已交付：`796aa7f8`，scheduled apply gate `56e677e2`
* [x] G3 merger pagination 已交付：`77741cd5`
* [x] G3 annotation-error settlement 已交付：`e8552682`
* [x] G4a migration、operator 與 application guard 已交付：`60978b5c` 至 `1295ca4d`
* [x] G4b status-last 已交付：`e6203c09`、`6b739a42`
* [x] G4b deterministic performer dispatch 已交付：`90e5e9fd`、`c7f42c4c`
* [x] Migration 094 與 inactive maintenance row 已上線，RPC 回傳 `false`
* [ ] 第一個 maintenance window 前 retrieve 或重新驗證四象限 auth evidence
* [ ] 第一個 maintenance window 前以足夠權限擷取 workflow 與 variable 狀態

## Round 5 spec sync

* [x] 指定 worktree 與 branch 驗證通過，且線性快轉至最新 `origin/main`
* [x] `proposal.md` 與 `tasks.md` 更新至 2026-07-29，spec 保持 active
* [x] H0 與 G1 至 G4b 由 active implementation 改列已交付 audit history
* [x] G-P 列為下一個 code delivery，與 T-P 和 production data work 分離
* [x] T-P 改為原 publication CLI 內延伸，不預抽 generic primitives
* [x] 補齊 logical 與 observed after-image、rollback horizon、Phase 4 prerequisite 與 service-role-safe window close order
* [x] 記錄 $B_{2026-07-29}$，保留 204、237、251 為歷史比較
* [x] `notes.md` 保持 bytes 不變

## Round G-P：publication annotation hotfix

* [x] 先加 truthy-organizer regression，證明 pre-fix 會洩漏 `_publisher_evidence`
* [x] 加 empty 或 missing organizer fallback regression，證明 evidence 會成為 organizer 且 internal key 被移除
* [x] 將 finalizer 改為先 `pop` evidence，再套用 event organizer precedence
* [x] 保留 pure publication null policy、registry lookup、organizer URL 與所有 public payload semantics
* [x] Focused publication tests、完整 scraper tests、compileall 與文件檢查通過
* [x] 獨立 Tester 回 PASS
* [ ] 取得 G-P push、merge、deploy 與 scheduled annotation effects 核准
* [ ] 部署 exact G-P SHA，觀察完整授權週期，確認沒有新 publication `PGRST204` 或 internal-key leak
* [x] 不執行 reset、re-annotation batch、report settlement、manifest apply 或 DB write

## Round T-P：現有 publication CLI 的 reset 與 rollback

* [ ] 在 `scraper/_oneoff_backfill_publication_metadata.py` 內延伸 exact error reset
* [ ] Manifest 僅批准 logical expected after-image，apply read-back 記錄 observed physical after-image 與 trigger-generated `updated_at`
* [ ] Rollback eligibility 比對 observed physical after-image
* [ ] 實作 rollback preview、rollback apply 與 bounded rollback horizon
* [ ] 加 failure-injection 與 rollback rehearsal tests
* [ ] 不預抽 `cleanup_manifest.py` 或 generic primitives
* [ ] Tester PASS 並取得 tools-only 核准，不授權 DB write

## Round T-A：Admin cleanup CLI

* [ ] T-P 與五條 G lane 都已部署後才開始
* [ ] Admin CLI 成為第二 consumer 時才抽 shared policy-neutral helpers
* [ ] 實作 discover、classify、freeze、apply、rollback、export-review
* [ ] 全部 action 使用 full report UUID、完整 before-image 與 journaled per-field write
* [ ] 加 failure-injection 與 rollback rehearsal tests
* [ ] Tester PASS 並取得 tools-only 核准，不授權 DB write

## Phase 4：publication manifest 與 live repair

* [ ] 驗證 exact deployed H0 `5457b5f2`、G1 `a2ba5bbe`、G4a `60978b5c` 至 `1295ca4d`、G3 settlement `e8552682`
* [ ] 驗證 exact G-P SHA、clean authorized cycle 與 exact T-P SHA
* [ ] 驗證 maintenance inactive row、false RPC 與四象限 auth evidence
* [ ] 以 full UUID 產生 immutable publication manifest，明確排除 `cfb4050b-bcec-4478-a120-5cc9d1a3198a`
* [ ] Reset 僅允許 `error -> pending`、retry count 歸零與其他欄位不變
* [ ] Apply journal 記錄 observed physical after-image，不預猜 `updated_at`
* [ ] Writers disabled 時完成 verify 與 rollback preview
* [ ] 先 release lock 並確認 inactive，再 restore workflow 與 variable
* [ ] 第一個 scheduled 或 GPT write 後關閉 rollback horizon，後續只 fix-forward
* [ ] 正常 annotation 成功後，僅由下一次 `error_recovery.py` 執行 settlement
* [ ] 每個 manifest、window、apply 與 rollback 都取得各自 digest-bound 核准

## 後續 Admin cleanup 與資料工作

* [ ] 部署 T-A 後凍結 fresh $P_0$ ledger，兩次完整掃描 byte-identical
* [ ] 驗證 $P_0=A+S+M$，每個 full report ID 只有一個 current class
* [ ] Automatic batch 不含 compound、human、mixed、unknown、empty 或 payload token
* [ ] Digest-bound automatic manifest apply 與 rollback preview
* [ ] Evidence-qualified Round S source release、manifest 與 apply
* [ ] Manual reports 產出 digest-bound review export
* [ ] Final reconcile 與完整 scheduled observation 不重建已修復 defect

## Approval gates

* [x] 本次核准僅涵蓋 spec sync 與 G-P implementation、validation
* [ ] G-P push、merge、deploy 與 scheduled effects 另行核准
* [ ] T-P 與 T-A 各自 tools-only 核准
* [ ] Maintenance window 的 lock 與 writer state 操作另行核准
* [ ] 每個 production manifest apply 以既存 SHA-256 與 literal command 另行核准
* [ ] 最終 docs-only archive 另行核准

## 本次驗證

* [x] Pre-fix focused test 以預期 assertion failure 證明 regression 有效
* [x] `scraper/tests/test_annotator_publication.py` 通過
* [x] 完整 `scraper/tests` 通過
* [x] `python -m compileall -q scraper` 通過
* [x] Frontmatter、Markdown、stale topology 與 `git diff --check` 通過
* [x] 僅四個核准檔案 modified，`notes.md` SHA-256 未變
* [x] 無 `web/messages` diff，無 production DB write

## Done：歸檔條件

* [ ] G-P、T-P、T-A 與需要時的 Round S 均獨立測試、部署並完成觀察
* [ ] Phase 4 與後續 data apply 全部使用核准的 immutable manifest
* [ ] Fresh $P_0=A+S+M$ 驗證完成，manual rows 有 digest-bound export
* [ ] 每個 window 都先驗證 lock inactive，才 restore service-role writers
* [ ] Final exact scan 與完整 scheduled cycle 不重建已修復 defect
* [ ] 將 spec directory 移至 `docs/specs/archive/<YYYY-MM>-admin-reports-204-cleanup/`，並保留 `notes.md`
