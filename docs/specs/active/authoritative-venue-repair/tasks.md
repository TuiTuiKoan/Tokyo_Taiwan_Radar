---
title: 權威場館修復執行追蹤
description: authoritative-venue-repair 的隔離、實作、驗證與兩階段 production gate
---

## Tracking rules

每完成一項即更新 checkbox 並納入 scoped commit。此檔是跨 session 的進度真實來源；
`/memories/session/plan.md` 保存完整架構、UUID allowlist、production protocol 與 STOP 條件。

## Phase 0: Worktree, evidence, and spec

* [x] 讀取現行 global、Git、scraper、Architect、Engineer、Tester 與 Scraper Expert protocol
* [x] Fetch 最新 `origin/main`，確認 exact starting SHA `f3884eba`
* [x] 依 state matrix 判定 NEW，確認 branch、registered worktree 與 path 原先皆不存在
* [x] 從 `origin/main` 建 `feat/authoritative-venue-repair`
* [x] 掛載 `ttr-authoritative-venue-repair-worktree` 並驗證 clean
* [x] Idempotently 加入主 repository `.git/info/exclude`
* [x] 驗證主工作樹九個既有 tracked WIP 與 governing prompt 未被修改
* [x] 從官方頁複核 TCC、Johakyu、Century、Hulic 與 TOHO venue truth
* [ ] 以可稽核同網域官方證據複核高田世界館與 TIFF stable root
* [x] 以 mechanically read-only client 重新查詢 production baseline
* [x] 確認 31 target events、八 existing venues 與三個新 venue-name absences
* [x] 確認 TCC canonical-linked 29、duplicate references 19/1 與兩個 live collisions
* [x] 建立 `/memories/session/plan.md` 並獨立重讀驗證
* [x] 建立 active `proposal.md` 與 phase-aligned `tasks.md`
* [x] Commit Phase 0 spec foundation，不納入主工作樹 WIP

## Phase 1: Authoritative registry

* [ ] 建立分離 canonical 與 alias indexes
* [ ] 只載入 `is_authoritative = true` rows
* [ ] Reject canonical/canonical same-tier collision
* [ ] Reject alias/alias same-tier collision
* [ ] Reject canonical/alias 與 alias/canonical cross-tier collision
* [ ] Load failure 清空並 cache empty registry，不留下 partial/stale data
* [ ] 新增 test-only cache reset helper
* [ ] 測試 canonical、alias、unknown、各 collision、load failure 與 reset/reload
* [ ] 第一個 substantive edit 後立即跑 registry focused suite

## Phase 2: Desired-state venue seed

* [ ] Alias union 改為 tracked desired-state exact replacement
* [ ] Seed-wide canonical/alias all-tier collision preflight fail closed
* [ ] Postal-code、NFKC、dash、whitespace 與 street address normalization
* [ ] 保留 active-event conflict guard
* [ ] Dry-run 精確分類 insert、update、noop、conflict 與 skip
* [ ] 修正 TCC、TIFF、八丁座、サロンシネマ、Century 與高田世界館 verified values
* [ ] 八丁座 aliases 移除 `サロンシネマ` 與 `サロンシネマ1・2`
* [ ] 新增三個 TIFF physical authoritative seeds，但不預猜 production UUID
* [ ] 測試 stale alias removal、collision、address compatibility、active conflict、noop 與零寫入

## Phase 3: Database FK population

* [ ] Canonical venue query 只接受 authoritative rows
* [ ] Alias query 移除 `.limit(1)` 並讀取完整 authoritative matches
* [ ] 只有唯一命中才寫 `venue_id` 與 canonical fields
* [ ] 傳播 JA/ZH/EN names、address、prefectures、stable homepage 與 fill-only hours
* [ ] 所有 venue field writes 遵守 FC precedence 與既有 override-attempt accounting
* [ ] Pure publication bypass venue resolution
* [ ] Multi-venue output 保持 FK 與 physical addresses null
* [ ] Ambiguous/non-authoritative lookup 保持 unset 並輸出可測試 warning
* [ ] 不把 source、official、submission、organizer、ticket 或 schedule URL 提升為 location URL
* [ ] 測試 canonical、alias、ambiguous、non-authoritative、multi、publication 與 URL ownership
* [ ] 測試 normal 與 force-rescrape FC precedence

## Phase 4: TIFF venue-tree routing

* [ ] Same-year 同時取得 films API 與 venues API
* [ ] 遞迴 flatten 完整 venue tree
* [ ] 每個 act screen 提升至最近的 `type = "cinema"` parent
* [ ] 每個 physical cinema 經 authoritative resolver 取得 canonical row
* [ ] Unknown screen、venues fetch failure 與 unprovable venue 跳過整部 film
* [ ] Single venue 輸出唯一 FK 與完整 canonical fields
* [ ] Multi venue 依 act 首次出現順序 dedupe 並以 `・` join
* [ ] Multi venue 保持 FK/address translations null，prefecture 為東京都
* [ ] `TiffJpScraper` news path 無行為 diff
* [ ] 建立 2025 films/venues offline fixtures
* [ ] Fixture 驗證木々の隙間為 Chanter only
* [ ] Fixture 驗證エイプリル為 Hulic、Chanter、Cineswitch
* [ ] Fixture 驗證ダブル・ハピネス為 Hibiya screens 12/13、Cineswitch
* [ ] Fixture 驗證人生は海のように為 Chanter、Hibiya screens 12/13、Cineswitch
* [ ] Failure-path tests 證明 unknown screen 與 venues failure 不回退 TIFF brand

## Phase 5: Fixed sources and TCC regression

* [ ] Johakyu 八丁座地址改為胡町福屋八丁堀本店8F
* [ ] Johakyu サロンシネマ地址改為八丁堀広島東映プラザビル8階
* [ ] Johakyu facility homepage 由 registry 提供，不由 schedule URL 提供
* [ ] Starcat 只更新 Century 至栄3-29-1名古屋パルコ東館8F
* [ ] Century ticket schedule 仍只作排片 input
* [ ] TCC source writer 零 production-code diff
* [ ] TCC tests 覆蓋 default center、explicit external、multi-city 與 online/multi-event

## Phase 6: Immutable production repair tool

* [ ] 新增 `_oneoff_repair_authoritative_venues.py`
* [ ] Default invocation mechanically read-only
* [ ] Capture、apply、rollback CLI modes 互斥且不隱式切換
* [ ] Capture output 限定 ignored `tmp/` path 並 exclusive create
* [ ] Manifest 保存 schema、timestamp、project ref 與 exact origin SHA
* [ ] Manifest 保存 per-action dependency、eligibility、digest 與 fixed order
* [ ] Manifest 保存完整 venue/event/FC before/after image 與 explicit FC absence
* [ ] Manifest canonical bytes 與 whole-manifest SHA-256 可重算驗證
* [ ] Capture 後檔案不可更新、補值或重新排序
* [ ] Event/FC actions 使用 `unlock_and_write()` expected event/FC CAS
* [ ] Null sentinel、array JSON 與 unrelated FC preservation 符合 repository contract
* [ ] Human FC 與不同 nonempty submission URL 分類為 review conflict
* [ ] Venue update/delete 使用 full-row CAS 與 local journal
* [ ] Venue insert 同時驗證 UUID absence 與 canonical-name absence
* [ ] Venue delete 在 mutation 時再次驗證 zero references
* [ ] Apply 先全批 before gate，再依 venue、event/FC、invariant、duplicate delete 排序
* [ ] Rollback 逆序並以 post-apply exact CAS，apply failure 不自動 rollback
* [ ] Exact after state 分類 already-applied，partial/third state STOP
* [ ] 同 manifest 第二次 apply 全部 noop/already-applied 且零 mutation

## Phase 7: Production action classification tests

* [ ] TCC six migrate 與 three attach actions 精確命中完整 UUID
* [ ] Japanese duplicate three historical、eight false、two multi/non-event unlink actions
* [ ] Chinese duplicate historical-text-preserving unlink action
* [ ] Online grant pure-online canonical fields 與 malformed system FC repair
* [ ] 四個 URL rehome actions 保持 URL ownership
* [ ] Canonical-linked complete live cohort 依 eligibility 重分類，不硬湊 29
* [ ] TIFF parent、single Chanter 與三個 ordered multi-venue actions
* [ ] Century keep-FK rewrite 與 attach-FK actions
* [ ] 全 action tests 檢查 mutation payload、CAS、read-back、conflict 與 idempotency

## Phase 8: Engineer validation

* [ ] Registry focused tests PASS
* [ ] Database FK/force-rescrape FC tests PASS
* [ ] Seed desired-state/collision/address/noop/dry-run tests PASS
* [ ] TIFF 2025 fixture與 failure paths PASS
* [ ] Johakyu、Starcat 與 TCC regression tests PASS
* [ ] Repair capture/apply/rollback/CAS/idempotency/conflict/order tests PASS
* [ ] `python -m compileall -q .` PASS from `scraper/`
* [ ] `python -m pytest tests` PASS from `scraper/`
* [ ] Tiff source dry-run完成；current-year empty 只標 graceful empty
* [ ] Johakyu source dry-run PASS
* [ ] Starcat source dry-run PASS
* [ ] Taiwan Cultural Center source dry-run PASS
* [ ] `git diff --check` PASS
* [ ] Scope assertion 無 `web/**`、`supabase/**`、`scraper/main.py` 或 merger diff
* [ ] 主工作樹既有 WIP 保持原樣
* [ ] Engineer Changes Log 列出 commits、paths、tests、dry-runs、risks 與 no-production-write

## Phase 9: Independent Tester

* [ ] Tester 重新執行完整 focused 與 broad validation matrix
* [ ] Tester 證明 2025 fixture 實際 exercise，不以 current-year empty 取代
* [ ] Tester 證明 mocks 實際檢查 mutation payload 與 exact read-back
* [ ] Tester 證明 31 target UUID 可由 read-only classification path 讀取
* [ ] Tester scope assertion PASS
* [ ] Tester verdict 明確 PASS
* [ ] FAIL/INCONCLUSIVE 時完成 Engineer fix and Tester retry，最多三輪

## Gate 1: Push approval

* [ ] 顯示 exact local commits 與全部 changed paths
* [ ] 顯示完整 Test Report、dry-run evidence、risks 與 live drift
* [ ] 明確聲明 production 未 mutation
* [ ] 取得針對同一 validated changeset 的當下 push 批准
* [ ] 未批准前不 push、merge、main commit 或 capture manifest

## Post-Gate 1: Push and read-only capture

* [ ] V-M-D 完成 fetch、conflict check、clean rebase、revalidation 與 fast-forward push
* [ ] Fetch 並證明 exact `origin/main` 包含 validated feature commit
* [ ] 從同一 clean exact SHA 重新查官方來源與 production live state
* [ ] 產生 immutable manifest 與三筆固定新 venue UUID
* [ ] 顯示每個 full UUID action、dependency、before/after、conflict 與 digest
* [ ] 顯示 project ref、capture timestamp、new ID/name absence 與 duplicate ref counts

## Gate 2: Production approval

* [ ] 取得綁定同一 manifest SHA-256 的當下批准
* [ ] 批准明確涵蓋 writer pause/drain/resume
* [ ] 批准明確涵蓋 authoritative venue updates 與三筆 inserts
* [ ] 批准明確涵蓋 event/FC actions
* [ ] 批准明確涵蓋兩筆 duplicate conditional deletion
* [ ] Manifest digest 改變時重新取得 Gate 2

## Post-Gate 2: Production CAS and read-back

* [ ] 盤點所有 service-role writers
* [ ] Pause、drain 並證明零 in-flight writes
* [ ] 重新驗證 project ref、repo SHA、digest、all before CAS 與 refs
* [ ] 依 manifest 固定順序執行並逐筆 read-back
* [ ] Zero-reference + full-row CAS 後才刪 duplicate venues
* [ ] 驗證 registry、venue、event、FC、URL、sentinel 與 TIFF invariants
* [ ] 第二次 apply 全為 noop/already-applied
* [ ] Resume writers 並監看第一個 writer run 無回歸
* [ ] Production Tester read-only exact verdict PASS
* [ ] 保存 final journal、rollback artifacts、conflicts 與 follow-up

## Deferred and forbidden

* [ ] NOT EXECUTED before Gate 1: push、merge、main commit、manifest capture
* [ ] NOT EXECUTED before Gate 2: production venue/event/FC mutation或 duplicate deletion
* [ ] NOT IN SCOPE: migration、web、i18n、main.py、merger、geocoder、event non-venue fields