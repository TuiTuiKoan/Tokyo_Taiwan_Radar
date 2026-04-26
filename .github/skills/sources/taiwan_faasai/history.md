# 台湾發祭 Taiwan Faasai Scraper History

## 2026-04-26

### Initial Implementation

- Annual outdoor festival in Ueno Park (上野恩賜公園 竹の台広場).
- Date extracted from `/outline` page: `8月28日(金) ・29日(土) ・30日(日)` format.
- `verify=False` required due to TLS certificate issue on `taiwanfaasai.com`.
- Year extracted from page heading: `台湾發祭 Taiwan Faasai 2026`.
- Source ID `taiwan_faasai_2026` is stable per year — no drift across runs.
- `is_paid=False` (free admission confirmed on page).
- `category=["lifestyle_food"]` — food & culture festival.
