# OAFF Scraper History

## 2026-04-26 — Initial implementation

**Implemented by**: Scraper Expert agent

### Non-obvious decisions

1. **WP REST API over HTML list page**  
   The program list page (`/oaff{YEAR}/programs/`) uses `li.wp-block-post` WordPress blocks with country info in `.is-dynamic-field .value` spans. Both approaches work, but the WP REST API (`/wp-json/wp/v2/posts?categories=8&per_page=100`) is simpler: returns all editions in one paginated response without needing to discover the year-specific URL first.

2. **Three date formats across editions**  
   - 2024 main: `M/D(曜) HH:MM　会場名` (slash format, full-width space before venue)  
   - 2025 main: `M月D日（曜）HH:MM／会場名` (kanji month, slash before venue)  
   - 2025 expo: `M月D日(土) [spaces] HH:MM [spaces]/会場名` (mixed spacing)  
   - TAIWAN NIGHT: `YYYY年M月D日（曜）HH:MM` (full year in text)  
   All four patterns handled. Year inferred from slug for partial dates.

3. **source_id uses WP post ID not slug**  
   Slugs like `taiwan-night2025` could theoretically collide if OAFF reuses naming patterns across editions. WP integer post IDs are guaranteed unique and permanent.

4. **Venue regex covers both `/` and `　` (full-width space) delimiters**  
   The venue extraction regex `\d{1,2}[月/]\d{1,2}[^\n]*\d{2}:\d{2}\s*[/／　\s]([^\n/／]{5,60})` handles all observed venue separators.

5. **0 events is expected when festival is not running**  
   Dry-run on 2026-04-26 returned 0 events because the 2026 program was not yet announced. This is correct behavior — confirmed by checking all 29 historical posts, all with valid dates.

### Dry-run results (2026-04-26)
- All 29 historical Taiwan posts: date ✓, venue ✓
- Active events (after cutoff today-45): 0 (2026 program not yet published)
- Duplicate: 1 (`oaff_2417 The Horse 馬語` appeared twice in WP API — handled by `dedup_events()`)
