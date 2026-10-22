---
title: pr-flow-tiering Plan Critic 報告
reviewer: Codex（codex-cli 0.160.0，`codex exec -s read-only`），與撰寫者不同模型家族
reviewed: proposal.md、tasks.md、notes.md 與 diff 3428e521..acea5ca3
date: 2026-10-22
---

> 以下為 Codex 原始報告，未經修改。協調者的逐條回應在文末。檔內連結是評審時 worktree 的絕對路徑。

# Plan Critic 評審報告

## 1. 商業主軸對齊（Business Alignment）

**評分：🟡 弱對齊。** 此計畫屬開發流程治理，直接價值是降低單人開發時的 worktree、terminal 與 push 指令操作成本；它不直接改善資料完整性、i18n 或使用者觸達。proposal 將五個機制都納入長期方向，但 Phase B 目前只改 `check_push`，尚未解決使用者提到的 worktree 選擇與指令複製成本。[proposal.md:10–21](/docs/specs/active/pr-flow-tiering/proposal.md#L10)

計畫沒有偏離「全日本台灣相關活動聚合」使命；它是內部開發效率工作。必須把「降低 push 人工步驟」與「降低整個小任務的手動流程」分開衡量，否則 Phase B 的成功不代表原始痛點已解決。

## 2. 複雜度 vs 價值評估

**預估複雜度：high。預估業務價值：medium。** 完整方案包含五個機制、三層 PR 分流、三個待決點，並跨 6 個 Phase；檔案範圍涵蓋 hook、測試、設定、workflow、GitHub 設定及後續治理文件。[proposal.md:14](/docs/specs/active/pr-flow-tiering/proposal.md#L14), [proposal.md:34–58](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/proposal.md#L34), [tasks.md:15–46](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/tasks.md#L15)

複雜度相對價值有**比值警示**：雖然 Phase B 的 `check_push` 是窄範圍改動，但整體目標還包括自動建 worktree、PR 分層、合併後清理及跨工具延續。應以試行數據判斷完整流程是否真的減少每任務耗時，再決定是否投入 Phase D–F，避免先建出完整治理系統、卻未驗證使用者最花時間的操作是否改善。[proposal.md:18–21](/docs/specs/active/pr-flow-tiering/proposal.md#L18), [tasks.md:30–46](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/tasks.md#L30)

## 3. 優先順序提醒（Anti-Rabbit-Hole）

**評分：🟡 可延後。** 已讀到的材料中，找不到本計畫以外尚未完成的高優先事項清單；repo 根目錄沒有 `history.md`，而本次唯讀查證也無法取得 GitHub open issues。因此，無法據此斷言資料品質或爬蟲工作目前沒有更高優先事項。

Phase D 的 Tier 0 自動合併與 Phase E 試行依賴人為決策及 GitHub 設定，但不是使用者原始痛點的全部解法。建議把試行驗收增加「單一小任務的人工步驟數／耗時」指標；現有指標只有各層 PR 數、Tier 0 revert 次數及 commit 到 main 的時間，無法驗證手動 worktree 與 push 操作是否減少。[tasks.md:36–39](/docs/specs/active/pr-flow-tiering/tasks.md#L36)

## 4. 全站架構整合分析

此計畫沒有新增網站 component、資料表、migration、i18n key 或 scraper，因此 EventCard、FilterBar、Category Sync、Event Form Sync、i18n Regression、FC lock 與 SCRAPERS List Completeness Guard 均不適用。它修改的是 Claude Code hook 權限、GitHub PR 流程與 repo 治理規則。

Architect 的「工作流／治理計畫三查」適用：計畫引用現行 Git 規範，並明確把全面政策改寫延至 Phase F；也把 worktree 與 branch protection 的時點列出。[Architect SKILL.md:79](/.github/skills/agents/architect/SKILL.md#L79), [proposal.md:28–29](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/proposal.md#L28)

**P1 — Phase D 開啟 Tier 0 auto-merge，Phase F 才開啟 main branch protection／required checks，存在檢查缺口。** 若 Tier 0 workflow 要求的 checks 尚未被 GitHub 設為 required，auto-merge 可能在可用 checks 條件不足時合併。計畫應先定義 Tier 0 的必要 checks 與未設定 branch protection 時的合併行為，再決定此順序是否安全。[proposal.md:81–87](/docs/specs/active/pr-flow-tiering/proposal.md#L81), [tasks.md:30–34](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/tasks.md#L30), [tasks.md:41–46](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/tasks.md#L41)

## 5. 既有 Component 復用建議

**復用率：🟢 充分復用。** Phase B 延伸既有 `check_push`、tokenizer、deny/ask/allow 決策合併邏輯與 pytest 測試，不另建 hook 引擎；Tier 0 也指定沿用現有 Dependabot auto-merge workflow 模式。[`_policy.py`](/scripts/claude/_policy.py#L559), [proposal.md:48](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/proposal.md#L48), [proposal.md:91–95](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/proposal.md#L91)

Phase B 的 scope 與既有架構相稱；後續新增 labeler 與 workflow 屬必要新元件，但目前尚未提供實作細節，應在 Phase D 計畫中補上路徑白名單和 checks 的可驗證規則。

## 6. 建議更新後的計畫

**結論：修正後再繼續 Phase B 收尾；不應將目前 Phase B 視為已驗收。**

具體修改點：

- **P1：** 完成 tasks.md 標記未完成的 Claude Code 2.1.304 實測，或明確將其列為方案 B 前置條件。notes 已記錄互動實測 NOT TESTED，且移除／收窄 settings ask 後的 allow 行為尚未驗證。[tasks.md:20–21](/docs/specs/active/pr-flow-tiering/tasks.md#L20), [notes.md:73–87](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/notes.md#L73)
- **P1：** 在 Phase D 前訂出 Tier 0 required checks 與 branch protection 的安全開啟順序，確保 auto-merge 不會在保護條件尚未生效時先合併。[tasks.md:30–34](/docs/specs/active/pr-flow-tiering/tasks.md#L30)
- **P2：** 試行指標加上每任務人工步驟數或耗時，直接衡量使用者提出的操作痛點。[tasks.md:36–39](/docs/specs/active/pr-flow-tiering/tasks.md#L36)
- **P2：** 明確記錄 Phase B 預期可覆蓋與未覆蓋的 Git 設定／命令形式，避免將 hook 視為普遍 push 防線。[notes.md:48–53](/docs/specs/active/pr-flow-tiering/notes.md#L48)

本次由不同模型家族執行批評：proposal 記錄由 Claude Opus 撰寫，Phase B 由 Claude Fable 實作，本次使用 Codex。

# 安全審查

## `check_push` 是否存在可放行推到 `main` 的命令？

**P1 — 找到一種可重現的命令，可由 `-c` 設定替代 remote 的 push refspec，讓實際目的端為 main，而 parser 判為 feature refspec。**

```bash
git -c remote.origin.push=feat/x:main push origin feat/x
```

依目前 `check_push` 的邏輯，`-c` 與其參數會在 Git 選項掃描中略過；`feat/x` 是唯一 refspec，目的端明確不是 main，故回傳 allow。[`_policy.py`:546–550](/scripts/claude/_policy.py#L546), [`_policy.py`:617–650](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/scripts/claude/_policy.py#L617) 若 Git 在此命令中採用 `remote.origin.push` 設定並推送至 main，這就是 hook allow 與實際 push 目的地不一致的漏洞。**本次未在 repo 驗證 Git 對「明確命令列 refspec 與設定 refspec 同時存在」的優先順序，故這個案例的可利用性標為不確定。**在確認前，parser 不應忽略 `-c remote.*.push`。

以下是已能從程式碼推導的判斷：

- **refspec 解析：** 多個 refspec 只要有 main 就 ask；缺 refspec、HEAD／變數／動態值及 wildcard 類目的端都 ask；正常的 `feat/x:feat/x` 放行。[`_policy.py`:599–650](/scripts/claude/_policy.py#L599)
- **短旗標群組：** `-f`／`-d` 群組會 deny；`-uo ci.skip` 會把 `ci.skip` 當作 `-o` 值略過，避免把 repository 誤當 refspec。[`_policy.py`:631–641](/scripts/claude/_policy.py#L631) 但 parser 不是完整 Git push option parser；未知的短旗標不一定被保守拒絕。需補齊未知旗標的實例測試，否則其安全性不確定。
- **`git -c` 其他設定：** `core.hooksPath` 的確可改變本機 pre-push hook 路徑。命令 `git -c core.hooksPath=/dev/null push origin feat/x` 會被 parser 當 feature push allow，並可能略過本機 gitleaks hook；這是 notes 已記錄的殘餘風險。[notes.md:48–53](/docs/specs/active/pr-flow-tiering/notes.md#L48) 這個例子本身推 feature，並未證明可推 main，但削弱了 push 前 secret scan 保證。
- **`push.default`：** 無 refspec 的 `git push` 會 ask，因此 `push.default=current`、`upstream` 或 `matching` 不會單靠設定使無參數 push 被放行。[`_policy.py`:644–646](/scripts/claude/_policy.py#L644) remote 名稱（例如 `main`）也不直接影響目的端解析；但 remote-specific push refspec 是上方不確定案例。
- **別名、引號、跳脫與包裝動詞：** tokenizer 對 shell 引號做去引號，故 `'feat/x'`、`"feat/x"` 仍會被當作 feature refspec；已知包裝形式交由 parser 遞迴檢查。notes 已列出 git alias、變數動詞與未解包 wrapper 為殘餘風險。[notes.md:48–53](/docs/specs/active/pr-flow-tiering/notes.md#L48), [test_bash_guard.py:229–255](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/scripts/claude/tests/test_bash_guard.py#L229) 本次未證明這些形式能 bypass main 目的端檢查；不能把「可繞過某層 hook」等同於「可推 main」。

## 偏離決策表是否合理？

- **`--no-verify` 一律 ask：合理。** 它跳過 pre-push hook，和 repo 禁用 `--no-verify` 的規範一致；ask 比 allow 保守。[notes.md:32–38](/docs/specs/active/pr-flow-tiering/notes.md#L32), [test_bash_guard.py:252–255](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/scripts/claude/tests/test_bash_guard.py#L252)
- **refspec 或 remote 含變數／命令替換時 ask：合理且較安全。** 動態內容可能改變 positional argument 的角色，使實際目的端不能由靜態命令判定。[`_policy.py`:645–649](/scripts/claude/_policy.py#L645)
- **`heads/main` 視為 main：合理。** notes 指出 Git DWIM 可將其解析為 `refs/heads/main`，加進完整 ref 名稱比對符合「可能是 main 就 ask」原則。[notes.md:32–36](/docs/specs/active/pr-flow-tiering/notes.md#L32)

## notes 的 settings 方案 A/B

**較佳方向是方案 B，但目前內容不足以作為 hook 失效時的可靠保底。** 方案 A 移除 settings 的 ask，只留 hook；若從不載入 project settings 的子目錄啟動，或 hook 被停用／失效，便失去既有 settings 閘門。notes 自己也列出此缺口。[notes.md:91–104](/docs/specs/active/pr-flow-tiering/notes.md#L91)

方案 B 的 `Bash(git push *main)` 與 `Bash(git push *main *)`：

- **可能漏掉**以裸 `main` 之外的等價目的端形式，例如 `git push origin HEAD:refs/heads/heads/main` 是否會被 Git 解作 main，或 `git push origin HEAD:refs/heads/main` 加上特定旗標順序；實際匹配取決於 Claude Code 的 Bash 規則 glob 語義與 Git refname DWIM。notes 只列部分案例，沒有可重現的完整匹配測試。[notes.md:105–124](/docs/specs/active/pr-flow-tiering/notes.md#L105)
- **明確會多問**如 `git push origin domain` 及 `git push origin main:feat/x`；這是額外詢問，不會直接放行 main。notes 已辨識此誤擋。[notes.md:119–122](/docs/specs/active/pr-flow-tiering/notes.md#L119)
- settings pattern 對 `git -C … push`、`git -c … push`、`env … git push` 等前綴變體不匹配；hook 是主要保護時尚可，但 hook 失效時方案 B 的保底不覆蓋這些形式。[notes.md:69–70](/docs/specs/active/pr-flow-tiering/notes.md#L69)

## 路徑白名單與 branch protection 開啟順序

**P1 — 目前順序有保護缺口。** Tier 0、Tier 1 使用白名單，未列路徑歸 Tier 2，且多層取最高風險，這個分類原則是合理的。[proposal.md:44–52](/docs/specs/active/pr-flow-tiering/proposal.md#L44) 但在 Phase D 開啟 auto-merge、Phase F 才啟用 branch protection／required checks 的間隔中，尚未定義保證自動合併必須等待哪些 checks；這是流程上的洞，不能只靠路徑分類解決。[proposal.md:81–87](Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-pr-flow-tiering-worktree/docs/specs/active/pr-flow-tiering/proposal.md#L81)

## 評審順序與重工風險

**P2 — 先實作 `check_push`、最後才做 Plan Critic，確實增加重工風險。** 設計把 parser 細節落到程式與測試後才進行獨立評審；若本報告指出 remote push refspec 或未知短旗標解析缺口，Phase B 測試與實作就可能需要返工。這個順序由 tasks 明列，Phase B commit 也要求 Phase C 完成前不得合併，保留了修正窗口，故屬可控但不必要的重工風險。[tasks.md:15–28](/docs/specs/active/pr-flow-tiering/tasks.md#L15)

## 查證結果

執行了唯讀 pytest 命令 `python3 -m pytest -p no:cacheprovider scripts/claude/tests -q`，但目前 Python 3.14 環境沒有安裝 pytest（`No module named pytest`），因此本次無法重新驗證測試結果。Phase B 測試數字僅能引用 notes 中的紀錄，不能視為本次重跑通過。[notes.md:5–15](/docs/specs/active/pr-flow-tiering/notes.md#L5)
---

# 協調者回應（Claude Opus 5.5，2026-10-22）

| 批評 | 嚴重度 | 處理 | 說明 |
|---|---|---|---|
| `git -c remote.origin.push=… push origin feat/x` 可推到 main | P1 | 採納，已實測成立 | 在 scratchpad 的本機 bare repo 執行 `git -c remote.origin.push=refs/heads/feat/x:refs/heads/main push origin feat/x`，輸出 `f79ff12..4e8f2e5  feat/x -> main`，遠端 main 被更新。Codex 標為「不確定」，實測確認為真。修正交由 Fable，記錄在 notes.md B3：push 前帶全域選項時 ask、寫入 push 相關 git config 時 ask。真實 repo 目前沒有設定 `remote.origin.push`，評審時沒有實際暴露。 |
| `git -c core.hooksPath=… push` 可關掉 gitleaks | P1 | 採納 | 與上一列一起修，push 前帶 `-c` 一律 ask。 |
| 未知短旗標與未知選項沒有保守處理 | P2 | 採納 | 改成已知選項允許清單，清單外 ask，記錄在 notes.md B3。 |
| Phase D 開 auto-merge 早於 required checks | P1 | 採納，修改 proposal | 改成先建立 main 的 ruleset，要求 status checks 且讓 repo owner 可 bypass，再開 auto-merge。這樣使用者試行期間仍能直接 push，Tier 0 也必須等 checks。「要求 PR」仍留在 Phase F。 |
| settings 互動實測 NOT TESTED | P1 | 採納 | 已是方案 B 的前置條件。tasks.md 改寫成明確的阻擋條件：使用者完成 U-B1～U-B3 之前不改 `.claude/settings.json`。 |
| 方案 B 的 `Bash(git push *main)` 覆蓋不足 | P2 | 部分採納 | 方案 B 只是 hook 失效時的保底，主要閘門是 hook。套用時要附上 pattern 比對測試。Codex 舉的 `HEAD:refs/heads/heads/main` 目的端是名為 `heads/main` 的 branch，不是 main，不構成漏洞，此例駁回。 |
| 試行指標沒有直接量測原始痛點 | P2 | 採納 | Phase E 加上「每個小任務的人工步驟數與耗時」，並設停止條件：未改善就停在 Phase D，不做 Phase F。 |
| 複雜度高、價值中等 | — | 採納為 gating | Phase D 到 F 都以 Phase E 數據決定是否繼續。roadmap 中的成本修正（enrich_poster）排在 Phase D 之前。 |
| 先實作、後評審造成重工 | P2 | 接受 | 這是使用者指定的順序。實際重工限於 B3 一輪修正；Phase C 完成前不合併的規則保住了修正窗口。 |
| Codex 環境沒有 pytest，未能重跑 | — | 補充 | 協調者在 Phase B 完成後重跑 `python3 -m pytest scripts/claude/tests scripts/tests -q`：615 passed。B3 修正後會再跑一次。 |
