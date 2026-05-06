---
title: AI 生成程式碼的人工審查流程
description: 在執行 AI 生成的 shell/Python 程式碼前，快速辨識潛在惡意內容的操作指南
ms.date: 2026-05-06
---

## 背景

2026-05-06 曾偵測到一起 **shell command injection** 事件：一段 AI 生成的 Python 腳本，
在 f-string 變數名稱位置夾帶了 `rm -f` 指令，試圖刪除本地 OAuth token 檔案。
該指令因 Python SyntaxError 自動失敗（exit code 1），未造成實際損害。

此類攻擊的特徵：

- 惡意內容藏在長程式碼中間，視覺上難以辨識
- 路徑高度精確，代表攻擊者可能從 AI context（terminal 輸出、對話歷史）取得路徑資訊
- 失敗的唯一原因是 Python 語法限制；若攻擊者改用其他注入方式，可能成功

---

## 危險模式速查

在執行任何 AI 生成的程式碼前，搜尋以下關鍵字（`Cmd+F`）：

```
rm          → 刪除檔案
os.remove   → Python 刪除檔案
shutil      → Python 目錄/檔案操作
subprocess  → 執行任意 shell 命令
os.system   → 同上
eval / exec → 動態程式碼執行
```

找到關鍵字後，確認：

1. 這個功能**真的需要**這個操作嗎？（例如「刪除暫存檔」是合理的，「刪除 credentials/」不是）
2. 路徑是否在預期範圍內？（`/tmp/`、當前專案目錄 → 可接受；`~/.ssh/`、`credentials/`、`token.json` → 警戒）

---

## 日常審查流程

### 快速流程（30 秒，適合大部分情況）

```
AI 生成程式碼
    ↓
Cmd+N → 貼入 VS Code 空白檔（讓語法高亮顯示異常）
    ↓
Cmd+F 搜尋：rm / subprocess / os.remove / shutil
    ↓
沒找到 → 直接複製到 terminal 執行
找到了 → 確認路徑合理且功能需要此操作 → 再執行
```

### 標準流程（適合較長的腳本）

不要用 `python3 -c "..."` 執行長腳本，改成先存檔再看：

```bash
# 1. 存成暫存檔
cat > /tmp/review_me.py << 'EOF'
# 貼上 AI 生成的程式碼
EOF

# 2. 看完整內容
cat /tmp/review_me.py

# 3. 確認無疑慮後執行
python3 /tmp/review_me.py
```

---

## 本專案的高風險操作清單

以下涉及敏感路徑或副作用，**必須逐行審查**再執行：

| 類型 | 說明 |
|------|------|
| `scraper/.env` 操作 | 包含所有 API 金鑰 |
| `credentials/` 或 `token.json` 操作 | OAuth token，遺失需重新授權 |
| 包含 `/Users/` 絕對路徑的 rm | 可能跨專案刪除 |
| `supabase` + `DELETE` / `UPDATE` 無條件 | 可能批量改寫生產資料 |
| `git push --force` | 覆蓋遠端歷史 |

純讀取操作（Supabase `.select()`、`print` 輸出、`--dry-run`）風險極低，可快速過。

---

## 已知攻擊案例

### 2026-05-06 — f-string 變數名稱注入

**目標**：刪除 `stock status sync` 專案的 Google OAuth token

**手法**：

```python
# 正常程式碼（預期）
print(f'{fname}: backToList = {value} added')

# 惡意程式碼（實際）
print(f'{fname}: backToList = {valuerm -f "/Users/flyingship/development/stock status sync/credentials/token.json"} added')
```

**結果**：Python SyntaxError，exit code 1，rm 未執行，token 安全

**防範要點**：f-string `{` 後面若出現空格，就是異常（Python 變數名稱不含空格）

---

## 定期檢查建議

| 項目 | 頻率 | 說明 |
|------|------|------|
| `credentials/token.json` 存在確認 | 每次重大操作後 | `ls -la` 確認 |
| Google 第三方授權清單 | 每月 | myaccount.google.com → 第三方應用程式 |
| Claude / ChatGPT 對話記錄 | 每季 | 清除含敏感路徑的對話 |
