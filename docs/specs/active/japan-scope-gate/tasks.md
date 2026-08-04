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
* [x] Phase 2：新增 annotator scope contract、runtime validation、effective-location decision 與 report lifecycle
* [x] Phase 2：擴充 manual consumer eligibility tests
* [x] Phase 2：在 isolated worktree 更新 Architect Dead Instruction Guard 與 Baseline Snapshot Completeness Guard
* [x] Phase 2 checkpoint：imports OK，focused `21 passed`，regression `74 passed`，建立 atomic local commit
* [x] Phase 3：閉合 admin per-row confirm、bulk exclusion、history status 與 machine-note visibility
* [x] Phase 3：三語 i18n、指定 web tests `36 passed` 與 production build `250/250` static pages PASS
* [x] Phase 3 checkpoint：本 atomic web commit 收尾，三語 i18n diff `0 key deletion`
* [x] Phase 4（web）：指定四檔 tests `36 passed`，`pnpm build` PASS（`250/250` static pages）
* [x] Phase 4（scraper）：imports OK；Phase 1/2 具名 suites `95 passed`
* [x] Phase 6a：commit `94f17a33` 實作 one-off snapshot/apply safety interface；focused tests `32 passed`
* [x] Phase 6a：執行唯讀 snapshot attempt，22 個 prefix 唯一解析、evidence 與 active state 通過
* [ ] Phase 6a acceptance：關係 gate STOP。Parent `3f693869-c263-4812-96c0-a6433d9be3af` 有 4 個 active target children，4 筆皆具有 `parent_event_id`：
	* `47262b02-d817-4c4b-a1b0-a5f3fae06cd2`
	* `7c6c1e7f-1693-4c94-b3f2-04067a997eee`
	* `a62ce9e1-ddc5-4fd7-8327-2c47f54fe0ec`
	* `fe47a25c-ec38-4f0d-be21-7d06607cbbb2`
* [x] Phase 7：更新 Google News RSS source history與本 spec 的 commits/tests/approval state
* [x] Final checkpoint：本次 docs commit 完成後確認 tracked worktree clean；Changes Log 含 commits、validation 與 snapshot STOP 證據

## Wave 2：明確延後

* [ ] 另立計畫評估 Google News RSS narrow guard
* [ ] 另立計畫評估 Big Romantic Records leg-level location filter
* [ ] 另立計畫評估 publisher domain risk 與 `startup_terrace`
* [ ] 另立計畫處理任何 `source_exclusions` 與 security/broken-link history routing

## Approval Gates

* [ ] Phase 5：push、merge、deploy、exact-SHA workflow 與三筆 runtime canary，等待 Tester PASS 與使用者另行核准
* [ ] Phase 6b：`--apply` production DB mutation，等待成功 manifest 的 exact digest-bound 明確核准
* [ ] Phase 6c：production read-back，僅能在 Phase 6b 核准並完成後執行

## Changes Log

* `0495539e`：記錄 v3.1 preflight、baseline 與 isolated worktree
* `23072d8e`：抽出 canonical location region classifier
* `7f974490`：新增 consumable annotator scope decision 與 report lifecycle
* `5cc8f7b8`：新增 admin 逐筆 scope report action
* `6dfab75f`：加強 scope report UI source guards
* `94f17a33`：新增 digest-bound scope cleanup manifest 與 unit tests

Snapshot attempt：`tmp/scope_manifest_20260804T145452Z.json` 在寫入前 STOP，因此檔案不存在，digest unavailable。`--apply` NOT RUN。

## Prohibited This Round

* [x] 不執行 `git push`、merge、V-M-D、Vercel deploy 或 workflow dispatch
* [x] 不執行 one-off `--apply` 或其他 production DB mutation
* [x] 不新增 migration、不改 QA auto-consumer、不改 sub-event active contract
