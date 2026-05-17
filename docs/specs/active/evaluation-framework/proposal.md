---
slug: evaluation-framework
title: Evaluation 框架 — annotation 精度、scraper 召回、Guards 元評估
status: active
branch: feat/evaluation-framework
created: 2026-05-17
tags: [evaluation, annotator, scraper, quality, meta]
---

## What（做什麼）

為 Tokyo Taiwan Radar 建立一套**多層次 evaluation 框架**，量化下列三個目前憑感覺的層面：

1. **Annotator 精度**：name_zh / category / event_form / organizer / location_name / start_date 等欄位的正確率
2. **Scraper 召回與品質**：per-source 漏抓、錯填、欄位完整度、DOM drift
3. **AI 報錯與 Guards 的實際效果**：`field_corrections` / `category_corrections` / SKILL.md Guards 是否真的阻止重犯

最終目標：把「每天花幾小時手修」的問題從**靠感覺改 prompt** 轉為**靠數據改 prompt**。

## Why（為什麼）

### 目前痛點（使用者陳述）

- Annotation 精度感受最差，無法量化是否在改善
- Scraper 經常漏抓或填錯，但不知道哪個 source 最該重寫
- 舊事件沒時間人工檢驗，沉默漂移無法察覺
- AI 報錯閉環基礎建設已存在（`field_protect_hits`、`monthly_health_check`），但**閉環有沒有效**沒有量測
- history.md / SKILL.md 寫了大量 Guards，但**是否真的被遵循、是否真的減少重犯**完全未知

### 現有資產（已具備但未充分消費）

- `field_corrections` / `category_corrections` / `selection_reason_corrections` 三張 corrections 表
- `event_reports`（使用者前台報錯）
- `scraper_runs.notes` 已記錄 `field_protect_hits`
- `scraper/health_check.py` / `daily_quality.py` / `monthly_health_check.py`
- [docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md](../../MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md) — 已有閉環健檢，但只回答「閉環有沒有斷」，不回答「閉環有沒有效」

### 為什麼**不**該做 fine-tuning（先排除這條路）

1. corrections 樣本量不足（OpenAI 建議 ≥ 5000 high-quality examples，目前 < 1000 量級）
2. 核心問題是規則的 **recall**（漏抓、未提取），不是模型語言能力
3. 規則持續演化（每月新 incident），fine-tuned model 一旦上線就老化
4. GPT-4o-mini + 結構化 SYSTEM_PROMPT + few-shot from corrections 已是業界最佳實踐
5. **何時可重評**：corrections 累積 > 5000 筆 + 每月新增規則 < 5 條時，可實驗 `category` 欄位（封閉 enum）fine-tuning

---

## Design（設計摘要）

### A. 閉環效能評估（Feedback Loop Effectiveness）— 最高 CP 值

擴展 `monthly_health_check.py`，新增四個指標：

| 指標 | 定義 | 健康信號 |
|---|---|---|
| **重犯率（Recurrence Rate）** | 過去 90 天 `field_corrections` 中同一 source × 同一欄位被修正 ≥ 2 次的比例 | 低 → annotator 學到了；高 → P1 保護鏈未覆蓋該欄位 |
| **保護命中率** | `field_protect_hits / annotated_events_30d` 月趨勢 | 應隨時間遞增；下降 → corrections 未被讀進 `human_field_map` |
| **首次正確率（First-Pass Accuracy）** | 新事件 24h 內被 `event_reports` 報錯的比例（依 source / 依欄位） | 直接量化「每天要花幾小時修」的痛點 |
| **平均修復延遲** | scraper 抓到 → 手動修正的時間差中位數（依 source） | 排序 scraper 改進優先序 |

**輸出位置**：`docs/monthly_review/YYYY-MM.md`

### B. Annotator 黃金測試集（Golden Set Regression）— 解決精度根本

**核心**：把過去 reference incidents 變成可重跑的 regression test。

1. **建立 `scraper/tests/golden/` 目錄**
   - 從 `field_corrections` + `annotation_status='reviewed'` 中抽 100–200 筆已知正確答案的 events
   - 凍結 `raw_title` / `raw_description` 作 input
   - 凍結最終欄位作 expected output（JSON fixture）
   - 涵蓋至少：8 種 category × 3 種 event_form × 含/不含 performer × 含/不含 sub-events
2. **`scraper/eval_annotator.py`（新檔）**
   - 對 golden set 跑 annotator（dry-run，不寫 DB）
   - 對每筆做欄位級 diff，輸出 per-field accuracy table
   - 輸出 markdown 報表至 `docs/evaluation/annotator/YYYY-MM-DD.md`
3. **CI 門檻**
   - 每次改 `annotator.py` 的 PR 自動跑 golden set
   - 精度下降 > 3%（任一欄位）→ 阻止 merge
   - 通過後在 PR comment 顯示 per-field diff

**直接回答**：「Architect Guards 寫的規則究竟有沒有效？」— 把每個 reference incident 變成 golden case，每次改動立刻量化。

### C. Scraper 健康度評估（擴展現有 daily_quality.py）

per-source 新增指標：

| 指標 | 偵測邏輯 | 行動建議 |
|---|---|---|
| **欄位完整度** | 該 source events 中 `start_date / location_address / business_hours / price_info / image_url` 的 non-null 率 | 排序「最常漏填」的 source |
| **annotator 修正率** | scraper 輸出 → annotator 後新增了幾個非 null 欄位（GPT 比 raw 多填的欄位數中位數） | 高 → scraper 抽取太薄 |
| **DOM drift 偵測** | per scraper 記錄 `parsed_fields_per_event` 中位數，連續 3 天下跌 > 30% | 告警網站可能改版 |
| **錯填率** | 該 source 進入 `field_corrections` 的速率（per 100 events） | 排序「最該重寫」的 source |

**輸出**：`scraper/reports/scraper_quality_YYYY-MM-DD.md`，每週生成一次。

### D. 歷史事件回測（Backfill Validation）— 解決「舊事件沒時間檢驗」

**`scraper/eval_historical.py`（新檔）**：

1. 取樣 100 筆 `is_active=true` 且 `created_at > 30d` 的事件（分層取樣，per source 比例分配）
2. 對每筆執行：raw → 重跑 annotator（dry-run） → diff 現存欄位
3. 輸出三類報表：
   - **沉默漂移**：現存欄位 vs 新 annotation 不一致 **AND** 現存值未在 `field_corrections` → 高機率舊資料是錯的，列入人工 review queue
   - **保護命中**：差異被 `field_corrections` 擋下 → 健康
   - **GPT 倒退**：新 annotation 比舊的差（如 name_zh 變空、category 變 senses fallback）→ prompt regression，要回溯 git history
4. **執行頻率**：一次性執行 + 之後每月隨 `monthly_health_check` 排程

### E. UI/前端評估（次要）

- **Lighthouse CI**：對 `/zh`、`/zh/events/[id]`、`/ja/announcements` 跑 perf/a11y/SEO，門檻 perf ≥ 80
- **Playwright E2E**：FilterBar 跨地區 / 城市切換 + AdminEventTable 的 `globalIndexMap` 行為（防 cross-filter reference 回歸）

### F. AI 報錯 / Guards / history 的元評估（Meta-Evaluation）

針對「**SKILL.md / history.md 究竟有沒有效**」：

1. **Guard 對應 Detection SQL**
   - 在 `.github/skills/agents/architect/SKILL.md` 每條 Guard 末尾補一行 `Detection SQL:`
   - 由 `monthly_health_check.py` 自動執行所有 Detection SQL，統計每條 Guard 的觸發次數
   - **連續 3 個月觸發 0 次** → 標記為「可能已內化或不再相關」，候選精簡
   - **觸發次數上升** → Guard 沒被 annotator/scraper 程式碼真正套用，需排查
2. **history 引用率**
   - semantic_search 自己的 history.md vs 最近 30 天 commit message + PR description
   - 計算 reference incidents 在後續 commits 中的引用率
   - **從未被引用的 history 條目** → 候選精簡或刪除
3. **Subagent 採用率**
   - 解析 `session_store_sql` 資料（chronicle skill），量化 Architect → Engineer → Tester 三段式工作流的實際使用率
   - 低 → 流程過重，需簡化或合併步驟

**輸出**：併入 `Reviewer` agent 的月度報告 `docs/monthly_review/YYYY-MM.md`。

---

## Non-Goals（不做什麼）

- **不做 fine-tuning**（理由見 Why 區）— 視 6 個月後 corrections 累積量再評估
- **不做使用者 satisfaction survey**（樣本太小，不具統計意義）
- **不做 image/poster quality evaluation**（enrich_poster.py 仍在實驗階段，未到評估時機）
- **不做跨語言翻譯品質 BLEU/ROUGE 自動評估**（中日英三語對照需大量人工標註 reference，CP 值低）
- **不重構現有 health_check.py / daily_quality.py 既有指標** — 只新增，避免回歸

---

## 實作優先序

| 階段 | 內容 | 投入 | 何時做 |
|---|---|---|---|
| **P1** | B（golden set 100 筆）+ A（重犯率 / 保護命中率加入 monthly_health_check） | ~1 週 | 立即 |
| **P2** | C（per-scraper 欄位完整度報表）+ D（歷史回測一次性執行） | ~1 週 | P1 完成後 |
| **P3** | F（Guard Detection SQL 補齊 + Reviewer agent 整合） | 持續 | P2 完成後 |
| **不做** | fine-tuning、E（UI evaluation）非阻塞 | — | — |

---

## Success Criteria（驗收標準）

- [ ] P1：golden set ≥ 100 筆 fixture，CI 在 annotator PR 自動跑並 comment per-field diff
- [ ] P1：`monthly_health_check.py` 輸出 4 個新指標（recurrence rate / protect hit rate / first-pass accuracy / repair latency）
- [ ] P2：每週生成 per-source scraper quality 報表，可一眼看出「最該重寫的 3 個 source」
- [ ] P2：一次性歷史回測產出三類報表（沉默漂移 / 保護命中 / GPT 倒退）
- [ ] P3：所有 SKILL.md Guards 配有 Detection SQL，月度報告統計觸發次數
- [ ] 6 個月後：使用者「每天花幾小時手修」的時間有可量化的下降（基準：當前約 2–3 小時/天）

---

## References

- [docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md](../../MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md) — 既有閉環健檢（本 spec 擴展之）
- [docs/SCRAPER_PIPELINE.md](../../SCRAPER_PIPELINE.md) — pipeline 全景
- [docs/TRANSLATION_PIPELINE.md](../../TRANSLATION_PIPELINE.md) — 翻譯流程
- `.github/skills/agents/architect/SKILL.md` — 所有 Guards 與 reference incidents
- `scraper/annotator.py` — `field_protect_hits` 指標出處（line 1188, 1974）
- `scraper/monthly_health_check.py` — 既有月度健檢
- 對話紀錄：2026-05-17 使用者提出「annotation 精度 / scraper 漏抓 / Guards 是否有效」三大評估訴求
