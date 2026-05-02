---
title: Translation Pipeline — 翻譯與標注完整流程
description: 從爬蟲原始文本到三語前端顯示的翻譯流程，涵蓋 GPT 標注、eiga.com 片名查詢、Wikipedia 人名查詢、DeepL 回退
ms.date: 2026-05-02
---

## 總覽

一個事件從爬蟲抓取到前端三語顯示，最多經過 **六層翻譯處理**，涉及 **14 個翻譯欄位**。

```text
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 1 — 爬蟲層（Scraper）                                         │
│                                                                      │
│  sources/*.py → raw_title + raw_description（永不覆寫）              │
│  cinema scrapers → movie_title_lookup.py → name_zh / name_en        │
│  → DB upsert（annotation_status = 'pending'）                       │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 2 — DeepL 回退（Translator，可選）                             │
│                                                                      │
│  translator.py → fill_translations() → 只補空欄位                    │
│  ZH-HANT（繁體中文）/ EN-US / JA                                     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 3 — GPT-4o-mini 標注（Annotator，核心）                       │
│                                                                      │
│  annotator.py → _annotate_one() → 全部 14 翻譯欄位                  │
│  + category + dates + pricing + sub-events                           │
│  → annotation_status = 'annotated'                                   │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 4 — 官方片名補全（Movie Title Enrichment）                     │
│                                                                      │
│  annotator.py --enrich-movie-titles                                  │
│  → eiga.com 查到 → 覆寫 name_zh / name_en + description 括號引用    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 5 — 人名修正（Person Name Enrichment）                        │
│                                                                      │
│  annotator.py --enrich-person-names                                  │
│  → eiga.com + Wikipedia 查 cast/crew                                 │
│  → GPT-4o-mini 修正 desc_zh 中的錯誤音譯人名                         │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 6 — 前端 Fallback Chain                                       │
│                                                                      │
│  getEventName(event, locale)                                         │
│  → locale → ja → zh → en → "（未命名）"                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 翻譯欄位清單

一個事件最多有 **14 個翻譯欄位**：

| 分組 | 欄位 | 語言數 | 來源 |
|------|------|--------|------|
| 名稱 | `name_ja`, `name_zh`, `name_en` | 3 | 爬蟲 + GPT |
| 描述 | `description_ja`, `description_zh`, `description_en` | 3 | GPT |
| 地點名稱 | `location_name`（日文）, `location_name_zh`, `location_name_en` | 2 翻譯 | GPT |
| 地址 | `location_address`（日文）, `location_address_zh`, `location_address_en` | 2 翻譯 | GPT |
| 營業時間 | `business_hours`（日文）, `business_hours_zh`, `business_hours_en` | 2 翻譯 | GPT |
| 收錄理由 | `selection_reason`（JSON `{ja, zh, en}`） | 3（JSON 內）| GPT |

**地點/地址/營業時間的多語欄位**由 migration 010 新增，不在 `Event` dataclass 中，由 annotator 直接寫入 DB。

---

## CI/CD 執行順序

GitHub Actions 每日 09:00 JST 依序執行（`.github/workflows/scraper.yml`）：

| 步驟 | 指令 | 功能 |
|------|------|------|
| 1 | `python main.py` | 爬取全部來源 + upsert + 標注 pending 事件 |
| 2 | `python merger.py` | 跨來源去重（相似度 > 85% + 同日期） |
| 3 | `python annotator.py --fix-reviewed` | 補全 reviewed 事件缺失的翻譯欄位 |
| 4 | `python annotator.py --enrich-movie-titles` | eiga.com 官方片名覆寫 |
| 5 | `python annotator.py --enrich-person-names` | eiga.com + Wikipedia 人名修正 |
| 6 | `python summarize_run.py` | 生成 LINE 推播摘要 |

---

## Layer 1 — 爬蟲層

### 核心檔案

| 檔案 | 用途 |
|------|------|
| `sources/base.py` | `Event` dataclass — 定義全部翻譯欄位 |
| `sources/*.py` | 各來源爬蟲，`scrape() → list[Event]` |
| `movie_title_lookup.py` | cinema scrapers 呼叫 eiga.com 查官方片名 |
| `database.py` | `upsert_events()` → ON CONFLICT source_name,source_id |

### 爬蟲寫入的欄位

```python
Event(
    raw_title="上映イベント「月老」",           # 原始標題（永不覆寫）
    raw_description="台灣電影「月老」...",       # 原始描述（永不覆寫）
    name_ja="赤い糸 輪廻のひみつ",              # 日文名（爬蟲提取）
    name_zh="月老",                             # 中文名（cinema → eiga.com lookup）
    name_en="Till We Meet Again",               # 英文名（cinema → eiga.com lookup）
    original_language="ja",                     # 原始語言
)
```

### name_ja_locked 機制

migration 034 新增 `name_ja_locked BOOLEAN DEFAULT FALSE`。當爬蟲設定為 `True` 時，annotator 保留 `name_ja` 不覆寫（翻譯欄位仍正常生成）。

---

## Layer 2 — DeepL 回退

### 核心檔案

| 檔案 | 函式 | 用途 |
|------|------|------|
| `translator.py` | `fill_translations(event)` | 補全空欄位 |

### 語言對照

| 系統語碼 | DeepL 語碼 |
|----------|-----------|
| `ja` | `JA` |
| `zh` | `ZH-HANT`（繁體中文） |
| `en` | `EN-US` |

### 策略

```python
def fill_translations(event):
    for lang in ["ja", "zh", "en"]:
        if lang == event.original_language:
            continue
        # 只補空欄位，不覆寫已有值
        if not getattr(event, f"name_{lang}"):
            translated = _translate(source_name, event.original_language, lang)
            if translated:
                setattr(event, f"name_{lang}", translated)
```

**定位**：DeepL 是輔助回退，主要翻譯引擎是 GPT-4o-mini（Layer 3）。DeepL 品質較高但無法提取結構化欄位。

---

## Layer 3 — GPT-4o-mini 標注（核心）

### 核心檔案

| 檔案 | 函式 | 用途 |
|------|------|------|
| `annotator.py` | `annotate_pending_events()` | 主要排程函式 |
| `annotator.py` | `_annotate_one()` | 單事件 GPT 呼叫 |
| `category_feedback.py` | `load_corrections()` | 載入 admin 類別修正 |
| `category_feedback.py` | `build_feedback_prompt()` | 生成 few-shot 範例 |

### Annotation Status 生命週期

```text
pending ──(GPT 標注)──→ annotated ──(admin 審核)──→ reviewed
   ↑                       ↓                          │
   └──(--all 重跑)─────────┘                          │
   └──(--fix-reviewed)─────────(只補翻譯欄位)─────────┘
```

| 狀態 | 說明 | 可被覆寫？ |
|------|------|-----------|
| `pending` | 等待標注 | 是 |
| `annotated` | AI 已處理 | 是（`--all` 可重跑） |
| `reviewed` | 人工確認 | 否（僅 `--fix-reviewed` 補翻譯） |
| `error` | 標注失敗 | 是 |

### GPT System Prompt 架構

`SYSTEM_PROMPT` 包含以下規則：

1. **語言規則（CRITICAL）**：ALL `*_zh` fields MUST use 繁體中文，NEVER 简体字
2. **日期提取**：從全文（標題 + 本文 + 頁尾）提取，推斷年份，single-day 時 `end_date = start_date`
3. **名稱寫法**：`name_ja` 必須自描述性（10-40 字），不可只寫「上映会」
4. **地址規則**：場館名需補完實際地址（含丁目/番地/郵遞區號）
5. **子事件拆分**：多場次 / 多地點 → `sub_events[]`
6. **分類規則**：22 個 category + 關鍵字注入（lecture/geopolitics/history）
7. **收錄理由**：三語說明為何與台灣相關

### GPT 呼叫參數

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT + feedback_prompt},
        {"role": "user",   "content": f"Raw Title: {raw_title}\n\nRaw Description:\n{raw_description}"},
    ],
    response_format={"type": "json_object"},
    temperature=0.1,
    max_tokens=4000,  # 重試時提高至 6000
)
```

### GPT JSON 回應結構

```json
{
  "name_ja": "...",
  "name_zh": "...（繁體中文）",
  "name_en": "...",
  "description_ja": "2-4 句",
  "description_zh": "2-4 句（繁體中文）",
  "description_en": "2-4 sentences",
  "category": ["movie", "lecture"],
  "start_date": "ISO-8601",
  "end_date": "ISO-8601",
  "location_name": "...",
  "location_name_zh": "...",
  "location_name_en": "...",
  "location_address": "東京都渋谷区...",
  "location_address_zh": "東京都澀谷區...",
  "location_address_en": "Shibuya-ku, Tokyo...",
  "business_hours": "...",
  "business_hours_zh": "...",
  "business_hours_en": "...",
  "is_paid": true,
  "price_info": "一般 1,500円",
  "selection_reason": {
    "ja": "台灣映画の上映イベント",
    "zh": "台灣電影上映活動",
    "en": "Taiwan film screening event"
  },
  "sub_events": [...]
}
```

### 簡繁轉換安全網

GPT 偶爾在 `location_*_zh` 中輸出简体字。`_loc_zh()` 函式自動轉換：

```python
_LOC_ZH_SIMP_TO_TRAD = str.maketrans({
    "东": "東", "区": "區", "内": "內", "园": "園",
    "来": "來", "长": "長", "进": "進", "实": "實",
    "诺": "諾", "厅": "廳", "络": "絡", "设": "設",
    "联": "聯", "馆": "館", "门": "門", "发": "發",
    "会": "會",
})
```

### 類別關鍵字注入

`_inject_keyword_categories()` 在 GPT 分類結果後補充遺漏的類別：

| 規則 | 關鍵字範例 | 來源 |
|------|-----------|------|
| `lecture` | 座談、講座、トークイベント | 29 筆 admin 修正 |
| `geopolitics` | 危機、海峡、独立、民主化 | 18 筆 admin 修正 |
| `history` | 戦没、植民地、統治、秘録 | 16 筆 admin 修正 |

### 費用追蹤

每次標注完成後寫入 `scraper_runs`：

```python
# GPT-4o-mini：$0.15 / 1M input tokens, $0.60 / 1M output tokens
cost = (total_tokens_in * 0.15 + total_tokens_out * 0.60) / 1_000_000
```

### CLI 參數

```bash
python annotator.py                          # 標注所有 pending 事件
python annotator.py --all                    # 重跑所有事件（排除 reviewed）
python annotator.py --fix-translations       # 補全缺少翻譯的 active 事件
python annotator.py --fix-reviewed           # 補全 reviewed 事件缺少的翻譯
python annotator.py --id <uuid>              # 標注單一事件
python annotator.py --enrich-movie-titles    # eiga.com 片名補全
python annotator.py --enrich-person-names    # 人名修正
```

---

## Layer 4 — 官方片名補全

### 核心檔案

| 檔案 | 函式 | 用途 |
|------|------|------|
| `movie_title_lookup.py` | `lookup_movie_titles(name_ja)` | eiga.com 查官方片名 |
| `annotator.py` | `enrich_movie_titles()` | 批量覆寫 + description 連動修正 |

### 查詢策略

```text
1. 搜尋 eiga.com/search/{title}/movie/
2. 取第一個 /movie/{id}/ 結果
3. 從 p.data 解析「原題または英題：月老 Till We Meet Again」
4. 拆分 CJK 部分 → name_zh，ASCII 部分 → name_en
5. In-memory cache 避免重複查詢
```

### 覆寫規則

- **範圍**：category 含 `movie`，排除 `eiga_com` 來源 + `reviewed` 狀態
- **片名來源區分**：
  - 新聞來源（google_news_rss / prtimes / nhk_rss）：從 `raw_title` 的 `「」`/`『』` 提取片名搜尋
  - 其他來源：使用 `name_ja`（fallback: `raw_title`）
- **覆寫行為**：查到就覆寫 `name_zh` / `name_en`，即使已有 GPT 翻譯
- **Description 連動**：`_replace_title_in_desc()` 替換 description 中括號引用的舊片名

### 括號引用替換

`_replace_title_in_desc()` 僅在辨識到的括號對內替換，避免誤改：

```python
_TITLE_BRACKETS = [
    ("《", "》"),   # 中文雙角
    ("「", "」"),   # 日文角
    ("『", "』"),   # 日文白角
    ("\u2018", "\u2019"),  # 英文單引號
    ("\u201c", "\u201d"),  # 英文雙引號
    ("'", "'"),    # ASCII 直引號
    ('"', '"'),    # ASCII 雙引號
]
```

---

## Layer 5 — 人名修正

### 核心檔案

| 檔案 | 函式 | 用途 |
|------|------|------|
| `person_name_lookup.py` | `lookup_person_names(name_ja)` | eiga.com + Wikipedia 查人名 |
| `annotator.py` | `enrich_person_names()` | 批量修正 desc_zh / desc_en |
| `annotator.py` | `_fix_person_names_gpt()` | GPT-4o-mini 修正音譯人名 |

### 問題背景

GPT 將日文片假名人名音譯為中文時經常出錯（特別是筆名/藝名）：

| 日文 | GPT 音譯（錯） | 正確中文名 |
|------|---------------|-----------|
| ギデンズ・コー | 紀德恩 | 九把刀 |
| クー・チェンドン | 柯震東 | 柯震東 |

### 三層查詢鏈

```text
1. eiga.com 電影頁 → 提取 cast/crew 清單
   - 角色名前綴去除：「孝綸（シャオルン）クー・チェンドン」→「クー・チェンドン」
   - 取得 (role, katakana_name, person_url)

2. eiga.com 人物頁 → 英文名 + 出身國
   - 解析「英語表記：Giddens Ko」「出身：台湾」

3. zh.wikipedia 搜尋 → 中文名
   - 搜尋「{英文名} {出身國}」（消歧義）
   - 優先：snippet 含人物關鍵字（演員/導演/歌手/出生）且標題 2-4 字
   - 回退：ja.wikipedia 搜假名 → 若文章標題為純 CJK → 使用或取 zh interlanguage link
```

### desc_zh 修正（GPT 驅動）

錯誤人名是 GPT 音譯產物，無法字串比對找到。必須用 GPT 辨識並替換：

```python
_PERSON_FIX_PROMPT = """你是翻譯校對專家。以下中文描述中的人名可能是從日文片假名
音譯而來的錯誤翻譯。請根據正確名單替換為正確的中文名。

規則：
- 只修改人名，不改動其他內容
- 已正確的人名不要改
- 找不到需修改的人名就原樣返回
- 只輸出修正後的描述

正確名單：
{mapping}

描述：
{desc}"""
```

### desc_en 修正（直接替換）

英文名在 desc_en 中通常可直接字串比對（假名外洩到英文時替換為英文名）。

### Caching

| 快取 | 鍵 | 值 |
|------|------|------|
| `_movie_cache` | 電影日文名 | `dict[假名人名, PersonInfo]` |
| `_person_cache` | eiga.com person URL | `(name_en, name_zh)` |

---

## Layer 6 — 前端 Fallback Chain

### 核心檔案

| 檔案 | 函式 | 用途 |
|------|------|------|
| `web/lib/types.ts` | `getEventName()` | 名稱 fallback |
| `web/lib/types.ts` | `getEventDescription()` | 描述 fallback |
| `web/lib/types.ts` | `getEventLocationName()` | 地點名 fallback |
| `web/lib/types.ts` | `getEventLocationAddress()` | 地址 fallback |
| `web/lib/types.ts` | `getEventBusinessHours()` | 營業時間 fallback |

### 名稱/描述 Fallback

```text
locale → ja → zh → en → "（未命名）"
```

```typescript
function getEventName(event: Event, locale: Locale): string {
  return event[`name_${locale}`] || event.name_ja
      || event.name_zh || event.name_en || "（未命名）";
}
```

### 地點欄位 Fallback

地點/地址/營業時間的策略不同：`locale-specific → 日文原文`

```typescript
function getEventLocationName(event: Event, locale: Locale): string | null {
  if (locale === "zh") return event.location_name_zh || event.location_name;
  if (locale === "en") return event.location_name_en || event.location_name;
  return event.location_name;  // ja: 直接用原文
}
```

---

## 子事件翻譯

### 拆分時機

GPT 在以下情況拆分子事件：

1. **多場次**：不同日期的放映/講座（如影展的個別場次）
2. **多地點**：3+ 個不同城市的場地（如巡迴活動）

### 子事件欄位

每個子事件擁有完整的三語翻譯：

```json
{
  "name_ja": "第1回上映「月老」",
  "name_zh": "第一場放映《月老》",
  "name_en": "Screening 1: Till We Meet Again",
  "description_ja": "...",
  "description_zh": "...",
  "description_en": "...",
  "start_date": "2026-05-08T19:00:00",
  "end_date": "2026-05-08T21:00:00"
}
```

### 子事件 source_id

```python
source_id = f"{parent_source_id}_sub{j+1}"  # e.g. "shin_bungeiza_123_sub1"
```

### 地點繼承

子事件若未指定 `location_*` 欄位，繼承父事件的地點資訊。

### Prefecture 聚合

若 2+ 子事件在不同都道府縣，annotator 聚合到父事件：

```python
parent.location_prefectures = sorted(["東京", "大阪", "京都"])
```

---

## Admin 人工回饋循環

### 類別修正回饋

```text
admin UI → category_corrections 表 → load_corrections()
→ build_feedback_prompt() → 附加到 SYSTEM_PROMPT → few-shot 學習
```

`build_feedback_prompt()` 將最近的 admin 修正轉為 GPT few-shot 範例，提升後續標注的分類準確度。

### 人工類別覆寫

```python
human_category_map = {
    event_id: corrected_category
    for r in sb.table("category_corrections").select(...).execute().data
}
# 若 event_id 在 map 中 → 直接使用 admin 指定的 category
```

---

## 相關文件

* [系統架構總覽](ARCHITECTURE.md)
* [爬蟲來源研究到上線完整工作流](SCRAPER_PIPELINE.md)
* [Merger 跨來源去重工作流](MERGER_WORKFLOW.md)
* Engineer SKILL.md — `Movie Title Lookup Pattern` / `Person Name Lookup Pattern`
