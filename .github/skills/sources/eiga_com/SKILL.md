---
name: eiga_com
description: Platform rules, listing structure, and Taiwan filter for the 映画.com 台湾映画 scraper
applyTo: scraper/sources/eiga_com.py
---

# 映画.com 台湾映画 Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://eiga.com> |
| Rendering | Static HTML — no JS required |
| Auth | None |
| Rate limit | 0.5 s delay per detail page fetch |
| Source name | `eiga_com` |
| Source ID format | `eiga_com_{movie_id}` (numeric ID from URL, e.g. `eiga_com_82162`) |

## Listing Strategy

1. Fetch `https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/` (and `/2/`, `/3/` up to 5 pages)
2. All results from this search URL contain "台湾" in the title — inherently Taiwan-relevant
3. Filter by pub_date window: `today - 90 days` ≤ pub_date ≤ `today + 180 days`
4. Stop paginating early if a page yields no new in-window films

## Listing Page HTML Structure

```html
<ul class="row list-tile">
  <li class="col-s-3">
    <a href="/movie/82162/">
      <p class="title">台湾ハリウッド</p>
      <small class="time">2026年4月25日</small>
    </a>
  </li>
</ul>
```

## Detail Page HTML Structure

```html
<h1 class="page-title">台湾ハリウッド</h1>
<p class="date-published"><strong>2026年4月25日</strong> 劇場公開日</p>
<p class="data">2013年製作／124分／G／台湾
  原題または英題：…
  配給：…
</p>
<!-- Synopsis: first <p> without class and len > 80 -->
```

## Taiwan Relevance Filter

Search URL `%E5%8F%B0%E6%B9%BE` = `台湾` — all results are inherently Taiwan films.
Additional filter: pub_date within `[today-90, today+180]` to exclude very old releases.

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `h1.page-title` (or listing `p.title` as fallback) |
| `raw_title` | same as `name_ja` |
| `source_id` | `eiga_com_{movie_id}` |
| `source_url` | `https://eiga.com/movie/{id}/` |
| `start_date` | `p.date-published strong` → date, fallback to listing `small.time` |
| `raw_description` | `開催日時: …\n\np.data text\n\nsynopsis` |
| `location_name` | `None` (no fixed Tokyo venue) |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction Notes

- Listing `small.time` format: `"2026年4月25日"` → `_DATE_RE` extracts Y/M/D
- Detail `p.date-published strong` format: same
- `raw_description` prefix: `開催日時: YYYY年MM月DD日\n\n` required

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| Old Taiwan films returned | Pub date filter window too wide | Adjust `_LOOKBACK_DAYS` / `_LOOKAHEAD_DAYS` |
| 0 results | Date filter excludes all current films | Check today vs pub_date logic |
| 403 errors | Missing User-Agent | Session headers include Chrome UA |
| `source_id` collision | Multiple films with same ID | IDs are movie-specific numeric — should not collide |

## Pending Rules

- Monitor whether eiga.com changes its search URL format (path vs query param).
- If listing structure changes, update `ul.row.list-tile li.col-s-3` selectors.
