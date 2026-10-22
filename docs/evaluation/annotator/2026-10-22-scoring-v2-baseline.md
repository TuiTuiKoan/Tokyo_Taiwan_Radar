# Annotator Golden Set — scoring v2 基準（2026-10-22）

量尺改版（#324，PR #365）後的第一份基準。golden set 沒有變動，仍是 2026-05-18 凍結的 50 筆；擴充與清理在 #353 處理。

## 執行條件

- mode：frozen；stage：1（LLM only）；frozen sha256：`b93672a8…ebe7`
- 兩次執行：workflow_dispatch run 39756721033（門檻 0.85）、PR run 39762878350（加上逐筆分數）。下表以第二次的逐筆分數，用最終門檻 0.70 重算。
- 每次花費約 $0.14；GPT-4o-mini 佔絕大部分，embedding 約 $0.0002。
- 兩次執行在 0.85 門檻下的 Tier 1 結果是 27／76 與 25／76。LLM 輸出在 temperature 0.1 下仍有差異，單次 ±2 筆以內不構成迴歸。
- 以最終門檻 0.70 確認的 PR run 39763498551：Tier 1 annotator 36／76（47.4%），與下表重算值相差 1 筆。

## v1 與 v2 對照（Tier 1，annotator 分桶）

| Field | Method (v2) | Tested | v1 準確率（10/01） | v2 準確率 |
|---|---|---|---|---|
| category | set | 13 | 30.8% | 30.8% |
| description_en | semantic | 8 | 0.0% | 87.5% |
| description_zh | semantic | 15 | 0.0% | 73.3% |
| is_paid | exact | 1 | 0.0% | 0.0% |
| location_name | fuzzy | 38 | 31.6% | 39.5% |
| name_zh | fuzzy | 1 | 7.1%（14 筆） | 0.0%（1 筆） |
| **合計** | | **76** | **20.4%**（含片名） | **48.7%** |

片名查詢分桶（不計入上表）：name_zh 1／13、name_en 4／14，合計 18.5%。這是 LLM-only 的數字，只供對照；片名由 works 表與 eiga.com 查詢取得，成績看 Stage 2。

失敗 case（annotator 分桶）：31／50。

## 語意門檻校準

門檻定在 0.70。依據為 PR run 的逐筆 cosine：

| Field | 期望值 vs 同一 case 輸出 | 負對照（期望值 vs 下一筆 case 的輸出） |
|---|---|---|
| description_zh | 0.58 – 0.88，15 筆 | 0.13 – 0.48，15 筆 |
| description_en | 0.62 – 0.93，8 筆 | 0.26 – 0.57，另有一筆 0.78 |

- 負對照的 0.78 來自同一部片在兩間戲院的兩筆 case 相鄰，內容本來就相近，不代表無關文字。
- 0.73 的 `258ea821` 實際翻譯比期望值更正確：期望值寫「悲情城市擔任製片」，輸出寫「侯孝賢擔任製片」。0.82 的 `262752a7` 也是合格翻譯。這兩筆在 0.85 門檻下會被判失敗。
- 低於 0.70 的 5 筆列在報表的 Failures，供人工判讀。

語意比對只判斷內容是否相同，無法檢查日期、地點這類細節。

## location_name 的分佈

38 筆中 22 筆的輸出是 null，分數為 0；其餘 16 筆中 15 筆完全相符，1 筆 0.64。失分幾乎都來自「LLM 沒有從 raw 文字抽出地點」，fuzzy 門檻的高低影響不大。地點的分段評估見 #325。

## Feedback loop A2／A3（2026-09 窗口，唯讀 SQL 重算）

| 指標 | 舊值 | 修正後 |
|---|---|---|
| A2 | 3515 hits / 775 annotated（453.55%） | 每筆受保護欄位數 4.54 |
| A3 | ndl_opensearch 等 10 個來源 100% | 194 筆新事件，24h 內讀者回報 0 筆；系統自動回報 89 筆另計 |

A3 修正後的 0 是實際狀況：讀者從前台回報的件數很少。原本的 100% 全部來自 auto-QA 與 annotator 自動寫入的回報。

## 交給 #353 的 golden 資料問題

- `258ea821`（ks_cinema「めぐる面影、今、祖父に会う」）：期望 name_zh 是另一部片「車頂上的玄天上帝」，name_en「Be with Me」也不符。
- `05aefbdf`（peatix）：期望 category 被存成 Postgres 陣列字串 `'{movie,indigenous,…}'`，不是 list，set 比對必然失敗。
- `b26019c7`（taiwan_cultural_center）：期望 description_zh 是「雲門舞集的《WAVES》將在雲門舞集上演。」，地點錯置。
- location_name 的期望值來自 `field_corrections`，但該欄位 1324 筆中有 1323 筆是腳本寫入的鎖定值（`corrected_by` 為空），不是人工修正。golden 標籤的 `from_fc` 不能當作「人工確認」。
