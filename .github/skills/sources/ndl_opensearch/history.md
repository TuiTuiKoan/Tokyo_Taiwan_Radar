# ndl_opensearch scraper 修訂歷史

## 2026-06-04 — publication venue placeholder sync

- publication 事件の `location_name` は占位文字を維持し、`[新刊出版]` の接頭辞は付けない。
- annotator 側の publication 分岐と source skill の記述を同期し、会場欄に販売案内の prefix が入る回帰を防ぐ。

## 2026-06-04 — publication placeholders locale sync

- 日本語 UI の既定占位文は `新刊のご購入は各販売チャネルでお願いします`。
- publication の占位文字は `location_name` / `location_address` / `business_hours` すべて locale ごとに一致させる。

## 2026-05-31 — 初版実装

- 新規スクレイパー（Publication Intel 計画 v3.1）
- 実装要点:
  - NDL OpenSearch API (RSS 2.0 + Dublin Core) を `xml.etree.ElementTree` で解析
  - `dcterms:issued` → `dc:date` → `pubDate` の優先度で発売日取得
  - 180 日 client-side 過去フィルタを実装（NDL ソートが日付順でないため必須）
  - `source_id` は `dc:identifier` 末尾数字列または `md5(link)[:12]`
  - `health_check.py` の `ZERO_EVENT_OK_SOURCES` に追加（台湾フィルタ後 0 件は正常）
