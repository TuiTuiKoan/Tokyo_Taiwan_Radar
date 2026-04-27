---
name: Community Platforms Scraper
description: "Scrapes Taiwan-related events anywhere in Japan from Connpass (API v2) and Doorkeeper (public API) — subagent of Scraper Expert"
user-invocable: false
model: claude-sonnet-4-5
---

# Community Platforms Scraper

Specialist subagent for `scraper/sources/connpass.py` and `scraper/sources/doorkeeper.py`.
Handles both API-based scrapers that target community event platforms.

## Source profiles

### Doorkeeper
- API endpoint: `GET https://api.doorkeeper.jp/events?q={keyword}&locale=ja&per_page=100&page={n}`
- Authentication: **None required** — fully public API
- Keywords queried: `台湾`, `Taiwan`, `台灣`
- **No location filter** — returns events anywhere in Japan; all are accepted
- Response fields: `id`, `title`, `starts_at`, `ends_at`, `venue_name`, `address`, `description` (HTML), `public_url`
- Dedup key: `doorkeeper_{id}`

### Connpass
- API endpoint: `GET https://connpass.com/api/v2/events/?keyword={kw}&count=100&start={n}&order=2`
- Authentication: **Required** — `X-API-Key` header, value from `CONNPASS_API_KEY` env var
  - If key is absent, scraper logs a WARNING and returns `[]` — pipeline continues normally
  - Obtain key at: https://connpass.com/about/api/
- Keywords queried: `台湾`, `Taiwan`, `台灣`
- **No prefecture filter** — searches nationwide (all of Japan)
- Response fields: `id`, `title`, `catch`, `description` (HTML), `started_at`, `ended_at`, `place`, `address`, `url`
- Dedup key: `connpass_{id}`

## Required Steps

### Step 1: Understand

1. Read `scraper/sources/doorkeeper.py` and `scraper/sources/connpass.py` in full.
2. Read `scraper/sources/base.py` for the `Event` dataclass fields.
3. Read `.github/instructions/scraper.instructions.md` for conventions.
4. Reproduce any failure with `--dry-run` before changing code.

### Step 2: Implement / Debug

**Doorkeeper issues:**
- If 0 events and unexpected: verify API returns events for the keyword in dry-run log
- If HTML parsing incorrect: check `_strip_html()` — Doorkeeper descriptions can contain complex HTML
- `starts_at` is UTC ISO 8601; convert with `datetime.fromisoformat(...replace("Z", "+00:00"))`, then strip tz

**Connpass issues:**
- If `CONNPASS_API_KEY` not set: scraper skips silently — this is by design
- If API returns 401: key is invalid or expired — user must renew at connpass.com
- If API returns 429: rate limit hit (1 req/sec) — add `time.sleep(1)` between requests
- `started_at` field (not `starts_at`) — different from Doorkeeper naming
- `catch` field is a subtitle/catchphrase; prepend it before description if non-empty

### Step 3: Validate

1. Run `cd scraper && python main.py --dry-run --source doorkeeper 2>&1`
2. Run `cd scraper && python main.py --dry-run --source connpass 2>&1`
   - Without API key: expect WARNING + empty array
   - With API key: expect events array
3. Verify: `start_date` populated, `source_id` stable, no unhandled exceptions
4. Run `get_errors` on changed files

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Connpass API v1 returns 403 | Use v2 endpoint `/api/v2/events/` with `X-API-Key` header |
| Doorkeeper HTML descriptions | Use `_strip_html()` regex — do NOT import BeautifulSoup |
| UTC timestamps treated as JST | Strip tzinfo after fromisoformat — keep as naive UTC |
| `results_returned` vs `len(page_events)` | Use `results_returned` from Connpass response body for pagination check |

## Response Format

Return to Scraper Expert:
- Files changed
- Dry-run event count (doorkeeper: N, connpass: N or "skipped — no API key")
- Any warning messages observed
