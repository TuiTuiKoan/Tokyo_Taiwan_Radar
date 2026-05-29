---
title: GITHUB_TOKEN Sync Checklist
description: GITHUB_TOKEN 依賴位置盤點與 PAT 輪替同步清單，避免 create-issue 流程中斷
author: Architecture team
ms.date: 2026-05-01
ms.topic: how-to
keywords:
  - github token
  - pat
  - token rotation
  - scraper
  - checklist
estimated_reading_time: 4
---

## 目的

此清單用於確保 GITHUB_TOKEN 輪替時，同步更新所有必要位置，避免研究來源標記為 researched 後，無法建立 GitHub Issue。

> [!IMPORTANT]
> 本檔案是 GITHUB_TOKEN 同步清單的唯一維護來源。請勿在其他位置維護重複版本。

## 何時使用

* 每 90 天例行輪替時
* 收到 GitHub 即將到期通知時
* 執行 update_source.py 的 create-issue 參數出現 401 或 403 時

## 必須同步的 3 個位置

### 1. Token 值本體

* 檔案: scraper/.env
* 位置: 第 11 行
* 內容格式: GITHUB_TOKEN=github_pat_xxx
* 說明: 這是執行期實際使用的 token 值

驗證方式:

```bash
grep "^GITHUB_TOKEN=" scraper/.env
```

### 2. 讀取與錯誤提示位置

* 檔案: scraper/update_source.py
* 位置: 106, 109, 217
* 說明: create_github_issue() 會從環境變數讀取 GITHUB_TOKEN，並在缺值時拋出錯誤

重點需求:

* fine-grained PAT 需具備 Issues: write + Metadata: read 權限
* classic token 需具備 repo scope

### 3. Agent 操作文件

* 檔案: .github/agents/researcher.agent.md
* 位置: 99
* 說明: 記錄 create-issue 的權限前提與操作說明

驗證方式:

```bash
grep -n "GITHUB_TOKEN" .github/agents/researcher.agent.md
```

## 標準輪替流程

1. 在 GitHub 建立新 PAT
2. 更新 scraper/.env 的 GITHUB_TOKEN
3. 檢查 researcher.agent.md 的權限描述是否仍正確
4. 本機執行一次 create-issue 測試
5. 確認 Issue 已成功建立

測試指令:

```bash
cd scraper
source venv/bin/activate
python update_source.py --url "https://example.com" --status researched --create-issue
```

## 權限檢查速查

最小建議權限:

* Fine-grained PAT: Issues: write + Metadata: read
* Classic token: repo scope

## 快速一致性檢查

可在 repo 根目錄直接執行:

```bash
python3 scripts/check_token_permission_consistency.py
```

結果判讀:

* Exit code 0: 口徑一致，未發現違規
* Exit code 1: 發現違規，輸出會列出 file:line 與摘要

GitHub 頁面快速核對:

1. GitHub Settings
2. Developer settings
3. Personal access tokens
4. Fine-grained tokens
5. 點開目前使用中的 token，確認 Repository permissions 內有:
  * Issues: Write
  * Metadata: Read

本機快速驗證:

```bash
cd scraper
source venv/bin/activate
python update_source.py --url "https://example.com" --status researched --create-issue
```

判讀結果:

* 成功建立 Issue: 權限足夠
* 403 Resource not accessible: 權限不足（優先檢查 Issues 或 Metadata）
* 401 Bad credentials: token 過期或 token 值錯誤

## 驗收標準

* grep 可讀到新的 GITHUB_TOKEN 值
* create-issue 指令可成功建立 Issue
* researcher.agent.md 的權限描述與實際 token 類型一致
* Git 歷史未出現 pat 明文外洩

## 常見異常與處理

| 症狀 | 可能原因 | 處理方式 |
|---|---|---|
| 401 Bad credentials | Token 過期或錯誤 | 立即重新產生 PAT 並更新 .env |
| 403 Resource not accessible | 權限不足 | 重建 fine-grained PAT 並加入 Issues: write + Metadata: read |
| GITHUB_TOKEN env var required | .env 缺值或未載入 | 檢查 .env 是否存在且鍵值正確 |

## 依賴關係補充

* 被動監控: scraper/secret_reminder.py 會透過 load_dotenv 讀取 .env，並在輪替週期時發送 LINE 提醒
* CI 狀態: 目前工作流程檔案未直接使用 secrets.GITHUB_TOKEN 作為此流程依賴

## 相關文件

* .github/instructions/token-rotation.instructions.md
* .github/agents/researcher.agent.md
* scraper/update_source.py
* scraper/secret_reminder.py

## Secrets 文件入口

* [GITHUB_TOKEN 快速參考清單](docs/GITHUB_TOKEN_SYNC_CHECKLIST.md)
* [GITHUB_TOKEN 完整輪替指南](.github/instructions/token-rotation.instructions.md)
* [Secrets 生命週期與審計路線圖](.github/SECRETS_LIFECYCLE.md)

---

### Location 6: Yahoo! JAPAN ジオコーダ API AppID (`YAHOO_GEOCODER_APPID`)

- **File**: `scraper/.env`
- **Format**: `YAHOO_GEOCODER_APPID=<appid>`
- **Purpose**: Geocodes `events.location_address` → lat/lng
- **Who reads it**: `scraper/geocode_events.py`
- **Rotation**: No expiry — revoke and re-register if leaked
- **CI secret**: Add `YAHOO_GEOCODER_APPID` to GitHub Actions secrets (`Settings → Secrets and variables → Actions`)
- **Attribution required**: Footer "Powered by Yahoo! JAPAN" on any page displaying geocoded data
- **Note**: 50,000 requests/day free tier. Not a rotating secret. See [Yahoo! Developer Network](https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html) for registration.
