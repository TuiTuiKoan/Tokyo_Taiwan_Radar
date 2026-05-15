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
    // halftone dense — staggered hex: r=128 (diameter=256), step=384 (= 1.5× diameter)
    const S = 384;
    for (let row = -4; row <= 7; row++) {
      const ox = (row % 2 === 0) ? 0 : S / 2;
      for (let col = -4; col <= 7; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S + ox} cy={row * S} r={128} fill={fg} />);
    }
  } else if (v === 1) {
    // halftone sparse — staggered hex: r=20, step=210 (half density vs step=150)
    const S = 210;
    for (let row = -3; row <= 9; row++) {
      const ox = (row % 2 === 0) ? 0 : S / 2;
      for (let col = -3; col <= 8; col++)
        els.push(<circle key={`${row},${col}`} cx={col * S + ox} cy={row * S} r={20} fill={fg} />);
    }
  } else if (v === 2) {
    // stripes: width=40, step=110
    for (let i = -11; i <= 24; i++)
      els.push(<rect key={i} x={i * 110} y="-900" width={40} height="3000" fill={fg} />);
  } else if (v === 3) {
    // grid: H + V lines, lineWidth=8, step=100
    for (let i = -6; i <= 21; i++) {
      els.push(<rect key={`h${i}`} x="-900" y={i * 100} width="3000" height={8} fill={fg} />);
      els.push(<rect key={`v${i}`} x={i * 100} y="-900" width={8} height="3000" fill={fg} />);
    }
  } else if (v === 4) {
    // wavy: strokeWidth=16, rowStep=110, amp=28, wl=140
    const rS = 110, amp = 28, wl = 140;
    for (let row = -6; row <= 17; row++) {
      const y0 = row * rS;
      let d = `M -900 ${y0}`;
      for (let x = -900; x < 2100; x += wl) {
        d += ` Q ${x + wl / 4} ${y0 - amp} ${x + wl / 2} ${y0} Q ${x + (3 * wl) / 4} ${y0 + amp} ${x + wl} ${y0}`;
      }
      els.push(<path key={row} d={d} stroke={fg} strokeWidth={16} fill="none" />);
    }
  } else {
    // checker: sz=130
    const SZ = 130;
    for (let row = -7; row <= 16; row++)
      for (let col = -7; col <= 16; col++)
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
  x: number, y: number, sz: number, rot: number,
) {
  const s = sz / 100;
  return (
    <g key={`${cat}-${x}`} transform={`translate(${x} ${y}) scale(${s})`}>
      <g transform={`translate(50 50) rotate(${-(rot * 0.7)}) scale(0.9) translate(-50 -50)`}>
        {getRandomCollageBase(bv, p.fg, p.accent)}
      </g>
      <g transform={`translate(${50 + rot * 0.2} ${50 - rot * 0.2}) rotate(${rot}) scale(0.92) translate(-50 -50)`}>
        {getSemanticSymbol(cat, v, p.bg, "#3A261F")}
        <g transform="translate(2 -2) scale(0.98)">
          {getSemanticSymbol(cat, v, p.fg, p.accent)}
        </g>
      </g>
    </g>
  );
}

// Organic multi-category layouts — varied sizes, overlapping cells

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
  const bgAngle = ((h >> 12) % 151) - 75;
  const motifRots = [
    ((mv * 7) % 31) - 15,
    ((mv * 7 + 11) % 31) - 15,
    ((mv * 7 + 22) % 31) - 15,
    ((mv * 7 + 9) % 31) - 15,
  ];

  const n = cats.length;
  let cells;
  if (n === 1) {
    // single: centered large
    cells = motifCell(cats[0], mv, bv, palette, 150, 150, 900, motifRots[0]);
  } else if (n === 2) {
    // diagonal bloom: two large cells overlapping at center
    cells = [
      motifCell(cats[0], mv % 5, bv % 5,       palette,  0,   0,  840, motifRots[0]),
      motifCell(cats[1], (mv+1) % 5, (bv+1) % 5, palette, 360, 360, 840, motifRots[1]),
    ];
  } else if (n === 3) {
    // triad: large left, medium top-right, medium bottom-right — diagonal cascade
    cells = [
      motifCell(cats[0], mv % 5,     bv % 5,     palette,   0,  80, 720, motifRots[0]),
      motifCell(cats[1], (mv+1) % 5, (bv+1) % 5, palette, 600,   0, 580, motifRots[1]),
      motifCell(cats[2], (mv+2) % 5, (bv+2) % 5, palette, 400, 580, 620, motifRots[2]),
    ];
  } else {
    // mosaic: one dominant + three scattered at varied sizes
    const layout = [
      { x:   0, y:   0, sz: 720 },
      { x: 660, y:   0, sz: 540 },
      { x:   0, y: 660, sz: 540 },
      { x: 520, y: 520, sz: 620 },
    ];
    cells = cats.slice(0, 4).map((cat, i) =>
      motifCell(cat, (mv + i) % 5, (bv + i) % 5, palette, layout[i].x, layout[i].y, layout[i].sz, motifRots[i])
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
