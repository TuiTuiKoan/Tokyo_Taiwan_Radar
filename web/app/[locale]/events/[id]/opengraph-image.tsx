import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale, type Event, getEventName } from "@/lib/types";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CATEGORY_LABEL: Record<string, string> = {
  movie: "FILM",
  performing_arts: "LIVE",
  art: "ART",
  senses: "FOOD",
  lifestyle_food: "FOOD",
  lecture: "TALK",
  academic: "ACAD",
  books_media: "BOOK",
  taiwan_japan: "TWNJ",
  exhibition: "EXPO",
  drama: "DRAM",
  retail: "SHOP",
  nature: "ECO",
  tech: "TECH",
  tourism: "TOUR",
  gender: "GNDR",
  geopolitics: "INTL",
  competition: "COMP",
  workshop: "WKSP",
  literature: "LIT",
  indigenous: "INDIG",
  history: "HIST",
  urban: "ARCH",
  business: "BIZ",
  taiwan_mandarin: "LANG",
  tv_program: "TV",
  report: "NEWS",
};

function getCategoryLabel(categories: string[]): string {
  for (const cat of categories) {
    if (CATEGORY_LABEL[cat]) return CATEGORY_LABEL[cat];
  }
  return "EVENT";
}

function formatDate(dateStr: string | null, locale: string): string {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

async function loadFont(text: string, locale: string): Promise<ArrayBuffer | null> {
  const family = locale === "ja" ? "Noto+Sans+JP:wght@700" : "Noto+Sans+TC:wght@700";
  const url = `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(text)}&display=swap`;

  try {
    const css = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17",
      },
    }).then((r) => r.text());

    // Extract src URL — Chrome 24 UA forces Google Fonts to return woff1 (supported by Satori) instead of woff2
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);
    if (!match) return null;

    const fontRes = await fetch(match[1]);
    return fontRes.ok ? fontRes.arrayBuffer() : null;
  } catch {
    return null;
  }
}

// Yushan (3952 m) east-west ridge — extracted from real elevation data (top5_profiles.npz)
// Algorithm: contiguous segment above 2000m floor, gaussian smooth σ=0.6, cosine-tapered endpoints
// Mapped to OG canvas (1200x630): baseline y=490, peak y≈344, x range 680-1130
const YUSHAN_POINTS =
  "680,490 690,483 701,457 711,448 722,457 732,456 743,465 753,457 " +
  "764,453 774,432 785,436 795,434 806,447 816,448 827,459 837,429 " +
  "847,422 858,407 868,374 879,380 889,389 900,356 910,344 921,348 " +
  "931,370 942,385 952,411 963,434 973,430 983,418 994,426 1004,419 " +
  "1015,385 1025,364 1036,367 1046,387 1057,404 1067,428 1078,450 1088,440 " +
  "1099,430 1109,453 1120,478 1130,490";

export default async function Image({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { locale, id } = await params;

  // --- Fetch event data ---
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data: event } = await supabase
    .from("events")
    .select("name_ja, name_zh, name_en, start_date, end_date, category, location_name, location_name_zh, is_paid")
    .eq("id", id)
    .single();

  const name = event ? getEventName(event as Event, locale) ?? event.name_ja ?? "Event" : "Event";
  const categoryLabel = event?.category ? getCategoryLabel(event.category) : "EVENT";
  const dateStr = event ? formatDate(event.start_date, locale) : "";
  const location = locale === "zh"
    ? (event?.location_name_zh ?? event?.location_name ?? "")
    : (event?.location_name ?? "");

  const truncatedName = name.length > 36 ? name.slice(0, 34) + "…" : name;
  const fontSize = name.length > 22 ? 54 : 72;

  // --- Load bold CJK font subset for the actual text ---
  const textToLoad = truncatedName + (dateStr ?? "") + (location ?? "") + "Tokyo Taiwan Radar";
  const fontData = await loadFont(textToLoad, locale);
  const fontName = locale === "ja" ? "NotoSansJP" : "NotoSansTC";

  return new ImageResponse(
    (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          background: "#0E3B23",
          display: "flex",
        }}
      >
        {/* Scan lines + Yushan waveform layer — behind content */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "1200px",
            height: "630px",
            display: "flex",
          }}
        >
          <svg width="1200" height="630" viewBox="0 0 1200 630">
            {Array.from({ length: 100 }, (_, i) => (
              <line
                key={i}
                x1="0"
                y1={i * 630 / 99}
                x2="1200"
                y2={i * 630 / 99}
                stroke="white"
                strokeWidth="0.7"
                strokeOpacity="0.32"
              />
            ))}
            <polyline
              points={YUSHAN_POINTS}
              fill="none"
              stroke="white"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Content layer */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: "52px 64px",
            color: "white",
            fontFamily: fontData ? fontName : "sans-serif",
          }}
        >
          {/* Brand */}
          <div style={{ display: "flex", alignItems: "center" }}>
            <div
              style={{
                fontSize: "22px",
                fontWeight: "bold",
                letterSpacing: "0.5px",
              }}
            >
              Tokyo Taiwan Radar
            </div>
          </div>

          {/* Category + Title */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "18px",
              maxWidth: "860px",
            }}
          >
            <div
              style={{
                display: "flex",
                border: "1.5px solid rgba(255,255,255,0.5)",
                borderRadius: "6px",
                padding: "5px 14px",
                alignSelf: "flex-start",
                fontSize: "17px",
                fontWeight: "bold",
                letterSpacing: "1.5px",
                color: "rgba(255,255,255,0.85)",
              }}
            >
              {categoryLabel}
            </div>
            <div
              style={{
                fontSize: `${fontSize}px`,
                fontWeight: "bold",
                lineHeight: 1.2,
              }}
            >
              {truncatedName}
            </div>
          </div>

          {/* Date + Location */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: "40px",
              maxWidth: "700px",
            }}
          >
            {dateStr && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    letterSpacing: "1.5px",
                    color: "rgba(255,255,255,0.5)",
                    fontWeight: "bold",
                  }}
                >
                  DATE
                </span>
                <span style={{ fontSize: "21px" }}>{dateStr}</span>
              </div>
            )}
            {location && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    letterSpacing: "1.5px",
                    color: "rgba(255,255,255,0.5)",
                    fontWeight: "bold",
                  }}
                >
                  VENUE
                </span>
                <span style={{ fontSize: "21px" }}>{location}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fontData
        ? [{ name: fontName, data: fontData, weight: 700, style: "normal" }]
        : [],
    }
  );
}
