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
  music: "🎵",
  exhibition: "🖼️",
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

export default async function Image({
  params,
}: {
  params: { locale: Locale; id: string };
}) {
  const { locale, id } = params;

  // --- Load CJK font (Noto Sans JP subset) for Chinese/Japanese rendering ---
  // Fetch only the characters needed to avoid large payloads.
  // Falls back gracefully if unavailable (characters may render as boxes).
  let fontData: ArrayBuffer | null = null;
  try {
    const res = await fetch(
      "https://fonts.gstatic.com/s/notosansjp/v53/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFBEi75vY0rw-oME.woff2",
      { next: { revalidate: 86400 } }
    );
    if (res.ok) fontData = await res.arrayBuffer();
  } catch {
    // font load failure is non-fatal
  }

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

  const truncatedName = name.length > 40 ? name.slice(0, 38) + "…" : name;
  const fontSize = name.length > 25 ? 52 : 68;

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
          fontFamily: fontData ? "NotoSansJP" : "sans-serif",
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
              fontSize: "72px",
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
        ? [{ name: "NotoSansJP", data: fontData, weight: 700, style: "normal" }]
        : [],
    }
  );
}
