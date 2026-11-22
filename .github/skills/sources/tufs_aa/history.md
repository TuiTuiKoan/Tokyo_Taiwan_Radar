# tufs_aa Scraper — Implementation History

## 2026-11-22 — Initial implementation（#726）

**Trigger:** #726 的正例活動（e441 台湾資料贈呈記念式典）只經 Google News 事後新聞稿進到 TTR，AA研活動列表是來源缺口。

**Decisions:**

- **Static HTML + 標籤式 parser**：開發環境只能看到頁面的文字化結果，拿不到逐字 HTML，所以刻意不寫 CSS selector，改用詳細頁 URL 模式與日文標籤取值。這也讓主題小改版不會打斷爬蟲。
- **從 `/events/` page 1 往後讀**：列表依活動日期新→舊排序，page 1 是最遠的未來；整頁都結束就停，上限 8 頁（約 80 筆，涵蓋兩個多月以上）。
- **`非公開` 在列表階段跳過**：TTR 只收一般人能參加的活動。AA研的台灣原住民語共同研究課題多數是非公開研究會，所以實際收錄量會很少；依 Low-Signal Source Policy 仍值得每日掃描。
- **台灣判定在詳細頁**：e441 標題有「台湾」，但同系列研究會的講題常只寫アミ語、アタヤル語，所以加入族語名稱。`アミ` 單獨不收，`仙台湾` 排除。
- **只收日文版**：英文版是同一個 `e<N>`，不另建 Event。

**Not verified at implementation time:** 真實 HTML 下的卡片定位與標籤格式、`robots.txt` 內容。由 PR 的 CI dry-run 補證據。
