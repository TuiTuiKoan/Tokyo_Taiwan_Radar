---
spec: evaluation-framework
---

# Tasks

## P1 — Annotator Golden Set + 閉環效能指標（~1 週）

### B. Annotator Golden Set
- [ ] 設計 `scraper/tests/golden/` 目錄結構與 fixture JSON schema
- [ ] 從 DB 抽 100 筆 reviewed + field_corrections 覆蓋的 events 作為 golden cases
  - 涵蓋至少 8 種 category × 3 種 event_form × 含/不含 performer × 含/不含 sub-events
- [ ] 撰寫 `scraper/eval_annotator.py` — dry-run annotator + per-field diff + markdown 報表
- [ ] 加入 CI workflow（`.github/workflows/eval-annotator.yml`）— PR 觸發、per-field 差距 > 3% 阻擋 merge
- [ ] 文件：`docs/evaluation/annotator/README.md` 說明用法

### A. 閉環效能指標
- [ ] `monthly_health_check.py` 新增：重犯率 SQL
- [ ] `monthly_health_check.py` 新增：保護命中率 SQL（30 天趨勢）
- [ ] `monthly_health_check.py` 新增：首次正確率 SQL（per source × per field）
- [ ] `monthly_health_check.py` 新增：平均修復延遲 SQL（per source）
- [ ] 輸出整合進 `docs/monthly_review/YYYY-MM.md` 模板

## P2 — Scraper Quality + 歷史回測（~1 週）

### C. per-Scraper 品質報表
- [ ] 撰寫 `scraper/eval_scraper_quality.py`（或擴展 daily_quality.py）
- [ ] 指標 1：欄位完整度（per source × per field non-null 率）
- [ ] 指標 2：annotator 修正率（GPT 比 raw 多填的欄位數中位數）
- [ ] 指標 3：DOM drift 偵測（parsed_fields_per_event 連 3 天 -30% 告警）
- [ ] 指標 4：錯填率（field_corrections per 100 events per source）
- [ ] 輸出 `scraper/reports/scraper_quality_YYYY-MM-DD.md`
- [ ] CI workflow 每週日 09:00 JST 排程

### D. 歷史事件回測
- [ ] 撰寫 `scraper/eval_historical.py`
- [ ] 分層取樣 100 筆 active + created_at > 30d 的事件
- [ ] dry-run annotator + diff 現存欄位
- [ ] 輸出三類報表：沉默漂移 / 保護命中 / GPT 倒退
- [ ] 一次性執行，產出首份 baseline 報表
- [ ] 排程：每月 1 號隨 monthly_health_check 執行

## P3 — Guards 元評估（持續）

### F. Meta-Evaluation
- [ ] 盤點 `.github/skills/agents/architect/SKILL.md` 所有 Guards（目前 30+ 條）
- [ ] 為每條 Guard 撰寫 Detection SQL，補進 SKILL.md
- [ ] `monthly_health_check.py` 自動執行所有 Detection SQL，統計觸發次數
- [ ] 標記「連續 3 個月 0 次」的 Guard 為候選精簡
- [ ] history.md 引用率分析（semantic_search vs commit messages）
- [ ] Subagent 採用率分析（session_store_sql）
- [ ] 整合進 Reviewer agent 月度報告

## 不做（明確排除）

- [ ] ~~Fine-tuning GPT-4o-mini~~ — 樣本不足、規則持續演化，6 個月後重評
- [ ] ~~UI Lighthouse / E2E~~ — 非阻塞性問題，延後
- [ ] ~~跨語言翻譯 BLEU/ROUGE 自動評估~~ — CP 值低
- [ ] ~~使用者 satisfaction survey~~ — 樣本太小

## 驗收

每階段完成後，更新 `proposal.md` 的 Success Criteria checkbox。
