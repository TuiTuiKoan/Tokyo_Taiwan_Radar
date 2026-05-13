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

## OG Image 規範（`opengraph-image.tsx`）

Current design (as of 2026-05-14, commit `ef305d3`):

- **Size:** 1200×1200 正方形（優於 1200×630 的跨平台相容性）
- **Background:** `CATEGORY_PALETTE[category].bg`（CategoryThumbnail 的色彩系統，`web/lib/design/CategoryThumbnail.tsx`）
- **Layout:** 事件圖片佔左側 65% 寬，右欄 35% 含標題 + meta
- **Right-bottom:** wax-apple 吉祥物 SVG（body color = `palette.fg`）+ 品牌名稱
- **Fonts:** Noto Sans JP（inline fetch from Google Fonts API）

**Rules:**
1. Satori 不支援 Tailwind class，**全部使用 inline `style={{}}`**。
2. 顏色來源只能是 `CATEGORY_PALETTE`；不可在 OG 圖中硬寫 hex。
3. `export const runtime = "edge"` 必須設定（Edge Runtime 限制見 engineer SKILL.md §OG Image）。
4. 更改 OG 圖設計時，同步更新 `CategoryThumbnail.tsx` 的 `CATEGORY_PALETTE` 若有新 category。



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
