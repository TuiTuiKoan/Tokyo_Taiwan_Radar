---
description: "Implementation history and incident notes for the Peatix scraper"
---

# Peatix Scraper — Implementation History

---

## 2026-06-29 — Detail text blocks, cookie rescue, and price fallback

**問題：** Peatix rows scraped during the OneTrust cookie-wall period could keep `raw_description` as cookie text, while detail pages still had useful structured content in rendered text blocks. Some pages also exposed `business_hours` and venue only through `DATE AND TIME` / `日時` and `LOCATION` / `場所` blocks. Price selectors could return only generic labels such as `料金`, leaving `price_info` empty even when the body contained `参加費｜800円(税込)`.

**根本原因：** The scraper depended too heavily on CSS selector output and did not treat Peatix's rendered text blocks as authoritative field boundaries. Existing dirty rows were also protected by normal idempotent upsert behavior, so `main.py --rescrape-ids` did not overwrite the cookie-wall data.

**修復：** Add explicit text-block helpers for location and business hours, detect online events before physical fallbacks, reject generic address labels, and use body price labels only when selectors are empty or generic. Historical cookie-wall rows require a direct-URL rescue path with `force_keys` and a targeted annotator rerun after re-querying rescued UUIDs.

**教訓：** Peatix field extraction should read the rendered text contract first, then fall back to selectors. Treat label-only selector output as empty, use high-confidence body labels for price, and never expect normal non-force upsert to repair existing cookie-wall rows.