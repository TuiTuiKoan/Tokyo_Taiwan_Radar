---
slug: japan-scope-gate
title: Japan Scope Gate
description: Add a consumable non-Japan audience decision and a review-safe admin action path
status: active
branch: feat/japan-scope-gate-6b
created: 2026-08-04
updated: 2026-10-23
tags:
  - scraper
  - admin
  - data-quality
---

## What（做什麼）

建立 Japan→Taiwan 收錄範圍的可消費決策鏈。Annotator 以結構化欄位判斷活動受眾，再由 canonical location classifier 限定非日本地點，只建立人工複審 report。Admin 必須逐筆確認後才能停用事件。

## Why（為什麼）

現行 LOCATION GATE 要求模型在心中設定 `is_active=false`，但 JSON contract 與 writer 都沒有 consumer。Japan→Taiwan B2C、B2B 與其他境外活動因此可保持 active，且既有 admin queue 無法安全完成逐筆處置。

2026-08-04 的 v3.1 reconciliation 已把 daily pipeline 漂移解釋為 `1424 + 13 - 2 = 1435`，並建立完整 identity 與 pending-report baseline。本次執行以該 baseline fail closed。

## Design（設計摘要）

Wave 1 包含：

* 從 prefecture backfill 抽出無 DB 副作用的 canonical region classifier
* 在 annotator prompt、response contract、runtime validator 與 report consumer 間閉合 `scope_decision`
* 只對非日本地點且 decision 不是 `in_scope` 的事件建立 manual report
* 在 admin confirm path 加逐筆 acknowledgment、exact-one event update、machine notes 保全與 history routing
* 提供 22 筆已審核事件的 immutable snapshot/apply one-off interface，但本輪只執行唯讀 snapshot

Scope finding 不寫入 `events` 新欄位，也不自動停用事件。2026-10-22 rebase 時新增 migration `098_scope_report_transaction.sql`（原編號 097 與 main 撞號；`confirm_scope_report` RPC 與 machine token 的 RESTRICTIVE INSERT policy），必須由使用者先在 production 套用，再部署呼叫該 RPC 的 web code。`irrelevant` 是 actionable base type，`scopeReviewNonJapan` 與 `scopeDecision:`、`scopeRegion:`、`scopeHash:` 是人工處理 metadata。

## Non-Goals（不做什麼）

Wave 2 延後以下工作：

* Google News RSS 窄化 guard
* Big Romantic Records 場次級海外地點過濾
* Publisher domain risk、`startup_terrace` 存廢與任何 `source_exclusions`
* Security 或 broken-link history routing 改動

本輪除 migration 098（admin 單筆 confirm 的原子 RPC 與 report token provenance）外，不做其他 DB migration、QA consumer 改動或 sub-event active 行為改動；cleanup apply 所需的 transactional RPC 仍屬 Phase 6b。Code delivery 已進入 PR、merge 與 deploy 流程；production cleanup 仍是獨立工作流，不包含在 code delivery 核准內。

## Baseline（v3.1）

Capture window `2026-08-04T11:09:30.624644Z` 至 `2026-08-04T11:09:34.759722Z`：

* Active count before/paged/after：`1435 / 1435 / 1435`
* Sorted full UUID identity SHA-256：`bf6ed020c764acc1a0cc5690433c166c4d6b45867694a1528780bc6f1b4367d0`
* Parent/child：`1247 / 188`
* Annotated/reviewed：`1290 / 145`
* Pending reports：`181`，page lengths `[50, 50, 50, 31]`，181 unique IDs，0 empty `report_types`
* Payload tokens：11，分布為 `field:` 2、`fieldEdit:` 6、`selectionReason:` 3
* Base token set 與 Plan v3.1 完全一致

Phase 0.5 的現行 GPT raw JSON 沒有 `scope_decision`、`is_active` 或其他 scope output。正向 `selection_reason` 只描述 Taiwan relevance，沒有回答活動受眾，因此可繼續實作 structured consumer。

## Implementation Status（2026-08-06）

### Delivery branch

先前測試過的 branch 已發布至 `origin/feat/japan-scope-gate`，遠端 SHA 為 `28d01f25`。PR review 修正完成後，本地 branch 於 2026-08-06 重放到最新 `origin/main=9b2f6368`，結果為 behind `0`、merge commits `0`。下列 10 個 rebased code/history commits 位於本次文件更新之前。舊遠端 branch 未被 force push；PR 將使用新的 linear remote ref。

Rebased commits：

* `c098147a`：記錄 v3.1 preflight、baseline 與 isolated worktree
* `3c0639c3`：抽出 canonical location region classifier
* `bb614391`：新增 consumable annotator scope decision 與 report lifecycle
* `99303b6f`：新增 admin 逐筆 scope report action
* `51050092`：加強 scope report UI source guards
* `321a0859`：新增 digest-bound scope cleanup manifest
* `442d4e5a`：記錄 Google News RSS scope incident
* `a18e1a49`：使 scope manifest publication 嚴格 immutable
* `fe66a9d2`：關閉 target-row CAS、relation query 與 scope report lifecycle races
* `cd4c2b04`：在 transactional RPC 完成前禁用 non-transactional cleanup apply

### Validation

最新 main 上的本地驗證結果：

* Cleanup safety suite：`36 passed`
* Location classifier 與 scope lifecycle suites：`23 passed`
* Scope admin web suites：`36 passed`
* Full scraper suite：`606 passed, 1 skipped`，另有 14 個既有 `datetime.utcnow()` deprecation warnings
* Web i18n parity：三語各 `1163` keys
* JSON-LD security assertions：PASS
* Next.js production build：compile、TypeScript 與 static pages `250/250` PASS
* VS Code diagnostics：0
* `git diff --check`：PASS

### Cleanup Safety Boundary

Production 唯讀 snapshot 曾使用預定輸出路徑 `tmp/scope_manifest_20260804T145452Z.json`。22 個 prefix 均唯一解析為 full UUID，evidence assertions 通過，22 筆皆維持 active；關係 gate 隨後發現 parent `3f693869-c263-4812-96c0-a6433d9be3af` 有 4 個 active target children：

* `47262b02-d817-4c4b-a1b0-a5f3fae06cd2`
* `7c6c1e7f-1693-4c94-b3f2-04067a997eee`
* `a62ce9e1-ddc5-4fd7-8327-2c47f54fe0ec`
* `fe47a25c-ec38-4f0d-be21-7d06607cbbb2`

Snapshot 在寫檔前 STOP，因此該 path 不存在，也沒有 manifest digest。Review remediation 已把 target stable before-image 綁入每筆 CAS，並將 relation read 改為 target-scoped query；但 sequential PostgREST calls 無法原子保證 parent 與 children 在驗證後不漂移。Web maintenance lock 也不能阻擋 service-role scraper writers。

因此本版 CLI 在讀 manifest 或建立 Supabase client 前即拒絕 `--apply`。解除限制需要另一個 cleanup workstream：建立 service-role-only transaction/RPC，在單一 transaction 中驗證完整 before-images、parent/child relations 並更新整個 action set；同時 pause、drain、resume 所有 service-role writers。RPC 完成後仍須重新產生 immutable manifest，並以新 digest 取得當下的 production apply 明確核准。設計見 `plan.md`：cleanup 本身的原子性由 DB 表鎖加逐欄比對保證，pause／drain 只用於降低停用後被 in-flight 寫入者蓋回去的機率（2026-10-23 使用者決定）。

目前沒有 production DB mutation。Code PR、merge 與 deploy 不構成 cleanup apply 核准，spec 維持 active。

## References

* `/memories/session/plan.md`
* `.copilot-tracking/research/subagents/2026-08-04/active-events-baseline-reconciliation.md`
* `scraper/annotator.py`
* `scraper/backfill_location_prefectures.py`
* `web/lib/reportActionsCore.ts`
* `web/components/AdminReportsTable.tsx`
