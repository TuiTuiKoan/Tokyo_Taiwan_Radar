# 閉環效能指標 — 2026-05
_Generated: 2026-05-22 11:07 JST_

## A1 — 重犯率（Recurrence Rate）
過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**138**

| source_name | field_name | count |
|---|---|---|
| google_news_rss | name_zh | 50 |
| peatix | category | 39 |
| taiwan_cultural_center | category | 32 |
| taiwan_cultural_center | name_zh | 31 |
| taiwanshi | organizer_zh | 25 |
| taiwan_festa | category | 24 |
| gguide_tv | category | 23 |
| taiwan_cultural_center | name_en | 22 |
| taiwanshi | organizer_en | 21 |
| google_news_rss | name_en | 19 |

## A2 — 保護命中率趨勢（Protect Hit Rate Trend）
| 期間 | Protect Hits | Annotated Events | 命中率 |
|---|---|---|---|
| 30d | 227 | 0 | n/a |
| 60d | 227 | 0 | n/a |
| 90d | 227 | 0 | n/a |

## A3 — 首次正確率（First-Pass Accuracy）
過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：

| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |
|---|---|---|---|
| transit_store | 1 | 1 | 100.0% |
| taiwan_prism | 1 | 1 | 100.0% |
| mot | 1 | 1 | 100.0% |
| jinf | 1 | 1 | 100.0% |
| taiwan_kyokai | 1 | 1 | 100.0% |
| amayaza | 1 | 1 | 100.0% |
| placebymethod | 1 | 1 | 100.0% |
| asahiculture | 7 | 6 | 85.7% |
| hakusuisha | 5 | 4 | 80.0% |
| peatix | 13 | 9 | 69.2% |

## A4 — 修復延遲（Repair Latency）
過去 180 天 field_corrections.created_at − events.created_at 中位數（per source）：

| source_name | 修正次數 | 中位數（天） |
|---|---|---|
| peatix | 62 | 13.6 |
| taioan_dokyokai | 15 | 13.5 |
| taiwan_kyokai | 2 | 13.2 |
| zinbun_kyoto | 1 | 13.1 |
| eslite_spectrum | 2 | 11.9 |

## 其他健檢指標（摘要）
- field_protect_hits (30d): 227
- field_corrections (30d): 2336
- category_corrections (30d): 292
- selection_reason_corrections (30d): 2

## Researcher 健康度（30d）
過去 30 天 `research_sources` 各 status 計數（retrospective）：

| status | count |
|---|---|
| implemented | 133 |
| not-viable | 225 |
| candidate | 63 |
| researched | 13 |
| other | 0 |
| **total** | **434** |

通過率：**37.1%** （implemented / (implemented + not-viable)）

_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_
