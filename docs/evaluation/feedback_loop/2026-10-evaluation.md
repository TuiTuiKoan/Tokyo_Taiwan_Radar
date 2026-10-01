# 閉環效能指標 — 2026-10
_Generated: 2026-10-01 11:43 JST_

## A1 — 重犯率（Recurrence Rate）
過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**76**

| source_name | field_name | count |
|---|---|---|
| ndl_opensearch | location_address | 57 |
| ndl_opensearch | location_address_zh | 55 |
| ndl_opensearch | location_address_en | 55 |
| ndl_opensearch | business_hours | 55 |
| ndl_opensearch | business_hours_zh | 54 |
| ndl_opensearch | business_hours_en | 54 |
| ndl_opensearch | location_prefectures | 54 |
| gguide_tv | location_name | 42 |
| ndl_opensearch | organizer | 29 |
| ndl_opensearch | performers | 21 |

## A2 — 保護命中率趨勢（Protect Hit Rate Trend）
| 期間 | Protect Hits | Annotated Events | 命中率 |
|---|---|---|---|
| 30d | 3515 | 775 | 453.55% |
| 60d | 9666 | 2179 | 443.60% |
| 90d | 12545 | 3072 | 408.37% |

## A3 — 首次正確率（First-Pass Accuracy）
過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：

| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |
|---|---|---|---|
| ndl_opensearch | 40 | 40 | 100.0% |
| nagano_aioiza | 1 | 1 | 100.0% |
| hanmoto | 2 | 2 | 100.0% |
| ciema | 6 | 6 | 100.0% |
| uedaeigeki | 5 | 5 | 100.0% |
| tsudoi_osaka | 1 | 1 | 100.0% |
| cinemadict | 1 | 1 | 100.0% |
| kokuchpro | 2 | 2 | 100.0% |
| eplus | 1 | 1 | 100.0% |
| koryu | 1 | 1 | 100.0% |

## A4 — 修復延遲（Repair Latency）
過去 180 天 field_corrections.created_at − events.created_at 中位數（per source）：

| source_name | 修正次數 | 中位數（天） |
|---|---|---|
| hanmoto | 2 | 52.4 |
| taiwanbunkasai | 1 | 36.7 |
| manual | 1 | 25.3 |
| user_submission | 2 | 22.7 |
| mot | 2 | 18.7 |

## 其他健檢指標（摘要）
- field_protect_hits (30d): 3515
- field_corrections (30d): 698
- category_corrections (30d): 0
- selection_reason_corrections (30d): 0

## Researcher 健康度（30d）
過去 30 天 `research_sources` 各 status 計數（retrospective）：

| status | count |
|---|---|
| implemented | 0 |
| not-viable | 0 |
| candidate | 0 |
| researched | 0 |
| other | 0 |
| **total** | **0** |

通過率：**n/a** （implemented / (implemented + not-viable)）

_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_
