---
name: community-platforms
description: "Rules and reference for Connpass and Doorkeeper API scrapers in Tokyo Taiwan Radar"
---

# Community Platforms Skill

Authoritative rules for `scraper/sources/connpass.py` and `scraper/sources/doorkeeper.py`.

## Platform Overview

| Platform | API | Auth | Tokyo filter |
|----------|-----|------|--------------|
| Doorkeeper | `https://api.doorkeeper.jp/events` | None (public) | Client-side on `address` + `venue_name` |
| Connpass | `https://connpass.com/api/v2/events/` | `X-API-Key` header | Server-side `prefecture=tokyo` param |

## Connpass Setup

1. Register for an API key at https://connpass.com/about/api/
2. Add to `scraper/.env`: `CONNPASS_API_KEY=<your_key>`
3. The scraper silently skips with a WARNING if the key is absent — no pipeline failure

## Tokyo Location Filter Rules (Doorkeeper)

The Doorkeeper API has no built-in prefecture filter. Location filtering is done client-side.

**Safe markers** (add to `_TOKYO_MARKERS`):
- `東京都` — full prefecture name
- `東京` — substring match catches all 東京都 addresses

**Conditionally safe** — only if provably unique to Tokyo:
- `渋谷区`, `新宿区`, `豊島区`, `千代田区`, `港区` (大阪・神戸 do not have these)

**Never add** — exist in multiple cities:
- `中央区`, `南区`, `北区`, `西区`, `東区` — common across Japan

## Keyword Strategy

Both scrapers search across three keyword passes to maximise recall:

```python
SEARCH_QUERIES = ["台湾", "Taiwan", "台灣"]
```

Results are deduplicated by platform event ID before building `Event` objects.

## Field Mapping

### Doorkeeper → Event
| API field | Event field | Notes |
|-----------|-------------|-------|
| `id` | `source_id` | `f"doorkeeper_{id}"` |
| `title` | `name_ja`, `raw_title` | |
| `starts_at` | `start_date` | UTC ISO 8601; strip tzinfo |
| `ends_at` | `end_date` | UTC ISO 8601; strip tzinfo |
| `venue_name` | `location_name` | |
| `address` | `location_address` | |
| `description` (HTML) | `raw_description` | Strip HTML; prepend `開催日時: …` |
| `public_url` | `source_url` | |

### Connpass → Event
| API field | Event field | Notes |
|-----------|-------------|-------|
| `id` | `source_id` | `f"connpass_{id}"` |
| `title` | `name_ja`, `raw_title` | |
| `started_at` | `start_date` | Note: `started_at`, not `starts_at` |
| `ended_at` | `end_date` | |
| `place` | `location_name` | |
| `address` | `location_address` | |
| `catch` + `description` | `raw_description` | catch = subtitle; prepend date, then catch, then description |
| `url` | `source_url` | |

## raw_description Convention

Always prepend the event date per scraper conventions:

```python
date_prefix = f"開催日時: {start_dt.strftime('%Y年%m月%d日')}\n\n"
raw_description = date_prefix + desc_text
```

For Connpass, also include the `catch` (subtitle) between date and description:

```python
raw_description = date_prefix
if catch:
    raw_description += f"{catch}\n\n"
raw_description += desc_text
```

## Pagination

**Doorkeeper**: `page=1,2,...` — stop when `len(response) < per_page` (empty = no more)

**Connpass**: `start=1,101,201,...` — stop when `results_returned < count`

Both scrapers cap at `MAX_PAGES = 5` per keyword as a safety limit.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Doorkeeper: 0 events | No Tokyo events right now | Normal — platform coverage varies |
| Doorkeeper: non-Tokyo events | Overly broad `_TOKYO_MARKERS` | Remove ambiguous ward names |
| Connpass: WARNING + 0 events | `CONNPASS_API_KEY` not set | Add key to `.env` |
| Connpass: HTTP 401 | Invalid/expired API key | Renew at connpass.com |
| Connpass: HTTP 429 | Rate limit exceeded | Add `time.sleep(1)` between requests |
| Connpass: HTTP 403 on `/api/v1/` | v1 is deprecated | Use v2 endpoint only |
