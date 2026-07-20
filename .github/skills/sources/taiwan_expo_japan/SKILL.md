---
name: taiwan_expo_japan
description: Wix SSR anchors, annual date guards, and schedule exclusion rules for the Taiwan Expo Japan scraper
applyTo: scraper/sources/taiwan_expo_japan.py
---

# taiwan_expo_japan Scraper Skill

## Platform Profile

| Field            | Value                                                        |
|------------------|--------------------------------------------------------------|
| Site URL         | <https://jp.twexpojapan.com/>                                |
| API/Rendering    | Wix SSR HTML through `requests` and BeautifulSoup            |
| Auth             | None                                                         |
| Rate limit       | One homepage request per run; no rate-limit headers observed |
| Source name      | `taiwan_expo_japan`                                          |
| Source ID format | `taiwan_expo_japan_<year>`                                   |

## Event Model

* Emit exactly one canonical event for the annual expo homepage.
* Require the official page title and a complete date range to contain the same year.
* Return no event when the title year, complete date range, description boundary, or venue is missing.
* Never infer a date from blog publication dates, sitemap `lastmod`, registration URLs, or the current year.

## Field Mappings

| Event field       | Source                                                     |
|-------------------|------------------------------------------------------------|
| `source_id`       | Title year in `taiwan_expo_japan_<year>`                   |
| `raw_title`       | Official HTML `<title>`                                    |
| `start_date`      | First date in the complete `YYYY.M.D - M.D` range          |
| `end_date`        | Second date in the same range                              |
| `raw_description` | Structured date, venue, organizer, and bounded about text |
| `location_name`   | Exact venue text on the homepage                           |
| `location_address`| Address line adjacent to the venue text                    |
| `organizer`       | Verified official organizer, `経済部国際貿易署`            |
| `official_url`    | Homepage URL                                               |
| `category`        | `business`, `tech`, `taiwan_japan`, `lifestyle_food`       |

## Semantic Anchors

Wix-generated `comp-*` IDs, rich-text classes, and `data-testid` values are not stable selectors. Parse visible text instead:

1. Start the main description after `Taiwan Expo について`.
2. Stop before the first later `イベントスケジュール` heading.
3. Stop earlier when a previous-year `YYYY年 開催実績` section appears.
4. Strip NUL bytes from every emitted string.

The complete day-by-day schedule must not enter `raw_description`. It can cause the annotator to create program sessions as sub-events even though this source owns one annual main event.

## Date Extraction Notes

Accepted compact ranges include `2026.7.15 -7.17`, `2026年7月15日〜17日`, and cross-month or cross-year forms with an explicit start year. Dates are timezone-aware UTC-midnight `datetime` values. Invalid dates, reversed ranges, incomplete ranges, and title-year mismatches fail closed.

## Taiwan Relevance

Every annual event on this official source is in scope. It is a Taiwan government trade and public exhibition held in Japan for Japanese businesses and visitors, with technology, food, culture, and lifestyle content. No keyword or regional filter is needed.

## Troubleshooting

| Symptom                         | Likely cause                            | Fix                                                        |
|---------------------------------|-----------------------------------------|------------------------------------------------------------|
| Dry-run returns zero events     | Homepage title or date format changed   | Inspect visible SSR text and add a tested semantic variant |
| Description includes sessions   | Schedule boundary is no longer matched  | Update the heading boundary; do not parse program cards    |
| Wrong annual record is updated  | Title and date years are not cross-checked | Restore strict year agreement before creating the event |
| Address is missing              | Address moved away from the venue text  | Expand only the local venue window; never use the venue name as an address |
| Garbled output contains `\x00` | Wix text contains embedded NUL bytes    | Keep `_clean_text()` on every emitted string               |

## Pending Rules

<!-- Add source-specific rules discovered during future fixes here -->