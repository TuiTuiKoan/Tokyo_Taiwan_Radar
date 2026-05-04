# Tasks

## Layer A — 來源發現

- [x] `researcher.py`：GPT-4o-search-preview，5 個 CategoryAgent 並行
- [x] `discovery_accounts.py`：note.com / Peatix 平台探索
- [x] `research_sources` DB schema + state machine（candidate / researched / not-viable...）

## Layer B1 — 自動研究評估（auto_research.py）

- [x] Playwright 抓取頁面 + GPT-4o 評分（Taiwan relevance score）
- [x] 分數分支：≥0.70 easy → researched；≥0.70 medium → recommended；<0.30 → not-viable
- [x] GitHub Issue 建立（`--create-issue` flag）
- [x] batch 模式（`--batch --max-sources N`）
- [x] 7 天 cooldown（避免重複評估）
- [x] DB migration：`auto_research_status` 欄位（DEFAULT 'pending'）
- [x] batch query 包含 `auto_research_status.eq.pending`（解決 DEFAULT 'pending' 靜默跳過 bug）

## Layer B2 — 自動代碼生成（generate.py）

- [x] Playwright 抓樣本 HTML（50,000 chars truncated）
- [x] GPT-4o JSON mode 生成 spec（CSS selectors + date_regex + source_name...）
- [x] `spec_to_code.py`：Jinja2 template render + jsonschema validate
- [x] AST safety check（禁止 subprocess/eval/requests 等）
- [x] sandbox subprocess dry-run（stripped env, timeout 300s）
- [x] 產出 `runs/<source_id>/{spec.json, generated.py, meta.json}`
- [x] `auto_scraper_status` 欄位更新

## Layer C — 自動 PR 建立（下一步）

- [ ] 實作 `auto_scraper/pr_creator.py`：
  - [ ] 建立 branch `spx/auto-<source_name>`
  - [ ] copy `generated.py` → `sources/_auto_<name>.py`
  - [ ] 自動在 `main.py` SCRAPERS 新增（或產生 diff 讓人貼）
  - [ ] `git commit + push`（或直接呼叫 GitHub Contents API）
  - [ ] 呼叫 GitHub PR API 開 PR
  - [ ] 更新 `research_sources.auto_scraper_pr_url`
- [ ] `generate.py` 成功後自動呼叫 `pr_creator.py`（flag：`--auto-pr`）
- [ ] `daily_report.py` 「待 review PR」欄位已實作，確認 `auto_scraper_pr_url` 正確填入

## Layer B1.3 — Deferred（spec_to_code.py TODO）

- [ ] feasibility hints 回寫 source_profile，讓 Researcher agent 可以 flag auto-scrapable

## Verification

- [ ] `python -m auto_scraper.auto_research --batch --dry-run` 正常執行
- [ ] `python -m auto_scraper.generate --source-id <id> --dry-run` 產出 runs/ 目錄
- [ ] `--auto-pr` flag 建立 PR 並寫入 `auto_scraper_pr_url`
- [ ] `daily_report.py --dry-run` 顯示待 review PR 列表
