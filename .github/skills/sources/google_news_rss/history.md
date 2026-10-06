# Google News RSS Scraper — Implementation History

---

## 2026-10-06 — 依賴未鎖版本，import 階段崩潰讓整個 Daily Scraper 停擺 15 天

**問題：** 2026-09-21 ～ 10-05 的 Daily Scraper 連續 15 次失敗（最後成功 09-20）。`requirements.txt` 寫的是 `googlenewsdecoder>=0.1.6`，2026-09-20 21:27 UTC 上游發佈 0.2.1，會一併裝進 `selectolax` 1.0；selectolax 1.0 移除了 Modest 後端（`selectolax.parser`），0.2.x 本身也拿掉了我們呼叫的 `new_decoderv1`。`main.py` 啟動時會 import 所有來源，於是 `google_news_rss.py` 第一行 import 就丟 `ImportError`，所有來源（117 個模組）一起停擺。起初懷疑是 GitHub 認證過期，但同一次執行的 Supabase 與 LINE 呼叫都是 200，排除認證。

**修正：** 鎖定 `googlenewsdecoder==0.1.7` 與 `selectolax>=0.3,<1.0`；`google_news_rss.py` 的 import 改為 `try/except ImportError`，失敗時 `new_decoderv1=None`，`_decode_gnews_url()` 直接回傳 `None`，退回使用 Google News 轉址 URL，只記警告不中止執行。

**教訓：**
- 第三方套件（尤其是小型、單一維護者的套件）在 `requirements.txt` 必須鎖定已驗證版本，並一併鎖住會被它拉進來的間接依賴；`>=` 會讓上游發版直接改變 CI 行為。
- 任何來源模組在 import 階段失敗都會拖垮 `main.py` 的全部來源。非核心依賴應在模組內 guard import 並提供降級路徑，讓單一來源壞掉只影響自己。
- 排查 CI 連續失敗時，先看失敗步驟的耗時與 traceback（本次 `Run scraper` 1 秒就結束 = import 錯誤），再比對上游套件發佈時間與首次失敗時間，不要先假設是認證問題。

## 2026-06-03 — 台灣限定串流新聞誤留 active pool，手動停用（event `2b9ee650`）

**問題：** `2b9ee650` 是台灣公共電視串流平台上架台語配音版《葬送的芙莉蓮》的新聞稿，不是日本境內可參與活動，也不是本站要保留的常設配信。但因標題含 `配信`、`end_date=NULL`，仍留在 active pool，最後被前端長期/常設 shelf 吸入。

**修正：** DB 直接更新 `is_active=false`，並寫入 `deactivated_reason='out_of_scope: Taiwan-only streaming news article — not a Japan event'`。

**教訓：** Google News RSS 會抓到台灣境內串流平台上架新聞。若內容只有台灣平台配信消息、沒有日本場域或參與性，就不應保留在 active 事件池，更不應當成常設內容補欄位留存。小樣本（`<20`）時優先單筆手動停用，不先做大規模清理。

## 2026-05-31 — VOD/ストリーミング クエリ追加（commit `a9a0066`）

**変更：** `google_news_rss.py` の検索クエリに VOD/ストリーミング関連キーワードを追加。オンライン配信・VOD リリース関連の台湾コンテンツ記事が取得できていなかった。

**修正（commit `a9a0066`）：** 新しい VOD/ストリーミング系クエリを追加。

**教訓：** Google News RSS は映画・ドラマ・ドキュメンタリーの VOD 配信告知も拾う。新しい配信プラットフォームや台湾コンテンツ関連のストリーミング用語が登場したらクエリを定期更新する。
