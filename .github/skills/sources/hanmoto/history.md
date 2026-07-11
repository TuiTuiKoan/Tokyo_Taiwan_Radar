# hanmoto scraper 修訂歷史

## 2026-07-11 — publication phase 3 invariant sync

- hanmoto publication 規則改為 exact `event_form=['publication']` 判定，避免 source/category blanket skip。
- 純出版資料模型改為 metadata-only（七欄 intentional null + sentinel），不再依賴 locale placeholder 語意。
- publisher required 與 mixed negative（`['publication','lecture']` 仍 physical）一併入規範。

## 2026-06-07 — BeautifulSoup 輕量爬取、書籍細節解析功能升級與書籍封面大圖抓取

- **BeautifulSoup+requests 重構**：詳細頁 fetch 原本對 Playwright `new_page()` 負載極重。改用 requests 及 BeautifulSoup 直接抓取網頁原始碼，速度提升 10 倍以上且執行極為穩定。
- **詳情頁解析度升級**：成功爬取 `.book-kaisetsu-section` (內容紹介) 、`.book-toc-section` (目次) 與 `.book-author-profiles-section` (著者プロフィール)，拼接編寫成優質有條理的 `raw_description`。
- **Numerical Price & Cover Image 提取**：解析 `.book-price-section` 並 regex 提取數值化為 `price_amount` (本體價格)，從 `img.book-image` 抓取並組裝 absolute `image_url` 作為書籍封面。
- **Skeleton loading 骨架防禦**： `wait_for_selector` 原始鎖定 `.bd-booklist-item-book` 會在 skeleton state 下提前通過而拿到空 list。修正為鎖定內層實際標題元素 `.bd-booklist-item-book [data-content-name="title"]`，保證 100% 成功加載。
- **初始化 TypeError 修復**：Event 構造一律不注入非法 attributes (如 `business_hours_zh` / `location_address_zh`)，以符合 `BaseScraper` 的 Event dataclass 基底宣告。

## 2026-06-04 — publication hotfix sync

- publication 事件の address は占位文字を保持しつつ Maps リンク化しないように同期。
- 詳細ページから `performer` / `official_url` / `organizer_url` / `price_info` を補完する方針を明記。
- 日付 fallback を `発売日 > 登録日` に固定。

## 2026-06-04 — publication placeholders locale sync

- publication の占位文字は `location_name` / `location_address` / `business_hours` すべて locale に合わせて出し分ける。
- 日本語 UI の既定占位文は `新刊のご購入は各販売チャネルでお願いします`。
- 日本語 UI で中国語の占位文字が残らないよう、`*_zh` / `*_en` も同時に埋める。

## 2026-05-31 — 初版実装

- 新規スクレイパー（Publication Intel 計画 v3.1）
- 実装要点:
  - Playwright Chromium (headless) で最大 3 ページ取得
  - 4 段階 selector フォールバック（`div.booklist-item` → `ul.bookList > li` → 他）
  - ISBN は `data-isbn` 属性 → href パス `/isbn/{13桁}` の順で取得
  - server-side 台湾フィルタ済みだが client-side フィルタも保持（防衛的実装）
  - `ZERO_EVENT_OK_SOURCES` には追加しない（0 件 = scraper 異常として検出する）
