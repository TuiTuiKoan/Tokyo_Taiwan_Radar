---
slug: authoritative-venue-repair-followups
title: authoritative-venue-repair 後續項目（官方證據與 source dry-run、production capture、Gate 2、production CAS）
status: parked
branch:
created: 2026-10-22
tags: [scraper, venue, data-repair, cas, production]
---

# authoritative-venue-repair 後續項目

## 來源與搬移理由

`docs/specs/archive/2026-10-authoritative-venue-repair/tasks.md`（原 `docs/specs/active/authoritative-venue-repair/`，2026-10-22 歸檔）到 Gate 1 為止的程式修正已完成：Gate 1 correction cycle 2
的 commit `10770777`（fix(scraper): include authoritative venue updates）經獨立 Tester PASS 與使用者 Gate 1 批准，
於 2026-10-22 fast-forward 推上 `origin/main`。使用者同日決定**暫停 production 套用**，退役
`ttr-authoritative-venue-repair-worktree`，剩餘項目改由本 parked spec 追蹤。

- 下列 26 條取自 `10770777` 的 `tasks.md`，逐字搬入，只改位置；每條仍是未完成項目，搬移不代表任何一條已處理。
  可用下列指令重算，預期 `7c3ba6f5de1361455a526be9e2629422ec4bd7be7cecfdb2f827fd48f1ba21a3`：
  `git show 10770777:docs/specs/active/authoritative-venue-repair/tasks.md | sed -n '22p;140,142p;367p;376,379p;383,388p;392,401p;406p' | LC_ALL=C sort | shasum -a 256`
- 分組標題沿用原 `tasks.md` 的章節名，組內保持原順序。
- 條目中的 UUID allowlist、production protocol 與 STOP 條件，以 `.github/prompts/authoritative-venue-repair.prompt.md`
  與 `docs/specs/archive/2026-10-authoritative-venue-repair/proposal.md` 為準（2026-10-22 自 `active/` 歸檔）。
- 結案紀錄：`docs/evaluation/campaigns/2026-10-22-authoritative-venue-repair.md`；看板代表卡是 issue #339。
- 三筆 TIFF 新場館 insert（ヒューリックホール東京、TOHOシネマズ シャンテ、TOHOシネマズ 日比谷 スクリーン12・13）
  與不在原計畫內的丸の内ピカデリー，由 issue #341 另案先行處理。重啟本 runbook 時，先查 #341 的結果，
  已寫入 production 的場館要從 capture 與 Gate 2 範圍扣除，不可重複 insert。
- 重啟時：依 `docs/specs/README.md` 把本檔移回 `active/`，從**當下最新的 `origin/main`** 新建 worktree，不要復用已退役的
  `ttr-authoritative-venue-repair-worktree`。production state 自 2026-08-06 baseline 後已漂移，所有 live 數字必須重新 capture。

## Phase 0: Worktree, evidence, and spec

* [ ] 以可稽核同網域官方證據複核高田世界館與 TIFF stable root

## Phase 8: Engineer validation

* [ ] Tiff source dry-run完成；current-year empty 只標 graceful empty
* [ ] Johakyu source dry-run PASS
* [ ] Starcat source dry-run PASS

## Gate 1: Push approval

此項在 2026-10-22 的 Gate 1 只完成一半：已顯示完整 Test Report 與 risks；source dry-run evidence 與 live drift
不在該次範圍（未做任何 production 查詢），因此搬到這裡，由重啟後的 capture 前補齊。

* [ ] 顯示完整 Test Report、dry-run evidence、risks 與 live drift

## Post-Gate 1: Push and read-only capture

* [ ] 從同一 clean exact SHA 重新查官方來源與 production live state
* [ ] 產生 immutable manifest 與三筆固定新 venue UUID
* [ ] 顯示每個 full UUID action、dependency、before/after、conflict 與 digest
* [ ] 顯示 project ref、capture timestamp、new ID/name absence 與 duplicate ref counts

## Gate 2: Production approval

* [ ] 取得綁定同一 manifest SHA-256 的當下批准
* [ ] 批准明確涵蓋 writer pause/drain/resume
* [ ] 批准明確涵蓋 authoritative venue updates 與三筆 inserts
* [ ] 批准明確涵蓋 event/FC actions
* [ ] 批准明確涵蓋兩筆 duplicate conditional deletion
* [ ] Manifest digest 改變時重新取得 Gate 2

## Post-Gate 2: Production CAS and read-back

* [ ] 盤點所有 service-role writers
* [ ] Pause、drain 並證明零 in-flight writes
* [ ] 重新驗證 project ref、repo SHA、digest、all before CAS 與 refs
* [ ] 依 manifest 固定順序執行並逐筆 read-back
* [ ] Zero-reference + full-row CAS 後才刪 duplicate venues
* [ ] 驗證 registry、venue、event、FC、URL、sentinel 與 TIFF invariants
* [ ] 第二次 apply 全為 noop/already-applied
* [ ] Resume writers 並監看第一個 writer run 無回歸
* [ ] Production Tester read-only exact verdict PASS
* [ ] 保存 final journal、rollback artifacts、conflicts 與 follow-up

## Forbidden

* [ ] NOT EXECUTED before Gate 2: production venue/event/FC mutation或 duplicate deletion

## 搬移後新增

以下是 2026-10-22 獨立 Tester 驗收時新發現的項目，不在上述 26 條內。

- [ ] **R1：完整計畫的 rollback 無法回到 exact before。** online grant event
      `dec284a5-983a-4149-a093-b24dd6212a9a` 的 before 狀態中，FC `corrected_value` 為 `"null"` 與 `"[]"`，
      但 event 本身有實際地址與都道府縣；`unlock_and_write` 讓 event 與 FC 保持同步，重建不出這種不一致，
      rollback 於倒序第 37 筆 mutation 後以 event/FC exact read-back mismatch 停下，venue update 的 rollback 跑不到。
      舊版 64-action planner 有完全相同的失敗，不是 correction cycle 2 的回歸；現有測試未涵蓋完整計畫 rollback。
      Gate 2 前由 Engineer 決定：補上 malformed 狀態的 rollback 路徑，或在 Gate 2 明確揭露該筆 action 不可 exact rollback
- [ ] 補一個對完整 70-action 計畫執行 apply → 第二次 apply → rollback 的測試（R1 只有這樣才找得到）
