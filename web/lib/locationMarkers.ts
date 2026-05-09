/**
 * Client-side location filter helpers.
 *
 * Mirrors the SSR location predicate that previously lived inside
 * `app/[locale]/page.tsx`. Used by `EventListClient` to filter events
 * without a server round-trip.
 *
 * Notes:
 * - Tokyo: NULL/empty `location_address` is treated as Tokyo (preserves
 *   prior SSR behavior).
 * - "京都" is a substring of "東京都"; always use "京都府"/"京都市" markers.
 */

export const LOCATION_KEYS = [
  "tokyo",
  "kanto",
  "tohoku",
  "chubu",
  "chugoku",
  "online",
  "overseas",
] as const;

export type LocationKey = (typeof LOCATION_KEYS)[number];

interface LocationMarkerSet {
  /** Substrings to look for in `location_address` (case-insensitive). */
  addressMarkers: string[];
  /** Prefecture names to look for in `location_prefectures` array. */
  prefectures: string[];
}

const TOKYO_MARKERS = [
  "東京",
  "新宿区",
  "港区",
  "渋谷区",
  "千代田区",
  "文京区",
  "台東区",
  "台北駐日",
];
const KANTO_MARKERS = ["神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨"];
const TOHOKU_MARKERS = ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島"];
// Address markers use "京都府"/"京都市" to avoid matching "東京都".
const CHUBU_KINKI_ADDRESS_MARKERS = [
  "愛知",
  "静岡",
  "岐阜",
  "長野",
  "新潟",
  "富山",
  "石川",
  "福井",
  "大阪",
  "京都府",
  "京都市",
  "兵庫",
  "奈良",
  "滋賀",
  "和歌山",
  "三重",
];
// Prefecture-array values are bare prefecture names (no "府"/"市" suffix).
const CHUBU_KINKI_PREFECTURES = [
  "愛知",
  "静岡",
  "岐阜",
  "長野",
  "新潟",
  "富山",
  "石川",
  "福井",
  "大阪",
  "京都",
  "兵庫",
  "奈良",
  "滋賀",
  "和歌山",
  "三重",
];
const CHUGOKU_KYUSHU_ADDRESS_MARKERS = [
  "広島",
  "岡山",
  "鳥取",
  "島根",
  "山口",
  "福岡",
  "佐賀",
  "長崎",
  "熊本",
  "大分",
  "宮崎",
  "鹿児島",
  "沖縄",
  "高知",
  "愛媛",
  "徳島",
  "香川",
];
const CHUGOKU_KYUSHU_PREFECTURES = CHUGOKU_KYUSHU_ADDRESS_MARKERS;
const TAIWAN_MARKERS = [
  "台北",
  "台中",
  "高雄",
  "台南",
  "新竹",
  "嘉義",
  "花蓮",
  "台東",
  "基隆",
  "宜蘭",
  "桃園",
  "屏東",
  "南投",
  "彰化",
  "雲林",
  "澎湖",
];

export const LOCATION_MARKERS: Record<LocationKey, LocationMarkerSet> = {
  tokyo: { addressMarkers: TOKYO_MARKERS, prefectures: ["東京"] },
  kanto: { addressMarkers: KANTO_MARKERS, prefectures: KANTO_MARKERS },
  tohoku: { addressMarkers: TOHOKU_MARKERS, prefectures: TOHOKU_MARKERS },
  chubu: {
    addressMarkers: CHUBU_KINKI_ADDRESS_MARKERS,
    prefectures: CHUBU_KINKI_PREFECTURES,
  },
  chugoku: {
    addressMarkers: CHUGOKU_KYUSHU_ADDRESS_MARKERS,
    prefectures: CHUGOKU_KYUSHU_PREFECTURES,
  },
  online: { addressMarkers: [], prefectures: [] },
  overseas: { addressMarkers: TAIWAN_MARKERS, prefectures: [] },
};

interface EventLike {
  location_name?: string | null;
  location_address?: string | null;
  location_prefectures?: string[] | null;
}

function containsAny(haystack: string, needles: string[]): boolean {
  for (const n of needles) {
    if (haystack.includes(n)) return true;
  }
  return false;
}

/**
 * Returns true if `event` matches the given `locationKey`. Mirrors the
 * SSR query predicates exactly.
 */
export function matchesLocation(
  event: EventLike,
  locationKey: string,
): boolean {
  if (!locationKey) return true;

  const addr = event.location_address ?? "";
  const prefs = event.location_prefectures ?? [];
  const name = event.location_name ?? "";

  if (locationKey === "tokyo") {
    if (!addr) return true; // NULL/empty counts as Tokyo
    if (containsAny(addr, TOKYO_MARKERS)) return true;
    if (prefs.includes("東京")) return true;
    return false;
  }

  if (locationKey === "online") {
    return name.includes("オンライン");
  }

  const set = LOCATION_MARKERS[locationKey as LocationKey];
  if (!set) return true;

  if (addr && containsAny(addr, set.addressMarkers)) return true;
  if (set.prefectures.length > 0) {
    for (const p of set.prefectures) {
      if (prefs.includes(p)) return true;
    }
  }
  return false;
}
