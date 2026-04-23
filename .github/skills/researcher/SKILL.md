# Researcher Skills

Read this at the start of every session before evaluating any source.

## Source Evaluation
- Check `robots.txt` and ToS before profiling a scraping target.
- Verify whether the site uses client-side rendering — determines Playwright vs. simple HTTP fetch. Check by viewing page source vs. rendered output.
- Test rate limits: attempt 3 rapid requests and observe response headers (`Retry-After`, `X-RateLimit-*`, `Retry-After`).
- Confirm Taiwan-related events actually appear (not just Japanese-domestic events) before profiling.

## Output
- Save source profiles to `.copilot-tracking/research/sources/{source_name}.md`.
- Always include a scraping feasibility verdict: Easy / Medium / Hard / Blocked.
- Include at least 2 example event URLs so the Scraper Expert can verify selectors.

## After a Source Evaluation Error
1. Append an entry to `.github/skills/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
