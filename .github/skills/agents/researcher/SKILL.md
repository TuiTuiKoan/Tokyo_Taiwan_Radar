---
name: researcher
description: Source evaluation rules and discovery criteria for the Researcher agent
applyTo: .github/agents/researcher.agent.md
---

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

## Research Source Status Values

When writing a source record to the `research_sources` table, use these `status` values:

| Status | Meaning | When to use |
|--------|---------|-------------|
| `not-viable` | Evaluated; will NOT be scraped | Not Taiwan-themed; annual manual entry; ToS blocks scraping |
| `viable` | Evaluated; ready for Engineer to implement | Taiwan events confirmed; selectors verified |
| `pending` | Evaluation in progress | Default before research is complete |

**Mandatory fields for every insert:**
```python
{
    'name': '<source display name>',
    'url': '<canonical URL>',
    'category': '<government|ngo|community|commercial|...>',
    'status': '<not-viable|viable|pending>',
    'reason': '<one sentence why this status>',  # required for not-viable
    'url_verified': True,
    'first_seen_at': now_iso,
    'last_seen_at': now_iso,
}
```

**`not-viable` reason examples:**
- 台湾はメインテーマではなく複数開催地の一つ（全国ツアー型）
- 年1回の大型イベントで台湾人登壇は偶発的 → 手動登録推奨
- `robots.txt` がクローラーを明示的に禁止

## After a Source Evaluation Error
1. Append an entry to `.github/skills/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
