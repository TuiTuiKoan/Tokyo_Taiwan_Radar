---
title: Spec Directory — Tokyo Taiwan Radar
ms.date: 2026-05-05
---

# Spec Directory

每個進行中的功能或改動都有一份 spec，讓你在 Copilot Chat 換 session 後不需要重述脈絡。

## 目錄結構

```
docs/specs/
├── _template/          ← Copilot 新建 spec 時抄這裡
├── parked/             ← 暫存的 idea，單一 .md 檔
├── active/<slug>/      ← 進行中（proposal.md + tasks.md [+ notes.md]）
└── archive/            ← 完成後 git mv 進來（單一 .md 或子目錄）
```

## Frontmatter 規約（proposal.md）

```yaml
---
slug: <kebab-case 唯一識別>
title: <人類可讀標題>
status: active          # parked | active | archived
branch: feat/<slug>     # 對應 git branch（可空）
created: YYYY-MM-DD
tags: [scraper, web, infra, tooling]
---
```

## Status 流轉

```
parked → active → archived
```

- `parked` → `active`：開新 git branch，把 `parked/<slug>.md` 移至 `active/<slug>/proposal.md` 並補 `tasks.md`
- `active` → `archived`：`git mv docs/specs/active/<slug> docs/specs/archive/$(date +%Y-%m)-<slug>`

## 給 Copilot 的使用守則

1. **新功能前先建 spec**：在 `active/<slug>/proposal.md` 寫清楚 what/why/non-goals，再開 branch。
2. **tasks.md 是唯一進度依據**：每完成一步就把 `- [ ]` 改 `- [x]`，commit 進 git。
3. **換 session 時**：把 `docs/specs/active/<slug>/tasks.md` 貼給 Copilot，說明「繼續執行未完成項目」，不需要重述背景。
