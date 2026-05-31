# Stranger Scraper History

---

## 2026-05-31 — openDate で start_date を安定化・scan lookback 14 日延長（commit `75b36dc`）

**問題 1（start_date 上書き）：** Eigaland API の 5/15〜5/29 booking 空白期間後、日次 cron が 6/1 に再び booking を検出すると `_build_movie_extend_row` が `merged_start = new_start`（6/1）をセット。本来の初映日 5/8 が消滅した。

**問題 2（映画消失）：** scan window が「今日から 90 日」のみのため、上映中だが Eigaland に未来 booking 未登録の映画が window 外へ落ちて invisible になっていた。

**根本原因（問題 1）：** `_build_event()` が `start_date` を Eigaland booking の最小日付から算出していた。Eigaland は映画館が手動更新する booking system であり、booking 未登録期間は「上映終了」ではなく「未登録」を意味する。

**修正（commit `75b36dc`）：**
1. movie detail API の `openDate` フィールド（映画館が一度設定する公式初映日）を `start_date` として採用。booking gap があっても start_date は変動しない。
2. scan window を `today-14 .. today+89`（計 104 日）に拡張。直近 14 日を含めることで booking 未登録期間中も映画を catch できる。

**教訓：** Eigaland では「公式初映日」≠「Eigaland に登録された最初の booking 日」。`openDate` が存在する場合は常にそれを `start_date` として使用する。lookback を加えることで booking gap への耐性が増し、end_date も最近の実績日まで延伸できる。

---

## 2026-05-06 — Initial implementation

**Context**: New scraper for Stranger cinema (東京墨田区), which uses the Eigaland platform API.

**Key decisions**:
- Used Eigaland JSON API (`listByDomainAndDate` + `movie/detail`) — no Playwright needed.
- Taiwan filter via `movieDetail.countries` array (`"台湾"` | `"台灣"`), not keyword search — avoids false positives like `仙台湾`.
- 90-day window loop collects `min_date`/`max_date` per `movieId` before calling detail API.
- `synopsis` field is base64-encoded HTML; decoded via `_HTMLStripper(HTMLParser)`.
- `name_ja_locked = True` — title comes from structured API, annotator should preserve it.
- `official_url` set from `officialPageUrl` (movie's own website, e.g. `https://www.afoggytale.com/`).
- First Taiwan movie found: 「霧のごとく」(大濛, 2026-05-08〜2026-05-14).

**Dry-run result**: 1 Taiwan movie found, all fields correctly populated.
