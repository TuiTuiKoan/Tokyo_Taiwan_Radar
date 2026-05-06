---
name: stranger
description: Scraper conventions for Stranger cinema (stranger.jp) — Eigaland JSON API, Taiwan movie filter via countries field
applyTo: scraper/sources/stranger.py
---

# Stranger Scraper — Source-Specific Skill

## Platform Profile

| Property | Value |
|---|---|
| Site URL | https://stranger.jp/ |
| API / Rendering | Eigaland JSON API (no auth) |
| Auth | None required |
| Rate limit | Conservative: 0.3s between calls |
| Source name | `stranger` |
| Source ID format | `stranger_{movieId}` (MongoDB ObjectId string) |
| Venue | Stranger, 東京都墨田区菊川3丁目6-13 |

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/website/show/listByDomainAndDate?domain=stranger.jp&date=YYYY-MM-DD` | Daily show list |
| `GET /api/website/movie/detail/{movieId}?domain=stranger.jp` | Full movie detail |

## Field Mappings

| Event field | API source |
|---|---|
| `raw_title` / `name_ja` | `movieDetail.movieName` |
| `start_date` | Earliest date in 90-day window where movie appears |
| `end_date` | Latest date in 90-day window where movie appears |
| `director` | `detail.directors` joined with `", "` |
| `raw_description` | Decoded base64 `detail.synopsis` + slogan + cast etc. |
| `official_url` | `detail.officialPageUrl` (movie's own website) |
| `source_url` | `https://stranger.jp/movie/{movieId}` |
| `location_name` | `"Stranger"` (fixed) |
| `location_address` | `"東京都墨田区菊川3丁目6-13"` (fixed) |

## Taiwan Relevance Filter

- Check `movieDetail.countries` array for `"台湾"` **or** `"台灣"`.
- Filter applied in the list API loop — skip detail API call for non-Taiwan movies.
- Do **not** rely on keyword matching in title or synopsis (countries field is authoritative).

## Synopsis Decoding

`detail.synopsis` is **base64-encoded HTML**. Decode via:
1. `base64.b64decode(b64_str).decode("utf-8")`
2. Strip HTML tags with `html.parser.HTMLParser`

The resulting plain text may contain non-breaking spaces; `strip()` each part.

## Dedup Strategy

One Event per `movieId` — not one per screening day. The scraper loops all 90 days to find `min_date` / `max_date`, then calls detail API once per unique `movieId`.

## Date Notes

- `openDate` in the list API is the movie's **release date in Japan**, not the screening date.
- Use the calendar date of the API query (`listByDomainAndDate?date=...`) as the screening date.
- `start_date` = earliest date the movie appears across the 90-day window.
- `end_date` = latest date the movie appears across the 90-day window.
- Both are `datetime` with `tzinfo=JST` (required by `dedup_events`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No Taiwan events found | Film schedule not yet published | Normal; API only returns published shows |
| `director` is empty list | No directors in API data | No fix needed — annotator will try to fill |
| `synopsis` decode error | API returned non-base64 data | `_decode_synopsis()` returns `""` gracefully |
| `91` events (one per day) | Bug: forgot to dedup by movieId | Ensure `taiwan_movies` dict deduplication in loop |

## Pending Rules

_Add lessons learned here as they arise._
