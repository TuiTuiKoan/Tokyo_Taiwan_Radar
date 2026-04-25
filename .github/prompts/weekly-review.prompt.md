---
description: 每週復盤：分析爬蟲健康、Agent 使用模式、工具效率，輸出下週優先事項。
agent: Architect
---

# Weekly Review

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

## 📌 下週優先事項（最多 5 項，依優先順序）
1. ...
2. ...
3. ...
```
