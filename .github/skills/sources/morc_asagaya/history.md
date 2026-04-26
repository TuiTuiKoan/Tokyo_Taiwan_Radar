# Morc阿佐ヶ谷 Scraper History

## 2026-04-26

**Issue**: All 24 film pages returned as Taiwan-relevant (false positives)

**Root cause**: Every film page at Morc contains a site-wide INFORMATION section (`section#tp_info`) that includes a "【台湾巨匠傑作選2024】上映のお知らせ" promotion link. The initial implementation applied the Taiwan keyword filter to the full page `get_text()` output, causing all films to match.

**Fix**: Added `soup.select('#tp_info')[0].decompose()` (via CSS selector loop) before extracting text for Taiwan relevance check. After removal, zero false positives.

**Lesson**: Site-wide banners/notices can pollute keyword-based Taiwan filters. Always inspect non-Taiwan pages when scraper returns unexpectedly high hit counts. Check the DOM for promotional sections that appear on every page.

**Verification**: 0 events returned for current listing (no Taiwan films on screen) — correct for the period 2026-04-26. Will return events when 台湾巨匠傑作選 or similar Taiwan festival runs.
