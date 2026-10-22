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

## ENFORCE: card_selector_hint required when feasibility=easy

Before `update_source.py --status researched --feasibility easy`, self-verify:

| Check | Required |
|-------|----------|
| Fetched listing page HTML (fetch_webpage / curl)? | ✅ |
| Identified the repeating card element from DOM? | ✅ |
| Selector is **verbatim** from HTML (no guess)? | ✅ |
| Selector matches ≥1 element in sample HTML? | ✅ |

Failure modes:
- No stable repeating selector → **downgrade to `--feasibility medium`** + record reason in `--notes`. Never pass a fabricated selector.
- Listing requires JS rendering and only static HTML available → downgrade to `medium`.

Data point (2026-05-02 batch e2e): Phase 2 success rate is **17% (1/6)** without a verbatim selector hint — GPT-4o fabricates plausible-looking CSS classes that don't exist in the real DOM.

## Source Evaluation
- Check `robots.txt` and ToS before profiling a scraping target.
- Verify whether the site uses client-side rendering — determines Playwright vs. simple HTTP fetch. Check by viewing page source vs. rendered output.
- Test rate limits: attempt 3 rapid requests and observe response headers (`Retry-After`, `X-RateLimit-*`, `Retry-After`).
- Confirm Taiwan-related events actually appear (not just Japanese-domestic events) before profiling.

## Output
- Save source profiles to `.copilot-tracking/research/sources/{source_name}.md` — the local, gitignored directory that `scraper/update_source.py --create-issue` reads. The legacy directory name is kept because the script depends on it; it is not session state.
- Always include a scraping feasibility verdict: Easy / Medium / Hard / Blocked.
- Include at least 2 example event URLs so the Scraper Expert can verify selectors.

## Research Source Status Values

When writing a source record to the `research_sources` table, use these `status` values:

| Status | Meaning | When to use |
|--------|---------|-------------|
| `not-viable` | Evaluated; will NOT be scraped | Technically unscrapable (login/robots/terminated); **or** confirmed zero Taiwan events after thorough history check |
| `researched` | Deep research complete; ready for scraper issue | Taiwan events confirmed; selectors verified; profile written |

> **`pending` and `viable` are NOT valid statuses** — `update_source.py` only accepts `not-viable` and `researched`.

## Research Exclusion List

`scraper/research_exclusions.py` (`RESEARCH_EXCLUDED_DOMAINS`) holds platforms that were tried and retired — never propose them again. `auto_research.py` refuses to assess them (domain or any subdomain, e.g. `<group>.connpass.com`). Check the list by hand before proposing a source manually.

To exclude a platform after it proves low-value:
1. Add one line `"<domain>": "<YYYY-MM> retired: <reason>"` to `RESEARCH_EXCLUDED_DOMAINS`.
2. Set its `research_sources` rows to `not-viable` with the same reason (`update_source.py --status not-viable` or SQL).

A `not-viable` row alone only blocks the exact host; use the exclusion list when the platform has per-organizer subdomains or when a whole platform (not one page) is rejected.

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

### Low-Signal Policy — assessed sources (score 0.30–0.69)

`auto_research` marks these `assessed` and leaves them for human review.
**Human reviewers MAY manually set `status=researched`** when:

- Daily scraping cost is near-zero (Playwright static HTML, < 5 pages)
- Missing a rare Taiwan event is costlier than scanning 0-result pages
- The site hosts annual events / film festivals whose schedule is not predictable in advance (e.g. JPIFF, ACROS Fukuoka, Internet Museum)
- LLM found indirect or low-signal evidence (Taiwan artists "included", Taiwan film "sometimes shown")

**NOT a valid reason to keep `assessed`:**
- ~~「スコアが低い」~~ ← Score < 0.70 は「台湾専用ではない」を示すだけ
- ~~「現時点でコンテンツなし」~~ ← 将来の掲載可能性があれば viable

**Scale for decision:**

| score | taiwan_evidence | Action |
|-------|----------------|--------|
| ≥ 0.70 | Direct | auto-promoted → `researched` |
| 0.30–0.69 | Indirect / low | Human review → manually set `researched` if scrapable |
| < 0.30 | None | Keep `not-viable` |

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

## researcher.py and discovery_accounts.py — removed 2026-10 (#318)

Both depended on `gpt-4o-search-preview`, which OpenAI retired around 2026-08-20; they then failed silently while their workflows still reported success. Before that their yield was low (researcher: $30 in 2026-07 and $19.6 in 2026-08 for 3 sources reaching `implemented` after 2026-06; discovery_accounts: accounts implemented only in 2026-04–05). Both scripts and `researcher.yml` / `discovery-accounts.yml` were removed; evidence in `docs/specs/active/llm-cost-reset/notes.md`.

- `.copilot-tracking/research/candidates/` no longer receives new files, so Step 0 of the Researcher agent normally finds none and goes straight to manual search.
- `research_sources`, `update_source.py` and `auto_scraper/auto_research.py` (which uses `research_exclusions.py`) are unchanged.
- The old slot schedule, LINE dedup and domain skip-hint rules live in git history (`scraper/researcher.py` before the removal commit) if a search-based discovery job is ever rebuilt. Rebuild it only behind the shared LLM client and a cost cap (see the llm-cost-reset spec).

## WordPress Mixed-Content Sites（日本／台湾イベント混在サイト）

For WordPress sites that publish both Japan-hosted and Taiwan-hosted events:

**1. Listing-page date pre-filter (90-day window)**
Before fetching any article, parse `<time datetime="...">` on the listing page to get the post publish date.
Skip articles older than 90 days and stop paginating when an entire page is older than 90 days.
This can reduce HTTP requests by 30–40× (e.g. 220 → 6 fetches).

**2. Three-pass Japan-event filter (`_is_japan_event()`)**
Apply in this exact order — **Stage 2 must come before Stage 3**:
- Stage 1 (title): `TAIWAN_ONLY_PATTERNS` — exclude events clearly held in Taiwan (e.g. 台湾ランタン, 澎湖花火)
- Stage 2 (body): `TAIWAN_VENUE_KW` — exclude if venue is explicitly in Taiwan (`（台湾・`, `（台湾）`, etc.)
- Stage 3 (body): `JAPAN_LOCATION_KW` — include only if a Japan city/region name is present

Reversing Stage 2 and Stage 3 causes false positives: a Taiwan-held event can mention Japanese travel companies (e.g. 近畿日本ツーリスト), which triggers Stage 3 before Stage 2 can reject it.

**3. Date extraction priority ladder for Japanese WordPress**
Never rely on the first date in the body — it is almost always the post publish date. Use this priority:
1. `日時：` labeled date range
2. Weekday-annotated range (e.g. `YYYY年M月D日（土）〜D日（日）`)
3. Labeled single date
4. Weekday-annotated single date
5. Plain date range
6. Last resort: first plain date in body (high risk of picking up the publish date)

**4. WordPress REST API check first**
Always try `/wp-json/wp/v2/posts` first. If 401, fall back to HTML scraping.

## Manual Source DB Insert Workflow

`update_source.py --create-issue` performs an **UPDATE only** — it requires the row to already exist in `research_sources`. When a source is discovered manually, insert the row first:

```python
sb.table("research_sources").insert({
    "name": "<display name>",
    "url": "<canonical URL>",
    "category": "<government|ngo|community|commercial|...>",
    "status": "candidate",
    "reason": "<one sentence>",
    "url_verified": True,
    "first_seen_at": now_iso,
    "last_seen_at": now_iso,
}).execute()
```

Note: the column is `reason`, **not** `notes` (that column does not exist).
After INSERT, run: `python scraper/update_source.py --url <url> --status researched --create-issue`

## Events テーブル — URL フィールド分離規則（2026-05-07）

3 つの URL フィールドは役割が異なる。**混在させない**。

| フィールド | 役割 | 上書き可否 |
|-----------|------|----------|
| `source_url` | 爬蟲が取得した原始 URL（戲院ページ/ニュース記事） | **絶対不可**（NOT NULL 制約、null 不可） |
| `official_url` | 配給会社/公式サイト（全国上映情報など） | 新規追加・更新はここ |
| `secondary_source_urls` | 合併元の追加 URL（配列） | `source_url` と重複させない |

**操作手順（公式サイト URL を追加する場合）:**
```python
sb.table("events").update({"official_url": "https://example.com/"}).eq("id", eid).execute()
# NG: source_url は触らない
```

**`secondary_source_urls` の重複排除:**
```python
# source_url と同じ URL を secondary から除外してから保存
secondary = [u for u in secondary_urls if u != event["source_url"]]
```

## Works テーブル — 検索・新規作成規則（2026-05-07）

**検索時は全タイトル列 + director を OR 検索すること:**
```sql
SELECT * FROM works
WHERE title_ja ILIKE '%keyword%'
   OR title_zh ILIKE '%keyword%'
   OR original_title ILIKE '%keyword%'
   OR title_en ILIKE '%keyword%'
   OR director ILIKE '%keyword%';
```

**events 検索も `raw_title` と `name_ja` の両方を確認する**（annotation 後に title が変わる）:
```sql
SELECT * FROM events
WHERE raw_title ILIKE '%keyword%'
   OR name_ja ILIKE '%keyword%';
```

**新規 work 作成時の必須フィールド:**
```python
{
    "title_ja": "<日本語タイトル>",
    "title_zh": "<繁体字タイトル>",
    "title_en": "<英語タイトル（公式 og:title など）>",
    "director": "<中文漢字（読み）/ 中文漢字（読み）>",  # 共同監督はスラッシュ区切り
    "external_links": {"official": "<公式URL>"},
}
```

**監督名フォーマット例:** `黄明川（ホアン・ミンツァン）/ 連楨惠（リェン・チェンフイ）`

## After a Source Evaluation Error
1. Append an entry to `.github/skills/agents/researcher/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## `--create-issue` Permission Consistency

When documenting or running source status updates with `python scraper/update_source.py --create-issue`, use one canonical permission wording:

* Fine-grained PAT: `Issues: write + Metadata: read`
* Classic token: `repo` scope

Do not use non-standard expressions (such as `&`-separated permissions) in profiles, summaries, or agent guidance.

## Token Checklist Source of Truth

For token sync and rotation references, always point to:

* `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` (canonical checklist)

`/.github/TOKEN_SYNC_CHECKLIST.md` is redirect-only and should not be used as an editable checklist body.
