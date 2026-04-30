# moonromantic — History

Newest at top.

---

## 2026-04-30 — RENTAL venue-hire posts entered DB (false positive)

**Error**: Two `PRIVATE RENTAL` posts (`moonromantic_260406`, `moonromantic_260505d-1`) were scraped and stored as Taiwan-related events despite containing no Taiwan content.

**Root Cause — dual bug**:
1. **`related_idx > 200` logic was inverted**: When `関連記事` appeared at position 141 (< 200), the code fell back to `check_text = page_text` (full text including related articles). The related articles sidebar listed actual Taiwan events (e.g., `Andr`), causing RENTAL posts to pass the keyword filter.
2. **No title-level block**: There was no fast-reject for posts whose title contained `RENTAL` / `PRIVATE RENTAL`.

**Fix**:
- Added `_BLOCKED_POST_PATTERNS = re.compile(r"\bRENTAL\b|PRIVATE\s+RENTAL|...", re.IGNORECASE)` applied twice: against `first_line` of `page_text` (early exit) and against confirmed `title` (second-pass).
- Fixed `related_idx` logic: always truncate at `関連記事` when found (`related_idx != -1`), regardless of position.
- Hard-deleted both RENTAL records from DB.

**Lesson**: 
- Always add title-pattern blocklists for known non-event post types at a source (venue hire, announcements, etc.). Apply BEFORE the Taiwan keyword check.
- Do NOT use position thresholds (`> N`) when truncating page text — always truncate on the marker itself.

---

## 2026-04-26 — Initial implementation

**Observation**: `--source moonromantic` failed with "Unknown source" error. Correct key is `moon_romantic` (auto-derived from class name `MoonRomanticScraper`).

**Lesson**: The `--source` key is derived from the class name (CamelCase → snake_case, minus `Scraper` suffix), NOT from `SOURCE_NAME`. For `MoonRomanticScraper` → `moon_romantic`.

**Status**: Scraper created; dry-run timed out (Playwright loading 4 Wix pages + individual posts is slow). This is expected behavior, not an error. Run with `timeout=600` or allow extended runtime.
