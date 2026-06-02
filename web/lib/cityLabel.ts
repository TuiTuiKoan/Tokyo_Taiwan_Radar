/**
 * City badge derivation for EventCard and homepage list.
 *
 * Priority:
 *   1. location_prefectures array (annotator-set, authoritative) — single or multi
 *   2. extractCity(location_address) — regex fallback for legacy events
 */

/** Normalize a location_prefectures entry (e.g. "東京都" → "東京"). */
export function shortPrefecture(p: string): string {
  if (p === "北海道") return "北海道";
  // Strip Japanese 都道府県, Taiwan 市縣, and Japanese-style Taiwan 県
  return p.replace(/[都道府県市縣]$|県$/, "");
}

/** Extract short prefecture name from a Japanese or Taiwanese address.
 *  Searches anywhere in the string (not just at start) to tolerate
 *  〒xxx-xxxx postal-code prefixes and leading whitespace. */
export function extractCity(address: string | null | undefined): string | null {
  if (!address) return null;

  // 1. Taiwan (check for common Taiwan city/county names)
  const twRegex =
    /([臺台]北|新北|桃園|[臺台]中|[臺台]南|高雄|基隆|新竹|苗栗|彰化|南投|雲林|嘉義|屏東|宜蘭|花蓮|[臺台]東|澎湖|金門|連江)(市|縣|県)/;
  const mTw = address.match(twRegex);
  if (mTw) {
    return mTw[1].replace("臺", "台");
  }

  // 2. Japan
  const m = address.match(
    /(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県\d〒-]{2,4}[都道府県])/,
  );
  if (!m) return null;
  const full = m[1];
  if (full === "北海道") return "北海道";
  if (full === "大阪市" || full === "大阪府") return "大阪";
  if (full === "京都市" || full === "京都府") return "京都";
  if (full === "東京都") return "東京";
  return full.replace(/[都道府県]$/, "");
}

/** Derive city badge label from an event's location fields. Returns null
 *  when no city can be determined (e.g. online or overseas events). */
export function getCityLabel(
  prefectures: string[] | null | undefined,
  address: string | null | undefined,
): string | null {
  if (prefectures && prefectures.length >= 1) {
    return prefectures.map(shortPrefecture).join("・");
  }
  return extractCity(address);
}
