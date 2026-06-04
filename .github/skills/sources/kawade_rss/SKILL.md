---
name: kawade_rss
description: 河出書房新社 RDF/RSS 1.0 scraper for Taiwan-related books and events (Publication Intel v3.1)
---

# kawade_rss Scraper

## 機能説明

- **来源名**: `kawade_rss`
- **URL**: `https://www.kawade.co.jp/np/rss/index.rdf`
- **資料類型**: 河出書房新社の新刊書籍・著者イベント（RDF/RSS 1.0）

河出書房新社の公式 RDF フィードから新刊書籍情報とイベント告知を取得する。

## 技術規格

| 項目 | 詳細 |
|------|------|
| プロトコル | HTTP GET / RDF/RSS 1.0 |
| Namespace | `rss: http://purl.org/rss/1.0/` / `dc: http://purl.org/dc/elements/1.1/` |
| Pagination | なし（全件フィード）|
| `source_id` 形式 | `kawade_{md5(link)[:12]}` |
| 発売日フィールド | `dc:date`（ISO 8601 形式）|
| カテゴリ分流 | タイトルが `【イベント】` で始まる場合 `["books_media", "lecture"]`、それ以外 `["books_media"]` |

## RDF/RSS 1.0 パース注意

RDF/RSS 1.0 は `<item>` が `<rdf:RDF>` の直接子要素（`<channel>` 配下ではない）。
`{http://purl.org/rss/1.0/}item` で直接 `root.findall()` する。

```python
items = root.findall("{http://purl.org/rss/1.0/}item")
```

フィードによっては名前空間が省略される場合があるため `root.findall("item")` でフォールバック。

## 来源分流説明

### 未来発売日を含む

フィードには**未来の発売予定書籍**も含まれる。`start_date` が未来日付の場合、
ウェブサイトの「近日開催」セクションに表示される（正常動作）。

### ZERO_EVENT_OK 理由

台湾関連書籍の出版サイクルによって 0 件になる期間がある（nhk_rss と同性質）。
`health_check.py` の `ZERO_EVENT_OK_SOURCES` に登録済み。

### NHK RSS との類似性

運用上 nhk_rss と同じ性質（散発的なマッチ、空振り期間あり）。

## 特殊規則

- **出版事件欄位模板**: 書籍系は `location_name` / `location_address` / `business_hours` を locale に合わせた占位文字で維持し、日本語 UI では `新刊のご購入は各販売チャネルでお願いします` を使う。`location_name_zh` / `location_name_en`、`location_address_zh` / `location_address_en`、`business_hours_zh` / `business_hours_en` を必ず同時に埋める。`performer` は作者、`organizer` は出版社名、`organizer_url` は出版社ホームページ、`official_url` は書籍公式詳細ページ、`event_form = ["publication"]` を基本とする。著者イベントは内容に応じて別途 lecture 分流する。
- **sync 規則**: 書籍系 publication 分流は `scraper/annotator.py::_PUBLICATION_SOURCES` の白名單と双方向同期する。kawade_rss の書籍系扱いを変える時は source SKILL と annotator を同一変更で揃える。
- **null-byte strip 必須**: 全外部テキストに `.replace("\x00", "")` を適用
- **`tzinfo=timezone.utc`**: `datetime(y, m, d, tzinfo=timezone.utc)` を使用
- `name_ja_locked = True`
- `organizer = "河出書房新社"` 固定（`organizer_type = ["media"]`）

## 既知の問題

- **NDL ↔ kawade_rss 重複**: NDL にも同一書籍が登録されている場合がある（許容）
