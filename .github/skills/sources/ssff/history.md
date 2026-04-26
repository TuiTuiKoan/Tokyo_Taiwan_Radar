## 2026-04-26

### Initial implementation

- Implemented `SsffScraper` for Short Shorts Film Festival & Asia.
- Source URL: `https://www.shortshorts.org/{year}/all-program/` (all films in one static page)
- Year detection: tries `/{current_year}/all-program/`, falls back to ±1 year.
- Taiwan detection: filter `<a>` link text for `台湾` on all-program page.
- Dry-run result: 6 events for SSFF 2026 — all with `start_date` from screening table and `location_name` from venue column. Japanese titles correctly extracted from breadcrumb `nav ol li[-1]`.
- research_sources id=58 updated to `implemented`.
- Decision: `article h1` yields English title, while Japanese title comes from the last breadcrumb item (not h1).
- Decision: dl.info items extracted by splitting `get_text(separator="\n")` and matching `"監督"`, `"国"` labels.
- Decision: synopsis extracted from `article section` paragraphs; skip sections containing "上映会場" or "チケット" in first 30 chars.
