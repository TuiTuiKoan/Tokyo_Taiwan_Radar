# Waseda Taiwan Scraper — History

## 2026-05-30 — `_STOP_LABELS` 欠如で venue_raw に講演者・モデレーター情報が混入（commits `0604a6f`, `b3be645`）

**問題：** event `75a46729`（郭智輝氏講演）の `location_name` が `早稲田大学早稲田キャンパス11号館710教室 講演者：郭智輝氏（...） モデレーター：久保克行（...） 対象：学生・教職員・一般` と表示された。また、`performers = ['郭智輝']` のみで モデレーター `久保克行` が未収録。

**根本原因（2件）：**
1. `_STOP_LABELS` に `講演者`/`モデレーター`/`対象` が未登録 → `_extract_after_label()` が会場ラベル後の全行を `venue_raw` に取り込んでいた。`venue_raw` はそのまま `raw_description` に `会場: {venue_raw}` として埋め込まれ、annotator が全テキストを `location_name` に格納した。
2. `raw_desc_parts` に `講演者`/`モデレーター` を追加していなかった → 上記バグが存在しなかったとしても、annotator が `performers` に両者を収録するのに必要な構造化テキストが不足していた。

**修正（commit `0604a6f` + `b3be645`）：**
- `_STOP_LABELS` に `"講演者"`, `"モデレーター"`, `"対象"` を追加。
- `raw_desc_parts` に `f"講演者: {speaker_raw}"` と `f"モデレーター: {moderator_raw}"` を追加。`_extract_after_label()` の stop boundary が正しく効くため、`speaker_raw` は `講演者：...（モデレーター：手前まで）`、`moderator_raw` は `モデレーター：...（対象：手前まで）` が得られる。
- DB 直接修正：`location_name = '早稲田大学早稲田キャンパス11号館710教室'`（FC lock）、`performers = ['郭智輝', '久保克行']`（FC lock）、`performer_zh/en = null`（多人 Guard）。

**教訓：**
- `_extract_after_label()` で会場を抽出するスクレイパーは、**ソース同一行に登場しうる全ラベル**（発表者・言語・対象者等）を `_STOP_LABELS` に登録すること。発見漏れは `venue_raw` 汚染として annotator まで伝播する。
- 学術イベント系スクレイパーで `講演者`/`モデレーター` が存在する場合は、`raw_desc_parts` に**必ず個別エントリとして追加**する。`会場: {venue_raw}` に混ぜた形では annotator は performers を拾えない。
- 多人 Guard：`performers.length ≥ 2` のとき `performer_zh/en` は `null` に設定する（UI は `performers[].join("、")` で表示するため）。

---

## 2026-04-26

**Implementation**: Initial build.

- WP REST API available. All posts are in single category `未分類` (id=1) — no category filtering possible.
- Not all posts are events: working papers, newsletters, and blog entries are mixed in. Event detection relies on `日時：` / `開催日時：` / `日 時：` label presence in content.
- Critical bug found during testing: `YYYY/M/DD（土）HH:MM` → removing `（土）` with `""` produces `YYYY/M/DDHH:MM` (concatenated). Fix: replace DOW with `" "` not `""`.
- Two venue label formats: `場所：` and `会場：` and `場 所：` (with space). Use `r"(?:場\s*所|会\s*場|開催場所)"` to match all.
- `location_address` sometimes contains full address `東京都新宿区西早稲田1-20-14` embedded in parentheses after venue name — extract with regex and `.rstrip("）)")`.
- `_STOP_LABELS` for special chars (`■`, `●`, `※`, `http`) need single-char stop rule (no trailing `[\s：:]` check) — these chars are immediately followed by Japanese text without space/colon.
