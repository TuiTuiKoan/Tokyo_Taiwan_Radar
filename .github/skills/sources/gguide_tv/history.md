# gguide_tv History

## 2026-05-01 — business_hours fallback 到 detail page

**問題：** list page `schedule_raw` 為單行格式（只有開始時間），`end_time_str = None`，detail page 有完整播出時段但未被使用，`business_hours` 仍為 `None`（如 event `14740bf4`：21:00〜22:00）。

**修正：** 加入 fallback：`end_time_str = None` 時，對 detail_text 執行 `r"(\d{1,2}:\d{2})\s*\n[-−]\s*\n(\d{1,2}:\d{2})"` 正規表達式提取結束時間，成功時設 `business_hours = f"{start_time_str}〜{end_time_str}"`。

**DB 補丁：** event `14740bf4` 直接更新 `business_hours = '21:00〜22:00'`。

**Commit：** fix(scraper): gguide_tv fallback end_time extraction from detail page

---

## 2026-05-01 — get_text() 須加 separator="\n" 才能識別多行 schedule（commit `a895e07`）

**問題：** `ps[2].get_text(strip=True)` 把開始時間、`-`、結束時間三個 HTML 子節點合併為無分隔字串（`"23:450:00 歌謡ポップス"`），`_parse_schedule()` 的多行分支永遠不觸發，`end_time_str = None`。

**修正：** 改為 `ps[2].get_text(separator="\n", strip=True)`，產生 `"23:45\n-\n0:00 歌謡ポップス"` 格式，正確觸發多行解析。

**教訓：** HTML 子節點各佔一個元素時，**必須加 `separator` 參數**才能在文字間保留邊界。

---

## 2026-04-28 — Initial implementation

- Implemented 2-step HTTP session: Step 1 GET `/search/` for cookie, Step 2 GET `/fetch_search_content/` for HTML fragment.
- `ebisId` from `a.js-logging[data-content]` JSON is the stable dedup key.
- Year inference logic for schedule strings: try current year, fall back to next year if result > LOOKBACK_DAYS in past — handles Dec→Jan boundary.
- Late-night broadcast convention (`25:00` style) handled with `day_offset`.
- テレサ・テン keyword filter: only keep programs where full `テレサ・テン` appears in title (not as minor guest).
- `台湾ドラマ` search omitted — fully covered by `台湾` keyword.
- Detail page fetched for description; `<main>` tag contains clean program content.
- dry-run: 21 events, 1 in-source duplicate detected and dropped by `dedup_events`.
