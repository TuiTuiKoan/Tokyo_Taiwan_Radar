---
name: livepocket
description: "Platform rules, search URL structure, dl field extraction, and Taiwan filter for the LivePocket（ライブポケット）e-ticket scraper"
applyTo: scraper/sources/livepocket.py
---

# LivePocket（ライブポケット）Scraper

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://livepocket.jp/ |
| Search URL | `/event/search?word=台湾&page=N` |
| Rendering | Static HTML — no JavaScript required |
| Auth | None required |
| Rate limit | Polite — use `REQUEST_DELAY = 0.5s` between requests |
| Source name | `livepocket` |
| Source ID format | `livepocket_{slug}` — URL slug from `/e/{slug}` path (e.g. `livepocket_hmvyt`) |

## Field Mappings

| Event field | Source element |
|-------------|---------------|
| `raw_title` | `h1.heading01` — top-level event title |
| `start_date` | `dl.event-detail-info__list` → `div.event-detail-info__block` where `dt` contains `開催日` → `dd` text, first `YYYY年M月D日` match |
| `end_date` | Same `dd` text — second date if range `〜` separator present; otherwise same as `start_date` |
| `location_name` | `会場` `dd` — text before `（都道府県）` suffix |
| `location_address` | `会場` `dd` — `<span>` after `（都道府県）`; stripped of map link boilerplate |
| `raw_description` | Composed: `開催日時:` header + `会場:` + `出演者:` (if present) + `div.event-detail__content` main text |
| `price_info` | `div.event-detail-ticket-body` — `¥` price strings joined with ` / ` |
| `is_paid` | `True` unless price text contains `無料` or `¥0` / `0円` |
| `source_id` | `livepocket_{slug}` |

## Taiwan Relevance Filter

Applied on full detail-page text (after fetching `/e/{slug}`).

```python
TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
```

- Search keywords: `台湾`, `Taiwan`, `臺灣` (三組)
- Filter is applied on the **detail page text** because search results can match keyword in performer names or unrelated context
- Events with "台湾" only in ticket seller name (e.g. 台湾スタジオ) are still included — broad filter is intentional

## CSS Selectors — Critical Note

> **The `dl` class is `event-detail-info__list`, NOT `event-detail-info`.**

```python
dl = soup.select_one("dl.event-detail-info__list")
```

The `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` divs:

```html
<dl class="event-detail-info__list">
  <div class="event-detail-info__block">
    <dt class="event-detail-info__title">
      <span class="event-detail-info__date">開催日</span>
    </dt>
    <dd class="event-detail-info__data">2026年7月27日(月)</dd>
  </div>
  ...
</dl>
```

Use `_get_dd_text(dl, label)` which iterates `div.event-detail-info__block` and checks `dt.get_text()`.

There are **two identical `dl.event-detail-info__list` blocks** per page (desktop + mobile rendering). Always use `select_one()` to get the first.

## Venue Parsing

Raw venue `dd` text format:
```
新宿MARZ (東京都)
東京都新宿区歌舞伎町2-45-1 第一常磐ビルB1
会場マップ・アクセス方法はこちら
```

- `location_name`: text up to and including `(都道府県)` parenthetical — matched via `_PREF_RE = re.compile(r"[（(][^）)]+[都道府県][）)]")`
- `location_address`: `<span>` text after the parenthetical; strip map link boilerplate

## Date Extraction Notes

- Single day: `"2026年7月27日(月)"` → `start_date = end_date`
- Date range: `"2026年6月27日(土)〜2026年6月28日(日)"` → extract first and second `YYYY年M月D日` matches
- Day-of-week `(曜)` parentheticals are stripped by the regex matching only `\d{4}年\d{1,2}月\d{1,2}日`

## Search Pagination

Search pages return 404 when the page number exceeds the result count. The scraper breaks the loop cleanly on 404 via `_fetch()` warning + `None` return.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 events found | `dl.event-detail-info__list` selector changed | Inspect page for new `dl` class; update selector and `_get_dd_text` block iterator |
| `start_date` null | `開催日` label not found in `dt` text | Check HTML; the `span` child text may have changed (e.g. `開催日時`) |
| `location_address` null | Venue has no `<span>` for address (online event or no address listed) | Expected for online events |
| No events pass Taiwan filter | Search results page format changed | Inspect `a.event-card[href^='/e/']` selector and badge logic |
| Price info blank | `div.event-detail-ticket-body` missing | Free events or old ticket format; `is_paid` falls back to `None` |

## Pending Rules

- [ ] Verify behaviour for online-only events (no venue address)
- [ ] Add tour page (`/t/`) detection if any slip through the `/e/` guard
