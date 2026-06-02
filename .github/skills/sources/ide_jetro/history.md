# ide_jetro Scraper — History

## 2026-06-02 — `開催日程` / `講師・プログラム` / `主催` 抽取不足，導致時間與講者資訊缺失（event `aacfb816`）

**問題：**
- 活動頁 `https://www.ide.go.jp/Japanese/Event/Seminar/260611.html` 在前端缺少時間、講者與主辦細節。
- DB 事件 `aacfb816-bb7d-4093-abe3-01b401388e95` 原先 `business_hours=null`、`performer(s)=null`，可見資訊不足。

**根本原因：**
- `ide_jetro.py` 先前只抓 listing 日期與一段簡介，沒有解析 detail page 的結構化區塊（`開催日程`、`会場`、`主催`、`講師・プログラム`）。
- heading 後的內容位於 IDE CMS 的 nested block（`pbNested` / `paragraph` / `table-basic`）中，若只用傳統 sibling 抓法會拿不到值。

**修正：**
- 在 `_fetch_detail()` 新增結構化抽取：
  - `開催日程` → 時間區間，回填 `business_hours`
  - `主催` → 回填 `organizer`
  - `会場` → 回填 `location_name`
  - `講師・プログラム` table 第三欄（講師）→ 組成 speaker 名單
- 將 `会場:`、`主催:`、`時間:`、`講師:` 明確寫入 `raw_description`，供 annotator 穩定抽取。
- 對既有事件單筆回填並重跑 annotator，最終得到：
  - `business_hours = 14時00分～15時30分`
  - `organizer = ジェトロ・アジア経済研究所`
  - `performers = [松本 はる香, 竹内 孝之]`

**教訓：**
- IDE 這類 CMS 頁面不能只依賴「摘要段落」，必須優先抽取 heading 對應的結構化區塊。
- 人物與主辦資訊要以顯式前綴寫入 `raw_description`（例如 `講師:`、`主催:`），避免 annotator 因文本形態差異漏抓。
