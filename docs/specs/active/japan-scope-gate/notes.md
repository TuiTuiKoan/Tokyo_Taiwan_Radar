---
title: Japan Scope Gate Notes
description: Live read-only evidence collected for Phase 6b
status: active
updated: 2026-10-23
---

## 2026-10-23 live 唯讀事實（issue #399）

使用者在 Supabase Dashboard SQL Editor 執行唯讀查詢，結果如下。查詢只含 SELECT。

| 項目 | 結果 | 對設計的影響 |
| --- | --- | --- |
| 22 筆是否都存在 | `targets_found = 22`，全部 `is_active=true`，`deactivated_reason` 皆 NULL | 可進入 capture |
| 名單外的 child | `children_not_in_list = []` | `external_children` 預期為空 |
| `parent_event_id` | 有 FK：`FOREIGN KEY (parent_event_id) REFERENCES events(id) ON DELETE SET NULL`；另有 `merged_into_event_id`、`organizer_id`、`owner_user_id`、`venue_id`、`work_id` 的 FK | UPDATE 不觸發 `ON DELETE SET NULL`。其他表（`saved_events` 等）insert 時的 FK 檢查只取 `ROW SHARE`，與 `SHARE ROW EXCLUSIVE` 不衝突（PostgreSQL 17.11 實測）；只有指向 target 列的 FK 檢查會等 apply commit |
| `events` trigger | 只有 `events_updated_at BEFORE UPDATE … set_updated_at()` | `updated_at` 嚴格相等等於「自 capture 後沒有任何 UPDATE」；apply 自己的 UPDATE 也會刷新 `updated_at`，rollback 無法還原它 |
| 寫入 `events` 的 public 函式 | 只有 `confirm_scope_report(uuid,text,text)`（migration 098） | DB 側沒有其他 writer |
| `events` 表權限 | `service_role` 有 UPDATE；`anon`、`authenticated` 也有全部表權限（含 `TRUNCATE`），靠 RLS 擋 | `LOCK TABLE` 需要的權限具備 |
| migration 097 | `sources.connpass`、`sources.doorkeeper` 仍是 `is_active=true` | 當時 097 尚未套用。097 與本工作無關，使用者已於 2026-10-25 另行套用並讀回確認（`sources_active` 0、`doorkeeper_active` 0、`doorkeeper_retired` 5、`research_pending` 0），`database.instructions.md` 與 migration 檔頭已更新 |

### 22 筆的 `updated_at`

- 20 筆的 `updated_at` 在 2026-05-13 到 2026-08-01 之間，早於 2026-08-04 的 probe。
- **`3f693869`（A4 parent）與 `fe47a25c`（A4 child）的 `updated_at` 是 2026-08-31 05:08:17**，晚於 8/4 probe，表示 8/4 之後被寫入過。這兩筆的 before-image 與 evidence 必須在 capture 時重驗，核准包前人工重看。
- 其餘 child：`7c6c1e7f`、`a62ce9e1` 為 2026-07-20，`47262b02` 為 2026-06-26。

### 關聯計數（會受影響的使用者可見資料）

- `saved_events`：22 筆皆 0。
- pending `event_reports`：只有 `9e1c9b0b-d191-4ae1-b420-305dbc19570b`（南國國際生活節）有 1 筆，停用後留在 admin 佇列（已決定接受）。核准包需附該 report 內容。
- `announcement_events`：`2af3196f` 2、`3d74504d` 2、`3f693869` 3、`5f3866d0` 2、`e74020ee` 6，共 15 筆連結。公開公告頁查詢帶 `.eq("is_active", true)`（`web/app/[locale]/announcements/[slug]/page.tsx:67–71`），停用後這些事件會從公告頁消失，不會留下死連結；連結列不刪除，rollback 後恢復顯示。

## 其他

- 使用者聲明沒有 GitHub Actions 以外的 events 寫入者（2026-10-23），未獨立驗證。
- 同日 main 新增 launchd job `com.ttr.home-ip-scrape`（commit `27b9539e`，每週一 15:00 JST 在使用者的 Mac 跑 `main.py`，寫 events）；`launchctl list` 顯示已安裝。因此上一句的聲明已不成立，runbook 須納入此 job（見 plan.md）。

## 2026-10-23 migration 103 套用

使用者在 Dashboard 以 postgres 先做 rollback-only 試跑（成功），再正式套用（成功）。read-back：`prosecdef=false`、owner `postgres`、`proconfig` = `["search_path=pg_catalog","lock_timeout=5s"]`、ACL `{postgres=X/postgres,service_role=X/postgres}`。ACL 沒有 `anon`、`authenticated` 或 PUBLIC 條目，所以它們沒有 EXECUTE。尚未用 `has_function_privilege` 與匿名呼叫實測 `42501`，進 production `--snapshot` 前不需要；cleanup 仍未執行。

套用後 migration 檔頭只改了註解（APPLY STATUS），函式本體不變；`operator.migration_sha256` 以此後的檔案為準。

## 2026-10-23 production snapshot 的證據核對

第一次 `--snapshot` 在證據檢查停止（沒有寫出 manifest）。使用者在 Dashboard 以唯讀 SQL 核對全部 44 項證據，只有一項不符：

- `fe47a25c`（A4 child，台北公演）：`raw_description` 在 2026-08-31 被換成一行摘要「jizueの台北公演が9月17日にTHE WALL LIVE HOUSEで開催されます。」，不再含「台北・香港公演」。內容仍是日本樂團 jizue 在台北 THE WALL LIVE HOUSE 的公演（與 child `7c6c1e7f` 同場地），分類不變；證據條件改為 `raw_description` 含「jizueの台北公演」。其餘 43 項證據仍成立。

此判斷需要使用者在核准包審核時確認，不是自動核准。

## 2026-10-23 production apply 執行紀錄

使用者對 manifest digest `f9f7238452330f4ccd4e2eff6af695183f57a2be9e6fe6ba3e55ed64515fb054` 說出明確核准句（涵蓋 workflow 暫停與還原、launchd 卸載與重載、094 維護鎖、apply 22 筆），並親自執行 runbook。agent 只做唯讀檢查。核准包審核時，使用者重看 `3f693869`、`fe47a25c`、`f925a943`（NHK 報導 5/15 上海 APEC 會議，已過期）、`9e1c9b0b`（有 1 筆 pending report），決定四筆都照其餘一起停用，清單與 digest 不變。

| 時間（JST） | 動作 | 結果 |
| --- | --- | --- |
| 14:5x | `gh workflow disable`（`to_pause.txt` 的 16 個） | 讀回全部 `disabled_manually`，其餘 27 個維持 active |
| 14:5x | `launchctl bootout com.ttr.home-ip-scrape` | `launchctl list` 不再列出 |
| 14:53 | drain：`Run Merger`（run 39908079646，14:51 以 schedule 啟動）自然結束 | `success`；之後沒有任何 in-flight run |
| 14:56 | 094 維護鎖 `acquire` | window_id `6664d275f2b641df835d8d2abef94697` |
| 14:5x | idleness probe 兩次 | 完全相同：events 3373、active 2406、`max_updated` 05:31:57 UTC、`max_created` 04:10:12 UTC、`last_run` 04:55:56 UTC |
| 15:0x | `--validate` | `validate=ok target_count=22` |
| 15:21 | `--apply` | `status=applied`、`applied_count=22` |
| 15:2x | `--readback` + Dashboard SQL | `readback=ok`；`active` 2384（少 22）、`marked` 22 |
| 15:29 | 維護鎖 `release` | `active=false` |
| 15:3x | `gh workflow enable`、`launchctl bootstrap` | 43 個 workflow 與暫停前逐行比對相同；`home-ip-scrape` 重新載入 |

留存於使用者本機 `~/.ai-notes/ttr/japan-scope-gate/`（0400）：`scope_manifest_20261022T190533Z.json`、`approval_package_f9f7…fb054.md`、`rollback_f9f7…fb054.sql`（SHA256 `2119c4072fc38dcb2ca3c729f98fbda97959da1742caefffe67483cb33191cb3`，**未使用**）、apply journal `scope_manifest_20261022T190533Z.json.apply-20261023T062124Z.json`。

### 公開網址檢查（agent 唯讀，2026-10-23 15:2x–15:3x JST）

- 22 筆詳情頁（ja）全部回 **HTTP 200**，內容是 Next.js not-found 畫面：`<title>` 為通用站名並帶 `<meta name="robots" content="noindex">`；對照用 active 事件有事件標題且無 noindex。推測是 `[id]/loading.tsx` 先送出 200 串流，之後 `page.tsx` 才呼叫 `notFound()`（未驗證）。因此 runbook 的驗收標準由「回 404」改為「not-found 內容加 noindex」。
- 首頁（ja）不含這 22 筆。
- sitemap（`last-modified` 06:23:36 GMT，apply 後約 2 分鐘）仍含 22 筆中的 10 筆；`web/app/sitemap.ts` 查詢有 `is_active=true`。同日 17:51 JST 重抓（`x-vercel-cache: MISS`）已是 0/22，確認是快取延遲，自行恢復。

### 復驗（2026-10-24 14:3x JST）

apply 之後有寫入者跑過：2026-10-24 的 `scraper.yml`（run 40056871578，12:05 啟動、14:31 結束）整體 `failure`，但失敗只在最後一步 `Fail on LLM step errors`，scrape 與寫入步驟都成功；前一天（10-23，暫停之前）的 run 也是同一步失敗，不是 cleanup 造成，追蹤於 issue #403。

- `--readback`：`readback=ok`。
- Dashboard 逐列查 22 筆：`is_active=false`、`deactivated_by_pass=admin_manual`，`deactivated_at` 全部是 `2026-10-23 06:21:24.176993+00`，`updated_at` 全部是 `2026-10-23 06:21:23.759939+00`（apply 當下，之後沒有任何 writer 動過），`deactivated_reason` 全部以 `scope cleanup f9f723845233` 結尾。
- 計數：`active` 2397、`marked` 22、`new_after_apply` 13；2384 + 13 = 2397，差額全部是 apply 之後新增的事件。
- 公開網址：22 筆詳情頁仍是 not-found 加 `noindex`，sitemap 0/22。
- 過程中使用者貼回一次 `active` 2397、`marked` 0。逐列查證 22 筆的 reason 都以該字串結尾、`updated_at` 沒動，資料沒有被改；那次查詢為何得 0 不明，未再追查，之後同一條 SQL 回 22。

### 待辦

- 停用期間 `gh run list` 還有兩個從未開始的 queued run（Refetch Thin Events 32219879166，自 2026-08-19；web-darkmode-smoke 25906992019，自 2026-05-15），drain 檢查須排除；歸入 issue #403 追蹤。

### 對 runbook 的修正（已併入 `runbook.md`）

- 貼上長指令會被終端機在中間換行拆成兩條，這次又發生一次（`xargs` 迴圈與 `--validate`，都在參數檢查階段失敗、零寫入）；指令改成短行，並用縮寫變數 `P`、`S`。
- `gh workflow disable／enable` 經 `xargs` 執行時不是互動終端機，不會逐項印出 ✓，要用 `gh workflow list --all` 讀回確認。
- 維護鎖的 `--reason` 被換行拆開，reason 欄位帶了一段換行；只影響註解文字。

