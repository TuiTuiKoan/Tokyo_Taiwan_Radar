# Notes — 2026-10-22 盤點

以下數字來自 production 唯讀查詢（Supabase `cjtndektjjpvvjofdvzr`）與 OpenAI dashboard（使用者提供）。成本以 dashboard 為準。

## OpenAI dashboard（使用者提供）

- 2026-04-01～08-02：$97.21，`gpt-4o-search-preview`（大多是 web search 呼叫費）佔 70%。
- 2026-08-01～10-22：$49.76；8 月 $29.76；10-01～10-22 $10.11。search 支出約 08-20 停止。
- 目前支出以 gpt-4o（enrich_poster）為主；annotator 的 gpt-4o-mini 約七成 input tokens 已命中 prompt cache。

## `scraper_runs`（repo 帳本）

| source | 月份 | 執行次數 | events_processed | cost_usd |
| --- | --- | --- | --- | --- |
| annotator | 2026-07 | 63 | 769 | 2.26 |
| annotator | 2026-08 | 59 | 1459 | 3.94 |
| annotator | 2026-09 | 33 | 774 | 2.09 |
| annotator | 2026-10 | 37 | 788 | 2.18 |
| researcher | 2026-07 | 91 | 52 | 30.02 |
| researcher | 2026-08 | 93 | 40 | 19.57 |
| researcher | 2026-09 | 95 | 0 | 0.00 |
| researcher | 2026-10 | 64 | 0 | 0.00 |

所有列 `success = true`。enrich 系列、qa、web 都沒有紀錄。

## `research_sources` 的實作率（#318 去留依據）

- researcher 的分類（`academic_lecture`、`art_exhibition`、`books_media`、`cinema_screening`、`community_social`、`food_retail`、`fukuoka`、`gender_society`、`geopolitics_policy`、`kansai`、`music_live`、`tech_business`…）自 2026-06 起只有 3 筆走到 `implemented`：`tech_business` 06-26、`event_listing` 07-03、`media` 07-10。
- discovery_accounts：`note_creator` implemented 4 筆（04-29～05-03）、`peatix_organizer` implemented 6 筆（05-15），之後沒有；最後一筆 candidate 是 07-20。

## 缺地址事件（enrich_addresses 改寫依據）

- `is_active` 且有 `location_name`、沒有具體地址（排除 gguide_tv 與線上）：511 筆，312 個不同場館名稱。
- 其中未來活動（`coalesce(end_date, start_date) >= now()`）只有 26 筆。
- `venues` 表 425 筆，只有 54 筆有 address、58 筆 `is_authoritative`；以完全相同名稱或 alias 比對命中 0 筆（未經 `venue_registry` 的正規化，實作時以 `lookup_venue_for_location` 重測）。
- 相同 `location_name` 的其他事件只有單一具體地址：85 筆可沿用；有多個地址：46 筆（不沿用）。

## #325 狀態（2026-10-22）

Eval session 的 worktree 只有 commit `95101f2e docs(specs): split the remaining evaluation-framework work into issues`，#325 尚未動工，沒有改 `venue_registry.py`。本 spec 只唯讀呼叫 `lookup_venue_for_location`；M1 動工前再確認一次。

## OpenAI 呼叫點（2026-10-22 grep）

scraper：`annotator.py`（1558、1575、4187、4221、5176）、`discovery_accounts.py`（256、316）、`enrich_addresses.py`（76）、`qa_auto_fix.py`（100）、`enrich_location.py`（64）、`enrich_poster.py`（196）、`weekly_line_broadcast.py`（232）、`qa_heartbeat.py`（149）、`researcher.py`（408）、`sources/cinemaclair.py`（198）、`auto_scraper/generate.py`（388）、`auto_scraper/auto_research.py`（273）、`eval_annotator.py`（77、93）。另有三個 `_oneoff_*.py` 不納入。

web：`api/admin/extract-from-image`、`api/upload-with-qr`、`api/admin/annotate-event`、`api/line-webhook`、`api/account/annotate-event`、`api/account/extract-from-image`。

M1 移除 researcher（1）、discovery_accounts（2）、qa_auto_fix 備援（1）、enrich_addresses（1）後，剩 scraper 14 個、web 6 個，共 20 個（原估 21 個；`enrich_ocr_event.py` 經確認不呼叫 LLM）。

## M2 驗證（2026-10-22）

- 以 SDK 真正的 `openai.NotFoundError`（404、`model_not_found`）模擬下架模型，經 `llm_client` 穿過 `except Exception` 後，程序以 exit code 1 結束，訊息含 caller、model、status 與 code。
- `main.py`：`tests/test_main_llm_config_error.py` 確認一個來源丟出 `LLMConfigError` 時，其他來源仍會爬取，最後才失敗。
- 來源健康預覽（production 唯讀 SQL，與 `source_health.zero_output` 相同規則）：49 個 silent，10 個新近歸零，其中 prtimes 之前 6 週有 1148 筆，最後一次有產出是 2026-09-14，已開 #367。

## M1 dry-run（2026-10-22，使用者執行 `enrich_addresses.py --dry-run`）

- 候選 26 筆（未來活動）；`field_corrections` 已鎖 9 筆，跳過。
- 沿用其他事件的地址 2 筆：`銀座 蔦屋書店` → `東京都中央区銀座6丁目10-1`。
- registry 命中 0 筆；查不到 15 筆。其中「青山 月見ル君想フ」（前綴地名）、「丸の内ピカデリー2」（廳號接在名稱後，不在 parent-suffix 分隔字元內）屬於 venue 解析的比對缺口，歸 #325，本 spec 不改 `venue_registry.py`。
- 既有資料警告：`サロンシネマ1・2` 與 `サロンシネマ` 對到兩筆 authoritative venue，key 被拒（與本次改動無關）。

## M3 備註

- migration 編號用 `099`：`098_scope_report_transaction.sql`（japan-scope-gate）已在 origin/main。
- 單價來源：OpenAI 模型頁（2026-10-22 查詢）。gpt-4o $2.50／$1.25 cached／$10.00，gpt-4o-mini $0.15／$0.075／$0.60（每百萬 tokens）。web search 單價未填，目前沒有呼叫者；#366 若加回時再補。
- 既有 `account_usage` 表（migration 086/087）已記帳號 API 每日 annotate 次數；M5 做 #322 限流前先確認它的現況，避免重複。
- 本機沒有 Postgres，Docker daemon 未啟動，pip 的私有來源抓不到 `pglast`，所以 SQL 只做了人工語法檢查。

## M3 production 試跑（2026-10-22，BEGIN … RAISE，整批 rollback）

- 成本：gpt-4o-mini 1M input（700k cached）＋100k output → $0.1575；gpt-4o 2M input＋500k output 加一次 error → $10.00、errors=1；無單價模型 → `unpriced_calls=1`、cost 0。與手算一致。
- `llm_cost_daily` 為 `security_invoker=true`；三張表 RLS 開啟；非 admin 的 authenticated 讀到 0 列。
- 第一次試跑發現 anon 有 28 項權限（Supabase 10/30 前的 default privileges 仍會自動授權）。已在 migration 加 `REVOKE ALL … FROM anon, authenticated`；重跑後 anon 無權限，authenticated 只有 SELECT。
- 每次試跑後以 `to_regclass` 確認四個物件都不存在。

## M3 套用（2026-10-22，使用者核准）

- `apply_migration` 套用 `099_llm_usage`（commit `2671f162` 的版本）；migration 紀錄 `20261022135429 099_llm_usage`。
- 讀回：`llm_usage`／`llm_pricing`／`llm_cache` 為 table 且 RLS 開啟，`llm_cost_daily` 為 view 且 `security_invoker=true`；`llm_pricing` 2 列；`llm_usage` 0 列；anon 無權限；authenticated 只有三個物件的 SELECT；policy 為兩條 admin read。
- Security advisor：新物件只有 INFO `rls_enabled_no_policy`（`llm_cache`，刻意只給 service_role）。其餘警告為既有項目，與本 migration 無關，已另行口頭回報使用者（repo 公開，不在 issue 寫細節）。

## M4 實測（2026-10-22，使用者執行）

- 以 `get_client("eval.smoke")` 送一次 gpt-4o-mini（`max_tokens=1`）。API 回 13 input／1 output tokens。
- production `llm_usage` id 1：`eval.smoke`、`gpt-4o-mini`、`chat`、13／0／1、`ok`。`llm_cost_daily` 算出 $0.000003（手算 $0.00000255），`unpriced_calls=0`。
- 這一列保留在表中，caller 為 `eval.smoke`，彙總時可依 caller 排除。
- 網站端：`tsc`、eslint、`web/tests/llm-usage.test.ts`（7 項）通過；`pnpm run build` 的 prebuild 與編譯通過，prerender 因 worktree 沒有網站的 Supabase 環境變數而停下，留給 PR 的 Vercel preview 驗證。

## PR #391 的 Historical Backtest 失敗（2026-10-23）

- 原因：`AttributeError: 'AsyncLLMClient' object has no attribute 'embeddings'`。`eval_annotator.semantic_scores_for` 用 `text-embedding-3-small` 評分，而共用 client 只有 chat 與 responses。
- 為何漏掉：第一次盤點只 grep `chat.completions.create`／`responses.create`；`eval_annotator` 的單元測試用假 client，沒有碰到。這個 workflow 在 PR 只有改到 `eval_historical.py` 才會觸發，是 CI 抓到的。若沒抓到，每月的 monthly_health_check 會失敗。
- CI 端的紀錄實證：失敗前的 100 次 gpt-4o-mini 呼叫（$0.18）與 Venue Pipeline Eval 的 38 次（$0.06）都寫進了 production `llm_usage`，`run_ref` 為 `Historical Backtest#39799126338` 等。表示 PR 上跑的 eval 也會入帳，彙總時 caller 以 `eval.` 開頭可篩出。
- 修正：client 加 `embeddings`（只計 input tokens）；migration 102 放寬 `endpoint` 的 CHECK 並為 `text-embedding-3-small` 定價（$0.02／百萬 tokens，OpenAI 模型頁，2026-10-23 查）；新增 `test_every_sdk_surface_in_use_is_exposed`，舊版 client 會讓它失敗。
- migration 編號：main 已有 `100_rpc_execute_lockdown.sql`（另一個 session，已替本 spec 的 099 保留編號），所以原本用 101。2026-10-23 套用到 production 後，才發現另一個 session 同時以 `101_rpc_lockdown_followup.sql` 用掉 101 並已套用；兩者內容不重疊，本檔改名為 `102_llm_usage_embeddings.sql`，production 的紀錄名稱仍是 `20261022165956 101_llm_usage_embeddings`。教訓：開 migration 前先 `git fetch` 看 main 的最新編號，套用前再看一次。
- 修正後重跑（run 39818875798）：成功；`llm_usage` 有 100 次 gpt-4o-mini chat 與 1 次 `text-embedding-3-small` embeddings（97,943 input tokens），該次合計 $0.18。
- `Auto-merge Dependabot` 的 skipped 是正常的：`if: github.actor == 'dependabot[bot]'`。
