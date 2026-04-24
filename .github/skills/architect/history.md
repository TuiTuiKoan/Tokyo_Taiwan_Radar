# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.
