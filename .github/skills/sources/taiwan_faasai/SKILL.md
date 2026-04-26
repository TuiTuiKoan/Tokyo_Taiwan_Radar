---
name: taiwan_faasai
description: Platform rules and date extraction for the 台湾發祭 Taiwan Faasai annual festival scraper
applyTo: scraper/sources/taiwan_faasai.py
---

# 台湾發祭 Taiwan Faasai Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://taiwanfaasai.com/outline> |
| Rendering | Static HTML — no JS required |
| Auth | None |
| Rate limit | Single page; no rate limiting needed |
| Source name | `taiwan_faasai` |
| Source ID format | `taiwan_faasai_{year}` (e.g. `taiwan_faasai_2026`) |

## Strategy

Single annual event. The `/outline` page contains all relevant information.

1. Fetch `https://taiwanfaasai.com/outline` (with `verify=False` — site has TLS cert issues)
2. Extract year from page title heading (`台湾發祭 Taiwan Faasai 2026`)
3. Extract start date from `N月M日` pattern in text
4. Extract additional days from `・N日` following the start date
5. Return single `Event` with `start_date` = first day, `end_date` = last day

## Date Format on Page

```
2026年
8月28日(金) ・29日(土) ・30日(日)11:00 - 21:00（予定）
```

- `_DATE_DAY_RE = r"(\d{1,2})月(\d{1,2})日"` → extracts month=8, day=28
- `_EXTRA_DAY_RE = r"・(\d{1,2})日"` → extracts additional days [29, 30]
- Assumes all days are in the same month

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `台湾發祭 Taiwan Faasai {year}` (constructed) |
| `raw_title` | same as `name_ja` |
| `source_id` | `taiwan_faasai_{year}` |
| `source_url` | `https://taiwanfaasai.com/outline` |
| `start_date` | First day extracted from page |
| `end_date` | Last additional day extracted from page |
| `location_name` | `上野恩賜公園 竹の台広場（噴水前広場）` (fixed) |
| `location_address` | `東京都台東区上野公園8番（竹の台広場）` (fixed) |
| `category` | `["lifestyle_food"]` |
| `is_paid` | `False` (free admission) |

## Important Notes

- **TLS issue**: `requests.get(..., verify=False)` required. Suppress `InsecureRequestWarning` with `warnings.catch_warnings()`.
- **Annual event**: Source ID is year-based → upserts cleanly each year without creating duplicates.
- **Venue note**: 竹の台広場 is inside 上野恩賜公園; address includes 台東区.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 0 events | Year or date regex no longer matches | Inspect page text for new format |
| Wrong end date | Extra days in different month | Extend `_EXTRA_DAY_RE` to handle month boundary |
| SSL error | Certificate issue | Ensure `verify=False` and `InsecureRequestWarning` suppressed |

## Pending Rules

<!-- Add new rules discovered after initial implementation here -->
