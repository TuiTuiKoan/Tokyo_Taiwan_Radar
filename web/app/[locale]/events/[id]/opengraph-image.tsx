import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale, type Event, getEventName } from "@/lib/types";
import { satoriTokens } from "@/lib/design/tokens";

// Brand colors — inline from token values (no CSS vars in Edge/Satori)
const c = satoriTokens.color;
const PAPER     = c.primitive.paper;      // #FFFDF5
const BLUSH     = c.primitive.blush;      // #FFF1EE
const MATCHA    = c.primitive.matcha;     // #F7FFE8
const MOCHA     = c.primitive.cocoa;      // #3A261F
const FOREST    = c.primitive.greenDeep;  // #1F5E2B
const RED       = c.brand.primary;        // #E84860
const LEAF      = c.primitive.greenLeaf;  // #C4E86F
const PINK_SOFT = c.primitive.pinkSoft;   // #FF7AA0
const COAL      = c.primitive.coal;       // #1A1818

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

async function loadFont(text: string): Promise<ArrayBuffer | null> {
  // Zen Maru Gothic — brand display font (same as website h1/h2/h3).
  // Chrome 24 UA tricks Google Fonts into returning woff1 (supported by Satori).
  const family = "Zen+Maru+Gothic:wght@700";
  const url = `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(text)}&display=swap`;

  try {
    const css = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17",
      },
    }).then((r) => r.text());

    // Extract src URL — woff1 returned for Chrome 24 UA, which Satori supports
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);
    if (!match) return null;

    const fontRes = await fetch(match[1]);
    return fontRes.ok ? fontRes.arrayBuffer() : null;
  } catch {
    return null;
  }
}

export default async function Image({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { locale, id } = await params;

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

  const truncatedName = name.length > 60 ? name.slice(0, 58) + "…" : name;
  const titleSize = name.length > 30 ? 44 : name.length > 20 ? 56 : 68;

  const textToLoad = truncatedName + (dateStr ?? "") + (location ?? "") + "Tokyo Taiwan Radar" + categoryLabel;
  const fontData = await loadFont(textToLoad);
  const fontName = "Zen Maru Gothic";
  const FF = fontData ? fontName : "sans-serif";

  return new ImageResponse(
    (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          display: "flex",
          background: `linear-gradient(135deg, ${PAPER} 0%, ${BLUSH} 58%, ${MATCHA} 100%)`,
        }}
      >
        {/* Layer 1: gridPink pattern — matches SiteBackground */}
        <svg
          style={{ position: "absolute", top: 0, left: 0 }}
          width="1200"
          height="630"
          viewBox="0 0 1200 630"
        >
          <defs>
            <pattern id="gridOg" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M20,0 L0,0 L0,20" fill="none" stroke="#F56A82" strokeWidth="1.6" opacity="0.25" />
            </pattern>
          </defs>
          <rect width="1200" height="630" fill="url(#gridOg)" opacity="0.6" />
        </svg>

        {/* Layer 2: Bauhaus geometric accents */}
        <svg
          style={{ position: "absolute", top: 0, left: 0 }}
          width="1200"
          height="630"
          viewBox="0 0 1200 630"
        >
          {/* Leaf-green circle glow — top-right behind mascot */}
          <circle cx="1050" cy="130" r="200" fill={LEAF} opacity="0.18" />
          {/* Red arc quarter-circle — bottom-right */}
          <path d="M1200,630 A220,220 0 0,0 980,630 Z" fill={RED} opacity="0.10" />
          {/* Mocha triangle — bottom-left */}
          <polygon points="0,490 90,630 0,630" fill={MOCHA} opacity="0.07" />
          {/* Bauhaus accent: small red square top-left */}
          <rect x="52" y="52" width="14" height="14" fill={RED} />
        </svg>

        {/* Layer 3: Mascot (蓮霧 wax-apple) — right side */}
        {/* viewBox "0 0 200 220", scaled to 400×440 */}
        <svg
          style={{ position: "absolute", top: 70, right: 60 }}
          width="400"
          height="440"
          viewBox="0 0 200 220"
        >
          <g transform="rotate(3 100 150)">
            {/* Stem */}
            <path
              d="M100,80 C110,30 60,0 80,20 C100,40 140,50 160,30"
              fill="none"
              stroke={FOREST}
              strokeWidth="4.5"
              strokeLinecap="round"
            />
            {/* Antenna ball outer ring */}
            <circle cx="164" cy="26" r="11" fill="none" stroke={FOREST} strokeWidth="1.4" opacity="0.4" />
            {/* Antenna ball solid */}
            <circle cx="164" cy="26" r="6" fill={FOREST} />
            {/* Antenna ball highlight */}
            <circle cx="164" cy="26" r="2.2" fill={LEAF} />
            {/* Body */}
            <path
              d="M100,80 C 86,80 78,88 74,98 C 72,108 66,116 60,128 C 46,146 30,166 36,190 C 44,210 72,216 102,216 C 132,216 160,210 164,190 C 170,166 154,146 140,128 C 134,116 128,108 126,98 C 122,88 114,80 100,80 Z"
              fill={RED}
            />
            {/* Cheek left */}
            <ellipse
              cx="58" cy="142" rx="13.3" ry="8"
              fill={PINK_SOFT} opacity="0.65"
              transform="rotate(-10 58 142)"
            />
            {/* Cheek right */}
            <ellipse
              cx="146" cy="150" rx="12" ry="6.5"
              fill={PINK_SOFT} opacity="0.75"
              transform="rotate(12 146 150)"
            />
            {/* Eye white */}
            <ellipse cx="80" cy="116" rx="13" ry="14" fill="white" />
            {/* Pupil */}
            <circle cx="78" cy="118" r="7" fill={COAL} />
            {/* Eye highlight */}
            <circle cx="75" cy="115" r="2.6" fill="white" />
            {/* Smile */}
            <path
              d="M116,128 Q124,118 132,128"
              fill="none"
              stroke={COAL}
              strokeWidth="4.5"
              strokeLinecap="round"
            />
          </g>
        </svg>

        {/* Layer 4: Text content (left column, max 700px) */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "700px",
            height: "630px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: "52px 64px",
          }}
        >
          {/* Brand name */}
          <div style={{ display: "flex" }}>
            <span
              style={{
                fontSize: "22px",
                fontWeight: "bold",
                color: MOCHA,
                fontFamily: FF,
                letterSpacing: "0.3px",
              }}
            >
              Tokyo Taiwan Radar
            </span>
          </div>

          {/* Category badge + event title */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                display: "flex",
                background: RED,
                borderRadius: "6px",
                padding: "5px 14px",
                alignSelf: "flex-start",
                marginBottom: "20px",
              }}
            >
              <span
                style={{
                  fontSize: "14px",
                  fontWeight: "bold",
                  color: "white",
                  letterSpacing: "2px",
                  fontFamily: FF,
                }}
              >
                {categoryLabel}
              </span>
            </div>
            <span
              style={{
                fontSize: `${titleSize}px`,
                fontWeight: "bold",
                color: MOCHA,
                lineHeight: 1.25,
                fontFamily: FF,
              }}
            >
              {truncatedName}
            </span>
          </div>

          {/* Date + Venue */}
          <div style={{ display: "flex", gap: "48px" }}>
            {dateStr && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: "bold",
                    color: FOREST,
                    letterSpacing: "1.8px",
                    marginBottom: "5px",
                  }}
                >
                  DATE
                </span>
                <span
                  style={{
                    fontSize: "28px",
                    fontWeight: "bold",
                    color: MOCHA,
                    fontFamily: FF,
                  }}
                >
                  {dateStr}
                </span>
              </div>
            )}
            {location && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: "bold",
                    color: FOREST,
                    letterSpacing: "1.8px",
                    marginBottom: "5px",
                  }}
                >
                  VENUE
                </span>
                <span
                  style={{
                    fontSize: "28px",
                    fontWeight: "bold",
                    color: MOCHA,
                    fontFamily: FF,
                  }}
                >
                  {location}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Bottom accent bar */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "6px",
            background: RED,
            display: "flex",
          }}
        />
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
