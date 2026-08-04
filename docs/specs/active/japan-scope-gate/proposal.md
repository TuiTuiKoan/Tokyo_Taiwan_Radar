---
slug: japan-scope-gate
title: Japan Scope Gate
description: Add a consumable non-Japan audience decision and a review-safe admin action path
status: active
branch: feat/japan-scope-gate
created: 2026-08-04
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

Scope finding 不寫入 `events` 新欄位，不新增 migration，也不自動停用事件。`irrelevant` 是 actionable base type，`scopeReviewNonJapan` 與 `scopeDecision:`、`scopeRegion:`、`scopeHash:` 是人工處理 metadata。

## Non-Goals（不做什麼）

Wave 2 延後以下工作：

* Google News RSS 窄化 guard
* Big Romantic Records 場次級海外地點過濾
* Publisher domain risk、`startup_terrace` 存廢與任何 `source_exclusions`
* Security 或 broken-link history routing 改動

本輪也不做 DB migration、QA consumer 改動、sub-event active 行為改動、production apply、push、merge或部署。

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

## Implementation Status（2026-08-04）

目前分支的 commit 與本地實測紀錄如下。這些結果不是 push、merge 或 deploy 證據：

* Phase 0 commit `0495539e` 記錄 v3.1 preflight、baseline 與 isolated worktree
* Phase 1 commit `23072d8e` 抽出 canonical location classifier，focused tests `15 passed`
* Phase 2 commit `7f974490` 閉合 annotator scope contract，imports OK、focused tests `21 passed`、regressions `74 passed`
* Phase 3 commits `5cc8f7b8` 與 `6dfab75f` 閉合 admin 逐筆處理及 UI source guards，四個 web test files `36 passed`
* Phase 4 web build 完成 `250/250` static pages；Phase 1/2 scraper 具名 suites 重跑結果為 `95 passed`

Phase 6a code commit `94f17a33` 新增 digest-bound one-off 與 32 個 focused unit tests。`py_compile`、CLI help、imports、`get_errors` 與 `git diff --check` 均通過。

Production 唯讀 snapshot 使用預定輸出路徑 `tmp/scope_manifest_20260804T145452Z.json`。22 個 prefix 均唯一解析為 full UUID，evidence assertions 通過，22 筆皆維持 active；關係 gate 隨後發現 parent `3f693869-c263-4812-96c0-a6433d9be3af` 有以下 4 個 active children，而這 4 筆也都在 target set 且具有 `parent_event_id`：

* `47262b02-d817-4c4b-a1b0-a5f3fae06cd2`
* `7c6c1e7f-1693-4c94-b3f2-04067a997eee`
* `a62ce9e1-ddc5-4fd7-8327-2c47f54fe0ec`
* `fe47a25c-ec38-4f0d-be21-7d06607cbbb2`

Snapshot 在寫檔前 STOP，預定 path 不存在，沒有 manifest digest。Phase 5、Phase 6b 與 Phase 6c 仍 pending；Phase 6b 仍需一份成功產生的 immutable manifest 及引用其 exact digest 的明確核准。`--apply` 未執行，沒有 push、merge 或 deploy，spec 維持 active。

## References

* `/memories/session/plan.md`
* `.copilot-tracking/research/subagents/2026-08-04/active-events-baseline-reconciliation.md`
* `scraper/annotator.py`
* `scraper/backfill_location_prefectures.py`
* `web/lib/reportActionsCore.ts`
* `web/components/AdminReportsTable.tsx`
