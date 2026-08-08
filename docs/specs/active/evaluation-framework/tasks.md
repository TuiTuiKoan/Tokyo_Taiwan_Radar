---
spec: evaluation-framework
---

# Tasks

> **對帳紀錄 2026-08-06**：本清單先前長期未更新，P1 實際上大致已完成卻仍全部標為未勾選，
> 導致「P2 卡在 P1 沒做完」的錯誤判斷。本次逐項比對程式碼與 CI 實況後修正。
>
> - **P1-A**：4 個指標全部存在於 `monthly_health_check.py`，輸出已產出（`docs/monthly_review/2026-06-evaluation.md`）
> - **P1-B**：golden set、`eval_annotator.py`、2 個 CI workflow、README 均已存在；
>   唯 golden cases 為 50 筆（目標 100），且 `event_form`／`performer`／sub-events 三個覆蓋維度尚未實際評估
> - **P2**：`eval_scraper_quality.py` 與 `eval_historical.py` 皆不存在，無對應 workflow → 未開始
> - **P3**：無實作跡證 → 未開始
>
> 下次修改本檔時，請一併更新此對帳日期，否則勾選狀態會再次腐化。

## P1 — Annotator Golden Set + 閉環效能指標（~1 週）

### B. Annotator Golden Set
- [x] 設計 `scraper/tests/golden/` 目錄結構與 fixture JSON schema
- [ ] 從 DB 抽 100 筆 reviewed + field_corrections 覆蓋的 events 作為 golden cases
  - 涵蓋至少 8 種 category × 3 種 event_form × 含/不含 performer × 含/不含 sub-events
  - **部分完成（2026-08-06 對帳）**：實際 50 筆（目標 100），全部 `tags=fc_backed`、涵蓋 24 個 source
  - category 21 種達標；**`event_form` 於 50 筆中值全為 null、`performer` 不在 `expected` 欄位內、sub-events 未覆蓋** → 這三個維度目前並未被評估
- [x] 撰寫 `scraper/eval_annotator.py` — dry-run annotator + per-field diff + markdown 報表
- [x] 加入 CI workflow（`.github/workflows/eval-annotator.yml`）— PR 觸發、per-field 差距 > 3% 阻擋 merge
  - **實作與描述分歧**：實際門檻為 `name_zh` KPI baseline 迴歸阻擋，收緊版本位於 `eval-annotator-stage2.yml`，非原文的「per-field 差距 > 3%」
- [x] 文件：`docs/evaluation/annotator/README.md` 說明用法

### A. 閉環效能指標
- [x] `monthly_health_check.py` 新增：重犯率 SQL — `_count_recurrence()`
- [x] `monthly_health_check.py` 新增：保護命中率 SQL（30 天趨勢）— `_protect_hit_trend()`
- [x] `monthly_health_check.py` 新增：首次正確率 SQL（per source × per field）— `_first_pass_accuracy()`
- [x] `monthly_health_check.py` 新增：平均修復延遲 SQL（per source）— `_repair_latency()`
- [x] 輸出整合進 `docs/monthly_review/YYYY-MM.md` 模板
  - **刻意的實作差異**：A1–A4 產出獨立檔 `docs/monthly_review/YYYY-MM-evaluation.md`（例：`2026-06-evaluation.md`），不併入 `YYYY-MM.md`；`YYYY-MM.md` 仍由 `docs_report.py` 產生

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
