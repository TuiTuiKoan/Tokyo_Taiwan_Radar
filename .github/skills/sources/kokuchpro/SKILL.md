---
name: kokuchpro
description: "Platform rules, search URL structure, hCard address extraction, and date parsing for the こくちーずプロ (Kokuchpro) scraper"
applyTo: scraper/sources/kokuchpro.py
---

# こくちーずプロ (Kokuchpro) Scraper

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://www.kokuchpro.com/ |
| Search URL | `/s/q-台湾/area-東京都/?page=N` |
| Rendering | Static HTML (no JavaScript required) |
| Auth | None required |
| Rate limit | Polite — use `REQUEST_DELAY = 0.4s` between requests |
| Source name | `kokuchpro` |
| Source ID format | URL slug between `/event/` and trailing `/` — either an MD5 hash or organizer-chosen short name (e.g. `tokyobonji0531`) |

## Field Mappings

| Event field | Source element |
|-------------|---------------|
| `name_ja` | `.event_name` link text in card |
| `start_date` | `.value-title[title]` ISO 8601 attribute (e.g. `2026-05-31T13:00:00+0900`) |
| `end_date` | Parsed from range text `〜YYYY年M月D日` in `.dtstart`; fallback = `start_date` |
| `location_name` | Detail page: `.fn.org` (hCard microformat venue name) |
| `location_address` | Detail page: `.adr` (hCard microformat full address); fallback = venue name |
| `raw_description` | Detail page: `.event_page_description.editor_html` full text |
| `short_desc` (card only) | `.event_description.description` — used only for Taiwan keyword guard |
| `source_id` | URL slug extracted by `_SLUG_RE` |

## Taiwan Relevance Filter

- Keyword check against: `["台湾", "Taiwan", "台灣", "タイワン"]`
- Applied to: `title + short_desc` from card (before detail page fetch)
- No geographic filter needed — search URL is already scoped to 東京都

### Known False Positives to Watch

- Events mentioning 台湾 only as one stop on a multi-city tour (similar to iwafu `_GLOBAL_TOUR_PATTERNS`). Not yet observed but possible for food festival circuits.
- Social exchange events ("台日交流会") are legitimate — do NOT block these; they appear frequently and are on-topic.

## Date Extraction Notes

- **Primary**: `.value-title[title]` attribute on the card — ISO 8601 with JST offset. Parse with `datetime.fromisoformat()` then strip timezone.
- **End date**: Look for `〜YYYY年M月D日` pattern in `.dtstart` text. Applies to multi-day events (e.g. ticket sale windows that span weeks).
- **Fallback**: `end_date = start_date` when no range found.
- **No detail-page date parsing needed** — the card reliably provides the ISO date.

## Detail Page Fetch Strategy

Only fetch detail pages for:
- Events with `start_date >= now - 60 days` (i.e. recent past + future)

Past events older than 60 days use card-level data only (short description, card venue). This keeps run time reasonable when the listing contains many past events.

## Address Extraction (hCard Microformat)

The detail page uses the hCard microformat:
```html
<span class="fn org">会場名</span>
<span class="adr">東京都 世田谷区三軒茶屋1-35-5</span>
```

- `location_name` ← `.fn.org`
- `location_address` ← `.adr` (join children with space)
- If `.adr` is absent, fall back to `location_name` value

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 events from listing | Search URL changed or geo parameter renamed | Check `SEARCH_URL` against site manually |
| `start_date` null | `.value-title[title]` attribute missing (organizer used old post type) | Add fallback: parse `YYYY年MM月DD日` from `.dtstart` text |
| `location_address` null | Event is online-only (no venue address) | Expected — `.adr` absent for online events |
| Detail fetch slow | Too many past events triggering detail fetch | Reduce `DETAIL_CUTOFF_DAYS` or add future-only guard |
| Source ID collision | Two events share a slug (very rare) | `dedup_events()` in `base.py` catches this |

## Pending Rules

_(Add rules here as edge cases are discovered in production.)_
