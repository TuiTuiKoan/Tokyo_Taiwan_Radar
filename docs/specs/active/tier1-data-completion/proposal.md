---
slug: tier1-data-completion
title: Tier 1+1.5 資料基礎設施完成路徑（P4 缺口、location_prefectures、performer Tier 2）
status: active
branch: feat/tier1-data-completion
created: 2026-05-05
tags: [data, scraper, infra, backfill]
---

## What（做什麼）

把 Tier 1（migration 035-036）+ Tier 1.5（037-040）已建好的欄位群，**從「schema 完成」推到「填充率達商業可用門檻」**。本 spec 處理三個明確缺口：

1. **location_prefectures 嚴重缺口**（1.8% → 目標 ≥85%）—— Product C 城市維度阻斷點
2. **performer Tier 2 backfill**（17.7% → 目標 ≥45%，僅針對 lecture/performance/workshop 類）
3. **P4.1–4.4 缺口認領**（確認是否含蓋於 P3，或需另開 sub-issue）

## Why（為什麼）

- 商業化定位（見 `market-positioning-strategy`）已確認**中層 B2G/B2B 為 6 個月主要變現引擎**
- 中層所有產品（A/B/C）都依賴「city × category × organizer_type」三軸切片
- 目前 `location_prefectures` 僅 1.8% 填充率，**完全無法做城市維度切片**
- `performer` 17.7% 在通用情境可接受，但對「講座 / 表演」類事件是賣點欄位
- P4.1–4.4 的真實狀態未確認，可能是無效列表或真實未做工作

## Non-Goals（不做什麼）

- ❌ 不新增 schema 欄位（Tier 1+1.5 已完成；Tier 2 是另一個 spec）
- ❌ 不做 organizer_type i18n DB CHECK 對齊（拆到 `organizer-type-vocab-alignment` spec）
- ❌ 不修 GPT 對 location_prefectures 抽取的 prompt（先用 deterministic regex backfill，prompt 改善延後）
- ❌ 不對歷史 inactive 事件做 backfill（只處理 `is_active = true`）

## Design（設計摘要）

### 一、現況快照（2026-05-05）

```
total active annotated events: 164

✅ category               : 100.0%
✅ location_name          : 100.0%
✅ start_date             : 100.0%
✅ organizer              :  92.1%
✅ location_address       :  87.8%
✅ event_form             :  86.0%
⚠️  organizer_type (≠unk)  :  81.7%   ← 18 件 unknown，多為 organizer=null
❌ location_prefectures   :   1.8%   ← 阻斷 Product C
🟡 performer              :  17.7%   ← 一般可接受，但需 lecture/performance Tier 2
```

### 二、三組缺口的處理方案

#### Gap A：location_prefectures（最高優先）

**根因**：`backfill_location_prefectures.py` 只處理「父事件由子事件聚合」場景；
未處理「一般事件 location_address → prefecture」直接抽取。

**設計**：
- **A1**：擴展 `backfill_location_prefectures.py` 加 `--mode single` flag
  - 對 `is_active=true AND location_address IS NOT NULL AND (location_prefectures IS NULL OR location_prefectures = '[]')` 的事件
  - 用既有 `extract_prefecture()` regex
  - dry-run 驗證後實寫
- **A2**：把 `extract_prefecture()` 整合進 `annotator.py` 的 `update_data` 構造階段
  - 從 `location_address` 自動衍生 `location_prefectures`，若 GPT 沒回此欄位
  - 確保**未來新事件不再有此缺口**
- **A3**：對剩餘 20 件「有場地名無地址」事件
  - 不在本 spec 處理；由 `enrich_addresses.py` 既有流程逐步補

**預期效果**：
- 立即補 141 件（filled rate 1.8% → ~88%）
- 未來新事件自動填，不再退化

#### Gap B：performer Tier 2 backfill

**根因**：`_extract_performer_from_raw()` regex 設計保守（純漢字 2-6 字），
對「英文姓名 + 中文姓氏」「片假名外國名」「多人演出」覆蓋不足。

**設計**：
- **B1**：篩選候選池：`performer IS NULL AND event_form ∈ {lecture, performance, screening_with_talk, workshop, conference}`
  - 目前 44 件
- **B2**：用 GPT-4o-mini 對候選池逐筆 re-annotate（只 patch `performer` 欄位，其他欄位不動）
  - 成本估算：44 件 × $0.0015/件 ≈ $0.07
- **B3**：執行後對「明顯異常」(過長 / 含敬語 / 包含日期) 做 sanity check
- **B4**：通過驗證的 performer 寫入 `field_corrections` 鎖住，避免下次 annotator 覆蓋

**預期效果**：
- performer 17.7% → ~44%（覆蓋所有需要 performer 的類型）
- 不影響其他類型（市集、展覽不需 performer）

#### Gap C：P4.1–4.4 缺口認領

**現況**：用戶提供的進度表中 P4.5 / P4.6 已完成（commit `307591b` + `040`），
但 P4.1–4.4 標注為「⬜ 待確認」。Codebase 中無對應紀錄。

**設計**：
- **C1**：用戶 review 自身規劃文檔（聊天紀錄 / Notion / 私人筆記），確認 P4.1–4.4 的具體內容
- **C2**：對每項回答以下三選一：
  - (a) 已合併進 P3 修正 → 在 `architect/history.md` 加註「合併」
  - (b) 已不需要 → 在本 spec `notes.md` 加註「廢棄」
  - (c) 仍需做 → 拆為獨立 sub-task，加入本 spec Phase D
- **C3**：若 (c) 為主，新增 spec `feedback-loop-p4-residual` 獨立追蹤

### 三、檔案影響範圍

| 檔案 | 異動類型 |
|---|---|
| `scraper/backfill_location_prefectures.py` | 加 `--mode single` flag |
| `scraper/annotator.py` | `update_data` 加 prefecture fallback |
| `scraper/annotator.py` | 加 `--backfill-performer-tier2` flag |
| `scraper/main.py` | （無異動）|
| `web/lib/types.ts` | （無異動）|
| `.github/skills/agents/architect/SKILL.md` | 加 Tier 1 fill rate guard |

### 四、執行順序與依賴

```
Gap A1 (single-mode backfill) ──┐
                                ├──→ 驗證填充率 ≥85%
Gap A2 (annotator integration) ─┘
                                
Gap B1-B4 (performer Tier 2)  ──→ 驗證填充率 ≥45%

Gap C1-C3 (P4 認領)            ──→ 文件化結論
```

A 與 B 可並行（無依賴），C 為獨立行動項。

## References

- `docs/specs/active/market-positioning-strategy/`（戰略上層）
- `docs/specs/active/product-c-opportunity-radar/`（本 spec 解鎖的下游）
- `scraper/backfill_location_prefectures.py`
- `scraper/annotator.py`（`_extract_performer_from_raw` 函數）
- `.github/skills/agents/architect/history.md`（P 系列 commit 紀錄）
- 對話紀錄「商業化計劃進度總覽 2026-05-04」（用戶 2026-05-05 提供）
