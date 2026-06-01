import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { matchesLocation } from "@/lib/locationMarkers";
import { matchesCity, REGIONS_WITH_CITY } from "@/lib/regionPrefectures";
import { buildMonthRange } from "@/lib/analytics/monthlyBuckets";

export const dynamic = "force-dynamic";

type RegionKey =
  | "japan"
  | "taiwan"
  | "east_asia"
  | "southeast_asia"
  | "north_america"
  | "europe"
  | "oceania"
  | "other"
  | "unknown";

const COUNTRY_TO_REGION: Record<string, RegionKey> = {
  JP: "japan",
  TW: "taiwan",
  HK: "east_asia",
  KR: "east_asia",
  SG: "southeast_asia",
  TH: "southeast_asia",
  MY: "southeast_asia",
  ID: "southeast_asia",
  PH: "southeast_asia",
  VN: "southeast_asia",
  US: "north_america",
  CA: "north_america",
  GB: "europe",
  DE: "europe",
  FR: "europe",
  ES: "europe",
  IT: "europe",
  NL: "europe",
  AU: "oceania",
  NZ: "oceania",
};

const ALL_PREFECTURES = [
  "東京",
  "神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨",
  "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
  "愛知", "静岡", "岐阜", "長野", "新潟", "富山", "石川", "福井",
  "大阪", "京都", "兵庫", "奈良", "滋賀", "和歌山", "三重",
  "広島", "岡山", "鳥取", "島根", "山口", "福岡", "佐賀", "長崎", 
  "熊本", "大分", "宮崎", "鹿児島", "沖縄", "高知", "愛媛", "徳島", "香川"
];

const JP_REGION_TO_PREFECTURE: Record<string, string> = {
  "01": "北海道", "02": "青森", "03": "岩手", "04": "宮城", "05": "秋田",
  "06": "山形", "07": "福島", "08": "茨城", "09": "栃木", "10": "群馬",
  "11": "埼玉", "12": "千葉", "13": "東京", "14": "神奈川", "15": "新潟",
  "16": "富山", "17": "石川", "18": "福井", "19": "山梨", "20": "長野",
  "21": "岐阜", "22": "静岡", "23": "愛知", "24": "三重", "25": "滋賀",
  "26": "京都", "27": "大阪", "28": "兵庫", "29": "奈良", "30": "和歌山",
  "31": "鳥取", "32": "島根", "33": "岡山", "34": "広島", "35": "山口",
  "36": "徳島", "37": "香川", "38": "愛媛", "39": "高知", "40": "福岡",
  "41": "佐賀", "42": "長崎", "43": "熊本", "44": "大分", "45": "宮崎",
  "46": "鹿児島", "47": "沖縄",
};

function normalizeCountryCode(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const normalized = raw.trim().toUpperCase().slice(0, 2);
  return /^[A-Z]{2}$/.test(normalized) ? normalized : null;
}

function getRegionKey(countryCode: string | null): RegionKey {
  if (!countryCode) return "unknown";
  return COUNTRY_TO_REGION[countryCode] ?? "other";
}

export async function GET(req: Request) {
  try {
    // Auth check
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const { data: roleRow } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .single();
    if (!roleRow || roleRow.role !== "admin") {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    // Parse URL query params
    const { searchParams } = new URL(req.url);
    const fromMonth = searchParams.get("fromMonth");
    const toMonth = searchParams.get("toMonth");
    const location = searchParams.get("location");
    const city = searchParams.get("city");
    const category = searchParams.get("category");
    const localeParam = searchParams.get("locale");

    if (!fromMonth || !toMonth) {
      return NextResponse.json({ error: "Missing fromMonth or toMonth" }, { status: 400 });
    }

    // Check date format and 24 months limit
    const partsFrom = fromMonth.split("-");
    const partsTo = toMonth.split("-");
    if (partsFrom.length !== 2 || partsTo.length !== 2) {
      return NextResponse.json({ error: "Invalid date format" }, { status: 400 });
    }
    const y1 = parseInt(partsFrom[0], 10);
    const m1 = parseInt(partsFrom[1], 10);
    const y2 = parseInt(partsTo[0], 10);
    const m2 = parseInt(partsTo[1], 10);
    if (isNaN(y1) || isNaN(m1) || isNaN(y2) || isNaN(m2)) {
      return NextResponse.json({ error: "Invalid date format" }, { status: 400 });
    }
    const diff = (y2 - y1) * 12 + (m2 - m1) + 1;
    if (diff > 24) {
      return NextResponse.json({ error: "RangeTooWide" }, { status: 400 });
    }
    if (diff <= 0) {
      return NextResponse.json({ error: "toMonth must be after or equal to fromMonth" }, { status: 400 });
    }

    // Build UTC ISO strings for viewed_at range filtering
    const rangeStart = `${fromMonth}-01T00:00:00.000Z`;
    const lastDay = new Date(Date.UTC(y2, m2, 0)).getUTCDate();
    const rangeEnd = `${toMonth}-${String(lastDay).padStart(2, "0")}T23:59:59.999Z`;

    // Fetch meeting records
    // Loop paging to fetch all records (completely removing limit)
    let views: any[] = [];
    let page = 0;
    const pageSize = 5000;
    let hasMore = true;

    while (hasMore) {
      const { data: pageData, error: fetchErr } = await supabase
        .from("event_views")
        .select("viewed_at, country, country_region, locale, event_id, events(category, location_name, location_address, location_prefectures)")
        .gte("viewed_at", rangeStart)
        .lte("viewed_at", rangeEnd)
        .range(page * pageSize, (page + 1) * pageSize - 1);

      if (fetchErr) {
        return NextResponse.json({ error: fetchErr.message }, { status: 500 });
      }

      if (pageData && pageData.length > 0) {
        views = views.concat(pageData);
        if (pageData.length < pageSize) {
          hasMore = false;
        } else {
          page++;
        }
      } else {
        hasMore = false;
      }
    }

    // Filter server-side
    const filteredViews = views.filter(v => {
      const e = Array.isArray(v.events) ? v.events[0] : v.events;
      if (!e) return false;

      // Location filter (against event locale)
      if (location && location !== "all") {
        if (!matchesLocation(e, location)) return false;
      }

      // City filter
      if (location && REGIONS_WITH_CITY.includes(location as any) && city && city !== "all") {
        if (!matchesCity(city, e.location_address, e.location_prefectures, location as any)) return false;
      }

      // Category filter
      if (category && category !== "all") {
        const cats = (e as any).category;
        if (!cats || !cats.includes(category)) return false;
      }

      // Locale filter (applies exclusively to event_views!)
      if (localeParam && localeParam !== "all") {
        if (v.locale !== localeParam) return false;
      }

      return true;
    });

    const monthsList = buildMonthRange(fromMonth, toMonth);

    // 1. byMonth (monthly views trend)
    const byMonthMap: Record<string, number> = {};
    for (const m of monthsList) {
      byMonthMap[m] = 0;
    }
    for (const v of filteredViews) {
      const yymm = v.viewed_at.substring(0, 7);
      if (yymm in byMonthMap) {
        byMonthMap[yymm]++;
      }
    }
    const byMonth = monthsList.map(m => ({ month: m, count: byMonthMap[m] }));

    // 2. byVisitorRegion
    const visitorRegionMap: Record<string, number> = {
      japan: 0,
      taiwan: 0,
      east_asia: 0,
      southeast_asia: 0,
      north_america: 0,
      europe: 0,
      oceania: 0,
      other: 0,
      unknown: 0,
    };
    for (const v of filteredViews) {
      const code = normalizeCountryCode(v.country);
      const regKey = getRegionKey(code);
      visitorRegionMap[regKey] = (visitorRegionMap[regKey] ?? 0) + 1;
    }
    const byVisitorRegion = Object.entries(visitorRegionMap)
      .map(([region, count]) => ({ region, count }))
      .sort((a, b) => b.count - a.count);

    // 3. byVisitorCountry
    const visitorCountryMap: Record<string, number> = {};
    for (const v of filteredViews) {
      const code = normalizeCountryCode(v.country) ?? "UNKNOWN";
      visitorCountryMap[code] = (visitorCountryMap[code] ?? 0) + 1;
    }
    const byVisitorCountry = Object.entries(visitorCountryMap)
      .map(([country, count]) => ({ country, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    // 3b. byVisitorPrefecture (JP only)
    const visitorPrefMap: Record<string, number> = {};
    for (const v of filteredViews) {
      const code = normalizeCountryCode(v.country);
      if (code !== "JP") continue;
      if (!v.country_region) continue;
      const key = String(v.country_region).padStart(2, "0");
      const pref = JP_REGION_TO_PREFECTURE[key];
      if (!pref) continue;
      visitorPrefMap[pref] = (visitorPrefMap[pref] ?? 0) + 1;
    }
    const byVisitorPrefecture = Object.entries(visitorPrefMap)
      .map(([prefecture, count]) => ({ prefecture, count }))
      .sort((a, b) => b.count - a.count);

    // 4. byEventCategory
    const eventCategoryMap: Record<string, number> = {};
    for (const v of filteredViews) {
      const e = Array.isArray(v.events) ? v.events[0] : v.events;
      if (e) {
        const cats = (e as any).category;
        if (cats) {
          for (const cat of cats) {
            eventCategoryMap[cat] = (eventCategoryMap[cat] ?? 0) + 1;
          }
        }
      }
    }
    const byEventCategory = Object.entries(eventCategoryMap)
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count);

    // 5. byEventPrefecture
    const eventPrefectureMap: Record<string, number> = {};
    for (const v of filteredViews) {
      const e = Array.isArray(v.events) ? v.events[0] : v.events;
      if (!e) continue;
      let foundPref = false;
      if (e.location_prefectures && e.location_prefectures.length > 0) {
        for (const pref of e.location_prefectures) {
          const cleanPref = pref.replace(/(都|府|県)$/, "");
          eventPrefectureMap[cleanPref] = (eventPrefectureMap[cleanPref] ?? 0) + 1;
          foundPref = true;
        }
      }
      if (!foundPref && e.location_address) {
        for (const p of ALL_PREFECTURES) {
          if (e.location_address.includes(p)) {
            eventPrefectureMap[p] = (eventPrefectureMap[p] ?? 0) + 1;
            foundPref = true;
            break;
          }
        }
      }
      if (!foundPref && matchesLocation(e, "tokyo")) {
        eventPrefectureMap["東京"] = (eventPrefectureMap["東京"] ?? 0) + 1;
      }
    }
    const byEventPrefecture = Object.entries(eventPrefectureMap)
      .map(([prefecture, count]) => ({ prefecture, count }))
      .sort((a, b) => b.count - a.count);

    // 6. byLocale
    const localeMap: Record<string, number> = {};
    for (const v of filteredViews) {
      const loc = v.locale ?? "unknown";
      localeMap[loc] = (localeMap[loc] ?? 0) + 1;
    }
    const byLocale = Object.entries(localeMap)
      .map(([locale, count]) => ({ locale, count }))
      .sort((a, b) => b.count - a.count);

    return NextResponse.json({
      byMonth,
      byVisitorRegion,
      byVisitorCountry,
      byVisitorPrefecture,
      byEventCategory,
      byEventPrefecture,
      byLocale,
      byVisitorCity: [],
    });

  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Internal Server Error" }, { status: 500 });
  }
}
