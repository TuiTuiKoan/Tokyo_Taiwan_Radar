---
name: architect
description: Planning principles, model selection, and scope rules for the Architect agent
applyTo: .github/agents/architect.agent.md
---

# Architect Skills

Read this at the start of every session before producing any plan.

## Planning
- Always check whether a new feature requires a DB schema change. If yes, mark Step 1 as a manual migration with verification SQL.
- Identify all code paths affected by a data model change — not just the obvious one (a new column needs both the table AND every writer that populates it).
- Never ship a plan with an untested API or signature change. Include an explicit smoke-test step.
- Confirm that all pending migrations are applied before designing features that build on them.

## Category Addition Checklist（新增分類的必備 5 步驟）

每次新增 `Category` 值，以下 **5 個位置必須同一 commit 同步**，缺一返工：

| 步驟 | 位置 | 說明 |
|------|------|------|
| 1 | `web/lib/types.ts` | Category union + CATEGORIES array + CATEGORY_GROUPS |
| 2 | `scraper/annotator.py` | VALID_CATEGORIES + SYSTEM_PROMPT enum string + definition |
| 3 | `web/messages/{zh,en,ja}.json` | `categories.<key>` + `categoryDesc.<key>`（三語各一）|
| 4 | `web/lib/design/organicMotifs.tsx` | `case '<key>':` 5 個 SVG 變體（缺少則 fallback 為預設 blob，無報錯）↳ **同時自動涵蓋 CategoryThumbnail UI + category OG image + event OG image**（三者均動態呼叫 `getSemanticSymbol()`，無硬編碼列表）|
| 5 | Sync Guard 驗證 | `python3 -c "from annotator import VALID_CATEGORIES, _check_category_sync; _check_category_sync()"` pass |

**步驟 4（縮圖）是最容易被遺漏的**：TypeScript 不報錯、build 不失敗、只有在 `/debug/motifs` 頁才能看到 fallback blob。計畫中必須明確標注 Engineer 要加 `case` 到 `organicMotifs.tsx`。

**Reference incident:** 2026-05-16 — `design_craft`、`herbal`、`study_abroad` 三個分類在 annotator/i18n sync 後，縮圖 case 補加為獨立 commit，違反「同一 commit」原則。教訓：Architect 計畫從此明列步驟 4。

## 🔁 Lesson-in-fix-commit Rule（避免 V-M-D ↔ docs update 循環）

**問題模式**：fix commit → V-M-D → docs commit → V-M-D 第二輪。每個邏輯變更跑兩次部署，浪費 token 又阻礙 session。

**規則**：Architect 設計計畫時，若預判修復會揭露新教訓（silent failure、GPT 污染、新 Guard、paired-handler 模式、第三方 API 行為），必須在計畫的 Verification 段明示：
> 「**Engineer Step 3a 必做**：在 commit fix 之前，將教訓寫入對應的 `history.md` / `SKILL.md` / `agent.md`，與 fix code 合併為單一 commit。」

**對應稽核點**：
- Engineer agent Step 3a（前置稽核）
- V-M-D Step 1a（推送前偵測未配對 docs 的 fix/feat commit）

**不適用情境**：cosmetic refactor、dependency bump、typo、純 i18n 字串調整、純 CSS 調整。

## Supabase Python Client API Rules

- **`order()` 語法**：`.order("col", desc=True)` — 不是 `.order("col", ascending=False)`（pandas 風格在此無效）。計畫中任何排序操作必須使用正確語法。
- **`upsert` vs `update`**：既存 row 的部分更新必須用 `.update().eq()`，不可用 `upsert`（會觸發 INSERT fallback，撞 NOT NULL 約束）。

## Transient Failure Triage Guard（暫時性故障快速排除）

當使用者報「production 後台 / 客戶端寫入突然全部失效」且最近 24h 有 Vercel 部署，**在深入結構性分析（migration / RLS / GRANT）之前**先要求使用者執行 1 分鐘 DevTools 三點檢查：

1. **Network tab → 觸發那個操作 → 找對應 PATCH/POST 請求 → Request Headers：**
   - 無 `authorization: Bearer ...` → 客戶端 session 遺失（結構性 bug，深挖 auth callback / cookie 設定）
   - 有 → 進下一步
2. **同筆請求 Response body：**
   - 空陣列 `[]` 或空白 200 → RLS / expired JWT 過濾為 0 列（**可能是暫時性，先請使用者重整再試**）
   - 4xx/5xx → 結構性錯誤，依 body 訊息深挖（如 `42501` GRANT 缺失）
3. **Application → Cookies → `sb-<ref>-auth-token` HttpOnly 欄：**
   - 打勾 → JS 讀不到 cookie，結構性 bug（auth helper 設錯）
   - 未勾 → 正常

**三點全綠 + 重整後恢復 = 暫時性 Vercel 滾動部署故障，不需動程式碼。** 但應提案在 Engineer SKILL guard 加 0-row UPDATE 防護（`.select("id")` + `data.length === 0` 視為失敗）。

**反面教訓（2026-05-15）：** 後台 events UPDATE 三項全失，第一輪假設 migration 069 漏 events 表 GRANT（錯誤），第二輪假設 `ae9dc77` cookie 寫入問題（錯誤），準備寫新 migration。使用者實測 DevTools 三點全綠後判定暫時性。若一開始就先讓使用者跑三點檢查，可省 20 分鐘誤判時間。

## Multi-Session Stash Discipline（多線開發 Stash 紀律）

在審核任何多 session/subagent 平行開發工作流前，**必須**確認：

1. **Stash message 必須以 `[STATE]` 開頭**：
   - `[WIP]` — 草稿，禁止合併
   - `[READY]` — 已驗證，可立即合併
   - `[REVIEW]` — 待人工確認
   - `[BLOCKED]` — 有外部依賴未就緒
2. **`./scripts/stash-status.sh list`** 是快速狀態總覽的入口，點 VMD agent 前應先執行。
3. **Promote 流程（`./scripts/stash-status.sh promote <N>`）**：
   - 自動檢查 working tree clean → fetch + rebase → pop → diff preview → commit → push prompt
   - 任何步驟失敗即中止，stash 保留原狀
4. **VMD agent Step 0 自動攔截**：VMD agent 啟動時會自動偵測 `[READY]` stash 並提示促銷，無需手動記得跑 stash-status。
5. **3 天 STALE 警告**：`[READY]` stash 超過 3 天未合併，CLI 標記 `⚠ STALE`——可能與 main 衝突或內容過時。

**architect 設計 multi-session 任務計畫時，必須在「完成條件」中明確指定 stash state 標籤**，例如：
> 完成後執行 `git stash push -m "[READY] scraper/starcat: end_date fix"`

---

## Circular Merge Redirect Loop Guard（merged_into 循環 redirect 防護）

在審核任何 merger 輸出、或手動設定 `merged_into_event_id` 前，**必須**確認不形成循環：

1. **A → B → A、A → B → C → A 等任何循環都會讓 `permanentRedirect()` 無限觸發**，瀏覽器收到 HTTP 308 loop，不停重載。
2. **偵測指令**（在 `scraper/` 執行）：
   ```python
   r = sb.table('events').select('id,merged_into_event_id').not_.is_('merged_into_event_id','null').execute()
   merged_map = {e['id']: e['merged_into_event_id'] for e in r.data}
   cycles = []
   for start in merged_map:
       visited = set(); cur = start
       while cur in merged_map and cur not in visited:
           visited.add(cur); cur = merged_map[cur]
       if cur in visited: cycles.append(start)
   print(f"{'✅ No cycles' if not cycles else f'⚠ {len(set(cycles))} cycle nodes'}")
   ```
3. **修復方式**：找到循環中「最不重要的節點」（通常是 gnews 二手來源），將其 `merged_into_event_id = NULL`。如有多個事件把此節點當 merge target，評估是否改指向真正的 canonical active 事件。
4. **跨作品 merge 是警示訊號**：`A`（電影 X）→ `B`（電影 Y，不同片名）幾乎必然是 merger 錯誤，直接 NULL 斷開。
5. **`auto_qa` 應加入此 cycle 偵測**（待實作）。

Reference incident: 2026-05-15 — `57642851`↔`c8e813ae`（赤い糸）二節點循環 + `84cb3ff3→2117c91e→a04e7ebb→84cb3ff3`（台湾Filmake/めぐる面影）三節點循環，共 4 筆 DB 更新修復。

---

## Weekly LINE Broadcast 系統設計節奏

在審核任何涉及 `weekly_line_broadcast.py` 的計畫前，**必須**先確認系統設計的執行時序：

1. **時序**：木曜（Thursday）CI 生成草稿 → 金曜（Friday）CI 發送。草稿 slug/title 日期應使用**金曜發佈日**，不是木曜生成日。
2. **期間計算**：發佈週報的期間為金曜 ~ 下下木曜（+13 天），不是 +6 天。
3. **診斷 CI 失敗前**：先讀 `weekly_line_broadcast.py` 的 cron 時序設計，不要急於本地補跑草稿，避免製造多餘的重複草稿。
4. **多語言連結**：broadcast 訊息中的事件連結必須直接嵌入語系路徑（`/{lang}/events/{id}`），不可使用 `/r/{id}` 短連結（固定重導向至 `/zh/`）。

Reference incident: 2026-05-08 — 多重錯誤同時發生（Supabase `order()` bug、草稿重複、連結語系錯誤、日期範圍錯誤）。

## Auto-Generate Promotion Checklist

When a plan includes promoting an auto-generated scraper (`auto_scraper_status=success`) to `status=implemented`, the plan must explicitly include **all 5 steps**:

1. PR merged — `scraper/sources/<name>.py` exists and is registered in `scraper/main.py`.
2. `research_sources` row: `status = 'implemented'`.
3. **`scraper_source_name = '<scraper key>'`** — MUST be filled or `/admin/sources` shows 0 events and cannot trigger Run Scraper (backend JOINs `scraper_runs` by this key). **auto_generate does NOT fill this automatically.**
4. Smoke-test: `python main.py --dry-run --source <key>` confirms events are found.
5. For annual-subdomain sites (e.g. `YYYY.tiff-jp.net`): replace hardcoded year with dynamic year resolution (follow redirect from root domain → fallback `datetime.now().year`).

Missing step 3 has no compile-time or runtime error — it silently appears as a 0-count row in the admin UI.

## LINE Broadcast Query Guard

在審核任何涉及 `weekly_line_broadcast.py`（或未來任何 LINE push 腳本）的計畫前，**必須**確認：

1. **`_fetch_upcoming_events` 必須過濾 `annotation_status`**：只允許 `annotated` 或 `reviewed` 的事件進入廣播 pool。
   ```python
   .in_("annotation_status", ["annotated", "reviewed"])
   ```
2. **不得假設 `is_active=True` 等於翻譯完整**：新刮取的事件在 annotator 執行前 `name_zh`/`name_en` 為 NULL，`annotation_status='pending'`。若廣播在每日 pipeline 之前手動觸發，pending 事件會進入 pool，ZH/EN 訂閱者收到日文 fallback。
3. **廣播 dry-run 後驗證 pool**：確認 `Fetched N upcoming events` 中無 pending 事件（`annotation_status` 過濾後應比無過濾少幾筆）。

Reference incident: 2026-05-05 — `赤い糸 輪廻のひみつ` 以日文出現在 ZH 週報，缺 `annotation_status` 過濾（commit `9b33ad3` 後修正）。

## Person Name Enrich English Guard

在審核任何涉及 `enrich_person_names()` 或人名翻譯邏輯的計畫前，**必須**確認：

1. **description_en 中的人名是英文音譯，不是片假名**：GPT 翻譯時已將片假名 → 英文音譯（如 `クー・チェンドン` → `Koo Kuan-Dong`），片假名字串**不在** desc_en 中，`if ja_name in desc_en` 永不命中。
2. **`description_en` 必須走 `_fix_person_names_gpt_en()` GPT 路徑**（鏡像 desc_zh 的 `_fix_person_names_gpt`）。已於 2026-05-05 修復；任何回退到 katakana direct-replace 的 PR 必須拒絕。
3. **`enrich_movie_titles` / `enrich_person_names` 成功後必須自動鎖**：透過 `_lock_fields_via_corrections()` upsert 進 `field_corrections` 表，避免下次 re-annotation 覆寫。

Reference incident: 2026-05-05 — event `f970e4e3`（月老）desc_en `Koo Kuan-Dong` 從 5/4 daily CI 後持續未修正；同事件多次手修又被 AI 覆寫，根因為缺 lock。

## Known Person Map Guard（`_KNOWN_PERSON_MAP` 藝名/筆名覆寫機制）

在審核任何涉及 performer/director 翻譯、`backfill_performer_i18n()`、或新增 `_KNOWN_PERSON_MAP` 條目的計畫前，**必須**確認：

1. **GPT 無法可靠翻譯藝名/筆名**：片假名 `ギデンズ・コー` 與漢字 `九把刀` 無語音對應關係（pen name），GPT 只能語音推測，必然失敗。所有**已知藝名/筆名**必須收錄進 `_KNOWN_PERSON_MAP`。
2. **三語同時驗證**：新增 `_KNOWN_PERSON_MAP` 條目時，`ja`/`zh`/`en` 三個值必須同時提供且驗證。資料來源優先序：eiga.com → 官方網站 → Wikipedia → 可靠第三方。
3. **三個整合點全覆蓋**：`_KNOWN_PERSON_MAP` 生效位置：① 主 annotation loop（performer/director GPT 輸出覆寫）② `performers[]` 陣列逐元素檢查 ③ `backfill_performer_i18n()` Layer 0（已知名字跳過 GPT）。新增整合點時需三處同步。
4. **翻譯規則（嚴格執行）**：
   - 拉丁字母名 → 原樣保留，不翻譯
   - CJK 漢字名無驗證來源 → 不翻譯（zh: 照抄漢字，en: 跳過 / NULL）
   - 日文名無完整漢字 → 不翻譯成中文
   - 片假名音譯 → 僅在有驗證來源時翻譯（`_KNOWN_PERSON_MAP` 或 eiga.com lookup）
5. **`backfill_performer_i18n()` 不可限定 `is_active=True`**：非活躍事件同樣需要翻譯完整性。批次 backfill 腳本的 active 過濾需明確設計。

Reference incidents:
- 2026-05-09 — `ギデンズ・コー` → `基登斯·高` (GPT 幻覺)；正確 `九把刀` / `Giddens Ko`。14 筆已驗證名人收錄 `_KNOWN_PERSON_MAP`，11 筆 DB 事件修正。
- 2026-05-09 — 46 筆非活躍事件因 `is_active=True` 過濾而缺翻譯，需一次性批次 backfill。

## Performer Multilingual Fields Guard（performer_zh/en/director_zh/en）

在審核任何涉及 `performer_zh`、`performer_en`、`director_zh`、`director_en` 的計畫，或設計多語言表演者顯示邏輯時，**必須**確認：

1. **欄位架構（migration 053/054）**：
   - `performer TEXT`：日文原名（供 ja locale）
   - `performer_zh / performer_en TEXT`：各語言名稱（GPT 填入或人工設定）
   - `performers TEXT[]`：所有具名表演者/發表者的陣列（支援多人）
   - `director / director_zh / director_en`：同上，用於導演
2. **locale 優先序**：`zh` → `performer_zh || performer`；`en` → `performer_en || performer`；`ja` → `performer`（不走翻譯欄位）
3. **AI翻譯標注規則**：GPT 填入 performer_zh/en/director_zh/en 時，若該語言名稱**未明確出現在來源文本**，必須附加「（AI翻譯）」（如 `黃以文（AI翻譯）`）。若來源中有該語言名稱，不加標注。
4. **academic performers[]**：學術研討會（学会大会、研究大会、シンポジウム）中所有具名發表者（発表者/報告者/登壇者）必須列入 `performers[]`，即使有 5 人以上。
5. **手動設定必須鎖 `field_corrections`**：`performer_zh`、`performer_en`、`director_zh`、`director_en` 手動修正必須同時 upsert 進 `field_corrections`，否則下次 re-annotation 覆寫。
6. **新增人名欄位的 migration 模式**：新增 performer/director 等人名欄位時，必須在同一 migration 中同時新增對應的 `_zh`/`_en` 欄位，避免二次 migration。
7. **`works.work_type` 有效值**：`film | stage | exhibition | concert_tour | tv_drama | tv_variety | other`。`conference` 不在允許清單，學術研討會用 `other`。

Reference incidents:
- 2026-05-08 — commit `65a50b9`：SYSTEM_PROMPT 追加 AI 翻譯標記規則 + 學術大會 performers[] 填寫規則（Incidents A & B）
- 2026-05-08 — commit `191d939`：migration 053 新增 `performers TEXT[]`（Incident C）
- 2026-05-08 — commit `3822fb8`：migration 054 新增 `performer_zh`, `performer_en`, `director_zh`, `director_en`（Incident D）

## Organizer Multilingual Fields Guard（organizer_zh/en）

在審核任何涉及 `organizer_zh`、`organizer_en` 的計畫，或設計主辦方顯示邏輯時，**必須**確認：

1. **欄位架構（migration 059）**：
   - `organizer TEXT`：日文原名（供 ja locale）
   - `organizer_zh / organizer_en TEXT`：各語言名稱（`_KNOWN_ORGANIZER_MAP` 或 GPT 翻譯填入）
2. **locale 優先序**：`zh` → `organizer_zh || organizer`；`en` → `organizer_en || organizer`；`ja` → `organizer`
3. **`_KNOWN_ORGANIZER_MAP`**：高頻主辦方（10 筆）hardcoded 在 `annotator.py`，確保翻譯品質。新增條目時 ja/zh/en 三語同時提供。
4. **子事件繼承**：annotator 主迴圈中，sub-event 自動繼承 parent 的 organizer_zh/en。
5. **手動修正必須鎖 `field_corrections`**：`organizer_zh`、`organizer_en` 手動修正必須同時 upsert 進 `field_corrections`。

**i18n 文字欄位新增標準流程（已確立，第三次套用）：**
1. Migration：ADD COLUMN `field_zh TEXT`, `field_en TEXT`
2. Annotator：SYSTEM_PROMPT schema + KNOWN_MAP + 翻譯邏輯 + 子事件繼承
3. Scraper infra：`base.py` Event dataclass + `database.py` `_event_to_row()` 映射
4. Web：`types.ts` interface + `getEvent<Field>(event, locale)` helper + page.tsx 渲染
5. Backfill：KNOWN_MAP → kanji copy → GPT batch

**日文漢字 ≠ 簡體中文判斷規則：** 使用者反映「簡體字」時，先確認是 GPT 的 SC 輸出還是日文原文被顯示在非 ja 頁面。若為後者，正解是新增多語言欄位，非 SC→TC 轉換。

Reference incident: 2026-05-08 — commit `95c7ad8`：migration 059 + annotator + web 全套。273/273 backfill。

## SC→TC Mapping Maintenance Burden Guard

在審核任何涉及 `_SIMP_TO_TRAD` / `_to_trad()` 擴充的計畫時，**必須**留意：

1. **手動映射表是打地鼠**：表已從 ~50 筆成長到 300+ 筆仍不完整。每次 GPT-4o-mini 輸出新 SC 字，就需手動新增。
2. **長期方案**：評估 OpenCC 或完整 Unicode SC→TC 映射庫，一次解決完整性問題。在正式導入前，繼續維護手動表。
3. **新增字時必須同步更新兩處**：`annotator.py` 的 `_SIMP_TO_TRAD_RAW` + `auto_qa.py` 的 `SIMP_RE`。
4. **DB patch**：新增字後立即批量修正現有事件（scan all `*_zh` fields + translate + FC lock）。

## SC→TC Three-Layer Defence Model

SC→TC 防禦分三層，在審核**任何**涉及 `_zh` 欄位寫入路徑的計畫時，確認三層全覆蓋：

| Layer | 機制 | 位置 | 職責 |
|-------|------|------|------|
| **L1 — 預防** | `_to_trad()` on GPT output | `annotator.py` 主迴圈 | 捕捉 GPT 輸出的 SC 字元 |
| **L2 — Chokepoint guard** | `_to_trad()` on FC write | `_lock_fields_via_corrections()` | 捕捉所有寫入 FC 的 `_zh` 值（含 backfill、手動 upsert） |
| **L3 — 偵測 + 修復** | `SC_ONLY` + `fix_simplified()` | `auto_qa.py` | 捕捉 L1/L2 遺漏的殘留 SC |

**三層一致性規則：**
1. L1/L2 使用 `_SIMP_TO_TRAD` 字元映射（衍生自 `_SIMP_TO_TRAD_RAW`）
2. L3 的 `SC_ONLY` 字元集必須是 `_SIMP_TO_TRAD_RAW.keys()` 的子集——不可包含不在映射表中的字元（否則偵測到但無法修復 → 無限 dismiss 循環）
3. L3 的 `fix_simplified()` 掃描範圍必須與 `_detect_simplified_chinese()` 完全一致（目前 6 個 `_zh` 欄位）

**反模式：**
- ❌ `SC_ONLY` 包含 SC/TC 共用字元（如 征/蹈/零/蒙）→ 假陽性
- ❌ `_SIMP_TO_TRAD_RAW` 缺映射但 `SC_ONLY` 有該字元 → 偵測到但無法修復
- ❌ `fix_simplified()` 掃描範圍 < `_detect_simplified_chinese()` 掃描範圍 → 修復遺漏

Reference incidents: 2026-05-11 commits `f7790a2`, `aa24400`。

Reference incident: 2026-05-08 — commit `95b79ef`：新增 9 字（`诗`/`禅`/`图`/`猎`/`过`/`员`/`剧`/`别`/`于`）。

## Annotator name_ja Suffix Omission Guard

在調查**任何**「カテゴリバッジが表示されない」「カテゴリが DB に存在するのに画面に出ない」問題、または `name_ja` が期待と異なる場合に、**必須**確認：

1. **`name_ja` と `raw_title` の diff を確認する**：annotator は `raw_title` → `name_ja` 変換時に後置された分類語（「レポート」「告知」「詳細」「ご案内」等）を「タイトルの装飾」と判断して削除することがある。
2. **脱落が発覚した場合の修正パターン**：
   ```python
   # name_ja を raw_title 通りに復元 + FC ロック
   sb.table("events").update({"name_ja": raw_title}).eq("id", eid).execute()
   sb.table("field_corrections").upsert({
       "event_id": eid, "field_name": "name_ja",
       "corrected_value": json.dumps(raw_title, ensure_ascii=False)
   }, on_conflict="event_id,field_name").execute()
   ```
3. **「レポート」は削除対象になりやすい**：報告記事/観覧記 の suffix「レポート」は annotator が装飾語と誤認して削除する典型ケース。`category: ['report']` が付与されていてもタイトルから「レポート」が消えることがある。
4. **デバッグ優先順序**：① DB `category` 確認 → ② `messages/*.json` `i18n` 確認 → ③ `raw_title` vs `name_ja` diff 確認 → ④ UI レンダリングロジック確認。

Reference incident: 2026-05-07 — `f7ff56ca`「台湾文化センター映画...トークイベント レポート」の `name_ja` から「レポート」が annotator によって削除されており、`category: ['movie','lecture','report']` は正常だがタイトルバッジ調査で発覚。

---

## Manual Translation Fix Persistence Guard

在審核**任何**直接 SQL UPDATE 翻譯欄位（`name_zh` / `name_en` / `description_zh` / `description_en` / `performer`）的計畫前，**必須**確認：

1. **手動修正必同時鎖入 `field_corrections`**：否則下次 `annotation_status` 翻回 `pending` 時，annotator 主迴圈用 GPT 重寫，所有人工修正瞬間蒸發。這是「修了又錯、錯了又修」迴歸鏈的根因。
2. **正確 pattern**：
   ```python
   from annotator import _get_supabase, _lock_fields_via_corrections
   sb = _get_supabase()
   sb.table("events").update({"name_zh": "月老"}).eq("id", eid).execute()
   _lock_fields_via_corrections(sb, eid, {"name_zh": "月老"})
   ```
3. **enrich_* 函式自動鎖**：`enrich_movie_titles` 與 `enrich_person_names` 成功 patch 後**已自動 upsert** `field_corrections`（2026-05-05 起）。手動修正不可漏這一步。
4. **靜默 `continue` 是反 pattern**：lookup 失敗必須 `logger.warning`，否則 CI log 看不到，錯誤翻譯靜默上線數日。

Reference incident: 2026-05-05 — event `f970e4e3`（月老）多次被修又被 AI 覆寫；今日同步補入 `field_corrections` 鎖定四個翻譯欄位後免疫。

## Admin Form Component Prop Completeness Guard

在任何包含「新增 prop 到 shared form component」或「後台新增欄位」的計畫前，**必須**確認：

1. **Grep 所有 usage site**：新增 prop 後執行 `grep -r "AdminEventForm\|<ComponentName" web/components/ web/app/` 找出所有呼叫點，逐一確認新 prop 是否已傳入。TypeScript 若 prop 有 fallback default 不會報錯，**靜默失敗**難以發現。
2. **後台 form 必須暴露 DB 所有可人工修正的欄位**：新增 DB column 後，同步在 `AdminEventForm.tsx` 增加對應 input，否則管理員無法覆寫 AI 填錯的值。清單：
   - 翻譯欄位：`name_*`、`description_*`、`selection_reason`
   - 結構欄位：`organizer`、`organizer_url`、`event_form`、`co_organizers`、`sponsors`
   - 語言支援：`primary_language`、`has_japanese_support`、`has_english_support`、`has_chinese_support`
   - performer（三語 i18n）
3. **TRACKED_FIELDS 必須包含新欄位**：若欄位需觸發 `annotation_status → reviewed`，`AdminEditClient.tsx` 的 `TRACKED_FIELDS` 必須加入。陣列（`string[]`）與布林值欄位需特別確認比對邏輯（不能用 `===`，需深比對）。
4. **陣列欄位雙向轉換 pattern**：DB `string[]` 欄位在 form 用 comma-separated string 表示；save 時轉換：
   ```ts
   value.split(',').map(s => s.trim()).filter(Boolean)
   ```
   讀取時轉換：`(arr ?? []).join(', ')`

Reference incident: 2026-05-05 — `AdminEventForm` 新增 `tEventForm` prop 後，`AdminEventTable` 呼叫時忘記傳入，TypeScript 無錯誤（commit `30999ea` 補齊）；同次 commit 補齊 organizer、event_form 等 8 個後台隱藏欄位。

## Movie-Extend Invariant Guard

在審核任何修改 `database.py` `_build_movie_extend_row()`、新增 movie-extend 觸發分支、或擴張「對既存 row 部分更新」邏輯的計畫前，**必須**確認：

1. **白名單欄位不可擴張至 P3.2 受保護欄位**：`_build_movie_extend_row()` 允許更新的欄位限定為 `raw_description`、`business_hours`、`start_date`、`end_date`、`scraped_at`、`annotation_status`（僅在 `raw_description` 變動時 flip 為 `pending`）。**禁止**新增 `name_*` / `description_*` / `category` / `location_*` / `performer` / `organizer*` / `is_paid` / `price_*` / `event_*` 任何欄位。新增白名單欄位的 PR 必須拒絕。
2. **觸發條件必須三重 AND**：`'movie' ∈ category` + 既存於 DB（`existing_keys`）+ 不在 `blocked` / `reviewed` / `force_keys`。任何單一條件放寬會破壞「reviewed 事件不被自動更新」的保證。
3. **Partial 寫入必須用 `.update().eq().eq()` 而非 upsert**：既存 row 確認存在後不可用 `client.table("events").upsert(rows, on_conflict=...)` ——supabase-py 會嘗試 INSERT fallback，撞 NOT NULL 約束（如 `source_url`）。詳見 engineer history `2026-05-05 — Partial-payload upsert violates NOT NULL constraints`。
4. **對處流程互斥檢查**：計畫不可同時觸發 movie-extend 與 `force_rescrape=true`（後者全覆寫會吃掉 movie-extend 的 MIN(start_date) 保留語意）。如需 reviewed 電影更新場次，走 manual SQL + `field_corrections` 路徑，不可改 movie-extend 條件。
5. **新類型擴張需獨立分支**：演唱會巡演、巡迴展等「同 source_id 多檔期」需求，不可在 `_build_movie_extend_row()` 加 if-else，必須獨立 helper 並重新評估白名單欄位。

Reference incident: 2026-05-05 — commit `8572104` 引入 movie-extend；同 commit message 明示「by construction, extend rows touch zero P3.2-protected columns」與 `.update()` not upsert 的設計理由。

## Homepage Inline Card Divergence Guard

在審核任何修改「事件卡片視覺呈現」的計畫前（包含 location 顯示、徽章、日期格式、分類 chip、save 按鈕、報告按鈕等），**必須**確認：

1. **首頁 `web/app/[locale]/page.tsx` 使用 inline list-style 渲染，不使用 `EventCard.tsx`**：grep `EventCard` in `page.tsx` 會回傳 0 match。修改 `EventCard.tsx` 對首頁完全無效。
2. **其他頁面（saved、category 列表、search）使用 `EventCard.tsx`**：這些頁面共享元件。
3. **修改卡片 UI 的計畫必同時列出兩個檔案**：
   - `web/components/EventCard.tsx`（其他頁面）
   - `web/app/[locale]/page.tsx`（首頁 inline，行 ~290 附近的 `events.map(...)` 區塊）
4. **共用邏輯必抽至 `web/lib/`**：純函式（如 `getCityLabel`、`extractCity`、日期格式化）抽到 `web/lib/<name>.ts`，兩處 import；避免「修了一處忘了另一處」的迴歸。React component（如 chip 子元件）若值得共用可抽到 `web/components/`。
5. **驗證 pattern**（Vercel 部署後）：
   ```bash
   curl -s https://tokyotaiwanradar.com/zh | grep -c '<新元素 class 識別字>'
   # 期望非 0，若為 0 → 修了 EventCard 但首頁 inline 沒同步
   ```

Reference incident: 2026-05-05 — commit `5a29c13` 修 EventCard.tsx 城市徽章邏輯，但首頁完全無變化（首頁不用 EventCard）。commit `9f4b468` 抽 `web/lib/cityLabel.ts` 共用 helper 後雙處同步生效。

## Database Safety Rules

- **NEVER batch-set `is_active = False` based on `end_date < today`**. Past events must remain `is_active = True` so users can view event history. Visibility for ended events is controlled by the frontend `FilterBar` ("顯示已結束活動" toggle), not by `is_active`.
- **`is_active` has exactly two legitimate write sources**:
  1. Admin manually disables a specific event via the admin page.
  2. `merger.py` deactivates a duplicate secondary event during merge.
- Any bulk UPDATE touching `is_active` must be verified against these two sources before execution. If it does not match either, abort.

## Annotator Backfill QA Rule

任何計畫包含 `annotator.py --backfill-*` 步驟時，**必須**在步驟清單中明確列出「backfill 後多語言欄位 QA 驗證」子步驟：

- `selection_reason["ja"]`：必須含假名（平假名或片假名）；無假名表示語言污染
- 驗證 SQL：
  ```sql
  SELECT id, source_name, (selection_reason->>'ja') as ja_text
  FROM events
  WHERE selection_reason->>'ja' IS NOT NULL
    AND selection_reason->>'ja' !~ '[ぁ-んァ-ン]'
  LIMIT 20;
  ```
- 發現污染 → 執行翻譯修正腳本（從 zh 欄 GPT 翻譯覆寫）

**Incident**: 2026-05-04 `--backfill-tier1` 導致 49 筆 `selection_reason["ja"]` 為中文，需人工腳本修正。

## Scope

- State explicitly what is NOT in scope. Ambiguous scope = scope creep = breaking changes.
- List every affected file path explicitly — vague descriptions ("the scraper files") are not acceptable.

## Docs Update Rule

`/docs` 是**結構性文件**，只在架構改動時需要更新。以下情況屬於架構性改動，計畫中必須明確包含「更新 docs/ARCHITECTURE.md 或 docs/SCRAPER_PIPELINE.md」步驟：

| 改動類型 | 需更新 |
|---------|-------|
| 新增或移除整個 CI workflow | ARCHITECTURE.md |
| 新增或移除 pipeline layer（auto_scraper、researcher 等） | SCRAPER_PIPELINE.md |
| 新增或移除 Supabase 整合點（LINE bot、新 webhook） | ARCHITECTURE.md |
| 新增 `web/app/api/` 下的 API endpoint | ARCHITECTURE.md |

**不**屬於架構性改動（無需更新 docs）：bug fix、單一 scraper 新增、i18n 修改、CSS 調整、新增個別 Supabase migration。

`/docs` 記錄的是「系統怎麼運作」，不是「系統現在的狀態」。不要在文件中寫入會每天變動的數字（scraper 數量、事件總數、migration 編號）。

## Server Component + Realtime 分離模式 Guard

在任何包含「Server Component 中有 badge 或動態計數器」的 feature plan 中，**必須**明確標示：

> **⚠️ 此 badge / 計數器需要即時性嗎？若是，plan 必須包含「拆出 Client Component + Supabase Realtime 訂閱」步驟。**

**分離模式：**
```
ParentComponent (Server Component)
  └─ 查詢初始 count（SSR，一次性）
  └─ <DynamicBadge initialCount={n} />（Client Component）
       └─ Supabase Realtime 訂閱 INSERT + UPDATE 保持即時更新
```

**強制規則：**
- Server Component 的資料在 SSR 時固定，頁面渲染後不再更新。任何需要即時性的計數器 / badge，**不得**留在 Server Component 中。
- Client Component 接收 `initialCount` prop 作為 SSR 初始值，啟動後改由 Realtime 維護。
- 計畫中必須明確列出：哪個元件需要拆分、Realtime 訂閱哪個 table 的哪些事件（INSERT / UPDATE）。

**無操作 Quality Section 應直接移除：**
Quality check section 如果沒有對應的可執行 action（fix button / batch action），且數值永遠不清空（例如 archive cron 一天只跑一次的 expired-but-active），**計畫不應包含此 section**，已存在的應移除。只有數值能被操作清零的 check section 才值得顯示。

Reference incident: `AdminTabNav` badge（2026-05-02）—（commit `4a71258`）; expired-but-active section（commit `cd4cc29`）.

## Quality Check Design Rules

在任何包含「新增或修改 `/admin/quality` check 條件」的 feature plan 中，**必須**確認以下三點：

### 規則一：判斷欄位 = 詳情頁顯示欄位

> Quality check 用哪個欄位 IS NULL 做判斷，該欄位必須是詳情頁實際 render 的欄位。

- 設計 check 前先查前端程式碼（`app/[locale]/events/[id]/page.tsx`），確認「哪個欄位 null 才真正影響使用者體驗」。
- 錯誤範例：用 `location_address IS NULL` 做缺地點 check，但詳情頁顯示 `location_name`（commit `b82849d` → `80920ce`）。

### 規則二：排除「天生無法填寫」的事件類型

設計每個 quality check 時，同步列出「哪些事件類型天生不需要此欄位」，並在 DB query 層排除：

| Check 類型 | 已知排除 | 排除原因 |
|-----------|---------|---------|
| 缺地點（`location_name IS NULL`）| `source_name = 'gguide_tv'` | 電視節目 |
| 缺地點（`location_name IS NULL`）| `category` 含 `competition` | 競賽/補助，全國性活動 |

若未排除 → flag 永遠無法清零 → 無意義的噪音。

**排除語法（Supabase RPC）：**
```ts
.not('source_name', 'eq', 'gguide_tv')
.not('category', 'cs', '{"competition"}')
```

### 規則三：DB 層過濾優先於 client-side 過濾

所有 quality check 的排除條件**必須**推到 DB query（`.not()`），禁止在 JS 側 `.filter()` 排除。原因：DB 層過濾減少傳輸量，且排除邏輯集中在 query 中易於審查與維護。

Reference incident: 2026-05-02 quality page — `gguide_tv` 排除原為 JS client-side filter，後移至 DB query（commit `80920ce`）；`competition` 排除直接寫在 DB query（commit `4ca383a`）.

### 規則四：Client-Side Filter Prerequisites

撰寫任何依賴 DB 欄位的 client-side filter 前，必須確認以下三步驟：

1. **欄位出現在 `.select("...")` 字串中**：否則欄位值為 `undefined`，filter 條件永遠不成立，靜默通過所有資料（不報錯）。
2. **TypeScript interface 包含該欄位及正確型別**（如 `location_prefectures?: string[] | null`）。
3. 確認以上兩點後才撰寫 filter 邏輯。

**反例**（commit `bf22756` 之前）：
```ts
// ❌ location_prefectures 不在 select 字串 → 欄位 = undefined → 過濾靜默無效
if ((e.location_prefectures?.length ?? 0) > 1) return false;
```

**正確做法**：
```ts
// Step 1: 確認 select 含欄位
.select("id, location_name, location_prefectures, ...")
// Step 2: interface 宣告型別
interface QualityRow { location_prefectures?: string[] | null; ... }
// Step 3: 才寫 filter 邏輯
if ((e.location_prefectures?.length ?? 0) > 1) return false;
```

Reference incident: 2026-05-02 — `location_prefectures` 未加入 select，多城市活動過濾靜默失效。

## SSR Props Pass-Through Guard（Server 抓取資料必須傳入子 Component）

在審核任何 **Server Component（page.tsx）** 的 PR 前，若 page.tsx 抓取了資料並用 prop 傳給子 component，**必須**確認：

1. **page.tsx 抓取的每一份資料都有對應的 prop 傳入**：若 page.tsx 抓取 `worksList` 但 `<AdminEventTable>` 沒有 `initialWorks={worksList}`，資料完全浪費，子 component 會自己做一次 client-side 重複 fetch。
2. **用戶即時操作（下拉、選單、自動完成）的資料不能依賴 client-side fetch**：非同步 fetch 有 race condition——用戶在 fetch 完成前操作，看到空清單。
3. **正確模式**：
   ```tsx
   // page.tsx（Server Component）
   const { data: worksData } = await supabase.from("works").select(...);
   const works = (worksData ?? []) as Work[];
   return <AdminEventTable initialWorks={works} ... />;

   // AdminEventTable（Client Component）
   const [works, setWorks] = useState<Work[]>(initialWorks); // 立即可用
   useEffect(() => { /* refresh after creation */ }, []);     // 僅作刷新用
   ```
4. **確認清單**：在 page.tsx 搜尋所有 `const { data: ... } = await supabase.from(...)` 呼叫，對照子 component 的 Props interface 確認每份資料都有對應 prop。

Reference incident: 2026-05-16 — `page.tsx` 抓取 `worksList` 但未傳給 `AdminEventTable`，`works` state 初始化為 `[]`，用戶開下拉時 fetch 未完成 → 空清單（`work選項又不見了`）。

## QA Keyword Precision Guard（地名關鍵字子字串污染）

在審核任何修改 `TAIWAN_VENUE_KEYWORDS`（或類似地名比對清單）的 PR 前，**必須**確認：

1. **禁用縮寫裸字串**：`'新北'` ⊂ `'新北島'`（大阪市住之江区）；`'台中'` 可能出現在日本地名中。必須使用完整行政單位名：`'新北市'`、`'台中市'` 等。
2. **新增前 grep 日本地名**：對新關鍵字執行 `grep -r "<keyword>" scraper/` 確認無日本地名誤觸。
3. **Dedup 失效機制**：auto_qa dedup 僅在「事件 `updated_at` ≤ report `confirmed_at`」時跳過。每次 scraper upsert 更新 `updated_at`，即使 dismissed，下次 run 仍重新觸發——**假陽性關鍵字無法靠 dismiss 解決，必須修正關鍵字本身**。

Reference incident: 2026-05-05 — `'新北'` 匹配大阪市 `新北島`，event 371cf624 (GRAFFYHALL) 連續三次 auto_qa_taiwan_venue (commit 6b7174a)。

## auto_qa False Positive Guard

在審核任何 auto_qa 偵測器的改動或新增 `auto_qa_*` 類型前，**必須**確認：

1. **城市名誤報**：`location_name` 為純城市名（東京、大阪、岡山 等）時，新聞彙整類 source（`google_news_rss`、`koryu` 等）本就無法提供具體場地。`auto_qa_missing_address` 不應 flag 此類事件。維護 `VAGUE_CITY_NAMES` frozenset。
2. **海外場地誤報**：非日本場地（スイス、フランス 等）不在日本地址查核範圍內。維護 `OVERSEAS_KEYWORDS` tuple。
3. **正常 flag 保留**：有具體場地名（大學、美術館、○○ホール 等）但 `location_address = NULL` 的事件，仍應 flag。
4. **偵測精準度原則**：寧可少報，不可誤報——誤報會使管理員對回報系統失去信任。

Reference incident: 2026-05-04 — 13 筆 auto_qa_missing_address pending，其中 5 筆為城市名/海外場地誤報（commit `15c5b4b`）。

## RLS Cross-Status Query Guard

在任何涉及「SSR 頁面查詢關聯資料（父事件、鏈結實體）」的 feature plan 中，**必須**確認以下三點：

### 規則一：anon key 不讀非 active 資料

RLS `"Public read events"` policy 限制 anon key 只讀 `is_active = true` 的事件。若查詢目標（如父事件）被下架（`is_active = false`），anon key 查詢**靜默回傳 null**，不拋 error，難以察覺。

### 規則二：跨 active 狀態查詢必須用 service role key

若查詢的關聯資料可能處於 `is_active = false` 狀態（例如：父事件下架、存檔紀錄），**必須在 Server Component / route handler 中用 service role key**：

```ts
// Server Component only — 不可傳到 client-side
const adminClient = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)
const { data } = await adminClient
  .from("events")
  .select("id, name_ja, name_zh, name_en")  // 只查需要的欄位
  .eq("id", parentId)
  .single()
```

**強制限制**：service role key **絕對不得**暴露到 client-side。只在 Server Components 或 API route handlers 使用。

### 規則三：最小欄位原則

用 service role key 查詢關聯資料時，**只 select 當前頁面真正需要的欄位**（如 `id, name_ja, name_zh, name_en`），不得用 `select("*")` 避免洩漏敏感欄位。

Reference incident: 2026-05-02 — 父事件（台東祭）被設為 `is_active = false` 後，子事件詳情頁父事件連結消失；改用 service role key 後恢復（commit `f5931e0`）。

## Admin UI Dashboard Necessity Check

Before planning any new admin page or dashboard column whose primary output is a count / status / health number, ask:

1. **「這頁面真的會被點開嗎？」** — Admin UI requires manual navigation. If the signal isn't urgent enough to justify proactively visiting `/admin/...`, it will be ignored.
2. **「沒有 action 按鈕的純計數值得做嗎？」** — A dashboard column without a one-click fix / batch action / drill-down is visual decoration. If the user will read it and do nothing, the value is near zero.
3. **Is a passive push channel cheaper?** — LINE message, weekly email, or auto-filed GitHub issue cost less than a new page and have higher retention (signal arrives without being requested).

**Default preference order for monitoring features:**
1. Passive push (LINE / email / issue) → preferred for periodic health, budget, quality summaries.
2. Existing page extension with **actionable** column (e.g. add a row to AdminEventTable that has a fix button) → acceptable when tightly coupled to existing workflow.
3. New `/admin/<topic>` page → only when the user explicitly asks for an interactive审查 surface (multi-row triage, manual selection, bulk action).

If a plan introduces a new admin page or count column with no associated action, document the rationale explicitly in the plan; otherwise propose the passive push variant first.

Reference incident: 2026-05-01 Tier 1 monitoring — `/admin/quality` page and `/admin/stats` SLA columns were planned, implemented, then撤銷 same week; only the LINE budget push (`weekly_report.py`) survived.

## Annotator Scraper-Priority Guard

Before approving any change to `annotator.py` annotation field priority, verify:

1. **Scraper values always take precedence** over GPT inference for factual fields:
   - `start_date` / `end_date`
   - `location_name` / `location_address`
   - `business_hours`
   - `is_paid`
2. **GPT only fills in** when the scraper left the field empty (`None`/`null`).
3. **Translation fields are always GPT-generated** — `name_zh`, `name_en`, `description_*`, `location_name_zh/en`, `business_hours_zh/en`.
4. **`name_ja` special case**: when `name_ja_locked=true`, the scraper's value is preserved verbatim. The source title may be in Japanese, Chinese, or English — `name_ja` is a field identifier, not a language constraint.
5. **`location_url`** — conditional write: GPT may extract it from `raw_description` text (schema prompt must say "extract from text only, no hallucination"). Write only when non-null (`_loc_url = event.get("location_url") or _str(annotation.get("location_url"))`); never write `null` back to DB — `null` would overwrite admin-entered values. This is a field shared between scraper/GPT extraction and admin manual entry. (commit `fb568c4`, 2026-05-02)
6. The safe way to fix a GPT-overwritten date: prepend `開催日時: YYYY年MM月DD日` header to `raw_description`, then set `annotation_status='pending'` to trigger re-annotation.

## Scraper Date Timezone Guard（爬蟲日期時區守護）

在審核任何 scraper 的 `start_date`/`end_date` 傳入邏輯前，**必須**確認：

1. **禁止傳 JST-aware datetime**：`datetime(..., tzinfo=timezone(timedelta(hours=9)))` 傳入 Supabase 後以 UTC 儲存，JST+9 偏移導致日期倒退一天（`2026-05-08T00:00:00+09:00` → `2026-05-07T15:00:00+00:00`）。
2. **正確模式 — UTC midnight**：
   ```python
   # CORRECT — 保留日曆日期，強制 UTC tzinfo
   start_date = jst_dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
   # WRONG — JST-aware datetime 傳入 Supabase
   start_date = jst_dt  # tzinfo=JST, Supabase 轉成前一天 UTC
   ```
3. **naive datetime 也有風險**：`datetime` 無 tzinfo 時 Supabase 依伺服器時區解讀（通常 UTC），一般安全，但不如明確設定 UTC midnight。
4. **驗證**：新 scraper dry-run 後，確認 DB 的 `start_date` 與來源頁面的日期完全一致。

Reference incident: 2026-05-07 — Stranger scraper `f3554212` start_date 存為 `2026-05-07T15:00:00+00:00`（應為 2026-05-08），Vercel 顯示前一天（commit `b7dc34f`）。

## Hallucination Scan Safety Guard

Before acting on any hallucination scan result (address/location not found in raw_description), verify:

1. **Scan result = suspicion only**: An address absent from raw_description does NOT confirm hallucination. GPT correctly recalls well-known venues from training data.
2. **Always verify with Google Maps before editing**: Search the venue name directly — takes 30 seconds. Do NOT infer address from venue name, neighborhood, or landmark associations.
3. **Venue name ≠ postal address**: `MoN Takanawa` (inside Takanawa Gateway City) has postal address 港区三田 — not 高輪. Station names, building brands, and postal addresses can differ.
4. **Incident**: 2026-05-02 — architect changed correct GPT address `港区三田3-16-1` to wrong `港区高輪4-10-30` based on venue name reasoning. Reverted after user confirmation.

## Universal Year-Anchor Guard（年份錨點注入 — 全來源）

在審核任何涉及 annotator 日期提取邏輯、或分析任何來源事件年份錯誤時，**必須**確認：

1. **年份錨點注入必須覆蓋所有來源（非僅 gnews 類）**：
   - 觸發條件：`scraped_at AND "記事配信日:" not in raw_desc`（不限 source_name）
   - 注入格式：`（記事配信日: YYYY-MM-DD）\n\n` 前綴
   - **必須在 gnews article fetch 之後注入**：article fetch 會替換 raw_desc，丟失已有的年份錨點

2. **兩類年份幻覺場景均被覆蓋**：
   - (a) raw_desc **完全無 4 位年份**（e.g. `5月8日（金）公開`）→ GPT 從訓練資料猜年，可能猜出過去年份
   - (b) raw_desc **含誤導性年份**（e.g. `2025年11月に公開を迎えた台湾国内での興行収入`，指另一國的上映年）→ GPT 誤用該年份為日本活動年份

3. **SYSTEM_PROMPT DATE Rule 7 必須引用 記事配信日**：
   - 規則文字含 `（記事配信日: YYYY-MM-DD）` → `use that year as the reference year`

4. **field_corrections 鎖定已修正的年份**：
   - 若曾因幻覺設定錯誤年份，修正後必須同時鎖入 `field_corrections`（start_date, end_date），否則 re-annotation 重新覆寫

5. **失效症狀**：事件 start_date 年份比 scraped_at 年份差超過 1 年（可能是過去也可能是未來）

**驗證命令**：
```bash
grep -n "記事配信日\|scraped_at year anchor" scraper/annotator.py | head -10
# 確認不含 "_gnews_sources_needing_year" 的限制條件
```

Reference incidents:
- 2026-05-06 — `0d33b617` (gnews 熊本チップ・オデッセイ) scraped_at=2026-04-28 → annotated start_date=2024-04-01（應為 2026-04-12）
- 2026-05-07 — `dded67a6` (uplink_cinema 霧のごとく大濛) raw_desc 含「2025年11月に公開を迎えた台湾国内での」（台灣內地年份），GPT 幻覺 start_date=2025-05-08（應為 2026-05-08）

## enrich_movie_titles Sub-Event Hallucination Guard

在審核任何涉及 `enrich_movie_titles()` 修改、或分析 gnews sub-event 電影標題錯誤的計畫前，**必須**確認：

1. **gnews sub-event 的 `name_ja` 不可作為 eiga.com lookup 的標題來源**：
   - 若 `source` 在 `_NEWS_MOVIE_SOURCES` 且 bracket 命中來自 `name_ja`（非 `raw_title`），且事件有 `parent_event_id` → 必須 `continue`（跳過）並記錄 `logger.warning`。
   - Sub-event 的 `name_ja` 是 GPT 從極薄語境（單句描述 + 文章全文）生成，極易幻覺電影名稱。
   - 只信任 `raw_title`（scraper 直接捕獲）中的括號標題。

2. **`enrich_movie_titles` select 查詢必須含 `parent_event_id`**：
   - Guard 邏輯需要讀取 `parent_event_id`，若 select 字串缺少此欄位，`event.get("parent_event_id")` 永遠 `None`，guard 靜默失效。

3. **SYSTEM_PROMPT `SUB-EVENT name_ja` 規則的 CRITICAL 補丁**：
   - 規則已加入：若 sub-event 標題是描述性位置短語（e.g., "早稲田大学での上映会"）且電影名稱未直接出現在該 sub-event 描述旁，禁止從文章其他段落推斷電影名稱。
   - 核查點：SYSTEM_PROMPT 中的 `SUB-EVENT name_ja` 段落須包含 `CRITICAL — DO NOT INFER MOVIE TITLES` 文字。

4. **根因機制（供調試參考）**：
   - GPT 標注父事件時，同時識別多個 sub-events
   - 含多部電影的文章中，GPT 可能把 A 電影的場館名稱配對到 B 電影的放映日期
   - 場館描述性 sub-event（如 "早稲田大学での上映会"）因無明確電影名稱，GPT 從文章語境推斷並幻覺

**驗證命令**（執行後確認 `_title_from_raw` 旗標存在）：
```bash
grep -n "_title_from_raw\|skipping enrich for news sub-event" scraper/annotator.py
```

Reference incident: 2026-05-05 — `d18339d5` (`gnews_f9a2e51bc89a_sub3`) raw_desc 只有 1 句話，GPT 幻覺 `name_ja = "赤い糸 輪廻のひみつ"`（月老），應為チップ・オデッセイ（造山者）場次。無 bracket → `enrich_movie_titles` 未鎖定，但 GPT 直接寫入 DB（annotation_status=annotated）且人工修正前無法自動偵測。

## Cinema Series Sub-Event Sub_Events Guard

在審核任何涉及 ks_cinema（或其他系列頁電影場館來源）的 annotator 計畫，或分析同一電影出現多筆事件的問題前，**必須**確認：

1. **Annotator sub_events 規則有電影時段豁免**：SYSTEM_PROMPT Rule 1 必須有明確 EXCEPTION 說明「電影類別的單一放映若只有多個時段（如 `4/25～5/1 10:00、5/2～8 14:40`），不建立 sub_events；改用 start_date=首日、end_date=尾日，時段細節放 business_hours」。
2. **程式碼守衛存在**：annotator.py 中 `_cinema_sources = {"ks_cinema"}`，若 `source_name in _cinema_sources AND source_id ends in _{digit} AND parent_event_id=None` → `sub_events = []`（防止首次 race condition）。
3. **Race condition 已知**：ks_cinema 系列頁 sub-events（`_0`, `_1`, `_2`）在 scraper 首次執行時 `_get_parent_uuid` 查不到 parent（尚未 commit）→ `parent_event_id=None`。這是已知的架構限制；現有守衛已防止 annotator 誤生成 `_sub1`。
4. **`_sub1` 不會被 merger 消除**：同 source 的事件（ks_cinema → ks_cinema）被 Pass 1 `source_name == source_name` 跳過。若 DB 已有殘留 `_sub1`，需人工 `deactivated_by_pass=admin_manual`。

**Quick Check（出現重複電影事件時）**：
```python
# Check if _sub1 events exist for the film
r = sb.table("events").select("id,source_id,is_active,parent_event_id").ilike("source_id", "%_sub1%").eq("source_name","ks_cinema").execute()
# Deactivate if found
sb.table("events").update({"is_active": False, "deactivated_by_pass": "admin_manual"}).in_("source_id", [e["source_id"] for e in r.data if e["is_active"]]).execute()
```

Reference incident: 2026-05-06 — `車頂上的玄天上帝`（ks_cinema `taiwan-filmake_2_sub1`）因 SYSTEM_PROMPT 多時段規則 + race condition 生成 `_sub1`，出現 4 筆重複（其中 2 筆已被 merger 停用）。修復：停用 `_sub1`、SYSTEM_PROMPT 加豁免規則、annotator.py 加程式碼守衛。

## Organizer Non-Hallucination Guard（annotator.py few-shot 污染防護）

在審核任何涉及 `organizer` 欄位，或評估 `category_corrections` few-shot 範例設計的計畫前，**必須**確認：

1. **GPT 返回的 organizer 必須出現在原始文本中**：`_gpt_org_raw` 在寫入 `update_data` 前，需確認 `_gpt_org_raw in (raw_title + " " + raw_description)`。不存在則丟棄（`_guarded_organizer = None`）並發出 WARNING log。
2. **few-shot 例子中的具名機構有污染風險**：`category_corrections` 的補正例若含具體主辦方名稱，GPT 可能對缺主辦人的其他活動 hallucinate 相同名稱。這是 named entity 的跨事件遷移效應。
3. **contamination 路徑**：`category_corrections` few-shot → SYSTEM_PROMPT 注入 → GPT hallucinate organizer → P0 保護鏈保存錯值 → 子事件繼承 → 雪球效應。
4. **organizer 必須走 `_ai_or_existing()`**：確保 P1（field_corrections）保護也覆蓋 organizer 欄位。

**驗證指令（改動 annotator.py organizer 邏輯後執行）**：
```python
# 確認 guard 存在
import ast, pathlib
src = pathlib.Path("scraper/annotator.py").read_text()
assert "_gpt_org_raw" in src and "_source_text" in src and "Organizer hallucination detected" in src
print("Guard: OK")

# DB 掃描：找到 organizer 但 raw_text 不含 organizer 名稱的事件
# (需在 DB 層做，此為人工 SQL)
# SELECT id, name_ja, organizer, LEFT(raw_description, 200)
# FROM events
# WHERE organizer IS NOT NULL
#   AND annotation_status = 'annotated'
#   AND raw_description NOT ILIKE '%' || organizer || '%'
#   AND raw_title NOT ILIKE '%' || organizer || '%'
# LIMIT 20;
```

Reference incident: 2026-05-06 — `category_corrections` 含 2 筆 `セシリアママのHappy Table...` few-shot 範例，導致 31 件 Peatix 活動被 hallucinate `organizer = "セシリアママ"`（commit `fix(annotator): add organizer non-hallucination guard`）。

---

## Joint Distributor Split Guard（聯合配給商拆分守護）

在審核任何設定「配給」→ `organizer` 的案例，或分析 organizer 字串含「／」的事件前，**必須**確認：

1. **「配給：A／B」中「／」代表聯合配給**：A 和 B 是兩家獨立公司，不可整串存為 organizer（例如 `"JAIHO/Stranger"` 是錯誤的）。
2. **正確拆分方式**：排名先者（左邊）→ `organizer`，其餘 → `co_organizers[]`。
3. **工具驗證**：
   ```python
   if "/" in (organizer or "") or "／" in (organizer or ""):
       # 需要拆分，不可整串儲存
       parts = re.split(r"[/／]", organizer)
       organizer = parts[0].strip()
       co_organizers = [p.strip() for p in parts[1:]]
   ```
4. 同樣需鎖 `field_corrections`：`organizer`、`co_organizers`、`organizer_type` 手動修正後必須同時 upsert。

Reference incident: 2026-05-07 — `dec5031b` `organizer = "JAIHO/Stranger"` 應為 `organizer = "JAIHO"`, `co_organizers = ["Stranger"]`, `organizer_type = ["commercial_brand"]`。

---

## Work Title ≠ Event Name Guard（作品標題不等於活動名稱守護）

在審核任何涉及 `work_id` 的事件的 `name_zh`/`name_en` 前，**必須**確認：

1. **`name_zh`/`name_en` 必須是 `name_ja`（完整活動標題）的翻譯**；不可從 `works.title_zh`/`works.title_en` 繼承。電影名、作品名只是活動的一部分，不等於活動標題。
2. **症狀識別**：若 `len(name_zh) << len(name_ja)`（如 `name_zh = "中村地平"`（4字）而 `name_ja = "第78回 日本と台湾を考える集い 紀錄片《中村地平》上映会"`（30+字）），屬高可信度異常。
3. **驗證命令**：
   ```python
   # 查所有有 work_id 且 name_zh 長度 < name_ja 長度 50% 的事件
   suspect = [e for e in events if e.get("work_id") and e.get("name_zh") and e.get("name_ja")
              and len(e["name_zh"]) < len(e["name_ja"]) * 0.5]
   ```
4. 修正後必須同時鎖 `field_corrections`：`name_zh`、`name_en` 均需 upsert，防止 re-annotation 覆寫。

Reference incident: 2026-05-07 — `622f51c1` `name_zh = "中村地平"`（4字）vs `name_ja`（32字）；根因為 annotator 把 `works.title_zh` 直接用作 `name_zh`，未翻譯完整活動標題。

---

## Blog/Creator Source Thin Content Guard

在審核任何涉及 `note_creators`、`note.com` 等部落格/創作者聚合來源的計畫前，**必須**確認：

1. **`raw_description` 通常只有「続きをみる」截斷文字**：organizer 在此情況下必然為 null，絕不可從 note 發文者的個人簡介或背景推斷主辦方。
2. **純介紹文章/觀影報導不是活動資料**：標題含「おすすめ」「紹介」「行ってきた」「読んでみた」等字樣的文章，應設 `is_active=false`（非活動事件）。
3. **`_HEADLINE_REWRITE_SOURCES` 必須包含部落格來源**：`note_creators` 的 `raw_title` 是文章標題，不是活動名稱，必須加入 `_HEADLINE_REWRITE_SOURCES` 讓 GPT 從 raw_description 重新生成正確的 `name_ja`。
4. **Short-text organizer guard 的侷限性**：Non-Hallucination Guard 確認 organizer 字串存在於 `raw_title + raw_description`，但文本極短（< 100 字）時 GPT 仍可能從外部知識推斷，guard 無法完全阻止。對此類事件，organizer 應保持 null。

**快速識別模式（需要 is_active=false 的文章）**：
```python
NON_EVENT_TITLE_RE = re.compile(
    r"(おすすめ|紹介|まとめ|行ってきた|読んでみた|観てきた|鑑賞レポ|映画紹介)",
    re.IGNORECASE
)
# raw_title 命中 → 標為非活動文章
```

**驗證指令（note_creators 事件 organizer 掃描）**：
```sql
SELECT id, name_ja, organizer, LEFT(raw_description, 100)
FROM events
WHERE source_name = 'note_creators'
  AND organizer IS NOT NULL
  AND is_active = true
LIMIT 20;
-- 所有 note_creators 事件的 organizer 應為 NULL
```

Reference incident: 2026-05-08 — `2cae572a`/`10a4ee5d` organizer 被推斷為 `埼玉県日台親善協会`（note 發文者）；`4180ad0f`/`4ebc8a35` 介紹文章/觀影報導入庫（commit `b589fbb`）。

---

## Collection Attribution Guard（所蔵元 ≠ 活動場地）

在審核任何涉及 `location_name` 抽取邏輯的計畫，或分析展覽類事件 venue 識別錯誤的問題前，**必須**確認：

1. **`〇〇美術館蔵`/`〇〇博物館蔵` 是作品所蔵機關標記，不是活動場地**：GPT 容易將「高雄市立美術館蔵」中的「高雄市立美術館」提取為 `location_name`，這是錯誤的。
2. **yebizo（東京都写真美術館）的 `location_name` 應固定為「東京都写真美術館」**：無論展品的所蔵機構來自哪個國家或城市，活動場地永遠是東京都写真美術館本身。
3. **SYSTEM_PROMPT 已有 COLLECTION ATTRIBUTION NOTE**：此規則已注入 GPT 指示，但程式碼層面的 scraper 也應確認 `location_name` 有靜態預設值（如 yebizo scraper 應直接設定 `location_name="東京都写真美術館"`）。
4. **識別模式**：`raw_description` 中出現「蔵」字緊接機構名，如 `〇〇美術館蔵`/`〇〇博物館蔵`/`〇〇文化基金蔵`，這些是所蔵標記，不是場地。

**驗證指令（展覽來源 location 掃描）**：
```sql
-- 確認 yebizo 事件 location 是否正確
SELECT id, name_ja, location_name, location_address
FROM events
WHERE source_name = 'yebizo'
  AND location_name != '東京都写真美術館'
  AND is_active = true
LIMIT 10;
-- 應為空結果
```

Reference incident: 2026-05-08 — `e37db12e`（yebizo）`location_name='高雄市立美術館'`（作品所蔵元），修正為「東京都写真美術館」（commit `47f8184`）。

---

## Performer Null Guard（annotator.py 三層 fallback 守則）

在審核任何涉及 `performer` 欄位的計畫，或分析 `performer = NULL` 案例時，**必須**確認 annotator.py 是否正確執行三層 fallback：

### 三層優先順序
1. **DB 既有值**（`event.get("performer")`）— 已有值時不覆蓋（含 `field_corrections` 保護）
2. **GPT 提取**（`annotation.get("performer")`）— SYSTEM_PROMPT 有 PERFORMER EXTRACTION RULES
3. **Regex 確定性提取**（`_extract_performer_from_raw(raw_title, raw_description)`）— GPT 失敗時的最後防線

### 確定性提取覆蓋的關鍵 pattern
| Pattern | 範例 | Regex |
|---------|------|-------|
| `<role>・<name>氏を迎え` | `料理研究家・宮武衣充氏を迎え` | `_PERFORMER_INTRO_RE` |
| `<name>氏を迎え` / `<name>さんを迎え` | `田中花子氏を迎え` | `_MUKAE_RE` |
| `<name>　｜<role>` | `前田知里｜植物民族学研究家` | `_PIPE_ROLE_RE` |
| `<role>: <name>` | `講師：田中花子` / `ゲスト：田中花子` | `_PERFORMER_INTRO_RE` |

**`_PIPE_ROLE_RE` 使用注意**：`<name>　｜<role>` 格式常見於 Peatix の「主催者 = 主講人」型活動（例：`里山文庫　前田知里　｜植物民族学研究家`）。Role suffix 限定 `家/者/師/士/督` 以防假陽性。

**搜索範圍**：`raw_description` 前 **1500 字元**（原為 500，2026-05-06 擴展）。事件 `4427f965` 的講師資訊在 pos 859，500 字元範圍不夠。

### 防範靜默 null 的 QA 規則
- **Backfill 後執行 null 掃描**：任何 `--backfill-performer` 後，執行：
  ```sql
  SELECT id, raw_title, performer FROM events
  WHERE annotation_status='annotated'
    AND performer IS NULL
    AND (raw_title ILIKE '%氏を迎え%' OR raw_title ILIKE '%さんを迎え%'
         OR raw_title ILIKE '%(講師|ゲスト|スピーカー)%');
  LIMIT 20;
  ```
- **結果非空 → 直接 DB 修正 + `field_corrections` 保護**（正確方式；`--id` 重標注費時且 GPT 可能再次失敗）。
- **SYSTEM_PROMPT performer 規則**：JSON schema 必須含 `"performer"` 欄位；PERFORMER EXTRACTION RULES 段落必須在 ORGANIZER 段落**前面**。

### 已知 GPT 容易漏抓的模式
- **複合職稱 + 氏**：`料理研究家・宮武衣充氏` — GPT 容易把整個字串當職稱描述，忘記提取人名
- **標題中的氏を迎え**：GPT 通常從 description 找 performer，不從 raw_title 找

### Regex 設計原則（防假陽性）
- **名字字元類必須保守**：用 `[\u4e00-\u9fff]{2,5}` 純漢字（上限 5），而非排除清單 `[^\u3000\u30fb...]`
  - 錯誤：`{2,6}` → `翻訳者一青窈`（6 字）被誤識別為名字（role+name 連串）
  - 正確：`{2,5}` → `宇田川幸洋`（5 字）仍可匹配，`翻訳者一青窈` 不匹配
- **`_MUKAE_RE` 必須有 negative lookbehind `(?<![\u4e00-\u9fff])`**：防止從職稱字串中間開始匹配。例：`訳者一青窈` 從 `訳` 開始匹配出 `訳者一青窈`（`訳` 前面是漢字 `翻`，lookbehind 阻擋）。
- **每次修改後掃描 DB**：對全部 performer=null 事件跑 `_extract_performer_from_raw`，人工確認所有命中
- **敬語形式需覆蓋**：`をお迎え`（帶 `お`）與 `を迎え` 是不同 pattern，需同時收錄
- **DB 回填只用 INTRO pattern**：MUKAE 只感知「名字+敬語」，不知道上下文有幾位講者。多人講者事件（林宏文、宇田川幸洋案例）由 MUKAE 匹配但應保持 null。

Reference incidents:
- 2026-05-04 — event `e72b2c15` performer 三層 fallback 缺失；初版 regex 3 件假陽性（commits `562a620`, `1ef6953`, `b2a8806`）。
- 2026-05-06 — event `4427f965`（台湾植物紀行）`前田知里｜植物民族学研究家` 未提取，三重根因：(1) 無 `_PIPE_ROLE_RE`；(2) 資訊在 pos 859 > 500 上限；(3) GPT 視主催者不為 guest（commit `c82e746`）。
- 2026-05-08 — `翻訳者一青窈` 假陽性：INTRO `{2,6}` + MUKAE 無 lookbehind 導致 role+name 連串被誤匹配；修法：max 6→5 + lookbehind + `翻訳者` 加入 role list（本 commit）。

## Manual Merge Completeness Guard（手動合併必須同時更新所有關聯欄位）

在審核任何手動合併（merger / admin）操作的計畫前，**必須**確認以下三件事全部完成：

1. **合併後次要事件 `is_active` 必須為 `False`**：合併後設定 `merged_into_event_id` 但忘記設 `is_active=False` 是最常見的遺漏步驟。合併後驗證指令：
   ```sql
   SELECT id, is_active, merged_into_event_id
   FROM events
   WHERE merged_into_event_id IS NOT NULL
     AND is_active = true;
   -- 應為空結果；非空 = 資料不一致
   ```
2. **Works 表必須與 event 合併同步更新**：合併前補充 works 表的 `director`、`release_year`、`cast_summary`、`description`；合併後確認 `work_id` 正確連結。只做 event 合併但不更新 works 表，則 works 詳情頁缺少作品資訊。
3. **Events 表的 `director`/`performer` 欄位也需補充**：不能只更新 works 表，events 自身的 `director`/`performer` 欄位也需同步設定（用於清單頁/卡片顯示）。

**`is_active=True + merged_into_event_id IS NOT NULL` 為已知資料不一致模式**：Admin UI 的「⚠ 中繼節點」badge 是偵測工具，但根本防護是每次合併後立即執行上述驗證 SQL。

Reference incident: 2026-05-06 — `b891cc5e` 合併後 `is_active` 未更新為 `False`；`ソウル・オブ・ソイル` 合併後 works 表同時補充 `director=顏蘭權`、`release_year=2024`、`cast_summary`。

## AdminEventTable Cross-filter Reference Guard（globalIndexMap vs displayEvents）

在審核任何 AdminEventTable 或類似 admin 表格中「一行引用另一行 ID」的 UI 計畫前（merged_into、parent_event_id 等），**必須**確認：

1. **行號 map 必須從完整 `events` props 建立，不能從篩選後的 `displayEvents` 建立**：若 map 建立自 displayEvents，被篩選掉的事件 `id` 在 map 中為 `undefined`，行號顯示靜默消失（不報錯）。
2. **Pattern — 雙 map 架構**：
   ```ts
   // globalIndexMap — 從完整 events prop 建立，不受 filter 影響
   const globalIndexMap = useMemo(() =>
     new Map(events.map((e, i) => [e.id, i + 1])),
     [events]
   );
   // rowIndexMap — 從 displayEvents 建立，用於顯示當前篩選下的行號
   const rowIndexMap = useMemo(() =>
     new Map(displayEvents.map((e, i) => [e.id, i + 1])),
     [displayEvents]
   );
   // merged_into 目標可能被篩選掉 → 優先用 globalIndexMap
   const targetIdx = globalIndexMap.get(e.merged_into_event_id) ?? "?";
   ```
3. **TypeScript 不報錯**：`Map.get()` 回傳 `T | undefined`；`undefined` 靜默渲染為空字串。這是靜默 UI 錯誤，只能靠人工觀察或 QA 發現。

Reference incident: 2026-05-06 — AdminEventTable `rowIndexMap` 從 `displayEvents` 建立，`merged_into` 目標被篩選時行號消失（commits cb1bf83, 979725f）。

## Admin Table Column Width Guard

在審核任何 admin 表格欄寬設定，或修改 `AdminEventTable.tsx` Tailwind 寬度 class 的計畫前，**必須**確認：

1. **固定欄寬必須同時設 `w-[Npx]` + `min-w-[Npx]`**：只設 `max-w-[Npx]` 時，表格被其他欄擠壓後該欄仍會縮小（`max-w` 只設上限，無法防壓縮）。
   ```tsx
   // ✅ 固定寬度
   <td className="w-[160px] min-w-[160px] ...">
   // ❌ 可被壓縮
   <td className="max-w-[160px] ...">
   ```
2. **Works 清單排序用 `title_ja`，不用 `original_title`**：`original_title` 是原始語言片名（可能是中/英文），PostgreSQL `ORDER BY ASC` 將 null 值排末，導致大量 `title_ja` 有值的日文片名因 `original_title=null` 而沉底。後台以 `title_ja` 排序符合日文使用習慣。
   ```ts
   .order("title_ja", { nullsFirst: false })
   ```
3. **新增 modal 觸發點時，所有「新增」入口點必須同步改為 modal**：bulk action bar 的按鈕改為 modal 時，dropdown 底部的次要連結（`<a href="…" target="_blank">`）也必須同步改為 `<button>` 觸發 modal；不可混用跳頁和 modal。

Reference incident: 2026-05-06 — `category` 欄從 `w-96` → `max-w-[160px]` → `w-[160px] min-w-[160px]`；works 清單從 `.order("original_title")` 改為 `.order("title_ja", { nullsFirst: false })`；dropdown「新增 work」從 `<a>` 改為 `<button>`。

## After Identifying a Planning Mistake
1. Append an entry to `.github/skills/agents/architect/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Stop-Point Contract (Architect 直接編輯時)

Architect 預設為 read-only（規劃 + 報告）。但在以下情況會直接編輯檔案：revert 操作、緊急修正、小幅文檔更新。**直接編輯後必須走完以下其一**，禁止留半成品：

1. **完整鏈路**：編輯 → 自呼叫 V-M-D（commit + push + Vercel 驗證）→ 報告結果。
2. **明示交還**：編輯 → 在最終回應**第一行**標注「⚠️ 工作樹有未提交修改，需手動處理」並列出檔案，**禁止只報「已完成」**。

絕不允許：編輯完直接呈現 commit hash 或「完成」字樣而沒明確指出 push 狀態。

## Status Reporting Vocabulary

呈現 git 狀態時，**必須**用以下三種標籤之一，禁止只給 hash：

- ✅ **已推送**：`<hash> → origin/main`（已驗證 Vercel 部署或 push 成功 exit code 0）
- ⏳ **本地 only**：`<hash> (local, not pushed)`
- 📝 **未 commit**：`N files modified (working tree)` 並列檔名

裸 hash（如「commit cf1e0a9」）會讓用戶誤以為已推送，這是 anti-pattern。

## Atomic Revert Rule

刪除 i18n key、type union member、或任何被多處引用的 symbol 時，**同一 commit 必須同時刪所有 caller**：

1. 編輯前先 `grep_search` 找出所有引用點。
2. 改動順序：先刪 caller，再刪 definition（反之會留下編譯壞掉的中間狀態）。
3. 完成後跑 `cd web && npx tsc --noEmit` 確認 0 error 才 commit。

反例：2026-05-01 撤銷 Tier 1 時刪掉 `statsSlaHeader` 等 i18n keys，但 stats/page.tsx 仍呼叫 `t("statsSlaHeader")`，導致工作樹半成品狀態（用戶察覺後手動修復）。

## AEO Feature Planning Rules

When planning any AEO (AI Engine Optimization) or SEO feature:

- **Static file checklist**: Any `web/public/` file added (e.g. `llms.txt`, IndexNow key `.txt`, Google verification `.html`) must have a corresponding `proxy.ts` matcher exclusion step in the plan. Without it, next-intl i18n middleware 307-redirects the file to a locale path (e.g. `/zh/google...html`), making it unreachable by external services. Use `google[0-9a-f]+\.html` to cover all Google verification file formats.
- **FAQPage plan must include visible `<dl>`**: Never plan "add FAQPage JSON-LD" without also planning "add matching visible `<dl>` section on the page". Google requires FAQ content to be visually present.
- **Migration number pre-check**: Before assigning a migration number, confirm the next available number with `ls supabase/migrations/ | sort | tail -5`. Two migrations with the same number must use `NNN` and `NNNb_` suffix.
- **i18n namespaces upfront**: When planning new page types (city pages, category pages), explicitly list all new i18n namespace keys needed in all three messages files as a plan step. Silent namespace miss = raw key on page.
- **IndexNow env vars**: Plans that add IndexNow submission must explicitly list `INDEXNOW_KEY` and `NEXT_PUBLIC_SITE_URL` as required env vars in both GitHub Actions secrets and (if needed) Vercel.
- **GSC integration must use OAuth2 refresh token**: Google Search Console UI **only accepts regular Google accounts** as users — service account emails return "找不到電子郵件" and cannot be added. Always design GSC API integration with OAuth2 refresh token (`GSC_CLIENT_ID` + `GSC_CLIENT_SECRET` + `GSC_REFRESH_TOKEN`), never service account JWT.
- **OAuth Playground requires test user setup**: When the OAuth consent screen is in "Testing" mode, the authorizing account must be added as a test user first, otherwise the flow returns 403 `access_denied`. Plans that include OAuth token generation steps must note this prerequisite.

## OG Image Multi-Language Truncation Rules

When planning or reviewing changes to `web/app/[locale]/events/[id]/opengraph-image.tsx`:

- **截斷閾值必須以英文長度為基準**：日/中文每字元視覺寬，36 字足以填滿標題區域；英文每字元視覺窄，需 50+ 字元才填滿同等空間。截斷 `N` 值應設 ≥ 55（英文基準），而非 36（日文基準）。
- **優先增加字體縮小級別，而非降低截斷閾值**：新增中間字體層（如 40px）讓長英文標題縮小後多行顯示，保留完整語意；只有視覺上確實溢出時才截斷。
- **目前三級字體設計**（截至 2026-05-01）：
  - ≤ 22 字 → 72px
  - 23–36 字 → 54px
  - 37–55 字 → 40px
  - > 55 字 → 40px + 截斷至 53 字
- 任何修改此邏輯的 plan 必須包含「用英文長標題（如 40+ 字母）和日文短標題（≤ 10 字）各一組」的視覺驗收步驟。

## Category Union Change Guard

After any plan that touches `web/lib/types.ts` Category union:
- `multi_replace_string_in_file` `oldString` for union type changes must include **≥3 lines** before and after the target member — insufficient context silently truncates adjacent union members (see: `retail` removed when `drama` added, commit `f9e6b52`)
- Plan must include an explicit post-change verify step: `cd web && npx tsc --noEmit`, confirming **all** prior union members still compile

## Admin Form New Field Checklist

When adding a new optional field to the `events` table that also appears in the Admin UI, all 7 points must be in the same plan:

1. **Migration** (manual step): `ALTER TABLE events ADD COLUMN IF NOT EXISTS <field> <type>;` — must be executed in Supabase Dashboard SQL Editor **before** any Python client seed or upsert referencing the new field. (Error if skipped: `PGRST204: Could not find the '<field>' column`)
2. **`scraper/sources/base.py`**: Add to `Event` dataclass as `Optional[str] = None`.
3. **`web/lib/types.ts`**: Add to `Event` interface as `field: type | null`.
4. **`AdminEventForm.tsx`** — two sub-steps:
   - `EMPTY_FORM`: add `field: ""`
   - UI: add corresponding `<input>` or `<textarea>` element
5. **`AdminEditClient.tsx`**: add `field: event.field ?? ""` to form initialization.
6. **`web/messages/*.json`**: add i18n key to all three files (`zh`, `en`, `ja`) simultaneously.
7. **Event detail page** (`web/app/[locale]/events/[id]/page.tsx`): if the field is user-visible, add locale-aware rendering (e.g. conditional `<a>` for URL fields).

Missing any point causes silent failures. Particularly:
- Missing point 1 → `PGRST204` at runtime, not at compile time.
- Missing EMPTY_FORM or form init → field appears blank in admin even when DB has a value.
- Missing i18n key → raw key string rendered in UI.
- Vercel build failure from a TypeScript error does **not** take the site down — it serves the previous build silently. Regression is invisible to users until manually checked.
- All 6 locations must be updated in the same commit (union, CATEGORIES, CATEGORY_GROUPS, zh/en/ja messages). See Engineer SKILL.md § Category Update Protocol for the full list.


- `sources/{name}/` — per-scraper platform profile（有 `applyTo: scraper/sources/*.py`）
- `agents/{name}/` — per-agent operational rules
- top-level — workflow/tooling skills only（local-preview, cc-statusline, session-analytics）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下，不可直接放頂層

## SQL Privilege Syntax Guard
- For PostgreSQL privilege statements, verify object-type syntax before finalizing migration SQL.
- View privilege revocation should use `REVOKE ... ON TABLE <view_name> ...`, not `ON VIEW`.
- For Supabase Security Advisor fixes, validate these statements line-by-line before execution:
  - `GRANT ... ON ...`
  - `REVOKE ... ON ...`
  - `ALTER VIEW ... SET (...)`
- If SQL Editor reports a syntax error, resolve by exact failing line first; do not change security model design until syntax is confirmed valid.

## Supabase RPC Auth Context Guard
- For `SECURITY DEFINER` RPC functions that gate admin access, do not rely only on `request.jwt.claim.sub`.
- Use `auth.uid()` as the primary identity source for real app requests, then fallback to claim only for SQL Editor simulation: `coalesce(auth.uid(), v_sub::uuid)`.
- Keep the function deterministic and explicit: `set search_path = pg_catalog`, schema-qualify cross-schema objects (`public.user_roles`, `auth.users`).
- Preserve strict denial path: when no effective user id or role mismatch, raise `42501` (`admin privileges required`).
- Before approving migration rollout, verify four cases:
  - app admin request: PASS
  - app non-admin request: DENY 42501
  - SQL Editor with `request.jwt.claim.sub` set to admin uid: PASS
  - SQL Editor without claim injection: DENY 42501

## Classifier Keywords
- Avoid single-character or title words (博士, 先生, 教授) in category keyword lists — they appear as proper nouns (person names) and trigger false positives. Prefer compound terms: 「博士課程」「博士論文」「教授法」.
- After adding a new category with new keywords, run a dry-run of `backfill_categories.py` and manually inspect every match before applying to DB.
- When a backfill produces a suspicious tag (e.g., a plant-walk event tagged `academic`), trace which keyword triggered it and tighten the rule immediately.

## GitHub Actions Cron Dispatch Guard

在設計任何使用 `schedule:` cron 觸發並需要根據「是哪個 cron 觸發的」來 dispatch 不同行為的 workflow 前，**必須**確認：

1. **不要用精確小時 `-eq` 判斷**：GitHub Actions cron 啟動有 1–2 小時（甚至更長）的延遲。`if [ "$HOUR" -eq 21 ]` 在實際執行時幾乎永遠不會匹配。
2. **改用 6 小時視窗 `-ge`/`-lt`**：每個 cron slot 之間間隔 6 小時，用視窗範圍覆蓋延遲。
3. **`else` fallthrough 必須是安全行為**：若用 `else` 作 fallthrough，部署後要驗證每個分支是否都有被正確觸發，不能假設 `else` 只有在「預期外情況」才觸發。
4. **費用驗證**：multi-slot researcher 的費用應該均勻分布在各 slot；若某一 slot 費用異常高（如 $2.62 vs 其他 $0），應立即檢查 dispatch 邏輯。

Reference incident: 2026-05-04 — `researcher.yml` 所有 4 個 cron 全部 fallthrough 到 `else → slot3`，slot3 費用 $2.62/週（正常應為 $0.67），slot0/1/2 幾乎未執行。修復：改用 6 小時視窗。

## Scraper Failure Notes Guard

在設計或審核任何 `scraper_runs` 寫入邏輯前，**必須**確認：

1. **`success=False` 必須搭配 `notes`**：只寫 `success=False` 等於告訴你「失敗了，但不知道為什麼」。`notes` 欄位必須包含 `f"{type(exc).__name__}: {exc}"[:500]`。
2. **事後診斷需要 notes**：無 notes 的失敗記錄在週報中只能顯示「❌×N」，無法判斷是網路問題、selector 失效還是程式 bug。
3. **failure 寫入自身不應 raise**：failure logging 的 `except Exception: pass` 是正確的，避免 logging 失敗掩蓋原始錯誤。

Reference incident: 2026-05-04 — eurospace 3 次失敗（4/28–4/29）notes 全為 NULL，無法從 DB 追溯原因。修復：`main.py` except 區塊新增 `"notes"` 欄位。

## Persistent Zero Sources Diagnostic Guard

在週報或每日報告出現「持續 0 件」來源時，**不要立即 dry-run 或修改 scraper**，先依以下順序診斷：

1. **查歷史最高事件數**（`last_nonzero = never` ≠ 邏輯失效）：
   ```python
   sb.table('scraper_runs').select('events_processed,ran_at')
     .eq('source', src).order('ran_at').execute()
   # 計算 max_events 和 last_nonzero_date
   ```
2. **四種分類判斷**：
   - **季節性**：doc string 有年度節期（oaff → 3月、tokyo_filmex → 11月）→ 期間外 0 件是設計行為
   - **低頻設計**：doc string 說「1-2件/年」「2-5件/年」→ 前半年 0 件是常態
   - **時機問題**：場地排片無台灣內容 → 等新排片
   - **API key 缺失**：本地 `.env` 無 key → CI 可能正常，確認 Actions secret
3. **設定監控閾值**（不要人工週報審查）：`PERSISTENT_ZERO_DAYS=30` 觸發自動警告。

**給 doc string 加上活躍期標注**（防止未來誤報）：
```python
# Active period: Oct–Nov (festival announcement); returns [] outside festival year
```

Reference incident: 2026-05-04 — 13 個 0 件來源全部屬於正常狀態，透過查歷史+分類診斷在 30 分鐘內確認無需修改任何 scraper。修復：`daily_report.py` 加入 30 天自動監控。

## AI Model Selection
- Verify model capabilities before designing features requiring real-time data (web search, live prices, current events). `gpt-4o-mini` and `gpt-4o` have no web browsing. Use `gpt-4o-search-preview` or a real search API for current data.
- "Plausible-looking output" ≠ "real data access." A model without search access will hallucinate convincing-looking URLs.

## HTMLParser Thin Content Guard

在審核任何使用 `html.parser.HTMLParser` 的 scraper PR 前，**必須**確認以下三點：

1. **噪音標籤已被過濾**：`<script>`、`<style>`、`<nav>`、`<header>`、`<footer>` 等噪音標籤必須在 `handle_starttag`/`handle_endtag` 中跳過。
   - 標準 pattern：`_SKIP = frozenset({"script","style","nav","header","footer"})` + `_skip` 計數器
   ```python
   def handle_starttag(self, tag, attrs):
       if tag in _SKIP:
           self._skip += 1
   def handle_endtag(self, tag):
       if tag in _SKIP and self._skip > 0:
           self._skip -= 1
   def handle_data(self, data):
       if self._skip == 0:
           self._buf.append(data)
   ```
2. **有效內容不僅是 `len(text) > 0`**：JS/CSS 代碼也是非空文字，但對業務邏輯無用。需確認業務關鍵字（如 `日時`、`場所`）是否存在於提取文字中。
3. **字元限制是否足夠**：對含大量 JS 的頁面，2000 字元常常不夠（JS 代碼先消費完預算，業務內容在限制之後）。建議至少 4000 字元。

Reference incident: 2026-05-04 hakusuisha `_T` HTMLParser 未過濾 script/nav，`■日時：` 出現在 2000 字元之後 → `raw_description` 無效（commit `4784266`）。

## Scraper Self-Prefix Pollution Guard

在審核任何 scraper 先 prepend 前綴到 `raw_description` 再對整份文字做 regex 搜索的邏輯前，**必須**確認：

1. **Scraper 注入的前綴不干擾後續 regex**：若 scraper prepend `開催日時: YYYY年MM月DD日`，而後又用匹配 `開催日時` 的 regex 搜索整份文字，命中的是**自己注入的前綴**而非頁面原文的 `■日時：HH:MM〜HH:MM`。
2. **解法選擇（三選一）**：
   a. 用不同 pattern 區分「前綴格式」vs「頁面原文格式」（推薦：`_TIME_RE` 只匹配 `HH:MM〜HH:MM`，不匹配 `開催日時: YYYY年MM月DD日`）
   b. 限定搜索範圍到前綴之後（`text[len(prefix):]`）
   c. 在 prepend 之前先完成所有 regex 搜索，保存結果，再 prepend
3. **字元預算驗證**：detail-page 抓取加完 skip-tags 後，確認業務關鍵標籤（`■日時：`/`会場：`/`主催：`）在字元預算內。建議下限 8000 字元。

Reference incident: 2026-05-04 hakusuisha — `_JITSU_RE` 命中 scraper 自注入的 `開催日時:` 前綴，`business_hours` 永遠 null（commit `a0292a2`）。

## Listing Page Date vs Event Date Guard

在審核任何 auto-generated 或人工撰寫的 scraper，其 `FIELD_SELECTORS["date"]` 或 listing page 日期提取邏輯時，**必須**確認以下兩點：

1. **listing page 日期欄位語意需驗證**：`span.note`、`time.published`、`.date` 等 selector 抓到的可能是**記事公開日**（YYYY.MM.DD），而非**活動日**。需實際檢視 listing page HTML 確認語意。
2. **活動日應從 detail 頁 `日時：` 標籤提取**：若 listing page 日期語意不可靠，必須從 detail 頁的 `日時：`、`開催日時：`、`■日時：` 等結構化標籤提取。
   - 有 `日時`：prepend `開催日時: YYYY年MM月DD日` 到 `raw_description`
   - 無 `日時`（公告/新聞文）：prepend `（記事投稿日: YYYY年MM月DD日）` 年份錨點
   - 參考實作：`scraper/sources/hakusuisha.py` → `_extract_event_dates(detail_text, card_year)`

Reference incident: 2026-05-04 hakusuisha `FIELD_SELECTORS["date"] = "span.note"` 抓取記事公開日而非活動日（commit `b3708e1`）。

## Auto-Generate Scraper Date Field Guard

auto_generate で生成された Layer B scraper の `FIELD_SELECTORS["date"]` をレビューする際は：

1. **date キーが公開日か開催日かを確認する**。出版社・組織のお知らせサイトでは「記事公開日 ≠ イベント日」が普通。カードの日付テキストが `span.note` 等の「投稿日」要素を指している場合は、detail ページの `日時：` ラベルから抽出するロジックを追加すること。
2. **`start_date` 誤植は annotator では修正できない**。scraper が非 null の誤値をセットすると、annotator の `event.get("start_date") or GPT` チェーンは GPT 値を無視する（`or` は falsy 値のみ置換）。根本修正は scraper 側のみ。
3. **hakusuisha 参照実装**：`_extract_event_dates(detail_text, card_year)` — `日時：` ラベルから start/end を抽出する 3 パターン対応関数。同様の問題を持つサイトには同パターンを適用すること。

## reviewed 保護邊界 Guard

在審核任何觸及 `annotation_status = 'reviewed'` 保護邏輯的計畫或 PR 前，**必須**明確區分以下兩種情境：

### 保護有值欄位（不允許覆蓋）
- 已有值的 `category`、`start_date`、`end_date`、`name_ja`（若 `name_ja_locked`）等欄位，`reviewed` 狀態**應阻止** GPT 重新覆蓋。
- 違反此規則 = 人工確認的資料被機器覆蓋 = data quality regression。

### 允許補填空欄位（不應被阻止）
- 值為 `NULL` 的 `business_hours`、`location_name`（若原本就空）等欄位，`reviewed` 狀態**不應阻止**確定性（非 GPT）邏輯補填。
- 空值補填是「填入缺失資料」，不是「覆蓋已確認資料」。

**設計準則**：
1. `--fix-reviewed` 模式應支援「空值補填」——只有當欄位目前為 `null`/空 時才寫入，有值則跳過。
2. 確定性提取（regex pattern）比 GPT 更適合用於 `reviewed` 事件的補填，因為不會產生幻覺。
3. 計畫中若包含「修復 reviewed 事件缺失欄位」，需明確說明是「補填空值」而非「重新標注」。

Reference incident: 2026-05-04 `business_hours=NULL` 因 `reviewed` 狀態保護永遠不修復（commit `54a20d7`）。

## Online Location Standard
- **Canonical online event representation**: `location_name = 'オンライン'`, `location_address = 'オンライン'`. **Both columns must be set; neither should be NULL.** DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
- All scrapers must normalize online markers **before** building the `Event` object. Use `_ONLINE_RE` pattern: `r'(?:online|オンライン|ライブ配信|配信のみ|[Zz][Oo][Oo][Mm])'`.
- The web `location=online` filter queries `location_name ILIKE '%オンライン%'` (location_address is redundant for filtering but must still be set).
- The `location=other_japan` filter must exclude online events via BOTH `location_name NOT ILIKE '%オンライン%'` AND `location_address NOT ILIKE '%オンライン%'`.
- `AdminEventTable.tsx` `other_japan` filter must also check `!addr.includes('オンライン')` before accepting the event.
- Variants like `'オンライン（Zoom）'` must be canonicalized to `'オンライン'`.

## TV / Non-Physical Location Standard
- **Canonical TV/broadcast event representation**: `location_name = '電視頻道'`, `location_address = null`. TV programmes have no physical address — do not attempt to fill `location_address`.
- `gguide_tv` scraper must always set `location_name = '電視頻道'` regardless of the actual channel name (tvk1, BS朝日1, etc.). Storing raw channel names causes them to be treated as venue names and creates false positives in `other_japan` filtering and the quality page address check.
- The `location=other_japan` filter must exclude TV events via `location_name NOT ILIKE '%電視頻道%'`. Add this alongside the existing `オンライン` exclusion.
- **Quality page address check whitelist**: The「缺地址」(missing address) quality check must skip sources/venues that are inherently address-free. Current whitelist: `source_name = 'gguide_tv'` and `location_name ILIKE '%電視頻道%'`.
- When adding a new no-physical-address source in the future, update BOTH the `other_japan` filter exclusion AND the quality page whitelist.

## New Location Type Checklist

> **Pre-flight check**: Before adding a new location filter option, run `SELECT count(*) FROM events WHERE location_name = '<value>' AND is_active = true` to confirm there are enough matching events. A location option with zero or near-zero results is an invalid option and should not be added (or must be removed). The `tv` filter was added and later removed because `location_name` no longer matched — always verify DB data format against the actual scraper output first.

When adding a new `location` filter type (e.g., a new region or a new special category like `tv`), update ALL 6 of the following in the same commit:

1. **Scraper** — Set a canonical `location_name` value in the relevant scraper(s)
2. **`web/app/[locale]/page.tsx`** — Add the new filter branch with the correct Supabase query; update `other_japan` to exclude the new type if applicable
3. **`web/messages/{zh,en,ja}.json`** — Add the new i18n key to ALL THREE files simultaneously
4. **`web/components/FilterBar.tsx`** — Add the new `<option>` to the location select
5. **`web/components/AdminEventTable.tsx`** — Update BOTH `getFiltered` AND `sourceCountMap` with the new filter logic; add the `<option>` to the admin select; update `other_japan` exclusion
6. **Quality page** (`web/app/[locale]/admin/quality/page.tsx`) — If the new type has no physical address, add it to the「缺地址」whitelist

Missing any one of these causes: filter mismatch (items appear in wrong section), missing translation (raw key shown), or quality false positives.

### Overseas (Taiwan Cities) Filter Special Notes
- **Address format differs from Japan**: Taiwan city addresses are stored directly in the `address` column (e.g. `台北市…`). No prefix guard or `.startswith()` check is needed — Taiwan city names are not substrings of Japanese place names.
- **Use `ilike '%城市名%'`** for matching; do NOT use `location_name` equality — Taiwan events use the raw address column.
- **`OVERSEAS_MARKERS` must stay in sync** between `page.tsx` and `AdminEventTable.tsx`. The canonical 16-city list: 台北、台中、高雄、台南、新竹、嘉義、花蓮、台東、基隆、宜蘭、桃園、屏東、南投、彰化、雲林、澎湖.
- Overseas filter does **not** require exclusion from `other_japan` — these are physically separate geographic categories.

## Online Events (Peatix)
- Peatix renders online-only events as `LOCATION\n\nOnline event` (single line, no address group). The two-part regex `LOCATION\n\n(.+)\n\n(.+)` will NOT match — always add a separate `loc_online_m` check BEFORE the two-part regex.
- Set an `is_confirmed_online` flag immediately on match and **skip all CSS and regex address fallbacks** — description body text often mentions a venue as a conditional/secondary option and must never be used as `location_address`.
- For confirmed online events: `location_name = 'オンライン'`, `location_address = 'オンライン'`.
- The final body-text online fallback must also set `location_address = 'オンライン'`, NOT `None`.

## Address Verification
- **Never change a hardcoded address based on a DB value alone.** The DB may contain AI-hallucinated addresses from `backfill_locations.py` or the annotator. Always verify against the official source website first.
- Every hardcoded `location_address` in a scraper must include a comment citing the verification URL and date, e.g.:
  ```python
  # Verified: https://jp.taiwan.culture.tw/cp.aspx?n=362 (2026-04-26)
  location_address = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
  ```
- When a user questions a displayed address, use `fetch_webpage` on the official source URL before drawing any conclusion.
- If `backfill_locations.py` has run on a source with a known fixed address, audit those DB records — AI-generated translations may contain hallucinated street numbers.
- **`enrich_addresses.py` batch fills are AI-generated and NOT verified**: GPT-4o-mini fills `location_address` / `_zh` / `_en` for events with a venue name but no address. These must be treated as unverified estimates. Known failure: MoN Takanawa (新場館) was filled with `東京都港区高輪4-10-30` (incorrect) instead of `東京都港区高輪2-21-2` (2026-05-01). After any batch fill run, manually spot-check records from high-profile partner venues (SSFF, TAICCA co-hosted venues, etc.) against their official access pages (`会場・アクセス` section).

## i18n Completeness
- After writing or reviewing any TSX file with visible UI text, run the CJK audit before approving: `python3 -c "import os, re; [print(f+':'+str(i)+':'+l.strip()) for root,_,files in os.walk('web') for f in files if f.endswith('.tsx') for i,l in enumerate(open(os.path.join(root,f)).readlines(),1) if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]',l) and not any(p in l for p in ['t(','tFilters(','tCat(','tEvent(','getEvent','MARKERS','//',"'//"])]" 2>/dev/null`
- Module-level consts that include translated strings CANNOT use `useTranslations()` (React hook rules). Either move the const inside the component function, or pass the translation function as a parameter.

## Cross-Platform Environment Variables

When a feature spans **both GitHub Actions and Vercel** (e.g., LINE broadcast runs in GitHub Actions; LINE webhook runs on Vercel), each platform needs its own copy of every required secret.

**GitHub Actions secrets ≠ Vercel environment variables.** They are completely separate systems and do not share values automatically.

### LINE bot deployment checklist
Both of the following must be set in **both** platforms before the feature goes live:

| Variable | GitHub Actions Secrets | Vercel Env Vars |
|---|---|---|
| `LINE_CHANNEL_TOKEN` | ✅ (for broadcast) | ✅ (for webhook signature) |
| `LINE_CHANNEL_SECRET` | ✅ (for broadcast) | ✅ (for webhook signature) |

Setting a secret in only one platform silently breaks the other side. Webhook 401 failures are especially hard to detect because LINE does **not** retry failed webhook deliveries — events are permanently lost.

### General rule for cross-platform features
In the Verification section of any plan involving both CI (GitHub Actions) and web hosting (Vercel), explicitly list:
1. Which env vars are needed on **Vercel** (web-facing features: webhooks, API routes)
2. Which env vars are needed in **GitHub Actions** (CI/cron features: scrapers, broadcasts)
3. Any vars that are needed in both (shared secrets like LINE credentials)

## GITHUB_TOKEN Permission Consistency Guard

- Canonical wording for this repo:
  - Fine-grained PAT: `Issues: write + Metadata: read`
  - Classic token: `repo` scope
- Any change that touches token requirements must update all relevant layers in one batch:
  1. Runtime/error message (`scraper/update_source.py`)
  2. Operational docs (`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`, `.github/instructions/token-rotation.instructions.md`)
  3. Agent workflow docs (`.github/agents/researcher.agent.md`)
  4. Lifecycle summary (`.github/SECRETS_LIFECYCLE.md`)
- Do not allow non-standard permission wording (e.g. combining read+write with an `&`) to coexist with the canonical `Issues: write + Metadata: read`.

## Secrets Documentation Single Source Rule

- `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` is the single source of truth for the GITHUB_TOKEN sync checklist.
- Other files may reference it, but must not maintain an independent duplicated checklist body.
- If a legacy path must remain for compatibility (for example, `.github/TOKEN_SYNC_CHECKLIST.md`), convert it to a redirect-style stub that points to the docs source.

## Public Repo Secret Hygiene Check

- For public repositories, treat secret-documentation changes as security-sensitive changes.
- Before closing a token-related task, verify:
  1. `scraper/.env` is ignored by git (`git check-ignore -v scraper/.env`)
  2. No real token examples are committed in docs (use placeholders like `github_pat_xxx`)
  3. Secret references in tracked files are descriptive only, never literal credentials
- If a real credential is found in tracked files: rotate immediately, purge history if needed, then update docs with placeholders.
- Every new i18n key must be added to ALL THREE `messages/*.json` files simultaneously — never add to just zh.json.
- When an admin page uses `getTranslations("admin")`, check if it also needs `getTranslations("general")` for shared strings (footer, error banners).
## i18n Regression Prevention (CRITICAL)
- **翻譯 JSON 只能新增、修改，絕不刪除 key**，除非確認全 codebase 所有 TSX/TS 都已移除該 key 的引用。
- **Scraper / DB / Agent 等非 web commit 不得修改 `web/messages/*.json`**。如果 AI 在同一 commit 中捆綁了翻譯修改，必須 split commit 或手動 revert 翻譯部分。
- **Staging index 汙染防護**：commit 前必須先執行 `git status` 確認 staging area 只有預期的 file，再執行 `git add`。若其他檔案意外出現在 index（第一欄為 M 而非空格），代表舊的修改已 staged，需分開 commit。
- **pre-commit hook 自動保護（2026-05-07 起）**：`.git/hooks/pre-commit` 已加入 i18n regression guard。若 staged 的 messages/*.json 刪減了任何 key，commit 會被攔截並列出缺失 key。可用 `git commit --no-verify` 強制繞過，但必須有充分理由。
- 每次修改翻譯後，執行 key 完整性驗證：
  ```bash
  python3 -c "import json; a=set(json.load(open('web/messages/zh.json')).keys()); b=set(json.load(open('web/messages/en.json')).keys()); c=set(json.load(open('web/messages/ja.json')).keys()); print('zh-en diff:', a-b); print('zh-ja diff:', a-c)"`
  ```
- 若懷疑翻譯被洗掉，立即執行：`git log --oneline --since="3 days ago" -- 'web/messages/*.json'` 逐一檢查可疑 commit 的 diff（`git show <hash> -- 'web/messages/*.json' | grep '^-'`）。
- **根本防護**：`categories` namespace 中的 group_ 標籤（`group_arts`/`group_lifestyle`/`group_knowledge`/`group_society`/`group_archive`）和晚期新增的子分類（`competition`/`indigenous`/`history`/`urban`/`workshop`）是歷史上最常被意外洗掉的 key，每次 web 功能發布前必須確認這些 key 存在。

Reference incident: 2026-05-07 — commit `694a363` 將 web/messages/*.json 的 197 個 key（organizer, eventForm, admin 各段落）意外刪除，因為 `/tmp/fix_sources.py` 已把 messages 修改寫入 staging index，而後續的 `git add <3 files>` + `git commit` 捲走了所有 staged 變更。

## Reviewed Event Translation Guard (CRITICAL)
- **`reviewed` 狀態的活動不應有 `name_zh = NULL` 或 `name_en = NULL`**。若有，後台 AdminEventTable 會顯示紅色 ⚠ 徽章提醒管理員。
- **永遠不要在翻譯欄位未填齊的情況下將活動標記為 `reviewed`**。完整欄位清單：`name_zh`、`name_en`（必要）；`description_zh`、`description_en`（建議）。
- `annotator.py` 的 `--fix-reviewed` 旗標可自動修復缺少翻譯的 reviewed 活動（僅補翻譯欄位，保留 category 和 `annotation_status = "reviewed"`）。
- **daily CI 已設定每日自動執行 `python annotator.py --fix-reviewed`**，作為背景防護網。
- 設計涉及 `annotation_status` 流程的功能時，必須考慮 reviewed 活動跳出翻譯流程的問題。
## Prompt Efficiency (User-Side Rules)

## Migration Verification Protocol
- For any `SECURITY DEFINER` RPC or privilege-critical migration, establish a **four-quadrant verification matrix**:
  - App request with admin user (real auth.uid())
  - App request with non-admin user (real auth.uid())
  - SQL Editor with claim-injected admin uid (`request.jwt.claim.sub = '<admin_uuid>'`)
  - SQL Editor without claim injection (no auth context)
- Create an executable SQL smoke test suite (e.g., `027_smoke_test.sql`) with temp tables to avoid manual UUID copy-paste errors.
- Generate a verification report (e.g., `027_VERIFICATION_REPORT.md`) documenting:
  - Test date and status (ALL TESTS PASSED or FAILING with step number)
  - Each test's code line reference and expected result
  - Security architecture diagram (e.g., "Prefer auth.uid(), fallback to claim with exception handler, then role gate")
  - Deployment readiness checklist
- Mark migration as "PRODUCTION READY" only after all four quadrants + return type validation pass.

## Separate Workflow Decision（新 Pipeline 的 CI 設計原則）

當設計新的自動化 pipeline（auto-research、auto-generate、heartbeat PR 等）時：

- **禁止將新 pipeline 加入 `scraper.yml`**。`scraper.yml` 是事件抓取主流程，任何非必要的步驟失敗都不應中斷每日爬蟲排程。
- **每個獨立 pipeline 必須有自己的 workflow file**（例如 `auto-research.yml`、`auto-generate.yml`）。
- **排程時間設計**：新 pipeline 應在主爬蟲完成後排程。參考時間線（JST）：
  - 00:00 — researcher Slot 3（現有）
  - 00:30 — auto-research（30 分鐘緩衝後）
  - 01:00 — auto-generate（再 30 分鐘後）
  - 02:00 — daily report（彙總上述結果）
- 每個新 workflow 都應有 `workflow_dispatch` 以便手動觸發，並支援 `dry_run` input。

## Heartbeat Pipeline Guard（auto PR 建立的前提條件）

在設計或重啟「heartbeat PR 自動建立（auto-generated scraper PR）」pipeline 之前，以下三個先決條件必須全部滿足：

### 1. Prompt Injection 防護（必要）
`generate.py` 在 spec 生成時把 sample HTML 直接送入 LLM prompt。外部網站的 HTML 可能包含惡意 comment（如 `<!-- SYSTEM: ignore previous instructions -->`），操控 LLM 輸出惡意程式碼，再自動 commit 進 repo。

**解法（必須先實作）**：在 HTML 進入 LLM 前先 sanitize：
```python
from bs4 import BeautifulSoup, Comment

def sanitize_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "meta", "link", "noscript", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    return str(soup)
```
此 sanitize 步驟必須在 `_fetch_sample_html()` 回傳前執行，不能只在 spec 生成時執行。

### 2. sandbox 驗證強化（必要）
目前 sandbox 只檢查 `events_found >= 1`，不足以確認品質。heartbeat pipeline 啟用前須加入：
- `source_id` 穩定性：連續兩次執行 `source_id` 值不變
- `start_date` 非空且非 fallback 至今日（排除以發布日代替活動日的情形）

### 3. main.py 衝突避免（必要）
多個 auto-generated PR 同時修改 `scraper/main.py` 的 `SCRAPERS` 列表，merge 時必定衝突。解法之一：每個 PR 僅新增一行，並在 PR description 中標示唯一的插入位置（如「在 peatix.py 之後」）。

**此規則的後果**：在三個條件都滿足之前，`auto-generate.yml` 不應啟用 `--create-pr` 或 heartbeat 模式，只允許 dry-run + sandbox 驗證。

## Scraper Source Registration Audit
- Monthly audit: Compare `sources/` directory against `SCRAPERS` list in `scraper/main.py` to find unregistered source files.
  - Command: `comm -23 <(find sources/ -name '*.py' | xargs -I {} basename {} .py | grep -v '^__' | sort) <(grep 'Scraper()' scraper/main.py | sed 's/.*\(.*\)Scraper().*/\1/' | sort)`
- When a new scraper source file is created, immediately register it in `SCRAPERS` and run `python main.py --dry-run --source <name>` to verify event count is non-zero or document expected reason (offline season, no Taiwan matches, festival in October).
- Do not rely on CI discovery or daily cron to catch missing registrations — manual registration is mandatory at commit time.

## Cinema Official URL Extraction
- Cinema scrapers must extract `official_url` from the film detail page using one of:
  - Link with text "チケット" or "購入" (ticket/purchase keywords)
  - Href pattern containing `/ticket/` or `/purchase/` (domain-agnostic)
- Always verify extracted URL domain is not a third-party ticket vendor (e.g., Playplay, Peatix reseller, Rakuten Ticket) — maintain a domain whitelist of known official cinema URLs.
- When adding `official_url` extraction to an existing scraper, immediately backfill validation:
  1. Run scraper with `--dry-run` and manually inspect first 5 events
  2. Confirm URLs are valid, resolve without 404, and point to official pages (not redirects to vendor)
  3. Only then commit and push to production
- For Google Search fallback in film title lookup: always prioritize `name_ja` (Japanese title) regardless of current request locale. Google Search ranks results by search query locale, not result locale — using a locale-specific name variable will cause wrong film matches and incorrect `official_url` extraction.

## Prompt Efficiency (User-Side Rules)

When plans involve multiple similar tasks or iterative fixes, guide the user toward these batching patterns to avoid unnecessary tool overhead:

- **Scope creep via URL**: If a user pastes a URL and asks to "check similar cases", clarify scope first. Do NOT do a full codebase scan unless explicitly requested. Ask: "只修這個？還是要檢查所有同類？"
- **Sequential same-type tasks**: When the user says "請繼續做 XXX" for each item, propose batching: "建議一次列出全部，我依序完成後統一回報" to avoid repeated context reloading.
- **Fix + rule update coupling**: When discovering a bug, fix it first. Defer history/skill updates to a dedicated batch step. Recommend: "先修完所有 bug，稍後一次批次更新 skill 和 history。"

See `.github/skills/session-analytics/SKILL.md` for the full anti-pattern catalogue and efficiency thresholds.

## Agent Handoff Design

When designing agent workflows that need one-click handoff buttons:

### `.prompt.md` vs `.agent.md` Distinction
- **`.prompt.md`** — One-off tasks invoked via `/` command or skill menus. No persistent role, no tool restrictions per task. Use for: "Generate test cases", "Create README", "Summarize metrics".
- **`.agent.md`** — Persistent agent persona with role, tools, and instructions. Use for: long-running workflows, role-based tool restrictions, or handoff chains. Can be invoked via agent picker or as handoff target.
- **Handoffs only route to `.agent.md` files** — the `agent:` field in `handoffs:` must reference an `.agent.md` file's `name`, NOT a `.prompt.md` filename.

### Handoff Frontmatter Format
```yaml
handoffs:
  - label: "🔧 Button text"
    agent: AgentNameFromFile        # Must match .agent.md name exactly
    prompt: "Chinese instruction"    # Pre-filled when user clicks
    send: false                       # Optional, default false
    model: "Claude Sonnet 4.5 (copilot)"  # Optional, inherits agent default if omitted
```

### Subagent Configuration for Handoff Targets

> ⚠️ **Critical**: `user-invocable: false` **blocks handoff buttons from appearing**.
> Even though the VS Code docs describe it as "hide from agent picker only", in practice the
> handoff button does not render in the source agent's response when the target has `user-invocable: false`.

Handoff target agents must use the **default** (omit `user-invocable` entirely, or set `true`):
```yaml
---
name: My Handoff Agent
description: "Brief role description"
tools: [read, search, execute, web] # Minimal necessary tools
---
```

If you want the agent hidden from the manual picker AND still reachable via handoff buttons,
this combination does NOT currently work — `user-invocable: false` suppresses both.
The only way to keep it out of the picker while allowing handoff is to use `user-invocable: true`
and instruct users not to invoke it manually (via the description field).

Reference incident: 2026-05-14 — `update-history-agent.agent.md` and `validate-merge-deploy.agent.md`
had `user-invocable: false`. Handoff buttons were silently invisible in all 7 source agents.
Fixed by removing `user-invocable: false` (commit `6188653`).

### `send: true` — ⚠️ Do NOT use（VS Code 行為已改變）

**現行 VS Code 行為（2026-05-14 以後）：**
- 沒有 `send: true`：按下按鈕開新 chat，prompt **出現在 input 欄**等待使用者確認後按 Enter。✅ 推薦。
- 有 `send: true`：按下按鈕 prompt **立即 auto-fire**，使用者無法審閱或編輯。❌ 不建議。

**不要在 handoff 加 `send: true`：**
```yaml
handoffs:
  - label: "🔧 Button text"
    agent: AgentNameFromFile
    prompt: "Chinese instruction"   # prompt 會出現在 input 欄，等待使用者確認
    # 不加 send: true
```

> 歷史備忘：2026-05-14 之前，沒有 `send: true` 時 input 欄是空的（問題 B），所以加了 `send: true`。之後 VS Code 行為改變，`send: true` 變成 auto-fire。commits `4f1dd6c`（加入）→ `aa3f615` + `2463547`（移除）記錄這段轉變。

### Best Practices
1. **Name consistency**: Agent `name:` in frontmatter must match the handoff `agent:` field exactly (case-sensitive).
2. **Chinese instructions in prompt**: Always include `prompt:` field with clear Chinese task description to ensure context transfer.
3. **Never set `user-invocable: false` on handoff targets** — this silently breaks all buttons pointing to that agent.
4. **Always include `send: true`** on handoffs that have a `prompt:` field, or the prompt won't appear.
5. **Workflow grouping**: If two agents form a natural sequence (e.g., Plan → Implement → Review), add all three as handoffs in each agent to enable any→any routing.
6. **Testing**: After adding handoffs, `Developer: Reload Window`, then verify buttons appear in the response area after a message.

## Resource Monitoring

預算層——`scraper/weekly_report.py`（LINE 週報）為全站唯一資源使用監控來源：

- 三個門檻常數：`WEEKLY_OPENAI_USD_WARN = 5.0`、`WEEKLY_DEEPL_CHARS_WARN = 100_000`、`MONTHLY_BUDGET_USD = 20.0`。
- LINE 訊息包含：本月迄今 / OpenAI 本週 / DeepL 本週，超過閾值顯示 ⚠ 或 🚨。
- 適用時機：每週一 09:00 JST（GitHub Actions cron）。
- 閾值調整請同步更新這份文件與 `weekly_report.py` 常數。

## Admin Page Consistency

新增任何 `/admin/` 子頁面時，**header 必須使用完整 tab nav** 而非「← 返回管理後台」連結：

1. 從 `getTranslations("admin")` 取得所有 tab 標籤的 i18n 翻譯。
2. 使用與其他 admin 頁面一致的 Link 列表結構（參考 `web/app/[locale]/admin/aeo/page.tsx` 或 `events/page.tsx`）。
3. 把新 tab 的 key 同步加入三個 `messages/*.json` 中的 `admin` namespace。
4. 不可只放「← 返回」連結——這會破壞 admin 導航一致性。

反例：2026-05-01 aeo 頁面原本只有「← 返回管理後台」連結，後來在 commit 5cae991 才補齊完整 tab nav。計劃階段就應強制要求。

## Untrusted-Code Sandbox Rules (auto-scraper Phase 2+)

When designing any feature that runs LLM-generated or otherwise untrusted Python in a subprocess (auto-scraper codegen, plugin execution, etc.):

- **env scrubbing must be allowlist, not blacklist.** Pass only `PATH` / `HOME` / `PYTHONUNBUFFERED` / `PLAYWRIGHT_BROWSERS_PATH` / `TMPDIR` / `LANG` / `LC_ALL`. Never pop known secret keys (`SUPABASE_*`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `LINE_*`) from a copied env — any future `.env` addition will silently leak. Allowlist is fail-closed; blacklist requires constant maintenance.
- **Temp file cleanup needs both `try/finally` AND `atexit.register(cleanup)`.** `try/finally` covers normal + exception paths; `atexit` covers SIGKILL / unhandled exit. One alone is insufficient for codegen artifacts (e.g. `_auto_<name>.py` shimmed for subprocess import).
- **Mutation surface must be locked per phase.** Codegen / unsafe-validation phases must NOT register into production lookup tables (e.g. `SCRAPERS`), open PRs, or write to user-facing DB tables (`events`). Only the source's own status row may be updated. Activation must live in a separate phase / commit / reviewer to keep the unsafe→safe boundary auditable.
- **AST safety check + sandbox dry-run is the minimum bar** before promoting any auto-generated code to "ready for review". Both gates fail-closed.

Reference incident: 2026-05-01 commit `a0606fe` (auto-scraper Phase 2). Pre-implementation review chose allowlist after enumerating future `.env` additions.

## LLM Pricing Constants Re-verification

Any code path that gates on LLM cost (per-call budget, daily ceiling, abort-on-overspend) hardcodes pricing constants that drift over time. Architect session checklist when reviewing such code:

- **Verify pricing constants vs current OpenAI / Anthropic public pricing page** at every quarterly review or whenever the model upgrades (e.g. `gpt-4o` → `gpt-4.1`).
- **Centralize constants in one file.** Do not duplicate `INPUT_USD_PER_1M` / `OUTPUT_USD_PER_1M` across scrapers. Current home: `scraper/auto_scraper/generate.py` (`$2.50/1M input`, `$10.00/1M output`, default budget `$1.50/source`).
- **Pair every pricing constant with a comment citing the verification source URL and date.**
- **Treat budget guards as security-critical.** A stale pricing constant means the abort threshold is wrong — either runaway costs or premature abort. Add to release-readiness checklist: "Pricing constants checked? Y/N".

## Prompt-Referenced Artifact Verification

When reviewing any plan whose prompt copy says things like "matching the schema (provided)", "following the spec attached", "as listed below", verify the referenced artifact is **actually injected** into the LLM `messages` array — not merely cited by name.

- `grep` the prompt text for the file/schema name, then trace every reference to confirm: (a) the file is read at runtime, (b) its contents are concatenated into a `system` or `user` message, (c) the injection point sits BEFORE any place where the LLM is asked to use it.
- A prompt that references X without injecting X is functionally equivalent to omitting X entirely. The LLM will hallucinate a plausible-looking version of X.
- For required-field checklists in `spec.json`-style outputs, also enumerate critical fields explicitly in the prompt body (belt + braces). Schema injection alone is not enough — the LLM ignores schema details when verbose.
- Reference incident: 2026-05-02 Phase 2 — SYSTEM_PROMPT cited `spec_schema.json` but the schema was never loaded. Three retries omitted `base_url`. Fix in `b6e1768`.

**Plan-review checklist line**: "Every prompt-referenced artifact (schema, sample, examples) is verified to actually appear in the messages array."

## LLM-Generated Artifact Validation Pattern

For any LLM-generated artifact that references real-world identifiers (CSS selectors, file paths, function names, API endpoints, package names, environment variables), add a **fast pre-validation step** that confirms the reference exists before downstream consumption.

- **Grounding > trust.** LLMs hallucinate plausible-looking identifiers (`.event-card`, `.user-list-item`, `getUserById`) at high rates, especially when the reference base is large or the LLM is verbose.
- **Pre-validation should fail-fast and feed back into the retry loop.** Failure messages must be specific ("selector `.event-card` matches 0 elements in sample HTML; available repeating elements: `li.article-list` (12), `article.post` (4)") so the next LLM call can correct itself.
- **Cost asymmetry justifies the validation step.** A 50ms BeautifulSoup check vs a 30s Playwright sandbox + $0.04 LLM round-trip is 600× / $0.04 cheaper per failed validation.
- Reference incident: 2026-05-02 Phase 2.3 — `_validate_selectors_against_html()` added before sandbox spawn. Zepp Tokyo / Fukuoka Now batch1 wasted $0.04 each on sandbox-failed; batch2 fast-failed in <100ms with no Playwright spawn.

**Pattern catalogue** for future LLM-generated artifacts:

| Artifact | Validation step | Tool |
|----------|----------------|------|
| CSS selectors | `BeautifulSoup.select()` count ≥ 1 against sample HTML | bs4 |
| File paths in repo | `Path(...).exists()` | pathlib |
| Python function/class names | `ast.parse` + symbol walk | ast |
| URLs | HEAD request, expect 2xx/3xx | requests |
| Env var references | `os.environ.get(...) is not None` | os |

## Failure-Path Instrumentation

When a function returns different shapes for success/failure paths, instrumentation (cost, retry count, elapsed time, token usage) must be in a `finally` block or shared mutable accumulator — not after the success-only return.

- Symptom: meta files show `cost_usd=0.0` and `retries=0` on failed runs even though logs prove multiple LLM calls happened.
- Fix pattern: maintain `accumulator = {"cost": 0.0, "retries": 0}` at function scope; mutate in every retry branch; persist in `finally` regardless of exit path.
- Reference incident: 2026-05-02 Phase 2.3 spec-invalid path — 3 retries shown in logs, 0 cost in meta. Phase 2.4 TODO.

## Merger Schema Change Guard

在審核**任何**動到 `merger.py`、`works` 表、`parent_event_id` / `merged_into_event_id` 欄位、或新增 / 修改 Pass 1–N 邏輯的 PR 前，**必須**確認：

1. **Push 前在本地對生產 DB 跑 dry-run**（merger 與 schema 同步度極高，UNIT TEST 不能取代生產資料驗證）：
   ```bash
   cd scraper && python merger.py --dry-run 2>&1 | tail -20
   ```
   驗收標準：
   - 結尾必須出現 `Done: N pair(s)/orphan(s) would be merged`
   - **不可有 `Traceback`**
   - 所有 Pass 各自印出 `Pass X done` 或 `Pass X: ... handled`
2. **連續多個 merger 改動 commit 累積風險**：5/5 連 push `56b0ad2 → 27c21a7 → 79a5c40` 三個 merger 改動，全部沒跑 dry-run，導致 02:11 cron 噴 32s。**規則：當天每動 merger 一次都重跑 dry-run，不要連續 commit 不驗證**。
3. **新增資料模型欄位（`work_id`、`merged_into_event_id` 等）必須掃所有 Pass**：每一個 Pass 的 query / filter / skip 條件都要明確處理新欄位，不可假設「跟其他 Pass 一樣」。
4. **跨 source 特殊類型（`google_news_rss` 等 `_NEWS_SOURCES`）必須在所有 Pass 各自驗證**：5/5 失敗根因即「sub-event 處理只覆蓋 Pass 1/2 沒覆蓋 Pass 3」（fix `ab3bd9e`）。

Reference incident: 2026-05-05 19:52 + 2026-05-06 02:11 — Run Merger 連續兩次失敗。根因：`56b0ad2 / 27c21a7 / 79a5c40` 加入 `works` skip 與 `merged_into_event_id` badge logic，沒處理 google_news_rss sub-events 的特殊形式。修復 `ab3bd9e`（5/6 13:27）+ `5f98b3b` 又補 Pass 5。

## Sub-Venue Parent Address Guard

在審核任何包含 `location_name` 或 `location_address` 的 annotator 修改、或任何新 scraper 的 location 欄位邏輯前，**必須**確認以下四點：

1. **`location_address ≠ location_name`**：兩者相同是地址抽取失敗的標誌。SYSTEM_PROMPT 必須明示「identical 時保持 null」。`auto_qa_address_is_venue_name` 偵測器持續監控此情況。
2. **子場地 → 親設施地址**：`○○S.C. 森のまち広場`、`○○ビル2階 大会議室`、`○○ホール内 スタジオA` 等複合場地名，地址 geocode 對象是**親設施**，不是子空間。annotator SYSTEM_PROMPT 的 LOCATION ADDRESS RULE 需要有 PARENT VENUE ADDRESS RULE 段落。
3. **Scraper 端不得直接 `location_address = location_name`**：annotator 的 `_ai_or_existing()` 保護邏輯在 DB 欄位非 null 時會**保留 scraper 寫入的錯誤值**，不覆蓋。因此 scraper 若直接把 venue name 複製到 address，annotator 的規則完全無效。正確做法：scraper 使用 `_ADDR_RE`（`〒` 或 prefecture+city+street pattern）從 raw text 抽取真實地址；找不到則設 `None`。
4. **auto_qa 偵測器**：`auto_qa_address_is_venue_name`（`location_address == location_name`）必須存在於 `auto_qa.py` 的 `QA_TYPES` 中，且由 `run()` 呼叫。

Reference incidents:
- 2026-05-04 `878660a0 iwafu` — `流山おおたかの森S.C. 森のまち広場` scraper 直接設 `location_address = place_val`（venue name），導致 annotator 的 PARENT VENUE ADDRESS RULE 完全無效。修復：`iwafu.py` 改為 `_ADDR_RE` 抽取真實地址，找不到設 `None`。
- 2026-05-04 hakusuisha — annotator SYSTEM_PROMPT 加入 PARENT VENUE ADDRESS RULE，`auto_qa_address_is_venue_name` 偵測器加入 auto_qa.py。

## Scraper Address Regex Prefecture-Optional Guard

在審核任何 scraper 的 `_ADDR_RE`（或類似地址抽取 regex）定義前，**必須**確認：

1. **都道府県プレフィックスは `(?:...)?` 省略可能にする**：`東京都|...府|...県` を必須にすると、`港区芝公園3-2`（プレフィックスなし）のように公式サイトが都道府県を省略した住所がサイレントに `None` になる。
2. **`[市区町村]` を必須アンカーとして設ける**：prefecture optional にする代わりに `[^\s]{1,4}[市区町村]` を必須にすることで false positive を防ぐ。
3. **公式サイトの `body_text` を住所フォールバックとして活用する**：公式サイトを fetch する scraper では、`_ADDR_RE` を `main_text` に適用して失敗した場合、公式サイト `body_text` にも適用する。helper 関数は `body_text` を戻り値に含めること（iwafu は `_fetch_official_organizer_info` を 3-tuple 化済み）。
4. **サイレント失敗の識別**：`location_address = None` かつ `location_prefectures = None` のまま入庫 → annotator が正しく推定できず、Vercel 地図リンクも生成されない。CI では気づきにくい。

Reference incident: 2026-05-15 — 屋台湾フェス2026 `iwafu_1137442`、`location_address=None` / `location_prefectures=None`。根因は `_ADDR_RE` の都道府県必須プレフィックスと `official_body_text` の未活用（commit 修正済み）。



在審核任何使用 Contentful CDA API 的 scraper 前，**必須**確認：

1. **年度系列展的 `scheduleStartsOn` 可能為 `YYYY-01-xx`（財年佔位符）**，不代表實際開展日期。Contentful 使用整個 1 月（1/1 至 1/31）作為佔位，**不限 Jan 1**。
2. **Slug fallback 必須存在**：若 `start_date` 的**月份 = 1**（`start_date.month == 1`），從 URL slug 末尾 `/YYYY-MM-DD` 提取真實日期。
3. **不可只檢查 `day == 1`**：已觀察到 `2026-01-15` 也是佔位符（events `977da793`, `e7cf2a51`）。正確條件：`start_date.month == 1`。
4. **測試模式**：對抓到的所有事件印出 `name, start_date, slug`，確認無 January 佔位符。

Reference incidents:
- 2026-05-05 — event 6a91a4ce (アジア美術の歩き方 東アジア編) start_date=2026-01-01，真實日期 2026-04-18 在 slug (commit a1e58a9)。
- 2026-05-07 — events 977da793 (2026-01-15) 和 e7cf2a51 也是佔位符，guard 改為 `month == 1` 才完整覆蓋 (commit 7df9f56)。

## Scraper Server-Side Keyword Filter Verification Guard

在審核任何新 scraper 的關鍵字 URL 參數過濾前，**必須**確認：

1. **Server-side keyword filter 是否真正生效**：發送含 keyword 的請求，再發送不含 keyword 的請求，比較回傳數量。若兩次相同 → server-side filter 無效。
2. **必須加 client-side filter**：無論 server 是否過濾，都應在 Python 層加 `_is_taiwan_relevant()` 檢查，防止 server 行為無聲改變。
3. **Author bio false positive**：台灣大學名稱（`台湾大学`、`淡江大学`、`国立台湾師範大学` 等）出現在作者略歷中，不代表活動內容與台灣相關。需用 regex 排除後再計 keyword count。
4. **推薦 pattern**：
   ```python
   _AUTHOR_BIO_RE = re.compile(r'台湾[・・]?(?:大学|淡江|国立|師範|政治|成功|交通|中山|清華)')

   def _is_taiwan_relevant(title: str, description: str) -> bool:
       if any(kw in (title or "") for kw in TAIWAN_KEYWORDS):
           return True
       excerpt = (description or "")[:500]
       if sum(excerpt.count(kw) for kw in TAIWAN_KEYWORDS) < 2:
           return False
       cleaned = _AUTHOR_BIO_RE.sub("", excerpt)
       return any(kw in cleaned for kw in TAIWAN_KEYWORDS)
   ```

Reference incident: 2026-05-07 — bookandbeer `?keyword=台湾` 被 server 靜默忽略；初版無 client filter → 所有事件進 DB。進階修正排除作者略歷誤判 (commits 7df9f56, e1ab468)。
Reference incident: 2026-05-07 — tsutaya_portal `_is_taiwan_relevant()` 全文搜索導致 5 件アーティスト略歴偽陽性入庫（artist bio pos 586–1634）。修正：title 全文 + description[:500] に限定（commit `c3ae92a`）。

## gnews RSS Snippet Date Guard

在審核任何 RSS-based scraper 的 start_date 提取邏輯前，**必須**確認：

1. **RSS description snippet 不可用作 start_date 提取來源**：snippet 通常 < 200 字，缺乏完整年份/日期資訊，GPT 只能猜測 → 錯誤率高。
2. **article fetch 失敗時 start_date = None**（不是 fallback 到 snippet）：
   ```python
   # WRONG
   start_date = _extract_start_date(article_text or description_plain, pub_date)
   # CORRECT
   start_date = _extract_start_date(article_text, pub_date) if article_text else None
   ```
3. **`start_date = None` + universal year-anchor = 最佳 fallback**：annotator 的 `（記事配信日: YYYY-MM-DD）` 前綴已確保年份正確。
4. **health_check gnews_suspect alert 只對過去日期報警**：未來日期不影響使用者，屬 annotator 尚未處理的正常狀態，不需告警。條件：`start_date < today`。

Reference incident: 2026-05-07 — gnews RSS snippet fallback 造成錯誤 start_date；health_check gnews_suspect 對未來日期誤報 (commit 1c0f69a)。

## SCRAPERS List Completeness Guard（防止 main.py import 重排時丟失 scraper）

在審核**任何** `scraper/main.py` 的 commit 前，**必須**確認：

1. **SCRAPERS list 項目數不得減少**（除非明確停用某 scraper）：
   ```bash
   git diff HEAD -- scraper/main.py | grep "^-.*Scraper()" | wc -l
   # 若 > 0 → 必須確認每個刪除都是有意的
   ```
2. **scraper count 不變性**：`grep -c "Scraper()" scraper/main.py` 值只可增加或維持，不可下降。
3. **import 重排是高風險操作**：即使只是調整 import 排列順序，也需事後確認 SCRAPERS list 項目完整。
4. **功能性 commit 不應修改 SCRAPERS list**：year-anchor、merger、annotator 等 commit 不需重排 main.py imports。

Reference incident: 2026-05-08 — commit `694a363` 做 import 重排，意外刪除 `WalkerplusScraper`、`BigRomanticRecordsScraper`、`WasedaIclScraper`、`TsutayaPortalScraper`（與 2026-05-04 `045d1fa` 同型）。

## Venue = Organizer Default Guard

在審核任何美術館/博物館類 scraper 的 PR 前，**必須**確認：

1. **`organizer` 欄位已設定**：若 scraper 只有 venue 資訊，應設 `organizer = venue_name`。  
   美術館/博物館展示中，venue 通常即主辦方。
2. **`raw_description` header 包含 `主催:` 行**：確保 GPT annotator 有明確主辦信號，不靠推斷。
3. **`event_form` 已設定**：展覽類 scraper 應 hardcode `event_form = ["exhibition"]`；  
   reviewed 事件的 event_form 被 annotator 跳過，scraper 層是唯一機會。

Reference incident: 2026-05-05 — tokyoartbeat organizer 未設 → GPT 幻想 横浜美術館；event_form 未設且已 reviewed → 永遠空 (commit a1e58a9)。

## Film Title Cross-Language Verification Guard

在審核任何涉及**建立 works 記錄**或**批次映射電影中文片名**的計畫前，**必須**確認：

1. **必須先呼叫 `lookup_movie_titles(name_ja)`**：`scraper/movie_title_lookup.py` 已有完整的 eiga.com 查詢 pipeline，能從 `原題または英題` 欄位取得正確的中文／英文片名。批次腳本必須先對每一筆 work 的 `title_ja` 呼叫此函式，取得 `(name_zh, name_en)`。
2. **僅對 lookup 回傳 `(None, None)` 的片名需人工查證**：eiga.com 未收錄的片名才需用維基百科、台灣電影網、IMDb 交叉驗證。驗證來源優先順序：
   - 維基百科中文版（`zh.wikipedia.org/wiki/<片名>`）
   - 台灣電影網（`taiwancinema.bamid.gov.tw`）
   - IMDb（`imdb.com/title/<id>`）
3. **日→中電影片名禁止 GPT 直譯**：日文片名是日本發行商的行銷創作，與台灣原始片名經常完全無關（如 `導演你有病` → `超低予算ムービー大作戦`）。GPT 直譯必然產生看似合理的虛構片名。
4. **`field_corrections` 鎖定前必須確認值正確**：一旦用錯誤值 upsert `field_corrections`，`enrich_movie_titles()` 的 `_human_protected` 邏輯會永遠保護該錯誤值，自動修正 pipeline 完全失效。
5. **batch 腳本標準流程**：
   ```python
   from movie_title_lookup import lookup_movie_titles
   zh, en = lookup_movie_titles(title_ja)
   if zh:  # eiga.com 有結果 → 使用
       work['title_zh'] = zh
       work['title_en'] = en or work.get('title_en')
   else:   # eiga.com 無結果 → 標記待人工確認
       work['_needs_manual_check'] = True
   ```

Reference incident: 2026-05-05 — `超低予算ムービー大作戦` 被 GPT 直譯為 `超低預算電影大作戰`。eiga.com 上有正確答案 `原題：導演你有病 Out of Nowhere`，但批次腳本未呼叫 `lookup_movie_titles()`，直接用 GPT 結果寫入並鎖定 `field_corrections`，阻斷了自動修正 pipeline。

## Batch Script Post-Enrichment Guard

在審核任何 `_oneoff_*.py` 或 batch 修復腳本的計畫前，**必須**確認：

1. **腳本結尾必須呼叫 `post_batch_enrich(event_ids)`**：`annotator.py` 的共用函式，自動執行電影片名 eiga.com lookup + `field_corrections` 鎖定，避免 GPT 直譯幻覺。
2. **禁止在 batch 腳本中用 GPT 生成 `name_zh`/`name_en`**：改用 `lookup_movie_titles(name_ja)` 取得正確片名。
3. **`field_corrections` 只能鎖定經驗證的值**：未經 eiga.com 或人工確認的值，不可 upsert 進 `field_corrections`。
4. **人名修正需額外步驟**：`post_batch_enrich` 後執行 `python annotator.py --enrich-person-names`。
5. **`post_batch_enrich` 的實作位置**：`scraper/annotator.py`，在 `enrich_person_names()` 之後、`backfill_tier1_events()` 之前。

Reference incidents:
- 2026-05-05 — `_oneoff_fix_movies.py` 跳過 `lookup_movie_titles()`，導致 `超低予算ムービー大作戦` 被 GPT 直譯為虛構片名。
- 2026-05-05 — 月老翻譯反覆被 AI 覆寫，根因為手動修正未鎖 `field_corrections`。

## Auto-Research Low-Signal Policy Guard

在審核任何涉及 `auto_research.py` 閾值或 `not-viable` 判定的計畫前，**必須**確認：

1. **`SCORE_PROMOTE_THRESHOLD = 0.70` 是「自動昇格」的閾值，不是「viable/not-viable」的分界**：score 0.30–0.69 的來源標記為 `assessed`，留人工決定。人工可手動設為 `researched`。
2. **score < 0.30（台灣證據為零）才應保持 `not-viable`**：LLM 明確找不到任何台灣關聯性 → 真正 not-viable。
3. **Low-Signal Policy 適用情況（年度影展、低頻文化機構）**：以下情況人工應升格為 `researched`，即使 score 偏低：
   - 每天爬取成本 near-zero（靜態 HTML、< 5 頁）
   - 年度或不定期的台灣相關展覽 / 影展（JPIFF、アクロス福岡、Internet Museum 等）
   - 人工無法預測每年活動時間，定期爬取是唯一可靠方式
   - LLM 找到間接或弱證據（台灣藝術家「有時被邀請」、台灣電影「偶爾放映」）
4. **設計 auto_research 相關功能時，禁止用 score < 0.70 自動 → `not-viable`**：正確行為是 `assessed`（保留人工決定權）。
5. **重複來源必須在 auto_research cron 執行前封鎖**：若 candidate 是已 implemented 來源的重複（同 URL / 同 scraper），立即設為 `not-viable/skipped`，否則浪費 API token。

Reference incident: 2026-05-06 — score 0.30–0.70 的 5 筆來源（98/110/144/178/191）被 `not-viable` 阻擋，並發現 4 筆重複 candidate（251/252/257/260）。手動批量修正。根因：誤將自動昇格閾值當作 viable/not-viable 判斷標準。

## Entity Normalization Guard（organizers / venues tables）

在審核任何涉及主辦方聚合、場地報表，或使用 `organizer_id`/`venue_id` FK 欄位的計畫前，**必須**確認：

1. **`events.organizer`/`events.location_name` 保留為稽核用途**：報表與聚合使用 FK 欄位（`organizer_id`/`venue_id`），事件詳情頁仍顯示原始文字欄位。不可直接改動 `organizer` 文字欄。
2. **`_populate_entity_fks()` 在 `upsert_events()` 後自動執行**：新刮取的事件會自動比對 `organizers.aliases` 和 `venues.aliases` 解析 FK。若 migration 050 未套用，gracefully no-op（不報錯）。
3. **`backfill_entities.py` 必須在 migration 050 套用後執行**：先用 `_oneoff_review_organizer_clusters.py` 預覽聚類結果（SequenceMatcher ≥ 0.92），人工確認後再執行 backfill。
4. **新增 organizer/venue 實體時**：在 `organizers`/`venues` 表新增一行（`canonical_name_ja` + `aliases`），FK 解析管道自動處理後續事件。
5. **`works.work_type` 包含 `tv_drama` 和 `tv_variety`**（migration 051）：設計涉及電視劇或綜藝的 work entity 時直接使用；不需「other」fallback。

Reference: migration `050_entity_tables.sql`、`051_works_tv_drama.sql`（commit `913b7a2`）。

## gnews Sub-Event Merger Guard

在審核任何涉及 `google_news_rss` sub-events（`source_id` 含 `_sub`）的 merger 邏輯前，**必須**確認：

1. **gnews sub-events 必須參與跨來源 dedup（Pass 0/1/2）**：早期版本排除了 `_sub` 事件，導致 gnews 電影場次永遠不被 ks_cinema 等官方來源吸收。
2. **Pass 0 必須有 `_gnews_base_id` 守衛**：同一篇文章的 sub-events（例 `gnews_abc_sub1`、`gnews_abc_sub2`）代表同場次的不同場，不可彼此合併；比對 base ID 相同時跳過。
3. **Pass 0 位置守衛**：gnews sub-events 若地點不同（不同電影院），不可以 name similarity 合併——它們是不同場館的同一部電影。
4. **Pass 2（news matching）work_id 守衛**：有 `work_id` 的 news event 已被 Pass 1 按名稱相似度處理，不再以日期+地點做第二次合併（避免 false positive）。
5. **每日 CI 在 `enrich-person-names` 後執行第二次 merger**：同日爬取後的新 sub-events 也能在當天完成合併。

Reference: commits `ab3bd9e`（gnews sub-events in all passes）、`5f98b3b`（Pass 5 same-work_id dedup）。

## SC → TC Guard（簡體字防護）

在審核任何涉及 GPT enrichment 函式（`enrich_person_names`、`enrich_movie_titles`）或 `auto_qa --fix` 的計畫前，**必須**確認：

1. **所有 GPT 輸出必須過 `_to_trad()`**：`enrich_person_names()` 的 GPT 回傳值必須通過模組層級的 `_to_trad()` 函式，防止 SC 字元重新引入。
2. **`auto_qa --fix` 修正後必須鎖 `field_corrections`**：`fix_simplified()` 轉換完畢後呼叫 `_lock_fields_via_corrections()`，防止下次 re-annotation 再覆寫。
3. **`_SIMP_TO_TRAD` 字元映射表為模組層級**：不可放在函式內（否則 enrichment 函式呼叫不到）。

Reference: commits `239cb19`（enrich SC guard）、`6e21c52`（auto_qa lock）。

## workflow_run Self-Loop Guard

在審核任何使用 `workflow_run` trigger 的 notify workflow 前，**必須**確認：

1. **`workflow_run` + job 層級 `if:` 的 `failure` 語意**：當 `if:` 條件為 false，整個 workflow run 的結論是 `failure`（"No jobs were run"），**不是 `skipped`**。若 notify workflow 本身在監控清單 `workflows:` 裡，它的 `failure` 會再次觸發自身，形成無限迴圈。
2. **self-exclusion 是必要守衛**：任何 notify workflow 必須在 job 層級 `if:` 加入自我排除條件：
   ```yaml
   if: >
     github.event.workflow_run.conclusion == 'failure' &&
     github.event.workflow_run.name != '<本 workflow 名稱>'
   ```
3. **或將自身從 `workflows:` 移除**：若 `workflows:` 明確列舉被監控的 workflow，確保列表不包含本 workflow 自身的名稱。
4. **`skipped` 不等於 `failure`**：workflow 本體的結論 `skipped` 由 GitHub 定義；job 層級 `if: false` 的結論是 `failure`（workflow 有執行，但沒有任何 job 跑）。

Reference incident: 2026-05-06 — `workflow-failure-notify.yml` 自我觸發 → 無限迴圈 → 垃圾通知郵件（commit `266daa1`）。

## NON_DAILY_SOURCES Registration Guard

在建立**任何新的定期（非每日）workflow** 或 **health_check 相關改動**前，**必須**確認：

1. **`health_check.py` 的 `NON_DAILY_SOURCES` 必須包含所有非每日 source**：每新增一個非每日 cron workflow，立即在同一 commit 更新 `NON_DAILY_SOURCES`。
   ```python
   NON_DAILY_SOURCES: frozenset[str] = frozenset({
       "weekly_broadcast",
       # <new_non_daily_source>,
   })
   ```
2. **不在 `NON_DAILY_SOURCES` 的 source = health_check 認為應每日執行**：若 7 天內有執行記錄但今天沒跑，health_check 每天回報 missing，直到修復。
3. **cron 頻率 vs health_check 告警頻率需對齊**：weekly cron（7 天一次）不可被 daily health_check（每天）誤報 missing。告警觸發條件應為「最近 N 天內無記錄（N = cron 間隔 + 1 天緩衝）」。
4. **同時更新 checklist**：若有 source 進入 `NON_DAILY_SOURCES`，在對應的 workflow yml 加上 comment 標注告警視窗。

Reference incident: 2026-05-06 — `weekly_broadcast` 因 `NON_DAILY_SOURCES = frozenset()` 為空，被 health_check 每天誤報 missing（commit `7df9f56`）。

## GitHub Actions YAML Guard

在審核任何新增或修改 `.github/workflows/*.yml` 的計畫前，必須確認：

1. **`if:` 欄位只允許單行雙引號字串**：
   - ❌ `if: |` 或 `if: >-`（block scalar）→ GitHub Actions YAML 解析器不支援 → parse error。
   - ✅ 必須：`if: "condition1 && condition2"`（全部在雙引號內，單行）
   - 長條件可用 `&&` 連接，不可換行。

2. **`run: |` 區塊內不可包含 `[{...}]` inline 模式**：
   - `[{"type": "text", "text": ...}]`（flow sequence + nested flow mapping）在 `run: |` 區塊內會被 GitHub Actions YAML 解析器誤判為 nested mapping → parse error。
   - 修復方法：將 jq filter / JSON 內嵌結構先賦值給 shell 變數，再引用：
   ```bash
   # ❌ 不可（將被誤判為 nested mapping）
   run: |
     echo '{"k": [{"type":"text"}]}' | jq .

   # ✅ 正確（先賦值給 shell 變數）
   run: |
     JQ_FILTER='{"k": [{"type":"text"}]}'
     echo "$JQ_FILTER" | jq .
   ```

3. **連續 parse error 時的應對順序**：
   - Error A（`if: |`）→ 改單行雙引號字串。
   - Error B（`if: >-`）→ 同上。
   - Error C（`[{...}]` in `run: |`）→ 賦值給 shell 變數。

Reference incidents: 2026-05-07 — commits `0b5ba72`、`c38ddd5`、`b9a462c`：`workflow-failure-notify.yml` 連續三次 YAML parse error，依序為 `if: |` → `if: >-` → `if: "..."`，加上 jq filter 賦值變數才全部解決。

## Movie Lookup Official URL Guard（`lookup_movie_titles()` 3-tuple + eiga.com `/jump/?u=` 解析）

在審核任何擴充 `lookup_movie_titles()` 或 `enrich_movie_titles()` 的計畫前，**必須**確認：

1. **回傳型別包含 official_url**：`lookup_movie_titles()` 回傳 `(name_zh, name_en, official_url)` 3-tuple。official_url 從 eiga.com detail page 的 `オフィシャルサイト` `/jump/?u=<URL-encoded>` 解析（`urllib.parse.parse_qs`）。
2. **寫入保護**：`enrich_movie_titles()` 寫入 official_url 時，**只在 event 目前 official_url 為 null/falsy 才寫入**，不可覆寫已存在值（否則可能蓋掉已 FC-lock 的人工值）。
3. **寫入後自動 FC 鎖定**：呼叫 `_lock_fields_via_corrections()` upsert 進 `field_corrections`，與其他 enrich_* 函式一致。
4. **Backward-compatibility**：擴充回傳型別時，所有呼叫點的解包必須同步更新（目前 `annotator.py` 共 3 處：~line 1892, 1902, 2468）。漏更新會 silent break（`ValueError: too many values to unpack`）。

Reference incident: 2026-05-12 — Phase A 實作；3 個呼叫點全部更新後上線。

## Movie Re-release official_url Guard（4K 重映 / リバイバル / リマスター）

對 `raw_description` 含「**4K**」「**リバイバル**」「**リマスター**」「**デジタル修復**」「**○周年**」等重映信號的電影類事件，annotator/lookup pipeline 提取的 official_url **不可信任**——eiga.com 收錄的多半是原作頁，新版發行的官方網站（如 4K 重映專屬站）detail page 常**沒有** `オフィシャルサイト` jump link。

**判斷信號：**
- 電影頁面有「○○年○月○日劇場公開」但年份比原作晚很多（如 2000 年作品 / 2025 年公開）。
- 配給商欄寫「ポニーキャニオン」「ライツキューブ」等專做重映的公司。
- raw_description 含上述關鍵字。

**遇到時的補救流程：**
1. Google 搜尋「`<原片名>` 公式サイト」或「`<原片名>` 4K」。
2. 確認該域名是新版發行的官方網站（檢查發行公司資訊）。
3. UPDATE event official_url + FC 鎖定。
4. 若該重映已建 work_id，可考慮把 official_url 也記到 `works` 表，方便日後其他場次共用。

Reference incident: 2026-05-12 — ヤンヤン 4K 重映實際官網為 `yi-yi.jp`，但 eiga.com 詳情頁無 jump link；初次 enrich 寫入錯誤 `yiyi-movie.jp`，需手動修正並 FC 鎖定。

## Aggregator official_url Guard（聚合站來源的 `official_url ≠ source_url`）

在審核**任何**新 scraper 或既有 scraper 修改的計畫前，**必須**確認 `official_url` 的設定方式與 source 性質一致：

1. **Aggregator 來源**（第三者投稿型／集約站）`official_url` 不可 fallback 到 `source_url`：
   - 對象：`tokyoartbeat`、`peatix`、`doorkeeper`、`connpass`、`eplus`、`livepocket`、`kokuchpro`、`walkerplus`、`arukikata`、`prtimes`、`ftip`、`google_news_rss`、`nhk_rss`、`note_creators`
   - `source_url` = aggregator 頁面（保留作 audit trail）
   - `official_url` = 從頁面 body 提取的主辦方一手 URL；提取不到時必須為 `None`
2. **常見反 pattern**：
   - `source_url = official_url_extracted` — 破壞 audit trail（已於 ftip 2026-05-10 處理）
   - `official_url = ... or source_url` — CMS 欄位為空時靜默汚染（已於 tokyoartbeat 2026-05-16 處理）
3. **First-party 來源例外**（`source_url` 自體即官方頁，可明示設定 `official_url=url`）：
   - `taiwan_cultural_center`、`taiwan_matsuri`、`koryu`、`taioan_dokyokai`、`taiwan_kyokai`、`asahiculture`、各 cinema scraper
4. **審核命令**（規劃完成前執行）：
   ```bash
   grep -rn "official_url.*or source_url\|official_url=source_url" scraper/sources/
   # 期待結果：0 件
   ```
5. **影響範圍**：`official_url` 汚染後 UI「公式サイト」按鈕指回 aggregator 而非主辦方頁面，使用者無法到達真正的活動資訊源。

Reference incidents:
- 2026-05-10 — `ftip.py` `source_url` 被 official_url 覆寫，破壞 FTIP audit trail（commits `ab771e2` → `7c34788`）。
- 2026-05-16 — `tokyoartbeat.py` line 124 `or source_url` fallback 汚染 event `74ee6d89`（共時的星叢）official_url；DB 修正 + FC 鎖定，scraper 改為 `or None`。

## Venue Parent vs Sub-event business_hours Guard

在審核任何「**場館型父事件 + 多場次 sub-event**」結構（YCAM、新文芸坐、シネマート新宿、ks_cinema 等）的 `business_hours` 設定計畫前，**必須**確認：

1. **父事件 `business_hours` = 場館營業時間**：開館時間、休館日、固定休業日（例：「10:00–20:00、火曜休館」）。
2. **Sub-event `business_hours` = 場次時刻**：一場放映/演出一行（例：「4/20（土）14:00〜」）。
3. **兩者同時並存，不可互相覆寫**：父的場館時間不能被 sub 的場次時刻取代；sub 的場次時刻不能被父的場館時間取代。
4. **三語版本（ja/zh/en）都要設定 + FC 鎖定**：`business_hours` / `business_hours_zh` / `business_hours_en` 一起。

**反模式：** 父事件 business_hours 寫成「2026年4月15日〜4月26日 各場次..」（放映期間摘要）→ user 看不到場館的實際開門時間。

Reference incident: 2026-05-12 — YCAM `6801814c` 父事件 business_hours 原為放映期間摘要，修正為場館營業時間「10:00–20:00、週二休館」；場次時刻全部移至 sub-events。

## Google Cloud API Avoidance Guard

在審核任何引入 **Google Cloud API**（特別是 Custom Search、Translation、Vision 等需要 GCP project 啟用的 API）的計畫前，**必須**確認：

1. **前例驗證**：該 API 在此 GCP project 過去是否成功呼叫過。若無前例，**先做 30 分鐘 spike test** 驗證 `403 PERMISSION_DENIED` 不會發生（即使帳單綁定、API enable、key 無限制，仍可能因組織政策或 project metadata 而被擋）。
2. **替代方案優先**：優先考慮**無 GCP 依賴**的替代——TMDB API（電影資料 + homepage）、OpenAI、Anthropic、DeepL、原始來源網站直爬。
3. **Graceful skip**：若仍要保留 GCP API 為 fallback，必須在 helper 內偵測缺 key / 403 / 401 時 graceful skip（log warning，不丟例外），避免拖垮主 pipeline。

Reference incident: 2026-05-12 — `movie_title_lookup` Phase B 嘗試 Google Custom Search API fallback；帳單已綁定、API enable、key 無限制、等待 5+ 分鐘、換新 key、改 endpoint 都試過，**持續 `403 PERMISSION_DENIED`**，無法在使用者端解決。Phase B 程式碼保留為 graceful-skip 結構，但不再規劃用 GCP API 作 fallback。

## Migration Constraint Replacement Guard（REPLACE CONSTRAINT 現存值超集守護）

在審核任何 `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT … CHECK` 組合的 migration 前，**必須**確認：

1. **先查現存值**：執行診斷查詢，列出目標欄位的所有現存值：
   ```sql
   SELECT unnest(event_form) AS val, count(*) FROM events
   WHERE event_form IS NOT NULL GROUP BY val ORDER BY count DESC;
   ```
2. **新 constraint 必須是現存值的超集**：任何現存值不在新清單內 → `ERROR: 23514` migration 失敗。
3. **migration 執行前先在 staging 跑診斷**；若無 staging，在 SQL Editor 先 `EXPLAIN` 或只 `SELECT` 檢查。

Reference incident: 2026-05-15 — migration 047 `study_abroad`（1 筆）不在新清單，觸發 23514。

## organizer_type Source-Level Batch Inference Guard（來源級批次推斷守護）

在設計任何 `organizer_type` 批次補值腳本前，**必須**確認：

1. **可批次推斷的條件**（全部滿足）：
   - 來源名稱（`source_name`）對應的機構性質高度一致
   - 該來源所有事件的 organizer 均為同一機構（如 cinema、大學、官方文化節）
2. **不可推斷的條件**（任一條件成立即保留 `['unknown']`）：
   - `organizer` 欄位為空
   - `organizer` 為縮寫代號（如 `RTC`、`湾.味`）無法對應已知機構
   - 薄文本來源（`note_creators`、RSS snippet）依 Blog/Creator Source Guard
3. **Python 傳值型別**：`organizer_type` 是 `text[]`，必須傳 Python list（`['civic_group']`），不可傳字串
4. **不需要 FC 鎖定**：`organizer_type` 不在 `TRACKED_FIELDS`，補值後不需寫 `field_corrections`

Reference incident: 2026-05-15 — gguide_tv（media）、cinema 來源（independent_venue）、wuext_waseda（academic）等批次推斷後 organizer_type 非 unknown 從 70% 提升至 92.1%。

