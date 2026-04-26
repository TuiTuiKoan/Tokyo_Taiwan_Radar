# PR TIMES Scraper — Implementation History

## 2026-04-26 — prtimes: initial implementation

**Context:** PR TIMES was identified as a high-value source for Taiwan-related event
announcements in Japan. Unlike event-listing platforms (Peatix, connpass), PR TIMES
receives press releases from official tourism bodies, event organisers, and brands —
often 2–4 weeks before the event.

**API Discovery:**
- Standard search URL (`/main/html/searchrlp/key/`) returned 404 on all attempts.
- `schema.org` SearchAction pointed to `action.php?run=html&page=searchkey&search_word=`
  which worked but had client-side pagination only.
- The actual JSON API was found in the Next.js bundle (`_app-d5e27ce51595715c.js`,
  module 20400): `G = \`${$}/keyword_search.php\`` → `https://prtimes.jp/api/keyword_search.php/search`.

**Filter calibration:**
- Initial dry-run returned 26 events; ~35% were events held IN Taiwan (not Japan).
- Added `_TAIWAN_BASED_TITLE_RE` (title patterns: `in 台湾`, `台湾進出`, `台湾.*に集結`) and
  `_TAIWAN_VENUE_RE` (venue contains city names: 台北, 高雄, 花蓮 etc.) to exclude Taiwan-based PRs.
- After filtering: 12 events — a cleaner signal with Japan-held Taiwan events dominant.
- Residual noise (business tie-ups, product launches that mention Taiwan) passes to the annotator.

**Date extraction decisions:**
- PR TIMES detail pages have no structured schema.org date field.
- Body text labeled patterns (`開催日時：`, `日時：`) are reliable but absent for ~40% of PRs.
- Standalone `YYYY年MM月DD日` fallback: skip index 0 (always the PR publish dateline),
  use first plausible subsequent date. Added 2-year lookback guard to reject ancient
  historical mentions (e.g. one PR about the 2011 earthquake had a date extracted as 2011-03-11).
- Final fallback: `released_at` from the API response.

**HTML structure of detail pages:**
- PR body is inside `.release-content` (most common), `.press-release-body`, or `article/main`.
- Venue often labeled as `会場：` or `開催場所：`.

**Lessons learned:**
1. Always check JS bundles for internal API endpoints when the public search URL fails.
2. Double-filter (Taiwan keyword + event-type keyword) is essential for PR platforms —
   without the event keyword, business/product PRs dominate.
3. Skip index-0 standalone date — it is always the PR publish date in the dateline header.
4. Add a sanity-check to reject dates older than 2 years; PR bodies often mention historical
   context that contains old dates before the actual event date.
