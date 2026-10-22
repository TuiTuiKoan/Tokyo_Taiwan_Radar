# Guards 元評估

`.github/skills/agents/architect/SKILL.md` 的 guard 是否真的被遵守、是否還有必要（#356）。`scraper/guard_detections.py` 每月 1 日由 `monthly_health_check.yml` 執行，結果寫入本目錄的 `YYYY-MM.md` 與 `YYYY-MM.json`。Reviewer agent 的「功能 1b」讀取最新月份。

## 判讀

- **違規計數**：目標為 0。非 0 代表 guard 沒有被程式碼套用，或有資料殘留。
- **連續 3 個月為 0**：候選精簡。先確認規則已內化進程式碼（例如有測試或 DB constraint），才從 SKILL.md 移除；也可能只是偵測條件寫錯。
- **比上月增加**：優先排查。
- **代理指標**：待審清單，不是違規數，不列入精簡候選。

## 盤點（2026-10-22）

共 103 條：93 條標題含 Guard／守護／防護，10 條是寫出具體資料症狀的規則。行號是盤點當時的位置。

| 類型 | 條數 | 偵測方式 |
|---|---|---|
| DATA：失敗會留下資料症狀 | 47 | 28 條由 `guard_detections.py` 以單表 PostgREST 查詢計數；其餘需要 join、regex、遞迴或欄位互比，見下表「未實作」 |
| CODE：失敗只在程式碼層 | 41 | grep、測試或 lint；不在本工具範圍 |
| PROCESS：規劃或審查規則 | 15 | 無法自動偵測 |

### DATA guard

| 行 | Guard | detection id |
|---|---|---|
| 54 | Derived enrichment candidate audit | `placeholder_cover_image` |
| 68 | Pure-online / Hybrid planning guard | `online_with_physical_fields` |
| 228 | Admin API enum 防禦 | 未實作：需要比對陣列與程式碼中的白名單 |
| 368 | Circular Merge Redirect Loop Guard | 未實作：遞迴 |
| 404 | Auto-Generate Promotion Checklist | `implemented_without_scraper_key` |
| 429 | Person Name Enrich English Guard | 未實作：regex（片假名） |
| 439 | Known Person Map Guard | `inactive_person_missing_translation` |
| 457 | Performer Multilingual Fields Guard | `person_missing_translation` |
| 482 | Multi-Session Course business_hours Guard | 未實作：代理條件太弱 |
| 486 | Organizer Multilingual Fields Guard | `organizer_missing_translation` |
| 531 | SC→TC Three-Layer（L2 chokepoint） | 未實作：GROUP BY |
| 555 | Annotator name_ja Suffix Omission Guard | `name_ja_report_suffix_lost` |
| 593 | Report Prefix Injection Guard | `report_prefix_injected` |
| 688 | Database Safety Rules | `inactive_without_pass`（代理） |
| 694 | Annotator Backfill QA Rule | 未實作：jsonb 加 regex |
| 846 | auto_qa False Positive Guard | `missing_address_reports_dismissed`（代理） |
| 939 | Scraper Date Timezone Guard | 未實作：時間 cast |
| 965 | Universal Year-Anchor Guard | 未實作：跨欄位計算（2026-10-22 SQL 試算 127 筆，含出版品） |
| 1024 | Cinema Series Sub-Event Sub_Events Guard | `ks_cinema_active_sub1` |
| 1043 | Organizer Non-Hallucination Guard | 未實作：欄位互比（SQL 試算 977 筆，受 organizer 正規化影響，需先調整） |
| 1075 | Joint Distributor Split Guard | `organizer_with_slash`（代理） |
| 1095 | Work Title ≠ Event Name Guard | 未實作：長度函式 |
| 1113 | Blog/Creator Source Thin Content Guard | `note_creators_with_organizer` |
| 1146 | Collection Attribution Guard | `yebizo_location_not_venue` |
| 1171 | Performer Null Guard | `performer_null_with_guest_title`（代理） |
| 1223 | Manual Merge Completeness Guard | `merged_but_active` |
| 1412 | Scraper Failure Notes Guard | `failed_run_without_notes_30d` |
| 1422 | Persistent Zero Sources Diagnostic Guard | 未實作：GROUP BY；改由 #354 的品質週報追蹤 |
| 1450 | Kanji Time Format business_hours Guard | `tcc_kanji_time_missing_hours` |
| 1522 | reviewed 保護邊界 Guard | `reviewed_missing_hours`（代理） |
| 1551 | TV / Non-Physical Location Standard | `tv_location_not_standard` |
| 1667 | Reviewed Event Translation Guard | `reviewed_missing_title_translation` |
| 1739 | Cinema Official URL Extraction | `official_url_ticket` |
| 1922 | Sub-Venue Parent Address Guard | 未實作：欄位互比（SQL 試算 12 筆；要求的偵測器已不存在，見 #384） |
| 1935 | Address Regex Prefecture-Optional Guard | `venue_name_without_address`（代理） |
| 1946 | Contentful 1 月佔位符 | 未實作：跨年日期條件 |
| 2015 | Venue = Organizer Default Guard | `museum_source_missing_organizer` |
| 2063 | Auto-Research Low-Signal Policy Guard | `lowsignal_rejected_above_threshold` |
| 2079 | Entity Normalization Guard | `organizer_fk_unresolved`（代理） |
| 2091 | gnews Sub-Event Merger Guard | 未實作：self-join |
| 2103 | SC → TC Guard | 未實作：regex（auto-QA 的簡體字回報可作代理） |
| 2146 | Venue QA Skip Source Registration Guard | 未實作：join |
| 2194 | Movie Lookup Official URL Guard | `official_url_eiga` |
| 2223 | Aggregator official_url Guard | 未實作：欄位互比 |
| 2245 | Venue Parent vs Sub-event business_hours Guard | 未實作：subquery 加 regex |
| 2282 | organizer_type Batch Inference Guard | `organizer_type_without_organizer` |
| 2300 | Organizer Authority Guard | 未實作：陣列長度函式（migration 095 已有 CHECK） |

### CODE 與 PROCESS guard

CODE（41）：predicate projection contract（50）、rendered visual-delta（52）、sub-event source_id drift（66）、OCR array sync（192）、category sync（207）、QA heartbeat FC 番兵（283）、loading state try/finally（317）、LINE broadcast query（416）、mixed-script performer（478）、SC→TC mapping burden（509）、Movie-extend invariant（653）、homepage inline card（668）、server component + realtime（731）、SSR props（815）、QA keyword precision（836，已過時，#384）、RLS cross-status（857）、scraper-priority（907）、event intake alignment（922）、enrich_movie_titles sub-event（996）、admin form prop（634）、AdminEventTable cross-filter（1242）、column width（1266）、category union（1343）、SQL privilege（1376）、RPC auth context（1385）、cron dispatch（1401）、HTMLParser thin content（1467）、self-prefix pollution（1489）、listing page date（1502）、auto-generate date field（1514）、GITHUB_TOKEN permission（1625）、pre-commit i18n（1657）、heartbeat prompt injection（1702）、LLM budget（1864）、server-side keyword filter（1959）、gnews snippet date（1983）、SCRAPERS list（2000）、batch post-enrichment（2049）、workflow_run self-loop（2113）、NON_DAILY_SOURCES（2129）、GitHub Actions YAML（2164）。

PROCESS（15）：multi-phase manifest（26）、canonical path（88）、workstream status（90）、security release matrix（99）、pre-flight baseline drift（152）、transient failure triage（299）、manual translation persistence（576）、re-annotation date clearing（614）、hallucination scan safety（956）、staging index（1656）、merger schema change（1904）、film title cross-language（2025）、movie re-release official_url（2206）、Google Cloud API avoidance（2258）、migration constraint replacement（2268）。

## 2026-10-22 試算（唯讀 SQL）

| detection | 數量 |
|---|---|
| merged_but_active | 0 |
| reviewed_missing_title_translation | 0 |
| official_url_eiga | 0 |
| official_url_ticket | 0 |
| failed_run_without_notes_30d | 18 |
| online_with_physical_fields | 26 |

正式數字以第一次 workflow 執行為準。

## 尚未涵蓋

- 上表「未實作」的 19 條：需要唯讀 RPC 或資料庫連線，使用者 2026-10-22 決定先做 PostgREST 版（#386）。
- 原 #356 清單中的 history.md 引用率與 subagent 採用率分析：原本依賴 Copilot 的 `semantic_search` 與 `session_store_sql`，在 Claude Code／Codex 下沒有對應資料來源，見 #386。
