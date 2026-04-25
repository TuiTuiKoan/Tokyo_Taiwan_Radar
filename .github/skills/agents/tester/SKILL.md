---
name: tester
description: Scraper test execution rules, output validation criteria, and report format for the Tester agent
applyTo: .github/agents/tester.agent.md
---

# Tester Skills

Read this at the start of every session before running any test.

## Scraper Testing
- Always run with `--dry-run` first to avoid writing to DB during validation.
- Check `start_date` is populated (not null) for every scraped event — missing dates are the most common data quality failure.
- Verify `source_id` is stable across two separate runs before declaring a scraper production-ready. Run twice, diff the IDs.
- For TCC scraper: confirm `start_date` is NOT the page update date (visible at the bottom of the page as `日付：`).

## Reporting
- Report failures with: source name, event title, field name, expected value, actual value.
- If > 20% of events from a source have null `start_date`, escalate to Engineer before proceeding.
- Distinguish between logic errors (wrong field extracted) and selector errors (selector no longer matches).

## After a Test Failure
1. Append an entry to `.github/skills/tester/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
