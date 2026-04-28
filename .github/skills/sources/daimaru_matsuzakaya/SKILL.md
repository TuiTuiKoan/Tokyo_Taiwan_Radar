---
name: daimaru_matsuzakaya
description: "Platform rules, JSON API structure, and store map for the 大丸・松坂屋 scraper"
applyTo: scraper/sources/daimaru_matsuzakaya.py
---

# daimaru_matsuzakaya Scraper Skill

## Platform Profile

| Item | Value |
|------|-------|
| Brand sites | https://www.daimaru.co.jp / https://www.matsuzakaya.co.jp |
| API/Rendering | **static-json** — `requests` only (no Playwright needed) |
| Auth | None (Referer header required) |
| Rate limit | Polite: `_DELAY = 0.3s` between store fetches |
| Source name | `daimaru_matsuzakaya` |
| Source ID format | `daimaru_matsuzakaya_{slug}_{event_id}` |

## Key Discovery (2026-04-28)

Both brands use a React/Vite SPA, but all event data is loaded via a **public JSON API**:

```
https://www.daimaru.co.jp/spa_assets/events/{slug}.json
https://www.matsuzakaya.co.jp/spa_assets/events/{slug}.json
```

This was found by running Playwright with response interception on `https://www.daimaru.co.jp/tokyo/event/`.
The `Referer` header matching the store's event page URL is required for 200 responses.

## JSON Response Structure

```json
[
  {
    "id": 54,
    "largeEventHallName": "11階 催事場/…",
    "eventHalls": [
      {
        "id": 94,
        "eventHallName": "11階 催事場",
        "events": [
          {
            "id": 1091,
            "eventName": "〈洪瑞珍（ホンレイゼン）〉台湾サンドイッチ",
            "eventStartDate": "202405220000",
            "eventEndDate":   "202406041700",
            "displayDate":    "5月22日(水)→6月4日(火)",
            "eventUrl":       "https://www.daimaru.co.jp/tokyo/…/",
            "comment1":       "最終日は17時閉場",
            "comment2":       ""
          }
        ]
      }
    ]
  }
]
```

## Field Mappings

| Event field | Source |
|-------------|--------|
| `raw_title` / `name_ja` | `ev["eventName"]` |
| `raw_description` | `開催日時: …\n\n会場: …\n\ncomment1\n\ncomment2\n\n期間表示: …` |
| `source_url` | `ev["eventUrl"]` if non-empty, else store event page URL |
| `start_date` | `ev["eventStartDate"][:8]` → `datetime.strptime(..., "%Y%m%d")` |
| `end_date` | `ev["eventEndDate"][:8]` → same |
| `location_name` | `"{store_name} {eventHallName}"` |
| `location_address` | Hardcoded per store (see `_STORES` map) |
| `source_id` | `daimaru_matsuzakaya_{slug}_{ev["id"]}` |

## Confirmed Store JSON Endpoints (2026-04-28)

| Brand | Slug | JSON URL | Total Events | Taiwan (all-time) |
|-------|------|----------|-------------|-------------------|
| daimaru | tokyo | .../events/tokyo.json | 1820 | 2 |
| daimaru | shinsaibashi | .../events/shinsaibashi.json | 57 | 0 |
| daimaru | umedamise | .../events/umedamise.json | 1807 | 2 |
| daimaru | kobe | .../events/kobe.json | 133 | 0 |
| daimaru | kyoto | .../events/kyoto.json | 90 | 0 |
| daimaru | sapporo | .../events/sapporo.json | 76 | 0 |
| daimaru | shimonoseki | .../events/shimonoseki.json | 583 | 0 |
| matsuzakaya | nagoya | .../events/nagoya.json | 1727 | 0 |
| matsuzakaya | ueno | .../events/ueno.json | 2752 | 0 |
| matsuzakaya | shizuoka | .../events/shizuoka.json | 1777 | 0 |
| matsuzakaya | shimonoseki | .../events/shimonoseki.json | 583 | 0 |
| ~~daimaru~~ | ~~fukuoka~~ | 403 永久不可 | — | — |
| ~~matsuzakaya~~ | ~~takatsuki~~ | 403 永久不可 | — | — |

**Note on slugs**: The JS bundle at `/spa_assets/assets/index-mo0PHooD.js` contains React Router path definitions like `path:"/umedamise/*"` — use this to discover new store slugs if the store list changes.

## Taiwan Events — All-Time History

| Store | Period | Event Name |
|-------|--------|-----------|
| daimaru/tokyo | 2022-09-21〜27 | 〈グランドカステラ〉台湾カステラ |
| daimaru/tokyo | 2024-05-22〜06-04 | 〈洪瑞珍（ホンレイゼン）〉台湾サンドイッチ |
| daimaru/umedamise | 2021-06-16〜22 | 〈台湾カステラ米米(ファンファン)〉台湾カステラ |
| daimaru/umedamise | 2022-01-02〜11 | 〈菓匠三全〉萩の月、〈台湾カステラ米米〉台湾カステラ |

## Seasonal Pattern

Taiwan events are **rare and unpredictable** (not seasonal). All past events have been food stalls (`台湾カステラ`, `台湾サンドイッチ`). 0-event dry-runs are expected behaviour between Taiwan fair cycles. Category `lifestyle_food` is appropriate as default.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 events | No current Taiwan fair | Normal — check back after any Taiwan food fair announcement |
| HTTP 403 on a store | That store requires Playwright (or geo-blocked) | Skip — add to `_BLOCKED` note in source file |
| New store not covered | Store added by brand | Check JS bundle router paths for new slug; add to `_STORES` |
| `eventUrl` is empty string | Event has no dedicated page | Falls back to store event page URL — correct behaviour |
| JS bundle hash changes | SPA deployment update | Re-run Playwright intercept to confirm JSON API URL is unchanged |

## Pending Rules

<!-- Add lessons learned from future debug sessions here -->
