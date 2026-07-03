# PR TIMES Scraper — Implementation History

---

## 2026-07-04 — filter calibration: 台湾 + 地点量詞 + で/にて…開催（漏洞 C／event 4e558c1c）

**Context:** イベント `4e558c1c`（日本の高級日本酒ブランド HENGE が台北・台中・高雄で開催する「進出記念ディナーイベント」、Japan→Taiwan の輸出／進出＝商業展開）が active event として収録された。2026-06-29 Rental819、同日 b90f0b77 に続く 3 例目の Japan-brand-held-in-Taiwan（漏洞 C）。title「台湾3都市で…開催」は既存 4 分岐すべてに非該当、body には `開催地：`/`会場：` 等の venue label が一切なく（台北・台中・高雄は叙述文に散在）、両層 guard が取りこぼした。

**Filter calibration（今回の進化）：**

- **Title guard 第 5 分岐**：`_TAIWAN_BASED_TITLE_RE` に「台湾 + 地点量詞（`[\d０-９]+都市`／`各地`／`主要都市`／`複数都市`／`全土`…）+ `で`／`にて` + 活動動詞（開催／実施／開講／スタート）」を追加。従来は「台湾国内／現地／本島／の地」または「台湾にて／において」が必須で、「台湾3都市で…」を取りこぼしていた。
- **二重 negative lookahead**：(1) Japan-pivot（`日本上陸／各地／初／進出`）＝「台湾で人気→日本上陸」型；(2) **Japan-venue（`東京／大阪…で・にて`）**＝「台湾3都市で人気の…を東京で開催」（東京主催）を除外。numeric-quantifier 入口ゆえ Japan-venue 誤除外の防御が必須。
- **「日本酒」は除外しない**：lookahead は `上陸／各地／初／進出` のみ列挙するため、「日本」の直後が「酒」の場合は該当せず、目標 title 中段の「日本酒」を含んでも正常に命中する。
- **source_exclusions**：`raw_title` regex `台湾[\d０-９]+都市で` を追加（次回 scrape で即時有効）。範囲は意図的に code guard より狭く numeric `N都市で` のみ——サンプルが 1 件のため `各地／主要／複数／全土` 系は code guard の CI 反映に委ね、DB 規則の誤除外リスクを抑える。既知の盲点：この DB regex は Japan-venue lookahead を含まないため `台湾3都市で人気の…を東京で開催` を誤除外し得るが、当該句式は実サンプル未出現で、code guard が根本防線・DB 規則は CI 反映までの短期保険。

**body-no-label 型で venue guard を強化しない取捨：** 目標イベントは title guard（detail fetch 前に実行）で捕捉でき、body guard は到達しない。label のない叙述文に広範な台湾シグナル検出を入れると「東京で台湾フェア、台北の名店が出店」型の誤除外リスクが高く、他サンプルも無いため過度な抽象化を避けた。

**教訓：** Japan→Taiwan の輸出／進出 PR は台湾開催・台湾受け手向けなら out of scope。title guard は「台湾国内／現地」「台湾にて／において」に加え「台湾 + 地点量詞 + で／にて…開催」もカバーし、numeric 入口には Japan-venue negative lookahead で「台湾N都市で人気→日本開催」型の誤除外を必ず塞ぐ。

---

## 2026-07-04 — filter calibration: 台湾にて/において…開催 + 開催地：台湾 国名 guard

**Context:** イベント `b90f0b77`（日本のペットオーラルケアブランドが台湾で開催する業者向け合宿講座、Japan→Taiwan の商業／教育展開）が active event として収録された。2026-06-29 Rental819 に続く 2 例目の Japan-brand-held-in-Taiwan。

**Filter calibration（今回の進化）：**

- **Title guard**：`_TAIWAN_BASED_TITLE_RE` に分岐 `台湾(?:にて|において)(?:(?!日本).){0,40}?(?:開催|実施|開講|スタート)` を追加。従来は「台湾国内／現地／本島／の地」の修飾語が必須で「台湾にて…開催」を取りこぼしていた。負の先読み `(?!日本)` で「台湾にて人気→日本上陸」型の誤除外を防ぐ。
- **Body guard**：`_TAIWAN_HELD_BODY_RE` を新設。会場ラベルが国名のみ（`開催地：台湾`）の PR を捕捉。従来の `_TAIWAN_VENUE_RE` は都市名（台北・台中…）と英字 Taiwan のみで、日本語国名「台湾」を欠いていた。terminator に全角／半角括弧を含め「開催地：台湾（新北市）」も命中、「台湾夜市（東京・お台場）」は非命中。
- **Label 単一化**：`_VENUE_LABEL_ALT`（`開催場所|会場名|会場|開催地|場所`）を抽出し、`_VENUE_LABELS` と `_TAIWAN_HELD_BODY_RE` で共用。ラベル集合のドリフトを防止。
- **source_exclusions**：`raw_title` substring `台湾にて海外初` を追加（scraper guard の CI 反映を待たずに次回 scrape で即時有効）。

**教訓：** Taiwan-held の PR は「日本人向け」等の明示的シグナルがある場合のみ収録。title は「台湾にて／において…開催」の無修飾語パターン、body は国名のみの venue label の両方をカバーする必要がある。

---

## 2026-05-31 — VOD/ストリーミング クエリ追加（commit `a9a0066`）

**変更：** `prtimes.py` の検索クエリに VOD/ストリーミング関連キーワードを追加。従来は映画館上映とイベント PR が主な取得対象だったが、台湾コンテンツのオンライン配信・VOD リリース関連プレスリリースが漏れていた。

**修正（commit `a9a0066`）：** `QUERIES` リストに VOD/ストリーミング系クエリを追加。

**教訓：** PR TIMES は映画・ドラマ・ドキュメンタリーの VOD/ストリーミング配信告知も頻出する。新たな配信プラットフォームや台湾コンテンツのストリーミング関連キーワードが登場したらクエリを定期更新する。

---

## 2026-04-26 — prtimes: initial implementation

**Context:** PR TIMES was identified as a high-value source for Taiwan-related event
announcements in Japan. Unlike event-listing platforms (Peatix, connpass), PR TIMES
receives press releases from official tourism bodies, event organisers, and brands —
often 2–4 weeks before the event.

**API Discovery:**
- Standard search URL (`/main/html/searchrlp/key/`) returned 404 on all attempts.
- `schema.org` SearchAction pointed to `action.php?run=html&page=searchkey&search_word=`
  which worked but had client-side pagination only.
- The actual JSON API was found in the Next.js bundle (`_app-d5e27ce51595715c.js`,
  module 20400): `G = \`${$}/keyword_search.php\`` → `https://prtimes.jp/api/keyword_search.php/search`.

**Filter calibration:**
- Initial dry-run returned 26 events; ~35% were events held IN Taiwan (not Japan).
- Added `_TAIWAN_BASED_TITLE_RE` (title patterns: `in 台湾`, `台湾進出`, `台湾.*に集結`) and
  `_TAIWAN_VENUE_RE` (venue contains city names: 台北, 高雄, 花蓮 etc.) to exclude Taiwan-based PRs.
- After filtering: 12 events — a cleaner signal with Japan-held Taiwan events dominant.
- Residual noise (business tie-ups, product launches that mention Taiwan) passes to the annotator.

**Date extraction decisions:**
- PR TIMES detail pages have no structured schema.org date field.
- Body text labeled patterns (`開催日時：`, `日時：`) are reliable but absent for ~40% of PRs.
- Standalone `YYYY年MM月DD日` fallback: skip index 0 (always the PR publish dateline),
  use first plausible subsequent date. Added 2-year lookback guard to reject ancient
  historical mentions (e.g. one PR about the 2011 earthquake had a date extracted as 2011-03-11).
- Final fallback: `released_at` from the API response.

**HTML structure of detail pages:**
- PR body is inside `.release-content` (most common), `.press-release-body`, or `article/main`.
- Venue often labeled as `会場：` or `開催場所：`.

**Lessons learned:**
1. Always check JS bundles for internal API endpoints when the public search URL fails.
2. Double-filter (Taiwan keyword + event-type keyword) is essential for PR platforms —
   without the event keyword, business/product PRs dominate.
3. Skip index-0 standalone date — it is always the PR publish date in the dateline header.
4. Add a sanity-check to reject dates older than 2 years; PR bodies often mention historical
   context that contains old dates before the actual event date.
