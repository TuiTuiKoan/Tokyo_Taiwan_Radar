# Scraper Expert Error History

<!-- Append new entries at the top -->

---

## 2026-05-31 — iwafu aggregator 重複：merger.py の dedup ロジックがアグリゲーター来源に未対応（commit `c407a71`）

**問題：** `iwafu` アグリゲーター来源から取得したイベントが `merger.py` で重複候補として複数生成され、誤った merge ペアが作られていた。

**根本原因：** `merger.py` の重複検出は title/date 近似マッチで候補を生成するが、iwafu は同一イベントを複数エントリで返すアグリゲーター来源のため、**来源内部の重複**（同一来源の複数エントリ）と**来源横断の重複**（異なる来源の同一イベント）を区別できなかった。

**修正（commit `c407a71`）：** `merger.py` に iwafu 来源向け前処理（+192 lines）を追加。同一 `source_name` + `source_id` prefix の複数エントリを merge 候補生成前にまとめる。

**教訓：** アグリゲーター来源（同一イベントを複数エントリで返す来源）を merger に追加する際は、merge 候補生成前に来源内 dedup ステップを設ける。新規アグリゲーター追加時は `merger.py` の前処理リストへの登録を確認すること。

---

## 2026-05-31 — kokuchpro 薄文本：GPT が泛稱「語学スクール」を organizer に誤填（手動 DB 修正）

**問題：** `kokuchpro` 来源イベント `fb12bfa7` の `organizer` が泛稱「語学スクール」で、真実の主催者「Asao Language School」が欠落していた。

**根本原因：** `kokuchpro` は薄文本来源（raw_description が短い・構造が少ない）であり、GPT が組織名を特定できず泛稱をそのまま organizer に充てた。`note_creators` と同様、薄文本来源では GPT が「最もそれらしい一般名詞」を捏造しやすい。

**修正：** kokuchpro ページを fetch して真実の主催者名を確認後、DB 直接更新・`field_corrections` ロック。

**教訓：** `kokuchpro` / `note_creators` 等の薄文本来源で `organizer` が「語学スクール」「イベント会社」「主催者」のような泛稱になっている場合は、元ページを fetch して実名を確認してから FC ロックする。

---

## 2026-05-31 — note_creators 泛標題が内文の顕著主題（二二八国家記念館）を欠落（prompt/code 不同步）

**問題：** `note_creators` 来源の事件 `cceca5a2` が、部落格の泛標題「台湾のポスター展」を `name_ja` にそのまま照抄し、内文中で最も顕著な主題「二二八国家記念館」を欠落していた。タイトルだけでは活動の焦点（228 国家紀念館のポスター展）が読者に伝わらなかった。

**根本原因：** `note_creators` は code 側の `_HEADLINE_REWRITE_SOURCES` frozenset に含まれていたが、SYSTEM_PROMPT の NEWS HEADLINE REWRITE RULE「applies only to: ...」来源清单には記載されていなかった。そのため当該ソースは書き換え許可されているのに GPT は書き換え指示を受け取らず、泛標題を silent に照抄した。さらに「泛標題は内文の顕著主題を取り込む」という SALIENT SUBJECT ルール自体が存在しなかった。

**修正：** (A) `annotator.py` SYSTEM_PROMPT の NEWS HEADLINE REWRITE RULE 来源清单に `note_creators` を追加し、新たに SALIENT SUBJECT RULE（泛標題 + 内文の顕著主題 → name_ja に取り込む、228 範例付き）を追加。(B) `scraper-expert/SKILL.md` の Headline Rewrite セクションに SALIENT SUBJECT rule と code↔prompt 同步注意を追記。事件 `cceca5a2` は Architect が DB タイトルを手動修正し FC をロック済み（再 annotation 不要）。

**教訓：** (1) headline-rewrite 来源清单は code（`_HEADLINE_REWRITE_SOURCES`）↔ prompt（SYSTEM_PROMPT「applies only to: ...」）を必ず同步させる。どちらか一方の更新時、もう一方も同じソースを含めること。不同步は silent な泛標題照抄を招く。(2) 泛標題が内文の顕著主題（著名機関名・歴史/人権テーマ・具体的作品名）を欠落している場合は、その主題を取り込むよう name_ja を書き換える。

---

## 2026-05-20 — performers[]: 繁体字が入り日本語（カタカナ）が消失 + performers_zh に 'Ju 88轟炸機' ハルシネーション（DB 直接修正）

**問題：** 霧のごとく（大濛）11 件の `performers[]` が繁体字（`['范少勳', '區偉', '9m88', '曾敬驊']`）で格納されており、日本語モードでカタカナ名が表示されなかった。`performers_zh[]` には `'Ju 88轟炸機'`（WW2 爆撃機名）というハルシネーションが入っており、GPT が `9m88`（台湾ミュージシャンの芸名）を爆撃機名に誤変換していた。加えて `field_corrections` に旧来の悪い値がロックされており、FC 削除なしには修正できない状態だった。

**根本原因：** (1) `performers[]` 言語規約が annotator SYSTEM_PROMPT に明記されておらず、GPT が繁体字をそのまま格納した。(2) アーティスト芸名（英数字混じり）は翻訳不可だが GPT へその指示がなかった。

**修正：** 京都シネマ公式ページから正確なカタカナ（`ケイトリン・ファン`、`ウィル・オー`、`9m88`、`ツェン・ジンホア`、`リウ・グァンティン`、`ビビアン・ソン`）を確認。全 11 件の `performers[]` をカタカナに更新、`performers_zh[]` を正しい繁体字 6 名に修正、FC 削除・再ロック、`works.cast_summary` 更新。

**教訓：** (1) `performers[]` は日本語ソースのカタカナ名が入る。`performers_zh[]` が繁体字。(2) アーティスト芸名（`9m88` 等）は翻訳不可 — GPT に `performers_zh` を生成させる場合は「芸名はそのまま転記」の指示を SYSTEM_PROMPT に追加する。(3) performers データを手動修正する場合は必ずソースページをフェッチしてカタカナを確認してから FC をロックする。

---

## 2026-05-19 — annotator Phase C: 地域名｜会場名 prefix が location_name に混入（commit `2b328e1`）

**問題：** eplus 等のプラットフォームが `東京六本木｜EX THEATER ROPPONGI`・`大阪梅田｜Zepp Osaka Bayside` 形式で会場を表示する。`｜` 前の地域ナビゲーションラベルが `location_name` に丸ごと混入していた。

**根本原因：** annotator SYSTEM_PROMPT Rule 6 に `｜` 形式への指示がなく、GPT が `｜` を含む全文字列を会場名として採用していた。

**修正（commit `2b328e1`）：** SYSTEM_PROMPT Rule 6 に VENUE NAME PREFIX NOTE を追加。`地域名｜会場名` 形式を検出し `｜` 以降のみを `location_name` とするルール。

**教訓：** eplus / livepocket など `地域名｜会場名` 形式のプラットフォームを扱う場合は annotator SYSTEM_PROMPT にこのルールが適用されているか確認する。

---

## 2026-05-19 — enrich_addresses: location_address_zh が SC のまま DB に書き込まれていた（commit `2b328e1`）

**問題：** `enrich_addresses.py` が gpt-4o-search-preview から取得した `location_address_zh` を `_to_trad()` なしで DB に直接書き込んでいた。dry-run では `东京都涩谷区圆山町2-3 6楼`（簡体字）が表示され DB に SC が混入するバグ。

**根本原因：** `_to_trad()` は `annotator.py` の `annotate()` 内でのみ呼ばれており、外部スクリプト `enrich_addresses.py` はこの処理が漏れていた。

**修正（commit `2b328e1`）：** `from annotator import _to_trad` を追加し、`patch["location_address_zh"] = _to_trad(result["location_address_zh"])` に変更。

**教訓：** annotator 外部のスクリプト（バックフィル、`enrich_*` 系）が `_zh` フィールドを直接 DB に書き込む場合は必ず `_to_trad()` を通すこと。

---

## 2026-05-19 — eplus: scraper 層で `ev.performer` 直接セット — SKILL.md performer ルール違反（commit `fe72ea2`）

**問題：** `_fetch_detail_info()` が performer を `ev.performer = info["performer"]` と直接セット。SKILL.md「Scraper 層用不到」ルール違反（performer は annotator GPT が raw_description から抽出する）。

**根本原因：** 機能追加前に SKILL.md performer ルールを確認しなかった。

**修正（commit `fe72ea2`）：** `ev.performer` 直接セットを削除し、`raw_description` に `出演: …\n曲目・演目: …` 形式で追記。

**教訓：** performer 関連フィールドを scraper で触る場合は必ず SKILL.md `## performer / performers[] 注解規則` を確認する。scraper は raw_description に書くだけ。

---

## 2026-05-19 — enrich_addresses: 市区レベルアドレス（`'福岡市'`）が VAGUE 未判定 + FC ロック二重ブロック（commit `113fceb`）

**問題：** `VAGUE_ADDRESS_VALUES` に市区名が含まれず候補フィルタ通過不可。加えて FC に古い `'福岡県'` がロックされ eplus の補完も毎回上書き（event `7cdd06cb`）。

**根本原因：** VAGUE は固定 set のみで正規表現カバレッジなし。eplus（都道府県→市区）と enrich_addresses（市区→街路）の 2 段階パイプラインで後段が市区を VAGUE と見なさなかった。

**修正（commit `113fceb`）：** `_VAGUE_GEO_RE = re.compile(r'^[^\s]{2,10}[都道府県市区]$')` 追加。FC 削除 + NULL リセット後に enrich_addresses 実行 → `'福岡県福岡市中央区天神1-1-1'` に補完。

**教訓：** enrich_addresses に FC ロックがあるイベントは常にスキップ。街路補完を強制する場合は FC 削除 + `location_address = NULL` が必要。

---

## 2026-05-19 — Peatix: Playwright `inner_text()` がページ全体テキストを返し `organizer_name` が数千文字になる（commit `f839508`）

**問題：** Playwright の `inner_text()` がグループアンカー要素に対して、組織名（数十文字）ではなく「Translate this page...」から始まるページ全体テキスト（数千文字）を返すケースがあった。`organizer_name` がページ全体テキストになりブロックリスト照合が誤動作する可能性があった。

**根本原因：** Playwright `inner_text()` は live DOM テキストを返すが、DOM 構造や SPA レンダリング状態によって要素が期待以上のコンテンツを含む場合がある。「主催者名は短い文字列」という暗黙の前提を検証するガードがなかった。

**修正（commit `f839508`）：** 主パスと fallback パス両方に `len(_txt) <= 100` ガード追加。

**教訓：** Playwright `inner_text()` を短い文字列フィールド（組織名・タイトル・地名等）に使う場合は `if _txt and len(_txt) <= 100` の長さガードを必ず設ける。

---

## 2026-05-19 — Peatix: `organizer_name` を抽出しながら `Event()` に渡していなかった（commit `24198d0`）

**問題：** Peatix イベントの `ev.organizer` が常に null。`organizer_name` はブロックリスト照合のために抽出されていたが、`Event()` コンストラクタには渡されていなかった。

**根本原因：** フィールドが「ブロックリスト照合」目的として追加されたとき「DB 保存」という第 2 の用途が見落とされた。「Extract but not store」anti-pattern。

**修正（commit `24198d0`）：** `Event()` の引数に `organizer=organizer_name or None` を追加。

**教訓：** (1) 抽出ロジック (2) `Event()` コンストラクタへの代入 (3) DB migration の 3 点が揃っているか確認する。ブロックリスト照合用に抽出した変数は必ず `Event()` にも渡す。

---

## 2026-05-19 — eplus: 詳細ページを既に fetch していたが `dt/dd` フィールドを無視（commit `e897d29`）

**問題：** eplus イベントの `ev.performer` が常に null。詳細ページには `<dt>出演</dt><dd>…</dd>` と `<dt>曲目・演目</dt><dd>…</dd>` が構造化されていたが取得していなかった（event `7cdd06cb`）。

**根本原因：** `_fetch_city_from_detail()` は都市抽出のみを目的として設計。同一 HTTP レスポンスに含まれる `dt/dd` ペアを無視。「1 リクエスト 1 フィールド」の設計。

**修正（commit `e897d29`）：** `_fetch_city_from_detail()` → `_fetch_detail_info()` に拡張。`{"出演": "performer", "曲目・演目": "program"}` の dt/dd を一括取得し `ev.performer` と `ev.raw_description` に反映。

**教訓：** 詳細ページを fetch しているなら同一リクエストで取れる全フィールドを一括抽出する。「1 リクエスト 1 フィールド」は追加要件発生のたびにリクエスト数が増加する。

---

## 2026-05-19 — eplus: 詳細ページ fetch による都道府県→市区レベルアドレス補完（commit `0cfd07f`）

**問題：** eplus.jp 検索結果カードは会場名を `（福岡県）` 形式（都道府県レベル）でしか提供しない。`location_address = "福岡県"` が DB に保存されるが `enrich_location.py` が null/空のみ対象のためスキップ（event `7cdd06cb` — アクロス福岡シンフォニーホール）。

**根本原因：** `_parse_card()` はカードテキストの `（都道府県）` パターンのみ抽出。詳細ページ H1 の `(福岡市・2026/8/1(土))` 市区名はカードスクレイプでは到達できなかった。

**修正（commit `0cfd07f`）：** Playwright セッション終了後、`_PREF_ONLY_RE`（純粋な都道府県名）にマッチする各イベントに対して `requests.get()` + `BeautifulSoup` で詳細ページ H1 を fetch。`r"\(([^・)]+[市区])\s*・"` で市区名抽出 → `ev.location_address = city`。

**教訓：** プラットフォームの検索カードが都道府県レベルしか持たない場合は詳細ページ H1 の `(市名・日付)` パターンを fetch して補完する。`enrich_location.py` は null/空のみ対象のため、都道府県 placeholder には効かない。

---

## 2026-05-19 — Peatix URL 正規化を URL 収集段階に拡張（7 件 DB 修正、commit `8b901ec`）

**問題：** 2026-05-17 の `_scrape_detail()` 入口修正は 1 件（`e9c6f80b`）のみカバーしていたが、DB に `/us/event/` URL が 7 件蓄積されており `55d766ae`（台湾家庭料理会in亀有）で再発。`peatix.com/us/event/4994536` → 302 → トップへリダイレクト。

**根本原因：** `_scrape_group_events` と `_search_events` でも locale prefix 付き URL が取得されていた。`_scrape_detail()` 入口の修正は detail scrape 時のみ有効で、URL 収集リストへの混入を防げなかった。さらに正規 URL (`/event/`) でスクレイプ済みの重複レコードが別途存在する場合、`/us/event/` 版は `source_id` が異なる別レコードとして重複していた。

**修正（commit `8b901ec`）：** `_normalize_peatix_url()` をモジュールレベルに追加。`_scrape_group_events` と `_search_events` の URL 収集ループで適用。DB 7 件：5 件は `merged_into_event_id` で merge soft-delete、1 件は `source_url`/`source_id` 正規化、1 件（inactive）skip。

**教訓：** URL 正規化は収集段階（`_search_events`・`_scrape_group_events`）で行う。detail 入口の修正は後段であり収集済みリストの汚染を防げない。DB 修正スクリプトは「重複チェック → DUP: merge / NO-DUP: update」の 2 分岐で設計。

---

## 2026-05-17 — Peatix: ロケール付き URL（/us/event/）が source_url に保存 → broken link（event e9c6f80b）

**根因：** Peatix group ページで取得した `<a href>` が `/us/event/{id}` 形式（ブラウザロケール起因のリダイレクト先）。`source_url=url` がそのまま保存されるため、ロケールプレフィックス付き URL が DB に入り 404 になる。

**教訓：**
- `_scrape_detail()` 入口で `re.sub(r"^(https://peatix\.com)/[a-z]{2}/event/", r"\1/event/", url)` を実行し、ロケールプレフィックスを除去してから `page.goto()` する。
- Peatix に限らず、ロケール別 URL（`/en/`、`/us/`、`/jp/`）が `source_url` に混入していないかスクレイパーテスト時に確認。

---

## 2026-05-15 — tsutaya_portal: span.place 店内エリア名 + end_date 年なしパース失敗

**根因（2件）：**
1. `div.date > span.place` は店内棚エリア名（例: 「スターバックス横平台」）で、venue 名ではない。`card_store`（genre span）が正しい店名だが、`span.place` が存在すると card_store にフォールバックしなかった。
2. `YYYY年MM月DD日 - MM月DD日`（end-date に年なし）形式を `_DETAIL_DATE_RE`（年必須）で検出できず `end = start` になった。

**教訓：**
- 蔦屋書店系サイトでは `card_store`（genre span）を `location_name` に優先し、`span.place` は venue として使わない。
- 年省略 end-date は `_DETAIL_END_DATE_SHORT_RE` で捕捉し `start_date.year` から補完（end_month < start_month なら翌年）。

---

## 2026-05-15 — 台湾文化センター海報 OCR で co_organizer 発見 + location_name 幻覚修正（剪花・綻放 切り絵展）

**問題：** イベント `dbfac7c9`（剪花・綻放 切り絵アート展）の `location_name` が `東京・京都`（誤）、`co_organizers` が空。

**根因（2件）：**
1. **location_name 幻覚**：annotator GPT が東京のみの TCC 会場を `東京・京都` と誤設定。`raw_description` に「台湾文化センター(東京都港区虎ノ門1-1-12 2階)」と明記されているにも関わらず、GPT が京都を付け加えた（ツアー展の記憶汚染と推定）。
2. **co_organizers 欠落**：`共催：遼江市政府` と `企画運営：日青創藝有限公司` は海報画像（`image_url`）にしか記載されておらず、HTML テキストには `主催：台湾文化センター` のみ → annotator は HTML テキストしか参照しないため空になる。

**修復（直接 DB update）：**
- GPT-4o Vision で `image_url` の海報 JPEG を OCR → `co_organizers=['遼江市政府']`、`sponsors=['日青創藝有限公司']`、`image_url` を設定
- `location_name='台湾文化センター'` に修正（`location_name_zh`、`location_name_en` も修正）
- 6 フィールドを `field_corrections` にロック（再 annotation で上書きされない）

**教訓：**
- **TCC（台湾文化センター）の `location_name` は annotator が稀に幻覚する**。`東京・京都` は TCC の典型的な誤設定パターン（ツアー展記憶の汚染）。`raw_description` に京都への言及がないのに `location_name` に京都が入っていれば幻覚を疑う。
- **海報画像（`image_url`）は共催者情報の最終参照元**。HTML テキストに `共催:` がなくても海報には記載されることが多い。admin OCR フロー（GPT-4o Vision）で `image_url` を OCR すれば、スクレイパーが取れない共催者・企画運営を補完できる。
- **修正後は必ず `field_corrections` にロック**。`co_organizers`、`sponsors`、`location_name` は re-annotation で上書きされる可能性がある。`field_corrections` にロックすることで annotator の上書きを防ぐ。

---

## 2026-05-06 — bookandbeer: keyword= URL パラメータがサーバー側でフィルタされない（100% ノイズ問題）

**根因：** `bookandbeer.com/event/?keyword=台湾` はサーバー側でフィルタされず全件返却。クライアント側チェックなしだと active 19 件全てが非台湾イベント。

**修復（commit e1ab468）：** 3 段階クライアント側フィルタを実装。
1. タイトルに台湾キーワードがあれば即通過
2. 説明冒頭 500 字に台湾キーワード 2 件以上
3. `_AUTHOR_BIO_RE`（台湾の大学名パターン）で著者略歴 false positive を除去

**教訓：**
- **keyword= URL パラメータは信用しない**。サイトによってはサーバー側フィルタが無効。dry-run で台湾キーワードが本当に含まれているか確認。
- 書店イベントは著者の大学名に「台湾大学」が含まれやすい → 大学名 regex で著者略歴を先に除去してから再判定。
- auto_scraper 生成スクレイパーはクライアント側フィルタを生成しない → 台湾関連性のチェックは手動で追加。

## 2026-05-11 — Shopify 絶対 URL / `update_source.py` 既存行専用 / `feasibility` 列非存在（placebymethod）

**根因：**
1. Shopify `<a href>` はフル絶対 URL を出力 → 相対パス `r"^/pages/"` で 0 件
2. `update_source.py` は UPDATE 専用（行が存在しない場合は `No row found` で失敗）
3. `research_sources` に `feasibility` 列は存在しない（`scraping_feasibility` または `source_profile` JSONB 内に格納）

**教訓：**
- Shopify の `<a href>` は `href=re.compile(r"example\.com/pages/")` でマッチ
- 新規ソース登録は `insert()` または `upsert(on_conflict="url")` で直接 SDK 操作
- 列名は `scraping_feasibility`（`feasibility` は PGRST204 エラー）

---

## 2026-05-14 — rti_jp.py dry-run で 0 件（RSS `&amp;` 二重エンコード）

**問題：** `rti_jp` の dry-run が RSS フェッチ成功（HTTP 200）にも関わらず常に 0 件。DEBUG ログで全 3 番組が 200 OK を受信していることは確認済み。

**根因：** RSS の `<link>` テキストノードが HTML エンティティ `&amp;` を保持したまま配信されていた。例:
```
<link>https://www.rti.org.tw/jp/programnews?uid=4&amp;pid=103701</link>
```
`xml.etree.ElementTree` は XML パース時に `&amp;` → `&` を復元するが、実際に配信されていたのは既に `&amp;` がリテラル文字列として埋め込まれた二重エンコード状態だった。つまり `.text` は `"...&amp;pid=103701"` を返す。`_extract_pid()` の正規表現 `[?&]pid=(\d+)` は `&amp;` にマッチしないため、全エピソードが `pid=None` → skip。

追加因子:
- `LOOKBACK_DAYS=14` — ミュージックステーションは月1配信（33日前）のため全件 cutoff 外れ。
- `PROGRAMS` dict に廃番プログラム 4 件（363/367/375/382、2025年7月以降更新なし）が含まれ、そもそも有効エピソードが 0 件だった。

**修正：**
- `_extract_pid(link)` と link URL 構築の両方で `.replace("&amp;", "&")` を適用:
  ```python
  link = link_raw.replace("&amp;", "&")
  normalised = link.replace("&amp;", "&")
  m = re.search(r"[?&]pid=(\d+)", normalised)
  ```
- `LOOKBACK_DAYS`: 14 → 60（月次配信番組対応）
- `STALE_DAYS = 90`: 最新エピソードがこれより古い番組はスキップ（廃番自動検出）
- `PROGRAMS` dict: 廃番 4 件削除、`文化の台湾`（id=378、15d）追加

**教訓：**
- **RSS `<link>` テキストノードは `&amp;` を二重エンコードして配信する場合がある。** XML パーサーは本来 `&amp;` → `&` を変換するが、ソースが既に `&amp;` リテラルを持つ場合は二重エンコード状態が残る。リンク URL を正規表現で処理する前に必ず `.replace("&amp;", "&")` を適用すること。
- **Python の XML Element `if element:` は常に `True`**（DeprecationWarning）。`element is not None and element.text` と書くこと。
- **Podcast/RSS 型 scraper には `STALE_DAYS` チェックを入れる**: 最新エピソードの `pubDate` が `STALE_DAYS` より古ければ廃番扱いでスキップし、無駄な全件フェッチを防ぐ。
- **RSS 型 scraper の `LOOKBACK_DAYS` は配信頻度に合わせる**: 週次なら 14d、月次なら 60d 以上。

---

## 2026-05-15 — asahiculture オンライン受講コースに物理住所が入る

**問題：** `台湾映画最前線2026（オンライン受講）` (d617e8c4) の `location_name = 川西教室`、`location_address = 〒666-0033 川西市栄町25-1 アステ川西3階` — 物理住所が FC ロックされていた。

**根因：** `scrape_card()` 内の location 解決ロジックが `CLASSROOM_ADDRESS_MAP.get(location_name)` で川西教室の住所を補填。raw_title に「（オンライン受講）」と明記されているが、スクレイパーがそれを見ていなかった。

**修正：**
- `asahiculture.py` scrape_card() に「オンライン」検出を追加：
  ```python
  _is_online = "オンライン" in raw_title or "オンライン" in (detail["location_name"] or "")
  if _is_online:
      location_name, location_address = "オンライン", None
  else:
      location_name = detail["location_name"] or card_branch
      location_address = detail["location_address"] or CLASSROOM_ADDRESS_MAP.get(location_name)
  ```
- DB: `location_name='オンライン'`, `location_address=None`, `location_name_zh='線上'`, `location_name_en='Online'`, `location_prefectures=None` に更新。
- FC: 旧 `location_address` FC を削除し、5 フィールド全て FC ロック。

**教訓：** **課程タイトルに「オンライン」が含まれる場合、物理的な教室情報より title が優先される。** 教室名・住所 MAP の前に title による `_is_online` チェックを挟むこと。この pattern は他の多教室型カルチャースクール scraper（shinjuku 系、hankyu 系など）にも適用可能。

---

## 2026-05-15 — iwafu.py `location_address` が取れない（公式サイト body_text 未活用）

**問題：** `屋台湾フェス2026 in 芝公園` (iwafu_1137442) の `location_address`・`location_prefectures` が共に `None` のまま入庫。DB に手動で `東京都港区芝公園3-2` を設定 + FC ロック済み。

**根因（3層）：**
1. **`_ADDR_RE` が都道府県プレフィックス必須** — iwafu ページの `場所：都立芝公園4号地（御成門駅前広場）` には住所がなく、公式サイトには `港区芝公園3-2`（`東京都` なし）があったが regex が不一致。
2. **公式サイトは既に fetch 済み**（`_fetch_official_organizer_info`）だが、`body_text` を返さずローカル変数で捨てていた。
3. **`_fetch_official_organizer_info` の戻り値が `(organizer, supplemental)` の 2-tuple** だったため、住所フォールバックとして再利用できなかった。

**修正（`scraper/sources/iwafu.py`）：**
- `_ADDR_RE`：都道府県プレフィックスを `(?:...)?`（省略可能）に変更、代わりに `[市区町村]` を必須アンカーに追加 → `港区芝公園3-2` がマッチするようになる。
- `_fetch_official_organizer_info`：戻り値を `(organizer, supplemental, body_text)` の 3-tuple に変更（全 return 箇所修正）。
- `_scrape_detail`：`place_m` マッチ後、`main_text` で住所が取れない場合に `official_body_text` をフォールバック検索するよう追加。

**教訓：**
- **公式サイトを fetch する scraper は、住所抽出のフォールバックとして `body_text` を保持すること。** iwafu 形式のイベントは公式サイトの方が詳細な住所を持つ場合が多い。
- **`_ADDR_RE` に都道府県のない住所（`港区...`、`中央区...`）が入ることは正常。** プレフィックスは省略可能にし、`[市区町村]` を必須アンカーとする。
- **正規表現の「必須プレフィックス」はサイレントミスの温床。** マッチしなくても例外を投げず `None` が入るだけなので、CI では気づきにくい。

---

## 2026-05-15 — matsumoto_cinema_select.py 建立後未同步登錄 main.py（Promotion Checklist 遺漏）

**問題：** `matsumoto_cinema_select.py` 建立並修正完畢，但 V-M-D 流程中 `git status` 顯示為 `??`（untracked），且 `scraper/main.py` 無對應 import 與 SCRAPERS 登錄。CI 無法執行此 scraper。

**根因：** 實作 matsumoto_cinema_select 時，session 聚焦在修正 3 個 dry-run 錯誤（class 名稱、回傳值解包、非法欄位），修正後直接結束 session，未執行 Promotion Checklist Step 2（main.py 登錄）與 Step 5（Combined Post-Build Audit）。

**修正：** V-M-D 流程中補齊 `scraper/main.py` import + `SCRAPERS` 登錄，確認 SCRAPERS audit ALL CLEAR 後一起 commit。

**教訓：**
- **Scraper 實作 session 結束前，必須確認 `git status` 中 `scraper/sources/` 無 `??` 未 tracked 檔案。** 若有，代表 Promotion Checklist 未完成。
- **`main.py` 登錄要和 scraper 檔案在同一個 commit**。分開 commit 會造成 CI 執行期間 import error。
- **每次 debug 循環（fix → dry-run）結束後，立即跑 SCRAPERS audit 確認登錄狀態**，不要等到 V-M-D 才發現。

---

## 2026-05-15 — starcat_cinema end_date 被 annotator SINGLE-DAY RULE 覆寫

**問題：** `starcat_cinema` 事件的 `end_date` 設為每週排片最後一天（木曜），但 annotator SINGLE-DAY RULE 將其覆寫為 `start_date`，導致存檔時所有事件都變成「單日活動」。

**根因：** annotator 的 `_get_end_date()` 邏輯中，SINGLE-DAY RULE 檢查 `description` 是否含「單日」關鍵詞，但 starcat `raw_description` 起始為 `"上映日: YYYY年M月D日"` (含空格，只標單日)，被誤判為單日活動。即使 `start_date != end_date`，RULE 也會強制覆寫 `end_date = start_date`。

**修正：**
1. `_build_ticket_schedule()` 改為回傳 tuple：`(business_hours_str, last_date_utc)`。
2. 新增 `_lookup_end_date()` helper，從 schedule 取得最後一天。
3. `_parse_date()` 加入 `tzinfo=timezone.utc`（符合 SKILL.md 規則）。
4. `raw_description` 前綴改為 `"上映期間: YYYY年M月D日〜YYYY年M月D日"` → annotator 不再誤判為單日。
5. `scrape()` 中 `Event()` 的 `end_date = _lookup_end_date(schedule, start_date)` 確保日期跨度。

**驗證：** `python main.py --dry-run --source starcat_cinema` 輸出顯示 `"start_date": "2026-05-19T00:00:00", "end_date": "2026-05-30T00:00:00"` ✅。

**教訓：**
- **scraper raw_description 的措辭會影響 annotator 決策：** 「上映日」(単日含意) vs 「上映期間」(期間含意) 的字眼差異導致 SINGLE-DAY RULE 觸發。
- **Scraper 改動時要考慮 annotator 層級的副作用：** 日期改動不只是改 code，還要確保 raw_description 前綴不會被 SINGLE-DAY RULE 誤判。
- **多日排片的 end_date 應由 scraper 負責取得，不應仰賴 annotator 推導：** annotator 的 SINGLE-DAY RULE 是為了處理資訊不足的情況，不能用來處理 scraper 本應產出的完整日期跨度。

---

## 2026-05-15 — matsumoto_cinema_select (teket.jp) 初回 dry-run 0 件 — sitemap timeout

**問題：** `matsumoto_cinema_select.py` の初回 dry-run で 0 件取得。サイトマップ fetch で `ReadTimeout` 発生。

**根因：** teket.jp の `sitemap.xml` は 34,000+ URL を含む大容量ファイルで、応答完了に 15〜20 秒かかる。`timeout=15` では完了前に打ち切られた。

**修正：** `requests.get(SITEMAP_URL, timeout=30)` に変更（15 → 30）。

**教訓：**
- **teket.jp sitemap.xml は timeout=30 以上を使うこと。** teket.jp の全プラットフォームイベントが詰まった大容量 sitemap のため、デフォルト 15s では失敗する。
- **サイトマップ取得 0 件 → 第一確認: timeout を 30s 以上に引き上げる。** その後エラーログで `ReadTimeout` を確認する。
- **teket.jp の `/api/events?group_id=` は使用不可**: group フィルタが無効で全プラットフォーム (34,000+ 件) を返す。グループ別列挙には sitemap.xml が唯一の手段。
- **teket.jp JSON-LD `description` はフェスタ名のみ**: 台湾フィルタを JSON-LD に適用しても無意味。full page text (script/style 除去後) に `2021年｜台湾｜カラー` / `台湾映画社` 等のキーワードが含まれる。
- **teket.jp JSON-LD `location.name` は常に `その他のホール`**: page title の `| venue` 部分または OG description の `[venue_name address]` ブラケットから取得する。

---

## 2026-05-15 — starcat_cinema business_hours 場次資訊需從 starcat-ticket.com 抓取

**問題：** `starcat_cinema.py` 爬取的事件缺少 `business_hours`（每日場次時間），無法讓使用者知道實際放映時刻。

**根因：** 台灣電影資訊（スターキャット・シネマ）主頁面不包含每週詳細場次，場次資料存放在 `starcat-ticket.com`（票務平台），需另外查詢。

**修正：**
1. 新增 `TICKET_SCHEDULE_URLS` dict，映射電影片名 → 票務頁面 URL。
2. `_build_ticket_schedule(url)` 從票務頁解析每日放映時段，回傳 `dict[date_str, list[time_str]]`。
3. `_lookup_business_hours(title, start_date, end_date)` 依日期範圍格式化成：
   ```
   5/15(金): 12:05〜13:49
   5/16(土): 12:05〜13:49
   …
   ```
4. `scrape()` 在建立 Event 時呼叫 `_lookup_business_hours()`，填入 `business_hours`。

**教訓：**
- **場次時間（business_hours）與主要活動資訊常分散在不同頁面**（主頁 vs 票務平台）。實作時需判斷主頁是否含場次，若無則需額外爬取票務頁。
- `TICKET_SCHEDULE_URLS` 應作為 scraper 內的 dict，避免每次 dry-run 都重新 fetch 票務頁（可考慮加 TTL cache）。
- `business_hours` 格式統一為 `M/DD(曜): HH:MM〜HH:MM`，多天用 `\n` 分隔。

---

## 2026-05-14 — wuext_waseda オンデマンド講座の日付が term fallback になる

**問題：** 早稲田エクステンション（wuext_waseda）のオンデマンド講座は、一覧表の「日時」列に
`2025年度 冬期 全4回` のように期間名のみが書かれており、具体的な日付範囲がない。
スクレイパーが listing column からの日付抽出（Tier 1）に失敗し、
term fallback（冬期 → `2026-01-01`）を返した。
ユーザーから「日期沒抓到」と報告：`start_date=2026-01-01` が表示されていた。

**根因：** 実際の視聴期間（`(2025/11/26)から(2026/04/30)まで`）は詳細ページ本文に
`(YYYY/MM/DD)` 形式で書かれていたが、scraper がその情報を参照していなかった。
fallback 優先順位が Tier 1（listing）→ Tier 3（term）で、詳細ページ参照（Tier 2）がなかった。

**修正：** `_extract_detail_dates()` 関数を追加（`(YYYY/MM/DD)` と `YYYY年MM月DD日` を抽出）。
listing 日付失敗時に detail page 日付を Tier 2 として試みてから term fallback（Tier 3）へ進む。
DB の該当イベント `30bdfc30` を `start=2025-11-26`、`end=2026-04-30` に修正・FC ロック済み（commit `bacd4cd`）。

**教訓：**
- オンデマンド / 録画配信コースは listing に日付がない場合でも、detail page 本文に `(YYYY/MM/DD)` 形式で視聴期間が書かれていることが多い。**term fallback より前に detail page を参照すること。**
- term fallback が返す `YYYY-01-01` や `YYYY-04-01` はユーザーに「日期未定」として表示される誤情報。最後の手段として使い、可能な限り具体的な日付を優先する。
- 汎用ルールを `scraper-expert/SKILL.md § On-Demand / Viewing Period — detail page date extraction` に追加済み。

---

## 2026-05-14 — cine_gallery 相對路徑未加 BASE_URL → source_url 損壞 + raw_description = None

**問題：** auto-generated `cine_gallery.py` 只處理以 `/` 開頭的相對路徑（`detail_url.startswith("/")`），但 cine-gallery.jp 部分 detail link 為 `cinema/2026/event/shinotenshi/shinotenshi_2026.html`（無前導 `/`）。此 URL 被直接存入 `source_url`，detail page 無法開啟，`raw_description = None`，annotator 缺乏資料可用。

**根因：** spec_to_code / template 生成的相對路徑補全邏輯只考慮 absolute-from-root（`/xxx`），未考慮 document-relative（`xxx/yyy`）路徑。

**修正：**
```python
if detail_url and detail_url.startswith("/"):
    detail_url = f"{BASE_URL}{detail_url}"
elif detail_url and not detail_url.startswith("http"):
    detail_url = f"{BASE_URL}/{detail_url}"
```

**連帶效應：** 事件 `cdf5e555`（フィシスの波文 ゲストトーク）因資料損壞且無台灣關聯，設為 `is_active=False` + `deactivated_reason`。

**教訓：**
- auto-generated scraper 的相對路徑補全必須同時處理：`/` 前導（absolute-from-root）和無前導 document-relative 路徑。
- `raw_description = None` 是 detail URL 損壞的診斷訊號：annotator 只輸出「details will be announced later」類型的佔位翻譯。
- 資料損壞且無台灣關聯的事件：直接 `is_active=False`，不嘗試資料補齊。

---

## 2026-05-14 — SNET台湾スクレーパー：WP REST `content` 空 + タイトルフィルタ設計パターン（commit `64034ec`）

### A — Elementor WP サイトで REST API `content` フィールドが空になる

**問題：** `/wp-json/wp/v2/accomplishment?_fields=content` の `content.rendered` が `""` で返る。Elementor テーマが JavaScript 側でレンダリングするため、静的 HTML レスポンスには本文が存在しない。

**修正：** `content` フィールドは使わず、`link` フィールドで取得した URL に対して `requests.get` → `BeautifulSoup` で HTML を直接スクレーピング。`get_text()` でプレーンテキスト化してから日付・会場・本文を正規表現で抽出。

**教訓：** WP REST API を使うソースで `content.rendered` が空の場合、Elementor / Gutenberg blocks ベースのテーマが原因。`link` URL を直接 fetch することで解決できる。詳細ページ取得のコストを抑えるため、**API 段階でタイトルフィルタを先に適用し、対象投稿のみ fetch する（後述 B）**。

### B — 低頻度ソース（年 3〜5 件）のタイトルベースフィルタ設計

**問題：** 66 投稿のうちイベント募集は約 5 件。YouTube アカデミー動画（27 本）・過去活動報告・B2B 講師派遣報告が混在。全件を詳細ページ fetch すると不要な HTTP コスト・レート制限リスクが発生。

**設計：**
```python
_INCLUDE_RE = re.compile(r"開催のお知らせ|申込|プランニング大賞|作品募集|ツアー.*ご案内|…")
_EXCLUDE_RE = re.compile(r"アカデミー.*第\d+回|受賞作品が決定|講師.*派遣|事前学習|事後学習")

for post in posts:
    if not _INCLUDE_RE.search(title): continue   # 非イベント除外
    if _EXCLUDE_RE.search(title):    continue   # 明示除外
    event = fetch_and_parse(post["link"])        # ここで初めて HTTP fetch
```

**教訓：** 投稿数が多い（50+）のに真のイベントが少ないソースは、**詳細ページ fetch 前に API 取得タイトルだけで 2 段階 INCLUDE/EXCLUDE フィルタ**を入れる。フィルタ条件は `scraper/__doc__` または docstring に記録しておくこと。

### C — 複数形式混在ソースの日付 cascade（5 段階）

**問題：** シンポジウム（`日時　2025年7月19日`）・ツアー募集（`（2026年2月25日`）・コンテスト（`締切：2026年11月13日`）で日付の文脈が異なる。単一パターンでは取れない。

**設計（優先順位付き cascade）：**
1. `日時[　\s：:]*YYYY年M月D日` — シンポジウム系イベント開催日
2. `[（(]YYYY年M月D日` — ツアー開始日（括弧内）
3. `締切[：:]\s*YYYY年M月D日` — コンテスト締切（開催日代理）
4. 本文中最初の `YYYY年M月D日`
5. WP publish date（最終フォールバック）

**教訓：** 同一ソース内で「開催日・ツアー出発日・締切日」が混在する場合、1 つの正規表現でまとめようとせず **優先順位を明示した cascade** にする。SKILL.md に「イベント日付 cascade テンプレート」として汎用化済み。

---

## 2026-05-11 — SC→TC 偵測/修復不一致 + `fix_simplified()` 掃描範圍不足

### A — `SC_ONLY` 假陽性 + `_SIMP_TO_TRAD_RAW` 缺映射（commit `aa24400`）

**問題：** `_detect_simplified_chinese()` 的 `SC_ONLY` 集合含 4 個假陽性字元（征/蹈/零/蒙——SC/TC 共用字），導致正常 TC 文本被誤報為含 SC。同時 `_SIMP_TO_TRAD_RAW` 缺 3 個映射（见→見、从→從、库→庫），`fix_simplified()` 無法修復真正的 SC 字元，造成無限 dismiss→reappear 循環。

**修正：**
1. 移除 `SC_ONLY` 中 4 個假陽性：征、蹈、零、蒙
2. 新增 3 個映射到 `_SIMP_TO_TRAD_RAW`：见→見、从→從、库→庫
3. Data fix：2 筆 gguide_tv 事件 `description_zh`（智库→智庫、见解→見解）
4. Dismissed 7 筆 stale pending 報告

**教訓：**
- **SC_ONLY 字元驗證規則**：加入前必須確認該字元在 TC 中**不存在或字形不同**。共用字元（征=征伐、蹈=舞蹈、零=零、蒙=蒙古）不可加入 SC_ONLY。
- **偵測與修復字元集必須同步**：從 `_SIMP_TO_TRAD_RAW` 的 keys 衍生 `SC_ONLY`，或至少確保 `SC_ONLY ⊆ _SIMP_TO_TRAD_RAW.keys()`。

### B — `fix_simplified()` 僅掃描 2 個欄位（commit `f7790a2`）

**問題：** `fix_simplified()` 僅修復 `name_zh` 和 `description_zh`，但 `_detect_simplified_chinese()` 掃描全部 6 個 `_zh` 欄位。`location_name_zh`、`location_address_zh`、`business_hours_zh`、`organizer_zh` 中的 SC 字元被偵測到但無法自動修復。

**修正：** `fix_simplified()` 擴展到掃描全部 6 個 `_zh` 欄位。

**教訓：** 偵測範圍與修復範圍必須完全一致。每次擴展偵測範圍時，同步擴展修復範圍。

---

## 2026-05-11 — `_lock_fields_via_corrections()` 缺 SC→TC guard 導致 SC 永久鎖定

**問題（commit `f7790a2`）：** `_lock_fields_via_corrections()` 使用 `str(fvalue)` 寫入 FC 表，未經 `_to_trad()` 轉換。backfill 腳本將日文漢字複製到 `organizer_zh` 時（kanji copy），日文漢字（`会`=SC `会`）被永久鎖入 FC，annotator P1 保護阻止後續修正。39 筆事件 `organizer_zh` 受影響。

**修正：** `_lock_fields_via_corrections()` 對 field name 以 `_zh` 結尾的值自動呼叫 `_to_trad()` 後再寫入 FC。13 筆 taiwan_prism `location_name_zh` + 2 筆 inactive `name_zh` + 39 筆 `organizer_zh` 批量修正。

**教訓：** `field_corrections` 表是資料的永久閘門。任何寫入 FC 的路徑（`_lock_fields_via_corrections()`、手動 upsert、backfill 腳本）都必須對 `_zh` 欄位過 `_to_trad()`，否則 SC 值一旦進入便永久免疫於自動修復。

---

## 2026-05-10 — ftip.py `source_url` vs `official_url` 分離修正

**問題（commit `7c34788`）：** 先前修正（`ab771e2`）讓 `_OFFICIAL_URL_RE` 提取的官方 URL 直接覆寫了 `source_url`，導致 FTIP 聚合站 URL audit trail 遺失。事件 `023dcbec` 的 `source_url` 被改為 `www.taiwanprism.com`，ftip-japan.org 溯源連結中斷。

**修正：**
- `source_url` = 永遠是 FTIP RSS 項目 URL（`https://www.ftip-japan.org/NNN`）— 聚合站次要連結保留
- `official_url` = 提取的第一方主辦方 URL（活動官網、Facebook event 頁等）
- DB 事件 `023dcbec` 手動修正：`source_url=ftip-japan.org/699`、`official_url=taiwanprism.com`，FC×2 鎖定

**教訓：** 聚合站 scraper（ftip、prtimes、gnews、walkerplus）的 `source_url` 必須**永遠保留**聚合站自身的 URL；提取的第一方 URL 存入 `official_url`。`source_url` 的語義是「我從哪裡找到此資料」，覆寫它等同破壞 Second-hand Source URL Guard。SKILL.md 的「RSS 聚合站」section 已同步修正。

---

## 2026-05-10 — note_creators レポート記事の三重問題パターン

**問題（event `a7a05be6`、台湾薬膳文化体験レポート）：** note_creators 來源的レポート記事存在三個固定問題：

1. **`start_date` = 記事公開日（2026-05-08）**：實際活動日期為 2026-04-21（相差 17 天）
2. **`location` = 主催者の日本拠点**（台湾華語文学習センター大阪弁天町）：實際為台灣場地（台北医学大学）；`location_address` / `location_prefectures` 需設 null（活動在台灣，非日本）
3. **接頭辭缺失 + `report` category 缺失**：需加 `【レポート】`/`【活動報導】`/`[Report]` 前綴

**修正：** 9 個 FC 鎖定（start_date、location_name、location_address、location_prefectures、name_ja、name_zh、name_en、categories）

**後續自動化（commit `1e00933`）：** annotator.py 的 `_REPORT_TRIGGER_RE` 自動注入 `report` category + 三語接頭辭；但 **`start_date`（記事日 ≠ 活動日）** と **`location`（主催者拠点 ≠ 活動場所）** の修正は依然として人工必須。

---

## 2026-05-10 — TaiwanPrism scraper 三重 bug（null byte + organizer_type + parent_event_id）

**問題（commits `a3d67fc`, `c7e9b73`）：** 新建的 `taiwan_prism.py` scraper dry-run 成功但 DB 寫入失敗，出現三個獨立 bug：

**Bug 1 — `\u0000` null byte（Postgres `22P05`）：**
- 根因：speaker 清單中含 `×\u0000栖来ひかり`（`×` 為 Unicode cross mark，後接 null byte），直接拼入 `description_ja`。
- 修正：在 speakers join 後立即 `.replace("\x00", "")`，清除源頭。

**Bug 2 — `organizer_type=["npo"]`（check constraint violation）：**
- 根因：`npo` 不在 DB 允許清單；正確值為 `civic_group`。
- 修正：兩處（父事件 + 子事件）改為 `["civic_group"]`。

**Bug 3 — `parent_event_id=f"taiwan_prism_{year}"`（`22P02` uuid 語法錯誤）：**
- 根因：`parent_event_id` 欄位型別為 `uuid`，不能傳 source_id 字串。
- 修正：改用 `get_event_id_by_source(SOURCE_NAME, parent_source_id)` 查真實 UUID；首次執行因父事件尚未入庫而回傳 `None`，第二次起正確解析。首次執行後手動 patch 12 筆子事件 `parent_event_id`。

**教訓：**
1. `parent_event_id` 必須是 DB UUID，不可傳 source_id；需在 `scrape()` 中 import `database.get_event_id_by_source` 解析。
2. 任何 scraper 在寫入 `raw_description` 之前，必須對所有外部文字 `.replace("\x00", "")` 防護。
3. `organizer_type` 只允許 8 個值；NPO 型組織統一使用 `civic_group`。

---

## 2026-05-10 — Peatix scraper `_extract_peatix_dates` 缺 return 靜默丟棄事件

**問題（commit `2a9540c`）：** Peatix 連續 7 天 0 新事件。原因不明，無任何 ERROR log。

**根因：** `_extract_peatix_dates()` 在事件有日期但無時間範圍時，`if`-`else` 所有分支執行完畢後直接 fall-through，隱式返回 `None`。呼叫端嘗試 unpack `None`（`start, end = ...`），拋出 `TypeError: cannot unpack non-iterable NoneType object`，該頁面的所有事件被靜默丟棄。

**修正：** 新增明確 `return start, None` 確保所有路徑都有回傳值。

**教訓：** 拆解日期的 helper 函式必須有 exhaustive return path。任何 `if/elif/else` 的 date-parser 函式都應加 `assert False, "unreachable"` 或明確 `return None, None` 作為 fallback，防止隱式 `None` 傳播造成靜默丟棄。

---

## 2026-05-10 — ftip.py `start_date` 回退 / `source_url` 指向聚合站 / `location_address` 硬編碼

### A — `M/D~D` 範圍未識別 → start_date 落到 pubDate（commit `ab771e2`）

**問題：** 事件 `023dcbec`（台湾光譜 taiwan prism）`start_date` 為文章發布日，因為 `8/30~31` 模式未被任何 DATE_PATTERNS 匹配。
**根因：** `ftip.py` 僅有 `M/D` 全日期 patterns，無 `M/D~D` 多日範圍的結束日提取。`~D` 後的數字被忽略，start_date 靜默回退到 RSS pubDate。
**修正：** 新增 `DATE_PATTERNS[4]`（`M/D` fallback）+ `_END_DAY_RE`（提取 `M/D~D` 的結束日，附 `(?![/])` 跨月防護）。
**教訓：** 凡含 `~` 的日期字串（`8/30~31`）應同時解析 start 和 end。若 `~` 後接 `/`（跨月，如 `3/10~5/31`），不提取 end_date 以防假匹配。

### B — `source_url` 指向聚合站而非官方站

**問題：** `source_url = "ftip-japan.org/..."` — 但 raw_description 已明確標示 `公式サイト www.taiwanprism.com`。
**根因：** scraper 直接把 RSS 的 `<link>` 存為 source_url，未嘗試提取 `公式サイト` URL。
**修正：** 新增 `_OFFICIAL_URL_RE`，從 content 提取 `公式サイト www.xxx.com` 或 `公式サイト https://...`，優先作為 `source_url`。
**教訓：** RSS 聚合站 scraper（如 FTIP）應優先提取 `公式サイト` URL 作為 `source_url`；僅當不存在時才使用 RSS link。此為**通用模式**，不限於 ftip。

### C — `location_address` 硬編碼為 `東京都`

**問題：** 台湾光譜活動實際在京都（`〒603-8163 京都府...`），但 `location_address` 被寫死為 `"東京都"`。
**根因：** ftip.py 使用 `location_address = "東京都"` 作為全組織 fallback，錯誤假設所有活動都在東京。
**修正：** 新增 `_VENUE_NAME_RE` / `_VENUE_ADDR_RE` 從 `会場は VENUE（...）` 模式提取真實場地與地址；無法提取時 `location_address = None`。
**教訓：** 以城市名（`東京都`、`大阪`）作為全國性組織的 `location_address` fallback 是反模式——GPT 會信任它並造成錯誤標注。未知時必須設 `None`。

---

## 2026-05-08 — SC→TC 映射表缺字靜默通過 + organizer 多語言欄位新增

### A — `_SIMP_TO_TRAD_RAW` 缺 9 字（commit `95b79ef`）

**問題：** GPT-4o-mini 輸出含 `诗`/`禅`/`图`/`猎`/`过`/`员`/`剧`/`别`/`于`，`_to_trad()` 無法轉換，SC 字直接寫入 DB `description_zh` 和 `selection_reason`。
**根因：** `_SIMP_TO_TRAD_RAW`（292 筆）手動維護不完整，每次 GPT 用到新 SC 字就靜默通過。
**修正：** 新增 9 字 + 3 筆活躍事件 DB 修正 + FC 鎖定。
**教訓：** 映射表方式是打地鼠（表已從 ~50 成長到 300+ 筆仍不完整）。長期應考慮 OpenCC 等完整 SC→TC 庫。每次新增字後必須同步更新 `auto_qa.py` 的 `SIMP_RE`。

### B — `organizer_zh` / `organizer_en` 多語言欄位（migration 059, commit `95c7ad8`）

**問題：** 日文 organizer 名稱直接顯示在 zh/en 頁面。
**修正：** annotator.py 新增 `_KNOWN_ORGANIZER_MAP`（10 筆高頻主辦方） + GPT 翻譯邏輯 + 子事件繼承 organizer_zh/en。scraper infra（base.py + database.py）同步更新。
**教訓：** 文字欄位多語言化已成標準流程：KNOWN_MAP → kanji copy → GPT batch。`_KNOWN_ORGANIZER_MAP` 設計模式同 `_KNOWN_PERSON_MAP`，高頻主辦方必須 hardcode 確保翻譯品質。

---

## 2026-05-08 — 湾.味(ワンウェイ) organizer 污染 + performer job title 假陽性

**Error:** 事件 `fe03288b` / `b8621ee9`（台湾料理体験会 1部・2部）出現兩類問題：
1. `organizer` hallucinated 為 `語学スクール`（真實主辦方：湾.味(ワンウェイ)）
2. `organizer_zh` / `organizer_en` 被另一個完全不同事件（上田村振興会・普門寺）的 `field_corrections` 資料污染
3. `performer = シェフ`（職稱，非人名）→ 應為 null

**Root cause:**
1. GPT 在 organizer Non-Hallucination Guard 不足時，從 few-shot context 中其他事件的資料推斷 organizer（few-shot pollution 模式）。
2. `organizer_zh`/`organizer_en` 欄位內容來自不同事件的 FC 表格——跨事件 FC 污染，`annotation_status = annotated` 不觸發重新驗證，無法自動偵測。
3. `_extract_performer_from_raw` 未過濾純職稱（`シェフ`/`講師`/`先生` 等），job title 被誤認為人名。

**Fix:** 8 筆 `field_corrections` 鎖定（兩件事各 4 欄）；`performer` 設 null；`organizer_zh/en` 更正後鎖定。

**Lesson:**
1. **Performer Job Title Guard**：`performer` 只能填人名，不能填職稱（`シェフ`、`講師`、`先生`、`料理人` 等）。regex 應使用 negative filter 過濾純職稱。
2. **FC 跨事件污染偵測**：若 `organizer_zh`/`organizer_en` 含有在 `raw_title + raw_description` 中找不到的內容，即為 FC 污染。偵測指令：`SELECT id, organizer_zh FROM events WHERE organizer_zh IS NOT NULL AND raw_description NOT ILIKE '%' || split_part(organizer_zh, ' ', 1) || '%'`。
3. **few-shot pollution**：GPT 從 few-shot examples 的其他事件推斷欄位。annotator 的 Non-Hallucination Guard 在 organizer 文本極短（< 2 字）時效果有限；thin content 事件 organizer 應設 null。

---

## 2026-05-08 — WhitestoneGallery 新 scraper + ZERO_EVENT_OK_SOURCES 模式確立

**Event:** 新增 `whitestone_gallery.py`（Whitestone Gallery Ginza / Karuizawa，台灣藝術家展覽）。

**Design decisions:**
- 爬取 `/tagged/current` 靜態 HTML listing，不需 JS
- 過濾日本地點（Ginza、Karuizawa、Tokyo）
- 在 detail page main content 中檢查台灣關鍵字（避免 footer country dropdown 假陽性）
- `source_id = whitestone_gallery_{url-slug}`
- 0 events 是正常結果（台灣藝術家展覽為偶發性），加入 `ZERO_EVENT_OK_SOURCES`

**Lesson:**
- **ZERO_EVENT_OK_SOURCES 模式**：定期舉辦但大多時候無台灣相關活動的場館（藝廊、部分影院），應加入 `health_check.py` 的 `ZERO_EVENT_OK_SOURCES`，避免每日 CI 觸發假警告。加入標準：(a) scraper 邏輯正確；(b) 台灣內容為偶發性（年 0–3 次）；(c) 0 events 是預期行為。
- 0 events 且未在 `ZERO_EVENT_OK_SOURCES` → health check 觸發「missing」警告，每次 CI 都需人工確認 → 雜訊過多。

---

## 2026-05-08 — note_creators 薄文本：organizer hallucination + 非活動文章入庫（commit b589fbb）

**Error:** `note_creators` 來源的 4 個事件出現問題：(1) `name_ja` 為部落格文章標題（如 `大阪で開催される無料の映画上映イベント`），非活動名稱；(2) `organizer='埼玉県日台親善協会'`（note 發文者，非主辦方）；(3) 2 件純介紹文章/觀影心得報導被識別為活動，應 `is_active=false`。

**Root cause:** `note_creators` 的 `raw_description` 通常只有「続きをみる」截斷文字（< 50 字）。GPT 在無法從 raw_description 識別主辦方時，從 note 發文者背景知識推斷 organizer。Non-Hallucination Guard 在文本極短時保護有限。`_HEADLINE_REWRITE_SOURCES` 未包含 `note_creators`，故 raw_title（文章標題）直接被用作 `name_ja`。

**Fix (commit b589fbb):**
- `note_creators` 加入 `_HEADLINE_REWRITE_SOURCES`（GPT 可改寫 name_ja）
- 4 件 DB 修正 + `field_corrections` 鎖定
- `4180ad0f`（台灣電影介紹文）、`4ebc8a35`（觀影心得報導）設 `is_active=false`

**Lesson:**
1. `note_creators` 等部落格來源 `raw_description` 通常只有截斷文字 → organizer 必然為 null，不可從 note 發文者推斷。
2. 純介紹文章（標題含「おすすめ」「紹介」等）與觀影心得報導不是活動資料 → `is_active=false`。
3. `_HEADLINE_REWRITE_SOURCES` 必須包含所有部落格/聚合類來源（`note_creators`、`note.com` 等）。

---

## 2026-05-08 — news headline 標題未改寫 + 學術場次識別碼（commit 47f8184）

**Error:** `e166878a`（gnews）：`name_ja='日本の植民地支配へ抵抗描く 台湾映画 17日那覇で上映会'`（新聞標題，非活動名稱）。`12e375da`（taiwanshi）：`name_ja='第1報告'`（學術會議場次識別碼，非發表題目）。

**Root cause:** (1) `_HEADLINE_REWRITE_SOURCES` 未完整涵蓋所有新聞/聚合來源，gnews 事件的 raw_title 直接被用作 `name_ja`。(2) 學術會議的場次識別碼（`第N報告`/`基調講演`/`招待講演` 等）沒有對應的 `_SLOT_TITLE_RE` 偵測，未觸發改寫邏輯。

**Fix (commit 47f8184):**
- `_HEADLINE_REWRITE_SOURCES` 常數正式涵蓋 `gnews`/`nhk`/`prtimes`/`walkerplus`
- `_SLOT_TITLE_RE` 正規表示式偵測學術場次識別碼
- SYSTEM_PROMPT 加 NEWS HEADLINE REWRITE RULE + ACADEMIC SLOT REWRITE RULE

**Lesson:** 新聞標題是記者寫作，不是活動名稱。學術會議的「第N報告」是場次識別碼，不是論文題目。新增來源時，凡是 raw_title 非活動正式名稱的來源，都必須加入 `_HEADLINE_REWRITE_SOURCES`。

---

## 2026-05-08 — MUKAE_RE 缺少 をゲストに迎え，一青窈未被捕捉（commit 6c2f1ab）

**Error:** `一青窈氏をゲストに迎え` 無法被 `_MUKAE_RE` 捕捉，performer 返回 null。`をゲストに迎え` 是日式正式邀嘉賓慣用語，與 `をお迎え`/`を迎え` 語義相同，但不在 lookahead 清單中。

**Root cause:** `_MUKAE_RE` lookahead 只列舉 `をお?迎え|による|が登壇|がトーク|にご登場`，缺少 `をゲストに迎え`。

**Fix (commit 6c2f1ab):** Lookahead 加入 `をゲストに迎え`：`(?:をお?迎え|をゲストに迎え|による|が登壇|がトーク|にご登場)`。

**DB impact:** 受影響事件 e0521671（ようこそ物語の島へ）、1d741522（絵本朗読×トーク），以 DB 手動設定 `performer='林廉恩、一青窈'` + `field_corrections` 鎖定。

**Lesson:** MUKAE lookahead 必須涵蓋所有「邀請演出者」語義的日語慣用語：`をお迎え`、`を迎え`、`をゲストに迎え` 三者缺一不可。每次新增邀嘉賓用語時，同步補全。

---
## 2026-05-08 — PERFORMER_INTRO_RE separator `+` 導致 絵本作家林廉恩 無法捕捉（commit fe8b273）

**Error:** `絵本作家林廉恩氏` 無法被 `_PERFORMER_INTRO_RE` 捕捉。`作家` 在 role list 中，但 `[・：:\s]+`（1+ 個分隔符必填）阻斷了角色與名字直接連接的寫法。

**Root cause:** separator `[・：:\s]+` 要求至少 1 個分隔符，而 `絵本作家林廉恩` 角色詞與人名直連（無任何分隔符）。MUKAE 路徑也無法命中（缺 `をゲストに迎え` 且不含 `と` 連接結構）。

**Fix (commit fe8b273):** `[・：:\s]+` → `[・：:\s]*`（separator 改為 optional，0 個或多個）。

**DB impact:** Event e0521671（ようこそ物語の島へ）文本為 `作家の林廉恩氏`（`の` 不在 `*` 範圍），仍以 DB 手動修正 + lock 處理。Event 1d741522 同上。

**Lesson:** 日語中角色詞與人名直接連接是常見寫法（如 `絵本作家林廉恩`、`料理人鈴木一郎`）。`_PERFORMER_INTRO_RE` separator 必須用 `*`，而非 `+`，否則直連寫法靜默失敗。Sanity check 三種情況：直連、點號分隔（`・`）、冒號分隔（`：`/`:`）均應命中。

---
## 2026-05-08 — performer regex 假陽性：INTRO `{2,6}` + MUKAE 缺 lookbehind

**Error:** `_PERFORMER_INTRO_RE` 在 `歌手・翻訳者一青窈氏による` 中擷取出 `翻訳者一青窈`（6 字）。`_MUKAE_RE` 則從 `訳者一青窈氏による` 中間開始匹配出 `訳者一青窈`。兩者均為假陽性，真實姓名為 `一青窈`（3 字）。

**Root cause:** (1) `{2,6}` 上限過寬——role 詞（`翻訳者`=3 字）+ 真名（`一青窈`=3 字）共 6 字符合上限。(2) `_MUKAE_RE` 無 negative lookbehind，從字串中間任意位置開始匹配。

**Fix (本 commit):**
- INTRO + MUKAE：max 6 → 5，防止 6 字 role+name 組合被捕獲
- MUKAE：加入 `(?<![一-鿿])` negative lookbehind
- INTRO：role list 新增 `翻訳者`

**DB impact:** 215 筆 null-performer 事件掃描後，4 筆命中。INTRO 命中 2 筆（真陽性）已鎖 field_corrections；MUKAE 命中 2 筆（多人講者）保持 null。

## 2026-05-08 — bookandbeer: server-side keyword param silently ignored + author bio false positives

**Error:** `bookandbeer.py` の初版は `?keyword=台湾` URL パラメータを頼りにしていたが、bookandbeer.com サーバーはこのパラメータを完全に無視し全件返却。結果として多数の非台湾関連イベントが DB に登録された。さらに、著者略歴に「台湾大学 客員教授」「淡江大学」という記述があるだけで `_is_taiwan_relevant()` が True を返す問題があった。

**Fix (commits 7df9f56, e1ab468):**
1. keyword param をドキュメントコメントにだけ残し、クライアントサイドの `_is_taiwan_relevant()` を追加。
2. `_AUTHOR_BIO_RE` で大学名マッチングを除外。
3. タイトル優先 + description 冒頭 500 字で ≥ 2 matches + 大学名除去後も keyword 残存の三段ロジック。

**Lesson:** Before relying on a URL keyword parameter, empirically verify it filters — request with vs without keyword and compare response counts. Also, author biographies are NOT event content; always strip them before counting Taiwan occurrences.

---

## 2026-05-08 — tokyoartbeat: Contentful placeholder dates use entire January (month == 1, not day == 1)

**Error:** `tokyoartbeat.py` の Contentful 佔位符ガードが `start_date.day == 1` だったため、`2026-01-15` の佔位符日付 (events `977da793`, `e7cf2a51`) を見逃した。Contentful は財年未定の系列展に `YYYY-01-xx`（1 月いっぱい）を使う。

**Fix (commit 7df9f56):** ガード条件を `start_date.month == 1` に変更。DB events `977da793` と `e7cf2a51` を直接修正。

**Lesson:** Contentful 佔位符は Jan 1 限定ではない。整 1 月が佔位符として使われる可能性を常に考慮し、`month == 1` でガードする。

---

## 2026-05-07 — google_news_rss: RSS snippet used as start_date fallback when article fetch fails

**Error:** `google_news_rss.py` は article_text の取得に失敗した場合、RSS description snippet を fallback として `_extract_start_date(description_plain, pub_date)` に渡していた。snippet は通常 200 字未満で年月日情報が不完全なため、annotator が誤った start_date を推定していた。

**Fix (commit 1c0f69a):**
```python
start_date = _extract_start_date(article_text, pub_date) if article_text else None
```
article_text が None の場合は start_date も None にし、annotator の universal year-anchor に委ねる。

**Lesson:** RSS snippets are marketing truncations, not structured event data. Never use them for date extraction. If the full article is unavailable, set start_date = None.

---
## 2026-05-05 — artistcafe: auto-generated scraper had no Taiwan filter + wrong description selector

**Error:** `artistcafe.py` は `?keyword=台湾` URL パラメータを使っていたが、artistcafe.jp はこのパラメータを無視しサイト全体のイベントを返す。結果として 12 件中 8 件（後に 14/17 件と判明）が台湾無関係のイベントとして DB に登録された。また `raw_description` に `body.inner_text()` を使っていたため、ナビゲーションヘッダー（`OPEN 11:00 - 19:00 アクセス …`）が格納されていた。

**Root cause:** auto-generated scraper はサイトが keyword 検索をサポートすると仮定したが、実際には client-side でもなく完全に無視されていた。詳細ページ取得に `article` セレクターではなく `body` を使っていたため、コンテンツが汚染された。

**Fix:**
1. `SEARCH_KEYWORD` と `?keyword=` URL パラメータを削除
2. `_TAIWAN_KEYWORDS` + `_is_taiwan()` 関数を追加
3. 詳細ページ取得で `article` セレクター優先、fallback `body`
4. `_is_taiwan()` チェックをイベント作成前に追加（非台湾はスキップ）
5. DB の非台湾イベント 14 件を `is_active=false` に更新

**Result:** dry-run で 12 件→4 件（台湾関連のみ）に正常フィルタリング。

**Lesson:** auto-generated scraper の `?keyword=` フィルターは必ずローカルで検証すること。「keyword あり」と「keyword なし」の URL を両方試して返件数が同じなら、サイトがパラメータを無視している。その場合は `_is_taiwan()` をスクレイパー内に実装する。

---
## 2026-05-05 — 24 scrapers lost in SCRAPERS when 045d1fa rewrote main.py [multiple]

**Error:** Commit `045d1fa`（add WasedaIclScraper）で `main.py` が書き直され、既存の 24 個の scraper が import と SCRAPERS から消えた。同日に `8a9dcd7` で ArtistcafeScraper を追加したが audit を実行せず、24 個の欠落は発見されなかった。

**Affected scrapers (24):** LivepocketScraper, FukuokaNowScraper, PrtimesScraper, MaruhiroScraper, EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper, CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper, GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper, MotScraper, TransitStoreScraper, GoTaiwanScraper, TaiwanFestaScraper, TiffJpScraper, RightscubeScraper

**Fix:** 24 個の import + SCRAPERS エントリを復元（commit `6a83c64`）。audit で 66 scrapers 確認。

**Detection:** `grep -i "shin_bungeiza" scraper/main.py` が exit 1 → 手動調査 → audit で 24 個の UNREGISTERED 判明。

**Lesson:** `main.py` を ANY 理由で編集した後は、必ず SCRAPERS audit を実行。特に「新しい scraper を 1 個追加」する際に既存のリストを書き直すと、既存のすべての登録が消えるリスクがある。

---
## 2026-05-05 — ArtistcafeScraper: ファイル存在・POC完了・commit済みなのに SCRAPERS 未登録で 3 日間無視された

**Error:** `scraper/sources/artistcafe.py` はファイルとして存在し、feature branch にも commit されていたが、`main.py` への `import` と `SCRAPERS` 登録が一度も実施されなかった。CI は 3 日以上この scraper を完全に無視した。

**Root cause:** 「POC 完成 → spec を parked → feature branch に commit」という flow で、「import + SCRAPERS 登録」ステップが別タスクに先送りされ、そのまま見落とされた。spec に「Phase 1: import + SCRAPERS 追加」と書いてあったが、実行されなかった。

**Fix:** `from sources.artistcafe import ArtistcafeScraper` と `ArtistcafeScraper()` を同一コミット（`8a9dcd7`）で追加。dry-run で 12 events 確認。

**Lesson:** scraper ファイルと `main.py` への登録は **atomic** でなければならない。spec の「次のステップ」として書いた時点で、すでに登録漏れのリスクがある。POC → spec parked → 後で登録、というパターンは禁止。

**Protocol fix:** agent.md Phase 5 と SKILL.md Documentation Protocol の両方に、コミット前に確認すべき numbered checklist（import・SCRAPERS・per-source SKILL・history・DB）を追加。ファイルの存在だけでなく、登録の完了を明示的に確認するまで commit しない。

---
## 2026-05-04 — hakusuisha body text 截斷 + `開催日時:` 前綴誤匹配（commit `a0292a2`）

**問題**：`scraper/sources/hakusuisha.py` 詳情頁的 `location_name`、`business_hours`、`organizer` 全部為 `null`。

**根本原因（兩個 bug）**：

**Bug 1 — body text 截斷**：Playwright `body.inner_text()[:4000]` 與 HTTP fallback `[:4000]` 截斷，導航列（nav menu）佔去大量字元，把 `■日時：` 推到截斷點之後，導致日時/会場/主催 label 全部被截掉。

**Bug 2a — 缺少 会場:/主催: 提取邏輯**：auto-generated scraper 只有日期提取，沒有 `会場:`/`主催:` regex，`_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE` 都不存在。

**Bug 2b — `開催日時:` 前綴誤匹配（最重要）**：scraper 自身在 `raw_description` 開頭加了 `開催日時: 2026年4月26日\n\n` 前綴。之後用 `_JITSU_RE.search(full_description)` 找 `日時:` 時，**先匹配到此前綴**（`開催日時:` 包含 `日時:`），group(1) = `2026年4月26日`（無時間），`_TIME_RE` 永遠找不到時間。

**修正**：
- Bug 1：截斷上限提高至 8000 字元
- Bug 2a：新增 `_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE`，在 `_extract_cards()` 末段提取 location / hours / organizer
- Bug 2b：改為直接 `_TIME_RE.search(full_description)` 繞過前綴問題

**教訓**：
- auto-generated scraper body text 上限 4000 不夠，nav/header 噪音吃掉預算；**最低建議 8000 字元**
- **Self-injected Prefix Interference**：scraper 自加的前綴（如 `開催日時:`）若包含 field label 關鍵字，後續 regex 的 `re.search()` 會先匹配前綴而非正文；解法是在加前綴前完成提取，或用更具體的 pattern（如 `_TIME_RE`）直接搜索全文

---
## 2026-05-04 — `scraper_runs` source 名查詢陷阱：`_scraper_key()` 轉換規則

**Error:** 調查「未執行的 6 個爬蟲」時，用 `cinemarine`、`moonromantic`、`tiff`、`tokyoartbeat` 等 class 前綴查詢 `scraper_runs.source`，全部回傳 NO RUNS FOUND，誤判為未執行。

**Root cause:** `scraper_runs.source` 儲存的是 `_scraper_key()` 的輸出，規則是把 class name 的 CamelCase 邊界加底線並轉小寫：`CineMarineScraper → cine_marine`、`MoonRomanticScraper → moon_romantic`、`TiffJpScraper → tiff_jp`、`TokyoArtBeatScraper → tokyo_art_beat`。手動輸入時省略底線或 suffix 就會對不到任何記錄。

**Fix:** 查詢前執行：
```bash
cd scraper && python3 -c "
import sys; sys.path.insert(0, '.')
from main import SCRAPERS, _scraper_key
for s in SCRAPERS:
    print(_scraper_key(s))
" | sort
```
找到精確 key 名後再查 DB。

**Lesson:** 永遠不要從記憶中猜測 `scraper_runs.source` 的 key — 必須從 `_scraper_key(scraper)` 輸出取得正確名稱。常見陷阱：含縮寫（`Jp`→`_jp`）、多字複合（`ArtBeat`→`art_beat`）、連寫縮寫（`Ssff`→`ssff`，但 `TaipeiTCC`→`taipei_t_c_c`）。

---
## 2026-05-04 — `scraper_runs.notes` 現在記錄例外類型與訊息（commit `7e9f617`）

**Change:** `main.py` 的 scraper 失敗處理改為：`"notes": f"{type(exc).__name__}: {exc}"[:500]`

**Before:** `scraper_runs.notes` 在失敗時為 `None` 或空字串，無法從 DB 判斷失敗原因。

**After:** `notes` 欄位現在包含例如 `"PlaywrightTimeoutError: Timeout 30000ms exceeded."` 或 `"AttributeError: 'NoneType' object has no attribute 'get_text'"`，直接從 DB 就能診斷，不需再翻 CI log。

**Lesson:** 調查失敗 scraper 時，先查 `scraper_runs.notes`：
```python
sb.table('scraper_runs').select('ran_at,notes').eq('source','<key>').eq('success', False).order('ran_at',desc=True).limit(5).execute()
```

---
## 2026-05-04 — gguide_tv schedule 解析缺 separator、hakusuisha 相對路徑 URL（commits `a895e07`、`1b344f7`）

### gguide_tv schedule 文字解析缺 `separator="\n"`（commit `a895e07`）
- **問題**：`gguide_tv.py` 用 `.get_text(strip=True)` 提取排程文字，各節點文字直接拼接無分隔，時間資訊擠在一起（例：`09:00映画『…』台湾10:00映画『…』`）
- **根本原因**：BeautifulSoup `get_text()` 預設無分隔符；多行資訊應用 `separator="\n"` 換行分隔
- **修復**：改為 `get_text(separator="\n", strip=True)`
- **教訓**：任何需要保留行結構的 BeautifulSoup 文字提取，**必須**使用 `separator="\n"`；預設行為會讓連續 inline 元素的文字擠在一起，造成下游解析失敗

### hakusuisha 相對路徑 URL 未轉換為絕對路徑（commit `1b344f7`）
- **問題**：`hakusuisha.py` 詳情連結 `href="../news/n*.html"` 直接存入 `source_url`；DB 中 10 筆事件的 `source_url` 為相對路徑，點擊連結 404
- **根本原因**：`a["href"]` 對相對路徑 href 直接賦值，未處理相對 URL 轉換
- **修復**：改用 `from urllib.parse import urljoin`；`source_url = urljoin(page.url, detail_url)`；DB 中 10 筆事件直接 patch
- **教訓**：**所有 `a["href"]` 值在存入 `source_url` 前必須通過 `urljoin(base_url, href)` 轉換**，不論 href 看起來是否已是絕對路徑

---
## 2026-05-03 — ks_cinema sub-event parent_event_id UUID 型別錯誤（commit `263e333`）
- **問題**：`ks_cinema.py` sub-event 中，`parent_event_id` 被設為 source_id 字串（`"ks_cinema_taiwan-filmake"`）而非 UUID，每次 upsert 出現 `invalid input syntax for type uuid` 錯誤，CI 連續 5 天失敗（`scraper_runs.success = false`）
- **根本原因**：直接將 source_id 字串賦值給 `parent_event_id` 欄位，未透過 `get_event_id_by_source()` 查詢 DB UUID
- **修正**：改用 `get_event_id_by_source(SOURCE_NAME, f"ks_cinema_{url_slug}")` 查詢 parent UUID，與 `taiwanshi.py` 模式相同；初次執行（parent 尚未寫入 DB）回傳 `None`
- **教訓**：`parent_event_id` 是 UUID 欄位，**絕不可**直接放 source_id 字串；必須透過 `get_event_id_by_source()` 查詢，回傳 `None` 時 sub-event 不設 parent

---
## 2026-05-02（深夜 2）— tokyoartbeat venue 資料擴充、annotator scraper 優先序統一、location_url、PR Times 日期幻覺、IDE JETRO 線上活動（commits `c747484`、`eaab464`、`fb568c4`）

### tokyoartbeat venue 資料擴充（commit `c747484`）
- **問題**：`raw_description` 沒有場地資訊 → GPT 從訓練資料猜知名場館（東京都現代美術館等）→ 幻覺。
- **修復**：`_parse_event()` 從 Contentful venue linked entry 新增讀取 `openingHoursOpens`、`openingHoursCloses`、`closedDays`、`admissionFee`；組合成 `biz_hours`；`raw_description` 前綴加入結構化 header（`開催日時:`、`会場:`、`住所:`、`開場時間:`、`入場料:`）；`is_paid` 改由 `admissionFee` 數值推斷（`"0"` → False；非零數字 → True；非數字 → None）。
- **教訓**：GPT 場地幻覺的根本原因是 raw_description 沒有場地資訊。預防方法：在 raw_description prepend structured header，讓 GPT 有明確文字可抽取，而非依賴訓練資料。

### annotator scraper 優先序統一（commits `c747484` + `eaab464`）
- **問題**：annotator 對 `location_name/address`、`business_hours`、`is_paid`、`start_date`/`end_date` 都是 GPT 優先，會蓋掉 scraper 取得的正確資料。
- **修復**：翻轉上述欄位為 scraper 值優先，GPT 只補空值。翻譯欄位（name_zh/en、description_*）仍由 GPT 生成。
- **教訓**：scraper 提供的結構化資料比 GPT 從自由文字推斷的更可靠。統一原則：factual fields → scraper 優先；translation fields → GPT 生成。

### annotator location_url 條件式寫入（commit `fb568c4`）
- **問題**：`location_url` 不在 annotator `update_data` 內 → GPT 提取結果永遠丟失；若直接加入且不 null guard → 蓋掉 Admin 手填值。
- **修復**：GPT prompt schema 新增 `location_url` 欄位（指示「僅從文字提取，禁止推測」）；`update_data` 條件式寫入，僅在非 null 時才寫入。
- **教訓**：兼具 GPT 提取 + Admin 手填的欄位，寫入時**必須**加 null guard（僅在有值時寫入），否則 GPT null 輸出會蓋掉人工設定值。`location_url` 是場地官方網站，不是 Google Maps；scraper 通常無此欄位。

### name_ja_locked language note（commit `eaab464`）
- **問題**：有人以為 `name_ja_locked` 標題必須是日文（field name 含「ja」）。
- **修復**：SKILL.md 加入 Language note。
- **教訓**：`name_ja` 是欄位識別符，不是語言限制。`name_ja_locked=True` 的標題可能是中文（`台灣...`）或英文（`Taiwan...`），來源語言由活動頁面決定。不應因 field name 含「ja」就強制改為日文。

### PR Times 日期幻覺（DB fix，無 commit）
- **活動**：`e45d4022`（台湾＆沖縄フードイベント）
- **問題**：`start_date=2026-02-25`（PR Times 發布日），實際活動 `3月11日→16日` 在 raw_description 正文中。
- **根本原因**：`prtimes.py` 用文章發布日作為 `start_date`；raw_description 無 `開催日時:` header，GPT 無法從散落的日期字串正確推斷。
- **修復**：直接 DB update（`start_date=2026-03-11`、`end_date=2026-03-16`），補充 raw_description header，設 `annotation_status='reviewed'`。
- **教訓**：PR Times scraper 應嘗試從正文 regex 提取活動日期（`\d月\d+日` pattern）而非使用發布日；或在 raw_description 標記「プレスリリース発信日: YYYY年MM月DD日」以讓 GPT 區分。高風險 source：`prtimes`、`google_news_rss`、`nhk_rss`。

### IDE JETRO 線上活動 location_name=null（DB fix，無 commit）
- **活動**：`86efda2a`（オンデマンド講座）
- **問題**：`location_name=null`；GPT annotation 未識別為線上活動，前端無場地顯示。
- **修復**：直接設 `location_name='オンライン（オンデマンド）'`（含 zh/en），設 `reviewed`。
- **教訓**：線上活動 scraper 應主動判斷活動形式並設 `location_name='オンライン'`（細分：オンデマンド / ライブ配信 / ウェビナー）。Annotator SYSTEM_PROMPT 需補規則：活動明確為線上時，`location_name` 應設相應詞彙，不應留 null。

---
## 2026-05-02（下午）— デニス・リン展 場地幻覺：tokyoartbeat raw_description 缺少場地資訊

- **活動**：`1e375d6c`（デニス・リン展, source=`tokyoartbeat`）
- **問題**：網站顯示場地名稱、地址、開放時間全部錯誤。GPT 猜測場地為「東京都現代美術館，東京都江東区冬木7-2-1，10:00〜18:00」；正確為「Yukikomizutani，東京都品川区東品川1-32-8 TERRADA ART COMPLEX II 1F，12:00〜18:00（月・日・祝 休廊）」。
- **根本原因**：`raw_description` 只含英文藝術家簡介，完全沒有場地資訊（venue name、address、hours）。GPT 從訓練知識猜測知名大型美術館，對高知名度場館（東京都現代美術館、森美術館）特別容易過度自信。
- **修復**：直接呼叫 Contentful API 取得正確場地資料（`GET /entries/{event_id}` → 取得 venue link id → `GET /entries/{venue_id}`），執行 DB update 覆蓋。
- **教訓**：tokyoartbeat scraper 的 `raw_description` **必須**在開頭附加結構化場地資訊 header，否則 annotator GPT 會用訓練知識猜測並產生錯誤場地。Contentful API 提供完整欄位：`fullName`、`address`、`openingHoursOpens/Closes`、`closedDays`、`admissionFee`。格式範例：
  ```
  開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日
  会場: {fullName}
  住所: {address}
  開場時間: {openingHoursOpens}〜{openingHoursCloses}
  休廊日: {closedDays}
  入場料: {admissionFee}円（0 = 無料）
  ```

---
## 2026-05-02 — 5 件修復：HTTPAdapter retry、子活動欄位、get_event_id_by_source、health_check Check 4/5、annotator 日期覆蓋

### 修復 1：taiwanbunkasai — HTTPAdapter retry 補強
- **問題**：網路暫時性失敗（transient errors）無法重試，造成 Sentry 報警。
- **修復**：加入 `HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2, status_forcelist=[429,500,502,503,504]))`。
- **教訓**：所有 scraper 對外 HTTP 呼叫都應加 retry，尤其目標站台有限流（rate limit）的情況。

### 修復 2：taiwanshi — 子活動欄位錯誤
- **問題**：爬蟲沒有子活動解析邏輯，子活動資料被錯誤放在父活動欄位。
- **修復**：新增 `_parse_reports()` 函數與 4 個 regex；`scrape()` 建立父活動後查 UUID 再建子活動。
- **教訓**：當一個 source 頁面包含多個獨立 programme items，需在爬蟲層建立子活動（`parent_event_id`），不能全塞在父活動。

### 修復 3：database.py — 新增 `get_event_id_by_source()`
- **問題**：子活動需要查詢父活動的 UUID，但原本沒有 helper 函式。
- **修復**：新增 `get_event_id_by_source(source_name, source_id) -> str | None`。
- **教訓**：跨事件 UUID 查詢是子活動建立的必要基礎建設，應在開始撰寫含子活動邏輯的 scraper 前確認此 helper 存在。

### 修復 4：health_check.py — 新增 Check 4 & Check 5
- **Check 4**：偵測 gnews 活動有 `start_date` 但原始 description 未實際抓取文章（只有 fallback pub_date）。
- **Check 5**：偵測 tokyoartbeat 活動 DB 日期與 `source_url` 中的日期不符。
- **教訓**：日期異常很難用肉眼發現，需要系統性健康檢查（health_check.py）定期偵測。

### 修復 5：annotator 日期覆蓋問題（重要）
- **問題根因**：annotator 第 581-582 行：
  ```python
  "start_date": annotation.get("start_date") or event.get("start_date"),
  "end_date": annotation.get("end_date") or event.get("end_date"),
  ```
  手動修正 `start_date` 後，若同時把 `annotation_status` 設為 `'pending'`，annotator 重跑時 GPT 若能從 `raw_description` 找到任何日期字串（甚至是錯誤的），就會覆蓋掉手動修正的值。
- **案例**：デニス・リン展（id: `1e375d6c`）的 `raw_description` 沒有 `開催日時:` header，GPT 輸出了 `2026-01-15`（舊錯誤值），覆蓋掉了修正後的 `2026-04-10`。
- **正確修法（已驗證）**：
  1. 直接更新 `start_date`/`end_date`
  2. 同時在 `raw_description` 前面加入 `開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日\n\n` header
  3. 才能安全地設 `annotation_status='pending'` 讓 annotator 重跑
  - **或者（更安全）**：手動修正後，設 `annotation_status='annotated'`（不設 `'pending'`），讓 annotator 不再重跑。
- **教訓**：手動修正日期時，**絕對不要**單獨設 `annotation_status='pending'` 而不更新 `raw_description`。`raw_description` 的 `開催日時:` header 是防止 GPT 猜錯日期的關鍵保護機制。

---
## 2026-05-02 — CI 加入 `--enrich-person-names` 步驟（commit `85fd475`）

**問題：** `person_name_lookup.py`（eiga.com + zh.wikipedia）與 `annotator.py` 的 `enrich_person_names()` 已實作，但 CI 從未呼叫它，全 `category=movie` 活動的演職員姓名中英文補完功能形同虛設。

**修復：** `.github/workflows/scraper.yml` 在 `--enrich-movie-titles` 之後加入新步驟：
```yaml
- name: Enrich cast/crew names from eiga.com + Wikipedia
  run: python annotator.py --enrich-person-names
```

**CI 流程（更新後）：** `--fix-reviewed` → `--enrich-movie-titles` → `--enrich-person-names` → `summarize_run.py`

**教訓：** 新的 enrichment 函式實作完後，必須同步確認已加入 `scraper.yml`。已在 `scraper-expert/SKILL.md` 的 `## person_name_lookup` 區段記錄此規則。

---
## 2026-05-02 — Promotion 後 `scraper_source_name` 缺失，後台來源關聯斷裂

**問題：** auto_generate 完成、PR merge 後手動 promote 兩個來源（id=150 TIFF、id=151 台湾フェスタ），`/admin/sources` 後台顯示 0 筆活動、無法觸發 Run Scraper。

**根本原因：** promotion 流程（`status → implemented`）沒有填寫 `research_sources.scraper_source_name`。後台 API 靠此欄位 JOIN `scraper_runs` 顯示統計；auto_generate pipeline 只建立 scraper 檔案，不自動填此欄位。

**修復：** Supabase UPDATE — id=151 → `taiwan_festa`、id=150 → `tiff_jp`。

**教訓：** Promotion 最後一步必須填寫 `scraper_source_name`。已加入 SKILL.md § New Scraper Checklist (step 3)。

---
## 2026-05-02 — taiwan_festa: auto_generate 失敗（Playwright 403），改用 requests + BeautifulSoup

**問題：** auto_generate 對 `taiwanfesta.com`（WordPress/UIkit 主題）失敗——Playwright headless 返回 403，`card_selector .uk-card-default` 在渲染後 DOM 中找不到。

**根本原因：** 部分 WordPress/UIkit 網站對 headless browser 返回 403；靜態 HTML 可直接取得。

**修復：** 改用 `requests + BeautifulSoup` 手動撰寫 `scraper/sources/taiwan_festa.py`。

**教訓：** auto_generate sandbox 0 events → 立即嘗試 `requests.get()` 靜態抓取驗證。若靜態 HTML 完整，直接手寫 scraper。

---
## 2026-05-02 — TIFF: auto_generate 成功，promotion 後需修正年度 URL 與 Taiwan 過濾

**問題 1（年度 URL）：** auto_generate 產生 `BASE_URL = "https://2026.tiff-jp.net"`，每年需手動更新。**問題 2（Taiwan 過濾缺失）：** keyword 搜尋結果可能混入非台灣電影。

**修復：** 加入 `_resolve_base_url()`（follow redirect from `www.tiff-jp.net`，fallback `datetime.now().year`）+ `_TAIWAN_KW` regex 過濾器。

**教訓：** URL 含 4 位數年份的來源，promotion 時必須改為動態解析。spec 應標記「needs annual review」。

---
## 2026-05-02 — auto_generate eligibility check 未接受 `recommended` 狀態

**問題：** `generate.py` `_check_eligibility()` 只接受 `status == 'researched'`，`recommended` 來源執行 `--source-id` 時直接 abort。

**修復：** 改為接受 `('researched', 'recommended')` 兩種狀態。

**教訓：** `recommended`（GitHub Issue 已建立）是可信度最高的狀態，eligibility check 從設計時就應涵蓋。

---
## 2026-05-02 — go_taiwan.py / prtimes.py：台灣地點活動日本訪客例外（commit `012ec72`）

**問題：** `go_taiwan.py` 的 `_is_japan_event()` 和 `prtimes.py` 的台灣地點過濾把所有地點在台灣的活動都排除，導致日台交流旅遊活動（ファムトリップ、日台交流ツアー）漏掉。

**根本原因：** 過濾邏輯的目標是「只收日本活動」，但正確目標應是「收與日本受眾相關的活動」——地點在台灣但以日本訪客為目標的活動兩者判斷不同。

**修復：**
- `go_taiwan.py`：新增 `TAIWAN_FOR_JAPANESE_KW` 清單（`日本人向け`、`日本語対応`、`日本から参加`、`日本から`、`日本発`、`ファムトリップ`、`日台交流ツアー`）；`_is_japan_event()` 在 Stage 2 台灣地點判斷後加例外：含上述關鍵字則 return True。
- `prtimes.py`：`_TAIWAN_VENUE_RE.search(venue)` 過濾區塊加入同樣例外，`body_text` 或 `title` 含 `_JAPAN_VISITOR_KW` 則不 skip。
- `annotator.py`：Location Address Rule 第 6 條補充：台灣地點不強制轉換格式，保留原始台灣地址，適用 `tourism` category。

**教訓：** 台灣在地舉辦但以日本人為目標的活動（訪台旅遊、日台交流）是 Radar 核心價值之一。任何 source 若有台灣地點過濾，都應審視是否需要加日本訪客例外。

---
## 2026-05-02 — Auto-scraper Phase 2 batch e2e：6 候選 1 成功（17%）

**結果分布：**
- ✅ Artist Cafe Fukuoka（id 提供 `li.article-list` hint） → success（detail_url fallback 修復後 0→12 events）
- ❌ Zepp Tokyo（id=148）→ batch1 sandbox-failed、batch2 spec-invalid（fast-fail，selector validation 擋下）
- ❌ Fukuoka Now（id=140）→ 同上
- ❌ SSFF / Blue+ / TAP-NY → LLM 幻覺 selector + 1 站點 timeout

**根本原因：**
1. **LLM CSS selector 幻覺**（最大宗）：GPT-4o 編造看似合理但不存在的 class，如 `.event-card`、`.event-list-item`、`.c-event-list__item-title`。每次 30s Playwright + ~$0.04 浪費。
2. **Researcher 沒填 `--card-selector-hint`**：6 個只有 1 個有 hint。其餘等於把 LLM 丟進無 grounding 的猜謎題。
3. **OpenAI 月度額度耗盡**：batch 中段觸發 429 `insufficient_quota`，後續所有呼叫直接 0 美金 abort。

**修復鏈（Phase 2.1/2.2/2.3，commits `b6e1768`/`f9eff43`/`d23be68`）：**
- Phase 2.1：注入 `spec_schema.json` 進 SYSTEM_PROMPT；失敗路徑補 forensic artifacts（prompt/sample/meta）
- Phase 2.2：detail_url fallback（template 端遇到 `DETAIL_LINK_SELECTOR == ""` 抓 card 內首個 `<a href>`）；sandbox-failed 補 spec+generated+dry_run
- Phase 2.3：SYSTEM_PROMPT 加 grounding 硬規則（只准用 sample HTML 中 verbatim 出現的 class/ID，列出常見幻覺）；BeautifulSoup pre-sandbox `_validate_selectors_against_html()`（~50ms 快速失敗，省下 30s Playwright）；違規結果回灌 LLM retry 訊息

**Phase 2.4 TODO（Tester 發現）：** 失敗路徑 `meta.cost_usd` 與 `meta.retries` 都被低估為 0，需把 cost 累計移到 `finally` 區塊。

**教訓：** Researcher 的 `--card-selector-hint` 在 production 是「實質必要」而非 optional——已寫入 `researcher.agent.md`。

---
## 2026-05-02 — google_news_rss: 修正 start_date fallback to pubDate 規則（commit `9510a05`）
**修改：** scraper-expert/SKILL.md `## google_news_rss-specific` 第 2 條
**內容：**
- 舊規則「 fallback to pubDate 」已賢正為「絕對不可 fallback pubDate，返回 None」
- RSS description 總是文章摘要（不含活動日期）；pubDate = 文章發布日，跟活動日期無關
- 40 筆日期錯誤事件已下架
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — taiwan_cultural_center: 多城市巡迴活動誤錨定東京 HQ 地址（commit `a2d6eea`）

**問題：** 台湾文化センター發佈的部分活動會跨多個日本城市巡迴（如「台湾映画上映会2026」走 5 個城市）。scraper 對此 source 寫死 HQ 地址（東京港區），導致多城市巡迴活動全被打成「東京」，前台地區篩選 / 多城市顯示完全錯誤。

**修正（`scraper/sources/taiwan_cultural_center.py`）：**
- 新增 regional keyword 偵測：description 含 ≥ 2 個 `北海道|大阪|京都|神奈川|福岡|名古屋|仙台` 等地名 → 判定為多城市巡迴。
- 多城市時：`location_name = '台湾文化センター（全國巡迴）'`、`location_address = None`（清掉 HQ 地址，由 annotator/`location_prefectures` 流程聚合）。
- 單一地點時維持原本 HQ 預設行為。

**教訓：** Scraper 對單一機構錨定固定地址時（HQ pattern），必須加「多城市描述去錨定」守門。可推廣的 rule：任何 hardcoded address scraper（taiwan_cultural_center / koryu / 其他駐日機構）→ description 偵測 ≥ 2 個地區關鍵字時，清空 `location_address`、改寫 `location_name` 為「<機構>（全國巡迴）」，讓下游 annotator 透過子活動聚合 `location_prefectures`。

---
## 2026-05-01 — annotator: 多地點子活動規則 + `--id` CLI + `location_prefectures` 自動聚合

**背景：** 台東祭有東京/京都/大阪三城市各自地址，但 annotator prompt 無「多地點建子活動」規則，且無法對單一 event 強制重新標注。

**修正（`scraper/annotator.py`）：**
- Prompt rule 1 擴充：新增「3+ 個不同城市各自有地址的多地點活動，每個地點建立一個子活動」規則
- 新增 `--id <uuid>` CLI 選項：可對單一 event 強制重新標注（不限 `annotation_status`，但 `reviewed` 除外）
- 新增 `_extract_prefecture()` helper：從 `location_address` 提取都道府縣名，regex 涵蓋 北海道/東京都/大阪府・市/京都府・市/其他縣
- 子活動 loop 結束後自動計算 `location_prefectures`：≥ 2 個不同都道府縣時寫入父事件；單城市不寫入

**`location_prefectures` 欄位（Migration 012）：**
- DB 欄位：`location_prefectures text[]`（nullable）
- 由 `annotator.py` 在子活動建立後自動聚合並更新父事件
- backfill script（`scraper/backfill_location_prefectures.py`）可補填現有多城市母活動
- 前台/後台篩選加入 `location_prefectures.cs.{"X"}` OR 條件，讓多城市母活動也命中地區篩選

**教訓：**
- `_extract_prefecture()` regex 需同時覆蓋「府」省略格式：`大阪府`/`大阪市` 和 `京都府`/`京都市` 都必須納入，否則「大阪市中央区...」地址無法提取都道府縣
- `--id` 選項必須略過 `annotation_status` 檢查（除 reviewed 外），以支援重新標注已 annotated 的事件

---
## 2026-05-01 — gguide_tv: `_parse_schedule` 多行格式解析錯誤（business_hours 空白）

**問題：** bangumi.org 的 schedule_str 有兩種格式：
- 單行：`"12:00 テレ東"`
- 多行：`"23:45\n-\n0:00 歌謡ポップス"`

原本 regex 為單行設計，遇到多行格式時把 `-` 誤抓為 channel 名，且無法提取 end_time，導致 `business_hours` 欄位空白，詳細頁面無放送時間。

**修正（`scraper/sources/gguide_tv.py`）：**
- `_parse_schedule()` 回傳值從 `(datetime, channel)` 改為 `(datetime, channel, end_time_str)`
- 多行格式：開始時間從第一行 `HH:MM` 提取；結束時間與 channel 從第三行 `H:MM <channel>` 提取
- `Event()` 加入 `business_hours=business_hours`（格式：`"23:45〜0:00"`）
- DB backfill：15 個無 business_hours 的 gguide_tv 事件全數補齊

**測試結果：**
```
Test 1 (multi-line): 23:45 歌謡ポップス 0:00  ✅
Test 2 (single-line): 12:00 テレ東 None       ✅
Test 3 (midnight): 00:00 NHK-BS 0:55          ✅
```

**教訓：**
- bangumi.org schedule 格式必須區分單行（`HH:MM channel`）與多行（`HH:MM\n-\nH:MM channel`）；單行 regex 在多行格式下把 `-` 行誤判為 channel，且漏取 end_time
- 修完後立即執行 `python main.py --source gguide_tv`（非 dry-run）寫入 DB；再對舊資料做 backfill UPDATE

---
## 2026-05-01 — prtimes: 多城市活動漏建子活動（raw_description 固定截斷過早）

**問題：** `_fetch_detail()` 固定截斷 `text[:3000]`。PR 文章前半是商品介紹時，東京/大阪行程被截掉，Annotator 無法生成 sub_events。1 篇含東京（5/2）+ 大阪（5/9）兩場的 PR，只建出 1 個 Event。

**根本原因：** 固定長度截斷對「商品介紹先於活動行程」的 PR 文章失效。

**修正（commit `ecd2bb8`）：**
- 新增 `_MULTI_CITY_SECTION_RE`：偵測 `(東京|大阪|京都|...|日期)` 多城市行程模式
- 無多城市：`text[:3000]`（不變）
- 偵測到多城市：`text[:2000]` + `---[イベント開催情報]---` 分隔符 + 行程區塊 4,000 字（合計上限 8,000 字）

**驗證結果：**
- `_MULTI_CITY_SECTION_RE.search(body_text)` 成功偵測「東京｜2026年5月2日」
- raw_desc 4,312 字（vs 原本 3,000）
- Annotator 自動生成 2 個 sub_events：東京 5/2（TOKYO FAMILY RESTAURANT）、大阪 5/9（TOBI SHOP / KITTE 大阪）

**多城市子活動補建標準流程：**
1. 手動建子活動確認資料正確
2. 刪除手動建的子活動（不可保留）
3. 修正 scraper raw_description 邏輯
4. 重新抓取 + 更新 DB + 重置 `annotation_status = pending`
5. 執行 `annotator.py` → 自動生成正確 sub_events

**教訓：**
- 偵測式延長（用正則選擇性延長）比單純增大全域截斷上限更精準，不影響其他 PR 效能。
- 多城市活動的正確修正流程必須走完整五步驟；跳過「刪除手動建的子活動」會導致重複資料。

---
## 2026-05-01 — auto_qa anomaly detection writes into event_reports queue (commit `2ae731b`)

**Feature:** `scraper/auto_qa.py` scans `is_active` events from the past 14 days and inserts pending rows into `event_reports` for two anomaly types: `auto_qa_simplified_zh` (simplified chars in any `*_zh` field) and `auto_qa_missing_address` (has `location_name` but empty `location_address`; skips online/TV/zoom/youtube + `gguide_tv` source). Dedups against existing pending `auto_qa_*` rows per `event_id`. Inserts in chunks of 100. Runs 3×/day in `merger.yml` after `--fix-reviewed`. Production dry-run found 2 real findings (永旺夢乐城太田 simplified `乐`; 一石三鳥グループ missing address).

**Lesson 1 — `SIMP_RE` / `_LOC_ZH_SIMP_TO_TRAD` char addition rule:** Only add a char when its Trad/JP form is **a different glyph**. Counter-example: `亮` is identical in Trad and Simp (`照亮` is valid Traditional) — including it produced a false positive in production dry-run. Verify each candidate via CC-CEDICT or kanji.jitenon.jp before adding.

**Lesson 2 — auto-QA via shared `event_reports` queue:** New automated content-quality checks should write findings into `event_reports` with an `auto_*` prefix in `report_types[]` rather than building a separate admin queue. Admin checks one URL; the existing confirm/dismiss flow handles auto-detected and user-submitted findings the same way; `report_types text[]` supports multiple anomaly types per row.

---
## 2026-05-01 — 8 scrapers not registered in research_sources (silent CI gap)

**Error:** Architect review discovered 8 active scrapers were present in `main.py SCRAPERS` but had no corresponding row in `research_sources`. The gap was silent — no warning, no CI failure — so it accumulated undetected.

**Affected scrapers:** `prtimes`, `maruhiro`, `hankyu_umeda`, `daimaru_matsuzakaya`, `google_news_rss`, `nhk_rss`, `mot`, `transit_store`

**Root cause:** The "add new scraper" workflow had only 3 steps (create file → register in SCRAPERS → dry-run). Step 4 ("register in research_sources") did not exist in any checklist. The `research_sources` table is used by `researcher.py` to skip already-known sources, so unregistered scrapers caused the researcher to re-report them as new candidates.

**Fix:**
- Manually inserted all 8 missing rows into `research_sources` with `status='implemented'` and `scraper_source_name` set.
- Added `_warn_unregistered_scrapers()` to `main.py`: on every non-dry-run, it compares `SCRAPERS` keys against `research_sources.scraper_source_name`. Any gap emits a `⚠️ WARNING` in CI logs — immediately visible on next daily run.
- Added step 3 ("Register in research_sources") to the **New scraper checklist** in this SKILL.md.

**Lesson:** Whenever you add a scraper to `SCRAPERS`, you MUST also insert a row in `research_sources` with `status='implemented'` and `scraper_source_name=<key>`. Without this, `researcher.py` will keep re-discovering and re-reporting the same source. The CI warning added to `main.py` makes any future omission visible within 24 hours.

---
## 2026-04-29 — eurospace / tokyoartbeat: category="string" instead of category=["string"]

**Error:** `malformed array literal: "movie"` (PostgreSQL code 22P02) on upsert.
The `category` column is `text[]` in Supabase. Both `eurospace.py` and `tokyoartbeat.py`
passed a bare string (`category="movie"`, `category="art"`), causing the DB to reject it.

**Fix:** Changed to list literals: `category=["movie"]`, `category=["art"]`.

**Lesson:** `Event.category` is typed `list[str]` (see `base.py` line 30). Any scraper that
hard-codes a single category must use `["value"]` not `"value"`. Bare strings silently compile
but fail at DB write time with a cryptic PostgreSQL array literal error.

---
## 2026-04-29 — maruhiro: datetime.date vs datetime.datetime type error + 15 scrapers lost from SCRAPERS

**Part 1 — Type error in dedup_events:**
`_parse_dates` in `maruhiro.py` returned `datetime.date` objects. `dedup_events` in `base.py`
calls `.date()` on `start_date`, expecting a `datetime.datetime`. Error:
`AttributeError: 'datetime.date' object has no attribute 'date'`.
Fix: changed `_parse_dates` to return `datetime.datetime(y, m, d)` instead of `date(y, m, d)`.

**Lesson:** All scrapers must return `datetime.datetime` for `start_date`/`end_date`, not bare `date`.
`dedup_events` contract requires `.date()` to be callable on the value.

**Part 2 — 15 scrapers deleted from SCRAPERS by 7aecfef:**
SCRAPERS audit (run after implementing maruhiro) revealed 15 scrapers present in `sources/` but
absent from `SCRAPERS` in `main.py`. Root cause: commit `7aecfef` ("chore: tighten workflow guards
and restore admin filters") rewrote `main.py` and omitted the imports and registrations for:
EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper,
CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper,
ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper,
GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper.
All 15 were restored, total SCRAPERS count: 56.

**Lesson:** SCRAPERS audit must run after ANY commit touching `main.py`, not only when
adding new scrapers. Run `python3 -c "import re, glob; ..."` (see SKILL.md) before `git push`.

---
## 2026-04-29 — prtimes: 川越台湾フェア and all non-Tokyo events missed (3 bugs)

**Trigger:** User reported https://prtimes.jp/main/html/rd/p/000000015.000127081.html (丸広百貨店川越店「台湾フェア」) not captured.

**Root cause 1 — Geographic restriction in `_SEARCH_KEYWORDS`:**
All 5 keywords contained `東京` (e.g. `"台湾 イベント 東京"`). The prtimes search API
only returns articles matching the full keyword string, so articles from Saitama (川越),
Osaka, Nagoya, etc. were **never returned**. Violates the project rule: "Never restrict
geographic scope".
Fix: Removed `東京` from all keywords → `["台湾 イベント", "台湾フェア", "台湾フェス", "台湾 開催", "台湾 夜市", "台湾 祭"]`.

**Root cause 2 — `_EVENT_KW` missing `フェア`:**
`_EVENT_KW` regex did not include `フェア`. A title like「台湾フェア」would have no
_EVENT_KW match and be rejected. Fix: added `フェア` to `_EVENT_KW`.

**Root cause 3 — `_TAIWAN_BASED_TITLE_RE` false positive:**
Pattern `台湾.*?で` matched `台湾フェア」で` (a Japan-held Taiwan fair) as if the event
were held IN Taiwan, causing it to be skipped. The intended purpose was to exclude
events held inside Taiwan (not Japan). Fix: tightened the regex to require explicit
Taiwan-location context only:
- `台湾国内|現地|本島|の地.*?で`
- `in 台湾 / in Taiwan`
- `台湾出展|輸出|進出|販路|海外展示|海外販売`

**Result:** dry-run: 20 → 30 events; 川越台湾フェア now first in list.

**Lesson:**
- `_SEARCH_KEYWORDS` must NEVER contain city/region names — geographic scope is all-Japan.
- `_TAIWAN_BASED_TITLE_RE` patterns must be precise; `台湾.*?で` is too broad and matches Japan-based Taiwan fairs.
- When a PR article is missing, check: (1) search keyword geography, (2) `_EVENT_KW`, (3) `_TAIWAN_BASED_TITLE_RE`, (4) venue filter `_TAIWAN_VENUE_RE`.

---
## 2026-04-29 — movie_title_lookup + PrtimesScraper registration + FukuokaNow scope fix [multiple]

**Changes (commit 3286522):**

1. **`movie_title_lookup.py`** (NEW): `lookup_movie_titles(name_ja)` → `(name_zh, name_en)` via eiga.com search. In-memory cache `_cache`; returns `(None, None)` silently on any error. Used by 8 cinema scrapers + annotator `--enrich-movie-titles` flag.

2. **`prtimes.py` geographic filter removed**: `_SEARCH_KEYWORDS` previously included `東京` scope restriction. Removed — project scope is all of Japan. Added `フェア` to `_EVENT_KW`. `PrtimesScraper` was also NOT in `SCRAPERS` — now registered.

3. **`fukuoka_now.py` scope**: Correct from the start — no regional filter added.

**Lessons:**
- Cinema scrapers should call `lookup_movie_titles(title)` before constructing `Event()` and pass `name_zh`/`name_en`. Annotator GPT fallback still applies if `(None, None)`.
- PR TIMES keywords must NEVER include city names (e.g. `東京`) — project covers 全日本.
- Every new scraper file must be added to `SCRAPERS` in the same commit. Do not defer.

---
## 2026-04-29 — Fukuoka Now scraper implemented [fukuoka_now]

**New source**: `FukuokaNowScraper` — Fukuoka's major English-language event calendar.

**Key decisions:**
- Static HTML (WordPress) — used `requests` + BeautifulSoup, no Playwright needed
- Taiwan filter on card title + tags + short description before detail page fetch
- `_is_taiwan()` only; no false-positive guard needed (site uses "Taiwan" in actual Taiwan events only)
- Venue extracted via line-by-line keyword match (City Hall, Fureai, Tenjin, etc.) — no structured `場所:` label
- 0 events in dry-run is correct: 台湾祭 in 福岡 2026 ended Feb 23; next event not yet listed

**Lesson**: For seasonal event scrapers, 0 dry-run output is valid when the annual event is between seasons. Verify by unit-testing `_parse_detail()` on the archived event URL directly.

---
## 2026-04-29 — research_sources status not updated after scraper implementation [livepocket]

**Error:** After implementing and committing `LivepocketScraper`, the `research_sources` row (id=106) was left with `status = 'researched'` instead of `implemented`. The admin Sources table showed「已深度研究」badge and a「建立爬蟲 Issue」button — implying the scraper had NOT been built.

Additionally, `scraper_source_name` was left as `null`, so the "scraper_source_name → source mapping" used by `AdminSourcesTable` to link event counts to sources could not resolve the source.

**Fix:** Manual DB update:
```python
sb.table('research_sources').update({
    'status': 'implemented',
    'scraper_source_name': 'livepocket'
}).eq('id', 106).execute()
```

**Lesson:** The new source checklist must include **both** DB fields as a single atomic step:
- `status = 'implemented'`
- `scraper_source_name = '<source_name>'` (matches `SOURCE_NAME` constant in the scraper)

Neither field alone is sufficient. Omitting `scraper_source_name` breaks event-count display in AdminSourcesTable. This step must be done in the same session as the scraper commit — not deferred.

---
## 2026-04-29 — LivePocket scraper: wrong dl selector + class name conflict [livepocket]

**Error 1: dl selector class mismatch**
Assumed `dl` class was `event-detail-info` based on the docstring in the research profile. Actual class is `event-detail-info__list`. Additionally, `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` inside the `dl` — they are NOT direct children. Using `dt.find_next_sibling("dd")` returned nothing. All 14 events had `start_date = null` on first dry-run.

**Fix:** Changed selector to `soup.select_one("dl.event-detail-info__list")` and rewrote `_get_dd_text()` to iterate `dl.select("div.event-detail-info__block")` → `block.select_one("dt")` / `block.select_one("dd")`.

**Error 2: CamelCase class name `_scraper_key` conflict**
Named the class `LivePocketScraper`. The `_scraper_key()` function in `main.py` splits on CamelCase boundaries, producing `live_pocket` — which does NOT match `source_name = "livepocket"`. Running `--source livepocket` reported "Unknown source".

**Fix:** Renamed class to `LivepocketScraper` (lowercase `p`) → `_scraper_key = livepocket`.

**Result:** 14 Taiwan events found after both fixes. `start_date` populated for all.

**Lessons:**
- Always verify `dl` class name from live HTML before writing selectors — research profiles can have stale assumptions.
- For platform names with no natural CamelCase split (e.g. "livepocket"), always use `Livepocket` (not `LivePocket`) to ensure `_scraper_key` matches `source_name`.
- Duplicate `dl` blocks exist (desktop + mobile) — always use `select_one()`.

---
## 2026-04-29: Peatix organizer Layer 3 + discovery_accounts.py daily rotation

**變更：**
- peatix.py: `_load_db_organizers()`, `_scrape_group_events()`, `scrape()` DB loop
- discovery_accounts.py: 4-slot rotation, `_run_note_task()`, `_run_peatix_task()`, `_verify_peatix_group()`
- discovery-accounts.yml: Mon-Thu daily cron, `DISCOVERY_SLOT` env var

**規則新增：**
- Layer 3 擴充到新平台時，`agent_category` 必須是平台獨立的值（`peatix_organizer` 而非通用名稱）
- `source_profile` 結構須包含 `platform` 欄位以區分來源
- discovery_accounts.py 的 `--dry-run --slot N` 組合是必要的驗證入口

**Skills folder convention（同日修正）：**
- `jats/` 和 `waseda_taiwan/` 移入 `.github/skills/sources/` 子目錄（原放在頂層，屬錯誤）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下

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

---

## 2026-04-29 — annotator: truncation limit 12K→20K でも GPT が sub-events を 2 件しか生成しない

**発見：** 台湾文化センター「台湾映画上映会2026」（16 場上映）の sub-events が 2 件しか DB に存在しない。annotator の truncation limit を 12,000→20,000 に引き上げたが、GPT-4o-mini は依然 2 件の sub-events しか返さなかった（output: 1,191 tokens）。

**根本原因：** description が 13,492 文字（旧 12,000 char truncation で切断されていた）→ truncation 修正後も GPT-4o-mini は全 16 件を抽出しなかった。入力が長く密度が高い場合、GPT が自律的に生成を打ち切る傾向がある。

**修正：** 
1. `annotator.py` truncation limit 12,000→20,000 chars（commit `ff2a2ac`）
2. `_insert_sub_events.py` で 16 件の sub-events を手動挿入（一時スクリプト、削除済み）
3. Sub-events：10 正片（5月〜10月）＋ 6 アンコール（6/7, 9/19, 10/4 @ ユーロライブ/シネ・ヌーヴォ）

**教訓：** GPT が全 sub-events を確実に生成しない場合、scraper 層で直接 sub-events を生成するほうが信頼性が高い。連続上映シリーズ（映画祭等）は scraper で各回を `Event` として生成し `parent_event_id` を設定するべき。

---

## 2026-04-28 — eiga_com: 原題から name_zh / name_en を直接抽出する

**発見：** 映画.com の映画詳細ページ（例：`/movie/82162/`）の `p.data` に「原題または英題：阿嬤的夢中情人 Forever Love」という行が存在する。スクレイパーは `name_ja`（日本語配給タイトル）しか設定していなかったため、中文・英語タイトルは AI アノテーターの推測に頼っていた。

**根本原因：** `_fetch_movie_detail()` は `p.data` から製作年・上映時間・国情報のみ使用し、`原題` 行を無視していた。

**修正：** `_ORIG_TITLE_RE` regex と `_parse_original_title()` helper を追加。
- 非 ASCII ブロック（CJK）→ `name_zh`、ASCII ブロック（英語）→ `name_en` に分離
- `_fetch_movie_detail()` の返り値を `(title, pub_date, raw_description, name_zh, name_en)` に拡張
- fallback Event と `_scrape_area_page()` の両方に `name_zh`, `name_en` を渡す

**例：**
- `原題または英題：阿嬤的夢中情人 Forever Love` → `name_zh="阿嬤的夢中情人"`, `name_en="Forever Love"`

**Lesson：**
- 映画系ソースには必ず詳細ページの「原題」「英題」「原題または英題」フィールドを確認すること。
- 原タイトルは AI より高精度 — スクレイパーで確定できる情報は AI に任せない。
- ルールを SKILL.md `## eiga_com-specific` に追記済み。

---

## 2026-04-26 — scope expanded to all of Japan（全日本）

**Change:** Removed `prefecture=tokyo` from Connpass API params; updated docstrings for Doorkeeper and Connpass; updated agent descriptions and community-platforms subagent.

**Root cause:** Scrapers were unintentionally limited to Tokyo by an API parameter. The project scope is all of Japan — Osaka, Kyoto, Fukuoka, Sapporo, etc. are all in scope.

**Fix:** `connpass.py` no longer passes `prefecture=tokyo`; `doorkeeper.py` has never had a location filter and should stay that way.

**Lesson:** Never add a prefecture/region filter to API scrapers unless the *source itself* is geographically bounded. Taiwan relevance (`_TAIWAN_KEYWORDS`) is the only required filter. → Added `## Geographic Scope` to SKILL.md.

---
## 2026-04-26 — スコープ拡張：東京限定 → 全日本

**変更内容**: ユーザー指示により対象スコープを東京から全日本（全国）に拡張。

**背景**: プロジェクト名は「Tokyo Taiwan Radar」だが、台湾関連イベントは大阪・京都・福岡・札幌等でも開催される。スクレイパーが地理フィルターで東京以外のイベントを除外することは意図しない動作。

**適用した変更**:
- `copilot-instructions.md` — プロジェクト概要を「in Japan（全日本）」に更新、Geographic Scope 注記追加
- `scraper-expert.agent.md` — description + `> **Scope**` 注記追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加

**教訓**: 地理的スコープは SKILL.md の冒頭に専用セクションとして明示すること。東京以外を除外する地理フィルターを追加する前に Geographic Scope セクションを必ず確認すること。

---
## 2026-04-26 — cine_marine + taiwan_faasai: two new scrapers implemented

**cine_marine (横浜シネマリン):**
- Listing page structure: each film entry is `<h2>` (date) + `<h3><a>` (title+URL) + `<div class="content_block">` (details) within a single `.entry-content` article.
- Taiwan filter applied only to `content_block` text (not full film page) to avoid false positives from sidebar that lists all current films.
- Source name: `cine_marine` (from `CineMarineScraper` via `_scraper_key`).

**taiwan_faasai (台湾發祭 Taiwan Faasai):**
- Annual 3-day free outdoor festival in Ueno Park.
- TLS issue: `verify=False` required, `InsecureRequestWarning` suppressed.
- Source ID: `taiwan_faasai_{year}` — stable per year.

---


**Error (morc_asagaya):** All 24 film pages matched Taiwan filter because every page contains a site-wide `section#tp_info` with "台湾巨匠傑作選2024" promotion links. Initial implementation applied `get_text()` to the entire page including this section.

**Fix (morc_asagaya):** Added `soup.select('#tp_info')[...].decompose()` before keyword search. Result: 0 events (correct — no Taiwan films on screen).

**Error (shin_bungeiza):** `_parse_nihon_date_only` used `p.find_previous("h2")` to find the start date. Because `p.nihon-date` is the first child in its container, `find_previous` returned an h2 from a prior film block → wrong date (e.g. 5/6 instead of 5/8).

**Fix (shin_bungeiza):** Rewrote to iterate `parent.children`, collecting h2 elements that appear after the `p`. First h2 → start date (M/D format). Last h2 → end date (day-only, same month with wrap guard).

**Lesson (generalizable):** When an element is the first sibling in its container, `find_previous()` crosses container boundaries. Always iterate `parent.children` for sibling-relative navigation. Also: site-wide banners can pollute keyword filters — inspect false-positive pages to identify the offending section and exclude it.

---
## 2026-04-26 — workflow: push step was missing from post-change checklist

**Error:** After implementing cinemart_shinjuku scraper (Phase 4 docs complete), task_complete was called without committing or pushing. The feature branch had to be created and pushed manually in a follow-up turn.

**Fix:** Added Step 5 (git commit & push) to `## Mandatory Post-Change Checklist` in `SKILL.md`, and added Phase 5 (Commit & Push) to `scraper-expert.agent.md`.

**Lesson:** Every scraper session must end with a commit + push to a feature branch before calling task_complete. → Added to SKILL.md Step 5 and agent.md Phase 5.

---
## 2026-04-26 — taiwanshi: date/venue regex misses non-standard separators

**Error:** 2 posts had `date parse failed` warnings; 1 post had `venue=None`. Affected: `場所：` label, `会場　` (full-width space only, no colon), and `日時： 2025 年10月4 日` (spaces within date).

**Root cause:** Initial regex assumed `日時[：:]` (colon required) and `会場[：:]` (colon required), missing: (a) full-width space separator `日時　`, (b) `場所：` label instead of `会場：`, (c) OCR/copy-paste spacing within the date `2025 年10月4 日`.

**Fix:** Extended date regex separator to `[：:\s\u3000]*` and date component matches to `\s*年\s*...\s*月\s*...\s*日`. Extended venue regex to `(?:会場|場所)[\uff1a:\u3000 \t]+`.

**Lesson:** Japanese blog posts use inconsistent separators after label words. Always allow `[：:\s\u3000]*` (colon or any whitespace) as the separator between a label (`日時`, `会場`, `場所`) and its value. Also allow `\s*` between digit groups and kanji connectors in date fields. → Added to `## taiwanshi-specific` in SKILL.md.

---
## 2026-04-26 — ifi: URL injected into location_address from venue map link

**Error:** `location_address` contained `https://www.u-tokyo.ac.jp/campusmap/...` appended after the venue name.

**Root cause:** IFI appends a campus map URL on the line immediately after the venue name in `inner_text`. `_extract_info()` captured it as part of the venue value.

**Fix:** Filter venue lines with `not ln.strip().startswith("http")` before building `location_name`/`location_address`.

**Lesson:** Academic sites frequently append map/registration URLs directly below venue names without a visual separator. Always filter HTTP lines from venue extraction.

---
## 2026-04-26 — tokyonow: API keyword search returns 0 for Japanese terms

**Error:** `GET /wp-json/tribe/events/v1/events?search=台湾` returns 0 results even when Taiwan events exist on the site.

**Root cause:** The Tribe Events v1 WordPress plugin `search` parameter only matches English title/slug fields — it does not index Japanese text.

**Fix:** Full-page scan strategy — paginate all future events with `start_date=<today>&per_page=50`, apply local `_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]` filter on stripped title + description.

**Lesson:** Do not assume REST API `search` parameters support Japanese full-text search. Always test a known Japanese keyword against a known Japanese event before relying on server-side filtering. Fall back to full-scan + local filter when the API returns 0 unexpectedly.

---
## 2026-04-25 — koryu: Taiwan-office events leaking into DB (wrong location_address)

**Error:** `_scrape_detail()` never called `_is_tokyo_venue()`. The function existed but was dead code. As a result, events organised by koryu’s Taiwan offices (台北・台中・高雄) were ingested alongside Tokyo events. One event showed `location_address='台北'` even though the title clearly said 台中. 8 bad events accumulated in the DB.

**Root cause:** The koryu.or.jp DNN CMS renders a breadcrumb in the `<main>` inner text as a run-on string: `お知らせイベント・セミナー情報台北`. The trailing kanji (`台北`, `台中`, `東京`) is the office/category tag assigned in the CMS. Taiwan-office events were not filtered because no code checked this tag.

**Fix:**
1. Added `_TAIWAN_OFFICE_TAGS = {'台北', '台中', '高雄', '台南', '桃園', '新竹', '基隆', '嘉義'}` constant.
2. Added `_extract_office_tag(body_text)` that regex-extracts the tag after `イベント・セミナー情報\s*([\u4e00-\u9fa5]{1,6})`.
3. In `_scrape_detail`: if `office_tag in _TAIWAN_OFFICE_TAGS` → return None.
4. DB: hard-deactivated (`is_active=False`) all 8 Taiwan-location koryu events.

**Lesson:**
- After adding a geographic filter, ALWAYS audit existing DB rows with `eq('source_name','koryu')` and deactivate any that would have been blocked.
- DNN CMS breadcrumb text is part of `main.inner_text()` — location/office tags from the breadcrumb can pollute venue/address extraction if not stripped or checked first.
- `_is_tokyo_venue()` was defined but never called — dead utility functions should either be wired up or deleted. Prefer wiring them up and adding a test to confirm.

---

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
