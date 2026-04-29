---
name: maruhiro
description: 丸広百貨店イベントカレンダーから台湾関連イベントを取得するスクレイパーのスキル
applyTo: scraper/sources/maruhiro.py
---

# maruhiro Scraper Skills

## Platform Profile

| Item | Details |
|------|---------|
| Site URL | https://www.maruhiro.co.jp |
| Event list URL | `https://www.maruhiro.co.jp/top/events` (page 1), `/page:N` (pages 2+) |
| Rendering | Static HTML — requests + BeautifulSoup only, no Playwright needed |
| Auth | None |
| Rate limit | None observed; `_DELAY = 0.4s` is sufficient |
| Source name | `maruhiro` |
| Source ID format | `maruhiro_{event_id}` — integer from `data-url="/events/view/{id}"` |

## Stores

All stores are in Saitama Prefecture:

| Store key | location_name | location_address |
|-----------|---------------|-----------------|
| `川越店` | まるひろ川越店 | 埼玉県川越市新富町2-6-1 |
| `飯能店` | まるひろ飯能店 | 埼玉県飯能市栄町24-4 |
| `入間店` | まるひろ入間店 | 埼玉県入間市豊岡1-6-12 |
| `上尾SC` | まるひろ上尾SC | 埼玉県上尾市宮本町1-1 |
| `南浦和SC` | まるひろ南浦和SC | 埼玉県さいたま市南区南本町1-7-4 |

Satellite stores (no main store page) fall back to 川越店 address.

## Field Mappings

| Event field | Source |
|-------------|--------|
| `raw_title` | `h3 a` text in card |
| `start_date` | `p.card-text` — parsed as `datetime.datetime` (required by `dedup_events`) |
| `end_date` | `p.card-text` (range pattern), else `None` |
| `location_name` | Resolved from `開催店舗:` via `_STORE_ADDRESS` dict |
| `location_address` | Same as above |
| `source_id` | `maruhiro_{id}` from `data-url="/events/view/{id}"` |
| `source_url` | `https://www.maruhiro.co.jp/events/view/{id}` |
| `category` | `["lifestyle_food"]` (default) |

## Taiwan Relevance Filter

Title-only filter: `_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)`

**All data is in the list page — detail pages contain only a JPEG image (no text).**
Do NOT fetch detail pages; all date, floor, and store info is in `p.card-text`.

## Date Extraction Rules

Date patterns in `p.card-text` — three variants:

| Pattern | Example |
|---------|---------|
| Range | `●2026年4月29日(水・祝)～2026年5月4日(月・祝)まで` |
| Start-only | `●2026年4月29日(水・祝)から` |
| No date | `開催店舗: 川越店` only → **skip** (no `start_date`) |

**Critical**: `start_date` must be `datetime.datetime`, NOT `datetime.date`.
`dedup_events` in `base.py` calls `.date()` on `start_date`, so passing a bare
`date` object raises `AttributeError: 'datetime.date' object has no attribute 'date'`.

## Seasonality

- Taiwan events appear primarily during **Golden Week (Apr–May)** — 台湾フェア confirmed.
- Autumn (Sep–Oct) is possible based on general department store patterns.
- 0-event dry-runs outside these periods are normal.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `AttributeError: 'datetime.date' object has no attribute 'date'` | `start_date` is `date` not `datetime` | Use `datetime(y, m, d)` not `date(y, m, d)` |
| 0 events found | Off-season (no current Taiwan events) | Expected — check manually or wait for GW/autumn |
| Store address is wrong | `開催店舗:` key not matched | Add new key to `_STORE_ADDRESS` dict |
| Pagination incomplete | `_MAX_PAGES` cap reached | Increase `_MAX_PAGES` if site grows |

## Pending Rules
