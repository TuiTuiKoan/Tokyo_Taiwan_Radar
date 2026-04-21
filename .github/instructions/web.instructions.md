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
· `art` · `lecture` · `report`

These map 1-to-1 with `Category` type in `lib/types.ts`. Do not add new values.

## Tailwind CSS 4

Tailwind 4 uses a CSS-first config — there is no `tailwind.config.js`. Use `@theme` blocks in
`globals.css` for customizations. Standard utility classes work as expected.
