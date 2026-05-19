import { ImageResponse } from "next/og";
import type { ReactNode } from "react";
import type { Locale } from "@/lib/types";
import { getRandomCollageBase } from "@/lib/design/organicMotifs";

export type PageMotifKey = "home" | "announcements" | "about" | "sources" | "saved" | "admin";

type Palette = { bg: string; fg: string; accent: string };
type BgKind = "halftoneDense" | "halftoneSparse" | "stripes" | "grid" | "wavy" | "checker";

const PALETTES: Palette[] = [
  { bg: "#FFE9DD", fg: "#E84860", accent: "#1F5E2B" },
  { bg: "#E8F6D6", fg: "#1F5E2B", accent: "#E84860" },
  { bg: "#FFF1C2", fg: "#C9A227", accent: "#3A261F" },
  { bg: "#FFD9D0", fg: "#F47A86", accent: "#3A261F" },
  { bg: "#E0EBFF", fg: "#3B5BA9", accent: "#E84860" },
  { bg: "#FFE0EF", fg: "#D85862", accent: "#1F5E2B" },
  { bg: "#F0E6FF", fg: "#7B4FB8", accent: "#C9A227" },
  { bg: "#D6F0EA", fg: "#2C8A7A", accent: "#E84860" },
];

const BG_KINDS: BgKind[] = ["halftoneDense", "halftoneSparse", "stripes", "grid", "wavy", "checker"];
const MOTIFS = ["yushan", "wetland", "typhoon", "sun", "banana"] as const;
const PAGE_MOTIFS: Record<PageMotifKey, number> = {
  home: 0,
  announcements: 2,
  about: 3,
  sources: 1,
  saved: 4,
  admin: 0,
};

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

function pickThumbnailStyle(id: string, primaryKey: string) {
  const rand = mulberry32(hashString(id || "default"));
  const paletteIdx = (Math.floor(rand() * PALETTES.length) + hashString(primaryKey)) % PALETTES.length;
  const palette = PALETTES[paletteIdx];
  const bgKind = BG_KINDS[Math.floor(rand() * BG_KINDS.length)];
  const patRotation = Math.floor(rand() * 90) - 45;
  const bgPatColor = rand() > 0.5 ? palette.fg : palette.accent;
  const baseVariant = Math.floor(rand() * 5);
  const rotate = Math.floor(rand() * 30) - 15;
  const scale = 0.85 + rand() * 0.2;
  const dx = Math.floor(rand() * 12) - 6;
  const dy = Math.floor(rand() * 12) - 6;

  return { palette, bgKind, patRotation, bgPatColor, baseVariant, rotate, scale, dx, dy };
}

function bgTexture(kind: BgKind, color: string, rotation: number) {
  const els: ReactNode[] = [];

  if (kind === "halftoneDense") {
    const step = 144;
    for (let row = -3; row <= 11; row++) {
      const ox = row % 2 === 0 ? 0 : step / 2;
      for (let col = -3; col <= 11; col++) {
        els.push(<circle key={`${row},${col}`} cx={col * step + ox} cy={row * step} r={42} fill={color} />);
      }
    }
  } else if (kind === "halftoneSparse") {
    const step = 220;
    for (let row = -3; row <= 8; row++) {
      const ox = row % 2 === 0 ? 0 : step / 2;
      for (let col = -3; col <= 8; col++) {
        els.push(<circle key={`${row},${col}`} cx={col * step + ox} cy={row * step} r={28} fill={color} />);
      }
    }
  } else if (kind === "stripes") {
    for (let i = -10; i <= 24; i++) {
      els.push(<rect key={i} x={i * 110} y="-900" width={42} height="3000" fill={color} />);
    }
  } else if (kind === "grid") {
    for (let i = -6; i <= 20; i++) {
      els.push(<rect key={`h${i}`} x="-900" y={i * 100} width="3000" height={9} fill={color} />);
      els.push(<rect key={`v${i}`} x={i * 100} y="-900" width={9} height="3000" fill={color} />);
    }
  } else if (kind === "wavy") {
    const rowStep = 110;
    const amp = 28;
    const wave = 140;
    for (let row = -6; row <= 17; row++) {
      const y0 = row * rowStep;
      let d = `M -900 ${y0}`;
      for (let x = -900; x < 2100; x += wave) {
        d += ` Q ${x + wave / 4} ${y0 - amp} ${x + wave / 2} ${y0} Q ${x + (3 * wave) / 4} ${y0 + amp} ${x + wave} ${y0}`;
      }
      els.push(<path key={row} d={d} stroke={color} strokeWidth={18} fill="none" />);
    }
  } else {
    const sz = 130;
    for (let row = -7; row <= 16; row++) {
      for (let col = -7; col <= 16; col++) {
        if ((row + col) % 2 === 0) {
          els.push(<rect key={`${row},${col}`} x={col * sz} y={row * sz} width={sz} height={sz} fill={color} />);
        }
      }
    }
  }

  return (
    <g transform={`rotate(${rotation} 600 600)`} style={{ opacity: 0.18 }}>
      {els}
    </g>
  );
}

function natureSymbol(variant: number, c: string, a: string): ReactNode {
  const v = variant % MOTIFS.length;

  if (v === 0) {
    return (
      <g>
        <path d="M4 84 L18 70 L30 74 L42 52 L55 68 L66 34 L76 64 L86 54 L98 84 Z" fill={c} />
        <path d="M4 84 L18 70 L30 74 L42 52 L55 68 L66 34 L76 64 L86 54 L98 84" stroke="#3A261F" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" fill="none" />
        <path d="M38 58 L42 52 L50 60 L44 59 L41 64 Z M60 48 L66 34 L72 50 L68 47 L65 54 Z M73 66 L76 64 L84 58 L80 68 Z" fill="#FFF" opacity="0.95" />
      </g>
    );
  }

  if (v === 1) {
    return (
      <g>
        <path d="M6 72 Q28 58 50 72 T94 70" stroke={c} strokeWidth="8" strokeLinecap="round" fill="none" />
        <path d="M8 84 Q30 74 52 84 T96 82" stroke={a} strokeWidth="5" strokeLinecap="round" fill="none" />
        <path d="M24 80 C26 56 22 40 18 24 M42 82 C44 54 42 36 38 18 M62 80 C62 58 66 42 74 24 M78 78 C80 56 78 42 88 28" stroke="#3A261F" strokeWidth="4" strokeLinecap="round" fill="none" />
        <ellipse cx="18" cy="24" rx="7" ry="18" transform="rotate(-18 18 24)" fill={c} />
        <ellipse cx="38" cy="18" rx="7" ry="18" transform="rotate(-8 38 18)" fill={a} />
        <ellipse cx="74" cy="24" rx="7" ry="18" transform="rotate(22 74 24)" fill={c} />
        <ellipse cx="88" cy="28" rx="7" ry="18" transform="rotate(18 88 28)" fill={a} />
      </g>
    );
  }

  if (v === 2) {
    return (
      <g transform="rotate(-12 50 50)">
        <path d="M12 58 C22 16 72 12 88 42 C67 33 50 40 42 56 C34 72 20 78 8 70" stroke={c} strokeWidth="10" strokeLinecap="round" fill="none" />
        <path d="M88 42 C78 84 28 88 12 58 C33 67 50 60 58 44 C66 28 80 22 92 30" stroke={a} strokeWidth="8" strokeLinecap="round" fill="none" />
        <circle cx="50" cy="50" r="11" fill="#3A261F" />
        <circle cx="50" cy="50" r="5" fill="#FFF" />
      </g>
    );
  }

  if (v === 3) {
    const rays = Array.from({ length: 12 }, (_, i) => {
      const angle = (i * Math.PI * 2) / 12;
      const x1 = 50 + Math.cos(angle) * 29;
      const y1 = 50 + Math.sin(angle) * 29;
      const x2 = 50 + Math.cos(angle) * 44;
      const y2 = 50 + Math.sin(angle) * 44;
      return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={a} strokeWidth="5" strokeLinecap="round" />;
    });
    return (
      <g>
        {rays}
        <circle cx="50" cy="50" r="25" fill={c} />
        <circle cx="50" cy="50" r="12" fill={a} opacity="0.45" />
      </g>
    );
  }

  return (
    <g>
      <path d="M32 86 C36 56 46 28 66 8 C66 42 54 68 32 86 Z" fill={c} />
      <path d="M34 86 C60 64 76 42 96 26 C90 60 66 82 34 86 Z" fill={a} />
      <path d="M34 86 C28 56 18 34 2 14 C0 48 10 72 34 86 Z" fill={c} opacity="0.75" />
      <path d="M34 86 C36 58 42 32 52 12" stroke="#3A261F" strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M48 68 C58 80 78 82 92 68 C82 88 58 90 42 74 Z" fill="#FFD66B" />
      <path d="M54 76 C64 87 82 88 96 76 C86 94 64 96 48 82 Z" fill="#FFD66B" />
      <circle cx="48" cy="68" r="4" fill="#3A261F" />
    </g>
  );
}

function motifHero(variant: number, pageStyle: ReturnType<typeof pickThumbnailStyle>, seed: string) {
  const cell = pickThumbnailStyle(seed, MOTIFS[variant]);
  const palette = pageStyle.palette;
  const rotate = cell.rotate;

  return (
    <g transform="translate(180 180) scale(8.4)">
      <g transform={`translate(50 50) rotate(${-rotate}) scale(0.9) translate(-50 -50)`}>
        {getRandomCollageBase(cell.baseVariant, palette.fg, palette.accent)}
      </g>
      <g transform={`translate(50 50) rotate(${rotate}) scale(${cell.scale}) translate(${-50 + cell.dx} ${-50 + cell.dy})`}>
        {natureSymbol(variant, palette.bg, "#3A261F")}
        <g transform="translate(2 -2) scale(0.98)">
          {natureSymbol(variant, palette.fg, palette.accent)}
        </g>
      </g>
    </g>
  );
}

export function renderPageMotifOgImage(locale: Locale, pageKey: PageMotifKey) {
  const variant = PAGE_MOTIFS[pageKey] ?? hashString(pageKey) % MOTIFS.length;
  const style = pickThumbnailStyle(`fallback-og-${pageKey}-${locale}`, MOTIFS[variant]);
  const palette = style.palette;

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", background: palette.bg, display: "flex" }}>
        <svg width="1200" height="1200" viewBox="0 0 1200 1200">
          <rect width="1200" height="1200" fill={palette.bg} />
          {bgTexture(style.bgKind, style.bgPatColor, style.patRotation)}
          {motifHero(variant, style, `${locale}-${pageKey}-${MOTIFS[variant]}`)}
        </svg>
      </div>
    ),
    { width: 1200, height: 1200 },
  );
}