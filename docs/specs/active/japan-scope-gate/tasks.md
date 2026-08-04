---
title: Japan Scope Gate Tasks
description: Wave 1 delivery checklist and approval boundaries for the Japan scope gate
status: active
updated: 2026-08-04
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
* [ ] Phase 2：新增 annotator scope contract、runtime validation、effective-location decision 與 report lifecycle
* [ ] Phase 2：擴充 manual consumer eligibility tests
* [ ] Phase 2：在 isolated worktree 更新 Architect Dead Instruction Guard 與 Baseline Snapshot Completeness Guard
* [ ] Phase 2 checkpoint：focused/regression scraper tests PASS，建立 atomic local commit
* [ ] Phase 3：閉合 admin per-row confirm、bulk exclusion、history status 與 machine-note visibility
* [ ] Phase 3：三語 i18n、core behavior tests 與 AST/source assertions PASS
* [ ] Phase 3 checkpoint：建立 atomic local web commit，確認 i18n diff 沒有 key removal
* [ ] Phase 4：imports、具名 scraper tests、`pnpm build` 與具名 web tests 全部 PASS
* [ ] Phase 6a：實作 one-off snapshot/apply safety interface與 unit tests
* [ ] Phase 6a：只執行 immutable `--snapshot`，確認 22 筆唯一解析且無 parent/child 牽連
* [ ] Phase 7：更新 Google News RSS source history與本 spec 的 commits/tests/approval state
* [ ] Final checkpoint：worktree clean，Changes Log 含每個 commit SHA、validation、manifest path/digest

## Wave 2：明確延後

* [ ] 另立計畫評估 Google News RSS narrow guard
* [ ] 另立計畫評估 Big Romantic Records leg-level location filter
* [ ] 另立計畫評估 publisher domain risk 與 `startup_terrace`
* [ ] 另立計畫處理任何 `source_exclusions` 與 security/broken-link history routing

## Approval Gates

* [ ] Phase 5：push、merge、deploy、exact-SHA workflow 與三筆 runtime canary，等待 Tester PASS 與使用者另行核准
* [ ] Phase 6b：`--apply` production DB mutation，等待 manifest digest-bound 明確核准
* [ ] Phase 6c：production read-back，僅能在 Phase 6b 核准並完成後執行

## Prohibited This Round

* [x] 不執行 `git push`、merge、V-M-D、Vercel deploy 或 workflow dispatch
* [x] 不執行 one-off `--apply` 或其他 production DB mutation
* [x] 不新增 migration、不改 QA auto-consumer、不改 sub-event active contract
