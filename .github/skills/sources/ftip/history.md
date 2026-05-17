# ftip (台湾原住民族との交流会) Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-05-17 — Peatix URL が HTML アンカーとして埋め込まれ `.get_text()` で消失

**問題:** `official_url` / `source_url` に Peatix URL が設定されず、イベント詳細ページの CTA ボタンが ftip.org（二手）を指したままだった。

**根本原因:** WordPress RSS CDATA 内の Peatix リンクは `<a href="https://xxx.peatix.com/...">` アンカーとして埋め込まれている。`content_html = content_el.get_text()` → `BeautifulSoup(content_html).get_text()` の二段階テキスト変換で href が消えるため、`_extract_peatix_url(content_text)` の正規表現で URL が検出できなかった。

**修正（commit `ee870f7`）:**
- `_extract_peatix_url_from_html(html_text)` を追加。生の CDATA HTML 文字列（`content_html`）を BS4 で再パースし `find_all("a", href=True)` を走査。
- 呼び出し: `_peatix = _extract_peatix_url(content_text) or _extract_peatix_url_from_html(content_html)`
- Peatix URL 発見時: `source_url = _peatix`、`official_url = _peatix`（一手 URL が CTA に直結）。

**教訓:** WordPress RSS CDATA の URL はプレインテキストではなく `<a href>` として埋め込まれる。URL 抽出時は `content_text` と `content_html` の両方を検索すること。

---

## 2026-05-17 — `location_name` に組織名定数 "台湾原住民族との交流会" がフォールバックされ会場欄に誤表示

**問題:** 会場抽出に失敗した全 ftip イベントで `location_name = "台湾原住民族との交流会"`（組織名）が設定されていた。event `eeb5b12e`（ねりま沖縄映画祭2025）では実際の会場「Coconeri３階 練馬区民・産業プラザ研修室１」ではなく組織名が表示されていた。

**根本原因:** `LOCATION_NAME = "台湾原住民族との交流会"` 定数を venue フォールバックとして使っていた。

**修正（commit `278e6d8`）:** `location_name = venue_name if venue_name else None`

**DB fix (event `eeb5b12e`):**
- `location_name` → `"Coconeri３階 練馬区民・産業プラザ研修室１"` + FC lock
- `location_address` → `"〒176-0012 東京都練馬区豊玉北6丁目12番1号"` + FC lock
- `business_hours` → `"19:00"` + FC lock
- `source_url` / `official_url` → `"https://nerimaokinawaeigasai.peatix.com"` + FC lock (official_url)

**教訓:** 組織名定数を `location_name` のフォールバックに使わない。会場不明の場合は `None` を設定し、annotator に委ねる。

---

## 2026-05-17 — `business_hours` / organizer / Peatix URL の抽出ロジックを追加

**背景:** ftip scraper には時刻・主催者・Peatix URL の抽出ロジックがなく、annotator に完全依存していた。

**追加（commit `278e6d8`）:**
- `_SHOWTIME_RE` + `_extract_showtime()` — `HH:MM` パターンを `business_hours` に設定
- `_ORGANIZER_RE` + `_extract_organizer()` — `主催：XXX` パターンから organizer を抽出
- `_PEATIX_URL_RE` + `_extract_peatix_url()` — プレインテキストから Peatix URL を抽出（`_extract_peatix_url_from_html()` と組み合わせて使用）

**教訓:** ソースページに構造化フィールド（時刻・主催者）が存在する場合は、scraper で直接設定する。annotator への依存は fallback であり主たる手段ではない。
