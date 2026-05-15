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

function bgTexture(kind: number, fg: string, angle: number) {
  const v = ((kind % 6) + 6) % 6;
  const els: React.ReactNode[] = [];

  if (v === 0) {
    const S = 100;
    for (let row = -4; row <= 16; row++)
      for (let col = -4; col <= 16; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S} cy={row * S} r={28} fill={fg} />);
  } else if (v === 1) {
    const S = 160;
    for (let row = -3; row <= 11; row++)
      for (let col = -3; col <= 11; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S} cy={row * S} r={18} fill={fg} />);
  } else if (v === 2) {
    for (let i = -12; i <= 30; i++)
      els.push(<rect key={i} x={i * 70} y="-900" width={22} height="3000" fill={fg} />);
  } else if (v === 3) {
    for (let i = -7; i <= 23; i++) {
      els.push(<rect key={`h${i}`} x="-900" y={i * 80} width="3000" height={5} fill={fg} />);
      els.push(<rect key={`v${i}`} x={i * 80} y="-900" width={5} height="3000" fill={fg} />);
    }
  } else if (v === 4) {
    const rS = 80, amp = 22, wl = 120;
    for (let row = -7; row <= 23; row++) {
      const y0 = row * rS;
      let d = `M -900 ${y0}`;
      for (let x = -900; x < 2100; x += wl) {
        d += ` Q ${x + wl / 4} ${y0 - amp} ${x + wl / 2} ${y0} Q ${x + (3 * wl) / 4} ${y0 + amp} ${x + wl} ${y0}`;
      }
      els.push(<path key={row} d={d} stroke={fg} strokeWidth={8} fill="none" />);
    }
  } else {
    const SZ = 110;
    for (let row = -8; row <= 19; row++)
      for (let col = -8; col <= 19; col++)
        if ((row + col) % 2 === 0)
          els.push(<rect key={`${row},${col}`} x={col * SZ} y={row * SZ} width={SZ} height={SZ} fill={fg} />);
  }

  return (
    <g transform={`rotate(${angle} 600 600)`} style={{ opacity: 0.18 }}>
      {els}
    </g>
  );
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
  const bgKind = (h >> 8) % 6;
  const bgAngle = ((h >> 12) % 61) - 30;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", background: palette.bg, display: "flex" }}>
        <svg width="1200" height="1200" viewBox="0 0 1200 1200">
          {bgTexture(bgKind, palette.fg, bgAngle)}
          {motifCell(category, mv, bv, palette, 150, 150, 900)}
        </svg>
      </div>
    ),
    { ...size }
  );
}
