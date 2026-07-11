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
- [ ] NOT EXECUTED: live DB apply、Eslite live remap與 QA live reconcile
- [x] 安全邊界確認：無 live DB write、push、merge或 deploy
