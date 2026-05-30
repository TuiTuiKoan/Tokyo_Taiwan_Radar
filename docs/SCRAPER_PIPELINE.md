---
title: Scraper Pipeline — 來源研究到爬蟲上線
description: 從來源發現、研究評估、自動代碼生成，到手動整合與 CI 部署的完整工作流
ms.date: 2026-05-31
---

## 總覽

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer A — 來源發現（Source Discovery）                                       │
│                                                                              │
│  researcher.py  ←── GitHub Issues / 人工輸入                                  │
│  discovery_accounts.py  ←── note.com / Peatix 平台探索                        │
│                                                                              │
│  → research_sources DB（status: candidate）                                  │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer B Phase 1 — 自動研究評估（Auto Research）                              │
│                                                                              │
│  auto_research.py  ←── Playwright + GPT-4o                                  │
│    score ≥ 0.70 + easy    → researched（自動進入 Phase 2）                    │
│    score ≥ 0.70 + medium  → recommended + GitHub Issue（人工審查）            │
│    score < 0.30           → not-viable                                       │
│    0.30–0.70              → unchanged（人工判斷）                             │
│                                                                              │
│  → research_sources DB（status 更新）                                        │
└──────────────────────────────────────────────────────────────────────────────┘
                              │ status=researched + feasibility=easy
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer B Phase 2 — 自動代碼生成（Auto Generate）                              │
│                                                                              │
│  generate.py  ←── Playwright + GPT-4o                                       │
│    1. 抓取樣本 HTML（50,000 chars truncated）                                 │
│    2. GPT-4o 輸出 JSON spec（CSS selectors + date_regex + source_name...）   │
│    3. spec_to_code.py → render() 生成 Python 爬蟲                            │
│    4. ast_check() 安全驗證（禁止 subprocess/eval/requests）                  │
│    5. sandbox dry-run（subprocess，stripped env，timeout 300s）               │
│    6. 產出 runs/<source_id>/{spec.json, generated.py, meta.json}             │
│                                                                              │
│  → auto_scraper_status: success | sandbox-failed | budget-exceeded |         │
│    llm-error | spec-invalid                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
                              │ status=success
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer C — 人工整合（Manual Integration）                                     │
│                                                                              │
│  Scraper Expert Agent / 人工：                                                │
│    1. 複製 runs/<source_id>/generated.py → sources/<name>.py                 │
│    2. 在 main.py SCRAPERS 列表新增（同一 commit 必須含兩個檔案）               │
│    3. 本機 dry-run 驗證：python main.py --dry-run --source <name>            │
│    4. git commit + push → CI 自動生效                                        │
│                                                                              │
│  → research_sources.status: implemented                                      │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer D — 每日 CI 爬取                                                       │
│                                                                              │
│  scraper.yml 09:00 JST → main.py → events DB → annotator → LINE 通知        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## research_sources 狀態機

```text
(新來源) ──→ candidate
                │
         auto_research.py（Layer B Phase 1）
                │
    ┌───────────┼──────────────┐
    │           │              │
    ▼           ▼              ▼
researched  recommended    not-viable
(easy)      (medium, GH Issue)
    │
    │ generate.py（Layer B Phase 2）
    │
    └──→ auto_scraper_status: success
              │
              │ 人工整合（Layer C）
              │
              └──→ status: implemented
```

| status 欄位 | 含義 | 下一步 |
|------------|------|--------|
| `candidate` | 已收集 URL，等待評估 | 自動或人工評估 |
| `researched` | 評分 ≥ 0.70 + easy，待代碼生成 | auto-generate.yml |
| `recommended` | 評分 ≥ 0.70 + medium，待人工決策 | GitHub Issue 審查 |
| `not-viable` | 評分 < 0.30 或技術不可行 | 歸檔 |
| `implemented` | 已整合進 SCRAPERS，定期執行中 | 無 |

| auto_scraper_status 欄位 | 含義 |
|--------------------------|------|
| `NULL` | 尚未嘗試生成 |
| `success` | sandbox 通過，artifacts 可用 |
| `sandbox-failed` | CSS selector 無效或爬取 0 事件 |
| `budget-exceeded` | 超過 $1.50 預算上限 |
| `llm-error` | GPT-4o API 呼叫失敗 |
| `spec-invalid` | JSON spec 未通過 schema 驗證 |

---

## Layer A — 來源發現

### 人工 + Researcher Agent

```bash
# 新增一個 candidate
cd scraper
python update_source.py --url "https://example.com/events" --status candidate

# 同時建立 GitHub Issue（需要 GITHUB_TOKEN）
python update_source.py --url "..." --status researched --create-issue
```

### researcher.py — 批次探索

| 檔案 | 用途 |
|------|------|
| `scraper/researcher.py` | 依分類批次搜尋候選來源，寫入 research_sources |

CI workflow：`researcher.yml`（4 slot × daily）

**4 slots（每日 JST）：**
- Slot 0 — 06:00：university、fukuoka
- Slot 1 — 12:00：media、government
- Slot 2 — 18:00：thinktank、hokkaido
- Slot 3 — 00:00：social、performing_arts、senses

### discovery_accounts.py — 平台帳號探索

| 平台 | 策略 | CI Slot（每週）|
|------|------|---------------|
| note.com | JSON API 搜尋台灣創作者 | Slots 0–2（Mon–Wed）|
| Peatix | Group page 驗證 | Slot 3（Thu）|

Peatix 找到的組織 → `agent_category='peatix_organizer'` → `peatix.py` 的 `_load_db_organizers()` 會讀取並直接爬取其活動。

---

## Layer B Phase 1 — 自動研究評估

### auto_research.py

**入口條件（evaluate 前必須滿足）：**
- `status = 'candidate'`
- `url_verified = true`

**LLM 評估輸出（assessment_schema.json）：**

| 欄位 | 說明 |
|------|------|
| `taiwan_score` | 0.0–1.0，定期發布台灣相關內容的可能性 |
| `feasibility` | `easy` / `medium` / `hard` — 爬蟲技術難度 |
| `card_selector_hint` | 找到的 CSS selector（**feasibility=easy 時必填**）|
| `rejection_reason` | 不可行時的原因 |
| `notes` | 其他人工審查備注 |

**ENFORCE 規則（2026-05-02 新增）：**
- `feasibility=easy` → `card_selector_hint` 必須填入 HTML 中確實存在的 selector
- 若找不到明確 selector → 降為 `medium`，不可以空字串帶過

**費用：** 每來源 ~$0.02–0.05（GPT-4o + 40k HTML）

CI workflow：`auto-research.yml`（每日 00:30 JST，最多 10 sources）

---

## Layer B Phase 2 — 自動代碼生成

### generate.py

**入口條件（generate 前必須滿足）：**
- `status = 'researched'`
- `feasibility = 'easy'`
- `auto_scraper_status IS NULL` 或 `'sandbox-failed'`（7 天 cooldown 後重試）

**Pipeline 步驟：**

```text
1. Playwright 抓樣本 HTML（含 JS 渲染）
2. GPT-4o JSON mode → spec（spec_schema.json 驗證）
3. spec_to_code.render(spec) → Python scraper 原始碼
4. ast_check() → 禁止的 API 呼叫檢查
5. 前置 selector check → 避免沙盒浪費
6. sandbox subprocess dry-run
   - 環境變數限制：無 SUPABASE_*、OPENAI_*、GITHUB_*
   - timeout: 300s
   - 臨時檔案：sources/_auto_<name>.py（atexit 清除）
7. 產出 artifacts → auto_scraper/runs/<source_id>/
   - spec.json
   - generated.py
   - dry_run.txt
   - meta.json（cost_usd, retries, sha256, events_found）
8. 更新 DB: auto_scraper_status
```

**費用：** 每來源 ~$0.05–0.15（GPT-4o + 50k HTML，最多 3 次重試）

**預算上限：** $1.50/run（可 `--budget` 調整）

CI workflow：`auto-generate.yml`（每日 01:00 JST，每批最多 3 sources）

### spec_schema.json — Spec 欄位定義

| 欄位 | 必填 | 說明 |
|------|------|------|
| `source_name` | ✓ | snake_case，唯一（e.g. `iwafu`）|
| `class_name` | ✓ | PascalCase（e.g. `IwafuScraper`）|
| `listing_url` | ✓ | 事件列表頁 URL |
| `card_selector` | ✓ | 事件卡片 CSS selector（**必須在 HTML 中存在**）|
| `field_selectors.title` | ✓ | 標題 selector |
| `field_selectors.date` | ✓ | 日期 selector |
| `field_selectors.link` | — | 詳情連結 selector |
| `date_regex` | ✓ | 從日期文字提取 YYYY-MM-DD |
| `source_id_url_pattern` | ✓ | 從 URL 提取穩定 ID |
| `detail_link_selector` | — | 卡片內詳情連結（留空則 fallback 到第一個 `<a>`）|
| `max_pages` | — | 最多抓幾頁（預設 3–5）|

### template.py.j2 — 生成的爬蟲模板

生成的爬蟲繼承 `BaseScraper`，結構為：
```python
class XxxScraper(BaseScraper):
    source_name = "xxx"
    def scrape(self) -> list[Event]: ...
```

### 安全限制（allowlist.txt）

只允許以下 imports：
- `sources.base`（BaseScraper, Event）
- `bs4`, `re`, `datetime`, `logging`
- `urllib.parse`

明確禁止：`requests`, `subprocess`, `os.system`, `eval`, `exec`, `open`

---

## Layer C — 人工整合

### 標準流程

```bash
# 1. 複製生成的爬蟲
cp scraper/auto_scraper/runs/<source_id>/generated.py scraper/sources/<name>.py

# 2. 人工審查（必要時調整 selector、LOOKBACK_DAYS、Taiwan filter）

# 3. 在 main.py 新增（同一 commit 必須含兩個檔案）
#    from sources.<name> import <ClassName>
#    SCRAPERS = [..., <ClassName>(), ...]

# 4. 本機 dry-run 驗證
python main.py --dry-run --source <name>

# 5. 確認 start_date 非空（非 publish date fallback）

# 6. 更新 research_sources.status → implemented

# 7. git commit + push
```

### 常見整合修改

| 問題 | 解決方式 |
|------|---------|
| 事件太多（非台灣） | 加 `_is_taiwan(title + description)` filter |
| start_date 用 publish date | 在 description 中正則提取 `YYYY年M月D日` |
| 需要分頁 | 在 scrape() 加 for page in range(max_pages) |
| 低頻來源（月刊/年刊）| 設定 `LOOKBACK_DAYS = 365` 或 `730` |

### 登記後的驗證（Pipeline 監控）

| 工具 | 用途 |
|------|------|
| `validate.py` | 每日檢查：selector 失效、缺日期、缺翻譯 |
| Admin → Sources | 來源健康監控（last_scraped_at、event_count）|
| `health_check.py` | 異常時 LINE 告警 |

---

## 關鍵 DB 欄位（research_sources）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | int | PK |
| `name` | text | 人類可讀名稱 |
| `url` | text | 來源 URL |
| `status` | text | candidate / researched / recommended / not-viable / implemented |
| `feasibility` | text | easy / medium / hard |
| `url_verified` | bool | URL 可存取確認 |
| `agent_category` | text | 探索分類（`peatix_organizer` 等）|
| `auto_scraper_status` | text | NULL / success / sandbox-failed / budget-exceeded / ... |
| `auto_scraper_last_run` | timestamptz | 最後一次 generate 嘗試 |
| `auto_scraper_cost_usd` | numeric | 累計代碼生成費用 |
| `card_selector_hint` | text | auto_research 找到的 CSS selector（easy 必填）|
| `reason` | text | 人工或 LLM 評估理由 |
| `notes` | text | 備注 |

---

## 檔案對照表

| 檔案 | 層 | 用途 |
|------|----|------|
| `scraper/researcher.py` | A | 批次探索候選來源 |
| `scraper/update_source.py` | A | 手動新增/更新 research_sources |
| `scraper/discovery_accounts.py` | A | note.com / Peatix 帳號探索 |
| `scraper/auto_scraper/auto_research.py` | B1 | 自動評估 candidate |
| `scraper/auto_scraper/generate.py` | B2 | 自動代碼生成 + sandbox |
| `scraper/auto_scraper/spec_to_code.py` | B2 | spec → Python + AST 安全驗證 |
| `scraper/auto_scraper/template.py.j2` | B2 | 爬蟲 Jinja2 模板 |
| `scraper/auto_scraper/spec_schema.json` | B2 | GPT 輸出 spec 的 JSON Schema |
| `scraper/auto_scraper/assessment_schema.json` | B1 | GPT 輸出評估的 JSON Schema |
| `scraper/auto_scraper/allowlist.txt` | B2 | 沙盒允許的 Python imports |
| `scraper/auto_scraper/runs/` | B2 | 生成結果 artifacts（gitignored）|
| `scraper/sources/base.py` | C | BaseScraper + Event dataclass |
| `scraper/sources/<name>.py` | C | 各來源爬蟲（人工整合後）|
| `scraper/main.py` | C/D | 排程器 + SCRAPERS 登記 |
| `.github/workflows/researcher.yml` | A | 每日 4 slot 探索 |
| `.github/workflows/discovery-accounts.yml` | A | 每日帳號探索 |
| `.github/workflows/auto-research.yml` | B1 | 每日 00:30 JST 自動評估 |
| `.github/workflows/auto-generate.yml` | B2 | 每日 01:00 JST 自動生成 |
| `.github/agents/researcher.agent.md` | A/B1 | Researcher Agent 指令 |
| `.github/agents/scraper-expert.agent.md` | B2/C | Scraper Expert Agent 指令 |
| `scraper/refetch_thin_events.py` | D | 空白事件重抓 — 重抓 `auto_qa_thin_content` 事件的詳細頁 |
| `.github/workflows/refetch-thin-events.yml` | D | 每日 14:00 JST 重抓（`REFETCH_THIN_LIVE` 控制）|

---

## CI 排程（研究→生成 相關）

| Workflow | 時間（JST）| 用途 |
|----------|-----------|------|
| `researcher.yml` | 06:00 / 12:00 / 18:00 / 00:00 | Layer A 批次探索（4 slots）|
| `discovery-accounts.yml` | 每日（Mon–Thu）| note.com + Peatix 帳號探索 |
| `auto-research.yml` | 00:30 | Layer B Phase 1 自動評估 |
| `auto-generate.yml` | 01:00 | Layer B Phase 2 自動代碼生成 |
| `scraper.yml` | 09:00 | Layer D 每日爬取（整合後的爬蟲生效）|
| `refetch-thin-events.yml` | 14:00 | Layer D 空白事件重抓（`REFETCH_THIN_LIVE` 控制）|

---

## 費用預估

| 步驟 | 每來源費用 | 說明 |
|------|-----------|------|
| auto_research | ~$0.02–0.05 | GPT-4o + 40k HTML |
| auto_generate | ~$0.05–0.15 | GPT-4o + 50k HTML，最多 3 次重試 |
| 每日批次上限 | ~$0.50 + $1.50 | auto-research + auto-generate 各自有上限 |

---

---

## Layer E — 外部統計資料（Government Open Data）

政府公開統計資料每月自動拉取，作為月報對比基準，**不影響事件爬蟲主 pipeline**。

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  Layer E — 外部統計拉取（每月 1 日 09:30 JST）                                │
│                                                                              │
│  external-stats-pull.yml                                                     │
│    → external_stats/pull_all.py                                              │
│       ├── jnto_visitors.py  → external_stats_taiwan_visitors（月別）          │
│       ├── moj_residents.py  → external_stats_resident_taiwanese（都道府縣別）  │
│       └── estat_population.py → external_stats_population（年更）             │
│                                                                              │
│  report_generator.build_section_benchmark()                                  │
│    → 讀取三張外部統計表，組合月報對比 section                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 資料表與來源

| 表 | Migration | 資料來源 | 授權 |
|----|-----------|---------|------|
| `external_stats_taiwan_visitors` | 055 | JNTO 訪日外客統計 | jp-gov-pdl-1.0 |
| `external_stats_resident_taiwanese` | 055 | MOJ 在留外國人統計 | jp-gov-pdl-1.0 |
| `external_stats_population` | 055 | e-Stat 住民基本台帳人口 | jp-gov-pdl-1.0 |

### 環境變數

| 變數 | 說明 |
|------|------|
| `ESTAT_APP_ID` | e-Stat API 應用程式 ID（[申請頁](https://www.e-stat.go.jp/api/)）— 無過期，洩漏後需重新申請 |

### 檔案對照

| 檔案 | 用途 |
|------|------|
| `scraper/external_stats/pull_all.py` | 拉取入口 — 依序執行三個 puller |
| `scraper/external_stats/jnto_visitors.py` | JNTO Excel 解析 + upsert |
| `scraper/external_stats/moj_residents.py` | MOJ CSV 解析 + upsert |
| `scraper/external_stats/estat_population.py` | e-Stat JSON API + upsert |
| `scraper/external_stats/base.py` | 共用基底（`BaseStatsPuller`）|
| `scraper/report_generator.py` | `build_section_benchmark()` |
| `supabase/migrations/055_external_stats.sql` | 三張統計表 schema |
| `.github/workflows/external-stats-pull.yml` | 每月 CI workflow |


## 相關文件

- 全站架構：[ARCHITECTURE.md](ARCHITECTURE.md)
- Researcher Agent 指令：[.github/agents/researcher.agent.md](../.github/agents/researcher.agent.md)
- Scraper Expert SKILL：[.github/skills/agents/scraper-expert/SKILL.md](../.github/skills/agents/scraper-expert/SKILL.md)
- Researcher SKILL：[.github/skills/agents/researcher/SKILL.md](../.github/skills/agents/researcher/SKILL.md)
