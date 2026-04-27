# taipei-fukuoka — History

## 2026-04-26 — Initial implementation

- **Dry-run results**: 3 events from 5 posts on main page
  - 2026-03-30: 風林の会セミナー（熊本市）— date from `日時：3月30日`, year from `発信日時：2026-03-11`
  - 2026-04-02: 防府市ガラコンサー（山口県防府市）— date from `日時：2026年4月2日`
  - 2026-04-25: 他鄉拾拾 山口シンポジウム — date from `日時：2026年4月25日（土）`
- **Venue extraction** works: `場所：...` pattern correctly extracts address-level location
- **2 posts skipped**: Taiwan Arrival Card notice (no date label, no event keyword) and Taiwan Fellowship scholarship (no date label)
- **Decision**: Main page only (5 posts) is sufficient for daily cron; WP REST API returns 404; no paginated listing found
- **DB**: id=80, status → implemented, Issue: https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/27
