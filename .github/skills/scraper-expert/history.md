# Scraper Expert Error History

<!-- Append new entries at the top -->

---

## 2026-05-19 — eplus: 詳細ページ fetch による都道府県→市区レベルアドレス補完（commit `0cfd07f`）

**問題：** eplus.jp 検索結果カードには会場名が `（福岡県）` 形式（都道府県レベル）でしか含まれない。`location_address = "福岡県"` がそのまま DB に保存されるが、`enrich_location.py` は `location_address IS NULL OR ''` のみ処理するためスキップされ続けた（event `7cdd06cb` — アクロス福岡シンフォニーホール）。

**根本原因：** `_parse_card()` はカードテキストから `（都道府県）` パターンを抽出する設計。詳細ページ H1 には `(福岡市・2026/8/1(土))` という市区名が含まれるが、カードスクレイプではアクセスされない。

**修正（commit `0cfd07f`）：** Playwright セッション終了後、`_PREF_ONLY_RE = re.compile(r"^[^\s]+[都道府県]$")` にマッチした各イベントに対して `requests.get()` + `BeautifulSoup` で詳細ページ H1 を fetch。`r"\(([^・)]+[市区])\s*・"` パターンで市区名を抽出し `ev.location_address = city` に更新。

**教訓：**
- eplus.jp（および同様のチケットプラットフォーム）では詳細ページ H1 の `(市名・日付)` パターンから市区名が取得できる。
- `enrich_location.py` に頼らず、スクレイパー自身でアドレス精緻化を完結させる設計のほうが確実（後段スクリプトは null/空のみ処理するため）。
- regex に特定 Unicode 文字を使う場合は literal 文字を直接埋め込む（raw string 内の `\u30fb` は Unicode 文字として解釈されない）。

---

## 2026-05-19 — Peatix URL 正規化を URL 収集段階に拡張（7 件 DB 修正、commit `8b901ec`）

**問題：** 2026-05-17 の `_scrape_detail()` 入口修正（`e9c6f80b`）後も、DB に `/us/event/` URL が 7 件蓄積されており `55d766ae`（台湾家庭料理会in亀有）で再発。`peatix.com/us/event/4994536` → 302 → トップへリダイレクト。

**根本原因：** `_scrape_group_events` と `_search_events` でも locale prefix 付き URL が取得されていた。`_scrape_detail()` 入口の修正は detail scrape 時のみ有効で、URL 収集リストへの混入を防げなかった。正規 URL でスクレイプ済みの重複レコードが存在する場合、`/us/event/` 版は `source_id`（md5 ハッシュ）が異なる別レコードとして重複していた。

**修正（commit `8b901ec`）：** `_normalize_peatix_url()` をモジュールレベルに追加。`_scrape_group_events` と `_search_events` の URL 収集ループで適用。DB 7 件：5 件は `merged_into_event_id` で merge soft-delete、1 件は `source_url`/`source_id` 正規化、1 件（inactive）skip。

**教訓：** URL 正規化は収集段階（`_search_events`・`_scrape_group_events`）で行う。detail 入口修正は後段のため収集済みリストの汚染を防げない。DB 修正は「重複チェック → DUP: merge soft-delete / NO-DUP: update in place」の 2 分岐で設計する。

---

## 2026-05-17 — `ftip`: Peatix チャンネル URL がイベント URL より先に HTML に現れ、チャンネルページが source_url に設定された（event `eeb5b12e`）

**問題:** `source_url` / `official_url` が `https://nerimaokinawaeigasai.peatix.com`（主催者チャンネルページ）に設定され、個別イベントページ `https://peatix.com/event/4572285/view` が使われなかった。

**根本原因:** `_extract_peatix_url_from_html` が HTML アンカーを先頭から走査して**最初の** `peatix.com` リンクを返す設計。ftip 記事ではバナーのチャンネルリンク（`nerimaokinawaeigasai.peatix.com`）が個別イベントリンク（`peatix.com/event/4572285/view`）より先に出現するため、チャンネルページが返された。

**修正（commit `34368e3`）:** `_extract_peatix_url_from_html` を全アンカーを走査し `peatix.com/event/NNN` 形式を即時返却するよう改修。`/event/` が存在しない場合のみチャンネル URL を fallback として返す。

**教訓:** Peatix には `peatix.com/event/NNN`（個別イベント）と `org.peatix.com`（チャンネル）の 2 種類の URL がある。HTML 内で両方が出現する場合は `/event/NNN` を優先すること。「最初に見つかった URL を返す」実装は URL 種別の優先度を無視するため誤りを招く。

---

## 2026-05-17 — Peatix: ロケール付き URL（/us/event/）が source_url に保存される → broken link（event e9c6f80b）

**問題**
Peatix は訪問者のブラウザロケール設定によって `https://peatix.com/us/event/{id}` 形式（または `/jp/event/` 等）にリダイレクトする。Playwright が group ページから取得した `<a href>` がこのロケールプレフィックス付き形式だったため、`source_url=url` がそのまま保存され 404 になっていた。

**修復（commit ece9d33）**
`_scrape_detail()` の先頭で `re.sub(r"^(https://peatix\.com)/[a-z]{2}/event/", r"\1/event/", url)` を実行しロケールプレフィックスを除去。DB の event `e9c6f80b` も直接 update + `field_corrections` でロック済み。

**教訓**
- **Playwright が redirect 後の URL を `href` に反映することがある**：`page.goto(url)` 前にロケールプレフィックスを除去する。Peatix 以外でも `/en/`、`/us/`、`/jp/` 付き URL が `source_url` に混入しないかスクレイパーテスト時に確認する。
- **broken source_url の発見は user レポートに依存しがち**：`source_url` に `/us/`、`/en/`、`/jp/` が入っていないか dry-run ログで確認する習慣をつける。

---

## 2026-05-17 — `ftip`: WordPress RSS CDATA の `<a href>` が `.get_text()` で消え Peatix URL が未設定

**問題:** `scraper/sources/ftip.py` で Peatix URL が `official_url` / `source_url` に設定されなかった。ftip 記事ページには「Peatixからご購入」という記載はあったが、Peatix URL はプレインテキストではなく `<a href="https://xxx.peatix.com/...">` アンカーとして WordPress 記事本文（RSS CDATA）に埋め込まれていた。

**根本原因:** `content_html = content_el.get_text()` → `content_text = BeautifulSoup(content_html, "html.parser").get_text()` の二段階テキスト変換で `href` 属性が消える。既存の `_extract_peatix_url(content_text)` は正規表現でプレインテキストを検索するため URL を検出できなかった。

**修正:** `_extract_peatix_url_from_html(html_text)` を追加（commit `ee870f7`）。生の CDATA HTML 文字列（`content_html`）を BeautifulSoup で再パースし `find_all("a", href=True)` を走査。テキスト検索と HTML anchor 検索を OR で組み合わせ: `_extract_peatix_url(content_text) or _extract_peatix_url_from_html(content_html)`.

**教訓:** WordPress RSS CDATA にはリンクが `<a href>` として埋め込まれる。URL 抽出には `.get_text()` だけでなく、生 HTML 文字列を別途 BS4 でパースして `find_all("a", href=True)` を走査する関数が必要。テキスト検索と HTML 検索の両方を試みること。

---

## 2026-05-17 — `ftip`: `location_name` フォールバックに組織名定数を使用 → 会場欄に組織名が誤表示

**問題:** 会場抽出に失敗した全イベントで `location_name = "台湾原住民族との交流会"`（組織名）が設定されていた。event `eeb5b12e` では実際の会場「Coconeri３階 練馬区民・産業プラザ研修室１」ではなく組織名が会場として表示されていた。

**根本原因:** `LOCATION_NAME = "台湾原住民族との交流会"` 定数を venue フォールバックに使う設計。`location_name = venue_name if venue_name else LOCATION_NAME` というコードが原因。

**修正:** `location_name = venue_name if venue_name else None`（commit `278e6d8`）。

**教訓:** 組織名定数を `location_name` のフォールバックに使わない。会場が不明なら `None` を設定し、annotator や手動修正に委ねること。

---

## 2026-05-16 — `wuext_waseda` 多重セッション講座: `performer` が片假名+漢字複合名で截斷 + `business_hours` 不完整

**問題：** event `1be67e0f-36a3-4299-b178-9a6f13de98ee`（沖縄現場学, source=wuext_waseda）で 2 つの不具合：
1. `performer` = `吉田`（截斷）。本来は `カベルナリア 吉田`（片假名筆名 + 漢字姓）。
2. `business_hours` = `19:00〜20:30`（曜日・全N回・個別開講日が脱落）。詳細頁の `(日程詳細) 07/09, 07/16, 07/23, 07/30, 08/20, 08/27, 09/03` から構成すべき。

**根本原因：**
1. `scraper/sources/wuext_waseda.py` が `Event.performer=` を設定していなかった。Annotator の `_PERFORMER_INTRO_RE` は `[\u4e00-\u9fff]{2,5}` 純漢字パターンを使うため、`カベルナリア 吉田` は漢字部分 `吉田` のみ抽出されて DB に書き込まれた。
2. Scraper が `business_hours=` を設定していなかった。Annotator は単一の時間範囲（`19:00〜20:30`）しか抽出できず、曜日・全7回・跳週日付（08/06, 08/13 抜け）を保存できない。

**修正：**
1. `wuext_waseda.py` に `_SESSION_DATES_RE`、`_WEEKDAY_LISTING_RE`、`_KAISU_RE` regex と `_build_business_hours()` helper を追加。`Event(performer=instructor, performers=[instructor], business_hours=bh, ...)` を構造化欄から直接設定。
2. DB 直接 fix（`scraper/_oneoff_*` 不要、admin が手動で行う）。`field_corrections` で `performer` / `performers` / `business_hours` 3 件 lock。

**Lesson：**
- **Annotator の regex は構造化フィールドの代替ではない。** Source page に instructor / 講師 / 登壇者 / 時間表 のような structured field があるなら、scraper で `Event(...)` に直接設定。Annotator は raw text からの fallback 抽出のみ。
- 多重セッション講座（wuext_waseda、asahiculture 等）は `business_hours` を scraper で組み立てる必要がある。曜日 + 時間範囲 + 全N回 + 個別開講日逐項列出 を含める。

---

## 2026-05-16 — `tokyoartbeat` aggregator が `official_url=source_url` フォールバックでイベント詳細ページの「公式サイト」リンクを汚染

**問題：** event `74ee6d89`（共時的星叢―時を共にした星たち　越境する芸術のまなざし）の `official_url` が `https://www.tokyoartbeat.com/events/-/Synchronic-Constellation-...`（aggregator 自身）になっており、UI の「公式サイト」ボタンが東京都現代美術館の展覧会ページではなく tokyoartbeat に戻ってしまっていた。

**根本原因：** `scraper/sources/tokyoartbeat.py` line 124 の `or source_url` フォールバック。Contentful CMS の `showsWebpage` フィールドが空のとき、`official_url = source_url` となり tokyoartbeat URL に汚染される。

```python
# ❌ 汚染源
official_url = (
    self._loc(f.get("showsWebpage", {}), "en-US")
    or self._loc(f.get("showsWebpage", {}), "ja-JP")
    or source_url  # ← aggregator URL に汚染
)
```

**修復：**
1. DB レベル — event `74ee6d89` の `official_url` を `https://www.mot-art-museum.jp/exhibitions/Constellation/#section1` に修正し `field_corrections` にロック
2. scraper レベル — `or source_url` を `or None` に変更（aggregator は first-party ではないため null が正しい）
3. SKILL.md — 既存の「聚合站 scraper」ルールに `or source_url` フォールバックを「反パターンの第二形（CMS / API 系 aggregator 用）」として追記

**教訓：**
- Aggregator scraper（tokyoartbeat、peatix、doorkeeper、connpass、eplus、livepocket、kokuchpro 等）は **`source_url ≠ official_url`** が原則。CMS フィールドが空のときは `or None` でフォールバックを止め、annotator や手動 enrichment に委ねる。
- First-party scraper（taiwan_cultural_center、taiwan_matsuri、koryu、asahiculture、各シネマ等）は `official_url=url` / `official_url=detail_link` を明示的に設定してよい——`source_url` 自体が主催者の公式ページだから。
- 監査コマンド：`grep -rn "official_url.*or source_url\|official_url=source_url" scraper/sources/` → 0 件であるべき。

---

## 2026-05-15 — annotator が静的会場データを上書き → `database.py` に `_auto_lock_location()` を追加（commit `435d68a`）

**問題：** `cinemaclair`・`ks_cinema`・`hakusuisha` など固定会場を持つ cinema scraper では、`Event(location_name=..., location_address=...)` をスクレイパーが正確に設定していても、annotator 再実行時に GPT が `location_name` を書き換えることがあった（例：`シネマ・クレール` → `岡山市`）。

**根本原因：** 新規イベントが `upsert_events()` で挿入された後、`field_corrections` にロックレコードが存在しなかったため、annotator の `_ai_or_existing()` が DB 値を null とみなして上書きした。

**修復（commit `435d68a`）：** `database.py` に `_auto_lock_location(client, eid_to_event)` helper を追加。`upsert_events()` が新規イベントを挿入した直後に呼ばれ、`location_name`・`location_address`・`location_prefectures` を `field_corrections` に `ignore_duplicates=True`（DO NOTHING on conflict）で自動挿入する。既存イベントには影響しない。

**教訓：**
1. **固定会場 scraper は新規挿入時に自動ロックされる**：`location_name` を持つ新規イベントは `upsert_events()` 経由で挿入されると同時に FC にロックされる。手動 `field_corrections` 挿入は不要。
2. **既存イベントへの適用は手動**：既存イベントは自動ロックされない。`field_corrections` に手動挿入するか、`_lock_fields_via_corrections()` を使う。
3. **`ignore_duplicates=True` パターン**：FC upsert は常に DO NOTHING on conflict にする。既存の管理者修正値を上書きしないためのセーフガード。

---

## 2026-05-15 — cinemaclair: GPT-4o Vision OCR でスケジュール画像から上映時刻を取得（commit `33dc715`）

**背景：** シネマ・クレールの上映時刻は HTML に存在せず週次 JPEG スケジュール画像にのみ記載されている。通常の BeautifulSoup パースでは `business_hours` を取得できなかった。

**解決パターン（2-pass scrape + Vision OCR）：**
1. **1st pass**: 上映中台湾映画の候補を収集（`candidates` リスト）
2. **OCR step**: `_fetch_schedule_image_url()` でスケジュールページから週次 JPEG URL を動的取得 → `_ocr_schedule_showtimes(image_url, taiwan_titles)` で GPT-4o Vision に JSON 返答を要求 → `{title: "HH:MM / HH:MM"}` dict を返す
3. **2nd pass**: `_match_schedule(schedule_map, title)` で完全一致→部分一致の順でマッチング → `Event()` 生成

**Graceful fallback：** `OPENAI_API_KEY` 未設定時・例外時は `{}` を返し、`business_hours` は `NULL`（または `１週間限定上映` ラベルのフォールバック）になる。CI が Vision API なしでも動作する。

**コスト：** gpt-4o Vision 1回/実行 ≈ \$0.005/日。

**教訓：**
1. **HTML にない情報は Vision OCR で取得できる**：スケジュール画像・海報・掲示板など。2-pass パターン（候補収集 → OCR 1回 → Event 生成）でバッチコストを最小化する。
2. **Vision OCR は常に graceful fallback 付きで実装**：`OPENAI_API_KEY` 未設定時は `{}` を返す。例外を握り潰す（`except Exception: return {}`）のが正しいパターン。
3. **週次変更 URL は動的取得**：`_SCHEDULE_URL` を HTML パースして最新 JPEG href を取得する。ハードコードした URL は週替わりで 404 になる。

---

## 2026-05-15 — `lookup_movie_titles()` の戻り値が 2-tuple から 3-tuple に変更 → 16 call site で `ValueError` 発生（commit `c8bf85d`）

**問題：** `lookup_movie_titles(name_ja)` の返り値が `(name_zh, name_en)` 2-tuple から `(name_zh, name_en, official_url)` 3-tuple に変更された。既存の 13 ファイル・16 call site がすべて `a, b = lookup_movie_titles(...)` のまま残っており、実行時に `ValueError: too many values to unpack (expected 2)` が発生した。

**影響：** CinemartShinjuku, UplinkCinema, ShinBungeiza, CineMarine, GguideTV, RightsCube, CineswitchGinza, HumanTrustCinema, Johakyu, KsCinema, MorcAsagaya, TtcgKansai（12 scraper + eurospace logger 修正）。

**修復（commit `c8bf85d`）：** 全 16 call site を `a, b, _ = lookup_movie_titles(...)` に一括更新。`eurospace.py` の `self.logger` → モジュール level `logger` も同時修正。

**教訓：**
1. **`lookup_movie_titles()` の戻り値は 3-tuple `(name_zh, name_en, official_url)`**：`official_url` が不要な場合は `name_zh, name_en, _ = lookup_movie_titles(name_ja)` と書く。
2. **API signature 変更時は全 call site を同一 commit で一括更新する**。`grep -rn "lookup_movie_titles" scraper/sources/` で全件確認してから変更する。
3. **`official_url` は `lookup_movie_titles()` から自動取得できる**：eiga.com で映画が見つかった場合、その映画ページ URL が `official_url` として返される。scraper で `official_url=url` を別途取得する手間が省ける。

---

## 2026-05-15 — 電影院 scraper に `organizer` 未設定で admin イベントカードに場所名が表示されない（cinemaclair / human_trust_cinema）

**問題：** admin イベント一覧で `cinemaclair`（シネマ・クレール）や `human_trust_cinema`（ヒューマントラストシネマ有楽町）のイベントに対し、event card 内に 🏢 venue 行が表示されず、`kyoto_cinema`（🏢 京都シネマ表示）と比較して「場所なし」に見えた。

**根因：** `cinemaclair.py` と `human_trust_cinema.py` が `Event()` 生成時に `organizer=` を設定していなかった。`AdminEventTable` の event card は `organizer` フィールドを使って 🏢 行を表示する。`location_name` は venue column（右端 td）では表示されるが、event card 内には表示されない。一方 `kyoto_cinema.py`・`kino_shinsaibashi.py`・`sakurazaka.py` はいずれも `organizer=` を設定済みだったため表示されていた。

**修復：**
- `cinemaclair.py`: `organizer="シネマ・クレール"`, `organizer_type=["commercial_brand"]` 追加（commit `b7243a6` で実施済み）
- `human_trust_cinema.py`: `organizer="ヒューマントラストシネマ有楽町"`, `organizer_type=["commercial_brand"]` 追加

**教訓：**
1. **専用施設（映画館・劇場・ギャラリー等）の固定会場 scraper は必ず `organizer=` と `organizer_type=["commercial_brand"]` を設定する。** `location_name` は DB に保存されるが admin event card には表示されない。`organizer` が venue name の唯一の card 内表示手段。
2. **新規 scraper の動作確認チェックリスト**: `--dry-run` 結果に `organizer` フィールドが含まれているかを確認する。`location_name` が設定されていても admin UI 上で「場所なし」に見えることがある。
3. **参照 scraper**: `kyoto_cinema.py`・`kino_shinsaibashi.py`・`sakurazaka.py` は正しいパターンの例。

---

## 2026-05-15 — tsutaya_portal: span.place が venue 名に化ける + end_date 年なしパース失敗（event 7b37604e）

**問題 A — location_name に店内エリア名が入る**
イベントページの `div.date > span.place` には「スターバックス横平台」（店内の棚エリア名）が格納されていた。スクレイパーはこれを `location_name` として採用し、`card_store`（genre span から取得した「六本松 蔦屋書店」）へフォールバックしなかった。

**問題 B — end_date が start_date と同日になる**
詳細ページの `div.date` テキスト「2026年05月08日(金) - 06月07日(日)」において、end_date の「06月07日」は年を含まない。`_DETAIL_DATE_RE`（年必須パターン）のみでは 1 件しかマッチせず `end = start` になっていた。

**修復（commit 5f247c1）**
- `_DETAIL_END_DATE_SHORT_RE = re.compile(r"-\s*(\d{1,2})月(\d{1,2})日")` を追加、start_date の年から補完して end_date を算出。
- `location_name = card_store or location_name or None` — store 名を常に優先、`span.place`（店内エリア名）は venue として使わない。
- DB 手動修正（end_date / location_name / location_address を 3 件 FC ロック済み）

**教訓**
1. **詳細ページの「場所」フィールドは venue 名ではなく店内エリア名の場合がある**：`span.place` を `location_name` に使う前に、それが建物名（「〇〇 蔦屋書店」）か店内エリア名（「スターバックス横平台」）かを確認する。蔦屋書店系サイトでは genre span の店名（`card_store`）を優先するのが正しい。
2. **年なし end_date は short regex で補完する**：`YYYY年MM月DD日 - MM月DD日` 形式（年省略）は蔦屋書店ポータルでよく出現する。`start_date.year` から補完し、`end_month < start_month` の場合は翌年として処理する。

---

## 2026-05-15 — 台湾映画イベントの片名・人名 3 重誤り（cinemaclair 莎莉/Salli）

**イベント**: `6a0dbfb3` cinemaclair — 映画「サリー」（2023 年台湾）

**問題 A — 片名の誤り（薩莉 → 莎莉 / Sally → Salli）**

scraper が eiga.com に登録のない台湾映画を処理した際、GPT が漢字片名と英語片名を誤生成した。
- `name_zh = '薩莉'`（誤）→ `'莎莉'`（正）
- `name_en = 'Sally'`（誤）→ `'Salli'`（正）
- `works.title_zh`, `works.title_en`, `description_zh/en` も同様に誤り

**問題 B — 導演名の誤り（連建宏 → 練建宏 / Chien-hong → Chien-hung）**

導演名の漢字が 1 文字違い（`連` vs `練`）、ローマ字も誤り。
- `director_zh = '連建宏'`（誤）→ `'練建宏'`（正）
- `director_en = 'Lien Chien-hong'`（誤）→ `'Lien Chien-hung'`（正）
- `works.director` も同様

**問題 C — performers_zh[0] が片假名音訳（艾絲特·劉 → 劉品言）**

annotator が `performers[]` の片假名 `エスター・リウ` を機械的に音訳して `performers_zh[0] = '艾絲特·劉'` とした。エスター・リウの本名 `劉品言` とは一致しない。

**発覚経緯**: 金馬獎（GHFF）公式ページ `goldenhorse.org.tw/film/about/archive/detail/3913` を参照。

**修正**:
- `events`: `name_zh`, `name_en`, `director_zh`, `director_en`, `description_zh`, `description_en` 修正
- `works`: `original_title`, `title_zh`, `title_en`, `director` 修正
- `performers_zh[0]`: `'艾絲特·劉'` → `'劉品言'`
- `field_corrections` で 4 フィールド FC lock（re-annotation 上書き防止）

**規則**:
1. **台湾映画の権威ソース優先順位: GHFF > eiga.com > GPT**。金馬獎ページには正式な中文・英文片名と監督名が記載される。eiga.com に登録のない台湾映画は必ず GHFF を確認する。
2. **performers_zh[] は片假名音訳禁止**。エスター・リウ(`エスター・リウ`) → `艾絲特·劉` は機械音訳であり本名ではない。`_KNOWN_PERSON_MAP` に登録するか GHFF/eiga.com で本名を確認してから設定する。
3. **漢字 1 文字違いの人名を GPT に信頼しない**。`練建宏` vs `連建宏` のような近似漢字の誤りは視覚的に気づきにくい。人名は必ず信頼ソースで確認する。
4. **works 作成時は description_zh/en 内の片名参照も同時修正する**。`name_zh` だけ修正すると説明文内に旧片名が残る。

---

（セパレーター量詞 `*`→`+` / `get_text("\n")` 切替）

**A. `場所` キーワードが本文の一般名詞にマッチ（量詞 `*` → `+` 修正）**

**問題：** `_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]*([^\n]{3,60})")` が、文章中の「自由と多様性を称揚する**場所**」にマッチし、`location_name` が `」となるまでには、長く険しい道があったのです。 台湾の高校、そして...` というゴミテキストになった。

**根因：** `[　\s：:]*`（0 回以上）はセパレーターなしでもマッチする。`場所` の直後が `」` であっても通過し、後続 60 文字を venue として取得してしまう。

**修復：** `[　\s：:]*` → `[　\s：:]+`（1 回以上必須）。セパレーターのない `場所」` 形式はマッチしなくなる。

```python
# BEFORE (wrong)
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]*([^\n]{3,60})")
# AFTER (correct)
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]+([^\n]{3,60})")
```

**教訓：** venue / 日時ラベル後のセパレーター文字クラスは `+`（必須）で書く。`*` を使うと本文中の同名の一般名詞にマッチする。

**B. `get_text(" ")` で会場名にプログラム情報が混入**

**問題：** `+` 修正後も `location_name` が `早稲田大学早稲田キャンパス 3号館305教室 プログラム 司会　許仁碩（北海道大学 助教） 14:00-14:15　趣旨` となり、会場名以降のプログラム情報が混入した。

**根因：** `soup.get_text(" ", strip=True)` は HTML の全ブロックをスペース区切りで 1 行に結合する。会場行と次のセクションの間に改行がなく、`[^\n]{3,60}` が 60 文字まで取り込んでしまう。

**修復：** 会場抽出用に改行区切りのテキストを別途取得する：

```python
full_text    = soup.get_text(" ",  strip=True).replace("\x00", "")  # 既存（日付等）
full_text_nl = soup.get_text("\n", strip=True).replace("\x00", "")  # NEW（venue 専用）

mv = _VENUE_RE.search(full_text_nl)  # [^\n] がブロック境界で停止
```

**教訓：**
- `[^\n]` を使う regex の検索テキストには改行が必要 → `get_text("\n")` を使う。
- `get_text(" ")` は日付・概要など改行不要な場合に使い、構造依存の抽出（venue・日時）では `get_text("\n")` を使うこと。
- 二つのバリアントを変数として保持するのが安全：`full_text`（スペース区切り）と `full_text_nl`（改行区切り）。

---

## 2026-05-15 — annotator.py に `結果発表` パターンを追加 + `_inject_report_prefix` の ja 二重括弧バグを修正（commit `d0eb93e`）

**問題：** `【結果発表】台湾教育旅行プランニング大賞2023`（event `83f0723a`）が `report` カテゴリに分類されず、通常の学術イベントとして表示されていた。また、既存の `_inject_report_prefix` は ja 名称がすでに `【...】` で始まっていても `【レポート】` を前置し、`【レポート】【結果発表】xxx` という二重括弧を生成していた。

**根因：** `_REPORT_TRIGGER_RE` に `結果発表` が含まれていなかった。`_inject_report_prefix` は `name.startswith(p)` のみチェックし、`p = 【レポート】` 以外の任意の `【...】` 前置を考慮していなかった。

**修復（commit `d0eb93e`）：**
1. `_REPORT_TRIGGER_RE` に `結果発表` を追加 — 今後の re-annotation で自動的に `report` カテゴリが付与される。
2. `_inject_report_prefix` に `lang == "ja" and name.startswith("【")` ガードを追加 — ja 名称がすでに任意の `【...】` で始まる場合は prefix を注入しない。
3. Follow-up 作業：Supabase SQL で `raw_title LIKE '%結果発表%'` の既存 events に `report` を追加し、`python annotator.py --backfill-report-prefix` で name 接頭辞を注入。

**教訓：**
- `report` カテゴリの自動注入範囲を拡張する際は `_REPORT_TRIGGER_RE` を更新する（レポート・レポ・報告・記録・アーカイブ・recap・行ってきた・観てきた・見てきた・鑑賞レポ・**結果発表**）。
- `_inject_report_prefix` は「このプレフィックスで始まるか」だけでなく「任意の `【...】` ブラケット接頭辞がすでにあるか」も確認すること。単純な `startswith(p)` では不十分。
- 既存の annotated events は annotator の自動フローでは更新されない。バルク修正には Supabase SQL + `--backfill-report-prefix` を組み合わせる。

---

## 2026-05-13 — wuext_waseda スクレイパー実装（POST 検索・本文コンテナ・関数消失・日付フォールバック・台湾本文フィルタ）

**A. POST 検索 + 302 リダイレクト**
**問題：** `https://www.wuext.waseda.jp/course/search-list/` は GET パラメータでなく POST body で検索し、Cookie なしで 302 リダイレクトを返す。`?keyword=台湾` 形式の GET パラメータは無視される。
**根因：** サイトの `<form method="post">` を確認せず GET アクセスした。
**修復：** `requests.post(url, data={"keyword": "台湾", ...}, allow_redirects=True)` に変更。セッション Cookie 不要。
**教訓：** 大学・機関サイトの検索フォームは POST + 302 パターンが多い。`form[method]` 属性を必ず確認すること。

**B. 本文コンテナの特定（`id="course"`）**
**問題：** `soup.find('main')` / `soup.find('body')` でナビゲーションリンクが大量混入し、台湾キーワード判定が不正確になった。
**修復：** ブラウザ devtools / curl + grep で `id="course"` を特定し使用。
**教訓：** 本文コンテナは必ずソース確認で id/class を特定する。`find('main')` は万能ではない。

**C. `multi_replace_string_in_file` による関数消失**
**問題：** 複数箇所を一括置換した際、`def _get_detail_price(soup)` が `_is_taiwan_content()` の末尾に docstring のみとして混入し関数本体が消えた。実行時に `NameError: name '_get_detail_price' is not defined` が発生。
**根因：** 2 つの `newString` に `def _get_detail_price` が含まれ、2 回目の置換で関数定義行が孤立した。
**修復：** `read_file` でファイルの実際の内容を確認後、`replace_string_in_file` 1 回で正しく挿入。
**教訓：** `multi_replace_string_in_file` 後は必ず `read_file` で各関数境界（空行 2 行）を確認する。新しいヘルパー関数を追加する際は、空行 2 行の境界を明確にした `newString` を書くこと。

**D. オンデマンド講座の日付フォールバック（学期 → 月初）**
**問題：** オンデマンド講座の `日時` 列に日付範囲がなく `_parse_dates()` が `(None, None)` を返し、イベントがスキップされた。
**修復：** 3 段階（明示日付 → detail body 日付 → 学期フォールバック）の優先順位を実装。`_TERM_MONTH = {"年間":(4,1,False), "春期":(4,1,False), "夏期":(7,1,False), "秋期":(10,1,False), "冬期":(1,1,True)}`（`True` = 翌暦年）
**教訓：** オンデマンド・アーカイブ型コンテンツには学期・学年度から日付を導出するフォールバックを用意する。`None` でスキップするより近似値のほうが有用。→ SKILL.md § On-Demand / Viewing Period 参照

**E. タイトル非台湾コースの台湾本文フィルタ**
**問題：** 「緊迫する世界状勢と現代地政学」「沖縄現場学」など、タイトルに「台湾」を含まないが内容で台湾を扱うコースがスキップされた。
**修復：** 詳細ページ `id="course"` 本文を常に取得（価格取得と兼用）し、台湾キーワード（台湾・台北・台中・高雄・台南・日台・台日・中華民国）を検索。タイトルまたは本文のどちらかに含まれれば収録。
**教訓：** 大学講座では「台湾有事」「日台関係」のみ言及するコースが多い。台湾フィルタはタイトルだけでなく詳細ページ本文も検索すること。

---

## 2026-05-11 — Shopify サイトの `<a href>` は絶対 URL / `update_source.py` は既存行専用 / `feasibility` 列非存在（placebymethod 実装）

**問題①：** `placebymethod.com`（Shopify）の展覧会一覧ページで `soup.find_all("a", href=re.compile(r"^/pages/"))` を試みたところ 0 件返却。

**根因①：** Shopify は `<a href>` に**フル絶対 URL**（`https://placebymethod.com/pages/slug`）を出力する。相対パス `^/pages/` にはマッチしない。

**修正①：**
```python
# ❌ 相対パス前提 — Shopify では 0 件
soup.find_all("a", href=re.compile(r"^/pages/"))

# ✅ フル URL にマッチ
soup.find_all("a", href=re.compile(r"placebymethod\.com/pages/"))
```

**問題②：** `python update_source.py --url https://placebymethod.com/pages/contact --status researched` → `ERROR: No row found in research_sources for URL`。

**根因②：** `update_source.py` の UPDATE 処理は**対象 URL の行が既に `research_sources` に存在する場合のみ**動作する。新規ソース（DB 未登録）には使えない。

**修正②：** 新規ソースは Supabase SDK で直接 `insert()` する:
```python
sb.table("research_sources").insert({
    "url": "https://placebymethod.com/pages/contact",
    "name": "(PLACE) by method",
    "status": "implemented",
    "scraper_source_name": "placebymethod",
    "url_verified": True,
    "source_profile": {"feasibility": "medium"},
}).execute()
```

**問題③：** `insert()` に `"feasibility": "medium"` をトップレベルで指定 → `PGRST204: Could not find the 'feasibility' column`。

**根因③：** `research_sources` のトップレベル列名は `scraping_feasibility`（`feasibility` ではない）。または `source_profile` JSONB 内に `"feasibility"` キーで格納する。

**教訓：**
- **Shopify サイトは `<a href>` に絶対 URL を出力する。** 相対パス regex は必ず 0 件になる。`href=re.compile(r"{domain}/pages/")` パターンを使うこと。
- **`update_source.py` は既存行の UPDATE 専用。** 新規ソースを `research_sources` に登録するには Supabase SDK で `insert()` を使う（行が存在する場合は `upsert(on_conflict="url")`）。
- **`research_sources` の feasibility 列名は `scraping_feasibility`**（`feasibility` ではない）。または `source_profile` JSONB 内に `"feasibility"` キーで格納する。

---

## 2026-05-06 — bookandbeer: keyword= URL パラメータがサーバー側でフィルタされない（100% ノイズ問題）

**問題：** `bookandbeer.com/event/?keyword=台湾` というURLをフェッチしていたが、サイト側でキーワードフィルタが**全く機能していない**（全イベントが返される）。スクレイパーにクライアント側チェックがなく、active 19 件の全てが非台湾イベントだった（台湾関連ヒット率 0%）。

**根因：** auto_scraper で生成されたスクレイパーは、URLの keyword= パラメータが実際にフィルタされているかどうかを検証しない。生成時に 1 件でも台湾イベントが返れば「動いた」と判定して登録してしまう。

**修復（commit e1ab468）：**
- `_is_taiwan_relevant(title, description)` を 3 段階で実装：
  1. タイトル（name_ja）に台湾キーワードがあれば即通過
  2. 説明文冒頭 500 字に台湾キーワードが 2 回以上出現
  3. 著者略歴の大学名パターン（`_AUTHOR_BIO_RE`：台湾大学・淡江大学等）を除去してから再判定 → false positive 防止
- DB の既存 active 19 件を `is_active=False` に更新

**教訓：**
1. **keyword= は信用しない**：サイトによっては keyword URL パラメータがサーバー側でフィルタされず、全件返す。新規 scraper 追加時は `dry-run` で取得結果に台湾キーワードが含まれるか必ず確認。
2. **著者略歴の false positive**：書店イベントは著者の大学名・所属に「台湾大学」が出やすい。タイトルに台湾がない場合は 500 字冒頭チェック + 大学名パターン除去が有効。
3. **auto_qa の盲点**：`auto_qa_address_is_venue_name` 等の detector は台湾関連性チェックをしない。keyword フィルタ有効性は人間による定期確認が必要。

---

## 2026-05-15 — annotator が講座イベントに performers=['記'] を誤設定（手動 DB 修正）

**問題：** asahiculture イベント `1334fc96`（村山秀太郎講師の台湾現代史講座）で `performers=['記']`・`performer_zh='記'`・`performer_en='Ki'` という誤値が存在。`performer='村山 秀太郎'`（FC 済み）は正しいのに `performers[]` が単一漢字「記」で汚染されていた。

**根因：** annotator の GPT（または `enrich_person_names()` の B1 ロジック）が `performer` フィールドから `performers[]` を導出する際、テキスト断片の単一文字「記」を performer 名と誤解析した。その後 `enrich_person_names()` がその誤値をそのまま翻訳し `performer_zh='記'` → `performer_en='Ki'` になった。

**修復（手動 DB 修正、2026-05-15）：**
```python
EID = '1334fc96-6dac-4862-afbb-6b95b78c1abc'
updates = {
    'performers':   ['村山 秀太郎'],
    'performer_zh': '村山秀太郎',      # 中国語表記：スペースなし
    'performer_en': 'Murayama Hidetaro',  # ローマ字：姓→名順
}
sb.table('events').update(updates).eq('id', EID).execute()
# + field_corrections FC lock（3フィールド全て）
```

**教訓：**
- `performers[]` に単一漢字・単一記号が含まれる場合は annotator の誤解析シグナル。現行 `auto_qa_performer_multi_value_pollution` は検出しない（1 要素のため）。
- 手動修正パターン：`performer` FC が正しい → `performers[0]` に sync → `performer_zh/en` はソース確認後に設定。
  - 日本人名の Chinese 表記：漢字そのまま、スペースなし（例：`村山秀太郎`）
  - 日本人名の English 表記：ローマ字、姓→名順（例：`Murayama Hidetaro`）
- 修正後は必ず `field_corrections` FC ロックを 3 フィールド（`performers`, `performer_zh`, `performer_en`）に適用する。

---

## 2026-05-15 — `event_form="film_screening"` 誤設定 revert（DB constraint 不存在）

**問題**: Cinema scraper 全稽核修復シリーズで `event_form=["film_screening"]` を4ファイルに設定したが、DB check constraint（migration 047）に `"film_screening"` は存在しない。有効値は `"screening"`。次回 CI 実行時に constraint エラーで upsert が全件失敗するところだった。

**根本原因**: SKILL.md に「`"screening"` は無効値 → `"film_screening"` が正解」と誤記した。実際の constraint を確認せずに文書化・実装した。

**発覚経緯**: cinemaclair イベント `6a0dbfb3` の performers_zh 修正時に `film_screening` で UPDATE を試みたところ `events_event_form_check` constraint エラーが返った。

**修正**:
- `human_trust_cinema.py`, `sakurazaka.py`, `kino_shinsaibashi.py`, `kyoto_cinema.py`: `["film_screening"]` → `["screening"]`
- `SKILL.md § 共通禁止事項 #5`: 誤記を訂正（`film_screening` → `screening`）
- `engineer.agent.md rule #10`: 同様に訂正

**教訓**: event_form の valid 値を変更・追加する場合は必ず migration 047 の check constraint を確認すること。SKILL.md に valid 値を明記して constraint 一覧と照合する。

---

## 2026-05-15 — Cinema scraper 全稽核修復シリーズ（13 scraper、4コミット）

**問題**: Cinema scraper 稽核表の作成後、実際の修復作業を実施。13個の scraper が UTC datetime 未対応・`event_form` 未設定・SINGLE-DAY RULE 未防護のいずれか（または複数）の問題を抱えていた。

**修復コミット**:
- `23e417f`: ks_cinema — `business_hours` 提取追加
- `544bbc4`: cinemadict UTC + business_hours / kino_shinsaibashi `film_screening` + prefix
- `e91f5cd`: 9 scraper 一括 — event_form×2（`"screening"` → `"film_screening"`）、SINGLE-DAY RULE prefix×3、UTC×7
- `7849021`: human_trust_cinema UTC + SINGLE-DAY RULE 防護 + event_form

**発見した bug パターン**:
1. **`event_form=["screening"]` 無効値**: `kyoto_cinema`・`sakurazaka`・`kino_shinsaibashi` が `"screening"` を使用。有効値は `"film_screening"`。DB check constraint エラーを引き起こす。
2. **naive datetime（UTC 未設定）**: 7ファイルで `datetime(y, m, d)` が naive。一般規則はあったが cinema scraper では徹底されていなかった。
3. **JST ISO datetime 誤変換**: `human_trust_cinema` が `.replace("+09:00", "")` で naive datetime を生成。正解: `datetime.fromisoformat(data_date)` → JST-aware → `datetime(y, m, d, tzinfo=timezone.utc)`。
4. **Type 3 SINGLE-DAY RULE 誤発動**: `end_date=None`（サイト情報なし）のとき、`raw_description` に単日付 prefix を入れると annotator が `end_date=start_date` に設定する。Type 3 で end_date 取得不可の場合は date prefix を入れない。start_date はフィールドに格納済みなので raw_description に繰り返す必要はない。
5. **稽核表の ghost エントリ**: `ciemarine` がファイル不存在なのに稽核表に記載されていた → 削除。

**規則（→ SKILL.md § Cinema scraper 共通禁止事項に追加）**:
- 全 cinema scraper は `event_form=["film_screening"]` 必須（`"screening"` は無効）
- Type 3 で end_date 取得不可の場合、raw_description に単日付 prefix を入れない
- JST ISO datetime: `.replace("+09:00", "")` パターン禁止 → fromisoformat + UTC midnight 変換
- 稽核表に新行追加前に `ls scraper/sources/<name>.py` でファイル存在を確認する

---

## 2026-05-15 — Cinema scraper `end_date` / `business_hours` 全体標準化（稽核表作成）

**問題**: 18個の cinema scraper のうち完全準拠は3個のみ（cinemart_shinjuku, shin_bungeiza, starcat_cinema）。15個が `business_hours = None` で、1個（human_trust_cinema）は `end_date` も None。

**根本原因**: `business_hours` と `end_date` の実装基準が文書化されておらず、新規 scraper 作成時の標準として伝達されていなかった。

**修正（commit `e24023c` + 今次 commit）**:
1. SKILL.md の重複セクション（`## Cinema scraper — business_hours`）を削除・統合
2. 3タイプ分類（Type 1: 票務平台分離型 / Type 2: 排片表嵌入型 / Type 3: 上映中リスト型）を定義
3. 共通禁止事項（`end_date=start_date`, 空 `business_hours=""`, 推測 `end_date`）を明記
4. annotator SINGLE-DAY RULE 防護規則（`raw_description` 前綴に期間範囲必須）を追記
5. 18 scraper 稽核表を SKILL.md に追加（新規 scraper 作成時に更新義務）
6. `engineer.agent.md` に Cinema scraper rule #10 を追加（3タイプ要約 + SKILL.md 参照）

**要対応リスト（`business_hours = None`）**:
ks_cinema, kino_shinsaibashi, kyoto_cinema, cineswitch_ginza, theater_enya, cinewind, ciema, cinemadict, ycam_cinema, sakurazaka, ciemarine, uedaeigeki, theater_kino

**緊急対応（`end_date = None` かつ `business_hours = None`）**:
- human_trust_cinema: TTCG CMS からの場次取得方法を調査必要

**規則**: Cinema scraper は Type 1/2/3 に従い `end_date` + `business_hours` を実装すること。新規作成時は SKILL.md § Cinema scraper 完全規則 + 稽核表を必ず参照。

---

## 2026-05-15 — starcat_cinema end_date 錯誤（SINGLE-DAY RULE 覆寫）

**問題：** `end_date = start_date`（兩者均為 2026-05-15）。電影實際上映至 5/21（木），但 annotator SINGLE-DAY RULE 把 end_date 覆寫成開始日。

**根本原因：**
1. scraper 設 `end_date=None` → annotator GPT 讀 raw_description 中的「2026年5月15日(金)より公開」 → 只有單一日期 → SINGLE-DAY RULE → `end_date = start_date`
2. scraper 沒有實作從票務排片推導 end_date 的邏輯

**修正（commit `3b40cb5`）：**
- `_build_ticket_schedule()` 改回傳 `(business_hours_str, last_date_utc)` tuple
- 新增 `_lookup_schedule_entry()` / `_lookup_end_date()` helpers
- `scrape()` 從 ticket schedule 最後一日取 `end_date`（= 當週木曜）
- `raw_description` 前綴改為「上映期間: YYYY年M月D日〜YYYY年M月D日」— 防止 annotator SINGLE-DAY RULE 覆寫
- `_parse_date()` 加 `tzinfo=timezone.utc`

**規則：** 日本電影院每週四公布排片（金曜〜木曜）。Cinema scraper 必須從票務 schedule 取 `last_dt` 作為 `end_date`，並在 `raw_description` 前綴中同時標明開始與結束日期。→ 新增至 SKILL.md § Cinema scraper — `end_date` 每週排片末日（木曜）規則

---

## 2026-05-15 — asahiculture 4 欄位同時抓錯（venue / end_date / performer / organizer）

**根本原因分析（事件 `asahiculture_8759178`，立川サテライト教室）：**

### A — `location_name` 讀搜尋卡片 branch，非實際場地
搜尋結果 `li.text-school` 顯示**行政管轄教室**（新宿教室），而衛星課程的實際場地（立川サテライト教室）只在 detail 頁`備考`表格以`「会場名」`括弧呈現。爬蟲直接用 card branch，導致 `location_name` 永遠是管理端教室。
**修正：** `_fetch_detail()` 讀 `備考` `th/td` row，以 `r"「([^」]+)」"` 提取真實場地；fallback 才使用 card branch。

### B — `end_date` 只取第一個日期（`re.search`）
`_parse_date()` 用 `re.search()` 只回傳第一個 match。`2026/04/07火～2026/06/16火` 兩個完整日期，只抓 `04/07`，`06/16` 永遠遺失。
**修正：** 替換為 `_parse_date_range()`，用 `re.findall()` 取所有日期，`[0]` 為 `start_date`，`[-1]` 為 `end_date`。

### C — `performer` 被「台湾キーワード」篩選遮蔽
`_fetch_detail_description()` 只撈含「台湾/Taiwan」的 `<p>` 段落。講師介紹區塊（`<h3>` heading）不含台灣關鍵字，完全被略過。annotator 後來從 `raw_description` 結尾的「（講師・記）」截出「記」作為 performer。
**修正：** `_fetch_detail()` 獨立掃所有 `<h3>`，用漢字姓名 regex `r"([\u4e00-\u9fff]{1,6}[\s\u3000]+[\u4e00-\u9fff]{1,6})[\s\u3000]*[（(]"` 提取姓名。

### D — `organizer` 從未提取
爬蟲完全沒有 organizer 提取邏輯，交給 annotator 推斷，annotator 缺線索也留 None。
**修正：** 加入模組級常數 `ORGANIZER = "朝日カルチャーセンター"`，Event constructor 直接設定。

**修正 commit：** `da3ac31`

---

## 2026-05-12 — nittai_toumonkai / tsudoi_osaka scrapers + frontend UTC date fix

### A — WordPress `<strong>` strip 後空格 → `\s*` regex

**問題：** WordPress RSS 的 `<description>` 中，`<strong>` 標籤 strip 後數字之間出現空格：`"2026 年 1 月 31 日"`（本文無空格，但 BeautifulSoup strip 後插入）。
**根因：** `BeautifulSoup.get_text()` 在移除 inline 標籤時會在 tag 邊界插入隱性空格。
**修正：** 日期 regex 改用 `\s*`：`r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"` — 通用於所有 WordPress 來源。
**教訓：** 所有 WordPress `raw_description` 的日期 regex 必須用 `\s*` 取代固定空格，以應對 tag-strip artifact。

### B — venue regex 負向前瞻 `(?!受付)` 防誤匹配

**問題：** `会場受付` 誤匹配 `会場` venue 偵測 regex，導致後綴詞被截成場地名。
**修正：** `r"会場(?!受付)"` — 負向前瞻阻止 `会場受付` 命中。
**教訓：** venue regex（`会場`、`場所`、`開催場所` 等）必須加上 `(?!<後綴詞>)` 防止誤匹配常見複合詞。

### C — 全形數字轉換 `unicodedata.normalize("NFKC")`

**問題：** nittai_toumonkai 網頁含全形數字（`２０２６年`），直接比對 `\d` 失敗。
**修正：** 在 parse 前呼叫 `unicodedata.normalize("NFKC", text)` 統一轉換為半形。
**教訓：** 任何日本網頁的文字 parse 前，應先 NFKC normalize。輔助函式可命名 `_fw_to_ascii()`。

### D — Jimdo URL 日語路徑編碼不一致 → `unquote(href)`

**問題：** Jimdo CMS 的 `href` 屬性有時使用 URL-encoded 日語路徑（`%E3%83%96%E3%83%AD%E3%82%B0`），有時直接為日語字元，導致比對/去重失敗。
**修正：** 收集所有 `<a>` href 時先 `from urllib.parse import unquote; unquote(href)` 正規化，再進行比對。
**教訓：** Jimdo / WordPress 等 CMS 的 href 需 unquote 後再比對，避免同一 URL 在不同頁面出現兩種編碼。

### E — Frontend client component UTC/本地時間不一致 → `getUTCDate()` + `timeZone:"UTC"`

**問題：** `EventListClient.tsx`（client component）使用 `getDate()` 和 `toLocaleDateString`（無 `timeZone` 參數）。DB 的 timestamp 以 UTC 儲存，JST 瀏覽器將 `UTC 15:00` 解讀為隔天，導致日期顯示比 SSR 多一天（如顯示 14 而非 13）。`MovieWorksList.tsx` 的 `fmtDate()` 有相同問題。
**根因：** 爬蟲將 JST 時間儲存時未附 `+09:00` offset，Supabase 解讀為 UTC，實際時間變為 JST 深夜（`2026-06-13T00:00:00+00:00` → JST `2026-06-13 09:00` 無問題；但 `2026-06-13T15:00:00+00:00` → JST `2026-06-14 00:00`，跨日）。
**修正：** `getDate()` → `getUTCDate()`；`toLocaleDateString` 加上 `{ timeZone: "UTC" }` 參數。兩個 client component 同步修正。
**教訓：** DB 儲存的 timestamp 是 UTC；client component 一律使用 `getUTCDate()` / `{ timeZone: "UTC" }` 才能與 SSR（UTC Node.js 環境）一致。

---

## 2026-05-09 — `_KNOWN_PERSON_MAP` 藝名/筆名 GPT 翻譯覆寫 + performers_zh/en 多語言陣列

### A — GPT 片假名藝名翻譯失敗 → `_KNOWN_PERSON_MAP` hardcoded 解法

**問題：** `backfill_performer_i18n()` 用 GPT 翻譯片假名名，對藝名/筆名產生錯誤音譯：`ギデンズ・コー` → `基登斯·高`（正確：`九把刀` / `Giddens Ko`）。
**根因：** 藝名與片假名無語音對應關係，GPT 語音推測必然失敗。
**修正：** `annotator.py` 新增 `_KNOWN_PERSON_MAP`（14 筆已驗證名人），三個整合點（annotation loop、performers[] 逐元素、backfill Layer 0）。11 筆 DB 事件修正。
**教訓：** 藝名/筆名不可靠 GPT 翻譯。已知名人必須收錄 `_KNOWN_PERSON_MAP`，新增時三語同時驗證（eiga.com / 官方 / Wikipedia）。

### B — `performers_zh[]` / `performers_en[]` 多語言陣列新增

**問題：** 多人事件只有 `performers[]`（日文），中英頁面顯示日文名。
**修正：** migration 056 新增 `performers_zh TEXT[]`、`performers_en TEXT[]`；Event dataclass / database.py 同步更新；getEventPerformer() 多人分支優先使用語言對應陣列。178 筆 backfill。
**教訓：** 多語言陣列欄位新增後，前端 locale 優先序和 array 長度判斷需同步更新。

### C — 翻譯規則嚴格化

**確立規則：** (1) 拉丁字母名原樣保留 (2) CJK 漢字名無驗證來源不翻譯 (3) 片假名僅有驗證來源時翻譯 (4) `backfill_performer_i18n()` 不可限定 `is_active=True`
**教訓：** 翻譯規則必須在 SKILL.md 明文記載，否則每次 backfill 都會重複犯錯。

---

## 2026-05-07 — KG+ Kyotographie scraper 新規実装 + 4 scrapers 復元（commit `de6c31d`）

### A — KgplusKyotographieScraper 実装

**新規 scraper**: `kgplus_kyotographie` — KYOTOGRAPHIE International Photography Festival の衛星プログラム KG+ の台湾関連展示を取得。

**設計**:
- **WP REST API で CPT 名を動的検出**：`/wp-json/wp/v2/types` から `exhibitions_plus{YEAR}` を探し、フェスティバル年度を自動判定（ハードコード不要）
- **全展示スラグ列挙**：`/wp-json/wp/v2/exhibitions_plus{YEAR}?per_page=100&page=N` でページネーション（2026年: 213件 × 3ページ）
- **個別HTML取得 + 台湾フィルタ**：各展示ページを fetch し `台湾/Taiwan/臺灣/台南/台北/Taiwanese` でフィルタリング
- **日付パース**：`<p class="-openclose">` の `"Open: M.D Weekday–M.D Weekday"` 形式、年度は CPT 名から推定
- Playwright 不要（WP REST API + requests のみ）

**2026年実績**: 4件の台湾関連展示を検出（makoto-lin, chan-man-ching, naoki-miyashita, sean-tseng-asano-tsutsumi-sara-wu）

**教訓**:
- WordPress CPT 名に年度を含むサイト（`exhibitions_plus2026` 等）は `/wp-json/wp/v2/types` で動的に名前を取得すること — ハードコードすると翌年に silent failure する
- 全件スキャン + クライアントサイドフィルタが最も確実。API 側の台湾フィルタが存在しなくても問題ない（`_REQUEST_DELAY = 0.5s` でレート制限）

### B — 4 scrapers 復元（johakyu, stranger, tsutaya_portal, tsudoi_osaka）

**問題**: 前回のコミットで `main.py` の import/SCRAPERS が再編成され、4 つの scraper が誤ってドロップされていた。

**復元内容** (commit `de6c31d`):
- `JohakyuScraper` — 浄化湯（映画館）
- `StrangerScraper` — Stranger（東京墨田区の映画館）
- `TsutayaPortalScraper` — 蔦屋書店ポータル（`_is_taiwan_relevant()` 偽陽性修正済み）
- `TsudoiOsakaScraper` — 大阪のコミュニティイベント

**教訓**: SCRAPERS リスト audit を main.py に変更を加える**全コミット前**に実行すること。新規 scraper 追加コミットでも既存 scraper が誤ってドロップされることがある。Audit コマンド:
```bash
python3 -c "import re, glob; registered=set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read())); [print('UNREGISTERED:', re.search(r'class (\w+Scraper)\b', open(f).read()).group(1), f) for f in glob.glob('sources/*.py') if re.search(r'class (\w+Scraper)\b', open(f).read()) and re.search(r'class (\w+Scraper)\b', open(f).read()).group(1) not in registered and re.search(r'class (\w+Scraper)\b', open(f).read()).group(1) != 'BaseScraper']"
```

---

## 2026-05-07 — note_creators full-article fetch + Vision OCR pipeline 実装（commit `a52f5b2`）

### A — note_creators.py full-article fetch + og:image

**Problem**: `note_creators.py` が RSS の「続きをみる」truncated text（39 字以下）しか取得できなかった。結果として：
- `start_date` が記事発布時間（`pub_date` + non-midnight timestamp）にフォールバック（`2cae572a` start_date=2026-03-17 が実際は 2026-04-06 だった問題の根本原因）
- `raw_description` が薄すぎて annotator が organizer/venue/date を正確に抽出できない
- `image_url` が未取得

**Fix**: `_fetch_article_content(url, session) → (body_text, image_url | None)` を実装：
1. JSON-LD `articleBody` → `description` → BS4 `<p>` タグ連結の 3 段階フォールバックで本文取得
2. `og:image` メタタグで画像 URL 抽取 → `Event.image_url` にセット
3. `_BODY_DATE_RE` パターン（`📅 2026年4月6日`、`日時：4/6`、`◎ MM月DD日` 等）で本文から直接日時抽出
4. thin content 検知（`len(body) < 40`）時は `time.sleep(1)` 後に自動 detail fetch を実行

**Lesson**: RSS-based scraper で `raw_description` が短い（「続きをみる」「Read more」等）場合は、scrape 段階で detail page を fetch して本文を取得するべき。`pub_date` フォールバックを debug するより根本的に thin content を解消することで start_date 問題も同時に解決できる。

### B — Vision OCR pipeline `enrich_poster.py` 新規作成

**Feature**: `scraper/enrich_poster.py` — GPT-4o Vision でイベントポスター画像から情報を抽出する enrichment pipeline。

**Design**:
- `_fetch_candidates(sb, max_events)`: `image_url IS NOT NULL` かつ `annotation_status IN ('pending', 'annotated')` のイベントを選択
- `_extract_from_poster(image_url)`: GPT-4o Vision で JSON 出力（date, venue, organizer, confidence）
- `_apply_if_confident(sb, event, result, dry_run)`: `confidence ≥ 0.8` のフィールドのみ適用 + `field_corrections` でロック
- **Thin Content Guard**: `raw_description < 100 字` の場合は `organizer` フィールドを non-apply（date/venue のみ）
- CLI: `python enrich_poster.py [--dry-run] [--event-id UUID] [--max N]`
- migration 057 適用済み：`events.image_url TEXT`; `Event` dataclass + `database.py` に `image_url` フィールド追加
- CI: `scraper.yml` の annotator ステップ直後に `Run Vision OCR enrichment` ステップ追加

**Lesson**: Vision OCR のような外部知識依存 enrichment では Organizer Non-Hallucination Guard と同様のリスクがある。thin content 時は organizer を適用しない Thin Content Guard を組み込み、GPT の hallucination リスクを抑制すること。confidence threshold（≥ 0.8）による自動適用は一見安全だが、画像から読み取れない情報は GPT が「知っている知識」で補完してしまう点に注意。

---

## 2026-05-07 — auto_research.py Playwright 逾時導致整批中止（commit `8029b74`）

**Error**: `_fetch_sample_html()` 呼叫 `page.goto(url, timeout=30_000)` 無 try/except。`note.com/swi0881` 逾時 → 未捕獲 `PlaywrightTimeoutError` → 整個 auto-research CI job exit code 1，所有後續來源全部跳過。

**Fix**:
1. `_fetch_sample_html` 捕獲 `playwright.sync_api.TimeoutError` → log warning → return `""`
2. `run()` 將空 `sample_html` 視為 `AssessError("error", ...)` → 該來源標記 `error` in DB → batch 繼續到下一列

**Lesson**: CI 批次腳本中，每個 `page.goto()` 都必須包裝 `TimeoutError` 捕獲。任何單一慢速 / 被封鎖 URL 都不得中止整個批次。

→ Added to SKILL.md §「Playwright CI 批次容錯規則」

---

## 2026-05-07 — AdminEventTable performers[] 顯示修正（commit 9b84d98）

**Error**: 父事件 `b90afe3c`（台湾史研究会3月例会）有 `performers=['陳志剛', '福田真郷']` 但 `performer=null`，`AdminEventTable` 只讀取 `performer` 欄位，導致顯示空白。`getEventPerformer()` helper 也未優先使用 `performers[]`，多人學術事件的表演者一律不顯示。

**Fix**:
1. `web/lib/types.ts` — `getEventPerformer()` 重寫：優先序 `performers[]`（join「、」）→ `performer_zh/en` → `performer`（legacy fallback）。
2. `web/components/AdminEventTable.tsx` — 顯示邏輯改用 `performers.join('、')`，全文搜尋也加入 `performers[]` spread。
3. `web/app/[locale]/events/[id]/page.tsx` — 移除複雜三段式條件，統一呼叫 `getEventPerformer()`。

**Lesson**: `performer`（TEXT）是 legacy 單人欄位，`performers[]`（TEXT[]）是正確的多人欄位。UI 所有使用 performer 的地方都必須改為 `performers[]` 優先，並統一透過 `getEventPerformer()` helper 讀取，不可直接存取 `event.performer`。

→ Updated architect.agent.md §「Performer Multilingual Fields Guard」Rule 2

---

## 2026-05-07 — 0d97e51c（2025年台湾史研究会3月例会）5 件 DB 手動修正

**Error 1 — performers[] 跨年度混入**：`performers=['陳志剛', '福田真郷']`（2026年3月例会成員）被錯填進 2025年3月例会。根本原因：performers[] 批次回填時按 source_name + 月份比對，不同年份的相同月份事件互相污染。  
**Fix 1**: `performers=['やまだあつし', '下岡友加']`（raw_description 明記）+ `field_corrections` 鎖定。

**Error 2 — event_form 不正確**：`['lecture']` 應為 `['conference']`（兩場報告的學術例会 = conference，非單場 lecture）。  
**Fix 2**: `event_form=['conference']` + FC 鎖定。

**Error 3 — location_name 不完整**：`関西大学千里山キャンパス 経商研究棟` 漏掉子場地後綴（6階 大会議室）。  
**Fix 3**: `関西大学千里山キャンパス 経商研究棟6階 大会議室`，多語言欄位（zh/en）同步更新。

**Error 4 — location_url 誤填申込表單 URL**：`https://forms.gle/...`（申込 Google Form）填入 `location_url`。`location_url` 應為會場 URL，不應填入申込表單。  
**Fix 4**: `location_url=null`。

**Error 5 — sub-events 未啟用**：子事件 a8702ec8（第1報告）和 d85547af（第2報告）`is_active=False`。  
**Fix 5**: `is_active=True`（兩件）。

**Lessons**:
- **performers[] 批次回填**必須對照 raw_description 確認姓名，不可只靠 source_name + 月份比對——不同年份同月份事件會互相污染。
- **event_form 區分**：單場演講 = `['lecture']`；多位報告者的學術例会（2 報告以上）= `['conference']`。taiwanshi 等研究会月例会通常是 `['conference']`。
- **location_url 語義**：只填會場官方 URL（e.g. 大学キャンパスページ）；申込表單（Google Forms 等）屬於 `source_url` / `official_url` 責任範圍，不填 `location_url`。

→ Added to SKILL.md §「performers[] 批次回填驗證規則」、§「event_form — lecture vs conference 區分」、§「location_url 語義規則補充」

---

## 2026-05-06 — 《中村地平上映会》business_hours 亂碼字元 U+3016（DB 手動修正）

**Error**: `business_hours='13:30〖16:30'`。`〖`（U+3016 LEFT BLACK LENTICULAR BRACKET）在 kokuchpro scraper 字元轉換過程中出現，導致時間字串顯示異常（非全形波浪號 ～）。

**Fix**: DB 直接修正 → `business_hours='13:30～16:30'`。

**Lesson**: kokuchpro 頁面的時間分隔符可能含非標準 Unicode（〖 U+3016 等），抓取後需驗證分隔符是否為正確字元（全形波浪號 U+FF5E）。新增「〖 U+3016 偵測」至 scraper 字元正規化流程。

→ Added to SKILL.md §「DB 手動修正 — business_hours 亂碼字元偵測」

---

## 2026-05-06 — 《造山者》片名局部錯誤（DB 手動修正）

**Error**: `name_ja='映画『造山者 ― 世紀の賭け』大阪上映会'`（正式日文片名應為「チップ・オデッセイ 台湾の賭け」）；`name_zh='電影《造山者─世紀的賭注》大阪放映會'`（副標題不正確）。note_creators 薄文本（「続きをみる」截斷），GPT 從截斷文字推出錯誤片名。

**Fix**: `name_ja='映画『チップ・オデッセイ 台湾の賭け』大阪上映会'`；`name_zh='電影《造山者》大阪放映會'`。

**Lesson**: note_creators 薄文本案例中 GPT 可能根據截斷文字推出錯誤片名；修正時應以 `works.title_ja` 為可信基準，優先參照 works 表記錄，而非依賴 GPT 推斷。

---

## 2026-05-06 — 《第2報告》學術子事件未啟用且標題為 slot 識別符（DB 手動修正）

**Error**: 子事件 `97f11903`：`is_active=False`（未啟用）、`name_ja='第2報告'`（slot 識別符，非活動題目）。正確題目 `台湾の「雲南菜」から見る「孤軍」と東南アジア（仮題）` 與 `performer='福田真郷'` 存在於 `raw_description` 中卻未被提取。

**Fix**: `is_active=True`；`name_ja='台湾の「雲南菜」から見る「孤軍」と東南アジア（仮題）'`；`performer='福田真郷'`（手動從 raw_description 提取）。

**Lesson**: 學術 slot 子事件啟用時必須同步更新標題，不得保留 slot 識別符（「第2報告」等）；raw_description 往往含有正確題目，需人工提取，不可依賴 annotator 自動補全。

→ Added to SKILL.md §「Sub-event 啟用 — 標題同步規則」

---

## 2026-05-06 — 《大濛/霧のごとく》主辦誤填 + 導演被填入 performer（DB 手動修正）

**Error**: `organizer='台北駐日経済文化代表処 台湾文化センター'`（商業院線映畫不應有主辦方）；`performer='チェン・ユーシュン'`（導演被誤填至 performer 欄）；`director` 欄為 null；主演（`performers`）也缺漏。

**Fix**: `organizer=null`；`director='チェン・ユーシュン'`；`director_zh='陳玉勳'`；`director_en='Chen Yu-hsun'`；`performer=null`；`performers=['ケイトリン・ファン', 'ウィル・オー']`（主演）。`works` 表同步更新 `director` + `cast_summary`。

**Lesson**: 商業院線映畫 `organizer` 應為 `null`（院線不是主辦方）。**導演（director）≠ 表演者（performer）**：導演必須填入 `director` 欄位，主演填入 `performer` / `performers[]`，兩者嚴禁混填。works 表 `director` / `cast_summary` 需與 events 表同步更新。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — performer/director multilingual fields + performers[] array（commits 3822fb8, 65a50b9, 191d939）

**Change**: migration `054_performer_director_i18n.sql`（performer_zh/en, director_zh/en）+ migration `053_events_performers_array.sql`（performers text[]）+ base.py / database.py / web 多語言 helpers。

**Lesson**:
1. **performer_zh / performer_en 手動修正必須同時 upsert `field_corrections`**: 未鎖定時 re-annotation 會覆蓋修正值。
2. **UI helper `getEventPerformer(event, locale)` 必須使用**: 不可直接取 `event.performer`；locale 優先序：zh → `performer_zh`，en → `performer_en`，fallback → `performer`。
3. **performers[] 回填命令**：`scraper/backfill_location_prefectures.py` 模式可複製——批次讀 performer 欄位拆分成 array，寫入 performers 欄位。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — AI translation marker 語言不一致污染 performer_en（commit f07c170）

**Error**: `performer_en` / `director_en` 被填入 `（AI翻譯）`（中文後綴），正確應為 `(AI Translation)`（英語後綴）。DB event `bf783b90` 已被錯誤標記。

**Fix**: annotator.py 依欄位語言分別追加：`performer_zh` → `（AI翻譯）`；`performer_en` → `(AI Translation)`；`performer` / `name_ja` → `（AI翻訳）`（日語）。DB 手動修正 + `field_corrections` 鎖定。

**Lesson**: 多語言 AI 翻譯 marker 必須語言別分開指定；跨語言後綴靜默污染資料，肉眼不易察覺。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — note_creators thin content + blog source headline rewrite guard（commit b589fbb）

**Error**: `note_creators` 的 `raw_description` 通常只有截斷文字「続きをみる」——純介紹文章/觀影報導被誤收錄為活動資料，organizer 欄位被 GPT 幻想填充。

**Fix**: `note_creators` 加入 `_HEADLINE_REWRITE_SOURCES` frozenset；4 件 note_creators 事件設 `is_active=false` 或清空 organizer。

**Lesson**:
1. `_HEADLINE_REWRITE_SOURCES` 必須涵蓋所有部落格/創作平台來源（note_creators、google_news_rss、nhk_rss、prtimes、walkerplus）。
2. 純介紹文/觀影報告不是活動資料，應設 `is_active=false`，不依賴 annotator 過濾。

→ Added to SKILL.md §「Annotator — Headline Rewrite Sources & Blog Source Guard」

---

## 2026-05-06 — collection attribution 誤填 location_name（commit 47f8184）

**Error**: Annotator 將 `〇〇美術館蔵` 識別為 `location_name`（e.g. yebizo event `e37db12e` → `location_name='高雄市立美術館'`）。`〇〇蔵` 是作品所蔵機關標記，非活動場地。

**Fix**: SYSTEM_PROMPT 新增 COLLECTION ATTRIBUTION NOTE。DB 手動修正 `location_name='東京都写真美術館'`（Yebisu Garden Cinema）。固定場地 scraper 直接設定靜態 `location_name`。

**Lesson**: `〇〇美術館蔵` / `〇〇所蔵` 是作品借展標記，不是活動場地。固定場地的 scraper 應在程式碼層設靜態 `location_name`，避免依賴 GPT 判斷。

→ Added to SKILL.md §「Annotator — Collection Attribution Guard」

---

## 2026-05-06 — performer regex：`_MUKAE_RE` lookahead 缺漏 + `_PERFORMER_INTRO_RE` separator `+`→`*`（commits 6c2f1ab, fe8b273）

**Error 1**: `_MUKAE_RE` lookahead 只覆蓋 `をお迎え` / `を迎え`，未包含 `をゲストに迎え`，導致 `一青窈氏をゲストに迎え` 無法捕捉。

**Fix 1**: `_MUKAE_RE` 追加 `をゲストに迎え` pattern。

**Lesson 1**: `_MUKAE_RE` 必須完整覆蓋所有敬語形式。目前三種：`をお迎え` / `を迎え` / `をゲストに迎え`。新出現形式需立即補充。

**Error 2**: `_PERFORMER_INTRO_RE` separator 為 `+`（1個以上），導致 `絵本作家林廉恩氏`（角色詞直連人名，0個分隔符）無法匹配。

**Fix 2**: separator 從 `+` 改為 `*`（0個以上）。

**Lesson 2**: 日語角色詞與人名直連無分隔符是常見寫法，separator 必須為 `*`（0個以上）而非 `+`（1個以上）。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — Add StrangerScraper (Eigaland JSON API)

**Source**: Stranger cinema (東京墨田区) — stranger.jp  
**Strategy**: Loop 90-day window via `listByDomainAndDate`, filter `movieDetail.countries == 台湾`, one Event per movieId.  
**Key lesson**: `synopsis` field is base64-encoded HTML — always decode via `base64.b64decode → HTMLParser`. `openDate` in list API is the release date, not the screening date; use the query date as screening date.  
**Dry-run result**: 1 Taiwan movie found (「霧のごとく」 / 大濛, 2026-05-08〜05-14).

---

## 2026-05-06 — gnews start_date RSS snippet fallback + tokyoartbeat slug guard 擴大（commits 7df9f56, 1c0f69a）

### google_news_rss — RSS snippet 作為 start_date fallback（commit 1c0f69a）
- `_extract_start_date(article_text or description_plain, pub_date)`：article fetch 失敗時 `article_text=None`，`or description_plain` 使 RSS snippet（< 200 字）成為 fallback 輸入，GPT 從稀少文字猜出錯誤日期
- 修復：改為 `start_date = _extract_start_date(article_text, pub_date) if article_text else None`
- 教訓：RSS snippet 不可用作日期提取來源；article fetch 失敗時直接 `start_date = None`，由 annotator 的 `（記事配信日: YYYY-MM-DD）` 前綴確保年份正確

### tokyoartbeat — Contentful 佔位符 slug fallback 條件過嚴（commit 7df9f56）
- Contentful `scheduleStartsOn` 佔位符不只 `YYYY-01-01`，也有 `YYYY-01-15`（events `977da793`、`e7cf2a51`）
- `month == 1 and day == 1` 的 slug fallback 條件漏掉 day 2–31，造成 DB 日期錯誤
- 修復：條件改為 `month == 1`（Contentful 使用整個 1 月作佔位，不限 Jan 1）
- 教訓：審核所有 Contentful 系列展 scraper 的 slug fallback 條件，正確用 `start_date.month == 1`

---

### 2026-05-05 — auto_qa TAIWAN_VENUE_KEYWORDS 子字串假陽性：新北 ⊂ 新北島（commit 6b7174a）
- `'新北'` 是 `'新北島'`（大阪市住之江区）的子字串，`auto_qa_taiwan_venue` 對 event `371cf624`（GRAFFYHALL venue）反覆誤觸
- 每次 scraper upsert 更新 `updated_at` → dedup 重新觸發 → 即使 dismissed 仍再建立新報告
- 修復：移除裸字串 `'新北'`，保留更精確的 `'新北市'`；dismiss 當時 pending 的假陽性報告
- 教訓：台灣地名關鍵字需完整行政單位名稱（市/縣），禁用縮寫裸字串；新增前需 grep 日本地名清單

---
### 2026-05-05 — tokyoartbeat 三連 bug：slug 日期佔位符 / GPT organizer 幻覺 / event_form 缺失（commit a1e58a9）
- scheduleStartsOn=YYYY-01-01 是 Contentful 年度系列展佔位符，需從 slug 末尾提取實際日期
- scraper 未設 organizer → GPT 從 "works from our collection" 幻想出橫浜美術館
- 設 organizer=venue_name；raw_description 加 主催: 行作為 GPT 明確信號
- reviewed 事件的 event_form 永遠不被 annotator 修補，需 scraper 層設定

---
## 2026-05-05 — event 82a106db 手動修正：location_name 誤填 organizer + 子場地地址（note_creators）

### 問題
`note_creators` source 事件 `82a106db`：`location_name` 欄位被誤填為 organizer 名稱（`NPO法人埼玉県日台親善協会`），`organizer` = null，`location_address` 只有「埼玉県」（過度省略）。

### 修復
直接 DB 更新三欄位：
- `organizer` = `NPO法人埼玉県日台親善協会`
- `location_name` = `台湾カフェ「茶と菓」（四萬部寺内）`（子場地 + 親設施標記）
- `location_address` = `埼玉県秩父市栃谷418`（四萬部寺官網查得）

### 教訓
1. 子場地（寺内カフェ）的地址應使用**親設施地址**，`location_name` 格式建議 `「子場地」（親設施内）`。
2. `note_creators` 不走 annotator 主流程，此修正未寫入 `field_corrections`（影響有限）。
3. `organizer` 與 `location_name` 若值互調，辨別線索：法人後綴（協会・団体・財団）→ organizer；設施詞（カフェ・ホール・スペース）→ location_name。

---
## 2026-05-04 — hakusuisha 三連 bug：char limit / regex 欠缺 / self-prefix 干擾（commit `a0292a2`）

### 問題
hakusuisha.py 修正後もなお `location_name`、`business_hours`、`organizer` が null。三つの連鎖バグ。

### 根因
A. **char limit 4000**：nav/menu ノイズが予算を消費し、`■日時：`・`会場：`・`主催：` が切断点の外にある。
B. **`_KAIJO_RE`・`_SHUKAI_RE`・`_TIME_RE` 未定義**：会場・主催・時間の regex が存在しなかった。
C. **Self-prefix interference**：`raw_description` 先頭に `開催日時: YYYY年MM月DD日\n\n` を prepend した後で `_JITSU_RE.search(raw_description)` を実行すると、自己注入したプレフィックスの `開催日時:` にマッチし、`_TIME_RE` が本文の `HH:MM〜HH:MM` を永遠に見つけられなくなる。

### 修復（commit `a0292a2`）
- char limit 4000 → 8000（nav ノイズ消費分を確保）
- `_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE` を追加
- `business_hours` 抽出：`_JITSU_RE.search(raw_description)` → `_TIME_RE.search(full_description)` に変更（プレフィックス回避）

### 教訓
1. **Self-prefix interference**：`raw_description` に prefix を prepend する **前に** すべての regex 抽出を完了させること。または prefix にマッチしない専用 pattern を使用。
2. **char 予算検証**：detail-page scraper は HTMLParser 適用後の実際のテキスト長とキーワード位置を確認してから上限を設定すること。
3. **SKILL.md 参照**：「Self-injected Prefix Interference」セクションを参照。

---
## 2026-05-05 — tsutaya_portal.py 建立 + scraper_source_name 再度漏填（第 3 件）

### 問題
`tsutaya_portal.py` 新增、`main.py` 登錄、dry-run 確認後に task_complete を呼んだが、`research_sources.scraper_source_name` が NULL のまま残った。ユーザーが管理後台を確認して発見し、手動で補完。

### 根因
同じ問題が walkerplus（2026-05-05）でも発生済みにもかかわらず、Combined Post-Build Audit が存在しなかったため（SCRAPERS 専用 audit しかなかった）、`scraper_source_name` は肉眼チェックに依存していた。

### 修復
```python
sb.table('research_sources').update({
    'scraper_source_name': 'tsutaya_portal',
    'scraping_feasibility': 'easy',
    'status': 'implemented',
}).eq('id', 229).execute()
```

### 教訓 / 対策
1. **Combined Post-Build Audit を新設**（SKILL.md `## ⚡ Combined Post-Build Audit`）：main.py SCRAPERS + `research_sources.scraper_source_name` を同時検査するワンコマンド。
2. **agent.md Phase 3 Step 4 を差し替え**：SCRAPERS-only audit → Combined audit に更新。「🎉 ALL CLEAR が出るまで Phase 4 に進むな」と明記。
3. **agent.md Phase 5 pre-commit gate 更新**：新規ソース・バグ修正とも Combined audit を必須チェックボックスに追加。
4. **SKILL.md Promotion checklist 更新**：「auto_generate 限定」の表記を削除、すべての新規 scraper に適用と明記し、ステップ 5 を「Combined audit で ALL CLEAR 確認」に変更。

---
## 2026-05-05 — walkerplus.py 建立 + Promotion checklist 遺漏 research_sources 登錄

### 問題
walkerplus.py 新增後，Promotion checklist 的步驟 3/4（`research_sources` 登錄 + `scraper_source_name` 填寫）被遺漏。使用者提醒後才補做。
另外，`update_source.py` 不支援 `implemented` 狀態，需直接寫 DB。

### 根因
Promotion checklist（5 步驟）在 scraper 建立時沒有完整執行，只做了 main.py 登錄就結束了 session。

### 修復
直接 upsert `research_sources` 表：`status='implemented'`、`scraper_source_name='walkerplus'`、`scraping_feasibility='medium'`、`agent_category='event_listing'`。

### 教訓
1. **Promotion checklist 5 步驟必須在同一個 session/commit 全部完成**，不能分段做。
2. **`update_source.py` 只支援 `researched`/`not-viable`**；`implemented` 狀態需直接寫 DB（Supabase SDK upsert）。
3. walkerplus HTML 解析注意事項：`m-articleset--3` 有 3 個實例，必須用 `.m-detail__contents` 限定範圍取說明文；場地 link 順序是 [地域, 都道府縣, 市区町村, 施設名]，最後一個 link = `location_name`，中間 links 組合 = `location_address`；無關鍵字搜尋 API，只能用分類頁 + title 過濾。

---
## 2026-05-05 — note.com creator 追加 4 件（commit `d7da54a`）

### 問題
nittaisinzen、vectortw、taiwanryugaku、tcml_osaka を note.com クローラーに追加。

### 修復
- `note_creators.py` の `CREATOR_META` に 4 行追加
- `research_sources` の status を `implemented` に同時更新
- 事前に RSS dry-run（28 → 122 件）で件数確認

### 教訓
**note.com creator 追加は 2 ステップをセットで実行**：
1. `CREATOR_META` に `{slug: ..., category: ..., location: ...}` を 1 行追加
2. DB の `research_sources` を `status=implemented` に更新
どちらか片方だけでは `/admin/sources` の件数表示や次回 researcher.py の重複排除が狂う。

---
## 2026-05-04 — auto_research: pending ステータス候補が永久スキップ（commit `5d2585d`）

### 問題
migration 033 で `auto_research_status DEFAULT 'pending'` が設定されているが、
batch クエリが `NULL or error` しか条件に入れていなかった。
→ 新規候補 14 件が 2 日間まったく評価されなかった。

### 根因
`research_sources.auto_research_status` に DEFAULT 'pending' が設定されており、
INSERT 時に明示的な NULL 指定がなければ 'pending' が入る。
しかし `auto_research.py` の batch クエリが `.or_("auto_research_status.is.null,auto_research_status.eq.error")` のみ → 'pending' は永遠にマッチしない。

### 修復
`.or_()` に `auto_research_status.eq.pending` を追加。
DB で 14 件を NULL にリセット → 翌夜再評価。

### 教訓
**migration で DEFAULT 値を追加した場合、batch クエリの `NULL` 条件に DEFAULT 値も含めること**。
`DEFAULT 'pending'` を設定したなら `.or_("...is.null,...eq.pending")` の両方が必要。

---
## 2026-05-04 — researcher.py: 重複提案バグ 2 件（commit `7554002`）

### 問題
GPT が Shibuya Eggman、DjangoGirls Japan、Raycast Community 等を毎日再提案し続けた。

### 根因
1. `url_verified=False` のソース（URL 疎通確認失敗）が DB に保存されなかった → `known_urls` に含まれず、GPT に「未知」として渡り続けた
2. `known_urls` に渡す前に `[:30]` でリストを切り詰め → 186 件中 156 件が GPT に見えていなかった

### 修復
1. `url_verified=False` の初回提案を `status=not-viable` として DB 保存
2. `[:30]` 制限を削除（全件渡す）

### 教訓
- **GPT に渡す既知 URL リストは全件渡す**。ソート後の先頭 N 件に切り詰めると、後半の URL が毎日「新規候補」として再提案される
- **検証失敗ソースも DB に記録**。`url_verified=False` でも `not-viable` として保存しなければ、GPT は翌日も同じ URL を提案する

---
## 2026-05-04 — auto-scraper branch 長期放置によるマージ衝突（commit `7cedc68`）

### 問題
`feat/auto-scraper-artistcafe` と `main` の両方で `main.py` の同じ行（import + SCRAPERS リスト）に
別々の scraper が追加されており、マージ時に conflict。
HEAD（NoteCreatorsScraper）と branch（ArtistcafeScraper）を両方保持して手動解決。

### 根因
feature branch が数日放置され、その間 main 側に複数の scraper 追加コミットが積まれた。

### 教訓
**auto-scraper feature branch は生成後 24 時間以内にマージする**。
`SCRAPERS` リストは全員が同じ行/ブロックを編集する → 放置するほど conflict が深刻化。

---
## 2026-05-03 — 本屋B&B / 白水社 scraper プロモーション（commit `1c4f4f8`）

### 問題
`auto_scraper/runs/169`（白水社）、`170`（本屋B&B）の `generated.py` を `sources/` にプロモーション。
`meta.json` に `source_name` / `class_name` が含まれていなかったため、クラス名が不明だった。

### 根因
auto_scraper の runs ディレクトリに保存される `meta.json` は `source_name` を含まない場合がある。

### 修復
`auto_scraper/runs/{id}/generated.py` の先頭数行（`class XxxScraper(BaseScraper):`）を直接確認してクラス名を取得。
DB: id=169/170 → `status=implemented`, `auto_scraper_status=deployed-manually`

### 教訓
**`meta.json` に `source_name` / `class_name` がない場合は `generated.py` 先頭を直接確認する**。
`class (\w+Scraper)\(BaseScraper\):` パターンで 1 行目付近に必ず存在する。

---
## 2026-05-05 — location_address = location_name 全 scraper 稽核修正（commits `9d6e0fc`、`f7a8a71`）

### 問題
多個 scrapers 將 `location_address` 設為與 `location_name` 相同的值。受影響 scrapers：iwafu、jposa_ja、kokuchpro、koryu、prtimes、taioan_dokyokai、taiwan_festa、waseda_taiwan。

### 根因
Scrapers 取得 combined "location" 欄位時，直接複製到兩個欄位。iwafu 的 `場所：` 文字同時包含場地名稱和地址，但未分開解析。

### 修復
- **iwafu（commit `f7a8a71`）**：從 `場所：` 後方文字中用 `_ADDR_RE` 提取真實地址，venue name 和 address 分開設值
- **其他 7 個 scraper（commit `9d6e0fc`）**：逐一稽核，有地址可解析時拆分；無實際地址時 `location_address = None`

### 教訓
- **`location_address ≠ location_name` 是全 scraper 通用規則**——不只是 iwafu 特定
- Combined location 欄位必須解析：venue name → `location_name`，street address → `location_address`
- `_ai_or_existing()` 對非 null DB 值不覆寫，所以 scraper 端寫入錯誤值後 annotator 無法修正
- `auto_qa_address_is_venue_name` 偵測器會持續監控此 anti-pattern

---
## 2026-05-05 — enrich_location GPT 回傳 venue name 作為 address + sub-venue 規則（commit `628e3e7`）

### 問題
`enrich_location.py` GPT 從 `会場：仙六屋カフェ` 直接提取 `仙六屋カフェ` 作為 `location_address`，造成 `location_address == location_name`（失敗標誌）。

### 修復
1. SYSTEM_PROMPT Rule 6（identical → return null）：address == venue_name 時回傳 null。
2. SYSTEM_PROMPT Rule 7（子場地親設施地址）：子場地（如 `○○ビル2階`）需用親設施地址，不得用子場地名。
3. 程式碼 guard：寫入前 `if addr.strip() == venue: skip + log warning`（雙重保護）。
4. SELECT 加入 `location_name` 供 guard 使用。

### 教訓
- `address == venue_name` 是地址抽取失敗的確定標誌，不得寫入 DB。
- **雙層防護**：SYSTEM_PROMPT 規則（GPT 層）+ 程式碼 guard（程式碼層）——不能只靠 GPT 自律。
- Sub-Venue Parent Address Rule 需同步套用至 enrichment pipeline，不只 scraper 端。

---
## 2026-05-05 — Sub-event annotation with parent inheritance（commit `38f4f3a`）

### 問題
Scraper 直接建立的 sub-events（如 rightscube 各戲院子活動）有 `annotation_status='pending'`，但 annotator 只處理 GPT-generated sub-events。Scraper-created sub-events 缺少 category、description 等欄位。

### 修復
`annotator.py` 修改為也 pick up scraper-created sub-events（有 `parent_event_id` 且 `annotation_status='pending'`），從 parent event 繼承 category 和 context。

### 教訓
- Annotator 必須處理 **所有** pending sub-events，不只 GPT 產生的
- Sub-event annotation 從 parent 繼承 category 是合理預設——子活動通常與 parent 同分類

---

## 2026-05-05 — location_address = location_name 跨 9 scraper 大範圍擴散

### 問題
修復 iwafu.py 後，對全體 scraper 執行 grep 掃描，發現以下 8 個 scraper 有相同模式：
- `kokuchpro`：初始值 `location_address = card["venue_card"]`；detail page 無 address 時 `elif venue: address = venue`
- `taiwan_matsuri`：`elif location_name: location_address = location_name`
- `taioan_dokyokai`：`if location_name and not location_address: location_address = location_name`
- `koryu`：`_extract_location_address(body_text) or (venue if venue else None)`
- `taiwan_festa`、`prtimes`、`jposa_ja`：直接 `location_address=venue`
- `peatix`：fallback chain 末端無 guard，某些情況下 address 等於 name
- `waseda_taiwan`：`elif venue: location_address = venue`

DB 受影響：65 件 `location_address = location_name`（kokuchpro 43、peatix 13、google_news_rss 3、koryu 3 等）

### 根因
annotator `_ai_or_existing()` 保護：非 null 的 `location_address` 不被覆蓋。Scraper 寫入錯誤值後永久鎖定，auto_qa 持續報告 `auto_qa_address_is_venue_name` 但無法自動修復。

### 修復（commit `9d6e0fc`）
- 9 scraper：移除所有 venue-as-address fallback；找不到真實地址 → `None`
- peatix：Canonicalize 前加 guard
- DB：65 件 bulk-update

### 教訓
1. **每次修 location 相關 bug 後，必須 grep 全體 scraper**：`grep -rn 'location_address.*=.*venue\|location_address.*location_name' scraper/sources/`
2. **通用 guard 模式**（peatix 已採用，其他 scraper 可選）：
   ```python
   if location_address and location_address == location_name:
       location_address = None
   ```
3. **DB 掃描命令**（每次懷疑有 address=venue 問題時執行）：
   ```python
   r = sb.table('events').select('id,source_name,location_name,location_address').execute()
   same = [e for e in r.data if e['location_address'] and e['location_address'] == e['location_name']]
   from collections import Counter; print(Counter(e['source_name'] for e in same))
   ```

---

## 2026-05-04 — taiwan-filmake 全國上映子活動手動插入 + シアターセブン 上映資料更新

### taiwan-filmake 全國上映館子活動手動插入（source_name=rightscube）
- **內容**：以 `source_name="rightscube"` 手動插入 4 館子活動（札幌・神奈川・神戸・大阪），全部設 `parent_event_id = 995801cc`（K's cinema 系列父事件）
- **annotator**：執行完成，全部 `annotation_status = 'annotated'`
- **source_id 命名不一致問題**：手動插入前發現存量 DB 資料的 source_id 格式有誤（`taiwan-filmake_jack-betty` 而非 `taiwan-filmake_jackandbetty`），需先修正再插入，否則 scraper 後續 upsert 無法對應到正確記錄
- **教訓**：手動插入 DB 記錄前，必須先用 `--dry-run` 確認 scraper 實際會產生的 source_id 格式，格式須完全一致；`parent_event_id` 必須使用 UUID，不可使用 source_id 字串

### シアターセブン 上映資料更新
- **來源**：`https://www.theater-seven.com/mv/mv_s1030.html`（戲院詳細時刻表頁）
- **更新欄位**：`end_date = 2026-05-15`（之前為 NULL）；`business_hours` 補入每日詳細上映時間
- **教訓**：`end_date = NULL` 的戲院放映事件，通常在戲院個別詳情頁有完整場次期間，值得直接查詢並手動修正

---

## 2026-05-04 — performer 欄位 + Tier 1.5 annotator SYSTEM_PROMPT 擴展

### performer 欄位新增（commit `edd101e`）
- **Migration 038：** `events` 新增 `performer text` 欄位
- **base.py：** Event dataclass 新增 `performer: str | None = None`
- **Annotator SYSTEM_PROMPT：** 新增 PERFORMER EXTRACTION RULES——bare personal name，去除敬稱（氏、先生、さん 等），非人物事件回傳 null
- **Detail page：** Rich Results JSON-LD 注入 `performer` property，修復 4 個 Google Rich Results warnings

### Tier 1.5 annotator 新增 price / organizer_url / event_status 規則（commit `0d4a0de`）
- **SYSTEM_PROMPT 新增區塊：** PRICE PARSING RULES、ORGANIZER URL RULES、EVENT STATUS RULES
- **新增 validators：** `_validate_organizer_url`、`_validate_price_amount`、`_validate_price_currency`、`_validate_event_status`
- **Price parsing：** 支援 `1500円`、`¥1,500`、`無料`、`free` 等格式
- **教訓：** 新增 annotator schema 欄位時，必須同步加 SYSTEM_PROMPT 規則 + validator 函數 + migration

### hakusuisha 相對 URL 修正（commit `1b344f7`）
- **問題：** hakusuisha.py 的新聞連結使用相對路徑 `../news/xxx`，未正確解析為完整 URL
- **修正：** 改用 `urljoin(base_url, relative_path)` 解析相對 URL
- **教訓：** 所有 scraper 解析 `<a href>` 時，一律使用 `urljoin()` 處理，不假設 URL 為絕對路徑

### bookandbeer + hakusuisha auto-generated scrapers 上線（commit `db48ad3`）
- 兩個新 scraper 透過 auto_generate pipeline（Phase 2）產生並 promote
- bookandbeer：書店＋啤酒吧活動平台
- hakusuisha：白水社出版社新聞（需上述 urljoin 修正）

### P0/P1 admin correction protection 與 annotator 整合（commits `9eab3aa`、`c393e93`）
- **`_ai_or_existing()` 函數：** 在 re-annotation 中保護既有非 null 值（P0）和 `field_corrections` 表中的明確修正（P1）
- **`human_field_map` 載入：** annotator 啟動時查詢 `field_corrections` 表，建立 event_id → protected columns set
- **Few-shot context：** 過去修正紀錄注入 SYSTEM_PROMPT，讓 GPT 學習
- **irrelevant status bug fix：** `--fix-reviewed` 不再誤處理 `irrelevant` 事件
- **教訓：** annotator 的欄位保護必須有兩層——隱性（保留非 null）+ 明確（field_corrections 永久保護）

---

## 2026-05-04 — gguide_tv 電視節目被錯標為 movie（annotator.py VALID_CATEGORIES 未同步 types.ts）
- **問題**：事件 3d835d19（ジーンちゃん 台湾・台北 食旅 TV 節目）被標為 movie 而非 tv_program
- **根本原因**：types.ts 已新增 10 個分類（tv_program 等），但 annotator.py VALID_CATEGORIES 和 SYSTEM_PROMPT 從未同步；GPT 無法選用 tv_program，被迫改選 movie
- **修正**：VALID_CATEGORIES 同步 types.ts；SYSTEM_PROMPT 加 tv_program/drama/documentary 定義；_inject_keyword_categories 加 TV 廣播標記注入（放送:/ジャンル: → tv_program）；DB 直接修正 7 筆 gguide_tv 事件
- **教訓**：每次 types.ts 新增 Category → 必須同步更新 annotator.py VALID_CATEGORIES + SYSTEM_PROMPT 分類列表 + 分類定義（三處同步）。驗證命令見 SKILL.md § Three-Location Sync Rule。

---

## 2026-05-04 — annotator.py SYSTEM_PROMPT 新增「日本→台灣單向事件排除規則」
- **背景**：3 筆事件（IMAGINE JAPAN in 台湾 f40980a8、Perxona AI 73981453、CLIP STUDIO PAINT 928aa003）被收錄，但其性質是「日本產品/企業進入台灣市場」，與台日文化交流無關
- **修正**：
  - DB 直接 deactivate 3 筆事件（`is_active = false`）
  - annotator SYSTEM_PROMPT 新增 TAIWAN-VENUE EVENTS 區塊：明確 INCLUDE（共同組織/演出/交流/學習）vs EXCLUDE（日本向台灣銷售/贊助/產品發表）
  - auto_qa 新增 `auto_qa_taiwan_venue` 偵測器：flags 台灣地址事件供人工審核
- **教訓**：「Taiwan 在 location_address」不等同「Taiwan-relevant」。日本企業在台灣市場的商業行為不是台日文化活動，需 SYSTEM_PROMPT 明確區分。

---

## 2026-05-04 — rightscube.co.jp 新增爬蟲（台灣電影戲院放映）
- **設計決策**：
  - parent event = 全國上映概覽（source_id: `rightscube_{slug}`）
  - child events = 各戲院放映（source_id: `rightscube_{slug}_{venue_key}`），venue_key 從戲院 URL 推導（deterministic、穩定）
  - venue_key 規則：SNS（x.com/twitter/instagram）→ URL path component；CDN host（jimdofree/thebase）→ subdomain；一般網域 → domain minus TLD，lowercased，非英數字替換為 `-`
  - 靜態 HTML，不需 Playwright；`movie_title_lookup` 自動補充官方中英文片名
- **首次執行 DB 修復**：手動修正 source_id（`taiwan-filmake_jack-betty` → `jackandbetty`），建立 parent UUID，更新 4 筆 child 的 parent_event_id
- **HTML 結構 — Unicode Bold Math section 標題**：section 標題（如 `𝗧𝗛𝗘𝗔𝗧𝗘𝗥`）使用 Unicode Mathematical Bold Sans-Serif 字元（U+1D5D4+），無法直接與 ASCII 字串比對，必須以 `_normalize_bold_math()` 轉換後再做 section 識別
- **HTML 結構 — `<span><a>` 包裝下的 sibling 日期**：劇場連結結構為 `<span><a href="...">劇場名</a></span>｜5/17(日)・5/24(日)`，日期文字是 `a.parent.next_sibling`（`<span>` 的兄弟節點），而非 `a.next_sibling`（= None）
- **Homepage 必要性**：`/movies/` 目錄頁只列常規放映作品；特集上映系列（如 taiwan-filmake）只出現在 homepage → 爬蟲必須同時爬 homepage + /movies/ 目錄
- **教訓**：首次加入新爬蟲時，若已有存量 DB 資料（格式錯誤），必須執行一次性修正 script 補齊 parent_event_id；rightscube venue_key 推導規則是 production contract，勿修改

---

## 2026-05-04 — main.py pipeline 補齊 enrich 步驟 + ks_cinema DB 修正

### main.py 新增 enrich_movie_titles / enrich_person_names 呼叫
- **問題**：手動 `python main.py --source ks_cinema` 執行後，電影片名得到直譯（`循環的面影`）而非官方片名（`車頂上的玄天上帝`）。`enrich_movie_titles()` / `enrich_person_names()` 只在 CI 以獨立步驟執行，`main.py` 未呼叫。
- **修正**：`main.py` 新增 `from annotator import enrich_movie_titles, enrich_person_names`，在 `annotate_pending_events()` 之後呼叫。enrich 為 idempotent，CI 二次執行無影響。
- **教訓**：新增 enrichment 函數時，必須同時加到 `main.py`（手動）和 `scraper.yml`（CI）。Pipeline 完整順序：scrape → merger → annotate → enrich_movie_titles → enrich_person_names → IndexNow。

### ks_cinema 電影片名 DB 手動修正
- 6 筆事件 `name_zh` / `name_en` 直譯修正為官方片名（`車頂上的玄天上帝`、`阿嬤的夢中情人`、`導演你有病`）

### ks_cinema sub-event hierarchy 修正
- 3 筆 sub-event 設正確 `parent_event_id`；2 筆舊版 `_sub1` 記錄 deactivate

---

## 2026-05-03 — ks_cinema sub-event parent_event_id UUID 型別錯誤（commit `263e333`）
- **問題**：`ks_cinema.py` sub-event 中，`parent_event_id` 被設為 source_id 字串（`"ks_cinema_taiwan-filmake"`）而非 UUID，每次 upsert 出現 `invalid input syntax for type uuid` 錯誤，CI 連續 5 天失敗（`scraper_runs.success = false`）
- **根本原因**：直接將 source_id 字串賦值給 `parent_event_id` 欄位，未透過 `get_event_id_by_source()` 查詢 DB UUID
- **修正**：改用 `get_event_id_by_source(SOURCE_NAME, f"ks_cinema_{url_slug}")` 查詢 parent UUID，與 `taiwanshi.py` 模式相同；初次執行（parent 尚未寫入 DB）回傳 `None`
- **教訓**：`parent_event_id` 是 UUID 欄位，**絕不可**直接放 source_id 字串；必須透過 `get_event_id_by_source()` 查詢，回傳 `None` 時 sub-event 不設 parent

---

## 2026-05-02 — annotator.py 擴展 google_news_rss 薄內容 fetch 觸發（事件 2d77c2c4）
- **錯誤**：2d77c2c4（チップ・オデッセイ 熊本上映）raw_description 只有 80 chars 標題，但 start_date 非 null，Playwright fetch 被跳過，GPT 無法取得正確日期與地點
- **根本原因**：fetch 觸發條件只看 `not start_date`，不考慮 raw_description 是否足夠長
- **修正**：新增 `_gnews_needs_article_fetch()` helper — `not start_date` OR `len(raw_desc) < 400 chars`；`gnews_needs_fetch` 計數與 per-event trigger 都改用此函數
- **教訓**：薄內容偵測（koryu 模式）應同時套用到 annotator 的 fetch trigger — 「start_date 有值」不代表「描述足夠豐富」

---

## 2026-05-02 — fetch_ref_text() 提升至 BaseScraper 通用工具函數
- **背景**：koryu 後援指引文修正（32d66fc7）使用了 `_fetch_ref_text()`，但該函數只存在 koryu.py 中
- **重構**：將 `fetch_ref_text(ref_url, max_chars=3000)` 移至 `base.py`；koryu.py 改從 base import（移除 `requests`、`BeautifulSoup` import 及 `_REF_MAX_CHARS`、`_REF_HEADERS` 常數）
- **意義**：任何 scraper 遇到薄內容指引文時可直接呼叫，不需複製貼上實作
- **教訓**：通用爬蟲工具函數應放在 base.py，不應在各 scraper 中重複

---

## 2026-05-02 — koryu 後援指引文缺乏 ref URL 抓取（事件 32d66fc7）
- **錯誤**：後援公告「指引文」只有短短幾行 + 外部 URL。start_date=2025-12-15（文章刊登日），category 缺少 competition，location_name 誤填後援機構名
- **根本原因**：`_extract_event_date()` fallback 匹配到 DNN CMS 在 body 頂部渲染的文章發布日；scraper 未跟進外部 URL 抓取實際活動資訊；`開催日時:` 標籤誤導 GPT
- **修正**：koryu.py 新增薄內容偵測（< 600 chars + 外部 URL）→ 自動抓取 ref URL → 追加到 raw_description；pointer 文章改用 `記事投稿日:` 標籤
- **教訓**：若 body_text 薄且含外部 URL，scraper 必須主動抓取；`開催日時:` 標籤應只在確認為活動日期時使用

---

## 2026-05-02 — google_news_rss 年份推斷錯誤（事件 2d77c2c4）
- **錯誤**：標題「4月に熊本で上映」，GPT 推斷年份 2024，正確應為 2026
- **根本原因**：`raw_desc` 中無任何年份錨點；`_extract_start_date` 無法提取日期（只有「4月」無日期），GPT 無上下文依據
- **修正**：`google_news_rss.py` → `raw_desc` 嵌入 `（記事配信日: YYYY年MM月DD日）`
- **教訓**：任何無法從文章提取完整日期的 google_news_rss 事件都必須在 raw_desc 中包含 pub_date 作為年份錨點

## 2026-05-02 — ide_jetro date_prefix 省略 end_date → SINGLE-DAY RULE 誤觸（事件 86efda2a）
- **錯誤**：配信期間 2025-11-25〜2026-03-13，end_date 被設為 2025-11-25（等同 start_date）
- **根本原因**：`date_prefix` 只寫入 start_date；GPT 只看到一個日期 → 套用 SINGLE-DAY RULE；annotator fallback `or event.get("end_date")` 對**非 null 的錯誤值**無效
- **修正**：`ide_jetro.py` → 當 end_date ≠ start_date 時，date_prefix 改為 `開催日時: A日〜B日`
- **教訓**：date_prefix convention 必須包含 end_date。任何 scraper 知道 end_date 時，raw_description 的 `開催日時:` 行必須同時寫出 `開催日時: A日〜B日`

## 2026-05-02 — prtimes「6日間」duration 被 GPT SINGLE-DAY RULE 忽略（事件 e45d4022）
- **錯誤**：「盛りだくさんの6日間」活動 start_date=2026-02-25，end_date 應為 2026-03-02，但被設為 2026-02-25
- **根本原因**：prtimes.py 硬寫 `end_date=start_date`；SYSTEM_PROMPT 無「N日間」duration 規則，GPT 套用 SINGLE-DAY RULE
- **修正**：`annotator.py` SYSTEM_PROMPT 新增 Rule 10：「N日間」→ end_date = start_date + (N-1)天
- **教訓**：GPT 需要明確的 duration keyword 規則；scraper 本身應嘗試解析 end_date 而不是硬寫等於 start_date

---

## 2026-05-02 — koryu: 後援公告の `start_date` が文章刊登日に誤設定（Event `5104a6fe`）

- **問題**：Event `5104a6fe-ab70-4ec6-bf58-87232fb252a7`（source: `koryu`）の `start_date` が `2025-10-14`（文章刊登日）になっており、正しくは `2025-11-06` であるべき。
- **根本原因**：`koryu.or.jp` の「後援（こうえん）」公告ページには `日時:` ラベルがない。`_extract_event_date()` の Level 1 が失敗し、Level 2 fallback `re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日)', body_text)` が DNN CMS のページ先頭に描画された**文章刊登日**（`2025年10月14日`）にマッチした。真の活動日 `11月6日（木）` は年号なし (`MM月DD日（曜日）`) で書かれていたため `\d{4}年...` の正規表現に引っかからなかった。さらにこの誤った日付が `開催日時: 2025年10月14日` として `raw_description` の先頭に前置され、GPT がその日付を優先してしまった。
- **修正**：`_scrape_detail()` の Level 1 失敗後・pub_date fallback 前に中間層を追加。`r'(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝][）)]\s*に開催'` で prose パターンを検索し、年号は pub_date から推定。
- **教訓①**：後援公告（title が `（後援）` 始まり）には `日時:` ラベルがない。正しい日付は body 内の `MM月DD日（曜日）に開催` prose パターンにある。
- **教訓②**：`開催日時:` を `raw_description` の先頭に前置するのは annotator への強烈なシグナル。Scraper が誤日付を前置すると GPT は body 中の正確な日付を無視する。
- **教訓③**：日付 fallback 優先順序：`日時：` ラベル → `時間：` ラベル → DOW-qualified `MM月DD日（曜日）` → **`に開催` prose** → generic `YYYY年MM月DD日`（最後手段）。

---

## 2026-05-02 — CI に `--enrich-person-names` ステップを追加（commit `85fd475`）

- **変更内容**：`.github/workflows/scraper.yml` に `python annotator.py --enrich-person-names` ステップを追加（`--enrich-movie-titles` の直後）。
- **背景**：`person_name_lookup.py`（eiga.com + zh.wikipedia）と `annotator.py` の `enrich_person_names()` は実装済みだったが、CI から呼ばれていなかった。全 `category=movie` イベントの出演者・スタッフ名中英訳が毎日 CI で自動補完されるようになった。
- **CI フロー（更新後）**：`--fix-reviewed` → `--enrich-movie-titles` → `--enrich-person-names` → `summarize_run.py`
- **教訓**：新しい enrichment 関数を実装したら、CI（`scraper.yml`）への追加を忘れずに確認する。実装済みでも CI に追加しなければ本番で動かない。

---

## 2026-05-02 — eurospace.py に `lookup_movie_titles` を追加、SKILL.md 更新

- **変更内容**：`eurospace.py` に `from movie_title_lookup import lookup_movie_titles` を追加し、`_scrape_detail()` 内で `name_zh, name_en = lookup_movie_titles(title)` を呼び出し `Event()` に渡すよう修正。
- **背景**：`lookup_movie_titles` は eiga.com 経由で日本語映画タイトルの中/英訳を取得するモジュール。eurospace は唯一の未適用スクレイパーだった。
- **SKILL.md 更新（2点）**：
  1. `scraper-expert/SKILL.md`（canonical: `.github/skills/agents/scraper-expert/SKILL.md`）: `movie_title_lookup` セクションに導入状況テーブルを追加、`name_ja_locked` セクションを old path から canonical に移植。
  2. `sources/cinemart_shinjuku/SKILL.md`：Phase 2 週次スケジュール（`_parse_schedule_page`、`_normalize_title`）と `lookup_movie_titles` 統合説明を追加。
- **教訓**：cinema scraper 追加時は **必ず `lookup_movie_titles` を追加**。採用状況テーブルをメンテナンスする（`## movie_title_lookup` セクション）。

---

## 2026-05-02 — record_links JSONB bug（`json.dumps()` 雙重編碼）、name_ja_locked 機制設計

### record_links JSONB bug
- **問題**：`database.py` `_event_to_row()` 對 `record_links` 欄位呼叫 `json.dumps()`，Supabase JSONB 欄位收到字串而非陣列；前端 `.map()` crash → HTTP 500。
- **修復**：移除 `json.dumps()`，直接傳 Python `list`。
- **教訓**：Supabase Python SDK 的 JSONB 欄位（`jsonb`、`jsonb[]`）**必須傳 Python `list`/`dict`，不可用 `json.dumps()` 先序列化**。SDK 自動序列化 native types；手動序列化造成雙重編碼。

### name_ja_locked 機制設計
- **問題**：annotator GPT 覆寫了 `taiwanshi.py` 從 `題目:` 欄位精準抓取的學術論文標題，截斷副標題並加「に関する講演会」後綴。
- **修復**：設計並實作 `name_ja_locked` boolean flag（migration 034 / Event dataclass / database.py / annotator.py）。
- **`annotator.py` 行為**：`name_ja_locked=True` 時直接使用 DB 現有 `name_ja`（`name_ja = event.get("name_ja")`），翻譯/分類/其他欄位照常生成。
- **適用場景**：`题目:` 欄位、官方片名 PDF、其他精確結構化來源 → `name_ja_locked=True`。
- **禁用場景**：標題只有通用詞（如「イベント」）、或是自由文字推斷的場景 → 讓 annotator 改善。
- **DB fix 指令**（已誤標注時）：
  ```python
  events = sb.table('events').select('id,name_ja,raw_title').like('source_id','<source>_%_sub%').eq('is_active', True).execute().data
  for e in [x for x in events if x['name_ja'] != x['raw_title']]:
      sb.table('events').update({'name_ja': e['raw_title']}).eq('id', e['id']).execute()
  ```

---

## 2026-05-02 — google_news_rss: `_extract_original_url()` 全回 None，因 RSS description href 也是 Google News URL

**問題：** `_extract_original_url(description_html)` 對所有事件返回 `None`，導致 `source_url` 停留在 Google News URL、`raw_description` 無法取得原始文章內容。

**根本原因：** 假設 RSS `<description>` 的 `<a href>` 指向真實文章 URL；實際上該 href 也是 `news.google.com/rss/articles/CBMi...?oc=5` 格式（另一層 Google News URL），無法用「非 google.com」過濾找到原始文章。base64 解碼 path 也不可行（是加密 protobuf，非單純 base64）；requests 直接 GET 亦無效（JavaScript redirect，requests 停在 400）。

**修復：** 移除 `_extract_original_url()`，改用 `googlenewsdecoder` PyPI 套件（`new_decoderv1`）對 RSS `<link>` URL 直接解碼。新增 `_decode_gnews_url(gnews_url)` 函數（帶 `interval=0`，自行控制 `_DECODE_SLEEP = 1.0` 間隔）。`requirements.txt` 新增 `googlenewsdecoder>=0.1.6`。

**教訓：** Google News RSS URL 唯一可靠解碼方案是 `googlenewsdecoder.new_decoderv1`。base64 解碼與 requests 繞過均無效。`raw_description` 應包含 500–4000 字元原始文章內容，供 annotator 標注 location/date。

---

## 2026-05-02 — taiwanshi: 「第N報告」子活動未解析；database.py 缺 `get_event_id_by_source` helper

**問題：** taiwanshi 台湾史研究会定例研究会的「第N報告」（sub-events）未存入 DB；設定 `parent_event_id` 時缺少按 `source_name + source_id` 查詢父事件 UUID 的方法。

**根本原因：** 原 scraper 只抓頂層活動，未解析 sub-events 結構（時間、題目、報告者、評論者）；`database.py` 無對應的 UUID lookup helper。

**修復：** `sources/taiwanshi.py` 新增 `_parse_reports()` 函數解析「第N報告」結構；`database.py` 新增 `get_event_id_by_source(source_name, source_id) -> str | None` helper，供 scraper 查詢父事件 UUID 後再設定 `parent_event_id`。

**教訓：** 建立 sub-events 時，必須透過 `get_event_id_by_source(source_name, source_id)` 查詢父事件 UUID 再設定 `parent_event_id`，不可在 scraper 內假設 UUID 或依賴執行順序。

---

## 2026-05-02 — merger Pass 1/3 相同 SOURCE_PRIORITY 時遍歷順序決定 primary（資料空洞）

**問題：** 兩個相同 `SOURCE_PRIORITY` 的來源配對時，merger 用「先遇到的」當 primary，可能選到 `start_date`、`location_address` 等欄位皆為 NULL 的事件。

**根本原因：** Pass 1 的 priority 比較使用 `<=`（而非嚴格 `<`），導致 priority 相同時無差別選第一個；沒有豐富度評估機制。

**修復：** 新增 `_richness_score()` helper（0–10 分）：`official_url`(+1) + `start_date`(+1) + `end_date`(+1) + `location_address`(+1) + `location_name`(+1) + `raw_description` 每 200 字 +1（上限 5）。Pass 1/3 的 priority 比較改為嚴格 `<` / `>`；priority 相同時比 richness score，高分者為 primary。`location_address` 同步加入 SELECT 查詢欄位。

**同步新建：** `docs/MERGER_WORKFLOW.md`——完整記錄四個 Pass 規則、SOURCE_PRIORITY 表、`_richness_score` 評分、Primary 選擇決策流程、幂等性保證、手動指令、CI 排程、FAQ。

**教訓：** SOURCE_PRIORITY 相同的兩個來源配對時，**一定要用豐富度判斷 primary**，不能依賴遍歷順序。新增來源若屬官方主辦方，應加入 SOURCE_PRIORITY 並設定低數值（高優先）。

---

## 2026-05-02 — google_news_rss 同活動多文章造成重複，merger Pass 1 跳過同來源

**問題：** DB 中出現多筆完全相同的 `google_news_rss` 活動（如「台湾屋台祭in海老名2026」3筆重複）。

**根本原因：** Google News RSS 對同一活動可能透過不同 query 或不同天產生多篇文章。每篇文章的 `source_id` 是 URL 的 MD5 hash，互不相同，in-scraper `dedup_events` 用 `raw_title`（帶 `- Source Name` 後綴）比對也無法命中。`merger.py` Pass 1 明確跳過同 `source_name` 的配對，故重複全部入庫。

**修復：**
1. `merger.py` — 新增 Pass 0（在 Pass 1 之前執行）：查詢所有 active `google_news_rss` 事件（含 `start_date=NULL`），對 `name_ja` 做相似度比對（≥ 0.85），超過門檻則合併；Primary 選擇規則：non-null `start_date` 優先，相同則選 `raw_description` 較長者；print 改為 `Pass 0+1+2+3`。
2. `sources/google_news_rss.py` — 新增 `_clean_title_for_dedup()`：strip RSS 標題後綴 `- Source Name` / `｜Source Name`；`Event.name_ja` 改用清洗後標題，`raw_title` 保留原始完整標題。
3. 手動合併 3 筆「台湾屋台祭in海老名2026」重複（Primary: f9709bb1，Secondary: e823ac41, ff4d9b6d deactivated；Primary `start_date` reset to NULL 等待 annotator 重新標注）。

**教訓：** debug `google_news_rss` 重複事件時，**先確認 merger.py Pass 0 log** 是否偵測到同名事件。annotator 可能用文章發布日（pubDate）填入 `start_date`——合併後若 `start_date` 疑似是文章發布日，應 reset to NULL 並重跑 annotator。

---

## 2026-05-02 — Promotion 後 `scraper_source_name` 缺失，後台來源關聯斷裂

**問題：** auto_generate 完成、PR merge 後，`/admin/sources` 顯示 0 筆活動且無法觸發 Run Scraper。

**根本原因：** `research_sources.scraper_source_name` 為 NULL。後台 API 靠此欄位 JOIN `scraper_runs`；auto_generate pipeline 只產生 scraper 檔案，不自動填此欄位。

**修復：** Supabase UPDATE — id=151 → `taiwan_festa`、id=150 → `tiff_jp`。

**教訓：** Promotion 最後一步必須手動填寫 `scraper_source_name`。已加入 SKILL.md § BaseScraper Contract 的 Promotion checklist。

---

## 2026-05-02 — taiwan_festa: auto_generate 失敗（Playwright 403），改用 requests + BeautifulSoup

**問題：** auto_generate 對 `taiwanfesta.com`（WordPress/UIkit 主題）失敗——Playwright headless 返回 403，`card_selector .uk-card-default` 在渲染後 DOM 中找不到。

**根本原因：** 部分 WordPress/UIkit 網站對 headless browser 返回 403；靜態 HTML 可直接取得，不需要 JS 渲染。

**修復：** 改用 `requests + BeautifulSoup` 手動撰寫 scraper（`scraper/sources/taiwan_festa.py`）。

**教訓：** auto_generate sandbox 顯示 0 events 時，立即嘗試 `requests.get()` 靜態抓取驗證。若靜態 HTML 完整，直接手寫 scraper，不必等 Playwright 重試。此類網站 `requests.Session` 須掛載 Retry adapter（參見 SKILL.md §requests.Session retry）。

---

## 2026-05-02 — TIFF: auto_generate 成功，promotion 後需修正年度 URL 與 Taiwan 過濾

**問題 1（年度 URL）：** auto_generate 產生 `BASE_URL = "https://2026.tiff-jp.net"`，每年需手動更新。

**修復 1：** 加入動態年份解析——follow `www.tiff-jp.net` redirect 取得 Location header，提取年份；fallback `datetime.now().year`。

**問題 2（Taiwan 過濾缺失）：** keyword 搜尋結果可能混入非台灣電影。

**修復 2：** 加入 `_TAIWAN_KW` client-side regex 過濾。

**教訓：** 對「每年換子網域」型網站（如 `YYYY.tiff-jp.net`），promotion 時必須將寫死年份改為動態解析。Architect/Scraper Expert 在 planning 時應標記此型 URL 為「需年度更新 review」。

---

## 2026-05-02 — auto_generate eligibility check 未接受 `recommended` 狀態

**問題：** `generate.py` 的 `_check_eligibility()` 只接受 `status == 'researched'`，但 recommended 來源為 `status = 'recommended'`，執行 `--source-id` 時直接 abort。

**修復：** `scraper/auto_scraper/generate.py` 改為接受 `('researched', 'recommended')` 兩種狀態。

**教訓：** `recommended` 是可信度最高的狀態，本應是 auto_generate 的優先對象。eligibility check 從設計時就應涵蓋此狀態。

---

## 2026-05-01 — 批次依 end_date 誤關 342 筆事件（is_active 語意誤用）

**問題：** 在 terminal 執行臨時批次腳本，將所有 `end_date < today AND is_active = True` 的事件設為 `is_active = False`。首頁大量歷史事件瞬間消失，用戶立即察覺，需緊急復原。

**根本原因：** `is_active` 表示「管理員是否主動隱藏」，與活動是否過期無關。過期事件應保持 `is_active = True`，由前端 `FilterBar` 的「顯示已結束活動」選項控制能見度。

**修正：** 反向 patch — 將所有 `end_date < today AND is_active = False` 的事件復原為 `is_active = True`，共復原 342 筆。

**教訓：** `is_active` 的合法寫入來源只有兩個：① 管理員在 admin 頁面手動關閉；② `merger.py` 合併重複事件。任何其他批次 UPDATE 都是錯誤。→ [Added to SKILL.md: DB Operations Safety Rules]

---

## 2026-05-01 — 映画 COMING SOON 期間的 start_date 錯誤（ナギ日記）

**問題：** 映画《ナギ日記》在 starsands.com 尚未公布正式上映日時，爬蟲在 4 月初抓到 `start_date = 2026-05-01`（應為 `2026-09-25`）。

**根本原因：** 電影類活動在正式公布上映日期前，官網可能只有「COMING SOON」或新聞稿，此時頁面上的任何日期都可能是「製作公告日」而非「上映日」。

**修正：** 直接 DB patch — `start_date → 2026-09-25`，`end_date = null`。

**教訓：** 電影類活動應優先從 `raw_description` 中查找「○月○日（曜日）公開」等明確上映格式；若找不到，設 `start_date = null` 而非使用頁面上模糊的日期。

---

## 2026-05-01 — gguide_tv business_hours fallback 到 detail page

**問題：** list page `schedule_raw` 為單行格式（只有開始時間，無結束時間），`end_time_str = None`，即使 detail page 已有完整播出時段，`business_hours` 仍為 `None`。

**修正：** 當 `end_time_str = None` 時，fallback 到 detail page 文字，用 `r"(\d{1,2}:\d{2})\s*\n[-−]\s*\n(\d{1,2}:\d{2})"` 提取結束時間。

**教訓：** list page 欄位不完整時，優先 fallback 到 detail page，而非直接設 `None`。此 pattern 適用於任何「list page 資訊精簡、detail page 資訊完整」的爬蟲。

---

## 2026-05-01 — gguide_tv schedule 文字提取須加 separator="\n"（commit `a895e07`）

**問題：** `ps[2].get_text(strip=True)` 把多行 HTML 子節點合併成 `"23:450:00 歌謡ポップス"`（無換行），導致 `_parse_schedule()` 無法識別多行格式，`business_hours = None`。

**修正：** 改為 `ps[2].get_text(separator="\n", strip=True)` — 加入 `separator` 後產生 `"23:45\n-\n0:00 歌謡ポップス"` 格式，多行解析正確。

**教訓：** BeautifulSoup `get_text()` 預設無 separator，多個子元素會直接串接。**當 HTML 結構中各欄位分別位於不同子元素時，必須加 `separator="\n"` 才能保留欄位邊界。**

---

## 2026-05-01 | gguide_tv channel name 改版（location_name 改為實際頻道名稱）

**問題：** `location_name="電視頻道"` 是虛設標籤，缺乏資訊量；23 件事件無法顯示正確頻道名稱。web 地址欄以 `event.location_name === "電視頻道"` 作判斷，`location_name` 語意一旦改變邏輯就失效。

**修正：** `gguide_tv.py` 改為 `location_name=channel`（如「歌謡ポップス」）。`web/app/[locale]/events/[id]/page.tsx` 地址欄判斷由 `event.location_name === "電視頻道"` 改為 `event.source_name === "gguide_tv"`。DB backfill 23 件事件。

**教訓：** UI 渲染的條件判斷應依賴 `source_name`（結構性欄位、永遠不變），而非 `location_name`（可變內容欄位）。依賴內容欄位做邏輯判斷，欄位修正後必須同步更新 UI 邏輯，容易出現 sync 問題。

---

## 2026-05-01 | i18n 標籤統一（event vs admin namespace 必須同步修改）

**問題：** `event.location`（場地・頻道）和 `event.address`（地點）標籤在前台詳情頁（`event` namespace）與後台管理頁（`admin` namespace）使用不同 JSON key，修改其中一個不會自動同步到另一個。

**修正：**
- `event.location`：zh「場地・頻道」/ en「Venue / Channel」/ ja「会場・チャンネル」
- `event.address` + `admin.address`：zh「地點」/ en「Location」/ ja「場所」

**教訓：** `event` namespace（前台）與 `admin` namespace（後台）是獨立的 JSON 命名空間。任何 UI 標籤修改必須同時更新三個 `messages/*.json` 的**兩個** namespace。

---

## 2026-05-01 | gguide_tv business_hours 修復（end_time fallback from detail page）

**根本原因：** list 頁的 `ps[2].get_text(strip=True)` 把 `<br>` 換行壓扁，多行格式 `23:45\n-\n0:00` 變成 `23:45-0:00`，導致 `\n-\n` regex 無法匹配，`end_time_str=None`，`business_hours` 無法計算。

**修復：** 當 `end_time_str=None` 時，fallback 從 `detail_text` 用 `r"(\d{1,2}:\d{2})\n-\n(\d{1,2}:\d{2})"` 補抓 end_time。DB backfill 從 `start_date`/`end_date` 反推 `business_hours`（格式 `21:00〜22:00`）。

**教訓：** BeautifulSoup `get_text(strip=True)` 會吃掉 `<br>` 結構，有跨行結構的欄位應改用 `get_text(separator="\n")` 保留換行。gguide_tv 的 `end_time` 在 detail 頁，不在 list 頁的 `schedule_raw`。

---

## 2026-05-01 | go_taiwan + transit_store スクレイパー実装

**go_taiwan (`scraper/sources/go_taiwan.py`):**
- サイト: 台湾観光庁 Japan 公式 (go-taiwan.net/ikutabi) — WordPress 静的 HTML、REST API 401 blocked
- **90-day pre-filter**: `<time datetime>` をリストページで先読みし 90 日超の記事をスキップ。フェッチ数 220 → 6
- **三段階フィルター**: Stage 2（`TAIWAN_VENUE_KW`）を Stage 3（`JAPAN_LOCATION_KW`）より**必ず先に**適用。逆順にすると台湾開催イベントが日本企業名テキストで誤通過する（野柳石光事例）
- **日付抽出優先順位**: `日時：` ラベル → 曜日注釈付き範囲 → ラベル付き単日 → 曜日注釈付き単日 → 平文範囲 → 本文最初の平文日付（公開日を拾うリスク大 — 最終手段）
- Issue #35 作成、DB status → recommended

**transit_store (`scraper/sources/transit_store.py`):**
- Shopify JSON API: `/collections/event/products.json?limit=20&page={n}`
- 台湾キーワードを `title` + `body_html` の両方でフィルタリング
- 日付: `body_html` 内の `日程[：:][^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日` 正規表現
- Issue #34 作成、DB status → recommended

**DB 手動挿入ワークフロー:** `update_source.py --create-issue` は UPDATE 専用（INSERT しない）。`researcher.py` 経由でない手動発見ソースは先に `research_sources` に INSERT してから実行すること。`notes` カラムは存在せず、`reason` に記載する。

---

## 2026-05-01 | merger.yml 加排程 3× daily + annotator 步驟

**修改：** `.github/workflows/merger.yml` 新增 3 個 cron（`01:00 / 09:00 / 16:00 UTC`，對應 JST 10:00 / 18:00 / 01:00），每次 merger 跑完後接著執行 `python annotator.py` 和 `python annotator.py --fix-reviewed`。

**原因：** 原本 merger 只能手動觸發，合併後的事件要等到隔天 CI 才會被重新標註。

**教訓：** merger 結束後必須立刻重新標註，避免合併事件以 `pending` 狀態長時間滯留。一天三次 merger 確保跨來源重複在數小時內被處理。

---

## 2026-05-01 | merger.py Pass 3 — 孤兒 sub-event 清理

**修改：** `merger.py` 新增 Pass 3：掃描所有 `is_active=True` 但 `parent is_active=False` 的 sub-events（孤兒）。
邏輯：
1. 找出孤兒 sub（parent 已被 deactivate）
2. 查找 primary parent（via `secondary_source_urls` contains 查詢）
3. 若 primary parent 下有 name_ja 相似度 ≥85% + 相同 start_date 的 sub → 合併（按 SOURCE_PRIORITY）
4. 若找不到對應 sub → 直接 deactivate 孤兒

**原因：** Pass 1/2 合併後，舊 parent 被 deactivate，但其 sub-events 仍為 active，成為孤兒顯示在前台。

**教訓：** Pass 3 必須在 Pass 1/2 之後執行（確保 parent 合併結果已就緒）。Print 訊息格式：`Done: N pair(s)/orphan(s) merged (Pass 1+2+3).`

→ 已更新 `SKILL.md` § merger.py — Pass 3

---

## 2026-05-01 | Node.js 24 opt-in（scraper.yml + merger.yml）

**修改：** `scraper.yml` 和 `merger.yml` top-level 加入 `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`。

**原因：** `actions/checkout@v4`、`actions/setup-python@v5` 在 Node.js 20 下出現 deprecation warning；GitHub 將於 2025-06-02 強制遷移。

**教訓：** 任何使用 `actions/checkout@v4` 或 `actions/setup-python@v5` 的 workflow 都需在 top-level `env:` 加入此 opt-in 環境變數，提前消除 warning。

→ 已更新 engineer SKILL.md § GitHub Actions Workflow Rules

---

## 2026-05-01 | merger.yml 新建 + scraper.yml 插入 merger 步驟

**修改：**
- 新建 `.github/workflows/merger.yml`：支援 `workflow_dispatch` 手動觸發，只跑 `python merger.py`
- `scraper.yml`：在 `main.py` 後、`annotator.py --fix-reviewed` 前插入 "Run merger" 步驟

**原因：** 每日 CI 跑完爬蟲後缺少自動去重步驟，跨來源重複事件要等手動執行或下次 CI 才被清理。

**教訓：** 每日爬蟲管道的步驟順序應為：`main.py` → `merger.py` → `annotator.py` → `annotator.py --fix-reviewed`。

---

## 2026-05-01 — annotator NAME WRITING RULES 新增

**Error:** Annotator produced self-referential titles like「東京オフ会」and「神戸オフ会」— users could not understand what the events were without reading the description.

**Fix:** Added NAME WRITING RULES to the `annotator.py` system prompt. Generic terms (`オフ会`, `ライブ`, `上映会`, `展示`, `イベント`, `セミナー`, `勉強会`) must not appear alone in a title; they must be prefixed with the organiser, topic, or series context. Two events were re-annotated: 「東京オフ会」→「台湾系YouTuber copochanの東京オフ会」and「神戸オフ会」→「台湾系YouTuber copochanの神戸オフ会」.

**Lesson:** Titles must be self-contained. A reader who sees only the title must understand the event without reading the description. → Added to `SKILL.md` § Annotator NAME WRITING RULES

---

## 2026-05-01 — google_news_rss Yahoo 集約過濾 & _STALE_DAYS 短縮

**Error:** (1) Yahoo!ニュース aggregation articles were included — they are duplicates of the source article and their redirect URLs expire faster. (2) `_STALE_DAYS = 60` was too long; Google News redirect URLs expire in ~2–3 weeks, so 60-day-old entries were always dead links. (3) Query `"台湾映画 上映"` returned pure news articles about release dates that are not event listings.

**Fix:** Added `_is_yahoo_aggregation()` to skip titles ending with `「- Yahoo!ニュース」`. Changed `_STALE_DAYS` from 60 → 21. Changed query from `"台湾映画 上映"` → `"台湾映画 上映会"` to target event listings specifically.

**Lesson:** Google News redirect URLs (`news.google.com/rss/articles/...`) CANNOT be resolved server-side — `requests` returns HTTP 400 and Playwright is blocked by bot detection. They work correctly in real browsers. Do not attempt server-side redirect resolution; do not exclude the entire scraper. Use `_STALE_DAYS = 21` for Google News RSS. → Added to `SKILL.md` § google_news_rss-specific

---

## 2026-05-01 — migrations/ 資料夾污染 (非 migration 檔案混入)

**Error:** A previous agent placed test/documentation files (`027_smoke_test.sql`, `027_VALIDATION.md`, `027_VERIFICATION_REPORT.md`) inside `supabase/migrations/` with sequence-number prefixes, polluting the migration history.

**Fix:** Deleted all three non-migration files from `supabase/migrations/`.

**Lesson:** `supabase/migrations/` must contain ONLY real SQL migration files (`.sql` format, sequential numbered). Test scripts, validation reports, and documentation files must NEVER be placed in this directory. → No SKILL.md update needed (see `database.instructions.md`).

---

## 2026-05-01 — sub-events missing scraped_at (クロール日時 = —)

**Error:** `annotator.py` builds `sub_row` without a `scraped_at` field. All 128 existing sub-events had `scraped_at = NULL`, causing the admin table `クロール日時` column to display `—` for every sub-event.

**Fix:**
1. Added `"scraped_at": event.get("scraped_at")` to `sub_row` in `annotator.py` — sub-events now inherit the parent's scrape timestamp at creation time.
2. Backfilled all 128 existing sub-events: 34 inherited parent's `scraped_at`; 94 used parent's `created_at` as fallback (parent also predated migration 018b).

**Lesson:** When `annotator.py` builds a sub-event row, it must explicitly carry over any field from the parent that is meaningful for operations/admin — `scraped_at` is a key example. Fields omitted from `sub_row` default to `NULL` and are not inherited automatically.

→ Added to `SKILL.md` § Annotator sub-event row fields

---

## 2026-04-30 — 天燈體驗 [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food
**After (corrected):** workshop
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 海濱派對 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


## 2026-04-30 — 橫濱國際電影節 特拉維斯·佩恩舞蹈比賽 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


## 2026-04-30 — 親愛的陌生人／ディア・ストレンジャー（字幕版） [gguide_tv] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** tv_program, movie
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 圍棋焦點 女子世界第一是？世界圍棋女子最強戰2026 [gguide_tv] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** competition
**After (corrected):** tv_program, competition
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 來自台灣的考察團參加國際研討會 [google_news_rss] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** academic, taiwan_japan, lecture
**After (corrected):** report, taiwan_japan, healthcare
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — Beginning ZERO [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** performing_arts, lifestyle_food
**After (corrected):** performing_arts
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 台灣博覽會 [maruhiro] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:台灣園遊會, fieldEdit:name:en:Taiwan Fair, fieldEdit:name:ja:台湾フェア
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-30 — 同步星座：藝術中的跨界視角 [tokyoartbeat] — user report confirmed
**Report types:** wrongDetails, wrongCategory, fieldEdit:name:zh:共時星座：藝術中的跨界視角, fieldEdit:name:en:Synchronic Constellation: Cross-boundary Perspectives in Art, fieldEdit:name:ja:シンクロニック・コンステレーション：アートにおける境界を越えた視点
**Before (AI category):** senses, art
**After (corrected):** movie, literature, art, senses, history, taiwan_japan
**Wrong fields:** name
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 台東祭 [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** nature, lifestyle_food, indigenous
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 精巡（しょうじん）料理～巡迴、調整。台灣藥膳健康講座～ [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan, lecture
**After (corrected):** senses, lifestyle_food, lecture
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-30 — 私人租借 [moonromantic] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


## 2026-04-30 — 橫濱市中高生管樂團電影音樂節 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


## 2026-04-30 — 造山者－世紀的賭注 [google_news_rss] — user report confirmed
**Report types:** wrongDetails, fieldEdit:start_date:zh:2026-03-17T00:00:00+00:00, fieldEdit:start_date:en:2026-03-17T00:00:00+00:00, fieldEdit:start_date:ja:2026-03-17T00:00:00+00:00, fieldEdit:end_date:zh:2026-03-17T00:00:00+00:00, fieldEdit:end_date:en:2026-03-17T00:00:00+00:00, fieldEdit:end_date:ja:2026-03-17T00:00:00+00:00
**Wrong fields:** start_date, end_date
**⚠ Scraper fix needed:** Fields [start_date, end_date] can only be fixed in the scraper source, not by re-annotation.
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-30 — 《晴天時空豆撒20周年紀念》三浦透子×近藤康平 [eplus] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


---
## 2026-04-29 — Peatix 三層爬取架構固化（daily review）
**新增/修改：**
- `## Peatix-specific` 新增 Three-layer organizer architecture 表格（Layer 1 keyword / Layer 2 hardcode / Layer 3 DB-driven）
- 記錄 `_load_db_organizers()` 的 `agent_category='peatix_organizer'` 查詢條件
- 記錄「Never remove Layer 2」規則（DB status 意外變更時的 backup）
**來源：** daily-skills-review（Step 4 建議）

## 2026-04-29 — iwafu docstring 誤記（東京限定と表記されていた全国スクレイパー）[iwafu]
**Error**: `iwafu.py` モジュール docstring に「Filter to events where prefecture == 東京」と記載されていたが、実コードは `cards = all_cards`（フィルターなし）で全国カバー済み。
DB candidate id=97（iwafu EN `/en/events/`）も「福岡拡張が必要」と判断されていたが、JP スクレイパーで既に全国カバーされているため重複。
**Fix**: docstring を「No prefecture filter — all regions included」に修正。DB id=97 を not-viable に更新（理由付き）。
**Lesson**: 「機能を追加する前にコードを読む」。scraper の実際の挙動（cards フィルター有無）を確認してから「拡張が必要か」を判断する。docstring とコードが乖離するリスクを防ぐため、prefecture フィルターの有無は SKILL.md に明記しておく。

---

## 2026-04-29 — SCRAPERS リスト未登録スクレイパー 8 件発見（pipeline 監査）[main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper の 8 件が `sources/*.py` として存在するが `SCRAPERS` リストに未登録のまま本番稼働していた。DB ステータスは `implemented` だったが CI では一度も実行されていなかった。
**Discovery**: `research_sources` DB の `implemented` 件数 vs `sources/` ファイル一覧と `SCRAPERS` リストの三者クロスチェックで発見。
**Fix**: `scraper/main.py` に 8 件の import と `SCRAPERS` 追記。全件 dry-run で動作確認後にコミット。
**Lesson**: DB `implemented`、ファイル存在、`SCRAPERS` 登録の三者は独立して管理される。新規スクレイパー作成時は必ず同一コミットで `SCRAPERS` に追加する。定期監査コマンド:
```bash
python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
"
```

---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:この映画は香港の食堂を舞台に、社会の変化に直面する人々の姿を描いており、台湾、香港、フランスの共同制作です。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-28 — 赤色的線 輪迴的秘密 [shin_bungeiza] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影是台灣製作，反映了台灣的文化和故事。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-29 — 8 Unregistered Scrapers Found in SCRAPERS List Gap [main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper all had `.py` source files but were NOT included in the `SCRAPERS = [...]` list in `scraper/main.py`. This caused them to be skipped by the daily CI run despite being ready for production.

**Discovery**: Audit found via manual inspection and confirmed via `python main.py --dry-run`.

**Fix**: Added all 8 to `SCRAPERS` list and validated dry-run output:
- CineMarineScraper: 1 event (横浜シネマリン)
- EsliteSpectrumScraper: 2 events (誠品生活日本橋)
- MoonRomanticScraper: 1 event (Moon Romantic)
- MorcAsagayaScraper: 0 events (正常 — no Taiwan films today)
- ShinBungeizaScraper: 1 event (新文芸坐)
- SsffScraper: 6 events (SSFF)
- TaiwanFaasaiScraper: 1 event (台湾發祭)
- TokyoFilmexScraper: 0 events (正常 — festival in October)

**Lesson**: The sources directory and `SCRAPERS` list can drift silently. Implement monthly audit: `comm -23 <(find sources/ -name '*.py' ... ) <(grep 'Scraper()' main.py ...)`. After creating any new scraper file, registration in `SCRAPERS` must happen at commit time, not rely on CI discovery.

---

## 2026-04-29 — Google search fallback used wrong locale title [web]
**Error**: Detail page Google search URL used `name` (locale-specific) as query text. In `zh` locale, the query became `大濛 公式サイト` instead of `霧のごとく 公式サイト`, causing the Japanese official site to not appear in results.
**Fix**: Changed query to prefer `event.name_ja || event.raw_title || name` so the Japanese title is always used regardless of the viewing locale.
**Lesson**: When building Japanese-language search URLs, always use `name_ja` (or `raw_title`) as the source of the search term — never the locale-resolved display name.
---

## 2026-04-29 — Existing DB records not updated after adding official_url to cinema scrapers [cinemart_shinjuku, ks_cinema]
**Error**: After adding `official_url` extraction to `cinemart_shinjuku.py`, the existing DB event `cinemart_shinjuku_002491` (「大濛」) still had `official_url = null` because the upsert only runs on the next scraper cycle.
**Fix**: Ran a targeted Supabase UPDATE: `update({'official_url': 'https://www.afoggytale.com/'}).eq('source_id', 'cinemart_shinjuku_002491')`.
**Lesson**: When adding a new field extraction to an existing scraper, always manually update currently-active DB records or set `force_rescrape=True` for affected events. Dry-run only confirms the code works — it does NOT write to DB.
---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影以香港的食堂為背景，描繪了面對社會變遷的人們，由台湾・香港・法國共同製作。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---


## 2026-04-28 — 霧的如同 [cinemart_shinjuku] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:大濛, fieldEdit:name:en:A Foggy Tale, fieldEdit:name:ja:霧のごとく
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 台灣發祭 Taiwan Faasai 2026 [taiwan_faasai] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** lifestyle_food
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 身體化巴索里尼 - 吸引力法則 [ssff] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** performing_arts
**After (corrected):** movie
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 品嚐台灣茶，享受台灣遊戲的聚會 [kokuchpro] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** taiwan_mandarin, lifestyle_food, taiwan_japan, workshop
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 台灣電影上映會《海をみつめる日》上映暨座談會 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongDetails, wrongCategory, fieldEdit:name:zh:台灣電影放映會《看海的日子》上映暨座談會, fieldEdit:name:en:Taiwan Film Screening of 'A Flower in the Raining Night' and Talk Event, fieldEdit:name:ja:台湾映画上映会『海をみつめる日』上映＆トークイベント
**Before (AI category):** movie, lecture
**After (corrected):** movie, literature, history
**Wrong fields:** name
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 阿嬤的夢中情人 [eiga_com] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie, lecture
**After (corrected):** movie, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 甘露水 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, art, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 看海的日子（數位修復版） [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, history, literature
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


---
## 2026-04-29 — taiwan_cultural_center: month-only date range caused publish-date fallback

**Error:** `期間：2026 年5 月～10 月(全10 回)` was matched by `_BODY_DATE_LABELS` regex, but `_parse_date("2026 年5 月")` returned `None` (no day component). `start_date` fell back to publish date `2026-04-27`, `end_date = 2026-04-27` — would have been archived that evening.

**Fix:** (1) `_parse_date()`: added month-only `YYYY年M月` → day 1 of that month. (2) `_extract_event_dates_from_body()`: detect month-only `end_raw`, inject year from start, advance to last day of month via `calendar.monthrange`. (3) DB record manually corrected to `2026-05-16 / 2026-10-24`. Scraper will upsert `2026-05-01 / 2026-10-31` on next run (acceptable).

**Lesson:** `_parse_date()` must handle `YYYY年M月` (no day). Multi-month series often use month-only ranges in the structured `期間：` label. Always verify end_date won't trigger same-day archival.

---

## 2026-04-28 — 台灣文化祭2026春 [arukikata] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan, lecture
**After (corrected):** lifestyle_food, tourism, lecture, retail
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


## 2026-04-28 — 電影《大濛》上映 [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》上映, fieldEdit:name:en:Screening of the Movie 'A Foggy Tale', fieldEdit:name:ja:映画『霧のごとく』上映
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場 x 映後座談, fieldEdit:name:en:Private screening & talk of the film 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく（大濛）』東京貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---
## 2026-04-28 — 8 個爬蟲 source 檔案存在但未加入 SCRAPERS 列表

**Error:** CineMarineScraper、EsliteSpectrumScraper、MoonRomanticScraper、MorcAsagayaScraper、ShinBungeizaScraper、SsffScraper、TaiwanFaasaiScraper、TokyoFilmexScraper 已有 source 檔案但未加入 `scraper/main.py` 的 `SCRAPERS = [...]`。CI 從未執行這些爬蟲。
**Fix:** 補充 8 個爬蟲的 import 及 SCRAPERS 列表項目。以 `--dry-run` 確認各爬蟲能執行（CineMarineScraper 1件、EsliteSpectrumScraper 2件、MoonRomanticScraper 1件、ShinBungeizaScraper 1件、SsffScraper 6件、TaiwanFaasaiScraper 1件；MorcAsagayaScraper 和 TokyoFilmexScraper 0件屬正常——當日無台灣活動）。
**Lesson:** 建立新爬蟲 source 檔案後必須在同一 commit 確認已加入 SCRAPERS。定期比對 `ls sources/*.py` 與 SCRAPERS 列表，source 檔案不在 SCRAPERS 中將被 CI 靜默略過。→ Updated "Registration" in SKILL.md.

---
## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京電影包場 x 映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


## 2026-04-28 — 電影《霧的如同（大濛）》東京包場上映會暨映後座談 [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場上映會暨映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トーク
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---
## 2026-04-28 — merger.py Pass 2: pre-event press release not matched (start_date before event)

**Error:** `c1ba79b6` (google_news_rss, gnews_c5e4ad11f794) pointed to a prtimes.jp press release about 台湾祭in群馬太田2026 published **2026-01-15** — two months BEFORE the event start (2026-03-14). Merger Pass 2 uses `_date_in_range(news.start_date, official.start_date, official.end_date)` which returned False (`2026-01-15 < 2026-03-14`). Event was not merged; remained is_active=False with empty secondary_source_urls and prtimes content never incorporated.

**Fix:**
1. `merger.py`: Added `_PRESS_RELEASE_LOOKBACK_DAYS = 90` constant; changed `_date_in_range` to accept `lookback_days` parameter; Pass 2 now calls `_date_in_range(..., lookback_days=_PRESS_RELEASE_LOOKBACK_DAYS)` → range becomes `[start_date - 90d, end_date]`.
2. DB: Manually merged c1ba79b6 into primary `taiwan_matsuri_202603-gunmaota`:
   - Added google_news URL + direct prtimes.jp URL to `secondary_source_urls`
   - Fetched prtimes article body → appended as `別来源補足 (prtimes)` in `raw_description`
   - Set `annotation_status = 'pending'` for re-annotation with enriched content

**Lesson:** Pre-event press releases (prtimes, PR WIRE) are published weeks or months BEFORE the event start date. Merger Pass 2 must use a lookback window (currently 90 days) on `official.start_date` — NOT a strict lower bound. Also: when a google_news_rss entry links to a prtimes article, the ACTUAL rich content is at prtimes.jp — fetch that URL for the merger's raw_description supplement, not the google_news headline.

---

**Error:** `google_news_rss` 的「イオン太田で台湾グルメと台南ランタン祭イベント」（id: 1c766979）和 `taiwan_matsuri_202603-gunmaota` 是同一個活動，但 `merger.py` Pass 1 未偵測到，原因有二：
1. 名稱相似度太低（新聞報導標題 vs 官方活動名稱），不達 0.85 閾值。
2. `start_date` 不同（報導發布日 2026-03-16 vs 開幕日 2026-03-14），不在同一 `date_group`。

**Fix:**
1. 手動合併 DB：將 google_news_rss source_url 加入 `taiwan_matsuri_202603-gunmaota` 的 `secondary_source_urls`；設 google_news_rss 事件 `is_active=False`。
2. 同時發現スカイツリー2026 也有相同問題（`a5d24992`），一併合併。
3. `merger.py` 新增 **Pass 2 — News-report matching**：對 `_NEWS_SOURCES = {google_news_rss, prtimes, nhk_rss}`，以「日期在範圍內 + 地點 token 重疊」取代名稱相似度，並新增 `_location_overlap()` / `_date_in_range()` helpers。DB select 同步補加 `end_date,location_name`。

**Lesson:** 新聞/報導來源（google_news_rss、prtimes、nhk_rss）的文章標題和官方活動名稱結構不同，無法用名稱相似度合併。發現此類重複時，應先 `python merger.py --dry-run` 確認 Pass 2 能偵測，再正式執行。 → Added `## merger.py` section and Pass 2 rules to SKILL.md.

---
## 2026-04-28 — taiwan_matsuri: geographic filter + dry-run-only fix caused missed events

**Error 1 (initial version):** `_TOKYO_KANTO_KEYWORDS` filter limited scraping to venues matching `東京|スカイツリー|横浜|幕張|千葉|埼玉`. Gunma (群馬), Kumamoto (熊本), Fukuoka (福岡), Nara etc. were silently dropped — even though the project scope is all of Japan.

**Error 2 (fix commit):** The fix commit (`1d3cd1c`, April 26) removed the filter and ran `--dry-run` to confirm both Tokyo and Kumamoto were found. However, **no non-dry-run was executed after the fix.** The newly discovered events (`202603-gunmaota`, `202604-kumamoto`) were never written to DB. They remained missing until a manual run on April 28.

**Fix:** Removed `_TOKYO_KANTO_KEYWORDS` entirely. After confirming with dry-run, ran `python main.py --source taiwan_matsuri` (non-dry-run) to actually write to DB.

**Lesson 1:** Never restrict a scraper's geographic scope to a subset of Japan. The project covers all of Japan（全日本）. If the initial implementation needs a filter for testing, remove it before the first production run.

**Lesson 2:** A dry-run fix commit is incomplete. After removing a scraper bug (especially a filter bug), always follow up with a real run (`python main.py --source <name>`, no `--dry-run`) before the next CI cycle. Otherwise the fix is verified but the data gap persists until the next CI run.

---
## 2026-04-27 — eiga_com: per-theater redesign (3 address extraction bugs)

**Error 1:** `a.more-schedule a[href*='/movie-theater/']` selected the first matching link which was `/movie-theater/{id}/{pref}/{area}/{theater_id}/mail/` (the copy-to-clipboard link), not the theater detail page. `theater_id` was extracted correctly, but `_fetch_theater_address()` fetched the mail page which has no `theater-table`.

**Fix 1:** Use `a.icon.arrow[href*='/movie-theater/']` to get the "all schedule" detail link specifically.

**Lesson 1:** When multiple links share the same `href` pattern (copy/print/all-schedule), always target by CSS class (e.g. `a.icon.arrow`) not by href pattern alone. → Added to `eiga_com-specific` in SKILL.md.

**Error 2:** Page-wide regex `r'東京都[^\s<>]{5,50}'` on the area page matched JS-embedded `東京都"};params_ga4.login_status=...` instead of the actual address.

**Fix 2:** Switched to structured extraction: `table.theater-table th:contains("住所") + td` on the theater detail page.

**Lesson 2:** Never use page-wide address regex on pages with embedded JS/JSON. Use structured HTML selectors (`th`/`td` pairs) for reliable address extraction. → Added to `eiga_com-specific` in SKILL.md.

**Error 3:** `td.get_text()` included `<a>` link text "映画館公式ページ" appended to the address string.

**Fix 3:** Call `a_tag.decompose()` on all `<a>` children inside `td` before `get_text()`.

**Lesson 3:** When a `<td>` contains both text nodes and `<a>` child elements, always decompose unwanted children before `get_text()` to avoid mixing link text into field values. → Added to `eiga_com-specific` in SKILL.md.

---
## 2026-04-27 — taipei_fukuoka / yebizo: scrapers written but not registered or dry-run verified

**Error:** `taipei_fukuoka.py` and `yebizo.py` were fully written (270 and 255 lines respectively, complete `scrape()` + `Event()` return) but were left as untracked files with no entry in `scraper/main.py` → `SCRAPERS`. Running `python main.py --dry-run --source taipei_fukuoka` returned `Unknown source` — the scrapers had never been tested.

**Fix:** Added imports and class instantiations to `main.py`. Ran dry-run for both (exit 0, 3 events each). Then committed all files together.

**Lesson:** Writing a source file without registering it in `main.py` and running a dry-run means the scraper will never execute in CI, and the work is invisible until discovered manually. The commit gate is: **source file + main.py registration + dry-run pass must all be in the same commit.** Never leave an untracked source file without a companion `main.py` edit.

---
## 2026-04-25 — iwafu: Conan events re-appeared (direct URL accessible + card title bypass)

**Error (1 — direct URL accessible):** Deactivated events (`is_active=False`) were still accessible via direct URL. The event detail page had no `is_active` check — it fetched by ID regardless of status.

**Error (2 — card title truncation bypass):** `_BLOCKED_TITLE_PATTERNS` only checked `card_title` from search-result card text. If the card title was truncated and didn't contain both "リアル脱出ゲーム" AND "名探偵コナン", the filter would pass. No second check was done on the actual h1 title after loading the detail page.

**Fix:**
1. Hard deleted all 7 Conan events from DB (iwafu_1133807, 1133810, 1134057–1134061).
2. `web/app/[locale]/events/[id]/page.tsx`: Added `if (!event.is_active) notFound()` — inactive events now return HTTP 404.
3. `scraper/sources/iwafu.py`: Added `_BLOCKED_SERIES = re.compile(r"名探偵コナン")` checked on both card title (pre-load) and h1 title (post-load). Extended `_BLOCKED_TITLE_PATTERNS`.

**Lesson:**
- Inactive events remain accessible by direct URL unless detail page returns `notFound()` for `!is_active`. Always add this guard.
- Title blocks must check BOTH card title (pre-load) AND h1 title (post-load). Card titles can be truncated.
- For permanently blocked IP series, use `_BLOCKED_SERIES` with just the IP name. Simpler and catches all title variants.
- When an IP series is confirmed non-Taiwan-themed, prefer hard delete over deactivation to prevent URL resurrection.

---
## 2026-04-25 — iwafu/koryu/peatix: location_address stored as generic prefecture name ("東京") instead of real venue

**Error:** Three scrapers were writing useless generic values to `location_address`:
- **iwafu**: `_scrape_detail()` set `location_address = card.get("prefecture")` which was always `"東京"` (or `"東 京"` with space). The detail page contains `場所：中野区役所…` but was never parsed.
- **koryu**: `_extract_location_address()` only finds `所在地/住所` sections; when absent, `location_address` stayed `None` even though `_extract_venue()` had already extracted a useful venue name.
- **peatix**: CSS selectors `.venue-address` / `[class*='address']` miss the address on many events. No regex fallback existed.

**Fix:**
- `iwafu.py` `_scrape_detail()`: Added `re.search(r'場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)', main_text)` regex before the `card.prefecture` fallback. Sets both `location_name` and `location_address` to the captured venue.
- `koryu.py` `_scrape_detail()`: Changed `location_address = _extract_location_address(body_text)` → `_extract_location_address(body_text) or (venue if venue else None)`.
- `peatix.py` location block: Added regex fallback on `page_text` — `LOCATION\n<name>` for venue name, `〒NNN-NNNN` or `東京都...` for address.
- `scraper/backfill_locations.py` (new): One-off script to re-visit iwafu/koryu source URLs and apply the new extraction logic to existing DB rows. Supports `--dry-run`.

**Lesson:**
- When a detail page contains a structured `場所：` or `会場：` label, always prefer that over the card-level prefecture. Parse it with a regex before falling back to coarser data.
- For scrapers where the main location field may be absent, use the venue name as an `or` fallback for `location_address` — partial info is better than `None` or a bare prefecture.
- CSS selectors on JS-heavy pages (Peatix) are unreliable for location; always add a `page_text` regex fallback.
→ Added to SKILL.md (`iwafu-specific`, `koryu-specific`) and `peatix/SKILL.md` (Location Extraction section).

---

## 2026-04-25 — location/address/hours displayed in Japanese on zh/en locale

**Error:** `location_name`, `location_address`, and `business_hours` had no localized variants in the DB schema. The event detail page always showed the Japanese original regardless of the visitor's locale (e.g., "高知県立牧野植物園", "午前9時から午後5時" displayed to English/Chinese visitors).

**Root cause:** DB schema had only single-language columns for these three fields. The annotator extracted them from Japanese source text and stored only Japanese. No `_zh`/`_en` variants existed.

**Fix:**
1. `supabase/migrations/010_localized_location.sql` — Added 6 new columns: `location_name_zh`, `location_name_en`, `location_address_zh`, `location_address_en`, `business_hours_zh`, `business_hours_en`.
2. `scraper/annotator.py` — Updated GPT schema in `SYSTEM_PROMPT` to request the 6 new fields. Updated `update_data` and sub-event rows to populate them.
3. `web/lib/types.ts` — Added 6 fields to `Event` interface. Added three helper functions: `getEventLocationName(event, locale)`, `getEventLocationAddress(event, locale)`, `getEventBusinessHours(event, locale)` — all fall back to the Japanese original.
4. `web/app/[locale]/events/[id]/page.tsx` — Import and use the three new helpers instead of raw `event.location_name`, `event.location_address`, `event.business_hours`.
5. DB fix: reset `f463ad3d` (iwafu_1062563) to pending and re-annotated after migration.

**Lesson:**
- Any field that a non-Japanese visitor reads should have `_zh`/`_en` variants. Apply the same `_ja/_zh/_en` pattern to location, address, and hours — not just name and description.
- Always check: does the event detail page display anything sourced from Japanese-only source text without a locale helper?
- When adding new localized columns, the annotator's `update_data` must include ALL new fields (with `_str()`/`_loc()` cleaning). The GPT schema must explicitly request them.

---

## 2026-04-25 — AdminEditClient: null name_zh/name_en converted to "" on save → title disappears

**Error:** When an event has `name_zh = null` (or GPT returned `null`), the admin edit form initializes the field with `event.name_zh ?? ""`, converting `null` to `""`. On save, `""` is written to the DB. The `getEventName` function used `??` which does NOT fall back on empty strings (`"" ?? fallback → ""`), so the event title disappeared in the zh/en locale.

Additionally, events with `annotation_status = 'annotated'` but empty strings in `name_zh`/`name_en`/`description_zh`/`description_en` (e.g. `iwafu_1062563` — 【高知県立牧野植物園】こんこん山花さんぽ) showed no title or description because the DB contained `""` instead of `null`.

**Root causes (two bugs interacting):**
1. `AdminEditClient.tsx`: `const payload = { ...form }` sends `""` for every empty name/description field, converting `null → ""` in the DB.
2. `web/lib/types.ts` `getEventName`/`getEventDescription`: used `??` instead of `||`, so `""` did not trigger fallback to next locale.

**Fix:**
1. `web/lib/types.ts`: Changed `??` → `||` in `getEventName` and `getEventDescription` so empty strings fall back to the next locale.
2. `web/components/AdminEditClient.tsx`: Added `nullify` helper in `handleSave` — converts `""` to `null` for name/description fields before PATCH. `name_ja` falls back to `event.raw_title` if empty.
3. Direct DB fix for `f463ad3d` (iwafu_1062563): cleared `""` → `null`, reset `annotation_status = 'pending'`, re-ran `annotator.py` → produced proper `name_zh = '春花漫步'`, `name_en = 'Spring Flower Walk'`.

**Lesson:**
- Admin form fields that represent nullable DB columns should send `null` (not `""`) when empty. Wrap empty strings with `|| null` in the save payload.
- `??` and `||` have different semantics: `??` only catches `null`/`undefined`; `||` also catches `""` and `0`. Use `||` for locale fallback chains where GPT might return empty string.
- After annotator bugs produce empty strings for existing events, you must manually reset those events to `pending` and re-run `annotator.py`. The `_str()` helper in annotator prevents recurrence for future runs only.

---

## 2026-04-25 — iwafu: 6 more Conan events survived after _GLOBAL_TOUR_PATTERNS fix

**Error:** When `_GLOBAL_TOUR_PATTERNS` was added to `iwafu.py`, it only prevented **future** scraper runs from re-inserting matching events. The 6 existing DB rows (`iwafu_1134057` through `iwafu_1134061` + `iwafu_1133807`) were already in the DB with `is_active=True` and were unaffected. They continued to appear in the admin backend.

**Fix:**
1. Queried for all `%コナン%` events, deactivated all 6 remaining ones via targeted `update().eq("id", ...)` calls.
2. Added `_BLOCKED_TITLE_PATTERNS` regex in `iwafu.py` with pattern `リアル脱出ゲーム.*名探偵コナン` — checked in `_scrape_detail` **before** the page load (fast-reject). This blocks any new source_id variants of the same series (e.g. new tour stops) regardless of description wording.

**Lesson:**
- Fixing the scraper filter does NOT retroactively remove existing DB records. After adding a filter, always run a DB audit to deactivate any already-stored events that match the new rule.
- For well-known IP series that run global tours (anime collabs, game IPs), add the series name to `_BLOCKED_TITLE_PATTERNS` so all future venue variants are blocked at title level — before the detail page is fetched. Description-only filters can miss series with identical descriptions.
- Pattern for querying all events from a false-positive series: `sb.table("events").select("id,source_id").ilike("raw_title", "%<keyword>%")`.

---

## 2026-04-25 — taiwan_kyokai: end_date always null; publish-date used instead of event date

**Error (1 — end_date null):** `_extract_event_fields` in `taiwan_kyokai.py` never set `result["end_date"]`, leaving a comment "we keep only start_date for now". All single-day events had `end_date=None`, causing them to remain in "active" listings indefinitely (the web filter keeps events where `end_date IS NULL` OR `end_date >= today`).

**Error (2 — wrong start_date):** For pages where the event date lacks a year (e.g. `今年は5月16日（土）に執り行われます`), the generic fallback regex `YYYY年MM月DD日` found the page's **publish date** at the top of the body (`2026年4月20日`) instead of the actual event date (`5月16日`). The publish date appears prominently on taiwan-kyokai.or.jp pages just below the title.

**Fix:**
1. Added DOW-qualified date extraction step in `_extract_event_fields` — searches for `\d{1,2}月\d{1,2}日（[月火水木金土日][曜]?[日]?）` and infers year from nearest `20XX年` in text. Runs BEFORE the generic fallback, so `今年は5月16日（土）` is preferred over the bare `2026年4月20日` publish date.
2. Added single-day end_date rule at the bottom of `_extract_event_fields`: `if result["start_date"] and not result["end_date"]: result["end_date"] = result["start_date"]`. Taiwan Kyokai events are all single-day.
3. Direct DB fixes: `taiwan_kyokai_news-260420-2` start/end → 2026-05-16; `taiwan_kyokai_news-260217` end_date → 2026-04-12.

**Lesson:**
- **Always set `end_date = start_date` at end of `_extract_event_fields` for single-day sources.** Never leave it with a "for now" comment.
- On japan-kyokai-style sites, the page body starts with the **publish date** (`YYYY年MM月DD日`) before the actual event body. Never rely on the generic year-qualified date fallback alone.
- Dates with day-of-week markers `（土）（日）etc.` are almost always actual event dates. Prioritize these over bare `YYYY年MM月DD日` patterns when no structured `日時：` field is present.

---

## 2026-04-25 — annotator: leading ：colon included in location_name

**Error:** GPT extracted `会場：台北世界貿易センター１F（...）` and included the label separator `：` as the first character of `location_name`, producing `：台北世界貿易センター１F（...）` in the DB and on the web UI.

**Fix:** Added `_loc()` helper in `annotator.py` that calls `.lstrip("：；:; \u3000")` on all `location_name` and `location_address` values before writing to DB. Also did a direct DB fix for `koryu_4899`.

**Lesson:** Always strip leading `：；:;` and full-width space (`　`) from GPT-extracted location strings. GPT occasionally includes the Japanese label separator when the source text uses `会場：〇〇` or `場所：〇〇` patterns. Apply `_loc()` to both `location_name` and `location_address`.

---

## 2026-04-25 — iwafu: global-tour event passed Taiwan filter (コナン脱出ゲーム)

**Error:** `iwafu_1133810` (リアル脱出ゲーム×名探偵コナン) was collected because the description contained `台湾など世界各地で開催`. The event is a Japan/world-wide tour and has no Taiwan theme; the Tokyo instance is culturally identical to the Osaka and Nagoya instances.

**Fix:** Added `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py`. Any detail page whose `title + description` matches patterns like `台湾など世界各地|全国各地.*台湾` is rejected in `_scrape_detail()` before an Event is returned. Set `iwafu_1133810` to `is_active=False` in DB.

**Lesson:** "Being held in Taiwan (among many other cities)" does NOT make an event Taiwan-related. Only accept events where Taiwan is the theme or a primary focus, not just one venue on a global tour. Add `_GLOBAL_TOUR_PATTERNS` reject guard wherever iwafu full-text is searched by keyword 台湾.

---

## 2026-04-25 — arukikata: duplicate class caused old code to shadow new code

**Error:** `replace_string_in_file` on docstring-only line caused the old class body to remain appended after the new class in the same file. Python silently uses the **last** definition, so the old (broken) `_parse_article` ran instead of the new one. Symptoms: dry-run returned old buggy results even after editing.

**Fix:** Used `wc -l` to detect the file was 615 lines instead of ~292; used `head -n 292 > /tmp && mv` to truncate to the correct end.

**Lesson:** After a large structural rewrite using `replace_string_in_file`, always verify the file has the expected line count with `wc -l`. If it's unexpectedly large, a duplicate class body is likely still present.

---

## 2026-04-25 — arukikata: keyword search strategy misses articles

**Error:** `?s=台湾+東京+イベント` search only returned 29 results; articles 362618 and 323275 were not among them — each requires a different keyword combination.

**Fix:** Switched to **WordPress sitemap monitoring**: `wp-sitemap-posts-webmagazine-2.xml` (605 entries) contains both target articles with `lastmod` timestamps. Filter by `lastmod >= today - 90 days`.

**Lesson:** For WordPress editorial sites, always check for `wp-sitemap-posts-{type}-{page}.xml` first. Sitemap monitoring is more comprehensive and stable than keyword search for low-frequency sources. The sitemap with the highest page number contains the newest articles.

---

## 2026-04-25 — Doorkeeper Tokyo filter false positive (中央区)

**Error:** `中央区` was included in `_TOKYO_MARKERS` in `doorkeeper.py`.
This matched 神戸市中央区, causing a Kobe event to pass the Tokyo location filter.

**Fix:** Removed all ward names that are not geographically unique to Tokyo from `_TOKYO_MARKERS`.
Kept only `東京都`, `東京`, and 23-ward names that are exclusive to Tokyo prefecture.

**Lesson:** Never add bare ward names like `中央区`, `南区`, `北区`, `西区` to a Tokyo marker set —
they appear in Osaka, Kobe, Nagoya, and many other cities.
The safest Tokyo markers are `東京都` and `東京` as substring matches.
Individual ward names are only safe if they are provably unique to Tokyo (e.g. `渋谷区`, `豊島区`).

---

## 2026-04-25 — Connpass API v1 → v2 migration (403 on v1)

**Observation:** Connpass API v1 (`/api/v1/event/`) now returns HTTP 403 for all requests,
including those from fixed IPs. The platform has fully migrated to v2 which requires an `X-API-Key` header.

**Implementation decision:** Built `ConnpassScraper` against v2 API.
If `CONNPASS_API_KEY` is not set, scraper logs a WARNING and returns `[]` — pipeline continues uninterrupted.

**Lesson:** API v1 is dead. Do not reference v1 endpoints in any future Connpass code.
The v2 key must be obtained via the Connpass help page: https://connpass.com/about/api/
Their ToS also explicitly prohibits non-API scraping (Playwright/curl), so the API key is mandatory.
