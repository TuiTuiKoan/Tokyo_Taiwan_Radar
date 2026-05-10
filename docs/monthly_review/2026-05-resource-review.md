---
title: "全站資源盤點、管理手段評估、與六月開發目標"
description: "基礎設施配額、Workflow/Agent/Source 使用分析、成本診斷、新功能評估、Monthly Experiment 設計、六月 P0-P3 待辦"
author: Architect
ms.date: 2026-05-10
ms.topic: report
keywords:
  - monthly review
  - resource audit
  - cost analysis
  - development goals
---

## A. 全站資源使用現況

### A-1. 基礎設施配額

| 資源 | 現況 | 上限（Free Plan） | 使用率 | 狀態 |
|---|---|---|---|---|
| Supabase DB | 35.4 MB | 500 MB | **7.1%** | 🟢 安全 |
| Supabase Auth | ~5 users | 50k MAU | <0.1% | 🟢 |
| Supabase Storage | 未啟用 | 1 GB | 0% | 🟢 |
| GH Actions minutes | ~150 min/月估 | 2,000 min | ~7.5% | 🟢 |
| OpenAI 30d | **$9.18** | 無硬限（月預算 $15） | **61%** | 🟡 |
| Vercel bandwidth | 未監控 | 100 GB (Hobby) | 未知 | ⚠ 需加監控 |
| LINE Messaging API | 週報+告警 | 200 免費 msg/月 | ~20 msg/月估 | 🟢 |
| X (Twitter) API | 自動發文 | 1,500 tweets/月 (Free) | ~30/月 | 🟢 |

### A-2. OpenAI 成本分析（30 天 $9.18）

| 用途 | 費用 | 占比 | 趨勢 |
|---|---|---|---|
| **researcher（4 slots + topic）** | $6.52 | **71%** | 🔴 主要成本 |
| **annotator** | $2.66 | 29% | 🟡 隨事件數線性增長 |
| enrich / other | $0.00 | 0% | 🟢 |

> **關鍵發現**：researcher 占成本 71%，但只產出 research_sources 的 candidate 紀錄（320 筆中 auto_research 完成僅 16 筆 assessed）。成本效益比偏低。

### A-3. DB 表空間分佈（Top 10）

| 表 | 大小 | 用途 |
|---|---|---|
| events | 11.3 MB | 核心事件 |
| aeo_visits | 6.0 MB | SEO 追蹤（增長最快） |
| category_corrections | 639 KB | 分類修正 |
| field_corrections | 582 KB | 欄位修正 |
| event_views | 557 KB | 頁面瀏覽 |
| venues | 344 KB | 場館實體 |
| research_sources | 344 KB | 研究來源 |
| event_reports | 254 KB | 使用者檢舉 |
| scraper_runs | 238 KB | 執行紀錄 |
| announcements | 205 KB | 公告 |

### A-4. 事件類別分佈（382 active）

| 類別 | 筆數 | 占比 | 評估 |
|---|---|---|---|
| lecture | 124 | 32.5% | 🟢 健康 |
| **movie** | 103 | **27.0%** | 🟡 偏高（39 新電影院 scraper 造成） |
| lifestyle_food | 90 | 23.6% | 🟢 |
| academic | 77 | 20.2% | 🟢 |
| history | 73 | 19.1% | 🟢 |
| geopolitics | 64 | 16.8% | 🟢 |

> movie 占比 27% 尚可接受（< 60% 警戒線），但需持續監控。

## B. 管理手段進行狀態

### B-1. 已建立的監控機制（5 條告警線）

| 機制 | 頻率 | 通知管道 | 狀態 |
|---|---|---|---|
| quota-monitor（DB + GH min + Vercel） | 每日 03:00 JST | LINE | ✅ 運作中 |
| daily-dev-report（成本告警） | 每日 02:00 JST | LINE | ✅ 運作中 |
| daily-health-check（scraper 健康） | 每日 10:30 JST | LINE | ✅ 運作中 |
| workflow-failure-notify | 即時（on failure） | Email（GH） | ✅ 已修自我迴圈 |
| secret-rotation-reminder | 每季 | LINE | ✅ |

### B-2. 缺失的監控

| 缺失項 | 影響 | 建議 |
|---|---|---|
| **Vercel build time / deploys** | 突破 100h build 會停站 | ✅ 已加入 quota-monitor（30d: 12.4h/100h, 1005 deploys） |
| **OpenAI 累計月額即時追蹤** | daily_report 只看單日，不看累計 | 🟡 加月累計 check |
| **aeo_visits 增長速度** | DB 第 2 大表，增速最快 | 🟡 加 cleanup cron |
| **scraper_runs 30d cleanup** | 無限增長 | 🟡 加 cleanup cron |
| **Category 比例即時告警** | movie > 60% 時自動警告 | 🟢 可延後 |

## C. Workflow / Agent / Source 使用分析

### C-1. 19 個 Workflows 使用率分析

| Workflow | 頻率 | 30d 估計執行次數 | 評估 |
|---|---|---|---|
| scraper.yml | 每日 | ~30 | 🟢 核心 |
| merger.yml | 每日 3 次 | ~90 | 🟢 核心 |
| annotate-now.yml | 手動 | ~5 | 🟢 急件補標注 |
| scrape-now.yml | 手動 | ~10 | 🟢 急件補爬 |
| daily-health-check.yml | 每日 | ~30 | 🟢 |
| daily-dev-report.yml | 每日 | ~30 | 🟢 |
| quota-monitor.yml | 每日 | ~30 | 🟢 |
| auto-generate.yml | 每日 | ~30 | 🟢 auto_scraper |
| auto-research.yml | 每日 | ~30 | 🟡 成本高 |
| researcher.yml | 每日 4 slot | ~120 | 🟢 每日 9 類別輪轉 |
| weekly-broadcast.yml | 每週 Thu+Fri | ~8 | 🟢 已有 cron |
| weekly-report.yml | 每週一 10:00 JST | ~4 | 🟢 已有 cron |
| x-post-cron.yml | 每日 3 slot | ~90 | 🟢 已有 cron |
| backup.yml | 每日 | ~30 | 🟢 |
| monthly_health_check.yml | 每月 1 號 | ~1 | 🟢 |
| external-stats-pull.yml | 每月 25 號 | ~1 | 🟢 |
| secret-rotation-reminder.yml | 每季 | ~0.3 | 🟢 |
| discovery-accounts.yml | 手動 | 0-1 | 🟡 幾乎未用 |
| workflow-failure-notify.yml | 被動觸發 | 低 | 🟢 |

**問題發現**：

1. `researcher.yml` + `auto-research.yml` + `discovery-accounts.yml` 三個 workflow 都在做「發現新來源」，分工不清

### C-2. 11 個 Agent 角色分析

| Agent | 使用頻率 | scope overlap | 建議 |
|---|---|---|---|
| **Architect** | 極高（主力） | — | 🟢 核心 |
| **Engineer** | 高 | — | 🟢 核心 |
| **Scraper Expert** | 高 | 與 3 個 subagent 重疊 | 🟡 subagent 較少用 |
| **Tester** | 中 | — | 🟢 |
| **Researcher** | 低 | 與 auto-research workflow 重疊 | 🟡 需釐清 |
| **Reviewer** | **極低（幾乎未用）** | — | 🔴 應月度自動化 |
| Update History | 低 | — | 🟡 |
| Validate-Merge-Deploy | 中 | — | 🟢 |
| 3 個 scraper subagents | **極低** | tcc/peatix/community 各自獨立但不常叫 | 🟡 可合併 |

### C-3. 29 個 Zero-Event Scrapers（30 天無產出）

| 來源 | 30d runs | 原因分析 | 建議 |
|---|---|---|---|
| connpass | 17 | 台灣活動少 | 🟢 保留（季節性） |
| tokyo_now | 15 | 目標網站可能改版 | 🔴 檢查 |
| tokyo_city_i | 15 | 同上 | 🔴 檢查 |
| ifi | 15 | 非每月有台灣展 | 🟢 保留 |
| morc_asagaya | 14 | 小型電影院 | 🟢 保留 |
| tokyo_filmex | 13 | 影展期間外 | 🟢 保留（季節性） |
| oaff | 12 | 影展期間外 | 🟢 保留（季節性） |
| jposa_ja | 12 | 日台友好團體 | 🟡 檢查 |
| 12 個電影院 | 2–14 | 非每月有台灣片 | 🟢 保留 |

> 29 個 zero-event 中只有 2-3 個需主動檢查（tokyo_now, tokyo_city_i, jposa_ja），其餘屬正常季節性空窗。

### C-4. Research Pipeline 效率

| 指標 | 數值 | 評估 |
|---|---|---|
| research_sources 總數 | 320 | |
| implemented | 117 (37%) | 🟢 高實施率 |
| not-viable | 168 (53%) | 正常淘汰 |
| candidate（待評估） | 26 | |
| auto_research assessed | 16/320 (5%) | 🔴 **極低**，$6.52 只完成 16 筆 |
| auto_scraper success | 5/320 (1.6%) | 🔴 **成功率太低** |
| auto_scraper deployed-manually | 23 | 人工介入遠多於自動 |

> **核心問題**：auto-research + auto-generate 花了 $6.52（30d），但自動部署成功只有 5 筆。絕大多數仍靠人工。

## D. 改善建議

### D-1. Workflow 整合方案

| 目前 | 問題 | 建議 |
|---|---|---|
| `researcher.yml`（每日 4-slot） | 與 auto-research 分工不清 | 考慮合併入 `auto-research.yml`，改為每週一次（降成本） |
| `discovery-accounts.yml` | 幾乎未用 | 刪除或合併入 researcher |
| `auto-research.yml`（每日） | 成本高、效率低 | 改為每 3 天或每週一次 |

### D-2. Agent 精簡方案

| 動作 | 說明 |
|---|---|
| **合併 3 個 scraper subagent** → 1 個 | peatix/tcc/community 知識差異小，合為一個 SKILL 即可 |
| **啟動 Reviewer 月度排程** | 每月 1 號自動執行，輸出到 `docs/monthly_review/` |
| **Researcher agent → 僅做人工深研** | 日常發現交給 auto-research workflow，agent 只處理複雜案例 |

### D-3. 監控強化方案

| 項目 | 做法 | 優先度 |
|---|---|---|
| **Vercel 用量監控** | `quota_monitor.py` 加 Vercel API call（`GET /v1/usage`） | 🔴 P0 |
| **OpenAI 月累計告警** | `daily_report.py` 加 30d rolling sum check | 🟡 P1 |
| **aeo_visits + scraper_runs cleanup** | 90 天前的 `DELETE` cron（新 workflow 或 monthly_health_check 內） | 🟡 P1 |
| **Category 比例監控** | `auto_qa` 加 category distribution check | 🟢 P2 |
| **i18n key 一致性 CI** | pre-push hook 或 workflow 比對 3 語 JSON keys | 🟢 P2 |

## E. 新功能規劃評估

### E-1. Business Analysis 面向

| 功能 | 與商業分析報告的對應 | 建議 | 優先度 |
|---|---|---|---|
| **反爬蟲（rate limit）** | T2 威脅：大平台抄襲資料 | 低優先——目前無流量壓力；Vercel 有基本保護。在 B2B API 啟動前無需 | 🟢 延後 |
| **DB 升級（Supabase Pro）** | 目前 7.1%，12 個月內不會滿 | 🟢 延後到 200MB 或 B2B 啟動時 |
| **社群功能** | O3 機會：在日華人 + Z 世代 | 先做 LINE OpenChat（零開發），再考慮站內評論 | 🟡 Q2 |
| **翻譯功能新增** | 商業分析建議 Note 長文 | `description_zh/en` 質量提升比新語言重要；考慮 Korean 為第四語（在日韓人 80 萬） | 🟡 Q3 |
| **電子報** | 商業分析 Q1 priority #2 | Buttondown/Substack 零成本，從 DB 自動生成 | 🟠 P1 |
| **Personal Pro 訂閱** | 商業分析 Q2 priority #1 | Stripe + Supabase Auth，需法律/特商法準備 | 🟡 Q2 |
| **B2B 付費置頂** | 商業分析 ROI 最高 | 先找 1 個 pilot 客戶（台灣文化中心/台灣祭主辦） | 🟠 P1 |

### E-2. 不建議現階段做的

| 功能 | 理由 |
|---|---|
| Vector search / RAG | 技術 cool 但無用戶需求驗證 |
| TikTok / YouTube Shorts | 需影片製作能力，不適合自動化 |
| 站內評論系統 | 需 moderation 人力，單人無法維持 |
| 多國擴展（Korea/Vietnam Radar） | 商業分析提到年底評估，現在太早 |

## F. 六月 Monthly Experiment 建議

結合 `monthly-experiment.prompt.md`（4-step 流程）與 `reviewer.agent.md`（健康分析），建議以下實驗：

### 實驗 1：Researcher 成本削減（$6.52 → $2.00 目標）

```
實驗假設：researcher 改為每週一次 + 縮小 prompt 可降 70% 成本

A 組（現況）：auto-research 每日執行 4 slots
B 組（實驗）：每週三執行 2 slots + 用 GPT-4o-mini 替代 GPT-4o

測試方法：
1. 6/1–6/7 B 組，6/8–6/14 A 組
2. 比較：research_sources 新增數、assessed 成功率、成本

成功標準：
- 成本降 ≥ 50%
- 新增 candidate 數降 ≤ 30%

預計工時：2h
```

### 實驗 2：電子報 MVP（驗證需求）

```
實驗假設：每週台灣活動精選電子報可達 50 位訂閱者/月

A 組（無電子報）
B 組（Buttondown 免費版，每週三發送 5 件精選）

測試方法：
1. 6/1 開通 Buttondown + 站內加訂閱 CTA
2. 內容從 DB 自動生成（已有 weekly_broadcast 邏輯可復用）
3. 6/30 統計：訂閱數、開信率、退訂率

成功標準：
- 30 天 ≥ 30 訂閱者
- 開信率 ≥ 40%

預計工時：4h（含 CTA 前端 + Buttondown 設定）
```

### 實驗 3：站內微問卷（使用者分群）

```
實驗假設：詳情頁底部 3 題微問卷可驗證 LTV 假設

A 組（無問卷）
B 組（cookie 控制一次性顯示：「您是？在日華人/日本人/其他」）

測試方法：
1. EventCard 詳情頁加 bottom banner
2. 結果存 Supabase（新表 user_surveys，3 欄位）
3. 6/30 統計比例

成功標準：
- 回答率 ≥ 5% of page views
- 取得可行動的用戶分群數據

預計工時：3h
```

## G. 六月開發目標

### 🔴 P0（六月第 1 週）

| # | 項目 | Owner | 預計工時 |
|---|---|---|---|
| 1 | **Researcher 降頻**：auto-research.yml 改 `0 15 * * 3`（每週三） | Engineer | 0.5h |
| 2 | **3 個無 cron workflow 啟用**：weekly-broadcast / weekly-report / x-post-cron | Engineer | 1h |
| 3 | **Vercel 用量加入 quota-monitor** | Engineer | 2h |
| 4 | **tokyo_now / tokyo_city_i / jposa_ja 檢查修復** | Scraper Expert | 1h |
| 5 | **aeo_visits + scraper_runs 90d cleanup cron** | Engineer | 1h |

### 🟠 P1（六月第 2-3 週）

| # | 項目 | Owner |
|---|---|---|
| 6 | **電子報 MVP**（Buttondown + DB 自動生成 + 站內 CTA） | Architect + Engineer |
| 7 | **OpenAI 月累計告警** | Engineer |
| 8 | **Reviewer agent 月度自動化**（monthly_health_check 觸發） | Architect |
| 9 | **Spec 收斂**：feedback-loop + tier1-data-completion 標記 done | Architect |
| 10 | **discovery-accounts.yml 刪除**（功能併入 auto-research） | Engineer |

### 🟡 P2（六月第 4 週）

| # | 項目 | Owner |
|---|---|---|
| 11 | **站內微問卷**（使用者分群驗證） | Engineer |
| 12 | **3 scraper subagent 合併為 1 SKILL** | Architect |
| 13 | **B2B pilot 接觸**（台灣文化中心 / JATS / 台灣祭主辦） | 人工 |
| 14 | **i18n key 一致性 CI** | Engineer |

### 🟢 P3（持續）

| # | 項目 |
|---|---|
| 15 | DeepL secret 處置 |
| 16 | migration 命名規則文件化 |
| 17 | Korean（第四語言）可行性評估 |

## H. 月度 Reviewer + Experiment 整合建議

目前 `reviewer.agent.md` 和 `monthly-experiment.prompt.md` 各自獨立，建議建立月度循環：

```
每月 1 號（monthly_health_check.yml 觸發後）：
  → Reviewer agent 自動生成 docs/monthly_review/YYYY-MM.md
  → 包含：scraper 健康 + agent scope + skill 新鮮度

每月第 1 個週末（手動）：
  → monthly-experiment prompt 設計下月實驗
  → 基於 Reviewer 報告 + 上月實驗結果

每週日（weekly-report.yml，加 cron 後自動）：
  → 輸出 docs/weekly_review/YYYY-MM-DD.md
```

這樣 Reviewer 不再是「幾乎未用」的 agent，而是月度治理循環的起點。
