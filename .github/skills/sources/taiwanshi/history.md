# taiwanshi Scraper — Implementation History

## 2026-04-26 — Initial implementation

**Decisions:**

- **Atom feed over Playwright**: The exblog.jp site redirects `fetch_webpage` through DoubleClick ad trackers. However, the Atom feed at `https://taiwanshi.exblog.jp/atom.xml` is accessible via plain `requests` with no JS rendering required. Used Atom feed approach — simpler, faster, no browser dependency.

- **Filter by `日時：` presence**: Posts in the 定例研究会 category include both event announcements (with `日時：`) and recruitment notices (`報告者募集`) without event dates. Filter on `日時` in body text to only process confirmed event announcements.

- **Geographic scope**: Physical meetings are held across Japan (Osaka, Nagoya, Kobe, etc.), not exclusively Tokyo. User explicitly requested this source; all meetings have online participation (Google Meet/Zoom), so Tokyo users can attend. Scrape all meetings regardless of physical location.

- **Date regex design**: Three format variations discovered in the feed:
  1. Standard: `日時：2026年5月16日（土）13時00分～16時10分`
  2. No colon: `日時　2025年6月28日(土) 13時00分～15時10分` (全角スペース only)
  3. Spaces in date: `日時： 2025 年10月4 日（土）15：30～18：00` (spaces between digits and kanji)
  Used `[：:\s\u3000]*` for separator and `\s*` between year/month/day components.

- **Venue regex design**: Two label variants discovered:
  1. `会場：venue` — regular monthly meetings
  2. `場所：venue` — guest lecture / co-organized events
  Used `(?:会場|場所)[\uff1a:\u3000 \t]+` to handle both labels and all separator styles.

- **Online suffix stripping**: Posts use both `および` and `及び` (same meaning, different script). Both added to the split pattern.

- **`source_id` format**: `taiwanshi_{post_id}` where `post_id` is the 8-digit numeric ID in the URL. Stable across runs; independent of post title or date.
