# 閉環效能指標 — 2026-08
_Generated: 2026-08-01 11:02 JST_

## A1 — 重犯率（Recurrence Rate）
過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**149**

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
| 30d | 2732 | 0 | n/a |
| 60d | 3861 | 0 | n/a |
| 90d | 4397 | 0 | n/a |

## A3 — 首次正確率（First-Pass Accuracy）
過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：

| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |
|---|---|---|---|
| hankyu_hakata | 1 | 1 | 100.0% |
| cinemadict | 1 | 1 | 100.0% |
| doorkeeper | 2 | 2 | 100.0% |
| matsumoto_cinema_select | 2 | 2 | 100.0% |
| waseda_icl | 1 | 1 | 100.0% |
| wuext_waseda | 2 | 2 | 100.0% |
| eplus | 2 | 2 | 100.0% |
| taiwan_matsuri | 1 | 1 | 100.0% |
| hanshin_umeda | 1 | 1 | 100.0% |
| bigromanticrecords | 3 | 3 | 100.0% |

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
- field_protect_hits (30d): 2732
- field_corrections (30d): 1838
- category_corrections (30d): 3
- selection_reason_corrections (30d): 0

## Researcher 健康度（30d）
過去 30 天 `research_sources` 各 status 計數（retrospective）：

| status | count |
|---|---|
| implemented | 2 |
| not-viable | 62 |
| candidate | 36 |
| researched | 0 |
| other | 0 |
| **total** | **100** |

通過率：**3.1%** （implemented / (implemented + not-viable)）

_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_
