# Tasks

本檔只放里程碑。細項、評審意見與 bug 開 GitHub issue，貼 `spec:venue-ground-truth` label；進度看 TTR Roadmap 看板。

- [x] Phase A：地址量尺、唯讀稽核腳本、單元測試、基準（不改既有行為）— PR #709
- [x] Phase A 驗收：使用者看過抽查樣本，判錯的列補進測試（人類關卡，#708；2026-11-22 street 合格）
- [x] 使用者決定：auto_qa 排除的來源是否需要地址；#339 的去向（#708；2026-11-22 納入、拆開）
- [ ] Phase B：`enrich_addresses` 改用量尺、同名證據正向認定、不寫複製鎖；每日 workflow 跑稽核並保存 JSON（#755）；自動鎖只鎖 scraper 原值（#754）；geocoder 不寫場館（#752）
- [ ] Phase C：6 筆既有場館修正（#733，planner #758，apply 需核准）；registry 寬鬆比對（#753）；排除來源的 148 筆（#732）；帶引號的地址（#756）；09-13 清空動作（#757）
- [x] 後段設計定案並再送評審（`plan-2.md` v2.1、`plan-critique-2.md`）
- [ ] Phase D：唯讀回填 planner（本 PR）；結論是 4b（migration、傳播、apply）不做；#371 的改掛另做
- [ ] Phase E：依剩餘量決定 #366 的 web search

## Verification

母體依 2026-11-22 的決定，含 auto_qa 排除的四個來源。基準值（`audit_venue_addresses.py` 的「＋排除來源」三列，2026-11-22）：全部 75.1%、即將舉辦 78.8%、近 60 天新進 76.3%。

- [ ] 即將舉辦事件的街道級比率達到 90%
- [ ] 近 60 天新進事件的街道級比率達到 88%

目標比不含排除來源時（95%、92%）低：排除來源裡有連鎖店、串流平台與團體名，這些本來就沒有單一地址。Phase C 之後依實際組成重訂。
