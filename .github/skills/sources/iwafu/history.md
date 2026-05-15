# iwafu Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-05-15 — location_address 取得できない根本原因修正（commit `ebe54b3`）

**問題：** iwafu イベントの `location_address` が多くの場合 NULL になる。正確な住所が公式サイトにあっても抽出できない。

**根因 A（regex 過狭）：** `_ADDR_RE` が都道府縣（`東京都|北海道|…|.{2,5}県`）をプレフィックスとして必須にしていたため、市区町村から始まる住所（例: `渋谷区〇〇1-2-3`）がマッチしなかった。

**根因 B（フォールバック欠如）：** `main_text`（iwafu ページ本文）のみを検索していた。`_fetch_official_organizer_info()` が公式サイトの body text を返していなかったため、公式サイトにある住所を二次検索できなかった。

**修正（commit `ebe54b3`）：**
- `_ADDR_RE` を改訂：都道府縣は optional、`[市区町村]` suffix を必須 anchor に変更
- `_fetch_official_organizer_info()` の戻り値を 3-tuple に拡張：`(organizer, supplemental_text, body_text)`
- 主流程で `main_text` を優先検索し、ヒットしない場合のみ `official_body_text` をフォールバック検索

**教訓：**
- 日本の住所 regex では都道府縣を optional にする。`[市区町村]` suffix が唯一の信頼できる anchor。
- 公式サイトのテキストは住所の最も信頼できるソース。`official_url` を fetch する際は body text も保存しておく。
- 関数の戻り値型を変更（tuple 長追加）した場合は即座に全呼び出し元を更新し、`py_compile` で smoke-test する。
