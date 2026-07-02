---
name: designer
description: Visual design rules, token system, i18n contract, motion patterns, and Recraft pipeline conventions for the Designer agent
applyTo: .github/agents/designer.agent.md
---

# Designer Skills

Read at the start of every session before proposing UI changes.

## Canonical Paths

- Agent file: `.github/agents/designer.agent.md`
- Skill file: `.github/skills/agents/designer/SKILL.md`
- History: `.github/skills/agents/designer/history.md`
- Token source of truth: `web/app/globals.css` (`@theme` block + `:root` / `:root.dark`)
- i18n source of truth: `web/messages/{zh,en,ja}.json`
- Theme toggle: `web/components/ThemeToggle.tsx`
- Anti-flash script: `web/app/layout.tsx` (inline `<script>` in `<head>`)

## Design System First Guard

在任何 `web/` 視覺設計與元件重構中，優先使用本站既有 design system 與 design-token 元件，不得預設回到原生 HTML control。

1. 若已有可重用元件（例如 `DesignSelect`、現成 dialog / popover / button / badge / input），設計稿與實作說明必須先選它們。
2. Native `<select>`、`<dialog>`、手寫 dropdown / popover 只能作為 fallback，且要說明為何既有 design system 不足。
3. 新增視覺互動之前，先確認是否能延伸現有 token、spacing、radius、shadow 與 hover/focus 模式，而不是另起一套樣式語言。
4. 若要引入新設計元件，需同時說明它如何符合現有 design system 的語意與維護成本，避免 component sprawl。

## Semantic Token Catalog

These are the **only** color tokens to use in new component code. Defined in `globals.css`.

| Token (Tailwind utility) | CSS variable | Light value | Dark value | Use for |
|---|---|---|---|---|
| `bg-surface` | `--color-surface` | `#ffffff` | `#1f1f1f` | Cards, dropdowns, inputs, modals |
| `bg-elevated` | `--color-bg-elevated` | `#f9fafb` | `#171717` | Filter panels, secondary surfaces |
| `bg-muted` | `--color-bg-muted` | `#f3f4f6` | `#262626` | Chips, hover fills, subtle accents |
| `text-fg` | `--color-text` | `#171717` | `#ededed` | Primary body text |
| `text-fg-strong` | `--color-text-strong` | `#111827` | `#fafafa` | Headings, emphasized text |
| `text-fg-muted` | `--color-text-muted` | `#6b7280` | `#a1a1aa` | Secondary text, labels |
| `text-fg-subtle` | `--color-text-subtle` | `#9ca3af` | `#71717a` | Placeholder, disabled, dates |
| `border-line` | `--color-border` | `#e5e7eb` | `#2a2a2a` | Default borders, dividers |
| `border-line-strong` | `--color-border-strong` | `#d1d5db` | `#3f3f46` | Form control borders, strong dividers |
| `divide-line` | `--color-border` | `#e5e7eb` | `#2a2a2a` | `divide-y` between list items |
| `text-brand` | `--color-brand` | `#16a34a` | `#22c55e` | Brand accents (NB: dark uses brighter green) |
| `bg-brand-soft` | `--color-brand-soft` | `#f0fdf4` | `#052e16` | Brand-tinted backgrounds |

**Adding a new token:**
1. Add CSS variable to BOTH `:root` AND `:root.dark` in `globals.css`
2. Add to `@theme` block to expose as Tailwind utility
3. Document in this table
4. Verify contrast ≥ 4.5:1 (body) or 3:1 (large text/UI) against backgrounds in both themes

## Color Decision Tree

```
Is it a brand identifier (logo green, alert red, link)?
├─ YES → use raw Tailwind palette (green-600, red-500, blue-600) — these are intentionally constant across themes
└─ NO  → use semantic token from catalog above
```

**Never** use these in new code:
- `bg-white`, `bg-black`, `bg-gray-*`
- `text-gray-*`, `text-black`, `text-white`
- `border-gray-*`, `divide-gray-*`

These are checked by:
```bash
grep -E "bg-white|bg-gray-|text-gray-|border-gray-|divide-gray-" web/components/*.tsx web/app/**/*.tsx
```
Should return zero matches in any new commit.

## i18n Three-Way Sync Contract

**Rule:** Every user-visible string requires keys in all three locale files in the **same commit**. next-intl renders missing keys as the raw key string with no warning.

### Adding a new key

1. Identify the namespace from the component's `useTranslations("<namespace>")` call.
2. Add key to **zh.json first** (canonical), then en.json, then ja.json.
3. Use a Python script (not `replace_string_in_file`) for CJK content to avoid encoding issues:

```python
import json, pathlib
for loc, val in [("zh", "繁中文字"), ("en", "English text"), ("ja", "日本語テキスト")]:
    fp = pathlib.Path(f"web/messages/{loc}.json")
    data = json.loads(fp.read_text())
    data["filters"]["newKey"] = val   # CORRECT — under namespace
    # NEVER: data["newKey"] = val     # WRONG — top-level
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
```

4. Verify:
```bash
for L in zh en ja; do grep -n '"newKey"' web/messages/$L.json; done
```
All three files must show the key.

### Common namespaces (verify in component before adding)

- `nav` — Navbar
- `filters` — FilterBar (search, category, location, paid, timeMode, dateFrom, dateTo, etc.)
- `categories` — Category labels (single source of truth for both display and dropdown)
- `categoryDesc` — Category long-form descriptions (used in `/categories/[category]` pages)
- `event` — Event detail page (free, paid, ended, organizer, performer, …)
- `organizerType` — Organizer type badges
- `eventForm` — Event form badges (exhibition, concert, lecture_seminar, …)
- `general` — Site-wide (footerCredit, noResults, loading, …)
- `admin*` — Admin-only (multiple sub-namespaces: `adminEvents`, `adminReports`, …)
- `announcement*` — Announcement system

### Translation tone

- **zh** — Traditional Chinese (繁體中文), 台灣常用詞彙（不用「網絡」改用「網路」、不用「視頻」改用「影片」）
- **ja** — 自然な日本語、です・ます調、漢字とひらがなのバランス
- **en** — Sentence case for labels, Title Case for proper nouns. Concise.

### Subtle gotchas

- `categories` namespace contains **both** category values (`movie`, `art`) AND group labels (`group_arts`, `group_lifestyle`). Don't confuse the two.
- `competition`, `indigenous`, `history`, `urban`, `workshop`, `group_arts`, `group_lifestyle`, `group_knowledge`, `group_society`, `group_archive` were added late — verify they exist before any commit.
- next-intl interpolation: `t("key", { n: count })` — never use `.replace("{n}", String(count))`.

## Component Inventory (high-traffic surfaces)

| Component | File | Notes |
|---|---|---|
| Navbar | `web/components/Navbar.tsx` | Sticky top-0; contains ThemeToggle, LangSwitcher, auth |
| FilterBar | `web/components/FilterBar.tsx` | Mobile collapsible; URL-state-driven |
| EventCard | `web/components/EventCard.tsx` | Server Component (uses `getTranslations`) |
| EventListClient | `web/components/EventListClient.tsx` | Client filter; reads `useSearchParams` |
| ThemeToggle | `web/components/ThemeToggle.tsx` | Sun/Moon icon, localStorage persistence |
| AdminEventTable | `web/components/AdminEventTable.tsx` | Largest component; sticky filter bar |
| AnnouncementCard | `web/components/AnnouncementCard.tsx` | Used on `/announcements` and homepage |

When designing new components, **mirror the existing patterns**:
- Inline SVG icons (24×24 viewBox, `currentColor` stroke, `strokeWidth=2`)
- `rounded-lg` for inputs/buttons, `rounded-xl` for cards/dropdowns, `rounded-full` for badges/chips
- Border-first design: `border border-line` on most surfaces, shadow only on raised modals/dropdowns
  - **例外（使用者明確要求，勿自動加回邊框）**：事件創建精靈（`AdminEventForm.tsx`）的三個 section card 用 `rounded-2xl bg-paper/60 p-5` —— **無邊框 + 60% 半透明紙色**（`f9989ff`, 2026-07-03）。這是刻意的 borderless 例外，未來 review「為何沒有 border-line」時不要改回 `border border-line bg-paper`。
- Spacing scale: `gap-1` (4px), `gap-2` (8px), `gap-3` (12px), `gap-4` (16px), `gap-6` (24px), `gap-8` (32px)

## FilterBar Dropdown Convention

All filter dropdowns in `FilterBar.tsx` **must** use custom button + absolute panel pattern. Native `<select>` is banned.

**Reason:** `appearance-none` + CSS chevron cannot reliably suppress browser-default select arrow across Safari/Chrome/iOS. Custom panel gives pixel-accurate brand background (`bg-paper #FFFDF5`) and consistent chevron.

**Pattern:**
```tsx
// ✅ Custom button + panel
const [open, setOpen] = useState(false);
<div className="relative">
  <button onClick={() => setOpen(!open)} className="... bg-paper ...">
    {label} <ChevronDownIcon />
  </button>
  {open && (
    <div className="absolute z-30 bg-paper border border-line rounded-lg shadow-md ...">
      {options.map(opt => <button key={opt.value} onClick={() => { applyWith(key, opt.value); setOpen(false); }}>{opt.label}</button>)}
    </div>
  )}
</div>

// ❌ Avoid — cross-browser inconsistency
<select className="appearance-none ...">
```

## Mobile Filter CTA State Rule

- Mobile FilterBar trigger must implement two explicit semantic states:
  - Closed state: primary action label (example: `searchOrFilter`) with high-visibility solid style.
  - Open state: confirm/apply label (example: `confirm`) that closes the panel after apply.
- Open state CTA must not leave the panel expanded after user confirms. "Apply" without collapse is treated as an incomplete interaction spec.
- Any new FilterBar CTA labels must be added to all three locale files in the same commit:
  - `web/messages/zh.json`
  - `web/messages/en.json`
  - `web/messages/ja.json`
- Visual state mapping should be obvious at a glance (color + label + icon can all change), but must keep contrast compliant in both light and dark themes.

## Card Link Hover Pattern

All card-type hyperlinks in the web app use a **unified hover pattern** matching the navbar hamburger menu. This is the single source of truth — import from `web/lib/classNames.ts`.

```ts
import { CARD_LINK, CARD_LINK_ARROW } from "@/lib/classNames";
// CARD_LINK      = "group flex items-center transition bg-[#FFFDF5] hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400"
// CARD_LINK_ARROW = "text-fg-subtle group-hover:text-[#1F5E2B] dark:group-hover:text-green-400 shrink-0"
```

> ⚠️ **bg-[#FFFDF5] ≠ bg-paper**：`bg-paper` 在 Tailwind v4 `@theme` 被 build-time 靜態編譯為 `#FFFDF5`；`dark:bg-paper` 雖語法正確，但實際上 CSS variable 切換對它無效。`bg-[#FFFDF5]` 搭配 `globals.css` line 378 的 `html.dark .bg-\[\#FFFDF5\]` runtime override 才是正確的 dark mode paper 寫法。

**Usage:**
```tsx
<Link className={`${CARD_LINK} px-4 py-3 gap-3`}>
  <span className="flex-1">Event title</span>
  <span className={CARD_LINK_ARROW}>↗</span>
</Link>
```

- Light mode: `#F7FFE8` (matcha) background + `#1F5E2B` (forest) text
- Dark mode: `green-900/40` background + `green-400` text
- `CARD_LINK` already includes `group` and `transition` — do NOT add again
- `CARD_LINK_ARROW` uses `group-hover:` because `text-fg-subtle` on the span would otherwise override the parent's hover color (CSS class specificity)

> ⚠️ **Arrow trap**: Any span with its own `text-*` class WILL override the parent `hover:text-*` via CSS specificity. Always use `group` on the parent and `group-hover:text-[#1F5E2B] dark:group-hover:text-green-400` on icon spans — or use `CARD_LINK_ARROW`.

## Navbar Icon Group Priority

- High-frequency personal actions (`saved`, `auth`, `lang switch`) should live in the header icon group, not only inside the hamburger menu.
- Avoid duplicate navigation affordances where one is icon-level and another is menu-text-level unless they serve different flows.
- If an action is kept in the icon group, mobile menu should not repeat it as a parallel primary entry.

## Hamburger Dropdown Frosted-Glass Contract

- Mobile hamburger panel must define a full material contract in both themes: color + opacity + blur.
- Recommended baseline (as of commit `0a66f93`):
  - Light: `bg-paper/75 backdrop-blur-lg`
  - Dark: `dark:bg-[#0a0909]/75 backdrop-blur-lg`
- Do not use near-opaque dark overlays (e.g., `.../95`) when light mode is translucent; this breaks theme parity.
- When tuning menu panel visuals, compare perceived visual weight in light/dark side-by-side, not single-theme screenshots.

### ⚠️ Stacking Context Rule — backdrop-blur 子元素陷阱

**`backdrop-blur` 不可設在擁有 `backdrop-filter` 的元件的 DOM 子孫上。**

父層 `backdrop-filter` 會建立新的 composite layer，子元素的 `backdrop-blur` 只能模糊父層的合成輸出，看不穿到頁面背後的內容，導致毛玻璃效果完全失效（外觀和純實心背景無差異）。

**修正方式：** 把 overlay/panel 移到 filter 父層**外部**。

```tsx
// ❌ 錯誤 — <nav> 在 <header backdrop-blur> 內，blur 失效
<header className="backdrop-blur-md sticky top-0">
  {menuOpen && <nav className="backdrop-blur-lg">…</nav>}
</header>

// ✅ 正確 — <nav> 改為兄弟元素，sticky top-14 貼在 h-14 header 下方
<>
  <header className="backdrop-blur-md sticky top-0 z-50">…</header>
  {menuOpen && (
    <nav className="sticky top-14 z-40 bg-paper/75 backdrop-blur-lg dark:bg-[#0a0909]/75">…</nav>
  )}
</>
```

**診斷步驟（「毛玻璃無效」排查清單）：**
1. 確認元素有透明度（`bg-.../opacity`）
2. 確認元素確實覆蓋在其他頁面內容上方（absolute/fixed/sticky）
3. **檢查 DOM 祖先是否有 `backdrop-filter`** ← 最常見被遺漏的根本原因
4. 如有，將元素移出該祖先或改用 React Portal

## OG Image 規範（`opengraph-image.tsx`）

Current design (as of 2026-05-15, commit `a273483`):

- **Size:** 1200×1200（正方形 — IG・LINE・Pinterest・Discord 均最佳呈現）
- **Background:** `PALETTES[hash(id) % 8].bg`（8 種通用 palette，依 event id / category name hash 選色，非 per-category 固定對應）
- **Layout:** Collage motif（多個 `getSemanticSymbol()` cell）＋ bg texture ＋ 右下角品牌名稱
- **Motif selection:** `getSemanticSymbol(cat, v, fg, accent)` — 直接從 `organicMotifs.tsx` **動態**取得；⚠ `SEMANTIC_RULES` / `pickSemanticMotif` / `CATEGORY_PALETTE` **不存在於現行程式碼**（2026 年舊設計稿殘留，已廢棄）
- **Fonts:** Noto Sans JP（inline fetch from Google Fonts API）
- **Locale PRNG:** 同一活動不同語言版本有不同設計（locale-seeded random seed）

**⚠ 新增分類時 OG 圖自動涵蓋**：category OG image（`app/[locale]/categories/[category]/opengraph-image.tsx`）和 event OG image（`app/[locale]/events/[id]/opengraph-image.tsx`）均動態呼叫 `getSemanticSymbol(category, ...)` — **新增 `organicMotifs.tsx` case 即自動支援，無需任何 OG 圖額外修改**。

**Fallback OG 圖分層規則：** `app/[locale]/opengraph-image.tsx` 是沒有分類標籤的一般頁面 fallback，必須沿用 `CategoryThumbnail` 的 `PALETTES`、FNV hash、`mulberry32`、背景 pattern、organic base blob、雙層 semantic symbol 邏輯，只替換 foreground motif 為台灣熱帶自然風物（雪線玉山、出海口溼地植物、颱風、太陽、蕉業）。一般頁面要是單頁單 motif，不可把五個 motif 同時拼進同一張圖；home、announcements、about、sources、saved、admin 這類頁面可以各自新增 segment-level `opengraph-image.tsx` 並用固定 page key 產圖。不要使用 runtime random，社群平台會快取第一次抓到的圖片；需要變化時使用 deterministic seed / page key。事件、分類、城市頁必須保留更深層的專屬 `opengraph-image.tsx`，且在 `generateMetadata()` 同步指定 `openGraph.images` 與 `twitter.images`，避免 Twitter 繼承 fallback。

**受保護頁 OG 圖規則：** `saved`、`admin` 這類登入保護頁若有 segment-level `opengraph-image.tsx`，`proxy.ts` 必須放行 `/(opengraph-image|twitter-image)$` metadata image route，否則分享平台抓圖會被 307 redirect 到登入頁。頁面 URL 本身仍可維持登入保護；若要讓社群平台讀到受保護頁的 `<meta>`，需要另設公開 preview/landing URL，不可直接放寬頁面內容。

**Rules:**
1. Satori 不支援 Tailwind class，**全部使用 inline `style={{}}`**。
2. 顏色來源只能是 `PALETTES` 陣列（8 種）；不可在 OG 圖中硬寫 hex。
3. `export const runtime = "edge"` 必須設定（Edge Runtime 限制見 engineer SKILL.md §OG Image）。
4. **型別定義必須先於使用**：`HeroObjectKey`、`MotifKey`、`SEMANTIC_OBJECT_RULES`、`renderHeroObject()` 必須在 `pickHeroObject()` 呼叫前定義。TS 不會在重設計 diff 中自動偵測跨文件型別缺失，必須整包 commit。
5. **OG PALETTES は CategoryThumbnail と週次同期**：`opengraph-image.tsx` の `PALETTES` は `CategoryThumbnail.tsx` の `PALETTES` の値に近似させること。デザインが乖離したら優先的に OG 側を合わせる（CategoryThumbnail が source of truth）。palette 更新後は `localhost:3000/.../opengraph-image` でビジュアル確認してから commit。

**⚠️ `export const size` 修改警示：**
`height` 改變後必須同步更新：
- 所有 `<svg width="1200" height="H" viewBox="0 0 1200 H">` 的 H 值
- 所有 `cornerShape` 的 `cx`/`cy`/`points`/`d` 座標（以 H 為基準的定位）
- 所有絕對定位元素（text block、mascot 等）的 `top`/`bottom`/`height`
- Pattern SVG 的 `rect height`

**Incident:** 2026-05-14 — working tree 只改 `height: 630→1200` 未同步版面，下半 570px 空白。`git restore` 還原。OG 圖必須做 local preview (`localhost:3000/.../opengraph-image`) 與 production 對比確認再 commit。

## Organic Motifs & Categorical Variants System (`organicMotifs.tsx`)

To keep UI components clean and provide visual variety, heavy SVG path definitions and geometries **must be extracted** into the `organicMotifs.tsx` system.

**Rules:**
1. **5 Sub-variants:** Each category should define 5 sub-variants of its motif. This ensures that lists of events under the same category avoid visual monotony.
2. **Layering:** Motifs layer organic SVG path geometries over background patterns.
3. **Extraction:** Never inline complex vector graphics directly into standard UI components. Always import them from the motif system.
4. **Verify in debug page:** After adding or editing any `case` in `getSemanticSymbol`, open `/debug/motifs` locally to visually confirm all 5 variants render correctly. Do not commit before visual review.
5. **Recognizability standard:** Without color, each motif must be identifiable within 2 seconds in a 100px viewBox. If a shape requires >6 path/shape elements, simplify.

**Implemented categories (as of 2026-05-16) — all 38:**

| Group | Categories |
|---|---|
| Core | `movie`, `performing_arts`, `senses`, `retail`, `nature`, `tech`, `tourism`, `lifestyle_food`, `books_media`, `gender`, `geopolitics`, `art`, `lecture`, `taiwan_japan`, `business`, `academic`, `competition`, `report` |
| Extended | `drama`, `documentary`, `tea_alcohol`, `parenting`, `scholarship`, `indigenous`, `folklore`, `history`, `urban`, `workshop`, `literature`, `design_craft`, `herbal`, `study_abroad`, `tv_program`, `radio_program`, `exhibition`, `taiwan_mandarin`, `healthcare`, `market` |

**⚠ Category Thumbnail Sync Rule (mandatory):** When a new category is added to `web/lib/types.ts` `CATEGORIES`, a corresponding `case` in `getSemanticSymbol` (`web/lib/design/organicMotifs.tsx`) **must be added in the same commit**. No exceptions. Missing cases fall through to the default blob and are invisible on debug page `/debug/motifs`.

Checklist for every new category:
1. `web/lib/types.ts` — Category union + CATEGORIES array + CATEGORY_GROUPS
2. `scraper/annotator.py` — VALID_CATEGORIES + SYSTEM_PROMPT enum + definition
3. `web/messages/{zh,en,ja}.json` — `categories.*` + `categoryDesc.*`
4. `web/lib/design/organicMotifs.tsx` — `case '<key>':` with 5 variants (airplane/globe/etc.) ↳ **automatically covers CategoryThumbnail + category OG image + event OG image** (all three call `getSemanticSymbol()` dynamically — no separate OG step needed)
5. Sync Guard — `python3 -c "from annotator import _check_category_sync; _check_category_sync()"` must pass

Add the new category slug to the Extended table above.

**Debug page convention:**
`app/[locale]/debug/motifs/page.tsx` must import `{ CATEGORIES }` from `@/lib/types` — **never maintain a separate hardcoded array**. A local copy silently drifts and hides missing motifs in production.

**Motif iteration cadence:**
Motif refinement typically requires 2–3 rounds of visual review. After each round, check all 5 variants in `/debug/motifs` locally. A motif passes when: (1) shape is identifiable without color within 2 seconds, (2) ≤6 path/shape elements, (3) all 5 variants are visually distinct from each other.

## MascotAvatar Component API

File: `web/lib/design/MascotAvatar.tsx`

```tsx
interface MascotAvatarProps {
  size?: number;                    // SVG size in px, default 80
  upright?: boolean;                // false = tilted 3°, true = straight
  antennaFlowAnimation?: boolean;   // energy-flow animation along antenna
  className?: string;
  title?: string;                   // accessible label
}
```

**Animation toggle pattern:**
- `antennaFlowAnimation` renders extra SVG layers + sets `data-antenna-flow="on"` on the `<svg>` root.
- CSS in `globals.css` targets `[data-antenna-flow="on"] .lianbu-antenna-flow-line` / `.lianbu-antenna-flow-dot`.
- Do NOT use inline `animation:` styles — use the data-attribute selector pattern for toggle control.

**SMIL vs CSS keyframe choice:**
- Circle pulse at antenna tip: CSS `@keyframes` with class selectors (`lianbu-tip-ring/core/spark`) — three separate layers allow independent timing without coupling.
- Stroke-dashoffset flow along path: CSS `@keyframes` via data-attribute selector (more flexible for timing sync).
- Path-following dot motion: SMIL `<animateMotion>` with `keyTimes` / `keyPoints` for dwell control.

**Tip flash pattern (three layers):**
```tsx
// In MascotBody: tag each tip circle with a semantic class
<circle className="lianbu-tip-ring" cx={164} cy={26} r={11} … />
<circle className="lianbu-tip-core" cx={164} cy={26} r={6}  … />
<circle className="lianbu-tip-spark" cx={164} cy={26} r={2.2} … />
```
```css
/* globals.css — each keyframe covers: 0% green → ~7% #C4E86F peak → 17% back to green */
@keyframes lianbu-tip-ring-flash { … }
@keyframes lianbu-tip-core-expand { … }  /* uses CSS scale() + transform-box:fill-box; Safari does NOT animate CSS r, so r-property keyframes silently freeze on Safari */
@keyframes lianbu-tip-spark-flash { … }
```
> ⚠️ **峰值色不可用純白 `#FFFFFF`** — 在 homepage 淺色背景（`#FFFDF5`）上完全隱形，無任何視覺 feedback。峰值色統一用品牌黃綠 `#C4E86F`。
> ⚠️ **`lianbu-tip-core-expand` 必須用 `scale()` 而非 CSS `r` 屬性動畫** — Safari 不支援 CSS `r` 動畫（`@keyframes { r: 6px → r: 10px }`），會靜默凍結在初始值。改用 `transform: scale()` 並加 `transform-box: fill-box; transform-origin: center` 確保跨瀏覽器縮放中心正確。

> ⚠️ **SVG `filter` + `opacity: 0` WebKit FBO 殘影** — `opacity: 0`（CSS 或 SVG attribute）不足以抑制 SVG filter 的渲染。WebKit/Safari 在離屏 FBO 渲染 filter 結果，`opacity` 合成在 FBO 之後；帶有 `filter` 屬性的 SVG 元素在隱藏時**必須同時使用 `visibility: hidden`**：
> - Element rule：`visibility: hidden` 與 `opacity: 0` 並列
> - Keyframes：可見期（通常 17–22%）設 `visibility: visible`，其餘設 `visibility: hidden`
> - SVG attribute：同步加 `visibility="hidden"` 作為 CSS 載入前的雙重防護（CSS animation specificity > SVG presentation attribute，`visibility: visible` keyframe 可正確覆寫）

> ⚠️ **Safari-only 偵測必須用 `@supports (-webkit-hyphens: none)`，不可用 `-webkit-touch-callout: none`** — `-webkit-touch-callout` 是 **iOS 專用**屬性，桌面 macOS Safari **不支援**，因此 `@supports (-webkit-touch-callout: none)` 對桌面 Chrome 與桌面 Safari **皆不成立**，整段規則靜默失效（曾連續 4 次微調 padding/translateY 完全無視覺變化）。正確偵測：
> - 桌面 + iOS Safari 都成立、Chrome 不成立的條件是 `@supports (-webkit-hyphens: none)`
> - 驗證方法（不要盲猜）：用 Chromium 跑 `CSS.supports('-webkit-touch-callout','none')` → `false`、`CSS.supports('-webkit-hyphens','none')` → `false`，確認 Chrome 被排除後再套用
>
> ⚠️ **Safari WebKit CJK 行高置中偏高 — 對齊修正會連帶影響子元素與兄弟元素，需逐一排除** — 用 Safari-only 非對稱 padding（`padding-top: calc(.375rem + 2px); padding-bottom: calc(.375rem - 2px)`）把膠囊/按鈕 CJK 文字往下推時，會連帶推動：
> - **flex 內已置中的子元素**（如 segmented tab 內的數字徽章）→ 用 `transform: translateY(-2px)` 推回，靠 `rounded-full` class 區分徽章 span 與文字 label span
> - **同選取器但無 CJK 文字的元素**（如 navbar `w-8 h-8` 的 SVG icon button）→ 在 `header button` 還原 `padding-top/bottom: 0 !important`
> - **未被選取器涵蓋的同類控制項**（如 `input[type="search"]` 的 placeholder）→ 需主動加進選取器，否則高度不一致
> - 通則：對齊 hack 套用後務必逐一檢視「子元素 / 同選取器無文字元素 / 漏網同類控制項」三類連帶影響

**Start-point dwell via SMIL keyTimes:**
```tsx
<animateMotion
  dur="12s"
  repeatCount="indefinite"
  path={antennaPathReverse}
  keyTimes="0;0.17;0.25;1"
  keyPoints="0;0;1;1"
  calcMode="linear"
/>
```
`keyPoints="0;0;1;1"` keeps the dot at position 0 (tip) from `t=0` to `t=0.17`, travels to position 1 (body) by `t=0.25`, then dwells at body until cycle reset.

**Direction reversal:** `animateMotion` follows the path *as written*. To reverse direction, reverse the path string coordinates — `antennaPathReverse` starts at the tip `M160,30` instead of the body `M100,80`. Do **not** use CSS `animation-direction: reverse` on SMIL-driven elements.

**SVG `overflow` for out-of-viewBox animation:** When `antennaFlowAnimation` is on, the dot travels outside the default viewBox. Add `overflow={antennaFlowAnimation ? "visible" : undefined}` to the `<svg>` root — without it the dot silently clips with no error.

**CSS duration and SMIL `dur` must stay in sync:** When changing animation speed, update BOTH the CSS `animation: lianbu-*` duration in `globals.css` AND the SMIL `dur` in `MascotAvatar.tsx`. Mismatched values cause desynchronized tip-flash and dot travel.

**`prefers-reduced-motion` checklist for new animation layers:**
- `lianbu-antenna-flow-line` → `animation: none`
- `lianbu-antenna-flow-dot` → `display: none`
- `lianbu-tip-ring`, `lianbu-tip-core`, `lianbu-tip-spark` → `animation: none`

**Adding new animation states:** add new CSS selector block under `[data-antenna-flow="on"]` in `globals.css`. Never hardcode animation values in the TSX file itself.

**Caller sync rule:** after adding any new optional animation prop to `MascotAvatar`, run `grep -r "MascotAvatar" web/` and explicitly decide whether each call site should enable the prop. Do not assume "optional = safe to ignore" — production pages that should show the animation will silently remain static otherwise.

## Motion and Interaction

**Default transition:** `transition-all duration-200 ease-out`
**Hover state:** color/border/shadow change only — never layout shift
**Active state:** subtle scale `active:scale-[0.98]` for tactile feedback
**Focus-visible:** `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2`

### When to add framer-motion

Only when **multiple components** would benefit. Examples that justify it:
- Page transitions
- Layout-shifting filters (FLIP animation)
- Drawer / modal entrance + exit
- Drag-to-reorder

For single-element micro-interactions, prefer Tailwind transitions.

### FloatingShapes motion constraints

Homepage full-mode `FloatingShapes` follows unique trails and size weight constraints to avoid overlap and noise:

- **Strictly Unique Trails**: Background slots are reduced to 8. Upon page mount, randomly shuffle the 8 drift directions (`DRIFTS`). Each slot is 1-to-1 uniquely assigned a direction. Subsequent cycles (`handleCycle`) preserve this original assigned path by inheriting `prev.drift`, ensuring no two shapes ever share a parallel overlapping trajectory.
- **Size Weight Limits**: Full background slot tier allocation is configured as `[0, 0, 1, 1, 2, 2, 3, 4]`. This limits large (tier 3) and largest (tier 4) geometries to at most 1 each simultaneously, preventing screen congestion.
- **Natural Mid-journey Start**: At initial page mount, shapes have `initialPhase = Math.random() * duration` (0% to 100% of their lifespan), turning into a negative delay. This allows shapes to appear pre-scattered across the viewport upon page load, rather than simultaneously emerging from the edges in a rigid lineup. Subsequent cycles reset delay to JST J-start edges.
- **Subtle Variant Trail Unification**: The inner-page subtle variant (randomly 2–6 floaters) similarly maps shuffled `DRIFTS` using modulo limits and preserves `prev.drift` on cycle to guarantee a noise-free overlay.

### Reduced motion

```tsx
className="transition-all duration-200 motion-safe:hover:scale-105 motion-reduce:transition-none"
```

Or via media query in `globals.css`:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

## Dark Mode Workflow

1. Make change in light mode first.
2. Open browser DevTools → toggle `:root.dark` class via console: `document.documentElement.classList.toggle("dark")`
3. Visually verify:
   - Text contrast (no `text-fg-subtle` on `bg-elevated` for body copy — too low)
   - Borders visible (avoid `border-line` on `bg-bg` — same color)
   - Brand color still pops
   - Form controls readable (test with actual typing)
4. Test theme persistence: toggle, refresh, confirm theme stuck.
5. Test system fallback: clear `localStorage.ttr_theme`, refresh, confirm follows OS.

## Recraft API Pipeline (Future Phase)

> **Status:** Not yet implemented. When user activates this work, follow this design.

### Use cases

1. **Article hero images** — for `announcements/*` posts when no manual image provided
2. **OG card backgrounds** — abstract Taiwan-themed visuals for social sharing
3. **Category illustrations** — one per category for `/categories/[category]` pages

### Architecture (proposed)

```
[Admin creates announcement] → [check image_ja/zh/en is null]
   → [POST to /api/recraft/generate with prompt + style preset]
   → [Recraft returns image URL] → [download + upload to Supabase Storage]
   → [save Storage URL to DB]
```

### Required env

- `RECRAFT_API_KEY` — added to `scraper/.env` (NOT `web/.env.local` if generation is admin-triggered server-side)
- Add to `secret_reminder.py` rotation list
- Document in `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` (or split secrets doc)

### Style presets (to define)

- `taiwan_cultural` — vibrant, festival-inspired, paper-cut motif
- `modern_tech` — minimal, gradient, geometric
- `editorial_photo` — clean, news-style, muted palette

### Cost discipline

- Cache by `prompt_hash + style_preset` in DB — never regenerate the same image
- Hard cap: 1 generation per announcement, max 5 retries on bad output
- Admin-only trigger; no auto-generate on every event

### Safety

- Image moderation: pass through Recraft's built-in NSFW filter
- Manual approve in `/admin/announcements/[id]` before publish
- Watermark "Generated" tag in admin UI (not public)

## Checklist Before Handoff to Engineer

- [ ] All affected components identified
- [ ] Token catalog used (no raw `bg-white`/`text-gray-*`)
- [ ] All i18n keys listed with zh/en/ja text
- [ ] Light + dark mode both verified mentally
- [ ] All interactive states defined (default, hover, focus, active, disabled, loading, empty, error)
- [ ] Motion timing & easing specified
- [ ] Accessibility: focus ring, ARIA, contrast ratio noted
- [ ] Spec saved to `/memories/session/design.md`
