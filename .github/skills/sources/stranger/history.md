# Stranger Scraper History

## 2026-05-06 — Initial implementation

**Context**: New scraper for Stranger cinema (東京墨田区), which uses the Eigaland platform API.

**Key decisions**:
- Used Eigaland JSON API (`listByDomainAndDate` + `movie/detail`) — no Playwright needed.
- Taiwan filter via `movieDetail.countries` array (`"台湾"` | `"台灣"`), not keyword search — avoids false positives like `仙台湾`.
- 90-day window loop collects `min_date`/`max_date` per `movieId` before calling detail API.
- `synopsis` field is base64-encoded HTML; decoded via `_HTMLStripper(HTMLParser)`.
- `name_ja_locked = True` — title comes from structured API, annotator should preserve it.
- `official_url` set from `officialPageUrl` (movie's own website, e.g. `https://www.afoggytale.com/`).
- First Taiwan movie found: 「霧のごとく」(大濛, 2026-05-08〜2026-05-14).

**Dry-run result**: 1 Taiwan movie found, all fields correctly populated.
