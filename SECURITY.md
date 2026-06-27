# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Tokyo Taiwan Radar, please report it responsibly.

**Do NOT open a public GitHub Issue for security vulnerabilities.**

Instead, please email: **tuitui.koan@gmail.com**

You will receive a response within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

The following are in scope for security reports:

- **Web application** (tokyotaiwanradar.com): XSS, CSRF, authentication bypass, data exposure
- **API endpoints**: unauthorized access, injection attacks
- **Scraper pipeline**: command injection, SSRF via scraped URLs
- **Infrastructure**: Supabase RLS bypass, environment variable exposure

## Out of Scope

- Denial of service attacks
- Social engineering targeting maintainers (phishing, pretexting against project members)
- Issues in third-party dependencies (report upstream instead)
- Scraped content accuracy (use the in-app report feature)

## Prompt Injection & Untrusted Content

Tokyo Taiwan Radar scrapes event content from external sources and passes it to an LLM for annotation. **All scraped text (titles, descriptions) is treated as untrusted input:**

- Before annotation, `scraper/security/injection_guard` scans for prompt-injection and social-engineering patterns. GPT input is wrapped in an `<UNTRUSTED_EVENT_DATA>` delimiter to reduce prompt-extraction and instruction-injection risk.
- Findings of severity >= 2 are queued to `event_reports` and surfaced in `/admin/reports` for human review (confirm / dismiss); they never mutate event data automatically.
- This is defense-in-depth: LLM-side guards are not a complete trust boundary, so human review and least-privilege remain the final safeguard.

Note: social engineering targeting maintainers (e.g. phishing) stays out of scope above; this section covers only injection / social-engineering text embedded in *scraped content*.
