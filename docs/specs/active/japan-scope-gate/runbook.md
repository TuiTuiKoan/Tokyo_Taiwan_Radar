---
title: Japan Scope Gate Phase 6c Runbook
description: Operator steps to pause writers, apply the reviewed cleanup, read back and resume
status: active
updated: 2026-10-23
---

使用者親自執行本手冊的所有指令（apply 與 `gh workflow disable／enable` 的決定，2026-10-23）。agent 只做唯讀 read-back 與公開網址檢查。設計與取捨見 `plan.md`；writer 盤點由 `scripts/inventory_events_writers.py` 產生。

**已於 2026-10-23 依本手冊執行一次**（digest `f9f7…fb054`，22 筆停用），過程與修正見 `notes.md`。下一次 cleanup 要重新 capture、重新核准，不能沿用這份 manifest 與核准。

**每行指令保持短行**：終端機會在長行中間換行，貼上時會把一行拆成兩個指令（2026-10-23 發生過一次）。

## 變數（每個新終端機視窗先設一次）

```
REPO="$HOME/Development/3-TTR/Tokyo Taiwan Radar"
D="$HOME/.ai-notes/ttr/japan-scope-gate"
M="$D/scope_manifest_20261022T190533Z.json"
DG=f9f7238452330f4ccd4e2eff6af695183f57a2be9e6fe6ba3e55ed64515fb054
P=../.venv/bin/python
S=_oneoff_deactivate_non_japan_scope.py
```

`P`、`S` 是縮寫，讓第 3、4 節的指令不會長到被換行；它們是相對路徑，**只能在 `$REPO/scraper` 目錄使用**。貼上變數後用 `echo "$M"`、`echo "$DG"` 確認有值（2026-10-23 曾因變數是空的，指令被拆成兩條而失敗）。

`M` 與 `DG` 是 2026-10-23 的 snapshot。重新 capture 後兩者都要換成新的值；舊 digest 的核准不能用在新 manifest。

## 0. 前置條件（任一不成立就不要開始）

- [ ] 核准包（`$D/approval_package_<digest>.md`）已重看，A5 的 [f925a943](https://tokyotaiwanradar.com/ja/events/f925a943-7c75-4d4b-9ebe-c8ae35f353d9) 與有 1 筆 pending report 的 [9e1c9b0b](https://tokyotaiwanradar.com/ja/events/9e1c9b0b-d191-4ae1-b420-305dbc19570b) 已特別確認
- [ ] 你已對**這個 digest** 說出明確核准句（見文末），不是簡短的「好」
- [ ] 不是星期一（launchd 的 `home-ip-scrape` 週一 15:00 JST 執行；Mac 睡眠時醒來會補跑）
- [ ] 主 checkout 在 `origin/main`、工作目錄乾淨：`cd "$REPO" && git status --short && git log --oneline -1`
- [ ] 回滾 SQL 在手：`ls -l "$D"/rollback_$DG.sql`
- [ ] migration 103 已套用（2026-10-23 已確認）

## 1. 捕捉現況（只讀）

```
cd "$REPO"
gh workflow list --all
gh run list --status in_progress --limit 20
launchctl list | grep ttr
python3 scripts/inventory_events_writers.py --workflows > "$D/pause_list.txt"
Q='.[]|select(.state=="active")|.path'
gh workflow list --all --json path,state --jq "$Q" > "$D/ap.txt"
sed 's#.github/workflows/##' "$D/ap.txt" > "$D/active_before.txt"
grep -Fxf "$D/active_before.txt" "$D/pause_list.txt" > "$D/to_pause.txt"
wc -l "$D/to_pause.txt"
cat "$D/to_pause.txt"
```

`wc -l` 是 0 就不要繼續。2026-10-23 實際清單是 16 個。

`to_pause.txt` 是「目前是 active 且可能寫 events」的 workflow；resume 時只還原這份，原本就停用的不動。盤點是過度近似（能 import 到會寫 events 的模組就列入），多停幾個無害。

## 2. 暫停 writer

1. **launchd**：`launchctl bootout "gui/$(id -u)/com.ttr.home-ip-scrape"`，再確認 `launchctl list | grep ttr` 沒有輸出、`pgrep -fl main.py` 沒有輸出。
2. **GitHub workflows**：
   ```
   test -s "$D/to_pause.txt" && echo OK
   xargs -n1 gh workflow disable < "$D/to_pause.txt"
   gh workflow list --all
   ```
   `xargs` 不是互動終端機，`gh` 不會逐項印出 ✓，所以一定要用 `gh workflow list --all` 讀回，確認 `to_pause.txt` 的每一個都不是 active（顯示 `disabled_manually`）。**停用期間任何人都不要手動 dispatch**（`annotate-now`、`scrape-now`、`enrich-and-annotate` 等）。
3. **等 in-flight run 結束（drain）**：不取消執行中的 run（取消可能留下半寫入的 annotation）。`scraper.yml` 單次約 2.5–2.8 小時，預留 3 小時。
   ```
   gh run list --status in_progress --limit 20
   gh run list --status queued --limit 20
   ```
   `in_progress` 沒有輸出才算 drain 完；有輸出就等，每 10–15 分鐘再跑一次，可用 `gh run view <run-id> --json status,conclusion` 看單一 run。`queued` 若有數週甚至數月前就排隊、從未開始的 run（2026-10-23 有兩個：Refetch Thin Events 自 2026-08-19、web-darkmode-smoke 自 2026-05-15），視為殘留，不用等，也先不要取消。
4. **web 維護鎖**（094；擋住 admin／owner 對 events 的寫入）：
   ```
   cd "$REPO/scraper"
   $P _oneoff_admin_reports_maintenance.py acquire --reason "cleanup"
   $P _oneoff_admin_reports_maintenance.py status
   ```
   `--reason` 用單一短字，不要有空白或換行（2026-10-23 的 reason 被貼上換行拆成帶換行的文字）。**記下印出的 `window_id`**，release 要用。
5. **idleness probe**（Dashboard SQL Editor，間隔約 60 秒執行兩次，兩次結果必須完全相同）：
   ```sql
   select count(*) as events, count(*) filter (where is_active) as active,
          max(updated_at) as max_updated, max(created_at) as max_created,
          (select max(ran_at) from public.scraper_runs) as last_run
   from public.events;
   ```
   記下 `active`（apply 後應恰好少 22）。DELETE 偵測不到；非 GitHub／非本機的寫入者只有你的聲明。

## 3. Apply

```
cd "$REPO/scraper"
$P $S --validate --manifest "$M" --expect-digest "$DG"
$P $S --apply --manifest "$M" --expect-digest "$DG"
```

`--validate` 回 `validate=ok` 才繼續。`--apply` 會再驗證一次，然後要求輸入 digest 前 12 碼（`f9f723845233`）。成功會印 `status=applied`、`applied_count=22` 與 journal 路徑。

- **回 `live validate failed`／`40001`／drift**：零寫入。**不要重試**；停在暫停狀態，回報給 agent（需要重新 capture 與重新核准）。
- **指令中斷或回應遺失**：不要再跑 `--apply`（驗證會因資料已變而失敗）。直接跑第 4 節的 `--readback`；全部符合就是已套用。
- **`lock_timeout`（55P03）**：表示有寫入者持有 events 的鎖。零寫入；找出誰（回頭檢查第 2 節），不要硬重試。

## 4. Read-back

```
$P $S --readback --manifest "$M" --expect-digest "$DG"
```

預期 `readback=ok`（22 筆都停用且帶本 manifest 的標記、`deactivated_at` 一致、沒有 active 子事件）。再在 Dashboard 執行：

```sql
select count(*) filter (where is_active) as active,
       count(*) filter (where deactivated_reason like '%scope cleanup f9f723845233') as marked
from public.events;
```

預期 `active` = 第 2 節記下的值 − 22，`marked` = 22。接著告訴 agent「apply 完成」，agent 會用公開網址做唯讀檢查：這 22 筆的詳情頁要顯示 not-found 內容並帶 `noindex`（HTTP 狀態碼是 200，不是 404：`[id]/loading.tsx` 先串流送出 200，見 issue #427），首頁不含它們，sitemap 在快取更新後不含它們（apply 後數分鐘內仍可能含部分，見 issue #427）。這些公開頁面的現象不影響是否可以進第 5 節恢復；是否恢復只看 `--readback` 與 Dashboard SQL。

## 5. 恢復

1. 釋放維護鎖：`$P _oneoff_admin_reports_maintenance.py release --window-id <WINDOW_ID>`，再 `status` 確認 inactive。
2. 啟用 workflow（只還原原本 active 的）：
   ```
   xargs -n1 gh workflow enable < "$D/to_pause.txt"
   gh workflow list --all
   ```
   讀回時所有 workflow 應與暫停前一致；可用 `gh workflow list --all --json path,state --jq "$Q"` 與 `active_before.txt` 比對。
3. 重新載入 launchd：`launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.ttr.home-ip-scrape.plist`，再 `launchctl list | grep ttr`。
4. 第一個完整的 `scraper.yml` run 成功結束後，再跑一次 `--readback`，確認沒有被蓋回去（復驗起點是第一個「成功完成」的 run，不是固定 24 小時）。

## 6. 回滾

只在確認結果有誤時使用，**維持暫停狀態**直到完成：

1. `pbcopy < "$D/rollback_$DG.sql"`，在 Dashboard SQL Editor 新 query 貼上執行。它會鎖 `events`，要求 22 筆共用同一個 `deactivated_at`、都帶本 manifest 的標記，任一列不符就整批中止（不還原任何東西）。
2. 還原 `is_active`、`deactivated_at`、`deactivated_reason`、`deactivated_by_pass`；`updated_at` 無法還原（trigger 會刷新）。
3. 第一個後續寫入這些列的 writer 之後只能 fix-forward（不能保證回滾仍可用）。
4. 回滾後照第 5 節恢復。

## 7. 中止條件（任一出現就停在目前步驟並回報）

- drain 超過 4 小時仍有 run
- idleness probe 兩次結果不同
- `--validate` 回 invalid 或任何 drift
- 維護鎖 `acquire` 失敗或 `status` 不是預期狀態
- 你不確定的任何狀況

## 核准句範本

核准必須同時涵蓋這些動作；請複述後再確認，簡短的「好」不算：

> 我核准 manifest_digest `f9f7238452330f4ccd4e2eff6af695183f57a2be9e6fe6ba3e55ed64515fb054`：我會親自停用並事後還原列在 `to_pause.txt` 的 GitHub workflows、卸載並事後重新載入 `com.ttr.home-ip-scrape`、取得並釋放 094 維護鎖，然後執行 `--apply`，將核准包列出的 22 筆事件（含 jizue 巡演的 parent 與 4 個 child）以 `is_active=false`、`deactivated_by_pass=admin_manual` 停用；我已重看 8/31 才改過的 `3f693869`、`fe47a25c`，以及 A5 的 `f925a943`；回滾 SQL 的 SHA 是核准包所列。
