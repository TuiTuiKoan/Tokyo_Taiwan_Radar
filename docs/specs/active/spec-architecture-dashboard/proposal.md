---
slug: spec-architecture-dashboard
title: Spec & Architecture Dashboard（Admin 內部工具）
status: active
branch: feat/spec-architecture-dashboard
created: 2026-05-05
tags: [admin, tooling, web]
---

## What（做什麼）

在 `/admin/specs` 新增一個唯讀的可視化頁面，包含：
1. **Kanban 看板**：Parked / Todo / Doing / Done 四欄，每張卡代表一個 spec
2. **Spec 詳細頁**：render proposal.md + tasks.md + notes.md，含「複製 Copilot prompt」按鈕
3. **架構地圖**：用 Mermaid 顯示 agent / skill / scraper 關係圖

## Why（為什麼）

- 多條 feat branch 同時進行，切換時常忘記哪個做到哪裡
- 每次新開 Copilot Chat session 要重新解釋背景（洗版）
- 架構關係全在腦中，沒有圖可以看

## Non-Goals（不做什麼）

- ❌ 不做 spec 編輯器（在 VS Code + Copilot 編輯 markdown）
- ❌ 不做拖拉切換狀態（用 `git mv` 切換）
- ❌ 不開 Supabase 新表（資料源 = 純 markdown 檔 + git）
- ❌ 不打 GitHub API（branch info 走 build-time git）
- ❌ 不做向量搜尋 / RAG

## Design（設計摘要）

### 資料架構
```
docs/specs/{parked,active,archive}/**/proposal.md  ← 掃描目標
docs/architecture/system-map.json                  ← 架構地圖資料
web/lib/specs/reader.ts + parser.ts                ← 讀取與解析
web/scripts/build-specs-snapshot.ts                ← Vercel-safe build-time snapshot
```

### Key Constraints
- **Vercel serverless**：不能 fs.readdir 任意路徑，不能跑 git → build-time 產 JSON snapshot
- **Mermaid SSR**：必須 `dynamic(() => ..., { ssr: false })`
- **Auth**：複用現有 admin auth gate（`createClient` SSR + `user_roles` 表）

### 新增 npm 依賴
`react-markdown`、`remark-gfm`、`gray-matter`、`mermaid`

## References

- 詳細計畫：`/memories/session/plan.md`（session 內）
- 參考：`web/app/[locale]/admin/page.tsx`（auth gate 模式）
- 參考：`web/components/AdminTabNav.tsx`（tab 新增模式）
