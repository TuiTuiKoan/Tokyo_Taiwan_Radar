---
slug: social-sources
title: 社群來源（臉書粉專與 X 帳號）
status: active
branch: feat/social-sources
created: 2026-11-22
tags: [scraper, sources, ci]
---

> v2（2026-11-22）：依 `plan-critique-1.md` 修訂。處理結果見該檔末表。評審由 Claude 的 plan-critic 執行（Codex 在此環境無法啟動），與撰寫者同一模型家族。

## What（做什麼）

把「主辦單位只發在臉書粉專或 X 的活動貼文」接進既有管線。抓取對象由後台的 `research_sources` 管理，貼文資料不足時跟著貼文裡的連結補資料，之後和所有來源走同一條路：`events` → merger → annotator → enrich → 網站。

```
research_sources（agent_category = facebook_page | x_account，status = implemented）
  → 抓取層：X 官方 API／臉書免登入 scraper（Apify）→ SocialPost
  → 前置過濾（規則，不花 LLM）：無活動訊號、已過期、回顧貼文、注入樣式 → 丟棄並計數
  → 補資料：貼文有連結就抓（最多 2 個、深度 1）
  → 沒有未來日期或地點訊號 → 記為「資料不足」，不產生 Event
  → 完整 → Event（source_name = facebook_pages | x_accounts）
  → [M3 之後] 每日管線：merger → annotator ＋ 上線閘門 → enrich → IndexNow
```

## Why（為什麼）

- 台灣相關的小型主辦單位（同鄉會、讀書會、獨立書店、個人策展）常常只在臉書或 X 公告活動，沒有官網也不上 Peatix，現有 100 多個來源抓不到。
- 使用者目前靠手機看到貼文再手動處理；`url-intake` 解決了單筆收錄，但仍需要人每次貼連結。
- 使用者決定（2026-11-22）：社群來源的活動要全自動上線，本人只做雙週或每月的事後稽核。

## Non-Goals（不做什麼）

- 不使用任何登入狀態：不帶 cookie、不用個人帳號、不用瀏覽器 agent 逐次操作。只讀免登入可見的公開粉專與公開帳號。
- 不做關鍵字全站搜尋（只追蹤清單上的帳號）；發掘新帳號交給 auto-research（M5）。
- 不抓留言、按讚數、個人檔案、圖片。
- 不抓 Instagram、Threads、LINE（登入牆，另案）。
- 不收活動結束後的回顧貼文（使用者 2026-11-22 決定 TTR 不收活動報導）。
- 不收純出版紀錄（`event_form == ['publication']`）：新刊公告沒有地點，和上線閘門的地點條件衝突；出版紀錄已有 `hanmoto`、`ndl_opensearch` 等專屬來源。
- 不用 Playwright 抓連結頁：需要 JS 渲染或擋機器人的頁面預期抓不到，以各網域的成功率統計決定日後是否補。
- 第一階段（M1）不寫 production、不註冊進每日排程、不花錢。

## Design（設計）

### D1 抓取對象：`research_sources` 是唯一清單

- 新增兩種 `agent_category`：`facebook_page`、`x_account`（欄位是自由文字，沒有 CHECK，不需要 migration）。
- 只載入 `status = 'implemented'` 的列，寫法比照 `peatix.py` 的 `_load_db_organizers`。
- handle 取 `source_profile.handle`，沒有時從 `url` 解析。格式不合的列跳過並記 log。
- 寫入規則（M2 起）：
  - `url` 用正規形式 `https://www.facebook.com/<handle>`、`https://x.com/<handle>`（`url` 有 UNIQUE，不同寫法會變成兩列）。
  - `scraper_source_name` 填 `facebook_pages`／`x_accounts`（比照 `peatix_organizer` 列）。否則 `audit_post_build.py` 會因 `implemented` 列缺 key 而失敗，M3 註冊時 `_ensure_scrapers_registered` 也會多插一筆空殼列。
  - `display_type` 一併填寫；後台分類標籤與三語字串在 M2 同一個 PR 補上。
  - `source_profile`：`handle`、`x_user_id`（事先填好，省去每次 0.010 美元的查詢）、`last_post_id`（M3c 起由排程回寫）。
- **與 auto-research／auto-generate 的隔離（M2 寫入第一列之前必須完成）**：`auto_research.py` 會把 `candidate` 列拿去評分並改狀態，`generate.py` 會替 `researched` 列生成 scraper。兩者的查詢都要排除這兩種 `agent_category`，並加測試。
- 新帳號以 `candidate` 進表，由使用者升為 `implemented`。抓誰屬於範圍判斷，也會增加費用，維持人類關卡。
- 停抓的狀態用 `paused`（沒有任何自動化讀取這個值），不用 `researched`。
- 不使用 `creators` 表當清單：它同時是使用者帳號的個人檔案與投稿者資料。後台「加入抓取來源」按鈕在 M4 把創作者的社群連結寫成一筆 `research_sources`。

### D2 抓取層（可替換）

| 平台 | 方案 | 理由 | 費用 |
|---|---|---|---|
| X | 官方 API v2（`tweepy`，Bearer Token），`GET /2/users/:id/tweets`，排除轉推與回覆 | repo 已有 `tweepy`；條款風險較低 | 每讀一則 0.005 美元；查帳號 id 每筆 0.010 美元 |
| 臉書 | Apify 上的免登入貼文 scraper（actor id 寫死在程式碼），REST `run-sync-get-dataset-items` | Meta 沒有可用的公開粉專讀取 API；自寫解析維護成本高 | 依 actor 而定，每千則約 1–2 美元 |

- 兩個抓取層都輸出同一個 `SocialPost`。回應轉換是純函式。
- **X 的轉換依官方文件的 v2 回應格式；臉書的轉換依多個 actor 公開文件中共通的欄位，測試 fixture 是合成資料，尚未對真實回應驗證。** M2 第一步用真實回應取代 fixture。
- 換 actor 要走 PR：環境變數覆寫會讓任意第三方 actor 拿著 Apify token 執行。
- 沒設定 token → `BackendUnavailable`，記為 `skipped`，不算失敗。有設定但失敗（token 過期、額度用完、HTTP 錯誤）→ 記入 `errors`，呼叫端必須讓它可見。
- 臉書 `source_id`：優先用數字貼文 id；只有 `pfbid…` 時改用永久連結（去掉 query）的雜湊，避免同一則貼文因網址形式不同而重複。

### D3 前置過濾（規則，不花 LLM）

依序判斷，結果與原因都計數：

1. 空白貼文、純轉貼 → 丟棄。
2. 注入掃描嚴重度 ≥ 2 → 丟棄，並把貼文連結留在 `flagged` 供稽核。
3. 找出貼文中的日期（`YYYY年M月D日`、`M月D日`、`M/D(曜)`、`YYYY-MM-DD`、`YYYY/M/D`）。
   - 沒有年份時取發文日前 180 天到後 185 天內最接近的那一年（與 `scraper.instructions.md` 的回推規則一致）；寫了星期時以星期為準。
   - 緊鄰 `締切`、`発売`、`予約開始`、`まで` 等字眼的日期不算活動日期。
   - 發文日與「今天」都以日本時間計算。
4. 所有日期都已過去 → 丟棄（`past_event`）。有回顧字眼且沒有未來日期 → 丟棄（`recap`）。
5. 沒有任何活動訊號字眼、也沒有未來日期 → 丟棄（`no_event_signal`）。
6. 其餘 → 保留，進補資料。

地點訊號要有上下文：`会場`、`場所`、`〒`、`オンライン`，或都道府縣名後面接 `市`、`区`、`駅` 等；單位名稱裡的地名和 @mention 不算。

已知會漏的寫法（試做期接受）：`12月5日〜7日` 只抓到第一個日期；沒有星期標記的 `12/5` 會被忽略。

這一層只是省錢的粗篩，不是上線閘門。真正的日期與地點由 annotator 抽取，上線與否由 D5 判定。

**注入掃描的刻意例外**：`security.injection_guard` 的政策是只偵測、不丟資料，annotator 也只是寫入 `event_reports`。社群來源不經人工就上線，所以貼文命中時直接丟棄；連結頁命中時只丟掉該頁文字，貼文照常處理。`SECURITY_SCAN_DISABLED` 會同時關掉這道丟棄。

### D4 補資料：跟著連結走

- 貼文只要有連結就抓，不論貼文本身看起來是否完整：貼文裡的日期可能是截止日，而 HTTP 抓取不花錢。
- 連結來源：API 提供的展開網址，加上貼文內文裡的網址。臉書的外連包裝（`l.facebook.com/l.php?u=…`）先解開，再經 `ingest_url.normalize_url`。
- 排除：同平台與登入牆網域、`t.co`、影音與圖片檔、YouTube。
- 排序：報名與活動平台優先，其餘照出現順序，連結集合頁與表單最後。這和 `extract_first_party_url` 的邏輯相反，所以另寫，不改既有函式。
- 抓取走 `ingest_url.fetch_html`，沿用它的上限：最多 5 跳轉址、每跳檢查非公開位址、回應 2 MB、timeout 20 秒。另設的上限：每則貼文最多 2 頁、每頁文字 3,000 字、少於 80 字視為無效。
- `extract_page` 會移除 `<script>` 並忽略 description，而報名平台的日期地點常在 schema.org `Event` JSON-LD 與 `og:description` 裡。所以在 `social/enrich.py` 先讀這兩者，放在頁面文字最前面；不改 `ingest_url`。
- 抓回的文字過注入掃描；以最終網址做快取，同一次執行同一頁只抓一次。
- 依網域統計成功與失敗（`link_stats`），供 M2 判斷哪些平台需要另外處理。
- 連結集合頁（`linktr.ee` 等）往下跟一層、圖片辨識，都留到之後。

### D5 Event 與上線

- `source_name`：`facebook_pages`、`x_accounts`；`source_id`：`fb_<id>`、`x_<id>`；`source_url`：貼文永久連結；`official_url`：補資料用的第一個頁面。
- `raw_description` 第一行是 `（記事配信日: <發文日，日本時間>）`，沿用 annotator 的年份錨點慣例；之後是 `投稿元`、`投稿者`、貼文全文、各連結頁文字。`start_date`、`organizer`、`category`、`image_url` 不由 scraper 填。
- 同一帳號單次最多產生 5 筆 Event，超過的留給稽核（帳號被盜或異常洗版時限制影響）。
- **merger（M3a）**：
  - 優先序 101。未列入 `SOURCE_PRIORITY` 的來源預設是 99，而 Pass 1 不排除新聞來源，所以低於 100 的值會讓貼文壓過大多數官方來源。101 也低於經使用者核准的 `url_intake`（100）。
  - 是否列入 `_NEWS_SOURCES` 先不決定：Pass 2 的條件是為新聞稿設計的，對活動公告過寬。M3a 用 M2 的資料跑 `run_merger(dry_run=True)`，在「不列入」與「列入但加名稱相似度下限」之間取捨，數據寫入 `notes.md`。
  - 同一帳號的公告、提醒、倒數貼文會是多筆活動：加入同來源去重（Pass 1.5）。
- annotator 的台灣相關性閘門**不豁免**社群來源。
- **上線閘門（M3a）**，與 `annotation_status = 'annotated'` 同一次 update 寫入：
  - `COALESCE(end_date, start_date)` 為空或早於今天 → `is_active = false`（用 `end_date` 才不會誤殺進行中的展覽）。
  - 沒有地點且不是線上活動 → `is_active = false`。
  - `event_form == ['publication']` → `is_active = false`（見 Non-Goals）。
  - 被停用的列之後重抓不會自動恢復。
- **不變條件**：把社群來源註冊進 `SCRAPERS` 的 PR，必須已包含上線閘門與它的測試，或晚於它合併。
- 來源自動停抓（M6）：同一帳號的活動連續被 `auto_qa` 判為問題 → 該列改為 `paused`。
- 雙週稽核報表（M6）：新增活動（含原貼文連結與資料來自貼文或連結）、資料不足清單、被注入掃描丟棄的貼文、各帳號命中率、重複上線筆數。

### D6 分階段與人類關卡

| 里程碑 | 內容 | 人類關卡 | 建議模型 |
|---|---|---|---|
| M1 | `scraper/social/` 核心與測試、`social_dryrun.py`；不註冊、不寫 DB | PR 合併 | Sonnet · medium |
| M2 | 見下 | 見下 | Sonnet · medium |
| M3a | 上線閘門、merger 優先序與去重 | PR 合併 | 設計評審 Opus · high |
| M3b | 註冊進 `SCRAPERS`、`source_expectations.json`、`ZERO_EVENT_OK_SOURCES` 的決定；抓取 job 不帶 production 憑證，產出 artifact 交給寫入 job | PR 合併（Tier 2） | Sonnet · medium |
| M3c | `last_post_id` 回寫（upsert 成功之後才寫） | PR 合併 | Sonnet · medium |
| M4 | 後台來源頁：新增社群來源、切換狀態、平台篩選；創作者頁「加入抓取來源」 | PR 合併 | Sonnet · medium |
| M5 | auto-research 反查既有單位的粉專與 X，寫入 candidate | PR 合併 | Sonnet · medium |
| M6 | 雙週稽核報表與來源自動停抓 | PR 合併 | Sonnet · medium |
| M7 | 圖片辨識補資料、連結集合頁往下一層 | PR 合併 | Sonnet · medium |
| M8 | 盤點：成本、命中率、誤上線筆數、重複上線筆數 | — | — |

**M2 的內容與順序**

1. 零成本驗證：列出 10 個粉專加 10 個 X 帳號的候選名單，人工數過去一個月各有幾則活動貼文。臉書命中太少就只做 X。
2. 排除 auto-research／auto-generate 對社群列的處理（D1）；後台最小支援（分類標籤、篩選、三語字串）。
3. 新增 `social-dryrun.yml`：每天排程，只帶 `X_BEARER_TOKEN`／`APIFY_TOKEN`，抓取對象讀 repo 內的 JSON 清單（不需要 production 憑證），不寫 DB，報告存成 artifact。
4. 兩週後把指標寫入 `notes.md`：讀取則數、各原因的丟棄數、各網域補資料成功率、產出 Event 數、人工抽 30 筆的正確率、實際花費。
5. 用真實回應取代臉書 fixture；存下 Peatix、LivePocket、eplus、teket 的真實 HTML 當 fixture。

**M2 的人類關卡（一張卡片交給使用者）**

- 明確接受以免登入方式抓公開粉專的 Meta 條款風險；Apify 是新的外部服務，會把追蹤的粉專清單交給第三方。
- X：確認開發者帳號已加入 pay-per-use 並儲值；決定讀取與發文是否共用同一個 app（共用時讀取花光額度會讓發文失敗；`x-post-cron.yml` 的四個 `X_*` secret 自 2026-10-20 起遺失，#313）；在 Developer Console 設定花費上限與警示。
- Apify：建立帳號、設定每月用量上限。
- 新增 secrets `X_BEARER_TOKEN`、`APIFY_TOKEN`。
- 核准候選帳號清單。

## 成本

- X：每次執行最多 30 則 × 0.005 美元 × 每天一次 ≈ 每月 4.5 美元。剩餘額度不足 API 的最小頁（5 則）時不發請求，所以不會超過單次上限。
- 回看視窗用 26 小時，不用 2 天：X 對同一則貼文只在同一個 UTC 日內不重複計費，跨日再讀會再付一次。
- 查帳號 id 每筆 0.010 美元：`x_user_id` 事先填好就是 0。
- 不要求 media 欄位（用不到）。
- 每天輪換起始帳號，避免排在後面的帳號長期讀不到。
- 臉書：10 個粉專 × 每次 5 則 × 30 天 = 最多 1,500 則，約 1.5–3 美元，實際看選用的 actor。
- 合計估計每月 6–8 美元。**程式裡的則數上限只是軟上限；真正的硬上限是 X Developer Console 與 Apify 帳號端設定的花費上限**（M2 人類關卡）。

## 決策紀錄（採建議值）

| 決策 | 取值 | 理由 |
|---|---|---|
| X 方案 | 官方 API | 既有 `tweepy`；條款風險較低 |
| 成本上限 | 每月 10 美元 | 使用者未回覆時採先前提出的建議值 |
| M1 不註冊進排程 | 是 | 最小範圍試做；上線閘門（M3a）必須先於註冊 |
| 試做期回看視窗 | 26 小時 | 不依賴狀態回寫，又不重複付費。M3c 改用 `last_post_id` |
| 社群來源不收純出版紀錄 | 是 | 與上線閘門的地點條件衝突；已有專屬來源 |
| 抓取與 secrets 隔離 | M3b 比照 url-intake 拆 job | 連結由被追蹤帳號決定，屬不可信輸入 |

## Risks（風險）

- **條款**：Meta 條款不分登入與否都禁止未經許可的自動蒐集；免登入抓公開頁是業界常見做法，但不是 Meta 認可的做法，由使用者在 M2 決定是否接受。X 官方 API 的開發者條款可能要求原貼文刪除後同步移除內容並標示出處，M2 讀條款原文確認；若屬實，M6 的稽核加上「原貼文已不存在」的處理。
- **第三方依賴**：Apify actor 可能改版、漲價或下架。抓取層可替換。
- **誤上線**：全自動代表錯誤先出現在網站上，最長兩週後才被稽核看到。相關性閘門只在信心 ≥ 0.8 時停用，邊緣貼文會上線。新活動隔天才進 merger，重複活動至少並存一天。由上線閘門、同來源去重、單帳號上限、來源自動停抓降低，無法歸零。
- **不可信輸入**：貼文與連結頁都是外部內容，連結由被追蹤帳號（包括被盜帳號）決定。`fetch_html` 先檢查 DNS 再連線，中間有 DNS rebinding 的空檔；M3b 把抓取放在不帶 production 憑證的 job。
- **規則式粗篩的誤判**：日期與地點規則會漏判與誤判，命中率要等 M2 的真實資料才知道。
- **未經實測**：M1 的抓取層沒有對真實 API 執行過，連結補資料沒有對真實的報名平台頁面執行過（都需要網路或付費 token）。
