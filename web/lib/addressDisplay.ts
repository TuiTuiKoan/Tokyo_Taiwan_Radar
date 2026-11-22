/**
 * Display helpers for event addresses.
 *
 * The database keeps postal codes (they help geocoding and admin merges prefer the
 * longer address). Visitors do not need them, so the event page shows the address
 * without them and moves the code into the structured data's `postalCode` field.
 */

const DASH = "[-‐‑‒–—―−－ー]";
const POSTAL = `\\d{3}\\s*${DASH}\\s*\\d{4}`;

// 〒 / 郵便番号 / 郵遞區號 / postal code followed by the number, anywhere.
const LABELLED_POSTAL_RE = new RegExp(
  `(?:〒|郵便番号[:：]?|郵遞區號[:：]?|郵政編碼[:：]?|postal\\s*code[:：]?|zip[:：]?)\\s*(${POSTAL})`,
  "gi",
);
// A bare number at the very start ("150-0033 東京都…") or the very end
// ("…, Tokyo 150-0033"). Not in the middle: a lot number can look the same.
const LEADING_POSTAL_RE = new RegExp(`^\\s*(${POSTAL})(?![\\d-])`);
const TRAILING_POSTAL_RE = new RegExp(`(?<![\\d-])(${POSTAL})\\s*(?:,?\\s*(?:日本|Japan))?\\s*$`, "i");
// "日本、" before the address or ", Japan" / " 日本" after it.
const COUNTRY_PREFIX_RE = /^\s*(?:日本|Japan)\s*[、,，]?\s*/i;
const COUNTRY_SUFFIX_RE = /\s*[,，、]?\s*(?:日本|Japan)\s*$/i;

function normalizePostal(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  return `${digits.slice(0, 3)}-${digits.slice(3)}`;
}

/** The first postal code in the address, as "NNN-NNNN", or null. */
export function extractPostalCode(address: string | null | undefined): string | null {
  if (!address) return null;
  const labelled = new RegExp(LABELLED_POSTAL_RE.source, "i").exec(address);
  const match = labelled ?? LEADING_POSTAL_RE.exec(address) ?? TRAILING_POSTAL_RE.exec(address);
  return match ? normalizePostal(match[1]) : null;
}

/** The address without postal codes or a bare country name around it. */
export function stripPostalCode(address: string): string;
export function stripPostalCode(address: string | null | undefined): string | null;
export function stripPostalCode(address: string | null | undefined): string | null {
  if (address == null) return null;
  const stripped = address
    .replace(LABELLED_POSTAL_RE, " ")
    .replace(COUNTRY_PREFIX_RE, "")
    .replace(LEADING_POSTAL_RE, " ")
    .replace(TRAILING_POSTAL_RE, " ")
    .replace(COUNTRY_SUFFIX_RE, "")
    .replace(/[ 　]{2,}/g, " ")
    // Separators left dangling where a code was removed: "（ 東京都…" / ", , Tokyo".
    .replace(/([（(])\s+/g, "$1")
    .replace(/\s+([）)])/g, "$1")
    .replace(/\s*,\s*,/g, ",")
    .replace(/^[\s,，、]+|[\s,，、]+$/g, "");
  return stripped || null;
}
