---
slug: people-ground-truth
title: 人名 ground truth：people 表與 DB 優先查詢
status: active
branch: feat/people-ground-truth
created: 2026-10-23
tags: [scraper, supabase, evaluation]
---

## What（做什麼）

新增 `people` 與 `person_lookup_cache` 兩張表，讓 `scraper/person_name_lookup.py` 的人名查詢改成先查資料庫，查不到才連 eiga.com 與 Wikipedia，結果寫回資料庫。人工確認過的人名（`verified = true`）在所有查詢路徑都優先，外部查詢不能覆蓋。eval stage 3 的人名查詢改讀凍結快照，不連外部網站，可以放進每週 CI。

來源 issue：#392。設計經兩輪評審（2026-10-23）：第一輪 Claude Haiku、第二輪 Codex。修正對照見 `notes.md`「評審紀錄」。

### 三個目標

1. 減少重複的外部網站請求。
2. 人工修正一次就固定生效：之後的查詢都用人工值，外部查詢不能覆蓋。
3. eval stage 3 的人名查詢不連外部網站，可以放進每週 CI。

## Why（為什麼）

- 現在只有 process 內的記憶體快取。每日排程、`qa_heartbeat` 與 eval 每次重啟就清空，同一個人名每天重打外部網站。
- 查錯的結果無法固定修正。例：9m88 曾被對到 Ju 88 轟炸機，只能改程式碼的判斷規則，不能直接指定正確答案。
- eval stage 3（`eval_annotator.py --stage 3`）每次對全部案例打外部網站，結果不穩定，無法放進每週 CI。
- 電影片名已經有 `works` 表當 DB 優先的快取，人名沒有對應的表；`works.cast_summary` 是一段文字，無法對照單一人名。

## Non-Goals（不做什麼）

- `work_people`（片、人、角色）關聯表：延後，見 #397。
- 人名別名表（同一人多種日文寫法）：只做 NFKC 正規化；別名等量測顯示需要再做。
- admin 介面設定 verified：第一版用 CLI，admin 頁見 #396。
- 回填：從現有事件匯出候選、人工確認後匯入。不是三個目標的必要條件，移到 #408。第一版不直接把現有事件的人名寫進 `people`，理由見「現況證據」。
- `propagate` 的實際寫入（把人工修正套回已鎖定的舊事件）：第一版只做 dry-run 計畫，寫入見 #409。理由見第 5 節。
- 修正 enrich FC guard 在例外時放行寫入的既有問題：見 #398。
- 自動依程式版本刷新舊結果：改為手動 `reset-unverified` 指令，見第 3 節。
- 降低 `enrich_person_names` 的 GPT 費用：屬於 #361（`spec:llm-cost-reset`）。本 spec 只減少外部網站請求。
- eval stage 2 的 `works` 查詢改離線：stage 3 沿用 stage 2 的即時 `works` 查詢，見第 6 節。
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
| `name_ja` | text NOT NULL | `CHECK (name_ja = normalize(btrim(name_ja), NFKC) AND name_ja <> '')`，資料庫層強制正規化 |
| `name_zh` | text | 一律存繁體（寫入前 `_to_trad`） |
| `name_en` | text | |
| `eiga_person_id` | int, nullable | 取自 `https://eiga.com/person/<id>/` |
| `person_key` | text GENERATED ALWAYS AS (`CASE WHEN eiga_person_id IS NOT NULL THEN 'eiga:' \|\| eiga_person_id ELSE 'name:' \|\| name_ja END`) STORED, **UNIQUE** | 唯一鍵。有 eiga id 的以 id 區分（允許同名不同人），沒有的以日文名區分 |
| `match_method` | text CHECK | `eiga_cast`（電影頁名單）／ `eiga_search`（人物搜尋，且姓名比對通過）／ `ja_wiki` ／ `manual` |
| `verified` | bool NOT NULL default false | |
| `verified_at` | timestamptz | `CHECK (NOT verified OR verified_at IS NOT NULL)` |
| `notes` | text | 人工備註，不進快照 |
| `created_at` / `updated_at` | timestamptz | `updated_at` 用 trigger 維護，比照 `works` |

- 一般 index `(name_ja)`。
- 用 generated column 加一般 UNIQUE，不用 partial unique index：PostgREST 的 `on_conflict` 產生的 `ON CONFLICT (col)` 不帶 predicate，對 partial index 會報錯。
- 「不要替換」標記：`verified = true` 且 `name_zh`、`name_en` 都是 NULL，表示這個字串確定不是人名或不該翻譯。

**`person_lookup_cache`**：只存 `people` 放不下的查詢結果。

| `kind` | 會寫入的 `status` | `payload` | 有效期限 |
| --- | --- | --- | --- |
| `eiga_movie_cast`（片名 → 演職員名單） | `found` / `not_found` | `found`：`[{role, ja_name, eiga_person_id}]` | `found` 不過期；`not_found` 30 天 |
| `single_person`（單一人名） | `not_found` / `ambiguous` | `ambiguous`：候選 eiga id 陣列；其餘 `{}` | 30 天 |

- 主鍵 `(kind, query)`；`query` 同樣有 NFKC CHECK。
- 單一人名查到的結果只存 `people`，不在 cache 重複存。
- 欄位：`kind`、`query`、`status`（CHECK）、`payload` jsonb、`fetched_at`、`expires_at`（NULL = 不過期）。

**權限**：兩張表都是 Tier C（只給 scraper）。

- `ENABLE ROW LEVEL SECURITY`，不建 policy。
- `REVOKE ALL … FROM PUBLIC, anon, authenticated`（Supabase 會直接授權給 anon/authenticated，只 revoke PUBLIC 不夠）。
- `GRANT SELECT, INSERT, UPDATE, DELETE … TO service_role`。Supabase 自 2026-10-30 起不再自動授權新表，GRANT 必寫。
- 整個 migration 包在一個交易裡，結尾用 `DO` 區塊做 read-back 檢查，不符合就中止交易（比照 `101_rpc_lockdown_followup.sql`）。檢查項目：兩張表 RLS 已開啟、沒有任何 policy、`anon`／`authenticated`／`PUBLIC` 沒有任何權限、`service_role` 有四種 DML 權限。
- 之後做 admin 頁時再另以 migration 加 admin policy。

### 2. 正規化：單一函式

`person_name_lookup.normalize_name_ja(s)`：NFKC、去頭尾空白。所有寫入與查詢入口都只用這一個函式，包含 store、CLI 各子命令、快照匯出與讀取、enrich 讀取事件既有欄位值。資料庫 CHECK 是最後一道防線：漏做正規化的寫入會直接失敗，不會產生第二個 key。

正規化後撞到既有列時，不靜默合併：遇到 verified 列，寫入失敗並回報；遇到未 verified 列，依第 4 節「寫入規則」處理。

### 3. 查詢結果的三種狀態

外部查詢函式回傳 `found` / `not_found` / `error` 三種狀態，取代現在以 `None` 或 `{}` 同時代表「查不到」與「出錯」的寫法。

- `error`（連線失敗、HTTP 4xx/5xx、逾時、解析例外）**不寫 DB、也不寫 process 內快取**，下次照常重查。
- 要移除現有 `except` 區塊裡的負向快取寫入：`_resolve_person`、`lookup_person_names`、`lookup_single_person` 都在例外時把空結果寫進 `_person_cache`／`_movie_cache`；`_search_person_eiga` 吞掉例外回傳 None，會讓流程誤退到 ja.wikipedia。
- `_lookup_zh_via_wikipedia` 等目前沒有 try 的函式，例外一律往上轉成 `error`。

**歧義（`ambiguous`）的唯一來源**：eiga 人物搜尋結果第一頁中，人物頁日文名經 `normalize_name_ja` 後與查詢名完全相等、且 eiga id 不同的候選有兩個以上。Wikipedia 的多筆搜尋結果不算歧義。資料庫裡的同名多列不直接當作歧義，見第 4 節。

### 4. 查詢與寫入（`person_name_lookup.py`）

資料庫存取以參數注入（`store`），單元測試用記憶體版。

**單一人名 `lookup_single_person(ja_name)`**

1. verified 列：`people WHERE name_ja = X AND verified`。多筆 verified 是資料錯誤，記 warning、不替換。
2. 未 verified 列：
   - 只有一筆：用它。
   - 多筆：只會是不同 eiga id 的同名人物（無 id 列已在寫入時併入，見下方寫入規則），視為歧義，不替換。
3. cache `(single_person, ja_name)` 未過期：`not_found`、`ambiguous` 直接回傳，不連外部。
4. 連外部網站：
   - eiga 人物搜尋，依第 3 節比對姓名。一個相符：採用。兩個以上：寫 `ambiguous`。沒有相符：改走 ja.wikipedia。
   - 結果：`found` 寫 `people`（`match_method` 記來源）；`not_found` 寫 cache；`error` 不寫。

**電影 `lookup_person_names(title)`**

1. cache `(eiga_movie_cast, title)`：`found` 直接用名單；`not_found` 未過期直接回傳 `{}`。
2. 否則連 eiga.com 搜尋片名與電影頁，名單寫 cache。
3. 名單中每個人：先查同名 verified 列；再以 `eiga_person_id` 查 `people`；都沒有才打人物頁與 Wikipedia，結果寫 `people`（`match_method = eiga_cast`）。

**寫入規則（保護人工資料、避免同名重複）**

| 要寫入的列 | 已存在 | 處理 |
| --- | --- | --- |
| 有 eiga id | 同名 verified 列 | 不寫，verified 優先 |
| 有 eiga id | 同名、無 eiga id、未 verified 的列恰好一筆 | 升級該列：`.update({eiga_person_id, …}).eq("id", id).eq("verified", False).is_("eiga_person_id", "null")`，以 compare-and-set 補上 id |
| 有 eiga id | 其他 | `upsert(on_conflict="person_key", ignore_duplicates=True)` 新增 |
| 無 eiga id | 同名的任何列（不論有無 id、是否 verified） | 不寫 |
| 無 eiga id | 無同名列 | `upsert(on_conflict="person_key", ignore_duplicates=True)` 新增 |

- 更新未 verified 的列一律帶 `.eq("verified", False)`；回傳 0 列時 log「被 verified 擋下或已被改動」。
- 重查未 verified 的列得到 `not_found`：以同樣條件刪除該列，再寫 `not_found` cache。

**驗收（里程碑 2）**：在本機 Postgres（`supabase start`）上，用 supabase-py 實際送出請求，不能只跑 SQL：

1. 相同 `person_key` 新增時跳過。
2. 升級無 id 列時，同名列不會變成兩筆。
3. verified 列不會被更新或刪除。
4. 未正規化的 `name_ja` 被 CHECK 擋下。

**離線模式**：`offline=True` 時不做任何 HTTP 請求（單元測試斷言 `requests` 未被呼叫），未命中回傳空結果並計入 miss。`offline=False` 且沒有 `store` 時（本機沒有 Supabase env 的 dry-run），維持現行只用記憶體快取的行為。

**刷新舊結果**：不自動依程式版本刷新。修改查詢判斷規則後，手動執行 `people_admin.py reset-unverified [--match-method X]`（預設 dry-run），刪除符合條件的未 verified 列與 cache，下次用到時重新查詢。

**計數**：每次執行結束時 log `verified_hit`、`db_hit`、`cache_hit`、`cache_negative_hit`、`external_request`、`external_error`、`offline_miss`。

### 5. 把 verified 套用到事件欄位（`annotator.py`）

只在 lookup 裡查 verified 還不夠：電影路徑先用片名查名單，只有名單為空才從內文抽名字；而且只有含「・」的 `performer` 才會查單一人名。所以 `9m88` 這類名字，即使有 verified 列也到不了欄位。

`enrich_person_names_single` 在算出 `update` 之前，加一個明確的覆寫步驟：

1. 收集事件既有的 `performer`、`performers[]`、`director` 值，用 `normalize_name_ja` 正規化，不限片假名、不限含「・」。
2. 每個值查 verified 列。
3. 有 verified 列時，用它覆寫 `people` 對照表中對應的項目。名單裡沒有這個名字時就新增一項。
4. verified 的「不要替換」標記：把該名字從對照表移除，對應欄位不寫。
5. 之後才產生 `update`，然後交給 FC guard 與 `_lock_fields_via_corrections`。所以被鎖定的一定是 verified 值，不會是外部查詢的猜測。

`PersonInfo` 增加 `verified: bool`。端到端測試四種情況：電影名單命中、電影名單無此人、無「・」名字、「不要替換」標記。

**已鎖定的舊事件**：上面的步驟只對還沒有自動鎖定的欄位生效。已被自動鎖定、值又不同的欄位，FC guard 會擋下寫入（這是既有保護行為，不改）。這類事件由下面的 `propagate` 處理。

**`people_admin.py propagate --name-ja X` 第一版只做 dry-run 計畫，不寫入**：

1. 找出受影響事件：`performers @> ARRAY[X]`、`performer = X`、`director = X`，限 `is_active = true`。
2. 欄位白名單：`performer`、`performer_zh`、`performer_en`、`performers`、`performers_zh`、`performers_en`、`director_zh`、`director_en`。不含 `description_*`。
3. 逐欄位列出：事件連結 `https://tokyotaiwanradar.com/ja/events/<id>`、目前值、verified 對應的新值、FC 擁有者。FC 擁有者分三類：
   - 腳本鎖定：`corrected_by IS NULL AND report_id IS NULL`。
   - 回報修正：`report_id` 非空。
   - 人工修正：`corrected_by` 非空。
4. 你依計畫在 admin 事件編輯頁逐筆修正，修正後會產生人工 FC，從此固定。

**為什麼第一版不自動寫入**：原設計是「刪除 FC → 重跑 enrich → 沒寫入就還原」。事件欄位與 FC 之間沒有交易，期間若排程或 `qa_heartbeat` 改了同一筆事件，判斷與還原都可能根據過期狀態。安全的寫入需要「事件欄位舊值 + FC 列」一起 compare-and-set，並定義部分成功時怎麼處理，見 #409。

### 6. eval stage 3 放進 CI

- `eval_annotator.py --stage 3 --warm-people`：本機執行，允許外部查詢並寫入 `people` 與 cache（不寫 `events`）。結束後把 golden set 用到的子集匯出成凍結快照 `scraper/tests/golden/people_snapshot.json`，比照 stage 1 的 `frozen_path` 做法。
- **快照欄位白名單**，以 schema 驗證：
  - `people`：`name_ja`、`name_zh`、`name_en`、`eiga_person_id`、`verified`。
  - cache：`kind`、`query`、`status`、`payload`。
  - 不含 `id`、`notes`、`match_method`、時間戳記。
- 更新快照時，PR 必須附上 diff 摘要，由使用者審閱。
- CI 的 stage 3：人名查詢只讀快照、`offline=True`，零 HTTP 請求。驗收以測試斷言 `requests` 未被呼叫。
- **離線範圍的界線**：stage 3 建在 stage 2 之上，stage 2 會用即時 Supabase client 查 `works`（`eval_annotator.py` stage ≥ 2 時建立）。所以 stage 3 是「即時 `works` + 凍結人名」，並不完全可重現，也需要與 stage 2 相同的 Supabase secrets。凍結 `works` 不在本 spec 範圍。
- stage 3 仍會呼叫 GPT 修描述，需要 `OPENAI_API_KEY`。因此掛在 `eval-annotator-stage2.yml` 的週排程裡，或比照它另開一個只用 `schedule` 與 `workflow_dispatch` 的 workflow，不掛 `pull_request`。
- 缺快照或缺 `OPENAI_API_KEY` 時明確 skip，並以專用 exit code 結束，不靜默降級。
- 報告加入「人名覆蓋率」：有解析到人名的 case 數 ÷ 總數。

### 7. CLI：`scraper/people_admin.py`

| 子命令 | 作用 | 寫 production |
| --- | --- | --- |
| `set --name-ja X [--zh] [--en] [--eiga-id] [--not-a-person] [--note]` | 新增或修改一筆並設 `verified = true`、`match_method = manual` | 是；預設 dry-run，`--apply` 才寫 |
| `show --name-ja X` | 顯示 `people` 與 cache 中相關列，以及使用這個名字的事件數 | 否 |
| `reset-unverified [--match-method X] [--name-ja X]` | 刪除未 verified 列與對應 cache | 是；預設 dry-run |
| `propagate --name-ja X` | 產生舊事件的修正計畫（第 5 節） | 否 |

每次 `--apply` 前都要使用者核准 dry-run 結果。

### 8. 影響檔案

- 新增：`supabase/migrations/102_people.sql`、`scraper/people_admin.py`、`scraper/tests/test_people_store.py`、`scraper/tests/test_people_admin.py`、`scraper/tests/golden/people_snapshot.json`
- 修改：`scraper/person_name_lookup.py`、`scraper/annotator.py`、`scraper/eval_annotator.py`、`.github/workflows/eval-annotator-stage2.yml`（或新增 stage 3 workflow）、`.github/instructions/database.instructions.md`（Latest／next／Other tables）
- 既有測試會受影響：`scraper/tests/test_person_name_lookup.py`（依賴 `_person_cache.clear()` 與模組內部函式）、`scraper/tests/test_person_name_enrich_helpers.py`
- 若更新 SKILL 或 agent 檔，執行 `python3 scripts/sync_ai_adapters.py`

### 9. 必測項目

- `error` 不寫 DB、不寫 process 快取（mock 429、timeout）。
- 離線模式零 HTTP 請求。
- 寫入規則表的每一列，包含升級無 id 列、同名不重複。
- verified 列：外部查到不同結果時不被更新或刪除。
- 第 5 節的四種端到端情況。
- eiga 搜尋姓名不符時不採用；同名多個候選時寫 `ambiguous`。
- `normalize_name_ja` 與資料庫 CHECK 一致：Python 正規化後的值能通過 CHECK。
- 快照 schema 驗證：多出白名單外欄位即失敗。
- `propagate` 計畫正確分類三種 FC 擁有者，且不寫入任何表。

## 風險

| 風險 | 處理 |
| --- | --- |
| 錯誤結果被固定下來 | eiga 搜尋需姓名比對；`match_method` 標示證據強度；`reset-unverified` 手動清除；人工 `set` 永久優先 |
| 同名不同人共用一筆 | 有 eiga id 的以 id 區分；歧義只由 eiga 搜尋候選判定 |
| 同一人因先後取得 eiga id 而變成兩筆 | 寫入規則：有 id 時升級既有無 id 列；無 id 時遇同名不寫 |
| 暫時錯誤被記成查不到 | 三種狀態；`error` 不寫任何快取 |
| 正規化漏做產生第二個 key | 單一函式；資料庫 CHECK |
| 寫入語法與 index 不相容 | generated `person_key` 加一般 UNIQUE；本機用 supabase-py 實測 |
| 舊事件的自動鎖定擋住人工修正 | `propagate` 產生計畫，經 admin 頁人工修正；自動寫入見 #409 |
| 快照把內部資料帶進 repo | 欄位白名單、schema 驗證、更新時審閱 diff |
| stage 3 被誤認為完全可重現 | 明寫「即時 `works` + 凍結人名」 |
| migration 權限漏項 | 交易內 read-back `DO` 區塊，不符即中止 |
| migration 編號與 `feat/llm-cost-reset` 衝突 | 合併前重新確認編號 |
| 外部請求量的改善被 #361 混淆 | 先取 baseline（里程碑 0），比較時註明 #361 是否已合併 |

## References

- #392（來源 issue）、#389（`ファン` 姓，已修）、#361（enrich 重複執行與費用）
- 延後：#396（admin 頁）、#397（`work_people`）、#398（FC guard fail open）、#408（回填）、#409（`propagate` 寫入）
- `scraper/person_name_lookup.py`、`scraper/annotator.py`（`enrich_person_names_single`、`_resolve_event_people`、`_lock_fields_via_corrections`）、`scraper/qa_auto_fix.py`（回報修正寫 FC）
- `scraper/eval_annotator.py` stage 1 `frozen_path`、stage 2 `works` 查詢、stage 3
- `supabase/migrations/048_works_entity.sql`（DB 優先快取的前例）、`101_rpc_lockdown_followup.sql`（交易與 read-back 檢查的前例）
- `.github/instructions/database.instructions.md`（GRANT 規則、migration checklist）
