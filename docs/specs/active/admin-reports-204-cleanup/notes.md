---
title: Plan Critique (Round 2) — Admin Reports 204-Row Cleanup Plan
critic-model: gpt-5
reviewed-plan: ./proposal.md
ms.date: 2026-07-11
round: 2
---

# 批評報告（第二輪）：Admin Reports 204-Row Cleanup Plan

> 對象：[proposal.md](./proposal.md)（實體檔 598 行，已依第一輪 critique 修訂）。
> 本輪定位：驗證第一輪三大解耦是否正確落地，並依 history.md 教訓**重新質疑上一輪自己的修訂**，專查大量計數調整是否引入新矛盾。
> 註：memory view 本輪一度顯示損壞（空行／重複行號／混入雜散文字）；已用 terminal 讀實體檔案確認內容乾淨、無注入，批評基於實體檔案。

## TL;DR

第一輪三大建議**全部正確落地**，算術完全自洽（117 + 43 + 44 = 204）。本輪未發現任何結構性 blocker，僅 3 個**文件層一致性瑕疵**（🟡）：兩張 disposition 表基準不一致、Group F step 1 措辭殘留「immutable ledger」、confirmReport 縮減後對 compound row 行為未明說。三者皆可在交 Engineer 前用小幅文字修訂解決，**不需再回架構設計**。

---

## 1. 商業主軸對齊（Business Alignment）

**評分：🟢 對齊（維持第一輪結論）**

主軸未變（資料完整性 #1）。解耦後價值排序更清楚：117 筆高 ROI 先行、43 筆低 ROI 後置。無新偏離。本段不再展開。

---

## 2. 複雜度 vs 價值評估

**評分：🟡→🟢 改善（單體風險已下降）**

第一輪標記的「very-high 單體耦合」已被拆解：

- 複雜度**分散**到兩個獨立部署循環（Phase 3 cycle 1 = Group A–E；Phase 6 cycle 2 = Group F），各自有 Tester PASS、push approval、apply snapshot。單次中斷面從 204 縮到 117 或 43。
- confirmReport 從「無-transaction 手動補償重構」降級為「最小 status-last」（Group E L331–332），移除第一輪標記的 +1 web 複雜度。
- 淨效果：整體工作量未減，但**單次部署的爆炸半徑顯著縮小**，符合第一輪 diff 1 意圖。

價值分層不變（Wave A high / Wave B low-medium / 人工 44）。比值警示解除。

---

## 3. 優先順序提醒（Anti-Rabbit-Hole）

**評分：🟢 已修正（第一輪 🔴/🟡 全數解除）**

- 3.1 主批評（Wave A 被 Group F 阻擋）**已解**：Phase 3 L353「gates Wave A only. Group F is explicitly out of scope for this deployment cycle」；Group F L337 起「cannot start until Wave A completes its nightly observation gate」。零資料依賴的解耦正確落地。
- 3.2 peatix category（1 筆）**已解**：Group E L330 改 manual-only，Excluded L168 明列不改 writer。不再為 1 筆觸發 Category Sync 全驗證。
- 3.3 organizer 21 筆**已解**：Group F L338 evidence inventory 量化 `N` / `o_manual`，L339 只對 `N` 筆改 parser。evidence-first gate 正確前置。

無新 rabbit-hole。

---

## 4. 全站架構整合分析

**評分：🟡 三個文件層一致性瑕疵（本輪新查出，皆非架構 blocker）**

### 4.1 兩張 disposition 表基準不一致 🟡

- 主表（L65–73）標為 **immutable baseline**：Deterministic=32、Human=43。
- 緊接的 98-row 表（L77–90）標題改為 **by `current_disposition`**：Deterministic=10、Human=24。
- 同一份文件並列，且 `auto_qa_missing_category` 那 1 筆在主表算 deterministic、在 98-row 表算 human。L75 說明文字雖解釋了移動，但**兩表欄位語義不同（baseline vs current）**會讓 Engineer 讀 98-row 表時誤判 baseline 組成。
- 這是第一輪計數調整的連帶產物。建議 diff（見第 6 段）。

### 4.2 Group F step 1 措辭殘留「in the immutable ledger」🟡

- L337：「Bind each of the 43 source-specific baseline rows to … regression fixture **in the immutable ledger**」。
- 與三處矛盾：(1) 架構決策 + Phase 0 L239 已強調 immutable ledger「never edit it afterward」；(2) Group F step 3（L339）自己說「The immutable discovery ledger remains untouched」；(3) regression fixture 是實作期產物，不可能寫進 Phase 0 就凍結的 ledger。
- 純措辭殘漏（第一輪改了 step 3 未回頭改 step 1）。建議改為 execution manifest。

### 4.3 confirmReport 縮減後對 compound row 行為未明說 🟡

- Group E L331–332 把 confirmReport 縮成 fail-fast/status-last，明確排除新語義。
- 但 Phase 7 L482–483 要求 2 筆 compound「without closing its other type prematurely」「in one Admin decision」。
- 縮減版若沿用現況「一次更新整個 report status」，則無法只關 compound 的單一 type。計畫未說明縮減版如何滿足 compound 的 partial-type 需求，也未說 compound 是否走既有分支。
- 這是第一輪縮減 confirmReport 範圍後的連帶 gap。建議加一句驗證或明示 compound 路徑。

### 算術完整性驗證（本輪重算，全部平衡）

| 檢查 | 明細 | 結果 |
|------|------|------|
| baseline ledger | 58+32+43+20+8+43 | 204 ✓ |
| 98-row current | 4+10+21+39+24 | 98 ✓ |
| Wave A | A1 78（37+20+21）+ A2 31 + A3 8 | 117 ✓ |
| 三分區總和 | Wave A 117 + Wave B 43 + manual 44 | 204 ✓ |
| Wave A 後未解 | 43 + 44 + a_manual | 87 + a_manual ✓ |
| Wave B 後未解 | 44 + a_manual + o_manual + b_manual | 自洽 ✓ |

算術是第一輪修訂的最大風險點，本輪逐項確認**無誤**。

### Guard 過覽（無新觸發）

- Category Sync Guard：因 category 改 manual-only，Group E L333 仍保留 annotator.py 觸碰時的同步驗證，且 L333 明示「no message file should change」。✅
- immutable-ledger 完整性：cleanup utility L510「Apply verifies the immutable discovery-ledger digest still matches … never edits that ledger」。✅（僅 4.2 措辭殘留需修）

---

## 5. 既有 Component 復用建議

**評分：🟢 維持充分復用（無變化）**

第一輪已確認復用 `lock_empty`/`_fc_value()`/`venue_registry`/`unlock_and_write()`。本輪縮減 confirmReport 反而**減少**新建面（不再新增補償機制）。execution manifest 是既有 immutable ledger 的衍生副本，非平行新結構。無重造輪子。

---

## 6. 建議更新後的計畫

**結論：接受計畫，可交 Engineer。三個瑕疵皆文件層小修，不需回架構設計。**

三大解耦正確落地、算術自洽，標任何 🔴 都是不誠實。以下 3 個 🟡 建議在交付前一次修掉：

### diff A — 統一兩張 disposition 表基準（對應 4.1）

- 於 98-row 表（L77）標題後加一句：「Deterministic 與 Human 欄已反映 category 的 current_disposition；對應 baseline 為 Deterministic 11、Human 23」。
- 或加一欄 baseline/current 對照，讓兩表可交叉核對。

### diff B — 修 Group F step 1 措辭（對應 4.2）

- L337「in the immutable ledger」→「reference each row in the execution manifest（immutable ledger 已於 Phase 0 凍結，不再寫入）」。

### diff C — 明示 confirmReport 縮減版對 compound 的行為（對應 4.3）

- 於 Group E L332 後或 Phase 7 L483 加一句：確認縮減版 confirmReport 對 2 筆 compound 是否僅更新目標 type 的 status、保留另一 type pending；若現況不支援，compound 走既有人工分支且不經此 action 關閉。

### 維持原樣的正確設計（不要再動）

- 兩循環部署 gate（Phase 3 / Phase 6）、Wave A 獨立 nightly、Phase 8 全局 nightly：正確，維持。
- immutable ledger + SHA-256 + execution manifest append-only log：資料模型正確，維持。
- evidence-first `N`/`o_manual`/`b_manual` 動態算術：自洽，維持。
- Excluded 明列 confirmReport 完整補償與 peatix writer 為 follow-up：範圍誠實，維持。

---

## 與第一輪的差異結論

第一輪：🔴 單體耦合（1 個主 blocker）+ 2 個 🟡。
第二輪：🔴/🟡 主批評**全數解除**，僅剩 3 個文件層 🟡（計數調整的連帶產物）。

計畫已達可交付門檻。建議修 diff A/B/C 後交 Engineer，不需再過第三輪 Critic。
