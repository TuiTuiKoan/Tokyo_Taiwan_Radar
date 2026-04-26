# 新文芸坐 Scraper History

## 2026-04-26

**Issue**: `start_date` returned `2026-05-06` instead of correct `2026-05-08` for "赤い糸 輪廻のひみつ"

**Root cause**: `_parse_nihon_date_only` used `p.find_previous("h2")` to locate the date. In the DOM, `p.nihon-date` is the first child of `div.schedule-content-txt`, and the h2 date elements come **after** it — not before. So `find_previous("h2")` found an h2 from the preceding film block, returning the wrong date.

**Fix**: Rewrote `_parse_nihon_date_only` to iterate `parent.children` and collect h2 elements that follow the `p.nihon-date`. First h2 → start date (has `M/D` format). Last h2 → end date (day-only, same month with month-wrap guard).

**Lesson**: When the target element is the first sibling in its container, `find_previous()` will find elements from other containers. Always verify DOM structure before using positional search. For chronological siblings, prefer iterating `parent.children`.

**Verification**: `start_date: 2026-05-08`, `end_date: 2026-05-14` for 赤い糸 輪廻のひみつ — correct.
