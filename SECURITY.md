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
- Social engineering
- Issues in third-party dependencies (report upstream instead)
- Scraped content accuracy (use the in-app report feature)
