---
title: Architecture Overview
description: 東京台灣雷達全站架構總覽 — 爬蟲、翻譯、資料庫、前端、CI/CD、LINE Bot
ms.date: 2026-05-01
---

## 系統總覽

```text
┌────────────────────────────────────────────────────────────────┐
│                    GitHub Actions（每日 09:00 JST）              │
│                                                                │
│  1. main.py ──→ 50+ scrapers ──→ database.py ──→ Supabase     │
│  2. merger.py ──→ 跨來源去重                                    │
│  3. annotator.py ──→ GPT-4o-mini 標注 14 欄位                   │
│  4. annotator.py --enrich-movie-titles ──→ eiga.com 官方片名    │
│  5. validate.py ──→ 異常偵測                                    │
│  6. notify.py ──→ LINE 推播摘要                                 │
│  7. health_check.py ──→ LINE 異常告警（僅錯誤時）               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                          │
                          ▼
                    ┌────────────┐
                    │  Supabase  │
                    │ PostgreSQL │
                    │  + Auth    │
                    └─────┬──────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Vercel（Next.js 16）  │
              │   三語前端 zh/en/ja    │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   LINE Messaging API   │
              │  webhook + broadcast   │
              └───────────────────────┘
```

---

## 相關文件

* [爬蟲來源研究到上線完整工作流](SCRAPER_PIPELINE.md)
* [翻譯與標注完整流程](TRANSLATION_PIPELINE.md)
* [GITHUB_TOKEN 快速參考清單](GITHUB_TOKEN_SYNC_CHECKLIST.md)
* [GITHUB_TOKEN 完整輪替指南](../.github/instructions/token-rotation.instructions.md)
* [Secrets 生命週期與審計路線圖](../.github/SECRETS_LIFECYCLE.md)

### 權限檢查速查

最小建議權限:

* Fine-grained PAT: Issues: write + Metadata: read
* Classic token: repo scope

GitHub 後台核對路徑:

1. GitHub Settings
2. Developer settings
3. Personal access tokens
4. Fine-grained tokens
5. 開啟目前使用中的 token，確認 Repository permissions 包含:
  * Issues: Write
  * Metadata: Read

本機快速驗證:

```bash
cd scraper
source venv/bin/activate
python update_source.py --url "https://example.com" --status researched --create-issue
```

判讀結果:

* 成功建立 Issue: 權限足夠
* 403 Resource not accessible: 權限不足（優先檢查 Issues 或 Metadata）
* 401 Bad credentials: token 過期或 token 值錯誤

---

## 爬蟲層（`scraper/`）

### 核心檔案

| 檔案 | 用途 |
|------|------|
| `sources/base.py` | `Event` dataclass（全部欄位定義）+ `BaseScraper` ABC |
| `sources/*.py` | 各來源爬蟲，每支實作 `scrape() → list[Event]` |
| `main.py` | 排程器 — `SCRAPERS` 清單、`--dry-run`、`--source NAME` |
| `database.py` | `_event_to_row()` + Supabase upsert（ON CONFLICT source_name,source_id）|
| `merger.py` | 跨來源去重 — 相似度 > 85% + 同日期 → 合併 + deactivate |
| `translator.py` | DeepL 翻譯補全（部分爬蟲在入 DB 前使用）|
| `annotator.py` | GPT-4o-mini 標注 + `enrich_movie_titles()` |
| `movie_title_lookup.py` | eiga.com 官方片名查詢（含 in-memory cache）|
| `validate.py` | 異常偵測：缺翻譯、缺日期、selector 失效 |
| `health_check.py` | 每日健康監控（LINE 告警，僅錯誤時推播）|
| `indexnow.py` | 新事件 URL 提交至 Bing/IndexNow 加速索引 |

### 資料流

```text
scraper.scrape()
  → Event(raw_title, raw_description, name_ja, ...)
  → [cinema scrapers] lookup_movie_titles(title) → name_zh/name_en
  → database.upsert_events() → DB (annotation_status='pending')
```

---

## 翻譯與標注流程

一個事件最多涉及 **14 個翻譯欄位**：

| 分組 | 欄位 | 語言數 |
|------|------|--------|
| 名稱 | `name_ja`, `name_zh`, `name_en` | 3 |
| 描述 | `description_ja`, `description_zh`, `description_en` | 3 |
| 地點名稱 | `location_name`（日文原文）, `location_name_zh`, `location_name_en` | 2 翻譯 |
| 地址 | `location_address`（日文原文）, `location_address_zh`, `location_address_en` | 2 翻譯 |
| 營業時間 | `business_hours`（日文原文）, `business_hours_zh`, `business_hours_en` | 2 翻譯 |
| 收錄理由 | `selection_reason`（JSON: `{ja, zh, en}`）| 3（JSON 內） |

### 五層流程

```text
1. 爬蟲層 → raw_title/raw_description 永不覆寫
           → cinema scrapers 呼叫 eiga.com lookup → name_zh/name_en

2. DeepL 層（可選）→ 部分爬蟲呼叫 fill_translations()，只補空欄位

3. GPT-4o-mini 標注 → 所有 14 欄位 + category + dates + pricing
                     → 子事件拆分（各自有完整 ja/zh/en）

4. 官方片名補全 → 所有 movie 事件（排除 eiga_com + reviewed）
                 → eiga.com 查到就覆寫 name + description 括號引用

5. 前端 fallback → locale → ja → zh → en → "(未命名)"
```

### 關鍵檔案對照

| 層 | 檔案 | 寫入欄位 |
|----|------|---------|
| 爬蟲 | `sources/base.py` | `Event` dataclass 定義 |
| 爬蟲 | `movie_title_lookup.py` | `name_zh`, `name_en`（電影） |
| DeepL | `translator.py` | `name_*`, `description_*` |
| GPT | `annotator.py` | 全部 14 欄位 |
| 補全 | `annotator.py` `enrich_movie_titles()` | `name_zh/en` + `description_zh/en` |
| 前端 | `web/lib/types.ts` | `getEventName()`, `getEventDescription()` 等 fallback chain |

---

## 資料庫（`supabase/`）

### 核心表

| 表 | Migration | 用途 |
|----|-----------|------|
| `events` | 001 | 事件主表 — 全部欄位 |
| `user_roles` | 004 | admin 權限（RLS policy 依賴） |
| `event_reports` | 006 | 使用者舉報 / 類別建議 |
| `scraper_runs` | 007, 014 | 每日爬蟲執行紀錄（token 用量、費用） |
| `research_reports` | 008 | 研究報告 |
| `research_sources` | 009 | 來源評估與狀態追蹤 |
| `creators` | 020 | 台灣內容創作者資料庫 |
| `line_subscribers` | 022 | LINE Bot 訂閱者 |
| `aeo_visits` | 029 | AI 引擎造訪紀錄 |
| `announcements` | 030 | 發文管理（三語 + 社群發布狀態）|
| `announcement_events` | 030 | 發文 ↔ 事件關聯（junction table）|

### 重要 migration 演進

| Migration | 新增功能 |
|-----------|---------|
| 002 | 兩層架構（raw + annotated）|
| 010 | 地點/地址/營業時間多語欄位 |
| 011 | `force_rescrape` / `secondary_source_urls` |
| 016 | `event_views` 瀏覽統計 |
| 017 | `reviewed` annotation status |
| 018 | `official_url` + `scraped_at` |

---

## 前端（`web/`）

### 技術棧

| 項目 | 版本/工具 |
|------|----------|
| 框架 | Next.js 16.2.4（App Router）|
| UI | React 19 + Tailwind CSS 4 |
| i18n | next-intl 4.9.1（zh / en / ja）|
| Auth | Supabase `@supabase/ssr` 0.10.2 |
| 錯誤追蹤 | Sentry |
| Middleware | `proxy.ts`（非 middleware.ts）|

### 路由結構

```text
web/app/
├── [locale]/
│   ├── page.tsx              首頁（事件搜尋 + 篩選 + AnnouncementCard）
│   ├── events/[id]/page.tsx  事件詳情（ISR revalidate=3600）
│   ├── categories/           分類瀏覽
│   ├── cities/               城市篩選
│   ├── saved/                收藏事件
│   ├── announcements/        發文列表 + 詳情（[slug]）
│   ├── auth/                 登入/回調
│   └── admin/
│       ├── page.tsx           事件管理主表
│       ├── [id]/page.tsx      事件編輯表單
│       ├── sources/           來源健康監控
│       ├── stats/             爬蟲統計（token/費用）
│       ├── reports/           舉報管理
│       ├── research/          研究來源管理
│       ├── creators/          創作者管理
│       ├── announcements/     發文 CRUD
│       ├── aeo/               AI 引擎造訪分析
│       └── users/             使用者管理
├── api/
│   ├── admin/                 admin API routes
│   ├── announcements/         發文 CRUD + 社群發布
│   └── line-webhook/          LINE Bot webhook
├── robots.ts                  SEO robots.txt（含 AI bot 許可）
├── sitemap.ts                 多語 sitemap
└── layout.tsx                 Root layout + JSON-LD schema
```

### 主要 Components

| Component | 用途 |
|-----------|------|
| `EventCard.tsx` | 事件卡片（列表用）|
| `FilterBar.tsx` | 篩選欄（category / date / location / paid）|
| `AdminEventTable.tsx` | admin 事件管理主表（批量操作）|
| `AdminSourcesTable.tsx` | 來源健康監控 |
| `AdminReportsTable.tsx` | 舉報管理 + 類別/描述編輯 |
| `AdminResearchTable.tsx` | 研究來源管理 |
| `AdminEventForm.tsx` | 事件編輯表單 |
| `AnnouncementForm.tsx` | 發文編輯表單 |
| `AnnouncementCard.tsx` | 首頁發文卡片 |
| `SaveButton.tsx` | 收藏按鈕（client component） |
| `ReportSection.tsx` | 舉報/類別建議區塊 |
| `ViewTracker.tsx` | 瀏覽數追蹤 |
| `Navbar.tsx` | 導覽列 + 語言切換 |

---

## 社群發文（Announcements）

### 流程

```text
Admin 撰寫發文（三語 title + body + images）
  → 選擇關聯事件（announcement_events）
  → 設定 published_at（發布 / 草稿）
  → 社群發布（LINE / 其他平台）
     └─ API: POST /api/announcements/[id]/publish/[platform]
        → social_status JSONB 更新
```

### 檔案對照

| 檔案 | 用途 |
|------|------|
| `supabase/migrations/030_announcements.sql` | DB schema + RLS |
| `web/lib/types.ts` | `Announcement` interface |
| `web/app/api/announcements/route.ts` | 列表 + 建立 |
| `web/app/api/announcements/[id]/route.ts` | 單筆 CRUD |
| `web/app/api/announcements/[id]/publish/[platform]/route.ts` | 社群發布 |
| `web/components/AnnouncementForm.tsx` | 編輯表單 |
| `web/components/AnnouncementCard.tsx` | 首頁卡片 |
| `web/app/[locale]/announcements/[slug]/page.tsx` | 發文詳情頁 |

---

## LINE Bot

### 兩個方向

| 方向 | 檔案 | 說明 |
|------|------|------|
| Inbound | `web/app/api/line-webhook/route.ts` | Webhook：follow/unfollow、語言設定、分類訂閱 |
| Outbound | `scraper/weekly_line_broadcast.py` | 每週推播：依語言分群、GPT 策展摘要 |
| Outbound | `scraper/notify.py` + `line_notify.py` | 每日爬蟲摘要推播（管理員）|
| Outbound | `scraper/health_check.py` | 異常告警（僅錯誤時）|

### 環境變數

| 變數 | 用途 | 平台 |
|------|------|------|
| `LINE_CHANNEL_SECRET` | Webhook 簽名驗證 | Vercel |
| `LINE_CHANNEL_TOKEN` | Messaging API 推播 | Vercel + GHA |
| `LINE_USER_ID` | 管理員推播目標 | GHA |

---

## CI/CD 與部署

### GitHub Actions Workflows

| Workflow | 排程 | 用途 |
|----------|------|------|
| `scraper.yml` | 每日 09:00 JST | 主爬蟲 pipeline（下方詳述）|
| `merger.yml` | — | 手動觸發跨來源合併 |
| `annotate-now.yml` | — | 手動觸發重新標注 |
| `scrape-now.yml` | — | 手動觸發爬取 |
| `researcher.yml` | 每日 4 slots JST | 來源批次探索（Layer A）|
| `discovery-accounts.yml` | 每日 Mon–Thu | note.com + Peatix 帳號探索 |
| `auto-research.yml` | 每日 00:30 JST | 自動評估 candidate 來源（Layer B1）|
| `auto-generate.yml` | 每日 01:00 JST | 自動代碼生成 + sandbox（Layer B2）|
| `weekly-broadcast.yml` | 每週一 10:30 JST | LINE 週報推播 |
| `weekly-report.yml` | 每週 | 營運週報產生 |
| `daily-dev-report.yml` | 每日 | 開發日報 |
| `backup.yml` | — | DB 備份 |
| `daily-health-check.yml` | 每日 | 健康監控 |
| `secret-rotation-reminder.yml` | — | 密鑰輪替提醒 |

### 每日 Pipeline（scraper.yml）

```text
Job 1: scrape
  → python main.py（50+ scrapers → DB upsert）
  → python merger.py（跨來源去重）
  → python annotator.py --fix-reviewed（補翻譯）
  → python annotator.py --enrich-movie-titles（eiga.com 補全）
  → python summarize_run.py（摘要 JSON）

Job 2: validate（depends: scrape）
  → python validate.py → 異常偵測

Job 3: notify（depends: scrape + validate, always runs）
  → LINE 推播摘要 + 警告
```

### 部署

| 平台 | 用途 | 觸發 |
|------|------|------|
| Vercel | Next.js 前端 + API routes | git push main → 自動部署 |
| GitHub Actions | 爬蟲 + 標注 + 推播 | 排程 / 手動 |
| Supabase | PostgreSQL + Auth + RLS | Migration 手動執行 |

### 環境變數總覽

| 變數 | GHA | Vercel | 用途 |
|------|-----|--------|------|
| `SUPABASE_URL` | ✓ | ✓ | DB 連線 |
| `SUPABASE_SERVICE_ROLE_KEY` | ✓ | — | 服務端寫入（bypass RLS）|
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | — | ✓ | 前端讀取 |
| `OPENAI_API_KEY` | ✓ | — | GPT 標注 |
| `DEEPL_API_KEY` | ✓ | — | DeepL 翻譯 |
| `LINE_CHANNEL_SECRET` | — | ✓ | Webhook 驗簽 |
| `LINE_CHANNEL_TOKEN` | ✓ | ✓ | LINE 推播（GHA=broadcast, Vercel=reply）|
| `LINE_USER_ID` | ✓ | — | 管理員推播 |
| `INDEXNOW_KEY` | ✓ | — | IndexNow 索引 |
| `SENTRY_DSN` | ✓ | ✓ | 錯誤追蹤 |
| `SENTRY_AUTH_TOKEN` | — | ✓ | Source map 上傳 |

---

## SEO / AEO

| 檔案 | 用途 |
|------|------|
| `web/app/robots.ts` | robots.txt — 許可 GPTBot、PerplexityBot 等 AI 爬蟲 |
| `web/app/sitemap.ts` | 多語 sitemap + `x-default` alternate |
| `web/app/layout.tsx` | Root JSON-LD（WebSite + SearchAction + Organization）|
| `web/app/[locale]/events/[id]/page.tsx` | 事件 JSON-LD（Event schema + BreadcrumbList）|
| `web/public/llms.txt` | AI 引擎索引文件 |
| `web/proxy.ts` | i18n middleware + 靜態文件排除 |
| `scraper/indexnow.py` | 新事件 URL 提交至 IndexNow |

