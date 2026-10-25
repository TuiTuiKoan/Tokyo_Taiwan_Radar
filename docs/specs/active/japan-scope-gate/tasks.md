---
title: Japan Scope Gate Tasks
description: Wave 1 delivery checklist and approval boundaries for the Japan scope gate
status: active
updated: 2026-10-25
---

## Phase 0：阻擋式 preflight

* [x] `git fetch origin` 後確認 `HEAD == origin/main == b3970b776f9a9d6909eab477f688111a555c1692`
* [x] 依 isolated worktree state matrix 建立 `ttr-japan-scope-gate-worktree` 與 `feat/japan-scope-gate`
* [x] Idempotent append `ttr-japan-scope-gate-worktree/` 至主 repo `.git/info/exclude`
* [x] 確認主 worktree 三個既存 Architect/Plan Critic WIP 未被修改、stash、清理或還原
* [x] 完成 v3.1 paged baseline，active identity 與 pending-report scalar/set assertions 全部通過
* [x] 記錄 capture window `2026-08-04T11:09:30.624644Z` 至 `2026-08-04T11:09:34.759722Z`
* [x] 記錄 active identity digest `bf6ed020c764acc1a0cc5690433c166c4d6b45867694a1528780bc6f1b4367d0`
* [x] Phase 0.5 保存指定事件的 GPT raw JSON 與 console；結果無 consumable scope output，可繼續

## Wave 1：本輪實作

* [x] Phase 1：抽出 canonical location classifier，保留 backfill re-export 與既有 tests
* [x] Phase 1 checkpoint：focused location tests `15 passed`，建立 atomic local commit
* [x] Phase 2：新增 annotator scope contract、runtime validation、effective-location decision 與 report lifecycle
* [x] Phase 2：擴充 manual consumer eligibility tests
* [x] Phase 2：在 isolated worktree 更新 Architect Dead Instruction Guard 與 Baseline Snapshot Completeness Guard
* [x] Phase 2 checkpoint：imports OK，focused `21 passed`，regression `74 passed`，建立 atomic local commit
* [x] Phase 3：閉合 admin per-row confirm、bulk exclusion、history status 與 machine-note visibility
* [x] Phase 3：三語 i18n、指定 web tests `36 passed` 與 production build `250/250` static pages PASS
* [x] Phase 3 checkpoint：本 atomic web commit 收尾，三語 i18n diff `0 key deletion`
* [x] Phase 4（web）：指定四檔 tests `36 passed`，`pnpm build` PASS（`250/250` static pages）
* [x] Phase 4（scraper）：imports OK；Phase 1/2 具名 suites `95 passed`
* [x] Phase 6a：commit `321a0859` 實作 one-off snapshot/apply safety interface
* [x] Phase 6a：執行唯讀 snapshot attempt，22 個 prefix 唯一解析、evidence 與 active state 通過
* [x] Phase 6a review：關係 gate 正確 STOP。Parent `3f693869-c263-4812-96c0-a6433d9be3af` 有 4 個 active target children，4 筆皆具有 `parent_event_id`：
  * `47262b02-d817-4c4b-a1b0-a5f3fae06cd2`
  * `7c6c1e7f-1693-4c94-b3f2-04067a997eee`
  * `a62ce9e1-ddc5-4fd7-8327-2c47f54fe0ec`
  * `fe47a25c-ec38-4f0d-be21-7d06607cbbb2`
* [x] PR review remediation：manifest no-replace publication、strict contract、target stable-field CAS、target-scoped relation read
* [x] PR review remediation：scope lookup fail closed、changed pending finding refresh、DB-derived admin event ID assertion
* [x] PR review remediation：non-transactional CLI `--apply` 在 manifest 或 DB access 前 STOP
* [x] Phase 6a focused validation：cleanup safety suite `36 passed`
* [x] Phase 7：更新 Google News RSS source history與本 spec 的 commits/tests/approval state
* [x] Rebase checkpoint：同步 `origin/main=9b2f6368`，behind `0`、merge commits `0`
* [x] Rebase validation：scope lifecycle `23 passed`、scope web `36 passed`、full scraper `606 passed, 1 skipped`
* [x] Rebase validation：i18n `1163` keys、JSON-LD security PASS、Next.js static pages `250/250`
* [x] 2026-10-22 第二次 rebase 到 `origin/main=4d02c5d0`（behind `0`、merge commits `0`）；migration 097 撞號改為 `098`；scraper `1112 passed, 1 skipped`、web scope tests `25 pass`、i18n `1169` keys、JSON-LD PASS。本機 `pnpm build` 在 compile 與 TypeScript 通過，prerender 因缺 Supabase 環境變數停止，完整 build 交由 PR 的 Vercel check

## Wave 2：明確延後

* [ ] 另立計畫評估 Google News RSS narrow guard
* [ ] 另立計畫評估 Big Romantic Records leg-level location filter
* [ ] 另立計畫評估 publisher domain risk 與 `startup_terrace`
* [ ] 另立計畫處理任何 `source_exclusions` 與 security/broken-link history routing

## Approval Gates

* [x] Phase 5 code delivery approval：使用者已要求同步最新 main、重驗、PR、merge 與 deploy
* [x] Phase 5 sync：feature commits 已 rebase 到 `origin/main=9b2f6368`，本地 linear history 驗證完成
* [x] Phase 5 push：發布新的 linear PR remote ref `feat/japan-scope-gate-linear`（PR #359），不 force push 舊 branch
* [x] Phase 5 PR：PR #359 的 required checks（Vercel build、eval、gitleaks）皆 pass
* [x] Phase 5 merge：2026-10-22 以 rebase merge 整合 main，exact merged SHA `b19a08e9`，main 歷史線性
* [ ] Phase 5 deploy：exact-SHA Vercel Production deployment 7249765880（`b19a08e9`）已 success；三筆 runtime canary 尚未執行
* [x] Phase 6b：建立 transactional DB RPC（migration 103，PR #413，2026-10-23 套用）、盤點 writers 並寫成 runbook（PR #418）；設計見 `plan.md`，追蹤 issue #385
* [x] Phase 6b：以 RPC 重新 capture immutable manifest（digest `f9f7238452330f4ccd4e2eff6af695183f57a2be9e6fe6ba3e55ed64515fb054`），並取得使用者針對該 digest 的 production apply 核准
* [x] Phase 6c：production apply 與 read-back（2026-10-23 15:21 JST，22 筆停用，`active` 2406 → 2384，`readback=ok`），經過程見 `notes.md`
* [x] Phase 6c 復驗（2026-10-24）：apply 後 `scraper.yml` 與 merger 跑過一輪，`--readback=ok`，22 筆 `updated_at` 仍停在 apply 當下，沒有被蓋回去；詳見 `notes.md`。公開網址 soft 404（HTTP 200）已於 2026-10-25 由 PR #438（`web/proxy.ts`）修正，production 22 筆回 404，issue #427 已關閉

## Changes Log

* `c098147a`：記錄 v3.1 preflight、baseline 與 isolated worktree
* `3c0639c3`：抽出 canonical location region classifier
* `bb614391`：新增 consumable annotator scope decision 與 report lifecycle
* `99303b6f`：新增 admin 逐筆 scope report action
* `51050092`：加強 scope report UI source guards
* `321a0859`：新增 digest-bound scope cleanup manifest 與 unit tests
* `442d4e5a`：記錄 Google News RSS scope incident
* `a18e1a49`：使 scope manifest publication 嚴格 immutable
* `fe66a9d2`：關閉 target-row CAS、relation query 與 scope report lifecycle races
* `cd4c2b04`：禁用 non-transactional production cleanup apply

Snapshot attempt：`tmp/scope_manifest_20260804T145452Z.json` 在寫入前 STOP，因此檔案不存在，digest unavailable。`--apply` NOT RUN，且目前由 CLI fail closed。

## Cleanup Safety Boundaries

* [x] 不執行 one-off `--apply` 或其他 production DB mutation
* [x] 不把 code delivery 核准解讀為 digest-bound production apply 核准
* [x] Transactional RPC 完成前，由 CLI 強制拒絕 non-transactional apply
* [x] 除 migration 098（admin confirm 原子 RPC，2026-10-22 已由使用者套用到 production 並 read-back 確認）外不新增 migration、不改 QA auto-consumer、不改 sub-event active contract
