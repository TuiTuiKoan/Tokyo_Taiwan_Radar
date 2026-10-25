---
description: "Campaign Closer error history and lessons learned"
ms.date: 2026-08-12
---

# Campaign Closer Error History

<!-- Append new entries at the top -->

---

## 2026-10-25 — 來源 5 排除 `deferred-work` label

出處：#344（heartbeat）。**症狀**：`AGENTS.md` 要求剩餘待辦開 issue，這些 issue 讓每次結案都判 `HOLD:unhandled_work`。
**修法**：`scripts/campaign-closeout-audit.sh` 新增 `ISSUE_DEFERRED_LABEL="deferred-work"`，來源 5 搜尋多排除此 label；
測試 `test_open_issue_search_excludes_daily_review_and_deferred_work_labels` 更新；SKILL 補述用法。label 由使用者貼。
**NOT TESTED**：真實 `gh` 搜尋語法（雲端無憑證）；`gh` 的 `-label:` 可重複，與既有 `daily-review` 同型。

---

## 2026-10-22 — authoritative-venue-repair 結案：push 日期、平行 session 開 issue 造成 HOLD、裸 `cd` 重犯

出處：#344；結案記錄 `docs/evaluation/campaigns/2026-10-22-authoritative-venue-repair.md`。

### 1. push 日期不等於 author date

**現象**：第一段 push 的 commit 作者日期是 2026-08-06，協調者交接時寫成「08-06 推上 main」。closer 從
`origin/main` reflog 的 `update by push` 查出實際 push 是 2026-08-09 14:49（`8113549c` → `01754b85`）。
**根因**：腳本段落輸出印 author date；rebase 後才 push 的 commit，author date 早於 push。
**教訓**：沒有 V-M-D handoff 時，push 時間與 base/head 都從 reflog 推，再用 first-parent 交叉核對。規則寫入
SKILL § 多次 push 的 campaign。

### 2. Phase A 到 D 之間，平行 session 開的 issue 讓結論變成 HOLD

**現象**：Phase A（06:36Z）`UNDETERMINED`。平行 session 依新的 `AGENTS.md` 進度追蹤規則開了 parked runbook 的代表卡
#339（07:09Z），動筆前重跑變 `HOLD:unhandled_work`。協調 session 自己在第 3 次稽核之後開了 #341（07:52Z），
結案記錄沒寫到它，D1 重跑又多一個阻擋。兩次都是「動筆前、移除前重跑稽核」才抓到；使用者兩次裁定為
Deferred work 的追蹤位置，#341 於 D5 以 Update 段落補進記錄。
**根因**：進度追蹤規則要求剩餘待辦開 issue 並貼 `spec:<slug>`，來源 5 則把這些 issue 算成未處理待辦，兩者
方向相反；而 issue 可能在 Phase A 之後才出現。
**教訓**：Phase C 動筆前與 D1 都重跑腳本；新 issue 是新的阻擋，舊的同意不涵蓋它。規則寫入 SKILL § 來源 5：
平行 session 新開的 issue。腳本是否排除已裁定的追蹤卡，留待 #344 決定。

### 3. 裸 `cd` 進受稽核的 worktree（既有規則重犯）

**現象**：closer subagent 在 Phase A／C 直接 `cd` 進 `ttr-authoritative-venue-repair-worktree`，自己與協調 session
的 primary working directory 都被改標成該 worktree。`lsof` 確認移除前沒有行程停留，沒有影響退役。
**根因**：SKILL § 在 Bash 工具裡解析路徑（2026-10-14 條目）只舉「解析別的 worktree 路徑」的例子，執行者沒把它
套用到受稽核的 worktree 本身。
**教訓**：整個 Phase A–D 都不 `cd` 進受稽核的 worktree。agent 檔 A0 加上硬性提醒，SKILL 同節補記重犯。

---

## 2026-10-22 — 稽核腳本只試 `archive/<slug>`，與 README 規定的日期前綴命名對不上

**事實**：2026-08-12 的 `spec_dir_unresolved` 修正（見下方同日條目）把 fallback 寫成 `archive/<slug>/`。但 `docs/specs/README.md`
規定的歸檔命名是 `archive/<YYYY-MM>-<slug>`。ai-portability 的結案記錄（2026-10-14）在 spec 還在 `active/` 時就預告：
歸檔後重跑稽核，兩個 spec 來源會因 slug 解析不到而 `not_checked`。2026-10-20 歸檔成 `archive/2026-10-ai-portability/` 之後，
這個預告成真，改由 commit `fix(agents): campaign closeout audit resolves date-prefixed archive directories`（2026-10-22）
修腳本（目錄維持 README 規約，不為了遷就腳本改名）。

**為何當初只試 bare slug（推測）**：2026-08-12 時 repo 唯一的歸檔實例是沒有前綴的 `archive/feedback-loop/`
（plan-critic history 2026-08-02 已記錄 README 與實況矛盾）；推測當時是對著這個唯一樣本實作，沒有用 README 寫的拼法造測資。

**如何被發現**：不是稽核跑出錯誤——bare slug 的 fallback 對現存樣本沒有問題。從結案記錄的文字可見，是撰寫記錄時把腳本的解析規則與
README 的命名規約並排比對，才看出兩者不是同一個拼法，並在歸檔前就寫成預告。

**教訓**：腳本要解析的命名規約若由文件定義，測資必須用**文件寫的拼法**造，不能只用現存實例；現存實例只有一個且與文件不一致時，
風險最高。規則本文（active 優先；archive 以目錄名或去掉 `^YYYY-(01-12)-` 後做字串相等，不是 glob；0 筆
`spec_dir_unresolved`、≥2 筆 `spec_dir_ambiguous`，皆 `not_checked`、不猜）已在 SKILL.md § `not_checked` 與 `0` 是不同的主張、
agent 檔 A2 與 `docs/evaluation/campaigns/README.md` 同步複述，這裡不重複；改這條規則要三處同動。實作用 `case` 樣式與
`${name#????-??-}` 剝前綴（相容 macOS 預設的 bash 3.2）；slug 只做 `=` 比較，不進 glob。

---

## 2026-10-22 — 搬移 spec 後的結案記錄：搬移可能由兩顆 commit 承載，且已提交的陳述不原地改寫

**事實 A（rename 被併進別的 commit）**：ai-portability 的 `docs/specs/active/ai-portability` → `docs/specs/archive/2026-10-ai-portability/`
共 10 檔 rename。`docs(specs): archive ai-portability and repoint live references`（2026-10-20）只改了 `status` 欄位與 7 個檔案的引用，
`git show --stat` 看不到任何 rename；真正的 10 檔 rename 在同日的 `docs(specs): drop the retired ttr-v8 worktree from the workstream ledger`
裡。`git log --follow --diff-filter=R -- <新路徑>` 只印出這顆 ledger commit，主旨與本 campaign 無關，若直接拿它的輸出當「搬移
commit」引用，讀者會看到一個牛頭不對馬嘴的主旨。

**事實 B（原地改寫已提交陳述）**：上述 archive commit 把結案記錄中「The move has **not happened**」整段原地改成「The spec moved to …」。
記錄當時的陳述是真的，被改掉之後，讀者無法分辨記錄當時知道什麼、現在知道什麼。事後由
`docs(agents): append post-move update to ai-portability record, repoint parked`（2026-10-22）還原原段，並追加
`### Update after the move (2026-10-22)`。

**教訓**：
1. 結案記錄引用「搬移 commit」前，用 `git show --stat <commit>` 核對它**實際承載 rename**（輸出有 `rename`／`=>` 的檔案行）；
   `--follow --diff-filter=R` 只是定位指令，印出來的可能是不相干的 commit。若 rename 與 status／引用更新分在兩顆，如實寫「兩顆
   commit 承載」，各自附主旨與日期，不放裸 SHA（rebase 會改 hash）。
2. **已提交的結案記錄不原地改寫。** 搬移後才成立的事實，只在記錄尾端追加 `### Update after the move (<date>)` 段：不刪既有行、
   不放裸 SHA、Correction 區維持原狀（那裡只放「當時就是錯的」）。「當時是真的、現在過期」不是 Correction，也不是改寫的理由。
   這條與 `docs/evaluation/campaigns/README.md` § Correction（錯誤陳述不得靜默覆蓋或刪除）同一精神，只是對象換成「已過期」的陳述。

---

## 2026-10-20 — vmd-summary-ai-scope 退役：整塊對帳順帶移除過期行，且對帳指令被 guard 擋下

**事實 A（順帶移除過期行）**：退役 `ttr-vmd-summary-ai-scope-worktree` 時，依 `git.instructions.md` 以 live worktree 推導目標清單、
整塊重寫 `ttr-*-worktree/` 區塊。除了本 campaign 的那一行，`ttr-deps-security-worktree/` 也一併被移除——該 worktree 已被另一個
session 退役，那行本就過期。這是對帳（convergent、idempotent）的預期行為，不是 bug，也沒有誤刪 live worktree 的行。

**教訓 A**：退役報告要明確告知使用者「順帶移除了非本 campaign 的過期行」並逐行列出，否則會被誤認為事故。已寫入
`git.instructions.md` § Reconciling 與 SKILL.md 「回報規則」。

**事實 B（guard 擋下對帳 one-liner）**：`git.instructions.md` 的對帳 one-liner 含命令替換、`while` 與 process substitution
（`comm -23 <(…) <(…)`）。Claude Code hooks 啟用時，guard 回報 `blocked [unsupported-syntax] the command uses syntax the guard
cannot verify`，整條指令被擋（指令未執行，exclude 未變）。這一點與下方「### 3」是同一類事件，不重複其處置。

**本次實際處置**：拆成簡單命令——先 `git worktree list --porcelain | grep '^worktree '` 與
`grep -E '^ttr-.*-worktree/$' .git/info/exclude` 分開比對，確認區塊內其餘 live 行都已存在、只多出剛退役的一行，再用單行
`grep -vxF '<行>' .git/info/exclude > .git/info/exclude.tmp && mv …` 移除，最後 grep 該區塊驗證與 live worktree 一一對應。

**教訓 B**：這個單行移除只在「區塊內其餘 live 行都已存在」且「當下沒有別的 session 在寫 exclude」時才與整塊對帳等價；第二個
條件無法可靠驗證（2026-08-14 事故），因此只記為備案，不升級為規則，也不放寬「不可盲刪單行」。被 guard 擋下時停下用拆開版，
不得用 `--dangerously-skip-permissions`、`disableAllHooks` 繞過。`git.instructions.md` 先前完全沒提 hook 會擋對帳指令，已補一段指向
本 SKILL.md。`pwd -P` 物理路徑推導（大小寫與 `3-TTR` 前綴變體路徑）已在 SKILL.md 「exclude 對帳的目標清單」記錄，這次不重複。

---

## 2026-10-20 — 寫 recovery capsule 之前，主工作樹 main 可能與 origin/main 分歧

**事實**：`iwafu-taiwan-relevance-gate` 準備移除時，主工作樹 `main` 領先 `origin/main` 2 個、落後 1 個（別的 session 留下未推送的 commit）。`git pull --ff-only` 會失敗；而遠端分支刪除後，`git branch -d` 改以主工作樹 HEAD 判斷「已合併」（機制見下一則），`main` 不含分支 tip 就會被拒，`-D` 又被禁止。

**規則**：寫 capsule 與給指令之前，先檢查 `git rev-list --left-right --count origin/main...main` 為 `0 0`，或至少 `main` 已含分支 tip；否則先停手，等該 session 推送完。已放進 agent 檔 D1 與 SKILL.md § Phase D 的 Cleanup 檢查。

---

## 2026-10-20 — rebase 合併後 `ahead>0` 是誤報，但 agent 不得自行放行

**事實**：`fix/iwafu-taiwan-relevance-gate` 的兩個 commit 經 PR 295 以 rebase 方式合併，`main` 上 SHA 不同（28999b39→116203a3、294d3a50→7f8e75c9）。審核腳本回 `HOLD:ahead`（`ahead=2`），但內容已全部在 `main`。佐證：`git cherry origin/main <branch>` 只有 `-` 開頭、沒有 `+`；`git patch-id --stable` 兩邊逐一相同。使用者看過證據後接受例外，結案記錄的 Known risks 寫明例外，腳本判定不改。

**規則**：`ahead>0` 仍是硬阻擋，agent 不得自行放行；附 cherry＋patch-id 證據交使用者決定。rebase 之後再提交記錄時，已合併的 commit 會被自動略過（"skipped previously applied commit"）。

---

## 2026-10-20 — 退役後 `git branch -d` 的判定基準會隨遠端刪除改變

**背景**：`iwafu-taiwan-relevance-gate` 退役（記錄 `docs/evaluation/campaigns/2026-10-20-iwafu-taiwan-relevance-gate.md`）。該分支 `ahead=2`，兩個 commit 在 `main` 上已有等價 commit（內容等價但 SHA 不同）。

**現象**：使用者先 `git push origin --delete`，再 `git branch -d`，後者通過。

**原因**：遠端刪除同時移除了本地的 upstream tracking ref；沒有 upstream 時，`-d` 改以目前 checkout 的 HEAD 判定「已 merge」，而主工作樹包含該 tip，所以通過。順序顛倒（先 `-d` 後刪遠端）時，`-d` 以 upstream 為基準，可能因 SHA 不同而被拒。

**教訓**：D3 給使用者的指令順序要寫明（remove worktree、刪遠端、`-d`），並說明 `-d` 通過是因為 tracking ref 已消失，不代表分支沒有獨有 commit；獨有 commit 的判定仍以 A2 / `git cherry` 為準，不以 `-d` 的結果代替。

---

## 2026-10-14 — 補兩點實測缺口：腳本版本落後的 worktree、終端機分頁的 shell 占用

**背景**：兩點都是 ai-portability 結案（2026-10-13）的 Phase A、D 實際經過，先記在 parked spec
（`docs/specs/parked/ai-portability-followups.md` 的結案後新增項），這次寫進 agent 檔與 SKILL.md。對應規則在
agent 檔 Phase A 與 D1，以及 SKILL.md § 重新觀測 session 占用、§ 腳本。

### 1. 受稽核 worktree 裡的腳本比稽核邏輯舊

**現象**：標準呼叫是從受稽核的 worktree 執行 `bash scripts/campaign-closeout-audit.sh`，但
`ttr-ai-portability-worktree` 停在 `87c2b557`，那裡的腳本不認得 `--range`。

**修正**：改用已含新版腳本的 checkout 的絕對路徑呼叫，並以 `--worktree` 指向受稽核者。不為了跑腳本去移動
或 rebase `feat/<slug>`。

**教訓**：腳本版本跟著被稽核的分支走，而被稽核的分支 tip 恰好是要觀測的值之一，兩者不能用同一個動作對齊。

### 2. `/exit` 不釋放 cwd

**現象**：agent session 結束後，終端機分頁的外層 zsh 仍以 worktree 為 cwd。SKILL 原本只說「關閉對應的
終端機或 session」，沒有說明 session 結束後 shell 仍持有 cwd。

**修正**：占用名單把分頁的外層 shell 列為獨立的占用者，請使用者**關閉分頁**，不是只 `/exit`。

**教訓**：使用者以為「結束了 session」與作業系統看到的「還有行程以該目錄為 cwd」是兩件事。要求他做的動作
必須對得上偵測所看的東西。

---

## 2026-10-14 — exclude 對帳的目標清單：用物理路徑推導，並以 worktree 計數當 STALE 閘門

**背景**：closeout-audit-multirange 退役的 D3，要把 `.git/info/exclude` 的 `ttr-*-worktree/` 區塊收斂到仍然存活
的 worktree。這一次沒有出錯：這條記錄的是實際做對的推導方式，以及它擋掉的失效模式。相鄰的兩條教訓（裸 `cd`、
整塊複合腳本被 hook 擋下）都出在這一步，所以放在一起。對應規則已寫進 SKILL.md § Phase D「exclude 對帳的
目標清單」。

### 1. 登記路徑不等於 root 之下的路徑

**現象**：20 個已註冊 worktree 中，要留在 exclude 的 8 個 `ttr-*` worktree 有 7 個登記在不是目前 root 字串
前綴的路徑：5 個在 `…/Development/Tokyo Taiwan Radar/…`，2 個在 `…/development/Tokyo Taiwan Radar/…`（小寫
d）。前者的父目錄是指向 `3-TTR/Tokyo Taiwan Radar` 的符號連結，後者靠大小寫不敏感的檔案系統。它們的物理路徑
都在 root 之下，所以都需要 exclude 行；只有 `ttr-iwafu-gate-worktree` 的登記路徑本身就在 root 之下。另外 10
個登記在兄弟目錄 `Tokyo Taiwan Radar.worktrees`，物理路徑在 root 之外，不需要行。

**根因（做錯會發生什麼）**：以登記路徑的字串比對 root 前綴，會把那 7 個存活的 worktree 判成 `external`，把它們
的 exclude 行當成多餘而刪掉。活的 worktree 重新出現在主樹的 untracked 清單，一個粗心的 `git add -A` 就會把它
掃進去。只看 basename 同樣分不出「在 root 之下」與「在 root 之外」。

**做法**：對每個已註冊路徑各下一條 `( cd "$WT" && /bin/pwd -P )` 取物理路徑；物理路徑在 `"$ROOT"/` 之下者取
basename 加 `/`，其餘不收。一條路徑一條指令，各自包子 shell，不用迴圈、不用裸 `cd`。

### 2. 目標清單是快照，用 worktree 計數當 STALE 閘門

**現象**：D1 的觀測到使用者執行 D3 之間隔了數分鐘到數小時，期間其他 session 可以新增或移除 worktree。同日
另一個 session 就推上了 `event-intake-wizard` 的結案記錄，平行 campaign 確實在動。

**做法**：貼上 D3 指令前，先輸出 `git worktree list --porcelain | grep -c '^worktree '`（本次 20，移除後預期
19）。不是預期值就視為 STALE：目標清單重新推導，不貼上先前產生的 `printf` 清單。移除後再算一次，應為預期值減一。

**教訓**：計數是最便宜的「世界變了沒」訊號，但它只偵測數量變化，偵測不到「一個移除、一個新增」的同數量替換，
所以不取代對帳後的 `comm -23`／`comm -13` 驗證。目標清單與 Freshness 六值一樣有時效，不能沿用先前的 PASS。

---

## 2026-10-14 — 在 Bash 工具單獨執行 `cd <worktree> && /bin/pwd -P`：cwd 漏進別的 campaign 的 live worktree

**背景**：ai-portability 退役的 D3 尾段做 `.git/info/exclude` 對帳。為確認各 live worktree 的物理路徑
落在 repo root 之下，當時的 session 對每個已註冊路徑下 `cd '<registered-path>' && /bin/pwd -P`。對應規則
已寫進 SKILL.md § Phase D「在 Bash 工具裡解析路徑」。本次沒有任何檔案被改到。

### 1. 裸 `cd` 讓整個 session 的 cwd 落在別人的 worktree

**現象**：該命令沒有包在 `( … )` 或 `$( … )` 裡。Bash 工具的 shell 狀態跨呼叫保留，cwd 因此停在另一個
campaign 的 live worktree（`ttr-v8-worktree`，分支 `feat/event-intake-wizard`）。同一批平行送出多個這種
`cd`，最後完成的那個決定 cwd，落點不可預期。Claude Code 隨後把 primary working directory 改標為該
worktree，並提示「請在該目錄執行、不要 cd 回 repo root」。使用者本來的任務屬於 main，那個分支不該收
commit。於是停下來問使用者 commit 要放哪裡，才用 `git -C` 加絕對路徑在主工作目錄的 main 上 commit。
多了一次確認，且整個 session 之後的 cwd 都不對。

**根因**：`cd` 與 `/bin/pwd -P` 被拆成兩段單獨執行。`/bin/pwd -P` 只是讀值，不會把 cwd 還原；`cd` 沒有
子 shell 包住，改的就是持久 shell 的 cwd。平行呼叫共用同一份 shell 狀態，各自的 `cd` 互相覆蓋。

**修正**：路徑解析只用兩種形式：包子 shell（`( cd "$WT" && /bin/pwd -P )` 或
`PHYS=$( cd "$WT" && /bin/pwd -P )`），或完全不 cd（`git -C '<絕對路徑>'`、絕對路徑）。平行呼叫不要各自
`cd`。cwd 已漂移時不靠 cwd 補救，先問使用者，之後用 `git -C '<絕對路徑>'` 明寫位置。

**教訓**：

* 文件已有正確形式：`docs/evaluation/campaigns/README.md` § Identity 的
  `PHYS=$( cd "$WT" && /bin/pwd -P )`。這次不是文件缺漏，是把一個複合式拆成兩段。抄範例要整段抄，包含
  外層的 `$( … )`。
* 對 live worktree 的後果比一般目錄嚴重：cwd 一旦落在別的 campaign 的 worktree，工具會把它當成工作位置，
  下一個 commit 就可能放錯分支。
* 本次沒有誤 commit，是因為動手前停下來問了使用者。那是補救，不是防線。

---

## 2026-10-14 — 平行送出的 Bash 檢查，結果顯示對不上呼叫順序

**背景**：同一個 D3 對帳中，同一批平行送出三個預期都會失敗的檢查。對應規則已寫進 SKILL.md § Phase D
「驗證類檢查帶明確標籤」。

### 1. 三個預期都失敗的檢查只有一個顯示 `Exit code 1`

**現象**：結果的顯示順序與送出順序對不上；三個預期都失敗的檢查，只有一個顯示 `Exit code 1`。無法靠
exit code 或結果順序判斷哪個檢查回了什麼。

**根因**：平行呼叫的結果由工具回傳，顯示順序與 exit code 是否出現，都不能當成「每個檢查各自的答案」。
確切機制本次沒有查證，規則不依賴它。

**修正**：驗證類檢查一律帶明確標籤，把結論寫進輸出文字：`<檢查> && echo '<名稱>=…' || echo '<名稱>=…'`。
`docs/evaluation/campaigns/README.md` § Cleanup checklist 的殘留驗證區塊已是這種形式
（`branch=STILL PRESENT`／`branch=deleted` 等）。

**教訓**：一個檢查的答案要自帶身份。標籤包含檢查名，同一批內就不會有兩條互相分不出來的 `ok`。

---

## 2026-10-13 — 稽核腳本補完：完整範圍偵測漏給的段落、空段落規則、可讀的未涵蓋輸出

**背景**：同日稍早的 `--range`（見下一條）避開了單一跨度被上游 commit 污染，但留下三個缺口，都在
ai-portability 結案前被指出。補完後同一組呼叫（兩段 `--range` 加上完整範圍 `--base`／`--head`）對舊
worktree 得到 `range_todo=0`、`uncovered_commits=10`、`uncovered_hits=7`、`open_issues=0`，verdict
`UNDETERMINED`。對應規則已寫進 SKILL.md § A2 與 agent 檔的交接契約。**本條取代下一條中三處說法：
「`--range` 與 `--base`／`--head` 互斥」、「重疊的 commit 算兩次」、「V-M-D 的 handoff 範本目前只有一組
base／head 欄位（本次未改）」——範本已在同批 commit 改為帶出成對 base／head 與完整範圍。**

### 1. 漏給一段的 `0`，與乾淨的 `0` 看起來一樣

**現象**：只傳 `--range` 時，少傳一次 push 不會有任何訊號；得到的 `range_todo=0` 只代表「有給的段落
沒有」，卻會被讀成整個 campaign 沒有。

**根因**：腳本只看得到呼叫端給的段落，沒有任何「應該涵蓋多少」的參照。

**修正**：`--base`／`--head` 與 `--range` 並用時是完整範圍。腳本輸出完整範圍內沒有任何一段涵蓋的
commit 數與其命中行數；沒給完整範圍時這兩個數字是 `not_checked`。未涵蓋的命中不計入 `unhandled_total`
（可能是別的 campaign 的工作），但 verdict 至多 `UNDETERMINED`。

**教訓**：「查過、沒有」需要一個分母。只給段落時，分母由呼叫端決定，腳本無從核對；完整範圍把分母交給
git。重疊的段改以 commit 集合去重，一個 commit 只算一次。

### 2. 兩端寫反或相等的段落回報 0

**現象**：`--range <head>..<base>` 或 `X..X` 是空集合，被當成乾淨的 0。

**修正**：`--range` 的段落若沒有任何 commit，回報 `not_checked`。刻意不做祖先檢查：base 不是 head 的
祖先是合法的分叉範圍（例如 push 前以 `origin/main` 為 base、而 feature 分支落後），必須照常計數。
單獨的 `--base`／`--head` 不套用這條，維持相容。

**教訓**：一次 push 至少交付一個 commit，所以「零個 commit」本身就是錯誤訊號，不需要祖先關係來判斷。

### 3. 只列 SHA 的輸出，人無從判斷歸屬

**現象**：未涵蓋的 commit 如果只印短 SHA，使用者要自己 `git show` 才知道它是誰的、動了什麼。

**修正**：每個新增了待辦字樣的未涵蓋 commit 都列出短 SHA、日期、作者、主旨、動到的檔案（最多 5 個，
其餘 `+N`）、命中行原文（約 150 字，附檔案路徑），再加一行歸屬提示；每一段也列出第一個與最後一個
commit 的短 SHA、日期、主旨。

**教訓**：歸屬提示（slug 是否出現在主旨或路徑）只是提示。slug 沒出現不代表不屬於這個 campaign，所以
它從不改變 verdict。判定歸屬的是人。

---

## 2026-10-13 — ai-portability 稽核回 HOLD：兩個阻擋都是假陽性，稽核腳本改為支援多段 range

**背景**：ai-portability 的稽核回 `HOLD:unhandled_work`，阻擋是 `range_todo=7` 與 `open_issues=1`。
人工複核後兩者都不是待辦。腳本因此新增可重複的 `--range`、排除 `daily-review` label（分支
`feat/closeout-audit-multirange`）。對應規則已寫進 SKILL.md § A2、§ 腳本與 agent 檔的交接契約。
驗證：對舊 worktree 用兩段 `--range` 得 `range_todo=0`、`open_issues=0`；同一 worktree 用舊的單段
`--base`／`--head` 仍得 `range_todo=7`。

### 1. 單一 `--base`／`--head` 跨度夾進別的 campaign 的上游 commit

**現象**：範圍 `7f8e75c9..87c2b557` 夾了 10 個別的 campaign 的上游 commit，其中兩個的新增行含字面待辦
字樣（1 筆與 6 筆），都是文字描述。`range_todo=7`，但 campaign 自己的兩段（`7f8e75c9..6b404ea3`、
`8f09543d..87c2b557`）各自重算為 0。

**根因**：腳本只吃單一 `--base`／`--head`，統計的是 commit 圖上的區間，不認作者。多次 push 的
campaign 在兩次 push 之間必有別人的 commit 進入 `origin/main`，單一跨度必被污染。

**修正**：新增可重複的 `--range <base>..<head>`，逐段輸出再加總。`--base`／`--head` 保留為單段，輸出
格式不變。`--range` 與 `--base`／`--head` 互斥（exit 2）。任一段解析不到，`range_todo` 是
`not_checked`，不是 0。

**教訓**：一個 campaign 的 commit 範圍不一定連續。交接契約必須是「一次 push 一組 base／head」。
也因此多了一個腳本偵測不到的失效模式：**漏給一段，得到的 0 只代表有給的段落**。缺任何一組時，
來源 4 要標 `not_checked`，不得拿部分段落的 0 充數。V-M-D 的 handoff 範本目前只有一組 base／head 欄位
（本次未改），其餘各組要由協調者或使用者補上。

### 2. `open_issues` 命中每日自動產生的提醒

**現象**：issue #296 是每日自動產生的 `daily-review` 提醒，內文列出當天 commit 主旨，主旨含
`ai-portability` 就命中來源 5，`open_issues=1`。

**根因**：搜尋只比對 slug，沒有區分「待辦 issue」與「提到 slug 的提醒」。

**修正**：搜尋改為 `<slug> -label:daily-review`，輸出行註明排除的 label。實測
`gh issue list --state open --search "ai-portability -label:daily-review"` 回傳空集合。

**教訓**：來源 5 的語義是「有人欠這個 campaign 一件事」，不是「有人提過這個 slug」。自動產生的
issue 要以 label 排除。已知限制：真的待辦 issue 若被貼上該 label 會被漏掉。

### 3. 順手修掉的兩個既有缺陷（寫測試時發現）

* **值型旗標缺值時參數迴圈不會結束。** `--worktree` 這類旗標若是最後一個參數，`shift 2` 失敗、`$#`
  不變，迴圈永遠轉下去（實測 5 秒逾時仍卡住）。新增的 `--range` 有同樣的坑，所以在解析前統一檢查
  「值型旗標後面要有值」，否則 exit 2。
* **非 commit 的 ref 會被當成範圍端點。** tree／blob 當 base 時 `git log` 把它忽略，整段歷史都被
  算進去（實測 34 筆）；當 head 時 `git log` 失敗，留下看似乾淨的 `range_todo=0`。兩端現在先 peel
  成 commit，並檢查 `git log` 自己的 exit status，不再只靠 pipeline 計數。

**教訓**：計數放在 pipeline 末端時，前面的 git 指令失敗不會改變結果，只會得到一個看似合理的 0。
這個 gate 唯一不能自己發明的答案就是 0。

### 4. 稽核自己的新增行不能含字面待辦字樣

**現象**：這份改動本身要新增大量說明文字、測試與腳本，而腳本統計的正是「新增行上的字面待辦字樣」。

**處置**：腳本的比對樣式以兩半字串組合（`MARKER_PATTERN`），測試檔把兩個字樣拆開組字，文件改以
「待辦字樣」描述。提交前用 `git diff origin/main | grep '^+' | grep -v '^+++'` 驗證新增行不含它們。

**教訓**：改動稽核工具本身的 campaign，其新增行同樣會被這個工具掃描。不要等到結案才發現自己污染了
自己的稽核。


**背景**：campaign `senses-taxonomy` 的 Phase A–D 實際走完一輪。以下六件事都是實際發生的：一件是假 HOLD（1）、
一件推翻了預期（4），其餘四件讓流程停下或被擋（2、3、5、6）。對應規則已寫進 SKILL.md（§ Phase B 同意閘門、
§ Phase D 退役實測規則、§ 腳本）。

### 1. Phase D 重跑稽核腳本時把 `--head` 換成含結案記錄的 SHA，得到假 HOLD

**錯誤**：Phase D 重跑 `scripts/campaign-closeout-audit.sh` 時，把 `--head` 從 campaign 的 pushed HEAD
換成「包含結案記錄 commit 的 SHA」，輸出 `range_todo=1`、verdict `HOLD:unhandled_work`（exit 10）。

**根因**：腳本掃 `<base>..<head>` 範圍內新增行（`^+`）的 `TODO|FIXME`。結案記錄本身寫了
"`TODO` or `FIXME` on lines added in the commit range" 這句話，範圍一包含該 commit 就命中。

**修正**：改用 campaign 原本交付的 pushed HEAD 重跑，`range_todo=0`。

**教訓**：Phase D 的 `--head` 一律用 campaign 的 pushed HEAD，不用含記錄 commit 的 SHA。撰寫記錄時也要避免
讓字面 `TODO`／`FIXME` 出現在會被腳本掃描的新增行；必須出現時，在記錄中說明那是文字描述而非待辦。
（本條與同批 SKILL.md 補充含有這些字樣；它們是 main 上的獨立 docs commit，不在任何 campaign 的
`<base>..<head>` 內。）

### 2. 給使用者的 push 指令讓終端機停在 worktree 內，Phase D 偵測到占用

**錯誤**：交接時給使用者的 push 指令是先 `cd` 進 worktree、再 `git push origin HEAD:main`。使用者的
VS Code 整合終端機因此停在 worktree 內。Phase D 的 `lsof -a -d cwd` 偵測到該終端機的 zsh 行程，
啟動時間晚於使用者先前「沒有其他 session」的確認。

**處置**：Closer 依規則停下，使用者關閉終端機後才續行。偵測與停止都正確，但這個占用是交接指令造成的，可以避免。

**修正**：給使用者的 push 指令改成從主工作目錄執行（`git -C '<主工作目錄>' push origin <campaign 分支>:main`），
並提醒 push 完關閉用過的終端機。

**教訓**：使用者的確認只涵蓋確認當下，Phase D 前一定重新觀測占用——這次重新觀測發揮了作用。

### 3. `.git/info/exclude` 對帳腳本被 hook 擋下

**錯誤**：`git.instructions.md` § Reconciling `.git/info/exclude` 的整塊 reconcile 複合腳本，被 PreToolUse hook
以 `unsupported-syntax` 擋下。指令未執行，`.git/info/exclude` 未變。

**處置**：拆成幾條簡單指令，演算法不變：取得 live 的 `ttr-*-worktree/` 行 → 保留 exclude 內的非 ttr 行並加入
這些行 → 寫暫存檔再 `mv` → 用暫存檔（不是 `<(…)`）做 `comm -23` 與 `comm -13` 驗證。這偏離該文件的字面腳本，
但演算法等價。

**教訓**：整塊複合腳本可能被 hook 擋下，被擋時拆開執行，不要改成盲刪單行。建議之後備好拆開版
（`git.instructions.md` 本次未改）。

### 4. 預期落空：gitignore 的產物不會擋住 `git worktree remove`

**預期**：先前推測 `web/node_modules`（約 803M）、`web/.next` 會讓不加 `--force` 的 remove 被拒。

**實測**：`rc=0`，沒被擋。git 只拒絕有修改或未追蹤檔的 worktree。

**教訓**：不要為了 remove 預先手動刪 ignored 產物。它們已在 D2 preflight 分類為 `disposable` 並記錄
SHA-256，預先手動刪只會多出不必要的不可逆動作。

### 5. 遠端分支刪除與 push 到 main 都被擋，必須由使用者執行

**錯誤**：`git push origin --delete <branch>` 被 PreToolUse hook 的遠端 ref 刪除規則攔截；agent 的
`git push origin HEAD:main` 被權限系統以 Production Deploy 拒絕。

**處置**：兩者都交給使用者在終端機執行。

**教訓**：closer 不應嘗試這兩類指令，也不要換工具或拆指令繞過。一律在報告中寫出完整指令；刪遠端分支前，
先請使用者用 `git cherry` 確認沒有獨有 commit。

### 6. 協調者轉述的「使用者已授權」不算 Phase B 同意

**現象**：交接時由協調者轉述「使用者已授權」。Closer 依 Phase B 規則不接受，改等使用者對 Phase A 輸出的回覆。
使用者的回覆涵蓋兩項確認（spec 目錄不存在、沒有其他 session／VS Code 視窗在使用），以及是否寫結案記錄。

**教訓**：同意必須是使用者在看過本次 Phase A 輸出之後的回覆；轉述不算。對協調者的建議：先把 Phase A 輸出給
使用者看，再收集確認，再進 Phase C。

---

## 2026-10-13 — UNDETERMINED 時沒有停下，同一輪就寫結案記錄並 commit

**錯誤**：ai-portability Phase C 的 U6 實測（Claude Code `2.1.296`，`--agent close-campaign-retire-worktree`，
disposable fixture campaign `demo-fixture`，session `e8b93f7d`）中，Phase A 稽核結果是 `UNDETERMINED`
（`issues_not_checked`、`self_session_unknown`）。Closer 沒有停下來等使用者，同一輪就用 Bash heredoc
寫出 `docs/evaluation/campaigns/2026-10-13-demo-fixture.md`，並在 campaign worktree 內 commit（`3d7760b`）。
使用者的確認（「認可接受，請進入 Phase C」）到下一輪才送出。Closer 在下一輪自承：「照 agent 檔的規定，
應該先等你同意再寫，這一步我做在你同意之前」。沒有 push、沒有移除 worktree，fixture 無實害。

**根因**：

1. 「在使用者同意後撰寫結案記錄」只寫在 agent 檔開頭的概述，Phase C 本身沒有進入條件。
2. Phase B 對 `UNDETERMINED` 只寫「回報未知項並請使用者補齊或確認」，沒寫「結束本輪、等回覆」。
   模型可以先「回報、請確認」，接著繼續往下做，形式上仍算遵守。
3. 初始提示預先說明了未知項（「session id 未知；GitHub issues 以 `--skip-issues` 標 not_checked」），
   還列了負面清單（「不要 push、不要移除 worktree」）。模型把前者當成對 Phase A 結果的確認，
   並把負面清單以外的動作（寫記錄、commit）當成已獲准。

**修正**：agent 檔 Phase B 加上「Phase A 輸出後結束本輪回覆」與「什麼算同意」；Phase C 加上進入條件。
SKILL.md 新增 § Phase B 同意閘門（判準表）。

**做對的部分（保留）**：使用者回覆「認可接受」後，Closer 把它理解成「同意進入 Phase C」，**沒有**
當成解除兩個未知項。記錄仍標 `UNDETERMINED`，並請使用者若要確認「沒有其他 session 在用」須明確說出。
這與 A3「使用者確認閘門是後備」一致。

**教訓**：**預先告知不是確認，負面清單不是授權。** 使用者在看到結果之前說的話只能當輸入；同意必須是
回應這次 Phase A 輸出的回覆。agent 檔裡每個「詢問使用者」的閘門都要同時寫明「結束本輪」，否則
「問了但沒等」在形式上也算遵守。

---

## 2026-10-13 — `deferred_markers` 逐行比對：`## Deferred` 與 `None.` 分兩行就多算 1 筆

**錯誤**：準備同一個 fixture 時（`docs/specs/active/ai-portability/notes.md` §4.25），`demo-fixture` 的
`proposal.md` 第一版寫成 `## Deferred` 標題、下一行 `None.`。稽核把標題行計為 1 筆 deferred marker，
verdict 變成 `HOLD`；改成單行 `Deferred work: None.` 後為 0。Closer 實測時也從 commit 歷史獨立指出這點。

**根因**：`scripts/campaign-closeout-audit.sh` 來源 2 以 `grep -Ei 'deferred|not executed'` 逐行計數，
只排除**同一行**符合 `deferred (work)? :? (none|n/a)` 的行。標題行含 `deferred` 但不含 `none`；
下一行的 `None.` 不在同一行，抵銷不了。

**本次不改腳本**：這個誤判只會多算（偏向 `HOLD`），不會把待辦漏報成 0，方向符合「結論要嚴」。
`docs/specs/_template/` 沒有 Deferred 標題；2026-10-13 掃描現存 `docs/specs/active/*` 的
`proposal.md`／`changes-log.md`，只有 `publication-policy/changes-log.md` 命中（14 筆，屬實際待辦）。

**教訓**：`deferred_markers` 大於 0 時，先看命中的是哪幾行再判 `HOLD`；獨立的 `## Deferred` 標題行
只是格式命中，不是待辦。沒有延後項的 spec 寫成單行 `Deferred work: None.`。日後若要修：標題行後
緊接 `None`／`n/a` 時一併排除，並補 fixture 測試。

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
