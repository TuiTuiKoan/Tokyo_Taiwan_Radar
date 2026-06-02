/**
 * Region → prefecture mapping — single source of truth shared by:
 *   - web/components/FilterBar.tsx  (city sub-select UI)
 *   - web/app/[locale]/page.tsx     (homepage post-filter)
 *   - web/components/AdminEventTable.tsx  (admin post-filter)
 *
 * Prefecture strings must match the address substrings / location_prefectures
 * values used in DB queries (KANTO_MARKERS, CHUBU_KINKI_MARKERS, etc.).
 */

export const CITY_OTHER = "_other" as const;

/** Regions that expose a prefecture sub-select. */
export const REGIONS_WITH_CITY = ["kanto", "tohoku", "chubu", "chugoku"] as const;
export type RegionWithCity = (typeof REGIONS_WITH_CITY)[number];

export const REGION_PREFECTURES: Record<RegionWithCity, string[]> = {
  kanto: [
    "神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨",
  ],
  tohoku: [
    "北海道",
    "青森", "岩手", "宮城", "秋田", "山形", "福島",
  ],
  chubu: [
    "愛知", "静岡", "岐阜", "長野", "新潟", "富山", "石川", "福井",
    "大阪", "京都", "兵庫", "奈良", "滋賀", "和歌山", "三重",
  ],
  chugoku: [
    "広島", "岡山", "鳥取", "島根", "山口",
    "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄",
    "高知", "愛媛", "徳島", "香川",
  ],
};

/** English romaji labels for each prefecture (used in en locale). */
export const PREFECTURE_LABELS_EN: Record<string, string> = {
  // Kanto / Tohoku / Hokkaido
  神奈川: "Kanagawa", 埼玉: "Saitama", 千葉: "Chiba",
  茨城: "Ibaraki", 栃木: "Tochigi", 群馬: "Gunma", 山梨: "Yamanashi",
  北海道: "Hokkaido",
  青森: "Aomori", 岩手: "Iwate", 宮城: "Miyagi", 秋田: "Akita",
  山形: "Yamagata", 福島: "Fukushima",
  // Chubu / Kinki
  愛知: "Aichi", 静岡: "Shizuoka", 岐阜: "Gifu", 長野: "Nagano",
  新潟: "Niigata", 富山: "Toyama", 石川: "Ishikawa", 福井: "Fukui",
  大阪: "Osaka", 京都: "Kyoto", 兵庫: "Hyogo", 奈良: "Nara",
  滋賀: "Shiga", 和歌山: "Wakayama", 三重: "Mie",
  // Chugoku / Kyushu / Shikoku
  広島: "Hiroshima", 岡山: "Okayama", 鳥取: "Tottori", 島根: "Shimane", 山口: "Yamaguchi",
  福岡: "Fukuoka", 佐賀: "Saga", 長崎: "Nagasaki", 熊本: "Kumamoto",
  大分: "Oita", 宮崎: "Miyazaki", 鹿児島: "Kagoshima", 沖縄: "Okinawa",
  高知: "Kochi", 愛媛: "Ehime", 徳島: "Tokushima", 香川: "Kagawa",
  // Taiwan
  台北: "Taipei", 新北: "New Taipei", 桃園: "Taoyuan", 台中: "Taichung", 台南: "Tainan", 高雄: "Kaohsiung",
  基隆: "Keelung", 新竹: "Hsinchu", 苗栗: "Miaoli", 彰化: "Changhua", 南投: "Nantou", 雲林: "Yunlin",
  嘉義: "Chiayi", 屏東: "Pingtung", 宜蘭: "Yilan", 花蓮: "Hualien", 台東: "Taitung", 澎湖: "Penghu",
  金門: "Kinmen", 連江: "Lienchiang", 臺北: "Taipei", 臺中: "Taichung", 臺南: "Tainan", 臺東: "Taitung",
};

/**
 * Client-side post-filter helper.
 *
 * city === CITY_OTHER → event matches the region but does NOT match
 *   any specific named prefecture in that region.
 * city is a prefecture string → event matches that prefecture.
 *
 * Returns true if the event should be included.
 */
export function matchesCity(
  city: string,
  address: string | null | undefined,
  prefectures: string[] | null | undefined,
  region: RegionWithCity,
): boolean {
  const addr = address ?? "";
  const prefs = prefectures ?? [];
  const regionPrefs = REGION_PREFECTURES[region];

  if (city === CITY_OTHER) {
    // Include if region matches but NO specific prefecture matches
    return !regionPrefs.some((p) => prefs.includes(p) || addr.includes(p));
  }
  // Include if the chosen prefecture appears in prefectures array or address
  return prefs.includes(city) || addr.includes(city);
}
