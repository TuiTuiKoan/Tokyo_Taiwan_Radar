# Tasks — Works 實體

每完成一步把 `- [ ]` 改 `- [x]` 並 commit。

## Phase 1: Schema

- [ ] 撰寫 `supabase/migrations/046_works_entity.sql`
- [ ] 在 Supabase Dashboard 套用 migration 046
- [ ] 在 `web/lib/types.ts` 新增 `Work` interface

## Phase 2: Backfill 觸發 case

- [ ] 建立月老（赤い糸 輪廻のひみつ）work：`work_type='film'`, `original_title='月老'`, `title_ja='赤い糸 輪廻のひみつ'`, `title_en='Till We Meet Again'`, `director='ギデンズ・コー'`, `release_year=2021`, `country='TW'`
- [ ] 指派 f970e4e3 與 4a8772ec 的 `work_id`

## Phase 3: Web 詳情頁

- [ ] 詳情頁查同 `work_id` 的其他 active events 並渲染「同作品其他場次」區塊
- [ ] 區塊空時隱藏（不要顯示空標題）
- [ ] EventCard 重用，避免另寫 UI
- [ ] i18n: `event.relatedScreenings.title`、`event.relatedScreenings.empty`（三語）

## Phase 4: Admin

- [ ] `web/app/[locale]/admin/works/page.tsx` works 列表 + 搜尋
- [ ] `web/app/[locale]/admin/works/[id]/page.tsx` 編輯頁
- [ ] AdminEventTable 增加 work_id 欄（顯示 title_ja，可點選跳到 work 編輯頁）
- [ ] 缺 work_id 且 category 為 movie/performing_arts 的事件標紅
- [ ] 「指派 work」action：dropdown 搜尋已有 work + 「+ 新增 work」按鈕

## Phase 5: Merger 行為

- [ ] `merger.py` Pass 1：兩 candidate 都有 `work_id` 且不同 → 跳過
- [ ] Pass 1：`category in ('movie','performing_arts')` 且 `location_name` 不同 → 寫 `merger_candidates`（依 Phase E 表結構）併標 `same_work_different_venue=true`
- [ ] dry-run 確認月老兩筆不再被自動合併

## Phase 6: Docs + Guards

- [ ] `.github/agents/architect.agent.md` 新 Guard：`Works Entity vs parent_event_id Guard`（兩者不互斥、職責分明）
- [ ] `.github/skills/agents/engineer/SKILL.md` 新 work 慣例段
- [ ] `docs/MERGER_WORKFLOW.md` 補 work_id 對 merger 的影響
- [ ] history.md 寫 ship 記錄

## Verification

- [ ] f970e4e3 詳情頁可看到 4a8772ec 卡片，反之亦然
- [ ] AdminEventTable 顯示 work_id 欄位正常
- [ ] `npm run build` pass、TypeScript no error
- [ ] `python merger.py --dry-run` 月老兩筆不被合併
- [ ] Vercel deploy 後人工檢查日/中/英三語顯示
