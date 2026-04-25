# tobunken Scraper — Implementation History

## 2026-04-26 — Initial implementation

**Decisions:**

- **Static HTML, no Playwright**: `requests` + BeautifulSoup is sufficient. The site does not require JavaScript rendering.

- **No pagination**: The listing page contains all 1534+ entries on a single page. There is no next-page link or API pagination. The approach is: fetch once, filter in-memory.

- **LOOKBACK_DAYS = 365**: Initial attempts with 180 days yielded 0 results because the most recent Taiwan/maritime-related seminar (2025-10-22) was 185 days old at implementation time. Extended to 365 days (1 year) to ensure at least a few events are captured on every run.

- **Broad relevance filter (user intent)**: The user explicitly requested that seminars on 海洋史, 交流史, and 物質史 be included even when Taiwan is not the primary keyword. Tier-2 keywords (海域, 東南アジア, 琉球, etc.) were added intentionally. If the yield becomes too noisy, the solution is to narrow these keywords, not to require Taiwan to be in the title.

- **Filtering on title only (listing page)**: The listing page title is sufficiently descriptive for this site — seminar titles at 東洋文化研究所 explicitly state the research topic. Body-text keyword filtering would require fetching all ~1500 detail pages, which is wasteful.

- **`当日期間：YYYYMMDD` as primary date**: The footer metadata block on each detail page has `当日期間：YYYYMMDD - YYYYMMDD` in a consistent format. Used as the primary date source. Fallback to `日時：` label.

- **href trailing newline bug**: BeautifulSoup returns the raw `href` attribute value from the page's HTML, which in this case includes a trailing `\n`. Always `.strip()` href values.

- **Venue online suffix `& Zoom`**: The first event retrieved used `大会議室 & Zoom（ハイブリッド形式）` format. Added `& Zoom` / `& Teams` / `& Google Meet` to the split pattern. Post-split, orphaned `（` at end of string is removed with `re.sub(r"[（(]\s*$", "", venue)`.

- **Institute address hardcode**: All seminars are at 東京大学東洋文化研究所 (〒113-0033 東京都文京区本郷7-3-1). Hardcode the address when `location_name` contains `東洋文化研究所`.
