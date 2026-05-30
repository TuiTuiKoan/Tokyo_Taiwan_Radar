# kawade_rss scraper 修訂歷史

## 2026-05-31 — 初版実装

- 新規スクレイパー（Publication Intel 計画 v3.1）
- 実装要点:
  - 河出書房新社 RDF/RSS 1.0 フィードを `xml.etree.ElementTree` で解析
  - Clark notation `{http://purl.org/rss/1.0/}item` で直接 item 取得
  - `dc:date` から UTC midnight の `start_date` / `end_date` を生成
  - `【イベント】` prefix でカテゴリを `["books_media", "lecture"]` に分流
  - `health_check.py` の `ZERO_EVENT_OK_SOURCES` に追加
