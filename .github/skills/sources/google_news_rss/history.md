# Google News RSS Scraper — Implementation History

---

## 2026-08-04: Japan→Taiwan B2C 活動誤留 active pool（event `3d74504d`）

**問題：** `3d74504d` 是台北收費體驗展，場地為台北市中山區，入場費為 NTD 350。活動面向台灣當地參加者，不是日本境內活動，卻因 Google News RSS 的台灣相關性判定而保留為 active。

**根因：** `google_news_rss.py::_is_taiwan()` 判斷新聞是否與台灣相關，不是活動地點或受眾 filter。Annotator 的舊 LOCATION GATE 又沒有可被 schema 或 writer 消費的輸出，因此無法把這類 Taiwan-local B2C 活動送入可執行的人工複審流程。

**處理：** Wave 1 已閉合 annotator scope decision、非日本地點雙閘門與 admin 逐筆確認路徑。Phase 6a 只建立 digest-bound cleanup 工具並執行唯讀 snapshot；snapshot 因已審核名單含 active parent/child 關係而 fail closed，沒有建立 manifest，也沒有執行 production mutation。

**教訓：** 台灣相關性不能替代活動地點與受眾判斷。Google News RSS 的 source-level narrow guard 屬 Wave 2，尚未實作，不得把本次共用 scope gate 誤記為來源層過濾已完成。

## 2026-06-03 — 台灣限定串流新聞誤留 active pool，手動停用（event `2b9ee650`）

**問題：** `2b9ee650` 是台灣公共電視串流平台上架台語配音版《葬送的芙莉蓮》的新聞稿，不是日本境內可參與活動，也不是本站要保留的常設配信。但因標題含 `配信`、`end_date=NULL`，仍留在 active pool，最後被前端長期/常設 shelf 吸入。

**修正：** DB 直接更新 `is_active=false`，並寫入 `deactivated_reason='out_of_scope: Taiwan-only streaming news article — not a Japan event'`。

**教訓：** Google News RSS 會抓到台灣境內串流平台上架新聞。若內容只有台灣平台配信消息、沒有日本場域或參與性，就不應保留在 active 事件池，更不應當成常設內容補欄位留存。小樣本（`<20`）時優先單筆手動停用，不先做大規模清理。

## 2026-05-31 — VOD/ストリーミング クエリ追加（commit `a9a0066`）

**変更：** `google_news_rss.py` の検索クエリに VOD/ストリーミング関連キーワードを追加。オンライン配信・VOD リリース関連の台湾コンテンツ記事が取得できていなかった。

**修正（commit `a9a0066`）：** 新しい VOD/ストリーミング系クエリを追加。

**教訓：** Google News RSS は映画・ドラマ・ドキュメンタリーの VOD 配信告知も拾う。新しい配信プラットフォームや台湾コンテンツ関連のストリーミング用語が登場したらクエリを定期更新する。
