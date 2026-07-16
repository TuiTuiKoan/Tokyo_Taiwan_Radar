# Tasks — admin-reports-204-cleanup

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。
完整設計與驗證細節見 [proposal.md](./proposal.md)；第二輪 critique 見 [notes.md](./notes.md)。

基線算術：Wave A 117（78+31+8）+ Wave B 43（16+27）+ 人工佇列 44（24+4+16）= 204。

## Phase W: Worktree Setup（實作開始前）

- [ ] 依 `.github/instructions/git.instructions.md § Isolated worktree` 建 `ttr-admin-reports-204-cleanup-worktree`（branch `feat/admin-reports-204-cleanup`）
- [ ] idempotent append `ttr-admin-reports-204-cleanup-worktree/` 至 `.git/info/exclude`

## Phase D0: 交 Engineer 前的文件修訂（第二輪 critique，僅文字）

- [x] diff A（notes §4.1）：統一 proposal.md 兩張 disposition 表的基準（加註 baseline Deterministic 11 / Human 23）
- [x] diff B（notes §4.2）：修 Group F step 1 措辭殘留「in the immutable ledger」（計畫修訂時已套用為 execution manifest）
- [x] diff C（notes §4.3）：明示 `confirmReport()` 縮減版對 compound row 的行為（Group E step 5 補述：不 partial-close，走人工分支）
- [x] 確認上述已落地後，才進入實作 handoff

## Phase 0: 隔離工作並凍結 discovery 基線

- [ ] 產出 immutable discovery ledger artifact（204 個 report ID + SHA-256 digest）
- [ ] 確認 read-only 基線計數：204 pending / 179 events / 180 Auto-QA / 8 stuck / 16 human

## Phase 1: 先寫回歸測試（改 production 邏輯前）

- [ ] 於 `scraper/tests/` 新增聚焦測試，涵蓋 detector predicate、publication 語意、prefecture 解析、lifecycle
- [ ] 測試先紅（重現缺陷）再進入 Phase 2

## Phase 2: 防復發（Group A–F）

- [ ] Group A：修正 publication writer 語意（不再寫 physical-field placeholder）
- [ ] Group B：收斂並統一 QA predicate（detection / repair / reconcile 共用同一 helper）
- [ ] Group C：修復 prefecture 抽取（完整分頁 + bounded address 解析）
- [ ] Group D：補齊 report lifecycle（recovered rows 有 owner 關閉）
- [ ] Group E：deterministic handler 與 human review 改為 status-last
- [ ] Group F：先量化 43 列的 organizer 證據，只對有明確 `主催`／結構化 metadata 的子集修 parser

## Phase 3: 部署週期 1 — 驗證並部署 Group A–E

- [ ] 跑 Verification commands（見 proposal.md）全綠
- [ ] Tester 回 PASS
- [ ] 使用者核准後 push；部署 Group A–E + cleanup 工具

## Phase 4: 部署後凍結 Wave A apply 基線

- [ ] 記錄部署 commit SHA 至 Wave A apply snapshot
- [ ] 產出 Wave A execution manifest（78+31+8）

## Phase 5: Wave A 清理（117 列）

- [ ] Batch A1：結構性偽陽性 + publication 精度，78 列（dry-run → apply）
- [ ] Batch A2：deterministic 修復，31 列（dry-run → apply）
- [ ] Batch A3：stale reconciliation，8 列（dry-run → apply）
- [ ] 每批 partial failure 即停，未驗證的 report 留 pending

## Phase 6: 部署週期 2 + Wave B source-specific 修復（43 列）

- [ ] Wave A 完成自己的 nightly 觀察後才開始 Group F 實作
- [ ] Venue / region group，16 列
- [ ] Event metadata group，27 列
- [ ] 部署週期 2 → 產出 Wave B manifest（snapshot post-Wave-A state）

## Phase 7: 匯出人工 review 佇列（44 列，禁 Python apply）

- [ ] Uncertain Auto-QA，24 列
- [ ] Live annotation errors，4 列
- [ ] Human reports，16 列
- [ ] 匯出含完整 UUID + 證據 + 明確決定至 `tmp/`

## Phase 8: 對帳、重掃、觀察一個 nightly 週期

- [ ] 全量分頁計數 == `count='exact'`
- [ ] 每個基線 report ID 恰有一個 disposition
- [ ] fresh scan + nightly 不重建已解決的基線列

## Verification（每個部署週期都要過）

- [ ] `python -m pytest scraper/tests` 通過
- [ ] `python -m compileall -q scraper` 通過
- [ ] 各 `--dry-run`（backfill_location_prefectures / merger / auto_qa --reconcile / auto_qa / qa_auto_fix / error_recovery）無異常
- [ ] 每個被改的 source `python main.py --dry-run --source <name>` 正常
- [ ] 無 `web/messages/` 變更；`confirmReport()` fail-fast 且 status-last
- [ ] Tester 回 PASS；push 前取得使用者明確同意

## Done（歸檔條件）

- [ ] 兩個部署週期都完成、nightly 不再重建已解決列
- [ ] `git mv docs/specs/active/admin-reports-204-cleanup docs/specs/archive/$(date +%Y-%m)-admin-reports-204-cleanup`
