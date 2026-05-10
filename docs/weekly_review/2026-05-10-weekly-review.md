---
title: "Tokyo Taiwan Radar 週報 — 2026/05/03 ～ 05/10"
description: "一週推送功能、Spec 與架構變動、爬蟲/事件/功能新增量、優缺點與優先待辦盤點"
author: Architect
ms.date: 2026-05-10
ms.topic: report
keywords:
  - weekly review
  - retrospective
  - tokyo taiwan radar
estimated_reading_time: 12
---

## 0. 概要

期間：**2026-05-03 ～ 2026-05-10（7 天）**
撰寫：Architect agent
資料來源：`git log`、Supabase（`events` / `scraper_runs` / `research_sources`）、`docs/specs/`

## 1. 數量總覽

| 指標 | 數值 | 備註 |
|---|---|---|
| commits | **369** | 平均 53/日，異常高密度 |
| feat | 139 | |
| fix | 141 | fix 數略多於 feat → 大量是迭代修補 |
| docs | 79 | 主要是 architect agent guards + spec 文件 |
| 新增 scrapers | **39 個** | 本週前 73 → 本週末 ≥ 92 |
| 新增 events（含 inactive） | 328 | active 121 |
| 累計 active events | 382 | |
| 累計 all events | 964 | |
| reviewed events | 47 | |
| pending（active） | **0** | annotation backlog 完全消化 |
| scraper_runs | 631 | 失敗僅 1（0.16%） |
| OpenAI 7 天費用 | **$9.86** | 月推算 ~$42（>$15 alert） |
| 處理過事件數 | 4,543 | |
| 新增 DB migrations | **28 個** | 035 → 059，史上最多 |
| 新增/修改 workflows | 9 個 | |
| active specs | 11 個 | 0 個 done |
| 新增 web pages | ≥ 15 個 | |

## 2. 架構 / Spec 變動

### 2.1 重大新表（migration 035–059）

| Migration | 引入概念 | 影響 |
|---|---|---|
| 035 organizer_form_language | 主辦方表單語言 | 多語標注前置 |
| 037 event_status_and_offers | 取消/延期/票券狀態 | 為 ticket 整合鋪路 |
| 038/038b performer + field_corrections | 表演者欄位 + 手動修正持久化 | 三件套之首 |
| 040 selection_reason_corrections | 入選理由修正 | 三件套之三 |
| 041/045 source_exclusions(+TTL) | 黑名單關鍵字 + 30 天 TTL | 過濾不相關事件 |
| 042 quota_snapshots | 配額快照表 | quota_monitor 寫入 |
| 043 weekly_broadcast | 週報推送資料源 | LINE broadcast |
| 044 event_deactivation_audit | 停用稽核 | merge/manual 可追溯 |
| 046 daily_quality_metrics | 每日品質快照 | quality 儀表板 |
| 048 works_entity | 作品層級實體（電影/巡演/劇場） | events 同 work 共享導演/演員/年份 |
| 049 merged_into_event_id | 跨來源去重 | 取代部分 parent_event_id 用途 |
| 050 entity_tables | organizers / venues 規範化 | events 文字欄保留稽核，FK 走 normalized 表 |
| 051 works_tv_drama | work_type 擴展 | TV 連續劇 / 綜藝 |
| 052/052b event_media_coverage_view | 媒體報導 view | gnews 多入口聚合 |
| 053–056 performer/director i18n | `performers[] TEXT[]` + `performer_zh/en/director_zh/en` | 多人發表者 + 三語姓名 |
| 055 external_stats | e-Stat 整合 | 政府開放資料管線 |
| 057 events_image_url | 事件主視覺 | LINE / X.com / 海報 OCR |
| 058 co_organizer_sponsor_types | 共催/贊助類型 | organizer 拆分 |
| 059 organizer_multilingual | 主辦方多語 | 完成 i18n 最後一塊 |

### 2.2 新增頁面

- `/admin/specs`（規格瀏覽 + architecture dashboard）
- `/admin/works/{,[id],new}`（作品 CRUD）
- `/admin/exclusions`（黑名單管理）
- `/admin/roadmap`（路線圖視圖）

### 2.3 新增 / 修改 workflows

| Workflow | 用途 | 狀態 |
|---|---|---|
| `quota-monitor.yml` | DB size + GH minutes | 新建，運作中 |
| `monthly_health_check.yml` | 月健檢 | 新建 |
| `external-stats-pull.yml` | e-Stat 拉取 | 新建 |
| `x-post-cron.yml` | X (Twitter) 自動發文 | 新建 |
| `workflow-failure-notify.yml` | failure 集中告警 | 新建（已修自我迴圈 bug） |
| `weekly-broadcast.yml` | 週報 LINE 推送 | 修改：圖片/分類群組 |
| `daily-dev-report.yml` | 日報 + 成本告警 | 新增 cost anomaly 偵測 |
| `researcher.yml` | 研究主題發現 | 6 小時視窗修補 |
| `scraper.yml` | 主排程 | annotate/auto_qa 拆獨立 step |

## 3. 主要新增功能

### 3.1 內容/資料層

1. **39 個新爬蟲**（多為電影院 / 劇場 / 出版社 / 大學）— 一週新增量歷史最高
2. **e-Stat 政府開放資料整合**（external_stats）
3. **Vision OCR 海報萃取**（GPT-4o，從 X.com 圖片補事件資料）
4. **performers[] 多人多語**（學術研討會、巡演團體可正確顯示）

### 3.2 前端 / UX

1. **Dark mode（Phase 1–4）**：semantic color tokens + SSR anti-flash
2. **Sticky FilterBar**（top-14 + border + shadow）
3. **Admin 海報 OCR 自動填欄**（new event form 左圖右表，760px 海報預覽）
4. **Tab nav 三群分組 + 深綠分隔線**
5. **AnnouncementForm 圖片預覽 + LINE broadcast 圖片支援**
6. **i18n 大量打磨**：表演者/發表者三語、群組類別映射 24 → 8

### 3.3 監控 / 治理

1. **quota_monitor**（Supabase DB + GH Actions minutes，03:00 JST）
2. **OpenAI 成本告警**（$0.50 warn / $1.00 alert / $15 月 / $1.50 source spike）
3. **source_exclusions** + admin UI + auto-suggest from reports
4. **field/category/selection_reason corrections** 三件套形成完整人工→AI 學習迴路
5. **scraper_runs notes 異常診斷**（失敗時記錄 exception type）
6. **researcher slot 6h 視窗**（修 Actions queue delay 漏跑）

## 4. 優點（做得好）

1. **資料治理三件套成熟**：`field_corrections` + `category_corrections` + `selection_reason_corrections` 形成完整人類校正 → AI 學習迴路（feedback-loop spec）
2. **annotation backlog = 0**：pipeline 完全消化，標注品質可信
3. **scraper 失敗率極低**：631 runs 只 1 失敗（0.16%）
4. **架構知識沉澱**：architect agent SKILL.md 累積 30+ guard 規則 + history 完整記錄
5. **規格驅動開發**：`docs/specs/active` 11 個 proposal，從「直接寫 code」轉向「先規格再實作」
6. **監控覆蓋成形**：DB / 配額 / 成本 / 失敗通知 / health check 五條告警線都有

## 5. 缺點 / 風險

1. **🔴 OpenAI 成本月推算 $42**（7 天 $9.86）已**超過 $15 月 alert**閾值
   - 原因：researcher slot3 + 大量新 scraper 標注 + Vision OCR
   - 行動：本週內 review researcher prompt 與 enrich 策略
2. **🟠 commit 過於碎片**：369 commits / 7 天，平均 7 行/commit。許多是即時 hotfix，未走 V-M-D agent 完整流程
3. **🟠 spec 規劃 11 個 / done 0 個**：開立多、收斂少。`market-positioning-strategy` / `product-c-opportunity-radar` 等大型 spec 無進度標記
4. **🟡 migration 衝突命名累積**：011/018/029/038/052 都出現 `b` 後綴，命名規則開始失控
5. **🟡 i18n 補丁密集**：`weeklyBroadcast` keys 曾被 performer commits 弄丟（`032f0f5`），i18n regression guard 仍需強化
6. **🟡 39 個新 scraper 多為電影院**：類別失衡，`movie` 類事件占比恐過高，影響 lifestyle / academic 多樣性
7. **🟢 inactive : active = 582 : 382**：舊事件累積，下個月須評估歸檔策略
8. **🟢 reviewed 47 / active 382 = 12%**：人工覆核比例偏低，依賴 annotator 自動結果

## 6. 優先待辦清單

### 🔴 P0（本週必做）

1. **OpenAI 成本治理**：診斷 researcher/slot3 + Vision OCR 高成本，調整 prompt / 頻率 / 抽樣率
2. **6 個未執行 scraper 處置**（cinemarine, moonromantic, tiff, tokyoartbeat, tokyocity_i, tokyonow）
3. **39 個新 scraper 抽樣 dry-run 驗證**：確認 BaseScraper contract、source_id 穩定、JST→UTC 正確

### 🟠 P1（兩週內）

4. **Spec 收斂**：選 2–3 個 active spec 標記 in-progress / done（建議 `feedback-loop`、`tier1-data-completion`、`spec-architecture-dashboard`）
5. **Inactive 事件歸檔策略**：582 件 inactive，討論 90 天前移到 `events_archive`
6. **Migration 命名規則修正**：把所有 `Nb` 重命名 / 文件化，避免 060+ 繼續混亂
7. **DeepL secret 處置**：30 天 0 chars，移除或啟用
8. **i18n 完整性 CI 守衛**：PR 階段比對 zh/en/ja keys 完全一致

### 🟡 P2（四週內）

9. **類別均衡監控**：admin/quality 加 category 分佈圖，觸發 movie 比例 > 60% 警示
10. **Reviewed 比例提升計畫**：自動推送 reviewed 候選到 admin
11. **Vision OCR 成本監控**：單獨統計 Vision API call 數，獨立預算
12. **Workflow 失敗 LINE 整合測試**：自我迴圈已修，全鏈路驗證一次
13. **Top 10 spec 排序工作坊**：指派各 spec 的 owner agent + estimated effort

### 🟢 P3（持續性）

14. 月度 reviewer agent 自動化
15. admin/resources 儀表板（quota 視覺化）
16. LINE 推播月配額追蹤
17. scraper_runs 30 天 cleanup cron

## 7. 一週走勢（質性）

| 維度 | 評分 | 趨勢 |
|---|---|---|
| 規格化程度 | 80% | ↑↑（specs 制度建立） |
| 監控覆蓋率 | 100% | ↑↑（quota+cost+failure 三線完整） |
| 資料品質防線 | 85% | ↑（三 corrections 表） |
| i18n 一致性 | 70% | ↓（weeklyBroadcast 事件 + SC→TC 補丁） |
| 類別多樣性 | 50% | ↓（39 新 scraper 多 movie） |
| 開發節奏 | 100% | ↑↑（369 commits — 過熱） |
| 工程紀律 | 60% | ↓（大量直接 push, 少 V-M-D 完整流程） |
| 成本控制 | 40% | 🔴（已超 $15 月 alert） |

## 8. 下一步

優先 P0 三項：

1. OpenAI 成本診斷（owner: Architect + Engineer）
2. 6 個未執行 scraper 清理（owner: Scraper Expert）
3. 39 個新 scraper 抽樣驗證（owner: Tester）

完成後進入 P1 的 spec 收斂與 i18n CI 守衛。
