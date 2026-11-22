# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:url-intake` label。

- [ ] M1 `scraper/ingest_url.py`（fetch／preview／apply）與單元測試
- [ ] M2 annotator 相關性閘門豁免 `url_intake`；merger 列為 news source、優先序 100
- [ ] M3 `url-intake.yml`（fetch 無 secrets、db 走 production）與 workflow 結構測試；Tier 2 PR 由使用者合併
- [ ] M4 第一筆實際收錄：#701 的寫真展（使用者貼 `url-intake:approved`）
- [ ] M5 兩週盤點：收錄筆數、標註後需人工修正的欄位、同網域重複次數，寫入 `notes.md`
