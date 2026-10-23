---
name: ndl_opensearch
description: NDL OpenSearch API scraper for Taiwan-related books (Publication Intel v3.1)
---

# ndl_opensearch Scraper

## 機能説明

- **来源名**: `ndl_opensearch`
- **URL**: `https://ndlsearch.ndl.go.jp/api/opensearch`
- **資料類型**: 国立国会図書館（NDL）蔵書データベースの台湾関連書誌（書籍・雑誌記事など。`mediatype` 指定なし）

NDL OpenSearch API に `title=台湾, cnt=100, from=<今日−90日>` でクエリし、書誌情報を取得する
（`scraper/sources/ndl_opensearch.py` の `_BASE_PARAMS`、`_LOOKBACK_DAYS = 90`）。

- `title=台湾` はシリーズ名・特集名にもヒットするため、台湾が主題でない記事（朝鮮半島有事、他国の投資動向など）が混入する。
  関連性は annotator が判定する（下記「関連性判定」）。

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
広い期間で検索すると、新刊が `_MAX_RESULTS=500` の外へ押し出される。

**対策**: server-side の `from=YYYY-MM-DD`（今日−90 日）で期間を絞る。短い `from=` 窓では NDL が
発売日降順に近い順で返すため、新刊が 500 件の窓に収まる。

### Active ビュー表示について

- `start_date` が 30 日以上前の書籍 → `is_active=true` のまま DB に残るが、ウェブサイトの「開催中」フィルタからは外れる（仕様どおり）
- 書籍は単日時間点であるため `end_date = start_date`（単日イベント扱い）

### ZERO_EVENT_OK 理由

90 日ウィンドウ内に台湾関連書誌が 0 件の日は正常（出版サイクルに依存）。

### 関連性判定と分類（2026-10-23，ndl-relevance-publication）

- annotator は pure publication に `RECORD_TYPE: publication` を付けて送り、prompt の `PUBLICATION RECORDS` 段落で
  「台湾が作品の主題か」を判定する。シリーズ名・特集名・掲載誌名だけの台湾は関連としない。
- 出版物専用の relevance gate は `PUBLICATION_RELEVANCE_GATE_ENABLED = False`（量測で G が N をほぼ除去しないため開かない）。
- 分類は作品の主題で選ぶ。pure publication では他の分類があれば `books_media` を除去し、
  `lecture` / `report` / `tv_program` のキーワード補完をしない。
- `title=台湾` を title-only ルール（R1）に絞る案は recall 門檻を満たさず不採用。
`health_check.py` の `ZERO_EVENT_OK_SOURCES` に登録済み。

## 特殊規則

- **純出版 invariant（exact-only）**: pure 判定は正規化後 `event_form == ["publication"]` のみ。`books_media`・source 名・title prefix では判定しない。
	intentional-null 七欄は `location_address` / `location_address_zh` / `location_address_en` / `business_hours` / `business_hours_zh` / `business_hours_en` / `location_prefectures` とし、empty sentinel で保護する。
	真實 DB 價格（`is_paid` / `price_info` / `price_amount`）は保持し、pure publication の UI / JSON-LD だけで隠す。価格欄、`location_name`、`location_url` は七欄の NULL / clear policy に含めない。`organizer`（publisher）は必須。
- **sync 規則**: 上記出版模板は `scraper/annotator.py::_PUBLICATION_SOURCES` の白名單と双方向同期する。出版來源を追加・削除する時は source SKILL と annotator 白名單を同一変更で更新する。
- **title prefix 規則**: publication の title prefix は locale-aware にする。`name_ja`/`name_zh` は `[新刊出版]`、`name_en` は `[New Release]`。期刊專文は `name_ja=[雑誌記事]`、`name_zh=[期刊專文]`、`name_en=[Periodical Article]` とし、`[期刊專文]` を日本語に流用しない。
- **mixed negative**: `['publication', 'lecture']` など physical form を含む rows は pure 扱いにしない。
- **null-byte strip 必須**: 全外部テキストに `.replace("\x00", "")` を適用
- **`tzinfo=timezone.utc`**: JST-aware datetime 禁止。`datetime(y, m, d, tzinfo=timezone.utc)` を使用
- `name_ja_locked = True`: 書名は NDL の確定値を保持する
- `organizer_type = ["government"]`: 出版社ではなく NDL 登録機関扱い

## 既知の問題

- **NDL ↔ hanmoto 重複**: 同一書籍が両ソースに登場する場合がある（既知の非バグ、少量の重複は許容）
- **発売日が年/月のみ**: `YYYY` や `YYYY-MM` 形式は 1 月 1 日 / 月初として UTC midnight に正規化
- **dc:identifier の形式**: URN・URL 混在。末尾 8 桁以上の数字列を抽出して stable ID とする
