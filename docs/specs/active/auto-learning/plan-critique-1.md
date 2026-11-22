# Plan Critique 1：auto-learning 開發規劃 v0.1

- 日期：2026-11-22
- 評審者：Claude（claude.ai session 內依 `.github/agents/plan-critic.agent.md` 與 plan-critic SKILL 執行；此環境沒有 codex）
- 對象：claude.ai Project 文件 `claude/auto-learning-dev-plan.md` v0.1（十條里程碑、P0–P10）
- 基準：`origin/main` `7d174a56`

本次批評與撰寫計畫者是同一個模型、同一個 session，不算第二視角。合併前應由 Codex 再評一次，或由使用者在 PR 上留 `@codex review`。

**結論：go with changes。** 退役與教訓段可以直接做。收集器、帳本、規則編號三塊做太早也做太大，其中收集器的設計讓 agent 改得到自己的成績。

## 1. 商業主軸對齊：🟡 弱對齊

計畫是治理工具，對應主軸第 4 項（後台運營效率）。plan-critic SKILL「適用範圍驗證實驗」一節已經點名過這種風險：治理工具自我增殖的封閉迴圈。現有學習元件十個，這份計畫再加一個 workflow、一個排程 agent、三支腳本。主軸第 1 項（資料正確性）目前是 category 30.8%、location_name 39.5%（`docs/evaluation/annotator/2026-10-22-scoring-v2-baseline.md`），open issue 143、`needs-human` 49。

計畫有一點是對齊的：把資料品質類教訓導向金標，不再寫成規則。

## 2. 複雜度 vs 價值：複雜度 high，價值 medium

11 張 PR，幾乎全部 tier 2；新 workflow 一個（要 `contents: write`）；新排程一個；新腳本三支；要改 104 KB 的 agent 檔與三份 178–235 KB 的 SKILL。價值在「重複問題變少」，但計畫自己承認兩個基準指標還沒量過。複雜度大於已證明的價值。

## 3. 優先順序：🟡 可延後一半

第 1 週排了三張 tier 2 PR，同一週 ground truth 計畫要核准 migration。已合併且有 tier label 的 PR 是 tier 2：160、tier 1：4、tier 0：5，使用者的早上已經滿了。P8–P10（規則編號、合併 SKILL、guard 轉測試）不解決任何眼前的故障，應該排在 learner 證明有用之後。

## 4. Blockers

**B1. learner 改得到自己的成績。** `scripts/ci/pr_tier.py` 的 `TIER0_INCLUDE` 是 `docs/*`（排除 `docs/specs/*`、`docs/architecture/*`），tier 0 由 workflow 自動合併 repo owner 開的 PR。learner 以 owner 帳號執行，計畫又允許它改 `docs/learning/**`，而訊號檔、帳本、報告都放在那裡。也就是 learner 可以開一張自動合併的 PR 改寫訊號或把提案標成 adopted。heartbeat 的白名單也含 `docs/**`（`heartbeat-prompt.md` 第 17 行）。計畫 §5.2 靠 `lessons.py` 檢查欄位，擋不住數值本身被改。
改法：訊號不存成 repo 檔案，由 workflow 在產生 digest 時從 GitHub 即時計算，寫在 `github-actions[bot]` 開的 issue 裡。帳本延後；真的要建時放在 tier 2 的路徑，或把 `docs/learning/*` 加進 `TIER0_EXCLUDE`。

**B2. 新 workflow 重複了既有元件，而且多要了寫入權限。** `scripts/ci/weekly_digest.py` 的 `collect()` 已經用 REST 取過去 7 天合併的 PR、open 的 `needs-human`、bot 留言，workflow 權限只有 `contents: read`、`issues: write`。計畫的 `learning-signals.yml` 另寫一支收集器、每週 push 到 main。#600 那次回退之後，新增一個有 `contents: write` 的 workflow 不應該是第一步。
改法：延伸 `weekly_digest.py`，digest 多一節「學習訊號」。不新增 workflow、不新增權限。

**B3. 範圍必須有關卡才擴大。** 計畫把關卡放在第 8 週，那時 P0–P10 都做完了。learner 有沒有用，第 3–4 週的兩輪報告就看得出來。
改法：本 spec 只含三張 PR：退役加教訓段、digest 學習訊號、learner report-only。帳本、propose 模式、規則編號、瘦身全部移到第二階段，兩輪報告後由使用者裁決才規劃。

## 5. Major

**M1. P1 與 P4 改同一段文字。** 兩者都改 `validate-merge-deploy.agent.md` 的「有教訓就補 `docs(skills)` commit」那一條與 `AGENTS.md` 的推送規則。分兩張 PR 會重演 #571 與 #600 平行改同一檔的衝突（agent-autonomy notes §11）。合成一張。

**M2. 只刪 agent 不夠，各 agent 檔還留著矛盾的指示。** 例如 `architect.agent.md`「After Identifying a Planning Mistake」要求在 `history.md` 頂部加條目並更新 `SKILL.md`；engineer、scraper-expert、tester、plan-critic 都有同型段落。逐檔改寫要動 104 KB 的檔案，風險高。
改法：在 `AGENTS.md` 與 `copilot-instructions.md`（兩處必須一起改）各加一條總則，明寫那些步驟不再執行；逐檔清理另開 issue。

**M3. 驗收條件漏了寫死的數量。** `scripts/tests/test_sync_ai_adapters.py` 有 `AGENT_COUNT = 15` 與兩張含 `history-teller`、`update-history-skill-agent` 的對照表；`scripts/tests/test_sync_hardening.py` 第 126、128 行寫死 15。計畫只寫「`sync --check` exit 0」，實際上 pytest 會紅。

**M4.「你的覆核」訊號量不到。** agent 與使用者用同一個 GitHub 帳號（agent-autonomy notes §9：「無法從 GitHub 區分 heartbeat 與使用者」）。計畫的 S7（你關的 PR、你改的 label）與「只取 owner 寫的 needs-human 理由」都分不出是誰做的。
改法：第一階段拿掉 S7 與理由詞表。使用者的判斷改用 learner 報告 issue 上的 👍／👎，agent 的提示詞禁止加 reaction。

**M5.「實測／推論」是自己標的。** 寫 PR 的 agent 自己宣稱實測，沒有人核對。計畫 §5.2 用這個欄位決定教訓能不能升級成規則，等於沒有門檻。
改法：只當線索；歸群的依據是可連結的證據至少 2 個。

**M6.「使用者建立的排程 agent 改不了」只觀測過一次。** 依據是 notes §5 的一次 `update_trigger` 被拒，那個排程是以 HTTP API 建立的。從 claude.ai 介面建立的排程是否同樣，沒有驗證過。
改法：列為 PR C 的驗收項，建立後實測一次；測不過就把 learner 維持在 report-only，不進第二階段。

**M7. 接受率指標可以灌水。**「提案被合併的比例 60%」可以靠只提瑣碎改動達成。
改法：關卡改看使用者的 👍 數與「被實作的張數」，並保留每週上限 3 張與「至少 2 個證據」。

**M8. 由 Haiku 替 600 KB 的 SKILL 加 ID。** 這正是 `b1873cc`（一次誤刪 1,227 行）的情境。第二階段若要做，必須由腳本產生 diff，並以「刪除行數為 0」為檢查。

**M9. system-map 有 web build 依賴。** 計畫有提到要跑 `pnpm --dir web run build`，但沒有列進驗收。`web/scripts/build-specs-snapshot.ts` 會讀這個檔。

## 6. Minor

- `daily-review` label 退役後，`campaign-closer.agent.md` 第 137 行、heartbeat 與 lane2 提示詞、`test_board_audit.py`、`test_campaign_closeout_audit.py` 仍提到它。保留無害，在 PR 註明即可，不要為了整潔去動 heartbeat 提示詞（要使用者重貼）。
- heartbeat 每次開工會讀 `AGENTS.md` 與 `copilot-instructions.md`，教訓段的規則寫在那兩處就會生效，不必改 heartbeat 提示詞。
- 2026-11-01 的月度 SKILL 掃描與月報沒有產出，原因未查。learner 的報告若引用掃描結果，要先確認這條管線還活著。
- 「歷史搬到 archive」沒有必要：搬 1.6 MB 的檔案只會讓 blame 與連結失效。留在原處、不再讀即可。
- 計畫 §6 的提示詞有「連續兩週被關閉 2 個以上就降為 report-only」，第一階段本來就是 report-only，刪掉。

## 7. 既有元件復用

- 🟢 `scripts/ci/weekly_digest.py`：`collect()`、`_pages()`、`build()`、`BOT` 常數與「只信 bot 留言」的寫法，直接延伸。
- 🟢 heartbeat 的排程建立流程與「建立後清空 MCP 連接器」（notes §3）。
- 🟢 `scripts/sync_ai_adapters.py`：新增 `learner.agent.md` 後自動產生 wrapper；`tier` 必填。
- 🔴 `scripts/ci/learning_signals.py`、`learning-signals.yml`、`lessons.py`、`skill_ids.py`：第一階段都不該新增。

## 8. 建議更新後的計畫

| PR | 內容 | 與原計畫的差異 |
| --- | --- | --- |
| A | spec 骨架、退役三個元件、教訓段規則、測試數量修正 | 原 P0＋P1＋P4 合併 |
| B | `weekly_digest.py` 學習訊號區與 `learning` 清單 | 取代原 P2、P6；不新增 workflow |
| C | `learner.agent.md` 與 `learner-prompt.md`，report-only | 原 P5 縮小；不讀帳本、不寫檔 |
| 關卡 | 兩輪報告後使用者裁決 | 從第 8 週提前到第 4 週 |
| 第二階段 | 帳本、propose 模式、規則編號、瘦身 | 原 P3、P7–P10，延後並另行評審 |

## 9. 人類關卡補列

- PR A、B、C 都是 tier 2，由使用者合併。
- 建立 learner 排程、清空連接器：使用者。
- 範圍縮減（上表）偏離使用者 2026-11-22「依建議進行」的裁決，需使用者確認。
- 關閉 daily-review 提醒 issue：合併 PR A 之後，使用者或 agent 皆可。
