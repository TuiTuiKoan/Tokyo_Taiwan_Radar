# ndl_opensearch scraper 修訂歷史

## 2026-10-23 — ndl-relevance-publication（relevance gate 靜默失效、出版物分類）

- **教訓**：annotator 的 Taiwan relevance gate（2026-10-12 上線）在 `field_corrections` 有任何列時跳過。
  ndl／hanmoto 寫入時就帶 `PUBLICATION_NULL_FIELDS` 的 7 個空 sentinel，gate 對出版物一次都沒生效（ndl 停用數 0），
  沒有錯誤也沒有日誌。改為 `_publication_gate_eligible()`：恰好 7 個空 sentinel、`annotated_at` 為空、FC 載入成功才進 gate，
  並回傳原因代碼；旗標 `PUBLICATION_RELEVANCE_GATE_ENABLED` 維持關閉。
- 出版物送 annotator 時加 `RECORD_TYPE: publication`；prompt 新增 `PUBLICATION RECORDS` 判準與欄位規則（凍結 cand6，SHA `b722d4b8…`）。
- 分類：pure publication 有其他分類時移除 `books_media`；不補 `lecture`／`report`／`tv_program`。盲測 40 筆 N 6 vs 現行 27。
- R1（只看標題）丟掉 P_seal 8 筆 R，未通過 recall 門檻，scraper 查詢不改。
- SKILL.md 修正過期內容：查詢是 `title=台湾`＋server-side 90 日 `from=`，不是 `q=台湾`／`mediatype=1`／180 日 client 過濾。

## 2026-07-11 — publication phase 3 invariant sync

- pure publication 判定改為 exact `event_form=['publication']`，不再依賴 category/source/title。
- 純出版 rows 對齊 `PUBLICATION_NULL_FIELDS` 七欄與 empty sentinel；真實 DB 價格保留，只在 pure publication UI / JSON-LD 隱藏。
- publisher/organizer 保持必填；mixed rows（含 lecture/workshop）明確保留 physical 行為。

## 2026-06-04 — publication venue placeholder sync

- publication 事件の `location_name` は占位文字を維持し、`[新刊出版]` の接頭辞は付けない。
- annotator 側の publication 分岐と source skill の記述を同期し、会場欄に販売案内の prefix が入る回帰を防ぐ。

## 2026-06-07 — publication title prefix locale sync

- publication title prefix は `name_ja`/`name_zh` = `[新刊出版]`、`name_en` = `[New Release]` に統一。
- periodical article は `name_ja=[雑誌記事]`、`name_zh=[期刊專文]`、`name_en=[Periodical Article]` に変更し、`[期刊專文]` を日本語へ流用しない。

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
