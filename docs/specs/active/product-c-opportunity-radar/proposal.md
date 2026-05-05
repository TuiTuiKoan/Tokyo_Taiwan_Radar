---
slug: product-c-opportunity-radar
title: Product C 機會雷達 MVP（週報 LINE 推播 + 城市×類別×主辦類型維度）
status: active
branch: feat/product-c-opportunity-radar
created: 2026-05-05
tags: [product, business, line, weekly-report]
---

## What（做什麼）

把現有的 `weekly_line_broadcast.py` 從「未來事件清單」升級為**「機會雷達訂閱」MVP**：

- 加入 **3 個切片維度**：城市（東京/關西/福岡/其他）× 類別 × 主辦方類型
- 加入 **「值得注意」訊號**：新類型主辦方、新城市首次活動、價格異常
- 提供 **訂閱層級**：免費（每週 LINE）vs 付費（每日 + 自訂篩選 + 月度 markdown 報告）

本 spec 是商業化定位中 **Product C** 的 MVP 版本，定價 ¥30k–¥80k/月（見 market-positioning-strategy）。

## Why（為什麼）

- Product C 是三產品中**最低啟動成本**的：複用既有 weekly LINE 廣播 + 既有資料模型
- 訂閱型 SaaS 比顧問型（Product A/B）更易自動化，更快驗證 willingness-to-pay
- LINE 是日本台僑社群最高滲透率的通訊工具，產品-市場契合度高
- 公部門 / 智庫 / 品牌客戶**第一次接觸 TTR 的入口**通常是訂閱類產品，再升級到顧問報告

## Non-Goals（不做什麼）

- ❌ 不做付費 paywall 機制（MVP 階段所有人都可訂閱所有層級）
- ❌ 不接入金流（LINE Pay / Stripe 在 v1.1 之後）
- ❌ 不做使用者帳號系統（沿用 LINE userId 即可）
- ❌ 不做網頁 dashboard（v1 只有 LINE 推播 + email markdown）
- ❌ 不做產品 A 或 B 的內容（那是另外兩個 spec）

## Design（設計摘要）

### 一、依賴前置條件

**必須先完成 `tier1-data-completion` spec**——本 spec 的城市維度切片完全依賴：
- `location_prefectures` ≥85% 填充率
- `organizer_type ≥80%` 非 unknown 填充率

未達門檻 → 城市維度 60% 案例為 (null)，產品價值崩塌。

### 二、訂閱層級設計

| 層級 | 推播頻率 | 內容 | 篩選 | 價格 |
|---|---|---|---|---|
| **Free** | 每週日 19:00 JST | 未來 7 天活動清單 | 無 | ¥0 |
| **Pro**（v1.1+）| 每日 09:00 JST + 即時警示 | 未來 30 天 + 新主辦方訊號 + 價格異常 | 城市 / 類別 / 主辦類型 | ¥30k/月 |
| **Pro+**（v1.2+）| 每週 + 月度 markdown 報告 | Pro 全部 + 月度趨勢 PDF + 場地容量推估 | 多選 | ¥80k/月 |

**MVP（v1.0）只實作 Free 層級的升級**，但訊息內容已包含**未來付費版本的鉤子**（如「升級至 Pro 解鎖城市篩選」）。

### 三、新增維度設計

#### 維度 1：城市分群

```
東京圈：東京 + 千葉 + 神奈川 + 埼玉
關西圈：大阪 + 京都 + 兵庫 + 奈良
福岡圈：福岡 + 佐賀 + 熊本
其他：所有其他都道府縣
```

可用既有 `location_prefectures` 加 client-side mapping。

#### 維度 2：類別（既有 28 類）

直接用 `category` 欄位。LINE 訊息呈現時聚合為「展演藝術 / 學術論述 / 食品零售 / 影像紀錄 / 議題政策」5 大群組。

#### 維度 3：主辦方類型（migration 035 已就位）

按 `organizer_type` 分組：政府 / 半官方 / 文化機構 / 學術 / 商業品牌 / 民間獨立 / 媒體 / NGO。

### 四、「值得注意」訊號偵測

在每週訊息頂部加「📡 本週值得注意」：

| 訊號 | 偵測邏輯 |
|---|---|
| 新主辦方首次出現 | `organizer` 在過去 12 週未出現 |
| 城市首次活動 | 該 prefecture 在過去 8 週無活動 |
| 高頻主辦方爆發 | 同一 organizer 本週 ≥3 場 |
| 價格異常 | `price_amount > median(同類別過去 90 天) × 2` |
| 系列性活動 | 同一 organizer 本週連續多日 |

這 5 個訊號全部用既有資料計算，**無需新增欄位**。

### 五、訊息結構（LINE Flex Message）

```
📡 Tokyo Taiwan Radar — 機會雷達 第 N 週

🔍 本週值得注意（3 條訊號）
  • 新主辦方：xxx 首次在大阪舉辦
  • 福岡 8 週後首次台灣活動
  • 公會堂連 5 天台灣文學週

📅 本週 / 下週活動（共 12 場）
  ┌─ 東京圈（5）
  │  • [影像] xxx | 5/8 19:00
  │  • [學術] xxx | 5/9 14:00
  │  ...
  ├─ 關西圈（4）
  └─ 其他（3）

💼 升級 Pro 解鎖：每日推播、城市篩選、月度報告
```

### 六、檔案影響

| 檔案 | 異動 |
|---|---|
| `scraper/weekly_line_broadcast.py` | 重寫訊息生成邏輯，加維度分組 + 訊號偵測 |
| `scraper/opportunity_signals.py` | **新檔案**：5 種訊號的偵測函數 |
| `web/app/[locale]/subscribe/page.tsx` | **新頁面**：訂閱說明 + LINE 加好友 QR + 未來付費升級 CTA |
| `web/messages/{zh,en,ja}.json` | 加訂閱頁與 LINE 訊息翻譯 |

### 七、驗證指標

- **使用者訊號**：第一週至少 30 個 LINE 訂閱（既有用戶遷移 + 新增）
- **內容品質**：每週訊號偵測命中率 ≥80%（人工抽查 5 條）
- **變現訊號**：第 4 週至少 3 位用戶**主動詢問**升級或客製
- **資料健康**：城市維度切片 (null) 比例 <15%

## References

- `docs/specs/active/market-positioning-strategy/`（戰略上層）
- `docs/specs/active/tier1-data-completion/`（資料前置條件）
- `scraper/weekly_line_broadcast.py`（既有 baseline）
- `.github/skills/agents/architect/SKILL.md` § LINE Broadcast Query Guard（必須遵守的過濾規則）
