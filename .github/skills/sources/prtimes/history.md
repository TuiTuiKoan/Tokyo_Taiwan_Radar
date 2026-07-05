# PR TIMES Scraper — Implementation History

---

## 2026-07-05 — カテゴリ D 手動停用：日本ブランド／企業が台湾で開催・台湾受け手向け（純 DB、code 改変なし）

**Context:** 漏洞 C（2026-07-04, `4e558c1c`）の検証中、Tester が dry-run で `c47ca1d9`（【DMMかりゆし水族館】台湾でのオフラインイベント「沖縄魅力祭り」開催、台北 LaLaport 南港）を発見。これは「台湾N都市で」型（漏洞 C）ではなく「台湾で…開催」型。規模量化のため prtimes active 全 61 件を精査した結果、location が実際に台湾 = 12 件、うち out-of-scope = 8 件（< 20 → SKILL「一律手動 patch」）と判明。

**カテゴリ D の定義:** 日本ブランド／企業が台湾で開催し、台湾の消費者向け（BtoC）または台湾での BtoB 出展を主目的とする販促・進出 PR は out of scope（＝日本国内の台湾関連イベントではない）。

**停用 8 件（純 DB `.update().eq()`、`deactivated_reason='out_of_scope: …'`、raw_* 保持）:**

| id | 概要 | location |
|----|------|----------|
| `c47ca1d9` | DMM水族館 沖縄観光 PR オフラインイベント | 台北市南港區 |
| `15e9a9d1` | Chatlock スマートロック 母の日ポップアップ | 台湾 |
| `8b1742c2` | acosta! コスプレイベント（来場者 2万台湾人、日本 coser は招待ゲストのみ） | 台北市信義区 |
| `d4632909` | フェリシモ Couturier 編み物ワークショップ | 台北市信義區 |
| `54ae8d26` | MomentumStudio 台湾 AI 展示会に出展（BtoB） | 台北市中山区 |
| `4a5484fd` | 東京23区マンション 台湾国際不動産博覧会へ出展 | 台北市 |
| `d93217ec` | Rujie 新北市「孝親演唱會」に出演 | 新北市三峡区 |
| `54f20a7d` | ネクサス 台北で日本不動産投資セミナー（台湾投資家向け） | 台北市信義區 |

**CHOYA `ad343f81`（高雄）は保留:** 「日本台湾交流協会」（公式の日台交流機関）が主催する梅文化講座での講演であり、日台文化交流の性質が強いため in-scope として active 維持。

**保留した in-scope 3 件（location は台湾だが日本人向け／日本業者向け）:**

- `3c3e8213` 名古屋商科大学 台湾へのスタディツアー — 日本の学生が渡台（面向日本人）。
- `21eda6a1` 浪人祭 日本人アーティストオーディション＋日本語サポート付ツアー — 日本の音楽人向け募集。
- `3e413744` TCCF「Japan Drama First Look」 — 日本の映像業者（国内対象）向け渡台ピッチング公募。

いずれも `.github/copilot-instructions.md` が明示する in-scope（study tour／日本人向け募集／日本業者向けプログラム）。

**title code guard を追加しない論証:** 保留 3 件の title も「台湾…開催／ツアー」を含み、OUT 8 件を捕捉するどの regex も IN 3 件を誤除外する。IN と OUT の差は「面向誰（受け手）」という語義であり、title 表面のキーワードではない。よって title regex は本質的に不適。location-based 自動停用も 3 件の IN を巻き込むため不採用。規模 8 < 20 の SKILL 閾値に従い一次的な手動停用で処理し、annotator／source_exclusions／web/i18n は一切変更しない。

**教訓:** 「日本ブランド／企業が台湾で開催・台湾受け手向け」は out of scope だが、同じ「台湾…開催」title でも日本人向け study tour・日本業者向け公募は in-scope。両者は title キーワードで区別できず（語義依存）、規模も閾値未満のため、通用 guard を作らず手動 DB 停用で処理するのが正しい。

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
