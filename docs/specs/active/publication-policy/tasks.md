---
title: 純出版紀錄資料政策執行追蹤
description: publication-policy 各 phase、Wave 邊界、驗證與交付狀態
---

## Tracking Rules

每完成一項即更新 checkbox。此檔是 worktree 跨 session 的實作進度真實來源，
`/memories/session/plan.md` 是需求與設計的唯一 authoritative plan。

## Phase 0: Isolation, Spec, and Drift Gates

- [x] 完整讀取 `/memories/session/plan.md`
- [x] 讀取 Engineer skill 與適用 scraper、web、git、markdown instructions
- [x] 確認 target path/branch 不衝突，建立 `ttr-publication-policy-worktree`
- [x] 建立並驗證 `feat/publication-policy` 對應最新 `origin/main`
- [x] 將 `ttr-publication-policy-worktree/` 加入主 repo `.git/info/exclude`
- [x] 確認 worktree clean，且主工作樹其他 session WIP 未被修改
- [x] 建立 active spec proposal 與 phase-aligned tasks
- [x] 讀取相關 Next.js 16 本地 App Router、route、metadata 與 testing docs
- [x] 配置 worktree Python 與 Web dependencies，不複製 secrets 到 tracked files
- [x] 全量分頁唯讀 events baseline，記錄 exact forms、pure/mixed 與 source counts
- [x] 全量分頁唯讀 FC、reports、organizers baseline，記錄 exact counts 與 type sets
- [x] 以唯讀方式確認沒有 publication backfill、annotator、auto-QA 或 cron writer 同時執行
- [x] 將 baseline drift 與 plan baseline comparison 寫入 Changes Log

## Phase 1: Shared Pure-Publication Policy

- [x] 新增 Python `publication_rules.py` normalization、pure 與 NDL periodical helpers
- [x] 新增 publisher-name normalization、URL canonicalization 與 strict validator
- [x] 在 TypeScript 實作語意一致的 publication helpers
- [x] 新增共用 Web presentation flags
- [x] 測試 exact pure、normalized duplicates、mixed、books-media negative 與 missing-form negative
- [x] 測試 NDL book/periodical 分流與 publisher validator 正負例

## Phase 2A: Source Classification and Metadata

- [x] NDL 保留 pure publication/date/publisher，不寫 placeholder 或 blanket organizer type
- [x] Hanmoto 移除 fake hours/price，保留真實書價及 anchor href 語意
- [x] Kawade 將 physical launch/Talk/signing 分為非-publication physical forms
- [x] Eslite 僅接受 article UUID URL，分離 page date 與 event datetime
- [x] Eslite 實作 physical-signal priority 與 UUID identity migration gate
- [x] 四個 source 都新增離線 fixture 與 mixed-event negative tests

## Phase 2B: Database Writer Atomic Protection

- [x] 將 `publication` 加入 writer valid forms 並新增 regression test
- [x] `_event_to_row()` 在 enrichment 前套用七欄 NULL policy
- [x] 補齊 `location_prefectures` 與 `location_url` writer 支援
- [x] Pure row 跳過 venue lookup、venue FK 與 venue-hours propagation
- [x] Organizer registry lookup 可回填 validated homepage
- [x] Force-rescrape FC 套用後重新 enforce pure policy並偵測 conflict
- [x] Upsert 後 overwrite 七個 empty-sentinel FC，不使用 ignore-duplicates 語意
- [x] Read-back postcondition 同時驗證 events 七欄 NULL 與 FC 七欄 empty sentinel
- [x] `_auto_lock_location()` 以 normalized row/pure flag 避免重鎖
- [x] Writer tests 覆蓋 new、force、skip、registry、venue bypass 與 failure postcondition

## Phase 2C: Annotator Final Guard

- [x] 移除 source whitelist 作 domain truth，prefix 常數改為 label-only 語意
- [x] 移除 publication address/hours/price placeholders
- [x] Publisher 優先使用 scraper/DB/registry evidence，不由 GPT 猜測
- [x] 所有 enrichment 後執行 pure final normalization
- [x] 舊 non-empty FC 產生 manifest conflict，不恢復 placeholder
- [x] 驗證 normal、fix-reviewed 與 re-annotate-all paths
- [x] Pure postcondition 違反時標 error/停止 row write

## Phase 2D: Poster Vision Candidate Guard

- [x] enrich_poster candidate select 包含 event_form/source_name/image_url，並在送 Vision 前排除 exact pure
- [x] canonical placeholder image helper 拒絕 Hanmoto noimage/no-cover 變體，不 blanket 拒絕所有 Hanmoto 封面
- [x] Vision 回傳後、任何 event/FC write 前重新讀取並二次驗證 pure + placeholder guard
- [x] pure/noimage fixture 證明 Vision 與 write 都不呼叫
- [x] physical Hanmoto 真 poster 仍可 enrich，ordinary nonpublication 不受影響

## Phase 3: QA, Intake, Admin, and Governance

- [x] QA venue/hours/prefecture/price checks 只略過 exact pure
- [x] Pure missing publisher 維持 pending
- [x] Reconcile 逐一分析全部 report types，保護 manual/unknown/compound rows
- [x] 退役 source-based publication pending cleanup live apply path
- [x] Admin quality 與 roadmap 改用 pure helper並補 select/type prerequisites
- [x] Admin/account 四個 intake prompts 加入字元級一致的 pure-vs-physical 指引
- [x] 新增四 route prompt parity tests
- [x] 更新 scraper instruction、Engineer/Scraper Expert agents 與 skills
- [x] 更新 Tester 與四個 source skills
- [x] 更新相應 history，記錄 root cause 與一般化 lessons

## Phase 4: Public Web and Structured Data

- [x] Detail 隱藏 pure end/address/hours/price/status，保留出版日與 publisher/source
- [x] Pure narrative/FAQ 使用三語 publication/date 文案
- [x] Pure 不渲染 Calendar CTA
- [x] Source links canonicalize/deduplicate，加入 publisher website link
- [x] Pure organizer section 使用 publisher 語意
- [x] ReportSection 支援 typed excluded fields 並清除 stale state
- [x] EventCard 與 EventListClient 隱藏 pure range/status/price/venue
- [x] 首頁 inline card 路徑使用同一 pure presentation policy
- [x] Ordinary pure JSON-LD 輸出 Book
- [x] NDL periodical JSON-LD 輸出 Article
- [x] Pure JSON-LD 不含 Event-only keys，physical fixture 保持 Event
- [x] 三語 i18n 新增 publisher website、narrative 與 FAQ keys
- [x] 固定 fixtures 覆蓋 detail/card/list/FAQ/Calendar/Report/JSON-LD

## Phase 5: Immutable Legacy-Repair Manifest

- [x] 重構既有 publication metadata script，不新增重疊 apply script
- [x] 驗證 manifest/snapshot 路徑被 gitignore 規則覆蓋
- [x] Dry-run 全量分頁讀取 events、FC、reports、organizers
- [x] Manifest 保存 UUID、identity、before hash、classification evidence 與 planned diffs
- [x] Manifest 列出 included pure、excluded mixed、URL/FC/location/classification conflicts
- [x] Eslite Talk 建立獨立 migration action但不 live remap
- [x] Pure cleanup 使用七欄 lock-empty audit contract
- [x] 保留真實書價，只清明確 fake placeholder allowlist
- [x] NDL legacy periodical 修復尊重 title FC 與來源 metadata
- [x] Apply 只接受 immutable manifest並有全批 drift gate
- [x] Snapshot/rollback 設計涵蓋 events、FC、reports、organizers 與逐列 read-back
- [x] 執行 Wave 1 manifest dry-run，記錄 counts/conflicts/exclusions
- [x] 新增 poster placeholder pollution repair pre-action，限定 exact 8 筆 signature（含 source/placeholder/大阪城ホール/2023-10-14/FC batch evidence）
- [x] 每筆 pre-action 規劃先修 location_name/start_date，3 筆另修 organizer，再進 pure cleanup
- [x] pre-action 證據不足保持 conflict，不允許 source blanket
- [x] 新增 manifest 測試覆蓋 exact 8、near-miss、FC before/after、date/publisher repairs、ordering
- [x] 重產唯讀 manifest 後 non-Eslite unresolved location conflicts=0

## Wave 2 Boundary

- [x] DuckDuckGo/OpenAI providers 僅保留介面、validator、manifest evidence 與成本邊界
- [ ] DEFERRED / NOT EXECUTED: DuckDuckGo publisher search
- [ ] DEFERRED / NOT EXECUTED: OpenAI search-preview fallback
- [x] Wave 2 unresolved homepage 保持 `NULL`，不阻塞 Wave 1

## Phase 6: Verification and Delivery

- [x] Focused publication rules tests PASS
- [x] Database writer/FC/postcondition tests PASS
- [x] Annotator mode regression tests PASS
- [x] Auto-QA detect/reconcile tests PASS
- [x] Python deterministic publication suite PASS（75 tests）
- [x] 四個 source offline fixture tests 納入 deterministic suite 並 PASS
- [ ] NOT EXECUTED（scope）: 四個 source live dry-run；offline fixtures 為本輪 release gate
- [ ] NOT EXECUTED（scope）: DB-backed Auto-QA reconcile dry-run；deterministic reconcile tests PASS
- [x] Web deterministic suites PASS（14 + 2 tests）
- [x] TypeScript diagnostics與 `tsc --noEmit` PASS
- [x] i18n parity/removal/category guard PASS（1,161 checks）
- [x] Focused touched-file ESLint PASS
- [x] Full-repo lint reviewed：247 個既有 baseline findings，無 feature regression
- [x] Next.js production build PASS（250/250）
- [x] Structured-data fixture parse assertions PASS
- [x] Browser smoke：pure Book 四欄隱藏，ordinary Event 四欄保留
- [x] Manifest safety：SHA-256、333 筆 action 分布、drift/snapshot/read-back contract 已驗證
- [x] `git status --short` 無 MM，feature diff 不含主工作樹 WIP
- [x] Changes Log 保存於 spec 目錄並列出 Phase 6 證據與結果
- [x] Final independent Tester re-verdict PASS; no blockers
- [x] 本 changeset 將建立單一原子 local feature commit
- [ ] NOT EXECUTED: push、merge與 deploy
- [ ] NOT EXECUTED: live DB apply、Eslite live remap與 QA live reconcile（Eslite live remap 已於 2026-08-04T11:41:04Z 執行，詳 Delivery Batch 3；live DB apply 與 QA live reconcile 仍未執行）
- [x] 安全邊界確認：無 live DB write、push、merge或 deploy

## Delivery Batch 1: Venue Writer Stop + Writer Matrix（code-only）

### Phase 0: Worktree 前置

- [x] 依 git instructions state matrix 確認 CONTINUING，於 `ttr-publication-policy-worktree` / `feat/publication-policy` 作業
- [x] `git fetch origin` 後 fast-forward 至 `origin/main`（`ff499aa2`），既有 web WIP 位元組完全保留
- [x] 確認主工作樹與其他 worktree 的不相關 WIP 未被本批次觸及

### Phase 1a: 停掉兩個 pure-publication venue writer

- [x] 移除 annotator 將 NDL `publication_label_*` 複製進三個 `location_name*` 的 assignment
- [x] `_finalize_publication_update()` 清除三個 venue-name 欄位與其 localized staging 值
- [x] 非空 field_correction 時保留精確值並發出 structured warning marker，不 raise
- [x] 七個 canonical `PUBLICATION_NULL_FIELDS` 的 hard failure 維持不變，未替 venue-name 建立 empty sentinel
- [x] `_assert_pure_publication_payload()` 接受 protected-field context 並拒絕未豁免的非 null venue payload
- [x] `_verify_publication_postcondition()` 驗證未受保護欄位為 NULL、受保護欄位等於預期保留值
- [x] `database.py::_apply_pure_publication_policy()` 對 exact-pure row 清除三個 venue-name 欄位
- [x] NDL `publication_label_*` 僅保留於 periodical `description_*` prefix，docstring 改述為 publisher/periodical enrichment
- [x] 保留所有 legacy placeholder 常數與 fixtures 作為歷史污染 detector

### Phase 1a 測試

- [x] annotator 新增 unprotected 清除、non-empty FC 豁免、empty FC 視為未保護三類案例
- [x] annotator 新增 payload guard 與 postcondition 的 venue-name 正負向案例
- [x] database 證明 exact-pure 清除 scraper venue 值，`["lecture"]` 保留
- [x] 關鍵負向斷言：`["publication","lecture"]` 混合型不得被當成 pure 處理

### Phase 1b: Writer matrix 稽核（唯讀）

- [x] 稽核 13 個目標欄位的所有可呼叫 writer，判準為是否 select `event_form` 與 mutation 前是否重檢 exact-pure
- [x] 明確涵蓋 5 個 location-enrichment guards、`annotator.py`、`database.py`、organizer_type authority path 與 venue/prefecture backfills
- [x] 矩陣寫入 `changes-log.md`，區分 covered、uncovered 與 verified non-writers
- [x] 發現 11 個未覆蓋 producer，已標示 blocks Phase 3（不阻擋 Batch 1 釋出）

### Batch 1 驗證與邊界

- [x] 聚焦測試 PASS（36 tests）
- [x] 全量 scraper 測試 PASS（473 passed, 1 skipped）
- [x] `compileall` 與 `git diff --check` PASS
- [x] `web/messages/*.json` 本批次零 diff；測試期間無 production DB 連線或寫入
- [ ] NOT EXECUTED（授權邊界）: Phase 3、`qa_auto_fix.py`、`_oneoff_backfill_publication_metadata.py`、`test_publication_manifest.py`
- [ ] NOT EXECUTED（授權邊界）: live DB apply、SQL migration、`web/` 變更、push、merge 與 deploy

## Delivery Batch 2: Phase-Aware Manifest Executor（code-only）

### Phase 0: Worktree 前置

- [x] 於既有 `ttr-publication-policy-worktree` / `feat/publication-policy` 續作（CONTINUING）
- [x] 未觸碰 worktree 內既有 `web/` WIP（7 檔位元組保留）

### Phase 3 執行器實作

- [x] `apply_phase` 成為唯一寫入選擇器；`route_action` 取代舊 `phase` provenance key
- [x] 三個 scoped checkpoint（`fc-remove.before` / `fc-remove.after` / `event-clear.after`）納入單一 manifest digest
- [x] `unlock_and_write()` 新增 `expected_fc` / `expected_event_value` / `expected_event_form` CAS 契約
- [x] `_audit_start()` 以既有 `field_correction_id` 欄位錨定 removal，未新增 migration
- [x] `event-clear` 先跑六欄 value-level CAS patch，再跑七個 canonical `lock_empty`
- [x] 全 no-op extended patch 被跳過（語意未弱化）

### Batch 2 修復：after-checkpoint 假 drift

- [x] 根因確認：manifest 內尚未建立的 empty sentinel 記為 `id: null`，read-back 讀到 DB 指派的 id，同一筆同時被判 `missing` 與 `unexpected`
- [x] `structural_row_diff()` 改為配對式比對，新增 `allow_db_assigned_ids` 參數（預設 False）
- [x] 既有列（before checkpoint、preserve set、`unlock_only` 刪除目標）仍以完整 FC `id` 比對，未一併放寬
- [x] 本 phase 新建列以 `(event_id, field_name)` + `corrected_value` / `original_value` / `corrected_by` / `report_id` 比對
- [x] 放寬僅套用於 `.after` checkpoint 的 `target_field_corrections`；`events` 與 `preserve_field_corrections` 維持 id-exact
- [x] `test_cleanup_phases_never_select_the_eslite_candidate` fixture 補上受污染 FC，讓 `fc-remove` 有真實工作（實作行為正確，無 FC 時不選取）
- [x] 新增 `test_after_checkpoint_still_rejects_drift_on_phase_created_sentinels`（值漂移與多餘 target FC 皆 STOP）
- [x] 新增 `test_existing_rows_still_match_only_on_the_full_field_correction_id`（證明既有列未被放寬）
- [x] red-when-broken 驗證：停用 `_phase_created_row_matches` 與 `structural_row_diff` 後偵測翻為 False

### Batch 2 驗證與邊界

- [x] 聚焦測試 PASS（66 tests）
- [x] 全量 scraper 測試 PASS（520 passed, 1 skipped）
- [x] `compileall -q scraper` 與 `git --no-pager diff --check` PASS
- [x] `web/` 本批次零 diff；測試期間無 production DB 連線或寫入
- [ ] NOT EXECUTED（授權邊界）: live DB apply、manifest apply、lock 操作、push、merge 與 deploy

## Delivery Batch 3: Eslite Gate Release（code + docs）

### Phase 0: 前置驗證

- [x] 於既有 `ttr-publication-policy-worktree` / `feat/publication-policy` 續作（CONTINUING）
- [x] 未觸碰 worktree 內既有 `web/` WIP（7 檔位元組保留）
- [x] 確認 remap 已執行：rollback 快照僅含舊值，DB `updated_at` 晚 46 秒
- [x] 確認 `source_id` 於 `eslite_spectrum` 及全表均唯一
- [x] 以 `ESLITE_ALLOW_UUID_IDENTITY=1` 做 dry-run 審視（355 筆，2019–2026）

### 程式修復

- [x] `_MIGRATION_GATE_DEFAULT = True`，保留 env override（`=0` 仍可關閉）
- [x] 新增固定下限 `_HISTORY_FLOOR = date(2026, 1, 1)`（非滾動視窗）
- [x] 歷史底線於 `start_date` 解析後、identity 指派前套用；`start_date` 為空時維持原行為
- [x] `_SKIP_TITLE_RE` 新增八條 alternative，逐條對 355 筆驗證無誤殺
- [x] 以 `禮物節` + `(?:母の日|父の日)ギフト` 取代裸 `ギフト`；剔除冗餘且高風險的 `のご案内`
- [x] 不加 `オープン` 與 `営業`（實測會誤殺兩筆真實活動），並以註解鎖定
- [x] `誠品選書` 列入 skip，依據：全表唯一一筆為 `is_active=false`，且 `event_form` 分類不穩定

### 測試

- [x] `test_eslite_emits_events_with_gate_default_and_no_env`（預設會產生事件 + `source_id` 格式）
- [x] `test_eslite_gate_still_closable_by_env`（override 語意保留）
- [x] `test_eslite_history_floor_drops_archive_and_keeps_floor_day`（邊界日通過）
- [x] `test_eslite_skip_patterns_drop_promotions_but_keep_real_events`（含兩筆誤殺風險樣本）
- [x] `pytest scraper/tests -q` PASS（532 passed, 1 skipped；HEAD 實測基準 528 + 4 新測試。計畫寫的 526 已過期，以 528 為準）

### 文件更正

- [x] changes-log 新增 Delivery Batch 3，記錄 remap 執行時間、證據與四項決策
- [x] 標註四處過期斷言為 SUPERSEDED（changes-log 兩處段落、一處清單、本檔一處）

### 驗證與邊界

- [x] S5 實測過濾結果：355 → 底線 −310 → 45 → skip −7 → **38**（以修改後模組的真實常數重跑）
- [x] 7 筆 skip 移除全為【誠品選書】月度書單，零誤殺；兩筆誤殺風險樣本已逐項確認
- [x] 最終集最早日期 `2026-01-24`、`location_name` 全含「誠品」、既有 active 事件仍在集內（UPDATE 非重複）
- [ ] NOT EXECUTED（授權邊界）: production DB write、push、merge 與 deploy；實際入庫交給 push 後的每日 cron
