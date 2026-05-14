import type { Category } from "@/lib/types";
import { getSemanticSymbol, getRandomCollageBase } from "./organicMotifs";

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

type BgKind = "halftoneDense" | "halftoneSparse" | "stripes" | "grid" | "wavy" | "checker";
const BG_KINDS: BgKind[] = ["halftoneDense", "halftoneSparse", "stripes", "grid", "wavy", "checker"];

function BgPattern({ kind, color, rotation, id }: { kind: BgKind; color: string; rotation: number; id: string }) {
  const pid = `pat-${id}`;
  let def: React.ReactNode = null;
  switch (kind) {
    case "halftoneDense": def = <pattern id={pid} width="12" height="12" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><circle cx="6" cy="6" r="3.5" fill={color} /></pattern>; break;
    case "halftoneSparse": def = <pattern id={pid} width="20" height="20" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><circle cx="10" cy="10" r="2.5" fill={color} /></pattern>; break;
    case "stripes": def = <pattern id={pid} width="16" height="16" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><line x1="0" y1="0" x2="0" y2="16" stroke={color} strokeWidth="6" /></pattern>; break;
    case "grid": def = <pattern id={pid} width="18" height="18" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><path d="M 18 0 L 0 0 0 18" stroke={color} strokeWidth="2.5" fill="none" /></pattern>; break;
    case "wavy": def = <pattern id={pid} width="30" height="16" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><path d="M 0 8 Q 7.5 0 15 8 T 30 8" stroke={color} strokeWidth="3" fill="none" /></pattern>; break;
    case "checker": def = <pattern id={pid} width="20" height="20" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}><rect width="10" height="10" fill={color} /><rect x="10" y="10" width="10" height="10" fill={color} /></pattern>; break;
  }
  return <><defs>{def}</defs><rect width="100" height="100" fill={`url(#${pid})`} opacity="0.45" /></>;
}

interface CategoryThumbnailProps {
  id: string;
  categories?: string[];
  className?: string;
  forceMotifIdx?: number;
}

export function CategoryThumbnail({ id, categories = [], className = "", forceMotifIdx }: CategoryThumbnailProps) {
  const rand = mulberry32(hashString(id || "default"));
  const primaryCat = categories[0] || "default";
  
  const paletteIdx = (Math.floor(rand() * PALETTES.length) + hashString(primaryCat)) % PALETTES.length;
  const palette = PALETTES[paletteIdx];
  const accentColor = palette.accent;

  const bgKind = BG_KINDS[Math.floor(rand() * BG_KINDS.length)];
  const patRotation = Math.floor(rand() * 90) - 45;
  const bgPatColor = rand() > 0.5 ? palette.fg : accentColor;

  // Each category has exactly 5 variants. We pick one based on random or force index
  const variantIndex = forceMotifIdx !== undefined ? (forceMotifIdx % 5) : Math.floor(rand() * 5);
  
  // Secondary randoms for organic blobs
  const baseVariant = Math.floor(rand() * 5);
  const m1Rotate = Math.floor(rand() * 30) - 15;
  const m1Scale = 0.85 + rand() * 0.2; 
  const m1Dx = Math.floor(rand() * 12) - 6;
  const m1Dy = Math.floor(rand() * 12) - 6;

  return (
    <div className={`relative overflow-hidden ${className}`} style={{ backgroundColor: palette.bg }}>
      <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
        <BgPattern kind={bgKind} color={bgPatColor} rotation={patRotation} id={id} />
        
        {/* Layer 1: Organic Base Blob (large, random organic shapes like fern/waves/blobs) */}
        <g transform={`translate(50 50) rotate(${-m1Rotate}) scale(0.9) translate(-50 -50)`}>
          {getRandomCollageBase(baseVariant, palette.fg, accentColor)}
        </g>
        
        {/* Layer 2: Semantic Foreground Symbol */}
        <g transform={`translate(50 50) rotate(${m1Rotate}) scale(${m1Scale}) translate(${-50 + m1Dx} ${-50 + m1Dy})`}>
          {getSemanticSymbol(primaryCat, variantIndex, palette.bg, "#3A261F")}
          <g transform={`translate(2 -2) scale(0.98)`}>
            {getSemanticSymbol(primaryCat, variantIndex, palette.fg, accentColor)}
          </g>
        </g>
      </svg>
    </div>
  );
}
