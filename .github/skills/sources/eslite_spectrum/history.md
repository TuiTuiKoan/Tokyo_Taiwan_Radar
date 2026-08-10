# eslite_spectrum — History

Newest at top.

---

## 2026-08-09 — 商品價格、子活動與官方營業時間

**Error:** 夏季 umbrella 頁把單一台灣茶禮盒 `6,980円` 誤當整體活動費，相關項目沒有拆成子活動；父活動與三個店內項目也缺少可由官方 access 頁確認的一般營業時間。

**Fix:** `_extract_price_info()` 改為只接受明確標示的活動費，保留 canonical parent 並建立七個直接子活動。官方店舖頁確認 `平日 11:00～20:00、土日祝 10:00～20:00`，寫入 authoritative venue seed／production ground truth；只回填四筆無專屬時段的父子活動，其他四筆保留自身日期別時段。

**Lesson:** 商品售價、餐飲價格與抽選購買門檻都不是活動入場費。系列頁的獨立項目應保留各自日期、地點、時間及參加條件。營業時間優先取活動專屬時段；缺少時才用官方 `アクセス`／店舖頁建立的 venue ground truth，餐廳或租戶例外不可套到全館。

## 2026-07-11 — publication phase 3 invariant sync

- publication 判定統一為 exact `event_form=['publication']`，不再以 source/category 當 pure shortcut。
- 純出版 rows 對齊 metadata-only（七欄 intentional null + sentinel），publisher 維持 required。
- eslite 的 physical launch/talk/signing/lecture/workshop rows 明確標記 mixed negative：不得含 `publication`。

## 2026-06-04 — publication rule sync

- Added a publication-specific note so placeholder addresses stay display-only and do not become map links.
- Aligned the publication field roles with the shared scraper rules: `performer`, `organizer_url`, and `official_url`.

## 2026-06-04 — publication placeholders locale sync

- Publication placeholders now stay locale-matched across `location_name`, `location_address`, and `business_hours`.
- Japanese UI uses `新刊のご購入は各販売チャネルでお願いします` as the default placeholder.
- The Japanese UI should not show Chinese fallback text for publication display placeholders.


## 2026-04-26 — 誠品 keyword false positive issue

**Error**: All 5 news articles were matching the Taiwan filter when `"誠品"` was included in `TAIWAN_KEYWORDS`.

**Root cause**: `"誠品"` appears in every page's navigation sidebar and footer (e.g. "誠品生活メンバーズカード", "誠品生活日本橋について"). When checking `page_text` (full page HTML), every article triggered the Taiwan filter.

**Fix**:
1. Removed `"誠品"` from `TAIWAN_KEYWORDS`.
2. Changed the keyword check to use `content_text = f"{title}\n{description}"` (main content only), not the full `page.text`.
3. Added `_SKIP_TITLE_RE` to pre-filter admin articles (membership, workshop calendars, notices) before fetching detail pages.

**Lesson**: For venue/shop scrapers, always check keywords against main content only, not the full page. Site-name branding in nav/footer will trigger false positives.
