# Tasks — intent-homepage（意圖首頁）

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。設計細節見同資料夾 `proposal.md`（以下 `D-n` 指 proposal 的設計段落）。

## Phase 0: Worktree Setup（強制，Large feature）

- [ ] **先向使用者確認**實作要在哪個 worktree 進行（建議 `ttr-intent-homepage-worktree`／`feat/intent-homepage`），取得明確答覆才動工；主工作樹不得實作
- [ ] `git worktree list --porcelain` 驗證現況，依 `.github/instructions/git.instructions.md` § Isolated worktree 的 state matrix 建立或切換（branch missing → `git worktree add ttr-intent-homepage-worktree -b feat/intent-homepage`）
- [ ] idempotent append `ttr-intent-homepage-worktree/` 至 `.git/info/exclude`
- [ ] 本機計畫筆記（`~/.ai-notes/ttr/plan.md` 或 `/memories/session/plan.md`）寫入 slug `intent-homepage`
- [ ] 讀 `web/node_modules/next/dist/docs/` 中 proxy（middleware）、rewrite、redirect、ISR、private folder（`_` 前綴）相關章節，記下與 proposal D-2／D-8 假設不符之處，回寫 proposal
- [ ] 創辦人回覆 proposal 的 Q1、Q2、Q3（Q4〜Q8 可在對應 phase 前回覆）

## Phase A: 動態數字＋量測基礎＋baseline（S，可獨立上線）

- [ ] A-1 `web/lib/homepage/siteStats.ts`：`getActiveSourceCount()`（`sources.is_active = true`，`count: 'exact', head: true`），回傳向下取整到十位的顯示值；查詢失敗回傳 `null`
- [ ] A-2 i18n（zh → en → ja，同一 commit，Python 腳本）：`home.statHeroDynamic`（`{count}`，「日本全国」取代「47都道府県」）、`about.sourcesBodyDynamic`；舊 key 保留
- [ ] A-3 首頁 hero 與 `web/app/[locale]/about/page.tsx` 改用新 key；`count` 為 `null` 時隱藏數字但保留句子
- [ ] A-4 `web/app/[locale]/design/page.tsx:122-126` 寫死三語字串改用新 key（或明確標註為 mock）
- [ ] A-5 `ls supabase/migrations/ | sort | tail -5` 確認編號後，撰寫 `supabase/migrations/<next>_homepage_experiment_events.sql`（D-8 schema；anon insert-only＋`with check` 限制 `event_type` 與欄位長度；admin select；GRANT 依 `069_explicit_grants.sql` 慣例；檔頭 `APPLY STATUS: NOT APPLIED`）
- [ ] A-6 **使用者**於 Supabase Dashboard 套用 migration，執行驗證 SQL（anon 可 insert、anon 不可 select、非法 `event_type` 被拒），回報結果；更新 migration 檔頭為 APPLIED 與 `.github/instructions/database.instructions.md`
- [ ] A-7 `web/app/actions/record-homepage-event.ts`：沿用 `record-view.ts` 模式（排除 dev、排除 admin、吞錯），不存 IP／UA／referer／國家
- [ ] A-8 `web/components/home/ExperimentTracker.tsx`：首頁 mount 送 `view`（含 `is_first_view`，由 `ttr_vid` cookie 是否新建判定）；LINE CTA、投稿 CTA 點擊送事件；不得阻擋導覽；bot UA 不送
- [ ] A-9 實驗 id 先設為 `e0-baseline`、variant `current`，在**現行首頁**上線，累積 ≥ 2 週 baseline
- [ ] A-10 `/about` 新增「アクセス解析について」段落（三語），內容依 D-8 隱私段
- [ ] A-11 `scripts/homepage_experiment_report.py`（或 `.sql`）：各 variant 的首次造訪數、首次點擊率、LINE CTA 點擊率、Bayesian `P(變體 > 對照)`；唯讀
- [ ] A-12 Phase A 結束時計算「每週首次造訪 ja 人數」與 e1 預估所需週數，依 D-8 流量閘門決定走 live 實驗或質性替代方案，結果寫回 proposal 的 Decision Log

## Phase B: 「レーダーを見る」路由搬遷（M，可獨立上線）

- [ ] B-1 新增 `web/app/[locale]/radar/page.tsx`：原樣搬遷現行首頁的資料抓取、`FilterBar`、`ListScrollManager`、`EventShelf`、`EventListClient`、`ItemList` JSON-LD；`revalidate = 600`
- [ ] B-2 `/radar` 的 `generateMetadata`：三語 site name、canonical `/{locale}/radar`（不帶 query）、`alternates.languages` 含 `x-default`；刪除任何同檔的靜態 `metadata`
- [ ] B-3 `web/lib/homepage/legacyRedirect.ts`（純函式）：`/{locale}?<篩選參數>` → `/{locale}/radar?<同參數>`；參數白名單＝`q, category, from, to, paid, timeMode, location, city, sort`；未知參數（如 `utm_*`）不觸發轉址但若有篩選參數則一併保留
- [ ] B-4 `web/proxy.ts` 呼叫 B-3，回傳 308；確認 `config.matcher` 與既有 bot 偵測、Supabase session 邏輯順序不受影響
- [ ] B-5 `web/tests/homepage-legacy-redirect.test.ts`：無參數不轉、篩選參數轉址、僅 `utm_source` 不轉、三種 locale、多值 `category=a,b` 保留
- [ ] B-6 `BackToListButton.tsx` → `/${locale}/radar`；`Navbar.tsx` 新增「レーダーを見る」（i18n `nav.radar` 三語），logo 仍回首頁
- [ ] B-7 `web/app/sitemap.ts` 新增 `/{locale}/radar`（priority 0.9）
- [ ] B-8 `npm run test:security:jsonld` 通過；`/radar` 頁面 build 為 ISR（非完全動態）
- [ ] B-9 部署後驗證：`curl -sI https://tokyotaiwanradar.com/ja?category=movie` 為 308 → `/ja/radar?category=movie`；`/ja/radar` 200；活動詳情頁「回到列表」導向 `/radar` 並恢復捲動位置

## Phase C: 新首頁 P0 區塊（M，以預設變體上線）

- [ ] C-1 **先量化再實作**：以 live 資料（service role，唯讀）計算 D-3 每個 intent／mode／channel 在 `when=week`、全国與各地區下的平均筆數（relevance 回填後以 `feed_tier='home'` 集合重算一次），並各抽 20 筆人工判定 precision；結果寫回 proposal，必要時調整映射表
- [ ] C-2 `web/lib/homepage/when.ts`：JST 計算 `week`（今天起 7 天）與 `weekend`（本週六日），以「活動期間與區間有交集」判定；`web/tests/homepage-when.test.ts` 含跨月、跨年、長期展、`end_date = null`、JST 午夜邊界
- [ ] C-3 `web/lib/homepage/intents.ts`：`IntentId`／`ModeId`／`ChannelSlug`、映射表（只存 i18n key 與 Category／EventForm）、`matchesIntent()`、共通排除；`web/tests/homepage-intents.test.ts`
- [ ] C-4 `web/lib/homepage/eligibility.ts`：`homeQuery()` 薄包裝 `taiwan-relevance-scoring` 的 `applyHomeFeed`（`web/lib/relevance.ts`），`HOMEPAGE_SELECT_FIELDS` 含 `feed_tier`；**不得**自訂分數門檻、不得把 NULL 當 home（D-6）。對方 migration 097 未套用前，只能在本機／preview 開發
- [ ] C-5 `web/lib/eventFilter.ts`：新增 `intent`／`mode`／`channel`／`when` 參數（`EventFilters` 型別、`buildInitialFilters`、`filterEvents`）；有意圖參數時只保留 `feed_tier === 'home'`（使用對方匯出的 `isHomeFeed(e)`；`/radar` payload 需帶 `feed_tier`）；`EventFilterContext.tsx` 的 URL 同步納入新參數
- [ ] C-6 `/radar` 顯示意圖 `FilterChip`（可移除）與意圖說明句；`FilterBar` 顯示 `when` 選項（沿用 custom button＋panel，不用原生 `<select>`）；空結果時顯示「今月」放寬連結
- [ ] C-7 `web/lib/homepage/picks.ts`：D-4 規則（最新已發布 `weekly_broadcast` → `announcement_events` → 過濾 → 排序 → 5–8 筆 → 自動補位 → < 3 筆隱藏 → 未發布時退回上一則）；`web/tests/homepage-picks.test.ts`
- [ ] C-8 `web/lib/homepage/region.ts`＋`proxy.ts`：`x-vercel-ip-country-region` → `LocationKey` 對照表（47 都道府縣代碼全覆蓋，單元測試）；寫 `ttr_region_guess`；使用者選擇寫 `ttr_region`；不使用 `navigator.geolocation`
- [ ] C-9 `web/lib/homepage/flags.ts`：`SHOW_PERSON_SECTION`、`SHOW_TOPIC_FOLLOW`、`SHOW_COMMUNITY_SECTION`、`SHOW_FESTIVALS` 預設 `false`
- [ ] C-10 交 Designer 產出首頁視覺規格（D-10 元件對照、所有互動狀態、light／dark、reduced motion、手機版），存入設計筆記後再實作
- [ ] C-11 元件：`web/components/home/HomeHero.tsx`（`MascotAvatar` 縮小＋主標副標＋動態數字）、`IntentEntry.tsx`（`CARD_LINK`）、`ModeRow.tsx`（`PillButton`）、`RegionSwitcher.tsx`（`DesignSelect`）、`WeeklyPicks.tsx`（`Badge`／`DateChip`／`CategoryThumbnail`）、`ChannelStrip.tsx`、`HomeCtas.tsx`（投稿 CTA＝`Button`、LINE CTA＝`#06C755`、レーダーを見る）
- [ ] C-12a **上線閘門**：確認 `taiwan-relevance-scoring` Phase 2 回填完成（active parent 中 `feed_tier IS NULL` = 0，live 查詢結果附在 commit 或 Decision Log），且 `/radar/page.tsx` 已套用 `applyRadarFeed`（`grep -n applyRadarFeed web/app/[locale]/radar/page.tsx`）；未通過不得部署 C-12
- [ ] C-12 `web/app/[locale]/page.tsx` 改為新首頁：只做少量查詢（picks、來源數、公告 ≤ 3 筆且排除 `weekly_broadcast`）；不再撈全部 events；輸出 picks 的 `ItemList` JSON-LD
- [ ] C-13 i18n（zh → en → ja 同一 commit，Python 腳本）：`home.intent.*`、`home.mode.*`、`home.copy.{A,B,C}.{title,subtitle}`、`home.picks.*`、`home.channels.*`、`home.region.*`、`home.radarCta`、`home.submitCta`、`home.lineWeekly`、`radar.*`、`filters.when*`；每個 key 三語 grep 驗證
- [ ] C-14 （選做）D-4b 季節の台湾フェス：以 `sources` 與 `scraper/main.py` `SCRAPERS` 核對祭典來源 id，未來 12 個月、每來源最近一場；0 筆不渲染；`SHOW_FESTIVALS` 開啟
- [ ] C-15 硬編碼檢查：`grep -rn '[一-鿿]' web --include='*.tsx' | grep -v 't(' | grep -v 'MARKERS' | grep -v '//'` 對新增檔案無命中；`grep -E "bg-white|bg-gray-|text-gray-|border-gray-|divide-gray-"` 對新增檔案無命中
- [ ] C-16 `web/tests/e2e/homepage.smoke.spec.ts`：首頁 200、意圖入口點一下到 `/radar?intent=…&when=week` 且有結果或放寬提示、地區切換改寫入口連結、light／dark 截圖、手機寬度無橫向捲動

## Phase D: 實驗機制與執行（M）

- [ ] D-1 **Spike**：proxy cookie 指派＋rewrite 到變體路由＋ISR，在 preview 部署確認 `x-vercel-cache`、變體不串、首頁未變成完全動態；結果寫回 proposal（R5）
- [ ] D-2 `web/lib/experiments/homepage.ts`：實驗 id、變體清單、權重、預設變體；環境變數 `HOMEPAGE_EXPERIMENT` kill switch
- [ ] D-3 變體路由（名稱依 Phase 0 文件確認，避免 private folder）＋`generateStaticParams`；`/ja` 才指派，`zh`／`en` 固定預設變體
- [ ] D-4 bot（`BOT_PATTERNS`）不指派、不記錄；`?hp_preview=<variant>` 強制顯示、不記錄、`noindex`
- [ ] D-5 `ExperimentTracker` 改送實際 experiment／variant；補 `intent_click`、`mode_click`、`channel_click`、`pick_click`、`radar_click`
- [ ] D-6 （若 Q5 為是）各變體使用不同 LINE「友だち追加経路」URL
- [ ] D-7 **e1**：`L3` vs `L4`（文案固定 Q1 預設），最短 2 週、最長 6 週，每週跑報表；依 D-8 判定規則決定，寫入 Decision Log
- [ ] D-8 **e2**：文案 A／B／C（版型＝e1 結果），同上判定規則
- [ ] D-9 （若 A-12 判定流量不足）質性替代：訪談中以 `?hp_preview=` 做 first-click／5 秒測試；X／IG 圖卡三文案互動比較或 LINE 單題投票；創辦人裁決並記錄理由

## Phase E: 決策落地與清理（S）

- [ ] E-1 移除落選變體的元件、路由與實驗分支程式；首頁固定為勝出組合；`HOMEPAGE_EXPERIMENT` 設 `off`
- [ ] E-2 i18n：落選文案 key 的刪除另開有意識的 commit，commit message 寫明刪除清單；`git show <hash> -- 'web/messages/*.json' | grep '^-'` 只出現預期刪除
- [ ] E-3 實驗結束後 90 天刪除 `homepage_experiment_events` 原始資料（保留匯總），或改為長期最小化埋點（需創辦人決定）
- [ ] E-4 更新 `.github/instructions/web.instructions.md`（目錄結構：`page.tsx` 為意圖首頁、`radar/` 為全部列表；Next 版本；Categories 段落指向 `web/lib/types.ts`）
- [ ] E-5 更新 `docs/ARCHITECTURE.md`（首頁實驗 server action、proxy 的轉址／指派／地區推定）
- [ ] E-6 交 History Teller：Architect SKILL「Homepage Inline Card Divergence Guard」標註 superseded；記錄本 spec 的教訓

## Phase F: 依賴 spec 上線後（各自觸發）

- [ ] F-1 `taiwan-relevance-scoring` 若新增 tier 值或改名：依對方 I-1「新增 tier 值必須同步修改兩份 spec」，同步更新 D-6 與 `eligibility.ts`；回歸測試
- [ ] F-2 `person-topic-entities` 上線後：`CHANNELS` 改用 `getTopicChannels()`（slug 一致性測試）；協調對方 helper 支援 `feed: 'home'`（首頁一律傳 `home`）；開啟 `SHOW_TOPIC_FOLLOW`、`SHOW_PERSON_SECTION`（`getFeaturedPeople` < 4 人不渲染）；チャンネル連結改到 `/[locale]/topics/<slug>`，`/radar?channel=<slug>` 308 到 Topic 頁
- [ ] F-3 `social-affordance-tags` 上線後：`watch`／`learn`／`talk` 改用交流強度標籤，映射表降為 fallback；今週の台湾卡片顯示通過 precision 門檻的門檻標籤
- [ ] F-4 `community-directory` 上線後：開啟 `SHOW_COMMUNITY_SECTION`

## Verification

- [ ] `cd web && npx tsc --noEmit` 0 error
- [ ] `cd web && npm run lint`（changed-hunk 無新錯誤）
- [ ] `cd web && npm run build` 成功；`/[locale]`、`/[locale]/radar` 為 ISR
- [ ] `cd web && npx tsx --test tests/homepage-*.test.ts` 全通過
- [ ] `cd web && npm run test:security:jsonld` 通過
- [ ] `cd web && npx playwright test tests/e2e/homepage.smoke.spec.ts` 通過；`npm run test:e2e:dark-smoke` 無回歸
- [ ] i18n：三語 key 數一致；`categories` late-added keys 仍存在；無非預期 key 刪除
- [ ] 部署驗證（production custom domain）：`/ja` 新首頁、`/ja?category=movie` 308 → `/ja/radar?category=movie`、`/ja/radar` 200、sitemap 含 `/radar`、首頁 HTML 不含「100+」
- [ ] `homepage_experiment_events` 在 production 有 `view` 列且無 admin／bot 列；anon 無法 select
- [ ] 上線後 4 週 GSC：`/ja`＋`/ja/radar` 的曝光與點擊相對前 4 週無顯著下滑（R4）
- [ ] push 前取得使用者明確同意；回報使用「已推送／本地 only／未 commit」標籤
