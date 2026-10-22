---
slug: people-ground-truth
title: 人名 ground truth：people 表與 DB 優先查詢
status: active
branch: feat/people-ground-truth
created: 2026-10-23
tags: [scraper, supabase, evaluation]
---

## What（做什麼）

新增 `people` 與 `person_lookup_cache` 兩張表，讓 `scraper/person_name_lookup.py` 的人名查詢改成先查資料庫，查不到才連 eiga.com 與 Wikipedia，結果寫回資料庫。人工確認過的人名（`verified = true`）在所有查詢路徑都優先，外部查詢不能覆蓋。eval stage 3 改讀凍結的人名快照，不連外部網站，也不需要 Supabase 連線，可以放進每週 CI。

來源 issue：#392。設計經 Plan Critic 評審一輪（2026-10-23），修正項目見 `notes.md`「評審紀錄」。

## Why（為什麼）

- 現在只有 process 內的記憶體快取。每日排程、`qa_heartbeat` 與 eval 每次重啟就清空，同一個人名每天重打外部網站。
- 查錯的結果無法固定修正。例：9m88 曾被對到 Ju 88 轟炸機，只能改程式碼的判斷規則，不能直接指定正確答案。
- eval stage 3（`eval_annotator.py --stage 3`）每次對全部案例打外部網站，結果不穩定，無法放進每週 CI。
- 電影片名已經有 `works` 表當 DB 優先的快取，人名沒有對應的表；`works.cast_summary` 是一段文字，無法對照單一人名。

## Non-Goals（不做什麼）

- `work_people`（片、人、角色）關聯表：延後，見 #397。
- 人名別名表（同一人多種日文寫法）：只做 NFKC 正規化；別名等量測顯示需要再做。
- admin 介面設定 verified：第一版用 CLI，admin 頁見 #396。
- 直接把現有事件的人名回填成資料：見第 7 節。
- 降低 `enrich_person_names` 的 GPT 費用：屬於 #361（`spec:llm-cost-reset`）。本 spec 只減少外部網站請求。
- 修正 enrich FC guard 在例外時放行寫入的既有問題（`annotator.py` FC guard 的 `except`）：見 #398；本 spec 只要求 `propagate` 路徑 fail closed。
- 自動依程式版本刷新舊結果（原 `lookup_version` 設計）：改為手動 `reset-unverified` 指令，見第 3 節。
- web 前台顯示人物頁。

## 現況證據（2026-10-23 production 唯讀查詢）

詳見 `notes.md`。重點：

- 有 `performers` 的事件 1,607 筆，不重複日文人名 1,786 個；其中含「カタカナ・カタカナ」形式的 116 個。
- 人名相關 `field_corrections`（`performer*`、`director*` 的 zh/en）共 732 筆，**`corrected_by` 全部是 NULL**，即沒有一筆是 admin 在 web 端修正的。其中：
  - 588 筆 `report_id IS NULL`：腳本自動鎖定（`annotator._lock_fields_via_corrections` 等），即過去外部查詢的結果。
  - 144 筆 `report_id` 非空：使用者回報後由 `qa_auto_fix.py` 自動修正並鎖定。有人類訊號但沒有人工確認。
- `performers` 與 `performers_zh` 長度不一致的事件 11 筆。

## Design（設計摘要）

### 1. 資料表（migration 編號暫定 102）

main 上最新是 `101_rpc_lockdown_followup.sql`。`feat/llm-cost-reset` 分支保留了 `099_llm_usage.sql`，另有 `101_llm_usage_embeddings.sql` 與 main 的 101 撞號。合併前以 `ls supabase/migrations` 重新確認，兩條線誰先合併誰取 102，另一方順延。

**`people`**：只放查到結果的人與人工設定的人，不放「查不到」。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `id` | uuid PK | |
| `name_ja` | text NOT NULL | 來源上看到的寫法，寫入前 NFKC 正規化並去頭尾空白 |
| `name_zh` | text | 一律存繁體（寫入前 `_to_trad`） |
| `name_en` | text | |
| `eiga_person_id` | int, nullable | 取自 `https://eiga.com/person/<id>/` |
| `person_key` | text GENERATED ALWAYS AS (`CASE WHEN eiga_person_id IS NOT NULL THEN 'eiga:' \|\| eiga_person_id ELSE 'name:' \|\| name_ja END`) STORED, **UNIQUE** | 唯一鍵。有 eiga id 的以 id 區分（允許同名不同人），沒有的以日文名區分 |
| `match_method` | text CHECK | `eiga_cast`（電影頁名單）／ `eiga_search`（人物搜尋，且姓名比對通過）／ `ja_wiki` ／ `manual` |
| `verified` | bool NOT NULL default false | |
| `verified_at` | timestamptz | `CHECK (NOT verified OR verified_at IS NOT NULL)` |
| `notes` | text | 人工備註 |
| `created_at` / `updated_at` | timestamptz | `updated_at` 用 trigger 維護，比照 `works` |

- 一般 index `(name_ja)`。
- 用 generated column 加一般 UNIQUE，不用 partial unique index：PostgREST 的 `on_conflict` 產生的 `ON CONFLICT (col)` 不帶 predicate，對 partial index 會報錯。
- 「不要替換」標記：`verified = true` 且 `name_zh`、`name_en` 都是 NULL，表示這個字串確定不是人名或不該翻譯。

**`person_lookup_cache`**：只存 `people` 放不下的查詢結果。

| `kind` | 會寫入的 `status` | `payload` | 有效期限 |
| --- | --- | --- | --- |
| `eiga_movie_cast`（片名 → 演職員名單） | `found` / `not_found` | `found`：`[{role, ja_name, eiga_person_id}]` | `found` 不過期；`not_found` 30 天 |
| `single_person`（單一人名） | `not_found` / `ambiguous` | `{}`；`ambiguous` 存候選 eiga id | 30 天 |

- 主鍵 `(kind, query)`；`query` 同樣 NFKC 正規化。
- 單一人名查到的結果只存 `people`，不在 cache 重複存。
- 欄位：`kind`、`query`、`status`（CHECK）、`payload` jsonb、`fetched_at`、`expires_at`（NULL = 不過期）。

**權限**：兩張表都是 Tier C（只給 scraper）。`ENABLE ROW LEVEL SECURITY`，不建 policy；`REVOKE ALL … FROM anon, authenticated` 作保險；`GRANT SELECT, INSERT, UPDATE, DELETE … TO service_role`。Supabase 自 2026-10-30 起不再自動授權新表，GRANT 必寫。migration 檔頭附 read-back 檢查 SQL（比照 `101_rpc_lockdown_followup.sql`）。之後做 admin 頁時再另以 migration 加 admin policy。

### 2. 查詢結果的三種狀態

外部查詢函式回傳 `found` / `not_found` / `error` 三種狀態，取代現在以 `None` 或 `{}` 同時代表「查不到」與「出錯」的寫法。

- `error`（連線失敗、HTTP 4xx/5xx、逾時、解析例外）**不寫 DB、也不寫 process 內快取**，下次照常重查。
- 要移除現有 `except` 區塊裡的負向快取寫入：`_resolve_person`、`lookup_person_names`、`lookup_single_person` 都在例外時把空結果寫進 `_person_cache`／`_movie_cache`；`_search_person_eiga` 吞掉例外回傳 None，會讓流程誤退到 ja.wikipedia。
- `_lookup_zh_via_wikipedia` 等目前沒有 try 的函式，例外一律往上轉成 `error`。

### 3. 查詢順序（`person_name_lookup.py`）

資料庫存取以參數注入（`store`），單元測試用記憶體版。

**以日文名查 verified（所有路徑共用）**：`people WHERE name_ja = X AND verified`。電影路徑、單一人名路徑，以及 enrich 對事件既有的 `performer`／`performers[]`／`director` 值，都先做這一步，**不限片假名、不限含「・」**。這樣 `9m88` 這類藝名的人工修正才會生效（目前 `extract_katakana_names` 只抽含「・」的片假名，`annotator.py` 也只在 `performer` 含「・」時才查單一人名）。

**單一人名 `lookup_single_person(ja_name)`**

1. verified 列（上面那一步）。
2. 未 verified 列：只有一筆就用它；多筆（同名不同人）視為歧義，不替換。
3. cache `(single_person, ja_name)` 未過期：`not_found`、`ambiguous` 直接回傳，不連外部。
4. 連外部網站：
   - eiga 人物搜尋取得候選後，比對人物頁的日文名與查詢名（NFKC 後相等）。不相等就不採用 eiga 結果，改走 ja.wikipedia。
   - 結果：`found` 寫 `people`（`match_method` 記來源）；`not_found` 寫 cache；搜尋有多個同名候選時寫 `ambiguous`；`error` 不寫。

**電影 `lookup_person_names(title)`**

1. cache `(eiga_movie_cast, title)`：`found` 直接用名單；`not_found` 未過期直接回傳 `{}`。
2. 否則連 eiga.com 搜尋片名與電影頁，名單寫 cache。
3. 名單中每個人：先以日文名查 verified 列；再以 `eiga_person_id` 查 `people`；都沒有才打人物頁與 Wikipedia，結果寫 `people`（`match_method = eiga_cast`）。

**寫入規則（保護人工資料）**

- 新增：`upsert(on_conflict="person_key", ignore_duplicates=True)`，即 `ON CONFLICT (person_key) DO NOTHING`。
- 更新未 verified 的列：`.update(...).eq("id", id).eq("verified", False)`，等同 compare-and-set；回傳 0 列時 log「被 verified 擋下」。
- 重查未 verified 的列得到 `not_found`：以同樣條件刪除該列，再寫 `not_found` cache。
- 上線前在本機 Postgres（`supabase start`）實測：新增衝突時跳過、verified 列不被更新或刪除。

**離線模式**：`offline=True` 時不做任何網路請求（單元測試斷言 `requests` 未被呼叫），未命中回傳空結果並計入 miss。`offline=False` 且沒有 `store` 時（本機沒有 Supabase env 的 dry-run），維持現行只用記憶體快取的行為。

**刷新舊結果**：不自動依程式版本刷新。修改查詢判斷規則後，手動執行 `people_admin.py reset-unverified [--match-method X]`（預設 dry-run），刪除符合條件的未 verified 列與 cache，下次用到時重新查詢。

**計數**：每次執行結束時 log `verified_hit`、`db_hit`、`cache_hit`、`cache_negative_hit`、`external_request`、`external_error`、`offline_miss`。

### 4. 呼叫端

- `annotator.enrich_person_names` / `enrich_person_names_single`：改用 DB 優先查詢，並對事件既有人名欄位先查 verified 列（第 3 節）。`PersonInfo` 增加 `verified: bool`。
- `qa_heartbeat.py`：經 `enrich_person_names_single`，不需另外改。
- `eval_annotator.py --stage 3`：見第 6 節。

### 5. 人工修正：`scraper/people_admin.py`（CLI）

| 子命令 | 作用 | 寫 production |
| --- | --- | --- |
| `set --name-ja X [--zh] [--en] [--eiga-id] [--not-a-person] [--note]` | 新增或修改一筆並設 `verified = true`、`match_method = manual` | 是；預設 dry-run，`--apply` 才寫 |
| `show --name-ja X` | 顯示 `people` 與 cache 中相關列，以及使用這個名字的事件數 | 否 |
| `reset-unverified [--match-method X] [--name-ja X]` | 刪除未 verified 列與對應 cache | 是；預設 dry-run |
| `candidates --out <csv> [--top N]` | 匯出回填候選（第 7 節） | 否 |
| `import --csv <csv>` | 匯入確認過的列，設 verified | 是；預設 dry-run |
| `propagate --name-ja X` | 把修正套回相關事件 | 是；預設 dry-run |

**為什麼需要 `propagate`**：只改 `people` 不會改到舊事件。enrich 寫入前會檢查 `field_corrections`，值不同就跳過，而舊事件的人名欄位多半已被自動鎖定。

`propagate` 流程：

1. 找出受影響事件：`performers @> ARRAY[X]`、`performer = X`、`director = X`，限 `is_active = true`。
2. 欄位白名單：`performer`、`performer_zh`、`performer_en`、`performers`、`performers_zh`、`performers_en`、`director_zh`、`director_en`。**不含 `description_*`**（描述裡的舊譯名由 GPT 替換，效果未驗證，另列決策）。
3. 只處理 `corrected_by IS NULL AND report_id IS NULL` 的 FC。`report_id` 非空的列在報告中標為「需人工確認」並跳過；`corrected_by` 非空的人工修正一律不動。
4. 刪除前把要刪的 FC 列備份成 JSON（寫到 `~/.ai-notes/ttr/people-propagate/`，不進 repo）。
5. 重跑 `enrich_person_names_single`，FC guard 在這條路徑 fail closed（查 FC 失敗就不寫）。重跑沒有寫入任何欄位時，從備份還原被刪的 FC。
6. 輸出事件連結 `https://tokyotaiwanradar.com/ja/events/<id>` 與前後差異。

每次 `--apply` 前都要使用者核准 dry-run 結果。

### 6. eval stage 3 放進 CI

- `eval_annotator.py --stage 3 --warm-people`：本機執行，允許外部查詢並寫入 `people` 與 cache（不寫 `events`），結束後把 golden set 用到的 `people` 與 cache 子集匯出成凍結快照（`scraper/tests/golden/people_snapshot.json`，比照 stage 1 的 `frozen_path` 做法）。
- CI 的 stage 3 只讀快照、`offline=True`，不需要 Supabase secrets。
- stage 3 仍會呼叫 GPT 修描述，需要 `OPENAI_API_KEY`；workflow 只用 `schedule` 與 `workflow_dispatch`，不掛 `pull_request`，比照 `eval-annotator-stage2.yml`。
- 缺快照或缺 `OPENAI_API_KEY` 時明確 skip 並以專用 exit code 結束，不靜默降級。
- 報告加入「人名覆蓋率」：有解析到人名的 case 數 ÷ 總數。

### 7. 回填

不直接把現有事件的人名寫進 `people`。可用的來源（`performers_zh` 等）都是過去自動查詢或 GPT 的產物，直接回填等於把舊錯誤當成 ground truth。

改成：

1. `people_admin.py candidates --top 200` 從 `is_active` 事件抽出「日文名 ≠ 中文名」的對照，依出現次數排序；附上目前的 zh/en、出現事件數、FC 狀態（自動鎖定／回報修正）。略過長度不一致的事件；同一日文名對到多個譯名時標為衝突。
2. 使用者在 CSV 勾選、修正。
3. `people_admin.py import` 只匯入勾選的列，設 `verified = true`、`match_method = manual`。

其餘資料由每日排程自然累積。

### 8. 影響檔案

- 新增：`supabase/migrations/102_people.sql`、`scraper/people_admin.py`、`scraper/tests/test_people_store.py`、`scraper/tests/test_people_admin.py`、`scraper/tests/golden/people_snapshot.json`
- 修改：`scraper/person_name_lookup.py`、`scraper/annotator.py`、`scraper/eval_annotator.py`、新增或修改 stage 3 workflow、`.github/instructions/database.instructions.md`（Latest／next／Other tables）
- 既有測試會受影響：`scraper/tests/test_person_name_lookup.py`（依賴 `_person_cache.clear()` 與模組內部函式）、`scraper/tests/test_person_name_enrich_helpers.py`
- 若更新 SKILL 或 agent 檔，執行 `python3 scripts/sync_ai_adapters.py`

### 9. 必測項目

- `error` 不寫 DB、不寫 process 快取（mock 429、timeout）。
- 離線模式零網路請求。
- verified 列：外部查到不同結果時不被更新或刪除；沒有 eiga id 的 verified 列在電影路徑生效；`9m88` 這類無「・」的名字生效。
- eiga 搜尋第一筆姓名不符時不採用。
- 歧義：同名多筆未 verified 時不替換，並寫 `ambiguous` cache。
- `propagate`：跳過 `report_id` 列與人工列、欄位白名單、重跑無寫入時還原 FC、FC 查詢失敗時不寫。

## 風險

| 風險 | 處理 |
| --- | --- |
| 錯誤結果被固定下來 | eiga 搜尋需姓名比對；`match_method` 標示證據強度；`reset-unverified` 手動清除；人工 `set` 永久優先 |
| 同名不同人共用一筆 | 有 eiga id 的以 id 區分；沒有 id 的同名多筆不替換 |
| 暫時錯誤被記成查不到 | 三種狀態；`error` 不寫任何快取 |
| 修好的查詢規則不套用到舊結果 | 修規則時執行 `reset-unverified`，寫進 SKILL 的流程 |
| 寫入語法與 index 不相容 | generated `person_key` 加一般 UNIQUE；本機 Postgres 實測 |
| `propagate` 誤刪鎖定或刪了沒補回 | `report_id`／`corrected_by` 分流、欄位白名單、備份、無寫入即還原、fail closed |
| migration 編號與 `feat/llm-cost-reset` 衝突 | 合併前重新確認編號 |
| 外部請求量的改善被 #361 混淆 | 先取 baseline（里程碑 0），比較時註明 #361 是否已合併 |

## References

- #392（來源 issue）、#389（`ファン` 姓，已修）、#361（enrich 重複執行與費用）
- `scraper/person_name_lookup.py`、`scraper/annotator.py`（`enrich_person_names_single`、`_resolve_event_people`、`_lock_fields_via_corrections`）、`scraper/qa_auto_fix.py`（回報修正寫 FC）
- `scraper/eval_annotator.py` stage 1 `frozen_path`、stage 3
- `supabase/migrations/048_works_entity.sql`（DB 優先快取的前例）
- `.github/instructions/database.instructions.md`（GRANT 規則、migration checklist）
