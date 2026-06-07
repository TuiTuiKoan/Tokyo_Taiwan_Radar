---
name: hanmoto
description: 版元ドットコム Playwright scraper for Taiwan-related books (Publication Intel v3.1)
---

# hanmoto Scraper

## 機能説明

- **来源名**: `hanmoto`
- **URL**: `https://www.hanmoto.com/bd/search/keyword/台湾/sdate_desc`
- **資料類型**: 版元ドットコムの台湾関連書籍（発売日降順検索）

版元ドットコムは日本出版社の統合書誌データベース。`keyword=台湾` + `sdate_desc`（発売日降順）で台湾関連書籍を最大 3 ページ取得する。

## 技術規格

| 項目 | 詳細 |
|------|------|
| エンジン | Playwright Chromium (headless=True) |
| ページング | `/order/desc/offset/{offset}`（20件/ページ、最大 3 ページ）|
| カード selector | `div.booklist-item` → `ul.bookList > li` → `div.list-item` → `.booklist .item`（優先度順）|
| `source_id` 形式 | `hanmoto_{isbn13}` または `hanmoto_{md5(detail_url)[:12]}` |
| ISBN 取得 | `data-isbn` 属性 → href パスの `/isbn/{13桁}` 部分 |
| 発売日形式 | `YYYY年MM月DD日` または `YYYY-MM-DD` |

## selector 多段フォールバック

hanmoto.com のマークアップは変更されることがあるため、カード検出に複数 selector を試みる仕様。
ページに表示されるカード数が `_PAGE_SIZE(=20)` 未満の場合はページング終了。

```python
_CARD_SELECTORS = [
    "div.booklist-item",
    "ul.bookList > li",
    "div.list-item",
    ".booklist .item",
]
```

実際の selector が変わった場合: `SKILL.md` の `_CARD_SELECTORS` を更新し `history.md` に記録する。

## 来源分流説明

### sdate_desc ソート

hanmoto は発売日降順でソートされるため、最初のページに最新書籍が並ぶ。
過去書籍は 3 ページ（60 件）を超えると自然にフォールオフする（アーカイブ挙動）。
`start_date` が過去日付の書籍は Active ビューから外れるが `is_active=true` は維持される（仕様どおり）。

### server-side 台湾フィルタ

版元ドットコムは `keyword=台湾` でサーバー側フィルタを実施済みだが、
server 側のフィルタが崩れた場合に備えて client-side フィルタも必ず実施する。

### ZERO_EVENT_OK について

hanmoto は server-side で台湾検索済みのため、0 件は異常（scraper 不具合の可能性）。
`ZERO_EVENT_OK_SOURCES` には **追加しない**。

## 特殊規則

- **出版事件欄位模板**: `location_name` / `location_address` / `business_hours` は占位文字を locale に合わせて維持する。日本語 UI では `新刊のご購入は各販売チャネルでお願いします` を使い、`location_name_zh` / `location_name_en`、`location_address_zh` / `location_address_en`、`business_hours_zh` / `business_hours_en` を必ず同時に埋める。`performer` は作者、`organizer` は出版社名、`organizer_url` は出版社公式サイト、`official_url` は書籍の公式詳細ページ、`event_form = ["publication"]`。
- **date fallback**: hanmoto の日付抽出は `発売日 > 登録日` の順でフォールバックする。
- **sync 規則**: 上記出版模板は `scraper/annotator.py::_PUBLICATION_SOURCES` の白名單と双方向同期する。hanmoto を出版來源として扱う規則は source SKILL と annotator の両方を同時に更新する。
- **null-byte strip 必須**
- **`tzinfo=timezone.utc`**: `datetime(y, m, d, tzinfo=timezone.utc)` を使用
- `name_ja_locked = True`
- `organizer_type = ["media"]` 固定（各書籍の出版社名は `organizer` フィールドに格納）
- **BeautifulSoup 詳細解読**: 詳細ページの巡回は Playwright `new_page()` を使わず、極めて軽量な `requests` + `BeautifulSoup` (`_scrape_hanmoto_detail`) を用いて行う。
- **書籍メタデータ解析要件**:
  - `raw_description`: `.book-kaisetsu-section` (内容紹介), `.book-toc-section` (目次), `.book-author-profiles-section` (著者プロフィール) を抽出し、独自のセクションヘッダー（【内容紹介】など）付きで結合する。
  - `performer`: `.book-authors-section` から抽出し、`著/編/訳/作者` 等の接頭辞をストリップする。
  - `price_amount`: `.book-price-section` の中から「本体 XXXX 円」の数値を正規表現抽出し、数値（float型）として格納する。
  - `image_url`: 書籍表面のカバー画像を `img.book-image` から絶対URL化して抽出し、格納する。
- **スケルトン・ローディング防止措置（2026-06-07 教訓）**: hanmoto リストページは、クライアントサイドでプレースホルダー（Skeleton）カードを先にロードするため、`wait_for_selector(".bd-booklist-item-book")` は空のデータを誤検知して終了してしまう。必ず、より深い実コンテンツ上の要素である `.bd-booklist-item-book [data-content-name="title"]` などを監視対象とすること。

## 既知の問題

- **NDL ↔ hanmoto 重複**: 同一書籍が両ソースに登場する場合がある（既知の非バグ、少量の重複は許容）
- **selector ドリフト**: hanmoto のマークアップ変更で 0 件になった場合は selector を更新する
