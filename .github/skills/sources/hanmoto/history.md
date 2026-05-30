# hanmoto scraper 修訂歷史

## 2026-05-31 — 初版実装

- 新規スクレイパー（Publication Intel 計画 v3.1）
- 実装要点:
  - Playwright Chromium (headless) で最大 3 ページ取得
  - 4 段階 selector フォールバック（`div.booklist-item` → `ul.bookList > li` → 他）
  - ISBN は `data-isbn` 属性 → href パス `/isbn/{13桁}` の順で取得
  - server-side 台湾フィルタ済みだが client-side フィルタも保持（防衛的実装）
  - `ZERO_EVENT_OK_SOURCES` には追加しない（0 件 = scraper 異常として検出する）
