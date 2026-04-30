---
applyTo: "web/**"
---

# Web — Coding Instructions

> **CRITICAL:** This is Next.js 16.2.4 with React 19. It has breaking changes vs common training
> data. Read `node_modules/next/dist/docs/` before writing any web code. Heed all deprecation
> notices in compiler output.

## Stack

- **Next.js 16.2.4** — App Router, TypeScript
- **React 19**
- **Tailwind CSS 4**
- **next-intl 4.9.1** — i18n
- **Supabase** — `@supabase/ssr` 0.10.2

## Directory structure

```
web/
  app/
    layout.tsx          Root layout (no locale)
    [locale]/           Locale-scoped routes
      layout.tsx        Sets locale for next-intl
      page.tsx          Event listing (homepage)
      events/[id]/      Event detail
      admin/            Admin CRUD interface
      auth/             Login / sign-up
      saved/            User saved events
  components/
    EventCard.tsx
    FilterBar.tsx
    Navbar.tsx
    AdminEventTable.tsx
    RawDataSection.tsx
    SaveButton.tsx
  lib/
    types.ts            Event, Category, Locale types + helpers
  messages/
    zh.json             Default locale strings
    en.json
    ja.json
  i18n.ts               next-intl config (default locale: zh)
```

## i18n rules

- Default locale: `zh`; supported locales: `zh`, `en`, `ja`
- Fallback chain when displaying event content: `locale → ja → zh → en`
- Use `getEventName(event, locale)` and `getEventDescription(event, locale)` from `web/lib/types.ts`
- Add new UI strings to **all three** `messages/*.json` files at the same time
- The `[locale]` segment is required in every page path — never create pages outside it
- **Translation hook namespaces** — before adding a `tXxx("key")` call, verify the namespace exists in `messages/zh.json`. Wrong namespace silently returns the raw key string with no build error.

  | Hook call | Namespace in messages/*.json | Used for |
  |-----------|------------------------------|----------|
  | `useTranslations()` | top-level keys | General UI (name, category, filterAll, …) |
  | `useTranslations("event")` | `event.*` | Event-specific strings (free, paid, online, categories) |
  | `useTranslations("admin")` | `admin.*` | Admin-only strings (edit, delete, approve, …) |

  There is no `tFilters` namespace — use the top-level `t()` for filter labels.

## Type conventions

- Import `Event`, `Category`, `Locale`, `CATEGORIES`, `getEventName`, `getEventDescription` from `@/lib/types`
- `Event.category` is `string[]` — always guard with `CATEGORIES` membership before display
- `Event.selection_reason` is a JSON string `{"ja":"…","zh":"…","en":"…"}` — parse before display
- Dates are ISO 8601 strings from Supabase; format with `toLocaleDateString(locale)` or a date lib

## Supabase client

- Use `@supabase/ssr` helpers, not the bare JS client
- Sub-events are hidden from the homepage with `.is("parent_event_id", null)`
- Only show events where `annotation_status = 'annotated'` on public pages (admin may show all)

## Categories

`movie` · `performing_arts` · `senses` · `retail` · `nature` · `tech`
· `tourism` · `lifestyle_food` · `books_media` · `gender` · `geopolitics`
· `art` · `lecture` · `taiwan_japan` · `business` · `academic` · `competition` · `report`

These map 1-to-1 with `Category` type in `lib/types.ts`. Do not add new values.

## Tailwind CSS 4

Tailwind 4 uses a CSS-first config — there is no `tailwind.config.js`. Use `@theme` blocks in
`globals.css` for customizations. Standard utility classes work as expected.

## SEO — robots / sitemap / generateMetadata

### Static route handlers (robots.ts, sitemap.ts) — plain Supabase client
`app/robots.ts` and `app/sitemap.ts` are static route handlers with no request context.
**Never use `createClient` from `@/lib/supabase/server`** (which calls `cookies()`) — it throws at runtime.
Use `createClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)` directly.

### generateMetadata vs static metadata
`export const metadata` and `export async function generateMetadata` **cannot coexist** in the same file.
When converting to `generateMetadata`, delete the old static `export const metadata` — Next.js 16 silently prefers the static version with no warning.

### Locale-aware site name
| locale | value |
|--------|-------|
| `zh` | 東京台灣雷達 |
| `ja` | 東京台湾レーダー |
| `en` | Tokyo Taiwan Radar |

Use this mapping in `title.template`, OG `siteName`, and Twitter card — never hardcode a single language.

### x-default hreflang
Always include `"x-default": /zh/...` in `alternates.languages` pointing to the default locale.

### NEXT_PUBLIC_SITE_URL fallback
All metadata files that construct absolute URLs must use:
```ts
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app"
```

## i18n — Hardcoded string rules

> **CRITICAL: Never hardcode CJK (Chinese/Japanese/Korean) text or any user-visible string in TSX/TS files.**

- All UI strings MUST go through `t()`, `tFilters()`, `tCat()`, `tEvent()`, or equivalent `useTranslations()` / `getTranslations()` calls.
- **Module-level consts** that contain UI text cannot use `useTranslations()` (React hook rules). Either:
  - Move the const inside the component function body, OR
  - Pass the translation function as a typed parameter (e.g., `type TFn = (key: string) => string`).
- **Footer and layout**: `app/[locale]/layout.tsx` footer text must use `getTranslations("general")`, not hardcoded strings.
- **Admin error banners**: Any hardcoded Chinese/Japanese error text in admin pages must use `getTranslations("admin")` or `getTranslations("general")`.
- After writing any TSX with visible text, verify with: `grep -rn '[\u4e00-\u9fff]' web --include='*.tsx' | grep -v 't(' | grep -v 'MARKERS' | grep -v '//'`
- Every new message key must be added to **all three** `messages/zh.json`, `messages/en.json`, and `messages/ja.json` simultaneously.
