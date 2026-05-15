import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale } from "@/lib/types";
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

// 6 bg texture kinds — inline elements only (no <defs>/<pattern>, Satori-safe)
// Each kind is wrapped in a rotated <g> so random angle applies cleanly
function bgTexture(kind: number, fg: string, angle: number) {
  const v = ((kind % 6) + 6) % 6;
  const els: React.ReactNode[] = [];

  if (v === 0) {
    // halftone dense: r=28, step=100
    const S = 100;
    for (let row = -4; row <= 16; row++)
      for (let col = -4; col <= 16; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S} cy={row * S} r={28} fill={fg} />);
  } else if (v === 1) {
    // halftone sparse: r=18, step=160
    const S = 160;
    for (let row = -3; row <= 11; row++)
      for (let col = -3; col <= 11; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S} cy={row * S} r={18} fill={fg} />);
  } else if (v === 2) {
    // stripes: vertical rects step=70 width=22
    for (let i = -12; i <= 30; i++)
      els.push(<rect key={i} x={i * 70} y="-900" width={22} height="3000" fill={fg} />);
  } else if (v === 3) {
    // grid: H + V lines step=80 lineWidth=5
    for (let i = -7; i <= 23; i++) {
      els.push(<rect key={`h${i}`} x="-900" y={i * 80} width="3000" height={5} fill={fg} />);
      els.push(<rect key={`v${i}`} x={i * 80} y="-900" width={5} height="3000" fill={fg} />);
    }
  } else if (v === 4) {
    // wavy: sinusoidal horizontal paths
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
    // checker: alternating squares sz=110
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

const GRID4_X = [80, 640, 80, 640];
const GRID4_Y = [80, 80, 640, 640];

export default async function Image({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { id } = await params;

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data: event } = await supabase
    .from("events")
    .select("category")
    .eq("id", id)
    .single();

  const categories = (event?.category as string[] | null) ?? ["art"];
  const cats = categories.slice(0, 4);
  const h = hashForId(id);
  const palette = PALETTES[h % PALETTES.length];
  const mv = h % 5;
  const bv = (h >> 4) % 5;
  const bgKind = (h >> 8) % 6;
  const bgAngle = ((h >> 12) % 61) - 30;

  const n = cats.length;
  let cells;
  if (n === 1) {
    cells = motifCell(cats[0], mv, bv, palette, 150, 150, 900);
  } else if (n === 2) {
    cells = [
      motifCell(cats[0], mv % 5, bv % 5, palette, 80, 360, 480),
      motifCell(cats[1], (mv + 1) % 5, (bv + 1) % 5, palette, 640, 360, 480),
    ];
  } else {
    const grid = cats.length >= 4 ? cats : [...cats, cats[0]];
    cells = grid.slice(0, 4).map((cat, i) =>
      motifCell(cat, (mv + i) % 5, (bv + i) % 5, palette, GRID4_X[i], GRID4_Y[i], 480)
    );
  }

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", background: palette.bg, display: "flex" }}>
        <svg width="1200" height="1200" viewBox="0 0 1200 1200">
          {bgTexture(bgKind, palette.fg, bgAngle)}
          {cells}
        </svg>
      </div>
    ),
    { ...size }
  );
}
