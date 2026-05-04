# Tasks

## Phase A: 資料層（無 UI）

- [x] A1: 建立 `docs/specs/` 目錄結構 + README + _template
- [x] A1: 為現有計畫建立 spec stubs（此任務本身）
- [ ] A2: 建立 `docs/architecture/system-map.json`（agent/skill/scraper 關係）
- [ ] A3: 實作 `web/lib/specs/reader.ts`（listSpecs()，掃 parked/active/archive）
- [ ] A3: 實作 `web/lib/specs/parser.ts`（frontmatter + tasks - [x] / - [ ] 計數）
- [ ] A3: 實作 `web/scripts/build-specs-snapshot.ts`（Vercel-safe，prebuild 觸發）
- [ ] A3: `package.json` 加 `"prebuild": "tsx scripts/build-specs-snapshot.ts"`
- [ ] A3: 安裝 npm deps：`react-markdown remark-gfm gray-matter mermaid`

## Phase B: UI

- [ ] B1: `AdminTabNav.tsx`：type 加 `"specs"`，渲染新 tab
- [ ] B1: `web/messages/{zh,ja,en}.json` 加 `admin.tabs.specs`（三語）
- [ ] B2: 實作 `/admin/specs/page.tsx`（Kanban 4 欄，auth gate）
- [ ] B3: 實作 `/admin/specs/[slug]/page.tsx`（詳細頁：markdown render + tasks 進度條 + 複製 Copilot prompt 按鈕）
- [ ] B3: 實作 `web/components/SpecTabs.tsx`（proposal/tasks/notes 切換，client component）
- [ ] B3: 實作 `web/components/CopyCopilotPrompt.tsx`（按一下複製未完成 tasks）
- [ ] B4: 實作 `/admin/specs/architecture/page.tsx`（讀 system-map.json → Mermaid 圖）
- [ ] B4: 實作 `web/components/Mermaid.tsx`（dynamic import, ssr: false）

## Phase C: 收尾

- [ ] C1: `web/messages/{zh,ja,en}.json` 補完 `admin.specs.*` i18n keys
- [ ] C2: 更新 `.github/copilot-instructions.md`：新功能前先建 spec 的守則
- [ ] C3: 更新 `docs/ARCHITECTURE.md`：加入 spec-driven workflow 段落

## Verification

- [ ] `cd web && npm run build` 無 TS/build error
- [ ] `cd web && npm run lint` 通過
- [ ] `/zh/admin/specs` 顯示 4 欄 Kanban，各 spec 卡片正確
- [ ] 點 spec 卡片 → 詳細頁 render markdown，tasks 進度條正確
- [ ] 「複製 Copilot prompt」按鈕複製到剪貼簿
- [ ] `/zh/admin/specs/architecture` 顯示 Mermaid 架構圖
- [ ] 無痕視窗訪問 `/admin/specs` → 導向 `/auth/login`
