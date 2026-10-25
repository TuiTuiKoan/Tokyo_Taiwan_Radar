---
title: Japan Scope Gate Phase 6b Plan
description: Transactional cleanup RPC, writer pause/drain runbook and approval package for the 22 reviewed non-Japan events
status: archived
updated: 2026-10-23
---

本檔是 Phase 6b／6c 的設計。進度看 issue #385 與 `label:spec:japan-scope-gate`，里程碑看 `tasks.md`。來源：Architect 草案（基準 `origin/main=02dfcf4c`），經 Codex 以 Plan Critic 角色評審（結論：修改後核可），再套用使用者 2026-10-23 的決定。

## 使用者決定（2026-10-23）

| 項目 | 決定 |
| --- | --- |
| 子事件 | 方案 A：22 筆（含 parent `3f693869` 與 4 個 child）同一 transaction 整組停用 |
| 執行者 | apply 與 `gh workflow disable／enable` 由使用者親自執行；agent 只做唯讀 read-back |
| 非 GitHub 寫入者 | 使用者聲明沒有。**但 2026-10-23 main 新增 launchd job `com.ttr.home-ip-scrape`（每週一 15:00 JST 在使用者的 Mac 跑 `main.py --source mot,taipei_fukuoka,jposa_ja`，寫 events），`launchctl list` 顯示已安裝**。它是非 GitHub writer，已納入 runbook；其餘仍只是使用者聲明，未獨立驗證 |
| pause／drain | 接受分層：DB 鎖加比對保證 cleanup 本身的原子性；pause／drain 只降低停用後被 in-flight 寫入者蓋回去的機率 |
| `updated_at` | 嚴格相等；任何漂移都重新 capture、重新核准 |
| 表鎖 | 接受 apply 期間短暫擋住 events 寫入，待拋棄式 Postgres 實測影響 |
| evidence | 核准包前人工重看 2026-08-04 的 evidence，特別是 A5 `f925a943`（規劃中的訪中） |
| rollback | CAS 同時比對 `is_active=false`、`deactivated_reason`、`deactivated_at`、`deactivated_by_pass` |
| `deactivated_by_pass` | 沿用 `admin_manual` |
| pending reports | 停用後留在 admin 佇列 |
| live 唯讀事實 | 由使用者在 Dashboard 執行唯讀 SQL；agent 不用 Supabase MCP 連接器查 production |
| 拋棄式測試環境 | **未決**：本機 `docker` daemon 不可用，也沒有 `psql`／`postgres`；PGlite 是單連線，無法測併發鎖。待決定：Supabase branch（可能有費用）或在本機安裝 Postgres |

## 事實與糾正

- 4 個 child 本來就在 22 筆內。原 gate 把「target 有 parent」與「有 active 列指向 target」都當 blocker；要改成封閉家族判定：每個 target 的 `parent_event_id` 必須是 NULL 或屬於 target 集合；非 target 的 child 集合必須等於 manifest 的 `external_children`，且全部 inactive。
- 現行 snapshot 分頁讀、逐筆讀、關係另讀，不是單一快照；before-image 缺 `deactivated_at`、`deactivated_reason`、`deactivated_by_pass` 與 `raw_description_sha256`，無法 exact rollback。
- 沒有可靠的安靜時段：`scraper.yml` 實際啟動約 02:47–03:10 UTC、單次約 2.5–2.8 小時；`merger.yml` 延遲 4–5 小時。所以用 disable＋drain，不靠避開排程。
- Migration 編號：`scripts/migration_next_id.py` 在 2026-10-23 動工時回 `103`（099、102 已被 llm-cost-reset 使用，100、101 是 RPC lockdown）。本 RPC 使用 `103_scope_cleanup_rpc.sql`；若套用前被占用，依腳本重新編號。
- 先例：migration 100／101 用 `REVOKE … FROM PUBLIC, anon, authenticated` 加 `GRANT … TO service_role`，並用尾端 `DO` 區塊在 ACL 不符時讓 transaction 失敗。本 RPC 沿用這個模式。

## RPC 設計

`public.apply_scope_cleanup(p_mode text, p_manifest jsonb) RETURNS jsonb`，`p_mode` 必填：`'validate'` 或 `'apply'`。不做 snapshot RPC；capture 沿用 Python 讀取，再立刻以 `validate` 檢查。

**兩個模式的保證不同，必須分開寫**：
- `validate`：未鎖、唯讀的預檢，沒有原子保證，只用於核准包。
- `apply`：取得表鎖後重做全部檢查，才有交易保證。測試要證明共用控制流程不會讓 apply 跳過鎖或 CAS。若實作後難以審查，改成共用內部函式加兩個薄 RPC。

**函式屬性**：`SECURITY INVOKER`、`SET search_path = pg_catalog`、`SET lock_timeout = '5s'`、owner `postgres`、全部 schema-qualified。不用 `SECURITY DEFINER`（service_role 本來就能寫 events，DEFINER 只會在 ACL 漂移時變成提權路徑）。`current_user IN ('service_role','postgres')`，否則 `42501`。ACL：`REVOKE ALL … FROM PUBLIC, anon, authenticated`，再 `GRANT EXECUTE … TO service_role`。本 migration 只放函式，不改任何 RLS policy 或 grant。

**apply 交易順序**：
1. 驗呼叫者與參數：JSON 形狀嚴格、id 唯一、筆數等於 `target_count` 且 ≤ 50、digest 符合 `^[0-9a-f]{64}$`。
2. `LOCK TABLE public.events IN SHARE ROW EXCLUSIVE MODE`。
3. 冪等：22 筆都已 inactive 且 reason 帶同一 digest 前 12 碼 → 回 `noop`；混合狀態 RAISE。
4. `SELECT … ORDER BY id FOR UPDATE`；缺列 RAISE 並列 id。
5. 逐欄 `IS NOT DISTINCT FROM` 比對 before-image（含 `updated_at` 嚴格相等、`raw_description_sha256`）；所有不一致一次收集，用 `40001` 帶 jsonb detail 回報。
6. 封閉家族檢查（見上）。
7. 單一 set-based `UPDATE`：`is_active=false`、`deactivated_at`（整批同一個 `clock_timestamp()`）、`deactivated_reason='out_of_scope: <category> - scope cleanup <digest12>'`、`deactivated_by_pass='admin_manual'`。`ROW_COUNT` 必須等於 N，否則 RAISE 回滾。`parent_event_id` 不動。
8. 同交易重讀 after-image，驗證 active 數量差恰為 N，回傳 `{status, applied_count, deactivated_at, targets, active_before, active_after}`。

DB 不重算 digest（無法重現 Python canonical JSON）；digest 對 DB 只是稽核字串。digest 與核准的綁定由 CLI 負責（script SHA、`--expect-digest`、沿用 `a18e1a49`）。

**表鎖與 FK（Codex 評審有誤，已實測更正）**：Codex 認為 `SHARE ROW EXCLUSIVE` 會和 FK 檢查需要的表級鎖衝突。在 PostgreSQL 17.11 實測，FK 檢查只取 `ROW SHARE`，與 `SHARE ROW EXCLUSIVE` 不衝突：對非 target 事件的 `saved_events` insert 不受阻；只有指向 target 列的 FK 檢查會因 apply 的 `FOR UPDATE` 等到 commit。events 本身的 INSERT／UPDATE／DELETE 一律被擋（`tests/test_scope_cleanup_rpc.py`）。其餘驗收項目（既有交易先持鎖、`lock_timeout` 零寫入、concurrent child insert、約束違反整批回滾、timestamp 精度與時區）已涵蓋；PostgREST 對 `40001` 與逾時的實際回應仍待 CLI 階段在 staging 外無法實測，CLI 以 JSON body 的 `code` 判斷。

**替代方案**：CLI 產生一次性 `DO $$…$$` 區塊由使用者貼 Dashboard。保留為退路；需另外綁定 SQL 文字，且 Dashboard 多語句的交易行為未驗證。

## pause／drain／resume

分層說明（避免再被誤讀）：
- **cleanup 會不會做到一半壞掉**：由 DB 鎖加比對保證，不需要 pause。
- **cleanup 之後會不會被蓋回去**：annotator 讀 parent 後呼叫 GPT 數分鐘、commit 後才 upsert child 且 `is_active: True`；scraper 的 `force_rescrape` 路徑也有 stale-read。表鎖擋不住這類 commit 在 apply 之後的寫入，所以需要 drain。

不得宣稱 pause 關閉所有復活路徑，除非 writer 盤點完整、DB trigger 查清。等待時間要如實寫：drain 必須等 in-flight run 結束，最長約 3 小時；不取消執行中的 run。

**Runbook（使用者執行）**：capture `gh workflow list --all --json name,state,path` → `gh workflow disable`（逐一，讀回確認）→ drain（每個 writer workflow 的 `gh run list` 無 `in_progress`／`queued`）→ 取得 094 maintenance lock（`_oneoff_admin_reports_maintenance.py acquire`）→ settle → idleness probe（間隔兩次讀 `count(*)`、`max(updated_at)`、`max(created_at)` 相同；DELETE 偵測不到）→ apply → release lock 並確認 inactive → enable 回精確原狀 → 監控第一個 run。disable 期間禁止人工 `workflow_dispatch`（`annotate-now`、`scrape-now`、`enrich-and-annotate` 等）。lock 與 disable／enable 都是對外狀態變更，必須列在核准句。

**本機 launchd writer**：`scripts/launchd/com.ttr.home-ip-scrape.plist`（週一 15:00 JST；Mac 睡眠時會在喚醒後補跑）。runbook 要求使用者在 disable 前 `launchctl bootout "gui/$(id -u)/com.ttr.home-ip-scrape"`、drain 時確認沒有 `main.py` 程序在跑（`pgrep -fl main.py`）、resume 時 `launchctl bootstrap` 還原；apply 避開週一。

**writer 盤點**：AST 腳本掃 `.table("events")` 寫入鏈與 `.rpc(` 名單，對應 workflow `run:` 與排程；GitHub 側已知 `scraper.yml`、`merger.yml`、`error-recovery.yml`、`refetch-thin-events.yml`、`qa-heartbeat.yml`、`qa-auto-fix.yml` 與手動觸發的三支；web 側 `owner-events`、`annotate-event`、`review-status` 已檢查 094 lock；DB 側 trigger／function 待 live 查詢；非 GitHub 寫入者只有使用者聲明。

## Manifest v2 與核准包

- 綁定 project ref `cjtndektjjpvvjofdvzr`（斷言 `SUPABASE_URL`）、`git_head`（乾淨的 `origin/main` exact SHA）、script SHA、migration 檔 SHA（RPC 定義 md5 無法經 PostgREST 取得，改以 migration SHA 加使用者的 read-back 綁定）。script 或 migration 變更後必須重新 capture 與核准。
- 每筆含完整 before-image（新增 `deactivated_*` 與 `raw_description_sha256`）、evidence 摘錄；加 `external_children`；pending `event_reports`、`saved_events`、`announcement_events` 計數（僅供核准參考）。
- 沿用 `a18e1a49`：no-replace 發布、0400、strict contract、digest 內嵌與外部比對。v1 從未產出 manifest，升版沒有相容成本。輸出另備份到 `~/.ai-notes/ttr/japan-scope-gate/`。
- 核准包：新 digest、22 筆 full UUID 加 `https://tokyotaiwanradar.com/ja/events/<id>` 連結、before-image 與 evidence、`validate` 結果、影響計數、writer 盤點與 drain 證據、rollback SQL 與 SHA。核准句須複述動作（新 digest、disable／drain／resume、lock、22 筆停用、子事件家族範圍）；簡短的「好」不算。
- 上線前必查：公開事件頁、首頁、sitemap 的實際 active 篩選行為（`web/app/[locale]/page.tsx` 的清單沒有 `parent_event_id IS NULL` 過濾，與 `database.instructions.md` 不符）。

## CLI v2（`scraper/_oneoff_deactivate_non_japan_scope.py`，#401）

模式：`--snapshot`（捕捉 v2 manifest，live `validate` 通過才寫檔）、`--validate`、`--approval-package`（離線）、`--rollback-sql`（離線）、`--apply`、`--readback`。只有 `--apply` 會寫入，且只經 RPC。`--apply` 需要：digest 與 manifest 契約驗證、script 與 migration SHA 吻合、`SUPABASE_URL` 指向 `cjtndektjjpvvjofdvzr`、live `validate` 通過、**互動終端機上輸入 digest 前 12 碼**（沒有 TTY 直接拒絕，所以 agent 無法代跑）；成功後寫不可覆蓋的 journal。snapshot 要求 script 與 migration 已 commit 且無修改。

回滾 SQL 可在 apply 前預先產生：不需要知道 `deactivated_at`，改為要求 22 筆共用同一個 `deactivated_at`，並比對 `is_active=false`、`deactivated_by_pass`、本 manifest 的 reason 標記，任一列不符整批中止。

## Apply 後 read-back 與回滾

read-back：RPC 的 per-id after-image；獨立唯讀查詢確認 22 筆 `is_active=false` 與 reason／`deactivated_by_pass` 正確；active identity 集合差恰為這 22 個 id；沒有 active 列的 `parent_event_id` 指向 target；anon 查這 22 筆為 0 列、事件頁 404；CLI 的 `--readback` 全數符合（apply 的回應遺失時不要重跑 `--apply`：資料已變，驗證會失敗，改以 `--readback` 判斷；RPC 層的重試仍是 `noop`，由測試涵蓋）。操作步驟見 `runbook.md`。復驗起點定為 apply 後第一個「成功完成」的 `scraper.yml` run；若排程延遲或失敗，順延，不以固定 24 小時代替。

回滾：不做 rollback RPC。CLI 在核准包內預先產生 CAS 保護的 rollback SQL（`UPDATE … WHERE id=… AND is_active=false AND deactivated_reason=… AND deactivated_at=… AND deactivated_by_pass=…`，驗證列數 = 22），由使用者在 Dashboard 執行。`updated_at` 無法還原（trigger 會刷新）。第一個後續寫入這些列的 writer 之後只能 fix-forward。rollback 是 apply 核准的必要保障，須在 6c 前演練。

## 里程碑對應（`tasks.md` 的 Phase 6b／6c 列）

1. 設計定稿（本檔）。
2. Spec 與看板同步：`tasks.md` 勾 Phase 5（附 PR #359、merge `b19a08e9`、Vercel deployment 證據）。
3. live 唯讀事實：FK、triggers、grants、097 狀態、22 筆 pending reports，結果寫入 `notes.md`；migration 設計在此之後定版。
4. Migration（編號以 `migration_next_id.py` 為準）與拋棄式 Postgres 驗收矩陣（RPC 與 CLI 共用同一份矩陣）。
5. CLI v2。
6. writer 盤點與 runbook（`gh` 唯讀演練併入 runbook dry-run，不另作交付物）。
7. 驗證、PR、merge、deploy（不等於 apply 核准）。
8. 使用者在 Dashboard 套用 migration 並 read-back；先備好文件與 read-back 指令，套用後再記錄結果。
9. production 唯讀重新 capture、`validate`、核准包，使用者對新 digest 明確核准。
10. 【6c】disable／drain、lock、apply、read-back、resume、復驗。

細項（例如 AST 盤點腳本、rollback 產生器、`database.instructions.md` 的重複與錯接修正、首頁過濾敘述查核、`scraper.yml` 註解時間）以 issue 追蹤，貼 `spec:japan-scope-gate`，不寫進 `tasks.md`。

## 待補證據

live 唯讀事實（FK、trigger、權限、097 未套用、22 筆現況與關聯計數）已在 2026-10-23 取得，見 `notes.md`。A4 的 `3f693869` 與 `fe47a25c` 在 8/4 probe 之後（2026-08-31）被寫入過，必須重驗。

Architect 引用的 GitHub 事實（`origin/main=02dfcf4c`、workflow 啟動延遲與執行時長、近期失敗次數、沒有 disabled workflow）Codex 無法獨立驗證，進入 7 前由 Engineer 重新查詢並附查詢日期與輸出。annotator 行號以計畫鎖定的 exact SHA 為準（`is_active: True` 約在 3903 行，非 3936）。
