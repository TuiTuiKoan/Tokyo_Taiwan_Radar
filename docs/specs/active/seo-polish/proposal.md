---
slug: seo-polish
title: SEO 收尾 — Image / Streaming / A11y / OG
status: active
created: 2026-05-12
tags: [seo, web, quick-win]
---

## What（做什麼）

完成 SEO 審計發現的 5 項收尾任務，將整體 SEO 評分從 8.2 提升至 9.5+。

核心基礎設施（metadata, JSON-LD, sitemap, robots.txt, canonical, hreflang, Speed Insights）已全部到位。本 spec 處理剩餘的 image 最佳化、streaming、accessibility、OG 擴充、反向連結。

## Why（為什麼）

- 公開 repo 後 GitHub README 是最容易的 dofollow 反向連結，目前是純文字未產生效果
- `<img>` 不經 Next.js Image Optimization Pipeline，缺 srcset / WebP / lazy-load
- 高流量頁面（首頁、事件詳情）無 `loading.tsx`，TTFB→FCP 之間白屏
- EventCard 連結缺 aria-label，螢幕閱讀器無法描述目標
- 分類/城市頁分享時無動態 OG 圖片，社群預覽只有文字

## Non-Goals（不做什麼）

- 不處理 admin 頁面 SEO（admin 被 robots.txt 排除）
- 不新增 SEO meta 欄位到 DB
- 不修改現有 JSON-LD 結構
- 不做 Core Web Vitals 的全面效能調校（留給獨立 spec）

## Design（設計摘要）

### T1 — README 超連結（5 分鐘）

`README.md` 第 3 行改為 markdown 超連結：
```markdown
🌐 Website: [tokyotaiwanradar.com](https://tokyotaiwanradar.com)
```

### T2 — `<img>` → Next.js `<Image>`（30 分鐘）

3 個元件需修改：

| 元件 | 現況 | 改法 |
|------|------|------|
| `AnnouncementCard.tsx` | `<img src={...} alt={...}>` | `<Image src={...} alt={...} width={...} height={...} />` |
| `AnnouncementForm.tsx` | `<img>` 預覽圖 | `<Image>` + `unoptimized`（blob URL） |
| `MovieWorksList.tsx` | `<img>` 海報圖 | `<Image>` + `fill` + `sizes` |

需在 `next.config.ts` 加 `images.remotePatterns` 允許外部圖片域名。

### T3 — EventCard aria-label（15 分鐘）

`EventCard.tsx` 的 `<a>` / `<Link>` 加 `aria-label={t("eventLink", { name: eventName })}`。
`web/messages/*.json` 新增 key `"eventLink": "{name} 的詳情"`。

### T4 — 分類/城市頁動態 OG（1 小時）

複製 `events/[id]/opengraph-image.tsx` 模板，分別建立：
- `categories/[category]/opengraph-image.tsx`
- `cities/[city]/opengraph-image.tsx`

內容：分類/城市名 + 事件數量 + 站名 logo。共用 edge runtime + DotGothic16 字型。

### T5 — loading.tsx Streaming（30 分鐘）

新增 `loading.tsx` 至：
- `web/app/[locale]/loading.tsx`（首頁）
- `web/app/[locale]/events/[id]/loading.tsx`（事件詳情）
- `web/app/[locale]/categories/[category]/loading.tsx`（分類頁）

骨架屏設計：與現有卡片佈局一致的灰色 placeholder。

## References

- [SEO 審計記錄（2026-05-12 session）]
- [Vercel Speed Insights Dashboard](https://vercel.com/analytics)
- [Next.js Image Optimization Docs](https://nextjs.org/docs/app/api-reference/components/image)
