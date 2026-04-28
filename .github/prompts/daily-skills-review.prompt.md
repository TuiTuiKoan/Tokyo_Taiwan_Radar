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

> 只要說「請更新」，我就會直接寫入對應的 SKILL.md，不需要你手動操作。

---

## Step 5（執行「請更新」之後自動觸發）：收尾

當使用者說「請更新」並完成所有 SKILL.md 寫入後，**立刻執行以下兩個動作，不需要等待使用者再次確認**：

### 5-1. 寫入 history.md

對每個今天**實際修改過的** SKILL.md，在對應的 `history.md`（同目錄）最頂端追加一筆記錄：

```
---
## YYYY-MM-DD — <本輪 review 的一句話標題>
**新增/修改：** <列出本輪在這個 SKILL.md 加了什麼，1–3 條>
**來源：** daily-skills-review（Step 4 建議）
```

- 若 `history.md` 不存在，用 `create_file` 建立
- 若修改了多個 SKILL.md，各自追加一筆，不合併
- 若今天的 review 結論是「無需更新任何 Skill」，跳過此步驟

### 5-2. 詢問是否 commit + push

完成 history 寫入後，**輸出以下問句，不要做其他事**：

> 以上變更已寫入完畢。要 commit 並 push 嗎？
> 我會使用以下 commit message（可修改）：
>
> `docs(skills): YYYY-MM-DD daily review — <本輪主要變更的一句話摘要>`

若使用者回答「是」或「好」或「push」→ 執行：

```bash
git add <所有修改過的 SKILL.md 和 history.md>
git commit -m "<上述 message>"
git push origin main
```

若使用者修改了 commit message → 用修改後的版本。
若使用者回答「不用」→ 僅輸出「已跳過 commit/push」並結束。
