---
name: ssff
description: Platform rules, listing structure, and Taiwan filter for the SSFF (Short Shorts Film Festival & Asia) scraper
applyTo: scraper/sources/ssff.py
---

# SSFF Short Shorts Film Festival & Asia Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://www.shortshorts.org> |
| Rendering | Static HTML (WordPress) — no JS required |
| Auth | None |
| Rate limit | 0.3 s delay per film detail page fetch |
| Source name | `ssff` |
| Source ID format | `ssff_{year}_{slug}` (e.g. `ssff_2026_what-it-says-about-us`) |

## Listing Strategy

1. Detect year by trying `/{year}/all-program/` (current year, then +1, then -1)
2. A valid page is >10KB — accept if `resp.ok and len(resp.text) > 10000`
3. Find all `<a href>` matching `/{year}/program/{slug}/` whose link text contains `台湾`
4. Typical link text: `"20- 満たされない私たち What it Says About Us Chien Yu Lin / 台湾"`

## All-Program Page Link Format

```html
<a href="https://www.shortshorts.org/2026/program/what-it-says-about-us/">
  20- ここで生きる私たち 満たされない私たち What it Says About Us Chien Yu Lin / 台湾
</a>
```

## Film Detail Page Structure

```html
<!-- breadcrumb: nav ol li[-1] = Japanese title -->
<nav><ol>
  <li>Home</li>
  <li>上映プログラム</li>
  <li>20- ここで生きる私たち</li>
  <li>満たされない私たち</li>  ← Japanese title
</ol></nav>

<!-- English title -->
<article>
  <h1>What it Says About Us</h1>

  <!-- Meta info -->
  <dl class="info">
    <dt>監督</dt><dd>Chien Yu Lin</dd>
    <dt>国</dt><dd>台湾</dd>
    ...
  </dl>

  <!-- Screening table -->
  <table>
    <tbody>
      <tr>
        <td><a href="...">WITH HARAJUKU HALL</a></td>
        <td>2026.06.08 [Mon] 13:00-14:50</td>
        <td>チケット購入</td>
      </tr>
    </tbody>
  </table>
</article>
```

## Taiwan Relevance Filter

- Link text from all-program page must contain `台湾`, `Taiwan`, or `臺灣`
- 2026: 6 Taiwan films confirmed

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | breadcrumb `nav ol li[-1]` text |
| `name_en` | `article h1` text (English title) |
| `raw_title` | `name_ja` |
| `source_id` | `ssff_{year}_{slug}` |
| `source_url` | film detail page URL |
| `start_date` | first screening table row date |
| `location_name` | first screening table row venue (`td[0]` link text) |
| `raw_description` | `開催日時: …\n\n監督: …\n国: …\n\nsynopsis` |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction Notes

- Screening table date format: `"2026.06.08 [Mon] 13:00-14:50"` → `_SSFF_DATE_RE = r"(\d{4})\.(\d{2})\.(\d{2})"`
- If no screening date found: fallback to `datetime(year, 5, 25)` (typical SSFF opening date)
- `raw_description` prefix: `開催日時: YYYY年MM月DD日\n\n`

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| 0 Taiwan films found | New year's page not yet published | Year detection tries current±1 year |
| Synopsis empty | Section contains venue text | Skip sections containing "上映会場" or "チケット" |
| Japanese title empty | Breadcrumb structure changed | Fall back to `h1` text |
| Venue not extracted | Table structure changed | Check `article table tbody tr td[0]` |

## Pending Rules

- SSFF publishes its program around January-February each year for May-June festival.
- If `/{year}/all-program/` returns 404 or <10KB, the current year's program is not yet published.
