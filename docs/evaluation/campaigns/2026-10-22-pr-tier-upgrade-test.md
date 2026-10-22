# PR Tier 升級情境實測（2026-10-22）

spec pr-flow-tiering Phase D 的驗證 PR。第一個 commit 只改這份文件（Tier 0）；開 PR 後、Secret Scan 跑完前，
立刻追加一個改 `scripts/ci/pr_tier.py` 註解的 commit（Tier 2）。

預期：第一個 commit 的掃描完成時，PR 的 head 已不是它，所以不合併；第二個 commit 的掃描完成後判為 Tier 2，
只貼 `tier:2`、不合併。這個 PR 驗證完就關閉，不合併。
