# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit。

## Phase A: 設計 token 與字體（基礎層）

- [x] A1: 在 `globals.css` 建立 `@theme` semantic token（paper、mocha、forest、matcha、line-bg、border-line…）
- [x] A2: 接入 next/font/google 四套字（Zen Maru / Noto Sans JP / JetBrains Mono / Bagel Fat One）
- [x] A3: `web/lib/design/tokens.ts` 匯出 satoriTokens（OG 圖共用）
- [x] A4: `web/lib/design/fonts.ts` 匯出 `fontVariables` 給 `<html>` className
- [x] A5: `@layer base`：h1–h3 套 font-display + mocha；a 預設 forest 色 + 取消底線

## Phase B: 核心 component

- [x] B1: `MascotAvatar`（蠟蘋果 inline SVG）
- [x] B2: `FloatingShapes`（10 槽程序化 × 9 fill × 雙色，純紅限制 + ≥1 solid 保證）
- [x] B3: `SiteBackground`（紙色 + 格線 SVG，掛 layout）
- [x] B4: `DesignDefs` patterns（procedural hash fill）
- [x] B5: `Badge`、`DateChip`、`FilterChip`、`CategoryThumbnail`
- [x] B6: `EventCardMockup`（設計稿本機預覽用，已加 .gitignore）

## Phase C: 頁面套用

- [x] C1: 首頁 hero（MascotAvatar + 4-line headline + LINE CTA `#06C755`）
- [x] C2: 公告 strip（金色漸層卡 + procedural pattern）
- [x] C3: 活動列表 row（64px 日期欄 + 絕對 SaveButton + hover lift）
- [x] C4: 活動詳情頁（font-display 標題、forest 連結、matcha hover）
- [x] C5: 公告列表頁（移除 tab strip）
- [x] C6: 來源頁、關於頁（連結色繼承 base 樣式）
- [x] C7: Navbar（icon button matcha hover + 蠟蘋果 logo）
- [x] C8: SaveButton compact 模式（32×32 心形）

## Phase D: 容量與部署修復

- [x] D1: 修復 OG image Edge function 14.62MB 爆量（barrel import → 直接 import tokens）
- [x] D2: `pnpm build` TS check 通過
- [x] D3: Vercel 部署綠燈（commit `f587022` 後驗證）

## Phase E: 規範化與後續（待辦）

- [ ] E1: 把本 spec 同步進 `docs/architecture/system-map.json`（加 designer agent + design 函式庫節點）
- [ ] E2: 在 `.github/instructions/web.instructions.md` 補一條規約：**OG / Edge function 路由禁止從 `@/lib/design` barrel import**（避免再次撐爆）
- [ ] E3: dark mode 平價驗證（每個新 component 切到 `.dark` 截圖一次，補 `:root.dark` token 覆寫缺漏）
- [ ] E4: 寫 designer history 條目（事故 + 修復、設計決策依據）
- [ ] E5: 後續 Recraft API 圖文管線開新 spec（hero 圖、OG 卡共用 token）

## Verification

- [x] `pnpm build` 通過（TS strict + Turbopack production）
- [x] Vercel 部署 status = success（`f587022` 之後）
- [ ] 三語（zh/en/ja）視覺切換無破版
- [ ] dark mode 對所有改動頁面確認過
- [ ] LINE 廣播圖文（如沿用 OG token）後續驗證
