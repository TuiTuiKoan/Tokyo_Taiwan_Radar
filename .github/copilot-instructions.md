# Tokyo Taiwan Radar — Copilot Instructions

## Communication Language

Unless the user explicitly requests otherwise, **always respond in Traditional Chinese (繁體中文)**.
This applies to all agents (Researcher, Architect, Engineer, Scraper Expert, Tester, etc.).

## Project overview

Tokyo Taiwan Radar aggregates Taiwan-related cultural events **anywhere in Japan（全日本）**,
scraped from multiple sources, stored in Supabase, and displayed on a
trilingual Next.js web app.

> **Geographic Scope**: Events in Tokyo, Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope. Do NOT reject an event or source solely because it is outside Tokyo.
>
> **Taiwan-based events are also in scope** when they are organized specifically for Japanese audiences or by Japan-based organizations for Japan↔Taiwan exchange (e.g., study tours, cultural immersion programs, academic exchanges targeting Japanese participants). These represent the "go to Taiwan" side of Japan-Taiwan cultural exchange and are a valid part of the project's mission.

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
  app/[locale]/           Localized routes — ja (default), zh, en
  components/             EventCard, FilterBar, Navbar, AdminEventTable, …
  lib/types.ts            Shared TypeScript types: Event, Category, Locale
  messages/               i18n strings: zh.json, en.json, ja.json
```

## Tech stack

| Layer | Technology |
|-------|------------|
| Web framework | Next.js 16.2.4, React 19, TypeScript, Tailwind CSS 4 |
| i18n | next-intl 4.9.1 — locales: `ja` (default), `zh`, `en` |
| Auth + DB | Supabase — `@supabase/ssr` 0.10.2 |
| Scraper | Python 3.12, Playwright 1.51, OpenAI ≥1.30, DeepL 1.21 |
| CI | GitHub Actions — daily 09:00 JST (`scraper.yml`) |
| Deploy | Vercel (web), GitHub Actions (scraper) |

> **Warning:** Next.js 16 has breaking changes vs common training data.
> Read `node_modules/next/dist/docs/` before writing any web code.
> Heed all deprecation notices in the output.

## Mascot — Lianbu (蓮霧 / 小霧 / レンブ)

| Language | Name | Notes |
|----------|------|---------|
| English | **Lianbu** | Always use this romanization — never "Renbu" or "Lianwu" |
| English (nickname) | **Bubu** | Cute short form of Lianbu — use where 小霧 / レンブちゃん appears |
| Traditional Chinese | **蓮霧** or **小霧** | 蓮霧 (wax apple) is the full name; 小霧 is the affectionate short form used in UI |
| Japanese | **レンブ** or **レンブちゃん** | Katakana transliteration; add ちゃん for warmth |

> **Rule**: Whenever the mascot name appears in code, comments, UI strings, docs, or agent instructions,
> use the correct language-specific form above. The English form is always **Lianbu** — never Renbu.
> The affectionate nickname (小霧 / レンブちゃん) is **Bubu** in English.

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
- **Default Fallbacks (預設回退政策)**:
  - 當 `business_hours` 為空時的前端回退：如果 `official_url` 或 `source_url` 存在，前端各語言會顯示 `「請參照原始來源」` 並附上超連結。
  - 電影院類別（`event_form` 含有 `screening` 或 `screening_with_talk`，或 `category` 是 `movie`，或 `source_name` 符合電影院來源（如 `cinema`, `cinemart`, `cineswitch`, `eurospace`, `human_trust`, `bungeiza`, `cinemarine`, `morc`））：
    - 若 `is_paid` 為空，且**非**台灣文化中心（`source_name="taiwan_cultural_center"` 或 organizer 含有台灣文化中心）主辦，設定其在 `annotator.py` 自帶 `is_paid = True`（有料）預設。
    - 若 `is_paid` 為 `True` 且 `price_info` 為空白，預設寫入 `price_info = "有料"`。

## Database conventions

- `annotation_status`: `pending` → becomes `annotated` after `annotator.py` runs
- Migrations are numbered `001`–`005`; run in order via Supabase Dashboard SQL editor
- Latest migration: `005_category_corrections.sql`

## i18n conventions

- Default locale: `ja`; fallback chain for display: locale → `ja` → `zh` → `en`
- Locale helpers in `web/lib/types.ts`: `getEventName(event, locale)`, `getEventDescription(event, locale)`
- Add new strings to all three `messages/*.json` files simultaneously

## Adding a new scraper source

1. Create `scraper/sources/<source_name>.py` extending `BaseScraper`
2. Register it in `scraper/main.py` → `SCRAPERS`
3. Test: `python main.py --dry-run --source <source_name>`
4. Confirm `start_date` is populated (not falling back to publish date)
5. Commit; the daily CI will pick it up automatically
