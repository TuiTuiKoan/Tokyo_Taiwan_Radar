---
title: Visual Design Styling Workflow
description: Tokyo Taiwan Radar 吉祥物、色票、背景、動態縮圖與品牌視覺語彙的設計工作流程
ms.date: 2026-05-18
ms.topic: how-to
keywords:
  - visual design
  - brand system
  - mascot
  - color palette
  - procedural thumbnails
  - bauhaus
estimated_reading_time: 12
---

## 用途與定位

Tokyo Taiwan Radar 的視覺風格由幾個互相支撐的系統組成：蠟蘋果雷達吉祥物、紙色與印刷紋理、紅綠品牌色票、程序化 Bauhaus 幾何、由資料生成的分類縮圖。這份 workflow 說明這些元素是怎麼被設計出來，以及日後如何延伸。

它補足 [UI Design Iteration Workflow](UI_DESIGN_WORKFLOW.md) 沒有涵蓋的「造型語言」部分。兩份文件的分工如下：

| 文件 | 回答的問題 | 適合任務 |
|---|---|---|
| [UI Design Iteration Workflow](UI_DESIGN_WORKFLOW.md) | 元件怎麼修、圖層怎麼排、如何驗證遮擋與互動 | bug fix、z-index、sticky、動畫速度、視覺 QA |
| 本文件 | 品牌長什麼樣、為什麼這樣選色、如何延伸圖像語彙 | mascot、palette、背景、縮圖、OG 圖、宣傳素材 |

目前它適合放在 `docs/`，作為人類可讀的工作文件。等流程穩定後，再把規則抽進 `.github/skills/agents/designer/SKILL.md` 或包成 Skill / Agent。

## 設計輸入

開始設計前，先把產品任務翻成視覺輸入。這能避免做出漂亮但無法延伸的裝飾。

| 輸入 | Tokyo Taiwan Radar 的答案 | 轉化成視覺 |
|---|---|---|
| 產品任務 | 聚合日本全國台灣相關活動 | 雷達、訊號、每日更新感 |
| 文化來源 | 台灣與日本之間的文化交換 | 蠟蘋果、紙色、印刷紋理、雙語友善字體 |
| 資料型態 | 大量活動、分類、公告、OG 圖 | 程序化縮圖與 hash-based variation |
| 使用情境 | 首頁掃描、活動列表、手機瀏覽、LINE 分享 | 高辨識圖像、穩定色票、低干擾背景 |

這套視覺不是一般文化活動站的白底卡片系統，而是一套「台日文化雷達」的品牌圖像語言。

## 品牌 DNA

新增視覺元素時，至少要對上下面兩個方向。若只對上一個，通常會顯得像孤立裝飾。

| 方向 | 說明 | 對應元素 |
|---|---|---|
| 台灣感 | 不靠國旗或地圖，而用生活物件建立記憶點 | 蠟蘋果、暖紅、紙色 |
| 雷達感 | 把搜尋、偵測、每日更新變成可見符號 | 天線、流光、漂浮幾何 |
| 印刷感 | 像小報、展覽海報、活動 DM | halftone、grid、stripe、wavy lines |
| 親和感 | 降低工具介面的冰冷感 | 圓潤字體、非對稱表情、溫暖深色 |
| 程序感 | 讓大量活動不靠人工製圖也有視覺辨識 | deterministic seed、motif variants |

一句話版本：用蠟蘋果吉祥物做情感入口，用 Bauhaus 幾何與程序化縮圖建立可擴充的活動雷達視覺系統。

## 吉祥物設計流程

### 角色選擇

吉祥物不是任意挑一個可愛角色，而是同時服務三個目的：

* 讓使用者快速感覺這是台灣相關產品
* 讓「雷達」這個抽象功能變成可見符號
* 讓活動列表這種資訊密度高的頁面有情感錨點

蠟蘋果適合這個產品，因為它有明確的台灣生活感，形狀簡單，紅色輪廓容易在小尺寸辨識，也能自然接上綠色天線。天線讓它不只是水果，而是「正在偵測活動」的角色。

### 造形規則

`MascotAvatar` 的造形由幾個可重複使用的規則組成：

| 部位 | 設計方法 | 目的 |
|---|---|---|
| 身體 | 一條 SVG path 畫出蠟蘋果外輪廓 | 小尺寸也能讀成單一清楚形狀 |
| 傾斜 | `mascot.tilt = 3` 度 | 讓角色有生命感，不像靜態 icon |
| 天線 | 一條從身體到右上角的曲線 | 連接吉祥物與雷達概念 |
| 天線端點 | 外圈、核心點、spark 三層 | 支援靜態辨識與動態發光 |
| 臉部 | 單眼加高光、簡化嘴部 | 保持親和但避免複雜表情搶內容 |
| 腮紅 | 左右不完全對稱的 pink ellipses | 增加手感，避免完美幾何過硬 |

這種設計適合 SVG，因為每個部位都能被 class 或 data attribute 控制，日後可在 hero、navbar、OG、社群圖中重用。

實作位置：

* `web/lib/design/MascotAvatar.tsx`
* `web/lib/design/patterns.tsx` 的 `waxMascot` symbol
* `web/lib/design/tokens.ts` 的 `mascot.tilt` 與 `mascot.viewBox`

### 吉祥物色彩

吉祥物本身使用固定色，不跟隨頁面主題任意改變：

| 色彩 | Hex | 用途 |
|---|---|---|
| mascot red | `#E84860` | 身體主色，品牌最高辨識色 |
| pink soft | `#FF7AA0` | 腮紅與柔和輔助色 |
| forest | `#1F5E2B` | 天線與雷達結構 |
| leaf | `#C4E86F` | 訊號 spark、天線亮點 |
| coal | `#1A1818` | 眼睛與表情暗部 |

不要把 mascot red 當成一般 danger red 使用。它是品牌主色，不是錯誤狀態色。

### 天線動態

天線動畫由三段組成：

1. 端點發光，提示雷達開始掃描
2. 短暫停頓，讓使用者看清起點
3. 光點沿天線 path 流向身體，形成收訊感

實作原則：

* 用 `data-antenna-flow="on"` 控制動畫，不用 inline animation
* 路徑移動用 SMIL `<animateMotion>`，因為它沿 SVG path 比 CSS transform 更準確
* 光圈大小用 SVG `<animate attributeName="r">`，避開 Safari 對 CSS `r` 動畫的不一致
* 帶 filter 的元素隱藏時同時設 `opacity: 0` 與 `visibility: hidden`，避免 WebKit filter 殘影
* 發光峰值避免純白，淺色紙背景上純白幾乎不可見，改用 `#C4E86F` 和黃綠漸層

## 色票設計流程

### 三層色票

色票不是一張扁平清單。專案分三層管理：

| 層級 | 來源 | 用途 |
|---|---|---|
| Primitive palette | `web/lib/design/tokens.ts` | 品牌原始色、OG 圖、SVG、非 CSS contexts |
| Semantic UI tokens | `web/app/globals.css` | 一般 UI、dark mode、表單、文字、邊框 |
| Generated palettes | `CategoryThumbnail.tsx` | 活動縮圖與分類圖像的程序化變化 |

這樣做可以避免兩種錯誤：把品牌裝飾色拿去做所有 UI 狀態，或把中性色系套到所有品牌圖像導致畫面失去個性。

### 品牌主色

主色從角色與產品任務推導，而不是從色輪平均挑選。

| 色名 | Hex | 設計角色 | 使用位置 |
|---|---|---|---|
| paper | `#FFFDF5` | 溫暖紙色，降低純白刺眼感 | 頁面底、卡片底、印刷感留白 |
| blush | `#FFF1EE` | 粉紅紙面，支撐柔和品牌氛圍 | 背景漸層、FilterBar、hero 區塊 |
| matcha | `#F7FFE8` | 淡綠 hover 與清爽背景 | icon hover、背景漸層第三色 |
| mascot red | `#E84860` | 品牌主色，蠟蘋果身體 | hero 強調、CTA、FloatingShapes |
| pink soft | `#FF7AA0` | 情緒與腮紅 | mascot cheek、輔助裝飾 |
| pink deep | `#D85862` | 較沉穩的粉紅紅 | gradient endpoint、link accent |
| forest | `#1F5E2B` | 天線、連結、台灣植物感 | link、天線、品牌綠 |
| leaf | `#C4E86F` | 訊號、亮點、動態能量 | antenna flash、FloatingShapes、badge |
| mocha | `#3A261F` | 溫暖深色，取代純黑 | 標題、icon、邊框、字色 |
| gold | `#C9A227` | 活動公告與文化質感 | CategoryThumbnail palette、公告卡 |

推薦比例：

| 類型 | 建議比例 | 例子 |
|---|---|---|
| 背景與留白 | 60% 到 70% | paper、blush、matcha |
| 文字與結構 | 15% 到 25% | mocha、forest、coal |
| 品牌強調 | 8% 到 12% | mascot red、pink deep |
| 高光與訊號 | 3% 到 6% | leaf、gold |

新增顏色前先問它要扮演什麼角色。若沒有角色，不要加入色票。

### dark mode

dark mode 不重做一套品牌，而是分離內容可讀性與裝飾固定色。

* 一般 UI 用 semantic token，例如 `bg-surface`、`text-fg`、`border-line`
* 標題中硬寫的 `#3A261F` 在 dark mode 轉成 `var(--color-text)`
* 品牌固定圖像可以維持原色，例如吉祥物、公告卡 light-preserved zone
* 表單控制必須用 token 顯式設定文字與背景，避免 mobile dark mode 變成黑底黑字

新增視覺色時，同步檢查 `:root` 與 `:root.dark`。若它是純裝飾固定色，要明確註記例外。

## 字體系統

字體和色票一樣，按用途分層：

| Token | Font | 用途 |
|---|---|---|
| `--font-display` | Zen Maru Gothic | hero、h1 到 h3、卡片標題、OG title |
| `--font-body` | Noto Sans JP | UI、列表、FilterBar、多語內容 |
| `--font-mono` | JetBrains Mono | 日期、ID、admin table、時間戳 |
| `--font-accent` | Bagel Fat One | retro 標籤、slide number、少量裝飾文字 |

選 Zen Maru Gothic 是因為它有圓潤感，能接住吉祥物與小報風格；Noto Sans JP 承擔大量日文與漢字 UI，避免 display font 在長文中降低可讀性。

實作位置：`web/lib/design/fonts.ts`。

## 背景與紋理

### 背景層

背景由三層構成：

| 層 | 元件 / 技術 | 視覺作用 |
|---|---|---|
| 紙色漸層 | `SiteBackground` fixed `-z-30` | 提供溫暖紙面與淡粉綠氣氛 |
| 格線 | `gridPink` SVG pattern `-z-20` | 建立雷達、地圖、印刷版面感 |
| FloatingShapes | `FloatingShapes` | 讓頁面像一個持續掃描中的視覺場 |

`SiteBackground` 的 light gradient 是：

```text
#FFFDF5 → #FFF1EE → #F7FFE8
```

這個漸層提供三個效果：

* 避免大量活動列表看起來像 generic dashboard
* 給吉祥物和縮圖一個暖色舞台
* 在三語文字很多的頁面保持柔和，不刺激眼睛

### 紋理來源

`DesignDefs` 提供可重用 SVG patterns：

| Pattern | 視覺語氣 | 常見用途 |
|---|---|---|
| `halftonePink` | 印刷、pop、活動感 | hero、framed mascot、卡片裝飾 |
| `halftoneGreen` | 自然、雷達、訊號 | hero、吉祥物框、輔助圖形 |
| `wavyLinesPink` | 展覽海報、手感 | highlight card |
| `wavyLinesGreen` | 流動、掃描 | highlight card |
| `diagStripes` | retro poster | callout、裝飾帶 |
| `gridPink` | 雷達、版面系統 | 全站背景 |

新增背景紋理時，先放進 `DesignDefs`，再由元件引用。不要在各元件內重複定義相同 pattern。

## FloatingShapes 設計流程

FloatingShapes 是品牌氣氛層，不是內容。它用 Bauhaus 幾何形狀模擬雷達視野中的訊號、活動碎片與海報元素。

目前有兩種 variant：

| Variant | 使用位置 | 視覺角色 |
|---|---|---|
| full | 首頁與設計頁 | 大型背景動態，建立第一印象 |
| subtle | 內頁 | 低干擾前景紋理，讓內頁延續品牌感 |

生成規則：

* 5 個尺寸 tier，每 tier 2 個 floater，最多 10 個同時在畫面
* 9 種 shape：triangle、pentagon、hexagon、star、sector、half circle、circle、diamond 等
* 9 種 fill：solid、outline、dashed、dots、stripes、hatch、grid
* 2 個主色：`#E84860` 與 `#C4E86F`
* 8 種 drift direction，從不同邊緣穿越畫面
* 每次動畫週期結束會重抽 floater，避免畫面固定重複

設計限制比隨機更重要：

* 同時只保留有限數量 floaters，避免畫面髒亂
* solid red 只允許在小尺寸 tier，避免大紅塊壓迫內容
* 至少保留一些 solid，避免全是線稿而沒有視覺重心
* 內頁 subtle variant 只使用較小 tier，並降低 opacity
* mobile 速度跟 viewport scale，避免小螢幕動畫慢到像停住

## 動態分類縮圖

活動資料量大，而且很多活動沒有穩定圖片。若每張卡片都用空白 placeholder，列表會失去掃描性；若每張都用手工圖，維護成本太高。所以 `CategoryThumbnail` 使用程序化 SVG：同一活動穩定、不同活動有變化、同一分類仍能辨識。

### 生成邏輯

縮圖由四層生成：

| 層 | 來源 | 功能 |
|---|---|---|
| seed | `hashString(id)` + `mulberry32` | 同一活動永遠得到同一張圖 |
| palette | `PALETTES` + primary category hash | 同分類有一致傾向，但不完全相同 |
| background pattern | dots、stripes、grid、wavy、checker | 補足印刷質地 |
| semantic motif | `getSemanticSymbol(category, variant)` | 讓使用者看得出活動類型 |

這種設計的關鍵是可預測的隨機。不能每次 render 都變，也不能所有卡片長一樣。

### Palette 設計

`CategoryThumbnail` 使用 8 組三色 palette：

```text
bg      fg       accent
#FFE9DD #E84860 #1F5E2B
#E8F6D6 #1F5E2B #E84860
#FFF1C2 #C9A227 #3A261F
#FFD9D0 #F47A86 #3A261F
#E0EBFF #3B5BA9 #E84860
#FFE0EF #D85862 #1F5E2B
#F0E6FF #7B4FB8 #C9A227
#D6F0EA #2C8A7A #E84860
```

設計重點：

* 每組都有背景、前景、accent，不只是一個主色
* 多數組合保留紅綠品牌記憶，但加入藍、紫、金、青綠避免單調
* 背景多為低飽和淺色，確保前景 motif 讀得出來
* accent 常回到 forest、mascot red、mocha 或 gold，讓整體仍屬於同一品牌

### Layering 規則

`CategoryThumbnail` 內部視覺順序固定：

```text
background color
→ background pattern, opacity 0.45
→ organic collage base
→ semantic symbol shadow layer
→ semantic symbol foreground layer
```

shadow layer 用背景色和 mocha 形成錯位感，foreground layer 用 palette 的 fg / accent。這讓 SVG 看起來像印刷套色，而不是單薄 icon。

實作位置：

* `web/lib/design/CategoryThumbnail.tsx`
* `web/lib/design/organicMotifs.tsx`

## Organic Motifs 設計方法

每個 category 有 5 個 semantic symbol 變體。設計時先找「分類最容易被辨識的物件」，再把物件簡化成 100×100 viewBox 內的幾何符號。

設計步驟：

1. 列出 category 的 6 到 10 個候選意象
2. 排除太抽象、太細節、太依賴文字的意象
3. 保留能在 100px 內一眼辨識的物件
4. 每個變體控制在少量 path / shape，不做插畫式細節
5. 用 `c` 作主色、`a` 作 accent，必要時用 mocha 或 white 補對比
6. 到 `/debug/motifs` 檢查 5 個變體是否彼此不同

範例：`study_abroad` 的 5 個變體是 airplane、globe、suitcase、passport、graduation cap。這種組合比單一「地球」更有延展性，列表中連續出現同類活動時也不會單調。

通過標準：

* 去掉顏色仍能在 2 秒內辨識
* 100px 大小下不糊成一團
* 5 個變體不是同一物件的微小角度差
* 圖像與 category 有直接語義關係
* 不依賴 emoji、文字或外部圖片

## 公告與卡片的印刷感

公告卡使用金色漸層、左側方形圖與 hash-based pattern swatch。它的角色比較接近展覽告示或活動快訊，所以刻意保留 light-themed 材質，即使在 dark mode 也用 `data-preserve-theme="light"` 保持黃色紙面。

設計方法：

* 用 `#FFF6D1 → #FFE9A8` 做公告紙感，不混入過多粉紅
* 左側圖片固定方形，讓橫向 strip 有節奏
* 右上角 pattern swatch 由 announcement id hash 決定
* date kicker 使用 mono 字體，像印刷品上的小標籤
* dark mode 中公告卡保留 light palette，視覺上像一張貼在暗背景上的紙

實作位置：`web/components/AnnouncementCard.tsx`。

## Hero 與品牌入口

首頁 hero 用 mascot 取代一般 marketing hero 圖，原因是這個產品不是大型 SaaS，也不是媒體首頁，而是每天掃描台日文化活動的工具。角色化入口能讓小型文化專案更容易被記住。

Hero 組成：

* 大尺寸 Lianbu mascot
* 天線流光動畫，暗示 radar / live update
* 小型 `font-accent` label，形成 retro print 標籤
* `font-display` 多行 headline，讓中日文有柔軟但清楚的節奏
* LINE CTA 使用 LINE green，這是唯一固定外部品牌色例外

設計重點：

* Hero 不用泛用插圖，也不用抽象 gradient orb
* 吉祥物必須是第一視覺訊號
* 動畫集中在天線，避免整個 hero 動來動去
* headline 不用過大，因為第一屏還要讓使用者進入搜尋與活動列表

## OG 圖與外部分享延伸

OG 圖延伸同一套語彙，但有不同限制：Satori 不支援 Tailwind class，所以必須使用 inline style 與可解析的 token。OG 圖不應另開一套視覺風格，否則社群分享與站內體驗會斷裂。

延伸規則：

* 使用 `tokens.ts` 或 Satori-friendly flattened token
* 使用同一組 palette 與 motif 語彙
* 不使用 emoji 作主視覺，避免 Satori 失敗
* event OG 與 category OG 都應從 `organicMotifs.tsx` 取得圖像語義
* 變更 `CategoryThumbnail` palette 時要檢查 OG 是否仍一致

## 實作決策樹

### 新增視覺資產

| 需求 | 優先做法 |
|---|---|
| 站內品牌角色 | 擴充 `MascotAvatar` 或 `patterns.tsx` symbol |
| 分類或活動縮圖 | 擴充 `organicMotifs.tsx` 與 `CategoryThumbnail` |
| 背景材質 | 擴充 `DesignDefs` pattern 或 `SiteBackground` |
| 動態背景 | 擴充 `FloatingShapes` shape / fill / tier |
| 外部分享圖 | 從 tokens 與 motifs 產生，不另做視覺語言 |

### 選新顏色

新顏色必須先有角色。不要因為畫面有點空就新增色票。

決策流程：

1. 能否用既有 `paper / blush / matcha / mascot red / forest / leaf / mocha / gold`
2. 若不能，它是在補語義狀態、品牌延伸，還是分類 palette
3. 是否需要 light 與 dark token
4. 是否會出現在 OG / Satori 等非 CSS 環境
5. 是否要同步 `tokens.ts`、`globals.css`、Designer SKILL

### 新增 pattern

優先考慮印刷與幾何語彙：

* halftone dots
* diagonal stripes
* grid
* wavy lines
* chevron
* checker
* hatch

避免新增照片感、bokeh、gradient blob、過度裝飾性背景。這個品牌的質地來自「紙 + 印刷 + 幾何」，不是光效堆疊。

## 可交接任務模板

把視覺風格任務交給設計者或 AI agent 時，可以使用這個格式：

```text
目標：為 [頁面 / 元件 / 分類 / 宣傳素材] 設計符合 Tokyo Taiwan Radar 的視覺延伸。

品牌語彙：
* 蠟蘋果吉祥物 Lianbu
* paper / blush / matcha 背景
* mascot red / forest / leaf 品牌三角
* mocha 作為溫暖深色
* Bauhaus / retro print：halftone、grid、stripe、幾何形
* radar：天線、流光、漂浮掃描感

限制：
* 不使用 stock-like 插圖或泛用 gradient blob
* 不新增 UI kit 或重型動畫套件
* 圖像要能在 mobile 與 dark mode 中辨識
* 新增 user-facing copy 時三語同步
* 新增 category 時要有 5 個 organic motif 變體

交付：
* 說明視覺概念與色票
* 指出實作檔案
* 提供 light / dark / mobile 驗證方式
* 若是縮圖或 OG，說明 deterministic seed 與 motif 規則
```

## 檢查清單

完成 styling 變更前檢查：

* 視覺概念至少對上品牌 DNA 中的兩個詞
* 新色有明確角色，且不只是為了變化而加入
* 一般 UI 使用 semantic token，品牌圖像才使用 primitive 色
* dark mode 沒有低對比文字或表單不可讀問題
* 裝飾層不阻擋點擊，並且有 `pointer-events-none`
* 程序化圖像同一 seed 穩定，不會每次 render 隨機變化
* SVG pattern id 不會在同頁多次渲染時衝突
* mobile 下動畫速度、尺寸與出現位置自然
* OG 或 Satori 圖不依賴 Tailwind class
* 重要規則已回寫到 `history.md`、`SKILL.md` 或 docs

## 何時寫回 Skill 或 Agent

寫回 Designer Skill 的條件：

* 某條規則已被 2 到 3 次實作驗證
* 忘記該規則會造成 build 不會報錯但視覺明顯退化
* 規則能用一句清楚的 guard 表達

適合寫回 Skill 的例子：

* `CategoryThumbnail` palette 是分類縮圖與 OG 圖的 source of truth
* 新增 category 必須同時新增 5 個 `organicMotifs.tsx` 變體
* 裝飾動畫只能使用品牌紅與 leaf，且 large solid red 受限制
* 吉祥物天線動畫不可使用純白作為主要峰值色

適合做成 Agent 的情境：

* 需要先提出 2 到 3 個視覺方向，再由人選擇
* 需要 Designer、Engineer、Tester 分工
* 需要透過截圖或 browser tool 做多 viewport 實測

## 最小完成定義

一次視覺風格設計完成時，至少應留下：

* 視覺概念：它從哪個品牌語彙延伸
* 色彩選擇：用了哪些既有色票，是否新增 token
* 形狀語彙：使用 mascot、geometry、pattern、motif 中哪一類
* 響應式檢查：小尺寸與 mobile 是否仍成立
* dark mode 檢查：不是只在 light mode 好看
* 實作位置：相關元件、token、pattern、motif、OG route
* 可重複規則：需要寫回 history、Skill 或本文件的教訓

好的 Tokyo Taiwan Radar 視覺延伸應該像同一套印刷物與雷達介面長出來的東西：有台灣感，但不靠符號堆砌；有動態感，但不妨礙找活動；有角色，但不犧牲資訊密度。
