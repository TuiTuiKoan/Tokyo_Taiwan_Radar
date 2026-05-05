---
slug: merger-multi-signal-pass4
title: Merger Phase E — Multi-signal Pass 4 (跨來源去重)
status: active
branch: feat/merger-multi-signal-pass4
created: 2026-05-05
tags: [scraper, merger, deduplication]
---

## What（做什麼）

在 `scraper/merger.py` 新增一道 multi-signal Pass 4，處理目前 Pass 1（name similarity ≥ 0.85）與 Pass 2（name partial + location overlap）都接不到的跨來源重複事件。

判定 primary ↔ secondary 不再單靠 name 或 location 任一訊號，而是綜合多個 weak signal：

- **Date overlap**：`start_date` 在 ±7 天內（或 date range 有交集）
- **Prefecture match**：`location_prefectures` 至少一項相同
- **Organizer substring**：`organizer` 任一方為另一方的 substring（≥ 4 char），或同 token ≥ 50%
- **Keyword overlap**：`raw_description` 抽取關鍵字（活動名片段、地名、主辦方）≥ N 個共現
- **Source class**：候選 secondary 必須屬於 `_NEWS_SOURCES`（避免兩個官方來源誤合併）

需要至少 3 / 4 訊號命中才標記為候選對；命中後寫入 `scraper_runs.merger_candidates`，由人工 review 後再 promote 為 secondary URL（**不自動寫 `parent_event_id`**）。

## Why（為什麼）

- **痛點**：2026-05-05 確認 gnews `c1ba79b6`「イオン太田で台湾グルメと『台南ランタン祭』を楽しむイベント」無法與官方 `台湾祭in群馬太田2026－台南ランタン祭－` (iwafu/prtimes/walkerplus/taiwan_matsuri) 自動合併。已嘗試的修法都失效：
  - **Phase A** 把 `_location_overlap()` 加入 substring 分支：仍失敗，因 `イオン太田 ⊄ イオンモール太田`（`モール` 中間插入），且 `群馬県太田市 ⊄ イオンモール太田`。
  - **Pass 1 name similarity**：news outlet 改寫標題，與官方名相似度 < 0.20。
  - **Pass 2 location**：news 地址常只到 city/prefecture 等級，與 venue 名稱無 token / substring 重疊。
- **影響**：每月 5–10 件這類 case 需手動合併。資料品質頁的「duplicate suspects」清單長期堆積。
- **為什麼現在做**：Phase A–C（ship 於 commit `<待補>`）已把容易處理的 prefix/suffix-extension venue 案例清掉，剩下的尾端就是 middle-insertion + city-only-address，必須改用 multi-signal 才解得開。

## Non-Goals（不做什麼）

- **不做** 自動寫入 `parent_event_id` — Pass 4 永遠輸出「候選對」交人工審核，避免 false positive 污染主事件。
- **不引入** 日文 morphological tokenizer（MeCab/SudachiPy）— 過重，且 substring + prefecture 已足以涵蓋目標 case。
- **不改** Pass 0–3 的既有判定門檻 — Pass 4 是「補網」而非「替換」。
- **不處理** 同來源內的重複（仍由 Pass 0 negotiate）。
- **不處理** 跨語言事件名比對（中/英/日 mix）— 留給未來 Phase F。

## Design（設計摘要）

### 資料流

```
Pass 0 (within-source) → Pass 1 (name sim ≥0.85) → Pass 2 (name partial + location)
   → Pass 3 (orphan cleanup) → Pass 4 (multi-signal candidate flagging) ← 新增
```

### 訊號 scoring（簡化版）

```python
def _multi_signal_score(primary, secondary) -> float:
    score = 0
    # 必要前提：secondary 屬於 _NEWS_SOURCES
    if secondary["source_name"] not in _NEWS_SOURCES:
        return 0
    # 1. Date overlap (±7d)
    if _date_overlap(primary, secondary, days=7): score += 1
    # 2. Prefecture match
    if _prefecture_match(primary, secondary): score += 1
    # 3. Organizer substring (>=4 char) or token overlap
    if _organizer_match(primary, secondary): score += 1
    # 4. Keyword overlap in raw_description (>=2 shared 4-gram tokens)
    if _keyword_overlap(primary, secondary, min_shared=2): score += 1
    return score
```

判定規則：`score ≥ 3` 進入候選清單；`score == 4` 額外標記為「高信心」。

### 影響檔案

- `scraper/merger.py` — 新增 `_multi_signal_score()` + `Pass 4` 主迴圈
- `scraper/merger.py` — 新增 `_date_overlap()` / `_prefecture_match()` / `_organizer_match()` / `_keyword_overlap()` helpers
- `supabase/migrations/045_merger_candidates.sql`（新）— `merger_candidates` 表，欄位 `primary_event_id, secondary_event_id, score, signals(jsonb), reviewed_at, reviewed_by, decision`
- `web/app/admin/merger-candidates/page.tsx`（新）— 候選對審核 UI（approve / reject）
- `.github/agents/architect.agent.md` — 新增 `Merger Pass 4 Multi-Signal Guard`
- `.github/skills/agents/engineer/SKILL.md` — 新增 Pass 4 helper 規則段

### 風險與緩解

| 風險 | 緩解 |
|---|---|
| False positive 污染主事件 | 一律走人工 review，Pass 4 不直接寫 `parent_event_id` |
| organizer / raw_description 雜訊高 | 抽取前先 strip HTML、URL、標點；keyword 用 4-gram |
| `_NEWS_SOURCES` 之外的 weak source 漏接 | 後續 Phase F 再考慮；先確保 news source 的 case 100% 進候選 |

### Acceptance criteria

- [ ] gnews `c1ba79b6` 在 dry-run 中被標記為候選 secondary，primary 為 `taiwan_matsuri`/`iwafu` 的「台湾祭in群馬太田2026」事件
- [ ] 跑全量 dry-run，Pass 4 候選對數量 ≤ 30（避免 review queue 爆炸）
- [ ] 任一既有 Pass 1/2 命中對不被 Pass 4 覆寫
- [ ] False positive sample audit：隨機抽 10 對人工檢查，accuracy ≥ 80%

## References

- 觸發 incident：2026-05-05 「台湾祭in群馬太田2026」7 筆跨來源重複手動合併
- Phase A–C ship commit：（待 commit hash 補入）
- Architect Guard：`Merger _location_overlap() Substring Rule Guard` 第 3 點明示中間插入未解
- 相關 Architect Guard：`News Article Title Mismatch — Manual Merge Reminder`
- 上游 merger doc：[docs/MERGER_WORKFLOW.md](../../../MERGER_WORKFLOW.md)
