# Tasks — Merger Phase E (Multi-signal Pass 4)

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。

## Phase 1: Helper functions

- [ ] 在 `scraper/merger.py` 新增 `_date_overlap(primary, secondary, days=7) -> bool`
- [ ] 新增 `_prefecture_match(primary, secondary) -> bool`（讀 `location_prefectures`）
- [ ] 新增 `_organizer_match(primary, secondary) -> bool`（substring ≥ 4 char 或 token overlap ≥ 50%）
- [ ] 新增 `_keyword_overlap(primary, secondary, min_shared=2) -> bool`（4-gram 抽取，先 strip HTML/URL/標點）
- [ ] 單元測試：對 gnews `c1ba79b6` ↔ taiwan_matsuri 「台湾祭in群馬太田2026」全部 4 訊號回 True

## Phase 2: Scoring + candidate pipeline

- [ ] 新增 `_multi_signal_score(primary, secondary) -> int`（前提 secondary ∈ `_NEWS_SOURCES`）
- [ ] 新增 `Pass 4` 主迴圈：對所有未被 Pass 0–3 合併的孤兒事件，與所有 active 主事件配對；`score ≥ 3` 寫候選
- [ ] dry-run mode 印出候選對與訊號明細，不寫 DB

## Phase 3: Database + audit table

- [ ] 撰寫 `supabase/migrations/045_merger_candidates.sql`：欄位 `id, primary_event_id, secondary_event_id, score, signals jsonb, created_at, reviewed_at, reviewed_by, decision`（`pending|approved|rejected`）
- [ ] 在 Supabase Dashboard 套用 migration 045
- [ ] `Pass 4` 寫入 `merger_candidates` 表（upsert by `(primary_event_id, secondary_event_id)`）

## Phase 4: Admin review UI

- [ ] 新增 `web/app/[locale]/admin/merger-candidates/page.tsx`：列出 `decision = pending` 的候選對，並排顯示兩事件
- [ ] approve action：寫入 `secondary_source_urls`、設 secondary `is_active=false` + `deactivated_by_pass='merger_pass_4_manual'`、更新 `decision='approved'`
- [ ] reject action：更新 `decision='rejected'`，下次 Pass 4 跳過
- [ ] AdminTabNav 加入入口

## Phase 5: Documentation + Guards

- [ ] 在 `.github/agents/architect.agent.md` 新增 `Merger Pass 4 Multi-Signal Guard`（規範 4 訊號定義、`score ≥ 3` 門檻、永不自動寫 `parent_event_id`）
- [ ] 在 `.github/skills/agents/engineer/SKILL.md` 新增 Pass 4 helper 規則段
- [ ] 在 `docs/MERGER_WORKFLOW.md` 補 Pass 4 流程圖
- [ ] history.md 寫 ship 記錄

## Verification

- [ ] `python merger.py --dry-run` 全量跑完，Pass 4 候選對數量 ≤ 30
- [ ] gnews `c1ba79b6` 出現在候選清單，primary 為 taiwan_matsuri/iwafu「台湾祭in群馬太田2026」
- [ ] 隨機抽 10 對候選人工檢查，accuracy ≥ 80%
- [ ] 既有 Pass 1/2 命中對不被 Pass 4 覆寫
- [ ] `npm run build` pass、TypeScript no error
- [ ] Vercel deploy 後 `/admin/merger-candidates` 可正常 approve/reject
