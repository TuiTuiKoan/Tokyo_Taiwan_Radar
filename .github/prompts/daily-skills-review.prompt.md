---
description: 每日開發結束後，反思本次工作，決定是否建立或更新 Skill。
argument-hint: "（可選）今天做了什麼，例如：修了 peatix 日期解析"
---

# Daily Skills Review

## Step 1：列出今天使用過的 Agents 與 Skills

若使用者提供了 `${input:today_work}` 作為上下文，以此為基礎分析；否則自行回顧本 session 的對話紀錄，列出：

- 今天使用過的 Agents（例如 Engineer、Scraper Expert、Tester）
- 今天參照或觸發過的 Skills（例如 date-extraction、peatix、engineer）
- 今天修改或建立的檔案

---

## Step 2：判斷是否有值得固化的新 Pattern

針對今天的工作，判斷是否出現以下情況：

- 同一類操作在 session 中重複出現超過 2 次
- 發現了一個未來一定會再用到的規則或限制
- 踩到了一個坑，修復後得到了明確的「下次怎麼做」的結論

若以上都沒有 → 輸出「今天沒有新 pattern 需要固化」並結束。

---

## Step 3：檢查相關 SKILL.md 的觸發條件

對每個與今天工作相關的 SKILL.md（根據 Step 1 列出的 Skills），確認：

- 觸發條件（何時應使用此 Skill）是否仍然精確？
- 是否有任何例子或規則已經過時？
- 是否有遺漏的 edge case 應補充進去？

使用 `read_file` 讀取相關 SKILL.md 後再作判斷。

---

## Step 4：輸出建議

以條列方式輸出，每條格式為：

```
📌 建議新增 SKILL: <新 Skill 名稱>
   理由：<一句話說明為何需要這個新 Skill>

📝 建議修改 SKILL: <現有 Skill 名稱>
   修改位置：第 N 行
   建議改為：<具體文字>
   理由：<一句話說明>
```

若無任何建議，輸出「今天的工作不需要更新任何 Skill」。

---

## 結語

提醒使用者：

> 只要說「請更新」，我就會直接寫入對應的 SKILL.md，不需要你手動操作。
