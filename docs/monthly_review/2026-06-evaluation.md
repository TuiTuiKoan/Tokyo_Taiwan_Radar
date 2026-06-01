# 閉環效能指標 — 2026-06
_Generated: 2026-06-01 11:52 JST_

## A1 — 重犯率（Recurrence Rate）
過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**139**

| source_name | field_name | count |
|---|---|---|
| google_news_rss | name_zh | 47 |
| peatix | category | 39 |
| taiwan_cultural_center | category | 32 |
| taiwan_cultural_center | name_zh | 30 |
| taiwanshi | organizer_zh | 25 |
| taiwan_festa | category | 24 |
| gguide_tv | category | 23 |
| taiwanshi | organizer_en | 21 |
| note_creators | category | 19 |
| taiwanshi | name_zh | 16 |

## A2 — 保護命中率趨勢（Protect Hit Rate Trend）
| 期間 | Protect Hits | Annotated Events | 命中率 |
|---|---|---|---|
| 30d | 536 | 0 | n/a |
| 60d | 536 | 0 | n/a |
| 90d | 536 | 0 | n/a |

## A3 — 首次正確率（First-Pass Accuracy）
過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：

| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |
|---|---|---|---|
| amayaza | 2 | 2 | 100.0% |
| taiwan_prism | 1 | 1 | 100.0% |
| uplink_cinema | 1 | 1 | 100.0% |
| placebymethod | 1 | 1 | 100.0% |
| hakusuisha | 6 | 4 | 66.7% |
| jats | 2 | 1 | 50.0% |
| note_creators | 12 | 5 | 41.7% |
| peatix | 5 | 2 | 40.0% |
| matsumoto_cinema_select | 3 | 1 | 33.3% |
| asahiculture | 19 | 6 | 31.6% |

## A4 — 修復延遲（Repair Latency）
過去 180 天 field_corrections.created_at − events.created_at 中位數（per source）：

| source_name | 修正次數 | 中位數（天） |
|---|---|---|
| peatix | 66 | 13.5 |
| taioan_dokyokai | 15 | 13.5 |
| taiwan_kyokai | 2 | 13.2 |
| zinbun_kyoto | 1 | 13.1 |
| eslite_spectrum | 2 | 11.9 |

## 其他健檢指標（摘要）
- field_protect_hits (30d): 536
- field_corrections (30d): 2678
- category_corrections (30d): 160
- selection_reason_corrections (30d): 2

## Researcher 健康度（30d）
過去 30 天 `research_sources` 各 status 計數（retrospective）：

| status | count |
|---|---|
| implemented | 68 |
| not-viable | 176 |
| candidate | 84 |
| researched | 15 |
| other | 3 |
| **total** | **346** |

通過率：**27.9%** （implemented / (implemented + not-viable)）

_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_
