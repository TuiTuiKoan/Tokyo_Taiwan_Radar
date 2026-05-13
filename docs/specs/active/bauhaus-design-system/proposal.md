---
slug: bauhaus-design-system
title: Bauhaus 設計系統 — 全站視覺重塑
status: active
branch: main
created: 2026-05-14
tags: [web, design, ui, i18n]
---

## What（做什麼）

把 Tokyo Taiwan Radar 全站從 stock Tailwind 視覺，重塑為**程序化 Bauhaus 風格**的品牌身份：
紙色背景 + 蠟蘋果吉祥物 + 程序化幾何形狀 + Zen Maru Gothic 顯示字體 + 語意化色彩 token。

**範圍**：首頁 hero、活動列表、活動詳情、公告、來源、關於、Navbar、SaveButton、SiteBackground、FloatingShapes、Mascot、OG 圖。
**新增**：`web/lib/design/` 設計函式庫（tokens、fonts、Badge、DateChip、FilterChip、MascotAvatar、FloatingShapes、CategoryThumbnail、patterns、EventCardMockup）。

## Why（為什麼）

- **產品差異化**：在 niche「台日活動聚合」領域，視覺辨識度比功能更難被複製。
- **品牌資產累積**：吉祥物（蠟蘋果）+ 固定色票 = 後續 LINE 廣播、OG 卡、X 貼文都能複用同一套視覺。
- **可擴充至 slide / image generation**：design token 對齊 Satori，未來 Recraft API 圖文管線可以共用。
- **i18n × 視覺一致性**：三語切換不破版（Zen Maru Gothic + Noto Sans JP 覆蓋 zh/ja，Latin fallback OK）。

## Non-Goals（不做什麼）

- ❌ **不做 dark mode 重塑**：保留現有 token 系統 + `:root.dark` 覆寫即可，不開新主題色票
- ❌ **不引入 UI 套件**（MUI / Radix / Mantine）：所有 component 以 Tailwind v4 + inline SVG 手刻
- ❌ **不做動效函式庫**（framer-motion）：CSS `transition` + `motion-safe:` 已足夠
- ❌ **不重畫 Admin 後台**：admin 路徑視覺維持工具感優先
- ❌ **本 spec 不含 Recraft API 圖文管線**（移至後續 spec）

## Design（設計摘要）

### 品牌色票（最終定案）

| Token | Hex | 用途 |
|---|---|---|
| paper | `#FFFDF5` | 主背景紙色 |
| mocha | `#3A261F` | 主文字、標題 |
| mascot-red / pink | `#E84860` | 品牌主色、強調 |
| forest | `#1F5E2B` | 連結預設色（取代 blue-600） |
| matcha | `#F7FFE8` | 圖示 hover 背景 |
| leaf | `#C4E86F` | FloatingShape 第二色 |
| LINE green | `#06C755` | LINE CTA 按鈕**唯一**使用 |

### 字體系統（`web/lib/design/fonts.ts`，next/font/google）

- `--font-display`：Zen Maru Gothic（hero、h1–h3、卡片標題、OG 標題）
- `--font-body`：Noto Sans JP（UI、列表、FilterBar）
- `--font-mono`：JetBrains Mono（時間戳、ID）
- `--font-accent`：Bagel Fat One（保留給 slide 編號）

### 核心 component

- `<SiteBackground />`：固定紙色 + 格線 SVG，掛在 `[locale]/layout.tsx`
- `<FloatingShapes />`：10 槽程序化幾何，9 種 fill × 兩色，每動畫週期重抽，純色紅僅在最小兩階出現
- `<MascotAvatar />`：蠟蘋果吉祥物（inline SVG）
- `<EventListClient />` row：64px 日期欄（週幾紅 / 月 / 日大字 / 跨日 `~MM/DD`），右側絕對定位 SaveButton（hover 顯現）
- `<Navbar />`：所有 icon button 統一 `w-8 h-8 rounded hover:bg-matcha`
- `<SaveButton compact />`：32×32 心形，未存愛心 mocha→forest，已存綠底白心
- `<AnnouncementCard />`：金色漸層 + 左方形圖 + 程序化 hash pattern

### Edge function 容量規約（已修復）

- `app/[locale]/events/[id]/opengraph-image.tsx` **不可從 barrel `@/lib/design` import**，必須直接 `import from "@/lib/design/tokens"`，否則 next/font binary 會被打包進 Edge bundle 撐爆 1MB 限制（事故 `94e4c76` → `f587022`）。

### 檔案影響

| 區域 | 檔案 |
|---|---|
| 設計函式庫（新增） | `web/lib/design/{tokens,fonts,Badge,DateChip,FilterChip,MascotAvatar,FloatingShapes,CategoryThumbnail,patterns,EventCardMockup,index}.{ts,tsx}` |
| Global 樣式 | `web/app/globals.css`（`@theme` token、`@layer base` 連結色、`html:has([data-site-bg])`） |
| Layout | `web/app/[locale]/layout.tsx`（掛 SiteBackground、fontVariables） |
| Pages | `web/app/[locale]/{page,events/[id]/page,announcements/page,sources/page,about/page}.tsx` |
| Components | `web/components/{Navbar,SaveButton,EventListClient,AnnouncementCard,SiteBackground}.tsx` |
| i18n | `web/messages/{zh,en,ja}.json`（heroPara、lineCta、tabs 移除等） |
| Agent | `.github/agents/designer.agent.md`、`.github/skills/agents/designer/SKILL.md`（已存在） |
| Architecture | `docs/architecture/system-map.json`（本 spec 同步加入 designer） |

## References

- `.github/agents/designer.agent.md`（Designer agent 定義）
- `docs/specs/active/spec-architecture-dashboard/`（看板讀取機制）
- Commit `fa22ae4`（首頁 Bauhaus 落地）
- Commit `94e4c76`（全站套用）
- Commit `f587022`（OG image Edge 容量修復）
