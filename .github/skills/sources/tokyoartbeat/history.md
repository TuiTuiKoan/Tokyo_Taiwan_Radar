# tokyoartbeat — History

Newest at top.

---

## 2026-04-26 — Initial implementation

**Observation**: `--source tokyoartbeat` fails with "Unknown source" error. Correct key is `tokyo_art_beat` (auto-derived from class name `TokyoArtBeatScraper`).

**Lesson**: The `--source` key is derived from the class name (CamelCase → snake_case, minus `Scraper` suffix), NOT from `SOURCE_NAME`. For `TokyoArtBeatScraper` → `tokyo_art_beat`.

**Status**: Scraper created; dry-run not yet completed (React-rendered pages are slow with Playwright). Expected runtime 3–8 minutes.
