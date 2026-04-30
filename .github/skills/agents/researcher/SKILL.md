---
name: researcher
description: Source evaluation rules and discovery criteria for the Researcher agent
applyTo: .github/agents/researcher.agent.md
---

# Researcher Skills

Read this at the start of every session before evaluating any source.

## ⚠️ CRITICAL: Canonical File Path

> **NEVER write to `.github/skills/researcher/`** — that path has been deleted.
> The canonical location is `.github/skills/agents/researcher/`.
> All agent skills live under `skills/agents/<agent-name>/`. See engineer SKILL.md for the full table.

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

## researcher.py — Schedule Management (SLOT_SCHEDULE)

`researcher.py` uses a **4-slot daily schedule** to cover all 9 research categories every day.

| Slot | JST | Categories |
|------|-----|------------|
| 0 | 06:00 | `university`, `fukuoka` |
| 1 | 12:00 | `media`, `government` |
| 2 | 18:00 | `thinktank`, `hokkaido` |
| 3 | 00:00 | `social`, `performing_arts_search`, `senses_research` |

**Key implementation rules:**
- `RESEARCH_SLOT` env var controls which slot runs. Set by GitHub Actions step before calling `python researcher.py`.
- `_resolve_slot()`: reads `RESEARCH_SLOT` env var first; falls back to deriving from JST hour.
- `_resolve_category_id()` returns `list[str]` — `run_research()` loops over each category in the slot.
- GitHub Actions: 4 cron triggers (`0 21/3/9/15 * * *` UTC). A `Determine slot` step maps UTC hour → slot and writes to `$GITHUB_ENV`.
- `github.event.schedule` returns the exact cron string (e.g. `"0 21 * * *"`) for the triggering schedule. Use shell `case` to compare it and set `RESEARCH_SLOT`.
- `workflow_dispatch` sets `github.event.schedule` to empty string — use `inputs.slot` as fallback.

**Duplicate suppression in LINE reports:**
- `known_urls` is fetched before agents run (pre-run snapshot). After `_upsert_sources()` completes, filter `report["top_sources"]` to remove any URL already in `known_urls`:
  ```python
  report["top_sources"] = [s for s in report["top_sources"] if s.get("url") not in known_urls]
  ```
- If no new verified sources remain after filtering, **skip LINE notification entirely** (log only). This prevents notification fatigue on days when GPT returns only already-known sources.
- `scraper_runs` cost logging and `research_reports` DB save are unaffected by this filter.

**When modifying the slot-to-category mapping**, update both `SLOT_SCHEDULE` in `researcher.py` and the corresponding cron comments in `researcher.yml`.

## discovery_accounts.py — Layer 2 (Weekly note.com Creator Discovery)

`scraper/discovery_accounts.py` discovers new note.com creators who post Taiwan-related content.

**Workflow (runs every Sunday 10:00 JST):**
1. 3 GPT `gpt-4o-search-preview` tasks (community events / culture & arts / food & lifestyle)
2. `_extract_creator_id()` normalises GPT output → bare slug; rejects article URLs (`/n/`) and template patterns
3. `_verify_note_creator()` confirms existence via `https://note.com/{creator_id}/rss` (HTTP GET only — no Playwright needed)
4. Loads existing known IDs from `research_sources` to skip re-insertion
5. Upserts verified creators with `status='candidate'`, `source_profile={platform: 'note.com', creator_id, categories: ['taiwan_japan']}`
6. Admin reviews at `/admin/sources` and sets `status='implemented'` to activate Layer 3 scraping

**Key rules:**
- note.com RSS: `https://note.com/{creator_id}/rss` is publicly accessible without auth.
- GPT output often includes article URLs (`/n/` path) and template strings — always validate with `_extract_creator_id()`.
- Use `--dry-run` for testing: runs GPT + verification but skips DB writes and LINE push.
- The daily scraper (`note_creators.py` or similar Layer 3 script) polls only `status='implemented'` creators from `research_sources`.
- **年份は `_THIS_YEAR = datetime.now(JST).year` を使う。** search query 文字列に年数を hardcode してはならない（毎年手動更新が必要になり、古い検索結果しか返らなくなる）。

## After a Source Evaluation Error
1. Append an entry to `.github/skills/agents/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.
