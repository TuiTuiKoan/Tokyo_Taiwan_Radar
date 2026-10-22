# Notes — ai-harness

執行證據與分類帳。只往後追加；既有段落不改寫。每段標明日期、執行者與工具版本。未實測的項目一律寫 NOT TESTED。

## 1. Phase 0 session（2026-10-20）

| 項目 | 值 |
|---|---|
| 執行者 | Claude Code 2.1.300；規劃由 Fable 5.1，spec 骨架由 Sonnet 5.5 建立 |
| 起點 | origin/main `90dab624`（docs(weekly_review): 2026-10-18 weekly review），fetch 後 main 與 origin/main 同步 |
| Worktree | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree`，branch `feat/ai-harness`，追蹤 origin/main |
| `.git/info/exclude` | 已 reconcile，含 `ttr-ai-harness-worktree/` |
| plan.md SHA-256 | `5f492d901f2846a6865aee0de5ebc1d73bed9889e88ccc1c00edc0e77ec585bf` |

- 主工作樹 `git status --short` 無輸出，無他人 WIP。
- `agents-repo` worktree（`…/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo`，HEAD `3b04a6d3`）工作樹乾淨；尚未退役，等 Close Campaign agent。
- 治理文件中的 exclude reconcile 片段在 macOS 預設 bash 3.2 會語法錯誤（`$(… case "$x" in "$root"/*) … esac …)`），pattern 需寫成 `("$root"/*)`。本 session 用修正版執行並驗證 converged。後續應修正 `git.instructions.md` 的片段。
- hooks guard 拒絕了一次把 worktree 建立、reconcile 與驗證串成單一命令的呼叫（`unsupported-syntax`），拆成簡單命令後通過。
