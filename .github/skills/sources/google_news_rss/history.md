# Google News RSS Scraper — Implementation History

---

## 2026-06-03 — 台灣限定串流新聞誤留 active pool，手動停用（event `2b9ee650`）

**問題：** `2b9ee650` 是台灣公共電視串流平台上架台語配音版《葬送的芙莉蓮》的新聞稿，不是日本境內可參與活動，也不是本站要保留的常設配信。但因標題含 `配信`、`end_date=NULL`，仍留在 active pool，最後被前端長期/常設 shelf 吸入。

**修正：** DB 直接更新 `is_active=false`，並寫入 `deactivated_reason='out_of_scope: Taiwan-only streaming news article — not a Japan event'`。

**教訓：** Google News RSS 會抓到台灣境內串流平台上架新聞。若內容只有台灣平台配信消息、沒有日本場域或參與性，就不應保留在 active 事件池，更不應當成常設內容補欄位留存。小樣本（`<20`）時優先單筆手動停用，不先做大規模清理。

## 2026-05-31 — VOD/ストリーミング クエリ追加（commit `a9a0066`）

**変更：** `google_news_rss.py` の検索クエリに VOD/ストリーミング関連キーワードを追加。オンライン配信・VOD リリース関連の台湾コンテンツ記事が取得できていなかった。

**修正（commit `a9a0066`）：** 新しい VOD/ストリーミング系クエリを追加。

**教訓：** Google News RSS は映画・ドラマ・ドキュメンタリーの VOD 配信告知も拾う。新しい配信プラットフォームや台湾コンテンツ関連のストリーミング用語が登場したらクエリを定期更新する。
