import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale, type Event, getEventName } from "@/lib/types";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CATEGORY_EMOJI: Record<string, string> = {
  movie: "🎬",
  performing_arts: "🎭",
  art: "🎨",
  senses: "🍜",
  lifestyle_food: "🍜",
  lecture: "🎤",
  academic: "📚",
  books_media: "📖",
  taiwan_japan: "🤝",
  exhibition: "🖼️",
  drama: "📺",
  retail: "🛍️",
  nature: "🌿",
  tech: "💻",
  tourism: "✈️",
  gender: "🏳️‍🌈",
  geopolitics: "🌏",
  competition: "🏆",
  workshop: "🛠️",
  literature: "✍️",
  indigenous: "🌺",
  history: "🏛️",
  urban: "🏙️",
  business: "💼",
  taiwan_mandarin: "🗣️",
  tv_program: "📺",
  report: "📰",
};

function getCategoryEmoji(categories: string[]): string {
  for (const cat of categories) {
    if (CATEGORY_EMOJI[cat]) return CATEGORY_EMOJI[cat];
  }
  return "📌";
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
      headers: { "User-Agent": "Mozilla/5.0" },
    }).then((r) => r.text());

    // Extract first woff2 src URL from CSS
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+\.woff2)\)/);
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
  params: { locale: Locale; id: string };
}) {
  const { locale, id } = params;

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
  const emoji = event?.category ? getCategoryEmoji(event.category) : "📌";
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
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "linear-gradient(145deg, #f0fdf4 0%, #e8f5e9 60%, #dcfce7 100%)",
          padding: "56px 64px",
          justifyContent: "space-between",
          fontFamily: fontData ? fontName : "sans-serif",
        }}
      >
        {/* Top bar — branding */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              background: "#16a34a",
              borderRadius: "10px",
              padding: "8px 20px",
              color: "white",
              fontSize: "20px",
              fontWeight: "bold",
              letterSpacing: "-0.3px",
            }}
          >
            🇹🇼 Tokyo Taiwan Radar
          </div>
          {event?.is_paid === false && (
            <div
              style={{
                background: "#dbeafe",
                borderRadius: "8px",
                padding: "6px 14px",
                color: "#1d4ed8",
                fontSize: "16px",
                fontWeight: "bold",
              }}
            >
              FREE
            </div>
          )}
        </div>

        {/* Event name — main content */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "20px",
            maxWidth: "1060px",
          }}
        >
          <div
            style={{
              fontSize: "80px",
              lineHeight: 1,
              flexShrink: 0,
              marginTop: "4px",
            }}
          >
            {emoji}
          </div>
          <div
            style={{
              fontSize: `${fontSize}px`,
              fontWeight: "bold",
              color: "#111827",
              lineHeight: 1.25,
            }}
          >
            {truncatedName}
          </div>
        </div>

        {/* Bottom bar — date + location */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "32px",
            borderTop: "2px solid #bbf7d0",
            paddingTop: "20px",
          }}
        >
          {dateStr && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: "#374151",
                fontSize: "22px",
              }}
            >
              <span style={{ fontSize: "24px" }}>📅</span>
              <span>{dateStr}</span>
            </div>
          )}
          {location && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: "#374151",
                fontSize: "22px",
              }}
            >
              <span style={{ fontSize: "24px" }}>📍</span>
              <span>{location}</span>
            </div>
          )}
          <div style={{ flex: 1 }} />
          <div style={{ color: "#9ca3af", fontSize: "18px" }}>
            tokyo-taiwan-radar.vercel.app
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
