# taiwan_matsuri Scraper History

<!-- Append new entries at the top -->

---
## 2026-04-28 — geographic filter + dry-run-only fix caused missed events

**Error 1:** Initial implementation (commit `3ff81d2`, April 25) included `_TOKYO_KANTO_KEYWORDS` filter: `東京|スカイツリー|横浜|幕張|千葉|埼玉`. Venues in Gunma (`群馬太田`), Kumamoto, Fukuoka, Nara, Shimane were silently dropped. Only スカイツリー events were captured.

**Error 2:** Fix commit (`1d3cd1c`, April 26) removed the filter correctly but executed `--dry-run` only. The dry-run confirmed Kumamoto was found, but no DB write occurred. `202603-gunmaota` (Gunma, active since March) and `202604-kumamoto` (started April 24) remained absent from DB until manual run on April 28.

**Fix:** Removed `_TOKYO_KANTO_KEYWORDS` entirely. Ran `python main.py --source taiwan_matsuri` (non-dry-run) on April 28 to write both missing events. Annotator processed 2 events (`lifestyle_food`, `taiwan_japan`).

**Lesson 1:** Never restrict a scraper to Tokyo/Kanto. Project scope is 全日本. → Added to `BaseScraper Contract` and `taiwan_matsuri-specific` in SKILL.md.

**Lesson 2:** After fixing a filter bug, always follow with a real run, not just dry-run. → Added to `BaseScraper Contract` in SKILL.md.
