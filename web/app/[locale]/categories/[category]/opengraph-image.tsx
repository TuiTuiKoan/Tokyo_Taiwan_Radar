import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale, CATEGORIES } from "@/lib/types";
import { getSemanticSymbol } from "@/lib/design/organicMotifs";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CATEGORY_LABELS: Record<string, Record<string, string>> = {
  zh: {
    movie: "電影", performing_arts: "表演藝術", art: "藝術", senses: "感官體驗",
    lifestyle_food: "生活飲食", lecture: "演講", academic: "學術", books_media: "書籍媒體",
    taiwan_japan: "台日交流", retail: "零售", nature: "自然", tech: "科技",
    tourism: "觀光", gender: "性別", geopolitics: "地緣政治", competition: "競賽",
    business: "商業", report: "報導",
  },
  en: {
    movie: "Film", performing_arts: "Performing Arts", art: "Art", senses: "Senses",
    lifestyle_food: "Food & Lifestyle", lecture: "Lecture", academic: "Academic",
    books_media: "Books & Media", taiwan_japan: "Taiwan-Japan", retail: "Retail",
    nature: "Nature", tech: "Tech", tourism: "Tourism", gender: "Gender",
    geopolitics: "Geopolitics", competition: "Competition", business: "Business",
    report: "Report",
  },
  ja: {
    movie: "映画", performing_arts: "舞台芸術", art: "アート", senses: "体験",
    lifestyle_food: "グルメ", lecture: "講演", academic: "学術", books_media: "書籍",
    taiwan_japan: "台日交流", retail: "ショップ", nature: "自然", tech: "テック",
    tourism: "観光", gender: "ジェンダー", geopolitics: "国際", competition: "コンペ",
    business: "ビジネス", report: "ニュース",
  },
};

const SITE_TITLES: Record<string, string> = {
  zh: "東京台灣雷達",
  en: "Tokyo Taiwan Radar",
  ja: "東京台湾レーダー",
};

// Yushan ridge polyline (shared with events OG)
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
  params: Promise<{ locale: Locale; category: string }>;
}) {
  const { locale, category } = await params;

  if (!CATEGORIES.includes(category as any)) {
    return new Response("Not found", { status: 404 });
  }

  const label = CATEGORY_LABELS[locale]?.[category] ?? category;
  const siteName = SITE_TITLES[locale] ?? "Tokyo Taiwan Radar";

  // Count active events in this category
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
  const { count } = await supabase
    .from("events")
    .select("id", { count: "exact", head: true })
    .eq("is_active", true)
    .is("parent_event_id", null)
    .contains("category", [category]);

  const eventCount = count ?? 0;

  const countText: Record<string, string> = {
    zh: `${eventCount} 場活動`,
    en: `${eventCount} events`,
    ja: `${eventCount} 件のイベント`,
  };

  const allText = `${siteName}${label}${countText[locale] ?? ""}Tokyo Taiwan Radar`;
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

        {/* Category motif decoration — top-right, above Yushan ridge */}
        <div
          style={{
            position: "absolute",
            right: "80px",
            top: "90px",
            width: "256px",
            height: "256px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: 0.8,
          }}
        >
          <svg width="240" height="240" viewBox="0 0 100 100">
            {getSemanticSymbol(category, 0, "#C4E86F", "#E84860")}
          </svg>
        </div>

        {/* Content */}
        <div style={{
          position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
          display: "flex", flexDirection: "column", justifyContent: "flex-start",
          padding: "52px 64px", color: "white",
          fontFamily: fontData ? fontName : "sans-serif",
        }}>
          {/* Brand */}
          <div style={{ display: "flex", fontSize: "33px", fontWeight: "bold", letterSpacing: "0.5px" }}>
            Tokyo Taiwan Radar
          </div>

          {/* Category label */}
          <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "64px" }}>
            <div style={{
              display: "flex", border: "1.5px solid white", borderRadius: "6px",
              padding: "5px 14px", alignSelf: "flex-start",
              fontSize: "17px", fontWeight: "bold", letterSpacing: "1.5px",
            }}>
              CATEGORY
            </div>
            <div style={{ fontSize: "72px", fontWeight: "bold", lineHeight: 1.15 }}>
              {label}
            </div>
          </div>

          {/* Event count + site name */}
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
