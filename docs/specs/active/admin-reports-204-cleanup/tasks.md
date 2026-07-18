# Tasks — admin-reports-204-cleanup

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。
完整設計見 [proposal.md](./proposal.md) 與權威計畫 `/memories/session/plan.md`；第二輪 critique 見 [notes.md](./notes.md)。

歷史觀測值（204 / 237 / 251）僅供彙總比較，**不是** apply gate，也不寫入任何 manifest。
新 manifest 的分割為動態 $P_0 = A + S + M$（自動修復／證據合格 source 修復／人工審查），不保留 117 / 43 / 44 固定執行數。

## Phase D0：交 Engineer 前的文件修訂（僅文字）

- [x] diff A（notes §4.1）：統一 disposition 基準
- [x] diff B（notes §4.2）：修 Group F 措辭殘留
- [x] diff C（notes §4.3）：明示 `confirmReport()` 對 compound row 的行為
- [x] 依此計畫改寫 proposal.md／tasks.md：204 標為歷史；刪除「204 JSONL 可從 session resource 取出」宣稱；刪除固定 117 / 43 / 44 Wave 數與舊 Wave A/B 拓撲；改為 H0-first、動態 $P_0=A+S+M$、五條 G lane、Round T-P/T-A、decision-16a 維護鎖遷移、per-artifact 核准拓撲；`notes.md` 不動

## Round H0：部署 SHA 上的緊急 writer-safety 熱修

- [ ] docs-only commit（proposal.md、tasks.md）先行，與 H0 code 分開
- [ ] 凍結 read-only production impact ledger（deployed SHA、workflow enabled 狀態、active runs、fresh exact pending baseline、`deployment_at <= created_at <= observed_through_utc` 全 ID 集合，deterministic ordering + 完整分頁 + exact-count 交叉核對，掃兩次 byte-identical，`0400` 雙份 + SHA-256、證明 byte 相等、零機密）；不改任何 row
- [ ] 建 `fix/event-report-writer-safety` worktree（基於含 docs commit 的 `origin/main`，`feb530e` 為 ancestor）
- [ ] 產出 event_reports consumer matrix（auto_qa / qa_auto_fix / qa_heartbeat / refetch_thin_events / error_recovery / annotator insert / web confirm-dismiss-submit / admin-owner-works / read-only / 禁用 G1-G3 one-off）
- [ ] 移除 `auto_qa.reconcile()` 泛用 reviewed→confirm 捷徑與 predicate-level reviewed skip
- [ ] 加 token-prefix aware、all-known-Auto 資格判定（`field:` / `fieldEdit:` / `selectionReason:` / unknown 永不自動處理）
- [ ] compound lifecycle invariant：deleted / inactive / reviewed / missing 不自動關閉 all-Auto compound
- [ ] `qa_auto_fix` / `qa_heartbeat` / `refetch_thin_events` / error-recovery 加 single-type 資格 + full report ID + pending CAS + exactly-one-row
- [ ] 先寫 fixtures（single、`[auto,auto]`、`[auto,human]`、`[human,auto]`、payload-token、unknown、empty、reordered；all-Auto compound deleted / inactive / reviewed / missing；reviewed no-FC / non-empty-FC / intentional-empty-FC）
- [ ] Verification 全綠、Tester PASS、取得含排程效果授權的核准後才部署

## Round G：殘餘 runtime prevention（五 lane）

- [ ] 建 `ttr-admin-reports-204-cleanup-worktree`（branch `feat/admin-reports-204-cleanup`），H0 已進 `origin/main` 才建；idempotent append `.git/info/exclude`
- [ ] 確認 tracked spec 已於 H0 step 0 修正且仍相符（204 歷史、無 missing-artifact／固定數指示）
- [ ] G3 前解決 `scraper/merger.py` 與 `merger-multi-signal-pass4` spec 的所有權衝突
- [ ] G1 Auto-QA predicate 正確性（與 G3 序列化整合）
- [ ] G2 prefecture 抽取 + 完整分頁
- [ ] G3 merger 分頁 + 共用 same-work primitive + annotation-error 結算
- [ ] G4a 跨 decision-16a 互動 writer 的共用維護鎖 + 三個 browser writer 改走 guarded server action + decision-16a 遷移
- [ ] G4b report-lifecycle status-last + deterministic QA 排程
- [ ] Verification 全綠、Tester PASS、deploy 核准明確接受／拒絕下一次排程 runtime writes
- [ ] 部署並觀察一個完整授權週期；任何 regenerated defect 阻擋後續 tooling／data cleanup

## Round T-P：共用 primitives + publication rollback 工具

- [ ] 建 `feat/admin-reports-cleanup-primitives` worktree（H0 / G1 / G4a 為 ancestor）
- [ ] 從 publication manifest 與 `unlock_and_write()` 抽取 immutable / pagination / snapshot / drift / journaled-write / after-image helpers
- [ ] 加 full-report-ID publication rollback + failure-injection／rollback rehearsal 測試
- [ ] Tester PASS、tools-only 核准（不授權任何 DB write）

## Round T-A：Admin cleanup CLI

- [ ] 建 `feat/admin-reports-cleanup-tooling` worktree（T-P 與五 G lane 皆 ancestor）
- [ ] 重用 T-P primitives，加 discovery / classify / freeze / apply / rollback / export CLI（全 full report ID、journaled per-field）
- [ ] failure-injection／rollback rehearsal 測試
- [ ] Tester PASS、tools-only 核准（不授權任何 DB write）

## Round D：digest-bound 生產操作（各自核准）

- [ ] Publication manifest（prereq：H0、G1、G4a、T-P）
- [ ] Fresh Admin automatic manifest（prereq：H0、G1、G2、G3、G4a、G4b、T-A）
- [ ] Source manifest（上述 + Round S）
- [ ] Reconcile-manifest（僅當 immediate reconcile 凍結為 full-ID manifest；預設走已授權的 recurring reconcile）
- [ ] Rollback apply（僅作為已預先授權的 partial-failure 回應）

## Round S：證據合格 source release

- [ ] 於 fresh ledger + 自動清理識別出實際 source defect 後才開始
- [ ] 依凍結的 evidence inventory 改對應 source 檔 + fixtures
- [ ] 獨立 implement／test／deploy／apply；deploy 核准明確涵蓋或暫停排程 scraper 效果

## Verification（每個 code release 都要過）

- [ ] `python -m pytest scraper/tests` 通過
- [ ] `python -m compileall -q scraper` 通過
- [ ] 各 `--dry-run`（auto_qa --reconcile／auto_qa／qa_auto_fix／qa_heartbeat／refetch_thin_events／error_recovery／backfill_location_prefectures／merger）無異常
- [ ] 每個被改的 source `python main.py --dry-run --source <name>` 正常
- [ ] 無 `web/messages/` 變更；`confirmReport()` fail-fast 且 status-last；唯一遷移為 decision-16a 維護鎖
- [ ] Tester 回 PASS；push 前取得使用者明確同意

## Done（歸檔條件）

- [ ] 每個部署週期後 fresh scan + nightly 不再重建已解決列
- [ ] 動態 $P_0 = A + S + M$ 分割驗證通過；人工列全數匯出且無 Python apply 可關閉
- [ ] `git mv docs/specs/active/admin-reports-204-cleanup docs/specs/archive/$(date +%Y-%m)-admin-reports-204-cleanup`；proposal.md status=archived；notes.md 保留
