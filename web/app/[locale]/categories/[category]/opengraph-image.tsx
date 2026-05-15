import { ImageResponse } from "next/og";
import { type Locale, CATEGORIES } from "@/lib/types";
import { getSemanticSymbol, getRandomCollageBase } from "@/lib/design/organicMotifs";

export const runtime = "edge";
export const size = { width: 1200, height: 1200 };
export const contentType = "image/png";

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

function hashForId(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

type Pal = { bg: string; fg: string; accent: string };

function bgDots(fg: string) {
  const STEP = 72;
  const N = 18;
  const els = [];
  for (let r = 0; r < N; r++) {
    for (let c = 0; c < N; c++) {
      els.push(
        <circle key={`${r}-${c}`} cx={c * STEP} cy={r * STEP} r="2.8" fill={fg} style={{ opacity: 0.2 }} />
      );
    }
  }
  return <g>{els}</g>;
}

function motifCell(
  cat: string, v: number, bv: number, p: Pal,
  x: number, y: number, sz: number,
) {
  const s = sz / 100;
  return (
    <g key={`${cat}-${x}`} transform={`translate(${x} ${y}) scale(${s})`}>
      <rect width="100" height="100" fill={p.bg} />
      {getRandomCollageBase(bv, p.fg, p.accent)}
      {getSemanticSymbol(cat, v, p.bg, "#3A261F")}
      <g transform="translate(2 -2) scale(0.98)">
        {getSemanticSymbol(cat, v, p.fg, p.accent)}
      </g>
    </g>
  );
}

export default async function OGImage({
  params,
}: {
  params: Promise<{ locale: Locale; category: string }>;
}) {
  const { category } = await params;

  if (!CATEGORIES.includes(category as any)) {
    return new Response("Not found", { status: 404 });
  }

  const h = hashForId(category);
  const palette = PALETTES[h % PALETTES.length];
  const mv = h % 5;
  const bv = (h >> 4) % 5;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", background: palette.bg, display: "flex" }}>
        <svg width="1200" height="1200" viewBox="0 0 1200 1200">
          {bgDots(palette.fg)}
          {motifCell(category, mv, bv, palette, 150, 150, 900)}
        </svg>
      </div>
    ),
    { ...size }
  );
}
