---
description: "每週開發週報生成器 — 從 git log 自動整理本週亮點，以四工廠框架分類，輸出繁中／英文／日文三語版本"
argument-hint: "days=7 langs=zh,en,ja"
---

# Dev Weekly Report

## Inputs

* ${input:days:7}: (Optional) 統計範圍天數，預設 7 天。
* ${input:langs:zh,en,ja}: (Optional) 輸出語言組合，可選 `zh`、`en`、`ja` 任意組合。

---

## Step 1 — 取得本週 commit 清單

執行以下指令，取得指定天數內的 commit：

```bash
cd ~/development/Tokyo\ Taiwan\ Radar && git log --since="${input:days:7} days ago" --pretty=format:"%h %ad %s" --date=short
```

同時取得每日 commit 數與總計：

```bash
git log --since="${input:days:7} days ago" --pretty=format:"%ad" --date=short | sort | uniq -c
echo "Total:" && git log --since="${input:days:7} days ago" --oneline | wc -l
```

---

## Step 2 — 依四工廠分類

將 commit 訊息依下列四個工廠歸類。一個 commit 可歸屬多個工廠。

| 工廠 | 符號 | 關鍵詞／scope 範例 |
|---|---|---|
| **車身**（使用者看到的網站） | 🚙 | `feat(web)` `fix(web)` `style(web)` `fix(admin)` `feat(design)` |
| **導航**（AI 判斷、翻譯、分類） | 🧭 | `fix(annotator)` `feat(annotator)` `fix(peatix)` `fix(scraper)` `feat(sources)` |
| **後勤工廠**（穩定性、成本、CI） | 🏭 | `fix(ci)` `fix(database)` `perf(ci)` `fix(db)` `chore` `fix(admin)` security/guard |
| **駕訓場**（評估、測試、教訓文件） | 🔁 | `docs(skills)` `docs(agents)` `feat(evaluation)` `feat(governance)` `docs(scraper-expert)` |

若分類不明確，依 commit 說明推斷最近似的工廠。

---

## Step 3 — 選出各工廠 2–3 個亮點

每個工廠挑出最有代表性或最有趣的 2–3 個 commit，準備寫入週報。

優先選擇：
- **有故事性**的 bug 修復（有趣的根本原因）
- **使用者看得到**的功能（視覺、互動、資料增加）
- **重要里程碑**（第一次上線的功能、新資料來源）

---

## Step 4 — 依語言輸出週報

依 `${input:langs:zh,en,ja}` 輸出對應語言版本。每個語言版本都必須包含完整的故事結構（不可只翻譯標題）。

### 語氣與風格規範

**目標讀者**：對 AI 開發有興趣的一般大眾，非技術背景也能讀懂。

**語氣**：
- 紐約客專欄語氣——精煉、有主見、不廢話
- 適度幽默，但不刻意搞笑
- 說故事，而非條列技術規格
- 術語換成生活比喻（AI 幻想 → 「開始堅持前方有長頸鹿」）

### 固定框架：四個工廠

每篇週報**必須**包含四工廠的說明（可簡化，但不可省略）：

```
以前做網路服務像造一台車——車造好，就完工。
AI 時代不一樣，要同時打造：

🚙 車身——使用者看到的網站
🧭 導航——AI 怎麼判斷、翻譯、分類
🏭 汽車工廠——讓系統穩定、便宜、不出錯
🔁 駕訓班——每天考它路況考試
```

### 固定元素：蓮霧小姐

若本週有視覺相關更新（`feat(design)`、`fix(web)` 含 mascot/animation/OG），在正文中提及吉祥物「蓮霧小姐」與蓮霧的故事背景：
> 一顆水果，承載四百年——印尼血統、荷蘭航線、台語音韻、現代科技。日本沒有、韓國沒有，只在台灣。

若本週無視覺更新，可省略蓮霧段落。

### 結尾固定格式

每語言版本結尾：
- 繁中：`下週見 👋🍎`
- 英文：`See you next week 👋🍎`
- 日文：`また来週 👋🍎`

### 週報結構（三語通用）

```
# 開發週報 · YYYY-MM-DD ~ YYYY-MM-DD
## [週報標題（本週主題的一句話）]

[引言：一句打動讀者的提問或觀察]

[四工廠框架說明（~50字）]

[蓮霧段落（如有視覺更新）]

[本週視覺亮點（如有）]

---
## 📋 這週修了什麼
- 🚙 [車身亮點 1–2 行]
- 🧭 [導航亮點 1–2 行]
- 🏭 [後勤亮點 1–2 行]
- 🔁 [駕訓場亮點 1–2 行]
- 📡 資料來源：[新來源、補回件數（如有）]

[結尾]
```

---

## Step 5 — 品質自查

輸出前確認：

- [ ] 沒有技術術語（`selector`、`migration`、`guard` 等）暴露給讀者
- [ ] 四工廠框架出現在每個語言版本
- [ ] 「這週修了什麼」每個工廠都有至少一行
- [ ] 總字數：繁中 200–350 字、英文 200–350 words、日文 200–350 字
- [ ] 結尾有 `👋🍎`
