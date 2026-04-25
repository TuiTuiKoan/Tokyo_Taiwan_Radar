---
description: "Add a new event category across all layers: types, i18n, scraper, classifier, docs, then validate and push"
argument-hint: "key=snake_case zh=中文標籤 en=English label ja=日本語ラベル keywords=comma,separated,ja,keywords"
agent: Engineer
---

# Add Category Workflow

You are the **Engineer** agent. Execute all steps below **without pausing for confirmation** unless a step explicitly says to stop. After completing all steps, return a Changes Log summary to the user.

## Inputs

Parse the following from the user's message (if not provided, ask once before proceeding):

| Variable | Description | Example |
|----------|-------------|---------|
| `KEY` | snake_case category key | `competition` |
| `ZH` | Traditional Chinese label | `競賽` |
| `EN` | English label | `Competition` |
| `JA` | Japanese label | `コンテスト・競技` |
| `KEYWORDS` | Comma-separated Japanese/Chinese/English keywords for `classifier.py` | `コンテスト,contest,大会,公募` |

---

## Step 1 — Update `web/lib/types.ts`

1. Add `| "KEY"` to the `Category` union type (before `"report"`).
2. Add `"KEY",` to the `CATEGORIES` array (before `"report"`).

---

## Step 2 — Update i18n messages (all three files simultaneously)

- `web/messages/zh.json` → `"KEY": "ZH"` (before `"report"`)
- `web/messages/en.json` → `"KEY": "EN"` (before `"report"`)
- `web/messages/ja.json` → `"KEY": "JA"` (before `"report"`)

---

## Step 3 — Update `scraper/annotator.py`

1. Add `"KEY"` to `VALID_CATEGORIES` list (before `"report"`).
2. Add `"KEY"` to the categories list in the system prompt (line starting with `2. Categories must be from this list:`).
3. Add a bullet explaining what `"KEY"` means (after the existing category bullet points, before `"report"`):
   - `"KEY"` = [write a 1-sentence English definition based on the label and keywords]

---

## Step 4 — Update `scraper/classifier.py`

1. Update the module docstring to include `KEY` in the category list.
2. Add a new rule tuple before `("academic", [...])`:

```python
("KEY", [
    # paste KEYWORDS here, one per line as quoted strings
]),
```

**Keyword safety rules (apply before writing):**
- No person-title words (博士, 先生, 教授) as standalone keywords — use compound forms only
- No words that commonly appear as proper nouns in unrelated contexts
- If a keyword overlaps with an existing category's keywords, only keep it here if it's clearly more specific

---

## Step 5 — Update `scraper/sources/base.py`

Append `KEY` to the comment on the `category` field (the line starting with `# Values from canonical list:`).

---

## Step 6 — Update `.github` documentation (all simultaneously)

- `.github/copilot-instructions.md` — add `` `KEY` `` to the canonical category list
- `.github/instructions/web.instructions.md` — same
- `.github/instructions/scraper.instructions.md` — same
- `.github/agents/tester.agent.md` — add `KEY` to the `category` validation list

---

## Step 7 — Validate

Run both checks:

```bash
# TypeScript
cd web && npx tsc --noEmit

# Python classifier smoke test
cd scraper && python -c "
from classifier import classify
# Test with a keyword from the new category
result = classify('TEST_EVENT_NAME', None, None, None, None, None)
print('classifier ok:', result)
"
```

If either check fails, fix the error before proceeding to Step 8.

---

## Step 8 — Git commit and push

Stage only the files changed in Steps 1–6:

```
web/lib/types.ts
web/messages/zh.json
web/messages/en.json
web/messages/ja.json
scraper/annotator.py
scraper/classifier.py
scraper/sources/base.py
.github/copilot-instructions.md
.github/instructions/web.instructions.md
.github/instructions/scraper.instructions.md
.github/agents/tester.agent.md
```

Commit message format:
```
feat(categories): add KEY category

- Category: KEY (ZH / EN / JA)
- Classifier keywords: KEYWORDS
- Updated: types.ts, i18n (zh/en/ja), annotator, classifier, docs
```

Then `git push`.

---

## Step 9 — Backfill existing DB events (optional)

If the user wants to tag existing events with the new category, run:

```bash
cd scraper && python backfill_categories.py --dry-run
```

Show the dry-run output and ask: **「是否要執行正式更新？」** before running without `--dry-run`.

> ⚠️ Always dry-run first. Review every match — false positives from overly broad keywords are common.

---

## Changes Log Format

Return a summary in this format:

```
## Changes Log — add category: KEY

Files modified: [list]
Classifier keywords added: [list]
TypeScript check: PASS / FAIL
Git push: SUCCESS / SKIPPED
DB backfill: [count] events updated / skipped
```
