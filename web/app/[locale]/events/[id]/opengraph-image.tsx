import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale, type Event, getEventName } from "@/lib/types";
import { satoriTokens } from "@/lib/design/tokens";

// Brand colors
const c = satoriTokens.color;
const MOCHA  = c.primitive.cocoa;     // #3A261F
const FOREST = c.primitive.greenDeep; // #1F5E2B

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// ── Deterministic PRNG (mirrors CategoryThumbnail.tsx) ──────────────────────
function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Palette (mirrors CategoryThumbnail.tsx) ──────────────────────────────────
const PALETTES = [
  { bg: "#FFE9DD", fg: "#E84860", accent: "#1F5E2B" },
  { bg: "#E8F6D6", fg: "#1F5E2B", accent: "#E84860" },
  { bg: "#FFF1C2", fg: "#C9A227", accent: "#3A261F" },
  { bg: "#FFD9D0", fg: "#F47A86", accent: "#3A261F" },
  { bg: "#E0EBFF", fg: "#3B5BA9", accent: "#E84860" },
  { bg: "#FFE0EF", fg: "#D85862", accent: "#1F5E2B" },
  { bg: "#F0E6FF", fg: "#7B4FB8", accent: "#C9A227" },
  { bg: "#D6F0EA", fg: "#2C8A7A", accent: "#E84860" },
];

// ── Category display labels ──────────────────────────────────────────────────
const CATEGORY_LABEL: Record<string, string> = {
  movie: "FILM", performing_arts: "LIVE", art: "ART",
  senses: "FOOD", lifestyle_food: "FOOD", lecture: "TALK",
  academic: "ACAD", books_media: "BOOK", taiwan_japan: "TWNJ",
  retail: "SHOP", nature: "ECO", tech: "TECH",
  tourism: "TOUR", gender: "GNDR", geopolitics: "INTL",
  competition: "COMP", business: "BIZ", report: "NEWS",
};

function getCategoryLabel(cats: string[]): string {
  for (const cat of cats) if (CATEGORY_LABEL[cat]) return CATEGORY_LABEL[cat];
  return "EVENT";
}

function formatDate(dateStr: string | null, locale: string): string {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
}

// ── Font loader ──────────────────────────────────────────────────────────────
async function loadFont(text: string): Promise<ArrayBuffer | null> {
  const family = "Zen+Maru+Gothic:wght@700";
  const url = `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(text)}&display=swap`;
  try {
    const css = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17" },
    }).then((r) => r.text());
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);
    if (!match) return null;
    const fontRes = await fetch(match[1]);
    return fontRes.ok ? fontRes.arrayBuffer() : null;
  } catch { return null; }
}

// ── Motifs (inline JSX for Satori, mirrors CategoryThumbnail.tsx) ────────────
// Drawn in a 100×100 viewBox; SVG element sized 520×520 for display.
function renderMotif(cat: string, fg: string, accent: string): React.ReactNode {
  switch (cat) {
    case "movie":
      return <g><rect x="20" y="30" width="60" height="40" fill={fg} /><rect x="20" y="30" width="60" height="6" fill={accent} /><rect x="20" y="64" width="60" height="6" fill={accent} /><circle cx="50" cy="50" r="8" fill="#fff" /></g>;
    case "performing_arts":
      return <g><circle cx="50" cy="50" r="28" fill={fg} /><circle cx="50" cy="50" r="18" fill={accent} /><circle cx="50" cy="50" r="6" fill="#fff" /></g>;
    case "art":
      return <g><polygon points="50,22 78,70 22,70" fill={fg} /><circle cx="50" cy="60" r="10" fill={accent} /></g>;
    case "senses": case "lifestyle_food":
      return <g><path d="M 18 50 Q 30 30 42 50 T 66 50 T 82 50" stroke={fg} strokeWidth="5" fill="none" strokeLinecap="round" /><path d="M 18 62 Q 30 42 42 62 T 66 62 T 82 62" stroke={accent} strokeWidth="5" fill="none" strokeLinecap="round" /></g>;
    case "lecture":
      return <g><rect x="28" y="32" width="44" height="32" fill={fg} /><rect x="32" y="36" width="36" height="4" fill={accent} /><rect x="32" y="44" width="28" height="4" fill={accent} /><rect x="32" y="52" width="32" height="4" fill={accent} /></g>;
    case "academic":
      return <g><polygon points="50,20 80,40 50,60 20,40" fill={fg} /><line x1="50" y1="60" x2="50" y2="76" stroke={accent} strokeWidth="3" /><circle cx="78" cy="48" r="3" fill={accent} /></g>;
    case "books_media":
      return <g><path d="M 22 28 L 50 36 L 78 28 L 78 70 L 50 78 L 22 70 Z" fill={fg} /><line x1="50" y1="36" x2="50" y2="78" stroke={accent} strokeWidth="3" /></g>;
    case "taiwan_japan":
      return <g><circle cx="36" cy="50" r="14" fill={fg} /><circle cx="64" cy="50" r="14" fill={accent} /></g>;
    case "retail":
      return <g><rect x="28" y="38" width="44" height="36" fill={fg} /><path d="M 38 38 Q 38 26 50 26 Q 62 26 62 38" stroke={accent} strokeWidth="3" fill="none" /></g>;
    case "nature":
      return <g><path d="M 30 70 Q 40 30 60 40 Q 70 50 50 70 Z" fill={fg} /><path d="M 50 70 L 50 40" stroke={accent} strokeWidth="2" /></g>;
    case "tech":
      return <g><rect x="26" y="30" width="48" height="36" fill={fg} /><rect x="32" y="36" width="36" height="24" fill={accent} /><rect x="40" y="66" width="20" height="6" fill={fg} /></g>;
    case "tourism":
      return <g><path d="M 24 70 L 24 44 Q 24 28 50 28 Q 76 28 76 44 L 76 70 Z" fill={fg} /><rect x="44" y="50" width="12" height="20" fill={accent} /></g>;
    case "gender":
      return <g><circle cx="38" cy="44" r="14" fill="none" stroke={fg} strokeWidth="4" /><circle cx="62" cy="56" r="14" fill="none" stroke={accent} strokeWidth="4" /></g>;
    case "geopolitics":
      return <g><circle cx="50" cy="50" r="28" fill="none" stroke={fg} strokeWidth="3" /><ellipse cx="50" cy="50" rx="28" ry="10" fill="none" stroke={accent} strokeWidth="2" /><line x1="22" y1="50" x2="78" y2="50" stroke={accent} strokeWidth="2" /></g>;
    case "competition":
      return <g><polygon points="50,18 60,38 82,42 66,58 70,80 50,68 30,80 34,58 18,42 40,38" fill={fg} /><circle cx="50" cy="48" r="6" fill={accent} /></g>;
    case "business":
      return <g><rect x="22" y="56" width="12" height="20" fill={fg} /><rect x="40" y="44" width="12" height="32" fill={accent} /><rect x="58" y="32" width="12" height="44" fill={fg} /><polyline points="22,46 40,38 58,28 76,18" stroke={accent} strokeWidth="2.5" fill="none" /></g>;
    case "report":
      return <g><rect x="26" y="22" width="48" height="56" fill={fg} /><line x1="34" y1="36" x2="66" y2="36" stroke={accent} strokeWidth="2" /><line x1="34" y1="46" x2="66" y2="46" stroke={accent} strokeWidth="2" /><line x1="34" y1="56" x2="58" y2="56" stroke={accent} strokeWidth="2" /></g>;
    default:
      return <g><circle cx="40" cy="46" r="20" fill={fg} /><rect x="48" y="38" width="28" height="28" fill={accent} /></g>;
  }
}

// ── OG Image ─────────────────────────────────────────────────────────────────
export default async function Image({ params }: { params: Promise<{ locale: Locale; id: string }> }) {
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
  const cats: string[] = event?.category ?? [];
  const primaryCat = cats[0] ?? "";
  const secondaryCat = cats[1] ?? "";
  const categoryLabel = cats.length ? getCategoryLabel(cats) : "EVENT";
  const dateStr = event ? formatDate(event.start_date, locale) : "";
  const location = locale === "zh"
    ? (event?.location_name_zh ?? event?.location_name ?? "")
    : (event?.location_name ?? "");

  // Palette — same algorithm as CategoryThumbnail
  const paletteIdx = (hashString((primaryCat || "x") + ":" + (secondaryCat || "y")) + cats.length) % PALETTES.length;
  const palette = PALETTES[paletteIdx];
  const accentColor = secondaryCat
    ? PALETTES[hashString(secondaryCat) % PALETTES.length].fg
    : palette.accent;

  // Background pattern
  const rand = mulberry32(hashString(id || "default"));
  const bgKinds = ["halftoneDense", "halftoneSparse", "stripes", "grid", "wavy", "checker"] as const;
  type BgKind = typeof bgKinds[number];
  const bgKind: BgKind = bgKinds[Math.floor(rand() * bgKinds.length)];
  const patRotation = Math.floor(rand() * 90) - 45;
  const bgPatColor = rand() > 0.5 ? palette.fg : palette.accent;

  // Motif transform
  const motifRotate = Math.floor(rand() * 24) - 12;
  const motifOffsetX = Math.floor(rand() * 8) - 4;
  const motifOffsetY = Math.floor(rand() * 8) - 4;

  // Corner accent
  const cornerShape = Math.floor(rand() * 4);
  const cornerOpacity = 0.55 + rand() * 0.25;

  // Text
  const truncatedName = name.length > 42 ? name.slice(0, 40) + "…" : name;
  const titleSize = name.length > 28 ? 54 : name.length > 18 ? 68 : 82;

  const textToLoad = truncatedName + (dateStr ?? "") + (location ?? "") + "Tokyo Taiwan Radar" + categoryLabel;
  const fontData = await loadFont(textToLoad);
  const fontName = "Zen Maru Gothic";
  const FF = fontData ? fontName : "sans-serif";

  // Pattern defs (scaled up 12× from 100px viewBox)
  function patternDef(kind: BgKind, color: string, rot: number) {
    switch (kind) {
      case "halftoneDense":
        return <pattern id="ogpat" width="96" height="96" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><circle cx="48" cy="48" r="20" fill={color} /></pattern>;
      case "halftoneSparse":
        return <pattern id="ogpat" width="168" height="168" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><circle cx="84" cy="84" r="14" fill={color} /></pattern>;
      case "stripes":
        return <pattern id="ogpat" width="120" height="120" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><line x1="0" y1="0" x2="0" y2="120" stroke={color} strokeWidth="42" /></pattern>;
      case "grid":
        return <pattern id="ogpat" width="144" height="144" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><path d="M 144 0 L 0 0 0 144" stroke={color} strokeWidth="9.6" fill="none" /></pattern>;
      case "wavy":
        return <pattern id="ogpat" width="240" height="120" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><path d="M 0 60 Q 60 0 120 60 T 240 60" stroke={color} strokeWidth="16.8" fill="none" /></pattern>;
      case "checker":
        return <pattern id="ogpat" width="168" height="168" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><rect width="84" height="84" fill={color} /><rect x="84" y="84" width="84" height="84" fill={color} /></pattern>;
    }
  }

  return new ImageResponse(
    (
      <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", background: palette.bg }}>

        {/* Background pattern — full bleed */}
        <svg style={{ position: "absolute", top: 0, left: 0 }} width="1200" height="630" viewBox="0 0 1200 630">
          <defs>{patternDef(bgKind, bgPatColor, patRotation)}</defs>
          <rect width="1200" height="630" fill="url(#ogpat)" opacity="0.35" />
        </svg>

        {/* Corner accent */}
        <svg style={{ position: "absolute", top: 0, left: 0 }} width="1200" height="630" viewBox="0 0 1200 630">
          {cornerShape === 0 && <circle cx="1100" cy="90" r="150" fill={palette.accent} opacity={cornerOpacity} />}
          {cornerShape === 1 && <polygon points="1200,0 1200,280 920,0" fill={palette.accent} opacity={cornerOpacity} />}
          {cornerShape === 2 && <rect x="880" y="370" width="420" height="420" fill={palette.fg} opacity={cornerOpacity * 0.6} transform="rotate(20 1090 490)" />}
          {cornerShape === 3 && <path d="M 0 630 Q 240 420 480 630 Z" fill={palette.accent} opacity={cornerOpacity * 0.7} />}
        </svg>

        {/* Category motif — right side, large */}
        <svg style={{ position: "absolute", top: 50, right: 60 }} width="480" height="480" viewBox="0 0 100 100">
          <g transform={`translate(${motifOffsetX} ${motifOffsetY}) rotate(${motifRotate} 50 50)`}>
            {renderMotif(primaryCat, palette.fg, accentColor)}
          </g>
        </svg>

        {/* Left text block — full height, no cream panel */}
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
            padding: "52px 64px 52px 72px",
          }}
        >
          {/* Category badge */}
          <div style={{ display: "flex" }}>
            <div style={{ display: "flex", background: palette.fg, borderRadius: "8px", padding: "6px 20px" }}>
              <span style={{ fontSize: "20px", fontWeight: "bold", color: "white", letterSpacing: "2.5px", fontFamily: FF }}>
                {categoryLabel}
              </span>
            </div>
          </div>

          {/* Event title */}
          <span style={{ fontSize: `${titleSize}px`, fontWeight: "bold", color: MOCHA, lineHeight: 1.25, fontFamily: FF }}>
            {truncatedName}
          </span>

          {/* Date + venue + brand */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: "40px" }}>
              {dateStr && (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: "13px", fontWeight: "bold", color: FOREST, letterSpacing: "2px", marginBottom: "4px" }}>DATE</span>
                  <span style={{ fontSize: "28px", fontWeight: "bold", color: MOCHA, fontFamily: FF }}>{dateStr}</span>
                </div>
              )}
              {location && (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: "13px", fontWeight: "bold", color: FOREST, letterSpacing: "2px", marginBottom: "4px" }}>VENUE</span>
                  <span style={{ fontSize: "28px", fontWeight: "bold", color: MOCHA, fontFamily: FF }}>{location}</span>
                </div>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
              {/* Wax-apple mascot — 蓮霧 */}
              <svg width="64" height="70" viewBox="0 0 200 220">
                <g transform="rotate(3 100 150)">
                  <path d="M100,80 C110,30 60,0 80,20 C100,40 140,50 160,30" fill="none" stroke={FOREST} strokeWidth="4.5" strokeLinecap="round" />
                  <circle cx="164" cy="26" r="11" fill="none" stroke={FOREST} strokeWidth="1.4" opacity="0.4" />
                  <circle cx="164" cy="26" r="6" fill={FOREST} />
                  <circle cx="164" cy="26" r="2.2" fill="#C4E86F" />
                  <path d="M100,80 C 86,80 78,88 74,98 C 72,108 66,116 60,128 C 46,146 30,166 36,190 C 44,210 72,216 102,216 C 132,216 160,210 164,190 C 170,166 154,146 140,128 C 134,116 128,108 126,98 C 122,88 114,80 100,80 Z" fill={palette.fg} />
                  <ellipse cx="58" cy="142" rx="13.3" ry="8" fill="#FF7AA0" opacity="0.65" transform="rotate(-10 58 142)" />
                  <ellipse cx="146" cy="150" rx="12" ry="6.5" fill="#FF7AA0" opacity="0.75" transform="rotate(12 146 150)" />
                  <ellipse cx="80" cy="116" rx="13" ry="14" fill="white" />
                  <circle cx="78" cy="118" r="7" fill="#1A1818" />
                  <circle cx="75" cy="115" r="2.6" fill="white" />
                  <path d="M116,128 Q124,118 132,128" fill="none" stroke="#1A1818" strokeWidth="4.5" strokeLinecap="round" />
                </g>
              </svg>
              <span style={{ fontSize: "15px", fontWeight: "bold", color: MOCHA, fontFamily: FF, opacity: 0.6 }}>
                Tokyo Taiwan Radar
              </span>
            </div>
          </div>
        </div>

        {/* Bottom accent bar */}
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "8px", background: palette.fg, display: "flex" }} />
      </div>
    ),
    {
      ...size,
      fonts: fontData ? [{ name: fontName, data: fontData, weight: 700, style: "normal" }] : [],
    }
  );
}
