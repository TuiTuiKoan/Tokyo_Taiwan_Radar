# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.
