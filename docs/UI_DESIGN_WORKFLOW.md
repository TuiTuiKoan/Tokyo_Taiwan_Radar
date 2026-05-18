---
title: UI Design Iteration Workflow
description: Tokyo Taiwan Radar UI 設計、動畫、圖層與視覺驗證的可重複工作流程
ms.date: 2026-05-18
ms.topic: how-to
keywords:
  - ui design
  - frontend workflow
  - visual QA
  - z-index
  - motion
estimated_reading_time: 8
---

## 用途與定位

這份文件整理 Tokyo Taiwan Radar 近期 UI 迭代中形成的實作流程，適合給設計者、工程師與 AI coding agent 共用。它不是單次設計稿，也不是立即執行的 Skill；目前最適合作為團隊工作文件與未來 Skill / Agent 的 source of truth。

若任務是吉祥物、色票、背景、程序化縮圖或整體品牌語彙，請改讀 [Visual Design Styling Workflow](visual_design_styling_workflow.md)。

建議先維持為獨立文件，原因如下：

* 文件能同時服務人類閱讀、onboarding、回顧與任務交接
* 內容仍在快速演化，先不要把尚未穩定的判斷寫死成 agent 行為
* 等流程重複出現 3 次以上，再抽成 Skill 或專用 Agent 會更準確

如果要自動化，建議演進路徑是：

1. 先用本文件作為人工 checklist
2. 將穩定檢查項抽到 `.github/skills/agents/designer/SKILL.md`
3. 將可重複操作包成 Skill，例如「visual-layering-fix」
4. 將需要跨角色協作的流程包成 Agent，例如 Designer 提案、Engineer 實作、Tester 驗證

## 適用範圍

適合使用這份流程的任務包括：

* 首頁或內頁視覺層級調整
* 背景動畫、吉祥物動畫、SVG 動畫微調
* sticky header、搜尋列、下拉選單與浮層排序
* 活動縮圖、公告封面圖、分類縮圖的遮擋問題
* 響應式速度、位置、透明度與 mobile-specific 視覺異常
* light / dark mode 的材質、透明度與可讀性檢查

不適合用這份流程處理：

* 爬蟲資料品質問題
* Supabase schema 或 migration 設計
* 純文字翻譯品質修正
* 後端排程、token rotation、CI/CD 權限問題

## 近期案例摘要

| Commit | 目的 | 主要檔案 | 提煉出的規則 |
|---|---|---|---|
| `d7f33bc` | 放大吉祥物天線光點，恢復綠到黃綠漸層，移除白點殘影 | `web/app/globals.css` | 動畫峰值色不可用純白；Safari / WebKit 的 SVG filter 需要 visibility 防護 |
| `07938f1` | 允許 LAN dev origin 使用 HMR | `web/next.config.ts` | 視覺驗證常需要手機或其他裝置連本機 server |
| `d2871c2` | FloatingShapes 速度隨 viewport 縮放，修正 mobile 中央突現，新增內頁 subtle variant | `web/lib/design/FloatingShapes.tsx`, `web/lib/design/FloatingShapesAuto.tsx` | 動畫時間需和移動距離一起縮放；mobile 不適合半週期 stagger |
| `fab70aa` | 讓內頁也能看見 subtle FloatingShapes | `web/lib/design/FloatingShapes.tsx` | `bg-paper` 卡片會蓋住背景層；subtle overlay 需要在內容上方但降低 opacity |
| `f11a67d` | 保持分類縮圖與公告卡縮圖在漂浮動畫上方 | `web/lib/design/CategoryThumbnail.tsx`, `web/components/AnnouncementCard.tsx` | 重要視覺焦點提升到 `relative z-20` |
| `35c3cd7` | 保持公告詳情頁大封面圖在漂浮動畫上方 | `web/app/[locale]/announcements/[slug]/page.tsx` | 大圖外層也需要 position，否則 z-index 不生效 |
| `aacee50` | 讓首頁搜尋列保持最上層 | `web/components/FilterBar.tsx` | sticky controls 必須高於縮圖層，FilterBar 使用 `z-30` |

## 核心原則

先描述使用者看到的問題，再修改程式碼。不要從 class name 開始猜；先確認現象發生在哪個 route、哪個 viewport、哪個 theme、哪種 scroll 狀態。

優先在元件邊界修正。若所有分類縮圖都被遮擋，改 `CategoryThumbnail`；若只有公告詳情頁大圖被遮擋，改該頁封面圖外層。這能減少每個呼叫端的重複修補。

圖層修正要建立階梯，不要只把單一元素拉到最大值。這次形成的基準是：

| 層級 | 用途 | Tailwind class |
|---|---|---|
| 背景紙色 | 全站底色 | `-z-30` |
| 背景格線 | SiteBackground grid | `-z-20` |
| 首頁大型 FloatingShapes | 首頁背景動畫 | `-z-10` |
| 內頁 subtle FloatingShapes | 內頁前景淡動畫 | `z-10` |
| 重要圖片焦點 | CategoryThumbnail、公告封面圖 | `z-20` |
| sticky 搜尋與篩選 | FilterBar | `z-30` |
| Navbar 與高優先選單 | header / menu | `z-40` 到 `z-50` |
| dropdown panel | FilterBar dropdown | `z-50` |

> [!IMPORTANT]
> `z-index` 只對 positioned element 生效。Tailwind 需要搭配 `relative`、`absolute`、`fixed` 或 `sticky`。只加 `z-20` 而沒有 position，通常不會解決遮擋。

動畫要先分 variant，再調數值。首頁可以保留大型、低層、裝飾性動畫；內頁需要 subtle variant，讓它在內容上方但不干擾閱讀。

視覺焦點要比裝飾層更高。分類縮圖、公告封面圖、hero image 是內容本體，不應被裝飾動畫覆蓋。相反，純背景、卡片留白、低資訊密度區域可以讓 subtle animation 漂過。

sticky controls 要高於內容焦點。搜尋列、篩選列、navbar 屬於操作層，應在捲動時保持可點、可讀、不可被縮圖或封面圖遮住。

## 標準工作流程

### 1. 鎖定可見症狀

先把問題寫成使用者語言，例如：

* mobile 上 FloatingShapes 太慢
* 內頁看不到動畫
* 公告頁大圖被漂浮物件覆蓋
* 搜尋框被事件縮圖蓋住

接著記錄環境：

* route，例如 `/zh`、`/ja/announcements`、`/[locale]/announcements/[slug]`
* viewport，例如 mobile、tablet、desktop、wide desktop
* theme，例如 light、dark、system fallback
* interaction state，例如 initial load、scroll、hover、dropdown open

### 2. 找到實際責任元件

用搜尋確認問題位於哪個元件，而不是憑畫面猜測。常見入口：

```bash
rg "FloatingShapes|CategoryThumbnail|FilterBar|AnnouncementCard" web
rg "z-[0-9]+|sticky|fixed|absolute|relative" web/components web/app
```

目前常見責任元件：

| 現象 | 優先檢查 |
|---|---|
| 背景動畫位置或速度 | `web/lib/design/FloatingShapes.tsx` |
| route-based 動畫顯示 | `web/lib/design/FloatingShapesAuto.tsx` |
| 分類縮圖遮擋 | `web/lib/design/CategoryThumbnail.tsx` |
| 公告列表縮圖 | `web/components/AnnouncementCard.tsx` |
| 公告詳情大圖 | `web/app/[locale]/announcements/[slug]/page.tsx` |
| 搜尋列或篩選層級 | `web/components/FilterBar.tsx` |
| 全域動畫 keyframes | `web/app/globals.css` |

### 3. 畫出圖層模型

修改前先列出目前層級：

```text
SiteBackground       -z-30 / -z-20
FloatingShapes full  -z-10
FloatingShapes subtle z-10
CategoryThumbnail     z-20
FilterBar             z-30
Navbar                z-50
```

如果某個元素被遮住，先問三個問題：

1. 被遮住的是內容本體，還是裝飾背景
2. 遮住它的元素是否真的需要在前景
3. 需要提升的是單一呼叫端，還是共享元件根節點

### 4. 用最小範圍修正

優先順序：

1. 修正共享元件根節點，例如 `CategoryThumbnail`
2. 修正特定頁面的內容外層，例如 announcement detail cover image
3. 修正操作層容器，例如 `FilterBar` sticky wrapper
4. 最後才調整全域 overlay 或 keyframes

圖層修正常見 class：

```tsx
<div className="relative z-20 overflow-hidden">
  ...
</div>

<div className="sticky top-14 z-30">
  ...
</div>
```

### 5. 檢查 light / dark 與 mobile / desktop

至少檢查以下組合：

* light desktop
* dark desktop
* light mobile
* dark mobile
* scroll 中段，尤其 sticky 元件覆蓋內容時
* dropdown open 狀態

視覺驗證重點：

* 文字沒有被動畫或圖片遮住
* 搜尋列與 navbar 保持可點擊
* 重要圖片沒有被 subtle overlay 壓暗或蓋住
* 動畫不在 mobile 中央突然出現
* 漂浮動畫速度與畫面尺寸成比例

### 6. 執行最小驗證

前端變更至少跑 build：

```bash
cd web && pnpm run build
```

若涉及視覺層級，優先用 local preview 或 production deploy 檢查實際頁面。可用這些路徑作為 smoke test：

```text
/zh
/ja/announcements
/zh/announcements/[slug]
/zh/events/[id]
/zh/saved
```

### 7. 記錄可泛化教訓

若修正揭露了可重複規則，更新 Designer 紀錄或 Skill：

* 一次性事件，放在 `.github/skills/agents/designer/history.md`
* 已穩定的規則，放在 `.github/skills/agents/designer/SKILL.md`
* 可供團隊閱讀的流程，放在 `docs/`
* 可由 AI 反覆執行的流程，抽成 Skill

## Motion 設計準則

距離與時間要一起縮放。若移動距離由 viewport 決定，duration 也要跟 viewport scale 調整，否則 mobile 會顯得過慢或過快。

避免在 mobile 使用半週期 stagger。當兩個元素差半個動畫週期，狹窄螢幕上的 midpoint 往往落在畫面中心，容易造成「中央突然冒出」的錯覺。

前景 subtle animation 的 opacity 要比背景 animation 更克制。內頁可使用 `opacity-30`、`mix-blend-multiply`、`dark:mix-blend-screen`，但內容焦點必須高於它。

裝飾動畫一律 `pointer-events-none`。任何背景或 subtle overlay 都不應阻擋點擊、hover 或文字選取。

## 可交接任務模板

把問題交給其他人或 AI agent 時，建議使用這個格式：

```text
目標：修正 [route / component] 的 [可見問題]。

目前現象：
在 [viewport / theme / interaction state] 下，[元素 A] 會 [遮住 / 變慢 / 不可見 / 跑位]。

已知層級：
* FloatingShapes subtle: z-10
* CategoryThumbnail / image focus: z-20
* FilterBar sticky: z-30
* Navbar / dropdown: z-40 to z-50

限制：
* 不新增 UI library
* 不使用 hard-coded gray / white tokens，除非既有品牌固定色
* light / dark mode 都要保持可讀
* mobile 與 desktop 都要檢查

驗收：
* `cd web && pnpm run build` 通過
* 相關頁面在 scroll、dropdown open、light / dark 下都不互相遮擋
* 若新增 user-facing copy，三語 messages 同步
```

## 何時轉成 Skill 或 Agent

維持獨立文件，當流程仍需要人類判斷、視覺審美與上下文解釋。

轉成 Skill，當同一種任務可用固定步驟重複執行，例如：

* 檢查 z-index ladder
* 找出 route 上所有可能被 overlay 蓋住的圖片
* 跑 build 並列出視覺 smoke test URL
* 掃描新增 hard-coded color token

轉成 Agent，當任務需要角色分工或上下文隔離，例如：

* Designer 只提出 layer / motion spec
* Engineer 實作並回報 diff
* Tester 用瀏覽器截圖驗證 mobile / desktop / dark mode
* Reviewer 將教訓寫回 history 或 SKILL

## 最小完成定義

一次 UI 視覺修正完成時，至少要有：

* 明確描述已修正的使用者可見問題
* 最小範圍 diff，優先改共享元件或責任頁面
* `pnpm run build` 通過
* light / dark 與 mobile / desktop 的驗證說明
* 若發現新規則，更新 history、Skill 或本文件其中之一

這個流程的目標不是把 UI 變成一串固定 class，而是讓每次視覺修正都能回答三件事：使用者看到什麼、哪個元件真正負責、修正後整個圖層系統是否更清楚。