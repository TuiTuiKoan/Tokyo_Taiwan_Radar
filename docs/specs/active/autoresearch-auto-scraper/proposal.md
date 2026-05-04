---
slug: autoresearch-auto-scraper
title: Auto Research & Auto Scraper 生成 Pipeline（Layer A→B→C）
status: active
branch: feat/autoresearch-auto-scraper
created: 2026-04-20
tags: [scraper, infra, ai]
---

## What（做什麼）

全自動化「發現來源 → 評估 → 生成爬蟲 → 整合」的 Pipeline：

- **Layer A**：`researcher.py`（GPT-4o search 發現） + `discovery_accounts.py`（平台探索）
- **Layer B1**：`auto_research.py`（Playwright + GPT-4o 評分，自動 promote/demote）
- **Layer B2**：`generate.py`（spec → code → AST check → sandbox dry-run）
- **Layer C**：目前人工整合；目標自動開 PR

## Why（為什麼）

- 手動研究來源太耗時，且容易遺漏小型活動場地
- Layer B1+B2 已可自動評估並生成程式碼；Layer C 仍需人工 copy + register + commit
- 自動 PR 讓 Layer C 變成「PR review」而非「手工編碼」

## Non-Goals（不做什麼）

- ❌ 不做自動 merge（PR 必須人工 review + merge）
- ❌ Layer C 不自動寫入 events / scraper_runs 表
- ❌ 不做 scraper 品質自動評分（由人工 review）

## Design（設計摘要）

### 現有架構
```
researcher.py / discovery_accounts.py
  → research_sources (status: candidate)
  → auto_research.py (score≥0.70 easy → researched)
  → generate.py (spec→code→sandbox)
  → runs/<source_id>/{spec.json, generated.py, meta.json}
  → [手工] copy to sources/ + register main.py + dry-run + commit
```

### 目標：Layer C 自動 PR
```
generate.py success
  → create branch spx/auto-<source_name>
  → copy generated.py to sources/_auto_<name>.py
  → add to main.py SCRAPERS
  → git commit + push
  → open GitHub PR（via GitHub API）
  → update research_sources.auto_scraper_pr_url
```

### 相關欄位
- `research_sources.auto_scraper_pr_url`：PR 建立後寫入，`daily_report.py` 讀取顯示
- `research_sources.auto_scraper_status`：success | sandbox-failed | budget-exceeded | llm-error

## References

- `scraper/auto_scraper/auto_research.py`（Layer B1）
- `scraper/auto_scraper/generate.py`（Layer B2）
- `scraper/auto_scraper/spec_to_code.py`（template render + AST check）
- `docs/SCRAPER_PIPELINE.md`（完整 pipeline 圖）
