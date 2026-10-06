---
slug: intent-homepage
title: 意圖首頁 — 首頁改為意圖入口，全部活動移到「レーダーを見る」（TTR 2.0 P0）
status: proposed
branch: feat/intent-homepage
created: 2026-10-06
tags: [web, ux, homepage, i18n, ab-test, seo, ttr-2.0, p0]
---

## What（做什麼）

把 `/[locale]` 首頁從「資料庫全部活動列表」改成「這位使用者現在想往台灣靠近哪一步」的**意圖入口頁**，並把既有的全部活動列表、搜尋與進階篩選完整搬到新路由 **「レーダーを見る」`/[locale]/radar`**。對應需求 R-HP-1〜5：

| ID | 本 spec 的交付 |
|---|---|
| R-HP-1 | 新首頁 IA（意圖入口＋今週の台湾＋次領域チャンネル＋CTA）；全部活動列表移到 `/[locale]/radar`，舊 URL 轉址保留 |
| R-HP-2 | 意圖入口點一下 → 直接進入 `/[locale]/radar?intent=<id>&when=week`（1 次轉場就看到結果） |
| R-HP-3 | 入口版型（三選一 vs. 四意圖）與主標文案（A／B／C）的實驗機制、量測與判定規則，並附「流量不足」的替代方案 |
| R-HP-4 | 地區切換：上次選擇 > IP 推定都道府縣 > 全国；不跳瀏覽器定位權限視窗 |
| R-HP-5 | 首頁、About 的來源數改從 `sources` 表動態計算，移除寫死的「100+」 |

本 spec 只做首頁與列表路由的 UI／IA／實驗機制。Taiwan relevance scoring、Person／Topic 實體、社交門檻標籤、Community directory 都是其他 spec；本 spec 只定義**介面契約與 fallback**（見 §Dependencies）。

## Why（為什麼）

- 需求文件 §4.2 Q1：首頁就是 database view，新用戶不知道從哪裡開始；§0 決策 1「從資料中心轉為人中心」。
- §11 **D2（已定案）**：核心族群是「台湾に少し踏み込みたい日本語話者」，已入坑者是切入點與留存對象，首頁要同時容納兩者。意圖入口服務前者，「レーダーを見る」與次領域チャンネル服務後者。
- §11 **D4（已定案）**：主標文案 A／B／C 與入口數（三選一 vs. 四意圖）都用原型 A/B 測試決定，量測首次點擊率與 LINE 訂閱轉換（§9 Phase 1、§10「發現」指標）。
- §4.1／§14：首頁寫「100+」，實際約 163 個以上，數字過時並造成信任落差（R-HP-5）。
- 附帶效益：目前首頁一次撈出**全部** active events（`web/app/[locale]/page.tsx` 無 limit 的 `select`），再交給 client 端篩選。新首頁只需要少量查詢，首頁 payload 與 TTFB 都會下降；完整 payload 只留在 `/radar`。

## Non-Goals（不做什麼）

- **不設計** relevance score 的演算法、門檻與 ground truth（→ `taiwan-relevance-scoring`）。
- **不設計** Person／Topic／follow 的資料模型與頁面（→ `person-topic-entities`）；本 spec 的 Person 區塊與 follow 按鈕在對方上線前一律**隱藏**。
- **不實作**交流強度、日本語OK、一人OK 等社交門檻標籤（→ `social-affordance-tags`）。本 spec 的「観る／学ぶ／話す」先用既有 `category`／`event_form` 做**暫代映射**，並在 UI 上不宣稱這是「交流強度標籤」。
- **不做** Community directory（P1）、Collection（P2）、「台湾に行く前に」策展頁內容（P1，§6.9）；首頁只預留區塊位置，資料不存在就不渲染。
- **不做** LINE 分眾通知（→ `line-segmented-digest`）。首頁 LINE CTA 維持現有單一好友連結。
- **不重做** `/radar` 的列表、`FilterBar`、`EventListClient`、`EventShelf` 的視覺；只搬遷路由並加 `intent`／`when` 兩個參數。
- **不改** `events` 表 schema；**不新增** picks 專用表（「今週の台湾」重用既有週報公告）。唯一的新 DB 物件是實驗事件表（Phase A）。
- **不引入**第三方 A/B 測試 SaaS、cookie banner 套件、geolocation 權限視窗或 framer-motion。
- **不做**品牌 meta／OG 改寫（§9 Phase 3 文案定案後另案），本 spec 只換首頁 H1 區。
- **不刪除**任何既有 i18n key（含目前已無呼叫端的 `home.introP1〜3`）；清理需另開有意識的 commit。

## 現況盤點（2026-10-06，實際檔案）

| 項目 | 現況 | 路徑 |
|---|---|---|
| 首頁 route | Server Component，`revalidate = 600`；一次撈全部 active events（`annotation_status in (annotated, reviewed)`），渲染 Lianbu hero、公告列、`FilterBar`、`EventShelf`、`EventListClient`；輸出前 20 筆 `ItemList` JSON-LD | `web/app/[locale]/page.tsx`（223 行） |
| 根路徑 | `/` → `redirect("/ja")` | `web/app/page.tsx` |
| 列表／篩選 | URL-state 驅動：`q, category, from, to, paid, timeMode(active/all/past), location, city, sort`；共用 predicate `filterEvents()`；`EventFilterProvider` 以 `router.replace` 同步 URL | `web/lib/eventFilter.ts`、`web/components/EventFilterContext.tsx`、`web/components/FilterBar.tsx`（515 行）、`web/components/EventListClient.tsx`、`web/components/EventShelf.tsx`、`web/components/ListScrollManager.tsx` |
| 「本週／週末」篩選 | **不存在**。`timeMode` 只有 active／all／past | `web/lib/eventFilter.ts` |
| 地區 | `LOCATION_KEYS = tokyo, kanto, tohoku, chubu, chugoku, online, overseas`（關西併在 `chubu`「中部・近畿」）；`REGIONS_WITH_CITY` 有都道府縣子篩選 | `web/lib/locationMarkers.ts`、`web/lib/regionPrefectures.ts` |
| 「回到列表」 | 寫死 `href={`/${locale}`}` | `web/components/BackToListButton.tsx`；Navbar logo／連結 `web/components/Navbar.tsx:191,219,372` |
| `/saved` | 已存在（`SavedListClient`）；與首頁改版無直接衝突 | `web/app/[locale]/saved/page.tsx` |
| 分類／城市落地頁 | 已存在，可作次領域チャンネル的 P0 落地頁 | `web/app/[locale]/categories/[category]/page.tsx`、`web/app/[locale]/cities/[city]/page.tsx` |
| Category | 40 個 `Category` 與 5 個 `CATEGORY_GROUPS`；`EVENT_FORMS` 16 值（含 `networking`、`tasting`、`publication`、`broadcast`） | `web/lib/types.ts:186-382` |
| 寫死「100+」 | `home.statHero`（首頁 hero 正在使用）、`home.introP2`（無呼叫端）、`about.sourcesBody`（About 使用）三語皆有；`/design` 預覽頁有寫死三語字串 | `web/messages/{ja,zh,en}.json:982,986,1109`；`web/app/[locale]/design/page.tsx:122-126` |
| 動態來源數的既有做法 | `/sources` 已從 `sources` 表（`is_active = true`，anon 可讀）計算 `total` | `web/app/[locale]/sources/page.tsx:71-109`；`supabase/migrations/060_sources_registry.sql` |
| LINE 週報入口 | 首頁 hero 內寫死 `https://line.me/R/ti/p/@769qbdkq` 按鈕（LINE 綠 `#06C755`）；webhook 收 follow／unfollow 寫入 `line_subscribers`（`subscribed_at`，**沒有任何來源歸因欄位**） | `web/app/[locale]/page.tsx`；`web/app/api/line-webhook/route.ts:252-268`；`supabase/migrations/022_line_subscribers.sql` |
| 週報選題 | `scraper/weekly_line_broadcast.py --generate-draft`：GPT 選題 → 存成 `announcements.type='weekly_broadcast'` 草稿（`published_at = NULL`），並寫入 `announcement_events`；管理員可在 `/admin/announcements/[id]` 編輯連結活動；送出後才有 `published_at` | `scraper/weekly_line_broadcast.py:136-168,703-768`；`supabase/migrations/030_announcements.sql`、`043_weekly_broadcast.sql`；`web/app/api/announcements/[id]/route.ts` |
| Analytics | `@vercel/analytics`（`<Analytics />`，cookieless 頁面瀏覽）與 Speed Insights；**沒有任何 `track()` 自訂事件**；自建 `event_views`（活動詳情頁瀏覽，anon insert-only，含國家／地區／流量來源，排除 admin）與 `/admin/analytics`。**首頁點擊、LINE CTA 點擊目前完全沒有量測** | `web/app/[locale]/layout.tsx:12-13,148`；`web/app/actions/record-view.ts`；`web/components/ViewTracker.tsx`；`supabase/migrations/016_event_views.sql` |
| Bot 偵測 | `proxy.ts` 已有 `BOT_PATTERNS`（AI 爬蟲與搜尋引擎） | `web/proxy.ts` |
| 全域設定 | `app_settings`（key-value，**僅 admin 可讀**，anon 不可讀） | `supabase/migrations/043_weekly_broadcast.sql` |
| Design system | `web/lib/design/`（`Badge`、`DateChip`、`FilterChip`、`MascotAvatar`、`FloatingShapes`、`CategoryThumbnail`、tokens）；`web/components/UiControls.tsx`（`PillButton`、`RadioGroup`、`ToggleSwitch`、`IconButton`、`StatusBadge`）；`web/components/Button.tsx`；`web/components/DesignSelect.tsx`；`CARD_LINK`／`CARD_LINK_ARROW`（`web/lib/classNames.ts`） | 同左 |

**治理漂移（順手記錄，不在本 spec 修）**：
1. `.github/instructions/web.instructions.md` 仍寫 Next.js 16.2.4（實際 `web/package.json` 為 16.3.6）、Categories 只列 18 個（實際 40 個）、`page.tsx` 為「Event listing (homepage)」。本 spec 上線後必須更新目錄結構段（見 tasks Phase E）。
2. Architect SKILL「Homepage Inline Card Divergence Guard」宣稱首頁用 inline list 而非共用元件；現況首頁已改用 `EventListClient`。建議交給 History Teller 標註 superseded。

## Design（設計摘要）

### D-1 新首頁 IA 與 P0 可上狀態

依 §6.4 草圖，逐區塊標示 P0 狀態。**原則：資料不存在的區塊不渲染、不放「即將推出」空殼**（個人專案沒有餘力維護假區塊，空殼也會傷信任）。

| # | 區塊 | P0 狀態 | 資料來源／依賴 | 不可用時 |
|---|---|---|---|---|
| 1 | Hero：主標＋副標（§5.3 A／B／C）＋佐證句（動態來源數） | ✅ P0 | i18n＋`sources` count | 文案依實驗變體；count 查詢失敗時隱藏數字、保留句子 |
| 2 | 「今、台湾とどうつながりたい？」意圖入口（四意圖 **或** 三選一，依變體） | ✅ P0 | `web/lib/homepage/intents.ts`（純函式＋設定表） | — |
| 2a | 篩選列：観る／学ぶ／話す ・ 地域 ・ 今週末 | ✅ P0（觀學話為**暫代映射**） | 同上＋D-5 地區 | — |
| 3 | 「あなたの今週の台湾」5–8 筆 | ✅ P0（上線閘門：relevance 回填完成） | D-4：最新已發布週報公告的連結活動，限 `feed_tier='home'` | 自動補位；仍 < 3 筆則整區隱藏 |
| 3a | 每筆的 metadata：次領域、費用、地點、日期 | ✅ P0 | `category`、`is_paid`／`price_amount`、`location_*` | — |
| 3b | 每筆的 交流強度、日本語OK | ⛔ 隱藏 | `social-affordance-tags` | 不顯示，不推測（§6.3「必須有原文依據」） |
| 4 | 次領域チャンネル（音楽／映画／原住民／ことば／茶と食／文学／学術／親子） | 🟡 P0 降級版：連到 `/radar?channel=<slug>` | P0 用本地常數映射到 Category；Topic 實體上線後改讀 `person-topic-entities` | follow 按鈕隱藏；區塊下方只放一個 LINE CTA |
| 5 | いま日本で活動する台湾の人（Person） | ⛔ 隱藏 | `person-topic-entities` | 不渲染 |
| 6 | 台湾好きのコミュニティ（Community） | ⛔ 隱藏 | `community-directory`（P1） | 不渲染 |
| 7 | 季節の台湾フェス | 🟡 Phase C 選做 | 未來 12 個月內、由大型祭典來源產生的活動（見 D-4b） | 0 筆就不渲染 |
| 8 | みんなの台湾リスト（Collection） | ⛔ 隱藏 | `place-and-collections`（P2） | 不渲染 |
| 9 | 主催者投稿 CTA「ポスター1枚で掲載」 | ✅ P0 | 既有 `AccountPortalButton`／`/account/events/new` | 投稿重建未完成時連到現有入口 |
| 10 | LINE で毎週受け取る | ✅ P0（加量測） | 現有好友連結 | — |
| 11 | [レーダーを見る] | ✅ P0 | `/[locale]/radar` | — |
| 12 | 頁尾：About、AI 標註說明、錯誤回報、編輯方針 | 🟡 P0 連到 `/about` 既有段落 | §6.11 頁面另案 | 連結指向 About 錨點 |

既有元素的去留：
- **公告列**（`AnnouncementCard`）：移到「今週の台湾」下方並限 3 筆；若與 D-4 選題同源的週報公告重複，排除 `type='weekly_broadcast'`。
- **Lianbu 吉祥物 hero**：保留 `MascotAvatar` 但縮小（例如 160px），把視覺重心讓給主標與意圖入口；`FloatingShapes` 保留。
- **`EventShelf`（長期・常設）**：從首頁移除，只留在 `/radar`。

### D-2 「レーダーを見る」路由與 SEO／舊 URL

- 新增 `web/app/[locale]/radar/page.tsx`：內容 = 目前 `web/app/[locale]/page.tsx` 的資料抓取、`FilterBar`、`EventShelf`、`EventListClient`、`ItemList` JSON-LD，**原樣搬遷**，加上 `generateMetadata`（三語 site name、`alternates.languages` 含 `x-default`、canonical `/{locale}/radar` 不帶 query）。
- **舊 URL 轉址**：凡 `/{locale}?<任何篩選參數>`（`q|category|from|to|paid|timeMode|location|city|sort`）一律 **308** 轉到 `/{locale}/radar?<同參數>`。在 `web/proxy.ts` 處理（在 i18n middleware 之前，避免先渲染首頁）。無參數的 `/{locale}` 才是新首頁。轉址邏輯抽成純函式 `web/lib/homepage/legacyRedirect.ts` 以便單元測試。實作前 Engineer 必須讀 `web/node_modules/next/dist/docs/` 確認 Next 16 `proxy.ts` 的 redirect 語意。
- **內部連結**：`BackToListButton` → `/{locale}/radar`；Navbar 新增「レーダーを見る」項目（logo 仍回首頁）；`ListScrollManager` 以 URL 為 key，搬到 `/radar` 後行為不變。
- **sitemap**：`web/app/sitemap.ts` 新增 `/{locale}/radar`（priority 0.9）；首頁維持 1.0。
- **JSON-LD**：`ItemList`（全部活動前 20 筆）搬到 `/radar`；首頁改輸出「今週の台湾」的 `ItemList`（5–8 筆）。必須經 `serializeJsonLd` 並通過 `npm run test:security:jsonld`。
- 搜尋流量風險：目前 `/ja` 承接「台湾 イベント」類查詢且有大量活動連結；改版後首頁仍有 5–8 筆活動連結＋到 `/radar` 的顯眼連結，內部連結結構保留。上線後以 GSC（既有 `web/lib/gsc.ts`）觀察 4 週曝光／點擊（見 Risks R4）。

### D-3 意圖入口 → 篩選條件（≤ 1 次轉場）

**機制**：新增 URL 參數 `intent`、`mode`、`channel`、`when`，由 `filterEvents()` 解讀；意圖點擊 = 一個 `<Link>` 直接到 `/{locale}/radar?intent=<id>&when=week[&location=<region>]`。不在首頁內做第二層選單，因此「點擊 → 看到結果」恰好 1 次轉場（R-HP-2）。

- `web/lib/homepage/intents.ts`：純資料＋純函式，**唯一**映射來源（首頁、`/radar`、`FilterBar` chip 共用），單元測試覆蓋。
  ```ts
  type IntentId = "deepdive" | "connect" | "meet" | "before_trip";  // 四意圖（id 不可與 ModeId 重名）
  type ModeId   = "watch" | "learn" | "talk";                     // 観る／学ぶ／話す（三選一版的入口，也是四意圖版的篩選列）
  type ChannelSlug = "music" | "film" | "indigenous" | "language" | "tea-food" | "literature" | "academic" | "family"; // 與 person-topic-entities §2.2 slug 一致
  interface IntentRule { categories: Category[]; eventForms?: EventForm[]; excludeCategories?: Category[] }
  export function matchesIntent(e: Pick<Event,"category"|"event_form">, id: IntentId | ModeId | ChannelSlug): boolean
  ```
- `when` 新值：`week`（今天起 7 天內有舉辦日，含跨期長期展）與 `weekend`（本週六日，JST）。判定為「活動期間 [start_date, end_date ?? start_date] 與目標區間有交集」。日期一律以 JST 計算（`Asia/Tokyo`），不得用 `toISOString().slice(0,10)`（UTC）——現有 `filterEvents` 的 `today` 就是 UTC，`when` 不沿用。
- `/radar` 收到 `intent`／`mode`／`channel` 時，以 `FilterChip` 顯示為可移除的 chip，並在列表上方顯示該意圖的一句說明（i18n）。
- `intent`／`mode`／`channel` 的結果**只取 `feed_tier='home'`**（D-6），因為使用者是從首頁進入；`/radar` 直接進入（無意圖參數）時使用 radar predicate。

**P0 暫代映射表**（只用既有 `Category`／`EventForm`；social-affordance-tags 上線後，`talk`／`watch`／`learn` 改讀交流強度標籤，映射表只保留作 fallback）：

| 入口 | 包含 Category | 加入 EventForm | 排除 |
|---|---|---|---|
| 好きな台湾を深掘り `deepdive` | movie, documentary, drama, performing_arts, literature, books_media, indigenous, folklore, art, photography, design_craft, history, tea_alcohol | — | 共通排除 |
| 台湾の人と話す `connect` | taiwan_mandarin, taiwan_japan | networking, workshop, tasting | 共通排除 |
| 日本で台湾に会う `meet` | lifestyle_food, market, senses, tea_alcohol, herbal, retail, performing_arts | market, tasting, performance | 共通排除 |
| 台湾に行く前に `before_trip` | tourism, study_abroad, scholarship, taiwan_mandarin, lifestyle_food | tour | 共通排除 |
| 観る `watch` | movie, documentary, drama, performing_arts, art, photography, exhibition, design_craft | screening, screening_with_talk, exhibition, performance | 共通排除 |
| 学ぶ `learn` | lecture, academic, workshop, literature, history, taiwan_mandarin, folklore | lecture, workshop, conference | 共通排除 |
| 話す `talk` | taiwan_japan, taiwan_mandarin | networking, tasting | 共通排除 |
| **共通排除** | `geopolitics`、`business`、`report`、`tv_program`、`radio_program`；EventForm `publication`、`broadcast` | | R-QA-3／R-QA-4：首頁只出「可以參加的活動」，政治時事不進一般推薦 |

次領域チャンネル映射（**逐字採用** `person-topic-entities` proposal §2.2 的種子映射，P0 作為本地常數，Topic 上線後改讀 `topic_categories`）：music→performing_arts（標籤暫用「音楽・舞台」，見對方 Q1）；film→movie, documentary；indigenous→indigenous；language→taiwan_mandarin；tea-food→tea_alcohol, lifestyle_food, herbal；literature→literature, books_media；academic→academic；family→parenting。

> 這張表是**假設**，不是事實：Phase C 實作前必須以 live 資料量化每個入口在 `when=week` 下的平均筆數與抽樣 precision（見 tasks C-1）。任何入口在全国範圍平均 < 3 筆，就要調整映射或在該入口顯示「今月」fallback，避免使用者一點進去就是空列表。

### D-4 「あなたの今週の台湾」人工挑選機制

**決策：重用既有 LINE 週報的選題，不新增 picks 表。**

- 來源：最新一則 `announcements.type='weekly_broadcast'` 且 `published_at <= now()` 的公告，透過 `announcement_events` 取得連結活動（anon RLS 已允許讀已發布公告的連結）。
- 「AI 輔助」= 既有 `weekly_line_broadcast.py --generate-draft` 的 GPT 選題；「人工挑選」= 管理員在 `/admin/announcements/[id]` 增刪連結活動後送出。**首頁與 LINE 週報同一份編輯判斷**，管理員每週只做一次，也讓首頁自然成為 LINE 訂閱的預覽。
- 取用規則（`web/lib/homepage/picks.ts`，純函式＋單元測試）：
  1. 過濾：`is_active`、未結束（JST）、`feed_tier='home'`（D-6）。
  2. 排序：本週有舉辦日的優先，其次 start_date 升冪。
  3. 取 5–8 筆；不足 5 筆時，用「本週、首頁層級可見、依 start_date 升冪」的活動自動補位（補位項不加任何「編輯推薦」字樣）。
  4. 補位後仍 < 3 筆 → 整區隱藏。
- 對方 spec 規劃讓 LINE 週報也只取 `home`，因此選題與首頁可見性天然一致。
- 如果週報當週未發布（`auto_publish` 關閉且未手動送出），自動退回上一則已發布週報（扣掉已結束活動）。
- `announcement_events` **沒有排序欄位**；若創辦人要指定首頁順序，需另加欄位（列為未決問題 Q3，P0 不做）。
- 替代方案（**不採用**）：新增 `homepage_picks` 表＋admin UI。理由：新 schema＋新 admin 頁，違反 Admin UI Dashboard Necessity Check 的低成本優先；且會讓管理員每週維護兩份清單。

#### D-4b 季節の台湾フェス（Phase C 選做）

需求：大型祭典的全年時程。P0 不新增欄位，以「來源屬於大型祭典 scraper」判定（`taiwan_matsuri`、`taiwan_festival_tokyo`、`taiwan_faasai`、`taiwanbunkasai`、`taiwan_expo_japan` 等，實作時以 `sources` 表與 `scraper/main.py` 的 `SCRAPERS` 實際 id 核對），取未來 12 個月、依 start_date 升冪、每個來源只取最近一場。這是 source allowlist 判定，屬已知妥協；若 `taiwan-relevance-scoring` 的 `content_type` 或 `social-affordance-tags` 的「商業祭典」主辦方類型上線，改用該欄位。

### D-5 地區切換（R-HP-4）

- 地區值沿用既有 `LocationKey`（不新增地區分類）；選項＝全国＋`tokyo, kanto, tohoku, chubu, chugoku`（`online` 作為額外選項，`overseas` 首頁不顯示）。
- **預設優先序**：(1) 使用者上次選擇（first-party cookie `ttr_region`，365 天）→ (2) IP 推定：`proxy.ts` 在首頁請求時讀 Vercel 的 `x-vercel-ip-country-region`（`record-view.ts` 已使用同一 header），國家為 JP 時對應到 `LocationKey`，寫入 cookie `ttr_region_guess`（session）→ (3) 全国。
- **不使用** `navigator.geolocation`（會跳權限視窗、手機上嚴重干擾首次體驗）。
- 首頁是 ISR 快取頁，地區在 client 端套用：地區選擇器（`DesignSelect`）改變後，(a) 改寫所有意圖入口 `<Link>` 的 `location` 參數，(b) 在「今週の台湾」中把同地區活動排前並顯示地區 `Badge`，**不**過濾掉其他地區（5–8 筆很容易被過濾到 0）。
- 已知限制：`chubu` 是「中部・近畿」，大阪使用者看到的是中部・近畿；拆分關西屬於地區分類變更，不在本 spec（未決問題 Q6）。

### D-6 與 `taiwan-relevance-scoring` 的介面（依對方 I-1 契約）

`docs/specs/active/taiwan-relevance-scoring/proposal.md` §Interfaces I-1 已定義查詢契約，本 spec **照單採用，不自訂門檻**：

| 項目 | 對方提供（owner） | 本 spec 的用法 |
|---|---|---|
| 欄位 | `events.feed_tier ∈ {home, radar, queue, NULL}`、`content_type`、`relevance_score` | 只讀 `feed_tier`；**不得**在 web 端用 `relevance_score` 自訂門檻 |
| 首頁 predicate | `applyHomeFeed(q)`（`web/lib/relevance.ts`）＝ `feed_tier='home'`（已保證 content_type=`event`、非政治、分數 ≥ T_HOME） | 今週の台湾（含補位）、季節フェス、意圖／模式／チャンネル結果，全部在此集合**之內**篩選 |
| レーダー predicate | `applyRadarFeed(q)` ＝ `feed_tier IS NULL OR feed_tier IN ('home','radar')` | `/radar` 無意圖參數時使用 |
| NULL 語意 | NULL＝radar，**不上首頁** | 首頁不得把 NULL 當 home |
| 前置條件 | 對方 Phase 2 回填完成，active parent 的 `feed_tier IS NULL` = 0 | **新首頁切換上線（Phase C-12 的 production 部署）的閘門** |

本 spec 的實作方式：

```ts
// web/lib/homepage/eligibility.ts —— 只是薄包裝，邏輯在對方的 web/lib/relevance.ts
export const HOMEPAGE_SELECT_FIELDS = "id, name_ja, name_zh, name_en, category, event_form, start_date, end_date, is_paid, price_amount, location_name, location_prefectures, image_url, feed_tier" as const;
export function homeQuery(q) { return applyHomeFeed(q).eq("is_active", true).in("annotation_status", ["annotated","reviewed"]).is("parent_event_id", null); }
```

- 意圖結果在 `/radar` 是 client-side 篩選（全量 payload），因此 `/radar` 的 payload 必須帶 `feed_tier`，`filterEvents()` 在有 `intent`／`mode`／`channel` 參數時只保留 `feed_tier === 'home'`（與 `applyHomeFeed` 同義的 TS predicate，請對方在 `web/lib/relevance.ts` 一併匯出 `isHomeFeed(e)` 以免兩套定義）。
- D-3 的「共通排除」是**意圖層**規則（例：入口不出 `report`、`tv_program`），不是 eligibility 的替代品；契約生效後仍保留，屬冗餘但無害。
- **欄位尚未存在時**（對方 migration 097 未套用）：`.select()` 不得引用 `feed_tier`（PostgREST 會報錯）。Phase C 在此期間只能在 preview（`?hp_preview=`）與本機開發，不得把 `/` 切換成新首頁。
- **待協商（Q9）**：人工挑選的「今週の台湾」是否可視為編輯覆寫，允許 `feed_tier IN ('home','radar')`？依現行契約答案是否，本 spec 預設遵守（只取 `home`）；若創辦人希望編輯判斷可覆寫，應由對方 spec 以 FC 鎖把該活動升為 `home`，而不是首頁端放寬。
- **檔案衝突**：對方 surface matrix 會修改現行 `web/app/[locale]/page.tsx`（套用 radar predicate），本 spec Phase B 會把這段搬到 `web/app/[locale]/radar/page.tsx`。先合併者為準，後者 rebase 時把 predicate 套到新位置；V-M-D 前以 `grep -n "applyRadarFeed" web/app/[locale]/radar/page.tsx` 確認沒有遺失。

### D-7 與 `person-topic-entities` 的介面（依對方 §5.2）

`docs/specs/active/person-topic-entities/proposal.md` §5.2 已承諾以下 server-only helpers（`web/lib/topics.ts`、`web/lib/people.ts`），本 spec 只消費、不設計其內容：

| 首頁需求 | 對方 helper | 本 spec fallback（對方未上線時） |
|---|---|---|
| 次領域チャンネル清單＋近期件數 | `getTopicChannels(locale)` → `{ slug, name, upcomingCount }[]` | `web/lib/homepage/intents.ts` 的 `CHANNELS` 常數（slug 與對方 §2.2 相同），件數由 `/radar` client 篩選計算或不顯示 |
| チャンネル落地頁 | `/[locale]/topics/<slug>` | `/[locale]/radar?channel=<slug>` |
| チャンネル follow | follow Topic server action；`getFollowedTopicSlugs(userId)` | 不顯示 follow 按鈕；區塊只放 LINE CTA |
| Person 區塊 | `getFeaturedPeople({ limit, withinDays: 30 })` | 不渲染；回傳 < 4 人也不渲染 |
| 今週の台湾個人化（未來） | `getFollowedTopicSlugs(userId)` | 不做個人化（P0 全體同一份） |

- **可見性契約**：對方 helper 回傳的活動（`getTopicUpcomingEvents`、`nextEvent`）若顯示在**首頁**，必須同樣只含 `feed_tier='home'`（D-6）。對方 §5.1 寫明 gate 欄位由 relevance spec 決定；本 spec 請求對方 helper 接受 `feed: 'home' | 'radar'` 參數，首頁一律傳 `'home'`（R-QA-4：follow 後的 Topic 頁才用 radar）。此請求列為跨 spec 協調事項（tasks F-2）。
- 首頁以 feature flag 常數（`web/lib/homepage/flags.ts`：`SHOW_PERSON_SECTION`、`SHOW_TOPIC_FOLLOW`、`SHOW_COMMUNITY_SECTION`）控制；預設全部 `false`，對方上線後開啟。
- slug 一旦發布不可變（對方 schema CHECK 與「發布後不可變」規則），因此 `/radar?channel=<slug>` 的舊連結在 Topic 頁上線後應 308 到 `/topics/<slug>`（tasks F-2）。

### D-8 A/B 測試機制（R-HP-3）

#### 變體

- 版型 L：`L3`（三選一：観る／学ぶ／話す 為入口）與 `L4`（四意圖入口＋観る／学ぶ／話す 篩選列；§1.4 預設方案）。
- 文案 C：`A`／`B`／`C`（§5.3）。
- 全因子 = 6 格。**不建議**直接跑 6 格（見下方樣本量）。

#### 指派與渲染

- **只在 `ja` locale 跑實驗**（核心族群是日本語話者，§5.3 三案也只有日文）。`zh`／`en` 永遠顯示預設變體（`L4` + 預設文案，見 Q1），並各自翻譯。
- `web/proxy.ts`：對 `/ja`（無篩選參數）請求，若無 cookie `ttr_hp_exp`，依權重隨機指派並寫入 first-party cookie（值例：`e1.L4.A`，含實驗 id，90 天）；然後 **rewrite** 到內部路由 `/ja/_hp/<variant>`（`web/app/[locale]/_hp/[variant]/page.tsx`，`generateStaticParams` 列出所有變體，各自 ISR 快取）。rewrite 不改變網址列，canonical 仍為 `/ja`。
  - 不用「同一頁 client 端換文案」：會造成首屏閃爍與 CLS，也讓 ISR 無效。
  - 實作前必須查 Next 16 文件確認 proxy rewrite 與 ISR 的組合，以及 `_` 開頭的 private folder 規則（`_hp` 會被當成 private folder 不產生路由——若是，改用不衝突的名稱，例：`hpv`）。
- **Bot 與預覽**：`BOT_PATTERNS` 命中的請求不指派、不記錄，固定看預設變體（搜尋引擎永遠看到同一版，避免 cloaking 疑慮）。`?hp_preview=L3.B` 強制顯示指定變體、不記錄事件、輸出 `noindex`，供訪談與 QA 使用。
- **Kill switch**：環境變數 `HOMEPAGE_EXPERIMENT`（`off` 時全部顯示預設變體且不寫 cookie），權重與實驗 id 寫在 `web/lib/experiments/homepage.ts` 常數。不放 `app_settings`（anon 不可讀，proxy 每次查 DB 也太貴）。

#### 量測

截至 2026-10-06，現有工具**無法**量測首頁點擊（`@vercel/analytics` 未用 `track()`；自訂事件是否在目前 Vercel 方案可用，需創辦人確認，見 Q4）。因此採**自建、最小化**事件表，沿用 `event_views` 的模式（anon insert-only、admin 才能讀）：

```sql
-- supabase/migrations/<next>_homepage_experiment_events.sql（編號實作時以 ls 確認，目前最後是 096）
create table public.homepage_experiment_events (
  id          bigint generated always as identity primary key,
  experiment  text not null,            -- 'e1'
  variant     text not null,            -- 'L4.A'
  visitor_id  uuid not null,            -- cookie 內的隨機 uuid，不含任何個資
  event_type  text not null check (event_type in ('view','intent_click','mode_click','channel_click','pick_click','radar_click','line_cta_click','submit_cta_click')),
  target      text,                     -- intent/mode/channel id 或 event id
  is_first_view boolean not null default false,
  locale      text not null,
  created_at  timestamptz not null default now()
);
-- RLS：anon insert-only（with check 限制 event_type 與長度）；select 僅 admin；GRANT 依 069_explicit_grants 慣例
```

- 寫入走 server action（同 `record-view.ts`：排除 admin、排除 dev 環境、吞掉錯誤），**不**存 IP、UA、referer、國家。
- `view` 在首頁 client mount 時送一次；點擊事件用 `navigator.sendBeacon` 或 server action 的 fire-and-forget，**不得**阻擋導覽。
- **指標定義**：
  - 主要指標「首次點擊率」= 首次造訪（`is_first_view`）的 visitor 中，同一 visitor 在 30 分鐘內送出任一 `intent_click | mode_click` 的比例。
  - 次要：任何有意義點擊率（含 pick／channel／radar）、`radar_click` 比例（§10「レーダーを見る」使用比例）、`line_cta_click` 率。
  - **LINE 訂閱轉換**：LINE 好友加入發生在 LINE App 內，webhook 的 follow 事件**無法**連回網站 visitor 或變體（`line_subscribers` 沒有歸因欄位，LINE 也不回傳 referrer）。因此：(a) 以 `line_cta_click` 率作為代理指標；(b) 若 LINE 公式アカウント管理畫面的「友だち追加経路」可為每個變體建立不同的追加 URL，則各變體使用不同 URL，在 LINE 後台比對新增好友數（需創辦人確認帳號方案是否支援，Q5）。不在 webhook 端做任何身份比對。
- 報表：P0 **不做** admin dashboard（Admin UI Dashboard Necessity Check）。提供一支唯讀 SQL／腳本 `scripts/homepage_experiment_report.py`（或 SQL 檔）輸出各變體 n、轉換數、比率與 Bayesian 後驗機率，創辦人每週跑一次或併入既有 `weekly_report.py` 的 LINE 推播。

#### 隱私

- 只有 first-party cookie（`ttr_hp_exp`、`ttr_vid`、`ttr_region`、`ttr_region_guess`），值都是隨機 id 或地區代碼；無第三方 cookie、無跨站追蹤、不與 `auth.users` 關聯。
- 在 `/about` 新增「アクセス解析について」段落（三語）：說明 Vercel Analytics、首頁改善實驗的 cookie、IP 推定地區只用於預設地區且不儲存、資料保存期間。日本電気通信事業法「外部送信規律」對本站是否適用、表述是否足夠，**需創辦人自行確認**（本 spec 不構成法律意見）。
- 保存期間：實驗結束後 90 天刪除原始事件，只保留匯總結果（tasks Phase E）。

#### 統計判定與「流量可能不足」的現實

以雙尾 α=0.05、檢定力 0.8 估算每格所需「首次造訪」人數：

| 情境 | 基準率 → 目標率 | 每格約需 | 2 格 | 6 格 |
|---|---|---|---|---|
| 首次點擊率，偵測 +5pt | 30% → 35% | ≈ 1,400 | ≈ 2,800 | ≈ 8,200 |
| 首次點擊率，偵測 +10pt | 30% → 40% | ≈ 360 | ≈ 720 | ≈ 2,200 |
| LINE CTA 點擊，偵測倍增 | 1% → 2% | ≈ 2,300 | ≈ 4,600 | ≈ 13,800 |

（基準率為假設值，Phase A 的 baseline 量測會取代它。）**LINE 實際好友轉換的量級更小，個人專案在合理期間內幾乎不可能得到統計顯著結果。**

因此採以下設計：

1. **不跑 6 格全因子，改成兩階段序列測試**：
   - 實驗 e1：版型 `L3` vs `L4`（文案固定為預設），主要指標＝首次點擊率。
   - 實驗 e2：文案 `A`／`B`／`C`（版型固定為 e1 勝者），主要指標＝首次點擊率，次要 LINE CTA 點擊。
2. **事前登錄的判定規則（Bayesian，Beta(1,1) 先驗）**：
   - 每週計算 `P(變體 > 對照)`。≥ 0.95 → 採用該變體；所有變體互相 ≤ 0.80 且已達上限期間 → **平手，採用預設方案**（e1 預設 `L4`，對應 §1.4；e2 預設見 Q1）。
   - 每個實驗最短 2 週（涵蓋週末）、最長 6 週；不提前偷看決策。
3. **流量閘門**（Phase A 結束時判定）：以 baseline 的「每週首次造訪 ja 人數」推算 e1 達到 +10pt 偵測所需週數。
   - ≤ 6 週：照上述執行。
   - > 6 週：**改走質性替代方案**，live 實驗降級為「方向性證據」不做統計判定：
     - (a) Phase 1 的 8–10 人訪談中，以 `?hp_preview=` 對每位受訪者做**第一次點擊測試**（first-click test）與 5 秒測試，交替呈現順序；
     - (b) 文案三案改用低成本外部測試：同一張活動圖卡搭配三種主標，分別在 X／Instagram 發布，比較互動率（§9 Phase 3 本來就要做圖卡）；或在 LINE 週報中加一則單題投票；
     - (c) 決策由創辦人依 (a)(b)＋live 方向性數據裁決，並把理由寫回本 spec 的 Decision Log。
4. 不論哪條路，實驗結束後**移除落選變體的程式碼與路由**，i18n key 的刪除另開有意識的 commit（i18n Regression Guard）。

### D-9 R-HP-5 動態數字

- 新增 `web/lib/homepage/siteStats.ts`：`getActiveSourceCount()` = `sources` 表 `is_active = true` 的 `count: 'exact', head: true`，與 `/sources` 頁同一定義（避免兩處數字不同）；ISR 600 秒下每 10 分鐘最多查一次。
- 顯示時**向下取整到十位**並加「以上」（例：163 → 「160 以上」，對應 §5.3 佐證句「日本全国 160 以上の情報源」），避免數字每天跳動。
- i18n 改為 ICU 參數：`home.statHero` → 新 key `home.statHeroDynamic`（`{count}`），`about.sourcesBody` → `about.sourcesBodyDynamic`。舊 key **保留不刪**，呼叫端改用新 key。
- 「47都道府県」改為範圍陳述「日本全国」（不是資料計數，不需動態化）。
- `/design` 預覽頁的寫死字串（`web/app/[locale]/design/page.tsx:122-126`）一併改用新 key 或標示為設計 mock（該頁是內部預覽）。

### D-10 Design System Guard（強制）

| 介面元素 | 必須使用 | 禁止 |
|---|---|---|
| 意圖入口卡（4 或 3 張） | `<Link>` + `CARD_LINK`／`CARD_LINK_ARROW`（`web/lib/classNames.ts`），`rounded-xl border border-line` | 原生 `<button>` 包 `<a>`、自訂 hover 色 |
| 観る／学ぶ／話す、今週末 切換 | `PillButton`（`web/components/UiControls.tsx`） | 原生 radio、手刻 pill |
| 地區選擇器 | `DesignSelect`（`web/components/DesignSelect.tsx`） | 原生 `<select>`（FilterBar Dropdown Convention） |
| `/radar` 上的意圖 chip | `FilterChip`（`web/lib/design/FilterChip.tsx`） | 新的 chip 元件 |
| 今週の台湾卡片 metadata | `Badge`、`DateChip`、`CategoryThumbnail`（`web/lib/design/`） | 另寫日期／徽章樣式 |
| CTA（投稿、レーダーを見る） | `Button`（`web/components/Button.tsx`）或 `CARD_LINK` | `bg-white`、`text-gray-*` |
| LINE CTA | 唯一允許 `#06C755`（Bauhaus spec 規定） | 其他按鈕使用 LINE 綠 |
| 吉祥物／背景 | `MascotAvatar`、`FloatingShapes`（遵守 reduced motion） | 新動效函式庫 |

- 色彩只用語意 token（`bg-surface`、`bg-elevated`、`text-fg*`、`border-line*`、`text-brand`）；`bg-[#FFFDF5]` 需搭配既有 dark override。
- 每個互動元件需定義 default／hover／focus-visible（`ring-2 ring-green-500`）／active／disabled／loading／empty 狀態；light／dark 兩種主題對比 ≥ 4.5:1。
- 「今週の台湾」若需要新卡片形狀，先評估延伸 `EventListClient` 的 row 或 `EventCardMockup`，不要第三種卡片視覺。
- 視覺稿交 Designer（`designer` agent）依 `.github/skills/agents/designer/SKILL.md` 的 Checklist Before Handoff 產出後再實作。

### D-11 i18n Regression Guard（強制）

- 所有新字串放在既有 `home` namespace 下的巢狀物件（例：`home.intent.deepdive.label`、`home.intent.deepdive.hint`、`home.mode.watch`、`home.copy.A.title`、`home.copy.A.subtitle`、`home.picks.title`、`home.channels.*`、`home.region.*`、`home.radarCta`、`home.submitCta`、`home.statHeroDynamic`）與新 namespace `radar`（`radar.title`、`radar.intentBanner.*`、`filters.when*`）。
- **zh.json 先、en、ja 同一個 commit**，用 Python 腳本寫入（Designer SKILL 規定），寫完逐 key 三語 grep 驗證。
- 文案三案（`home.copy.A/B/C`）的 ja 為 §5.3 原文；zh／en 為翻譯，但 zh／en 只會顯示預設案。
- 不刪除任何既有 key（含 `home.introP1〜3`、`home.statHero`、`about.sourcesBody`、`home.shelf*`——後者仍被 `/radar` 的 `EventShelf` 使用）。
- 每個 commit 跑：`git show <hash> -- 'web/messages/*.json' | grep '^-'` 確認無非預期刪除；`categories` namespace 的 late-added keys（`competition`、`indigenous`、`history`、`urban`、`workshop`、`group_arts`、`group_lifestyle`、`group_knowledge`、`group_society`、`group_archive`）仍存在。
- TSX 中不得寫死 CJK：意圖、模式、チャンネル的標籤設定表放在 `intents.ts` 只存 **i18n key**，不存文字。

### D-12 影響檔案清單

新增：
- `web/app/[locale]/radar/page.tsx`（＋`loading.tsx`、`opengraph-image.tsx` 視需要）
- `web/app/[locale]/<hpv>/[variant]/page.tsx`（實驗變體路由，名稱實作時確認）
- `web/components/home/IntentEntry.tsx`、`ModeRow.tsx`、`WeeklyPicks.tsx`、`ChannelStrip.tsx`、`RegionSwitcher.tsx`、`HomeHero.tsx`、`HomeCtas.tsx`、`ExperimentTracker.tsx`
- `web/lib/homepage/intents.ts`、`eligibility.ts`、`picks.ts`、`siteStats.ts`、`flags.ts`、`legacyRedirect.ts`、`region.ts`、`when.ts`
- `web/lib/experiments/homepage.ts`
- `web/app/actions/record-homepage-event.ts`
- `supabase/migrations/<next>_homepage_experiment_events.sql`
- `web/tests/homepage-intents.test.ts`、`homepage-picks.test.ts`、`homepage-legacy-redirect.test.ts`、`homepage-when.test.ts`；`web/tests/e2e/homepage.smoke.spec.ts`
- `scripts/homepage_experiment_report.py`（或 SQL）

修改：
- `web/app/[locale]/page.tsx`（改為新首頁，或 re-export 預設變體）
- `web/proxy.ts`（舊 URL 308、實驗指派 rewrite、地區推定 cookie；`config.matcher` 不變）
- `web/lib/eventFilter.ts`（`intent`／`mode`／`channel`／`when` 參數）
- `web/components/FilterBar.tsx`（顯示 `when` 與意圖 chip；不重做視覺）
- `web/components/EventFilterContext.tsx`（新參數的 URL 同步）
- `web/components/BackToListButton.tsx`、`web/components/Navbar.tsx`
- `web/app/sitemap.ts`
- `web/app/[locale]/about/page.tsx`（動態來源數＋アクセス解析段落）
- `web/app/[locale]/design/page.tsx`（寫死字串）
- `web/messages/{zh,en,ja}.json`
- `.github/instructions/web.instructions.md`（目錄結構、Next 版本、Categories 段落；Phase E）
- `docs/ARCHITECTURE.md`（新增 server action／proxy 實驗機制屬整合點變更）

## Dependencies（與其他 spec 的介面）

| Spec | 本 spec 需要什麼 | 何時需要 | 沒有時 |
|---|---|---|---|
| `taiwan-relevance-scoring` | `events.feed_tier`、`web/lib/relevance.ts` 的 `applyHomeFeed`／`applyRadarFeed`（＋請求 `isHomeFeed(e)`），回填完成 | **阻擋 Phase C 的 production 切換**（Phase A、B 與 C 的開發／preview 不受阻擋） | 首頁不切換；仍可用 `?hp_preview=` 在訪談中展示原型 |
| `person-topic-entities` | `topics`（slug 與本 spec 一致）、follow Topic API、近期活動 Person 查詢 | 非阻擋 | D-7 fallback（常數＋隱藏） |
| `social-affordance-tags` | 交流強度、日本語OK 欄位與信心分數 | 非阻擋 | 観る／学ぶ／話す 用暫代映射；卡片不顯示門檻標籤 |
| `organizer-submission-v2` | `/account/events/new` 重建 | 非阻擋 | 投稿 CTA 連到現有入口 |
| `line-segmented-digest` | 分眾 LINE 連結 | 非阻擋 | 單一 LINE 好友連結 |

本 spec 不阻擋任何其他 spec。唯一的**阻擋依賴**是 `taiwan-relevance-scoring` 的回填完成（依對方 I-1 前置條件），且只阻擋「把 `/` 切換成新首頁」這一步；其餘依賴都有 fallback。

## Risks（風險）

| # | 風險 | 影響 | 緩解 |
|---|---|---|---|
| R1 | **流量不足以得到統計結論**（尤其 LINE 轉換） | D4 的「用 A/B 測試決定」無法如字面執行，決策拖延 | 兩階段序列測試、Bayesian＋平手採預設、Phase A 流量閘門、質性替代方案（D-8） |
| R2 | **relevance scoring 回填延遲 → 新首頁無法切換上線**；且 `home` 集合可能很小，加上意圖映射後更少 | P0 時程被對方 spec 綁住；或首頁內容稀疏 | Phase A、B 先行上線；C 在 preview 完成；C-1 以 `home` 集合量化每入口筆數；e1 在切換後才開始計時 |
| R3 | **意圖入口結果過少**（`when=week`＋地區＋映射三重過濾） | 空列表，入口被認為「壞掉」 | 每入口 empty state 自動放寬到「今月」並明示；C-1 量化 |
| R4 | **SEO 流量下滑**：`/ja` 從全量列表變成少量連結 | GSC 曝光／點擊下降 | 308 保留篩選 URL、`/radar` 進 sitemap、首頁保留 5–8 筆活動與 ItemList；上線後 4 週 GSC 監看，必要時在首頁增加「本週全部活動」連結區 |
| R5 | proxy rewrite＋ISR＋cookie 的組合在 Next 16 的行為與預期不同 | 變體被快取錯置、或首頁變成動態渲染（成本上升） | Phase D 先做 spike，確認 `x-vercel-cache` 與變體正確性後才開實驗 |
| R6 | 週報選題與首頁共用造成耦合：週報沒發、或週報選了不適合首頁的活動 | 今週の台湾空白或品質不穩 | 退回上一則＋自動補位＋`feed_tier='home'` 過濾 |
| R7 | 外部送信規律／隱私說明不足 | 法遵與信任風險 | About 新增說明段；只用 first-party 隨機 id；創辦人確認（Q7） |

## Open Questions（需創辦人決定）

- **Q1** 文案預設案：zh／en 與 e1 期間 ja 固定使用哪一案？（建議 **A 案**「日本で、台湾に出会う。／観る・学ぶ・話す、あなたのペースで。」，因為它與篩選列一致。）e2 平手時採用的預設也是這一案。
- **Q2** 實驗順序與門檻：同意「e1 版型 → e2 文案」的序列設計、`P ≥ 0.95` 採用、最長 6 週、平手採預設嗎？
- **Q3** 「今週の台湾」是否同意與 LINE 週報**共用選題**？若要首頁獨立排序或獨立選題，需新增欄位或表（P0 不含）。
- **Q4** Vercel 方案是否支援 Web Analytics 自訂事件？若支援，可只用 `track()` 而不建事件表；本 spec 預設自建表，不依賴方案。
- **Q5** LINE 公式アカウント 是否能建立多個「友だち追加経路」URL？若可以，e2 用它量測真實好友轉換。
- **Q6** 是否要把「関西」從 `chubu`（中部・近畿）拆出？涉及地區分類與 scraper 地區標記，若要做需另開 spec。
- **Q7** 是否接受 About 頁的アクセス解析說明作為隱私告知？是否需要專門的プライバシーポリシー頁？
- **Q8** 首頁是否保留公告列？（建議保留但限 3 筆、放在今週の台湾下方。）
- **Q9** 人工挑選的今週の台湾是否允許 `feed_tier='radar'` 的活動？（預設否，依 relevance spec I-1；若要允許，由對方以 FC 鎖升級為 `home`。）

## Complexity & Phases

整體複雜度：**L**（新路由＋舊 URL 遷移＋實驗基礎設施＋新 DB 表＋三語文案＋多 spec 介面）。拆成可獨立上線的 phase：

| Phase | 內容 | 複雜度 | 可獨立上線 |
|---|---|---|---|
| A | R-HP-5 動態來源數＋實驗事件表＋現行首頁 baseline 量測（view／LINE CTA click）＋隱私說明 | S | ✅ |
| B | `/radar` 路由搬遷、舊 URL 308、內部連結、sitemap、JSON-LD（首頁暫時仍是列表） | M | ✅ |
| C | 新首頁 P0 區塊、`intents.ts`／`when`／地區／picks、`/radar` 的意圖 chip | M | ✅（以預設變體 `L4`＋預設文案上線；production 切換須等 relevance 回填完成） |
| D | 實驗機制（proxy 指派、變體路由、preview、kill switch、報表）＋e1／e2 執行或質性替代 | M | ✅ |
| E | 決策落地：移除落選變體、文件與 instructions 更新、事件資料清理 | S | ✅ |
| F（依賴他 spec） | 開啟 Person／Topic follow／Community 區塊、觀學話改用交流強度標籤 | S–M（各自） | 隨對方上線 |

建議：A → B → C 依序（B 必須在 C 之前，否則首頁改版時全部活動會暫時沒有入口）；D 需等 C 上線且 Phase A 至少累積 2 週 baseline。

## Worktree & Spec Tracking

- **分類**：Large feature（新路由＋實驗子系統＋DB migration＋多 session）→ spec ⟺ 專屬 worktree（1:1）。
- **Spec**：`docs/specs/active/intent-homepage/`（`proposal.md`、`tasks.md`）。
- **Worktree**：`ttr-intent-homepage-worktree`，branch `feat/intent-homepage`。撰寫本 spec 時（2026-10-06）`git worktree list` 只有主工作樹，此 worktree **為 NEW**；實作前仍須重新以 `git worktree list --porcelain` 驗證，不得假設存在或不存在。
- **Phase 0（強制）**：Engineer 開工前必須 (1) **先向使用者確認**要使用 `ttr-intent-homepage-worktree`（或使用者指定的其他 worktree），得到明確答覆才動工；(2) 讀 `.github/instructions/git.instructions.md` § Isolated worktree，依 state matrix 建立或切換；(3) idempotent 寫入 `.git/info/exclude`；(4) 主工作樹只供治理，不得在此實作。
- **Session 復原**：本機計畫筆記（Claude Code／Codex 為 `~/.ai-notes/ttr/plan.md`，Copilot 為 `/memories/session/plan.md`）須引用 slug `intent-homepage`，恢復 session 時以 `tasks.md` 的勾選狀態為準。
- **合併**：每個 Phase 完成後 rebase `origin/main`，交 V-M-D；push 前必須取得使用者明確同意。Phase A 含 DB migration，需使用者在 Supabase Dashboard 手動套用並回報驗證 SQL 結果後，才能部署依賴該表的程式。

## Decision Log

| 日期 | 決策 | 依據 |
|---|---|---|
| 2026-10-06 | spec 建立；relevance 介面改採 `taiwan-relevance-scoring` I-1 的 `feed_tier` 契約 | 對方 spec 同日提出 |
| 2026-10-06 | チャンネル slug 與映射逐字採用 `person-topic-entities` §2.2（`tea-food` 用連字號；film 不含 drama；academic 不含 lecture） | 避免兩套 slug，Topic 上線後 URL 不失效 |

## References

- 需求文件：`TTR strategy/2.0/TTR-2.0-pivot-requirements.md`
  - §0 決策 1、6；§1.4 首頁入口數裁決（預設四意圖＋観る／学ぶ／話す 篩選列）；§4.1 來源數；§4.2 Q1／Q2／Q6
  - §5.3 文案三案與佐證句；§6.1 R-QA-2〜4；§6.4 首頁 IA 與 R-HP-1〜5；§6.11 信任與編輯方針
  - §9 Phase 0（修正首頁數字）、Phase 1（首頁原型 A/B）；§10 發現指標
  - §11 **D1**（2.0 重做表層）、**D2**（核心族群：台湾に少し踏み込みたい日本語話者，同時容納已入坑者）、**D4**（文案與入口數以原型 A/B 測試決定）、D5（2.0 不設變現目標）
- 相關 spec：`docs/specs/active/bauhaus-design-system/`（色票、LINE 綠唯一用途）、`docs/specs/active/seo-polish/`（JSON-LD、loading、OG）、`docs/specs/active/works-entity-for-films-and-tours/`（格式參考）、`docs/specs/active/market-positioning-strategy/proposal.md`（D1 背景）
- 依賴介面：`taiwan-relevance-scoring`、`person-topic-entities`、`social-affordance-tags`、`community-directory`、`line-segmented-digest`（皆待建立，§15）
- 規則：`.github/agents/architect.agent.md`（Design System Guard、i18n Regression Guard、Spec & Worktree Decision Gate）、`.github/skills/agents/architect/SKILL.md`（Predicate projection contract、Admin UI Dashboard Necessity Check、AEO Feature Planning Rules）、`.github/skills/agents/designer/SKILL.md`、`.github/instructions/web.instructions.md`、`.github/instructions/git.instructions.md`
