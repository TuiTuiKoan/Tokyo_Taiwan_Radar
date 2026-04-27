---
name: eiga_com
description: Platform rules, per-theater listing strategy, and Taiwan filter for the 映画.com 台湾映画 scraper
applyTo: scraper/sources/eiga_com.py
---

# 映画.com 台湾映画 Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://eiga.com> |
| Rendering | Static HTML — no JS required |
| Auth | None |
| Rate limit | 0.5 s per movie, 0.3 s per area/theater page |
| Source name | `eiga_com` |
| Source ID format | `eiga_com_{movie_id}_{theater_id}` (e.g. `eiga_com_82162_3018`) |

## Listing Strategy

1. Fetch `https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/` (and `/2/`, `/3/` up to 5 pages)
2. All results from this search URL contain "台湾" in the title — inherently Taiwan-relevant
3. Filter by pub_date window: `today - 90 days` ≤ pub_date ≤ `today + 180 days`
4. Stop paginating early if a page yields no new in-window films

## Per-Theater Event Strategy

One event is created **per theater** (not per movie):

```
/movie/{id}/theater/                    → area links
  └─ /movie-area/{id}/{pref}/{area}/    → div.movie-schedule blocks (per theater)
       └─ div.more-schedule a.icon.arrow → /movie-theater/{id}/{pref}/{area}/{theater_id}/
            └─ table.theater-table       → 住所 row
```

**source_id**: `eiga_com_{movie_id}_{theater_id}` — stable across weekly runs (upserts update `end_date`)

**start_date**: movie's 劇場公開日 (`p.date-published strong`)

**end_date**: last `td[data-date]` in the current week's schedule (updated each run via upsert)

**Fallback**: if `/movie/{id}/theater/` returns no area links, emit one movie-level event with `location_name=None` and `source_id=eiga_com_{movie_id}`

## HTML Structure

### Listing Page

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

### Movie Detail Page

```html
<h1 class="page-title">台湾ハリウッド</h1>
<p class="date-published"><strong>2026年4月25日</strong> 劇場公開日</p>
<p class="data">2013年製作／124分／G／台湾
  原題または英題：…
  配給：…
</p>
<!-- Synopsis: first <p> without class and len > 80 -->
```

### Area Page (`/movie-area/{id}/{pref}/{area}/`)

```html
<div class="movie-schedule" data-theater="K's cinema" data-title="台湾ハリウッド">
  <table class="weekly-schedule">
    <td data-date="20260427">…</td>   <!-- YYYYMMDD format -->
    <td data-date="20260428">…</td>
  </table>
</div>
<div class="more-schedule">
  <a class="icon copy"  href="/movie-theater/82162/13/130201/3018/mail/">コピー</a>
  <a class="icon print" href="/movie-theater/82162/13/130201/3018/print/">印刷</a>
  <a class="icon arrow" href="/movie-theater/82162/13/130201/3018/">すべてのスケジュールを見る</a>
</div>
```

### Theater Detail Page (`/movie-theater/{id}/{pref}/{area}/{theater_id}/`)

```html
<table class="theater-table">
  <tr><th scope="row">住所</th><td>東京都新宿区新宿3-35-13 3F<br/><a>映画館公式ページ</a></td></tr>
</table>
```

## Taiwan Relevance Filter

Search URL `%E5%8F%B0%E6%B9%BE` = `台湾` — all results are inherently Taiwan films.
Additional filter: pub_date within `[today-90, today+180]` to exclude very old releases.

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `h1.page-title` (or listing `p.title` as fallback) |
| `raw_title` | same as `name_ja` |
| `source_id` | `eiga_com_{movie_id}_{theater_id}` |
| `source_url` | `/movie-area/{id}/{pref}/{area}/` URL |
| `start_date` | `p.date-published strong` → pub_date (movie release date) |
| `end_date` | last `td[data-date]` in weekly schedule |
| `location_name` | `div.movie-schedule[data-theater]` |
| `location_address` | `table.theater-table th="住所" + td` (a-tags stripped) |
| `raw_description` | `開催日時: start〜end\n\np.data text\n\nsynopsis` |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction Notes

- Listing `small.time` format: `"2026年4月25日"` → `_DATE_RE` extracts Y/M/D
- Detail `p.date-published strong` format: same
- Schedule dates: `td[data-date]` = `"YYYYMMDD"` → `_yyyymmdd_to_date()`
- `raw_description` prefix: `開催日時: YYYY年MM月DD日〜YYYY年MM月DD日\n\n`
- The schedule only shows 1 week (~5 days). Daily scraper runs keep `end_date` current via upsert.

## Key Selectors

| Purpose | Selector |
|---|---|
| Theater name | `div.movie-schedule[data-theater]` |
| Schedule dates | `div.movie-schedule td[data-date]` |
| All-schedule link | `div.more-schedule a.icon.arrow[href*='/movie-theater/']` |
| Theater ID | `_THEATER_ID_RE` on arrow link href |
| Address row | `table.theater-table th:contains("住所") + td` |

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| 0 theater events, 1 fallback event | `theater()` page has no area links (movie not yet released) | Fallback event is emitted — correct behavior |
| `location_address` includes "映画館公式ページ" | `<a>` not stripped from `td` before `get_text()` | Call `td.find_all("a")` → `a_tag.decompose()` before `get_text()` |
| `location_address` is JS code | Regex matched JS-embedded `東京都` | Use `table.theater-table` approach, not page-wide regex |
| `theater_id = "unknown"` | No `a.icon.arrow` in more-schedule | Check if area page structure changed |
| Old Taiwan films returned | Pub date filter window too wide | Adjust `_LOOKBACK_DAYS` / `_LOOKAHEAD_DAYS` |
| 403 errors | Missing User-Agent | Session headers include Chrome UA |

## Pending Rules

- Monitor whether eiga.com changes its search URL format (path vs query param).
- If listing structure changes, update `ul.row.list-tile li.col-s-3` selectors.
- When a movie has multiple theaters (e.g. wide release), each theater gets a separate event with its own `source_id`.
