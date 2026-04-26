# Tokyo Taiwan Radar — Copilot Instructions

## Communication Language

Unless the user explicitly requests otherwise, **always respond in Traditional Chinese (繁體中文)**.
This applies to all agents (Researcher, Architect, Engineer, Scraper Expert, Tester, etc.).

## Project overview

Tokyo Taiwan Radar aggregates Taiwan-related cultural events **anywhere in Japan（全日本）**,
scraped from multiple sources, stored in Supabase, and displayed on a
trilingual Next.js web app.

> **Geographic Scope**: Events in Tokyo, Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope. Do NOT reject an event or source solely because it is outside Tokyo.

- GitHub: TuiTuiKoan/Tokyo_Taiwan_Radar (main branch)
- Supabase project: cjtndektjjpvvjofdvzr
- Deploy: Vercel (web), GitHub Actions daily cron (scraper)

## Repository layout

```
.github/
  workflows/scraper.yml   Daily 09:00 JST scraper cron
  copilot-instructions.md This file — global Copilot context
scraper/
  sources/                One file per data source, all extend BaseScraper
    base.py               Event dataclass + BaseScraper ABC
    taiwan_cultural_center.py
    peatix.py
  main.py                 Orchestrator — flags: --dry-run, --source NAME
  annotator.py            OpenAI GPT-4o-mini annotation pipeline
  database.py             Supabase upsert helpers
  requirements.txt        playwright==1.51, supabase==2.28.3, openai>=1.30
supabase/
  migrations/             001–005 SQL migrations (run via Supabase Dashboard)
web/
  app/[locale]/           Localized routes — zh (default), en, ja
  components/             EventCard, FilterBar, Navbar, AdminEventTable, …
  lib/types.ts            Shared TypeScript types: Event, Category, Locale
  messages/               i18n strings: zh.json, en.json, ja.json
```

## Tech stack

| Layer | Technology |
|-------|------------|
| Web framework | Next.js 16.2.4, React 19, TypeScript, Tailwind CSS 4 |
| i18n | next-intl 4.9.1 — locales: `zh` (default), `en`, `ja` |
| Auth + DB | Supabase — `@supabase/ssr` 0.10.2 |
| Scraper | Python 3.12, Playwright 1.51, OpenAI ≥1.30, DeepL 1.21 |
| CI | GitHub Actions — daily 09:00 JST (`scraper.yml`) |
| Deploy | Vercel (web), GitHub Actions (scraper) |

> **Warning:** Next.js 16 has breaking changes vs common training data.
> Read `node_modules/next/dist/docs/` before writing any web code.
> Heed all deprecation notices in the output.

## Categories

Canonical list defined in `web/lib/types.ts` as `Category` type and `CATEGORIES` array:

`movie` · `performing_arts` · `senses` · `retail` · `nature` · `tech`
· `tourism` · `lifestyle_food` · `books_media` · `gender` · `geopolitics`
· `art` · `lecture` · `taiwan_japan` · `business` · `academic` · `competition` · `report`

## Scraper conventions

- Every source extends `BaseScraper` and implements `scrape() → list[Event]`
- Register new scrapers in `scraper/main.py` → `SCRAPERS = [...]`
- `source_name`: snake_case, unique per source (e.g. `peatix`, `taiwan_cultural_center`)
- `source_id`: must be stable across runs — used for upsert dedup
- `raw_title` + `raw_description`: original scraped text, never overwritten
- `selection_reason`: stored as JSON string `{"ja":"…","zh":"…","en":"…"}`
- Sub-events set `parent_event_id`; the homepage filters them out with `.is("parent_event_id", null)`
- Test without DB writes: `python main.py --dry-run [--source NAME]`

## Database conventions

- `annotation_status`: `pending` → becomes `annotated` after `annotator.py` runs
- Migrations are numbered `001`–`005`; run in order via Supabase Dashboard SQL editor
- Latest migration: `005_category_corrections.sql`

## i18n conventions

- Default locale: `zh`; fallback chain for display: locale → `ja` → `zh` → `en`
- Locale helpers in `web/lib/types.ts`: `getEventName(event, locale)`, `getEventDescription(event, locale)`
- Add new strings to all three `messages/*.json` files simultaneously

## Adding a new scraper source

1. Create `scraper/sources/<source_name>.py` extending `BaseScraper`
2. Register it in `scraper/main.py` → `SCRAPERS`
3. Test: `python main.py --dry-run --source <source_name>`
4. Confirm `start_date` is populated (not falling back to publish date)
5. Commit; the daily CI will pick it up automatically
