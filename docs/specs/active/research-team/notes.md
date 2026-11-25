# Notes

## 2026-11-25 試跑（quick 深度）

議題：日本民眾對台灣的好感度為何長期偏高？報告：https://claude.ai/artifact/95GzKXnoyTbHpycUVwnYs1 （私人 Artifact，附 state.json）。

| 步驟 | 結果 |
| --- | --- |
| Generation ×3（平行） | 回傳合法 JSON；6 個假說、17 個不重複來源。各約 35 秒、10 萬 token |
| Proximity | 由 Supervisor 判斷，H2 併入 H1（假說只有 6 個，未啟動 subagent） |
| Reflection ×5（平行） | 全部回報無法開啟來源，所有主張維持 `unchecked`，沒有任何一個標成已驗證；並各自提出反證線索 |
| Ranking ×1（5 場） | 回傳合法 JSON；評審理由明說判斷依據是可否證性與線索方向 |
| Evolution | quick 不執行 |
| render | 通過驗證；21 個主張中 1 個已驗證、1 個部分支持、19 個未查核 |

合計 10 個 subagent（含一次探測抓取的小 agent）。

### 發現

1. **查核受阻有兩層原因。** 第一層是雲端環境的網路等級為 Limited、允許清單是空的，WebFetch 回 `getaddrinfo ENOTFOUND`。建立只含 12 個來源網域的 `research-team` 環境並切換後，curl 經 proxy 可以連線，但代表處的 PDF、內閣府調查頁、Taipei Times、The Diplomat 回 HTTP 403（網站拒絕自動化存取），NUS 的 PDF 回 Incapsula 驗證頁；只有 nippon.com 開得了。第二層是 WebFetch 工具在這台機器重建前仍沿用舊的網路規則，切換環境後仍然 ENOTFOUND。
2. **機械門檻有效。** Reflection agent 在開不了來源時沒有用搜尋摘要充當查核；報告內文只有一個腳註，指向唯一開啟過的來源。
3. **唯一的已驗證主張由 Supervisor 用 curl 查核**，沒有與產生假說的 context 分開，已寫進報告的限制。
4. 手動合併 subagent 回傳容易出錯，試跑中途新增了 `merge` 子命令；Generation 階段仍是手動合併，下一次試跑才會完整用到 `merge`。
5. Generation agent 有一個把次級來源標成 `primary: true`（NUS 的 background brief），Supervisor 合併時改正。之後由 Reflection 覆核 `primary`。

### 尚未驗證

- 「已驗證」路徑在真實議題上由 Reflection subagent 完成（需要能開啟來源的環境）。
- Evolution 與第二輪以上的迭代、`resume`。
- standard、deep 深度的成本。
