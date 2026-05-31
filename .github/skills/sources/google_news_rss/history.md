# Google News RSS Scraper — Implementation History

---

## 2026-05-31 — VOD/ストリーミング クエリ追加（commit `a9a0066`）

**変更：** `google_news_rss.py` の検索クエリに VOD/ストリーミング関連キーワードを追加。オンライン配信・VOD リリース関連の台湾コンテンツ記事が取得できていなかった。

**修正（commit `a9a0066`）：** 新しい VOD/ストリーミング系クエリを追加。

**教訓：** Google News RSS は映画・ドラマ・ドキュメンタリーの VOD 配信告知も拾う。新しい配信プラットフォームや台湾コンテンツ関連のストリーミング用語が登場したらクエリを定期更新する。
