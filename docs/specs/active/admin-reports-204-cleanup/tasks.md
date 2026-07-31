---
title: Admin Reports Cleanup Tasks
description: Round 5 delivery checklist for Admin Reports cleanup
status: active
updated: 2026-07-31
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
* [x] G-P 與 Round 5 spec sync 已以 exact SHA `7c98491b8f7efd60d03c2b6d21112aca5a20389f` 發布
* [x] G-P.1 observability 已以 exact SHA `085d4441edf9a12eeb4ec774b84f900649f08302` 發布
* [ ] Lane O 等待 exact G-P.1 SHA 的自然 scheduled run；不得手動 dispatch workflow
* [x] 不執行 reset、re-annotation batch、report settlement、manifest apply 或 DB write

## Retired T-P：durable journal design

* [x] 已依新版權威計畫退休，不再執行第四輪 Tester、commit、push、release 或 production apply
* [x] Phase 0 盤點確認 worktree 在 `feat/admin-reports-204-cleanup`，HEAD 與 `origin/main` 同為 `085d4441edf9a12eeb4ec774b84f900649f08302`，ahead/behind 為 `0/0`
* [x] Phase 0 盤點確認 dirty path 僅三檔：publication metadata tool、manifest test 與本 tasks ledger
* [x] 退休 T-P diff 已備份到 `/tmp/ttr-admin-reports-retired-tp-20260731.patch`，SHA-256 為 `1a4b2630949a6639158f16258c5bb9b42d865f7b6548fa37e8f8d5216d1859cc`，讀回 4,972 行
* [x] 已只 restore `scraper/_oneoff_backfill_publication_metadata.py` 與 `scraper/tests/test_publication_manifest.py`
* [x] 本 tasks ledger 保留 G-P/G-P.1 history，改寫為新版 Lane R 狀態，不回復舊 T-P 設計

## Lane R：lightweight publication reset

* [x] `git fetch origin main` 後確認 G-P exact SHA `7c98491b8f7efd60d03c2b6d21112aca5a20389f` 與 G-P.1 exact SHA `085d4441edf9a12eeb4ec774b84f900649f08302` 均為 HEAD ancestor
* [x] Live read-only count 顯示 active `annotation_status=error` 總數 18，其中 exact pure publication error 為 14，通過 1-19 narrow one-off size gate
* [x] Tracked migrations 只顯示 `events_updated_at` 是 `events` update 的直接 trigger side effect；Supabase REST 不暴露 `information_schema`/`pg_catalog`，live catalog inventory 仍是 reset entry gate
* [x] `scraper/_oneoff_reset_publication_error.py` 已改為 exact-ID dry-run snapshot 與 apply-time per-row CAS
* [x] Apply path 拒絕 source-only、limit、missing IDs、UUID prefix/invalid value、20+ exact IDs，以及 snapshot digest/operator drift
* [x] Apply path 不再匯入或呼叫 GPT annotation，不 settle reports，不修改、刪除或 upsert `field_corrections`
* [x] Snapshot 記錄 full event rows、operator HEAD、script SHA-256、related FC hash/count、pending `annotation_error_stuck` report rows 與內部 digest
* [x] Stable-field contract 由完整 event row 動態計算，排除 `annotation_status`、`annotation_retry_count` 與 `updated_at`
* [x] `updated_at`-only drift 以 warning 記錄；stable non-target drift、third state、FC/report drift 或 CAS 0/multi-row 均停止
* [x] 新增 `scraper/tests/test_reset_publication_error.py`，focused Lane R tests 目前 `17 passed`
* [x] Full scraper suite、compileall、`git diff --check`、diagnostics 與 final status 驗證通過

## Round T-A：Admin cleanup CLI

* [ ] T-P 與五條 G lane 都已部署後才開始
* [ ] Admin CLI 成為第二 consumer 時才抽 shared policy-neutral helpers
* [ ] 實作 discover、classify、freeze、apply、rollback、export-review
* [ ] 全部 action 使用 full report UUID、完整 before-image 與 journaled per-field write
* [ ] 加 failure-injection 與 rollback rehearsal tests
* [ ] Tester PASS 並取得 tools-only 核准，不授權 DB write

## Phase 4：publication manifest 與 live repair

* [ ] 驗證 exact deployed H0 `5457b5f2`、G1 `a2ba5bbe`、G4a `60978b5c` 至 `1295ca4d`、G3 settlement `e8552682`
* [ ] 驗證 exact G-P SHA、clean authorized cycle 與 exact Lane R SHA
* [ ] 驗證 maintenance inactive row、false RPC 與四象限 auth evidence
* [ ] 以 repeated full UUID 產生單一 canonical publication reset snapshot
* [ ] Reset 僅允許 `error -> pending`、retry count 歸零與其他欄位不變
* [ ] Snapshot 與 after report 記錄 observed `updated_at` drift warning，不預猜 `updated_at`
* [ ] Writers disabled 時完成 verify 與 apply preflight；不建立 rollback preview 或 reverse compensation
* [ ] 先 release lock 並確認 inactive，再 restore workflow 與 variable
* [ ] 第一個 scheduled 或 GPT write 後關閉 rollback horizon，後續只 fix-forward
* [ ] 正常 annotation 成功後，僅由下一次 `error_recovery.py` 執行 settlement
* [ ] Production reset、maintenance lock、workflow state 變更與 post-reset manual annotation dispatch 均需另行核准

## 後續 Admin cleanup 與資料工作

* [ ] 部署 T-A 後凍結 fresh $P_0$ ledger，兩次完整掃描 byte-identical
* [ ] 驗證 $P_0=A+S+M$，每個 full report ID 只有一個 current class
* [ ] Automatic batch 不含 compound、human、mixed、unknown、empty 或 payload token
* [ ] Digest-bound automatic manifest apply 與 rollback preview
* [ ] Evidence-qualified Round S source release、manifest 與 apply
* [ ] Manual reports 產出 digest-bound review export
* [ ] Final reconcile 與完整 scheduled observation 不重建已修復 defect

## Approval gates

* [x] G-P 與 G-P.1 release approval、push、merge 及發布均已完成
* [x] 本次使用者「請執行」授權 Lane R tools implementation 與本地 validation，不授權 production reset、lock、workflow dispatch、manual annotation dispatch、migration apply、git push 或 Vercel deploy
* [ ] Lane R independent Tester、commit、push、merge、release 與 deployed SHA 記錄仍待另行核准
* [ ] T-A tools-only implementation 與 validation 另行核准
* [ ] Maintenance window 的 lock 與 writer state 操作另行核准
* [ ] 每個 production reset apply 以 exact IDs/count、deployed SHA、literal command 與 state-restoration procedure 另行核准
* [ ] 最終 docs-only archive 另行核准

## 本次驗證

* [x] Phase 0 worktree/status/released SHA rebaseline 完成
* [x] T-P patch backup SHA-256 與讀回驗證完成，退休 code/test WIP 已 local restore
* [x] Live candidate count 以 read-only SELECT 完成：14 active pure publication errors
* [x] `scraper/tests/test_reset_publication_error.py` 通過，`17 passed`
* [x] 完整 `scraper/tests` 通過，`443 passed, 1 skipped`，另有 11 個既有 `utcnow()` warning
* [x] `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m compileall -q scraper` 通過
* [x] `git diff --check` 通過
* [x] Modified-file diagnostics 通過
* [x] Final status 僅三個 Lane R path：reset script、focused test、tasks ledger
* [x] 無 staged 內容、commit、push、workflow dispatch、maintenance lock、production reset、manual annotation dispatch、migration apply、Vercel deploy 或 live DB write

## Done：歸檔條件

* [ ] G-P、Lane R、T-A 與需要時的 Round S 均獨立測試、部署並完成觀察
* [ ] Phase 4 與後續 data apply 全部使用核准的 exact-ID snapshot 與 literal command
* [ ] Fresh $P_0=A+S+M$ 驗證完成，manual rows 有 digest-bound export
* [ ] 每個 window 都先驗證 lock inactive，才 restore service-role writers
* [ ] Final exact scan 與完整 scheduled cycle 不重建已修復 defect
* [ ] 將 spec directory 移至 `docs/specs/archive/<YYYY-MM>-admin-reports-204-cleanup/`，並保留 `notes.md`
