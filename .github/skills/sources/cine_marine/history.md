# 横浜シネマリン (cine_marine) Scraper History

## 2026-04-26

### Initial Implementation

- Discovered listing structure: each film in `/coming-soon/` and `/movie-now/` is preceded by an `<h2>` (date) and `<h3><a>` (title+link) in the `.entry-content` article body.
- Date format: `6/27(土)～` (start only) or `4/25(土)－5/8(金)` (range with 全角ダッシュ U+FF0D).
- Taiwan filter applied to `content_block` div text only (not full page), since sidebar lists all current films — would cause false positives if applied to full film page text.
- Film detail pages fetched for full `raw_description` (with sidebar removed before extraction).
- Source name: `cine_marine` (matches `_scraper_key(CineMarineScraper)`).
- First Taiwan event detected: 日泰食堂 (`2024年／台湾・香港・フランス／83分`) starting 2026-06-27.
