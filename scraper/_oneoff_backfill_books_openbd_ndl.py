"""One-off script for backfilling and enriching publication books metadata from OpenBD API & NDL Search.

Requires virtual environment activated and environment variables loaded.
Usage:
    python _oneoff_backfill_books_openbd_ndl.py [--apply]
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(".env")
sys.path.append(".")
from annotator import _get_supabase, _lock_fields_via_corrections, _to_trad

# Placeholders
_PUBLICATION_PLACEHOLDER_ZH = "新書購買請洽各通路"


def extract_isbn(source_id: str | None, source_url: str | None) -> str | None:
    for text in [source_id, source_url]:
        if not text:
            continue
        m13 = re.search(r"(97[89]\d{10})", text)
        if m13:
            return m13.group(1)
        m10 = re.search(r"\b(\d{10})\b", text)
        if m10:
            return m10.group(1)
    return None


def clean_author(raw_author: str | None) -> str | None:
    if not raw_author:
        return None
    cleaned = raw_author.strip()
    for suffix in [
        " 著・文・その他",
        " 著",
        " 編集",
        " 編",
        " / 著",
        "／著",
        " [著]",
        " 著・訳",
        " 著/訳",
    ]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned


def format_price_info(raw_price: str | None) -> tuple[str | None, int | None]:
    if not raw_price:
        return None, None
    digits_match = re.search(r"(\d[\d,.]*)", raw_price)
    if digits_match:
        val_str = digits_match.group(1).replace(",", "")
        try:
            amount = int(float(val_str))
            if amount > 50:
                inclusive_amount = int(amount * 1.10)
                return f"{inclusive_amount:,}円 (税込)", inclusive_amount
        except Exception:
            pass
    return raw_price.strip(), None


def fetch_ndl_fields(isbn: str) -> dict[str, str | None]:
    for prefix in ("R100000137-I", "R100000002-I"):
        url = f"https://ndlsearch.ndl.go.jp/books/{prefix}{isbn}"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")

            soup = BeautifulSoup(html, "html.parser")
            author = None
            price = None

            for dt in soup.find_all("dt"):
                dt_text = dt.get_text(strip=True)
                dd = dt.find_next_sibling("dd")
                if not dd:
                    continue
                dd_text = dd.get_text(strip=True)

                if dt_text in ("著者:", "著者・編者:", "著者"):
                    author = dd_text
                elif dt_text in ("入手条件・定価:", "価格:"):
                    price = dd_text

            if author or price:
                return {
                    "author": clean_author(author),
                    "price_raw": price,
                    "source": f"NDL ({prefix})",
                }
        except Exception:
            continue
    return {}


def query_openbd(isbn: str) -> dict[str, str | None]:
    url = f"https://api.openbd.jp/v1/get?isbn={isbn}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))

        if data and data[0]:
            item = data[0]
            summ = item.get("summary", {})
            onix = item.get("onix", {})
            author = summ.get("author") or None

            price_amount = None
            try:
                price_amount = onix["ProductSupply"]["SupplyDetail"]["Price"][
                    0
                ]["PriceAmount"]
            except Exception:
                pass

            return {
                "author": clean_author(author),
                "price_raw": str(price_amount) if price_amount else None,
                "source": "OpenBD API",
            }
    except Exception:
        pass
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing author/price for publication books using openBD & NDL"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Commit changes to Supabase and lock fields"
    )
    args = parser.parse_args()

    sb = _get_supabase()
    res = (
        sb.table("events")
        .select("id, name_ja, source_name, source_id, source_url, performer, price_info")
        .eq("is_active", True)
        .execute()
    )
    all_events = res.data or []

    books = []
    for e in all_events:
        source_name = e.get("source_name") or ""
        is_pub = (
            source_name
            in ("hanmoto", "ndl_opensearch", "kawade_rss", "eslite_spectrum")
            or (e.get("event_form") and "publication" in e["event_form"])
            or (e.get("category") and "books_media" in e["category"])
        )
        if is_pub:
            isbn = extract_isbn(e["source_id"], e["source_url"])
            if isbn:
                books.append((e, isbn))

    print(f"Detected {len(all_events)} active events.")
    print(f"Identified {len(books)} books with valid ISBN.")

    updates_planned = []

    for i, (e, isbn) in enumerate(books, start=1):
        print(f"[{i}/{len(books)}] Auditing: {e['name_ja']} (ISBN: {isbn})...")

        # 1. Query openBD API
        meta = query_openbd(isbn)
        if not meta or not meta.get("author") or not meta.get("price_raw"):
            # 2. Fallback to NDL Web Parsing
            ndl_meta = fetch_ndl_fields(isbn)
            if ndl_meta:
                # Merge / fallback
                for k, v in ndl_meta.items():
                    if v and (not meta.get(k)):
                        meta[k] = v
                meta["source"] = (
                    f"{meta.get('source', '')} + {ndl_meta['source']}".strip(
                        " + "
                    )
                )

        if not meta:
            print("  -> Could not resolve metadata.")
            continue

        author = meta.get("author")
        price_raw = meta.get("price_raw")

        db_author = e.get("performer") or ""
        db_price = e.get("price_info") or ""

        # Flag changes
        update_payload = {}

        if author and (not db_author or db_author == "None"):
            clean_name = author
            update_payload["performer"] = clean_name
            update_payload["performer_zh"] = _to_trad(clean_name)
            # Simple fallback for English contributor
            update_payload["performer_en"] = clean_name
            update_payload["performers"] = [clean_name]
            update_payload["performers_zh"] = [_to_trad(clean_name)]
            update_payload["performers_en"] = [clean_name]

        if price_raw and (
            not db_price
            or db_price in (_PUBLICATION_PLACEHOLDER_ZH, "新書購買請洽各通路", "—")
        ):
            price_str, price_amount = format_price_info(price_raw)
            if price_str:
                update_payload["price_info"] = price_str
                update_payload["is_paid"] = True
                update_payload["price_currency"] = "JPY"
                if price_amount:
                    update_payload["price_amount"] = price_amount

        if update_payload:
            updates_planned.append((e["id"], e["name_ja"], isbn, update_payload, meta["source"]))
            print(f"  -> PLANNED via {meta['source']}:")
            for field, val in update_payload.items():
                print(f"     * {field}: {val}")
        else:
            print("  -> Already up-to-date in database.")

        # Be polite to APIs / servers
        time.sleep(0.5)

    print(f"\n--- Audit complete. Planned updates for {len(updates_planned)} / {len(books)} books. ---")

    if not updates_planned:
        print("All book pages are fully enriched and up to date.")
        return

    if not args.apply:
        print("\n[Dry-run] To apply change, re-run with: --apply")
        return

    print("\n--- Committing changes and locking fields via field_corrections... ---")
    for index, (eid, title, isbn, payload, src) in enumerate(updates_planned, start=1):
        print(f"[{index}/{len(updates_planned)}] Writing updates for {title} (ID: {eid})...")
        sb.table("events").update(payload).eq("id", eid).execute()
        # Lock fields
        _lock_fields_via_corrections(sb, eid, payload)

    print("\nAll database updates have been completed and locked successfully! 🎉")


if __name__ == "__main__":
    main()
