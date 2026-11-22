同一模型家族（Claude）評審，Codex 無法啟動

# Plan Critique 1：social-sources（臉書粉專與 X 帳號）

- 評審對象：`docs/specs/active/social-sources/proposal.md`（v1）、`docs/specs/active/social-sources/tasks.md`
- 工作樹：`/home/claude/tokyo_taiwan_radar/ttr-social-sources-worktree`（feat/social-sources，基於 01d9c14）
- 方式：唯讀。沒有改檔、沒有 commit、沒有讀 `.env`、沒有呼叫付費 API。只查了 X 官方文件的公開價格頁。
- 本次批評與 Architect 用的是同一模型家族，不算取得不同模型的第二視角。

## 摘要

方向對：小型主辦單位只在社群公告活動，這是真實的覆蓋缺口，對應商業主軸第 1 項「資料完整性」。但計畫對既有管線有幾個假設和程式碼不符，其中三個若照原樣做下去，會讓錯誤資料上線或讓官方活動被停用：

1. merger 優先序 90 會讓社群貼文在 Pass 1 壓過大多數官方來源（F1）。
2. `candidate`／`researched` 這兩個狀態會被 auto-research 與 auto-generate 自動接手處理（F5）。
3. 上線閘門的判斷規則會誤殺進行中的展覽與純出版紀錄（F18）。

M1 本身（純函式庫加測試，不註冊、不寫 DB）可以做，但要先修正 F10、F13、F20、F21、F23 這幾項 M1 範圍內的設計。總評：**修訂後實作**。

另外觀察到：worktree 裡已經有未追蹤的實作草稿（`scraper/social/{models,targets,filters,enrich,pipeline,x_backend,facebook_backend}.py`、`scraper/social_dryrun.py`，共約 1,200 行），評審前就開始寫了。下文有幾條發現直接對照這些草稿；Engineer 應把本文當成重工清單。

---

## 一、逐條發現

嚴重度定義：**阻擋**＝不修就不應進到該里程碑；**應修**＝本次修訂必須處理；**建議**＝可以改善，不擋。

### A. merger（檢查項 3）

**F1【阻擋（M3）】優先序 90 會讓社群貼文在 Pass 1 成為主活動，官方活動被停用**
- 證據：
  - `scraper/merger.py` L55-72：`SOURCE_PRIORITY` 只列了 16 個來源。L1039-1040：沒列到的來源預設是 99。
  - `scraper/main.py` L182 起的 `SCRAPERS` 有 123 個 scraper 實例，絕大多數不在表上。
  - Pass 1 只跳過同來源配對（`merger.py` L994-995），**沒有**排除 `_NEWS_SOURCES`；`date_groups` 收所有有 `start_date` 的活動（L625-630）。模組 docstring 說新聞來源「never by name similarity」，但程式碼並沒有這樣做。
  - `url_intake` 就是為了這個原因才設 100（`merger.py` L71 註解：「below every scraper, incl. unlisted ones (default 99)」；`docs/specs/active/url-intake/proposal.md` D2）。
- 後果：社群貼文與一個沒列在表上的官方來源（例如 `tokyo_city_i`、`kokuchpro` 或任何電影院）同日、名稱相似度 ≥0.85 時，社群貼文會變成主活動，官方活動被 `merger_pass_1` 停用。計畫說的「低於所有官方與票務來源」在現行程式碼下不成立。
- 修訂：優先序必須 ≥100。建議 `facebook_pages`、`x_accounts` 設 101，讓經使用者核准的 `url_intake`（100）勝過未經核准的社群貼文。把計畫 D5 的說法改正。

**F2【應修】列入 `_NEWS_SOURCES` 後，Pass 2 的比對條件對「活動公告」過寬，會汙染官方活動**
- 證據：
  - `merger.py` L87：`_PRESS_RELEASE_LOOKBACK_DAYS = 90`。
  - L133-149：`_location_overlap` 只要有一個 ≥2 字的 token 相同就算重疊。
  - L1133-1141：新聞來源只和非新聞來源配對。
  - L1213-1222：次活動的 `raw_description` 會接到主活動後面，並把主活動設回 `pending` 重新標註。
- 後果：Pass 2 原本是為新聞稿設計的（標題是報導體，配不上名稱）。社群貼文是活動公告，主辦單位常在同一場地（例如台湾文化センター）辦多場活動。只要 A 活動的貼文落在 B 活動開始前 90 天內、場地 token 相同，A 就會被吸進 B 並停用，A 的文字接進 B，B 用錯誤內容重新標註。這是對官方活動的資料汙染。
- 修訂：M3 先用 M2 的資料跑 `run_merger(dry_run=True)`，在兩案之間取捨並把數據寫進 `notes.md`：
  - (a) 不列入 `_NEWS_SOURCES`，只走 Pass 1；
  - (b) 列入，但比照 work_id guard（L1163-1170）要求名稱相似度下限（例如 ≥0.6）。

  計畫不應在沒有數據時直接決定「列入」。

**F3【應修】同帳號重複貼文、同一單位臉書與 X 同時發文，都會產生重複活動上線**
- 證據：
  - 每則貼文各自一個 `source_id`（D5）。
  - Pass 1 跳過同來源配對（L994-995）。
  - Pass 1.5 的同來源去重只對 `iwafu` 生效（`_WITHIN_SOURCE_DEDUP_SOURCES`，L83；L836-840）。
  - 臉書和 X 是兩個 source_name，又都是新聞來源，Pass 2 不會讓兩個新聞來源互相配對；Pass 1 則要相似度 ≥0.85 且同一天開始。
- 後果：公告、提醒、「残席わずか」三則貼文就是三筆活動。全自動上線時，這會是最常見的錯誤類型，但計畫完全沒提。
- 修訂：M3 把社群來源加入 `_WITHIN_SOURCE_DEDUP_SOURCES`（先確認 Pass 1.5 的條件適用：同 start/end、排除子活動等）；或改用單一 `source_name = social_posts`，`source_id` 以 `fb_`／`x_` 區分，讓 Pass 1.5 一次涵蓋跨平台。分平台統計可以改用 `source_id` 前綴計算。M8 的盤點指標加上「重複上線筆數」。

**F4【建議】新活動要隔天才進得了 merger**
- 證據：`main.py` L518-525 先跑 merger 再跑 annotator；merger 只載入 `name_ja` 不為空的活動（`merger.py` L619）。scraper 不填 `name_ja`。
- 後果：重複活動至少會在網站上並存一天。`url_intake` 也一樣，可以接受。
- 修訂：寫進 Risks。

### B. research_sources 與周邊程式（檢查項 2）

**F5【阻擋（M2 寫入任何列之前）】`candidate` 會被 auto-research 評分處理，`researched` 會被 auto-generate 拿去生成 scraper**
- 證據：
  - `scraper/auto_scraper/auto_research.py` L3-11（candidate → 依分數改成 researched／recommended／not-viable）、L167-173（條件 `status == 'candidate'` 且 `url_verified`）、L656-662（batch 查詢）。
  - `.github/workflows/auto-research.yml` L5：每週排程，帶 `--batch --create-issue`。
  - `scraper/auto_scraper/generate.py` L179、L856-861：撈 `status = 'researched'`、`url_verified`、可行性 easy／medium 的列，用 GPT-4o 生成 scraper。
- 後果：
  - D1 說新帳號一律以 `candidate` 進表。只要 `url_verified = true`，每週會被 GPT-4o 用 Playwright 開臉書頁面評分，臉書的登入牆大概率導致低分，列被自動改成 `not-viable`，並自動開 issue。
  - D5 的 M6「自動停抓：降回 `researched`」，正好是 `generate.py` 的輸入狀態，會觸發替臉書粉專自動生成 scraper（花 LLM 費用、必定失敗）。
  - 兩者都和使用者想要的流程相反。
- 修訂：
  - (a) 在 M2 寫入第一列之前，`auto_research.py` 與 `generate.py` 的查詢要排除 `agent_category IN ('facebook_page','x_account')`，加一個測試。
  - (b) M6 降級的目標改成不會被任何自動化讀取的狀態（`status` 沒有 CHECK，見 `supabase/migrations/009_research_sources.sql` L11，可以用 `paused`，或用 `not-viable` 加上 reason）。
  - (c) 在 D1 寫明這兩條。

**F6【應修】`implemented` 但沒有 `scraper_source_name` 的列，會讓強制稽核失敗**
- 證據：
  - `scraper/audit_post_build.py` L85-101、L112-121：任何 `implemented` 列缺少 `scraper_source_name` 就 exit 1。
  - `.github/skills/scraper-expert/SKILL.md` L152、L173 把它列為必跑。
  - `.github/skills/scraper-expert/history.md` L82：六筆 `peatix_organizer` 列已經為此補上 `scraper_source_name = peatix`。
  - `scraper/guard_detections.py` L101-102 每月把這種列算成 `implemented_without_scraper_key`。
- 修訂：D1 規定社群列寫入 `scraper_source_name = 'facebook_pages'`／`'x_accounts'`（M3 註冊的 key）。這樣 M3 的 `_ensure_scrapers_registered`（`main.py` L362-369）會看到 key 已存在，不會再插一筆 `url = ''` 的空殼列，正好避開計畫 M1 決策表擔心的雜訊。

**F7【應修】後台分類與計數規則被延到 M4，但 M2 就會寫入新的 `agent_category`**
- 證據：
  - `web/components/AdminSourcesTable.tsx` L296-299：`effectiveTypeOf` 只特判 `peatix_organizer`，其餘看 `display_type`，空的就顯示 other。
  - `.github/skills/agents/engineer/SKILL.md` L1144-1151 是成對檔案規則：寫入新 `agent_category` 的同一個 PR，必須更新 `SOURCE_TYPE_LABELS` 與 `getFilteredSources`；L1153-1168 規定新標籤要三語 i18n。
  - `web/app/[locale]/admin/page.tsx` L156-158 的「已建立爬蟲」數會直接加上 20 個帳號。
  - `scraper/monthly_health_check.py` L577-605 的 approval rate 也會被拉高。
- 修訂：把最小的後台支援（標籤、篩選、三語 key）從 M4 提前到 M2；或規定 M2 寫入的列同時設定 `display_type`，並在 spec 註明計數會被拉高。

**F8【確認＋建議】`agent_category` 確實沒有 CHECK**
- 證據：`009_research_sources.sql` L9 是 `agent_category TEXT`；後續 migration 只對 `display_type`（068、072）和 `default_organizer_type`（039、095）加了 CHECK。計畫「不需要 migration」成立。
- 補充：`url` 有 UNIQUE（009 L8），`facebook.com/x` 和 `www.facebook.com/x` 會被當成兩列。寫入前要正規化 URL（建議統一 `https://www.facebook.com/<handle>`、`https://x.com/<handle>`）。

**F9【建議】`note_creators._load_db_creators` 會讀所有 `implemented` 列**
- 證據：`scraper/sources/note_creators.py` L560-563。它用 URL 過濾，社群列不會誤中，無害。列出來只是讓 M2 知道有這個讀取者。

### C. 沿用 ingest_url（檢查項 1）

**F10【應修】`extract_page` 會丟掉 JSON-LD 與 meta description，而報名平台的資料多半就在那裡**
- 證據：`scraper/ingest_url.py` L60 的 `_STRIP_TAGS` 含 `script`，L218-219 會移除這些標籤（所以 `application/ld+json` 被移除）；L209-211 只保留 `og:title`，不保留 `og:description`。
- 後果：D4 把 Peatix、connpass、Eventbrite 等報名平台排在最前面。這類頁面正文常靠 JS 渲染，但伺服器回傳的 HTML 通常帶有 schema.org `Event` JSON-LD（startDate、location）與 `og:description`。照現行抽取方式，最有價值的部分會被丟掉，留下的正文可能很短。
- 修訂：在 `scraper/social/enrich.py` 呼叫 `extract_page` 之前，先自己解析 `@type: Event` 的 JSON-LD 和 `og:description`／`meta[name=description]`，放在頁面文字最前面。不改 `ingest_url`，避免影響 url-intake。
- 未驗證：我在沙箱裡用 `fetch_html` 抓 Peatix 時遇到 `cannot resolve host peatix.com`，沒能實測。M2 第一步要存下 Peatix、LivePocket、eplus、teket 的真實 HTML 當 fixture。

**F11【應修】只用 requests，沒寫明預期的失敗類型**
- 證據：`scraper/sources/peatix.py` L16、L532 用 Playwright；url-intake 明確不做 Playwright（`docs/specs/active/url-intake/proposal.md` L40、L108）。
- 修訂：D4 寫明「JS 渲染頁與擋機器人的網站預期抓不到」。`RunReport` 依網域統計補資料的成功與失敗，放進 M2 報告，再決定要不要補 Playwright 或擴充 F10 的結構化抽取。

**F12【建議】`MIN_BODY_LEN` 不會自動套用**
- 證據：`ingest_url.py` 的 `MIN_BODY_LEN`（L47）只在 `validate_payload`（L246-247）檢查，`extract_page` 不會因正文太短而報錯。草稿另設 `MIN_PAGE_CHARS = 80`。
- 修訂：計畫的「沿用 ingest_url」要寫清楚沿用哪些門檻（2 MB、5 跳轉址、20 秒 timeout），以及哪些是另設的（80 字、3,000 字）。

**F13【應修】臉書外連包裝網址會被整批丟掉**
- 證據：`normalize_url`（`ingest_url.py` L73-104）不會解開 `l.facebook.com/l.php?u=…`。草稿 `enrich.py` L29-33 的 `_SKIP_HOSTS` 用後綴比對，所有 `*.facebook.com` 都被排除。
- 後果：Apify 回傳或貼文內文裡的外連若是包裝過的網址，補資料這一步在臉書上等於沒做。
- 修訂：D4 加一步：先從 `l.facebook.com`／`lm.facebook.com` 的 `u` 參數解出真正網址，再正規化。加 fixture 測試。X 的 `t.co` 已經由 API 的 expanded_url 處理，但要對 t.co 原網址與展開網址做去重，免得浪費每則 2＋1 次的抓取額度。

**F14【應修】縱深防禦比 url-intake 弱，計畫沒有說明**
- 證據：
  - url-intake 刻意把抓頁面放在沒有任何 secret 的 job（`docs/specs/active/url-intake/proposal.md` D3「fetch job：沒有任何 secret 或 token」）。
  - 社群來源在 M3 會在 `scraper.yml` 內抓網址，而那個 job 持有 production 的 service role key 與 LLM key。
  - `fetch_html` 先解析 DNS 檢查（L152），再由 requests 重新解析並連線（L154），存在 DNS rebinding 的空檔。
  - 既有 scraper 抓的是固定網站；這裡的網址由任何被追蹤帳號（包括被盜帳號）決定。
- 修訂：Risks 明列這是已知殘餘風險，並二擇一：
  - (a) M3 比照 url-intake，把社群抓取拆成無 secrets 的 job，產出 artifact；
  - (b) 接受風險，另開 issue 追蹤「連線時固定已驗證 IP」。

### D. annotator 與注入掃描（檢查項 4）

**F15【確認】「相關性閘門不豁免」與現行做法一致**
- 證據：`scraper/annotator.py` L2441-2446、L2530：只有經人工把關的 `user_submission`、`url_intake` 豁免。社群貼文沒有逐則核准，不豁免是對的。
- 補充：閘門只在 `confidence ≥ 0.8`（L2441）時才停用，信心不足的邊緣貼文會上線。這要寫進「誤上線」風險，M8 盤點時分開統計。

**F16【應修】「嚴重度 ≥2 丟棄」與現行政策相反，計畫沒有說明這是刻意的例外**
- 證據：
  - `scraper/security/injection_guard.py` L6-9：「legitimate event data is NEVER dropped or mutated by this module — detection only」。
  - `annotator.py` L3250-3264：命中只寫進 `event_reports`，活動照常標註。
  - 草稿 `enrich.py` 對連結頁命中時只丟掉該頁、保留貼文，和計畫 D3「丟棄」不一致。
- 修訂：在全自動上線的前提下，丟棄是合理的，但 spec 要：
  - (a) 寫明這是對 v16 政策的刻意例外與理由；
  - (b) 被丟棄的貼文進稽核報表時要帶片段與原文連結，不能只有計數；
  - (c) 寫明 `SECURITY_SCAN_DISABLED`（`injection_guard.py` L17-19）也會關掉這道丟棄；
  - (d) 統一「貼文命中」和「連結頁命中」各自怎麼處理。

**F17【應修】年份錨點應沿用現行的 `記事配信日:` 慣例**
- 證據：`annotator.py` L3212-3233：只要 `raw_description` 沒有 `記事配信日:`，就用 `scraped_at` 當年份錨點插在最前面。計畫 D5 用的是自創的 `投稿日` 標籤。
- 後果：回看 2 天時影響很小。但 M3 改用 `last_post_id` 後的第一次執行、或之後補抓舊貼文時，`scraped_at` 不等於發文日，annotator 會拿錯的年份推日期。
- 修訂：`raw_description` 第一行寫 `記事配信日: <發文日，JST>`，annotator 就不會再插 `scraped_at`。`投稿元`、`投稿者` 保留。

### E. 日期、上線閘門與誤判（檢查項 5）

**F18【阻擋（M3）】上線閘門的規則本身會誤殺**
- 證據與後果：
  - (a)「`start_date` 已過即停用」會殺掉進行中的展覽。網站用的是 `end_date`：`web/app/[locale]/categories/[category]/page.tsx` L209 是 `.or(end_date.gte.today, end_date.is.null)`。
  - (b)「沒有地點即停用」會殺掉純出版紀錄。依 `.github/instructions/scraper.instructions.md` 的 Publication Policy Invariant 與 `docs/specs/active/publication-policy/proposal.md`，`event_form == ['publication']` 的紀錄地點刻意為空。社群上的新刊公告很常見。
  - (c) 閘門必須寫在把 `annotation_status` 設為 `annotated` 的同一次 update。公開頁只顯示 `annotated`／`reviewed`（`web/app/[locale]/page.tsx` L60），分成兩次寫入就會有一段時間誤上線。
  - (d) 被停用的列之後重抓也不會恢復（`scraper/database.py` L872、L966-967），要寫明。
- 修訂：判斷條件改成 `COALESCE(end_date, start_date) < today` 或為空；純出版紀錄豁免地點條件，或在 Non-Goals 寫明社群來源不收出版紀錄（此時閘門要把出版紀錄停用，原因另記）。

**F19【應修】要把「閘門先上、或與註冊同時上」寫成不變條件**
- 證據：現行管線不會停用沒有日期的活動。`scraper/auto_qa.py` L746-756 的 `auto_qa_missing_date` 只標記待審；F18 的網站查詢把 `end_date` 為空的活動當成現行活動顯示。
- 判斷：計畫把閘門和註冊放在同一個 M3，所以沒有空窗。但 M3 很大（見 F26），一旦拆 PR，就可能先註冊、後上閘門。
- 修訂：D6 加一條不變條件：「`SCRAPERS` 註冊的 PR 必須已包含（或晚於）閘門，並附閘門測試」。

**F20【應修】D3 規則式日期偵測的明顯誤判情境**
- 年份推定方向錯誤：
  - 計畫寫「推定最近的未來日期」。但 repo 規則是「accept dates up to 180 days before publish date (covers レポート/recap articles)」（`.github/instructions/scraper.instructions.md` L33）。草稿只往回看 30 天（`filters.py` L32、L72-80）。
  - 例：1 月 5 日發的「12月20日に開催しました」會被推成**下一年**的 12 月 20 日，變成未來日期。回顧判斷只在「沒有未來日期」時才生效，所以這則會被當成未來活動送下去。
  - 修訂：取發文日前 180 天到後 185 天內最接近的那一年；有星期標記（`(土)`）時，用星期驗證年份。
- 報名截止日、發售日、受付開始日被當成活動日期：例如 `申込締切 12月10日`、`11月20日発売`、`12月1日より予約開始`。計畫說這一層只是粗篩，沒錯；但 D3 第 6 步判為「完整」時就不補資料，等於帶著錯的日期線索直接進 annotator。
  - 修訂：(a) 緊鄰 `締切|〆切|発売|予約開始|受付開始|まで` 的日期標成非活動日期；(b) 只要有連結就補資料，「完整」只用來決定「沒有連結時算不算資料不足」。HTTP 抓取不花錢。
- 地點訊號過寬：
  - 草稿 `filters.py` L60 的 `[＠@]\s*[^\s@＠]{2,}` 會命中 X 上每一個 @mention 和 email。都道府縣名也會命中單位名稱（例如「東京台湾の会」）。結果是「完整」比例被高估。
  - 修訂：`＠` 只在接場地類詞或出現在行首時才算；都道府縣名要搭配 `市|区|町|村|会場` 等上下文。
- 時區：草稿 `filters.py` L90 用 `posted_at.date()`，`created_at` 是 UTC，接近午夜的貼文會差一天。要先轉成 Asia/Tokyo。
- 可接受、但要寫進 spec 的漏抓：`12月5日〜7日` 抓不到第二個日期；`12/5` 沒有星期標記會被忽略。

### F. 成本（檢查項 6）

**F21【應修】成本算術與上限不自洽，每月 10 美元沒有任何機制保證**
- 單次上限：60 則 × 0.005 美元 = 每次 0.30 美元；`scraper.yml` 每天跑一次（L6，`0 0 * * *`），每月 9.0～9.3 美元。D2 的「約 9 美元」算對了，但決策表寫「每月約 5 美元」，自相矛盾。
- 回看 2 天會重複付費：X 官方文件說，同一則貼文只在同一個 UTC 日內不重複計費，隔天再讀要再付一次（[X API pricing](https://docs.x.com/x-api/getting-started/pricing.md)、[How billing works](https://docs.x.com/x-api/fundamentals/post-cap.md)）。排程在 00:00 UTC，每次執行都在不同的 UTC 日，所以每則貼文會付兩次。
- 查帳號 id 不是免費的：同一份價格頁列 user lookup 每筆 0.010 美元。M1／M2 不回寫 `x_user_id`，10 個帳號每次執行要 0.10 美元，每月約 3 美元。
- `expansions=attachments.media_keys`（草稿 `x_backend.py` L179）：Non-Goals 說不存圖片，`image_urls` 也沒有用到；官方文件沒說 expansion 怎麼計費，應拿掉。
- 單次上限會被超過：`max_results` 最少是 5（`x_backend.py` L22、L176），剩餘額度不到 5 時，最多會多讀 4 則。
- 帳號被餓死：固定順序加上 60 則上限，排在後面的帳號長期讀不到。要每天輪換起點。
- 臉書：10 個粉專 × 5 則 × 30 天 = 1,500 則／月。依計畫自己的單價（每千則 1～2 美元）是 1.5～3 美元；回看 2 天同樣會重複付費。Apify 免費額度能不能涵蓋，要看實際選用的 actor。
- 最壞合計：X 9.3＋查帳號 3＋臉書 3 ≈ 15 美元，超過 10 美元。
- 修訂：
  - (1) 試做期改用 `start_time = now − 26h`（草稿已支援 `start_time`／`since_id`，`x_backend.py` L184-186），不用 2 天；
  - (2) 依月預算反推單次上限，例如 X 每次 30 則約 4.5 美元／月；
  - (3) M2 的人類關卡卡片要包含：在 X Developer Console 設定花費上限與警示、在 Apify 設定每月用量上限（這是唯一真正的硬上限）、事先填好 `x_user_id`；
  - (4) 修正決策表的數字。

**F22【應修】「已有 X 開發者帳號」這個前提沒有驗證**
- 證據：`tweepy` 確實在 `scraper/requirements.txt` L15。但 `.github/workflows/x-post-cron.yml` L3-6 寫著：2026-10-20 起四個 `X_*` secret 遺失（#313），排程已暫停。
- 風險：pay-per-use 是預付額度，用完後請求會失敗（[How billing works](https://docs.x.com/x-api/fundamentals/post-cap.md)）。讀取和發文若共用同一個 app 的額度，讀取花光額度後，將來 TTR 自己發文也會失敗。
- 修訂：M2 卡片列出以下確認事項：帳號已加入 pay-per-use 並儲值、讀取和發文用同一個 app 還是分開、Bearer token 要另存成 secret 還是從既有 consumer key 換取。

### G. M1 範圍（檢查項 7）

**F23【應修】M1 的臉書 backend 是建立在猜測上的**
- 證據：D2 說「多個 actor 共用 `startUrls`／`resultsLimit`／`onlyPostsNewerThan` 輸入與 `postId`／`url`／`time`／`text` 輸出」，這沒有驗證。Apify 上有很多不同作者的「Facebook Posts Scraper」，各自定義輸入與輸出（例：[alfalfa/facebook-posts-scraper](https://apify.com/alfalfa/facebook-posts-scraper)、[axesso_data/facebook-posts-scraper](https://apify.com/axesso_data/facebook-posts-scraper/pricing)、[danek/facebook-pages-posts-ppr](https://apify.com/danek/facebook-pages-posts-ppr)）。用猜出來的格式寫 fixture 測試，只會給出錯誤的信心。
- 修訂：M1 的臉書 backend 只做介面與 `BackendUnavailable`；轉換函式等 M2 拿到第一份真實回應再寫，或把 fixture 明確標成「合成資料」。X v2 的回應格式有官方文件，可以留在 M1。

**F24【建議】用零成本的方式先驗證前提**
- 修訂：
  - (a) M1 的 D3 測試 fixture 改用使用者實際看過的貼文全文（手動複製，不花錢），比自己編的句子更能調出規則；
  - (b) M2 花錢之前，先列出 10＋10 個候選帳號，人工數一下過去一個月有幾則活動貼文。若臉書命中太少，就只做 X，條款與第三方風險同時下降。

**F25【建議】`APIFY_FACEBOOK_ACTOR` 的環境變數覆寫是沒必要的抽象，也是供應鏈風險**
- 證據：D2；草稿 `facebook_backend.py` L25。
- 後果：任何人改了這個變數，就能讓任意第三方 actor 拿著你的 Apify token 執行，費用也記在你的帳號上。
- 修訂：actor ID 與 build tag 寫死在程式碼裡，換 actor 要走 PR。

**F26【建議】M3 太大**
- 證據：D6 的 M3 同時包含註冊、merger 優先序、閘門、`last_post_id` 回寫與 `source_expectations.json`，全部在一個 Tier 2 PR。
- 修訂：拆成三個：
  - M3a：閘門與 merger 調整（不需要新資料，可以單獨測）；
  - M3b：註冊、`source_expectations.json`、`ZERO_EVENT_OK_SOURCES` 的決定；
  - M3c：`last_post_id` 回寫，必須在 upsert 成功之後才寫，否則中途失敗會漏讀。

**F27【應修】M2「真實資料 dry-run 兩週」沒寫在哪裡跑、怎麼量**
- 問題：如果是使用者每天在本機跑，違反「本人只做稽核」；如果在 Actions 跑，就需要一個新 workflow（`.github/**`，Tier 2）加上 secrets（人類關卡），計畫都沒寫。「命中率」也沒有定義。
- 修訂：
  - 寫明新增 `social-dryrun.yml`：每天排程，只帶 `X_BEARER_TOKEN`／`APIFY_TOKEN`；抓取對象改從 repo 內的 JSON 清單讀，避免 dry-run 還要拿 production 憑證；不寫 DB。
  - 指標定義為：讀取則數、各原因的丟棄數、各網域的補資料成功率、產出 Event 數、人工抽 30 筆算出的正確率。

**F28【應修】`BackendUnavailable` 一律回傳空結果，會把真正的故障藏起來**
- 證據：D2；`scraper/health_check.py` L64 的 `ZERO_EVENT_OK_SOURCES`；計畫 M3 只提到 `source_expectations.json`。
- 後果：「沒設定 token」和「token 失效或額度用完（402／429）」看起來一模一樣。
- 修訂：分成兩種情況。沒設定時記 info 並跳過；有設定但失敗時要拋出，記成 `scraper_runs` 的錯誤。M3 決定是否列入 `ZERO_EVENT_OK_SOURCES`。

### H. 與既有 spec 與治理規則的衝突（檢查項 8）

**F29【應修】與既有 spec 的對照**
- `url-intake`：
  - 優先序（F1）；
  - 抓取與 secrets 隔離（F14）；
  - url-intake 的相關性閘門豁免以「使用者核准」為前提，社群來源不豁免是正確的（F15）；
  - 沿用 `ingest_url` 的函式後，日後改 url-intake 的常數會同時影響社群來源。建議另開 issue，把 `normalize_url`／`fetch_html` 抽成共用模組。
- `autoresearch-auto-scraper`：F5，衝突最嚴重。
- `publication-policy`：F18(b)。
- `agent-autonomy`（人類關卡）：
  - 計畫列了 secrets、花錢、寫入 `research_sources`，但漏了三項：(i) M2 的新 workflow 本身（F27）；(ii) 接受 Meta 條款風險是一項需要使用者判斷的決定（F33）；(iii) 在 Developer Console 與 Apify 設定花費上限（F21）。
  - 另外，`docs/specs/active/agent-autonomy/proposal.md` L161 的 D3「證據門檻自動合併」依賴 `pr-dryrun-evidence` 呈現「修復前 0、修復後 >0」。社群來源在沒有 secrets 的 dry-run 裡永遠是 0，M3 的 PR 要寫成 NOT TESTED 並附具體原因。

**F30【建議】計畫沒有標每個 phase 的建議模型**
- 證據：`AGENTS.md`「模型政策」要求計畫文件的每個 phase 標明建議模型。
- 修訂：例如 M1／M3 實作用 Sonnet medium，M3 的 merger 與閘門設計評審用 Opus high。

**F31【建議】追蹤方式**
- 修訂：本文的發現應由 Architect 依 `AGENTS.md`「進度追蹤」開成 issue，貼 `spec:social-sources` label，不寫進 `tasks.md`。我在這個環境用不了 `gh`，沒能查現有的 open issue。

### I. 條款與安全（檢查項 9）

**F32【應修，需查證】「X 走官方 API 沒有條款問題」說過頭了**
- 問題：X 的開發者條款一般要求，用 API 取得的內容在原貼文刪除或轉為非公開後，也要跟著移除（content compliance），並要標示出處。計畫沒有處理刪文同步。我沒有在這次評審中讀到條款原文，所以列為需查證。
- 修訂：M2 先讀條款原文確認。若屬實，M6 的稽核加上「原貼文已不存在」的處理；不要每天重新查（會花錢），可以在稽核時抽查，並保留人工下架流程。

**F33【應修】Meta 條款風險有寫，但沒有寫由誰承擔、何時決定**
- 修訂：把「使用者明確接受以免登入方式抓公開粉專的條款風險」列進 M2 的人類關卡卡片。同時寫明 Apify 是新的外部服務與帳號，會把追蹤的粉專清單交給第三方。

**F34【建議】帳號被盜時的影響範圍**
- 問題：全自動上線時，一個被盜或被冒用的帳號可以在一天內灌進很多筆活動。
- 修訂：同一帳號每天產生超過 N 筆活動（例如 5 筆）時，超出的部分不上線，留給稽核。和 M6 的自動停抓搭配使用。

**F35【建議】臉書 `source_id` 的穩定性**
- 問題：臉書貼文網址有數字 id 與 `pfbid…` 兩種形式，不同 actor 或不同時間可能給出不同形式，`fb_<postId>` 會跟著變，造成重複活動。
- 修訂：優先用數字 id；沒有時用正規化後永久連結的雜湊。加測試。

---

## 二、Plan Critic 固定六段

### 1. 商業主軸對齊
- 對應目標：主軸 1「爬蟲覆蓋率／資料完整性」。專案地理範圍是全日本，社群來源不分地區，符合使命。
- 評分：**綠（對齊）**。全自動上線帶來的誤上線風險，則和主軸 1 的「正確性」直接衝突，需要靠 F1、F3、F18 守住。

### 2. 複雜度 vs 價值
- 複雜度：**high**。依 SKILL 的啟發式：跨 3 個以上檔案（+1）、觸發既有 Guard（SCRAPERS 完整性、AdminSourcesTable 成對檔案規則、Publication Policy Invariant，+1）、新外部服務與花費（+1）、M3 改 merger 的優先序與來源分類（高回歸風險，+1～2）。8 個里程碑；M1 草稿已有約 1,200 行；M2 新增 2 個 secrets 和 1 個 workflow；不需要 migration。
- 價值：**medium-high**。新增覆蓋範圍，但命中率未知，M2 之前無法確認。
- 比值警示：M1～M3 的複雜度和目前已證實的價值相比偏高。在 F24 的零成本驗證完成前，不應投入臉書那一線。

### 3. 優先順序提醒（Anti-Rabbit-Hole）
- 評分：**黃（可以做，但要先砍範圍）**。
- 理由：url-intake 剛上線（01d9c14），它已經能處理使用者手上看到的單筆貼文。計畫應先證明社群來源每月能多出多少筆 url-intake 沒涵蓋的活動，再決定做不做臉書。X 那一線條款風險低，建議先做。
- 我無法讀取 GitHub issue，沒能比對目前更高優先的爬蟲故障清單。

### 4. 全站架構整合
- 觸發的 Guard：
  - SCRAPERS List Completeness／Auto-Generate Promotion Checklist（F6）；
  - AdminSourcesTable `agent_category` 成對檔案規則與 i18n 規則（F7）；
  - Publication Policy Invariant（F18）；
  - Scraper 日期規則中的 180 天回推（F20）；
  - annotator 的年份錨點慣例（F17）。
- 漏掉的同步點：`auto_research.py`／`generate.py` 的篩選（F5）、`audit_post_build.py`（F6）、`guard_detections.py`（F6）、`health_check.ZERO_EVENT_OK_SOURCES`（F28）、`_WITHIN_SOURCE_DEDUP_SOURCES`（F3）。

### 5. 既有元件復用
- 已復用：`ingest_url.normalize_url`／`fetch_html`／`extract_page`、`security.injection_guard`、`_load_db_organizers` 的讀取模式、`Event` 與 `upsert_events`、merger、annotator 閘門。
- 應再復用：
  - 年份錨點用 `記事配信日:`（`annotator.py` L3212-3233）；
  - merger Pass 1.5 的同來源去重（`merger.py` L836 起）；
  - `scraper_source_name` 慣例（比照 peatix_organizer，F6）；
  - `source_expectations.json` 與 `ZERO_EVENT_OK_SOURCES`。
- 不應新增的：`APIFY_FACEBOOK_ACTOR` 覆寫機制（F25）。
- 評分：**黃（部分新增）**。抓取層非新增不可，可以接受；去重與狀態語意應該復用既有機制，不要另起爐灶。

### 6. 建議更新後的計畫（只列要改的地方，不重寫）
1. D5／M3：優先序改為 101（F1）；`_NEWS_SOURCES` 列不列入，等 M2 資料跑 merger dry-run 後再決定（F2）；加入同來源去重（F3）。
2. D1：社群列寫入 `scraper_source_name`（F6）、正規化 URL（F8）；寫明 auto-research／auto-generate 要排除社群列，且這個排除在 M2 寫入第一列之前完成（F5）；M6 降級的目標狀態改成不會被自動化讀取的狀態（F5）。
3. M2 範圍加入：後台最小支援（F7）；`social-dryrun.yml` 與指標定義（F27）；人類關卡卡片的完整清單（secrets、儲值、花費上限、`x_user_id`、Meta 條款風險、Apify 帳號，見 F21、F22、F33）。
4. D3：年份推定改為前後 180 天內最接近的年份（F20）；過濾截止日與發售日（F20）；收緊地點訊號（F20）；有連結就補資料（F20）；用 JST（F20）。
5. D4：解開臉書包裝網址（F13）；加上 JSON-LD 與 og:description 抽取（F10）；按網域統計失敗（F11）；寫明 secrets 隔離的取捨（F14）。
6. D5 閘門：改用 `COALESCE(end_date, start_date)`、處理純出版紀錄、與標註狀態同一次寫入（F18）；加上「閘門先於或同時於註冊」的不變條件（F19）；`記事配信日` 錨點（F17）。
7. 成本：修正決策表數字；試做期改用 26 小時窗；移除 media expansion；每天輪換帳號起點；把硬上限改由平台端設定（F21）。
8. M1：臉書轉換函式延到 M2，或明確標成合成 fixture（F23）；actor ID 寫死（F25）；D3 用真實貼文當 fixture（F24）。
9. M3 拆成 M3a／M3b／M3c（F26）；區分「沒設定」與「設定了但失敗」（F28）。
10. 注入掃描的刻意例外寫進 spec，並統一貼文命中與連結頁命中的處理（F16）；補上 X 刪文同步（F32，先查證）；單一帳號每日產出上限（F34）；臉書 `source_id` 規則（F35）；每個 phase 標建議模型（F30）。

---

## 三、總評

**修訂後實作。**

- M1（純函式庫加測試、不註冊、不寫 DB、不花錢）的方向可以保留。照第六段第 4、5、8 點修完後，就可以交 Engineer。worktree 裡的草稿至少要改 `filters.py`（年份推定、地點訊號、時區）、`enrich.py`（臉書包裝網址、JSON-LD）、`x_backend.py`（移除 media expansion、輪換起點），臉書轉換函式則依 F23 處理。
- F5 必須在 M2 寫入任何 `research_sources` 列之前解決；F1、F18 必須在 M3 註冊之前解決。三者都應現在就寫進 spec，免得 M1 的程式碼把錯誤的假設固定下來。
- 本次沒能驗證的事項：用 requests 抓 Peatix 等報名平台頁面的實際效果（沙箱無法解析 DNS）；Apify actor 的實際輸入輸出格式；X 開發者條款中刪文同步的原文；目前 GitHub 上的 open issue（無法使用 `gh`）。

## 四、建議下一步

- **回 Architect 修改計畫**（建議模型 Opus high）：請 Architect 根據本文（存成 `docs/specs/active/social-sources/plan-critique-1.md` 後）修改 `docs/specs/active/social-sources/proposal.md` 與 `tasks.md`，回傳修訂後全文，並把各發現開成 `spec:social-sources` issue。
- 修訂完成後再交 Engineer 做 M1（建議模型 Sonnet medium）。

## 五、可能值得記住的事項（給主 session 決定要不要存）

- X API 現在是 pay-per-use：讀一則貼文 0.005 美元、查一筆帳號 0.010 美元、同一資源只在同一個 UTC 日內不重複計費、額度預付。出處：X 官方價格頁（[pricing](https://docs.x.com/x-api/getting-started/pricing.md)、[billing](https://docs.x.com/x-api/fundamentals/post-cap.md)）。
- TTR 的 `x-post-cron.yml` 從 2026-10-20 起因 `X_*` secrets 遺失（#313）而暫停排程。出處：該 workflow 檔頭的註解。
- 本次評審沒有用到使用者記憶。

---

## 處理結果（Architect 於 2026-11-22 補記，非評審原文）

| 發現 | 處理 | 落點 |
|---|---|---|
| F1 優先序 | 採納：101 | proposal v2 D5；M3a |
| F2 `_NEWS_SOURCES` | 採納：等 M2 資料跑 merger dry-run 再決定 | proposal v2 D5；issue |
| F3 重複貼文 | 採納：M3a 加入同來源去重；M8 指標加「重複上線筆數」 | proposal v2 D5；issue |
| F4 隔天才進 merger | 採納：寫入 Risks | proposal v2 |
| F5 auto-research／auto-generate | 採納：M2 寫入第一列之前排除社群列；停抓狀態改 `paused` | proposal v2 D1；issue |
| F6 `scraper_source_name` | 採納 | proposal v2 D1 |
| F7 後台最小支援 | 採納：提前到 M2 | proposal v2 D6；issue |
| F8 URL 正規化 | 採納：`SocialTarget.profile_url` 即正規形式，M2 寫入時使用 | proposal v2 D1 |
| F9 | 知悉，無動作 | — |
| F10 JSON-LD／og:description | 採納：本 PR 實作 | `social/enrich.py` |
| F11 依網域統計 | 採納：本 PR 實作 | `RunReport.link_stats` |
| F12 門檻說明 | 採納 | proposal v2 D4 |
| F13 臉書包裝網址 | 採納：本 PR 實作 | `social/enrich.py` |
| F14 secrets 隔離 | 採納 (a)：M3 的抓取 job 不帶 production 憑證 | proposal v2 D6；issue |
| F15 | 確認；邊緣貼文風險寫入 Risks | proposal v2 |
| F16 注入掃描例外 | 採納：寫明例外；被丟棄貼文留連結；本 PR 實作 | proposal v2 D3；`RunReport.flagged` |
| F17 `記事配信日` | 採納：本 PR 實作 | `social/pipeline.py` |
| F18 上線閘門規則 | 採納：`COALESCE(end_date, start_date)`；社群來源不收純出版紀錄 | proposal v2 D5、Non-Goals；M3a |
| F19 不變條件 | 採納 | proposal v2 D6 |
| F20 日期與地點規則 | 採納：本 PR 實作（年份推定、星期驗證、截止日排除、地點收緊、JST、有連結就補資料） | `social/filters.py` |
| F21 成本 | 採納：26 小時窗、每次 30 則、不足 5 則不發請求、每日輪換、移除 media expansion；硬上限由平台端設定 | `social/x_backend.py`；proposal v2 |
| F22 X 帳號前提 | 採納：列入 M2 卡片 | proposal v2 D6；issue |
| F23 臉書轉換函式 | 部分採納：保留轉換函式，fixture 明確標為合成資料；欄位依據是多個 actor 的公開文件，M2 以真實回應取代 | `social/facebook_backend.py`、測試 |
| F24 零成本驗證 | 採納 (b)：列為 M2 第一步；(a) 真實貼文 fixture 需使用者提供，開 issue | proposal v2 D6；issue |
| F25 actor 覆寫 | 採納：寫死，移除環境變數 | `social/facebook_backend.py` |
| F26 M3 拆分 | 採納 | tasks.md |
| F27 M2 怎麼跑 | 採納：`social-dryrun.yml` 與指標定義 | proposal v2 D6；issue |
| F28 沒設定與失敗分開 | 採納：本 PR 實作 | `RunReport.skipped`／`errors` |
| F29 | 採納各子項；共用模組抽取開 issue | issue |
| F30 建議模型 | 採納 | proposal v2 D6 |
| F31 | 採納：開 issue | PR 說明 |
| F32 X 刪文同步 | 採納：M2 查證條款原文 | proposal v2 Risks；issue |
| F33 Meta 條款由誰決定 | 採納：列入 M2 人類關卡 | proposal v2 D6 |
| F34 單一帳號每日上限 | 採納：本 PR 實作（每帳號每次 5 筆） | `social/pipeline.py` |
| F35 臉書 `source_id` | 採納：本 PR 實作 | `social/facebook_backend.py` |
| 「評審前就開始寫草稿」 | 屬實。草稿依本表重工後才 commit | — |
