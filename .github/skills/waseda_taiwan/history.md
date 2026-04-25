# Waseda Taiwan Scraper — History

## 2026-04-26

**Implementation**: Initial build.

- WP REST API available. All posts are in single category `未分類` (id=1) — no category filtering possible.
- Not all posts are events: working papers, newsletters, and blog entries are mixed in. Event detection relies on `日時：` / `開催日時：` / `日 時：` label presence in content.
- Critical bug found during testing: `YYYY/M/DD（土）HH:MM` → removing `（土）` with `""` produces `YYYY/M/DDHH:MM` (concatenated). Fix: replace DOW with `" "` not `""`.
- Two venue label formats: `場所：` and `会場：` and `場 所：` (with space). Use `r"(?:場\s*所|会\s*場|開催場所)"` to match all.
- `location_address` sometimes contains full address `東京都新宿区西早稲田1-20-14` embedded in parentheses after venue name — extract with regex and `.rstrip("）)")`.
- `_STOP_LABELS` for special chars (`■`, `●`, `※`, `http`) need single-char stop rule (no trailing `[\s：:]` check) — these chars are immediately followed by Japanese text without space/colon.
