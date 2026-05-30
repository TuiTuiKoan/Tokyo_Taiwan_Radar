# ndl_opensearch scraper 修訂歷史

## 2026-05-31 — 初版実装

- 新規スクレイパー（Publication Intel 計画 v3.1）
- 実装要点:
  - NDL OpenSearch API (RSS 2.0 + Dublin Core) を `xml.etree.ElementTree` で解析
  - `dcterms:issued` → `dc:date` → `pubDate` の優先度で発売日取得
  - 180 日 client-side 過去フィルタを実装（NDL ソートが日付順でないため必須）
  - `source_id` は `dc:identifier` 末尾数字列または `md5(link)[:12]`
  - `health_check.py` の `ZERO_EVENT_OK_SOURCES` に追加（台湾フィルタ後 0 件は正常）
