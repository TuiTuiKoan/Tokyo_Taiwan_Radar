# Agentic Design Workflow Slide Deck — Maintenance History

<!-- Append new entries at the top -->

---

## 2026-06-13 — Bilingual slide deployment workflow: case-sensitive paths & git push prerequisite

**問題：**
1. 投影片更新後，本地文件已修改且複製到 `web/public/202606/NormativityDesign/`（大寫），但 Vercel 上仍顯示舊版內容，且新增的 p.13 頁面無法出現。
2. 部署目錄名稱不一致：本地部署路徑為 `/202606/NormativityDesign/`（大寫），但生產 URL 指向 `/202606/normativity-design/`（小寫），導致雙重目錄共存。
3. 部署宣告時機過早：聲稱「已部署」，但實際未執行 `git push origin main`，致使 Vercel 無法取得更新。

**根本原因：**
1. **部署流程不完整**：缺乏 `git push` 這個關鍵環節的驗證檢查。
   - 本地 commits 存在但未推送時，Vercel webhook 無法被觸發
   - 需要確保 `git log origin/main` 與 `git log HEAD` 同步後才能宣稱「已部署」
2. **路徑大小寫混淆**：POSIX 檔案系統對大小寫敏感，但時隔多天後引入的新路徑與舊路徑大小寫不一致。
   - 直接 `cp` 到 `NormativityDesign/` 而未檢查 git history
   - 造成儲存庫中同時存在大寫和小寫版本

**修正：**
1. 統一部署路徑為小寫 `/202606/normativity-design/`（與線上生產 URL 對齊）
2. 刪除重複的大寫目錄 `NormativityDesign/`，保留單一來源
3. 在宣稱「已部署」前，必須驗證 `git push origin main` 已完成且 `git log origin/main -1` 顯示最新 commit

**改進的部署檢查清單：**
```bash
# 1. 修改投影片源文件（.html）
# 2. 複製到部署路徑
cp docs/slides/agentic-design-workflow.zh.html web/public/202606/normativity-design/index.zh.html

# 3. 驗證 git 狀態
git status

# 4. 提交變更
git add <files>
git commit -m "..."

# 5. **必須執行** — 推送到遠端
git push origin main

# 6. 驗證推送完成
git log origin/main -1  # 應顯示剛才的 commit

# 只有在第 5 步完成後，才能宣稱「已部署，Vercel 在處理」
```

**關鍵教訓：**
- **路徑大小寫統一**：部署前檢查 git history 中是否已存在路徑，並與生產 URL 對齐（通常線上為小寫 kebab-case）
- **`git push` 是部署的分界點**：本地修改 ≠ 部署；只有在 `git push origin main` 完成、Vercel webhook 被觸發後，才能稱之為「已部署」
- **雙重驗證**：
  1. 檢查 `git log origin/main` 是否包含最新 commit
  2. Vercel Dashboard 是否顯示新的 build 任務

---

## 2026-06-13 — Bilingual HTML indentation preservation: 2-space (ZH) vs 1-space (EN)

**問題：** 在對英文版本 (`agentic-design-workflow.en.html`) 進行編輯時，如不小心改變了縮進風格（從 1-space 改為 2-space 或反之），會導致 git diff 充滿大量非實質性改動，且難以 review。

**根本原因：** 投影片源文件由於歷史原因採用不同的縮進標準：
- 中文版本（`.zh.html`）：2-space 縮進
- 英文版本（`.en.html`）：1-space 縮進
- 若使用編輯器的 "Format Document" 功能或自動化工具，會導致縮進被重新統一，造成大範圍無意義的變更

**修正：**
1. 編輯前確認當前文件的縮進風格
2. 使用 `replace_string_in_file` 工具時，包含足夠的前後文行數（5 行以上），確保替換目標唯一且不會涉及縮進的自動轉換
3. 編輯後執行 `git diff` 檢查，確認僅包含實質內容變更，無大量縮進重排

**技術細節：**
```bash
# 檢查當前縮進風格
head -20 docs/slides/agentic-design-workflow.en.html | cat -A  # 顯示空格和製表符

# 檢查 git diff 中是否只有內容變更
git diff docs/slides/agentic-design-workflow.en.html | grep -E '^\+[[:space:]]|^-[[:space:]]'  # 若結果較多，表示縮進被改動
```

**應用到本次工作：**
- 在 p.2 和 p.8 的換行符改動時，保持了 1-space 縮進（英文版）和 2-space 縮進（中文版）各自的風格
- 使用 `multi_replace_string_in_file` 時，確保了 `oldString` 和 `newString` 的縮進風格完全一致

---

## 2026-06-13 — New architectural explanation slide (p.13) bridging design layers with live code references

**內容：** 新增投影片頁 13 （S-4c）「規範設計的三層」，展示如何在 Code、Skill、Agent 三層實踐規範設計。

**實作細節：**
- **Layer Ⅰ (Code)**: Event dataclass 標準化（`source_id`、`start_date`、多語言名稱、三欄位地點系統）
  - GitHub 參考：[base.py#L120–165](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/blob/main/scraper/sources/base.py#L120-L165)
- **Layer Ⅱ (Skill)**: Taiwan Relevance 規則（「Wansei」訊號、具體選擇理由、三階段 filter 順序）
  - GitHub 參考：[SKILL.md#L15–31](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/blob/main/.github/skills/scraper-expert/SKILL.md#L15-L31)
- **Layer Ⅲ (Agent)**: Session Start Checklist 執行模式（讀規則後才動手，修復 bug 沉澱回 Skill）
  - GitHub 參考：[agent.md#L20–24](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/blob/main/.github/agents/scraper-expert.agent.md#L20-L24)

**檢查清單（新增大規模內容時）：**
1. ✅ 中文版本（`.zh.html`）內容完成
2. ✅ 英文版本（`.en.html`）翻譯完成且語意等價
3. ✅ 所有後續 `pageno` 值遞增 +1（自動化 Python 腳本反向處理）
4. ✅ 所有 GitHub 連結使用精確行號範圍（`#L20–L24` 格式）
5. ✅ 頁面於投影片流中位置正確（p.12 DevOps 之後，p.15 多模態協作之前）
6. ✅ 兩個語言版本的 `brandfoot` 和 `pageno` 一致

---

## 2026-06-13 — Line break insertion at narrative punctuation (p.2, p.8)

**內容：** 在中文版本 p.2 和 p.8 的敘述段落中，於「——」標點後插入 HTML 換行符 `<br>`，改善視覺層級。

**中文版本變更：**
- **p.2**：「...給大家看 —— 一個正在運作...」 → 「...給大家看 ——<br>一個正在運作...」
- **p.8**：「...藏在水面下 —— Agent 位在...」 → 「...藏在水面下 ——<br>Agent 位在...」

**英文版本對應同步：**
- **p.2**：「...real-world case study — a live product...」 → 「...real-world case study —<br>a live product...」
- **p.8**：「...surface — agents live...」 → 「...surface —<br>agents live...」

**視覺設計理由：**
- 「——」 代表思維轉折或補充說明，換行後能強化節奏感
- 符合投影片的「講話停頓」節奏
- 改善主觀視覺平衡（避免行過長）

---

**Last updated**: 2026-06-13  
**Maintained by**: Docs Team  
**Related files**: `docs/slides/agentic-design-workflow.zh.html`, `docs/slides/agentic-design-workflow.en.html`, `web/public/202606/normativity-design/index.*.html`
