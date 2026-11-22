---
name: tufs-aa
description: Platform rules, listing walk, 非公開 filter, Taiwan/Formosan-language relevance and venue handling for the 東京外国語大学 AA研 (tufs_aa) scraper
applyTo: scraper/sources/tufs_aa.py
---

# 東京外国語大学 アジア・アフリカ言語文化研究所（AA研）Scraper — Platform Reference

## Why this source

#726：2026-06-19 的「小川尚義・浅井恵倫・土田滋台湾資料贈呈記念式典」在 AA研舉辦，但 TTR 只從 Google News 的事後新聞稿得知。AA研另有長期的「土田滋博士の台湾原住民語資料に基づく研究」共同研究課題，台灣相關活動以台灣原住民語言學為主，一年數場。

## Platform Profile

| Field | Value |
|-------|-------|
| Listing URL | `https://www.aa.tufs.ac.jp/events/`，第 n 頁 `…/events/page/{n}/` |
| Upcoming only | `https://www.aa.tufs.ac.jp/events/upcoming/`（目前未使用，見 Open questions） |
| Detail URL | `https://www.aa.tufs.ac.jp/events/detail/e{N}/`（英文版 `/en/events/detail/e{N}/`，同一場） |
| Platform | WordPress（`/wp-content/uploads/`），伺服器端渲染；頁面沒有 RSS 連結 |
| Rendering | 靜態 HTML，`requests` + BeautifulSoup，不需 Playwright |
| Auth | 不需要 |
| Robots | 詳細頁 `meta robots: index, follow`；`robots.txt` 尚未從 CI 取得確認 |
| Volume | 每頁 10 筆、約 41 頁；依活動日期新→舊排序 |
| Source name / ID | `tufs_aa` / `tufs_aa_e{N}` |
| Region | 東京都府中市（AA研本館）為主，也有外部會場與線上 |

## Listing walk

1. 從 page 1 讀到 `MAX_PAGES`（8）。
2. 卡片以 `/events/detail/e<digits>/` 連結定位，往上找最小的、含日期且只含一個活動 ID 的祖先節點當卡片。不依賴 CSS class。
3. 某頁所有卡片的最後日期都早於今天 → 停止。
4. 卡片文字含 `非公開` → 跳過（共共課題研究会等不對外的研究會）。**先查 `非公開`**，因為 `公開` 是它的子字串。

## Detail fields

標籤在詳細頁以「標籤／: 值」或「標籤: 值」呈現，parser 兩種都吃。

| Event field | Source |
|-------------|--------|
| `raw_title` / `name_ja` | `<h1>`，沒有時用 `og:title` 的 `|` 前段 |
| `start_date` | `日時` 的第一個日期；單日且有 `HH:MM` 時帶上開始時間 |
| `end_date` | `日時` 的最後一個日期（多日活動一行一個日期） |
| `location_name` | `場所`，以 `/` 切開後去掉「オンライン／Online／Zoom」段；全是線上 → `オンライン` |
| `location_address` | 含 `AA研` → `東京都府中市朝日町3-11-1 東京外国語大学アジア・アフリカ言語文化研究所`；含 `東京外国語大学`／`AGORA`／`プロメテウス` → 校本部地址；其他留空交 annotator |
| `organizer` | `主催・共催` |
| `raw_description` | `開催日時: YYYY年MM月DD日（<日時原文>）\n\n` + `<main>` 全文（去掉 header/footer/nav/script） |
| `image_url` | `og:image` |
| `category` | `["academic"]`（annotator 細分） |
| `is_paid` | 不設定（多數免費，但頁面不一定寫） |

`開催形態`（対面／ハイブリッド／オンライン）與 `使用言語` 保留在 description，交 annotator 判斷 `event_form` 與語言支援。

## Relevance filter

對詳細頁的「標題 + 全文」判斷，不只看列表標題——台灣常只出現在節目或「関連プロジェクト」。

- 明示：`台湾` `臺灣` `台灣` `Taiwan` `Formosa` `フォルモサ`
- 台灣原住民族語／台灣語言：`アミ語` `アミ族` `タイヤル` `アタヤル` `セデック` `パイワン` `ブヌン` `ツォウ` `ルカイ` `サイシャット` `プユマ` `タオ語` `ヤミ語` `サオ語` `カバラン` `シラヤ` `閩南語` `台湾語` `客家`，以及英文名（大小寫敏感）
- 排除：`仙台湾`
- `アミ` 單獨不收（會命中 `アミノ酸`），必須是 `アミ語`／`アミ族`。

已知會進來但不一定是台灣主題的情況：節目中有一篇講者在台灣做田野的報告（例：e250 刺青文化研究會）。這類交 annotator 的 relevance gate 判斷，不在爬蟲層硬擋。

## Example URLs

- https://www.aa.tufs.ac.jp/events/detail/e441/ — 台湾資料贈呈記念式典（公開，2026-06-19，已結束；#726 的正例）
- https://www.aa.tufs.ac.jp/events/detail/e97/ — 土田滋台湾原住民語資料研究會（非公開，應被跳過）
- https://www.aa.tufs.ac.jp/events/page/3/ — 列表頁樣本

## Troubleshooting

| 症狀 | 檢查 |
|------|------|
| log `no cards on … — selector drift?` | 詳細頁連結格式是否仍為 `/events/detail/e<N>/` |
| `no date for …` | `日時` 標籤是否改名或日期格式改成其他寫法；`_DATE_RE` 支援 `年月日`、`/`、`-` |
| 0 筆但網站有台灣活動 | 該活動是否標為 `非公開`；關鍵字是否需要補（新的族語名稱） |
| GitHub Actions 被擋（403） | 參照 `mot`／`taipei_fukuoka`：移到 `WEEKLY_SOURCES` 以家用 IP 執行 |

## Open questions

- `/events/upcoming/` 只列未來活動，若分頁格式穩定可改用它，省下判斷停點的邏輯。等 CI dry-run 看到真實 HTML 後再決定。
- 網站是 WordPress，`/wp-json/wp/v2/` 可能有 events 的 custom post type。第一版沒用，因為還沒驗證欄位；若可用，日期與分類會更穩。
