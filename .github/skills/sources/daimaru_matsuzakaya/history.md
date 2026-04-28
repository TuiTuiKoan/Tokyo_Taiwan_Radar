# daimaru_matsuzakaya Scraper History

<!-- Append new entries at the top -->

---

## 2026-04-28 — Initial implementation

**Context:** Research phase initially classified 大丸・松坂屋 as `needs-work` (React/Vite SPA requiring Playwright). Deep-dive investigation revealed a public JSON API.

**SPA JSON API discovery method:**
1. Ran Playwright with response interception on `https://www.daimaru.co.jp/tokyo/event/`
2. Filtered responses by `content-type: application/json`
3. Found: `https://www.daimaru.co.jp/spa_assets/events/tokyo.json` (HTTP 200)
4. Confirmed the same pattern for matsuzakaya: `/spa_assets/events/{slug}.json`
5. Tested `requests.get(url, headers={"Referer": page_url})` — works without Playwright

**Store slug discovery:**
- Most slugs match the URL path (e.g. `/tokyo/event/` → `tokyo.json`)
- Exception: 大丸梅田店 uses slug `umedamise` (not `umeda`)
- Discovered by parsing React Router paths in the JS bundle: `path:"/umedamise/*"`
- Command: `grep -o 'path:"/[a-z_-]*' bundle.js`

**403 stores (permanently excluded):**
- `daimaru/fukuoka` → even Playwright can't access (Waf/IP restriction)
- `matsuzakaya/takatsuki` → same

**Dedup key choice:**
- JSON `id` field (integer) is stable across daily runs — confirmed by checking that past events from 2022 still appear with the same `id` in 2026
- `source_id = daimaru_matsuzakaya_{slug}_{id}` is collision-safe across all stores

**Initial scan result (2026-04-28):**
- 11 stores accessible, 1820–2752 events per large store
- 4 Taiwan events total (all past; no current Taiwan fairs)
- dry-run output: 4 events, no errors

---
