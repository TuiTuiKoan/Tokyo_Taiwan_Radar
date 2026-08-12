---
description: "Campaign Closer error history and lessons learned"
ms.date: 2026-08-12
---

# Campaign Closer Error History

<!-- Append new entries at the top -->

---

## 2026-08-12 — 已知邊界（第三輪反例狩獵後**刻意不修**的四項）

Tester 第三輪對 A3 的 `workspace.yaml` / lock 檔名狩獵了 9 種新輸入形狀，**沒有找到具現實性
的假 `SOLE_OWNER`**。但過程揭露一個結構性根因，記在這裡當作下次擴充的起點。這一條不是錯誤
紀錄，是**明知而暫不修**的決策紀錄。

### 根因：`git_root` 存在但不可用時，`cwd` fallback 永遠不會被諮詢

* **位置**：A3 解析區的 `[ -z "$sroot" ]` — 只在 `git_root` 擷取結果為**空字串**時才退回 `cwd`。
  「擷取到了、但值不可用」不算空，於是 fallback 整條路徑被跳過。
* **觸發形狀**：
  * **S3** — `git_root: |` 區塊標量：`sroot` 被擷取成字串 `|`。
  * **S5** — `git_root` 縮排在某個父鍵之下：`^git_root:` 錨點不成立，改由 `cwd` 分支取值或落空。
* **為何類別守衛也接不住**：`sroot` 非空（`[ -z ]` 不成立），且不含目標 basename
  （`unparseable_but_names_target` 不成立），兩道防線都不觸發 → **靜默略過**。
* **本次不修的理由**：兩者都要求外部格式變成現行 writer 不會產生、或根本不是合法 YAML 的
  形狀——區塊標量只用於含換行的字串，路徑不會；縮排代表另一套 schema。三輪實測現行格式
  一致為「無引號絕對路徑 + `inuse.<pid>.lock`」。
* **未來若要修，最省的做法**：`git_root` 解析後，若 `[ -d ]` 失敗**且** `cwd` 可解析，就再用
  `cwd` 試一次。方向保守——只會增加 `CONTENDED` / `UNDETERMINED`，不會影響任何已驗證的
  通過路徑（`RETIRE_CANDIDATE` 仍需全部來源有數字且無競用）。

### 另外三項同類邊界（同屬「現行 writer 不產生」）

| 形狀 | 現行行為 | 若要修 |
|---|---|---|
| 隱藏檔 `.inuse.<pid>.lock` | glob 不匹配 → 該 session 不計入 | lock glob 增列 `.inuse.*.lock` |
| `inuse.<pid>.lock.tmp`（寫入中的暫存） | glob 不匹配 → 不計入 | glob 增列 `.tmp` 後綴，或改用前綴比對 |
| 重複的 `git_root` 鍵 | `sed -n '1p'` 取第一個；YAML 語義上後者才生效 | 改取最後一個，或偵測到重複即判 `UNDETERMINED` |

三者都只影響「誰被計入競用」，方向與上一條相同：修了只會更保守。

### 為什麼此刻不動程式碼

這個 session 已經出現三次「小修引入新問題」：`trim()` 絞碎含空白路徑、畸形條件式通過
`bash -n`、剝引號與去空白順序相反。現在測試全綠、shellcheck 零告警，而 S3／S5 需要現行
writer 不會產生的（甚至不合法的）YAML 才觸發。**此刻改動的期望值是負的。**

**教訓：把「已知但不觸發」記成有明確修法的邊界，比在綠燈狀態下動刀更有價值。** 記錄要
包含三件事才算完整——觸發條件、為何現有防線接不住、以及最省的修法方向。少了第三項，下次
接手的人只會看到一個模糊的警告，然後選擇重寫。

---

## 2026-08-12 — Tester 反例：打錯一個字母，A2 閘門形同虛設

**錯誤**：`--slug publication-polcy`（正確拼法少一個 `i`）對 `ttr-publication-policy-worktree`
執行稽核，得到 `spec_tasks=0`、`deferred_markers=0`、`unhandled_total=0`。同一個 worktree 用
正確 slug 是 `unhandled_total=24`。**24 筆未處理待辦被靜默報成 0。**

**根因**：來源 1／2 只判斷「`docs/specs/active/<slug>/tasks.md` 這個檔案在不在」。檔案不在的
原因有兩種——「這個 campaign 沒有 spec」與「slug 打錯了」——程式碼把兩者都當成前者，輸出 `0`。

**修正**：讀檔前先解析 `docs/specs/active/<slug>/`（再退而求其次試 `archive/<slug>/`）。目錄
不存在 → 兩個來源都輸出 `not_checked` 並計入 `not_checked_sources`，verdict 因此是
`UNDETERMINED:spec_dir_unresolved`（exit 20），而不是放行。目錄存在但缺 `tasks.md` 才輸出 `0`。

**教訓**：**「檔案不存在」永遠有兩種解釋，只有其中一種是 `0`。** 這個 agent 的整份設計都建立
在「`0` = 查過了沒有、`not_checked` = 沒查」之上，而第一版自己就在最核心的來源上違反了它。
凡是把外部輸入（slug、路徑、SHA）拿去查表的地方，都要先問「查不到是因為沒有，還是因為輸入
錯了」——分不出來就是 `not_checked`。

**連帶修正（同批，來自同一次反例演練）**：

* lock 檔名 glob 只匹配 `inuse.*.lock`，漏掉 `inuse.lock`（無 pid 段）。
* `git_root` 的值未剝除 YAML 引號，帶引號時 `[ -d ]` 與字串比對雙雙落空。

兩者都會讓一個**活著的 session 被靜默跳過**，直接產出 `SOLE_OWNER` → `RETIRE_CANDIDATE`。
現行 Copilot CLI 的實際格式不會觸發，但那是**別人的格式契約**，不該假設它永不變。原則：
**解析要寬，結論要嚴——格式看不懂但仍疑似指向目標，落 `UNDETERMINED`，不是跳過。**

**順帶避開的坑**：剝引號後原本要接 `trim()`，但該 helper 是 `tr -d '[:space:]'`（去除所有空白，
只適合 `wc -l` 的數字輸出）。本 repo 路徑含空格（`Tokyo Taiwan Radar`），套上去會把路徑打斷。
另拆 `trim_edges()` 只去前後空白。**去空白的 helper 不是通用的，用在路徑上要先確認語義。**

---

## 2026-08-12 — F2 的修法本身寫反了順序，等於只修一半

**錯誤**：上一條的引號剝除修好了 `git_root: "<路徑>"`，卻修不好
`git_root:` + **兩個以上空白** + `"<路徑>"`。後者仍然得到假 `SOLE_OWNER`。

**根因鏈**：擷取用的 `sed -n 's/^git_root: //p'` 只吃掉**一個**空白，剩下的前導空白留在值裡；
剝引號的 sed 錨在 `^"` 與 `"$`，**錨點因此不成立，引號原封不動存活**；接著 `[ -d ]` FALSE、
字串比對失敗，最後在 `matched` 檢查處靜默 `continue`。順序寫成「先剝引號、後去空白」時，
去空白發生在錨點失敗之後，永遠來不及。

**修正**：三處一起改，不靠單點。(a) 擷取改 `s/^git_root:[[:space:]]*//p`，來源端就不留前導
空白；(b) 比對前的順序對調成**先 `trim_edges`、再剝引號**；(c) 在 `matched` 檢查前加類別
守衛——`resolved=0` 且比對不中時，原字串含目標 basename 就判 `UNDETERMINED`。

**教訓一：錨定式的清理有順序依賴，順序本身就是正確性的一部分。** `^`／`$` 錨點的 sed 對
「前面還有沒有雜訊」極度敏感。凡是「正規化 + 錨定比對」的組合，去雜訊必須排在錨定之前，
而且來源端與比對前**兩道都要有**——它們覆蓋的輸入不同，只做一道就是這次的翻版。

**教訓二：修完一個變體不等於修完一類。** 前一條已經寫下「解析要寬，結論要嚴」，實作卻只
針對當時手上的那個變體補正規表示式，沒有落實成守衛。因此 SKILL.md 寫了契約、程式碼沒有
兌現，不成對引號與未展開的 `~` 都還是被靜默丟棄。**契約寫進 SKILL.md 的同時，要有一個
涵蓋整類的實作，並用「沒見過的變體」而不是「已知的變體」來驗收。**

**守衛的邊界**：只在 `resolved=0` 時適用。已成功解析、確定指向別處的路徑照常跳過——否則
每個名稱相近但無關的活躍 session 都會把結果拖成 `UNDETERMINED`，把反 fail-closed 的設計
再推回 fail-closed。已用「可解析且名稱相近的無關路徑」反向驗證仍得 `SOLE_OWNER`。

---

## 2026-08-12 — Agent 建立：從既有失敗案例反推的五條偵測規則

**背景**：本 agent 在建立時沒有自己的錯誤史，但它要防的每一種失敗都已經在別處發生過。
以下五條是把別人的事故翻譯成本 agent 的偵測規則，記在這裡以免日後被當成過度設計而砍掉。

| 既有事故 | 本 agent 的對應規則 |
|---|---|
| 2026-08-08 主工作樹 11 個檔案（+550/−134）被平行 session 的 `git stash` 掃走 | Phase C 的結案記錄一律寫在 campaign worktree 內，不寫主工作樹 |
| `ttr-admin-qa-cleanup-worktree` 在不到一小時內從「五檔殘骸」變回「逾千檔完整 checkout」 | D1 移除前必須重新觀測六值；先前的 PASS 絕不帶進移除 |
| Eslite 記錄第一版只寫「本報告落地後即可移除」，之後又有兩個 commit 落在同一份記錄上 | `Worktree disposition` 在 C1 階段填 `pending`，決策時間戳與六值一起補 |
| 兩個獨立 campaign 都留下同形狀的未註冊殘骸 | D4 殘留驗證用實際目錄名，不假設 `ttr-<slug>-worktree` |
| campaign baseline 與 rollback 快照常是全機唯一副本 | D2 ignored artifact preflight 必須逐筆分類並記 SHA-256 |

**教訓**：這五條沒有一條是預防性設計，全部是既成事故的複寫。要刪任何一條之前，先找出對應事故
為什麼不會再發生。

---

## 2026-08-12 — 三個實測發現，推翻了偵測設計的三個直覺假設

**問題**：`Close Campaign & Retire Worktree` 的初版設計用了三個看起來理所當然的判準，
實測後全部不成立。

**根本原因與修正**：

1. **PID 存活判準** — 直覺是「lock 檔名裡有 pid，檢查該 pid 還在不在就知道 session 是否活著」。
   實測本機三個互不相干的 session 全部記為 `pid=58145`，因為 Copilot CLI 共用同一個 Code Helper
   進程。任何 PID 存活測試都會把無關 session 判成競用者。
   **修正**：偵測邏輯完全不讀 PID，改用 `inuse.*.lock` 的存在 + `events.jsonl` 的 mtime。

2. **`turn_index` 切片** — 直覺是 `assistant_usage_events.turn_index` 可以把一個 session 切成
   多個回合。實測本 session 的 92 列 usage **全部 `turn_index=1`**，而 transcript 有數十個 turn。
   **修正**：Stage 2 若解凍，切片軸只能用 `created_at` 時間窗；`turn_index` 全面禁用。

3. **`origin/main...HEAD` 掃 TODO** — 直覺是「本地相對 main 的新增內容」就是本次 campaign 的範圍。
   實測 V-M-D push 之後 `HEAD` 就等於 `origin/main`，三點形式恆為空，會對每一個真的出貨過的
   campaign 回報零待辦。
   **修正**：commit range 由交接契約帶入的 `<base>..<head>` 決定；拿不到 base 就標 `not_checked`。

**教訓**：三個假設的共同點是「這個欄位看起來就是這個意思」。凡是要當成閘門判準的欄位，
先實跑一次確認它的實際分布，不要從名字推語義。

---

## 2026-08-12 — fail-closed 會把功能鎖死：`UNDETERMINED` 必須是可解除的

**問題**：A3 的初版規則寫成「任何無法確認的 session 一律視為競用」。看起來安全，實際上會讓
退役流程永遠無法通過——本機就有一個開在完全無關專案目錄（`~/Downloads/...`）的 session 持有 lock
且 `workspace.yaml` 沒有 `git_root`，它會讓**每一個** worktree 都被判成競用。

**根本原因**：把「保守」誤解成「所有未知都是阻擋」。保守的正確語義是「未知不放行」，
不是「未知永久封鎖」。

**修復**：
* 沒有 `inuse.*.lock` 的 session 不計入。
* 有 lock 但 `git_root` 缺失時退回 `cwd`，只有兩者皆無才升為 `UNDETERMINED`。
* `UNDETERMINED` 的處置定義為「停下來問人」，由使用者確認後可解除。
* verdict 優先順序：硬阻擋 > 未知。一個確定髒掉的 worktree 判 `HOLD:dirty`，
  不會因為同時有未知項而被降級成 `UNDETERMINED`，掩蓋掉真正該修的東西。

**教訓**：每寫一條 fail-closed 規則，就要同時跑一次 positive control——找一個**應該通過**的
對象確認它真的通過。只測「該擋的有沒有擋住」，會做出一個誰都過不了的閘門。
