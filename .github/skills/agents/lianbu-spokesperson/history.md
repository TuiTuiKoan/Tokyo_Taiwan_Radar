# Lianbu Spokesperson — History

（最新を上に追記する）

---

## 2026-06-29 — weekly_line_broadcast 地域順を地理順に固定

**変更内容：** nearterm の地域グループ順を、東京を先頭、北海道から沖縄までの日本都道府県を北から南、台湾、未設定の順に固定する方針に更新。

**根本原因：** 地域グループを辞書の挿入順やラベル文字列に依存すると、東京以外の地方イベントが日付や取得順で前後し、週報の読み順が安定しない。

**修復：** `_region_geo_rank()` を導入し、地域ラベル検出と同じ入力順で `location_address` / `location_prefectures` を評価する。ラベルとソート順位の判定をずらさない。

**教訓：** 公開配信の地域順は「見つかった順」ではなく編集方針として固定する。小霧の投稿草案では、`weekly_line_broadcast` から渡された地域順を保持し、五十音順や英字順に並べ替えない。

---

## 2026-05-31 — weekly_line_broadcast フォーマット多段改善（commits `7c8cbbc`〜`41fc02d`）

**変更内容：**
- 4-type 分組（活動 / 電影 / 線上 / 電視）導入
- nearterm 小節に日付範囲を追加し、新刊出版を独立グループに分離
- ヘッダーを「小霧精選 / レンブ厳選 / Bubu's Picks」（三言語）に統一
- タイトルを「今週のレーダー」に変更（旧：今週のスキャン）
- nearterm / monthly セクションから URL を削除し、精選段のみに URL を保持
- 電視節目の city label 処理を追加

**確認事項：** 英語での mascot nickname は **"Bubu"**（"Lianbu" の短縮形）。broadcast メッセージ・コード・コメント内の英語表記はこれで統一。

**教訓：** broadcast メッセージの URL は精選段（小霧精選 / Bubu's Picks）のみに付与する。nearterm / monthly セクションは日付・都市ラベルのみで十分（メッセージ長超過を防ぐ）。電視節目は city label を別途処理する必要がある（`location_address` が venue 名のみの場合 `_city_label()` が空になる — `location_prefectures` から補完）。

---

## 2026-05-31 — 初版人格設定

**変更内容**: Lianbu Spokesperson agent・SKILL・history の初版作成

**人格決定事項**:
- 表示名: `Lianbu Spokesperson`（吉祥物英語表記は常に "Lianbu"）
- 人格暱稱: 小霧 / レンブちゃん / Bubu（英語）
- 言語: 日本語メイン、繁体中文対照付き、英語版も生成
- ワークフロー A（返信草案）: 日本語草案 + 繁体中文対照 + 策略メモ
- ワークフロー B（三プラットフォーム投稿）: X.com / Threads / Instagram × ja/zh/en
- 禁則4条確定（政党指名禁止・正面衝突禁止・統独自発禁止・個人嘲笑禁止）

**教訓**: 特になし（初版）
