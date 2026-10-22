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
| migration 097 | `sources.connpass`、`sources.doorkeeper` 仍是 `is_active=true` | **097 尚未套用**，`database.instructions.md` 的「not yet applied」正確。097 與本工作無關，由使用者另行決定 |

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

