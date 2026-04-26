---
name: researcher
description: Source evaluation rules and discovery criteria for the Researcher agent
applyTo: .github/agents/researcher.agent.md
---

# Researcher Skills

Read this at the start of every session before evaluating any source.

## ⚠️ CRITICAL: Geographic Scope

> **Scope is ALL OF JAPAN（全日本）** — Tokyo, Osaka, Kyoto, Fukuoka, Nagoya, Sapporo, and all other prefectures are in scope.

**FORBIDDEN**: Do NOT use "開催地が東京ではない" or "東京スコープ外" as a reason to mark a source `not-viable`. This is an incorrect justification.

- A source covering only one region (e.g. 福岡のみ) is still `researched`/viable if it reliably surfaces Taiwan-related events there.
- When profiling, note which region(s) events are held in (`region: 全国 | 東京 | 大阪 | 福岡 | ...`).
- The question is: **does the source have Taiwan events?** Not: *is the venue in Tokyo?*

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
| `not-viable` | Evaluated; will NOT be scraped | Taiwan events too rare (< 2/year); ToS blocks scraping; login required |
| `researched` | Deep research complete; ready for scraper issue | Taiwan events confirmed; selectors verified; profile written |

> **`pending` and `viable` are NOT valid statuses** — `update_source.py` only accepts `not-viable` and `researched`.

**Mandatory fields for every insert:**
```python
{
    'name': '<source display name>',
    'url': '<canonical URL>',
    'category': '<government|ngo|community|commercial|...>',
    'status': '<not-viable|researched>',
    'reason': '<one sentence why this status>',  # required for not-viable
    'url_verified': True,
    'first_seen_at': now_iso,
    'last_seen_at': now_iso,
}
```

**`not-viable` reason examples:**
- 台湾イベントが年1-2件以下で密度が低すぎる
- 年1回の大型イベントで台湾人登壇は偶発的 → 手動登録推奨
- `robots.txt` がクローラーを明示的に禁止
- ログイン必須でスクレイピング不可

**NOT a valid `not-viable` reason:**
- ~~「東京以外で開催」~~ ← **スコープは全日本。絶対にこれを理由にしない。**

## After a Source Evaluation Error
1. Append an entry to `.github/skills/agents/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
