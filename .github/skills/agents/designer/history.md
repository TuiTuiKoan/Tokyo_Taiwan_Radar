## 2026-05-14 — OG Image punk Bauhaus collage 重設計（commit `171bea4`）

- **Observation**: 使用者要求將 OG 圖改為純幾何扛豁風格，去除所有文字資訊（標題、日期、場地、吸血髀），只保留 category label 和品牌水印。
- **Fix**: 尺寸改回 1200×1200 正方形；移除所有文字元素；改用 5 個確定性幾何圖形裝飾（disk/ring/tri/slab/arc/dash/plus/diamond 中選取）；主要 category label 以 `[TALK]`/`[FILM]` 形式呈現，對正 − 8°→+8° 隨機旋轉 + palette.fg 陰影；Ghost echo：200px label 以 22% 不透明度旋轉 90° 放於右下角。Supabase SELECT 簡化為只取 `name + category`。
- **Lesson**: OG 圖水印對品牌知名度有直接影響；設計時必須確認 category label 的可讀性。主要 label 平均 3–5 個字母（[FILM], [TALK], [LIFESTYLE+FOOD]）——最長案例進行了確認。`getCategoryLabel` 函式輸出包含 `[]` 括號的大寫 label，這是既有工具，直接復用。設計迴展實驗即 screenshot 工具確認。

## 2026-05-14 — OG Image 局部還原 bug：只改 height 未更新版面配置

- **Observation**: Validate-Merge-Deploy 流程中，local `opengraph-image.tsx` working tree 只把 `export const size.height` 從 630 改回 1200，但所有 SVG viewBox、corner accent 座標、文字欄寬高全都還是 1200×630 的版本。結果 local preview 下半 570px 完全空白。Production（1200×630 committed 版本）則完全正常。
- **Fix**: `git restore 'web/app/[locale]/events/[id]/opengraph-image.tsx'` 還原到 committed 狀態。無需重新 commit/push。
- **Lesson**: `export const size` 是 Satori OG Image 的 canvas 根設定。高度變更後**必須同步更新**：(1) 所有 `<svg viewBox="0 0 W H">` 的 H；(2) 所有絕對定位元素的 `top`/`bottom`/`right` 座標；(3) corner accent 形狀的 pivot 點。只改一行 size 等同於「換了畫框但圖不動」——視覺永遠是錯的。`git diff` 前必須先確認 local preview 是否與 production 一致，再決定是 commit 還是 restore。

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

## 2026-05-10 — Designer agent created

- **Observation**: UI / 視覺工作散落在 Engineer + Architect 之間，缺乏專責 owner。Dark mode rollout（Phase 1–4）後 token 系統已就緒，但缺長期維護者。
- **Fix**: 建立 Designer agent，定義 token catalog、i18n 三語同步契約、motion 預設、Recraft pipeline 預留設計。
- **Lesson**: 視覺一致性需要單一 owner agent。Token system 一旦建立，新 component 必須走 catalog；任何 raw `bg-white`/`text-gray-*` 都是回歸警訊。
