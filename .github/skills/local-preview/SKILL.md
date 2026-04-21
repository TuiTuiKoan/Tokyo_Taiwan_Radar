---
name: local-preview
description: "Run scrapers and web app locally without deploying — preview results before any DB or Vercel push"
---

# Local Preview

Run the full Tokyo Taiwan Radar stack locally so you can see results immediately — no deploy required.

## Prerequisites

- **Scraper**: Python 3.12 venv activated, `scraper/.env` populated
- **Web**: Node.js ≥20, `web/.env.local` populated with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Quick Start

```bash
# Preview scraper output (no DB writes):
bash .github/skills/local-preview/scripts/preview-scraper.sh

# Preview one source only:
bash .github/skills/local-preview/scripts/preview-scraper.sh taiwan_cultural_center

# Start web dev server:
bash .github/skills/local-preview/scripts/preview-web.sh
```

## Scraper Preview

The `--dry-run` flag scrapes all sources and prints JSON to stdout without writing to Supabase or calling the AI annotator.

```bash
cd scraper
source ../venv/bin/activate

# All sources:
python main.py --dry-run

# One source:
python main.py --dry-run --source taiwan_cultural_center
python main.py --dry-run --source peatix

# Pretty-print the first 3 events:
python main.py --dry-run --source taiwan_cultural_center | python -m json.tool | head -120
```

**What `--dry-run` does:**
- Runs all scrapers (Playwright, HTTP requests)
- Prints a JSON array of `Event` objects to stdout
- Logs progress to stderr
- Does **NOT** write to Supabase
- Does **NOT** call OpenAI or DeepL

## Web Dev Server

The Next.js app reads from the live Supabase DB. Run the dev server to preview UI changes instantly.

```bash
cd web
npm run dev
# Open http://localhost:3000
```

For a specific locale: `http://localhost:3000/zh`, `http://localhost:3000/en`, `http://localhost:3000/ja`

## Parameters Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Skip DB writes and AI annotation; print JSON to stdout |
| `--source <name>` | all | Run only the named scraper source |

Available source names: `taiwan_cultural_center`, `peatix`

## Script Reference

```bash
# Scraper dry-run (one or all sources):
bash .github/skills/local-preview/scripts/preview-scraper.sh [source_name]

# Web dev server:
bash .github/skills/local-preview/scripts/preview-web.sh
```

## Troubleshooting

**`ModuleNotFoundError`** — Virtual environment not activated. Run `source venv/bin/activate` from the repo root first.

**Playwright browser not found** — Run `playwright install chromium` inside the activated venv.

**Web shows no events** — The dev server reads from Supabase. Ensure `web/.env.local` has correct `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

**Empty scraper output** — The source may return 0 events in dry-run if the site is unreachable or selectors changed. Check stderr logs for errors.
