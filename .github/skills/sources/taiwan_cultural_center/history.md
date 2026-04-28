# Taiwan Cultural Center Source — Error History

<!-- Append new entries at the top -->

---

## 2026-04-29 — 台湾映画上映会2026: sub-events の name_zh 誤り・source_url 404・親日程ずれ

**発見：**
1. `source_url` を `https://www.taiwan.or.jp/ja/cinema2026/` （存在しない URL）に誤設定 → 全 16 件 404
2. 親イベント `start_date`/`end_date` = `2026-04-27`（公開日）のまま → sub 最早/最終日に更新必要
3. 中文タイトル 4 件が原題と不一致：
   - sub1 `望海的日子（數位修復版）` → 正：`看海的日子（數位修復版）`（原題：看海的日子）
   - sub12 `台北我愛你` → 正：`愛情城事`（原題：愛情城事）
   - sub13 `雙打人生` → 正：`乒乓男孩`（原題：乒乓男孩）
   - sub16 `金魚的記憶` → 正：`（真）新的一天`（原題：（真）新的一天）

**根本原因：**
1. `_insert_sub_events.py` で `source_url` を親の正 URL ではなく推測 URL に設定
2. 親の `start_date`/`end_date` は scraper が設定（公開日フォールバック）。Sub-events 挿入後に親を手動更新しなかった
3. `name_zh` は原題から手動で入力したため、4 件で転記ミス

**修正：** DB 直接修正（一時スクリプト `_fix_cinema2026.py`、削除済み）:
- 親 `start_date=2026-05-16`, `end_date=2026-10-24`
- 全 16 件 `source_url` → `https://jp.taiwan.culture.tw/News_Content2.aspx?n=365&s=254306`
- 4 件 `name_zh`/`name_en` 訂正

**教訓：**
- Sub-events を手動挿入するときは必ず `原題` 行を description から抽出して `name_zh` を設定すること（推測入力禁止）
- `source_url` には親の `source_url` をコピーすること。推測 URL は使わない
- Sub-events 挿入後は親の `start_date`/`end_date` を `MIN(sub.start_date)` / `MAX(sub.end_date)` に更新すること

---

## 2026-04-29 — 台湾映画上映会2026: sub-events が 2/16 件しか生成されない

**発見：** 「台湾映画上映会2026」（parent `3db5b1ec509b3342`）の sub-events が 2 件のみ。16 件（10 正片 + 6 アンコール）が期待値。

**根本原因：**
1. `raw_description` が 13,492 文字。annotator の truncation limit が 12,000 文字で description が切断されていた
2. Truncation を 20,000 に引き上げた後も GPT-4o-mini は 2 件しか生成しなかった（output 1,191 tokens）。長い密な description から多数の sub-events を生成するのは GPT-4o-mini には困難

**修正：**
1. `annotator.py` truncation limit 12,000→20,000 chars
2. 16 件の sub-events を手動スクリプトで直接 DB 挿入

**上映スケジュール（参考）:**
| # | 作品名 | 日程 | 会場 |
|---|--------|------|------|
| sub1 | 海をみつめる日 デジタル・リマスター版 | 5/16 | 北海道大学 |
| sub2 | あの写真の私たち | 5/30 | 大阪大学 |
| sub3 | うなぎ | 6/7 | ユーロライブ |
| sub4 | 小さな町の恋 デジタル・リマスター版 | 7/11 | 京都大学 |
| sub5 | 今夜は帰らない デジタル・リマスター版 | 7/18 | 中央大学 |
| sub6 | 宵闇の火花 | 7/25 | 慶應義塾大学 |
| sub7 | 夜明けの前に | 8/1 | 日本映画大学 |
| sub8 | 甘露水 | 9/19 | ユーロライブ |
| sub9 | 深く静かな場所へ | 10/4 | シネ・ヌーヴォ |
| sub10 | 荒野の夢 | 10/24 | 台湾文化センター |
| sub11 | 余燼（アンコール） | 6/7 | ユーロライブ |
| sub12 | タイペイ、アイラブユー（アンコール） | 6/7 | ユーロライブ |
| sub13 | 燃えるダブルス魂（アンコール） | 9/19 | ユーロライブ |
| sub14 | 夫殺し デジタル・リマスター版（アンコール） | 9/19 | ユーロライブ |
| sub15 | 猟師兄弟（アンコール） | 10/4 | シネ・ヌーヴォ |
| sub16 | 金魚の記憶（アンコール） | 10/4 | シネ・ヌーヴォ |

**教訓：** TCC 連続上映企画（映画上映会など）は将来的に scraper 層で各回を個別 `Event` として生成し `parent_event_id` を設定するほうが信頼性が高い。

---
