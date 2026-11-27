---
slug: research-team
title: 研究助理團：多 agent 假說迭代與可查核引用的深度研究
description: 以 /deep-research 啟動 Supervisor 與六種角色的 subagent，對一個議題做假說迭代、原始來源查核與錦標賽排名，輸出含議題關係圖、腳註超連結與參考書目的 Artifact
status: active
branch: claude/fervent-babbage-0rcn0m
created: 2026-11-25
tags: [tooling, ai, research]
---

## What（做什麼）

一個可重複使用的研究流程，入口是 Claude Code 的 `/deep-research <議題>`（claude.ai/code 網頁、App、終端機都能用）。架構參考 Google「AI co-scientist」：

| co-scientist 元件 | 本專案的對應 |
| --- | --- |
| Scientist 的 research goal、add idea、review、discuss | `/deep-research <議題>`；`/deep-research resume <連結>` 帶回饋再跑一輪 |
| Supervisor、Research plan configuration | 主對話；建議題樹與 `state.json` |
| Generation agent（文獻探索） | 每個子議題一個 subagent，平行執行 |
| Reflection agent（full review、deep verification） | 每個假說一個獨立 subagent，逐一開啟來源、摘錄原文引句、找反證 |
| Ranking agent（tournament） | 兩兩辯論判勝負；Elo 由腳本計算 |
| Proximity agent | 找出重複假說並合併 |
| Evolution agent | 以前段假說合併、簡化、延伸成新一代，回到查核 |
| Meta-review agent、research overview | 歸納勝敗樣態與限制，寫報告內文 |
| Memory | `state.json`，隨 Artifact 一起發布，可取回接續 |
| Ranked list、research plan、knowledge base | 報告頁：假說排名、下一步、查核帳本與書目 |

產出是一個獨立的 Artifact（每個議題一個）：摘要、議題與假說關係圖、假說排名、各子議題的論證與查核帳本、總評、腳註、參考書目。腳註連到原文與書目條目，書目每筆都有超連結。

## Why（為什麼）

使用者希望之後的深度研究議題都能用同一套多 agent 流程處理，並且能回頭查核每個說法的原始來源。單一對話寫出的研究報告有兩個常見問題：引用的編號或網址對不上，以及產生說法的同一個 context 自己確認自己。

## Design（設計決定與理由）

1. **角色不做成 14 個 agent 之外的新 agent 檔，而是一個 skill 加一個 prompt。** 角色卡在 `.github/skills/research-team/SKILL.md`，Supervisor 以 `general-purpose` subagent 啟動各角色並指定模型。理由：新增 agent 檔要決定 `tier` 與 `claude-role`（治理決定，需使用者核准），而且既有的 `researcher` 是「找活動來源」的角色，名稱會混淆。先用最小範圍試做，角色穩定後再考慮獨立成 agent 檔。
2. **agent 只寫結構化資料，編號與排版交給腳本。** `scripts/research/render_report.py` 負責驗證 id 對應、腳註編號、書目、Elo 與關係圖。理由：模型手寫腳註編號容易錯位；Elo 用算的才可重現。
3. **「已驗證」有機械門檻。** 主張標為已驗證必須附原文引句，且至少一個來源被實際開啟過；報告內文只能引用開啟過的來源。違反時腳本拒絕產生報告。腳本無法判斷引句是否真的出自該來源，這一點靠 Reflection 的規則與使用者點連結抽查。
4. **查核與產生分開 context。** Reflection 拿不到 Generation 的理由，只對照來源。
5. **研究內容不進 repo。** 工作檔在 `.research-runs/`（git 忽略）；持久的輸出是 Artifact 與附在其中的 `state.json`。理由：研究議題不一定與本專案有關，repo 是公開的。
6. **放在 Tokyo Taiwan Radar repo。** 這次 session 只能存取這個 repo。流程本身不依賴專案的其他部分（只有一個 Python 腳本、一個 skill、一個 prompt），之後要搬到獨立 repo 只需複製這三處。

## Non-Goals（不做什麼）

- 不建獨立的網站或後端。入口是 Claude Code 的對話；claude.ai 的 Project 無法由 agent 建立，使用者可以自行把 Artifact 連結收進 Project。
- 不接 wet lab、AlphaEvolve 之類的專用工具；工具只有網路搜尋與抓取。
- 不自動排程、不長時間常駐執行。每次由使用者啟動，跑完固定輪數就結束。
- 不寫入 Supabase、不影響活動資料與網站。

## 已知限制

- 付費牆後的論文只能讀到摘要，主張最高標為「部分支持」。
- 引句的真實性沒有機械檢查（見設計決定 3）。
- Ranking 的評審與參賽假說來自同一個模型家族，可能有共同偏好。
- 成本隨 depth 增加：standard 約 18–25 個 subagent。
