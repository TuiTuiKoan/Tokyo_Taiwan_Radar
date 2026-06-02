## 2026-06-04 — 解決「未命名」活動異常卡片與最佳化常設/長期活動分類邏輯

**問題：**
1. 畫面上會出現（未命名）的空白活動佔位卡片，影響使用者體驗。
2. 常設/長期活動（常設配信）分類，拉入過多單日/一次性的線上直播（Live Streaming）、線上播映、短暫的工作坊及特定時間的線上講座等，導致真正的長期常設作品被干擾掩埋。

**根因：**
- 部分爬蟲爬取後尚未經過 `annotator.py` AI 標註，其 `name_ja`, `name_zh`, `name_en` 皆為空白 / null，但之前在 `eventFilter.ts` 內未過濾，導致渲染出空白卡片。
- 常設判斷邏輯（`isPersistent`）先前過於簡略，只要有 "配信" 等關鍵字或無結束時間即認定為常設項目。而單日線上活動（例如 1-2 小時的 NHK 節目或特定單日工作坊）雖然有 "配信" 關鍵字，但其實屬於一次性活動。

**修正：**
1. **空白活動過濾**：在 `web/lib/eventFilter.ts` 全域篩選器中加入防禦檢查，若 `name_ja`、`name_zh` 與 `name_en` 皆為空值（`null` 或 `undefined`），則直接將此筆活動從陣列中排除，不再於前端顯示。
2. **常設/長期活動邏輯微調**：
   - 限制極其嚴格的「常設配信」進入門檻：
     - 若名稱、地點沒有任何線上標記，不進入常設。
     - 若明確給定了開始與結束時間，且持續天數（`durationDays`）小於等於 30 天，視為一般常規活動，並非長期常設。
     - 若帶有 event_form，只要符合常見的一次性活動型態（如 `lecture`, `screening`, `screening_with_talk`, `workshop`, `talk`, `concert`），則不應該進入 persistent 常設。
     - 若 `start_date` 為明確帶有特定時刻的行程（而非 UTC 零點 `T00:00:00Z`），代表為有特定播放排程的單次線上活動（如特定時刻的 Webinar、一次性直播），將之排除於常設，歸入一般垂直時間流。

**教訓：**
- 資料清洗與 AI 標註流程中，未經標註的瑕疵暫時性資料必須在過濾層（Filter）進行第一時間攔截，而非等 UI 元件各自處理（Null-safety 最佳實踐）。
- 用戶體驗最佳化的細節通常在「例外規則」的處理，純關鍵字判斷常設（如“配信”）不能涵蓋一次性的預約直播，必須搭配時間、性質（`event_form`）以及持續區間（`duration`）多重防線。

---

## 2026-06-03 — FloatingShapes 背景動畫防重疊、Slot 綁定與 unique-path 機制重構

**問題：**
1. 幾何飄浮圖形在首頁有時會發生完全重疊、黏在一起平行前進的現象（視覺打架）。
2. 在首頁載入（Mount）時，因為初始 Delay 設定在極小的隨機區間內，導致開啟首頁一瞬間所有圖形在同時間、從不同邊緣排隊冒出，生硬死板。
3. 全版模式下（`full` 變體）配置了 10 個 Slot，最大（Tier 4）與次大（Tier 3）圖形在畫面上同時出現高達 4 個，干擾閱讀且視覺擁擠。

**根因：**
- 舊版 `newFloater` 是各自隨機抽取 `DRIFTS` 移動方向。當多個 Slot 同時生成，碰巧選中相同的移動軌跡時會引發視覺重合。
- 為了避免 mid-journey 破圖而縮短了 `initialPhase` 係數，導致開場律動過於集中。
- 舊版 Slot 無尺寸總量上限管制（5 階 × 固定 2 個），造成大型色塊/圖形過度擁擠。

**修正：**
1. **軌跡絕對唯一化 (Strictly Unique Trails)**：將 Slot 縮減至 **8** 個。在 `useEffect` 對 8 個 Slot 1-to-1 分配打亂後的 `shuffledDrifts` 行進軌跡。
2. **生命週期鎖定**：每次物件 Cycle 重啟（`handleCycle`）時，傳入 `prev` 以繼承並鎖定其專屬 `drift` 軌跡，僅隨機重配置幾何/顏色。
3. **尺寸管制限額**：Slot 階層配置改為 `[0, 0, 1, 1, 2, 2, 3, 4]`，限縮次大與最大圖形在畫面中各自隨時至多僅能有 **1** 個，最小三階各 2 個。
4. **自然錯開分佈**：將 mount 時的 `initialPhase` 隨機係數自 `0~5%` 放開到它的全生命週期 `0~100%` 進度間，讓開場點綴在不同滑行階段，去除集中彈出感，後續 Cycle 仍回邊緣正常滑入。
5. **微縮模式支援**：微縮變體（`subtle`）初始化也分配 unique drifts，且重構 `handleCycle` 時同樣保持 `prev.drift` 鎖定以防重疊。

**教訓：**
- 全螢幕抽象幾何動效，Slot 與移動軌跡（`DRIFTS`）若不進行 exclusive-binding（打亂分配），單純隨機會必然引發機率性重疊。
- 對於大型幾何色塊應在 Slot 分配上建立重量限額規則（如最大階各 1 個），留白不干擾主內容才是良好的 Bauhaus 背景底調。
- `initialPhase` 設為物件 duration 的全生命週期，能讓初次 Hydration/Mount 瞬間顯得無痕自然。

---

## 2026-05-15 — SKILL.md 修正：tip flash 峰值色 + tip-core Safari scale() 規則

**新增/修改：**
- `Tip white-flash pattern` 標題改為 `Tip flash pattern`；峰值色描述從「green → white」改為「green → #C4E86F」；加⚠️ 警告純白在淺色背景不可見
- `lianbu-tip-core-expand` 說明從「uses r-property, not transform:scale」改為「uses CSS scale() + transform-box:fill-box；Safari 不支援 CSS r 動畫」；加⚠️ 警告
**來源：** daily-skills-review（commits `18c0f1b` / `228cb45` 改了實作但未更新 SKILL）

---

## 2026-05-15 — MascotAvatar tip-ring stroke 固定化 + tip-core scale() 跨瀏覽器 + flow-dot FOUC 防護

**問題：**
1. `tip-ring`（天線頂端光環）stroke 在不同瀏覽器寬度不一致（Chrome 粗、Safari 細），視覺不穩定。
2. `tip-core`（天線頂端核心點）使用 CSS `scale()` 動畫，Firefox/Safari 對 SVG 元素的 `transform-origin` 處理不同，縮放中心跑偏。
3. `flow-dot`（流光圓點）及 `tip-ring`（改為 `fill=radialGradient` 後）在頁面首次 paint 前以 `opacity=1` 全顯，造成「左上 / 左下白光球」FOUC 殘影。

**根因：** 
- `tip-ring` 改用 `fill=url(#radialGradient)` 而非舊版 `fill="none" stroke=...`，baseline opacity 未設 0。
- `flow-dot` SVG 屬性 `fillOpacity="0.85"` 在動畫生效前已渲染，CSS `opacity: 0` 第 0% keyframe 來不及壓制。
- `tip-core` 的 `scale()` 函數在 SVG 環境下需要顯式 `transform-box: fill-box` 才能以元素中心為原點。

**修正（commit `tip-ring…`）：**
1. `tip-ring`：將 stroke 值固定為 `1.4`（px），加 `opacity={0}` SVG 屬性。
2. `tip-core`：CSS 動畫加 `transform-box: fill-box`，確保跨瀏覽器縮放中心一致。
3. `flow-dot`：加 `opacity={0}` SVG 屬性；`globals.css` 的 `lianbu-antenna-flow-line` 初始 `opacity` 改為 `0`。

**教訓：**
- SVG 元素改為 `fill=url(#gradient)` 時，**必須同步加 `opacity="0"` SVG 屬性**（或 CSS baseline `opacity: 0`），否則 CSS animation 啟動前會以 opacity=1 全顯在 DOM 基底座標，形成 FOUC。
- SVG 元素的 CSS `scale()` / `rotate()` 動畫需加 `transform-box: fill-box` 才能在 Firefox/Safari 下以元素中心旋轉縮放。
- SVG stroke 寬度如需跨瀏覽器一致，用 `stroke-width="1.4"` 硬編碼而非繼承或預設值。

## 2026-05-14 — OG Image 1200×1200 → 1200×630 に差し戻し（full-bleed レイアウト、commit `92b9e82`）

- **Observation**: 以前のセッションで「正方形 1200×1200 が Instagram/LINE に強い」として方形に変更したが、Twitter/X・Facebook・Slack はいずれも 1.9:1（1200×630）を標準とし、正方形は上下クロップされてタイトルが見切れるフィードバックがあった。また 1200×1200 の cream bottom panel レイアウトはテキストが下半分に詰まり、1200×630 の横長 canvas では不釣り合いだった。
- **Fix**: `export const size` を `{ width:1200, height:630 }` に戻し、レイアウトを全面刷新。Motif（カテゴリ SVG 絵柄）を右側絶対配置（`right:60, top:50, 480×480`）に移動、左 700px にテキストブロックを full-height 配置（cream panel 廃止・背景直置き）。Corner accent・パターン SVG の viewBox をすべて `0 0 1200 630` に更新。パターン opacity `0.45→0.35`（cream panel なしでは濃すぎるため）。
- **Lesson**: OG 画像の縦横比は**変更前にターゲット SNS を列挙して確認**する。Twitter/X 大カード・Facebook・Slack = 1.9:1 必須。Instagram Feed = 1:1 or 4:5。用途が混在する場合は Twitter を優先する。正方形への変更は「Pinterest/Discord に強い」が「Twitter で文字が見切れる」というトレードオフがあり、イベント告知用途では 1.9:1 の方が有利。`export const size` を変えたら**すべての SVG viewBox と絶対配置座標を同時に更新すること**（高さが変わると cornerShape 位置が全てズレる）。

## 2026-05-14 — FilterBar 全面改為 custom button+panel；OG 圖 Bauhaus 方形重設計

### A — FilterBar：native `<select>` → custom button + panel（commits `f72566d`–`06254c7`）

- **Observation**: `appearance-none` + CSS 箭頭方案在各瀏覽器仍有不一致（Safari/Chrome chevron 殘留、iOS tap 目標過小）。User 要求所有下拉一律改用自訂 button+panel，視覺與 category picker 完全統一。
- **Fix**: 4 個 native `<select>` 全替換為 `<button>` toggle + absolute panel（location、paid、timeMode、city）。紙色背景（`bg-paper #FFFDF5`）統一套用到 keyword input 和 custom panel。`.select-arrow` CSS class 方案廢棄。
- **Lesson**: Native select 的跨瀏覽器外觀統一極其困難；一旦設計需要像素精確的 chevron 或品牌背景色，從一開始就用 custom button+panel，不要試圖用 `appearance-none` 補救。

### B — OG 圖重設計：Bauhaus 方形 + CategoryThumbnail 色系 + 吉祥物（commits `18055fd`, `c36673e`, `ef305d3`）

- **Observation**: 原 OG 圖（1200×630）水平比例在 Twitter card 顯示不理想；顏色與首頁 Bauhaus 設計系統脫節。
- **Fix**: 改為 1200×1200 正方形；背景色使用 `CategoryThumbnail` 已定義的 `CATEGORY_PALETTE`（每種 category 各自的 bg/fg/accent）；右下角加入 wax-apple 吉祥物 SVG（body color = `palette.fg`）＋品牌名稱。事件圖片寬佔 65%、左對齊，右欄為標題 + meta。
- **Lesson**: OG 圖改版時 Satori 不支援 Tailwind class，必須全用 inline `style={}` 物件。`CategoryThumbnail` 的 `CATEGORY_PALETTE` 是色彩唯一 source of truth；OG 圖不應另開色值。方形 1200×1200 比 1200×630 更容易跨平台（IG、LINE preview）顯示完整。

## 2026-05-14 — OG Image：wax-apple 吉祥物 + CategoryThumbnail 色系 + 方形設計

**問題：** OG Image 無品牌識別性，缺少吉祥物元素，矩形比例在社交媒體顯示較佳但失去 Pinterest/Discord square 最佳呈現。

**修正：**
1. 改為 1200×1200 方形 OG image（square 在多平台通用）
2. CategoryThumbnail 色系：依 category 衍生 `palette.bg`/`palette.fg`/`palette.accent` — OG 背景色與活動卡片同步
3. 右下角加入 wax-apple 吉祥物 SVG（size 80×88, viewBox 200×220），身體色跟隨 `palette.fg`，吉祥物上方顯示品牌名稱
4. 標題文字使用 Noto Sans JP（Edge Runtime 相容字體）

**教訓：**
- OG image 必須走 Edge Runtime 限制：不可用 `import`（圖片用 `fetch`），字體必須從 Google Fonts CDN fetch。
- `ImageResponse` 的 `width`/`height` 要同時更新 `opengraph-image.tsx` 的 `export const size`；否則 Next.js 回傳的 `content-type` header 與實際尺寸不符。
- 吉祥物 SVG 在 `ImageResponse` 的 JSX 環境中必須以 inline props（`style={{}}`）傳遞顏色，Tailwind class 在此環境無效。

## 2026-05-14 — Refined responsive constraints, localized pill placement, and orchestrated animation flights
- **Observation**: User noted that Navbar height changed across breakpoints (`h-14` vs `h-16`) and logo was scaling (`w-6` to `w-8`), breaking alignment. Right-side "Daily Radar" block disrupted the flow. The previous drifting background animation was too chaotic and the shapes didn't match the specific requested aesthetic boundaries.
- **Fix**: Removed breakpoint sizing from Navbar by locking `h-14`, `w-8 h-8` globally for seamless responsive state. Eradicated the right-bound aside info-card and replaced it with a targeted green pill (`bg-[#E8F8EE] text-[#06C755]`) directly under the main heading block. Purged the entire inner SVG scattered layout, injecting exactly mapped structural elements (Left/Right half-circles paired with semi-transparent patterns and rotated quadrilaterals). Registered `@keyframes fly-in-1`, `2`, `3`, and `shrink-fly-out` inside Tailwind `@theme` logic mapped globally to drive continuous linear crossing animations bounding out to `120vw` coordinates, generating a living layered atmosphere instead of static shapes.
- **Lesson**: Tightly lock navigational headers against responsive shifts to preserve spatial expectations. Unifying background vectors behind a global absolute scaling wrapper allows independent non-conflicting translate limits (avoiding viewport clipping cutoff walls during transit).
## 2026-05-14 — Abstract SVG drifting animation, Lianbu overlapping tether, and #3A261F purges
- **Observation**: SVG background was still too static and chaotic. Typography scaling for taglines was too obtrusive and overpowering identical hierarchy. "Lianbu" label flew out of its bounds in wider browser instances. Colors inconsistently applied deeply nested elements.
- **Fix**: Added `@keyframes float` to absolute CSS globals and scattered varying lengths of `animate-[float_X_ease-in-out_infinite_alternate]` over huge SVG shapes to mimic dynamic, drifting galaxies. Hard-tethered MascotAvatar layout via `inline-flex shrink-0` holding absolute bounding boxes to anchor the Lianbu label precisely on the bottom right side. Swept `text-[#3A261F]` onto all nav anchors, list titles, and primary headers instead of generic inherited overrides. Shrunk tagline font by 80% to (`7px/9px`) baseline-matched. Lowered EventList weight from `font-black` to `font-bold`.
- **Lesson**: Relying on container inheritance to distribute branding color tokens to React link tags will usually fail against browser agent native behaviors — manually pin brand hex wrappers on `.nav a, h1 span` directly when explicit precision is demanded by UI.
## 2026-05-14 — Typographic baseline alignment, Bauhaus extremes, and icon unifications
- **Observation**: "Tokyo Taiwan Radar" and its bilingual tagline were poorly aligned. Icons used varied sizing and arbitrary background bubbles. Bauhaus objects felt too stiff and predictable rather than free-floating.
- **Fix**: Centralized all Navbar element alignments using `items-center` for perfect baseline. Translated tagline dynamically. Scaled abstract Bauhaus geometry dramatically up (`scale(2) - scale(2.5)`), layered geometric intersections more wildly (`path` curves running through gigantic rotated bounding `rect` blocks), dropping all literal representations. Unified `.text-[#6A5148]` color mapping directly onto all core titles, navigational icons, and SVG shapes.
- **Lesson**: "Bauhaus" in digital layout requires reckless scalar bravery to feel deliberate — do not fear clipping the viewbox heavily with size modifiers. Brand colors should be rigorously enforced on sub-headers directly to bring cohesive depth over generic `.text-fg-strong`.
## 2026-05-14 — Form shadows, unified interaction states, geometric replacements
- **Observation**: Action hover colors were split between brand-red and standard greens, creating disjointed feedback loops. Search panels threw heavy dropdown box-shadows while the inputs themselves felt flat and unclickable. Geometries used literal shapes (like Mt. Fuji) leading to overly-illustrated feel vs abstract Bauhaus. Grid was too faint.
- **Fix**: Replaced all actionable interactive `hover:text-red-500` resets with standard `hover:text-green-700` unified paths. Stripped wrapper shadows from active filter panels and applied precise `shadow-sm` directly onto inputs and select triggers. Redrew SVG backgrounds abandoning literal paths in favor of massive interlocking abstract arcs, overlapping opaque circles, and thick geometric bands. Increased `gridPink` SVG definition stroke width from `0.9` to `1.6` and base opacity for deeper pop. Stripped right-aligned 'Details' call-to-action out of EventCards entirely to allow for seamless expanding.
- **Lesson**: If the user desires Bauhaus, reject literal illustration immediately (like mountains). Rely purely on primitives (`<rect>`, `<circle>`, `<path a...>` arcs) scaled massively with heavy opacities intersecting each other. When flattening panels, explicitly remember to transfer `shadow-sm` onto the deepest interactive children so inputs don't feel disabled.
## 2026-05-14 — Typography updates, responsive layouts, and pattern opacity tuning
- **Observation**: Default tracking/font-weight wasn't distinguishing the "LAMBU RADAR" badge properly. The top-left `Navbar` typography sizing overshadowed the page hero, and the sub-header label was breaking out on mobile formats. Background SVG dot patterns (`halftone`) were too visually noisy at the top.
- **Fix**: Replaced tracking sizes with explicit `font-accent` for the badge. Scaled Navbar logo text down, shifted the sub-header label underneath it natively at `sm` breakpoint via `flex-col sm:flex-row`. Toggled `min-[380px]` boundaries to gracefully hide the sub-header on extremely narrow phones. Removed the `halftone` opacity layer from SVG while boosting the primary `gridPink` baseline to `0.75` for crispness. Refactored top Navbar backing to `bg-paper/50`.
- **Lesson**: Navbar scaling on responsive views must rely on flex-wrapping the logo component rather than truncating immediately, relying on explicit `block` constraints for visibility on extreme narrows `<380px`. Always prefer dedicated accent fonts over raw scaling classes when branding elements.
## 2026-05-14 — Responsive alignment and layered backgrounds
- **Observation**: SVG patterns heavily overlapping at exactly `y=0` caused top-heavy visual weight. Elements centered natively in CSS flow (like absolute positioning within flex layouts) can fail on mobile if the wrapper isn't strictly controlled with `w-full flex-col`.
- **Fix**: Redistributed `<g>` transformed SVG shapes deeper into `viewBox` coordinates with scatter. Forced `w-full flex-col` and strict `text-center md:text-left mx-auto md:mx-0` cascades on mobile. Built targeted Mobile-open-only black borders without background wrappers to match designer specifications precisely.
- **Lesson**: Do not wrap functional inputs into background styling blocks before considering their expanded states on specific viewports; separate the container bounds from the toggle UI completely.

# Designer — History

Newest entries at top. Each entry: date, observation, fix, lesson.

---

## 2026-06-03 — Designer 規範未明示 design system 優先，導致可能回退原生 control

- **Observation**: 雖然 `DesignSelect` 等站內 design-token 元件已存在，但 Designer 的 agent / skill 只寫了 token 與 i18n 規範，沒有把「先用本站 design system，native control 只當 fallback」明文制度化。
- **Fix**: 在 `.github/agents/designer.agent.md` 新增 design system 優先原則，並在 `.github/skills/agents/designer/SKILL.md` 新增 `Design System First Guard`。
- **Lesson**: 視覺設計規範不只是色彩與間距，元件選型本身也是 design system 的一部分。若不把優先順序寫進 Designer agent，native control 會在不同頁面悄悄回流。

## 2026-05-10 — Designer agent created

- **Observation**: UI / 視覺工作散落在 Engineer + Architect 之間，缺乏專責 owner。Dark mode rollout（Phase 1–4）後 token 系統已就緒，但缺長期維護者。
- **Fix**: 建立 Designer agent，定義 token catalog、i18n 三語同步契約、motion 預設、Recraft pipeline 預留設計。
- **Lesson**: 視覺一致性需要單一 owner agent。Token system 一旦建立，新 component 必須走 catalog；任何 raw `bg-white`/`text-gray-*` 都是回歸警訊。
