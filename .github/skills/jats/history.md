# JATS Scraper — History

## 2026-04-26

**Implementation**: Initial build.

- WP REST API available at `/wp-json/wp/v2/posts`. Category 6 (`taikai-tokyo`) has both announcement posts and structured detail posts — must filter to `/taikai/tokyoNNN` URL pattern only.
- Announcement posts (URL `/taikai-tokyo/kantoNNN/`) contain only "学会ブログに掲載しました" — no date/venue info. Skipping them avoids duplicates.
- `日時` label has NO colon (unlike Waseda `日時：`) — regex must match `r"日時\s+(\d{4}年..."`.
- `場所` label also has no colon — same pattern.
- `_extract_after_label` stop labels for special chars (`■`, `※`, `http`) need `\s+CHAR` not `\s+CHAR[\s：:]` — the char is immediately followed by text, not space/colon.
- LOOKBACK_DAYS=90, MAX_PAGES=2 (40 posts) covers ~5 months of meetings at current pace.
