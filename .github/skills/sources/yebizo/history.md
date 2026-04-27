# yebizo — History

## 2026-04-26 — Initial implementation

- **Dry-run results**: 3 Taiwan-related events from 67 total programs
  - `yebizo_682`: 張恩滿（チャン・エンマン）展示 2026/2/6-2/23, 東京都写真美術館 B1F 展示室, 無料
  - `yebizo_1652`: 侯怡亭（ホウ・イーティン）展示 2026/2/6-2/23, 東京都写真美術館 2F 展示室, 無料
  - `yebizo_2021`: 針と糸と料理で紡ぐ―原住民族文化の体験ワークショップ 2026/2/7, 東京都写真美術館 1F スタジオ, 有料
- **Pre-filter**: 3 candidates from 67 programs (curators 邱于瑄/侯怡亭 also had CJK+katakana names → caught correctly)
- **Venue bug fixed**: Workshop program had `11:00 - 12:30` time segment between date and venue; added `_TIME_RE` to skip time segments in `_extract_artist_and_venue()`
- **2026 festival theme**: "あなたの音に｜日花聲音｜Polyphonic Voices Bathed in Sunlight" — strong Taiwan connection (curators from Taiwan, Taiwan artist as central figure)
- **Off-season behavior**: Returns 0 events from March onward (festival listing still shows 67 programs but dates are past — future improvement: filter by date recency)
- **DB**: id=76, status → implemented, Issue: https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/25
