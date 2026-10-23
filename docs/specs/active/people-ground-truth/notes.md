# Notes

## 2026-10-23 production 唯讀查詢（Supabase project `cjtndektjjpvvjofdvzr`）

| 指標 | 數值 |
| --- | --- |
| 有 `performers` 的事件 | 1,607 |
| 有 `performers_zh` 的事件 | 1,073 |
| `performers` 不重複日文名 | 1,786 |
| 其中「カタカナ・カタカナ」形式 | 116 |
| 有 `director` 的事件 | 354 |
| `works` 列數 | 55 |
| `performers` 與 `performers_zh` 長度不一致的事件 | 11 |

人名相關 `field_corrections`，依 `corrected_by` 分組：

| field_name | corrected_by | 筆數 |
| --- | --- | --- |
| performer_zh | NULL | 219 |
| performer_en | NULL | 202 |
| performers_zh | NULL | 121 |
| performers_en | NULL | 80 |
| director_zh | NULL | 58 |
| director_en | NULL | 52 |

合計 732 筆，全部 `corrected_by IS NULL`。

web 端寫入 `field_corrections` 的地方都帶 admin／使用者 uid：

- `web/lib/adminEventMutationsCore.ts`
- `web/lib/reportActionsCore.ts`
- `web/lib/fieldCorrections.server.ts`
- `web/app/actions/owner-events.ts`

腳本端 `scraper/annotator.py` 的 `_lock_fields_via_corrections` 寫入 `corrected_by: None`。因此目前沒有 admin 人工確認的人名資料，這是 `proposal.md` 第 7 節不直接回填的依據。但 NULL 不全是 enrich 的腳本鎖定，見下一節依 `report_id` 的拆分。

使用的查詢：

```sql
SELECT field_name, coalesce(corrected_by::text,'<null>') AS by_kind, count(*)
FROM field_corrections
WHERE field_name IN ('performer_zh','performer_en','performers_zh','performers_en','director_zh','director_en')
GROUP BY 1,2 ORDER BY 3 DESC;
```

### 依 `report_id` 再拆分（同日補查）

| field_name | report_id IS NULL（腳本自動鎖定） | report_id 非空（回報後 `qa_auto_fix.py` 自動修正） |
| --- | --- | --- |
| performer_zh | 172 | 47 |
| performer_en | 153 | 49 |
| performers_zh | 97 | 24 |
| performers_en | 56 | 24 |
| director_zh | 58 | 0 |
| director_en | 52 | 0 |
| 合計 | 588 | 144 |

`qa_auto_fix.py` 的 `lock_clean`／`lock_empty` 只寫 `report_id`，不寫 `corrected_by`。所以 `corrected_by IS NULL` 不全是 enrich 的腳本鎖定；`propagate` 以 `corrected_by IS NULL AND report_id IS NULL` 判斷可刪除的列。

```sql
SELECT field_name, (corrected_by IS NULL) AS by_null, (report_id IS NULL) AS report_null, count(*)
FROM field_corrections
WHERE field_name IN ('performer_zh','performer_en','performers_zh','performers_en','director_zh','director_en')
GROUP BY 1,2,3 ORDER BY 1,2,3;
```

## 評審紀錄

### 第一輪：Plan Critic，2026-10-23

評審模型 claude-haiku-5-5，撰寫模型 claude-opus-5-5，同屬 Claude 家族，不算獨立的不同模型視角。

採納並已改進 `proposal.md`：

| 問題 | 修正 |
| --- | --- |
| verified 列在電影路徑與無「・」名字（9m88）不會被讀到 | 所有路徑先以日文名查 verified，不限片假名 |
| 現有 `except` 會把暫時錯誤寫成負向快取 | 三種狀態，`error` 不寫任何快取 |
| eiga 人物搜尋取第一筆、未比對姓名，found 又有 180 天期限 | 姓名比對、`match_method`、取消 found 期限 |
| partial unique index 無法配合 PostgREST `on_conflict` | generated `person_key` 加一般 UNIQUE；本機實測 |
| 「沒有 DB 退回現行行為」與離線 CI 矛盾 | 離線模式零網路；CI 改讀凍結快照 |
| `propagate` 只看 `corrected_by` 會誤刪回報修正的鎖定；沒有欄位範圍、備份、還原 | `report_id` 分流、欄位白名單、備份、無寫入即還原、fail closed |
| stage 3 讀 live DB 不可重現，且仍呼叫 GPT | 凍結快照；只用 schedule／dispatch；報告覆蓋率 |
| 重查得 not_found、同名歧義沒有定義 | 刪除未 verified 列；`ambiguous` cache |
| 沒有改版前的 baseline，且受 #361 混淆 | 里程碑 0 先加計數 |
| 里程碑過大、缺 `--warm-people` | 重切為 10 條 |
| `lookup_version` 依賴人工記得加版本號，且會靜默改寫 | 改為手動 `reset-unverified` |

另開 issue：#398 FC guard 在查詢例外時放行寫入（既有問題，不在本 spec 範圍）；延後項目 #396（admin 頁）、#397（`work_people`）。

### 第二輪：Codex，2026-10-23

Codex CLI 0.160.0，`codex exec -s read-only`。CLI 記錄的模型為 `gpt-6-luna`；報告開頭自稱「GPT-6.1-sol」，以 CLI 記錄為準。與撰寫者（Claude Opus）不同家族。

第一輪用 Claude subagent，使用者指出 Plan Critic 應該用 Codex，因此補做本輪。

採納並已改進 `proposal.md`：

| 問題 | 修正 |
| --- | --- |
| `propagate` 刪 FC、重跑、還原之間沒有交易，會有競態 | 第一版只產生 dry-run 計畫，人工經 admin 頁修正；寫入移到 #409 |
| `person_key` 讓同一人先無 id、後有 id 時變成兩筆，又被誤判為歧義 | 寫入規則表：有 id 時以 compare-and-set 升級無 id 列；無 id 時遇同名不寫 |
| 只在 lookup 查 verified 不夠，套用到欄位的路徑與 FC 鎖定順序沒寫清楚 | 第 5 節：產生 update 之前先做 verified 覆寫，鎖定的一定是 verified 值 |
| 歧義的判定來源不明 | 唯一來源：eiga 搜尋第一頁中姓名完全相等、eiga id 不同的候選 ≥ 2 |
| stage 3 建在 stage 2 上，仍會用即時 Supabase 查 `works` | 明寫「即時 `works` + 凍結人名」，需與 stage 2 相同的 secrets；凍結 `works` 不在範圍內 |
| 快照沒有欄位白名單，可能帶出 `notes` 等內部資料 | 白名單、schema 驗證、更新時審閱 diff |
| NFKC 沒有單一入口，漏做會產生第二個 key | `normalize_name_ja` 單一函式；資料庫 CHECK `name_ja = normalize(btrim(name_ja), NFKC)` |
| 回填不是三個目標的必要條件 | 移到 #408 |
| migration 權限檢查不完整 | 交易內 read-back `DO` 區塊；revoke `PUBLIC, anon, authenticated` |
| baseline 等待會阻塞主線；里程碑依賴順序 | baseline 並行收集，只要求里程碑 5 合併前滿 7 天；里程碑重排為 0–8 |
