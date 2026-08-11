# eslite_spectrum — History

Newest at top.

---

## 2026-08-09 - authoritative venue hours and subspace precedence

### Error

The canonical summer parent and three in-store children had no `business_hours`. The authoritative `誠品生活日本橋` venue also lacked hours, and exact-only lookup could not attach parent metadata to specific labels such as `expo`, `書籍レジ`, and `各ショップ`.

### Fix

The first-party store and access page verified `平日 11:00～20:00、土日祝 10:00～20:00` as general venue hours. Manifest `5742d0438ed9` filled four events with no dedicated schedule while preserving four event-specific schedules. The venue overlay now preserves all three localized subspace labels, applies parent metadata only where eligible, respects every field-correction key including empty sentinels, and permanently rejects another `--apply` run.

### Lesson

Current and stored event schedules take precedence over authoritative venue hours. General hours require first-party venue evidence, while restaurant and tenant exceptions remain separate. Subspace labels inherit parent metadata without losing their more specific names in any locale.

## 2026-08-09 - price and summer hierarchy repair

### Error

The summer umbrella page treated an unlabeled `6,980円` Taiwan tea gift as the campaign admission price and did not represent the listed independently scheduled or conditioned activities as children.

### Fix

`_extract_price_info()` now accepts only explicitly labeled event fees such as `参加費`, `料金`, or `入場料`. Applied manifest `4f25dfc756d3` retained one canonical parent with seven direct children, deactivated the duplicate Collection row, and redirected it to the canonical parent. Its historical mutation code remains available for audit inspection, but another `--apply` run is permanently rejected.

### Lesson

Merchandise prices, menu prices, and purchase thresholds are not event admission fees. An umbrella page with independently dated, located, or conditioned activities requires child records that preserve each activity's schedule and participation terms.

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
