# Slide Deck Maintenance & Deployment Guide

## Quick Start

```bash
# 1. Edit source files
vim docs/slides/agentic-design-workflow.zh.html
vim docs/slides/agentic-design-workflow.en.html

# 2. Test locally (optional)
# Open in browser: file:///.../docs/slides/agentic-design-workflow.zh.html

# 3. Copy to deployment paths
cp docs/slides/agentic-design-workflow.zh.html web/public/202606/normativity-design/index.zh.html
cp docs/slides/agentic-design-workflow.en.html web/public/202606/normativity-design/index.en.html

# 4. Commit changes
git add docs/slides/agentic-design-workflow.*.html web/public/202606/normativity-design/index.*.html
git commit -m "docs(slides): [description]"

# 5. **CRITICAL: Push to origin**
git push origin main

# 6. Verify deployment started
git log origin/main -1  # Should show your commit

# Monitor Vercel: https://vercel.com/tuituikoan/tokyo-taiwan-radar
```

## File Organization

```
docs/slides/
├── agentic-design-workflow.zh.html    (Source: 2-space indentation)
├── agentic-design-workflow.en.html    (Source: 1-space indentation)
├── history.md                         (This file)
├── DEPLOYMENT.md                      (This guide)
└── TTR sharing/                       (Shared assets: PNGs, QR codes, diagrams)

web/public/202606/normativity-design/
├── index.zh.html                      (Copy of agentic-design-workflow.zh.html)
├── index.en.html                      (Copy of agentic-design-workflow.en.html)
└── TTR sharing/                       (Shared assets symlink or copy)
```

**Important:** Production URL uses lowercase `normativity-design`, NOT `NormativityDesign`.

## Bilingual Maintenance Rules

### Indentation Consistency
- **Chinese version (`.zh.html`)**: 2-space indentation
- **English version (`.en.html`)**: 1-space indentation
- **Rule**: Never auto-format or change indentation style. Use `replace_string_in_file` with explicit, complete oldString/newString.

### Content Parity
1. When adding new sections, create them in **Chinese first**
2. Translate to **English with semantic equivalence** (not literal)
3. Verify `pageno` values are identical between versions
4. Check all GitHub links point to correct files + line ranges

### Testing Multi-Section Changes
```bash
# After editing, verify page count
grep -c '<span class="pageno">' docs/slides/agentic-design-workflow.zh.html
grep -c '<span class="pageno">' docs/slides/agentic-design-workflow.en.html
# Should match

# Check for content anchors (e.g., new slide title)
grep 'S-4c\|S-5' docs/slides/agentic-design-workflow.zh.html
grep 'S-4c\|S-5' docs/slides/agentic-design-workflow.en.html
```

## Common Edits

### Adding a New Slide

**Example: Adding slide p.13 (S-4c)**

1. **Find insertion point** in source file:
   ```bash
   grep -n 'S-3\|S-4\|S-5' docs/slides/agentic-design-workflow.zh.html
   ```

2. **Locate previous slide's closing tag**:
   ```html
   <span class="brandfoot">STRUCTURE</span><span class="pageno">12</span>
   </section>
   <!-- INSERT NEW SLIDE HERE -->
   <section class="slide" data-accent="forest">
   ```

3. **Create new section with correct metadata**:
   - `data-accent="color"` (matches theme: red, gold, forest, etc.)
   - `eyebrow` with section code (e.g., "04 ・ S-4c")
   - `title-md` or `title-lg` for heading size
   - `pageno` set to target page number
   - All links should be GitHub URLs with explicit line ranges

4. **Update all subsequent pageno values** (if pageno >= new_page_number, increment by +1)
   ```bash
   # Automated via Python reverse-iteration to avoid index conflicts
   python3 << 'EOF'
   import re
   
   with open('docs/slides/agentic-design-workflow.zh.html', 'r', encoding='utf-8') as f:
       content = f.read()
   
   # Find all pageno values >= 14, increment by 1 (for new p.13)
   pagenos = list(range(14, 30))  # Adjust range as needed
   
   for pageno in reversed(pagenos):
       old = f'<span class="pageno">{pageno}</span>'
       new = f'<span class="pageno">{pageno + 1}</span>'
       content = content.replace(old, new, 1)  # Replace first occurrence only
   
   with open('docs/slides/agentic-design-workflow.zh.html', 'w', encoding='utf-8') as f:
       f.write(content)
   
   print("✓ Page numbers updated")
   EOF
   ```

5. **Replicate in English version** with proper translation

### Syncing Line Breaks or Styling

When you add `<br>` or other inline elements in Chinese version:

1. Identify exact line/context in `.zh.html`
2. Find corresponding location in `.en.html` (may have different line numbers due to 1-space vs 2-space)
3. Use `replace_string_in_file` with 5+ lines of context to ensure uniqueness

Example:
```bash
# Chinese version: 2-space indent
  <p class="lead">...給大家看 ——<br>一個正在運作...

# English version: 1-space indent (adjust accordingly)
 <p class="lead">...case study —<br>a live product...
```

## GitHub Links in Slides

### Format
Use explicit line ranges: `#L120-L165` (not just `#L120`)

### Examples
- `base.py#L120–165` (note: en-dash, not hyphen)
- `SKILL.md#L15–31`
- `agent.md#L20–24`

### Verification
```bash
# Check all GitHub links in current slide
grep -o 'href="https://github.com/[^"]*"' docs/slides/agentic-design-workflow.zh.html | head -10

# Verify links are valid (optional, requires curl)
curl -I https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/blob/main/scraper/sources/base.py#L120-L165
```

## Deployment Checklist

- [ ] Source files edited (both `.zh.html` and `.en.html`)
- [ ] Bilingual content verified (semantic parity)
- [ ] Page numbers consistent between versions
- [ ] GitHub links use explicit line ranges
- [ ] Copied to `web/public/202606/normativity-design/index.*.html`
- [ ] `git add` and `git commit` completed
- [ ] **`git push origin main` executed and verified**
  - Run: `git log origin/main -1` and confirm latest commit is yours
- [ ] Vercel build started (check Dashboard)
- [ ] Tested in browser (hard refresh: Cmd+Shift+R or Ctrl+Shift+R)
- [ ] All GitHub links in new slide clickable and correct

## Troubleshooting

### New slide doesn't appear after "deploying"
- **Check**: Did you run `git push origin main`?
- **Verify**: `git log origin/main -1` shows your commit?
- **Action**: If not, run `git push origin main` now.

### Content appears on local but not on vercel.com
- **Likely cause**: Vercel build hasn't finished or cache hasn't cleared
- **Action**: 
  1. Hard refresh browser (Cmd+Shift+R)
  2. Check Vercel Dashboard for build status
  3. Wait 1–2 minutes for build to complete

### Bilingual versions out of sync (different page counts)
- **Action**: 
  1. Count `pageno` spans: `grep -c '<span class="pageno">' file.html`
  2. If mismatch, re-run page number update automation
  3. Ensure all GitHub links in both versions have identical line numbers

### Large git diff with only indentation changes
- **Cause**: Editor auto-formatted the file with different indentation
- **Action**: 
  1. Discard changes: `git checkout docs/slides/agentic-design-workflow.en.html`
  2. Re-edit with careful `replace_string_in_file` (preserve indentation)
  3. Verify: `git diff` should show only content changes, not 1000+ lines of whitespace

## Related Documentation

- [Slide History](./history.md) — Maintenance log and lessons learned
- [Agentic Design Workflow Slides](./agentic-design-workflow.zh.html) — Source file (Chinese)
- [Agentic Design Workflow Slides](./agentic-design-workflow.en.html) — Source file (English)

---

**Last updated**: 2026-06-13  
**Maintained by**: Docs Team
