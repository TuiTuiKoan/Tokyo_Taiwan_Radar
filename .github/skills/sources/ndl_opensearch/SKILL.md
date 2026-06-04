---
name: ndl_opensearch
description: NDL OpenSearch API scraper for Taiwan-related books (Publication Intel v3.1)
---

# ndl_opensearch Scraper

## 機能説明

- **来源名**: `ndl_opensearch`
- **URL**: `https://ndlsearch.ndl.go.jp/api/opensearch`
- **資料類型**: 国立国会図書館（NDL）蔵書データベースの台湾関連書籍（mediatype=1）

NDL OpenSearch API に `q=台湾, mediatype=1, cnt=100` でクエリし、書籍書誌情報を取得する。

## 技術規格

| 項目 | 詳細 |
|------|------|
| プロトコル | HTTP GET / RSS 2.0 with Dublin Core namespaces |
| Namespace | `dc: http://purl.org/dc/elements/1.1/` / `dcterms: http://purl.org/dc/terms/` |
| Pagination | `&idx=` (1-based offset), 100件/ページ, 最大 500 件 |
| `source_id` 形式 | `ndl_{dc:identifier の末尾数字}` または `ndl_{md5(link)[:12]}` |
| 発売日フィールド | `dcterms:issued` → `dc:date` → `pubDate`（優先度順） |
| 発売日形式 | `YYYY`, `YYYY-MM`, `YYYY-MM-DD` いずれも対応 |

## 来源分流説明

### ⚠️ NDL は発売日降順ソートではない

NDL OpenSearch のデフォルトソートは**相関度 / 書誌 ID** であり、発売日降順ではない。
このため、古い書籍が先頭ページに登場することがある。

**対策**: 180 日 client-side フィルタを必ず実施（`cutoff = date.today() - timedelta(days=180)`）。
Server-side の日付フィルタは NDL API が提供していないため省略できない。

### Active ビュー表示について

- `start_date` が 30 日以上前の書籍 → `is_active=true` のまま DB に残るが、ウェブサイトの「開催中」フィルタからは外れる（仕様どおり）
- 書籍は単日時間点であるため `end_date = start_date`（単日イベント扱い）

### ZERO_EVENT_OK 理由

180 日ウィンドウ内に台湾関連書籍が 0 件の日は正常（出版サイクルに依存）。
`health_check.py` の `ZERO_EVENT_OK_SOURCES` に登録済み。

## 特殊規則

- **出版事件欄位模板**: `location_name` / `location_address` / `business_hours` / `price_info` 統一填 `新書購買請洽各通路`，`performer` 填作者，`organizer` 視為出版社，`event_form = ["publication"]`。
- **sync 規則**: 上記出版模板は `scraper/annotator.py::_PUBLICATION_SOURCES` の白名單と双方向同期する。出版來源を追加・削除する時は source SKILL と annotator 白名單を同一変更で更新する。
- **null-byte strip 必須**: 全外部テキストに `.replace("\x00", "")` を適用
- **`tzinfo=timezone.utc`**: JST-aware datetime 禁止。`datetime(y, m, d, tzinfo=timezone.utc)` を使用
- `name_ja_locked = True`: 書名は NDL の確定値を保持する
- `organizer_type = ["government"]`: 出版社ではなく NDL 登録機関扱い

## 既知の問題

- **NDL ↔ hanmoto 重複**: 同一書籍が両ソースに登場する場合がある（既知の非バグ、少量の重複は許容）
- **発売日が年/月のみ**: `YYYY` や `YYYY-MM` 形式は 1 月 1 日 / 月初として UTC midnight に正規化
- **dc:identifier の形式**: URN・URL 混在。末尾 8 桁以上の数字列を抽出して stable ID とする
