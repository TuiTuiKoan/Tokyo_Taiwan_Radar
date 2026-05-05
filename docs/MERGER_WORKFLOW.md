---
title: Merger Workflow — 跨來源活動合併規則
description: merger.py 的四個 Pass 執行流程、Primary 選擇規則、SOURCE_PRIORITY 表、richness 評分與幂等性保證
ms.date: 2026-05-02
---

## 概覽

`scraper/merger.py` 在每日 CI 中於 `main.py` 之後、`annotator.py` 之前執行，
也可透過 `merger.yml` 的排程（JST 10:00 / 18:00 / 01:00）或 workflow_dispatch 手動觸發。

```text
main.py → merger.py → annotator.py → annotator.py --fix-reviewed
```

執行後的統計行格式：

```
Done: N pair(s)/orphan(s) merged (Pass 0+1+2+3).
```

---

## 執行流程：四個 Pass

### Pass 0 — Google News RSS 同來源去重

**目的**：同一活動可能透過不同文章 URL 多次入庫 google_news_rss（不同查詢或不同天）。
每篇文章的 `source_id` 為 URL hash，Pass 1 跳過同來源，所以需要獨立處理。

**查詢範圍**：所有 `is_active=True` 且 `source_name='google_news_rss'` 的事件，
**包含 `start_date=NULL`**（annotator 尚未標注日期的也納入）。

**配對條件**：`name_ja` 相似度 ≥ 0.85（正規化後比對）。

**Primary 選擇**（依序）：

1. `start_date` 非空 > `start_date` 為 NULL
2. 相同時：`raw_description` 較長者優先

---

### Pass 1 — 跨來源名稱相似度去重

**目的**：同一活動被 Peatix、iwafu、Connpass 等不同平台各自列出。

**查詢範圍**：所有 `is_active=True`、`start_date` 非空、`name_ja` 非空的非 sub 事件。

**配對條件**：

- 不同 `source_name`
- `name_ja` 正規化相似度 ≥ 0.85（`_SIMILARITY_THRESHOLD`）
- 相同 `start_date`（YYYY-MM-DD）

**`_normalize()` 說明**：

- 全形空白、半形空白全部去除
- 統一小寫
- `®` / `Ⓡ` → `(r)`
- 去除 iwafu 風格副標題 `－副標－`

**Primary 選擇**（依序）：

1. `SOURCE_PRIORITY` 數值較小（較高權威）者為 primary
2. 相同 priority → `_richness_score()` 較高者為 primary
3. 完全相同 → ev_a 優先（查詢順序）

#### Pass 1 — Works entity 跳過條件（migration 048+）

進入合併前，新增兩個 skip 條件，避免「同名但實為不同作品」或「同作品的不同戲院場次」被誤合併：

1. **不同 `work_id`**：若 ev_a 與 ev_b 的 `work_id` 都非空且互異 → skip，輸出
   `[Pass 1 SKIP] different work_id: <id_a> ↔ <id_b>`。
   此情境發生於兩筆 events 已被 admin 明確指派為不同作品（例：同名但不同年份的電影）。
2. **電影／表演藝術跨 venue**：若任一方 `category` 含 `movie` 或 `performing_arts`，
   且 `_location_overlap(location_name_a, location_name_b) = False` → skip，輸出
   `[Pass 1 SKIP] same-name movie/performing_arts at different venues — likely same work, different screening`。
   此情境發生於月老在新文芸坐 ↔ シネマート新宿 等跨戲院場次：兩筆都是真實 events，
   不應合併；正確的串接層是 `work_id`，由 admin 在 `/admin/works` 指派同一 Work。

兩種 skip 都僅輸出 log，不寫任何 candidates table（Phase E spec 範圍）。

---

### Pass 2 — 新聞稿 / 報導配對

**目的**：新聞來源（google_news_rss、prtimes、nhk_rss）的文章標題與活動名稱差異太大，
無法用名稱相似度配對，改用日期範圍 + 地點重疊。

**新聞來源（`_NEWS_SOURCES`）**：

```python
{"google_news_rss", "prtimes", "nhk_rss"}
```

**配對條件**：

- `news.start_date ∈ [official.start_date − 90天, official.end_date]`
  （90 天 lookback 涵蓋活動前的預告文章）
- `location_name` 有 ≥1 個共同 token（長度 ≥2 字元）

**Primary**：官方來源固定為 primary；新聞稿固定為 secondary。

---

### Pass 3 — 孤兒 sub-event 清理

**目的**：Pass 1/2 deactivate parent 後，其 sub-events 變成孤兒
（`is_active=True` 但 `parent is_active=False`）。

**執行流程**：

1. 找出所有 active sub 且 parent 已 inactive 的事件
2. 透過 `secondary_source_urls contains inactive_parent.source_url` 找出 primary parent
3. 若 primary parent 下有相似 sub（`name_ja` ≥0.85 + 相同 `start_date`）→ 合併
4. 找不到對應 sub → 直接 deactivate 孤兒

> ⚠️ **已知 Bug（2026-05-02，程式碼尚未修復）**：Pass 3 可能誤 deactivate 有效父事件（非由 Pass 1/2 合併造成的 inactive parent）的所有子活動。
> 已知受害父事件：`00ae1ea8`、`dfb490c8`（各有 sub-events 被誤殺，已手動還原）。
> **暫行緊急修復**：若發現子活動莫名消失，立即執行：
> ```sql
> UPDATE events SET is_active = true WHERE parent_event_id = '<parent_uuid>' AND is_active = false;
> ```
> **待修方向**：Pass 3 在步驟 4 執行前，應確認父事件的 `secondary_source_urls` 非空（即真正被 Pass 1/2 合併），才允許清除孤兒子活動。

**Primary 選擇**（和 Pass 1 相同）：

1. `SOURCE_PRIORITY` 數值較小
2. 相同時 → `_richness_score()` 較高者

---

## SOURCE_PRIORITY 表

數值越小 = 越高權威，配對時為 primary。

| 數值 | 來源 | 說明 |
|------|------|------|
| 1 | `taiwan_cultural_center` | 台灣文化中心（官方） |
| 2 | `taiwan_kyokai` | 台湾協会（官方） |
| 3 | `taioan_dokyokai` | 台湾同郷会（官方） |
| 4 | `koryu` | 交流協会（官方） |
| 5 | `taiwan_festival_tokyo` | 台湾フェスティバル東京（主辦方） |
| 6 | `taiwan_matsuri` | 台湾祭（主辦方） |
| 7 | `taiwanbunkasai` | 台湾文化祭（主辦方，高於聚合平台） |
| 8 | `peatix` | 售票平台（高可信度） |
| 9 | `connpass` | 技術活動平台 |
| 10 | `doorkeeper` | 活動平台 |
| 11 | `iwafu` | 聚合平台 |
| 12 | `arukikata` | 旅遊資訊平台 |
| 13 | `ide_jetro` | 研究機構 |
| 99 | （其他未列出） | 預設最低優先度 |

> 新增來源時，若該來源屬於「官方主辦方」級別，應加入此表並設定適當數值。

---

## _richness_score() 評分規則

當兩個事件的 `SOURCE_PRIORITY` 相同時，分數較高者為 primary。

| 欄位 | 分數 |
|------|------|
| `official_url` 有值 | +1 |
| `start_date` 非空 | +1 |
| `end_date` 非空 | +1 |
| `location_address` 有值（街道級地址） | +1 |
| `location_name` 有值（場館名稱） | +1 |
| `raw_description` 長度 | +1 / 每 200 字，最多 +5 |

**最高分**：10 分（5 個固定欄位 + 描述 5 分）。

---

## 合併行為

### 當 secondary 被合併時

1. `primary.secondary_source_urls` 加入 `secondary.source_url`（不重複）
2. `primary.raw_description` 追加 secondary 的描述（若不重複）
3. `primary.annotation_status` 設為 `pending`（僅首次合併）
4. `primary.official_url` 若空則從 secondary 複製
5. `secondary.is_active` 設為 `False`

### 幂等性保證

每次重新執行 merger 不會重複合併：

- 判斷 `secondary.source_url ∈ primary.secondary_source_urls`
- 若已存在 → 跳過 raw_description 合併和 `pending` 標記
- secondary 已 inactive → scraper 重新 upsert 時會回到 `is_active=True`，
  下次 merger 再次 deactivate（輕微重工但正確）

---

## 手動操作指引

### Dry-run（只偵測不寫入）

```bash
cd scraper && python merger.py --dry-run
```

### 正式執行

```bash
cd scraper && python merger.py
```

### 手動合併特定兩筆

```python
# primary_id = 保留的那筆
# secondary_id = 要隱藏的那筆
sb.table('events').update({
    'secondary_source_urls': new_urls,
    'raw_description': combined_desc,
    'annotation_status': 'pending',
}).eq('id', primary_id).execute()

sb.table('events').update({'is_active': False}).eq('id', secondary_id).execute()
```

### start_date 錯誤時

若 annotator 把文章發布日誤填為活動日，需 reset 後等待重新標注：

```python
sb.table('events').update({
    'start_date': None,
    'end_date': None,
    'annotation_status': 'pending',
}).eq('id', event_id).execute()
```

---

## CI 排程

| UTC | JST | 工作 |
|-----|-----|------|
| 00:00 | 09:00 | Daily Scraper（main.py → merger → annotator） |
| 01:00 | 10:00 | Run Merger（merger → annotator） |
| 09:00 | 18:00 | Run Merger（merger → annotator） |
| 16:00 | 01:00 | Run Merger（merger → annotator） |

---

## 常見問題

### 為什麼同一活動仍然顯示兩筆？

可能原因：

1. 兩筆來自相同 `source_name` → Pass 1 跳過（同來源去重由 Pass 0 處理，
   但 Pass 0 僅限 google_news_rss）
2. 名稱相似度 < 0.85 → 未達門檻（活動名稱差異太大）
3. `start_date` 不同 → Pass 1 不配對（日期分組不同）
4. 一筆 `start_date=NULL` → Pass 1 不處理（需 Pass 0 或手動）
5. merger 尚未跑（下次排程在 JST 10:00 / 18:00 / 01:00）

### 新聞稿沒有被合併到對應活動？

可能原因：

1. `news.start_date` 超出 `[official.start_date − 90天, official.end_date]`
   → annotator 誤用文章發布日，需 reset `start_date`
2. `location_name` 沒有重疊 token
   → 新聞只寫城市名（「東京」）而活動記錄寫場館名（「国立代々木競技場」）

### Pass 3 誤 deactivate 了正常的 sub？

若孤兒 sub 是合理的獨立活動（parent 被誤合併）：

1. 手動 `is_active=True` 恢復
2. 確認 parent 合併是否正確
3. 若 parent 合併錯誤，回滾方式：`is_active=True` 給被 deactivate 的 parent，
   並從另一個 parent 的 `secondary_source_urls` 移除該 URL
