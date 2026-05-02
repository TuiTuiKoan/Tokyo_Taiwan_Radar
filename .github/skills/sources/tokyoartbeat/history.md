# tokyoartbeat — History

Newest at top.

---

## 2026-05-02 — デニス・リン展 場地幻覺：raw_description 無場地資訊導致 GPT 猜錯場館

**Error**: 活動 `1e375d6c`（デニス・リン展）的場地顯示為「東京都現代美術館」（錯誤），正確為「Yukikomizutani，TERRADA ART COMPLEX II 1F，品川区東品川」。

**Root cause**: `raw_description` 只有英文藝術家簡介，沒有任何 venue、address、hours 資訊。Annotator GPT 從訓練知識推斷場地，對高知名度美術館（東京都現代美術館、森美術館等）過度自信，直接猜錯。

**Fix**: 手動呼叫 Contentful API 取得正確場地資料並執行 DB update 覆蓋：
1. `GET /entries/{event_id}` → 取得 `venue` link id（`contentType: location`）和 `openingHours`
2. `GET /entries/{venue_id}` → 取得 `fullName`、`address`、`closedDays`、`openingHours`

**Lesson**: tokyoartbeat scraper **必須**在 `raw_description` 開頭附加結構化場地 header（会場・住所・開場時間・休廊日・入場料）。Contentful API 已有完整欄位，不應仰賴 GPT 推測。

**Required raw_description header format**:
```
開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日
会場: {fullName}
住所: {address}
開場時間: {openingHoursOpens}〜{openingHoursCloses}
休廊日: {closedDays}
入場料: {admissionFee}円（0 = 無料）
```

**Status**: Scraper still DISABLED (see 2026-04-26). This field mapping must be implemented when the scraper is re-enabled.

---

## 2026-04-26 — Search API does not filter by keyword in headless Playwright

**Error**: Dry-run collected 42 candidate event URLs from `?query=台湾` but returned 0 Taiwan-related events.

**Root cause**: Tokyo Art Beat is a statically-exported Next.js app (`nextExport: true`). The `?query=台湾` parameter is processed entirely client-side by React. In headless Playwright:
1. The page renders default popular events (Daniel Buren, Urs Fischer, etc.)
2. `台湾` never appears in `page.inner_text("body")` — not even after 30s of waiting
3. Zero API responses from tokyoartbeat.com contain Taiwan content
4. The search button on `multipleSearch` is never enabled (blocked by cookie consent modal)
5. Cookie consent "OK" click does not enable the search button

**Confirmed behavior**:
- GA fires `view_search_results` with `search_term=台湾` — React processes the URL, but the API call to get filtered results never completes/renders
- The search results come from a Contentful/Hasura backend that requires logged-in session or specific tokens

**Fix**: Commented out `TokyoArtBeatScraper()` from `main.py` SCRAPERS list to avoid wasting CI time.

**Lesson**: For React/Next.js apps with static export, URL parameters may not be applied to search results in headless mode. The `networkidle` event fires before the filtered API response is received. Test by checking if the search keyword appears in `page.inner_text("body")` with a 30s `wait_for_function` timeout.

**Status**: Scraper is DISABLED. Needs a new approach:
- Option A: Intercept the actual Contentful/Hasura GraphQL query and call it directly
- Option B: Use a different data source for Tokyo art events with Taiwan content

---

## 2026-04-26 — Incorrect --source key

**Observation**: `--source tokyoartbeat` fails. Correct key: `tokyo_art_beat` (from `TokyoArtBeatScraper`).

**Lesson**: `--source` key = class name CamelCase → snake_case, minus `Scraper` suffix.
