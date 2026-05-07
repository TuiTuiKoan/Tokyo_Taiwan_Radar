# Engineer Error History

<!-- Append new entries at the top -->

---

## 2026-05-07 — performers[] 手動補充 + 非日本地點停用流程

### performers[] 手動補充（三個 taiwanshi 事件）

**操作：** 從 `raw_description` 手動提取發表者姓名，直接 upsert `events.performers[]`，同時在 `field_corrections` 鎖定保護。三個事件：
- `37d53a28`（1月例会および総会）→ `performers=['野口英佑', '藤田千彩']`
- `578f0a01`（6月例会）→ `performers=['小林善帆', '釋七月子']`
- `dfb490c8`（日本台湾学会第22回関西部会研究大会）→ `performers=` 13 位（報告者 5 + 評論者 5 + シンポジウム登壇者 3）

**三人以上時 `performer`（TEXT）保留 null**：不設單一 performer，`performers[]` 為唯一出口。
**必須鎖定 field_corrections**：upsert 後鎖 `performers` 欄位，防止下次 re-annotation 清空。

```python
sb.table('events').update({'performers': ['野口英佑', '藤田千彩']}).eq('id', eid).execute()
sb.table('field_corrections').upsert({
    'event_id': eid, 'field_name': 'performers',
    'corrected_value': json.dumps(['野口英佑', '藤田千彩'], ensure_ascii=False)
}, on_conflict='event_id,field_name').execute()
```

### 非日本地點停用流程（`7a3d83ac` 首爾公演）

**問題：** 首爾公演被抓取入庫，地址誤設大阪 Channel 1969。
**修復模式：**
```python
sb.table('events').update({
    'is_active': False,
    'deactivated_reason': 'out_of_scope: Seoul, South Korea concert — not a Japan event',
    'location_address': None,
    'location_prefectures': None,
}).eq('id', eid).execute()
```
**規則：** `deactivated_reason` 格式為 `'out_of_scope: <說明>'`，包含城市與國家。停用時同步清除地址欄位，避免錯誤地址留在 DB 污染後續分析。非日本地點**不**鎖 `field_corrections`（停用後無需保護欄位值）。

---

## 2026-05-09 — annotator performer → performers[] 自動同步（commit 4526d3a）

**Feature：** 當 annotator 設定 `performer` 且 `performers[]` 為空時，自動設 `performers = [performer]`，讓 UI 永遠能從 `performers[]` 讀取，不需 fallback 回 `performer`。

**觸發條件（全部成立才同步）：**
1. `update_data.get("performer")` — 本次 annotator pass 有設定 performer
2. `not event.get("performers")` — DB 現有 performers[] 為空/null
3. `not update_data.get("performers")` — GPT 本次未回傳 performers 陣列
4. `"performers" not in _human_protected` — performers 未在 field_corrections 保護中

**三欄位職責（不可互換）：**

| Field | Type | 職責 |
|-------|------|------|
| `performer` | `TEXT` | 日文單人主表演者；annotator GPT/regex 輸出；`getEventPerformer()` fallback 來源 |
| `performer_zh` / `performer_en` | `TEXT` | performer 的語言翻譯（一對一對應）；GPT 填入或人工設定 |
| `performers[]` | `TEXT[]` | 多人顯示陣列；學術研討會全體發表者；自動 sync 自 performer |

**⚠ performer 欄位不可刪除**：`performer_zh/en` 是以 `performer` 為錨點的一對一翻譯；若 `performers[]` 有多人則翻譯欄位意義不明。設計決定：三欄並存，自動 sync 確保 UI 一致。

**Lesson：** 新功能設計前先確認欄位依賴關係。「刪除 performer 改用 performers[]」看似簡化，實際上 annotator.py、database.py、base.py、AdminEditClient、AdminEventForm 等 34+ 處引用，且 performer_zh/en 翻譯對必須有一對一的錨點欄位。

---

## 2026-05-09 — 手動修正污染了 field_corrections（c6d5232a）

**Problem:** 前次手動修正事件 `c6d5232a` 時，誤把污染後的 `description_ja`（霧のごとく版本）直接更新進 DB，並將 `name_zh=大濛` upsert 進 `field_corrections`。由於 FC 的 P1 保護，後續 re-annotation 永遠無法覆寫，污染被鎖定。

**Root cause:** 手動修正前未先讀取 `raw_description`（原始資料），直接從 `name_ja`/`name_zh`（已被 annotator 污染的欄位）推導修正值，導致把錯誤值當正確值鎖入 FC。

**Fix:**
```python
# 1. 刪除錯誤的 FC
sb.table('field_corrections').delete().eq('event_id', eid).eq('field_name', 'name_zh').execute()

# 2. 從 raw_description 重建正確值，更新 events 表
sb.table('events').update({
    'name_ja': '赤い糸 輪廻のひみつ',
    'name_zh': '月老',
    'name_en': 'Red Thread: The Secret of Reincarnation',
    'work_id': 'fd225042-...',
    'parent_event_id': '6649f6ba-...',
    'description_ja': '...',  # 從 raw_description 重建
}).eq('id', eid).execute()

# 3. 鎖定正確值
for field, val in [...]:
    sb.table('field_corrections').upsert({'event_id': eid, 'field_name': field, 'corrected_value': val},
                                          on_conflict='event_id,field_name').execute()
```

**Lesson:** 手動修正前**必須先讀 `raw_description`**，確認修正方向正確再 upsert FC。從已被污染的 `name_ja`/`name_zh` 欄位取值再鎖定 = 將污染永久化，後續無法自動修復。驗證命令：`SELECT id, raw_title, raw_description, name_ja, name_zh FROM events WHERE id = '<eid>'`。

---

## 2026-05-09 — performers[] 優先序蓋過 performer_zh/en，zh/en locale 永遠顯示日文名稱（commit 2e6f4c2）

**Problem:** `web/app/[locale]/events/[id]/page.tsx` 在顯示 performer 時，`performers[]`（永遠是日文陣列）的優先順序高於 `getEventPerformer(locale)`，導致 zh/en 頁面永遠顯示日文名稱，即使 `performer_zh`/`performer_en` 已設定（例：`ホアン・イーウェン` 在 zh 頁應顯示 `黃以文`，但始終顯示日文）。

**Root cause:** performers[] join 邏輯放在最前面，未先檢查 locale + performer_zh/en 的存在性。migration 054 新增多語言欄位後，UI 優先序未同步更新。

**Fix (commit `2e6f4c2`):**
```tsx
{locale !== "ja" && ((event as Event).performer_zh || (event as Event).performer_en)
  ? getEventPerformer(event as Event, locale)
  : ((event as Event).performers ?? []).length > 0
    ? (event as Event).performers!.join("、")
    : getEventPerformer(event as Event, locale)}
```
邏輯：zh/en locale + performer_zh/en 存在 → `getEventPerformer(locale)`；否則 `performers[].join("、")`；否則 `getEventPerformer` fallback。

**Lesson:** `performers[]` 永遠是日文陣列，不可作為 zh/en locale 的主要顯示來源。新增多語言欄位後，事件詳情頁的 UI 顯示優先序必須同步更新，否則新欄位永遠不會被 end-user 看到（隱性迴歸）。

---

## 2026-05-06 — business_hours 多日場次換行未顯示（commit af33133）

**Problem:** 電影多日場次的時刻表（`business_hours` 欄位，各場次以 `\n` 分隔）在詳情頁 `<td>` 元素內顯示為單行，換行符被 HTML 忽略。

**Root cause:** `web/app/[locale]/events/[id]/page.tsx` 的 `business_hours` `<td>` 未設定保留空白字元的 CSS 屬性，瀏覽器預設 `whitespace: normal` 折疊所有換行。

**Fix (commit `af33133`):** `<td>` 加入 Tailwind class `whitespace-pre-wrap`：
```tsx
<td className="... whitespace-pre-wrap">{getEventBusinessHours(event, locale)}</td>
```

**Lesson:** `<td>` 或 `<div>` 顯示含 `\n` 的多行文字時，必須加 `whitespace-pre-wrap`（保留換行 + 自動折行）。三種 class 的差異：`whitespace-pre-wrap`（保留換行 + 折行，**正確選擇**）、`whitespace-pre`（保留換行但不折行，內容過長時溢出）、`whitespace-normal`（預設，忽略換行——**勿用於多行字串**）。

---

## 2026-05-06 — works work_type check constraint 不含 conference

**Error:** 建立學術研討會 work 記錄時使用 `work_type='conference'` → `APIError: violates check constraint "works_work_type_check"`。

**Root cause:** Migration 048 + 051 的 check constraint 只允許 `film | stage | exhibition | concert_tour | tv_drama | tv_variety | other`。PostgreSQL check constraint 沒有 schema 預覽，執行時才報 IntegrityError。

**Fix:** 改用 `work_type='other'`；新建 work `c3588296`（日本台湾学会第23回関西部会研究大会）。

**Lesson:** 建立 works 記錄前先查現有 `work_type` 值：`sb.table("works").select("work_type").execute()`。或查 migration SQL 確認 check constraint 允許值。

---

## 2026-05-06 — CI YAML parser quirk: [{...}] inline jq filter

**Error:** `.github/workflows/workflow-failure-notify.yml` 的 `run: |` block 中包含 `[{type:"text",...}]` inline jq filter → GitHub Actions YAML parser 錯誤：`Nested mappings not allowed in compact mappings`。

**Root cause:** GitHub Actions YAML parser 對 block scalar（`|`）內容仍做 YAML 解析，`[{...}]` 被識別為 inline mapping array。這是 GitHub YAML parser 的 known quirk，非標準 YAML 行為。

**Fix (commit `b9a462c`):** 將 jq filter 指派給 shell 變數 `JQ_FILTER`，避免 `[{...}]` 直接出現在 inline argument：
```yaml
run: |
  JQ_FILTER='[{type:"text",text:"..."}]'
  curl ... --data "$(jq -n --arg t "$MSG" "$JQ_FILTER")"
```

**Lesson:** GitHub Actions YAML parser 的兩個 known quirk：
1. `if:` multi-line block scalar（`>-` / `|`）有時解析失敗 → 改用單行雙引號字串。
2. `run: |` 中 `[{key:"val",...}]` inline array of objects → 改用 shell 變數。
兩者都應優先測試；不要假設 block scalar 就能繞過 YAML 解析。

---

## 2026-05-06 — AdminEventTable per-row work dropdown：`<a>` → modal (4a266a1)

**Error:** Per-row work 下拉選單中「＋ 建立新作品」按鈕使用 `<a href="/admin/works/new">` 開新分頁，與 bulk action bar 的「＋ 新增作品」按鈕行為不一致（後者呼叫 `setShowCreateWorkModal(true)`）。

**Fix (commit `4a266a1`):** 改為 `<button onClick={() => setShowCreateWorkModal(true)}`，與 bulk action bar 保持一致。

**Lesson:** AdminEventTable 的 work 操作應一律透過 modal（`AdminCreateWorkModal`），不應從行內連結跳出至獨立頁面。一致性規則：相同操作的 UI 入口必須共用相同的實現路徑。

---



**Error:** ks_cinema `taiwan-filmake` 系列頁面的電影出現 2 筆 active 重複事件（`_2_sub1`, `_0_sub1`）。Annotator 看到兩個排片時段（`4/25～5/1`、`5/2～8`）→ 按 "multiple dates → sub_events" 規則生成 `_sub1`，因同 source 被 merger 跳過，永遠不被消除。

**Root cause:** scraper 首次執行時 `_get_parent_uuid` 查不到 parent（同批 upsert 未 commit）→ `parent_event_id=None`，繞過 grandchild 守衛。

**Fix (commit `a6cf029`):**
1. DB：停用 `_2_sub1`、`_0_sub1`（admin_manual）
2. SYSTEM_PROMPT Rule 1 加 EXCEPTION：電影時段窗口不建立 sub_events
3. 程式碼守衛：`_cinema_sources + source_id ends _{digit} + parent_event_id=None → sub_events = []`

**Lesson:** 電影放映時段 ≠ sub_events；`_sub1` 同 source 不被 merger 消除，必須靠守衛預防。

---
## 2026-05-06 — SC chars 被 enrich_person_names() GPT 重新引入

**Error:** `enrich_person_names()` GPT 輸出直接寫入 DB，未通過 `_to_trad()`，簡體字被重新寫入已修正的繁體欄位。

**Fix (commit `239cb19`):** `_SIMP_TO_TRAD` 提升為模組層級；`enrich_person_names()` 輸出包裹 `_to_trad()`。

**Lesson:** 任何寫入 name_zh/description_zh 的函式都必須過 `_to_trad()`，無論來源是 GPT 還是 DeepL。

---
## 2026-05-06 — auto_qa --fix SC 轉換後未鎖 field_corrections

**Error:** `fix_simplified()` 轉換 SC→TC 後未呼叫 `_lock_fields_via_corrections()`，下次 re-annotation 直接覆寫，SC 字元復活。

**Fix (commit `6e21c52`):** `fix_simplified()` 轉換後呼叫 `_lock_fields_via_corrections()`。

**Lesson:** 任何手動或批量修正翻譯欄位後必須立即鎖 `field_corrections`（見 Manual Translation Fix Persistence Guard）。

---
## 2026-05-08 — main.py import reorder silently dropped 4 scrapers (WalkerplusScraper, BigRomanticRecordsScraper, WasedaIclScraper, TsutayaPortalScraper)

**Error:** commit `694a363` (fix(annotator): extend year-anchor injection to all sources) rewrote the import block in `scraper/main.py` and accidentally dropped 4 scrapers from both the import section and the SCRAPERS list. The source files existed but daily CI never ran them.

**Detection:** Manual inspection during documentation review showed `grep -c "Scraper()" scraper/main.py` was lower than expected.

**Fix:** Re-added 4 import lines + 4 SCRAPERS list entries. Verified with `python main.py --dry-run --source <name>` for each.

**Lesson:**
- `main.py` import reordering is HIGH RISK. After any commit touching main.py, run: `git diff HEAD -- scraper/main.py | grep "^-.*Scraper()" | wc -l` — if > 0, confirm each removal is intentional.
- Feature/fix commits (annotator year-anchor, merger rules, etc.) should NOT touch the SCRAPERS list at all. Keep main.py changes separate from scraper-logic changes.
- This is the SECOND identical incident (`045d1fa` was the first in 2026-05-04). The pattern is now in SCRAPERS List Completeness Guard.

---

## 2026-05-07 — gnews RSS snippet used as start_date fallback when article_text is None

**Error:** `google_news_rss.py` called `_extract_start_date(article_text or description_plain, pub_date)`. When article fetch failed, `description_plain` (RSS snippet, ≤200 chars) was passed to the date extractor — too short to yield reliable dates. Result: incorrect `start_date` values on gnews events.

**Fix (commit 1c0f69a):** Changed to `_extract_start_date(article_text, pub_date) if article_text else None`. When article is unavailable, annotator's universal year-anchor handles the date.

**Lesson:** RSS snippet ≠ event data. Any date extraction that falls back to a snippet will produce noisy dates. Prefer `None` + annotator over a high-error fallback.

---

## 2026-05-07 — tokyoartbeat Contentful placeholder guard used day==1 instead of month==1

**Error:** The Contentful placeholder date guard in `tokyoartbeat.py` was `start_date.day == 1`, but Contentful uses the **entire January** (`YYYY-01-xx`) as a fiscal-year placeholder. Events `977da793` (2026-01-15) and `e7cf2a51` had placeholder dates that were NOT caught.

**Fix (commit 7df9f56):** Changed guard condition to `start_date.month == 1`. Applied direct DB correction for the 2 affected events.

**Lesson:** Platform placeholder conventions should be described broadly. When a vendor uses an entire month as a placeholder, the guard must cover the entire month, not just the 1st.

---

### 2026-05-05 — Batch Script Post-Enrichment Guard（程式碼層防護）

**設計問題**：每次寫 `_oneoff_*.py` 批次修復腳本，都從零用 urllib 直接打 REST API，完全繞過 annotator.py 已有的 enrichment pipeline。導致同類錯誤反覆出現：片名 GPT 直譯幻覺（超低預算 2026-05-05）、翻譯被 AI 覆寫（月老 2026-05-04）、人名音譯未修（desc_en 2026-05-05）。

**解法**：在 `annotator.py` 新增 `post_batch_enrich(event_ids)` 共用函式。所有 batch 腳本寫入 DB 後呼叫此函式，自動執行：(1) eiga.com 電影片名 lookup + field_corrections 鎖定；(2) 日後可擴充 person name enrichment。

**教訓**：
- **Guard 文件不夠，需要程式碼層強制**：同一類錯誤（繞過 enrichment pipeline）在 5 天內出現 3+ 次，每次都加 Guard 文件但下次仍被繞過。唯一有效防護是提供共用函式讓 batch 腳本一行呼叫。
- **「提供方便的正確路徑」優於「禁止錯誤路徑」**：與其禁止用 urllib 直接打 API（不可能），不如讓正確做法比錯誤做法更簡單（一行 import + 呼叫 vs 手動實作 enrichment）。

---
## 2026-05-05 — 首頁城市徽章修了兩輪才生效：EventCard.tsx 不是首頁使用的元件（commit `9f4b468`）

### 問題
第一輪修正 [`web/components/EventCard.tsx`](web/components/EventCard.tsx)（commit `5a29c13`），regex 理論上正確、TypeScript 無錯、Vercel 部署成功——但首頁仍看不到徽章。`curl https://tokyotaiwanradar.com/zh | grep -c '📍'` 只回 1（預期多筆），`grep -c 'border-gray-200 rounded-xl'`（EventCard root class）回 0。

### 根因
首頁 [`web/app/[locale]/page.tsx`](web/app/[locale]/page.tsx) 是 **inline list-style 渲染**，**沒 import EventCard**。grep `EventCard` in `page.tsx` = 0 match。`EventCard.tsx` 只服務 saved / category / search 頁面。首頁原來的 location 渲染是行 294-295：
```tsx
{event.location_name && (
  <p className="text-xs text-gray-400 mt-0.5">📍 {event.location_name}</p>
)}
```
完全沒有 `cityLabel` 邏輯。

### 修法
抽共用 helper 至 [`web/lib/cityLabel.ts`](web/lib/cityLabel.ts)：`getCityLabel(prefectures, address)` 內部依優先序走 prefectures 陣列 → `extractCity()` regex fallback。`EventCard.tsx` 與 `page.tsx` 同時 import，首頁第 294 行改為：
```tsx
{event.location_name && (() => {
  const cityLabel = getCityLabel(event.location_prefectures, event.location_address);
  return (
    <p className="text-xs text-gray-400 mt-0.5">
      📍 {cityLabel && <span className="...">{cityLabel}</span>}
      {event.location_name}
    </p>
  );
})()}
```

### 教訓
- **「原件以為被共用」是危險假設**：修任何事件卡片視覺前必在 `web/app/[locale]/` 與 `web/components/` 雙路徑 grep 使用者。`grep -rn '<EventCard\|EventCard ' web/app/ web/components/` 可快速列出實際 call site。
- **「修了一處忘了另一處」一旦發生必立刻抽 lib**：不要遵 inline 複製邏輯跨檔案；DRY 不是潔癖，是防迴歸。`web/lib/cityLabel.ts` 42 行取代了 EventCard.tsx 24 行 + page.tsx 1 行 × 來回迴歸二次的維護成本。
- **TypeScript 不能打不同路徑的架構 bug**：`page.tsx` 與 `EventCard.tsx` 各自類型正確，但「首頁使用的是哪個」這個事實 TS 無法驗證——需 grep 手動確認。
- **Vercel 部署驗證必用 `curl + grep`**：`grep -c` 計數 class 或 emoji，期望值明確。`grep -c '📍'` 與 `grep -c 'bg-gray-100 text-gray-600 px-1.5'`（新徽章識別類名）雙重交叉驗證。

---
## 2026-05-05 — annotator `_ai_or_existing()` 定義卻從未呼叫，P1 翻譯欄位被 GPT 重寫（commit `cf2d3f6`）

### 問題
`annotator.py` 主迴圈構造 `update_data` 時，對 `name_zh` / `name_en` / `description_zh` / `description_en` 四個翻譯欄位**直接寫入 GPT 輸出**，未經過 `_human_protected` 過濾。helper `_ai_or_existing()` 雖已定義但無任何 call site。`performer` 與 `localized_location_data` 有獨立保護路徑因此倖免。

### 觸發情境
event `f970e4e3`（月老）：source 頁面 5/8→5/9–5/13 日期變動 → `force_rescrape=true` 重新刮取 → annotator 重跑 → `name_zh='月老'`（field_corrections 已鎖）被 GPT 改回 `紅線 輪迴的秘密`。手動修了又被 AI 覆寫，迴歸鏈持續 1 週以上。

### 修法
在 `update_data` 構造完成後、送 Supabase PATCH 之前，新增 post-processing：對 `_human_protected` 中所有欄位以 DB 既有值（`event.get(fname)`）覆蓋 GPT 輸出。語意等同 `_ai_or_existing()`，但**無條件**且套用全部欄位。同時遞增 `field_protect_hits` counter，CI log 可觀察單次 run 的保護命中數。

### 教訓
- **「定義了的 helper 不等於被呼叫」**：refactor 時新增 helper 必 grep 確認所有應用位點都已切換；無 call site 的保護等於 0 保護。
- **保護機制必須是「default deny」**：`update_data[fname] = gpt_output` 是 default allow（除非顯式排除），改成 post-processing 強制覆蓋是 default deny（除非欄位不在 protected set）。
- **field_corrections 是最後一道防線**：人工鎖了欄位，annotator 也必須真的尊重——否則 architect 的 Manual Translation Fix Persistence Guard 形同虛設。
- **驗證 pattern**：任何修改 `update_data` 構造邏輯的 PR，必須驗證 `_human_protected` 中欄位在 PATCH payload 中等於 DB 既有值。

---
## 2026-05-05 — admin UI 修改分類未同步 `field_corrections`，下次 annotator 重跑覆寫（commit `1abbe38`）

### 問題
後台三條人工修正路徑（`AdminEventTable` inline + bulk、`AdminEditClient` edit form、`confirm-report` 報告確認）修改 `events.category` 時，只 UPDATE `events` 表，未 upsert `field_corrections`。下次 `annotation_status='pending'` 時，annotator 用 GPT 重新分類覆寫人工值，與翻譯欄位的「修了又錯」迴歸鏈同因。

### 修法
三條路徑統一補上 `field_corrections` upsert（`onConflict: event_id,field_name`）。
- `AdminEventTable.tsx`：inline 與 bulk 兩個 call-site
- `AdminEditClient.tsx`：edit form save 時若 category 變動
- `web/app/actions/confirm-report.ts`：confirm 時 category 修正

### 教訓
- **`field_corrections` 不只翻譯欄位**：`category` / `event_form` 等結構欄位也走 annotator GPT 路徑，凡是「人工修了 + annotator 會再覆寫」的欄位都必須鎖。
- **新增 admin mutation 路徑必查清單**：任何寫入 `events` 表的 server action / client mutation，自查欄位是否屬於 `_human_protected`；若是，必須同 transaction upsert `field_corrections`。
- 已對應 architect 的 Manual Translation Fix Persistence Guard 擴張範圍至非翻譯欄位。

---
## 2026-05-05 — Partial-payload upsert violates NOT NULL constraints

### 問題
實作 movie-extend 第二輪 update 用 `client.table("events").upsert(extend_rows, on_conflict="source_name,source_id")`，PostgREST 報 `null value in column "source_url" of relation "events" violates not-null constraint`。錯誤行 ID 是新生成的 UUID（不是現存 row 的 ID），代表 supabase-py 先嘗試 INSERT 才 fall back 到 UPDATE，但 NOT NULL 驗證在 row construction 階段就跳出。

### 修法
對保證已存在的 row 做 partial 寫入，改用 `.update(row).eq("source_name", sn).eq("source_id", sid)`，把 conflict key 從 payload pop 出來。

### 教訓
`on_conflict` upsert 是給「完整 row」的 partial 寫入會打到 NOT NULL（無 default 的欄位如 `source_url`）。只要 row 已透過 `existing_keys` 確認存在，一律改用純 `.update().eq()`，永遠不要用 partial upsert。

---
## 2026-05-05 — Works entity ship (migration 048)

### 問題
同一部台灣電影（月老、大濛）在多家戲院各自發行 events，使用者看不出是同一作品；merger Pass 1 名稱相似度 ≥ 0.85 又會錯誤合併不同戲院的場次（會丟失另一場資訊）。同類問題會擴散到舞台劇、巡演、特展等「跨場次同一作品」型內容。

### 根因（5 個）
1. **缺少作品層級實體**：events 是「單一場次」的呈現，但「作品」是更穩定的事物 — 沒有獨立 entity 就無法做 cross-screening 連結。
2. **merger Pass 1 對電影同名跨 venue 過度合併**：之前 `_location_overlap()` 有 prefix/suffix-extension 容忍度，月老 (新文芸坐 ↔ シネマート新宿) 仍可能撞上 sim=1.0 觸發誤合併。
3. **`parent_event_id` 被誤用為作品連結**：sub-event 結構是「同一活動拆 schedule」，把跨戲院場次塞進 parent/sub 會破壞 sub-event 過濾與展示邏輯。
4. **詳情頁 anon-key RLS 副作用**：cross-link sibling 查詢若用 anon client，會 silently 漏掉 `is_active=false` 的 sibling，admin 看不到完整列表。
5. **AdminEventTable 缺乏 work 缺漏訊號**：電影類 event 沒指派 `work_id` 不會被任何檢查工具標出，導致缺漏永遠累積。

### 修復
- **migration `048_works_entity.sql`**：新增 `works` 表（work_type CHECK、original_title UNIQUE、title_ja/zh/en、director、cast_summary、release_year、country、description、poster_url、external_links）+ `events.work_id` FK + RLS + updated_at trigger。
- **types.ts**：新增 `Work` interface、`WorkType` union、`getWorkTitle()` helper、`Event.work_id` 欄位。
- **詳情頁** `web/app/[locale]/events/[id]/page.tsx`：以 service role client 查同 `work_id` 其他 active events，渲染「同作品其他場次」block；i18n key `event.relatedScreenings.title` 三語齊備。
- **admin works CRUD** `web/app/[locale]/admin/works/{page,[id]/page,new/page}.tsx` + `web/app/actions/works.ts`：list / new / edit + `assignWorkToEvent` server action。AdminTabNav 新增 Works tab。
- **AdminEventTable Phase 5**：新增 `work` 欄、inline assign-work dropdown（搜尋 + 連到 `/admin/works/new`）、movie/performing_arts 缺 `work_id` 整列 `bg-red-50` 警示 + tooltip。
- **i18n** 三語：`admin.events.columns.work`、`admin.events.assignWork.{placeholder,unassigned,createNew}`、`admin.events.warnings.missingWorkForFilm`。
- **merger.py Pass 1 skip**：(a) 雙方 `work_id` 非空且不同 → skip；(b) movie/performing_arts + `_location_overlap()=False` → skip。輸出 `[Pass 1 SKIP]` log。
- **backfill** `scraper/_oneoff_backfill_works.py`：upsert 月老／大濛 + assign 4 events。支援 `--dry-run`。
- **docs**：architect 加 `Works Entity vs parent_event_id Guard`；engineer SKILL 加 `Works Entity Conventions`；MERGER_WORKFLOW 加 Pass 1 work_id skip 段落。

### 教訓
- **作品（Work）≠ 場次（Event）**：跨場次穩定實體必須單獨建表，不能塞進 `parent_event_id`。兩者並存且職責正交。
- **`on_conflict` 依賴需 UNIQUE constraint**：PostgREST 的 `upsert(on_conflict='...')` 只在該欄位有 unique index 時可靠運作。Backfill 改用先 SELECT 再決定 INSERT/UPDATE 的模式，更明確且不依賴 PostgREST 邊角行為。
- **service role 是 admin cross-link 的必要條件**：任何展示 `is_active=false` 的 sibling 場次都必須繞過 RLS。
- **i18n 巢狀 namespace 要透過 `useTranslations("admin")` + `t("events.columns.work")` 路徑訪問**；不要拆成多個 hook，效能與一致性都差。
- **merger 加 skip 比加 candidates table 便宜**：Phase E 還沒到位前，先 log skip 已能解 80% 即時痛點。

### 影響檔案（本回合）
- `supabase/migrations/048_works_entity.sql`（新增 unique index 補丁）
- `web/components/AdminEventTable.tsx`（Phase 5：work 欄、assign UI、紅列警示）
- `web/messages/{zh,en,ja}.json`（admin.events 巢狀 namespace）
- `scraper/merger.py`（Pass 1 work_id + venue skip）
- `scraper/_oneoff_backfill_works.py`（新建）
- `.github/agents/architect.agent.md`（Works Entity Guard）
- `.github/skills/agents/engineer/SKILL.md`（Works Entity Conventions）
- `docs/MERGER_WORKFLOW.md`（Pass 1 work_id skip 段落）

---
## 2026-05-05 — Merger 合併失效根因 + Pass 2 location 過嚴 + 缺停用稽核

### 問題
「台湾祭in群馬太田2026」事件在四個來源（taiwan_matsuri / iwafu / prtimes / walkerplus / gnews）持續以多筆獨立事件存在，merger 無法自動合併。手動合併後一週內又出現新重複。

### 根因（多個）
1. **dash 字元差異**：iwafu 用 `－`（U+FF0D），walkerplus 用 `ー`（U+30FC）。`_normalize()` regex 不包含 `ー`，sim 0.581 < 0.85。已於 commit `2d9685e` 修復。
2. **Wrapping quote**：prtimes 用 `「…」` 包住標題，sim 0.545。同 commit 修復。
3. **`_location_overlap` 過嚴**：gnews `群馬県太田市` 與 iwafu `イオンモール太田` token 集無交集（`{群馬県,太田市}` ∩ `{イオンモール,太田}` = ∅），Pass 2 不啟動。
4. **walkerplus 不算 news**：merger Pass 2 只處理 `_NEWS_SOURCES`，walkerplus 不在其中，但其資訊密度低於官方主辦方。
5. **缺停用稽核**：events 表沒有 `deactivated_at`/`deactivated_reason` 欄位，無法事後分析「為何此活動被合併」。

### 修復
- Phase A：`_location_overlap` 加入 ≥4 字子字串包含判定
- Phase B：`walkerplus` 加入 `_NEWS_SOURCES`（並補入 `SOURCE_PRIORITY` 為 14）
- Phase C：migration 044 新增三個稽核欄位（`deactivated_at`/`deactivated_reason`/`deactivated_by_pass`）+ merger 各 Pass 同步寫入 + 所有 admin manual deactivate 入口（`IsActiveToggle`、`AdminEventTable` bulk/single、`confirm-report.ts` 三條 is_active=false 分支）

### 教訓
- Location 字串多樣性遠超 token-based overlap 能處理。範例：`イオン太田` / `イオンモール太田` / `群馬県太田市` 是同一地點不同表達。
- 聚合站（walkerplus / arukikata 等）資料品質參差，應視為 news 而非 official。
- 沒有稽核欄位的「合併失敗」極難 debug — 必須事後從 git log 還原。
- Admin manual deactivate 有多個入口（toggle、bulk、confirm-report 三條 is_active=false 分支），新增稽核欄位時必須掃過所有 setter。

---
## 2026-05-05 — auto_research batch query 遺漏 `pending` 狀態，候選來源永遠跳過（commit `5d2585d`）

### 問題
Migration 033 將 `research_sources.auto_research_status` 的 DEFAULT 設為 `'pending'`（而非 NULL）。但 `auto_research.py` 的 batch query 只過濾 `NULL` 或 `'error'`，導致所有新候選來源在 migration 033 之後永遠被 batch 跳過（靜默失效，無錯誤訊息）。

```python
# 舊（有 bug）
.or_("auto_research_status.is.null,auto_research_status.eq.error")

# 修復後
.or_("auto_research_status.is.null,auto_research_status.eq.pending,auto_research_status.eq.error")
```

手動重置 14 筆既有 `pending` 候選為 NULL，讓當晚 cron 立即處理。

### 教訓
- **新增 DB 欄位時，若設定 DEFAULT 值，必須同時更新所有 batch query 的過濾條件**。DEFAULT `'pending'` 與 DEFAULT `NULL` 對 query 的影響截然不同。
- 靜默跳過的 bug（候選出現在 DB 但永遠不被處理）沒有 ERROR log，只能從處理計數為 0 的 CI 輸出發現。
- 每次新 migration 加了 DEFAULT 值的欄位，應立即搜尋所有 `.or_("... .is.null ...")` 的 query，確認是否需要加新 DEFAULT 值的條件。

---
## 2026-05-05 — merger.py 年份後綴造成年度例行活動無法自動合併

### 問題
`merger.py` Pass 1 的 `_normalize()` 函式未剝除年份後綴（`2026`、`2025春` 等）。每年在標題後加上年份的例行活動（如「台湾文化祭2026」vs「台湾文化祭」）相似度只有 0.714，低於 0.85 門檻，導致自動合併失效。

具體案例：
- `14dbef1a`（iwafu「台湾文化祭2026」）與 `ed313f24`（taiwanbunkasai「台湾文化祭」）— 同一活動，不同來源，merger 未合併
- 手動合併後才發現 _normalize 的系統性缺失

### 修復（`scraper/merger.py`）
在 `_normalize()` 尾端加入年份剝除：
```python
# Strip year suffix (e.g. "台湾祭2026", "台湾文化祭2025春")
name = re.sub(r"20\d{2}[春夏秋冬]?\s*$", "", name)
```

驗證：
- `台湾文化祭2026` vs `台湾文化祭` → 1.000 ✓
- `台湾文化祭2026春` vs `台湾文化祭` → 1.000 ✓
- `台湾フェスティバル™TOKYO2026` vs `台湾文化祭2026` → 0.200 ✗（正確，不誤合併）

### 教訓
- 例行活動（年度祭典）的標題通常會在年底加年份後綴，但來源不一致（官方來源常只寫活動名，其他來源加上年份）。`_normalize()` 必須消除年份差異，否則每年都需要手動修復。
- 每次新增 `_normalize()` 規則後，需跑全測試組確認無誤合併（特別是名稱相近但不同活動的案例，如「台湾フェスティバル」vs「台湾文化祭」）。

---
## 2026-05-05 — 霧のごとく（大濛）電影片名 description 未同步（DB patch）

### 問題
7 筆事件的 `description_zh` / `description_en` 中出現錯誤電影片名翻譯：「霧的如同」「霧的如夢」「霧的故事」（zh）、"Like Mist"（en），正確為「大濛」/ "A Foggy Tale"。涉及 cinemart_shinjuku、peatix、taioan_dokyokai、uplink_cinema、google_news_rss 五個來源。

### 根因
`enrich_movie_titles()` 只修正 `name_zh` / `name_en`，不修正 `description_zh` / `description_en`。GPT 翻譯 description 時用了直譯片名，與 name 欄位不一致。

### 修復
DB patch script 對 7 筆事件逐一替換 description 中的錯誤片名變體，並修正替換後產生的「大濛（大濛）」重複括號。

### 教訓
- `enrich_movie_titles()` 只修正 name 欄位，description 中的片名需另外 patch——已記錄為 engineer.agent.md Rule 11（`enrich_movie_titles() description sync rule`）
- 直譯變體可能有多種形式（`霧的如同`、`霧的如夢`、`霧的故事`），patch 時需全部列舉

---
## 2026-05-05 — LINE 週報都市前綴 + Python-level 去重（commits `5acb6a1`、`4a6fd5a`）

### 問題
LINE 週報只顯示活動名，讀者無法一眼判斷是東京還是關西活動。此外同一活動若有多個來源（如 peatix + connpass），會重複出現在推送中。

### 修復（`scraper/weekly_line_broadcast.py`）
- **都市前綴**：所有事件加 `[都市名]` prefix（如 `[大阪]`、`[京都]`）。初版排除東京（因為大部分事件在東京），但 commit `5acb6a1` 改為也顯示 `[東京]`，保持一致性。
- **Python-level 去重**：以 `name_ja` 為 key，同名活動只保留一筆。

### 教訓
- 都市前綴可做可不做的「差異」反而使讀者更困惑（「沒標籤=東京」不直觀），不如全部統一加上
- GPT 選出的活動可能跨多個 source_name，Python-level 去重比在 SQL 做更容易控制

---
## 2026-05-05 — auto_qa 重複建立 confirmed/dismissed 報告（commit `75d3c1e`）

### 問題
`auto_qa.py` 每次執行都重新產生 `auto_*` 類型報告，即使 admin 已確認（confirmed）或駁回（dismissed）同一筆報告。Admin 的處理工作被 auto_qa 覆蓋。

### 根因
Insert 前的去重查詢只檢查 `status='pending'`，未排除 `confirmed` 和 `dismissed` 狀態。

### 修復
去重查詢改為：同 `event_id` + 同 `auto_*` report type 且 status 為 `pending` / `confirmed` / `dismissed` 任一者皆 skip。

### 教訓
- **auto_qa 去重必須檢查 ALL statuses**（pending + confirmed + dismissed），不只 pending
- Admin 的 confirm/dismiss 是最終決定，自動化不得覆蓋

---
## 2026-05-05 — Sub-event annotation 缺失（commit `38f4f3a`）

### 問題
Scraper 直接產生的 sub-events（非 GPT 產生）有 `annotation_status='pending'`，但 annotator 只處理 parent event 的 GPT-generated sub-events。導致 scraper-created sub-events 缺少 category、description 等欄位。

### 修復
`annotator.py` 修改為也 pick up scraper-created sub-events（有 `parent_event_id` 且 `annotation_status='pending'`），從 parent event 繼承 category 和 context。

### 教訓
- Annotator 必須處理所有 pending 事件，不只 parent events 的 sub-events
- Sub-event annotation 應從 parent 繼承 category 和其他 context fields

---
## 2026-05-05 — enrich_location GPT 回傳 venue name 作為 address（commit `628e3e7`）

### 問題
`enrich_location.py` 呼叫 GPT 填補 `location_address` 時，GPT 有時回傳 venue name（如 `ユーロスペース`）而非街道地址，造成 `location_address == location_name`。

### 修復
新增 guard：如果 GPT 回傳的 address 等於 `location_name`，skip 更新。同時新增 sub-venue 規則處理。

### 教訓
- GPT 回傳的 location 資料需驗證 `address ≠ venue_name`，不能盲目寫入
- 此 guard 應同時存在於 scraper 端和 enrichment 端——雙層防護

---
## 2026-05-05 — location_address = location_name 全 scraper 稽核（commit `9d6e0fc`）

### 問題
多個 scrapers（iwafu、jposa_ja、kokuchpro、koryu、prtimes、taioan_dokyokai、taiwan_festa、waseda_taiwan）將 `location_address` 設為與 `location_name` 相同的值。`location_address` 應該是街道地址，不是場地名稱。

### 修復
稽核所有 scraper，逐一修正：有實際地址可解析時分開設值；無實際地址時設 `location_address = None`。

### 教訓
- **`location_address` 必須永遠不等於 `location_name`**——這是全 scraper 通用規則
- 當 scraper 只有一個 combined "location" 欄位時，正確做法：venue name → `location_name`，street address → `location_address`；找不到 street address 則設 `None`
- `_ai_or_existing()` 保護邏輯在 DB 欄位非 null 時保留既有值，所以 scraper 端寫入錯誤值後 annotator 也無法修正

---
## 2026-05-05 — proxy.ts /r/* 短網址被 i18n middleware 攔截（commit `3cfe438`）

### 問題
短重導路由 `/r/*` 被 i18n middleware 攔截並 307-redirect 到 `/zh/r/*`，造成 404。

### 修復
在 `proxy.ts` matcher 排除 regex 中新增 `/r/` 路徑。

### 教訓
- proxy.ts matcher 排除不只適用於 `public/` 靜態文件——任何**非 locale 路由**（API routes、短網址、redirect routes）都必須排除
- 新增 rule 的適用範圍從「static file exclusion」擴展為「non-locale route exclusion」

---
## 2026-05-05 — LINE 週報時間窗口擴大（commit `9b33ad3`）

### 問題
LINE 週報每週只推「未來 7 天」活動，月刊最遠僅到 35 天，讀者回饋活動太少、錯過較遠期熱門活動。

### 修復（`scraper/weekly_line_broadcast.py`）
| 參數 | 修改前 | 修改後 |
|------|--------|--------|
| `_fetch_upcoming_events` pool 範圍 | 35 天 | 60 天 |
| `_ai_select_events` week_end | 7 天 | 21 天 |
| `_ai_select_events` week2_end | 14 天 | 28 天 |
| `_ai_select_events` month_end | 35 天 | 60 天 |
| WEEKLY SELECTION 標籤 | next 7 days | next 21 days |
| MONTHLY SELECTION 標籤 | 8–35 days | 22–60 days |
| 備援觸發條件 | 14 天 | 28 天 |

### 教訓
- 廣播時間窗口直接影響 GPT 的分類邏輯（week/month 分界），修改時需同步調整 AI prompt 內的窗口標籤與數字，否則 prompt 與程式邏輯不一致

---
## 2026-05-05 — LINE 週報顯示日文 fallback（annotation_status 過濾缺失，commit `b2864ea`）

### 問題
LINE 週報中出現日文標題（如「赤い糸 輪廻のひみつ」）而非中文，ZH 訂閱者收到 `name_zh = NULL` 的事件。

### 根因
`_fetch_upcoming_events` 未過濾 `annotation_status='pending'`。新爬取事件在 annotator 執行前 `name_zh`/`name_en` 為 NULL，若廣播在 09:00 pipeline **之前**手動觸發，pending 事件會進入 pool。

### 修復
在 `_fetch_upcoming_events` 加入 `.in_("annotation_status", ["annotated", "reviewed"])` 過濾。效果：pool 76 → 74（2 筆 pending 正確排除）。

### 教訓
- **任何廣播 query 必須加 `annotation_status` 過濾**，不能假設所有 `is_active` 事件都已標注
- 手動觸發廣播時，應先確認 pool 筆數是否比無過濾少（少 = 過濾正常運作）

---
## 2026-05-04（Session 2）— Web UI 多項修復 + selection_reason["ja"] 品質 + is_active 誤設還原（commits `a895e07`、`1b344f7`、`2989940`、`d9ff85f`、`d7ab41a`、`7a81969`、`0abd8db`、`dedfa81`、`b559520`）

### NextIntlClientProvider 缺少 `locale` prop（commit `dedfa81`）
- **問題**：`layout.tsx` 的 `<NextIntlClientProvider>` 未傳入 `locale` prop，日語（`/ja/`）與英語（`/en/`）頁面的所有 Client Component UI 文字顯示中文（預設 locale）
- **根本原因**：`locale` 是 `NextIntlClientProvider` 的必要 prop，缺少時 next-intl 靜默回退到預設語言，無任何 console error
- **修復**：加入 `locale={locale}` prop（`locale` 從 `params` 解構）
- **教訓**：`NextIntlClientProvider` 的 `locale` prop 是必填的——缺少時錯誤靜默，多語言 UI 全部顯示預設語言，極難追蹤

### FilterBar「電視頻道」選項永遠顯示 0 筆（commit `2989940`）
- **問題**：FilterBar 的「電視頻道」location type 選項永遠顯示 0 筆事件，從未有任何事件被過濾到
- **根本原因**：`location_name` 欄位從未包含「電視頻道」字串；此 filter 邏輯存在但資料模型不支援
- **修復**：完全移除該 filter 選項（`FilterBar.tsx` + `page.tsx`）
- **教訓**：Filter 選項必須有對應的資料模型支撐；無效 filter 選項比沒有 filter 更差（給使用者錯誤的期待）

### 事件詳情頁 section 順序重排（commits `d9ff85f`、`d7ab41a`、`7a81969`）
- **調整**：重排為 title+save → summary table → description → CTA（購票/外部連結）→ AI selection reason → sub-events → record links → FAQ
- **問題**：CTA 按鈕之前被放在 summary table 之前，description 之後才是 AI reason，順序不符合使用者閱讀流程
- **教訓**：事件詳情頁的 UX 順序：重要資訊（摘要表）→ 正文（description）→ 行動（CTA）→ 輔助資訊（AI 原因）→ 相關項目

### ReportSection 新增 `brokenLink` 回報類型（commit `0abd8db`）
- **修復**：`ReportSection.tsx` 新增 `brokenLink` 作為第三個回報類型，讓使用者可回報失效連結

### wrongSelectionReason 三語言 textarea（commit `dedfa81`）
- **問題**：`ReportSection.tsx` 只有單一 textarea，無法指定要修正哪個語言的 selection reason
- **修復**：拆成三個 textarea（中文 / English / 日本語）；新增 `selectionReasonAll` prop；submit 格式 `selectionReason:zh:text`（含語言前綴）
- **教訓**：多語言欄位的回報 UI 需要對應的語言選擇機制，單一 textarea 會造成語言混淆

### AdminReportsTable 解析格式改 `indexOf`（commit `b559520`）
- **問題**：用正則 `/^(zh|en|ja):([\s\S]*)$/` 解析 `selectionReason:zh:text` 格式（含 `selectionReason:` 前綴），regex 無法匹配正確捕捉
- **修復**：改用 `indexOf(":")` 多次切割：先找 `selectionReason:` 前綴，再切語言碼，再取文字
- **教訓**：解析多層冒號分隔格式，`indexOf` + `slice` 比 regex 更穩定可靠；regex `^` 錨點在含多層前綴時容易失敗

### confirm-report.ts TS2352 型別轉換（commit `b559520`）
- **問題**：`origRow as Record<string, unknown>` 直接型別斷言失敗，TypeScript 2352 error
- **修復**：改為 `origRow as unknown as Record<string, unknown>`；`filter(Boolean)` 加型別謂詞 `(x): x is string => Boolean(x)`

### selection_reason["ja"] 中文污染（49 筆，DB patch）
- **問題**：`annotator.py --backfill-tier1` 對 49 筆事件的 `selection_reason["ja"]` 欄位產生中文內容（而非日文），事件詳情頁日語 textarea 預填中文
- **根本原因**：GPT prompt 語言控制不夠嚴格，中文意外生成到 ja 欄位（可能 GPT 混淆輸出語言）
- **修復**：Python 腳本用假名正則偵測（無假名字元 → 疑似非日文），逐一呼叫 GPT-4o-mini 從 zh 欄翻譯成日文，覆寫 `selection_reason["ja"]`
- **教訓**：
  1. backfill 完成後**必須立即執行品質抽查**：`selection_reason["ja"]` 必須包含假名；無假名表示語言污染
  2. annotator backfill 完成後需執行 QA script 驗證多語言欄位

### is_active 批次誤設（342 筆還原）
- **問題**：一次性腳本意外將所有 `end_date < today` 的事件設為 `is_active=False`，342 筆受影響；已結束事件不可見
- **修復**：全部還原為 `is_active=True`
- **教訓**：`is_active=False` 只能由：(1) Admin 手動停用特定事件，(2) `merger.py` 去重時停用次要事件；**任何批次 UPDATE `is_active` 前必須確認符合這兩個來源之一**

---
## 2026-05-04 — main.py pipeline 補齊 enrich 步驟 + ks_cinema DB 修正 + 035 migration

### main.py pipeline enhancement — enrich steps 補齊

**問題：** 手動執行 `python main.py --source ks_cinema` 時，事件被 scrape + annotate 但 **未** enrich——電影片名得到直譯（`めぐる面影、今、祖父に会う` → `循環的面影`）而非官方片名（`車頂上的玄天上帝`）。`enrich_movie_titles()` 和 `enrich_person_names()` 只在 CI workflow 中以獨立 `annotator.py --enrich-movie-titles` / `--enrich-person-names` 指令執行，`main.py` 完全沒呼叫。

**修復：** `main.py` 新增 `from annotator import enrich_movie_titles, enrich_person_names`，在 `annotate_pending_events()` 之後、IndexNow 提交之前呼叫兩者。enrich 函數為 idempotent，CI 的獨立 enrich 步驟變成 no-op 二次 pass，不影響 CI。

**教訓：**
1. **Pipeline parity rule**：任何新增到 CI workflow（`scraper.yml`）的 post-processing 步驟，必須同步加入 `main.py` 的正常（非 dry-run）流程。否則手動 scraper 執行會產生品質不完整的結果。
2. 目前 `main.py` 完整 pipeline 順序：scrape → merger → annotate → enrich_movie_titles → enrich_person_names → IndexNow。
3. Idempotent enrichment 在 main.py 和 CI 雙重執行是安全的——只多幾個 DB query，不會產生重複寫入。

### ks_cinema 電影片名 DB 手動修正

**問題：** 6 筆 ks_cinema 事件的 `name_zh` / `name_en` 是直譯（GPT 音譯）而非官方片名。原因：事件在 `main.py` 補齊 enrich 步驟之前被手動 scrape。

**修正的事件：**
- `めぐる面影、今、祖父に会う` → 車頂上的玄天上帝 / Be with Me
- `台湾ハリウッド` → 阿嬤的夢中情人 / Forever Love
- `超低予算ムービー大作戦` → 導演你有病 / Out of Nowhere

**教訓：** 補齊 pipeline 後，對之前手動 scrape 的事件需一次性 DB patch。可用 `enrich_movie_titles()` 自動修正，或手動 UPDATE。

### ks_cinema sub-event hierarchy 修正

**操作：** 手動 DB 修正——3 筆 sub-event 設正確 `parent_event_id`；2 筆舊版 scraper 產生的 `_sub1` 記錄 deactivate（`is_active=False`）。

### 035_organizer_form_language.sql migration（Tier 1）

**狀態：** 已 apply 到 production DB，migration SQL 已 commit。新增欄位：`organizer`、`co_organizers`、`sponsors`、`organizer_type`、`event_form`、`primary_language`、`has_japanese_support`、`has_english_support`。含 CHECK constraints 和 GIN indexes。

### P0: Admin 修正保護 — re-annotation 時保留既有非 null 值（commit `9eab3aa`）

**問題：** Admin 透過 confirm-report 修正欄位（例：修正 name_zh）時，`annotation_status` 重設為 `pending`。下次 annotator 執行時，GPT 重新產生所有欄位，覆寫 admin 的修正值。

**修復：** `annotator.py` 新增 `_ai_or_existing()` 函數——在一般 re-annotation 模式（非 `--all`/`--id`）中，既有非 null DB 值優先保留，GPT 輸出只填補 null 欄位。同步修復 `irrelevant` status bug（`--fix-reviewed` 誤處理 irrelevant 事件）。

**教訓：** 當 admin correction UI 會重設 `annotation_status` 觸發重新處理時，必須保護已修正欄位不被 AI 覆寫。

### P1: field_corrections 明確持久化 — admin 修正永不被 AI 覆寫（commit `c393e93`）

**問題：** P0 的隱性保護（保留非 null 值）不足——有時 admin 需要覆蓋一個已有 AI 值的欄位，且該覆寫必須在無限次 re-annotation 中持久。

**修復：**
- 新建 `field_corrections` 表（migration 038b）：記錄每次 admin 修正 `(event_id, field_name, original_value, corrected_value, corrected_by)`
- Annotator 啟動時載入 `human_field_map`：event_id → 受保護欄位 set
- `_ai_or_existing()` 優先檢查 `_human_protected`——此 set 中的欄位 AI **永不覆寫**，即使 `--all` 模式
- `confirm-report.ts` 同步寫入 events 表和 field_corrections 表
- Annotator SYSTEM_PROMPT 新增 few-shot context：將過去修正紀錄注入 prompt，讓 GPT 學習正確模式

**Schema：** `field_corrections(id, event_id, field_name, original_value, corrected_value, corrected_by, created_at)`，`(event_id, field_name)` UNIQUE

**教訓：** Admin correction 保護需兩層：P0（隱性：保留非 null）+ P1（明確：field_corrections 表永久保護）。只有 P0 時，`--all` 模式或 null→非 null→不同值 的修正會遺失。

### Tier 1.5 Schema: organizer_url, price, event_status（commit `0d4a0de`）

**Migration 037：** 新增 `organizer_url text`、`price_amount numeric`、`price_currency text DEFAULT 'JPY'`、`event_status text DEFAULT 'scheduled'`，含 CHECK constraints。

**Annotator：** SYSTEM_PROMPT 新增 price parsing、organizer URL、event status 規則。新增 validators：`_validate_organizer_url`、`_validate_price_amount`、`_validate_price_currency`、`_validate_event_status`。

### Performer 欄位（commit `edd101e`）

**Migration 038：** `events` 新增 `performer text` 欄位。`base.py` + `types.ts` 同步新增 `performer`。

**Annotator SYSTEM_PROMPT：** 新增 PERFORMER EXTRACTION RULES——bare personal name，去除敬稱，非人物事件回傳 null。

**Detail page：** Rich Results JSON-LD 注入 `performer` property（Schema.org Event compliance），修復 4 個 Rich Results warnings。

### next-intl organizerType + eventForm namespace 缺失（commit `e6461c7` context）

**問題：** Detail page 使用 `getTranslations("organizerType")` 和 `getTranslations("eventForm")`，但三語言 JSON 中無對應 namespace/keys。next-intl 靜默渲染 raw key string（例：`organizerType.commercial_brand`），無任何錯誤。

**修復：** 在三語言 JSON 中新增 `organizerType`（9 keys）和 `eventForm`（12 keys）namespace，以及 6 個 event namespace keys。

**教訓：** next-intl missing keys 靜默失敗。新增 `getTranslations()` namespace 時，必須確認 ALL 3 message files 有對應 entries。驗證：`grep -n "key" web/messages/zh.json`。

### Admin Dashboard 增強（commits `6f97d82`→`eec0d90`）

- 新增 sources 和 creators stat cards（commit `6f97d82`）
- Source type map modal 新增 category filter checkboxes（commit `ec1ce39`）
- NGO category + 5 筆 source reclassification（commit `7373fd3`）
- Category pills on source list（commit `eec0d90`）
- Source type label refinements：百貨・商圈、台灣商家（commits `c3774a3`、`0d4a0de`）
- organizer_type / event_form filters（AdminEventTable，commit `ee1831b`）
- Tier 1 欄位視覺化：organizer, event_form, language support（commit `1fdb332`）

### wrongSelectionReason 3-locale textareas + NextIntlClientProvider locale fix（commit `dedfa81`）

**問題：** `NextIntlClientProvider` 使用錯誤的 locale prop；wrongSelectionReason report 只有單一 textarea。

**修復：** 修正 locale prop；wrongSelectionReason 擴展為 zh/en/ja 三個 textareas，讓 admin 分別修正各語言的 selection_reason。

### brokenLink report type（commit `0abd8db`）

新增 `brokenLink` 到 event report section，使用者可回報壞掉的 source/official links。

### Price regex 擴展（commit `e6461c7`）

`backfill_price_from_price_info()` regex 擴展以匹配 `¥1,500` 格式（原本只匹配 `1500円`）。Pattern：`r'[¥￥]?\s*([\d,]+)\s*円?'`。

---
## 2026-05-02 — 父事件 RLS 隱藏 + Quality page 缺地址誤報 + Admin UI 改善

### 父事件 RLS cross-status 問題（commit `f5931e0`）

**問題：** 子事件詳情頁「返回主事件」連結查詢父事件時，若父事件 `is_active = false`（已下架），anon-key client 因 RLS `Public read events` policy 靜默返回 null——不報錯、不 throw，連結直接消失。

**修復：** 父事件 lookup 改用 service role key（`SUPABASE_SERVICE_ROLE_KEY`），只 select `id, name_ja, name_zh, name_en`，不暴露其他欄位。

**教訓：**
1. Supabase anon-key + RLS 查詢關聯記錄（parent, linked entity）時，若目標記錄可能 `is_active = false`，必須用 service role key
2. Service role key 只用於 Server Component / route handler，**永不傳入 Client Component**
3. 只 select 必要欄位——不使用 `select("*")`

### Quality page 缺地址誤報排除（commits `229810f`、`f5931e0`）

**問題：** 缺地址 check 重新定義為「有場地名但無地址」（`location_name IS NOT NULL AND location_address IS NULL`），但仍有大量非 actionable 項目：
- `location_name` 含 `〒`（地址已嵌入名稱中）
- `location_name` 含 `オンライン`（線上活動，無實體場地）
- 短地名 ≤6 字元且無空格（如「東京」「香港」「岡山」，無更精確地址可填）

**修復：** DB 層加 `.not("location_name", "like", "%〒%")` 和 `.not("location_name", "ilike", "%オンライン%")`；client 層過濾短地名。

### Admin UI 改善（commits `1f48807`、`15d6ab3`→`bf22756`、`bc6d1e7`、`636a52f`）

- **批次新增分類**（`1f48807`）：AdminEventTable 新增 bulk add category 列——multi-select category picker → "Apply to N events" → 寫入 `category_corrections` + 選取自動重設
- **Sticky 合併容器**（`15d6ab3`→`bf22756`）：filter bar 和 bulk action bar 包在同一個 `sticky top-14 z-20` wrapper，避免兩列分別固定導致跳動
- **來源搜尋框**（`bc6d1e7`）：AdminSourcesTable 新增 keyword 搜尋，搜尋 name / URL / scraper_source_name（case-insensitive）
- **tea_alcohol 分類**（`636a52f`）：新增 `tea_alcohol` 到 `Category` union + `CATEGORY_GROUPS` group_arts（五感）

**教訓：**
1. Bulk action bar 和 filter bar 必須在同一個 sticky container——分開固定會導致 scroll 時跳動
2. Bulk add category 使用 `Set` merge（`new Set([...prev, ...catsToAdd])`）避免重複，並寫入 `category_corrections` 讓 AI 學習

---
## 2026-05-02 — 子事件 name_ja 片假名被 GPT 覆寫為漢字

**問題：** TIFF 子事件 re-annotation 時，GPT 把 `チャン・ツィイー` → `章子怡`、`ジャ・ジャンクー` → `賈樟柯`，破壞日文模式的片假名人名顯示。原因：子事件 upsert 直接取 `sub.get("name_ja")`，無任何保留機制。

**修復：**
1. DB patch：3 個 TIFF 子事件 `name_ja` 還原為 `raw_title`（片假名版本）
2. annotator.py：子事件 upsert 前查詢既有 sub-events，若 `name_ja`/`raw_title` 已存在則保留（跟父事件同樣的 preservation policy）

**教訓：**
1. 子事件的 `name_ja` / `raw_title` 也必須有 preservation 機制——GPT 不可靠地保留片假名
2. 首次 annotation 的 GPT output 通常較好（遵守 SYSTEM_PROMPT）；re-annotation 容易偏離
3. 保留邏輯：`existing_name_ja or gpt_name_ja`，與父事件的 `event.get("name_ja") or raw_title` 一致

---
## 2026-05-02（深夜 3）— Quality check 判斷欄位錯誤、competition 排除（commits `b82849d`→`80920ce`、`4ca383a`）

**問題一（commits `b82849d`→`80920ce`）：** `/admin/quality` 缺地點 check 查詢 `location_address IS NULL`，但詳情頁 render 的是 `location_name`。兩個欄位不同，check 結果與頁面顯示矛盾。

**修復：** DB query 改為 `.is('location_name', null)`；同時把 `gguide_tv` 排除從 JS filter 移到 DB 層：`.not('source_name', 'eq', 'gguide_tv')`。

**問題二（commit `4ca383a`）：** 競賽/補助類活動天生無實體地點，但被 quality check flag 為缺地點，無法清零。

**修復：** 加 `.not('category','cs','{"competition"}')` 於 DB query 排除 `competition` category 事件。

**教訓：**
1. Quality check 的判斷欄位必須與詳情頁顯示欄位一致——先查「前端 render 哪個欄位」再設計 check
2. 某些事件格式（競賽、補助、電視節目、線上直播）天生不符某些 check 條件，排除條件應在 DB query 層處理，不在 JS 層
3. 排除條件用 `.not('column','operator','value')` Supabase RPC 語法，不在 client 側 `.filter()`

---
## 2026-05-02（深夜 3）— robots.txt allowlist social bots、scholarship 標籤更新（commits `d9765bb`、`60cc2f1`）

**robots.txt（commit `d9765bb`）：** `facebookexternalhit` 和 `Twitterbot` 未在 `robots.ts` 明確許可，依賴預設 allow 行為。為確保 OG 預覽正確抓取，加入明確 `Allow: /` 規則。

**scholarship 標籤更新（commit `60cc2f1`）：**
- zh: 補助・獎學金 → 徵件・補助・獎學金
- en: Grants & Scholarships → Open Calls, Grants & Scholarships
- ja: 助成・奨学金 → 公募・助成・奨学金
- Label-only rename：只動三個 `messages/*.json`，不動 `types.ts`。

---
## 2026-05-02（深夜 2）— NHK annotator fallback 移除（nhk_rss 薄描述由 scraper 處理）

**變更：** 移除 `annotator.py` 中 `nhk_rss` 專用的薄描述 fallback 區塊（在 annotator 中用 `fetch_ref_text()` 補抓文章全文）。此功能已由 `nhk_rss.py` scraper 端在 `scrape()` 中直接處理（commit `6604f44`），annotator 端重複執行已無意義。同步移除 `from sources.base import fetch_ref_text` import。

**教訓：** 內容補齊（article enrichment）應在 scraper 端處理，不在 annotator 端。annotator 收到的 `raw_description` 應已包含所有必要內容。annotator fallback 造成重複 HTTP 請求且難以測試。

---
## 2026-05-02（下午）— locationOverseas i18n namespace 錯誤、分類標籤更新、新增分類（commits `049edd8`、`a4a6f75`、`7567ef0`、`8aee4de`、`1870c8a`、`24fcb3c`、`b62b385`、`dfc5aaf`）

**問題：** 新增 `locationOverseas` filter 時，修改腳本使用 `data["locationOverseas"] = label`，將 key 寫到 JSON 頂層，而非 `data["filters"]["locationOverseas"]`。`FilterBar` 使用 `const t = useTranslations("filters")` 呼叫 `t("locationOverseas")`，next-intl production 找不到 key，靜默回傳 key 名稱字串，導致 FilterBar 渲染異常、預設「進行中」timeMode 消失。

**修復（commit `049edd8`）：** 三語言 JSON 全部把 `locationOverseas` 從頂層移入 `filters.{}` 內。

**教訓：**
- `t("key")` 只查找 `useTranslations("<namespace>")` 指定的 namespace 下的 key
- 修改 `messages/*.json` 的腳本新增 key 時，必須確認目標 namespace：`data["filters"]["key"]` 而非 `data["key"]`
- next-intl missing key 靜默失敗（production 回傳 key name 字串，不拋錯）——需靠 `grep -n "key" messages/zh.json` 確認行號在正確 block（filters block 約 L10–L40，頂層約 L400+）

### 同日其他變更（分類標籤 + 新增分類）

- `senses` zh：台灣感性 → 台灣感性・認同（commit `a4a6f75`）
- `senses` en：Taiwan Senses → Taiwanese Identity & Sensibility（commit `7567ef0`）
- `senses` ja：台湾の感性 → 台湾の感性・アイデンティティ（commit `7567ef0`）
- `competition` ja：スポーツ・競技大会 → スポーツ・コンテスト（commit `8aee4de`）
- 新增 `folklore`（民俗・歲時）→ group_arts（commits `24fcb3c`、`b62b385`）
- 新增 `scholarship`（補助・獎學金）→ group_knowledge（commit `dfc5aaf`）

---
## 2026-05-02 — 全 *_zh 欄位簡繁轉換防護

**問題：** GPT-4o-mini 偶爾在 `description_zh` 輸出簡體中文（例：`1e375d6c` tokyoartbeat 事件整段簡體）。既有的 `_loc_zh()` 只保護 location 欄位，`name_zh`/`description_zh`/`business_hours_zh` 完全無防護。

**修復：**
1. 將 `_LOC_ZH_SIMP_TO_TRAD` 擴展為通用 `_SIMP_TO_TRAD`（~100 字元），覆蓋 location + description + name 常見簡體字
2. 新增 `_to_trad(val)` 函式，套用到所有 GPT 輸出的 `*_zh` 欄位（`name_zh`、`description_zh`、`business_hours_zh`），含 fix_reviewed 與 sub-event 路徑
3. `_loc_zh()` 改為內部呼叫 `_to_trad()`，不再維護獨立字表
4. 全 DB 掃描並修復 7 筆事件（3 筆 active）的簡體殘留
5. `auto_qa.py` 的 `SIMP_RE` 同步擴展，`ZH_FIELDS` 加入 `business_hours_zh`

**教訓：** SYSTEM_PROMPT 的繁體指令不足以 100% 防止 GPT 輸出簡體。必須在寫入 DB 前對所有 `*_zh` 欄位做 character-level 轉換。新發現的簡體字應同步更新 `annotator.py._SIMP_TO_TRAD` 和 `auto_qa.py.SIMP_RE`。

---
## 2026-05-02 — name_ja 不再由 GPT 覆寫（保留原始標題）+ 子事件原始日文名規則

**問題：** `annotate_pending_events()` 中 `update_data["name_ja"]` 使用 GPT 回傳的 `annotation.get("name_ja")`，覆寫了爬蟲抓取的原始標題。GPT 經常改寫日文標題（加上 context、截斷副標、替換用語），導致 `name_ja` 偏離原始資料。

**修復：**
1. `update_data["name_ja"]` 改為 `event.get("name_ja") or raw_title`——永遠保留原始標題
2. SYSTEM_PROMPT `NAME WRITING RULES` 改為告知 GPT「name_ja 直接複製 raw_title，不要改寫」
3. GPT 仍然生成 `name_ja`（JSON schema 不變），但此值只用於 sub-events（sub-events 無 raw_title）
4. SYSTEM_PROMPT 新增子事件規則：sub-event `name_ja`/`description_ja` 必須使用原始日文文本中的寫法。電影片名用日本上映名，人名用原始片假名/漢字記載。禁止翻譯中文/台灣人名成日文或自創片假名讀音

**連帶影響：**
- `name_ja_locked` 機制不再需要用於 annotator（flag 仍存在於 DB + scraper dataclass，向後相容）
- 原本的 SYSTEM_PROMPT 中關於「name_ja 必須 self-contained」的規則已移除

**教訓：**
- 日文原始標題是 source of truth，不應由 AI 重新詮釋
- 翻譯校正（片名、人名）只應套用在翻譯欄位（`*_zh`、`*_en`），不碰原文欄位（`*_ja`）
- 子事件日文名也適用同一原則：使用原始文本中的日文寫法，不發明新的寫法

### 同日其他 annotator 改善（commits `eaab464`、`fb568c4`、`28c1b41`、`6604f44`）

- **日期優先級翻轉**（`eaab464`）：`start_date`/`end_date` 改為 scraper-first（`event.get("start_date") or annotation.get("start_date")`）。之前 GPT 推斷的日期會覆蓋爬蟲精確提取的日期。
- **location_url GPT 提取**（`fb568c4`）：SYSTEM_PROMPT JSON schema 新增 `location_url`，讓 GPT 從 raw_description 中提取場地官網 URL。規則：只提取明確出現的 URL，不推斷；scraper 值優先；null 不覆蓋已有值。
- **google_news_rss 薄描述觸發文章抓取**（`28c1b41`）：當 `raw_description` < 400 字且 `source_name == 'google_news_rss'` 時，自動用 `fetch_ref_text()` 抓取原文補充。
- **nhk_rss 薄描述補齊 + pubDate 錨定**（`6604f44`）：NHK RSS snippet 通常 50-200 字，新增 `_NHK_THIN_BODY_CHARS=400` 閾值 + `fetch_ref_text()` 補充。`pubDate` 作為 `start_date` fallback anchor。
- **news movie title bracket fallback**：`enrich_movie_titles()` 和 `enrich_person_names()` 中，news source（`prtimes` 等）的 `_BRACKET_TITLE_RE` 搜尋改為先查 `raw_title`，找不到括號時再查 `name_ja`（因 annotator 可能在 name_ja 中加了括號標題）。

---
## 2026-05-02 — 人名校正擴展至所有事件（非僅電影）

**變更：**
- `person_name_lookup.py`：新增 `extract_katakana_names()`（regex 提取帶 ・ 的片假名人名）、`_search_person_eiga()`（eiga.com 人物搜尋）、`lookup_single_person()`（通用人名查詢）
- `_lookup_zh_via_wikipedia()` + `_lookup_zh_via_ja_wikipedia()`：新增 `strict` 參數——`strict=True` 時要求人物關鍵字匹配（zh.wikipedia）或 zh 跨語言連結（ja.wikipedia），阻止假陽性
- `annotator.py` `enrich_person_names()`：移除 `.contains("category", ["movie"])` 過濾，改為全事件掃描。電影事件走 eiga.com 電影頁結構化查詢（`strict=False`），非電影事件走片假名提取 + Wikipedia（`strict=True`）
- CI workflow step 名稱更新為「Enrich person names via eiga.com + Wikipedia (all events)」

**假陽性防範：**
- 問題：非電影事件中 `リン・インジュ` → `安永亜季`（日本人名，非目標）；`ホアン・ヤーリー` → `脊蛇屬`（蛇屬名）
- 解決：`strict=True` 模式要求 zh interlanguage link 或 snippet 含人物關鍵字，消除 CJK fallback 的假陽性
- 噪音過濾：最多 3 ・ 分段、每段 ≤7 字、噪音後綴排除（ホテル、センター 等）

**測試結果：**
- 林志玲、周杰倫、蔡英文、鄧麗君：全部正確 ✓
- ジョン・スミス（非華人）：正確 SKIP ✓
- 電影管線（赤い糸 輪廻のひみつ, 5 人）：未受影響 ✓

**教訓：**
1. Wikipedia 自由文字搜尋的 CJK fallback（`2 ≤ len(title) ≤ 4`）在非策展輸入下會大量假陽性——通用管線必須用 `strict=True`
2. eiga.com 不只有電影搜尋，也有 `/search/{name}/person/` 人物搜尋——適用於所有事件中的演員/導演
3. 噪音控制靠「regex 過濾 + Wikipedia 自過濾」雙層即可，不需要 GPT 前置提取

---
## 2026-05-02（深夜）— Realtime stale closure 修復、badge client component、Quality page 清理（commits `c3fe0bc`、`4a71258`、`cd4cc29`）

### 問題一：AdminReportsTable Realtime stale closure（commit `4a71258`）
`AdminReportsTable` 在 component 頂層建立 `supabase` client，再於 `useEffect` 中捕捉 → 可能捕捉到舊實例（stale closure）。同時只訂閱 INSERT，UPDATE 事件（confirm/dismiss）不觸發列表更新。

### 修復
1. `supabase` client 改在 `useEffect` **內部**建立，每次 effect 執行都取得新實例，徹底消除 stale closure。
2. 補上 `UPDATE` handler，讓另一個 admin session confirm/dismiss 後目前列表即時反映。

### 問題二：AdminTabNav badge SSR 靜止不動（commit `4a71258`）
`AdminTabNav` 是 Server Component，pending count 在頁面 SSR 時固定，新報告提交後 badge 數字不更新。

### 修復
建立 `AdminReportsBadge` client component：接收 `initialCount` 做 SSR 初始值，訂閱 Realtime INSERT（count+1）和 UPDATE（重新 fetch count），badge 即時更新。

### 教訓
- **Supabase client 必須在 `useEffect` 內部建立**：在頂層建立再傳入 effect 會形成 stale closure，可能捕捉到已失效的舊 client 實例。（已新增至 SKILL.md Supabase Realtime 章節）
- **Server Component 中的動態 UI 必須抽出為 Client Component + Realtime**：SSR 抓取的靜態值永遠不會更新，任何需要即時性的計數器都必須走 Client Component + Realtime 分離模式。
- Admin pages 訂閱應同時包含 `INSERT` 和 `UPDATE`：兩個 admin session 同時開啟時，UPDATE 才能讓另一端的操作同步顯示。

### 問題三：Quality page expired-but-active 欄位無法操作（commit `cd4cc29`）
Archive cron 一天只跑一次，白天過期的事件留在「expired-but-active」欄位，但點擊後無任何可執行操作。

### 修復
移除整個「expired-but-active」section，避免顯示永遠有值但無法操作的清單。

### 教訓
無操作 Quality check section（無 fix button / batch action，且數值永不清空）應直接移除。（已新增至 SKILL.md Admin Quality Page 章節）

### 問題四：ReportSection wrongCategory 無預填（commit `c3fe0bc`）
使用者勾選「wrongCategory」時，`suggestedCategories` 為空，需手動重新選取目前分類，操作負擔高。

### 修復
`ReportSection.tsx` 新增 `currentCategories?: Category[]` prop；勾選 wrongCategory 時自動預填事件目前分類。

### 教訓
所有「修正建議」欄位應以目前值為預設。

---
## 2026-05-02 — Admin 頁面 SSR 快取無效化 + Realtime 自動重新整理（commits `cad13a2`、`046d8cd`、`08b4912`）

### 問題一：`router.push()` 後顯示舊快取
`AdminEditClient.handleSave()` 儲存後呼叫 `router.push('/admin')`。admin 列表頁是 SSR，導航回去時 Next.js router cache 尚未失效，`is_active` 等欄位顯示舊值，即使 DB 已更新。

### 問題二：confirm/dismiss 後同樣顯示舊快取
`AdminReportsTable.handleConfirm()` / `handleDismiss()` success 路徑導航回 `/admin`，同樣遇到 SSR 快取問題。

### 問題三：AI 建立報告後頁面不自動更新
`/admin/reports` 頁面不會自動顯示新報告，需手動重新整理。

### 修復
1. `AdminEditClient.handleSave()`：在 `router.push()` **前**加 `router.refresh()`。
2. `AdminReportsTable.handleConfirm()` / `handleDismiss()`：success 路徑各加 `router.refresh()`。
3. `AdminReportsTable`：新增 Supabase Realtime 訂閱 `{ event: "INSERT", table: "event_reports" }`，INSERT 後重新 fetch 完整 row（含 joined event），去重後插入列表頂端；unmount 時 `removeChannel()` 清理。

### 教訓
- **SSR 快取無效化**：Client Component 執行 mutation 後導航回 SSR 頁面，**必須**在 `router.push()` 前加 `router.refresh()`，否則頁面顯示舊快取。這是 Next.js App Router 的必要模式，不是 optional。
- **兩種即時更新模式應同時使用**：
  - **Realtime 訂閱** → 同一 tab 的即時更新（新 row 出現、狀態變更同步）
  - **`router.refresh()`** → 跨頁面導航（從編輯頁 / 審查頁回到列表頁）
  兩者覆蓋不同場景，缺一不可。
- Admin 列表元件的 `useEffect` 應同時訂閱 `INSERT` 和 `UPDATE`，fetch 完整 row（含 join）再更新 state。

---
## 2026-05-02 — GPT 副標題截斷修復（annotator.py SUBTITLE RULE + 批次 DB 修正）

### 問題
`annotator.py` GPT-4o-mini 遇到學術論文格式標題（`主標――副標`）時，習慣性省略副標，只翻譯主標。`name_ja_locked` 保護 `name_ja` 不被覆寫，但 `name_zh`/`name_en` 仍由 GPT 生成，仍會截斷。

### 修復
1. **SYSTEM_PROMPT 新增 SUBTITLE RULE**（`annotator.py`）：
   > 當 name_ja 含 `――`/`──`/`―`/`—` 副標題分隔符時，name_zh 和 name_en 必須包含完整副標題，不得截斷。
2. **批次 DB 修正**：掃描 15 筆 `name_ja_locked=True` 事件，找出 4 筆副標被截斷：
   - `116cadee`（台灣地方選舉 + 桃園觀音新屋）
   - `3dbfecbb`（釋迦出口 + 政治經濟學）
   - `8339ed6f`（朱西寧 + 美援體制關係）
   - `47db1bb2`（1937 女性教育 + 機構列表）

### 教訓
- **`name_ja_locked` 只保護 `name_ja`，不保護 `name_zh`/`name_en`**。結構化來源的副標題翻譯仍需靠 SYSTEM_PROMPT 規則，或手動修正。
- GPT 翻譯學術副標題的準確性必須在部署後抽查，不能只依賴自動 annotate。
- 新增含副標題的學術論文事件後，建議執行：`SELECT id, name_ja, name_zh, name_en FROM events WHERE name_ja_locked AND name_ja LIKE '%――%';` 確認翻譯完整。

---
## 2026-05-02 — 新增 `docs/TRANSLATION_PIPELINE.md` 翻譯管線文件

- **內容**：完整記錄 6 層翻譯管線（爬蟲層 → DeepL 回退 → GPT-4o-mini 標注 → 官方片名補全 → 人名修正 → 前端 Fallback Chain），含 CI 執行順序、CLI 參數、sub-event 翻譯、admin feedback loop、欄位清單。
- **同步**：`docs/ARCHITECTURE.md` 已新增交叉連結。
- **無新 coding rule**：此為純文件化工作，未發現新的 coding 教訓。

---
## 2026-05-02（下午）— generate.py load_dotenv、not-viable 來源、Admin 篩選預設值、eurospace lookup_movie_titles（commits `d94fc80`、`29046ad`、`f905ee2`）

### auto_scraper/generate.py load_dotenv 修復（commit `d94fc80`）
- **問題**：本機 `python -m auto_scraper.generate --source-id <id>` 執行崩潰：`KeyError: SUPABASE_URL`。
- **根本原因**：`generate.py` 無 `load_dotenv()` 呼叫；`main.py` 和 `annotator.py` 因為有 `load_dotenv` 所以正常，但 generate 是獨立入口。
- **修復**：在 `generate.py` import 區塊後加 best-effort `load_dotenv()`（`try/except ImportError` 包圍）。CI 用 secret，load_dotenv 為 no-op，不受影響。
- **教訓**：**任何有 `-m module` 獨立 CLI 入口的 Python module 都需要 `load_dotenv()`**。不能依賴父 module（main.py）已先執行 load_dotenv。→ 已加入 scraper-expert/SKILL.md § auto_generate Pipeline。

### source 126/148 標記 not-viable（純 DB 操作）
- source 126（TAP）：FullCalendar SPA，React 動態渲染，DOM 無事件元素 → not-viable。
- source 148（Zepp Tokyo）：Cloudflare JS challenge 攔截 Playwright；無標準 URL pattern → not-viable。
- **操作方式**：直接 `UPDATE research_sources SET auto_scraper_status='not-viable', auto_scraper_failed_reason='...'`，不需走 auto_generate。
- **新增 not-viable 判定準則**：
  - Cloudflare JS challenge → not-viable（Playwright stealth 無法可靠繞過）
  - SPA 動態行事曆（FullCalendar / React）→ not-viable（事件不在初始 HTML DOM 中）

### Admin 篩選預設值修復（commit `29046ad`）
- **問題**：AdminEventTable 預設 filter `active` 讓管理員只看到 active 事件，遺漏 pending / archived。
- **修復**：預設改為 `all`。
- **教訓**：後台管理頁預設應 `all`，前台頁預設應 `active`。

### eurospace.py 加入 lookup_movie_titles（commit `f905ee2`）
- eurospace 為最後一個未整合 `lookup_movie_titles` 的 cinema scraper。
- import 後在 `Event()` 建構前呼叫，silent failure（lookup 失敗時回傳 None，不中斷 scrape）。
- 詳細記錄在 scraper-expert/history.md 2026-05-02 頂部條目。

---
## 2026-05-02 — record_links JSONB bug、name_ja_locked 機制、Pass 3 孤兒誤殺 WARNING（commits `0cdad90`、`180c495`）

### record_links JSONB bug 修復
- **問題**：`database.py` 的 `_event_to_row()` 用 `json.dumps(links)` 傳給 Supabase SDK，JSONB 欄位存入字串而非陣列；前端 `.map()` 在字串上呼叫 → TypeError → HTTP 500。
- **修復**：直接傳 Python `list` 物件，移除 `json.dumps()`。Supabase Python SDK 自動序列化 Python native types。
- **教訓**：Supabase SDK JSONB 欄位（`jsonb`、`jsonb[]`）**必須傳 Python `list`/`dict`，絕對不能用 `json.dumps()` 先序列化**。`json.dumps()` 會造成雙重編碼，最終存入 `"[{...}]"` 字串而非 JSONB 陣列。→ 已加入 scraper-expert SKILL.md § Supabase SDK — JSONB Field Rules。

### name_ja_locked 機制（commits `0cdad90`、`180c495`）
- **設計**：`name_ja_locked: bool = False` 加入 `Event` dataclass；`database.py` `_event_to_row()` 在 True 時寫入 DB；`annotator.py` 在 True 時跳過 `name_ja` 覆寫（其他欄位照常生成）。
- **DB**：`supabase/migrations/034_name_ja_locked.sql`（`DEFAULT false`，不需 backfill）。
- **首次適用**：`taiwanshi.py` 的學術論文子活動（`題目:` 欄位抓取的精確標題）。
- **教訓**：「scraper 已有精確答案，annotator 不應覆寫」的場景，應用 `locked` flag 而非事後 DB patch。鎖定條件：標題來源是結構化定義欄位（`題目:` / 官方片名），而非自由文字推斷。

### ⚠️ Pass 3 孤兒誤殺 — 程式碼尚未修復
- **問題**：`merger.py` Pass 3 誤 deactivate 了有效父事件（`00ae1ea8`、`dfb490c8`）的所有子活動（共 12 筆）。
- **已做**：手動 DB hotfix 還原（`UPDATE is_active=True WHERE parent_event_id IN ('00ae1ea8...', 'dfb490c8...')`）。
- **尚未修復**：`merger.py` 程式碼未改動，下次執行仍可能再次誤殺。
- **需要的修復**：Pass 3 在清除孤兒前，加保護條件——只有當父事件的 `secondary_source_urls` 非空（即真正被 Pass 1/2 合併為 secondary）時，才允許清除其孤兒子活動。若父事件本身只是被「錯誤合併」成 secondary，此保護可防止連帶誤殺。

---
## 2026-05-02 — merger richness tiebreaker + MERGER_WORKFLOW.md（commits `19a2067`、`d4e9227`）

**問題：** `merger.py` Pass 1/3 在兩個來源 `SOURCE_PRIORITY` 相同時，以遍歷順序決定 primary，可能選到欄位空洞的事件。

**修復：**
- 新增 `_richness_score()`（0–10 分）：`official_url`/`start_date`/`end_date`/`location_address`/`location_name` 各 +1；`raw_description` 每 200 字 +1（上限 5）。
- Pass 1/3 priority 比較改為嚴格 `<`/`>`；相同 priority 時比 richness score。
- `location_address` 補入 SELECT 查詢欄位。
- 新建 `docs/MERGER_WORKFLOW.md`：四個 Pass 規則、SOURCE_PRIORITY 表、決策流程、幂等性保證、FAQ。

**教訓：** SOURCE_PRIORITY 相同的來源配對，一定要 richness tiebreaker，不能依賴遍歷順序。新建官方來源時同步設定 SOURCE_PRIORITY。

---
## 2026-05-02 — Person Name Lookup 系統（movie 事件人名修正）

**建構內容：**
- 新增 `scraper/person_name_lookup.py`：查詢電影演員/導演的正式中英文姓名
- 策略：eiga.com 電影頁 → 取得演員列表（角色、片假名、person URL）→ eiga.com 人物頁（英文名＋出身國）→ zh.wikipedia 搜尋（中文名）
- 新增 `annotator.py` 的 `enrich_person_names()` + CLI flag `--enrich-person-names`
- 使用 GPT-4o-mini 修正 desc_zh 中的錯誤音譯人名（`_fix_person_names_gpt()`）

**DB 修正：**
- Event `4a8772ec`（cinemart_shinjuku, 赤い糸 輪廻のひみつ）：「紀德恩」→「九把刀」
- Event `f970e4e3`（shin_bungeiza, 赤い糸 輪廻のひみつ）：desc_zh 修正為正確人名（九把刀、柯震東、宋芸樺、王淨）

**教訓：**
1. GPT 音譯人名不可靠：片假名→中文會產生錯誤音譯（ギデンズ・コー →「紀德恩」而非「九把刀」），藝名/筆名尤其嚴重
2. eiga.com 人物頁有英文名但無中文名，需 Wikipedia 補查
3. Wikipedia 搜尋需加出身國消歧義（「Wang Ching」→ 加「台灣」才能找到「王淨」）
4. ja.wikipedia 條目標題對中國/台灣人常直接用 CJK（搜「クー・チェンドン」→ 條目「柯震東」），可作 fallback
5. eiga.com 演員名含角色名前綴（「孝綸（シャオルン）クー・チェンドン」），需 regex 剝離
6. desc_zh 的錯誤人名是 GPT 音譯產物，無法用簡單字串替換修正，必須用 GPT 辨識並替換
7. Wikipedia 人物關鍵字過濾（演員/導演/出生）防止假陽性，優先選短標題（2-4 字）

---
## 2026-05-02 — competition 標籤更名（commit f3cae57）

- zh: `競技・競賽` → `競賽・運動`；en: `Competition & Contest` → `Sports & Competition`；ja: `コンテスト・大会` → `スポーツ・競技大会`
- 只更新 `web/messages/zh.json`、`en.json`、`ja.json`；不需動 `types.ts`（`Category` union value 未改）
- 教訓：若只改分類標籤的**顯示文字**而非 value，無需執行 `tsc --noEmit`，但養成習慣可執行確認

---
## 2026-05-02 — Auto-scraper Phase 2.1/2.2/2.3 實作（commits `b6e1768`、`f9eff43`、`d23be68`）

**Phase 2.1（`b6e1768`）— Schema injection + failure artifacts：**
- `generate.py` 模組初始化讀取 `auto_scraper/spec_schema.json` 至 `SPEC_SCHEMA_TEXT`；user message 開頭 prepend schema + 必填欄位 checklist。
- spec-invalid 路徑新增 prompt.txt / sample.html / meta.json 持久化。
- **症狀**：修前 GPT-4o 三次重試都漏 `base_url`；修後 schema 變成 grounding 上下文。

**Phase 2.2（`f9eff43`）— detail_url fallback + 完整 sandbox-failed artifacts：**
- `template.py.j2` 在 `DETAIL_LINK_SELECTOR == ""` 時，從 card 內抓第一個 `<a href>`，避免 `source_url = page.url`（listing URL）導致全 card 因 `source_id_url_pattern` 不符而被 skip。
- sandbox-failed 路徑補寫 spec.json / generated.py / dry_run.txt。
- **驗證**：Artist Cafe Fukuoka 0 → 12 events。

**Phase 2.3（`d23be68`）— Pre-sandbox selector validation + LLM grounding：**
- SYSTEM_PROMPT 加硬規則：只准用 sample HTML 中 verbatim 出現的 class/ID；明文列出常見幻覺（`.event-card` / `.event-list-item` / `.c-event-list__item-title`）；建議優先使用 tag selector（`article`、`li`）。
- 新增 `_validate_selectors_against_html()`（BeautifulSoup，~50ms）：確認 `card_selector` ≥ 1 個元素 + `field_selectors.title/date` 在第一張 card 內可命中。違規回灌 LLM retry 訊息。
- **效益**：fast-fail 改成 spec-invalid（無 Playwright spawn），單次失敗從 ~30s + $0.04 降至 ~50ms + 0 美金。

**運維事故：** batch e2e 中段觸發 OpenAI 月度額度耗盡（429 `insufficient_quota`），全 org 呼叫直接停擺。`--budget-usd` per-call guard 不保護 org-level 月配額——需另外監控（見 Engineer SKILL § OpenAI Org-Level Quota Monitoring）。

---
## 2026-05-02 — inline Python shell injection 汙染；zsh git add glob 括號失敗；分類新增 6 處協議

**問題 A：inline Python shell injection**
在終端執行 `python3 << 'PY' ... PY` 或 `python3 -c "..."` 時，shell history 汙染導致惡意片段（如 `rm -f ...`）插入 f-string，造成 SyntaxError 或非預期執行。
- **修正：** 改用 `create_file` 建立 `/tmp/<name>.py` 腳本，再執行 `python3 /tmp/<name>.py`。
- **教訓：** 一旦出現 SyntaxError 且指向 f-string 大括號，立即放棄 inline 模式，改用 `/tmp/*.py` 腳本。

**問題 B：zsh `git add` 含 `[...]` 路徑**
`git add web/app/[locale]/page.tsx` 在 zsh 中因 glob 展開失敗：`zsh: no matches found`。
- **修正：** `git add 'web/app/[locale]/page.tsx'`（單引號）
- **教訓：** 含方括號的路徑在 zsh 必須用單引號包覆，適用所有 `git add`、`cp`、`mv` 操作。

**問題 C：分類新增（`documentary`、`parenting`）6 處同步協議**
- 每次分類新增必須在**同一個 commit** 更新 6 處（Category union、CATEGORIES、CATEGORY_GROUPS、zh/en/ja.json）。
- 完成後執行 `cd web && npx tsc --noEmit`，無錯誤才能 commit。
- i18n JSON 含 CJK 字元時必須用 Python json-module 腳本編輯（不可用 `replace_string_in_file`）。

---
## 2026-05-02 — Daily Dev Report、WIP tracking、Overseas filter 實作（commits `0ee713d`、`f56c4e0`、`96834f8`、最新 commit）

**Daily Dev Report（`0ee713d`）：**
- 新增 `scraper/daily_report.py`：查詢 Supabase（`scraper_runs`、`events`、`event_reports`、`research_sources`）＋ `GIT_COMMITS` env var，輸出四個 section：昨日提交、爬蟲結果、待處理事項、安全日誌。
- 新增 `.github/workflows/daily-dev-report.yml`：每日 02:00 JST cron，`dawidd6/action-send-mail@v3` 透過 Gmail SMTP 寄送報告。
- **CI secrets 需求**：`GMAIL_USER`、`GMAIL_APP_PASSWORD`（App Password，非一般 Gmail 密碼）、`DEV_REPORT_EMAIL`。

**WIP tracking（`f56c4e0`）：**
- 新增 `.github/wip.md`：存放進行中開發項目，`## 功能名稱` = active，`## ✅ 功能名稱` = completed。
- `daily_report.py` 加入 `_read_wip_items()`：以 `Path(__file__).parent.parent / ".github" / "wip.md"` 跨目錄讀取；在「待處理事項」section 顯示「🚧 開發中項目」。

**Recently-completed WIP items（`96834f8`）：**
- `_read_wip_items()` 改回傳 `(active, recently_completed)` tuple。
- `## ✅` 項目需有 `最後更新: YYYY-MM-DD` 且落在過去 26 小時內，才顯示為「✅ 昨日完成」；超過 26 小時靜默略過。
- regex：`_WIP_DATE_RE = re.compile(r"最後更新[:\uff1a]\s*(\d{4}-\d{2}-\d{2})")` — 同時支援中文冒號（`：`）和英文冒號（`:`）。

**Overseas (Taiwan cities) filter（最新 commit）：**
- `FilterBar.tsx`：新增 `<option value="overseas">`。
- `AdminEventTable.tsx`：`filterLocation` union 加 `'overseas'`；filter 邏輯使用 16 個台灣城市 markers 做 `includes()` 比對。
- `web/app/[locale]/page.tsx`：overseas branch 用 `ilike '%城市名%'` 對 `address` 欄位比對；16 個城市依序 OR 組合。
- i18n 三語同步：`海外（台灣各城市）` / `Overseas (Taiwan Cities)` / `海外（台湾各都市）`。
- **教訓**：台灣城市名稱直接存在 `address` 欄位，不需前綴守衛；`OVERSEAS_MARKERS` 陣列在 `page.tsx` 和 `AdminEventTable.tsx` 兩處必須完全同步。

---
## 2026-05-02 — annotator google_news_rss Playwright 文章補抓（commit `9a0414a`）
- **問題**：google_news_rss 的 `raw_description` 只有 RSS snippet（通常只有標題），GPT 無法從中提取活動日期，`start_date` 永遠為 NULL。
- **修正**：在 `annotator.py` 新增 `_fetch_gnews_article_text()`，使用 Playwright 追蹤 Google News 重導向 URL 取得原始文章本文（最多 4000 字），替換 `raw_desc` 傳給 GPT。整個 run 共用一個 Playwright browser 實例；`raw_description` 欄位不寫回 DB（in-memory only）。失敗時（timeout / paywall / DNS）gracefully fallback 到原始 snippet。
- **教訓**：Playwright browser 實例應在 annotation loop 前啟動、`finally` 中關閉，不可逐事件重啟。文章文字是 annotation 輸入的暫存資料，絕不寫回 DB 原始欄位。

---
## 2026-05-02 — google_news_rss scraper start_date fallback 修正（commit `9510a05`）
- **問題**：`_extract_start_date()` 找不到日期時 fallback 使用 `pub_date`（文章發布日），與活動日期無關。Google News RSS `<description>` 永遠只有標題短文，不含活動日期，幾乎每筆都觸發 fallback。
- **修正**：`_extract_start_date()` 回傳型別改為 `Optional[datetime]`；找不到日期改回傳 `None`，不再 fallback 到 pub_date。批次效果：40 筆 start_date=pub_date 的錯誤資料被下架；1 筆原始連結失效的事件（c2c80efd）直接設為 `is_active=False`。
- **教訓**：聚合新聞來源（Google News RSS）的 pub_date ≠ 活動日期，不可作為 start_date fallback。找不到日期必須回傳 `None`；annotator 會透過 Playwright 文章補抓取得正確日期。原始連結已失效的事件直接設 `is_active=False`，不嘗試保留。

---
## 2026-05-01 — 移除無效地點篩選選項「電視節目 (tv)」（commit `2989940`）

**問題：** FilterBar 與 AdminEventTable 的 `<option value="tv">` 地點篩選選取後結果永遠為零，是無效選項。`gguide_tv` 事件 `location_name` 已改存頻道名稱，不再是「電視頻道」，與 tv 篩選邏輯不匹配。

**修正檔案（共 6 處）：**
- `web/components/FilterBar.tsx` — 移除 `<option value="tv">`
- `web/app/[locale]/page.tsx` — 移除 `sp.location === "tv"` 查詢分支
- `web/components/AdminEventTable.tsx` — 移除 tv option 及兩處 `filterLocation === "tv"` 判斷
- `web/messages/zh.json`、`en.json`、`ja.json` — 移除 `locationTv` i18n key（共 3 檔）

**教訓：** 地點篩選選項值必須對應 DB 實際存在的 `location_name`。移除某個 location option 時，需同時清理：FilterBar `<option>`、`page.tsx` 查詢分支、AdminEventTable option 與 filter 邏輯、三個 i18n 檔案的 key。

---
## 2026-05-01 — archive cutoff 與 quality page 截止日不一致（1e6cd24）

**問題：** `archive_ended_events()` cutoff = `yesterday 00:00 UTC`（1 天寬限），quality page cutoff = `today`，造成當天到期事件出現在 quality 清單但不會被自動下架，需等兩天才消失。

**根本原因：** `database.py` 的 `archive_ended_events()` 使用 `timedelta(days=1)` 寬限期，而 quality page 直接用 `today` 當截止，兩端定義不一致。

**修復：** `database.py` 移除 `timedelta(days=1)`，改為 `today 00:00 UTC`；DB 手動下架 4 筆到期事件（`b2589d75`、`78570c96`、`8c08c681`、`dec284a5`）。

**教訓（已廢止）：** ~~scraper `archive_ended_events()` 的 cutoff 必須與 admin quality page 的 `today` 截止一致。~~
> **⚠️ archiver 已於 2026-05-06 完全刪除**：`archive_ended_events()` 已從 codebase 移除，此教訓不再適用。事件 `is_active` 現為純手動管理。

---

## 2026-05-06 — archiver 完全刪除

**決策：** `archive_ended_events()` 及所有相關呼叫從 `scraper/database.py` 和 `scraper/main.py` 移除。

**影響：** 事件的 `is_active` 狀態不再由每日 CI 自動管理。停用／激活需透過 Admin UI 或手動 DB 操作。Quality page 的「已過期」清單仍顯示，但不再有自動下架動作。

**教訓：** 過去活動（含學術研討會 sub-events）激活後永遠保持激活狀態，不會被 CI 覆蓋。`work_id` 連結作為語意保留信號仍建議保留，但其「bypass archiver」的技術作用已消失。

---
## 2026-05-01 — 品質頁面誤判多城市活動為「地址缺失」

**問題：** `web/app/[locale]/admin/quality/page.tsx` 的「地址缺失」品質檢查把 `location_name` 含「・」（如「東京・京都・大阪」）的多城市活動標記為異常，造成誤報。

**根本原因：** 多城市活動格式慣例為 `城市A・城市B・城市C`，這類活動的 `location_address` 刻意設為 `null`（避免錯誤錨定到單一城市）。品質檢查邏輯沒有識別此格式，誤判為資料缺失。

**修正：** 在 missing-address 過濾器中排除 `location_name.includes('・')` 的活動。

**教訓：** 多城市活動 `location_address = null` 是正確狀態，不是錯誤。任何「地址缺失」品質檢查都必須先排除 `location_name.includes('・')` 的多城市活動。

---
## 2026-05-01 — quality page is_active=false 事件導致 404（commit `dd76445`）

**問題：** `reviewedMissing` 和 `annotatedNoCat` query 沒有 `.eq("is_active", true)`，已下架事件出現在清單，點選後 404（詳情頁只顯示 is_active 事件）。

**根本原因：** 新增 query 時只套用了主要 query 的 is_active filter，沒有同步套用到所有 section query。

**修復：** 兩個 query 都加上 `.eq("is_active", true)`。

**教訓：** Quality page 的所有 Supabase query 都必須加 `.eq("is_active", true)`，否則下架事件會出現在清單，點選後 404。

---
## 2026-05-01 — quality page 缺地址誤報：多城市 ・ filter（commit `a2fd6d6`）

**問題：** `location_name` 含 `・`（多城市格式，例如「北海道・東京・神奈川・京都・大阪」）的活動出現在缺地址清單，造成誤報。

**根本原因：** `missingAddr` filter 沒有排除多城市活動格式。多城市活動慣例是 `location_name` 用 `・` 連結城市，本身沒有單一地址。

**修復：** `missingAddr` filter 新增排除含 `・` 的 `location_name`；DB patch `一石三鳥グループ` 父活動（`466497e5`）`location_name` → `東京・京都・大阪`。

**教訓：** Quality page `missingAddr` filter 必須同時排除：「オンライン」、「電視頻道」、`gguide_tv` source、以及含 `・` 的 `location_name`（多城市活動）。

---
## 2026-05-01 — quality page 事件連結改為詳情頁（commit `9dd50f3`）

**問題：** `renderDetailTable` 中的 href 指向 `/{locale}/admin/{id}`（編輯頁），應改為 `/{locale}/events/{id}`（詳情頁）。

**根本原因：** 複製 admin 頁面連結時直接用了編輯路由，沒有考慮 quality page 是查看用途。

**修復：** 改 href 為 `/{locale}/events/{id}`，並加 `target="_blank"` 新分頁開啟。

**教訓：** Admin 後台列表頁面（quality、reports 等）的事件超連結一律指向 `/{locale}/events/{id}`（詳情頁），而非 `/{locale}/admin/{id}`（編輯頁）。

---
## 2026-05-01 — taiwan_cultural_center 多城市地點名稱改進（commit `0d900b5`）

**問題：** `location_name` 顯示模糊的「台湾文化センター（全国巡回）」，用戶期望看到具體城市列表（如「北海道・東京・神奈川・京都・大阪」）。

**根本原因：** `_MULTI_CITY_REGIONS` 偵測到多城市後，只設置通用「全国巡回」字串，沒有把偵測到的城市名列入 `location_name`。

**修復：**
1. 改為 `_found_regions = [r for r in _MULTI_CITY_REGIONS if r in _desc_check]`，然後 `"・".join(_found_regions)` 作為 `location_name`。
2. 新增 `東京` 和 `愛知` 到偵測清單（原本漏掉「東京」導致東京+大阪等場合無法觸發）。
3. DB 直接 patch event `51f7cd44` → `location_name = '北海道・東京・神奈川・京都・大阪'`。

**教訓：** 多城市偵測邏輯應直接輸出偵測到的城市列表，而非通用字串；`東京` 必須加入偵測清單（因為它出現在大多數多城市活動中）。

---
**Error**: TaiwanbunkasaiScraper fetch failed — HTTPSConnectionPool Max retries exceeded
**Fix**: Added HTTPAdapter with Retry(total=3, backoff_factor=2) to requests.Session in taiwanbunkasai.py
**Lesson**: All scrapers using requests.Session must mount HTTPAdapter with Retry at __init__ to handle transient network failures from GitHub Actions runners.

---
## 2026-05-01 — taiwan_cultural_center 多城市巡迴偵測修正（commit `a2d6eea`）

**問題：** `台湾映画上映会2026` 是跨北海道・東京・神奈川・京都・大阪 5 城市的巡迴活動，但 scraper 將 `location_address` hardcode 為東京（台湾文化センター）地址，admin 後台「住所」欄顯示東京地址，造成誤導。

**根本原因：** `taiwan_cultural_center.py` 的 location block 完全 hardcode，沒有任何多城市偵測邏輯。

**修復：**
1. **DB 補丁**：直接 patch event `51f7cd44`（台湾映画上映会2026）—— `location_name` → `台湾文化センター（全国5都市）`，`location_address` → `None`。
2. **Scraper 修正**：加入 `_MULTI_CITY_REGIONS` 偵測，description+name 中出現 ≥2 個地區 keyword 時，改用 `台湾文化センター（全国巡回）`，並清空 `location_address`：
   ```python
   _MULTI_CITY_REGIONS = ["北海道", "大阪", "京都", "神奈川", "福岡", "名古屋", "仙台"]
   if sum(1 for r in _MULTI_CITY_REGIONS if r in _desc_check) >= 2:
       location_name = "台湾文化センター（全国巡回）"
       location_address = None
   ```

**教訓：**
- 實體地址不應 hardcode 在 scraper 中；多城市活動需偵測。
- 門檻 ≥2（不用 1），避免「在東京舉辦但描述提到大阪食文化」的 false positive。
- 偵測 keyword list 應涵蓋台灣文化中心有據點的城市：北海道/大阪/京都/神奈川/福岡/名古屋/仙台。
- 多城市偵測模式可推廣至其他有固定地址 hardcode 的 scrapers。

---
## 2026-05-01 — auto_scraper Phase 2 codegen + sandbox（commit `a0606fe`）
**新增：** `## Auto-Scraper Layer B — generate.py` 段落至 engineer/SKILL.md
**內容：**
- Sandbox env allowlist（`SUPABASE_*`、`OPENAI_API_KEY` 等 secrets 絕對不傳）
- Phase 2 scope boundaries（不開 PR、不注入 SCRAPERS、不寫 events DB）
- Cleanup defence-in-depth（`try/finally` + `atexit.register` 雙重保障）
- Budget guard 常數（需定期驗證 OpenAI 定價）
- 7-day retry cooldown 機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — auto_qa anomaly detection + weekly report links (commit `2ae731b`)

**Feature:** New `scraper/auto_qa.py` scans `is_active` events from past 14 days for two anomaly types — `auto_qa_simplified_zh` (simplified Chinese chars in any `*_zh` field) and `auto_qa_missing_address` (has `location_name` but empty `location_address`, with online/TV/`gguide_tv` skipped). Findings are inserted into `event_reports` as pending rows so admins review them at `/admin/reports` (same UI as user-submitted reports). `merger.yml` runs auto_qa 3×/day after `--fix-reviewed`. `weekly_report.py` queries `event_reports` for past 7 days of `auto_qa_*` rows and appends a 🔍 自動 QA 偵測 section to the LINE message with a clickable admin link, only when total > 0. `weekly-report.yml` gained `NEXT_PUBLIC_SITE_URL` env.

**Lesson 1 — `亮` false positive:** Initial `SIMP_RE` draft included `亮`, but `亮` is identical in Traditional Chinese and Japanese (`照亮` is valid Trad). Production dry-run flagged a real Trad description. **Rule:** Only add a char to `SIMP_RE` (or `annotator._LOC_ZH_SIMP_TO_TRAD`) when the corresponding Trad/JP form is a **different glyph**. Verify via CC-CEDICT or kanji.jitenon.jp before adding.

**Lesson 2 — share the user-report queue:** Auto-detected anomalies and user-submitted reports both flow through `event_reports`. Benefits: (a) admin checks one URL; (b) `report_types text[]` allows multiple anomaly types per row; (c) existing confirm/dismiss flow handles auto-QA unchanged. Reusable pattern: future automated checks (dead links, date sanity) should also write to `event_reports` with their own `auto_*` prefix in `report_types`. Dedup against existing pending rows of the same `auto_*` type per `event_id`.

---
## 2026-05-01 — discovery-accounts cron expanded Mon-Thu → Mon-Sun (commit `c936920`)

**Change:** `.github/workflows/discovery-accounts.yml` cron schedule expanded from 4 entries (Mon-Thu) to 7 entries (Mon-Sun) at 02:00 UTC / 11:00 JST. Existing `(DAY-1) % 4` modulo logic in shell already handled all 7 days — no Python change. Slot mapping: Mon→0 / Tue→1 / Wed→2 / Thu→3 / Fri→0 / Sat→1 / Sun→2.

**Lesson — modulo wrap on cron-driven slots:** When N weekdays meet M<N slots via `(DAY-1) % M`, days M+1..N silently re-run slots 0..(N-M-1). Acceptable when those slots are idempotent (search + `skip_hint` dedup yields diminishing returns). NOT acceptable for slots that must run on a fixed cadence (e.g. Peatix slot 3 still only fires Thursdays). To break the wrap: (a) override via `DISCOVERY_SLOT` env on extra cron entries, or (b) raise `SLOT_COUNT`.

---
## 2026-05-01 — 8 scrapers missing from research_sources (no auto-registration mechanism)

**Error:** Architect audit discovered 8 scrapers in `main.py SCRAPERS` had no corresponding `research_sources` row: `prtimes`, `maruhiro`, `hankyu_umeda`, `daimaru_matsuzakaya`, `google_news_rss`, `nhk_rss`, `mot`, `transit_store`.

**Root cause:** The "new scraper checklist" listed only 3 steps (create → SCRAPERS → dry-run). Registering in `research_sources` was never documented. The `researcher.py` `known_urls` filter depends on this table to avoid re-surfacing already-implemented sources.

**Fix:**
- Manually inserted all 8 missing rows into `research_sources`.
- Added `_warn_unregistered_scrapers()` to `main.py` (non-dry-run guard): compares SCRAPERS keys against `research_sources.scraper_source_name`, emits `⚠️ WARNING` for any gap. Runs every CI cycle.
- Updated `Scraper Implementation` section in `SKILL.md` to make step 3 ("register in research_sources") explicit.

**Lesson:** "Register in research_sources" is step 3 of the new scraper checklist — as mandatory as registering in SCRAPERS. Any omission now produces a visible CI WARNING within 24 hours.

---
## 2026-05-01 — healthcare 新分類加入 group_lifestyle（commit `bd89c57`）

**變更：** 新增 `healthcare`（健康・醫療 / Health & Wellness / ヘルスケア）分類至 `group_lifestyle`。

**教訓：** Category Update Protocol 6 步驟全部完成（union + CATEGORIES + CATEGORY_GROUPS + zh/en/ja）。group_lifestyle 是此類分類的正確歸屬。

---
## 2026-05-01 — 分類標籤重命名：nature、history

**變更：**
- `nature` → 風土・水果・環境永續 / Nature, Produce & Sustainability / 風土・果物・SDG
- `history` → 歷史・文化遺產・根源 / History, Heritage & Roots / 歴史・文化遺産・ルーツ

**教訓：** i18n 標籤改名只需更新三個 `web/messages/*.json`，category key 不變，DB 資料不需異動。group labels 亦同（`group_arts`、`group_lifestyle`、`group_knowledge` 等鍵值不變，只改顯示文字）。

---
## 2026-05-01 — 分類群組大調整（commits `a07b792`, `5b66c33`）

**變更：**
- `competition`（競技・競賽）、`workshop`（體驗・工作坊）從 `group_knowledge` 移至 `group_lifestyle`
- `exhibition`（展覽）、`books_media`（書・媒體）、`tv_program`（電視節目）從 `group_knowledge` 移至 `group_lifestyle`
- `group_knowledge` 調整後只剩：`business`、`academic`、`lecture`、`taiwan_japan`

**根本原因：** 分類設計初期 `group_knowledge` 定義不夠嚴格，把生活風格類別錯誤納入。

**修復：** 僅修改 `web/lib/types.ts` 的 `CATEGORY_GROUPS` 陣列，不需動元件代碼。

**教訓：** Category 群組重組只需改 `types.ts` 的 `CATEGORY_GROUPS`，因為 `AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx` 都從 `CATEGORY_GROUPS` 讀取（三檔共用 source，不需個別修改元件代碼）。

→ 已更新 `SKILL.md § Category Update Protocol — 群組重組`

---
## 2026-05-01 — Location filter 6-region 完全重寫（commit `b8dfe2b`）

**變更：** 地點篩選器從 `tokyo / other_japan / taiwan / online / tv` 改為 `tokyo / kanto / chubu / chugoku / online / tv`，地區判斷改用 address `ilike` marker 清單：

| 選項 | marker 清單 |
|------|------------|
| tokyo | 東京各區標記，或 address 為 null（預設東京）|
| kanto | 神奈川/埼玉/千葉/茨城/栃木/群馬/山梨/東北各縣/北海道 |
| chubu | 愛知/静岡/岐阜/長野/新潟/富山/石川/福井/大阪/京都/兵庫/奈良/滋賀/和歌山/三重 |
| chugoku | 広島/岡山/鳥取/島根/山口/九州各縣/四國各縣/沖縄 |
| online | location_name 含 オンライン |
| tv | location_name 含 電視頻道 |

**根本原因：** 原 `other_japan` 選項過粗，無法區分關東、中部、中国・九州。

**修復：** 三處同步更新：
1. `FilterBar.tsx` — 選項 options + i18n keys
2. `web/app/[locale]/page.tsx` — server-side OR query（`location_address ilike`）
3. `AdminEventTable.tsx` — state 型別 union literal + marker arrays + `getFiltered` + `sourceCountMap`

**教訓：**
- Location filter 有三處必須同步：FilterBar 選項、page.tsx server query、AdminEventTable state 型別。
- `filterLocation` state 型別（union string literal）必須跟 options 精確一致，TypeScript 不報錯但未知值會導致所有事件被過濾。
- 地區判斷改用 address `ilike` marker 清單，避免 NOT 邏輯漏網。

→ 已更新 `SKILL.md § Location Filter Three-File Sync Rule`

---
## 2026-05-01 — GITHUB_TOKEN 權限描述不一致（Issues 權限口徑分裂）

**問題：** 同一 repo 內對 fine-grained PAT 權限出現多種寫法（非標準 `&` 合併寫法、`Issues: write` 兩種混用），且部分文件未明確寫出 `Metadata: read`，導致配置判讀混亂。

**修復：** 將 code + docs + agent 口徑統一為：
- Fine-grained PAT：`Issues: write + Metadata: read`
- Classic token：`repo` scope

同步更新檔案：`scraper/update_source.py`、`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`、`.github/instructions/token-rotation.instructions.md`、`.github/agents/researcher.agent.md`、`.github/SECRETS_LIFECYCLE.md`。

**教訓：**
1. 安全/權限敘述變更必須「跨層原子更新」（runtime error message + docs + agent 說明）。
2. 不可讓非標準的 `&` 分隔權限寫法與 `Issues: write + Metadata: read` 長期並存。
3. public repo 文件中的權限例子必須可直接採用最小權限原則，避免誤導開過寬權限。

---
## 2026-05-01 — Admin Tab Nav 10 頁不一致（commit `1f37bb4`）

**問題：** 10 個 admin 頁面的 tab nav 內容互不一致。有些頁面有 quality tab，有些沒有；有些有 announcements tab，有些沒有。最嚴重的是 announcements/page.tsx 只有 5 個 tab，而 admin 主頁有 10 個。

**根本原因：** 每次新增 admin 子頁面（quality、announcements 等），只在部分現有頁面加入新 tab link，沒有統一更新全部頁面。Tab nav 是手動在每個頁面各寫一份，沒有共用元件。

**修復：** 統一全部 10 頁的 tab nav 為相同順序：Events → Announcements → Reports → Stats → Quality → Research → Sources → Users → Creators → SEO-AEO。加上 `flex-wrap` 防止行溢出。

**教訓：**
- 新增 admin 子頁面時，**必須同時更新全部現有 admin 頁面的 tab nav**。
- 驗證指令：`grep -o 'admin/[a-z]*' web/app/\[locale\]/admin/*/page.tsx | sort | uniq -c` 確認每個 route 出現次數一致。
- 未來可考慮抽出 `AdminTabNav` 共用元件（每頁的 active tab 用 span vs Link 區分，需 prop 傳入 current page）。

→ 已更新 `SKILL.md` § Admin Tab Nav Sync Rule

---
## 2026-05-01 — OG Image 英文標題截斷過短（commit `47ac1ee`）

**問題：** OpenGraph 圖片中英文標題被截斷過短，只顯示部分文字。

**修復：** 增加截斷字數上限（36 → 55），並為長英文標題新增 40px 字體大小層級（原本只有 72px / 54px 兩級）。

**教訓：** OG image 截斷閾值以英文為基準（字元窄、數量多），搭配字體縮小梯級，避免硬截斷。詳見 Architect history 同日條目。

---
## 2026-05-01 — 地址補齊功能 + Quality page 缺地址誤報修正（commit `590a80a`）

**問題：** Quality page「缺地址（非線上活動）」顯示 29 筆，但其中 18 筆是 gguide_tv 電視頻道事件（NHK、BS朝日等），這些沒有實體地址，屬於誤報。

**根本原因：**
- gguide_tv 事件的 `location_name` 存的是頻道名稱（如 "NHK総合1・東京"），未統一為「電視頻道」，導致 filter 無法排除。
- Quality check 最初未考慮「無地址是合理的」情境（TV 頻道、線上活動）。
- 剩下真正缺地址的事件（如 ssff 展映）有場館名但 scraper 沒抓地址欄位。

**修復：**
1. `quality/page.tsx`：`missingAddr` filter 排除 `source_name === "gguide_tv"` 和 `location_name.includes("電視頻道")`。
2. DB 補丁：21 筆 gguide_tv 事件統一 `location_name = '電視頻道'`。
3. 新工具 `scraper/enrich_addresses.py`：用 OpenAI gpt-4o-mini 查場館地址，`confidence=high` 才寫入，支援 `--dry-run` / `--source`；執行結果：8 筆成功（ssff ×6、google_news_rss ×2）。

**教訓：**
- **Quality check 必須考慮「無地址是合理的」情境**：新增缺欄位 check 時，先列出受影響 source_name 分組統計，確認哪些來源天然就沒有該欄位。
- 診斷缺地址問題：先用 `GROUP BY source_name` 找主因，避免一律標示為「待修」。
- `enrich_addresses.py` 模式可複用：任何有 venue name 無地址的來源都適用，`confidence` 欄位防止 LLM 亂猜地址。

→ 已更新 `SKILL.md` § enrich_addresses.py — 地址補齊工具 及 § Quality Page — 缺欄位誤報排除模式

---
## 2026-05-01 — AdminReportsTable bulk confirm 被另一個 agent 意外刪除並恢復

**問題：** commit `3d45de6`（「refactor(web): remove realtime subscription and bulk confirm from AdminReportsTable」）由非 Engineer agent 執行，在移除 Realtime subscription 的同時，一併刪除了先前實作的多選批量確認功能（`selectedIds`、`bulkConfirming`、`handleBulkConfirm`、勾選框、bulk action bar）。

**根本原因：** Agent 把 bulk confirm 視為「與 Realtime 捆綁的功能」一起移除，而非獨立功能。Realtime subscription 可以拆除，但 bulk confirm 是獨立 UX 功能，不應隨之消失。

**修復（commit `4c30ab3`）：**
- 恢復 `selectedIds: Set<string>` 和 `bulkConfirming: boolean` state
- 恢復 `handleBulkConfirm(rows: ReportRow[])` sequential loop（不用 `Promise.all`，因 `handleConfirm` 內有 `setSaving`）
- 恢復每筆 pending 行的勾選框：`<div className="flex items-stretch">` 包住 checkbox label + button
- 恢復 section header 右側 bulk action bar（`bulkCancelSelect`、`bulkConfirmSelected { count }`、`bulkConfirmAll { count }`）
- 批量按鈕文字改用 i18n keys，三個 messages 檔同步新增

**教訓：**
- **AdminReportsTable bulk confirm 是受保護功能**：`selectedIds`、`bulkConfirming`、`handleBulkConfirm` 不得被任何 agent 移除，除非 PRD 明確指示。
- 移除某功能（如 Realtime）時，必須逐項確認 diff 不包含無關功能的刪除。
- 診斷方式：`git log --oneline --all | head -15` 找到刪除 commit → `git show <hash> --stat` 確認刪除內容 → 從 SKILL.md 規格重建實作。

→ 已更新 `SKILL.md` § AdminReportsTable — Protected Feature: Bulk Confirm

---
## 2026-05-01 — AdminSourcesTable i18n 修復：Filter Labels 硬編碼中文

**問題：** `AdminSourcesTable.tsx` 的「狀態」、「全部」、「來源分類」、「編輯分類對照表」都是 hardcoded 中文，未走 `t()` hook。

**根本原因：** 初次實作時只顧功能，未套 i18n，後來也沒有 lint 規則報錯，因此一直沒被發現。

**修復：** 改為 `t("sourcesFilterStatus")`、`t("sourcesFilterAll")`、`t("sourcesFilterType")`、`t("sourcesEditTypeMap")`，三個 i18n 檔（zh/en/ja）同步新增對應翻譯。

**教訓：** TSX 中任何可見文字（filter label、button、placeholder、section header）都必須走 `t()`，禁止硬編碼中文/日文。新增 admin 元件時，應在實作完功能後立即對照 TSX 全文搜尋裸字串，統一轉換。

→ 已更新 `SKILL.md` § AdminSourcesTable — i18n 規則

---
## 2026-05-01 — CI workflow 改善：merger.yml 排程 + Node.js 24 opt-in

**修改：**
1. **merger.yml 新建（commit 85049b1）**：`workflow_dispatch` 手動觸發，只跑 `python merger.py`。`scraper.yml` 同時插入 "Run merger" 步驟（位於 `main.py` 後、`annotator.py --fix-reviewed` 前）。每日 CI 管道順序確立為 `main.py → merger.py → annotator.py → annotator.py --fix-reviewed`。
2. **Node.js 24 opt-in（commit 3cd06a9）**：`scraper.yml` 和 `merger.yml` top-level 加入 `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`，消除 `actions/checkout@v4`、`actions/setup-python@v5` 的 Node.js 20 deprecation warning（GitHub 強制遷移日：2025-06-02）。
3. **merger.yml 加排程（commit 4c999cb）**：3 個 cron `01:00 / 09:00 / 16:00 UTC`（JST 10:00 / 18:00 / 01:00），每次跑完 merger 後接著跑 `annotator.py` + `annotator.py --fix-reviewed`。

**教訓：**
- 任何使用 `actions/checkout@v4` 或 `actions/setup-python@v5` 的 workflow **都需要** top-level `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`。
- merger 跑完後必須立刻跑 annotator，否則合併事件以 `pending` 狀態滯留。
- 新建共用依賴的 workflow（如 merger.yml）時，必須同步檢查 scraper.yml 的所有步驟是否也需要加入（step parity rule）。

→ 已更新 `SKILL.md` § GitHub Actions Workflow Rules

---
## 2026-05-01 — `/admin/quality` Tester 首輪 FAIL：react-hooks/static-components

**問題：** `web/app/[locale]/admin/quality/page.tsx` 在 `QualityPage` render body 內宣告 `SectionHeader` 元件與 `eventLink` JSX helper，被 ESLint `react-hooks/static-components` 規則擋下，Vercel build 失敗。

**根本原因：** Next.js 15+ / React 19 把任何 PascalCase + 回傳 JSX 的函式視為 component；component 必須在模組頂層宣告，不能寫在另一個 component 的 render 內。`eventLink` 雖為 camelCase，但被當 `<EventLink />` tag 使用時也會被誤判。

**修復：**
1. `SectionHeader` 提升至模組頂層，需要的值改透過 props 傳入。
2. `eventLink` 重新命名為 `renderEventLink`，並改以函式呼叫 `{renderEventLink(e)}` 使用，不再寫成 JSX tag。

**教訓：** 詳細規則已寫入 `.github/skills/agents/engineer/SKILL.md` § TSX Component vs Helper。實作 admin / 後台多區塊頁面時，先把可重複使用的小區塊（header、link、badge）提到模組頂層，避免後續因 lint 補修。

> 註：本次事件最終隨 Tier 1 monitoring 撤銷一同 revert（commit `cf1e0a9`），但 lint 規則本身仍適用。

---
## 2026-05-01 — AEO 實作（Phase A/B/C partial）：llms.txt、IndexNow、Aggregation Pages、監控 Dashboard

**背景：** 為提升 AI 搜尋引擎可見度（Perplexity、ChatGPT Search、Claude），實作 AEO（AI Engine Optimization）三階段：
- Phase A：AI crawler 開放、`llms.txt`、全域 JSON-LD
- Phase B：活動詳情頁 BreadcrumbList + FAQPage、sitemap x-default
- Phase C（partial）：AEO 監控（`aeo_visits` 表 + proxy.ts 偵測 + Admin Dashboard）+ IndexNow 提交 + 主題聚合頁（城市 × 6 + 分類 × 所有）

**關鍵教訓：**

1. **proxy.ts 靜態文件 307 問題**：任何新增到 `web/public/` 的靜態文件（如 `llms.txt`、`93bf67...txt`），必須同步更新 `proxy.ts` matcher 排除 regex，否則 i18n middleware 307 重導至 `/zh/<filename>`。

2. **FAQPage 必須有可見內容**：Google 要求 FAQPage 內容必須在頁面上可見，JSON-LD 本身不夠。必須同時添加 `<dl>` visible section 與 JSON-LD，缺一不可。

3. **Migration 號碼衝突處理**：若兩個 migration 分配到相同號碼，採用 `b` 後綴（如 `029b_realtime_events.sql`），並在 SQL 檔案頂部加 comment 說明衝突原因。

4. **TSX 禁止 CJK 硬編碼**：城市描述、分類描述等所有中文/日文文字必須走 `t()` hook 從 `messages/*.json` 讀取，絕不硬編碼在 `.tsx`。靜態分析不會報錯，但翻譯缺失時頁面會顯示 raw key。

5. **getTranslations namespace 靜默失敗**：使用 `tXxx("key")` 前必須確認 `messages/zh.json` 中對應 namespace 存在。Namespace 不存在時 `t()` 靜默返回 raw key string，不拋錯，難以發現。

6. **IndexNow 需兩個環境變數**：`INDEXNOW_KEY`（API key）和 `NEXT_PUBLIC_SITE_URL`（用於建構 event URL）。兩者都需加入 `.github/workflows/scraper.yml` 的 env 區塊。`upsert_events()` 改為返回 `list[str]`（新活動 UUID 列表）供 IndexNow 使用，原有呼叫方只需更新 unpack。

7. **Aggregation page i18n 命名**：城市頁用 `cities.*` namespace，分類頁用 `categoryDesc.*` namespace。必須同時更新三個 messages 文件，否則非 zh locale 的頁面顯示 raw key。

**新增文件：**
- `web/public/llms.txt` — AI engine index
- `web/app/robots.ts` — 9 個 AI crawler 規則（GPTBot, OAI-SearchBot, Anthropic-ai, Claude-Web, PerplexityBot, Google-Extended, cohere-ai, Meta-ExternalAgent, YouBot）
- `web/app/layout.tsx` — 全域 JSON-LD @graph (WebSite + SearchAction + Organization)
- `web/app/[locale]/events/[id]/page.tsx` — BreadcrumbList + FAQPage JSON-LD + 可見 `<dl>` FAQ section
- `web/app/sitemap.ts` — x-default alternates + 城市/分類頁（priority 0.7, daily）
- `supabase/migrations/029_aeo_visits.sql` — bot/ai_referral 追蹤表
- `web/proxy.ts` — BOT_PATTERNS（17）+ AI_REFERER_HOSTS（10）+ fire-and-forget logAeoVisit()
- `web/app/[locale]/admin/aeo/page.tsx` — Admin AEO Dashboard（6 summary cards + bot/AI referral tables）
- `web/public/93bf676318c36c2420ea9af290aa15a65efab2134bee2caf6f29037b06b4d9b9.txt` — IndexNow key 驗證文件
- `scraper/indexnow.py` — submit_urls(), event_urls()
- `web/app/[locale]/cities/[city]/page.tsx` — 6 城市 × 3 locales，CollectionPage + ItemList JSON-LD
- `web/app/[locale]/categories/[category]/page.tsx` — 所有分類 × 3 locales，CollectionPage + ItemList JSON-LD

---
## 2026-05-01 — AEO proxy.ts Edge Middleware 規則固化（daily review）
**新增/修改：**
- 新增 `## AEO Monitoring — proxy.ts Edge Middleware Rules` 段落
- Fire-and-forget logging rule：不能 `await`/`throw`，用 `void fetch()` + 原生 Web API
- Bot / AI referral 雙層偵測模式（BOT_PATTERNS + AI_REFERER_HOSTS，UA 優先）
- 靜態文件排除規則：`public/` 新文件必須同步加入 matcher regex
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — agent 將非遷移文件誤置 migrations/ 目錄（daily review）
**新增/修改：**
- `## Database` 段落新增 `supabase/migrations/` 只能放 `NNN_name.sql` 的明文規定
- 記錄事故案例：`027_smoke_test.sql`、`027_VALIDATION.md`、`027_VERIFICATION_REPORT.md` 被 agent 誤建於 `migrations/`
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-05-01 — AdminReportsTable Realtime 自動刷新修復

**問題**：報錯審核頁面前端有 `supabase.channel().on("postgres_changes", ...).subscribe()` 訂閱，但 INSERT/UPDATE 事件從未觸發，頁面不會自動刷新。

**根本原因**：`event_reports` 資料表從未加入 `supabase_realtime` publication。Supabase Realtime 需在資料庫層先執行 `ALTER PUBLICATION supabase_realtime ADD TABLE <table_name>` 才會廣播變更；前端訂閱程式碼本身不夠。

**修復**：
1. 新建 `028_realtime_event_reports.sql`：`ALTER PUBLICATION supabase_realtime ADD TABLE event_reports;`
2. 前端訂閱改為同時處理 INSERT（新報錯）和 UPDATE（確認/忽略），跨標籤頁即時同步。
3. 抽取 `fetchRow()` helper 避免 SELECT 子句重複。

**教訓**：
- Supabase Realtime 不是「開箱即用」：前端 `.on("postgres_changes", ...)` 不夠，資料庫層必須先 `ALTER PUBLICATION supabase_realtime ADD TABLE <table>` 才有效。
- 管理頁面須同時訂閱 INSERT + UPDATE，才能跨標籤頁同步確認/忽略狀態。
- 診斷方式：Supabase Dashboard → Database → Replication，確認目標表出現在 `supabase_realtime` publication 清單中。

*(補充：2026-04-30 的「AdminReportsTable Realtime subscription」條目教訓不完整，缺少「必須先 ALTER PUBLICATION」這個關鍵步驟。)*

---
## 2026-04-30 — AdminReportsTable 多選批量確認功能

**新功能**：待審核列表支援多選批量通過操作。`selectedIds: Set<string>` + `bulkConfirming: boolean` state；`handleBulkConfirm` 以 sequential `await for` loop 逐筆呼叫現有 `handleConfirm`，完成後清空 `selectedIds`。Section header 加 bulk action bar（flex justify-between），有勾選時顯示「通過已選取 (n)」和「取消選取」按鈕。

**關鍵技術決策**：
- `handleBulkConfirm` 用 sequential loop（不是 `Promise.all`），因為 `handleConfirm` 內部有 `setSaving` state 更新，parallel 會造成 state race。
- checkbox label 用 `onClick={(e) => e.stopPropagation()}` 防止冒泡觸發行展開/收合。
- 原本 `<button className="w-full ...">` 必須重構成 `<div className="flex items-stretch"> + checkbox label + <button className="flex-1 ...">`，因為 checkbox 不可作為 button 的子元素（違反 HTML 規範）。

**教訓**：
1. 在列表行加入 checkbox 時，若整行原本是 `<button>`，必須拆成外層 `<div>` + checkbox label + `<button flex-1>`；不能把 checkbox 放在 button 內。
2. 批量操作按鈕建議放在 section header 右側（flex justify-between），比底部 footer bar 更直覺。
3. 若 bulk handler 呼叫的子函數內部有 `setSaving` state 更新，必須用 sequential loop，不可用 `Promise.all`。

---
## 2026-04-30 — AEO 優化（Phase A + B）：proxy.ts 靜態文件排除規則

**錯誤**：新增 `web/public/llms.txt` 後，`/robots.txt`、`/sitemap.xml`、`/llms.txt` 請求被 i18n middleware 307 重導向至 `/zh/robots.txt` 等路徑，回傳 404。

**原因**：`proxy.ts` middleware matcher 缺少 `robots.txt`、`sitemap.xml`、`llms.txt` 的排除規則。Next.js i18n middleware 預設對所有未排除路徑加上 locale 前綴，不區分靜態文件與動態路由。

**修復**：在 `proxy.ts` matcher 排除正規表示式中補上 `robots\\.txt`、`sitemap\\.xml`、`llms\\.txt` 等靜態文件模式。

**教訓**：任何新增到 `web/public/` 的靜態文件，必須同步在 `proxy.ts` matcher 中加入排除規則，否則 i18n middleware 會 307 重導所有請求到 locale 前綴路徑（如 `/zh/llms.txt`）。

---
## 2026-04-30 — Satori emoji 靜默失敗導致 OG image 空白

**錯誤**：`opengraph-image.tsx` 回傳 HTTP 200 + `content-type: image/png` 但 `content-length: 0`。

**原因**：Satori（`ImageResponse` 底層）完全不支援任何 emoji，包括 📅📍🇹🇼🏳️‍🌈。遇到 emoji 時靜默失敗，不拋錯，直接回傳空 PNG。

**修復**：兩輪修改——第一輪移除 CATEGORY_EMOJI map 和品牌 🇹🇼，第二輪用 Python 掃 `ord(c)>127` 找到殘留的 📅📍，全部換成純 ASCII 文字標籤（DATE/AT/FILM/ART 等）。

**教訓**：Satori OG image 中完全不能使用任何 emoji。診斷方法：`fetch(...).arrayBuffer()` 檢查 `byteLength`，0 = Satori 靜默失敗。搜尋殘留：`python3 -c "..."` 掃 `ord(c)>127`。

---
## 2026-04-30 — AdminReportsTable Realtime subscription

**新功能**：報錯審核頁面新增 Supabase Realtime subscription，訂閱 `event_reports` INSERT 事件。有新報錯時自動 fetch 完整資料（含 events join）並插入列表頂部，無需手動刷新。

**教訓**：Supabase Realtime 在 `"use client"` 元件中使用 `supabase.channel(...).on("postgres_changes", ...)` 即可，記得 `useEffect` cleanup 時呼叫 `supabase.removeChannel(channel)`。

---
## 2026-04-29 — AdminReportsTable: description 欄位缺少可編輯支援 [AdminReportsTable]

**Bug:** `description` 欄位未加入 `EDITABLE_FIELDS`，也未宣告 `TEXTAREA_FIELDS` 集合，導致問題回報審核時無法直接修改事件描述。

**Fix (4a40b9a):** 將 `description` 加入 `EDITABLE_FIELDS` Set；新增 `TEXTAREA_FIELDS` Set（含 `description`），讓 description 渲染為 `<textarea rows={3} className="resize-y ...">` 而非 `<input>`。

**Lesson:** `AdminReportsTable.tsx` 有兩個控制欄位編輯行為的 Set：`EDITABLE_FIELDS`（可編輯）和 `TEXTAREA_FIELDS`（長文字，用 textarea）。新增可編輯欄位時：加入 `EDITABLE_FIELDS`；若為長文字，**同時**加入 `TEXTAREA_FIELDS`。

---
## 2026-04-29 — AdminEventTable 日期範圍篩選器無法搜索未來活動 [AdminEventTable]

**Bug:** `filterTimeMode === "past"` 分支在 `getFiltered` 和 `sourceCountMap` 兩處都有 `isPast` 判斷（`end_date < today`），導致「搜尋特定期間」無法找到 end_date 在未來的活動。

**根本原因：** 日期範圍篩選邏輯把「過去期間」和「任意日期範圍」混在一起；且 `getFiltered` 和 `sourceCountMap` 邏輯不同步。

**Fix (7f00d4e):** 移除兩處的 `isPast` 限制，改為純粹的 from/to 日期邊界篩選；同時重命名 i18n 標籤為「搜尋特定期間」。

**Lesson:** 日期範圍篩選器的 from/to 應為純粹的日期邊界，不應附加「只搜過去」的語意。修改 `AdminEventTable` 篩選邏輯時，`getFiltered` 和 `sourceCountMap` **必須同時更新**。

---
## 2026-04-29 — AdminSourcesTable: `eventCountByType` and `typeCountMap` not applying status filter [AdminSourcesTable]

**Bug:** `typeCountMap` was added (commit `6b92c53`) with the status filter applied, but `eventCountByType` (a sibling IIFE computing active event counts per type) was NOT updated to apply the same filter. When users selected the `不適合` (not-viable) status, `typeCountMap` correctly showed 0 for all types, but `eventCountByType` still showed stale counts from all sources regardless of status — making the dropdown misleading.

Separately, `candidate`, `researched`, and `recommended` status values were added to the status `<select>` (commit `618f93a`) but the `getFilteredSources` filter logic only handled `implemented`, `not-viable`, and `has_issue`. The new status values had no guard, so selecting them showed all sources unfiltered.

**Fix (c52c737):** Extracted an identical `statusFiltered` array into `eventCountByType` (same guard logic as in `typeCountMap`). Also added explicit `candidate / researched / recommended` guards to both the `typeCountMap` status filter and the `getFilteredSources` IIFE.

**Lesson:** When two parallel IIFE/`useMemo` blocks compute counts for related UI dimensions (e.g. one counts sources-per-type, another counts events-per-type), they must apply the **identical** status-filter logic. Whenever a new filter option is added to `getFilteredSources`, grep for all sibling count computations and apply the same guard. Treat status filter guards as a **closed set** — adding `candidate` to one block requires adding it to ALL blocks in the same file that filter by status.

---
## 2026-04-29 — AdminSourcesTable 來源分類 select 顯示各分類條目數

**工作內容：**
- `AdminSourcesTable.tsx` 的「來源分類」select 每個 option 改為顯示 `{label} ({count})` 格式
- 新增 `typeCountMap` IIFE：套用狀態篩選（`filter`）但**不套用**分類篩選，計算每個分類的條目數
- `"all"` 選項不顯示數字；count 為 0 時也不顯示括號
- 邏輯與 `getFilteredSources` 中的 `peatix_organizer` / `effectiveTypeMap` 判斷保持一致

**教訓：**
- Filter dropdown 的各選項計數，應套用**其他**篩選條件（此處是狀態），但排除**自身**篩選條件（分類），才能讓使用者看到切換後的預期數量
- `"all"` 選項語意上是 total，不適合顯示數字（旁邊已有 `{filtered.length} 筆`）
- count 為 0 時不顯示括號，避免 UI 噪訊

---
## 2026-04-29 — Peatix Layer 3 擴充：新 agent_category 需同步 AdminSourcesTable

**工作內容：**
- `peatix.py` 加入 `_load_db_organizers()`、`_scrape_group_events()`，`scrape()` 加入 DB organizer 迴圈
- `discovery_accounts.py` 完整重寫為 4 槽每日輪流（slot 0-2=note.com，slot 3=Peatix 主辦者）

**教訓：**
- 每次新增 `agent_category` 到 DB（如 `peatix_organizer`）時，**同一 PR 必須**更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯，否則管理界面無法篩選新類型
- `discovery_accounts.py` 的 platform-aware upsert 依賴 `agent_category` 欄位作為路由機制：Peatix → `peatix_organizer`，note.com → `note_creator`
- 驗證入口：`python discovery_accounts.py --dry-run --slot 3`

---
## 2026-04-29 — AdminSourcesTable 分類對照表編輯器（localStorage 覆蓋層）

**新增功能：**
1. `SOURCE_TYPE_LABELS` 加入「📦 歸檔」選項（key: `"archived"`）
2. `typeOverrides` state，初始值從 `localStorage` 讀取（key: `source_type_overrides`）
3. `getFilteredSources` 改用 `effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }` — 使用者覆蓋優先
4. 新增 Modal：搜尋框、所有來源依分類→名稱排序、分類下拉、被覆蓋列綠色標示 + 「↩」還原、「儲存」/「取消」
5. 移除 `sources/page.tsx` 冗餘 `<h2>` 標題

**教訓：**
- 硬寫 ID→分類對照表需配合 localStorage 覆蓋層（`effectiveTypeMap = { ...defaultMap, ...userOverrides }`），讓管理者無需改程式碼即可重新分類
- Modal 必須區分 draft state（`draftOverrides`）與 committed state（`typeOverrides`）：取消不影響已儲存狀態
- `localStorage` key 慣例：`source_type_overrides`（snake_case，明確表示功能範圍）

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---

## 2026-04-29 — skills/engineer/ 反覆復活（stray dir）

**問題：** 子代理更新 engineer SKILL.md 時寫入 `.github/skills/engineer/SKILL.md`（舊路徑），而非 `.github/skills/agents/engineer/SKILL.md`（正確路徑）。同一 session 發生兩次。

**修復：** SKILL.md 頂部新增 `## ⚠️ CRITICAL: Canonical File Paths`，列出所有 agent 正確路徑。

**教訓：** 路徑遷移必須在 SKILL.md **頂部第一章節**加 CRITICAL 警告，否則子代理讀不到就走舊路徑。

---
## 2026-04-29 — AdminSourcesTable 分類對照表編輯器（localStorage 覆蓋層）

**新增功能：**
1. `SOURCE_TYPE_LABELS` 加入「📦 歸檔」選項（key: `"archived"`）
2. `typeOverrides` state，初始值從 `localStorage` 讀取（key: `source_type_overrides`）
3. `getFilteredSources` 改用 `effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }` — 使用者覆蓋優先
4. 新增 Modal：搜尋框、所有來源依分類→名稱排序、分類下拉、被覆蓋列綠色標示 + 「↩」還原、「儲存」/「取消」
5. 移除 `sources/page.tsx` 冗餘 `<h2>` 標題

**教訓：**
- 硬寫 ID→分類對照表需配合 localStorage 覆蓋層（`effectiveTypeMap = { ...defaultMap, ...userOverrides }`），讓管理者無需改程式碼即可重新分類
- Modal 必須區分 draft state（`draftOverrides`）與 committed state（`typeOverrides`）：取消不影響已儲存狀態
- `localStorage` key 慣例：`source_type_overrides`（snake_case，明確表示功能範圍）

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.

---
## 2026-04-29 - GitHub Actions resolver could not fetch actions/checkout@v4

**Error:** `.github/workflows/secret-rotation-reminder.yml` failed at parse/resolve stage with `Unable to resolve action actions/checkout@v4, repository or version not found`.

**Fix:** Downgraded action refs in the same workflow to resolver-friendly majors for older environments:
- `actions/checkout@v4` -> `actions/checkout@v3`
- `actions/setup-python@v5` -> `actions/setup-python@v4`

**Lesson:** If a workflow must run on older GitHub Enterprise resolvers or constrained action mirrors, prefer the latest major that is known to exist in that environment, and downgrade related core actions together to keep compatibility expectations consistent.

---
## 2026-04-28 — Multi-locale field editing: always expose all locale variants simultaneously

**Context:** `ReportSection.tsx` initially showed a single textarea pre-filled with the *current locale's* value when a user flagged a wrong field. A user pointed out that the Japanese original may be correct while only the Chinese or English translation is wrong. Showing one locale obscures which specific translation is faulty.

**Upgrade:** Changed the textarea to three stacked labeled textareas (中文 / English / 日本語), each pre-filled with the field's own locale column value. Users edit only the incorrect locale(s) and leave others unchanged.

**Type change:**
```ts
// Before
eventFields?: Partial<Record<WrongDetailField, string | null>>;
fieldEdits:   Partial<Record<WrongDetailField, string>>;

// After
eventFields?: Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string | null>>>>;
fieldEdits:   Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string>>>>;
```

**Submission format:** `fieldEdit:<field>:<locale>:<value>` — only non-empty edits are appended to `report_types`.

**Lesson:** When a UI component edits a field that maps to localized DB columns (`*_ja`, `*_zh`, `*_en`), **never show only the current locale's value**. Show all locale variants with language labels. This applies to any future correction/review UI (admin edit forms, report flows, feedback widgets). → Added to SKILL.md as **Multi-locale Edit Pattern**.

---
## 2026-04-28 — Report section: editable textarea per wrong-detail field

**Feature:** When a user checks a sub-field (name, date, venue, etc.) under "內容錯誤 / wrongDetails" in `ReportSection.tsx`, a textarea now appears pre-filled with the current localized event content. The user can edit the value before submitting; the edited text is stored as `fieldEdit:<field>:<value>` in `report_types` alongside the existing `field:<field>` entry.

**Implementation:**
- Added `eventFields?: Partial<Record<WrongDetailField, string | null>>` prop to `ReportSection`
- Added `fieldEdits: Partial<Record<WrongDetailField, string>>` state; populated on field checkbox toggle
- `toggleField()` now sets `fieldEdits[field] = eventFields?.[field] ?? ""` on check, and deletes the key on uncheck
- JSX: sub-field checkboxes moved from `<label>` wrappers to `<div>` with conditional textarea below each checkbox
- `handleSubmit` appends `fieldEdit:<field>:<value>` entries (max 500 chars each) when `edit.trim()` is non-empty
- `page.tsx`: passes `eventFields` using the locale-aware helpers `getEventName`, `getEventLocationName`, etc. already imported
- New i18n key `fieldEditHint` added to all three `messages/*.json` files

**Pattern replicated from:** `wrongSelectionReason` textarea — same pre-fill + clear-on-uncheck pattern.

**Lesson:** When reusing a textarea-on-checkbox pattern, extract the pre-fill logic into `toggle<X>()` so the JSX stays declarative. Avoid inline `onChange` that mutates state outside the toggle handler.

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.
