---
slug: llm-cost-reset
title: OpenAI 成本重整：修掉失效呼叫者、讓錯誤現形、帳本對齊 dashboard
status: active
branch: feat/llm-cost-reset
created: 2026-10-22
tags: [scraper, web, infra, cost]
---

## What（做什麼）

把 OpenAI 的使用整理成「每次呼叫都有紀錄、錯誤會讓步驟失敗、只花在有產出的地方」。範圍是看板「成本」階段的 #317～#323、#360～#363，依下列順序執行：

1. #318 處理 `gpt-4o-search-preview` 下架後的四個呼叫者
2. #319 LLM 錯誤變成步驟失敗，健康檢查改看產出量
3. 帳本修準：#363 共用用量紀錄，加上 #322 分頁與限流、#320 分帳
4. #317 修好 enrich_poster 再恢復每日執行（2026-10-23 結果：dry-run 沒有正確寫入，退役）
5. #360、#321、#361
6. #323 移除 DeepL
7. #362 annotator 重標注成本

## Why（為什麼）

- 週報約低估四倍。`scraper_runs.cost_usd` 只涵蓋 annotator 與 researcher，月加總又被 1000 筆上限截斷。成本以 OpenAI dashboard 為準（project「Tokyo Taiwan Radar」）。
- 2026-08-20 前後 `gpt-4o-search-preview` 下架，四個呼叫者回 404，錯誤被 `except Exception` 吞掉，workflow 仍顯示成功。researcher 9～10 月共 159 次執行，產出 0。
- 目前主要支出是 enrich_poster 的 gpt-4o（每天約 65 張海報，10-16～10-21 寫入 0 筆，已暫停）。
- 證據與數字見 `notes.md`。

## Non-Goals（不做什麼）

- 不換 LLM 供應商，不改 annotator 的標注品質或 prompt 內容（#362 只動「什麼時候重標」與 prompt 排列）。
- 不做即時成本告警或自動斷路器；本 spec 只讓成本「看得見、對得上」。
- 不刪 GitHub／Vercel secret 本身。#323 的 `DEEPL_API_KEY`、#320 的舊 key 由使用者決定何時刪。
- 不處理 #325 地點三段 eval；本 spec 只以唯讀方式呼叫 `venue_registry.lookup_venue_for_location`。
- `_oneoff_*.py` 一次性腳本不遷移到共用 client，維持原樣（不在排程內）。

## Design（設計摘要）

### D1. #318 四個呼叫者的去留（已決定）

| 呼叫者 | 結論 | 理由 |
| --- | --- | --- |
| `scraper/researcher.py` + `researcher.yml` | **移除**，連同 cron、測試與文件中的引用 | 2026-07 花 $30.02、2026-08 花 $19.57；researcher 類別自 2026-06 起只有 3 筆來源走到 `implemented`。另有 `auto_scraper/auto_research.py` 每週一次的發掘管線。`research_sources` 表與 admin 頁保留。 |
| `scraper/discovery_accounts.py` + `discovery-accounts.yml` | **移除** | `note_creator` 與 `peatix_organizer` 的 `implemented` 只出現在 2026-04-29～05-15（共 10 筆），之後沒有；最後一筆 candidate 是 2026-07-20。 |
| `qa_auto_fix._search_venue_homepage_openai` | **移除這個備援**；改成先查 `venue_registry` 的 `homepage`，再走既有的 DuckDuckGo 查詢 | 備援自下架後一直靜默失敗，deterministic 路徑仍可用；查不到時已會在 report 留 note。 |
| `scraper/enrich_addresses.py` | **保留，改寫成不呼叫 LLM** | 見下方。 |

enrich_addresses 的新流程：

1. 候選只取 `coalesce(end_date, start_date) >= today` 的事件。2026-10-22 的 511 筆缺地址事件中只有 26 筆是未來活動，其餘是已結束、仍 `is_active` 的舊事件。
2. 先用 `venue_registry.lookup_venue_for_location`（唯讀）。
3. 再查其他事件：相同 `location_name` 且只對應到單一個具體地址時沿用（目前可補 85 筆，多半是舊事件）。
4. 剩下的只記 log，不呼叫 LLM。上線兩週後若剩餘量仍值得處理，另開 issue 評估 Responses API 的 `web_search` 並設每日上限；那時用 D3 的 `llm_cache` 做負向快取。

動工前再確認一次 #325 的進度：若 Eval session 已經改了 `venue_registry` 的介面，先對齊再改。

### D2. #319 錯誤語意

共用 client（D3）把錯誤分成兩類：

- **設定錯誤**：`model_not_found`、401、403、`insufficient_quota`、`invalid_api_key`。丟出 `LLMConfigError`，它繼承 `BaseException` 而不是 `Exception`，所以呼叫點既有的 `except Exception` 吞不掉，程序以非零狀態結束，step 會失敗。這是刻意的：21 個呼叫點幾乎都有寬鬆的 `except Exception`，逐一修改容易漏掉。
- **暫時錯誤**：429、5xx、逾時與只影響單一輸入的 400。SDK 先重試，之後照舊丟一般例外給呼叫點處理。client 記下次數；各腳本在 `__main__` 結尾呼叫 `llm_client.finish()`，本次執行的錯誤至少 3 次且超過半數時，以非零狀態結束。
- 分類只看例外的 `status_code` 與 `code`，不用 `isinstance`，所以測試替換 `sys.modules["openai"]` 或 SDK 改版都不會影響。
- `main.py`：某個來源遇到 `LLMConfigError` 只讓該來源記為失敗，其他來源照常爬取；AI 步驟中斷，IndexNow 照常送出，最後以非零狀態結束。
- `scraper.yml`：呼叫 LLM 的 step 設 `continue-on-error`，讓之後不依賴 LLM 的步驟照常執行；最後的「Fail on LLM step errors」只要其中一個失敗就讓 job 變紅。

健康檢查改看產出量（`scraper/source_health.py`）：週報與 `daily_quality.py` 標出最近兩週每週都有執行、產出都是 0 的來源，並分成兩層。「之前 6 週有產出、最近歸零」的標紅，`daily_quality` 只對這層發警示；長期 0 件的只列名稱，因為電影院沒有台灣片時本來就是 0。2026-10-22 預覽：49 個 silent，其中 10 個是新近歸零（#367）。

### D3. #363 共用用量紀錄（核心架構）

**資料表（一個 migration，套用前要使用者核准）**

- `llm_usage`：每次 API 呼叫一列。欄位：`id`、`created_at`、`caller`（`<group>.<name>`，例：`annotator.annotate`、`web.account.extract-from-image`）、`model`、`endpoint`（`chat`／`responses`）、`input_tokens`、`cached_input_tokens`、`output_tokens`、`web_search_calls`、`status`（`ok`／`error`）、`error_code`、`user_id`（網站帳號 API 才有）、`run_ref`（GitHub Actions 的 `GITHUB_RUN_ID`／workflow 名稱，網站為 null）。RLS 開啟，admin 可讀，`service_role` 寫入，依 `database.instructions.md` 加明確 GRANT。
- `llm_pricing`：`model`、`effective_from`、每百萬 tokens 的 `input`、`cached_input`、`output` 單價、`per_web_search_call`。單價只存在這裡；Python 與 TypeScript 都不寫死價格。新增模型或調價時只改這張表。
- `llm_cost_daily`（view）：依日期、caller、model 彙總 tokens，以 `llm_pricing` 在當天有效的單價算出 `cost_usd`。成本在查詢時計算，所以單價寫錯可以事後修正，不必回填舊列。
- `llm_cache`：`step`、`subject_key`、`result jsonb`、`attempted_at`、`outcome`，主鍵 `(step, subject_key)`。給 #317（海報圖片 hash）、#321（cinemaclair 圖片 URL、qa_heartbeat report id）、#360（event id）與 D1 之後可能的地址查詢共用，避免每個 issue 各加一個 `*_attempted_at` 欄位。

為什麼不用 `scraper_runs`：它一列代表一次執行，`source`、`events_processed`、`success` 是執行層的意義，網站沒有「執行」的概念，也記不下 model 別、cached tokens 與 search 次數。`scraper_runs` 繼續記執行層資料；舊的 `cost_usd` 欄位不再寫入，報表改讀 `llm_cost_daily`，避免重複計算。

**Python：`scraper/llm_client.py`**

- `get_client(caller)`／`get_async_client(caller)` 包住 `openai.OpenAI`／`AsyncOpenAI`，對外保留 SDK 的 `chat.completions.create(...)` 與 `responses.create(...)`，參數直接轉給 SDK，回傳原本的 response 物件。呼叫點只換建立 client 的那一行，既有的測試替身也不必改。M2 已完成這一步，M4 只在 client 內部加入寫入紀錄，呼叫點不必再改。
- 從 response 的 `usage` 讀 tokens：chat 用 `prompt_tokens`、`prompt_tokens_details.cached_tokens`、`completion_tokens`；responses 用 `input_tokens`、`input_tokens_details.cached_tokens`、`output_tokens`，`web_search_calls` 數 `output` 裡 `type == "web_search_call"` 的項目。圖片的 tokens 已含在 input 中。
- 紀錄先放在記憶體，每 20 筆或 `finish()`／`atexit` 時批次寫入 `llm_usage`。寫入失敗只記 warning，不影響主流程。`--dry-run` 若仍實際呼叫 API，也要記錄（那是真的花錢）。
- API key 依 caller 群組所屬的 OpenAI project 選擇：`OPENAI_API_KEY_<PROJECT>`，沒有設定時退回 `OPENAI_API_KEY`。使用者 2026-10-23 裁決分成 4 個 project：`annotator`、`enrich`（`qa`、`broadcast`、`auto_scraper` 也算在這裡）、`eval`（CI 與回測，讓 PR 測試的花費和正式環境分開）、`web`（`OPENAI_API_KEY_WEB`）。對照表在 `llm_client.PROJECT_OF_GROUP`。（原設計是每個群組一把 key，改成 4 個 project 以減少 secrets 數量。）scraper 的群組是 `annotator`、`enrich`、`qa`、`broadcast`、`eval`、`auto_scraper`，網站是 `web`；未知群組直接報錯。#320 因此只剩使用者在 OpenAI 建 project、發 key、設 secrets，以及在 workflow 傳入對應的環境變數。

**TypeScript：`web/lib/llm/openai.server.ts`**

- `callOpenAI({ caller, userId, body, timeoutMs })`：送出 fetch、解析 `usage`、以 service-role client 寫入 `llm_usage`（用 Next.js `after()`，不拖慢回應）、統一錯誤處理。6 個 route 改用它。
- ~~`assertLlmQuota(userId, caller, limitPerDay)`：數 `llm_usage` 中該使用者 24 小時內的列數~~（2026-10-23 改設計）：`llm_usage` 在回應送出後才由 `after()` 寫入，同時送出的多個請求都會看到舊的列數，擋不住連發。改用既有的 `account_usage` 計數表（migration 086），由 migration 104 加上 `extract_count` 與 service-role 專用的 `consume_account_ai_quota()`，在呼叫 OpenAI 前以列鎖原子地加一；`web/lib/llm/accountQuota.server.ts` 在 RPC 失敗時拒絕（fail closed）。上限由使用者裁決：每人每日 annotate 30、image 10，全站每日 annotate 300、image 100，以日本日期計。admin 路由不受限。2026-06-05 曾有同樣的限流（`4da6dede` 移除），當時兩個路由共用 `annotate_count`，annotate 會吃掉 image 的 5 次額度，而且 wizard 沒有對應的錯誤訊息。

**報表（#322）**

- `docs_report.py`、`daily_report.py`、`quota_monitor.py` 的成本一律讀 `llm_cost_daily`；讀 `scraper_runs` 的其他加總改用共用的分頁 helper（`.range()` 迴圈），並加測試。
- `quota_monitor --check-budget` 改讀 `llm_cost_daily` 中 `caller like 'scraper/eval_annotator%'` 的當週成本。
- 週報成本段落註明「以 OpenAI dashboard 為準」，並列出依 model 的小計，方便和 dashboard 逐項比對。

**呼叫點清單（D1 完成後共 21 個）**

原估 21 個；`enrich_ocr_event.py` 不呼叫 LLM（−1），embeddings 漏算（+1），所以合計仍是 21 個（scraper 15、web 6）。

scraper（15，M2 已改走 `llm_client`）：`annotator.py` ×5、`enrich_location.py`、`enrich_poster.py`、`weekly_line_broadcast.py`、`qa_heartbeat.py`、`sources/cinemaclair.py`、`auto_scraper/generate.py`、`auto_scraper/auto_research.py`、`eval_annotator.py` ×3（chat ×2、embeddings ×1）。embeddings 是第一次盤點漏掉的：當時只 grep 了 `chat.completions` 與 `responses`，PR #391 的 Historical Backtest 才發現 `eval_annotator.semantic_scores_for` 呼叫 `client.embeddings.create`。`test_every_sdk_surface_in_use_is_exposed` 之後會擋下任何未被 wrapper 涵蓋的 SDK 類型。Eval session 之後新增的 `eval_historical.py`、`eval_venues.py` 本來各自建立 `AsyncOpenAI`，在 rebase 時被 `check_llm_callers.py` 抓到，已改走 `get_async_client`（它們透過 `eval_annotator.annotate_one_async` 呼叫，沒有新增呼叫點）。
web（6）：`api/admin/annotate-event`、`api/admin/extract-from-image`、`api/account/annotate-event`、`api/account/extract-from-image`、`api/line-webhook`、`api/upload-with-qr`。

禁止直接呼叫的檢查（M4）以「建立 client」為關卡：`scraper/llm_client.py` 以外出現 `OpenAI(`／`AsyncOpenAI(`，或 `web/lib/llm/openai.server.ts` 以外出現 `api.openai.com`，就失敗（`_oneoff_*.py` 與 tests 除外）。repo 沒有跑 Python 測試的 CI，所以落在兩處：`scripts/check_llm_callers.py` 由 pre-commit hook（b1b）執行；網站端的同一檢查在 `web/tests/llm-usage.test.ts`，由 `prebuild` 執行，Vercel build 時會擋下。

網站端的 `openaiChat()` 回傳以 OpenAI 回應內容重建的標準 `Response`，路由原本的 `res.ok`／`res.text()`／`res.json()` 不用改；紀錄以 `after()` 在回應送出後寫入。帳號 API 傳入 `userId`，供 M5 的每人限流使用。

### D4. 其餘 issue 的做法

- #317 enrich_poster：以 `llm_cache(step='poster_ocr', subject_key=<image sha256>)` 讓同一張圖只送一次；查清 `skipped(confidence)` 計數錯誤；比較 `detail: low` 與 gpt-4o-mini 的抽取結果。dry-run 確認有實際寫入後，才移除 `scraper.yml` 的 `if: ${{ false }}`。
  - 2026-10-23 結果：照上述修好後做 dry-run（79 張，high 與 low 各一次），沒有任何正確寫入，使用者裁決退役，刪除腳本與 `scraper.yml` 步驟。`llm_cache` 留給 #321、#360 使用。數字見 notes.md「M6」。
- #360 enrich_location：候選限未來活動，先查 venue_registry，查過的以 `llm_cache(step='location_extract', subject_key=<event_id>)` 標記，30 天內不重送。
- #321 qa_heartbeat 先以 report type 規則分類，規則判斷不了的才呼叫 gpt-4o-mini；dry-run 不呼叫 API；分類結果以 report id 快取。cinemaclair 以圖片 URL 快取 OCR 結果。
- #361 由 `main.py` 執行 annotate 與兩個 enrich 步驟，刪掉 `scraper.yml` 的重複 step；`enrich_person_names` 加 `is_active` 與日期條件。
- #323 移除 `translator.fill_translations`、`deepl` 套件、五個 workflow 的 `DEEPL_API_KEY` 與 `docs/ARCHITECTURE.md` 的描述。
- #362 最後處理：排程與時段變動只重算變動欄位、`--fix-reviewed` 用精簡 prompt、靜態 prompt 放最前面維持 prefix cache；golden set 準確率不得退步（#324）。

### 模型分工（使用者指定）

- Opus：建 spec、#318 的去留、#363 的設計；production 資料庫寫入、migration、交給使用者的 settings patch。
- Sonnet（`/model sonnet`）：#323、#361、#322 的分頁、#360 的已嘗試標記等範圍固定的修改。

## Worktree & Spec Tracking

- Spec：`docs/specs/active/llm-cost-reset/`，label `spec:llm-cost-reset`。
- Worktree：`ttr-llm-cost-reset-worktree`，branch `feat/llm-cost-reset`（新建，依 `.github/instructions/git.instructions.md` § Isolated worktree 的 state matrix）。
- 跨多個 session：換 session 時先看 `label:spec:llm-cost-reset` 的 open issue，再讀 `tasks.md`。
- 完成後推 feature branch 並開 PR（使用者指定）。推到 `main` 由使用者執行。

## References

- 看板「成本」階段：#317～#323、#360～#363
- 相關：#324（golden set）、#325（地點三段 eval，Eval session 負責）
- `notes.md`：2026-10-22 的盤點數字
