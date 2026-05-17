---
name: plan-critic
description: Critique principles, complexity heuristics, and anti-rabbit-hole rules for the Plan Critic agent
applyTo: .github/agents/plan-critic.agent.md
---

# Plan Critic Skills

每次批評計畫前必讀。

## 商業主軸（Tokyo Taiwan Radar）

依優先順序：

1. **資料完整性與正確性** — 爬蟲覆蓋率、annotation 品質、去重 / merger、FC 鎖定機制
2. **i18n 一致性** — 三語（zh/en/ja）翻譯完整、locale 顯示正確
3. **使用者觸達** — LINE 推播、SEO、Sitemap、PWA
4. **後台運營效率** — Admin UI、auto-research、health check 自動化
5. **視覺與體驗** — Designer 範疇，優先級最低

**判斷原則**：若計畫主要修飾 5（視覺）而 1–4 仍有未解問題，必須在「優先順序提醒」段標紅。

## 複雜度評估啟發式

| 訊號 | 複雜度貢獻 |
|------|-----------|
| 新增 migration | +1 level |
| 跨 3 個以上檔案 | +1 level |
| 觸碰 annotator.py SYSTEM_PROMPT | +1 level |
| 新增 i18n key（三語檔案）| +0.5 level |
| 新增 GPT 呼叫路徑 | +1 level（成本 + 污染風險）|
| 觸發既有 Guard（Architect SKILL.md）| +1 level（需嚴格遵守）|
| 修改 merger.py `_normalize` | +2 level（高 regression 風險）|
| 修改 RLS / Supabase 權限 | +2 level |

基準：每 +1 level 對應約半天工程量。≥ 3 levels 為 high；≥ 5 為 very-high。

## 業務價值評估啟發式

| 影響範圍 | 價值 |
|---------|------|
| 修壞掉的爬蟲（事件斷流）| high |
| 修 annotation 污染（影響多事件）| high |
| 新增爬蟲（覆蓋新區域／類型）| medium-high |
| 新增 admin UI 功能（提升運營效率）| medium |
| 改善視覺 / 動畫 / 配色 | low |
| 修單一事件的資料 | low（手動修即可，不需計畫）|

## 復用優先 component 清單

新增 UI 前先檢查：

- `web/components/EventCard.tsx` — 事件卡片
- `web/components/FilterBar.tsx` — 篩選列
- `web/components/AdminEventTable.tsx` — 後台表格
- `web/components/AdminEventForm.tsx` — 後台表單
- `web/components/RawDataSection.tsx` — 原始資料展示
- `web/components/SaveButton.tsx` — 收藏按鈕

新增 scraper 前必檢查：

- `scraper/sources/base.py` — BaseScraper ABC
- `scraper/sources/peatix.py` — 事件平台聚合範本
- `scraper/sources/iwafu.py` — 單一品牌商範本

## 反鑽牛角尖訊號

下列模式必須在報告中明確標紅：

1. 「再優化一下 XX」型計畫 — 通常價值不高
2. 修飾性 UI 微調而忽略翻譯 / 資料錯誤
3. 為單一事件設計通用機制（過度抽象）
4. 在 5 個 Guard 規則之間反覆穿梭而不解決根因
5. 連續 3 個計畫都在同一檔案／同一功能微調

## 必踏一次的 Guard 檢查

每次批評計畫，至少瀏覽一次 Architect SKILL.md 中的這幾個高頻 Guard：

- Category Sync Guard（4 處同步）
- Event Form Sync Guard（4 處同步）
- i18n Regression Guard
- Manual Translation Fix Persistence Guard（必須鎖 FC）
- SCRAPERS List Completeness Guard

若計畫涉及上述任一主題，必須在「全站架構整合分析」段明確列出。

## 報告長度上限

- 整體 ≤ 600 行
- 單段 ≤ 100 行
- 引用既有檔案路徑用 markdown link，不展開檔案內容
- 計畫摘要 ≤ 10 行（不重複 plan.md 全文）
