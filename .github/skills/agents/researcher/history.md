# Researcher Error History

<!-- Append new entries at the top -->

---

## 2026-04-29 — Layer 2: Weekly note.com Creator Discovery (discovery_accounts.py)

**変更内容**: 新規スクリプト `scraper/discovery_accounts.py` と GitHub Actions ワークフロー `.github/workflows/discovery-accounts.yml` を作成し、毎週日曜 10:00 JST に note.com クリエイターを自動発見する Layer 2 ワークフローを追加。

**実装詳細**:
- 3つの GPT search タスク（コミュニティイベント / 文化芸術 / 食・ライフスタイル）
- `gpt-4o-search-preview` でリアルウェブ検索（researcher.py と同スタック）
- `_verify_note_creator()`: RSS フィード確認（note.com は Playwright 不要）
- `_extract_creator_id()`: 完全 URL または bare slug を受け付け、記事/テンプレート URL を拒否
- 既知の note_creator ID を `research_sources` から読み込み、重複挿入を防止
- status=`candidate` でクリエイターを upsert → Admin で confirmed → Layer 3 が自動ピックアップ
- Dry-run 結果: 11 クリエイター発見（1+5+5）、全件 RSS 検証済み

**教訓**:
1. note.com の RSS URL は `https://note.com/{creator_id}/rss` — Playwright なしの HTTP GET で存在確認が完結する。
2. GPT が返す URL には記事 URL（`/n/` を含む）やテンプレート URL が混入する。`_extract_creator_id()` は `/n/` パターンを拒否し、bare slug のみを抽出すること。
3. 既知クリエイター ID は毎回 DB から読み込み、GPT が同じクリエイターを再提案しても重複 upsert しない設計が正しい。

→ SKILL.md に `## discovery_accounts.py — Layer 2` セクションを追加済み。

---

## 2026-04-29 — Layer 1: WEEKDAY_SCHEDULE → SLOT_SCHEDULE（4 daily slots, 9 categories/day）

**変更内容**: `researcher.py` の週次ローテーション（WEEKDAY_SCHEDULE: 7日で7カテゴリ）を廃止し、4スロット/日スケジュール（SLOT_SCHEDULE）に変更。1日で全9カテゴリをカバーするようになった。

**旧設計**: cron 1回/日（09:30 JST）→ 曜日ごとに1カテゴリ

**新設計**:
- Slot 0 (06:00 JST): `university`, `fukuoka`
- Slot 1 (12:00 JST): `media`, `government`
- Slot 2 (18:00 JST): `thinktank`, `hokkaido`
- Slot 3 (00:00 JST): `social`, `performing_arts_search`, `senses_research`
- `RESEARCH_SLOT` env var で GitHub Actions からスロットを注入
- researcher.yml: 4 cron（21:00/03:00/09:00/15:00 UTC = 06/12/18/24 JST）

**教訓**:
1. `github.event.schedule` は起動した cron のスケジュール文字列（例: `"0 21 * * *"`）を返す。shell の `case` 文で比較して `$GITHUB_ENV` に書き込む方式が最善。
2. `workflow_dispatch` 時は `github.event.schedule` が空文字列になる。`inputs.slot` をフォールバックとして提供すること。
3. `_resolve_category_id()` の戻り値を `str → list[str]` に変更したため、`run_research()` でループが必要になる。戻り値の型変更は呼び出し箇所を必ず確認すること。

→ SKILL.md に `## researcher.py — Schedule Management` セクションを追加済み。

---

## 2026-04-27 — Low-Signal Policy 転換：頻度低を not-viable 理由にしない

**変更内容**: スクレイパーが1日1回実行になったため、「台湾イベントが年1-2件以下」は not-viable の正当な理由にならなくなった。

**旧ルール**: 「頻度 < 2件/月 → not-viable」

**新ルール**: 技術的にスクレイプ可能であり、かつ過去に台湾関連イベントが1件でも確認されていれば viable（LOOKBACK_DAYS で低頻度に対応）。

**影響範囲**: 以下のソースは再評価対象：
- `[27]` 京都大学人文科学研究所 / `[81]` 福岡アジア美術館 / `[82]` さっぽろ台湾祭 — スコープ解除
- `[41]` シネスイッチ銀座 / `[38]` Uplink Shibuya / `[35]` Human Trust Cinema — 頻度理由解除
- `[1]` 東大先端研 / `[2]` Asia University — 学術低頻度解除
- `[78]` note.com — クリエイターリスト方式で再設計

**追加ルール**: SKILL.md の「Low-Signal Source Policy」セクションに反映済み。

---

## 2026-04-27 — スコープルール違反：福岡ソースを誤って not-viable 判定

**エラー**: 深度調査セッションで以下の2ソースを「東京スコープ外」を理由に not-viable に判定した。

| ソース | 違反した判断 | 実際の状況 |
|--------|------------|----------|
| 福岡アジア美術館 | 「開催地が福岡市→東京スコープ外」 | 台湾アーティスト Wu Mali・台湾コレクション確認済み。技術的実装も easy。 |
| 台北駐福岡経済文化弁事処 | 「全イベントが九州開催→東京スコープ外」 | 文化イベント50%（シンポジウム・写真展・コンサート・映画）。RSS+静的HTML で easy。 |

**原因**: SKILL.md に Geographic Scope ルールが存在したにもかかわらず、評価時に「東京スコープ外」という直感的な判断が優先された。

**修正した変更**:
- `SKILL.md` — Geographic Scope セクションを `⚠️ CRITICAL` に昇格、`not-viable` の**無効な理由**として明示的に列挙
- `researcher.agent.md` — Step 1 の地域リストを「全国すべての都市」に拡張、Step 2 にスコープリマインダーを追加
- `history.md` — 本エントリ追加

**要再評価のソース**:
- `fukuoka-asian-art-museum.md` → 台湾コンテンツ確認済み（東アジア展・レジデンス展）→ `needs-work` 以上に昇格推奨
- `taipei-office-fukuoka.md` → 台湾文化イベント月3-5件確認済み → `researched` に昇格推奨

**教訓**: スコープルールは判定の最後ではなく**最初**に確認する。「開催地が東京以外 → not-viable」という思考パターンを常に疑うこと。

---

## 2026-04-26 — スコープ拡張：東京限定 → 全日本

**変更内容**: ユーザー指示により調査対象を東京から全日本（全国）に拡張。

**背景**:
- これまで「東京以外の開催」を not-viable 判定の理由として使用していた（九州大学・東北大学・FAAM 福岡等）
- ユーザーより「不必限於東京，可以包含全日本」と明示指示を受けた

**適用した変更**:
- `researcher.agent.md` — description・Role・Step 1・Step 2 を全日本スコープに更新
- `SKILL.md` — 「Geographic Scope」セクション追加、not-viable 理由から地理的除外を削除
- `history.md` — 本エントリ追加

**教訓**: 地理的スコープは明示的にドキュメント化すること。「東京のみ」という前提は上書きされやすいので SKILL.md 冒頭に専用セクションを設ける。

**影響を受ける既存プロファイル（再評価推奨）**:
- `kyushu-u-taiwan.md` — 「地理スコープ外」判定だったが、台湾イベント存在 → 再評価可
- `tohoku-u-taiwan.md` — 同上
- `fukuoka-asian-art-museum.md` — 同上
- `taipei-office-fukuoka.md` — 台北駐福岡弁事処 → 九州エリアの有望ソースとして再評価推奨
