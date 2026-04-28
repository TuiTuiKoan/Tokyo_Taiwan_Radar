# hankyu_umeda Scraper History

<!-- Append new entries at the top -->

---

## 2026-04-28 — Initial implementation

**Context:** Research phase confirmed 阪急うめだ本店 as the only immediately viable static-HTML target among major Japanese department stores. All other chains (大丸松坂屋、高島屋、三越伊勢丹、西武そごう) were SPAs or had HTTP/2 errors.

**Non-obvious decisions:**
- `location_address` hardcoded as `"大阪府大阪市北区角田町8-7 阪急うめだ本店"` — page does not expose a machine-readable address.
- `category` defaults to `["lifestyle_food"]` for all Taiwan展-type events; annotator will refine.
- `source_id` uses URL slug from the detail link (e.g. `hankyu_umeda_taiwan_life`) — slug is stable across CI runs. SHA1 fallback for events without a dedicated detail page.
- Year inference rolls over December→January: if the scraped month < current month AND the difference is large (e.g. current=December, scraped=1→next January), use next year.
- Taiwan展（台湾ライフ等）is typically held in autumn (September–November). During spring/summer the scraper will return 0 events — confirmed correct during 2026-04-28 dry-run (65 total items, 0 Taiwan).

---
