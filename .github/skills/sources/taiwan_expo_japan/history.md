---
description: "Taiwan Expo Japan scraper implementation history and source-specific lessons"
---

# Taiwan Expo Japan Scraper History

<!-- Append new entries at the top -->

## 2026-07-20 - Initial annual Wix SSR implementation

### Decision

The official Wix homepage exposes the current annual title, complete date range, venue, address, event introduction, past results, and program schedule in server-rendered HTML. Generated container IDs and classes are unsuitable as stable selectors, so the scraper parses visible text between semantic headings.

### Implementation

The scraper emits one annual event with `source_id=taiwan_expo_japan_<year>`. It requires title-year and full-date-year agreement, returns timezone-aware UTC-midnight datetimes, strips NUL bytes, and stops the description before previous-year results or the day-by-day schedule. Parser tests rename all Wix IDs, classes, and test IDs to prove the result does not depend on generated markup.

The authoritative venue registry had no canonical or alias match for `東京新宿住友ビル三角広場` at implementation time. The scraper therefore keeps the official venue text and parses the adjacent English address from the homepage. It does not hardcode the address or seed a venue from a single annual occurrence.

### Lesson

For annual Wix landing pages, semantic boundaries and strict year agreement are safer than generated selectors or current-year inference. Keep program schedules outside a one-event source's `raw_description`, because the annotator can otherwise turn sessions into unintended sub-events.