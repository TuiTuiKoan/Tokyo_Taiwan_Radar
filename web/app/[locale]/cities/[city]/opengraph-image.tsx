import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import type { Locale } from "@/lib/types";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CITY_SLUGS = ["tokyo", "osaka", "kyoto", "fukuoka", "sapporo", "nagoya"] as const;
type CitySlug = (typeof CITY_SLUGS)[number];

const CITY_LABELS: Record<CitySlug, Record<string, string>> = {
  tokyo:   { zh: "東京", en: "Tokyo", ja: "東京" },
  osaka:   { zh: "大阪", en: "Osaka", ja: "大阪" },
  kyoto:   { zh: "京都", en: "Kyoto", ja: "京都" },
  fukuoka: { zh: "福岡", en: "Fukuoka", ja: "福岡" },
  sapporo: { zh: "札幌", en: "Sapporo", ja: "札幌" },
  nagoya:  { zh: "名古屋", en: "Nagoya", ja: "名古屋" },
};

const CITY_MARKERS: Record<CitySlug, string[]> = {
  tokyo:   ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区", "台北駐日"],
  osaka:   ["大阪", "梅田", "難波", "なんば", "心斎橋", "天王寺"],
  kyoto:   ["京都"],
  fukuoka: ["福岡", "博多", "天神"],
  sapporo: ["札幌", "北海道"],
  nagoya:  ["名古屋", "愛知"],
};

const SITE_TITLES: Record<string, string> = {
  zh: "東京台灣雷達",
  en: "Tokyo Taiwan Radar",
  ja: "東京台湾レーダー",
};

const YUSHAN_POINTS =
  "680,490 690,483 701,457 711,448 722,457 732,456 743,465 753,457 " +
  "764,453 774,432 785,436 795,434 806,447 816,448 827,459 837,429 " +
  "847,422 858,407 868,374 879,380 889,389 900,356 910,344 921,348 " +
  "931,370 942,385 952,411 963,434 973,430 983,418 994,426 1004,419 " +
  "1015,385 1025,364 1036,367 1046,387 1057,404 1067,428 1078,450 1088,440 " +
  "1099,430 1109,453 1120,478 1130,490";

async function loadFont(text: string): Promise<ArrayBuffer | null> {
  const url = `https://fonts.googleapis.com/css2?family=DotGothic16:wght@400&text=${encodeURIComponent(text)}&display=swap`;
  try {
    const css = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17" },
    }).then((r) => r.text());
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);
    if (!match) return null;
    const fontRes = await fetch(match[1]);
    return fontRes.ok ? fontRes.arrayBuffer() : null;
  } catch {
    return null;
  }
}

export default async function OGImage({
  params,
}: {
  params: Promise<{ locale: Locale; city: string }>;
}) {
  const { locale, city } = await params;

  if (!CITY_SLUGS.includes(city as CitySlug)) {
    return new Response("Not found", { status: 404 });
  }

  const citySlug = city as CitySlug;
  const cityLabel = CITY_LABELS[citySlug][locale] ?? CITY_LABELS[citySlug].en;
  const siteName = SITE_TITLES[locale] ?? "Tokyo Taiwan Radar";
  const markers = CITY_MARKERS[citySlug];

  // Count events matching this city
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );

  const orConditions = markers.map((m) => `location_address.ilike.%${m}%`).join(",");
  const { count } = await supabase
    .from("events")
    .select("id", { count: "exact", head: true })
    .eq("is_active", true)
    .is("parent_event_id", null)
    .or(orConditions);

  const eventCount = count ?? 0;

  const countText: Record<string, string> = {
    zh: `${eventCount} 場活動`,
    en: `${eventCount} events`,
    ja: `${eventCount} 件のイベント`,
  };

  const allText = `${siteName}${cityLabel}${countText[locale] ?? ""}Tokyo Taiwan Radar`;
  const fontData = await loadFont(allText);
  const fontName = "DotGothic16";

  return new ImageResponse(
    (
      <div style={{ position: "relative", width: "100%", height: "100%", background: "#0E3B23", display: "flex" }}>
        {/* Scan lines + Yushan */}
        <div style={{ position: "absolute", top: 0, left: 0, width: "1200px", height: "630px", display: "flex" }}>
          <svg width="1200" height="630" viewBox="0 0 1200 630">
            {Array.from({ length: 50 }, (_, i) => {
              const y = i * 630 / 49;
              if (Math.abs(y - 490) <= 8) return null;
              return <line key={i} x1="0" y1={y} x2="1200" y2={y} stroke="white" strokeWidth="0.7" strokeOpacity="0.32" />;
            })}
            <line x1="0" y1="490" x2="680" y2="490" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <line x1="1130" y1="490" x2="1200" y2="490" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <polyline points={YUSHAN_POINTS} fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        {/* Content */}
        <div style={{
          position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
          display: "flex", flexDirection: "column", justifyContent: "flex-start",
          padding: "52px 64px", color: "white",
          fontFamily: fontData ? fontName : "sans-serif",
        }}>
          <div style={{ display: "flex", fontSize: "33px", fontWeight: "bold", letterSpacing: "0.5px" }}>
            Tokyo Taiwan Radar
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "64px" }}>
            <div style={{
              display: "flex", border: "1.5px solid white", borderRadius: "6px",
              padding: "5px 14px", alignSelf: "flex-start",
              fontSize: "17px", fontWeight: "bold", letterSpacing: "1.5px",
            }}>
              CITY
            </div>
            <div style={{ fontSize: "72px", fontWeight: "bold", lineHeight: 1.15 }}>
              {cityLabel}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "flex-end", gap: "80px", marginTop: "auto" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "16.5px", letterSpacing: "1.5px", fontWeight: "bold" }}>EVENTS</span>
              <span style={{ fontSize: "31.5px", fontWeight: "bold" }}>{countText[locale] ?? `${eventCount} events`}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "16.5px", letterSpacing: "1.5px", fontWeight: "bold" }}>SITE</span>
              <span style={{ fontSize: "31.5px", fontWeight: "bold" }}>{siteName}</span>
            </div>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fontData ? [{ name: fontName, data: fontData, weight: 400, style: "normal" as const }] : [],
    },
  );
}
