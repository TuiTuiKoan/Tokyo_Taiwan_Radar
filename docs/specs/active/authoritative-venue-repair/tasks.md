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

* [x] 建立分離 canonical 與 alias indexes
* [x] 只載入 `is_authoritative = true` rows
* [x] Reject canonical/canonical same-tier collision
* [x] Reject alias/alias same-tier collision
* [x] Reject canonical/alias 與 alias/canonical cross-tier collision
* [x] Load failure 清空並 cache empty registry，不留下 partial/stale data
* [x] 新增 test-only cache reset helper
* [x] 測試 canonical、alias、unknown、各 collision、load failure 與 reset/reload
* [x] 第一個 substantive edit 後立即跑 registry focused suite

## Phase 2: Desired-state venue seed

* [x] Alias union 改為 tracked desired-state exact replacement
* [x] Seed-wide canonical/alias all-tier collision preflight fail closed
* [x] Postal-code、NFKC、dash、whitespace 與 street address normalization
* [x] 保留 active-event conflict guard
* [x] Dry-run 精確分類 insert、update、noop、conflict 與 skip
* [x] 修正 TCC、八丁座、サロンシネマ、Century 與高田地址；高田/TIFF homepage preserve live
* [x] 八丁座 aliases 移除 `サロンシネマ` 與 `サロンシネマ1・2`
* [x] 新增三個 TIFF physical authoritative seeds，但不預猜 production UUID
* [x] 測試 stale alias removal、collision、address compatibility、active conflict、noop 與零寫入

## Phase 3: Database FK population

* [x] Canonical venue query 只接受 authoritative rows
* [x] Alias query 移除 `.limit(1)` 並讀取完整 authoritative matches
* [x] 只有唯一命中才寫 `venue_id` 與 canonical fields
* [x] 傳播 JA/ZH/EN names、address、prefectures、stable homepage 與 fill-only hours
* [x] 所有 venue field writes 遵守 FC precedence 與既有 override-attempt accounting
* [x] Pure publication bypass venue resolution
* [x] Multi-venue output 保持 FK 與 physical addresses null
* [x] Ambiguous/non-authoritative lookup 保持 unset 並輸出可測試 warning
* [x] 不把 source、official、submission、organizer、ticket 或 schedule URL 提升為 location URL
* [x] 測試 canonical、alias、ambiguous、non-authoritative、multi、publication 與 URL ownership
* [x] 測試 normal 與 force-rescrape FC precedence

## Phase 4: TIFF venue-tree routing

* [x] Same-year 同時取得 films API 與 venues API
* [x] 遞迴 flatten 完整 venue tree
* [x] 每個 act screen 提升至最近的 `type = "cinema"` parent
* [x] 每個 physical cinema 經 authoritative resolver 取得 canonical row
* [x] Unknown screen、venues fetch failure 與 unprovable venue 跳過整部 film
* [x] Single venue 輸出唯一 FK 與完整 canonical fields
* [x] Multi venue 依 act 首次出現順序 dedupe 並以 `・` join
* [x] Multi venue 保持 FK/address translations null，prefecture 為東京都
* [x] `TiffJpScraper` news path 無行為 diff
* [x] 建立 2025 films/venues offline fixtures
* [x] Fixture 驗證木々の隙間為 Chanter only
* [x] Fixture 驗證エイプリル為 Hulic、Chanter、Cineswitch
* [x] Fixture 驗證ダブル・ハピネス為 Hibiya screens 12/13、Cineswitch
* [x] Fixture 驗證人生は海のように為 Chanter、Hibiya screens 12/13、Cineswitch
* [x] Failure-path tests 證明 unknown screen 與 venues failure 不回退 TIFF brand

## Phase 5: Fixed sources and TCC regression

* [x] Johakyu 八丁座地址改為胡町福屋八丁堀本店8F
* [x] Johakyu サロンシネマ地址改為八丁堀広島東映プラザビル8階
* [x] Johakyu facility homepage 由 registry 提供，不由 schedule URL 提供
* [x] Starcat 只更新 Century 至栄3-29-1名古屋パルコ東館8F
* [x] Century ticket schedule 仍只作排片 input
* [x] TCC source writer 零 production-code diff
* [x] TCC tests 覆蓋 default center、explicit external、multi-city 與 online/multi-event

## Phase 6: Immutable production repair tool

* [x] 新增 `_oneoff_repair_authoritative_venues.py`
* [x] Default invocation mechanically read-only
* [x] Capture、apply、rollback CLI modes 互斥且不隱式切換
* [x] Capture output 限定 ignored `tmp/` path 並 exclusive create
* [x] Manifest 保存 schema、timestamp、project ref 與 exact origin SHA
* [x] Manifest 保存 per-action dependency、eligibility、digest 與 fixed order
* [x] Manifest 保存完整 venue/event/FC before/after image 與 explicit FC absence
* [x] Manifest canonical bytes 與 whole-manifest SHA-256 可重算驗證
* [x] Capture 後檔案不可更新、補值或重新排序
* [x] Event/FC actions 使用 `unlock_and_write()` expected event/FC CAS
* [x] Null sentinel、array JSON 與 unrelated FC preservation 符合 repository contract
* [x] Human FC 與不同 nonempty submission URL 分類為 review conflict
* [x] Venue update/delete 使用 full-row CAS 與 local journal
* [x] Venue insert 同時驗證 UUID absence 與 canonical-name absence
* [x] Venue delete 在 mutation 時再次驗證 zero references
* [x] Apply 先全批 before gate，再依 venue、event/FC、invariant、duplicate delete 排序
* [x] Rollback 逆序並以 post-apply exact CAS，apply failure 不自動 rollback
* [x] Exact after state 分類 already-applied，partial/third state STOP
* [x] 同 manifest 第二次 apply 全部 noop/already-applied 且零 mutation

## Phase 7: Production action classification tests

* [x] TCC six migrate 與 three attach actions 精確命中完整 UUID
* [x] Japanese duplicate three historical、eight false、two multi/non-event unlink actions
* [x] Chinese duplicate historical-text-preserving unlink action
* [x] Online grant pure-online canonical fields 與 malformed system FC repair
* [x] 四個 URL rehome actions 保持 URL ownership
* [x] Canonical-linked complete live cohort 依 eligibility 重分類，不硬湊 29
* [x] TIFF parent、single Chanter 與三個 ordered multi-venue actions
* [x] Century keep-FK rewrite 與 attach-FK actions
* [x] 全 action tests 檢查 mutation payload、CAS、read-back、conflict 與 idempotency

## Phase 8: Engineer validation

* [x] Registry focused tests PASS
* [x] Database FK/force-rescrape FC tests PASS
* [x] Seed desired-state/collision/address/noop/dry-run tests PASS
* [x] TIFF 2025 fixture與 failure paths PASS
* [x] Johakyu、Starcat 與 TCC regression tests PASS
* [x] Repair capture/apply/rollback/CAS/idempotency/conflict/order tests PASS
* [x] `python -m compileall -q .` PASS from `scraper/`
* [x] `python -m pytest tests` PASS from `scraper/`
* [ ] Tiff source dry-run完成；current-year empty 只標 graceful empty
* [ ] Johakyu source dry-run PASS
* [ ] Starcat source dry-run PASS
* [x] Taiwan Cultural Center source dry-run PASS
* [x] `git diff --check` PASS
* [x] Scope assertion 無 `web/**`、`supabase/**`、`scraper/main.py` 或 merger diff
* [x] 主工作樹既有 WIP 保持原樣
* [x] Engineer Changes Log 列出 commits、paths、tests、dry-runs、risks 與 no-production-write

### Phase 8 Changes Log (2026-08-06)

Validated implementation commits before the docs-only validation commit:

* `3b59beae4b70d053610d6336158eb626301ef2ed` establish the active spec
* `3aae7dadf96f51395c4db4b2d4ba50963d7b0a2e` make the registry collision-safe
* `f2da30bb7f3398e30edcf83d096584423f3ce23e` enforce seed desired state
* `29b13ab78569ccf2f196dd4f64bc35e302aee18f` enforce authoritative propagation
* `0d82677adcf0dd3a8fd502dbc932c7b694f5b551` route TIFF films to physical venues
* `e2afa4eba5b18985078b8c2f15060702ce2e52fa` update fixed venue locations
* `46c66cd90c3914028427356331be657d259fd0cf` add the immutable repair tool
* `f2237f7d5fa914d803e071654ca74b92d9b0ec3a` add production action planning

Feature paths at the validation boundary:

* `docs/specs/active/authoritative-venue-repair/proposal.md`
* `docs/specs/active/authoritative-venue-repair/tasks.md`
* `scraper/_oneoff_repair_authoritative_venues.py`
* `scraper/_oneoff_seed_authoritative_venues.py`
* `scraper/database.py`
* `scraper/sources/base.py`
* `scraper/sources/johakyu.py`
* `scraper/sources/starcat_cinema.py`
* `scraper/sources/tiff.py`
* `scraper/tests/fixtures/tiff_2025_films.json`
* `scraper/tests/fixtures/tiff_2025_venues.json`
* `scraper/tests/test_authoritative_venue_repair.py`
* `scraper/tests/test_database_venue_fks.py`
* `scraper/tests/test_fixed_source_venue_contracts.py`
* `scraper/tests/test_seed_authoritative_venues.py`
* `scraper/tests/test_taiwan_cultural_center_location.py`
* `scraper/tests/test_tiff_venue_routing.py`
* `scraper/tests/test_venue_registry.py`
* `scraper/venue_registry.py`

Focused and broad validation from `scraper/`:

* `python -m pytest tests/test_venue_registry.py -ra`: 9 passed in 1.40s
* `python -m pytest tests/test_database_venue_fks.py -ra`: 11 passed, 1 warning in 1.54s
* `python -m pytest tests/test_seed_authoritative_venues.py -ra`: 10 passed in 1.47s
* `python -m pytest tests/test_tiff_venue_routing.py -ra`: 7 passed, 2 warnings in 1.12s
* `python -m pytest tests/test_fixed_source_venue_contracts.py tests/test_taiwan_cultural_center_location.py -ra`: 19 passed, 8 warnings in 1.20s
* `python -m pytest tests/test_authoritative_venue_repair.py -ra`: 48 passed in 2.54s
* `python -m pytest tests/test_tiff_venue_routing.py::test_2025_fixture_routes_films_in_first_act_order -vv -ra`: 1 passed in 1.25s
* `python -m compileall -q .`: PASS, 0.79s wall time
* `python -m pytest tests -ra`: 622 passed, 1 skipped, 25 warnings in 13.86s; 15.04s wall time

The 25 full-suite warnings are the existing `datetime.utcnow()` deprecation at
`database.py:167`. The skipped test is the opt-in read-only DB gate, which remained disabled
because this phase forbids production queries.

The 2025 offline fixture test loaded both committed JSON fixtures and proved these ordered
routes: `木々の隙間` to Chanter; `エイプリル` to Hulic, Chanter, and Cineswitch;
`ダブル・ハピネス` to Hibiya screens 12/13 and Cineswitch; `人生は海のように` to
Chanter, Hibiya screens 12/13, and Cineswitch. The same focused suite proved unknown-screen,
unresolved-venue, and venues-API failure paths skip the whole film.

All source commands used the repository venv and `main.py --dry-run --source <name>` from
`scraper/`, with the main repository `scraper/.env` loaded read-only. An out-of-worktree
fail-closed guard replaced Supabase client entry points, cleared Sentry, and reported zero DB
access attempts for every command.

* `python main.py --dry-run --source tiff`: 0 events. The 2026 films API hostname did not
	resolve, so this is graceful degradation and remains INCONCLUSIVE, not parser proof.
* `python main.py --dry-run --source johakyu`: 0 events after finding two schedule sections.
	Zero output remains INCONCLUSIVE and is not recorded as PASS.
* `python main.py --dry-run --source starcat_cinema`: 5 events. Century used the corrected
	`栄3-29-1 名古屋パルコ東館8F` address and kept the ticket URL out of `location_url`.
	One event, `鯨が消えた入り江`, had `start_date=2026-08-20` after
	`end_date=2026-08-13`; the source gate remains FAIL because date repair is outside this
	feature's approved venue-only scope.
* `python main.py --dry-run --source taiwan_cultural_center`: 20 events, all with non-null
	start and end dates. It preserved TCC, Euro Live, Keio, Chuo, and Kyoto external venue
	distinctions. Eight date-parse warnings used fallback extraction without dropping records.

`git diff --check`, fail-closed path scope, no-`web/messages/*.json`, and editor diagnostics
for all modified Python files passed. Gitleaks 8.30.1 scanned all eight implementation commits
(about 285 KB) with redaction and found no leaks; the executable pre-commit hook also contains
the staged gitleaks gate.

The main worktree remained at `8c701799a29f39c1891c9103f79e8a3b88c5a61b`, with the same
13 WIP paths, identical tracked diff hash, empty index, and empty stash. One untracked prompt
changed concurrently immediately after the initial raw-file snapshot, but remained untracked;
no feature command wrote, staged, stashed, cleaned, or restored any main-worktree path.

No push, manifest preview or capture, repair apply or rollback, production query, production
write, or other production mutation was executed. Phase 9 and Gate 1 remain entirely open.

### Tester correction cycle 1 triage (2026-08-06)

This targeted cycle rechecked causality against exact feature base
`f3884ebaf5b10e151e4676f5ea3e92fdf96838f1` and pre-triage HEAD
`1c8b577430c91975f192aa5bb69b2a33ba82f774` before making this docs-only update.

Exact causality evidence:

* `git diff f3884eba..HEAD -- scraper/sources/starcat_cinema.py` contains exactly one
  changed line: Century's address changed from the old Skyle building value to
  `愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F`. The base and HEAD blobs are
  `aae4e54055990e2f9dca33fb2f25bedaed8f46f5` and
  `98472124472da13bfcbd4df3a5fc9023f03a12f5` because of that line alone.
* The Starcat control path from `_build_ticket_schedule()` through
  `Event(end_date=schedule_end)` is byte-identical at base and HEAD. Both extracted regions
  have SHA-256
  `d7c258a0a744580813c8cff2dafde9d306d88af7fae83edbe826a03e87ef2da9`.
  Commit `e2afa4eba5b18985078b8c2f15060702ce2e52fa` therefore changed the Century
  address, not date parsing or schedule lookup.
* `git diff --exit-code f3884eba..HEAD -- scraper/sources/taiwan_cultural_center.py`
  returned 0. The base and HEAD writer blobs are both
  `a1ec1f349f584859410a241f6817b77a958fecf3`, proving zero TCC production-writer
  change in this feature.

Focused rerun evidence:

* `python -m pytest tests/test_fixed_source_venue_contracts.py -vv -ra` passed all four
  tests. The contracts preserve current Johakyu addresses, the Century PARCO address,
  registry-owned facility homepages, and ticket-schedule URL ownership.
* `python -m pytest tests/test_taiwan_cultural_center_location.py -vv -ra` passed all
  15 tests with eight existing `datetime.utcnow()` warnings. Default-center, explicit
  external, multi-city, online, and mixed-batch location behavior remained intact.
* The guarded Starcat dry-run returned five events and made zero DB access attempts.
  Its one Century event used the corrected PARCO address, and the ticket URL appeared in
  none of `source_url`, `official_url`, or `location_url`. The output still exposed
  `鯨が消えた入り江` with `start=2026-08-20` and `end=2026-08-13`.
* The guarded Johakyu dry-run found two schedule sections, parsed all six dated week
  headers, and returned zero events with zero DB access attempts. The live page contained
  59 valid-title candidates among 67 item containers; eight containers were placeholders.
  The production path checked 24 deduplicated external references, received 21 nonempty
  texts, and found zero Taiwan hits in titles or external text. This is a current-source
  no-relevant-match result, not a zero-candidate or parser-health implementation gap.

The following three residual risks remain visible and intentionally unfixed:

* Starcat emits one inverted date range. Exact byte identity of the full date-control path
  proves this is pre-existing, while the governing scope permits only the Century address
  update and forbids event-date changes.
* The Tester-observed 20 TCC dry-run events retain noncanonical `culture`. The TCC writer
  blob is identical to the feature base, and the governing scope forbids category changes
  and requires production-writer zero diff.
* The Tester-observed five TCC publish-date fallbacks, including at least four incorrect or
  truncated dates, also come from the byte-identical baseline writer. Date correction is
  expressly outside this venue-only feature.

The Phase 8 broad Starcat dry-run PASS checkbox remains unchecked because the inverted date
is still present. Phase 9 and Gate 1 remain unchecked. This correction cycle changed no
scraper production code, performed no production query or mutation, captured no manifest,
and did not push.

## Phase 9: Independent Tester

* [x] Tester 重新執行完整 focused 與 broad validation matrix
* [x] Tester 證明 2025 fixture 實際 exercise，不以 current-year empty 取代
* [x] Tester 證明 mocks 實際檢查 mutation payload 與 exact read-back
* [x] Tester 證明 31 target UUID 可由 read-only classification path 讀取
* [x] Tester scope assertion PASS
* [x] Tester verdict 明確 PASS；correction cycle 1 完成

### Final Test Report (2026-08-06)

Independent Tester correction cycle 1 reported PASS against exact pre-closure HEAD
`c9184c034c7bb7a80a6cc9df32c6cc1f271ec64d`.

* Focused suites totaled 104 passed; the full suite reported 622 passed, 1 skipped, and
  25 warnings
* Five high-risk nodes passed
* Fail-closed dry-runs made zero DB attempts: `tiff` returned 0 events, `johakyu`
  returned 0, `starcat_cinema` returned 5, and `taiwan_cultural_center` returned 20
* The read-only planner classified all 31 target UUIDs and 64 eligible actions; the
  second apply produced zero mutations
* Scope and safety assertions passed, including changed paths, production access,
  production mutation, manifest capture, push, and main-worktree preservation

Residuals remain visible and intentionally unfixed:

* Starcat retains one base-identical inverted date range
* The byte-identical TCC writer retains noncanonical `culture` and four publish-date
  fallbacks
* TIFF 2026 remains unavailable because of DNS failure, while the committed 2025 fixture
  proves the parser contract
* Johakyu's parser was fully exercised and found zero Taiwan hits

The governing scope forbids event-date and category fixes in this feature. Causality proof
shows that Starcat has exactly one changed address line and the TCC writer has zero diff.
Gate 1 remains entirely unchecked because the validated changeset has not yet been presented
to the user and no current push approval has been requested or granted.

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
