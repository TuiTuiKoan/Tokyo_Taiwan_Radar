---
title: Pure Publication Policy Changes Log
description: publication-policy 實作、驗證、資料 dry-run 與剩餘風險的持續交付紀錄
---

## Status

* State: VALIDATED RELEASE CANDIDATE, independent Tester PASS
* Worktree: `ttr-publication-policy-worktree`
* Branch: `feat/publication-policy`
* Base SHA: `2ef1a94721a8f685e5b3f2223bffe6628fc1125a`
* Spec: active
* Local feature commits: one atomic feature commit (this changeset; hash assigned by Git)
* Final Tester verdict: PASS; the prior 11/11 governance exact-parity and tracking blockers are resolved

## Safety Boundaries

* Live DB writes: none
* Backfill apply: not executed
* QA live reconcile: not executed
* DuckDuckGo/OpenAI publisher search: not executed
* Git push: not executed
* Merge: not executed
* Deploy: not executed
* Main worktree WIP: not modified, staged, stashed, or reset

## Phase 0 Results

### Worktree and environment

* `main` and `origin/main` both resolved to `2ef1a947` before provisioning
* Target path and branch were absent, so state matrix result was NEW
* Worktree path/branch/HEAD matched the approved plan and was clean
* Main repo `.git/info/exclude` now contains `ttr-publication-policy-worktree/`
* Python uses the existing repo venv with Python 3.14.3 and Supabase 2.30.0
* Web dependencies were installed from the pnpm store with `--offline --frozen-lockfile`
* Next.js 16.2.10 local docs were read for Server/Client Components, dynamic params,
  route handlers, metadata, JSON-LD, Playwright, and Vitest

### Read-only baseline drift

Baseline generated at `2026-07-11T10:58:44Z` by full pagination with exact-count
cross-checks. Raw output is stored in ignored
`tmp/publication-policy/baseline.json`.

| Metric | Approved-plan baseline | Current read-only baseline | Drift |
|--------|------------------------|----------------------------|-------|
| Events containing `publication` | 326 | 333 | +7 |
| Active containing `publication` | 307 | 314 | +7 |
| Exact pure rows | 324 expected core rows | 332 | +8 before conflict exclusion |
| Exact mixed rows | 2 | 1 | -1 because Eslite is now misclassified exact pure |
| NDL rows | 269 | 275 | +6 |
| Hanmoto rows | 55 | 56 | +1 |
| NDL periodical family | 119 | 125 | +6 |
| All field corrections | 6,859 | 6,877 | +18 |
| Publication field corrections | 3,173 | 3,180 | +7 |
| Relevant non-empty policy locks | 856 | 857 | +1 |
| Events with relevant non-empty locks | 146 | 146 | 0 |
| Empty sentinel policy locks | 0 | 0 | 0 |
| Pending publication QA rows | 57 | 59 | +2 |
| Pending prefecture false positives | 37 | 39 | +2 |
| Pending missing-date rows | 20 | 20 | 0 |
| Organizer rows | 204 | 204 | 0 |
| Organizer homepages | 0 | 0 | 0 |

Pure rows currently violating at least one intentional-null field: 231.
Non-null counts are address 231, localized addresses 214 each, hours 210 in each
locale, and prefectures 11.

### Classification conflicts and exclusions

* Classification conflict: one active Eslite row is exact pure but has physical-event
  evidence. It is a release Talk at 誠品生活日本橋 with a Tokyo address, prefecture,
  lottery fee, and a known article UUID URL. The current source identity still uses
  `eslite_spectrum_9` and `/news/catalog/9`. It must be excluded from pure cleanup
  and handled only by the gated Eslite migration action.
* Exact mixed exclusion: one inactive user submission has forms
  `lecture + publication + networking`. It remains excluded and untouched.
* Expected Wave 1 pure cleanup cohort before later manifest conflict scans: 331
  NDL/Hanmoto rows. This is a drift-derived expectation, not a hardcoded apply gate.

### Concurrent-writer gate

* Local publication backfill, annotator, auto-QA, and scraper processes: none
* GitHub Actions in-progress runs: none
* GitHub Actions queued runs: one stale `web-darkmode-smoke` run created on
  2026-05-15; it is not a publication/data writer

## Modified Files

### Python

Runtime implementation is complete in the worktree across the shared publication policy,
writer, annotator, QA, four source adapters, manifest planner, and poster guard. The
targeted Tester fix did not modify Python runtime code.

### Web

Web implementation is complete in the worktree across shared helpers, presentation,
structured data, intake guidance, admin metrics, and deterministic fixtures. The
targeted Tester fix did not modify TypeScript runtime code.

### Tests

Deterministic Python, Web, structured-data, i18n, build, and browser evidence is
summarized in the Phase 6 release-candidate section below.

### Governance and Docs

* `docs/specs/active/publication-policy/proposal.md`
* `docs/specs/active/publication-policy/tasks.md`
* `docs/specs/active/publication-policy/changes-log.md`
* `.github/instructions/scraper.instructions.md`
* `.github/agents/engineer.agent.md`
* `.github/agents/scraper-expert.agent.md`
* `.github/skills/agents/engineer/SKILL.md`
* `.github/skills/agents/scraper-expert/SKILL.md`
* `.github/skills/agents/tester/SKILL.md`
* `.github/skills/scraper-expert/SKILL.md`
* `.github/skills/sources/eslite_spectrum/SKILL.md`
* `.github/skills/sources/hanmoto/SKILL.md`
* `.github/skills/sources/kawade_rss/SKILL.md`
* `.github/skills/sources/ndl_opensearch/SKILL.md`

## Phase Summary

### Phase 0

PASS. Worktree/spec provisioning, instruction loading, local dependency setup,
read-only baseline, drift capture, and concurrent-writer gate are complete.

### Phases 1 to 5

PASS for worktree implementation and deterministic validation. Wave 1 live apply,
Eslite live remap, and QA live reconcile remain intentionally unexecuted.

### Phase 6

PASS. Independent Tester re-verification found no blockers after the 11/11 governance
exact-parity and release-tracking corrections. Live DB apply, Wave 2, push, merge,
and deploy remain intentionally unexecuted.

## Validation Log

| Command or check | Result |
|------------------|--------|
| `git fetch origin` plus ahead/behind check | PASS, 0 ahead and 0 behind |
| Worktree state matrix and registration check | PASS, exact path/branch/HEAD |
| `git check-ignore` for worktree directory | PASS |
| Initial worktree diagnostics | PASS, no errors |
| Spec Markdown diagnostics | PASS, no errors |
| `pnpm install --offline --frozen-lockfile` | PASS, 752 reused and 0 downloaded |
| `git check-ignore` for baseline/manifest/snapshot | PASS, all matched `tmp/` |
| Baseline Python diagnostics | PASS, no errors |
| Full paginated Supabase read-only baseline | PASS, all exact counts matched fetched rows |
| Local writer process scan | PASS, none found |
| GitHub Actions in-progress scan | PASS, none found |

## Phase 2A Source Slice (2026-07-11)

### Scope

* Only Phase 2A source slice was implemented in this pass.
* No live DB writes, remap apply, push, merge, or deploy were performed.
* Eslite UUID identity migration gate remains default-blocked and requires explicit offline override (`ESLITE_ALLOW_UUID_IDENTITY=1`) for verification runs.

### Modified files in this slice

* `scraper/sources/hanmoto.py`
* `scraper/sources/eslite_spectrum.py`
* `scraper/sources/ndl_opensearch.py` (existing fix retained; no rework)
* `scraper/sources/kawade_rss.py` (existing fix retained; no rework)
* `scraper/tests/test_publication_sources.py`
* `scraper/tests/fixtures/publication/ndl_feed.xml`
* `scraper/tests/fixtures/publication/ndl_periodical_feed.xml`
* `scraper/tests/fixtures/publication/kawade_feed.rdf`
* `scraper/tests/fixtures/publication/eslite_news.html`
* `scraper/tests/fixtures/publication/eslite_article_talk.html`
* `scraper/tests/fixtures/publication/hanmoto_detail.html`
* `docs/specs/active/publication-policy/tasks.md` (Phase 2A checkboxes only)
* `docs/specs/active/publication-policy/changes-log.md` (this appended section)

### Command results

| Command | Result |
|---------|--------|
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_publication_sources.py scraper/tests/test_publication_rules.py -q` (first run) | `2 failed, 17 passed in 2.20s` |
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_publication_sources.py scraper/tests/test_publication_rules.py -q` (after source fix) | `19 passed in 1.29s` |

### Implemented outcomes

* Hanmoto now removes fake hours/price placeholders, preserves real book price metadata, keeps detail anchor href evidence in `raw_description`, and separates URL semantics (`official_url` content page only; `organizer_url` strict validator only).
* Eslite now accepts only `/news/<UUID>` listing targets, uses article UUID for `source_id`, separates page publish date from event datetime, prioritizes physical talk/seminar/workshop signals, preserves venue/address/hours/price for physical records, and enforces an explicit migration gate.
* NDL/Kawade previously passing Phase 2A behavior was preserved without rework; fixture tests now cover ordinary pure book, NDL periodical, Kawade physical talk, Eslite physical talk, Hanmoto real price/URL semantics, and source/category negative.

## Remaining Risks and Tester Focus

* Eslite is currently misclassified exact pure. The migration gate must prevent
  duplicate old/new identities, and no live remap may occur in this delivery.
* All 857 relevant FC locks are non-empty legacy values. Writer overwrite and
  seven-field read-back tests are a release-critical surface.
* Baseline drift added seven source rows and six NDL periodicals. Manifest tests
  must derive current counts and must not reuse planning numbers as apply criteria.
* No organizer homepage currently exists in the registry. Wave 1 must treat
  unresolved homepage as valid and must not invoke Wave 2 providers.
* Browser and structured-data fixtures must prove a physical books-media Talk is
  not hidden merely because of category, source, or title wording.

## Phase 2B + 2C Core Slice (2026-07-11)

### Scope

* 僅完成 publication-policy 的 Phase 2B + 2C core slice，並在既有 worktree WIP 上增量修補。
* 無 DB write、無 network data write、無 push、無 merge、無 deploy。
* 僅調整 writer/annotator/publication helper、對應 publication 測試與 spec 追蹤文件。

### Modified files in this slice

* `scraper/database.py`
* `scraper/annotator.py`
* `scraper/publication_rules.py`
* `scraper/tests/test_database_publication.py`
* `scraper/tests/test_annotator_publication.py`
* `docs/specs/active/publication-policy/tasks.md`
* `docs/specs/active/publication-policy/changes-log.md`

### Implemented outcomes

* Writer contract:
  * `publication` 已納入 writer valid forms。
  * `_event_to_row()` 在任何 entity enrichment 前即 enforce exact-pure 七欄 NULL policy。
  * writer 明確支援 `location_prefectures` 與 `location_url`。
  * exact pure rows 跳過 venue lookup / venue FK / venue-hours propagation。
  * organizer registry homepage 回填改為 validated-only（透過 `publication_rules.validated_registry_homepage()`）。
  * force-rescrape 在 FC 套用後再次 enforce pure policy；舊 non-empty policy FC 會 raise observable conflict。
  * upsert 取得 UUID 後，以 `ignore_duplicates=False` 覆寫七個 empty-sentinel FC。
  * read-back 同時驗證 events 七欄 NULL 與 FC 七欄 empty sentinel；任一失敗直接 raise，非靜默成功。
  * `_auto_lock_location()` 以 normalized row / pure flag 跳過 pure rows。
* Annotator contract:
  * 不以 source whitelist 作 pure domain truth；以 exact `event_form == ["publication"]` 為準。
  * pure publication 流程移除 address/hours/price 假占位寫入。
  * publisher 僅採 scraper/DB/registry evidence；registry homepage 僅在 validation 通過時回填。
  * normal / fix-reviewed / re-annotate-all 共用最後一層 pure final normalization。
  * 舊 non-empty policy FC 會產生 conflict（raise）而非恢復 placeholder。
  * 新增 pre-write payload guard；pure postcondition violation 會進入 error path，不會以成功完成收斂。

### Command results

| Command | Result |
|---------|--------|
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_database_publication.py scraper/tests/test_annotator_publication.py scraper/tests/test_publication_rules.py -q` | `31 passed, 11 warnings in 2.08s` |
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_annotator_*.py -q` | `32 passed in 1.95s` |

### Notes

* warning 僅為既有 `datetime.utcnow()` deprecation，非本 slice 新引入。
* 本次未修改 source/web/QA/admin/governance 以外 contract 面，並保留所有既有 WIP 檔案狀態。

## Phase 3 Tracking Close (2026-07-11)

### Scope

* 只封閉既有 Phase 3 實作的驗證與 tracking，不擴大到 Phase 4/5。
* 無 DB write、無 network write、無 push、無 commit、無 deploy。
* State 維持 IN PROGRESS（Phase 4/5 未完成）。

### Phase 3 Plan Cross-check

* QA venue/hours/prefecture/price 只略過 exact pure：已落地（`scraper/auto_qa.py` + `scraper/tests/test_auto_qa_publication.py`）。
* Pure missing publisher 維持 pending：已落地（`_check_missing_organizer` 不再 pure-skip + test 覆蓋）。
* Reconcile 全 report types 與 compound/manual 保護：已落地（`_all_auto_report_types`、`_resolve_report_disposition` + tests）。
* source-based cleanup live apply path 退役：已落地（`_oneoff_cleanup_publication_pending_qa.py` dry-run only）。
* Admin quality/roadmap 改用 pure helper 與 `event_form` prerequisite：已落地。
* 四 intake routes 採 shared constant：已落地（`PURE_PUBLICATION_EVENT_FORM_GUIDANCE`）。
* 四 route parity tests：已落地（`web/tests/intake-guidance-parity.test.ts`）。
* scraper instruction、Engineer/Scraper Expert docs：已落地（`.github/instructions/` + `.github/agents/` + `.github/skills/agents/`）。
* Tester 與四個 source skills：已落地（`.github/skills/agents/tester/` + `.github/skills/sources/*/`）。
* 相應 history lessons：已落地（agents/source skills history 檔已更新）。

### Command Results

| Command | Result |
|---------|--------|
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_auto_qa_publication.py scraper/tests/test_publication_pending_cleanup.py -q` | `13 passed in 0.04s` |
| `cd web && pnpm exec tsx --test tests/intake-guidance-parity.test.ts tests/publication-policy.test.ts` | `8 passed` |
| `/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python -m pytest scraper/tests/test_auto_qa_publication.py -k 'compound or all_auto_report_types or single_auto_report_type or resolve_report_disposition' -q` | `6 passed, 6 deselected in 0.10s` |

### Static and Unit Confirmation

* 四 intake routes shared constant：4 條 route 都 `import { PURE_PUBLICATION_EVENT_FORM_GUIDANCE } from "@/lib/intakeGuidance"`，且 prompt 內容都注入同一 constant。
* admin select event_form：
  * `web/app/[locale]/admin/quality/page.tsx` 的 missing-address query 已 `select(..., event_form)` 並用 `isPurePublicationRecord` 過濾 exact pure。
  * `web/app/[locale]/admin/roadmap/page.tsx` 的 `cols` 已含 `event_form`，且 fill-rate 判定走 `isPurePublicationRecord`。
* compound reconcile：`scraper/auto_qa.py` 已採 `_all_auto_report_types` + `_resolve_report_disposition`，不再依賴 `report_types[0]`。

### Governance Modified Files

* `.github/agents/engineer.agent.md`
* `.github/agents/scraper-expert.agent.md`
* `.github/instructions/scraper.instructions.md`
* `.github/skills/agents/engineer/SKILL.md`
* `.github/skills/agents/engineer/history.md`
* `.github/skills/agents/scraper-expert/SKILL.md`
* `.github/skills/agents/scraper-expert/history.md`

## Admin Metric Lint and Contract Fix (2026-07-11)

### Scope

* `admin/quality` missing-address rows now use a local concrete row type with
  typed `event_form`, `location_name`, and `location_prefectures`; the
  `any[]` cast was removed.
* `admin/roadmap` now uses `Record<string, unknown>` and narrows
  `event_form` to strings before exact-pure evaluation.
* Pure publication fill-rate exemptions are limited to
  `location_address` and `location_prefectures`. `location_name` is measured
  from its actual value.
* `web/tests/publication-policy.test.ts` asserts that `location_name` cannot
  re-enter the intentional-null metric allowlist.
* No DB write, push, commit, merge, or deploy was performed.

### Command Results

| Command | Result |
|---------|--------|
| `pnpm exec tsx --test tests/publication-policy.test.ts tests/publication-rendering-structured-data.test.ts tests/intake-guidance-parity.test.ts` | PASS, 16 tests passed, 0 failed |
| `pnpm exec tsc --noEmit` | PASS, exit 0 |
| Full publication touched-file `pnpm exec eslint` command | PASS, exit 0; jsx-ast-utils emitted its upstream `TSNonNullExpression` resolver notice with no lint warning or error |
* `.github/skills/agents/tester/SKILL.md`
* `.github/skills/agents/tester/history.md`
* `.github/skills/sources/eslite_spectrum/SKILL.md`
* `.github/skills/sources/eslite_spectrum/history.md`
* `.github/skills/sources/hanmoto/SKILL.md`
* `.github/skills/sources/hanmoto/history.md`
* `.github/skills/sources/kawade_rss/SKILL.md`
* `.github/skills/sources/kawade_rss/history.md`
* `.github/skills/sources/ndl_opensearch/SKILL.md`
* `.github/skills/sources/ndl_opensearch/history.md`

### Slice checkpoint status

* At this slice checkpoint, Phase 4 public presentation and structured data were still open; later sections record their completed validation.
* At this slice checkpoint, Phase 5 immutable manifest and Wave 1 dry-run were still open; later sections record their completed validation.

## Phase 5 Immutable Manifest and Wave 2 Boundary (2026-07-11)

### Scope

* 重構既有 `scraper/_oneoff_backfill_publication_metadata.py`，沒有新增第二支 apply script。
* Pure planning、immutable JSON、apply drift gate、rollback snapshot 與 read-back contract 都收斂在既有 script，unit tests 不需連線 DB。
* 本輪只有全量唯讀 Wave 1 dry-run。未執行 apply、Eslite live remap、QA live reconcile、network search、commit、push、merge或 deploy。
* `tmp/publication-policy/*.json` 由主 repo `.git/info/exclude` 的 `tmp/` 規則忽略，manifest 寫入前與寫入後都已用 `git check-ignore` 驗證。

### Modified files in this slice

* `scraper/_oneoff_backfill_publication_metadata.py`
* `scraper/tests/test_publication_manifest.py`
* `docs/specs/active/publication-policy/tasks.md`
* `docs/specs/active/publication-policy/changes-log.md`

### Implemented contract

* 預設 CLI 使用 mutation-blocking Supabase proxy，拒絕 `insert`、`update`、`upsert`、`delete` 與 `rpc`。只有同時提供 `--apply --manifest PATH` 才能進入 future apply path。
* 四張表都先以 `count="exact", head=True` 取 exact count，再以 500 rows 分頁全量讀取。每張表的 fetched count 必須等於 exact count。
* Candidate universe 只取正規化 `event_form` 含 `publication` 的 rows。只有 shared `is_pure_publication_record()` exact helper 決定 pure cleanup；source、category與 title prefix只寫入 evidence。
* Manifest 包含 schema/version、generated timestamp、四表 hash/read fingerprint、candidate UUID/source identity/updated timestamp/full before hash、classification evidence、完整 event before/after、FC before/after、report planned disposition與 organizer before/after。
* Pure cleanup 對七欄逐欄計畫 `qa_auto_fix.unlock_and_write(..., mode="lock_empty")`。Apply contract要求每欄與每 row read-back。
* Apply 只讀 manifest 中既定 changes，不重新計算。任何 full-table fingerprint drift 或 unresolved non-Eslite classification/location conflict 都在 snapshot與 DB write前停止。
* Apply 前的 immutable rollback snapshot包含 events、field corrections、event reports與 organizers四張完整表，並記錄 restore order、conflict keys與逐 row read-back要求。
* Eslite Talk 是獨立 migration action，記錄 old/new source ID、article URL、physical form與需保留的 date/venue/address/prefecture/location URL/venue ID/price。此次沒有 live remap。
* NDL periodical title repair只在 R000000004來源 evidence成立時規劃；任何既有 title FC都保持不動。
* `price_info` 僅在三個明確 fake placeholder allowlist值完全符合時清除；`—`及任何真實價格都保留。
* Wave 2 schema明列 DuckDuckGo HTML與 OpenAI search-preview provider evidence、cost unit與獨立 manifest boundary。本輪兩者皆 disabled、network disallowed、max cost 0。

### Dry-run command and exact result

首次執行因 worktree沒有 `.env` 而在任何 network/DB operation前停止。後續以 `PUBLICATION_MANIFEST_ENV_FILE` 指向主工作樹既有 ignored `scraper/.env`，沒有複製或修改 secret：

```bash
cd ttr-publication-policy-worktree/scraper
PUBLICATION_MANIFEST_MODE=read-only \
PUBLICATION_MANIFEST_ENV_FILE="/Users/flyingship/development/Tokyo Taiwan Radar/scraper/.env" \
  "/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python" \
  _oneoff_backfill_publication_metadata.py \
  --manifest-output ../tmp/publication-policy/wave1-manifest-20260711-phase5-v2.json
```

| Metric | Exact result |
|--------|--------------|
| Events exact/fetched | 2,101 / 2,101 |
| Field corrections exact/fetched | 6,877 / 6,877 |
| Event reports exact/fetched | 2,717 / 2,717 |
| Organizers exact/fetched | 204 / 204 |
| Manifest candidates | 333 |
| Included pure cleanup | 323 |
| Eslite migration actions | 1 |
| Mixed exclusions | 1 |
| Classification/location conflicts | 9, including Eslite |
| Non-Eslite location conflict blockers | 8 |
| Candidates with legacy non-empty policy FC | 145 |
| NDL periodical candidates | 125 |
| Candidates with planned periodical title repair | 46 |
| Explicit fake prices planned for clear | 146 |
| Real/non-allowlisted prices preserved | 65 |
| Resolved existing/registry homepages | 1 |
| Unresolved publisher homepages, valid Wave 1 outcome | 322 |
| Planned NULL count per policy field | 323 each |
| Planned empty sentinel count per policy field | 323 each |
| Planned report dispositions | confirm 39, keep 20, unchanged 1,063 |

### Conflicts and exclusions

* Eslite physical Talk `50c83c11-ed64-481a-bb5a-caa3e9981943` has `location_name=誠品生活日本橋`。Manifest excludes it from pure cleanup and preserves venue/address/prefecture/price while planning the separate UUID identity migration。
* Inactive mixed user submission `c56fbc6a-3d66-48f2-ae36-0a053126925c` has forms `lecture, publication, networking`。Manifest excludes it unchanged。
* Eight additional exact-pure rows contain `location_name=大阪城ホール` and remain excluded as classification/location conflicts: `0ca66140-4eb1-45a8-b3c4-9b61740705e4`, `3995e531-4ebe-403a-ac4d-f1bc7119c5c9`, `3dd4c8c8-d433-4221-961a-3b3c9b58d05e`, `407b750a-5f6c-427c-8206-542a278deb04`, `66aa80d7-7db2-41d4-882c-5ab759be4419`, `77d0177e-1709-4b09-9402-80c32a71e2b4`, `c1be1d3b-3708-42ba-9fe7-1c081dfe6d35`, `c865cbda-b9d3-4bc9-b14c-289771ec1260`。
* Future apply is intentionally blocked at zero writes while these eight non-Eslite conflicts remain in the manifest。They require human classification before a fresh manifest can be approved。

### Validation results

| Command or check | Result |
|------------------|--------|
| Focused manifest tests plus publication rules/writer/annotator/QA/cleanup regressions | PASS, 59 tests passed, 11 existing `datetime.utcnow()` warnings |
| Manifest immutable hash reload | PASS |
| Exact count equals fetched count for all four tables | PASS |
| Seven fields planned NULL and seven FC sentinels planned empty for every included pure row | PASS, 323 per field |
| Eslite preservation and inactive mixed exclusion assertions | PASS |
| Secret-like regex and loaded environment-value scan | PASS, no secret material |
| Wave 2 provider call count | 0 |
| Apply execution | NOT RUN |
| QA live reconcile | NOT RUN |

### Phase 5 v2 checkpoint blockers

* Eight `大阪城ホール` location conflicts required correction at this checkpoint; the poster-placeholder targeted fix below resolves them and regenerates the manifest with zero unresolved non-Eslite location conflicts。
* The Eslite migration action remains planned only。Live remap requires a later explicit approval and a fresh no-drift manifest。
* Wave 2 homepage enrichment remains a separate future task with a separate manifest、cost approval、evidence review與 Tester gate。

## Poster Placeholder Pollution Targeted Fix (2026-07-11)

### Scope

* 在既有 publication worktree 原地接續，針對 poster-placeholder pollution 做 root-cause targeted fix。
* 僅修改允許範圍內檔案：`scraper/enrich_poster.py`、publication manifest script/tests、spec tasks/changes-log、architect skill/history。
* 全程未執行 DB write/apply、未執行 network search、未 push、未 commit、未 deploy。

### Research evidence captured for the 8-row signature

* 8 筆全為 exact pure publication。
* source 僅 `hanmoto` / `ndl_opensearch`，且 `image_url` 都是 Hanmoto canonical placeholder（`noimage.jpg` 變體）。
* 同時具備污染 signature：`location_name='大阪城ホール'` + `start_date='2023-10-14T00:00:00+00:00'`。
* `field_corrections_before` 同批證據完整：`location_name/start_date` 皆由 null → 污染值；其中 3 筆另有 `organizer` 污染為 `コミックマーケット準備会`。
* 日期修復 evidence：7 筆使用未污染 `end_date`，1 筆（`3995e531`）使用同 ISBN `hanmoto_9784816379222` 交叉驗證。

### Implementation

* `scraper/enrich_poster.py`
  * 候選 select 補 `event_form`；前置 guard 使用 exact pure helper + canonical placeholder helper。
  * 新增 canonical placeholder helper，拒絕 Hanmoto `noimage/no-cover` 變體（scheme/query/fragment 正規化），不 blanket 拒絕 Hanmoto 真實封面。
  * Vision 回傳後，任何 `events.update()` / FC write 前 re-read row 再做 pure + placeholder guard，防 TOCTOU 與 helper 直呼繞過。
* `scraper/_oneoff_backfill_publication_metadata.py`
  * schema version 升級至 `2`。
  * 新增窄化 `poster_placeholder_pollution_repair` pre-action：只命中 8 筆 audited UUID/signature。
  * pre-action 先 lock_clean 修復 `location_name/start_date`，3 筆另修 `organizer`；再進既有 pure cleanup 七欄 lock-empty。
  * signature/evidence 不完整時改列 conflict（不進 pre-action、不進 pure cleanup）。
  * summary 增加 `poster_placeholder_pollution_repair_actions` 與 `unresolved_non_eslite_location_conflicts`。
  * apply contract 增加 `candidate_ordering`（pre-action → pure_cleanup → readback）。
* `scraper/tests/test_enrich_poster_publication.py`
  * 新增 pure/noimage 不呼叫 Vision、不寫 event/FC。
  * 新增 TOCTOU re-read guard 測試。
  * 新增 physical Hanmoto 真封面可 enrich、ordinary nonpublication 不受影響。
* `scraper/tests/test_publication_manifest.py`
  * 新增 exact 8 signature 命中測試。
  * 新增 near-miss 不命中測試。
  * 新增 FC before/after、date/publisher repair 測試。
  * 新增 future apply ordering（pre-action → pure cleanup → readback）測試。
* `docs/specs/active/publication-policy/tasks.md`
  * 新增並勾選 Phase 2D、Phase 5 items 10-13 對應任務與驗證。
* `.github/skills/agents/architect/SKILL.md` / `.github/skills/agents/architect/history.md`
  * 新增 planning-mistake lesson：domain surface audit 漏 `enrich_poster.py`，補上 derived enrichment candidate audit + placeholder image guard 一般化規則。

### Focused regression tests

```bash
cd ttr-publication-policy-worktree/scraper
"/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python" -m pytest \
  tests/test_enrich_poster_publication.py \
  tests/test_publication_manifest.py \
  tests/test_publication_rules.py \
  tests/test_database_publication.py \
  tests/test_annotator_publication.py \
  tests/test_auto_qa_publication.py -q
```

Result: PASS, `67 passed`, `11 warnings`（既有 `datetime.utcnow()` deprecation）。

### Read-only manifest regeneration

```bash
cd ttr-publication-policy-worktree/scraper
PUBLICATION_MANIFEST_MODE=read-only \
PUBLICATION_MANIFEST_ENV_FILE="/Users/flyingship/development/Tokyo Taiwan Radar/scraper/.env" \
  "/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python" \
  _oneoff_backfill_publication_metadata.py \
  --manifest-output ../tmp/publication-policy/wave1-manifest-20260711-phase5-v3-poster-fix.json
```

Summary:

| Metric | Result |
|--------|--------|
| Manifest candidates | 333 |
| Included pure cleanup | 331 |
| Poster repair pre-actions | 8 |
| Non-Eslite unresolved location conflicts | 0 |
| Eslite migration actions | 1 |
| Mixed exclusions | 1 |

Evidence sanity check:

* 8 筆都顯示 `pre_actions[0].action_type = poster_placeholder_pollution_repair`。
* 8 筆都顯示 `pre_actions[0].ordering = before_pure_cleanup`。
* 8 筆 `poster_pollution_repair.evidence.complete = true`。

Safety confirmation:

* Apply execution: NOT RUN
* DB writes: NOT RUN
* QA live reconcile: NOT RUN
* DuckDuckGo/OpenAI search providers: NOT RUN

## Phase 6 Release Candidate Verification (2026-07-11)

### Formal Tester evidence

| Gate | Result |
|------|--------|
| Python deterministic publication suite | PASS, 75 tests |
| Web publication and structured-data suites | PASS, 14 + 2 tests |
| TypeScript `tsc --noEmit` | PASS |
| i18n parity/removal/category guard | PASS, 1,161 checks |
| Focused touched-file ESLint | PASS |
| Next.js production build | PASS, 250/250 |
| Browser pure Book fixture | PASS, end date/address/hours/price hidden |
| Browser ordinary Event fixture | PASS, end date/address/hours/price retained |
| Full-repo lint | 247 pre-existing baseline findings; no feature regression |

### Manifest safety evidence

* Manifest: `tmp/publication-policy/wave1-manifest-20260711-phase5-v3-poster-fix.json`
* SHA-256: `e6e96f6d3d0126c77ce156561d1108d3d1a633743e0d309a89d19d872dad552c`
* Candidates: 333
* Action distribution: 331 `pure_cleanup`, 1 `eslite_physical_identity_migration`, 1 `excluded`
* Poster-placeholder repair pre-actions: 8
* Unresolved non-Eslite location conflicts: 0
* Apply contract retains full-batch fingerprint drift gate, rollback snapshot before any write, deterministic candidate ordering, and row read-back

### Targeted governance correction

* Active governance now uses the exact `PUBLICATION_NULL_FIELDS` contract:
  `location_address`, `location_address_zh`, `location_address_en`,
  `business_hours`, `business_hours_zh`, `business_hours_en`, and
  `location_prefectures`.
* Real DB price metadata (`is_paid`, `price_info`, `price_amount`) remains preserved.
  Pure-publication price is hidden only in UI and JSON-LD; price fields are not part
  of the NULL/clear policy.
* `location_name` and `location_url` are not part of the seven intentional-null fields.

### Targeted fix validation

| Check | Result |
|-------|--------|
| Direct import of `PUBLICATION_NULL_FIELDS` against active governance | PASS, 11/11 exact ordered matches |
| `.github` active contradiction and hard-coded old-pattern scans | PASS, 0 hits |
| Active governance DB-price preservation statements | PASS, 11/11 files |
| YAML frontmatter required keys | PASS, 14/14 files |
| Non-code relative Markdown links | PASS, 1/1 link |
| `git diff --check` | PASS |
| Worktree status guard | PASS, `MM=0`, `staged=0` |

### Release boundary

* Live source dry-runs: NOT EXECUTED in this targeted fix; offline source fixtures passed
* DB-backed Auto-QA reconcile dry-run: NOT EXECUTED; deterministic reconcile tests passed
* Live DB apply, Eslite live remap, and QA live reconcile: NOT EXECUTED
* Wave 2 DuckDuckGo/OpenAI publisher search: DEFERRED / NOT EXECUTED
* One atomic local feature commit: prepared by this changeset; hash assigned by Git at commit time
* Push, merge, and deploy: NOT EXECUTED
* Final Tester verdict: PASS; no blocking findings

### Final Test Report

| Gate | Final result |
|------|--------------|
| Python publication suite | PASS, 75 tests |
| Web deterministic suites | PASS, 14 + 2 tests |
| TypeScript and i18n | PASS, `tsc --noEmit` and 1,161 parity checks |
| Focused ESLint | PASS, zero feature findings |
| Production build | PASS, 250/250 pages |
| Browser fixtures | PASS, pure Book and ordinary Event behavior |
| Manifest safety | PASS, SHA-256 verified and 333 actions distributed 331/1/1 |
| Governance exact parity | PASS, 11/11 files |
| Full-repo lint | 247 pre-existing baseline findings; no feature regression |

Live DB apply, Eslite live remap, QA live reconcile, Wave 2 provider calls,
push, merge, and deploy remain outside this local delivery and were not executed.

## Delivery Batch 1 (code-only)

* Base SHA: `ff499aa2571614ea278b155421b4d357a81466d1` (worktree fast-forwarded to `origin/main`)
* Scope: Phase 1a (stop pure-publication venue writers) and Phase 1b (writer matrix audit)
* Boundary: no production DB write, no migration, no `web/` change, no push, no deploy

### Phase 1a — code changes

| File | Change |
|------|--------|
| `scraper/publication_rules.py` | Added `PUBLICATION_VENUE_NAME_FIELDS` (`location_name`, `location_name_zh`, `location_name_en`), documented as cleared for exact-pure rows but deliberately outside `PUBLICATION_NULL_FIELDS` because they carry no empty-sentinel field-correction contract |
| `scraper/annotator.py` | Removed the three assignments that copied NDL `publication_label_ja/zh/en` into `location_name` / `location_name_zh` / `location_name_en` |
| `scraper/annotator.py` | Added `_exempt_publication_venue_fields()` returning venue-name fields whose field_correction is non-empty |
| `scraper/annotator.py` | `_finalize_publication_update()` now clears the three venue-name fields and their localized staging values; a non-empty field_correction keeps the exact value and emits the structured `publication_venue_name_fc_exemption` warning marker (field names only, no values) without raising. The seven canonical `PUBLICATION_NULL_FIELDS` keep their unchanged hard `policy conflicts` failure |
| `scraper/annotator.py` | `_assert_pure_publication_payload()` accepts optional protected-field context and rejects any non-null `location_name*` payload or localized staging value unless that field has a non-empty field-correction exemption |
| `scraper/annotator.py` | `_verify_publication_postcondition()` accepts optional protected-field context; after write it requires the seven canonical fields to be NULL, unprotected venue-name fields to be NULL, and protected venue-name fields to equal the expected retained value |
| `scraper/annotator.py` | Both call sites now pass `_human_protected` |
| `scraper/annotator.py` | `_fetch_ndl_publication_context()` docstring rewritten as publisher / periodical-description enrichment instead of placeholder replacement; the label still feeds only the existing periodical `description_*` prefix |
| `scraper/database.py` | `_apply_pure_publication_policy()` also clears `location_name`, `location_name_zh`, `location_name_en` on every exact-pure row |

Legacy placeholder constants and fixtures were kept — they remain the detectors for historical pollution.

### Phase 1a — tests

| File | Test |
|------|------|
| `scraper/tests/test_annotator_publication.py` | `test_pure_finalizer_clears_unprotected_venue_names` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_finalizer_keeps_venue_name_with_nonempty_field_correction` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_finalizer_treats_empty_venue_field_correction_as_unprotected` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_finalizer_keeps_venue_names_for_mixed_publication_form` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_payload_guard_rejects_unprotected_venue_name` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_payload_guard_allows_venue_name_with_nonempty_correction` |
| `scraper/tests/test_annotator_publication.py` | `test_pure_payload_guard_ignores_mixed_publication_form` |
| `scraper/tests/test_annotator_publication.py` | `test_annotation_postcondition_rejects_residual_venue_name` |
| `scraper/tests/test_annotator_publication.py` | `test_annotation_postcondition_accepts_protected_venue_name` |
| `scraper/tests/test_annotator_publication.py` | `test_annotation_postcondition_rejects_protected_venue_name_mismatch` |
| `scraper/tests/test_database_publication.py` | `test_event_to_row_clears_scraper_venue_names_for_exact_pure` |
| `scraper/tests/test_database_publication.py` | `test_event_to_row_keeps_venue_name_for_physical_form` |
| `scraper/tests/test_database_publication.py` | `test_event_to_row_keeps_venue_and_policy_fields_for_mixed_form` |
| `scraper/tests/test_database_publication.py` | `test_apply_pure_publication_policy_ignores_mixed_form_row` |

All tests are offline; no Supabase client is constructed against production.

### Phase 1b — writer matrix

Target fields: the seven canonical `PUBLICATION_NULL_FIELDS` plus `location_name`,
`location_name_zh`, `location_name_en`, `location_url`, `venue_id`, `organizer_type`.
"Pure re-check" means the exact-pure state is re-confirmed immediately before the mutation.

#### Covered writers

| Writer | Entry point | Target fields written | Selects `event_form` | Pure re-check before write |
|--------|-------------|----------------------|----------------------|----------------------------|
| `scraper/annotator.py` | `_finalize_publication_update()` → `events.update()` | all 13 | Yes | Yes — pure computed from freshly read event merged with payload, `_assert_pure_publication_payload()` before write, `_verify_publication_postcondition()` read-back after write |
| `scraper/database.py` | `_apply_pure_publication_policy()` in `_event_to_row()` and after force-rescrape field-correction apply | 7 canonical + 3 venue names + `location_url` + `venue_id` + `organizer_type` | Yes | Yes — applied to the row itself as the last step before the upsert payload is finalized, and re-applied after field corrections |
| `scraper/enrich_addresses.py` | address enrichment | `location_address*`, `location_name` | Yes | Yes — `partition_pure_publications()` at candidate stage plus `is_pure_publication_in_db()` before write |
| `scraper/enrich_location.py` | location enrichment | `location_address` | Yes | Yes — same two-stage guard |
| `scraper/geocode_events.py` | geocoding | `venue_id`-adjacent geocode columns | Yes | Yes — same two-stage guard |
| `scraper/backfill_locations.py` | location backfill | `location_address`, `location_name` | Yes | Yes — same two-stage guard |
| `scraper/backfill_location_prefectures.py` | prefecture backfill | `location_prefectures` | Yes | Yes — same two-stage guard |
| `scraper/enrich_poster.py` | Vision poster enrichment | `location_name` | Yes | Yes — `_read_current_event()` re-reads `_GUARD_SELECT` and `_poster_guard_reason()` re-checks pure after Vision, before write |
| `scraper/_oneoff_backfill_publication_metadata.py` | publication metadata backfill | `business_hours*`, `location_name`, `location_url` | Yes | Yes — per-row exact-pure verification before action; out of scope for modification in this batch |

#### Uncovered producers — blocks Phase 3

These paths can mutate a target field on an exact-pure row without ever reading `event_form`.
They do not block the Batch 1 release, but Phase 3 cannot be considered safe until each is closed.

| Writer | Entry point | Target fields written | Selects `event_form` | Pure re-check | Note |
|--------|-------------|----------------------|----------------------|---------------|------|
| `scraper/auto_qa.py` | simplified-Chinese fix, candidate select is `"id," + _FIX_FIELDS + ",selection_reason,annotation_status"` | `location_name_zh`, `location_address_zh`, `business_hours_zh` (via `ZH_FIELDS`) | No | No | Also writes matching field-correction locks, so a violation persists |
| `scraper/qa_auto_fix.py` | batch fix over `FIX_FIELDS` | `location_name_zh`, `location_address_zh`, `business_hours_zh` | No | No | Out of scope for modification in this batch |
| `scraper/qa_auto_fix.py` | `handle_location_url_is_event_url()` | `location_url` | No | No | Selects `location_name` / `location_address` but not `event_form` |
| `scraper/qa_heartbeat.py` | rollback path, `events.update({field: before})` | any audited field, including `location_url` and the `*_zh` trio | No | No | `_fetch_event()` selects no `event_form` |
| `scraper/backfill_entities.py` | venue cluster backfill | `venue_id` | No | No | Candidate select is `id,{column}` only |
| `scraper/backfill_organizer_authority.py` | authority apply | `organizer_type`, `co_organizer_types`, `sponsor_types` | No | No | `_EVENT_COLUMNS` has no `event_form` |
| `scraper/_oneoff_repair_organizer_type_arrays.py` | array repair | `organizer_type`, `co_organizer_types`, `sponsor_types` | No | No | Source-agnostic one-off |
| `scraper/_oneoff_fix_puppet_month_locations.py` | one-off location repair | 12 of the 13 | No | No | Source-scoped one-off |
| `scraper/_oneoff_fix_tcc_locations.py` | one-off location repair | 7 of the 13 | No | No | Source-scoped one-off |
| `scraper/_oneoff_backfill_gnews_streaming_fields.py` | gnews backfill | `business_hours`, `location_name` | Yes | No | Selects `event_form` only to default it to `["broadcast"]`; source-scoped |
| Cinema `source_id` migration one-offs and `_oneoff_seed_authoritative_venues.py` | one-off migrations | `business_hours` | No | No | Source-scoped to non-publication cinema sources |

#### Verified non-writers

`scraper/merger.py` reads the location fields but never writes them.
`scraper/audit_organizers.py` is read-only for `events` — its only `.update()` is a Python set method.
`scraper/seed_authoritative_organizers.py` writes `organizer_type` on the `organizers` table, not on `events`.

### Batch 1 verification

| Gate | Result |
|------|--------|
| `pytest scraper/tests/test_annotator_publication.py scraper/tests/test_database_publication.py -q` | PASS, 36 tests |
| `pytest scraper/tests -q` | PASS, 473 passed, 1 skipped |
| `python -m compileall -q scraper` | PASS |
| `git diff --check` | PASS |
| `web/messages/*.json` diff from this batch | none |
| Production DB access during tests | none |

## Delivery Batch 2 — Phase-Aware Manifest Executor (code-only)

### Scope

Implements the Phase 3 execution model (Round 10 option B): `apply_phase` as the sole write
selector, three scoped checkpoints folded into one manifest digest, and an `expected_fc` /
value-level CAS contract on `qa_auto_fix.unlock_and_write()`. No migration, no `web/` change,
no production DB write.

### Modified files in this slice

| File | Change |
|------|--------|
| `scraper/_oneoff_backfill_publication_metadata.py` | phase-aware executor, scoped checkpoints, extended-field CAS, Eslite identity ordering |
| `scraper/qa_auto_fix.py` | `expected_fc` / `expected_event_value` / `expected_event_form` CAS, `field_correction_id` audit anchor, sentinel preservation |
| `scraper/tests/test_publication_manifest.py` | phase, checkpoint, CAS, and Eslite coverage |
| `scraper/tests/test_qa_auto_fix_unlock_only.py` | new offline `unlock_and_write` contract suite plus the shared `FakeSupabase` |

### Root cause fixed in this round — after-checkpoint false drift

Eight tests failed with `STOP: <phase>.after target_field_corrections drift; zero writes
performed`. The manifest records a field correction the phase has yet to create as
`"id": null`, because Postgres assigns the id during the write. The read-back saw the real
id (`field_corrections-1` …), so `structural_row_diff()` keyed both sides on `id` and
reported the same logical row as `missing` (the null-id expectation) and `unexpected` (the
live row) at once. Seven of the eight failures were this single false positive on
`event-clear.after` and `eslite-identity.after`.

The fix pairs rows explicitly instead of comparing id-keyed sets:

* `structural_row_diff(expected, observed, *, allow_db_assigned_ids=False)` now matches
  id-bearing expected rows first, by complete field-correction id, and only then pairs the
  leftovers.
* `allow_db_assigned_ids` is opt-in and applies to expected rows with no id — the rows this
  phase creates. They pair by `(event_id, field_name)` and must match on
  `corrected_value`, `original_value`, `corrected_by`, and `report_id`
  (`CHECKPOINT_NEW_ROW_MATCH_FIELDS`). A candidate without a real live id never matches, and
  an ambiguous identity is reported as `missing` rather than silently accepted.
* `verify_checkpoint()` passes `allow_db_assigned_ids=True` only for
  `target_field_corrections` on a `.after` checkpoint. `events`,
  `preserve_field_corrections`, every `.before` checkpoint, and the `unlock_only` delete path
  keep full-id matching. Phase 3a's safety core is unchanged.

The eighth failure was unrelated: `test_cleanup_phases_never_select_the_eslite_candidate`
built its pure candidate with no field corrections, so `fc-remove` had nothing to delete and
correctly selected nothing. The implementation was right; the fixture now carries a polluted
`location_name` correction so the control assertion has real work to observe.

### Drift detection is still load-bearing

Two regression tests were added, and each guard was neutralized in a scratch probe to confirm
the assertions fail when the guard is broken.

| Probe | Guard intact | Guard neutralized |
|-------|--------------|-------------------|
| Sentinel `corrected_value` drift on a phase-created row | detected | not detected |
| Extra unmanifested target field correction | detected | not detected |
| `fc-remove.before` event drift | detected, zero writes | n/a |

`test_existing_rows_still_match_only_on_the_full_field_correction_id` additionally proves an
expected row that carries an id is never matched by `(event_id, field_name)`, with or without
`allow_db_assigned_ids`.

### Preserved contracts

* `fc-remove` mutates no event; `event-clear` deletes no field correction
* An existing exact sentinel suppresses the upsert but the event value is still CAS-cleared
* Only the thirteen target fields are executable; `price_info`, titles, `organizer_id`, and
  `organizer_url` stay byte-for-byte unchanged
* `poster_pollution_repair_plan()` writes no `PUBLICATION_CHANNEL_LOCATION`
* `corrected_by IS NOT NULL` remains a hard cleanup exclusion
* The audit trail reuses the existing `field_correction_id` column; no migration was added

### Batch 2 verification

| Gate | Result |
|------|--------|
| `pytest scraper/tests/test_publication_manifest.py scraper/tests/test_qa_auto_fix_unlock_only.py -q` | PASS, 66 passed |
| `pytest scraper/tests -q` | PASS, 520 passed, 1 skipped |
| `python -m compileall -q scraper` | PASS |
| `git --no-pager diff --check` | PASS |
| `web/` diff from this batch | none |
| Production DB access during tests | none |
| Push / merge / deploy / manifest apply | not executed |

## Delivery Batch 2a — Independent Tester FAIL Remediation (code-only)

An independent Tester ran the Batch 2 executor against the offline fake database
and returned FAIL on three defects. All three are fixed here; no production DB was
read or written, and `web/` is untouched.

### F-1 (MEDIUM) — an after-gate failure claimed `zero writes performed`

`verify_checkpoint()` emitted one message for both gates. A `.before` gate failure
really does happen before any write, but the identical text was reused for the
after gate, which only runs once the phase has finished writing. The Tester
reproduced it on an ordinary non-Eslite manifest:

```text
apply succeeded, events written: 8   fc rows created: 7
MESSAGE: STOP: event-clear.after target_field_corrections drift; zero writes performed: {...}
```

On-call would read `zero writes performed` and conclude no rollback was needed,
while the rollback snapshot was in fact mandatory.

Fix — the two gates now speak different languages:

* New `checkpoint_stop_language(is_after_gate, write_context)` returns the drift
  marker and the remediation clause. Only a before gate may return
  `zero writes performed`; an after gate always returns ` AFTER writes` plus
  either the write context or `manual rollback verification required`.
* `verify_checkpoint(..., write_context=...)` renders
  `STOP: <checkpoint> <key> drift AFTER writes; rollback snapshot=<path>;
  applied_event_ids=[...]; fc_created=<n>; fc_deleted=<n>; manual rollback required: {diff}`.
* The same remediation clause is threaded into `verify_checkpoint_audits()`, so an
  audit-anchor mismatch at the after gate also names the snapshot.
* `execute_candidate()` now returns `{"fc_created", "fc_deleted"}`. `fc_created`
  counts only actions whose `expected_fc` is absent, so a preserved exact sentinel
  is never reported as a creation. `apply_manifest()` accumulates both counters and
  passes them, with the snapshot path and applied event ids, as the after gate's
  `write_context`.

### F-2 (LOW-MEDIUM) — the `event-clear` before gate took the relaxed path

`phase_creates_rows = name.endswith(".after")` inferred the gate's role from the
checkpoint name. Because `CHECKPOINT_BEFORE["event-clear"]` is `fc-remove.after`,
the event-clear *before* gate matched that suffix and ran with
`allow_db_assigned_ids=True`. The Tester confirmed this was not a no-op: a cleanup
manifest generated before the Eslite apply put six real `id=None` rows on that path.

Fix — the role is now stated by the caller, never inferred:

* `verify_checkpoint(..., is_after_gate: bool = False)` replaces the suffix test.
* `apply_manifest()` passes `is_after_gate=False` for `CHECKPOINT_BEFORE[...]` and
  `is_after_gate=True` for `CHECKPOINT_AFTER[...]`.
* Every before gate is id-exact regardless of the name of the payload it reuses.
  `events`, `preserve_field_corrections`, and the `unlock_only` delete path were
  already id-exact and stay that way.

### F-3 (LOW) — a pre-Eslite cleanup manifest wrote before it stopped

`build_manifest(scope="cleanup")` does not exclude the Eslite candidate, so its
`fc-remove.after` image carried the six `lock_clean` rows that only the
`eslite-identity` phase can create. `fc-remove` therefore completed the pure
cohort's writes (1 delete + 1 audit) and only then failed its own after gate.

Fix — new `assert_cleanup_manifest_excludes_eslite(manifest)`, called by
`apply_manifest()` before the checkpoint gate, before the rollback snapshot, and
before any write. A cleanup-scope manifest that still contains an
`eslite_physical_identity_migration` candidate is refused with an instruction to
apply `--scope eslite-identity` first, read back the migrated rows, and regenerate
the cleanup manifest. Generation is left intact so the candidate stays inspectable
as provenance.

### INFO items

* `CHECKPOINT_NEW_ROW_MATCH_FIELDS` now documents why `created_at` is excluded:
  Postgres assigns it during the same write, so the manifest cannot predict it.
* An end-to-end `preserve` / `events` id-exactness test was added (below).

### Tests added

| Test | Defect |
|------|--------|
| `test_after_gate_failure_names_the_rollback_instead_of_claiming_zero_writes` | F-1 |
| `test_before_gate_failure_still_reports_zero_writes` | F-1 |
| `test_the_event_clear_before_gate_is_id_exact_despite_its_after_payload_name` | F-2 |
| `test_a_cleanup_manifest_predating_the_eslite_migration_is_refused_before_any_write` | F-3 |
| `test_the_eslite_guard_leaves_a_clean_cleanup_manifest_alone` | F-3 |
| `test_preserve_row_id_swap_stops_the_after_checkpoint` | INFO-2 |

### Drift detection is still load-bearing

Each new guard was neutralized in place and the suite re-run, then restored and
verified byte-identical.

| Mutation | Result |
|----------|--------|
| After gate reverts to the `zero writes performed` clause | 1 failed — `test_after_gate_failure_names_the_rollback_instead_of_claiming_zero_writes` |
| Before gate infers the relaxed path from `name.endswith(".after")` | 1 failed — `test_the_event_clear_before_gate_is_id_exact_despite_its_after_payload_name` |
| `assert_cleanup_manifest_excludes_eslite()` removed from `apply_manifest()` | 1 failed — `test_a_cleanup_manifest_predating_the_eslite_migration_is_refused_before_any_write` |

The F-3 mutation also reproduced the Tester's finding exactly: `fc-remove` applied
the pure candidate (`fc_deleted=1`) and then failed its own after gate on the six
Eslite `id=None` rows — reported, with F-1 in place, as ` AFTER writes` with the
snapshot path rather than as `zero writes performed`.

### Preserved contracts

No drift detection was weakened. `allow_db_assigned_ids` still applies only to the
current phase's own after-image `target_field_corrections`; `fc-remove` mutates no
event and `event-clear` deletes no field correction; an existing exact sentinel
still suppresses only the upsert while the event value is CAS-cleared; the thirteen
target fields remain the only executable set; `price_info`, titles, `organizer_id`,
and `organizer_url` stay byte-for-byte unchanged; `poster_pollution_repair_plan()`
writes no `PUBLICATION_CHANNEL_LOCATION`; `corrected_by IS NOT NULL` remains a hard
exclusion; the audit trail reuses the existing `field_correction_id` column with no
migration.

### Batch 2a verification

| Gate | Result |
|------|--------|
| `pytest scraper/tests/test_publication_manifest.py scraper/tests/test_qa_auto_fix_unlock_only.py -q` | PASS, 72 passed |
| `pytest scraper/tests -q` | PASS, 526 passed, 1 skipped |
| `python -m compileall -q scraper` | PASS |
| `git --no-pager diff --check` | PASS |
| `web/` diff from this batch | none |
| Production DB access | none |
| Push / merge / deploy / manifest apply | not executed |
