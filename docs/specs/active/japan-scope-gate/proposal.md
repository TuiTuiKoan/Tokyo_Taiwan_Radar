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

## References

* `/memories/session/plan.md`
* `.copilot-tracking/research/subagents/2026-08-04/active-events-baseline-reconciliation.md`
* `scraper/annotator.py`
* `scraper/backfill_location_prefectures.py`
* `web/lib/reportActionsCore.ts`
* `web/components/AdminReportsTable.tsx`
