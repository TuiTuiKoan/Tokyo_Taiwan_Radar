# moonromantic — History

Newest at top.

---

## 2026-04-26 — Initial implementation

**Observation**: `--source moonromantic` failed with "Unknown source" error. Correct key is `moon_romantic` (auto-derived from class name `MoonRomanticScraper`).

**Lesson**: The `--source` key is derived from the class name (CamelCase → snake_case, minus `Scraper` suffix), NOT from `SOURCE_NAME`. For `MoonRomanticScraper` → `moon_romantic`.

**Status**: Scraper created; dry-run timed out (Playwright loading 4 Wix pages + individual posts is slow). This is expected behavior, not an error. Run with `timeout=600` or allow extended runtime.
