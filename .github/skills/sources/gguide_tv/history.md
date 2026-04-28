# gguide_tv History

## 2026-04-28 — Initial implementation

- Implemented 2-step HTTP session: Step 1 GET `/search/` for cookie, Step 2 GET `/fetch_search_content/` for HTML fragment.
- `ebisId` from `a.js-logging[data-content]` JSON is the stable dedup key.
- Year inference logic for schedule strings: try current year, fall back to next year if result > LOOKBACK_DAYS in past — handles Dec→Jan boundary.
- Late-night broadcast convention (`25:00` style) handled with `day_offset`.
- テレサ・テン keyword filter: only keep programs where full `テレサ・テン` appears in title (not as minor guest).
- `台湾ドラマ` search omitted — fully covered by `台湾` keyword.
- Detail page fetched for description; `<main>` tag contains clean program content.
- dry-run: 21 events, 1 in-source duplicate detected and dropped by `dedup_events`.
