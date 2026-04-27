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
| `not-viable` | Evaluated; will NOT be scraped | Technically unscrapable (login/robots/terminated); **or** confirmed zero Taiwan events after thorough history check |
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

**`not-viable` reason examples (valid):**
- `robots.txt` がクローラーを明示的に禁止
- ログイン必須でスクレイピング不可
- サービス終了済み（例：PassMarket）
- 過去のアーカイブを徹底調査した結果、台湾関連活動がゼロ件
- ストリーミング/VODサービス（物理的イベントが存在しない）

**NOT valid `not-viable` reasons:**
- ~~「東京以外で開催」~~ ← **スコープは全日本。絶対にこれを理由にしない。**
- ~~「台湾イベントが年1-2件以下で少ない」~~ ← **低頻率は理由にならない（下記 Low-Signal Policy 参照）**
- ~~「現在は台湾コンテンツなし」~~ ← **過去実績があれば viable（将来も出る可能性）**

## Low-Signal Source Policy（2026-04-27）

> **The scraper runs once per day. Adding an extra source costs near-zero CPU.**
> Optimize for coverage over precision — missing a signal is worse than scanning 0 events.

**New acceptance threshold**: A source is viable if:
1. Taiwan-related events have **ever** occurred in its history, **AND**
2. The source is technically scrapable (Playwright OK; no login required; not terminated)

**"Too infrequent" is no longer a valid rejection reason.**

Use `LOOKBACK_DAYS` to match the source's natural cadence:

| Source cadence | Recommended LOOKBACK_DAYS |
|---------------|---------------------------|
| Weekly / daily | 30 |
| Monthly | 60 |
| Quarterly | 90 |
| Annual | 365 |
| Biennial | 730 |

**Re-evaluation candidates** (previously marked `not-viable` for frequency/Tokyo-scope reasons):
- `[27]` 京都大学人文科学研究所 — scope exclusion lifted
- `[81]` 福岡アジア美術館 — scope exclusion lifted
- `[41]` シネスイッチ銀座 — occasional Taiwan films viable with daily scan
- `[38]` Uplink Shibuya — proven Taiwan film history
- `[35]` Human Trust Cinema — re-verify URL
- `[1]` 東大先端研 (RCAST) — Taiwan × economic security events
- `[2]` Asia University Asian Studies — Asia Watcher series
- `[78]` note.com — curated creator list approach

## After a Source Evaluation Error
1. Append an entry to `.github/skills/agents/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
