/**
 * CategoryThumbnail — procedural per-event thumbnail.
 *
 * Given a stable seed (event id) + categories, deterministically produces:
 *   1. A background pattern (halftone / stripes / grid / wavy), rotated and tinted
 *   2. One or two geometric "motif" shapes, layered as a Bauhaus collage
 *   3. A palette derived from the category combination
 *
 * Same event → identical thumbnail across renders. Different events → different.
 */

import type { Category } from "@/lib/types";

// ---------- Deterministic PRNG ----------------------------------------------
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

// ---------- Palette --------------------------------------------------------
const PALETTES = [
  { bg: "#FFE9DD", fg: "#E84860", accent: "#1F5E2B" },   // pink / red / green
  { bg: "#E8F6D6", fg: "#1F5E2B", accent: "#E84860" },   // leaf / green / red
  { bg: "#FFF1C2", fg: "#C9A227", accent: "#3A261F" },   // cream / gold / mocha
  { bg: "#FFD9D0", fg: "#F47A86", accent: "#3A261F" },   // blush / coral / mocha
  { bg: "#E0EBFF", fg: "#3B5BA9", accent: "#E84860" },   // sky / blue / red
  { bg: "#FFE0EF", fg: "#D85862", accent: "#1F5E2B" },   // light pink / deep pink / green
  { bg: "#F0E6FF", fg: "#7B4FB8", accent: "#C9A227" },   // lavender / purple / gold
  { bg: "#D6F0EA", fg: "#2C8A7A", accent: "#E84860" },   // mint / teal / red
];

// ---------- Background patterns --------------------------------------------
type BgKind = "halftoneDense" | "halftoneSparse" | "stripes" | "grid" | "wavy" | "checker";
const BG_KINDS: BgKind[] = ["halftoneDense", "halftoneSparse", "stripes", "grid", "wavy", "checker"];

function BgPattern({ kind, color, rotation, id }: { kind: BgKind; color: string; rotation: number; id: string }) {
  const pid = `pat-${id}`;
  let def: React.ReactNode = null;
  switch (kind) {
    case "halftoneDense":
      def = (
        <pattern id={pid} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <circle cx="4" cy="4" r="1.8" fill={color} />
        </pattern>
      );
      break;
    case "halftoneSparse":
      def = (
        <pattern id={pid} width="14" height="14" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <circle cx="7" cy="7" r="1.3" fill={color} />
        </pattern>
      );
      break;
    case "stripes":
      def = (
        <pattern id={pid} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <line x1="0" y1="0" x2="0" y2="10" stroke={color} strokeWidth="3.5" />
        </pattern>
      );
      break;
    case "grid":
      def = (
        <pattern id={pid} width="12" height="12" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <path d="M 12 0 L 0 0 0 12" stroke={color} strokeWidth="0.8" fill="none" />
        </pattern>
      );
      break;
    case "wavy":
      def = (
        <pattern id={pid} width="20" height="10" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <path d="M 0 5 Q 5 0 10 5 T 20 5" stroke={color} strokeWidth="1.4" fill="none" />
        </pattern>
      );
      break;
    case "checker":
      def = (
        <pattern id={pid} width="14" height="14" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation})`}>
          <rect width="7" height="7" fill={color} />
          <rect x="7" y="7" width="7" height="7" fill={color} />
        </pattern>
      );
      break;
  }
  return (
    <>
      <defs>{def}</defs>
      <rect width="100" height="100" fill={`url(#${pid})`} opacity="0.55" />
    </>
  );
}

// ---------- Motifs (per category) ------------------------------------------
type MotifFn = (color: string, accent: string) => React.ReactNode;

const MOTIFS: Partial<Record<Category, MotifFn>> = {
  // Sound / performance — concentric circles (vinyl / speaker)
  movie: (c, a) => (
    <g>
      <rect x="20" y="30" width="60" height="40" fill={c} />
      <rect x="20" y="30" width="60" height="6" fill={a} />
      <rect x="20" y="64" width="60" height="6" fill={a} />
      <circle cx="50" cy="50" r="8" fill="#fff" />
    </g>
  ),
  performing_arts: (c, a) => (
    <g>
      <circle cx="50" cy="50" r="28" fill={c} />
      <circle cx="50" cy="50" r="18" fill={a} />
      <circle cx="50" cy="50" r="6" fill="#fff" />
    </g>
  ),
  drama: (c, a) => (
    <g>
      <path d="M 30 30 Q 40 20 50 30 Q 60 20 70 30 L 70 65 Q 50 78 30 65 Z" fill={c} />
      <circle cx="42" cy="48" r="3" fill={a} />
      <circle cx="58" cy="48" r="3" fill={a} />
    </g>
  ),
  documentary: (c, a) => (
    <g>
      <rect x="22" y="32" width="56" height="36" fill={c} />
      <circle cx="36" cy="50" r="8" fill={a} />
      <polygon points="50,42 66,50 50,58" fill="#fff" />
    </g>
  ),
  senses: (c, a) => (
    <g>
      <path d="M 18 50 Q 30 30 42 50 T 66 50 T 82 50" stroke={c} strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M 18 62 Q 30 42 42 62 T 66 62 T 82 62" stroke={a} strokeWidth="5" fill="none" strokeLinecap="round" />
    </g>
  ),

  // Food & drink
  lifestyle_food: (c, a) => (
    <g>
      <ellipse cx="50" cy="65" rx="26" ry="8" fill={a} />
      <path d="M 30 65 L 35 30 Q 50 22 65 30 L 70 65 Z" fill={c} />
      <ellipse cx="50" cy="30" rx="15" ry="4" fill="#fff" />
    </g>
  ),
  tea_alcohol: (c, a) => (
    <g>
      <path d="M 30 38 L 30 60 Q 30 72 50 72 Q 70 72 70 60 L 70 38 Z" fill={c} />
      <ellipse cx="50" cy="38" rx="20" ry="5" fill={a} />
      <path d="M 70 45 Q 80 45 80 55 Q 80 65 70 65" stroke={a} strokeWidth="3" fill="none" />
    </g>
  ),

  // Nature / outdoor
  nature: (c, a) => (
    <g>
      <path d="M 30 70 Q 40 30 60 40 Q 70 50 50 70 Z" fill={c} />
      <path d="M 50 70 L 50 40" stroke={a} strokeWidth="2" />
    </g>
  ),
  indigenous: (c, a) => (
    <g>
      <polygon points="50,20 80,75 20,75" fill={c} />
      <polyline points="30,55 50,40 70,55" stroke={a} strokeWidth="3" fill="none" />
      <polyline points="35,65 50,50 65,65" stroke={a} strokeWidth="3" fill="none" />
    </g>
  ),
  folklore: (c, a) => (
    <g>
      <polygon points="50,22 62,42 84,46 67,60 72,82 50,72 28,82 33,60 16,46 38,42" fill={c} />
      <circle cx="50" cy="55" r="6" fill={a} />
    </g>
  ),

  // Visual / craft
  art: (c, a) => (
    <g>
      <polygon points="50,22 78,70 22,70" fill={c} />
      <circle cx="50" cy="60" r="10" fill={a} />
    </g>
  ),
  retail: (c, a) => (
    <g>
      <rect x="28" y="38" width="44" height="36" fill={c} />
      <path d="M 38 38 Q 38 26 50 26 Q 62 26 62 38" stroke={a} strokeWidth="3" fill="none" />
    </g>
  ),
  workshop: (c, a) => (
    <g>
      <rect x="42" y="20" width="16" height="40" fill={c} />
      <rect x="36" y="60" width="28" height="14" fill={a} />
      <circle cx="50" cy="22" r="4" fill="#fff" />
    </g>
  ),

  // Knowledge / talks
  lecture: (c, a) => (
    <g>
      <rect x="28" y="32" width="44" height="32" fill={c} />
      <rect x="32" y="36" width="36" height="4" fill={a} />
      <rect x="32" y="44" width="28" height="4" fill={a} />
      <rect x="32" y="52" width="32" height="4" fill={a} />
    </g>
  ),
  academic: (c, a) => (
    <g>
      <polygon points="50,20 80,40 50,60 20,40" fill={c} />
      <line x1="50" y1="60" x2="50" y2="76" stroke={a} strokeWidth="3" />
      <circle cx="78" cy="48" r="3" fill={a} />
    </g>
  ),
  books_media: (c, a) => (
    <g>
      <path d="M 22 28 L 50 36 L 78 28 L 78 70 L 50 78 L 22 70 Z" fill={c} />
      <line x1="50" y1="36" x2="50" y2="78" stroke={a} strokeWidth="3" />
    </g>
  ),
  literature: (c, a) => (
    <g>
      <rect x="26" y="22" width="48" height="56" fill={c} />
      <line x1="34" y1="36" x2="66" y2="36" stroke={a} strokeWidth="2" />
      <line x1="34" y1="46" x2="66" y2="46" stroke={a} strokeWidth="2" />
      <line x1="34" y1="56" x2="58" y2="56" stroke={a} strokeWidth="2" />
    </g>
  ),

  // Places / society
  tourism: (c, a) => (
    <g>
      <path d="M 24 70 L 24 44 Q 24 28 50 28 Q 76 28 76 44 L 76 70 Z" fill={c} />
      <rect x="44" y="50" width="12" height="20" fill={a} />
    </g>
  ),
  urban: (c, a) => (
    <g>
      <rect x="22" y="44" width="14" height="30" fill={c} />
      <rect x="40" y="32" width="20" height="42" fill={a} />
      <rect x="64" y="50" width="14" height="24" fill={c} />
    </g>
  ),
  history: (c, a) => (
    <g>
      <path d="M 18 40 L 50 22 L 82 40 L 82 46 L 18 46 Z" fill={c} />
      <rect x="26" y="46" width="48" height="28" fill={a} />
      <rect x="46" y="56" width="8" height="18" fill="#fff" />
    </g>
  ),
  geopolitics: (c, a) => (
    <g>
      <circle cx="50" cy="50" r="28" fill="none" stroke={c} strokeWidth="3" />
      <ellipse cx="50" cy="50" rx="28" ry="10" fill="none" stroke={a} strokeWidth="2" />
      <line x1="22" y1="50" x2="78" y2="50" stroke={a} strokeWidth="2" />
    </g>
  ),

  // People / identity
  gender: (c, a) => (
    <g>
      <circle cx="38" cy="44" r="14" fill="none" stroke={c} strokeWidth="4" />
      <circle cx="62" cy="56" r="14" fill="none" stroke={a} strokeWidth="4" />
    </g>
  ),
  parenting: (c, a) => (
    <g>
      <circle cx="38" cy="40" r="8" fill={c} />
      <circle cx="60" cy="46" r="6" fill={a} />
      <path d="M 28 70 Q 38 56 48 70 Z" fill={c} />
      <path d="M 50 70 Q 60 60 70 70 Z" fill={a} />
    </g>
  ),
  taiwan_japan: (c, a) => (
    <g>
      <circle cx="36" cy="50" r="14" fill={c} />
      <circle cx="64" cy="50" r="14" fill={a} />
    </g>
  ),

  // Career / money
  business: (c, a) => (
    <g>
      <rect x="22" y="56" width="12" height="20" fill={c} />
      <rect x="40" y="44" width="12" height="32" fill={a} />
      <rect x="58" y="32" width="12" height="44" fill={c} />
      <polyline points="22,46 40,38 58,28 76,18" stroke={a} strokeWidth="2.5" fill="none" />
    </g>
  ),
  scholarship: (c, a) => (
    <g>
      <path d="M 30 22 L 70 22 L 60 44 L 70 66 L 30 66 L 40 44 Z" fill={c} />
      <circle cx="50" cy="44" r="8" fill={a} />
    </g>
  ),
  competition: (c, a) => (
    <g>
      <polygon points="50,18 60,38 82,42 66,58 70,80 50,68 30,80 34,58 18,42 40,38" fill={c} />
      <circle cx="50" cy="48" r="6" fill={a} />
    </g>
  ),

  // Tech / media
  tech: (c, a) => (
    <g>
      <rect x="26" y="30" width="48" height="36" fill={c} />
      <rect x="32" y="36" width="36" height="24" fill={a} />
      <rect x="40" y="66" width="20" height="6" fill={c} />
    </g>
  ),
  tv_program: (c, a) => (
    <g>
      <rect x="22" y="34" width="56" height="34" fill={c} />
      <rect x="28" y="40" width="44" height="22" fill="#fff" />
      <line x1="40" y1="24" x2="50" y2="34" stroke={a} strokeWidth="2" />
      <line x1="60" y1="24" x2="50" y2="34" stroke={a} strokeWidth="2" />
    </g>
  ),
  radio_program: (c, a) => (
    <g>
      <rect x="22" y="44" width="56" height="28" fill={c} />
      <circle cx="36" cy="58" r="6" fill={a} />
      <line x1="50" y1="50" x2="70" y2="50" stroke={a} strokeWidth="2" />
      <line x1="50" y1="58" x2="68" y2="58" stroke={a} strokeWidth="2" />
      <line x1="50" y1="66" x2="64" y2="66" stroke={a} strokeWidth="2" />
    </g>
  ),
};

// Default fallback motif — a Bauhaus collage
function defaultMotif(c: string, a: string): React.ReactNode {
  return (
    <g>
      <circle cx="40" cy="46" r="20" fill={c} />
      <rect x="48" y="38" width="28" height="28" fill={a} />
    </g>
  );
}

// ---------- Main component -------------------------------------------------
export interface CategoryThumbnailProps {
  /** Stable seed (typically event.id) for deterministic output. */
  seed: string;
  /** Event categories — first two influence motif + palette. */
  categories?: string[] | null;
  /** Container size in px (renders 1:1 square). */
  size?: number;
  className?: string;
}

export function CategoryThumbnail({ seed, categories, size = 80, className = "" }: CategoryThumbnailProps) {
  const seedNum = hashString(seed || "default");
  const rand = mulberry32(seedNum);

  const cats = (categories ?? []).filter(Boolean) as Category[];
  const primaryCat = cats[0];
  const secondaryCat = cats[1];

  // Palette — selected from category hash, shifted by secondary count
  const paletteIdx = (hashString((primaryCat ?? "x") + ":" + (secondaryCat ?? "y")) + cats.length) % PALETTES.length;
  const palette = PALETTES[paletteIdx];

  // Background pattern — kind + rotation derived from seed
  const bgKind = BG_KINDS[Math.floor(rand() * BG_KINDS.length)];
  const rotation = Math.floor(rand() * 90) - 45;
  const bgColor = rand() > 0.5 ? palette.fg : palette.accent;

  // Motif — primary category resolves the main shape; secondary tweaks accent
  const motifFn = (primaryCat && MOTIFS[primaryCat]) || defaultMotif;
  const fgColor = palette.fg;
  const accentColor = secondaryCat ? PALETTES[hashString(secondaryCat) % PALETTES.length].fg : palette.accent;

  // Slight rotation + offset for variety
  const motifRotate = Math.floor(rand() * 24) - 12;
  const motifOffsetX = Math.floor(rand() * 8) - 4;
  const motifOffsetY = Math.floor(rand() * 8) - 4;

  // Optional decorative corner accent
  const cornerShape = Math.floor(rand() * 4);
  const cornerOpacity = 0.55 + rand() * 0.25;

  // Unique pattern id (for SSR safety)
  const patId = `${seedNum.toString(36)}`;

  return (
    <div
      className={`relative overflow-hidden rounded-lg border border-line ${className}`}
      style={{ width: size, height: size, background: palette.bg }}
      aria-hidden
    >
      <svg viewBox="0 0 100 100" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
        {/* Background pattern */}
        <BgPattern kind={bgKind} color={bgColor} rotation={rotation} id={patId} />

        {/* Decorative corner accent (varies by seed) */}
        {cornerShape === 0 && (
          <circle cx="92" cy="8" r="14" fill={palette.accent} opacity={cornerOpacity} />
        )}
        {cornerShape === 1 && (
          <polygon points="100,0 100,28 72,0" fill={palette.accent} opacity={cornerOpacity} />
        )}
        {cornerShape === 2 && (
          <rect x="-4" y="78" width="40" height="40" fill={palette.fg} opacity={cornerOpacity * 0.6} transform="rotate(20 12 92)" />
        )}
        {cornerShape === 3 && (
          <path d="M 0 100 Q 30 70 60 100 Z" fill={palette.accent} opacity={cornerOpacity * 0.7} />
        )}

        {/* Primary motif — translated + slightly rotated for uniqueness */}
        <g transform={`translate(${motifOffsetX} ${motifOffsetY}) rotate(${motifRotate} 50 50)`}>
          {motifFn(fgColor, accentColor)}
        </g>
      </svg>
    </div>
  );
}
