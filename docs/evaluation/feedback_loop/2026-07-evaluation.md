# 閉環效能指標 — 2026-07
_Generated: 2026-07-01 11:43 JST_

## A1 — 重犯率（Recurrence Rate）
過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**146**

| source_name | field_name | count |
|---|---|---|
| google_news_rss | name_zh | 47 |
| peatix | category | 39 |
| taiwan_cultural_center | category | 32 |
| taiwan_festa | category | 24 |
| gguide_tv | category | 23 |
| taiwan_cultural_center | name_zh | 22 |
| note_creators | category | 19 |
| taiwanshi | name_zh | 16 |
| taiwanshi | name_en | 16 |
| google_news_rss | category | 14 |

## A2 — 保護命中率趨勢（Protect Hit Rate Trend）
| 期間 | Protect Hits | Annotated Events | 命中率 |
|---|---|---|---|
| 30d | 1092 | 0 | n/a |
| 60d | 1628 | 0 | n/a |
| 90d | 1628 | 0 | n/a |

## A3 — 首次正確率（First-Pass Accuracy）
過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：

| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |
|---|---|---|---|
| nagano_aioiza | 3 | 3 | 100.0% |
| nittai_toumonkai | 1 | 1 | 100.0% |
| morc_asagaya | 1 | 1 | 100.0% |
| tokyonow | 3 | 3 | 100.0% |
| tsutaya_portal | 2 | 2 | 100.0% |
| peatix | 13 | 13 | 100.0% |
| jposa_ja | 1 | 1 | 100.0% |
| taiwan_matsuri | 1 | 1 | 100.0% |
| theater_enya | 1 | 1 | 100.0% |
| go_taiwan | 2 | 2 | 100.0% |

## A4 — 修復延遲（Repair Latency）
過去 180 天 field_corrections.created_at − events.created_at 中位數（per source）：

| source_name | 修正次數 | 中位數（天） |
|---|---|---|
| taiwanbunkasai | 1 | 36.7 |
| manual | 1 | 25.3 |
| user_submission | 2 | 22.7 |
| mot | 2 | 18.7 |
| bigromanticrecords | 8 | 13.8 |

## 其他健檢指標（摘要）
- field_protect_hits (30d): 1092
- field_corrections (30d): 4013
- category_corrections (30d): 12
- selection_reason_corrections (30d): 0

## Researcher 健康度（30d）
過去 30 天 `research_sources` 各 status 計數（retrospective）：

| status | count |
|---|---|
| implemented | 0 |
| not-viable | 26 |
| candidate | 21 |
| researched | 0 |
| other | 0 |
| **total** | **47** |

通過率：**0.0%** （implemented / (implemented + not-viable)）

_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_
