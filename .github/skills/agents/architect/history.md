# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-05-05 — 翻譯修正反覆失效：缺持久化鎖 + `enrich_person_names` desc_en 既有 bug 共同造成

### 問題
事件 `f970e4e3`（月老）使用者反映「先前花費非常多時間修理過，結果這條目怎麼又恢復沒有修改狀態了」。根本疑問：**為何修正過的事件會多次重複發生這種錯誤？**

### 根因分析（迴歸鏈）
1. **手動修正不寫 `field_corrections`**：使用者透過 SQL UPDATE 直接修翻譯欄位，但未同時插入 `field_corrections` row。沒有鎖定，下一次 `annotation_status` 被某種途徑（scraper diff / `--all` / `--fix-translations`）翻回 `pending` 時，`annotate_pending_events()` 用 GPT 重寫 `name_zh`/`name_en`/`description_*`，**所有人工修正瞬間蒸發**。
2. **`enrich_movie_titles` 失敗無 retry、無 WARN**：5/4 daily CI 當下 eiga.com lookup 失敗（網路或站點瞬斷），function 靜默 `continue`，沒有任何 log 提示「這個 movie 事件 lookup 失敗」。錯誤翻譯就此停留至下次成功運氣。
3. **`enrich_person_names` 對 `description_en` 永遠無法修正**：`description_en` 是 GPT 翻譯後的英文音譯（如 `Koo Kuan-Dong`），片假名字串根本不在 desc_en 中，`if ja_name in new_desc_en` 條件**結構性永不命中**，無論跑幾次 CI，desc_en 都不會被修正為 `Ko Chen-tung`。

### 修復（多層防線）
1. **`_fix_person_names_gpt_en()`**（annotator.py）：新增 GPT-based 修正路徑，鏡像 `_fix_person_names_gpt`，針對 desc_en 處理英文音譯 → 正確英文名。`enrich_person_names` 改用此函式。
2. **`_lock_fields_via_corrections()`** helper：在 `enrich_movie_titles` 與 `enrich_person_names` 成功 patch 後，自動 upsert `field_corrections` row，鎖定欄位。後續 annotator 主迴圈的 P1 保護（line 911 `_human_protected`）會跳過這些欄位。
3. **WARN 日誌**：`enrich_movie_titles` lookup 失敗時 logger.warning，CI log 中可見；`enrich_person_names` 找到人但未 patch 時也 WARN，避免靜默失效。
4. **既有 `f970e4e3` 修正手動寫入 `field_corrections`**：`name_zh`/`name_en`/`description_zh`/`description_en` 四欄已 lock，從此免疫於 AI 覆寫。

### 教訓
- **「靜默 continue」是反 pattern**：lookup/network 失敗必須 WARN，否則錯誤資料會持續上線數日無人察覺。
- **「直接字串替換」要驗證 source 與 target encoding**：原始片假名與已翻譯英文音譯不是同一字串，str.replace 永不命中。應走 GPT 語義修正路徑。
- **手動修正必須持久化**：任何透過 SQL UPDATE 修翻譯的操作，**必須同時** upsert `field_corrections`，否則下次 re-annotation 會清掉。已加入 architect Guard（`Manual Translation Fix Persistence Guard`）。
- **enrich 函式自動 lock**：成功 patch 等於官方權威值（eiga.com / Wikipedia），自動鎖定不會傷害正確性，反而防止 transient 失敗造成的迴歸。

---
## 2026-05-05 — `enrich_person_names` 對 description_en 修不到（音譯英文 vs 片假名）

### 問題
事件 `f970e4e3`（赤い糸 輪廻のひみつ / 月老）在 5/4 daily CI 跑過後，`description_zh`/`description_en` 仍含片假名/英文音譯人名（`ギデンズ・コー`、`Koo Kuan-Dong` 等），而非中文 `九把刀` `柯震東` 或正確英文 `Ko Chen-tung`。

### 根因（兩層）
1. **`enrich_movie_titles` 5/4 第一次 CI 失敗或時序問題**：標題仍是 GPT 直譯 `紅線 輪迴的秘密` / `The Red Thread`，未替換為 `月老` / `Till We Meet Again`。第二次手動執行立即修正，原因可能是 5/4 lookup 當下網路或 eiga.com 暫時失敗。
2. **`enrich_person_names` 對 description_en 邏輯有缺陷**：`description_en` 由 GPT 翻譯時已將片假名 → 英文音譯（如 `クー・チェンドン` → `Koo Kuan-Dong`），但 `enrich_person_names` 對 desc_en 採**直接字串替換片假名**（`if ja_name in new_desc_en`），片假名根本不在 desc_en 中，所以永遠無法修正。
   - desc_zh 用 GPT prompt 替換可成功（GPT 看得懂上下文），但 desc_en 沒有對等的 GPT 修正路徑。

### 修復
1. 立即執行 `python annotator.py --enrich-movie-titles`：標題修正為 月老 / Till We Meet Again。
2. 針對單筆事件呼叫 `lookup_person_names` + `_fix_person_names_gpt`：description_zh 修正人名為中文。
3. 手動 UPDATE description_en：`Koo Kuan-Dong` → `Ko Chen-tung`、`Wang Jing` → `Wang Ching`、補 `performer = '九把刀, 柯震東, 宋芸樺, 王淨'`。

### 教訓
- `enrich_movie_titles` 是 daily CI 每天跑的安全網，但仍會因臨時失敗漏修。設計時應加入「重試 / 留下失敗紀錄」機制，避免錯誤翻譯持續上線。
- **`enrich_person_names` 對 description_en 應改用 GPT 修正路徑**（同 description_zh），不能只靠 katakana direct-replace。這是既有 bug，已記入 SKILL.md「Person Name Enrich English Guard」。
- 手動修正後，可考慮把該事件 `annotation_status` 升為 `reviewed` 防止下次 CI 覆寫（本次未做，待觀察）。

---
## 2026-05-05 — location_address = location_name 在 9 個 scraper 中大範圍擴散（65 件受影響）

### 問題
修復 iwafu.py 之後，發現相同模式（直接複製 venue name 作為 location_address）存在於另外 8 個 scraper：kokuchpro、taiwan_matsuri、taioan_dokyokai、koryu、taiwan_festa、prtimes、jposa_ja、peatix、waseda_taiwan。DB 中共 65 件受影響事件。

### 根因
1. **annotator `_ai_or_existing()` 保護邏輯不區分「真實地址」和「venue 複製」**：只要 `location_address` 非 null，annotator 就保留現有值，不覆蓋。Scraper 寫入的錯誤值因此永久鎖定。
2. **沒有全局守則防止 scraper 複製**：修 iwafu 時才發現其他 scraper 有相同模式，事先沒有掃描所有 scraper。

### 修復（commit `9d6e0fc`）
- 9 個 scraper：移除所有 `location_address = venue/location_name` 的 fallback；若找不到真實地址則設 `None`
- peatix：在 Canonicalize 前加 guard `if location_address == location_name: location_address = None`
- DB：65 件 `location_address → null`，`annotation_status → pending`，等待 annotator 重新填充

### 教訓
1. **修完一個 scraper 後必須掃描所有 scraper**：grep `location_address.*=.*venue\|location_name` 找類似模式，而不是只修觸發案例。
2. **annotator `_ai_or_existing()` 是雙刃劍**：保護人工修正的同時也保護了 scraper 的錯誤。任何 scraper 寫入 `location_address` 都必須確保是真實地址，不能用 venue 做 fallback。
3. **Batch DB 修正命令**（掃描 + 修正）：
   ```python
   r = sb.table('events').select('id,location_name,location_address').execute()
   same = [e for e in r.data if e['location_address'] and e['location_address'] == e['location_name']]
   for e in same:
       sb.table('events').update({'location_address': None, 'annotation_status': 'pending'}).eq('id', e['id']).execute()
   ```

---
## 2026-05-05 — LINE 週報顯示日文標題 fallback（annotation_status 過濾缺失）

### 問題
LINE 週報中出現「赤い糸 輪廻のひみつ」（日文）而非「紅線 輪迴的秘密」（中文）。
ZH 訂閱者收到 `name_zh = NULL` 的事件，觸發 `name_ja` fallback。

### 根因
`weekly_line_broadcast.py` 的 `_fetch_upcoming_events` 未過濾 `annotation_status='pending'`。
新刮取的事件在 annotator 執行前 `name_zh`/`name_en` 為 NULL。
若廣播在每日 09:00 scraper+annotator pipeline **之前**手動觸發，pending 事件會進入 pool。

### 修復（scraper/weekly_line_broadcast.py）
在 `_fetch_upcoming_events` 加入 `.in_("annotation_status", ["annotated", "reviewed"])` 過濾，確保只有翻譯完整的事件進入廣播 pool。

### 教訓
- 廣播 query 必須加 `annotation_status` 過濾，不能假設所有 is_active 事件都已標注
- 規則已寫入 SKILL.md「LINE Broadcast Query Guard」

---
## 2026-05-04 — hakusuisha 詳情頁抓取截斷 + _JITSU_RE 偽匹配（venue/hours 第二輪）

### 問題
hakusuisha 三連修正後（commit `54a20d7`），`location_name`、`business_hours`、`organizer` 在下一次 scrape 仍全為 null。

### 根因（兩層）
1. **8000 字元截斷**：detail 頁原始抓取上限為 4000 字元，nav/menu 噪音消費了大部分預算，`■日時：`、`会場：`、`主催：` 等標籤出現在截斷點之後。雖然 `_T` HTMLParser 已過濾 script/nav，但頁面仍有大量其他噪音（導覽、廣告連結）佔用字元。
   → Fix：將上限從 4000 → 8000 字元。
2. **`_JITSU_RE` 偽匹配**：`_JITSU_RE.search()` 用來提取日時，但 scraper 自身在拼接 `raw_description` 時會先 prepend `開催日時: YYYY年MM月DD日` 前綴，`_JITSU_RE`（設計為匹配 `開催日時`）反而命中了自己加的前綴，而不是頁面原文的 `■日時：HH:MM〜HH:MM`，導致 `business_hours` 永遠為 null。
   → Fix：改用 `_TIME_RE`（專門匹配 `HH:MM〜HH:MM` 格式）直接搜索 `full_description`，繞過前綴干擾。

### 修復（commit `a0292a2`）
- `scraper/sources/hakusuisha.py`：字元上限 4000 → 8000；`_extract_cards()` 加 `_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE` 三個 regex；用 `_TIME_RE` 替代 `_JITSU_RE` 搜索 `full_description`

### 教訓
1. **Self-prepend 污染**：scraper 自己加的前綴（`開催日時: ...`）會干擾後續 regex，若用同一個 pattern 搜索整個 `raw_description`，應改用「不匹配前綴格式」的 pattern 或限定搜索範圍。
2. **字元預算驗證**：任何 detail-page scraper 加完 HTMLParser skip-tags 後，應實際列印截取後的文字長度與關鍵標籤位置，確認業務內容在預算內。
3. **Regex 偵測器作用域**：提取同一份文字的多個 regex（date vs hours）應明確區分作用域，避免同 pattern 匹配到 scraper 注入的中繼資料。

---
## 2026-05-04 — performer regex 假陽性掃描（純漢字限制）

### 問題
`_extract_performer_from_raw` 初版（commit `562a620`）對 295 件 performer=null 事件掃描時命中 3 件，人工複查發現全為假陽性：
- `評論家の龍應台` — 平假名 `の` 被納入名字字串
- `交流のあった萩原健太` — 上下文詞彙被納入名字字串
- `裕美` — 缺姓（`平野 裕美`），名字抓取不完整

### 根因
`_PERFORMER_INTRO_RE` 的 name 字元類過寬（排除清單 `[^\s・：:,、...]`），允許平假名（`の`、`あった`）被捕獲進名字組。`_MUKAE_RE` 的 `を迎え` 未覆蓋帶 `お` 的敬語形式（`をお迎え`）。

### 修復（commit `b2a8806`）
- 兩個 regex 的 name 字元類改為純漢字 `[\u4e00-\u9fff]{2,6}`：確保只抓 2-6 個漢字，平假名前綴 (`評論家の`) 無法進入
- `_MUKAE_RE` action 新增 `をお迎え`：覆蓋 `龍應台さんをお迎えし` 的敬語格式
- 人工確認：龍應台（`d3938822`）和 平野裕美（`719aac3d`）直接 DB 更新 + `field_corrections` 保護；`afb5f87e`（雙人活動）保持 null

### 教訓
1. **名字字元類應設計為最保守**：「排除壞字元」不如「只允許好字元」——`[\u4e00-\u9fff]` 明確比 `[^\s...]` 可靠
2. **每次 regex 修改後必須掃描現有資料驗證**：unit test 只測期望 case，掃描 DB 才能發現真實假陽性
3. **雙語名字需特別注意**：漢語人名（龍應台）常附帶職稱前綴（評論家の），regex 必須正確定位 separator

---
## 2026-05-04 — performer=null 儘管 raw_title 含 `氏を迎え`（event e72b2c15）

### 問題
`--backfill-performer`（200 件）執行完成後，event `e72b2c15`（精巡料理）的 performer 仍為 null。raw_title 明確含「料理研究家・宮武衣充氏を迎え」。

### 根因（雙層失敗）
1. **常規 annotation 流程從未寫入 performer**：`annotator.py` 的 `update_data` dict 根本沒有 `performer` key。`--backfill-performer` 是獨立 flag，不是每次標注的必要步驟。新標注的事件若未特別跑 backfill，performer 永遠 null。
2. **GPT 複合職稱漏抓**：`料理研究家・宮武衣充氏` 整體看起來像一個職稱片語，GPT 傾向忽略後面的人名部分，未提取 performer。SYSTEM_PROMPT 缺乏 `氏を迎え` 作為 performer 正向訊號的明示規則。

### 修復
- **即時**：直接 DB update `performer='宮武衣充'` + `field_corrections` 保護，防止再次被覆蓋。
- **系統性（本 session）**：
  1. `update_data` 加入 performer 三層 fallback：DB 既有值 → GPT (`annotation.get("performer")`) → regex (`_extract_performer_from_raw`)
  2. 加入 `_extract_performer_from_raw(raw_title, raw_description)` 確定性函數，覆蓋 `<role>・<name>氏`, `<name>氏を迎え`, `<name>さんを迎え`, `講師：<name>` 等 pattern
  3. SYSTEM_PROMPT 加 PERFORMER EXTRACTION RULES 段落（含 JSON schema 的 `performer` 欄位）
  4. SKILL.md 加 Performer Null Guard 章節

### 教訓
1. 新增任何欄位的標注後，必須確認 `update_data` **包含**該欄位——否則整個標注流程都無法填入。
2. 單靠 GPT 提取 performer 不可靠；`氏を迎え` / `役職・NAME氏` 等模式可用 regex 確定性提取，應作為 fallback。
3. `--backfill-performer` 僅補舊資料，不是 performer 欄位的設計保障——設計必須在主流程（`update_data`）中確保。

---
## 2026-05-04 — 「持續 0 件來源」診斷方法論 + 30 天監控閾值

### 問題
週報出現 13 個持續 0 件來源，需判斷是邏輯失效還是正常狀態。錯誤做法是立即 dry-run 或修改 scraper。

### 正確診斷步驟
1. 查歷史最高事件數（`last_nonzero = never` 不代表失效）
2. 分類：季節性 / 低頻設計 / 時機問題 / API key 缺失
3. 查 doc string 的預期產量（「1-2件/年」→ 0 件是常態）
4. 設定監控閾值，不要首週就干預

### 修復
`daily_report.py` 新增 `check_persistent_zero_sources(sb, window_start_30d)` —— 30 天內執行 30+ 次且從未產生事件的來源，在每日報告顯示 🔴 警告。

### 教訓
1. 新 scraper 首週 0 件：先查 doc string 預期產量，再決定是否需要調查
2. 季節性來源需在 doc string 標注活躍期（`# Active: Oct–Nov`）
3. 監控閾值優先於人工週報審查

---
## 2026-05-04 — GitHub Actions Cron Slot 精確匹配 Fallthrough + Scraper Notes 空白

### 問題 1：researcher/slot3 每週費用 $2.62（應為 $0.67）
`researcher.yml` 以 `-eq 21/3/9` 精確匹配 UTC 小時，但 GitHub Actions 有 1–2 小時延遲，導致所有 4 次 cron 全部 fallthrough 到 `else → slot3`。slot3 每天被研究 4 次，slot0/1/2 的 9 個 categories 完全未執行。本週僅 researcher/slot3 記錄 18 次執行、$2.62；slot0 只有 4 次（手動觸發）、slot1/slot2 無記錄。

### 問題 2：Scraper 失敗 notes 為空
`main.py` 的 except 區塊只寫 `success=False`，沒有帶入錯誤訊息到 `notes`。eurospace 3 次失敗（4/28–4/29）事後無法從 DB 知道失敗原因。

### 修復
1. `researcher.yml`：改用 6 小時視窗判斷（`-ge 18/12/6`）
2. `main.py`：except 區塊新增 `"notes": f"{type(exc).__name__}: {exc}"[:500]`

### 教訓
1. GitHub Actions cron 有 1–2 小時延遲；bash 中絕不用 `-eq` 精確匹配小時，改用 6 小時視窗
2. `else` 預設分支若覆蓋「所有其他情況」，部署後必須驗證每個 cron 槽位都觸發到正確分支
3. DB failure record 沒有 notes = 診斷盲點；`success=False` 必須搭配 `notes = ExceptionType: message`

---
## 2026-05-04 — Sub-Venue Parent Address Guard

### 問題
`iwafu` source の `878660a0` イベントで `location_address = location_name = "流山おおたかの森S.C. 森のまち広場"` が発生。
また `3cbe5682` では `森のまち広場`（S.C. 附属公共空間）が geocode 対象として使われ、親設施 `流山おおたかの森S.C.` の住所が得られなかった。

### 根本原因
SYSTEM_PROMPT の LOCATION ADDRESS RULE に以下 2 点が欠如していた：
1. 「子会場の location_address は親設施の住所を使え」という明示規則
2. 「location_address = location_name を禁止、失敗なら null を保て」という明示規則

### 修正
- `scraper/annotator.py`：LOCATION ADDRESS RULE 末尾に PARENT VENUE ADDRESS RULE 段落を追記
- `scraper/auto_qa.py`：`auto_qa_address_is_venue_name` 偵測器を追加（location_address == location_name を flag）

### 教訓
1. `location_address = location_name` は silent failure のシグナル。auto_qa で常時監視が必要
2. `○○施設内 ○○スペース` 形式の location_name は、子空間単体では geocode 不能。親設施を geocode 対象にすること
3. SYSTEM_PROMPT にルールがなければ GPT は既存動作を踏襲する（ベニュー名をそのまま address に echo する）

---
## 2026-05-04 — hakusuisha 三連修正：thin-content / start_date / business_hours

### 問題
hakusuisha scraper の 3 つの連鎖バグ：
1. HTMLParser が script/nav コンテンツをフィルタせず 2000 文字予算を無駄消費 → raw_description に日時情報が入らない
2. FIELD_SELECTORS["date"] が記事公開日を返す → start_date が全て誤植
3. business_hours が NULL → reviewed 保護で annotator も修正不能

### 根本原因
auto_generate Layer B scraper は「カード上の最近傍テキスト」を date キーに割り当てるが、それが公開日である場合に start_date が全て誤植になる。thin content 問題は HTMLParser の skip_tags 未実装が原因。

### 修正（3 commit）
- `4784266`: _T parser に skip_tags + 4000 char limit + annotator thin-content rescue
- `b3708e1`: _extract_event_dates() で ■日時 ラベルから実際の開催日を抽出
- `54a20d7`: _extract_hours_from_raw() + --fix-reviewed 拡張 + auto_qa_missing_hours

### 教訓
1. auto_generate scraper レビュー時は「date キーが公開日か開催日か」を必ず確認
2. HTMLParser thin content の判定は長さだけでなく「業務キーワード（日時/会場）の有無」で行う
3. reviewed 保護は「AI 上書き」を防ぐためのもの。確定性 regex 補填は safe — fix_reviewed モードで適用可能

---
## 2026-05-04（Session 3）— hakusuisha 三項修正：business_hours 防線、thin-content rescue、start_date 誤植

### business_hours 三層防線（commit `54a20d7`）
- **問題**：Playwright timeout → `raw_description=None` → GPT 無法提取 → `business_hours=NULL` → 事件標為 `reviewed` 後永遠不修復
- **根因**：`reviewed` 狀態保護整個事件不被覆蓋，但 `business_hours=NULL` 是「空欄位補填」，不是「有值欄位被覆蓋」，防線粒度過粗
- **修正**：
  - Layer A：`_extract_hours_from_raw(text)` 確定性提取三種 pattern（`HH:MM〜HH:MM`、`H〜H時`、`日時後的單一 HH:MM`）；加入 annotator `update_data` merge chain
  - Layer B：`--fix-reviewed` 模式擴展為也補填 `business_hours` 空值（確定性提取，非 GPT）
  - Layer C：`auto_qa_missing_hours` 偵測器（reviewed + null hours + HH:MM in raw_desc → event_report）
- **教訓**：`reviewed` 保護的語意應是「保護有值欄位不被覆蓋」，而非「完全凍結」。對「空欄位補填」應被允許，透過確定性（非 GPT）邏輯實現。防線設計需區分「保護有值欄位」vs「允許補填空欄位」。

### hakusuisha thin-content rescue（commit `4784266`）
- **問題**：`_fetch_detail_text_fallback()` 的 `_T` HTMLParser 未過濾 `<script>`/`<style>`/`<nav>`，JS 代碼消費了 2000 字元預算，`■日時：` 在 2000 字元之後 → `raw_description` 無效
- **根因**：`len(raw_description) > 0` 不等於「有效內容」—— JS 代碼也是非空文字。字元限制 2000 對含大量 JS 的頁面不夠
- **修正**：
  - `_T` parser 加 `_SKIP = frozenset({"script","style","nav","header","footer"})` + `_skip` 計數器
  - 字元限制 2000 → 4000（`_fetch_detail_text_fallback` + `_extract_cards` 兩處）
  - annotator 加 hakusuisha thin-content rescue：`source_name=="hakusuisha"` 且 `日時` absent 且 pre-extraction 都是 None → HTTP fallback 再取一次
- **教訓**：HTMLParser 不過濾 script/style 是靜默的效率殺手。Thin content detection 不能只看長度，需確認業務關鍵字（如 `日時`）是否存在。

### hakusuisha start_date 誤植修正（commit `b3708e1`）
- **問題**：`FIELD_SELECTORS["date"] = "span.note"` 抓取的是**記事公開日**（`YYYY.MM.DD` 格式），不是活動日。活動日在 detail 頁的 `■日時：YYYY年M月D日` 標籤中
- **根因**：auto-generated scraper 的 `FIELD_SELECTORS` 精度未在人工審查時確認；listing page 的日期欄位語意未驗證
- **修正**：
  - 新增 `_extract_event_dates(detail_text, card_year)` 函數，處理三種 pattern（同月 ・ 多日、同月 ／ 多日、兩個完整日期）
  - `_extract_cards()` 使用 `actual_start`/`actual_end` 取代公開日
  - 有 `日時`：prepend `開催日時:` 前綴；無 `日時`（公告文）：prepend `（記事投稿日: YYYY年...）` 年份錨點
- **教訓**：auto-generated scraper 的 `FIELD_SELECTORS["date"]` 可能是記事公開日而非活動日。listing page 日期欄位語意必須人工確認；活動日應從 detail 頁 `日時：` 標籤提取。

---
## 2026-05-04（Session 2）— selection_reason["ja"] 語言污染 + is_active 批次誤設再現

### selection_reason["ja"] annotator 語言品質控制（DB patch，無 commit）
- **問題**：`annotator.py --backfill-tier1` 對 49 筆事件產生 `selection_reason["ja"]` 為中文（而非日文），事件詳情頁日語 textarea 預填中文
- **根本原因**：GPT backfill prompt 語言控制不夠嚴格；backfill 後未執行品質驗證
- **修復**：Python 腳本用假名正則偵測（無假名字元 → 語言污染），逐一 GPT 翻譯修正
- **教訓**：
  1. **backfill 後必須執行多語言欄位 QA**：`selection_reason["ja"]` 必須含假名；缺假名即為污染
  2. Annotator plan 中若包含 backfill 步驟，必須明確列出「backfill QA 驗證」子步驟
  3. 防止方案：annotator 寫入 `selection_reason["ja"]` 前，加假名正則驗證（含假名才寫入，否則 fallback 到 zh 翻譯）

### is_active 批次誤設（342 筆）— 規則再度觸發
- **問題**：一次性腳本意外將所有 `end_date < today` 的事件設為 `is_active=False`，342 筆受影響
- **修復**：全部還原 `is_active=True`
- **備注**：此規則已在 SKILL.md 中記錄（Database Safety Rules § NEVER batch-set `is_active = False`），但仍再次發生
- **強化**：任何涉及批次 UPDATE `is_active` 的計畫必須先問「符合哪個合法來源？」；若無法對應兩個合法來源之一，拒絕執行

---
## 2026-05-04 — 兩次誤判 Engineer 越權 git push（其實是使用者並行 terminal 操作）

### 問題
連續兩次（commit `b2f046a` 035 / `0d4a0de` 037）看到 main 出現未經 Architect 授權的 commit，第一反應推論「Engineer subagent 違反禁止 git 操作的指令」，準備加規則禁止 Engineer 寫 git。實際追時序後兩次都是使用者在另一 terminal 並行手動 commit + push。

### 根因
Architect 在驗證階段沒先做時序交叉比對，看到陌生 commit + Engineer 剛 dispatch 過 → 直接推論為 Engineer 行為。Engineer 的 Changes Log 都只列檔案變更、沒宣稱做 git，但 Architect 沒把「報告未提 = 沒做」當證據。

### 教訓 / 規則
**陌生 commit 出現時，必跑「時序三步驟」再下結論：**
1. `git log --since=... --format='%cI %h %s'` 拉前後 30 分鐘 commit 列表
2. 找出夾住該 commit 的相鄰 commit，問使用者「這兩筆是你做的嗎？」
3. 只有當該 commit 在時序上孤立、且 Engineer dispatch 視窗完全涵蓋它時，才推論 Engineer

對應防呆：Engineer dispatch prompt 仍寫「禁止 git 操作」是合理 belt-and-suspenders，但**不要**因此跳結論說 Engineer 違規。working tree 乾淨可能是使用者剛 commit、不是 Engineer 沒做事。

---
## 2026-05-04 — auto_qa_missing_address 四類根本原因修正

### 問題
管理後台積壓 13 筆 auto_qa_missing_address pending，分 4 類根本原因。

### 修正
- P1（DB）：8 筆事件直接 fix，5 筆 dismiss；pending 歸零
- P2（taiwanshi）：_extract_venue() 新增 〒postal 括弧解析
- P3（auto_qa）：新增城市名/海外場地排除常數
- P4（note_creators）：JSON-LD fallback 解決 RSS 截斷

### 教訓
1. auto_qa 偵測器要分辨「無法提供地址」（新聞/城市名）vs「地址缺失」（有場地名但漏填）
2. note.com RSS 截斷是結構性問題，應在 scraper 層補 HTTP fallback，而非只靠 GPT
3. 學術場地常在 location_name 括號中嵌入完整地址 — scraper 要識別此模式

---
## 2026-05-02 — Quality 頁 location_prefectures 過濾靜默失效

### Quality Check 假陽性：client-side filter 依賴的欄位未包含在 select 中

- **錯誤**: 多城市活動仍出現在缺地址清單，client-side 的 `location_prefectures.length > 1` 過濾無效
- **根因**: `location_prefectures` 未加入 `.select()` 字串，欄位值為 `undefined`，`length > 1` 永遠不成立，過濾靜默通過所有資料
- **修正**: `QualityRow` interface 新增 `location_prefectures?: string[] | null`；DB `.select()` 加入 `location_prefectures`；同時補充 `.not("location_name", "ilike", "%youtube%")` 等線上活動排除條件
- **教訓**: client-side filter 依賴的欄位**必須先出現在 select 字串中**，否則欄位是 undefined，過濾條件靜默無效且不報任何錯誤

---
## 2026-05-02 — 相鄰 sticky 元素獨立定位導致捲動錯位（commit `bf22756`）

### Admin UI：多個 sticky 元素各自定位造成重疊

- **錯誤**: `AdminEventTable.tsx` 的篩選器（`sticky top-14`）和藍色批次操作列（`sticky top-0`）捲動後重疊錯位
- **根因**: 兩個相鄰 sticky 元素各自有不同 `top` 值，瀏覽器分別計算定位，導致捲動後互相覆蓋
- **修正**: 用共用 `sticky top-14 z-20 space-y-2 mb-3` wrapper 包住兩個區塊，讓它們作為一個整體固定在頂部
- **教訓**: 視覺上屬於同一群組的 sticky 元素應包在同一個 sticky wrapper 裡；各自不同 top 值的相鄰 sticky 元素是錯位的常見根因

---
## 2026-05-02 — RLS 阻擋父子事件跨 active 狀態連結（commit `f5931e0`）

### RLS 阻擋父子事件跨 active 狀態連結

- **錯誤**: 子事件詳情頁的父事件連結消失
- **根因**: RLS `"Public read events"` policy 限制 anon key 只讀 `is_active = true`；父事件下架後，SSR 用 anon key 查父事件名稱回傳 null
- **修正**: 父事件名稱查詢改用 service role key（server-side only，只查 `id, name_ja, name_zh, name_en` 欄位）
- **教訓**: SSR 頁面查詢「父子關聯」「存檔紀錄」等跨 active 狀態的資料時，必須用 service role key 繞過 RLS；anon key 查詢非 active 資料會靜默回傳 null，沒有任何 error。

---
## 2026-05-02 — 品質頁缺地址清單出現不可操作項目（commit `f5931e0`）

### Quality Check 假陽性：嵌入地址的 location_name 和短地名

- **錯誤**: `/admin/quality` 缺地址清單中出現無法補填的項目（如 `南山大学 Q棟103 (〒466-8673...)` 和 `東京`、`香港` 等短地名）
- **根因**: `location_name IS NOT NULL AND location_address IS NULL` 查詢未排除：(1) `location_name` 含 `〒`（地址已嵌入名稱）、(2) `location_name` 含 `オンライン`（線上活動）、(3) 短地名 ≤6 字無空格（只是城市/行政區，無具體地址可填）
- **修正**: DB 層加 `.not("location_name", "like", "%〒%")` 和 `.not("location_name", "ilike", "%オンライン%")`；client 層過濾 `loc.length <= 6 && !loc.includes(" ")`
- **教訓**: Quality check 設計必須同時考慮「有值但值的內容表示不需填」的假陽性情境。嵌入郵遞區號的欄位和短地名都是假陽性，應在 DB query 層排除。

---
## 2026-05-02（深夜 4）— MoN Takanawa 住所誤修正（幻覺スキャン false positive）

### MoN Takanawa 住所誤修正（幻覚スキャン false positive）
- **Error**: 幻覚スキャンで「住所が raw_description にない」→ 幻覚と誤判定。GPT 正解（三田3-16-1）を「高輪4-10-30」に誤って上書き。
- **Root cause**: 施設名「Takanawa」から住所を推論（施設名≠郵便住所地名）。公式サイトが JS レンダリングで住所非公開のため Web スクレイピングで確認できず。
- **Fix**: Google Maps 検索で正しい住所（港区三田3-16-1）を確認 → 即座に還元・reviewed ロック。
- **Lesson**: 幻覚スキャン結果は「嫌疑」のみ。修正前に必ず Google Maps で 30 秒確認。施設名と郵便住所は一致しないことがある（高輪ゲートウェイシティ内の MoN Takanawa の住所は「三田」）。

---
## 2026-05-02（深夜 3）— Quality Check 判斷基準錯誤、competition 類排除（commits `b82849d`→`80920ce`、`4ca383a`）

### 架構規則：Quality check 的判斷欄位必須與詳情頁顯示邏輯一致

- **問題一（commit `b82849d`→`80920ce`）**：`/admin/quality` 的缺地點 check 用 `location_address IS NULL`，但事件詳情頁顯示的是 `location_name`。191 筆事件有 `location_address` 但無 `location_name`；反之亦有只填 `location_name` 的事件。兩欄位不同，造成 quality check 結果與詳情頁顯示矛盾。
- **根本原因**：設計 quality check 時未先確認詳情頁實際 render 哪個欄位。`location_name` 是主要地點欄位（詳情頁 render 它），`location_address` 是次要欄位（輔助顯示用）。
- **修復**：查詢條件改為 `location_name IS NULL`；同時把 `gguide_tv` 的排除從 client-side filter 移到 DB query（`.not('source_name','eq','gguide_tv')`）。
- **架構規則**：
  > **Quality check 的判斷欄位 = 詳情頁顯示的欄位。** 設計 check 前先確認「前端哪個欄位 IS NULL 才真正影響使用者」，不可用非顯示欄位代替。

### 架構規則：Quality check 需排除「天生無法填寫」的事件類型

- **問題二（commit `4ca383a`）**：競賽/補助類活動（如「第22回日台文化交流青少年スカラシップ」）本質上是全國性活動，無實體地點，但被 quality check flag 為「缺地點」，無法操作消除。
- **根本原因**：quality check 設計時未考慮某些 category 的活動天生不符合該 check 條件（競賽、補助、線上直播等）。
- **修復**：加 `.not('category','cs','{"competition"}')` 排除含 `competition` category 的事件。
- **架構規則**：
  > **設計 quality check 時，同步確認「哪些事件類型天生不需要此欄位」並明確排除。** 無法消除的 flag = 無意義的噪音，應在 DB query 層過濾。

### 缺地點排除清單（`qualityMissingAddr` query 截至 2026-05-02）
| 排除條件 | 原因 |
|---------|------|
| `source_name = 'gguide_tv'` | 電視節目，無實體場地 |
| `category` 含 `competition` | 競賽/補助，全國性活動 |

---
## 2026-05-02（晚，二）— locationOverseas namespace bug、分類標籤調整、新增分類（commits `049edd8`、`a4a6f75`、`7567ef0`、`8aee4de`、`24fcb3c`、`b62b385`、`dfc5aaf`）

### 架構規則：next-intl i18n key 必須放在正確 namespace
- **問題**：用 `/tmp/*.py` 腳本新增 `locationOverseas` 時，腳本寫 `data["locationOverseas"] = label`，結果 key 放到 JSON 頂層，而不是 `filters` namespace。FilterBar 用 `useTranslations("filters")` 呼叫 `t("locationOverseas")` 時找不到 key，next-intl production build 回傳 key 名稱字串，導致 FilterBar 渲染異常，預設「進行中」timeMode 消失。
- **根本原因**：`/tmp/*.py` 修改腳本不了解 i18n namespace 結構，直接操作頂層 `data["key"]` 而非 `data["filters"]["key"]`。
- **修復**（commit `049edd8`）：三語言 JSON 全部把 `locationOverseas` 從頂層移入 `filters.{}` 內。
- **架構規則**：
  1. 任何修改 `web/messages/*.json` 的腳本，新增 filters namespace 的 key 必須用 `data["filters"]["key"] = value`，絕不能用 `data["key"] = value`。
  2. 新增 i18n key 後，立即用 grep 確認 key 出現在正確 block（行號約 10–40）而非頂層（行號 400+）：`grep -n "newKey" web/messages/zh.json`
  3. Next.js production build 對 missing key 回傳 key name 字串（不拋錯），這是 next-intl 的靜默失敗模式，需靠 grep 或 UI 目視確認。

### 分類標籤調整（label-only rename）
- `senses` zh：台灣感性 → 台灣感性・認同（commit `a4a6f75`）
- `senses` en：Taiwan Senses → Taiwanese Identity & Sensibility（commit `7567ef0`）
- `senses` ja：台湾の感性 → 台湾の感性・アイデンティティ（commit `7567ef0`）
- `competition` ja：スポーツ・競技大会 → スポーツ・コンテスト（commit `8aee4de`）
- **操作規則**：label-only rename 只動三個 `messages/*.json`，不動 `types.ts`（Category union、CATEGORIES、CATEGORY_GROUPS 不變）。

### 新增分類（6 location 同步更新）
- `folklore`（民俗・歲時 / Folklore & Seasonal Customs / 民俗・年中行事）→ group_arts（commits `24fcb3c`、`b62b385`）
- `scholarship`（補助・獎學金 / Grants & Scholarships / 助成・奨学金）→ group_knowledge（commit `dfc5aaf`）
- **操作規則**：新增 Category 值必須 6 location 同步（`types.ts` × 3 位置 + 三語言 `messages/*.json` × 3），在單一 commit 完成，不拆分。

---
## 2026-05-02（深夜 2）— Annotator scraper 優先序統一、location_url 條件寫入、PR Times 日期幻覺、IDE JETRO 線上活動（commits `c747484`、`eaab464`、`fb568c4`）

### 架構規則：annotator 欄位優先序統一（scraper 優先）
- **問題**：`annotator.py` 對 `location_name/address`、`business_hours`、`is_paid`、`start_date`/`end_date` 都是「GPT 優先，DB 次之」——只要 GPT 有推斷值，就會蓋掉 scraper 取得的正確資料。
- **根本原因**：annotator 設計時未區分「GPT 可信度高於 scraper」與「scraper 可信度高於 GPT」的欄位。
- **修復**（commits `c747484` + `eaab464`）：翻轉以下欄位為 scraper 優先、GPT 只補空值：`location_name`、`location_address`、`business_hours`、`is_paid`、`start_date`、`end_date`。
- **架構規則**：已更新 Annotator Scraper-Priority Guard（SKILL.md）。翻譯欄位（name_zh/en、description_*）仍由 GPT 生成，這是正確分工。

### 架構規則：annotator location_url 條件式寫入（commit `fb568c4`）
- **問題**：`location_url` 不在 annotator `update_data` 內 → 每次 annotation 都不寫入，即使 GPT 從文字提取了場地官網也丟失；但若直接加入且不加 null guard，GPT 的 null 輸出會蓋掉 Admin 手填值。
- **根本原因**：`location_url` 兼具兩種寫入來源（GPT 從文字提取 + Admin 手填），設計上衝突。
- **修復**：GPT prompt schema 新增 `location_url`，指示「僅從文字提取，禁止推測」；`update_data` 條件式寫入（`_loc_url = event.get("location_url") or _str(annotation.get("location_url"))`），僅在有值時寫入，null 不回寫 DB。
- **架構規則**：已更新 SKILL.md point 5（location_url 改為條件寫入，而非完全排除）。

### 資料修復教訓：PR Times 發布日 ≠ 活動日期
- **問題**：event `e45d4022`（台湾＆沖縄フードイベント）`start_date=2026-02-25`，為 PR Times 發布日；實際活動日期 `3月11日〜16日` 在 raw_description 正文中。
- **根本原因**：`prtimes.py` scraper 使用文章發布日作為 `start_date`；annotator 無法從沒有 `開催日時:` header 的 raw_description 正確推斷活動日期。
- **修復**：直接 DB update（`start_date=2026-03-11`、`end_date=2026-03-16`），補充 raw_description header，設 `annotation_status='reviewed'`。
- **防範**：prtimes scraper 應嘗試從正文 regex 提取活動日期，並在 raw_description 標記「プレスリリース発信日:」以讓 GPT 區分發布日與活動日。

### 資料修復教訓：線上活動 location_name=null
- **問題**：event `86efda2a`（オンデマンド講座, source=`ide_jetro`）`location_name=null`，前端無場地顯示。GPT annotation 未識別為線上活動。
- **根本原因**：`annotation_status='annotated'` 的 GPT 在 location 欄位為空時，不會主動補「オンライン」——需要 raw_description 中有明確文字提示。
- **修復**：直接設 `location_name='オンライン（オンデマンド）'`（含 zh/en 翻譯），設 `reviewed`。
- **架構規則**：線上活動 scraper（特別是 `ide_jetro`、`connpass`、`doorkeeper`）應主動判斷活動形式並設 `location_name='オンライン'`。Annotator SYSTEM_PROMPT 應加入規則：若活動明確為線上，`location_name` 應設「オンライン」或相應詞彙（オンデマンド / ライブ配信 / ウェビナー）。

---
## 2026-05-02（深夜）— UI 預填、Realtime badge、Quality page 清理（commits `c3fe0bc`、`4a71258`、`cd4cc29`）

### 架構規則一：Server Component + Realtime 分離模式（commit `4a71258`）
- **問題**：`AdminTabNav` 是 Server Component，pending reports badge 在 SSR 時抓取一次後靜止不動，報告提交後 badge 數字不更新。
- **根本原因**：Server Component 的資料在 SSR 時固定，無法在客戶端保持即時 state。
- **架構規則**（新增至 SKILL.md）：Server Component 中任何「動態計數器 / badge / 狀態指示」如果需要即時性，**必須**拆出為獨立 Client Component，接收 `initialCount` 做 SSR 初始值，再由 Supabase Realtime 訂閱維護更新。
- **拆分模式**：`AdminTabNav`（Server Component）→ 查詢初始 `pendingCount`（SSR）→ `<AdminReportsBadge initialCount={n} />`（Client Component）→ 訂閱 Realtime。

### 架構規則二：無操作 Quality section 應直接移除（commit `cd4cc29`）
- **問題**：Quality page「expired-but-active」欄位白天時段永遠有值（archive cron 一天只跑一次），點擊後無任何操作可執行。
- **根本原因**：archive cron 一天僅執行一次，白天過期的事件必然殘留在此清單。
- **架構規則**：Quality check section 如果沒有對應的可操作 action（fix button / batch action），且數值會永遠有值而非暫時性，**應直接移除**，不應保留純資訊性的永遠有值清單。

### UI 教訓：修正建議欄位應預填目前值（commit `c3fe0bc`）
- `ReportSection.tsx` 新增 `currentCategories` prop，使用者勾選「wrongCategory」時 `suggestedCategories` 自動預填事件目前分類。
- **UX 規則**：所有「修正建議」類欄位都應以目前值為預設，降低使用者操作負擔。

---
## 2026-05-02（晚）— 5 件修復：scraper retry、子活動欄位、health_check、annotator 日期覆蓋

### 摘要
本次 session 共 5 個跨層修復，最重要的教訓是 **annotator 日期覆蓋問題**。

### 架構層教訓：annotator 日期覆蓋（重要 guard）
- **問題**：`annotator.py` 對 `start_date`/`end_date` 的合併策略是「GPT 優先，DB 次之」（`annotation.get("start_date") or event.get("start_date")`）。手動修正日期後若把 `annotation_status` 設為 `'pending'`，annotator 重跑時 GPT 會從 `raw_description` 自由文字猜日期並覆蓋修正值。
- **根本原因**：`raw_description` 缺少結構化 `開催日時:` header 時，GPT 依賴散落在文章中的任意日期字串（包含錯誤的舊日期）。
- **架構規則**（新增至 SKILL.md）：
  - 手動修正日期後，**必須選擇以下其一**：
    - Option A：同步在 `raw_description` 前面加入 `開催日時:` header → 再設 `annotation_status='pending'`
    - Option B：直接設 `annotation_status='annotated'`（跳過 re-annotation）
  - 任何需要「手動修正 + 自動重跑」的資料修復流程，設計時必須確保 annotator 有明確的結構化欄位可依賴，不能只靠自由文字推斷。

### 其他修復（無新架構規則，歸 Scraper Expert 管轄）
- taiwanbunkasai：HTTP retry（HTTPAdapter + Retry）
- taiwanshi：子活動解析邏輯（`_parse_reports()` + `parent_event_id`）
- database.py：新增 `get_event_id_by_source()` helper
- health_check.py：Check 4（gnews fallback date）+ Check 5（tokyoartbeat URL-date mismatch）

---
## 2026-05-02（下午）— デニス・リン展 場地幻覺：annotator 不應對已知場館做 fallback 推測

### 架構層教訓：annotator 不應對場地資訊做 fallback 推測
- **問題**：活動 `1e375d6c`（デニス・リン展, source=`tokyoartbeat`）場地顯示為「東京都現代美術館」（錯誤），正確為「Yukikomizutani, TERRADA ART COMPLEX II 1F, 品川区東品川」。
- **根本原因**：`raw_description` 僅含英文藝術家簡介，無任何場地資訊。Annotator GPT prompt 中有 LOCATION ADDRESS RULE（「如果你知道就填」），GPT 對高知名度場館（東京都現代美術館、森美術館）過度自信地從訓練知識猜測，完全跳過「資訊不足」的保守路徑。
- **架構規則**（新增）：
  1. **Scraper 層責任**：凡有結構化 API 可取得場地資訊的 source（如 tokyoartbeat Contentful API），scraper **必須**在 `raw_description` 開頭附加場地 header（会場・住所・開放時間・入場料），否則 annotator 必然推測失敗。
  2. **Annotator prompt 原則**：LOCATION ADDRESS RULE 的「如果你知道就填」只應適用於已在 `raw_description` 中出現的明確資訊，而非訓練知識推斷。高知名度場館是最大的 hallucination 風險來源。
  3. **資料修復路徑**：場地錯誤需從原始 API（Contentful / official site）取得資料並手動 DB update，再補充 `raw_description` header 防止下次重覆錯誤。

---
## 2026-05-02（下午）— generate.py load_dotenv、not-viable 來源判定、Admin 篩選預設值、eurospace lookup_movie_titles（commits `d94fc80`、`29046ad`、`f905ee2`）

### auto_scraper/generate.py load_dotenv 修復（commit `d94fc80`）
- **問題**：`python -m auto_scraper.generate` 本機執行崩潰：`SUPABASE_URL required`。
- **根本原因**：`generate.py` 沒有 `load_dotenv()` 呼叫；CI 用 GitHub Actions secret 所以不受影響。
- **修復**：在 import 區塊後加入 best-effort `load_dotenv(Path(__file__).parent.parent / ".env")`，使 `try/except ImportError` 包圍以防非 dotenv 環境。
- **教訓**：任何有獨立 CLI 入口（`-m module` / `__main__`）的 Python module，必須在頂部加 `load_dotenv()`。CI 有 env var 時 load_dotenv 為 no-op，不影響 CI。

### source 126/148 標記 not-viable（純 DB 操作）
- source 126（TAP）：React FullCalendar SPA，事件 DOM 動態渲染，Playwright 選不到日期欄位 → `not-viable`。
- source 148（Zepp Tokyo）：Cloudflare JS challenge，Playwright 被攔截；頁面無標準活動 URL pattern，無法解析 source_id → `not-viable`。
- **操作**：直接 `UPDATE auto_scraper_status='not-viable', auto_scraper_failed_reason='...'`，不需 auto_generate pipeline。
- **新增判定規則**：
  - Cloudflare bot protection → not-viable（JS challenge 無法繞過）
  - SPA 動態行事曆（React/FullCalendar）→ not-viable（初始 HTML 無事件 DOM）

### Admin 篩選預設值修復（commit `29046ad`）
- **問題**：AdminEventTable 預設 filter 為 `active`，管理員進頁面看不到 pending / inactive 資料。
- **修復**：預設改為 `all`。
- **教訓**：Admin 管理介面預設應設 `all`；`active` 適合面向使用者的頁面，不適合後台管理。

### eurospace.py 加入 lookup_movie_titles（commit `f905ee2`）
- import `lookup_movie_titles`，在 `Event` 建構前呼叫，填入 `name_zh` / `name_en`。
- 同時更新 `.github/skills/agents/scraper-expert/SKILL.md`（cinema scraper 採用狀況表）及 `scraper-expert/history.md`。
- 本次 commit 為本地未推送狀態（main 分支 local commit）。

---
## 2026-05-02 — record_links JSONB bug、Pass 3 孤兒誤殺、name_ja_locked 設計、活動紀錄 UI（commits `0cdad90`、`180c495`）

### record_links JSONB bug（緊急修復）
- **問題**：`database.py` 用 `json.dumps(links)` 把 Python list 序列化後傳給 Supabase，JSONB 欄位存入字串而非陣列，前端 `.map()` crash → HTTP 500。
- **修復**：直接傳 Python `list` 物件，移除 `json.dumps()`。
- **教訓**：Supabase Python SDK 對 JSONB 欄位自動序列化 Python `list`/`dict`，**絕對不能先用 `json.dumps()` 序列化**，否則存入字串而非 JSONB（雙重編碼）。

### merger.py Pass 3 孤兒誤殺（緊急 hotfix，程式碼尚未修復）
- **問題**：Pass 3 孤兒清除邏輯誤殺了有效父事件（`00ae1ea8`、`dfb490c8`）的全部子活動（共 12 筆）。
- **緊急修復**：手動 `UPDATE is_active = True` 還原 12 筆子活動。
- **根本原因**：Pass 3 只看「sub 的 parent 是否 inactive」，未確認父事件的 inactive 是否由正確的合併造成（可能是誤合併）。
- **⚠️ 程式碼尚未修復**：下次 Pass 3 執行仍可能再次誤殺。需加保護：只有父事件在 `secondary_source_urls` 非空（真正被 Pass 1/2 合併）時，才允許清除孤兒子活動。
- **暫行方案**：若再次發生，立即執行 `UPDATE is_active=True WHERE parent_event_id = '<uuid>'`。

### name_ja_locked 機制設計（commits `0cdad90`、`180c495`）
- **問題**：annotator GPT 覆寫 scraper 從 `題目:` 欄位精準抓取的學術論文標題，截斷副標題並加通俗後綴「に関する講演会」。
- **設計決策**：新增 `name_ja_locked` boolean（migration 034 / Event dataclass / database.py / annotator.py）。`True` 時 annotator 保留現有 `name_ja`，翻譯/分類仍正常生成。
- **教訓**：判斷依據為「標題來源是定義式欄位（has-an-exact-value）vs 自由文字推斷（described-in-text）」；前者應 lock，後者讓 annotator 改善。

### 活動紀錄 UI feature（commit `0cdad90`）
- 事件詳情頁「結束日期」欄位：事件已結束且 `record_links` 非空時，顯示藍色「活動紀錄 ↗」連結。
- 三語 i18n 同步：`recordLinksBadge` key 加入 zh/en/ja.json。
- 同時手動合併兩筆重複事件（815dd841 ← e4a0edcc），活動レポート URL 存入 `record_links[{recommended: true}]`。

---
## 2026-05-02 — competition 標籤更名 + overseas 篩選器新增（下午）

### competition 標籤更名（commit f3cae57）
- zh: `競技・競賽` → `競賽・運動`；en: `Competition & Contest` → `Sports & Competition`；ja: `コンテスト・大会` → `スポーツ・競技大会`
- 只修改 zh/en/ja.json，**不需動 `types.ts`**（`Category` union value `competition` 未改）
- 教訓：分類標籤改名（非新增/刪除）= i18n-only 工作，無需 TypeScript 驗證

### overseas 篩選器新增（commit 8055f85）
- **三個檔案必須同時更新**：`FilterBar.tsx`（option）、`AdminEventTable.tsx`（型別聯集 + filter 邏輯 + option）、`web/app/[locale]/page.tsx`（server-side 查詢分支）
- page.tsx overseas 分支使用 `ilike '%城市名%'` 對 `address` 比對；台灣不是日本都道府縣，**不使用 `location_prefectures`**
- `OVERSEAS_MARKERS` 陣列（16 個台灣城市）在 `page.tsx` 與 `AdminEventTable.tsx` 兩處必須完全一致
- 教訓：AdminEventTable.tsx 有三個位置需改動（型別聯集、filter 邏輯、`<select option>`），只改其一會有 TypeScript 可過但邏輯錯誤的靜默 bug

---
## 2026-05-02 — Promotion 後 `scraper_source_name` 缺失，後台來源關聯斷裂

**問題：** auto_generate 完成、PR merge 後手動 promote 兩個來源（id=150 TIFF、id=151 台湾フェスタ），`/admin/sources` 後台顯示 0 筆活動、無法觸發 Run Scraper。

**根本原因：** promotion 流程（`status → implemented`）沒有填寫 `research_sources.scraper_source_name`。後台 API 靠此欄位 JOIN `scraper_runs` 顯示統計；auto_generate pipeline 只建立 scraper 檔案，不自動填此欄位。

**修復：** 手動 Supabase UPDATE — id=151 → `scraper_source_name='taiwan_festa'`、id=150 → `scraper_source_name='tiff_jp'`。

**教訓：** Promotion checklist 必須包含：填寫 `research_sources.scraper_source_name = <scraper key>`。已加入 SKILL.md § Auto-Generate Promotion Checklist。

---
## 2026-05-02 — Auto-Research Pipeline 設計、語言規則修正、Heartbeat 暫緩

### 變更摘要

**auto_research.py 實作（新增）**
- `scraper/auto_scraper/auto_research.py`（380 行）：自動評估 candidate 來源，score ≥ 0.70 → researched，score < 0.30 → not-viable，中間值維持 candidate。
- feasibility = "medium" + --create-issue → 自動建立 GitHub Issue 並升為 recommended。
- 架構完全照 `generate.py` pattern（AssessError / dataclasses / cooldown / mock-llm）。

**DB Migration 033_auto_research.sql**
- 新增 3 欄位：`auto_research_status` / `auto_research_attempted_at` / `auto_research_score`。
- 已在 Supabase Dashboard 執行完畢。

**CI Workflow 設計（分離原則）**
- `auto-research.yml`（00:30 JST）→ `auto-generate.yml`（01:00 JST），獨立於 `scraper.yml`。
- 決策：新 pipeline 失敗不得影響主爬蟲排程，因此絕不加入 `scraper.yml`。

**generate.py 兩處修改**
- eligibility：`"easy"` only → `"easy" OR "medium"`
- 新增 `BatchOptions` + `run_batch()` + `--batch` / `--max-sources` CLI flags

**daily_report.py：新增「待審核 PR」段落**
- 查詢 `auto_scraper_pr_url IS NOT NULL AND status != 'implemented'`
- 每天 02:00 JST 的 email 顯示待 merge 的 auto-generated PR 清單

**architect.agent.md 語言規則修正**
- 問題：Architect 模式預設用日文回覆，忽略 `copilot-instructions.md` 的繁體中文規定。
- 修正：在 `architect.agent.md` 最上方加入「## 語言規則：所有回覆必須使用繁體中文」。

### Heartbeat Pipeline（auto PR 建立）暫緩原因

識別出以下風險尚未解決：

1. **Prompt Injection 風險**：`generate.py` 把 sample HTML 直接送入 LLM prompt，HTML 中的 `<!-- SYSTEM: ignore... -->` 可能操控 LLM 輸出，導致惡意程式碼自動 commit 進 repo。
2. **sandbox 驗證不足**：只檢查 `events_found >= 1`，未驗證 `source_id` 穩定性與 `start_date` 正確性。
3. **main.py 衝突**：多個 auto-generated PR 同時存在會造成 `SCRAPERS` 列表 merge conflict。

### 教訓

- 分離 CI workflow 的判斷依據：只要新 pipeline 的失敗模式與主爬蟲無關，就應使用獨立 workflow file。
- LLM 處理外部 HTML 前必須先 sanitize（移除 `<script>`、HTML comment、`<meta>` 等標籤），這是 auto-PR pipeline 的先決條件。
- Agent 的語言設定必須在 agent 檔案本身明示，不能依賴 `copilot-instructions.md` 的全域規則——Architect 模式有自己的 system prompt context，會覆蓋全域設定。

---
## 2026-05-02 — 允許台灣舉辦但針對日本訪客的活動進入系統（commit `012ec72`）

**背景：** 地點過濾邏輯把所有台灣地點活動無條件排除，導致日台交流旅遊活動（訪台ファムトリップ、日台交流ツアー）全部漏掉。

**修改：**
- `go_taiwan.py`：`_is_japan_event()` 加入例外——活動在台灣但含 `TAIWAN_FOR_JAPANESE_KW`（`ファムトリップ`、`日本人向け`、`日台交流ツアー` 等）則保留（return True）。
- `prtimes.py`：台灣地點過濾區塊加入同樣例外，`body_text` 或 `title` 含 `_JAPAN_VISITOR_KW` 則不 skip。
- `annotator.py`：Location Address Rule 第 6 條補充：台灣地點保留真實台灣地址（不轉換格式），適用 `tourism` category。

**架構決策：** 地點過濾的設計原則是「收與日本受眾相關的活動」，而非「物理上在日本的活動」。台灣在地舉辦但專為日本人設計的活動（訪台旅遊、日台交流ツアー）是 Radar 的核心價值之一。

**教訓：** 關鍵字清單 `TAIWAN_FOR_JAPANESE_KW` 目前較短，未來可擴充：`台湾ツアー`、`訪台`、`台湾研修`、`台湾旅行` 等。每次新增 source 時若有台灣地點過濾，應審視是否需要此例外。

---
## 2026-05-02 — Auto-scraper Phase 2.1/2.2/2.3 教訓彙整（commits `b6e1768`、`f9eff43`、`d23be68`）

**Lesson 1（Phase 2.1 — `b6e1768`）：SYSTEM_PROMPT 必須真的把 `spec_schema.json` 注入訊息**
- Bug：prompt 寫「matching the spec_schema.json (provided)」，但 schema 從未被讀檔或加進 messages。GPT-4o 三次重試都漏 `base_url`。
- 修：模組初始化載入 `SPEC_SCHEMA_TEXT`，user message 開頭注入 schema，並列出必填欄位 checklist。
- **可推廣規則**：plan-review 時，凡 prompt 文案出現「matching X provided」必須 grep 確認 X 真的在 messages 陣列裡，不是只「被引用」。

**Lesson 3（Phase 2.1/2.2）：失敗路徑必須持久化 forensic artifacts**
- Bug：success path 寫六種檔（spec/generated/prompt/dry_run/sample/meta），失敗路徑什麼都不寫。Phase 2.1 補 prompt+sample+meta，Phase 2.2 補 spec+generated+dry_run（sandbox-failed）。
- **可推廣規則**：任何多失敗模式 pipeline（spec-invalid、sandbox-failed、llm-error、budget-exceeded）每條失敗路徑都必須寫足夠 artifacts 供離線除錯。最便宜做法：無條件寫 artifacts，僅 DB status 區分成敗。

**Lesson 5：Researcher hints 在 Phase 2 是「實質必要」而非 optional**
- 證據：今日 batch e2e 6 個候選——只有 Artist Cafe Fukuoka（有 `li.article-list` hint）成功，其餘 5 個（Zepp/SSFF/Fukuoka Now/Blue+/TAP-NY，無 selector hint）4 LLM 幻覺 + 1 站點 timeout。Phase 2 success rate **17%（1/6）**。
- **規則更新**：`researcher.agent.md` 已將 `--card-selector-hint` 標記為「feasibility=easy 時實質必要」。CLI（`update_source.py`）保留 optional 不破壞既有腳本，但 agent doc 強制要求。

**Lesson 7：失敗路徑的 cost/retry 累計儀表壞掉（Phase 2.4 TODO）**
- Bug：Phase 2.3 spec-invalid 經過 3 次重試後，`meta.cost_usd = 0.0`、`meta.retries = 0`，但 log 證實 3 次 OpenAI 呼叫已發生。retry loop 累計欄位只在 success return 之前更新。
- **可推廣規則**：當 function 對 success/failure 回傳不同 shape，instrumentation（cost/time/count）必須放 `finally` 或共用累加器，而非僅在 success-only return 之前更新。

---
## 2026-05-02 — 分類系統新增 `documentary`、`parenting`；`gender` 標籤調整（commits `6c53347`、`7c157a6`、`db7e1d7`）

**變更摘要：**
- `documentary`（紀錄片）加入 `group_arts`（commit `6c53347`）
- `parenting`（親子）加入 `group_society`（commit `7c157a6`）；同批將 `gender` zh 標籤由「性別議題」改為「性別」
- `gender` en 標籤：`Gender Issues` → `Gender`（commit `db7e1d7`）

**每次分類更新必須同步的 6 處（原子性）：**
1. `web/lib/types.ts` — `Category` union 型別
2. `web/lib/types.ts` — `CATEGORIES` flat array
3. `web/lib/types.ts` — `CATEGORY_GROUPS`（放入正確 group）
4. `web/messages/zh.json`
5. `web/messages/en.json`
6. `web/messages/ja.json`

完成後必須執行 `cd web && npx tsc --noEmit`，確認 0 error 才能 commit。

**教訓：**
- `multi_replace_string_in_file` 的 `oldString` 改 union type 時必須含 ≥3 行前後文，否則可能截掉相鄰成員（參見 Architect SKILL.md § Category Union Change Guard）。
- i18n JSON 含非 ASCII 字元時，必須用 Python json-module 腳本編輯，不可用 `replace_string_in_file`（參見 Engineer SKILL.md § i18n JSON File Editing — Unicode Safety Rule）。

---
## 2026-05-02 — Overseas (Taiwan cities) location filter 設計決策（commit 最新）

**背景：** 新增「海外（台灣各城市）」地點篩選選項，讓用戶可篩選在台灣各城市舉辦的活動。

**架構決策 A（Taiwan city markers 不需前綴守衛）：**
台灣城市名稱（台北、台中、高雄…）直接存放在 `address` 欄位，與日本地點格式完全不同來源。不需要 `.startswith()` 或前綴守衛——台灣城市名不會是日本地名前綴。改用 `ilike '%城市名%'` 直接比對即可。

**架構決策 B（`OVERSEAS_MARKERS` 必須同步維護）：**
16 個台灣城市 markers（台北/台中/高雄/台南/新竹/嘉義/花蓮/台東/基隆/宜蘭/桃園/屏東/南投/彰化/雲林/澎湖）需在 `page.tsx` 與 `AdminEventTable.tsx` 兩處保持完全同步；兩處邏輯一旦分叉，過濾結果就會不一致。

**教訓：**
- 海外 filter 是「地理範圍擴充」，不是「特殊類型」——不需要 `other_japan` exclusion；直接用城市 markers 比對即可。
- 新增地點篩選前，永遠要確認 DB 中確實有足夠數量的匹配事件。

---
## 2026-05-02 — Daily Dev Report + WIP tracking 架構決策（commits `0ee713d`、`f56c4e0`、`96834f8`）

**背景：** 設計每日 02:00 JST 自動寄送開發摘要報告的 CI 流程，並整合 WIP 追蹤功能。

**架構決策 A（wip.md 放在 `.github/` 而非 `scraper/`）：**
`wip.md` 屬於開發狀態文件，非 scraper 業務邏輯。存放在 `.github/wip.md`，`daily_report.py` 用 `Path(__file__).parent.parent / ".github" / "wip.md"` 跨目錄讀取——清楚表達「這是 repo 層的文件，不是 scraper 層的」。

**架構決策 B（completed item 靜默略過，超過 26 小時不顯示）：**
WIP 已完成項目只在完成後 26 小時內顯示為「昨日完成」，超過則靜默略過。避免報告被過時的 completed 項目佔滿。

**架構決策 C（Passive push 優先於 Admin UI）：**
每日 dev report 採 GitHub Actions + Gmail SMTP（被動推送），符合 Admin UI Necessity Check 的「passive push 優先」原則。報告涵蓋昨日提交、爬蟲結果、待處理事項、安全日誌四個 section。

**教訓：**
- WIP 日期格式規則必須精確：`最後更新: YYYY-MM-DD`，且需同時支援中文冒號（：）和英文冒號（:）。regex `r"最後更新[:\uff1a]\s*(\d{4}-\d{2}-\d{2})"` 可涵蓋兩種格式。
- GitHub Actions Gmail SMTP 需要 `GMAIL_USER`、`GMAIL_APP_PASSWORD`（App Password，非一般密碼）、`DEV_REPORT_EMAIL` 三個 secrets。

---
## 2026-05-02 — annotator 架構決策：google_news_rss Playwright 文章補抓（commits `9510a05`、`9a0414a`）

**背景：** google_news_rss scraper 的 `_extract_start_date()` 原先在找不到日期時 fallback 到 `pub_date`（文章發布日）。因 RSS `<description>` 永遠只有標題短文，幾乎每筆都觸發 fallback，造成 40 筆 `start_date=pub_date` 的錯誤資料。修正方向：scraper 端改回傳 `None`，由 annotator 取得正確日期。

**架構決策 A（scraper 端：None 優先 fallback）：**
聚合新聞來源（Google News RSS、NHK RSS）的 pub_date ≠ 活動日期，scraper 不可作為 start_date fallback。正確作法：找不到日期回傳 `None`，讓 annotator pipeline 處理。

**架構決策 B（annotator 端：共用 Playwright browser 實例）：**
- 只在 `source_name == "google_news_rss"` 且 `start_date IS NULL` 時觸發 Playwright fetch。
- 整個 annotator run 共用一個 `Browser` 實例（loop 前啟動、`finally` 關閉），避免每筆重啟的高延遲。
- `raw_description` 欄位**不更新**（in-memory only），保留原始 RSS 文字的不可變性。
- 失敗時（timeout / paywall / DNS）gracefully fallback 到原始 snippet，不中斷 pipeline。

**架構決策 C（連結失效事件：直接 is_active=False）：**
`source_url` 已失效（DNS failure / 404 / domain expired）的事件直接設 `is_active=False`，不嘗試保留或修補。

**教訓：**
- 「資料品質修正」與「日期補抓」應分層處理：scraper 只負責「有就填、沒有就 None」；annotator 負責增補語意資訊（包含透過 Playwright 補抓原文）。兩層職責混淆（scraper 自行 fallback 到語意無關欄位）是本次問題的根本原因。
- 共用 Playwright 實例 pattern 可在 annotator 中複用於其他需要「補抓外部頁面」的場景。

---
## 2026-05-01 — 「電視節目 (tv)」地點篩選選項移除（commit `2989940`）

**背景：** FilterBar 與 AdminEventTable 都有 `<option value="tv">` 地點篩選選項，但選取後結果永遠為零。原因是 `gguide_tv` 事件的 `location_name` 已改為存放實際頻道名稱，而非「電視頻道」字串，與篩選邏輯完全不匹配。

**修正：** 移除 `FilterBar.tsx`、`AdminEventTable.tsx` 的 tv `<option>`；移除 `page.tsx` 中 `location === "tv"` 的 Supabase 查詢分支；移除三個 i18n 檔案中的 `locationTv` key。

**根本原因：** 地點篩選選項的值（如 `"tv"`）未能對應實際存在於 DB 的 `location_name` 格式，成為無效選項。電視/媒體內容應透過「分類」篩選（`category = report` 或 `report`）而非地點篩選。

**教訓：**
- 新增地點篩選選項前，必須先 DB 查詢確認有足夠數量的匹配事件（`SELECT count(*) WHERE location_name = 'xxx'`）。
- 地點篩選選項的值必須對應 scraper 實際寫入 DB 的 `location_name` 格式，不可假設。
- 電視/媒體節目應透過分類篩選，而非地點篩選。

---
## 2026-05-01 — 批次 `is_active = False`（依 end_date）誤關 342 筆事件

**背景：** 在 terminal 執行臨時批次腳本，將所有 `end_date < today AND is_active = True` 的事件全部設為 `is_active = False`。首頁大量事件消失，用戶立即察覺。緊急補救：執行反向 patch，將所有 `end_date < today AND is_active = False` 的事件復原為 `is_active = True`，共影響 342 筆。

**根本原因：** 對 `is_active` 欄位語意理解錯誤。`is_active` 代表「管理員是否主動隱藏」，**不代表「活動是否已過期」**。過期事件（`end_date < today`）依然需要保留在網站上供使用者查閱；前端 `FilterBar` 的「顯示已結束活動」選項負責控制能見度。

**修正：** 執行 DB patch 復原所有被誤關的事件。`is_active` 只有兩個合法寫入來源：
1. 管理員在 admin 頁面手動關閉特定事件
2. `merger.py` 合併重複事件時停用次要事件

**教訓：** 永遠不可依 `end_date < today` 批次設定 `is_active = False`。任何涉及 `is_active` 的批次 UPDATE，必須先確認符合上述兩個合法來源之一。

---
## 2026-05-01 — gguide_tv channel name 改版：UI 判斷應依賴 `source_name` 而非 `location_name`（commits `19427e3`、`c017462`）

**背景：** 原 TV番組地址欄特判以 `event.location_name === "電視頻道"` 作條件。後來 `location_name` 改為存放實際頻道名稱（如「歌謡ポップス」），UI 邏輯因依賴可變內容欄位而失效，需同步修正。

**修正：** 地址欄判斷改為 `event.source_name === "gguide_tv"`（結構性欄位，永遠不變）。同批修正 i18n 標籤：`event.location` zh「場地・頻道」、`event.address` + `admin.address` zh「地點」，`event` namespace 與 `admin` namespace 必須同步。

**教訓：**
- **UI 條件判斷：source_name 優先於 location_name**。`source_name` 是結構性識別欄位，`location_name` 是可顯示的內容欄位；以 `location_name` 做邏輯分支，資料修正後 UI 會靜默失效。
- **i18n namespace 隔離**：`event`（前台）與 `admin`（後台）是獨立 JSON namespace，標籤修改必須同時更新兩處（×3 語言 = 6 個 key）。
- 此條目**取代**先前的「TV番組地址欄顯示規則（`location_name === "電視頻道"`）」教訓——新正確做法是 `source_name` 判斷。

---
## 2026-05-01 — auto-scraper Phase 2 sandbox：env scrubbing 必須用 allowlist（commit `a0606fe`）

**背景：** Phase 2 LLM-codegen 後在 subprocess 跑生成的 scraper 做 dry-run 驗證。env 必須阻止 LLM 生成的程式存取 `SUPABASE_*` / `OPENAI_API_KEY` / `GITHUB_TOKEN` / `LINE_*`。

**選擇：**
- ❌ Blacklist（pop 已知 secret keys）：未來新加 `.env` 變數一律遺漏，一個漏掉 = 洩漏。
- ✅ Allowlist：只放行 `PATH` / `HOME` / `PYTHONUNBUFFERED` / `PLAYWRIGHT_BROWSERS_PATH` / `TMPDIR` / `LANG` / `LC_ALL`，其他全部不傳。新加 `.env` 變數自動被排除。

**教訓：跑「不可信／自動生成」程式時，env 隔離一律 allowlist。** Blacklist 需要持續維護，allowlist 是 fail-closed 預設。

---
## 2026-05-01 — temp file 清理：try/finally + atexit 雙保險（commit `a0606fe`）

**背景：** Phase 2 sandbox 把 LLM 生成的 scraper 複製成 `_auto_<name>.py` 讓 subprocess `import`，跑完要刪。

**單一機制不足：**
- 只用 `try/finally`：subprocess 被 SIGKILL 或 unhandled exit 時不執行。
- 只用 `atexit.register`：normal flow 期間異常分支不一定觸發。

**修正：兩者並用。** `try/finally` 處理正常與例外路徑，`atexit.register(cleanup)` 是進程死亡時的最後防線（defense in depth）。任何 codegen / fetch-render / 暫存檔流程都應遵循同樣 pattern。

---
## 2026-05-01 — LLM 定價常數需季度性重新驗證（commit `a0606fe`）

**背景：** `scraper/auto_scraper/generate.py` 寫死 GPT-4o 定價：`INPUT $2.50/1M`、`OUTPUT $10.00/1M`，預算 `$1.50/source`，作為 sandbox abort 守門。

**風險：** OpenAI 定價會調整；常數寫死且無自動驗證，過時後預算守門失準。

**對策：**
- 程式內以註解標注「verify against current OpenAI pricing」。
- Architect session checklist 新增：審 LLM-cost 程式時，比對當前 OpenAI 公開定價頁。
- 任何新加的「LLM 計費 + 預算守門」功能，定價常數必須集中在單一檔案，避免散落各處。

---
## 2026-05-01 — auto-scraper 各 Phase 必須嚴格分離 mutation surface（commit `a0606fe`）

**設計原則：** Phase 2 codegen + sandbox 故意 **不** 做以下事：
- 不 register 進 `SCRAPERS`
- 不 open PR
- 不寫入 `events` DB

只 update `research_sources` 的 status 欄。這個邊界是讓 Phase 3（會 open PR）能被安全 review 的前提——Phase 3 之前所有產出都是檔案級 artifacts，沒有 production 影響。

**通則：** 設計後續 auto-* 功能（auto-merge / auto-deploy / auto-fix）時，**每個 phase 的 mutation surface 必須在 plan 階段明確列出並上鎖**。把「unsafe codegen」與「safe activation」放在不同 commit / 不同 phase / 不同 reviewer，是讓 LLM 自動化能在 production 安全運行的核心紀律。

---
## 2026-05-01 — Researcher Phase 1.3 source_profile hints 是 Phase 2 啟動條件（commit `7d62b52`）

**背景：** Phase 2 auto-codegen 只處理 `feasibility='easy'` AND `url_verified=true` AND `status='researched'` 的 row。`update_source.py` 新增 `--feasibility {easy|medium|hard}`（status=researched 時必填）+ `--pagination-hint` / `--card-selector-hint` / `--date-format-hint` / `--notes` 旗標，寫入 `source_profile` JSONB。

**教訓：** Researcher agent **必須**填齊 feasibility hint，否則 Phase 2 完全跳過該 source。Researcher agent doc 應明示這是 hard requirement，不是 optional metadata。

---
## 2026-05-01 — 多城市地點顯示與篩選支援（location_prefectures + extractPrefecture）

**問題 A（篩選 false positive）：** `"京都"` 是 `"東京都"` 的子字串（東**京都**），導致所有 `東京都...` 地址都命中 `CHUBU_KINKI_MARKERS` 中的 `"京都"` marker，58 個東京活動誤出現在「中部・近畿・關西」篩選。

**問題 B（多城市顯示）：** 台東祭等多城市母活動無法在事件詳情頁顯示跨都道府縣資訊，地址欄顯示 `—`。

**修正：**
- `CHUBU_KINKI_MARKERS` 中 `"京都"` → `"京都府"`, `"京都市"`（前後台一致）
- `web/app/[locale]/events/[id]/page.tsx` 新增 `extractPrefecture()` + `subEventPrefectures` 聚合，多城市時 Location/Address 欄顯示「東京・京都・大阪」
- Migration 012：新增 `location_prefectures text[]` 欄位；backfill script 補齊 3 個多城市母活動
- 前台/後台篩選加入 `location_prefectures.cs.{"X"}` OR 條件；annotator 子活動 loop 結束後自動計算並寫入

**教訓：**
- **城市 marker 必須使用完整前綴**：`"京都"` 是 `"東京都"` 的子字串；任何新 marker 都需驗證是否為其他都道府縣的子字串，使用 `"京都府"`/`"京都市"` 替代 `"京都"`。
- `extractPrefecture()` regex 初版只處理 `大阪府`/`京都府`，漏掉 `大阪市`/`京都市` 開頭的地址格式；日文地址有省略「府」的情況，regex 需同時覆蓋兩種 pattern。

---
## 2026-05-01 — TV番組地址欄顯示規則（`location_name === "電視頻道"`）

**問題：** `web/app/[locale]/events/[id]/page.tsx` 的地址欄對 TV番組顯示 Google Maps 超連結（用 `location_name` = `"電視頻道"` 搜尋），不合語意。

**修正：**
- address 渲染邏輯加入特判：`event.location_name === "電視頻道"` 時顯示「電視頻道」純文字，不加超連結
- 優先順序：`電視頻道` 純文字 → Google Maps `<a>` → 無

**教訓：**
- `location_name` 的語意值（如 `"電視頻道"`）需在 UI 層做特判，否則搜尋連結產生無效地圖搜尋
- 類似特例：`オンライン`、`Zoom` 等非實體地點，未來如需地址欄渲染亦應在此加特判

---
## 2026-05-01 — 事件品質手動修正（prtimes 台灣地址漏網 + google_news_rss 純新聞）

**問題 A（prtimes）：** `4cd75c4c`（「城市失物招領所」）：`location_name` 為「台北市中正區」，屬台灣地址。`_TAIWAN_VENUE_RE` 已有台灣城市過濾，但未捕到「台北市中正區」這種 `市區` 格式。已手動 `is_active=False` 非表示化；scraper 本身**尚未**修正。

**問題 B（google_news_rss）：** `71f575a4`（「ナルワンアワー」）：純新聞記事，無場地、無 `start_date`。已手動 `is_active=False`；scraper 應在產出前驗證 `start_date` 是否存在。

**教訓：**
- prtimes `_TAIWAN_VENUE_RE` 需涵蓋 `台北市.*區`、`台中市.*區` 等縣市區格式（TODO）
- google_news_rss 事件若無 `start_date` 或 `location_name`，不應寫入 DB（TODO：在 `scrape()` 或 `database.py` 加守門）

---
## 2026-05-01 — prtimes 多城市活動漏建子活動修正（偵測式延長 raw_description）

**問題背景：** `_fetch_detail()` 將 raw_description 固定截斷為 `text[:3000]`。當 PR 文章前半是商品介紹（如 S.C Lab 8 款商品說明），活動行程（東京/大阪日程）落在後半時，Annotator 沒有收到完整行程資訊，無法生成 sub_events。結果：1 篇 PR 有東京（5/2）+ 大阪（5/9）兩場，卻只建了 1 個 Event。

**修正方式（commit `ecd2bb8`）：**
- 新增 `_MULTI_CITY_SECTION_RE` 正則，偵測「東京｜日期」、「大阪｜日期」等多城市模式
- 偵測到多城市：`text[:2000]` + `---[イベント開催情報]---` 分隔標記 + 行程區塊 4,000 字（合計上限 8,000 字）
- 無多城市：維持原本 `text[:3000]`（不影響現有行為）

**多城市子活動補建標準流程：**
1. 手動建子活動確認資料正確
2. 刪除手動建的子活動（不可保留）
3. 修正 scraper raw_description 邏輯
4. 重新抓取 + 更新 DB + 重置 `annotation_status = pending`
5. 執行 `annotator.py` → 自動生成正確 sub_events

**教訓：**
- 固定截斷長度對「商品介紹在前、活動行程在後」的文章無效；偵測式延長比直接增大全域截斷上限更精準，不影響其他 PR 的處理效能。
- 多城市活動修正必須走完整流程（步驟 1–5），不可直接保留手動建的子活動當作最終結果。

---
## 2026-05-01 — 新增 `location_url` 欄位（會場超連結）

**工作內容（commit 235b5ea）：**
- Migration `031_location_url.sql`：`ALTER TABLE events ADD COLUMN IF NOT EXISTS location_url text`
- `scraper/sources/base.py`：`Event` dataclass 新增 `location_url: Optional[str] = None`
- `web/lib/types.ts`：`Event` 介面新增 `location_url: string | null`
- Event detail page：`location_url` 存在時將 location_name 包在 `<a target="_blank" rel="noopener noreferrer">` 內
- Admin UI：`AdminEventForm.tsx`（EMPTY_FORM + input）+ `AdminEditClient.tsx`（form init）三處同步
- i18n：三語 `locationUrl` 鍵（zh: 會場官網、en: Venue website、ja: 会場公式サイト）

**教訓 A（DB migration 順序）：**
- Migration 必須先在 Supabase Dashboard SQL Editor 執行後，才能用 Python client seed 含新欄位的資料
- 未執行 migration 直接 seed → `PGRST204: Could not find the 'location_url' column`
- 正確順序：建立 migration 檔 → git push → Supabase Dashboard 執行 → Python seed

**教訓 B（Admin form 三處同步）：**
- 新增欄位須同時更新：① `EMPTY_FORM` 初始值 ② UI `<input>` 元素 ③ `AdminEditClient.tsx` form 初始化
- 漏任一處導致欄位顯示空白或無法儲存（靜默失敗，難以偵測）

**教訓 C（`location_url` 安全屬性）：**
- `<a href={event.location_url}>` 必須搭配 `target="_blank" rel="noopener noreferrer"`（OWASP reverse tabnabbing 防護）

---
## 2026-05-01 — GITHUB_TOKEN 權限口徑分裂 + 清單多點維護造成漂移

**問題背景：** 最近一輪 token 整理前，repo 內同一件事出現多種寫法：
- 非標準的 `&` 分隔權限寫法（已廢止）
- `Issues: write`
- 是否需要 `Metadata: read` 未一致

同時清單內容分散於多處，容易出現「A 檔更新了、B 檔沒更新」的文件漂移。

**根本原因：**
1. 缺少「權限口徑唯一版本」規範，導致 code/doc/agent 各自演化。
2. 缺少「單一維護來源」規範，造成重複文件長期分岔。

**修復方法：**
1. 權限口徑統一為：fine-grained `Issues: write + Metadata: read`；classic `repo` scope。
2. `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` 定義為唯一維護來源，`.github/TOKEN_SYNC_CHECKLIST.md` 改為導引頁。
3. 同步更新 `scraper/update_source.py`、`token-rotation.instructions.md`、`researcher.agent.md`、`SECRETS_LIFECYCLE.md`。
4. 在 `README.md` 與 `docs/ARCHITECTURE.md` 新增入口，降低搜尋成本。

**教訓：**
1. 牽涉權限或安全敘述的變更，必須採用「code + docs + agent 同步改」的原子更新。
2. 對外流程文件要有單一真實來源（single source of truth），其他位置只放導引。
3. public repo 專案要把「描述一致性」視為安全議題的一部分，避免誤導配置造成權限過寬或過窄。

---
## 2026-05-01 — MoN Takanawa 錯誤地址（DB 直接修正，無 commit）

**問題背景：** `enrich_addresses.py` 使用 GPT-4o-mini 為「有場館名但無地址」的 SSFF 活動補全地址，對「MoN Takanawa: The Museum of Narratives」補出錯誤地址 `東京都港区高輪4-10-30`；正確地址為 `東京都港区高輪2-21-2`（來源：SSFF 2026 官方 Schedule & Access 頁面）。受影響活動 2 件（「力×変位」、「忘れ鶏」），已直接用 Supabase SDK UPDATE 修正，無 scraper code 變更。

**根本原因：** GPT-4o-mini 對新場館（MoN Takanawa 2024 年開幕）地址記憶不準確，hallucinate 了高輪4丁目的地址。

**修復方法：** 查閱 SSFF 2026 官網 `shortshorts.org/2026/ja/schedule/` Venue access 章節，確認正確地址後直接 Supabase SDK UPDATE，無 code 變更。

**教訓：**
1. GPT-4o-mini 批次補填的地址**不應視為已驗證**——新場館或改建後場館尤其容易出錯。
2. 批次補填後，應針對重點合作場館（SSFF、TAICCA 合作場地等）做人工抽查。
3. 最可靠的地址驗證方法：到活動主辦方官網「会場・アクセス」頁面交叉比對。
4. 未來可考慮在 DB 加 `address_verified` 欄位或在管理頁標記 AI 補填地址狀態。

---
## 2026-05-01 — Phase 1+3 SLA + Quality Dashboard 成功重建（commit bd818cf）

**背景：** Phase 1（SLA 欄位）和 Phase 3（Quality Dashboard）在首次實作（commit 644a0ad）後因 `react-hooks/static-components` lint error 和用戶決定 revert（commit cf1e0a9）。本次成功重建。

**本次做對的：**
1. `quality/page.tsx` 的 `renderDetailTable` 函式宣告在 module 頂層（`export default` 之前），避免 PascalCase-in-render lint error。
2. 使用 camelCase IIFE `{(() => {...})()}` 做 inline 計算，不觸發 react-hooks/static-components。
3. i18n 9 keys 與所有 caller 在同一 commit 新增，無遺漏。

**教訓：**
- 被 revert 的功能重建時，先回顧 revert 原因（lint error），確認 SKILL.md 已有對應規則（TSX Component vs Helper），再按規則重寫。
- Engineer SKILL 的 `react-hooks/static-components` 規則在此次發揮作用：首次失敗是因為規則尚未建立；第二次成功是因為規則已存在且被遵守。

---
## 2026-05-01 — OG image 英文標題截斷過早（字元密度差異）

**工作內容（commit 47ac1ee）：**
`web/app/[locale]/events/[id]/opengraph-image.tsx` 截斷邏輯從兩級改為三級：
- 舊：`> 36 字 → 截斷至 34 字`（字體：`> 22 字 → 54px`，否則 `72px`）
- 新：`> 55 字 → 截斷至 53 字`（字體：`> 36 字 → 40px`、`> 22 字 → 54px`、否則 `72px`）

新字體三級表：
| 標題長度 | 字體大小 |
|---------|----------|
| ≤ 22 字 | 72px |
| 23–36 字 | 54px |
| 37–55 字 | 40px（新增） |
| > 55 字 | 40px + 截斷至 53 字 |

**根因：**
英文標題字元數通常是日文的 2–3 倍（日文一個字 = 一個 CJK 字元；英文一個單字 = 5–8 字元）。原本 36 字截斷設計以日文視覺寬度為基準，英文標題在 36 字元時視覺上僅填滿約 40–50% 的標題區域，導致文字被過早截斷（顯示 "C…" 等不完整字串）。

**教訓：**
1. **OG image 截斷閾值應依語言分開設計**：日/中以字元視覺寬度計（每字元寬，36 字足夠）；英文以字元數計（每字元窄，需 50+ 字才填滿同等空間）。
2. **增加字體縮小級別優先於截斷**：新增 40px 中間層讓長英文標題縮小後多行顯示，而非硬截斷，保留完整語意。
3. **截斷欄位設計必須考慮多語言字元密度**：任何 `text.length > N ? text.slice(0, M) + "…" : text` 邏輯，N 值應以最長語言（英文）為基準，並搭配字體縮小梯級。

---
## 2026-05-01 — 電視頻道地點類型 + 品質檢查白名單 + AdminEventTable 雙重篩選同步

**工作內容（commits 5851e46 + enrich_addresses commit）：**
1. `scraper/sources/gguide_tv.py`：`location_name` 統一改為 `"電視頻道"`，取代各頻道名稱（tvk1, BS朝日1 等）
2. `web/app/[locale]/page.tsx`：新增 `tv` 地點篩選分支（`ilike '%電視頻道%'`）；`other_japan` 排除電視節目
3. `web/components/AdminEventTable.tsx`：`filterLocation` 型別加 `"tv"`；`getFiltered` 和 `sourceCountMap` 兩處同步更新；select 新增 TV 選項
4. `web/components/FilterBar.tsx`：location select 新增 `tv` 選項
5. `web/messages/{zh,en,ja}.json`：新增 `locationTv` i18n key（三個檔案同時）
6. `scraper/enrich_addresses.py`（新建）：GPT-4o-mini 為「有場館名但無地址」的活動補 ja/zh/en 地址；跳過 gguide_tv 和線上活動
7. `web/app/[locale]/admin/quality/page.tsx`：「缺地址」品質檢查排除 `source_name = 'gguide_tv'` 和 `location_name = '電視頻道'`

**根因（gguide_tv 混入地區篩選）：**
`gguide_tv` 爬取的是 TV 番組，無實體地點，但 `location_name` 原先儲存各頻道名稱（tvk1、BS朝日1 等），被 `other_japan` 篩選邏輯誤匹配，品質檢查也誤報「缺地址」。

**根因（AdminEventTable 計數與列表不一致）：**
`AdminEventTable.tsx` 內有兩套平行的篩選邏輯：`getFiltered`（控制列表顯示）和 `sourceCountMap`（控制各 source 計數）。只更新 `getFiltered` 而遺漏 `sourceCountMap` 會造成計數與列表對不上。

**教訓：**
1. **無實體地點的來源必須設 canonical location_name**：電視、廣播、串流等無地點活動應設固定 canonical 值（如 `電視頻道`），避免被地址篩選誤匹配、品質檢查誤報。
2. **`other_japan` 篩選必須明確排除所有特殊類型**：目前需排除 online（`オンライン`）和 TV（`電視頻道`）兩種。每新增一種無地點類型，`other_japan` 篩選邏輯都需更新。
3. **新增地點類型需同步更新 6 個地方**（見 SKILL.md 新增的「新增地點類型 Checklist」）。
4. **品質檢查「缺地址」規則需白名單機制**：天生無地址的來源（gguide_tv、online 等）必須在 quality page 明確排除，否則製造噪音。
5. **AdminEventTable 雙重篩選同步**：`getFiltered` 和 `sourceCountMap` 使用相同邏輯，任何篩選修改必須同步兩處，否則計數和列表對不上。

---
## 2026-05-01 — SEO/AEO 強化 + GSC OAuth2 + proxy.ts 排除規則 + Admin tab 一致性

**工作內容（commits a9ef1d1 → d2fddcd）：**
1. sub-events 日期補 `<time dateTime>` 語意標籤（a9ef1d1）
2. 新增 `web/app/api/admin/gsc/route.ts` + `web/components/GscSection.tsx`（GSC 監控卡片）
3. GSC API 從 service account JWT 改為 OAuth2 refresh token（c6f8075）
4. HTML 驗證檔 `web/public/google12eeb8b1a7239866.html` + `proxy.ts` 排除（e698874）
5. aeo 頁面 header 改為完整 tab nav（5cae991）
6. `aeoTab` i18n key 改名「SEO-AEO 監控」（d2fddcd）

**根因（GSC service account 問題）：**
Google Search Console UI **只允許一般 Google 帳號**作為使用者；service account email 提交時報「找不到電子郵件」。原本設計用 service account JWT 的方案無法走通，必須改用 OAuth2 refresh token（`GSC_CLIENT_ID` + `GSC_CLIENT_SECRET` + `GSC_REFRESH_TOKEN`）。

**根因（HTML 驗證檔被 i18n 攔截）：**
`web/public/` 下的靜態檔案若不在 `proxy.ts` matcher 的排除規則內，會被 next-intl middleware 307 重導向至語言路徑（`/zh/google...html`），導致 Google 無法讀到驗證檔。排除規則 `google[0-9a-f]+\.html` 可涵蓋所有 Google 驗證檔格式。

**教訓：**
1. **Google Service Account 無法加入 Search Console**：設計 GSC 整合時，預設方案必須是 OAuth2 refresh token，而非 service account。
2. **OAuth Playground 需先設定測試使用者**：App 處於「測試」模式時，需在 OAuth consent screen 把自己的帳號加入「測試使用者」，否則授權流程 403 `access_denied`。
3. **所有 `web/public/` 靜態檔案都需要同步更新 `proxy.ts` 排除規則**：這是 AEO Feature Planning Rules 中「Static file checklist」的延伸，必須把它列為每次新增靜態資源的預設檢查步驟。
4. **Admin 子頁面 header 必須使用完整 tab nav**：不可只放「← 返回」連結；必須使用 `getTranslations("admin")` + Link 列表，與其他 admin 頁面保持一致。

---
## 2026-05-01 — Architect 直接編輯後留半成品：停止點契約缺失

**情境：**
撤銷 Tier 1 監控（Phase 1+3）時，Architect 親自刪除 `web/messages/{zh,en,ja}.json` 中 10 個 i18n keys 與 `stats/page.tsx` 的 SLA 欄位、整個 `quality/page.tsx`。但**沒同步刪 stats/page.tsx 中的 `t("statsSlaHeader")`、`t("statsAvgDuration")` 呼叫**，工作樹留下會編譯失敗的半成品。用戶察覺後質疑「agent 開發完最後一步究竟停在哪裡？」

**根因：**
1. Architect 預設 read-only，沒有「直接編輯後須收尾」的停止點契約。
2. 報告中常用裸 commit hash（如「commit cf1e0a9」），用戶誤以為已推送，但實際只是 local commit 或甚至 working tree。
3. 刪 i18n key 沒先 `grep_search` 找 caller，違反 atomic revert 原則。

**修正：**
SKILL.md 新增三節 —
- **Stop-Point Contract**：直接編輯後必須走完 V-M-D 鏈路或明示「⚠️ 未提交」。
- **Status Reporting Vocabulary**：強制使用 ✅已推送 / ⏳本地only / 📝未commit 三種標籤。
- **Atomic Revert Rule**：刪 symbol 前必 grep caller，先刪 caller 再刪 definition，commit 前 `tsc --noEmit`。

**教訓：**
- 「Architect 不寫 code」是預設值不是絕對值；一旦破例就必須明示交接狀態。
- commit hash 出現 ≠ 已推送。報告必須區分三種狀態。
- 不是 git 分支策略問題（main 全程同步），是 agent 工作流程契約缺失。

---
## 2026-05-01 — AEO 架構設計（Phase A/B/C）：AI Engine Optimization 全域規劃

**工作內容：**  
設計並規劃 AEO 三階段實作，涵蓋 AI 搜尋引擎可見度提升、IndexNow 即時提交、監控追蹤。

**架構決策：**

1. **JSON-LD 分層策略**：全域 JSON-LD（WebSite + Organization）放 `layout.tsx`；頁面級 JSON-LD（BreadcrumbList、CollectionPage、FAQPage）放各自的 `page.tsx`。避免全域與頁面級 schema 衝突。

2. **AEO 監控不依賴伺服器組件**：monitoring 放在 Edge middleware（`proxy.ts`），而非 Server Component 或 API route，因為 proxy 是所有請求的必經路徑，能攔截 bot UA 和 AI referrer 而不影響正常渲染。

3. **IndexNow 整合點**：在 `upsert_events()` 返回新 UUID 列表（非修改現有函式簽名的破壞性變更，而是擴展返回型別），使 `main.py` 的 orchestrator 能在每次 scraper run 後立即提交新活動 URL，延遲最短。

4. **聚合頁 URL 設計**：`/[locale]/cities/[city]` 和 `/[locale]/categories/[category]` 靜態路由（generateStaticParams），可被搜尋引擎快取，也適合 CollectionPage + ItemList JSON-LD schema。

5. **FAQPage 設計規則**：FAQ 問答設計為 2-4 個問題，涵蓋「什麼是台灣文化活動」「如何找到最新活動」等常見 AI 查詢。**關鍵：** JSON-LD 必須搭配頁面上可見的 `<dl>` 元素，Google 不接受僅 JSON-LD 而無可見內容的 FAQPage。

**教訓：**
- AEO 計劃必須明確標注「static file → proxy.ts matcher 同步」的步驟，這是最容易被遺漏的實作細節。
- FAQPage JSON-LD 必須在計劃中同時要求可見 `<dl>` section，否則 Engineer 只會做 JSON-LD 而跳過可見部分。
- Migration 號碼衝突（如兩個 029_）要在規劃期確認最新 migration 號碼，避免衝突。規劃新 migration 前必查 `ls supabase/migrations/` 確認下一個可用號碼。

---
## 2026-05-01 — Tier 1 資源監控：保留預算護欄，撤銷 SLA + 品質 Dashboard

**背景：** 原本規劃三層儀表板（SLA、品質、預算），但實際上線後 `/admin/stats` 的 SLA 欄與 `/admin/quality` 全頁被使用者撤回，僅保留 `weekly_report.py` 的預算護欄。

**最終結果：**
- ✅ 保留：`weekly_report.py` 新增 `MONTHLY_BUDGET_USD = 20.0` 護欄與「本月迄今 / OpenAI 本週 / DeepL 本週」三行。
- ❌ 撤銷：`/admin/stats` 的「30 日成功率」「平均耗時」兩欄、`/admin/quality` 整頁、相關 i18n keys（statsSlaHeader/AvgDuration/qualityTab/qualityTitle 等 10 個）。

**教訓：**
- 規劃 admin UI 時，先問清楚「這頁面真的會被點開嗎？」單純的計數 dashboard 若沒導向具體 action（一鍵修正、批次處理）容易淪為視覺裝飾。
- 預算層信號（單一 LINE 訊息推送）成本低、留存率高；UI 層信號（需主動訪問）容易被忽略。下次規劃監控功能優先做被動推送（LINE / email / issue）而非新頁。
- 撤銷比新增便宜：留下 plan、commit history、SKILL.md「未來如需…」備註，將來想做時隨時可以重做。

---
## 2026-05-01 — Tier 1 規劃版本（已部分撤銷，記錄保留）

**背景：** 原本 `/admin/stats` 只顯示最近一次執行狀態、`weekly_report.py` 只看週費用、並無資料品質審核面。長期下來難以推斷「某個來源是偶發失敗還是長期退化」。

**變更：**
- `/admin/stats` Source Status 表加入「30 日成功率（🟢/🟡/🔴）」與「平均耗時」兩欄，來源為 `scraper_runs.duration_seconds`（migration 014）。
- `weekly_report.py` 新增 `MONTHLY_BUDGET_USD = 20.0` 護欄，並推送「本月迄今 / OpenAI 本週 / DeepL 本週」三行，超過閾值走 ⚠ / 🚨。
- 新建 `/admin/quality` 頁，並行查 4 個品質信號（已審缺翻譯 / 過期仍開放 / 已標註無分類 / 卸地址），每類列出前 50 筆詳情。

**教訓：**
- 「崩湬 / 安全」與「品質 / 退化」是兩個身分，儀表板也要分開；SLA 看來源健康、quality 看資料完整、budget 看費用。
- TypeScript 的 `latestBySource.r.duration_seconds` 在不同 migration 狀態下可能為 `undefined`，需以 `?? 0` 傅底，不能讓 SLA 表崩。
- LINE 週報 `format_line_message()` 报告變豊富時，請主動加一行空行，避免 「📊 周報」 與 「💰 本月迄今」 默一起。

---
## 2026-04-29 — AdminEventTable 日期範圍篩選器無法搜索未來活動

**問題：** `filterTimeMode === "past"` 分支在 `getFiltered` 和 `sourceCountMap` 兩處都有 `isPast` 判斷（`end_date < today`），導致「搜尋特定期間」無法找到 end_date 在未來的活動。

**根本原因：** 日期範圍篩選器把「過去期間」和「任意日期範圍」的語意混在一起；且 `getFiltered` 與 `sourceCountMap` 使用相同邏輯卻未同步修改。

**修復（7f00d4e）：** 移除兩處的 `isPast` 限制，改為純粹 from/to 日期邊界篩選；同時重命名 i18n 標籤為「搜尋特定期間」。

**教訓：**
- 日期範圍篩選器設計原則：from/to 應為純粹的日期邊界，不應附加「只搜過去」的語意
- 計劃中任何涉及 `AdminEventTable` 篩選邏輯的修改，都必須明確標注「`getFiltered` 和 `sourceCountMap` 兩處需同步更新」
- 篩選器 i18n 標籤應精確描述行為（「特定期間」而非「過去期間」）

---
## 2026-04-29: drama 新增導致 'retail' 從 Category union 遺失

**錯誤：**
`multi_replace_string_in_file` 新增 `"drama"` 到 Category union 時，意外刪除了 `"retail"`。
TypeScript build 失敗 → Vercel 停在舊版本 → 用戶看不到 drama 分類。

**修復：** `f9e6b52` — 補回 `| "retail"` 到 Category union。

**教訓：**
- Category union 新增後，必須立即執行 `npx tsc --noEmit`，確認所有既有成員仍存在
- `multi_replace_string_in_file` 的 oldString 必須包含足夠上下文（≥3行），避免截斷鄰近 union 成員
- Vercel build 失敗時頁面不更新但不會下線（顯示舊版），需主動檢查 TypeScript 錯誤

---
## 2026-04-29: Peatix organizer Layer 3 + daily discovery rotation

**工作內容：**
- peatix.py 加入 DB-driven organizer 動態載入（Layer 3 模式）
- discovery_accounts.py 完整重寫為 4 槽每日輪流
- discovery-accounts.yml 從每週日改為週一到週四每日執行

**教訓：**
- Layer 3 擴充到新平台（Peatix）時，需要獨立的 agent_category（`peatix_organizer`），不可與 `note_creator` 混用
- Skills 資料夾整理：per-source skill 必須放 `sources/{name}/`，不可在頂層建立

**Skills folder audit lesson：**
- `.github/skills/` 頂層只放 workflow/tooling skills（local-preview, cc-statusline, session-analytics）
- per-agent skills → `agents/{agent-name}/`
- per-source skills → `sources/{source-name}/`（有 `applyTo: scraper/sources/*.py` 的都應在這裡）

---
## 2026-04-29 — LINE webhook 0 subscribers — `LINE_CHANNEL_TOKEN` missing from Vercel
**Error:** After users added the LINE bot as a friend, `line_subscribers` remained at 0 rows. Schema INSERT worked fine in manual test; the issue was at the webhook layer.
**Diagnosis:** GitHub Actions secrets (`LINE_CHANNEL_TOKEN`, `LINE_CHANNEL_SECRET`) and Vercel environment variables are **completely separate systems**. The webhook runs on Vercel, not in GitHub Actions. `LINE_CHANNEL_TOKEN` was never set in Vercel → signature verification failed → HTTP 401 → follow events rejected. LINE does not retry failed webhook deliveries.
**Fix:** Added `LINE_CHANNEL_TOKEN` to Vercel Dashboard → Settings → Environment Variables (Production). User blocked + unblocked the bot to re-trigger the follow event → 1 row successfully inserted.
**Lesson:** When a feature spans GitHub Actions (scraper/broadcast) **and** Vercel (webhook/API), both platforms need their own copy of shared credentials. Never assume that secrets in one CI/CD platform propagate to another. Architect plans for cross-platform features must list required env vars per platform explicitly.

---
## 2026-04-26 — Admin table address cell lacked locale fallback
**Error:** `AdminEventTable.tsx` address column only read `location_address` (Japanese/default). Events with addresses stored only in `location_address_zh` (zh-first scrapers like `koryu`) or with address embedded in `location_name` showed blank in admin. The front-end detail page was correct because it used `getEventLocationAddress()` with a fallback chain.
**Fix:** Updated the `<td>` to `addr = location_address || location_address_zh || location_name` (commit `f45d5d5`).
**Lesson:** Architect plans must note: admin table display logic for any locale-aware field must match the helper function fallback in `lib/types.ts`. When designing a new table column, always reference the corresponding `getEvent*()` helper and replicate its fallback chain.

---
## 2026-04-26 — AdminEventTable orphaned `<td>` after `<th>` removal
**Error:** The `isPaid` `<th>` was deleted from the annotated-view header, but its paired `<td>` in the row renderer was not deleted in the same change. The misalignment was invisible to TypeScript and only caught visually by the user.
**Fix:** Removed the orphaned `<td>` (commit `5597150`). Added column-pairing rule to `engineer/SKILL.md`.
**Lesson:** Architect plans that include removing a column from `AdminEventTable.tsx` must explicitly state: "remove the matching `<td>` in the same PR". Column count is a visual contract that static analysis cannot enforce.

---
## 2026-04-26 — AdminEventTable filter label/style regressions repeated across multiple commits
**Error:** Three UI fixes (`tFilters("search")` search label, `tFilters("category")` category label, `bg-gray-50` category button) were re-introduced and re-regressed multiple times because later commits modifying the same file for unrelated reasons (bulk-toggle refactor, reannotate label rename) overwrote the corrected lines with default values.
**Fix:** Re-applied the three fixes; added protected-invariants rule to `engineer/SKILL.md`; added regression entry to `engineer/history.md`.
**Lesson:** Files with frequently-touched UI logic accumulate "sticky regressions". The architect plan for any `AdminEventTable.tsx` change must explicitly mention the protected invariants as a check item.

---
## 2026-04-26 — Online canonical form corrected: location_address must be 'オンライン', not NULL
**Error:** Previous session established `location_address = NULL` as the canonical form for online events. This was wrong: it caused online events to appear in the `tokyo` admin filter (which treats NULL address as "Tokyo"), and `other_japan` filtering relied solely on `location_name` to exclude online events, creating fragile single-point-of-failure logic. The `AdminEventTable.tsx` `other_japan` filter had no online exclusion at all, meaning online events would appear there too.

**Fix:**
1. New canonical form: `location_name = 'オンライン'`, `location_address = 'オンライン'`. Both columns set. DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
2. `peatix.py`: all 3 places that set `location_address = None` for online events changed to `= 'オンライン'`.
3. `connpass.py` + `doorkeeper.py`: `_normalize_location_address()` now returns `'オンライン'` instead of `None`.
4. `AdminEventTable.tsx`: added `if (addr.includes('オンライン')) return false` to `other_japan` filter.
5. `page.tsx`: updated comment; filter logic unchanged (still queries `location_name`).
6. DB: patched 7 peatix online events (`location_address = 'オンライン'`, zh/en translations set).

**Lesson:** `location_address = NULL` must not be used as a sentinel for "online" — NULL means "unknown/unset", not "online". Scrapers must always set `location_address = 'オンライン'` for online events. Any filter that gates on `location_address IS NOT NULL` will mis-classify events if online events have NULL address. Updated "Online Location Standard" rule in SKILL.md.

---
## 2026-04-26 — Online location filter broken: queried wrong column + scrapers lacked normalization
**Error:** The `location=online` filter in `page.tsx` queried `location_address ILIKE '%オンライン%'`. After the correct normalization (online events should have `location_address = NULL`), the filter returned 0 results. Additionally:
1. Several peatix events had `location_name = 'オンライン（Zoom）'` with non-null address — the `(Zoom)` suffix was not canonicalized and the address was not cleared.
2. `connpass.py` and `doorkeeper.py` had no online detection at all — API fields `place`/`venue_name` containing 'オンライン' were passed through without normalization.
3. `other_japan` filter excluded online via `location_address NOT ILIKE '%オンライン%'` which also failed once addresses became NULL.

**Fix:**
1. `page.tsx`: online filter → `location_name ILIKE '%オンライン%'`; other_japan exclusion → `location_name NOT ILIKE '%オンライン%'`.
2. `peatix.py`: added final canonicalize step after all fallbacks: if `location_name` matches online marker → `'\u30aa\u30f3\u30e9\u30a4\u30f3'`, address = None.
3. `connpass.py` + `doorkeeper.py`: added `_ONLINE_RE`, `_normalize_location_name()`, `_normalize_location_address()` helpers.
4. DB: cleared address for 7 active peatix events with online markers.

**Lesson:** The canonical online event representation is **`location_name = '\u30aa\u30f3\u30e9\u30a4\u30f3'`, `location_address = None`**. Any query filtering for online events must check `location_name`, not `location_address`. All scrapers must normalize their output before building the Event object. Added “Online Location Standard” rule to SKILL.md.

---
## 2026-04-26 — Peatix online event incorrectly assigned a physical address (×2 errors in same session)
**Error:** Event `05aefbdf` (周美花講演) is a hybrid/online event. Peatix renders its LOCATION block as a single line `"LOCATION\n\nOnline event"` — no second group. The scraper's primary regex (`LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})`) requires two groups separated by a blank line, so it didn't match. All CSS and regex fallbacks then ran, finding:
1. A campus name from the description body text → `location_name = '桜美林大学新宿キャンパス'`
2. `東京都新宿区` from the description → `location_address`

In the same session, the previous turn had wrongly "verified" and patched this same event with the full campus address `東京都新宿区百人町3-23-1`, compounding the error.

**Fix:**
1. Added `is_confirmed_online` guard in Peatix scraper: detect `LOCATION\n\n(Online event|オンライン|…)` FIRST, set the flag, and skip ALL subsequent address fallbacks.
2. Fixed final body-text online fallback to set `location_address = None` (was `'オンライン'`).
3. Patched DB event `05aefbdf`: `location_name='オンライン'`, all address fields `None`.

**Lesson:** When a Peatix LOCATION block contains an online marker, it must **immediately short-circuit all address extraction**. Address fallbacks must never run against the event description body — venue names mentioned in prose ("会場…桜美林大学") are conditional/secondary and must not become `location_address`. Added rule to SKILL.md under Online Events.

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.

---
## 2026-04-26 — Admin table address cell lacked locale fallback
**Error:** `AdminEventTable.tsx` address column only read `location_address` (Japanese/default). Events with addresses stored only in `location_address_zh` (zh-first scrapers like `koryu`) or with address embedded in `location_name` showed blank in admin. The front-end detail page was correct because it used `getEventLocationAddress()` with a fallback chain.
**Fix:** Updated the `<td>` to `addr = location_address || location_address_zh || location_name` (commit `f45d5d5`).
**Lesson:** Architect plans must note: admin table display logic for any locale-aware field must match the helper function fallback in `lib/types.ts`. When designing a new table column, always reference the corresponding `getEvent*()` helper and replicate its fallback chain.

---
## 2026-04-26 — AdminEventTable orphaned `<td>` after `<th>` removal
**Error:** The `isPaid` `<th>` was deleted from the annotated-view header, but its paired `<td>` in the row renderer was not deleted in the same change. The misalignment was invisible to TypeScript and only caught visually by the user.
**Fix:** Removed the orphaned `<td>` (commit `5597150`). Added column-pairing rule to `engineer/SKILL.md`.
**Lesson:** Architect plans that include removing a column from `AdminEventTable.tsx` must explicitly state: "remove the matching `<td>` in the same PR". Column count is a visual contract that static analysis cannot enforce.

---
## 2026-04-26 — AdminEventTable filter label/style regressions repeated across multiple commits
**Error:** Three UI fixes (`tFilters("search")` search label, `tFilters("category")` category label, `bg-gray-50` category button) were re-introduced and re-regressed multiple times because later commits modifying the same file for unrelated reasons (bulk-toggle refactor, reannotate label rename) overwrote the corrected lines with default values.
**Fix:** Re-applied the three fixes; added protected-invariants rule to `engineer/SKILL.md`; added regression entry to `engineer/history.md`.
**Lesson:** Files with frequently-touched UI logic accumulate "sticky regressions". The architect plan for any `AdminEventTable.tsx` change must explicitly mention the protected invariants as a check item.

---
## 2026-04-26 — Online canonical form corrected: location_address must be 'オンライン', not NULL
**Error:** Previous session established `location_address = NULL` as the canonical form for online events. This was wrong: it caused online events to appear in the `tokyo` admin filter (which treats NULL address as "Tokyo"), and `other_japan` filtering relied solely on `location_name` to exclude online events, creating fragile single-point-of-failure logic. The `AdminEventTable.tsx` `other_japan` filter had no online exclusion at all, meaning online events would appear there too.

**Fix:**
1. New canonical form: `location_name = 'オンライン'`, `location_address = 'オンライン'`. Both columns set. DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
2. `peatix.py`: all 3 places that set `location_address = None` for online events changed to `= 'オンライン'`.
3. `connpass.py` + `doorkeeper.py`: `_normalize_location_address()` now returns `'オンライン'` instead of `None`.
4. `AdminEventTable.tsx`: added `if (addr.includes('オンライン')) return false` to `other_japan` filter.
5. `page.tsx`: updated comment; filter logic unchanged (still queries `location_name`).
6. DB: patched 7 peatix online events (`location_address = 'オンライン'`, zh/en translations set).

**Lesson:** `location_address = NULL` must not be used as a sentinel for "online" — NULL means "unknown/unset", not "online". Scrapers must always set `location_address = 'オンライン'` for online events. Any filter that gates on `location_address IS NOT NULL` will mis-classify events if online events have NULL address. Updated "Online Location Standard" rule in SKILL.md.

---
## 2026-04-26 — Online location filter broken: queried wrong column + scrapers lacked normalization
**Error:** The `location=online` filter in `page.tsx` queried `location_address ILIKE '%オンライン%'`. After the correct normalization (online events should have `location_address = NULL`), the filter returned 0 results. Additionally:
1. Several peatix events had `location_name = 'オンライン（Zoom）'` with non-null address — the `(Zoom)` suffix was not canonicalized and the address was not cleared.
2. `connpass.py` and `doorkeeper.py` had no online detection at all — API fields `place`/`venue_name` containing 'オンライン' were passed through without normalization.
3. `other_japan` filter excluded online via `location_address NOT ILIKE '%オンライン%'` which also failed once addresses became NULL.

**Fix:**
1. `page.tsx`: online filter → `location_name ILIKE '%オンライン%'`; other_japan exclusion → `location_name NOT ILIKE '%オンライン%'`.
2. `peatix.py`: added final canonicalize step after all fallbacks: if `location_name` matches online marker → `'\u30aa\u30f3\u30e9\u30a4\u30f3'`, address = None.
3. `connpass.py` + `doorkeeper.py`: added `_ONLINE_RE`, `_normalize_location_name()`, `_normalize_location_address()` helpers.
4. DB: cleared address for 7 active peatix events with online markers.

**Lesson:** The canonical online event representation is **`location_name = '\u30aa\u30f3\u30e9\u30a4\u30f3'`, `location_address = None`**. Any query filtering for online events must check `location_name`, not `location_address`. All scrapers must normalize their output before building the Event object. Added “Online Location Standard” rule to SKILL.md.

---
## 2026-04-26 — Peatix online event incorrectly assigned a physical address (×2 errors in same session)
**Error:** Event `05aefbdf` (周美花講演) is a hybrid/online event. Peatix renders its LOCATION block as a single line `"LOCATION\n\nOnline event"` — no second group. The scraper's primary regex (`LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})`) requires two groups separated by a blank line, so it didn't match. All CSS and regex fallbacks then ran, finding:
1. A campus name from the description body text → `location_name = '桜美林大学新宿キャンパス'`
2. `東京都新宿区` from the description → `location_address`

In the same session, the previous turn had wrongly "verified" and patched this same event with the full campus address `東京都新宿区百人町3-23-1`, compounding the error.

**Fix:**
1. Added `is_confirmed_online` guard in Peatix scraper: detect `LOCATION\n\n(Online event|オンライン|…)` FIRST, set the flag, and skip ALL subsequent address fallbacks.
2. Fixed final body-text online fallback to set `location_address = None` (was `'オンライン'`).
3. Patched DB event `05aefbdf`: `location_name='オンライン'`, all address fields `None`.

**Lesson:** When a Peatix LOCATION block contains an online marker, it must **immediately short-circuit all address extraction**. Address fallbacks must never run against the event description body — venue names mentioned in prose ("会場…桜美林大学") are conditional/secondary and must not become `location_address`. Added rule to SKILL.md under Online Events.

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.

---
## 2026-04-29 — Migration 027 驗證完成：5 步驗證套件建立與全綠測試

**工作內容：** 修復 migration 027 中 `admin_list_users()` RPC 的假拒絕問題後，建立完整的 5 步驗證套件並全部通過。

**驗證框架（4 象限 + 回傳型別）：**
1. ✅ Function exists — `pg_proc` 查詢確認定義存在
2. ✅ No auth context → 42501 — Empty claim 和無 auth.uid() 時正確拒絕
3. ✅ Admin user → success — Admin 用戶取得行數並順利查詢
4. ✅ Non-admin user → 42501 — 非 admin 用戶正確被拒
5. ✅ Return type validation — 所有 5 欄位（id, email, created_at, last_sign_in_at, role）型別正確

**驗證產物：**
- `027_smoke_test.sql` — 可執行的 5 步 SQL 套件，包含 temp table 重用邏輯
- `027_VALIDATION.md` — 步驟分解指引與預期結果
- `027_VERIFICATION_REPORT.md` — Executive summary 和 deployment checklist

**Lesson：** Supabase `SECURITY DEFINER` RPC 函式若涉及權限閘，驗證不能只做單點測試（app 或 SQL Editor），必須建立**四象限驗證矩陣**（app admin/non-admin, SQL Editor with claim/without claim）並配合回傳型別檢查。「all tests passed」報告應包含具體測試 ID 和通過時間戳，方便事後審計。

---
## 2026-04-29 — Cinema scrapers 官網提取：official_url selector 設計與 DB backfill 分離執行

**工作內容：** CineMarti Shinjuku 和 KS Cinema 的 scraper 中添加 official_url 抽取邏輯；識別出 Google search 結果用了不同 locale 的電影名稱。

**場景：** Cinema scraper 需要從官網電影詳頁面提取官方購票連結（official_url），以優先於一般 source_url 在前台顯示。

**修復：**
1. Selector pattern：`a[href*=".../ticket..."]` 或 `a[href*=".../purchase..."]` 的 link-text 和 href（驗證 URL domain 非跨域）
2. 選擇邏輯：優先選 Japanese locale 的電影標題 `name_ja`，而非使用者 `locale` 變數
3. DB backfill：在 scraper 新增欄位後，必須**立即執行一次手動檢查**，確認新抽取的 official_url 不是偽造 / 過期連結

**Lesson：** 
- Cinema 官網連結提取必須包含 domain whitelist（避免第三方票券販賣站）
- Google search 結果中的電影名稱取決於 search box locale，與用戶 locale 無關；務必優先使用 `name_ja`（日本官網）而非 locale 參數
- 新增欄位後不能依賴日後人工驗證；須立即執行 dry-run 並手檢前 5 筆

---
## 2026-04-29 — 8 個 Scraper 後補註冊：未登錄 SCRAPERS list 的源碼檔案大清查

**工作內容：** 發現 CineMarineScraper、EsliteSpectrumScraper、MoonRomanticScraper、MorcAsagayaScraper、ShinBungeizaScraper、SsffScraper、TaiwanFaasaiScraper、TokyoFilmexScraper 都有 `.py` 源碼但未在 `scraper/main.py` 的 `SCRAPERS` 列表中註冊。

**修復方法：** 在 `SCRAPERS = [...]` 列表中追加 8 個 scraper 類別；執行 `python main.py --dry-run` 驗證各源碼發揮應有的事件抽取數量。

**驗證結果：**
- CineMarineScraper (横浜シネマリン, id=56) — 1 件
- EsliteSpectrumScraper (誠品生活日本橋, id=46) — 2 件
- MoonRomanticScraper (Moon Romantic, id=48) — 1 件
- MorcAsagayaScraper (Morc阿佐ヶ谷, id=51) — 0 件（正常，查無當日台灣電影）
- ShinBungeizaScraper (新文芸坐, id=50) — 1 件
- SsffScraper (SSFF, id=58) — 6 件
- TaiwanFaasaiScraper (台湾發祭, id=57) — 1 件
- TokyoFilmexScraper (東京フィルメックス, id=59) — 0 件（正常，十月無影展）

**Lesson：** 定期檢查 `sources/` 目錄與 `SCRAPERS` list 是否同步。實施策略：每月執行 `find sources/ -name '*.py' -exec basename {} .py \;` 並與 list 對比，找出未登錄源碼。新增源碼後不應依賴 CI 自動發現；必須立刻檢查 dry-run 數量是否合理。

---
## 2026-04-29 — Admin Users 後台誤擋：`admin_list_users()` 在 web request 出現 false-deny

**錯誤：** 後台使用者頁面呼叫 RPC `admin_list_users()` 時回傳 `42501 admin privileges required`，但同一管理員帳號在 SQL Editor 測試可通過。

**根本原因：** 權限閘門一度只依賴 `request.jwt.claim.sub`。在 `SECURITY DEFINER` 與不同呼叫上下文下，claim 可用性和 app request 不一致，導致正式網站請求被誤判為非管理員。

**修復方法：** 新增 migration `027_admin_list_users_uid_fallback.sql`，將 gate 改為 `coalesce(auth.uid(), v_sub::uuid)`，優先使用 app request 的 `auth.uid()`，僅在 SQL Editor 模擬時 fallback 到 claim；保留 `42501` 與 admin role 檢查。

**Lesson：** 任何 Supabase `SECURITY DEFINER` 的 admin RPC，若需辨識目前登入者，必須以 `auth.uid()` 為主，claim 僅作測試 fallback，並以「app admin / app non-admin / SQL editor with claim / SQL editor without claim」四象限驗證。

---
## 2026-04-29 | 多語言修正 UI 設計不完整 | 只設計單語版本再補改 | 重寫為三語 textarea UI | 涉及多語欄位的修正 UI 必須一次設計成三語版

**錯誤：** 設計「選取理由不準確」報告審核 UI 時，第一版只做了單一 textarea，預填用戶提交的修正文字。
**根本原因：** `selection_reason` 是 JSON 格式，包含 `zh`/`en`/`ja` 三欄。單語 textarea 只能修改一個 locale，其他兩個 locale 的既有值會被靜默覆蓋或丟失。
**修復方法：** 重寫為 3 個 textarea（中文 / English / 日本語），各自從活動現有 `selection_reason` JSON 帶入預設值，用戶提交的修正文字優先覆蓋對應欄位，`confirm-report.ts` 接收 pre-built JSON 字串直接寫入。
**Lesson：** 任何涉及 `selection_reason`、`name_*`、`description_*` 等多語欄位的修正或輸入 UI，**必須一次設計成三語版（zh/en/ja）**，不能先做單語再補。

---
## 2026-04-29 — Supabase migration 執行錯誤：`REVOKE ... ON VIEW` 語法不被 PostgreSQL 接受
**錯誤：** 在 `024_security_advisor_auth_view_fix.sql` 執行時出現 `syntax error at or near "public"`，錯誤定位在：
`revoke all on view public.admin_users_view from anon, authenticated;`

**根本原因：** PostgreSQL `REVOKE` 對 view 物件使用 `ON TABLE` 語法，而不是 `ON VIEW`。

**修復方法：** 將語句改為：
`revoke all on table public.admin_users_view from anon, authenticated;`
並重新在 Supabase SQL Editor 執行 migration。

**Lesson：**
1. 在撰寫權限語句時，先以 PostgreSQL 語法為準，不要依直覺使用 `ON VIEW`。
2. Security Advisor 修復 migration 必須先做一次語法快檢，特別是 `GRANT/REVOKE/ALTER VIEW`。
3. 對於 Supabase SQL Editor 的報錯，優先依錯誤行數回到 migration 原文逐行比對，不要直接懷疑權限模型本身。

---
## 2026-04-28 — Agent handoff 功能實現：.prompt.md vs .agent.md 混淆
**錯誤：** 設計了兩個工作流（update-history 和 validate-deploy），創建了 `.prompt.md` 文件並在 6 個 agent 的 `handoffs:` 中引用，但 handoff 按鈕在 VS Code 中沒有出現。

**根本原因：** VS Code Copilot Chat 的 `handoffs:` frontmatter 中的 `agent:` 字段**必須指向 `.agent.md` 文件的 name**，不能指向 `.prompt.md` 文件。`.prompt.md` 文件是獨立的 `/` 命令任務，不是 agent。

**修復方法：**
1. 刪除 `.github/prompts/update-history-skill-agent.prompt.md` 和 `validate-merge-deploy.prompt.md`
2. 創建 `.github/agents/update-history-agent.agent.md` 和 `.github/agents/validate-merge-deploy.agent.md`
3. 設置 `user-invocable: false`（只通過 handoff 調用，不在 agent 選擇器中顯示）
4. 在 6 個主要 agent 的 handoff 中添加 `prompt:` 字段（預填中文指令）

**Lesson：**
1. **Custom agents 有三種引用方式**：
   - `.prompt.md` → 通過 `/` 命令或 `/prompts` 調用，獨立任務
   - `.agent.md` → 通過 agent 選擇器調用或作為 handoff 目標，持久化角色
   - Handoff 中的 `agent:` 只能指向 `.agent.md` 文件，不能指向 prompt

2. **Handoff 完整格式**：
   ```yaml
   handoffs:
     - label: "按鈕文字"
       agent: AgentNameFromFile
       prompt: "預填指令"
       send: false  # 可選，false=用戶點擊後需手動發送
       model: "Claude Sonnet 4.5 (copilot)"  # 可選
   ```

3. **工作流設計需考慮調用方式**：若需通過 handoff 按鈕一鍵調用，必須建立 `.agent.md`；若僅作偶發任務，`.prompt.md` 足夠。

---
## 2026-04-28 — Reviewed 活動缺翻譯：annotator 永久跳過 reviewed 狀態導致翻譯缺漏
**錯誤：** 11 個活動被標記為 `reviewed` 後，`name_zh` / `name_en` 仍為 NULL。後台顯示活動標題為空白，前台無法正確顯示語言版本。

**根本原因：** `annotator.py` 的 query 一律排除 `annotation_status = 'reviewed'`（line 276: `.neq("annotation_status", "reviewed")`），導致這些活動**永遠不會再被 AI 翻譯**，即使翻譯欄位是空的。

**修復（三層防護，Option C）：**
1. **DB 緊急修復**：把 11 筆缺漏活動改回 `pending`，手動執行 `python annotator.py`，完成後確認 0 筆缺漏。
2. **annotator.py `--fix-reviewed` 旗標**：新增模式，只查詢 `reviewed + name_zh/name_en IS NULL` 的活動，補齊翻譯欄位，完成後維持 `annotation_status = "reviewed"`（不降級，不覆蓋 category / 日期）。
3. **scraper.yml CI 步驟**：`python main.py` 之後加 `python annotator.py --fix-reviewed`，每日自動掃描修復。
4. **AdminEventTable 紅色徽章**：每列若 `name_zh` 或 `name_en` 為 NULL，顯示 `⚠ name_zh / name_en` 提醒管理員。

**Lesson：**
1. **設計 annotation_status 保護規則時，必須同時考慮「已 reviewed 但翻譯未完整」的邊界狀況**。
2. 事件審核前應確認所有關鍵翻譯欄位已填齊。
3. 規則已寫入 SKILL.md §Reviewed Event Translation Guard。

---
## 2026-04-28 — 翻譯大規模回歸：scraper commit 意外洗掉 web/messages
**錯誤：** commit `1d3cd1c`（標題：fix scraper expand taiwan_matsuri）在修改 scraper 的同時，把 `web/messages/zh/en/ja.json` 覆蓋成舊版快照，將之前四、五個翻譯 commit 的成果全部洗掉。受害清單：
- `categories` 遺失：`competition`、`indigenous`、`history`、`urban`、`workshop`、全部 `group_*` 群組標籤（5 個）
- `categories` 標籤值還原為舊版：`performing_arts` en/ja、`geopolitics` en/ja
- `filters` 遺失：`timeModeAll`、`locationOnline`
- `admin` 遺失：`source`、`annotationLabel`、`annotationStatusLabel`、`scrapedAt`、`filterAnnotatedShort/ReviewedShort/ErrorShort/PendingShort`、`selectAll`、`bulkHide/Show`、`bulkForceRescrape`、`forceRescrapeOn/Off/Queued`、`statsTotalEventsLabel`、`statsActiveCount`、`statsPendingLabel`、`statsUsersLabel/Desc`、`statsReportsLabel/Desc`、`pendingSummaryInactiveOnly`、`bulkCommonCategories/Hint`

**根本原因：** AI 在大 context 中同時持有新舊版翻譯快照，將舊版本作為整份 JSON 輸出，覆蓋了所有中間的增量改動。

**修復：** 以 Python 腳本從 `b5a574a` / `65b90ca` / `471b66d` commit 取回正確值，逐一 merge 回三個語言檔案，並以 assert 驗證後 push。

**Lesson：**
1. **Scraper / non-web commit 絕不應修改 `web/messages/*.json`**
2. 翻譯 key 只增不減；刪除 key 前必須確認 codebase 無任何引用
3. 規則已寫入 SKILL.md §i18n Regression Prevention

---
## 2025-05-04 — Session 61b5118d 效率復盤：三個高工具數反模式
**觀察：** session `61b5118d` 共 54 回合、945 次工具呼叫，平均 17.5 次/回合（正常 < 12）。
分析出三個反模式：
1. **URL + 隱含大範圍**：貼 URL + 「請檢查類似狀況」→ 全域掃描（T04 61 tools, T12 68 tools）
2. **「請繼續做 XXX」連發**：同類爬蟲拆成 7 輪分別要求，每輪重新載入 context（T08–T14）
3. **問題 + 修正 + 規則更新三合一**：每個 bug 立即觸發 fix + history + skill 三連寫（T21→T22 71 tools）

**改善規則（已寫入 `session-analytics/SKILL.md`）：**
1. 指定明確範圍：「僅修這個 event，規則稍後批次更新」
2. 一次列出全部任務：「建 A、B、C 三個爬蟲，按順序，每完成告訴我」
3. 累積再批次：「先修 bug，我說『批次更新 skill』時再一次整理」

**Lesson：** 提示模式本身就是可優化的成本來源。每月 `--days 30` 確認效率趨勢，高峰 session 用 `--verbose` 定位回合後，對照三個反模式判斷原因。

---
## 2026-04-26 — AdminEventTable filter label/style regressions repeated across multiple commits
**Error:** Three UI fixes (`tFilters("search")` search label, `tFilters("category")` category label, `bg-gray-50` category button) were re-introduced and re-regressed multiple times because later commits modifying the same file for unrelated reasons (bulk-toggle refactor, reannotate label rename) overwrote the corrected lines with default values.
**Fix:** Re-applied the three fixes; added protected-invariants rule to `engineer/SKILL.md`; added regression entry to `engineer/history.md`.
**Lesson:** Files with frequently-touched UI logic accumulate "sticky regressions". The architect plan for any `AdminEventTable.tsx` change must explicitly mention the protected invariants as a check item.

---
## 2026-04-26 — Online canonical form corrected: location_address must be 'オンライン', not NULL
**Error:** Previous session established `location_address = NULL` as the canonical form for online events. This was wrong: it caused online events to appear in the `tokyo` admin filter (which treats NULL address as "Tokyo"), and `other_japan` filtering relied solely on `location_name` to exclude online events, creating fragile single-point-of-failure logic. The `AdminEventTable.tsx` `other_japan` filter had no online exclusion at all, meaning online events would appear there too.

**Fix:**
1. New canonical form: `location_name = 'オンライン'`, `location_address = 'オンライン'`. Both columns set. DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
2. `peatix.py`: all 3 places that set `location_address = None` for online events changed to `= 'オンライン'`.
3. `connpass.py` + `doorkeeper.py`: `_normalize_location_address()` now returns `'オンライン'` instead of `None`.
4. `AdminEventTable.tsx`: added `if (addr.includes('オンライン')) return false` to `other_japan` filter.
5. `page.tsx`: updated comment; filter logic unchanged (still queries `location_name`).
6. DB: patched 7 peatix online events (`location_address = 'オンライン'`, zh/en translations set).

**Lesson:** `location_address = NULL` must not be used as a sentinel for "online" — NULL means "unknown/unset", not "online". Scrapers must always set `location_address = 'オンライン'` for online events. Any filter that gates on `location_address IS NOT NULL` will mis-classify events if online events have NULL address. Updated "Online Location Standard" rule in SKILL.md.

---
## 2026-04-26 — Online location filter broken: queried wrong column + scrapers lacked normalization
**Error:** The `location=online` filter in `page.tsx` queried `location_address ILIKE '%オンライン%'`. After the correct normalization (online events should have `location_address = NULL`), the filter returned 0 results. Additionally:
1. Several peatix events had `location_name = 'オンライン（Zoom）'` with non-null address — the `(Zoom)` suffix was not canonicalized and the address was not cleared.
2. `connpass.py` and `doorkeeper.py` had no online detection at all — API fields `place`/`venue_name` containing 'オンライン' were passed through without normalization.
3. `other_japan` filter excluded online via `location_address NOT ILIKE '%オンライン%'` which also failed once addresses became NULL.

**Fix:**
1. `page.tsx`: online filter → `location_name ILIKE '%オンライン%'`; other_japan exclusion → `location_name NOT ILIKE '%オンライン%'`.
2. `peatix.py`: added final canonicalize step after all fallbacks: if `location_name` matches online marker → `'\u30aa\u30f3\u30e9\u30a4\u30f3'`, address = None.
3. `connpass.py` + `doorkeeper.py`: added `_ONLINE_RE`, `_normalize_location_name()`, `_normalize_location_address()` helpers.
4. DB: cleared address for 7 active peatix events with online markers.

**Lesson:** The canonical online event representation is **`location_name = '\u30aa\u30f3\u30e9\u30a4\u30f3'`, `location_address = None`**. Any query filtering for online events must check `location_name`, not `location_address`. All scrapers must normalize their output before building the Event object. Added “Online Location Standard” rule to SKILL.md.

---
## 2026-04-26 — Peatix online event incorrectly assigned a physical address (×2 errors in same session)
**Error:** Event `05aefbdf` (周美花講演) is a hybrid/online event. Peatix renders its LOCATION block as a single line `"LOCATION\n\nOnline event"` — no second group. The scraper's primary regex (`LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})`) requires two groups separated by a blank line, so it didn't match. All CSS and regex fallbacks then ran, finding:
1. A campus name from the description body text → `location_name = '桜美林大学新宿キャンパス'`
2. `東京都新宿区` from the description → `location_address`

In the same session, the previous turn had wrongly "verified" and patched this same event with the full campus address `東京都新宿区百人町3-23-1`, compounding the error.

**Fix:**
1. Added `is_confirmed_online` guard in Peatix scraper: detect `LOCATION\n\n(Online event|オンライン|…)` FIRST, set the flag, and skip ALL subsequent address fallbacks.
2. Fixed final body-text online fallback to set `location_address = None` (was `'オンライン'`).
3. Patched DB event `05aefbdf`: `location_name='オンライン'`, all address fields `None`.

**Lesson:** When a Peatix LOCATION block contains an online marker, it must **immediately short-circuit all address extraction**. Address fallbacks must never run against the event description body — venue names mentioned in prose ("会場…桜美林大学") are conditional/secondary and must not become `location_address`. Added rule to SKILL.md under Online Events.

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.
