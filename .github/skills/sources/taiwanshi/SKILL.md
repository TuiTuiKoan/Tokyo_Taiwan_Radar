---
name: taiwanshi
description: Platform rules, Atom feed parsing, and troubleshooting for the taiwanshi scraper (台湾史研究会)
applyTo: scraper/sources/taiwanshi.py
---

# 台湾史研究会 (Taiwanshi) Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://taiwanshi.exblog.jp |
| Category page | https://taiwanshi.exblog.jp/i3/ (定例研究会, 143 posts) |
| Atom feed | https://taiwanshi.exblog.jp/atom.xml |
| API/Rendering | Atom 0.3 feed via `requests` — no Playwright needed |
| Auth required | No |
| Rate limit | None observed |
| Source name | `taiwanshi` |
| Source ID format | `taiwanshi_{post_id}` (8-digit numeric ID from URL) |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `taiwanshi_{post_id}` — post ID from `<link href="https://taiwanshi.exblog.jp/NNNNNNNN/">` |
| `source_url` | `<link rel="alternate">` href (normalised to `https://`) |
| `name_ja` | `<title>` element |
| `start_date` | `日時：` line in CDATA content body |
| `location_name` | `会場：` or `場所：` line (first segment before online suffix) |
| `location_address` | Prefecture-prefixed address line following `会場：` |
| `raw_description` | `開催日時: YYYY年MM月DD日\n\n` + full stripped plain-text body |
| `category` | Hardcoded `["academic", "taiwan_japan"]` |
| `is_paid` | `False` (all meetings are free for members/attendees) |
| `original_language` | `"ja"` |

## Taiwan Relevance Filter

All posts in this blog are directly about Taiwanese history academic research.
No keyword filtering needed — every post from the 定例研究会 category (`dc:subject`) or containing `日時：` qualifies.

The scraper skips posts without a structured `日時：` field (e.g. "報告者募集" recruitment posts).

## Date Extraction Notes

**Separator variations** — `日時` label can use any of:
- `日時：` (full-width colon)
- `日時:` (half-width colon)
- `日時　` (full-width space, no colon)
- `日時 ` (regular space)

**Date body variations:**
- Standard: `日時：2026年5月16日（土）13時00分～16時10分`
- No end time: `日時：2026年3月29日（日）13時00分～`
- Spaces inside date: `日時： 2025 年10月4 日（土）15：30～18：00`
- ASCII parentheses for DOW: `日時　2025年6月28日(土) 13時00分～15時10分`

**Regex** (handles all above):
```python
r"日時[：:\s\u3000]*\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
r"[（(]?[^)）\d]*[)）]?"
r"\s*(?:(\d{1,2})時(\d{2})分)?"
```

Time extraction is best-effort. `HH：MM` full-width colon format (not `時分`) is not captured; `start_date` defaults to `00:00:00` in those cases.

## Venue Extraction Notes

**Separator variations** — `会場`/`場所` label can use any of:
- `会場：venue` (full-width colon)  
- `会場:venue` (half-width colon)
- `会場　venue` (full-width space)
- `場所：venue` (different label — used by non-定例研究会 posts)

Regex: `r"(?:会場|場所)[\uff1a:\u3000 \t]+(.+)"`

**Online suffix stripping** — venue line often ends with:
- `、およびGoogle Meet によるオンライン併用`
- `、及びGoogle Meet`
- `、及びZoom`
- `、およびZoomによるオンライン併用`

Split pattern: `r"[、,]?\s*(?:および|及び|またはGoogle|Google Meet|Zoom|オンライン)"`

**Address location** — appears on the line(s) after `会場：`, indented with full-width spaces (　). Extracted with a prefecture-prefix pattern.

## Geographic Note

Physical meetings are held at universities **across Japan** (Osaka, Nagoya, Kobe, etc.), NOT exclusively Tokyo. However, all meetings have online participation (Google Meet / Zoom), making them accessible to Tokyo-based users. Include all meetings regardless of physical location.

## Atom Feed Notes

- `https://taiwanshi.exblog.jp/atom.xml` is accessible via plain `requests` (no JS needed)
- The feed declares `xmlns="http://www.w3.org/2005/Atom"` with `version="0.3"` — same namespace as Atom 1.0, use `_ATOM_NS = "http://www.w3.org/2005/Atom"`
- `<issued>` element contains publication timestamp (Atom 0.3 term for `<published>`)
- `<content type="html">` wraps full post body as CDATA HTML with `<br />` line breaks
- `<dc:subject>` contains the category name (e.g. `定例研究会`)
- Feed contains the ~20 most recent posts across all categories

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `date parse failed for post NNNN` | New `日時` format variant | Check the raw content; extend `_extract_start_date` regex to handle the new separator/spacing |
| `venue=None` | Post uses `場所：` not `会場：`, or new separator variant | Add new label/separator to `_extract_venue` regex |
| 0 events scraped | Feed unreachable or no recent events with `日時：` | Check `https://taiwanshi.exblog.jp/atom.xml` directly |
| Old events still appearing | Atom feed has ~20 entries; old posts are not pruned | Feed naturally rotates — no action needed |
| Online suffix not stripped | New online platform keyword (e.g. `Teams`) | Add keyword to `re.split` pattern in `_extract_venue` |

## Pending Rules

<!-- Added automatically by confirm-report -->
