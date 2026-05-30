---
description: 每週完整開發週報 — 整合 DB 爬蟲健康、費用、git 推送，產出統一 markdown 存入 docs/weekly_review/。
agent: Architect
---

# Weekly Review

## Step 0：快速概覽儀表板

掃過以下訊號後再進入 Step 1：

1. `/zh/admin/stats` — Source Status 表，鎖定需要關注的來源。
2. `/zh/admin` 主表 — 過濾 `annotation_status = pending` 確認積壓量。
3. 費用閾值：OpenAI 本週 > $5 / DeepL > 100k 字元 / 月預算 > 80% 需在週報中點名。

---

## Step 1：全量 DB 指標查詢

一次取得所有指標（爬蟲健康 + 費用 + 事件數 + Auto-QA）：

```bash
cd scraper && source ../.venv/bin/activate && python - <<'PY'
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone

load_dotenv('.env')
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
now = datetime.now(timezone.utc)
since7 = (now - timedelta(days=7)).isoformat()
month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

# Per-source stats
res = sb.table('scraper_runs') \
    .select('source,events_processed,cost_usd,success,deepl_chars,ran_at') \
    .gte('ran_at', since7).execute()
rows = res.data or []

by_source = {}
for r in rows:
    s = r['source']
    if s not in by_source:
        by_source[s] = {'count': 0, 'success': 0, 'events': 0, 'cost': 0.0}
    by_source[s]['count'] += 1
    if r.get('success', True):
        by_source[s]['success'] += 1
    by_source[s]['events'] += r.get('events_processed', 0) or 0
    by_source[s]['cost'] += float(r.get('cost_usd', 0) or 0)

total_cost = sum(d['cost'] for d in by_source.values())
deepl_chars = sum(int(r.get('deepl_chars', 0) or 0) for r in rows)

print("=== 來源狀態 ===")
for src, d in sorted(by_source.items()):
    rate = d['success'] / d['count'] if d['count'] else 0
    flag = '🟢' if rate == 1.0 and d['events'] > 0 else ('🔴' if rate == 0 or d['events'] == 0 else '🟡')
    print(f"{flag} {src}: {d['count']}x {rate:.0%} {d['events']}件 ${d['cost']:.4f}")

# Summary
new_events = sb.table('events').select('id', count='exact') \
    .eq('is_active', True).gte('created_at', since7).execute().count or 0
pending = sb.table('events').select('id', count='exact') \
    .eq('is_active', True).eq('annotation_status', 'pending').execute().count or 0
total_active = sb.table('events').select('id', count='exact') \
    .eq('is_active', True).execute().count or 0

mtd_runs = sb.table('scraper_runs').select('cost_usd') \
    .gte('ran_at', month_start).execute().data or []
mtd_cost = sum(float(r.get('cost_usd', 0) or 0) for r in mtd_runs)

qa_rows = sb.table('event_reports').select('report_types,status') \
    .eq('status', 'open').execute().data or []
qa_types = {}
for r in qa_rows:
    for t in (r.get('report_types') or []):
        qa_types[t] = qa_types.get(t, 0) + 1

print(f"\n=== 摘要 ===")
print(f"新增事件(7d): {new_events}  |  active 總數: {total_active}")
print(f"待標注 pending: {pending}")
print(f"本週費用: ${total_cost:.4f}  |  DeepL: {deepl_chars:,} 字元")
print(f"本月累計: ${mtd_cost:.2f} / $20.00 ({mtd_cost/20*100:.0f}%)")
qa_sum = sum(qa_types.values())
if qa_sum:
    print(f"Auto-QA open: {qa_sum} — " + ", ".join(f"{t}: {n}" for t, n in qa_types.items()))
else:
    print("Auto-QA open: 0 ✅")
PY
```

---

## Step 2：Git 推送盤點

```bash
# 本週所有 commits（無 merge）
git log --since="7 days ago" --pretty=format:"%h %s" --no-merges

# 新增爬蟲
git log --since="7 days ago" --diff-filter=A --name-only --pretty=format: -- scraper/sources/ | grep "\.py$"

# 新增 Migration
git log --since="7 days ago" --diff-filter=A --name-only --pretty=format: -- supabase/migrations/ | grep "\.sql$"

# 統計數量
git log --since="7 days ago" --oneline --no-merges | wc -l
```

依四工廠分類 commits：

| 維度 | scope 範例 |
|---|---|
| 🚙 車身（web/admin） | `feat(web)` `fix(web)` `style` `design` |
| 🧭 導航（annotator/AI） | `fix(annotator)` `feat(annotator)` scraper AI 邏輯 |
| 🏭 後勤工廠（CI/DB/infra） | `fix(ci)` `fix(database)` `chore` `security` |
| 🔁 駕訓場（評估/文件） | `docs(skills)` `docs(agents)` `feat(evaluation)` |
| 📡 資料來源 | `feat(scraper)` `feat(sources)` 新爬蟲 |

---

## Step 3：Session Memory

讀取 `/memories/session/` 目錄，若有本週工作問題則列出；否則略過。

---

## Step 4：撰寫週報並存檔

整合以上所有資料，撰寫完整週報 markdown。

撰寫完成後：
1. 用 `create_file` 工具存到 `docs/weekly_review/YYYY-MM-DD.md`（YYYY-MM-DD = 本週日期）。
2. 執行 git commit + push：
   ```bash
   git add docs/weekly_review/ && \
   git commit -m "docs(weekly_review): $(date +%Y-%m-%d) weekly review" && \
   git push origin main
   ```

### 週報輸出格式

```markdown
# 週報 — YYYY-MM-DD ~ YYYY-MM-DD

## 📊 數據摘要

| 指標 | 值 |
|---|---|
| 本週新增事件 | N 件 |
| Active 事件總數 | N 件 |
| 待標注 (pending) | N 件 |
| 本週費用 | $N.XXXX |
| DeepL 本週 | N 字元 |
| 本月累計 | $N.XX / $20.00 (N%) |
| Auto-QA open | N 件 |

## 🟢 健康
（成功率 100%、事件數 ≥ 1 的來源清單）

## 🟡 待觀察
（成功率 50–99%，或事件數明顯低於歷史平均的來源）

## 🔴 需修復（0 件 / 0% 來源）
（持續 0 件來源，含已連續幾週的說明）

## 📦 本週推送摘要

- **Commits**：N 個（feat N / fix N / docs N / chore N）
- **新增爬蟲**：N 個（名稱）
- **新 Migration**：N 個（編號）

**本週功能亮點**（3–5 個最重要 feat commit）：
1. ...
2. ...
3. ...

## ✅ 優點
1. ...
2. ...

## ⚠️ 缺點與風險
1. ...
2. ...

## 📌 下週優先事項
1. 🔴 P0 ...
2. 🟡 P1 ...
3. 🟢 P2 ...
```


---

## Step 1：查詢上週爬蟲執行資料

執行 terminal 指令，查詢過去 7 天的 `scraper_runs` 資料：

```bash
cd scraper && python - <<'PY'
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone

load_dotenv('.env')
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

res = sb.table('scraper_runs').select('source,events_processed,cost_usd,success,ran_at').gte('ran_at', since).execute()
rows = res.data or []

by_source = {}
for r in rows:
    s = r['source']
    if s not in by_source:
        by_source[s] = {'count': 0, 'success': 0, 'events': 0, 'cost': 0.0}
    by_source[s]['count'] += 1
    if r.get('success', True):
        by_source[s]['success'] += 1
    by_source[s]['events'] += r.get('events_processed', 0)
    by_source[s]['cost'] += float(r.get('cost_usd', 0))

for src, d in sorted(by_source.items()):
    rate = d['success'] / d['count'] if d['count'] else 0
    print(f"{src}: {d['count']} 次, 成功率 {rate:.0%}, {d['events']} 件, ${d['cost']:.6f}")
PY
```

分析各來源的：成功率、事件數、費用趨勢。

---

## Step 1.5：盤點本週 Git 推送

執行以下指令，取得本週 commit 清單與新增檔案：

```bash
# Commits（無 merge，依 conventional commit type 分類）
git log --since="7 days ago" --pretty=format:"%h %s" --no-merges

# 新增爬蟲檔
git log --since="7 days ago" --diff-filter=A --name-only --pretty=format: -- scraper/sources/ | grep "\.py$"

# 新增 Migration
git log --since="7 days ago" --diff-filter=A --name-only --pretty=format: -- supabase/migrations/ | grep "\.sql$"

# Commit 數快計
git log --since="7 days ago" --oneline --no-merges | wc -l
```

依以下維度整理（可並行與 Step 1 一起跑）：

| 維度 | 說明 |
|---|---|
| 🚙 車身（web/admin） | `feat(web)` `fix(web)` `style` `design` |
| 🧭 導航（annotator/AI） | `fix(annotator)` `feat(annotator)` `fix(scraper)` |
| 🏭 後勤工廠（CI/DB/infra） | `fix(ci)` `fix(database)` `feat(governance)` `chore` |
| 🔁 駕訓場（評估/文件） | `docs(skills)` `docs(agents)` `feat(evaluation)` |
| 📡 資料來源（scraper） | `feat(scraper)` `feat(sources)` 新增爬蟲 |

---

## Step 2：列出本週 Session Memory 中的問題

讀取 `/memories/session/` 目錄，若有記錄本週工作問題則列出；若無 session memory 則略過此步驟。

---

## Step 3：分析反覆出現的問題

判斷哪些問題類型在過去 7 天內出現超過 2 次：

- 同一來源的爬蟲失敗
- 日期解析錯誤
- 標注品質問題
- TypeScript/lint 錯誤

---

## Step 4：輸出結構化報告

```
# 週報 — {{日期範圍}}

## 🟢 健康
（列出成功率 100%、事件數正常的來源）

## 🟡 待觀察
（列出成功率 50%～99%，或事件數明顯低於平均的來源）

## 🔴 需修復
（列出成功率 0%、7 天內無執行記錄，或持續 0 件的來源）

## 📊 費用摘要
- 本週總費用：$X.XXXXXX
- 費用最高來源：XXX（$X.XXXXXX）

## � 本週推送摘要
- Commits：N 個（feat N / fix N / docs N / chore N）
- 新增爬蟲：N 個（列出名稱）
- 新增 Migration：N 個（列出編號）
- 新增功能亮點（3–5 個最重要的 feat commit）

## ✅ 優點
1. （本週做對的事，值得延續的模式）
2. ...

## ⚠️ 缺點與風險
1. （技術債、設計不一致、遺留問題）
2. ...

## 📌 下週優先事項（最多 5 項，🔴P0 / 🟡P1 / 🟢P2）
1. 🔴 ...
2. 🟡 ...
3. 🟢 ...
```
