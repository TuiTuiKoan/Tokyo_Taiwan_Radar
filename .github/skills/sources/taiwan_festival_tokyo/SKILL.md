---
name: taiwan_festival_tokyo
description: Platform rules, annual festival date parsing, and year extraction for the 台湾フェスティバル™TOKYO scraper
applyTo: scraper/sources/taiwan_festival_tokyo.py
---

# taiwan_festival_tokyo Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://taiwanfes.org/` |
| Rendering | Playwright (`sync_playwright`) |
| Auth required | No |
| Source name | `taiwan_festival_tokyo` |
| Source ID format | `taiwanfes_{YYYY}` — **one event per year** (stable) |

## Event Structure

This source produces exactly **one event per year** — the annual 台湾フェスティバル™TOKYO held in 上野恩賜公園・噴水広場.

The event details are embedded in a footer widget (`#text-7`) on the homepage.

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `taiwanfes_{YYYY}` extracted from title (e.g. `"TOKYO2026"` → `2026`) |
| `raw_title` | Festival title from `#text-7` widget |
| `start_date` | `_parse_date_range()` result — first day of festival |
| `end_date` | `_parse_date_range()` result — last day of festival |
| `location_name` | Hardcoded: `"上野恩賜公園・噴水広場"` |
| `location_address` | Derived from venue name |
| `raw_description` | Widget text block from `#text-7` |

## Date Extraction

Festival dates are expressed in irregular compact notation:

```
"6月25日～27日10時～21時、28日10時～19時"   → start=Jun 25, end=Jun 28
"7月9日（木）～12日（日）"                  → start=Jul 9, end=Jul 12
"7月9日～12日"                              → start=Jul 9, end=Jul 12
```

`_parse_date_range(date_text, year)`:
1. Extracts first `月` reference to determine the month.
2. Extracts first and last `日` numbers using `(\d{1,2})日` pattern.
3. Applies the year extracted from the event title.

## Year Extraction

```python
def _extract_year_from_title(title: str) -> Optional[int]:
    m = re.search(r'(20\d{2})', title)
    return int(m.group(1)) if m else None
```

If `#text-7` is absent or the widget structure changes, the scraper returns an empty list — this is the expected behavior when the site has not yet published that year's festival information.

## Annual Refresh

Because `source_id = "taiwanfes_{YYYY}"`, the same record is upserted each run as details are updated on the homepage. The scraper does not create duplicate records across the year.

## Pending Rules

<!-- Added automatically by confirm-report -->
