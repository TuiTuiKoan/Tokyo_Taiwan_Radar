# IFI Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-04-26 — Initial implementation: URL injected into location_address

**Error:** `会場：` value included a map URL on the second line (e.g., `https://www.u-tokyo.ac.jp/campusmap/...`). This caused `location_address` to contain a URL when joining all venue lines.

**Root cause:** `_extract_info()` captures up to 3 lines after the `会場：` label. IFI adds a campus map link directly after the venue name without a visual separator.

**Fix:** Filter venue lines using `not ln.strip().startswith("http")` before building `location_name` / `location_address`.

**Lesson:** Always filter HTTP lines from venue/address fields — academic sites frequently append map links directly below venue names.

---
