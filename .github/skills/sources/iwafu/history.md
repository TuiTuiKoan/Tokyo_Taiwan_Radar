# iwafu Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-10-12 — 版面改版＋搜尋變寬：16 筆「詳細を見る」柯南活動上架

**問題：** 10/12 一次進了 16 筆 iwafu 活動，標題全是「詳細を見る」，內容是名探偵コナン リアル脱出ゲーム（全球巡演，與台灣無關），分類卻被標成「台湾の感性・アイデンティティ」。10/6 那批 6 筆裡也有 5 筆無關（鉄道フェスティバル、焼き芋パフェ等）。共 21 筆已以 `is_active=false` 下架（`deactivated_reason` 註明 iwafu layout change / broadened search）。

**根因（四層同時失效）：**
1. **卡片文字順序改變**：新版為「標題 → `{縣}{日期}` → 標題 → 摘要」。`_extract_title_from_card()` 以位置取第 2 行，拿到的是日期行 → `_BLOCKED_SERIES`（已含 名探偵コナン）在卡片比對撲空。
2. **詳細頁 `<h1>` 變成 UI 字串「詳細を見る」**，真標題移到 `<h2>` → h1 比對也撲空，DB 存了「詳細を見る」。
3. **`main` 抓不到內文** → description 退回卡片的 iwafu AI 摘要。原文「全国各地をはじめ、台湾など世界各地で開催」被改寫成「日本や世界で各地で開催」，`_GLOBAL_TOUR_PATTERNS` 失去比對對象。證據：16 筆全部 `official_url` 空、地點是卡片車站名、raw 無「台湾」。
4. **iwafu 搜尋變寬**（查詢被擴展為「台湾人気 イベント」），而 `scrape()` 的 Phase 2 過濾早已消失（`cards = all_cards`），搜尋結果被當成台灣相關直接放行。
5. **Annotator 的台灣關聯門檻是空轉的**：prompt 寫「set is_active=false in your mind」，沒有輸出欄位、程式也不讀。模型在 selection_reason 寫了「台湾との直接的な関連はありません」，活動照樣上架。

**修正：**
- 標題改用 `og:title`（`_clean_og_title`）→ h1 → h2 → 卡片；`_UI_TITLES` 與日期行一律不接受；卡片標題改為「第一個非日期／縣名／車站／UI 字串的行」，不依賴行序。
- 內文依序嘗試 `main` / `#app-content` / `[role=main]`，退路 `og:description` 再退卡片摘要；新增新版 noise markers。
- 全球巡演 regex 改對 title + description + og:description 比對。
- 補回 Phase 2 `_mentions_taiwan`（詳細頁層級）。
- 新增 run-level `_title_anomaly`：同標題佔一半以上（≥5 筆）就整批丟棄並 log error。
- Annotator 新增結構化 `taiwan_relevance {is_relevant, confidence}`；`_relevance_gate_update()` 在 confidence ≥ 0.8 且非人工審核、非 user_submission 時設 `is_active=false`，並不產生子活動。

**教訓：**
- **黑名單只在比對字串正確時有效。** 標題解析壞掉時，所有以標題為鍵的防線一起失效；要有一道不依賴標題的防線（Phase 2 全文檢查、annotator 結構化判斷）。
- **LLM 的判斷必須落到結構化欄位，並由程式碼執行。** 「in your mind」的指示等於沒有指示；selection_reason 的散文不是控制訊號。
- **優先用 meta（og:title / og:description）而非 DOM 位置。** 分享用 meta 跨改版最穩定，且 og:description 保留主辦方原文，不會被平台 AI 摘要改寫。
- **AI 摘要不是原文。** 平台的「AIおすすめ」會刪掉對判斷關鍵的字（台湾など世界各地）；相關性判斷一律用原文。
- **加輸出形狀的異常偵測**：同一來源整批相同標題是改版的最強訊號，應該讓該來源停下，而不是寫進 DB。

---

## 2026-05-30 — 主催者 URL が `location_url` に誤設定（DB 直接修正）

**問題：** `iwafu_1140344`（赤城で台湾さんぽ）の `location_url` が `https://gunma-taiwan-association.studio.site/`（群馬台湾総会 = 主催者サイト）に誤設定。会場リンクが主催者サイトに誤誘導されていた。

**根本原因：** `raw_description` 末尾に主催者 URL が含まれており、scraper または annotator が `location_url` に設定してしまった（会場 URL ではなく主催者 URL）。

**修正：** `location_url = null`、`organizer = '群馬台湾総会'`、`organizer_url` に移動、`official_url = 'https://gunma-kanko.jp/events/290'`（群馬観光公式サイト）。FC lock 3 フィールド。

**教訓：** iwafu の `raw_description` 末尾 URL は主催者サイトである可能性が高い。`location_url` ではなく `organizer_url` へ。

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
