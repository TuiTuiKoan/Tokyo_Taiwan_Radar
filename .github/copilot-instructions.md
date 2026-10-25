# Tokyo Taiwan Radar — Copilot Instructions

## Communication Language

Unless the user explicitly requests otherwise, **always respond in Traditional Chinese (繁體中文)**.
This applies to all agents (Researcher, Architect, Engineer, Scraper Expert, Tester, etc.).

## Progress Tracking: Board, Specs and Issues（進度追蹤）

The progress entry is the GitHub Project **TTR Roadmap**: https://github.com/users/TuiTuiKoan/projects/1 . Follow this split without being reminded:

- **Where things stand** lives on the board. Each card is an issue; Status is progress.
- **Why, what, non-goals, design and up to ten milestones** live in `docs/specs/active/<slug>/`. `tasks.md` holds milestones only.
- **Sub-tasks, review findings, bugs and follow-ups found along the way** become GitHub issues labeled `spec:<slug>`, not new lines in `tasks.md`. Create the label first if it is missing: `gh label create "spec:<slug>" --color 1D76DB --description "Work tracked by this spec"`. The board's Auto-add workflow picks up new open issues.
- Work that belongs to no spec is still an issue, just without a spec label.
- When reporting back, list the links of issues you opened.
- Tick a milestone in `tasks.md` and commit when it is done; a sub-task is done when its issue is closed.
- Existing checkboxes already in a `tasks.md` stay as they are; only new sub-tasks go to issues.
- Leftover work when a spec closes or pauses: independent items become issues (group them by theme with a checklist) and the parked file notes which issues took them; an ordered runbook with user approval gates stays in `docs/specs/parked/<slug>-followups.md`, with one card on the board linking to it.
- The same rule lives in `AGENTS.md` for Claude Code and Codex; change both together.

## Event Link Output Rule

When listing events in chat, never output event IDs alone.
Always include a clickable event page URL for each event in this format:

`https://tokyotaiwanradar.com/ja/events/<event_id>`

If locale is explicitly requested, replace `ja` with the requested locale.

## Handing Steps to the User（交接給使用者）

Whenever the user has to act (run a command, open a new session or terminal, look at a file, act on a website, approve), follow `.github/instructions/handoff.instructions.md`: one handoff card per step stating where to run it, the absolute directory, a copy-ready command that does not depend on earlier shell state, the expected result, what to do on failure, the risk level, and where to come back. Name sessions as "auto title (first 8 chars of the session ID)", never by an internal ListAgents name. Files and URLs are clickable links. The same pointer lives in `AGENTS.md`; change both together.

## Autonomy and Human Gates（自主程度與人類關卡）

The user is not a software professional and relies on the recommended default. Their job is only to **verify results** (PRs, the site, the data) and to **correct imprecise input** (open an issue, comment on a PR, change a label). Everything else the agent decides and records. Design and trial record: `docs/specs/active/agent-autonomy/`.

- Design details, slugs, worktree choice, model and effort, trial parameters: take the recommended value (usually "smallest scope first, watch for a few days"), write the decision and one line of reasoning into the spec proposal or an issue, do not ask.
- Hand-off to Codex for plan review or implementation: run `codex exec` yourself (commands in `AGENTS.md`), do not ask; if Codex cannot start, do the work yourself and say "not delegated".
- Creating a worktree, pushing a feature branch, opening a PR, creating issues and labels: do it and mention it in one sentence.
- Stop only at a human gate: merging to `main` (Tier 1 and Tier 2 PRs; agents never push `main` or run `gh pr merge`; Tier 0 merges by workflow), production data writes, permission or guard changes (`.claude/settings.json`, hooks, repo settings, secrets), irreversible actions, spending money or adding services, input that needs human judgement (annotation, ground truth, scope), public posts.
- Pushing: `git push -u origin <branch>` from the worktree, then `gh pr create` with what changed, how it was verified, NOT TESTED items and `Refs`/`Closes #n`, label `spec:<slug>`. The PR Tier workflow labels it; for Tier 1 and 2 hand the user one card with the PR link, the tier and what to look at.

The same rule lives in `AGENTS.md`; change both together.

## Project overview

Tokyo Taiwan Radar aggregates Taiwan-related cultural events **anywhere in Japan（全日本）**,
scraped from multiple sources, stored in Supabase, and displayed on a
trilingual Next.js web app.

> **Geographic Scope**: Events in Tokyo, Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope. Do NOT reject an event or source solely because it is outside Tokyo.
>
> **Taiwan-based events are also in scope** when they are organized specifically for Japanese audiences or by Japan-based organizations for Japan↔Taiwan exchange (e.g., study tours, cultural immersion programs, academic exchanges targeting Japanese participants). These represent the "go to Taiwan" side of Japan-Taiwan cultural exchange and are a valid part of the project's mission.
>
> **However, Japan→Taiwan commercial expansion is OUT of scope**: a Japanese brand/company holding a promotional event **in Taiwan for Taiwanese consumers (B2C)** — product pop-ups, brand launches, overseas-expansion (輸出/進出) dinners — or **exhibiting at a Taiwan trade show (B2B)** is NOT a Japan event, even if the title contains 台湾 and 開催. The in-scope exceptions above still apply: study tours, Japanese-participant auditions/programs, and Japan↔Taiwan official or cultural exchange (e.g. events hosted by 日本台湾交流協会) remain in scope. Judge by **who the event is for** — Japanese participants = in scope; Taiwanese consumers or B2B = out of scope — not by title keywords.

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
| Scraper | Python 3.12, Playwright 1.51, OpenAI ≥1.30 |
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
