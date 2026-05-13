/**
 * Design Tokens — Single source of truth for colors, typography, spacing, motion.
 *
 * Consumed by:
 *  - React components (import directly)
 *  - Tailwind via CSS variables in globals.css
 *  - OG image routes (Satori, flattens to inline style)
 *  - Future slide generation (read as JSON)
 *
 * When you change a value here, mirror it in `web/app/globals.css` if it's
 * a semantic color token (bg/fg/border/brand).
 */

// ---------- Color ----------
export const color = {
  // Primitive palette — raw swatches, do not use directly in components.
  // Prefer semantic tokens below.
  primitive: {
    paper: "#FFFDF5",
    blush: "#FFF1EE",
    matcha: "#F7FFE8",
    pink: "#F56A82",
    pinkSoft: "#FF7AA0",
    pinkDeep: "#D85862",
    pinkVivid: "#E84860",
    pinkBlush: "#F47A86",
    green: "#78B94E",
    greenLeaf: "#C4E86F",
    greenDeep: "#1F5E2B",
    gold: "#C9A227",
    cocoa: "#3A261F",
    coal: "#1A1818",
    mocha: "#6A5148",
  },

  // Semantic tokens — what components should reference.
  brand: {
    primary: "#E84860",   // mascot red, hero accent
    secondary: "#1F5E2B", // mascot antenna, success accent
    accent: "#C4E86F",    // highlight, hero underline
  },

  // Pattern fills (referenced as `url(#patternId)` in SVG components).
  patterns: {
    halftonePink: "halftonePink",
    halftoneGreen: "halftoneGreen",
    wavyLinesGreen: "wavyLinesGreen",
    wavyLinesPink: "wavyLinesPink",
    diagStripes: "diagStripes",
    gridPink: "gridPink",
  },

  // Gradient stops.
  gradient: {
    paperBlush: ["#FFFDF5", "#FFF1EE", "#F7FFE8"] as const,
    cta: ["#F47A86", "#D85862"] as const,
  },
} as const;

// ---------- Typography ----------
export const font = {
  /** Display — Hero titles, slide covers, OG titles. Round, friendly, matches mascot. */
  display: "var(--font-display)",
  /** Body — UI text, EventCard, FilterBar. Multilingual JP/ZH/EN. */
  body: "var(--font-body)",
  /** Mono — timestamps, IDs, admin tables. */
  mono: "var(--font-mono)",
  /** Accent — large numbers, slide page numbers, retro headings. */
  accent: "var(--font-accent)",
} as const;

export const fontSize = {
  xs: "12px",
  sm: "14px",
  base: "16px",
  lg: "18px",
  xl: "20px",
  "2xl": "24px",
  "3xl": "30px",
  "4xl": "36px",
  "5xl": "44px",
  "6xl": "56px",
  "7xl": "72px",
} as const;

export const fontWeight = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  black: 900,
} as const;

export const lineHeight = {
  tight: 1.1,
  snug: 1.25,
  normal: 1.5,
  relaxed: 1.75,
} as const;

// ---------- Spacing (4pt grid) ----------
export const spacing = {
  0: "0",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
  20: "80px",
  24: "96px",
} as const;

// ---------- Radius ----------
export const radius = {
  none: "0",
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "24px",
  full: "9999px",
} as const;

// ---------- Shadow ----------
export const shadow = {
  sm: "0 1px 2px rgba(0,0,0,0.06)",
  md: "0 4px 12px rgba(0,0,0,0.08)",
  lg: "0 12px 32px rgba(0,0,0,0.12)",
  focus: "0 0 0 3px rgba(232,72,96,0.35)",
} as const;

// ---------- Motion ----------
export const motion = {
  duration: {
    fast: 120,
    base: 200,
    slow: 320,
  },
  easing: {
    standard: "cubic-bezier(0.2, 0, 0, 1)",
    out: "cubic-bezier(0.0, 0, 0.2, 1)",
    in: "cubic-bezier(0.4, 0, 1, 1)",
  },
} as const;

// ---------- Mascot ----------
/**
 * Standard tilt for the wax-apple mascot across all surfaces.
 * Body rotates 3° clockwise around its base center.
 */
export const mascot = {
  tilt: 3,
  viewBox: "0 0 200 220",
} as const;

// ---------- Resolved tokens for Satori / non-CSS contexts ----------
/**
 * Flattens design tokens to inline-style-friendly values for Satori
 * (which does not support CSS variables).
 *
 * Usage in OG route:
 *   import { satoriTokens } from "@/lib/design/tokens";
 *   style={{ fontFamily: satoriTokens.font.display, color: satoriTokens.color.brand.primary }}
 */
export const satoriTokens = {
  font: {
    display: "Zen Maru Gothic",
    body: "Noto Sans JP",
    mono: "JetBrains Mono",
    accent: "Bagel Fat One",
  },
  color,
} as const;

export type DesignTokens = {
  color: typeof color;
  font: typeof font;
  fontSize: typeof fontSize;
  spacing: typeof spacing;
  radius: typeof radius;
  shadow: typeof shadow;
  motion: typeof motion;
  mascot: typeof mascot;
};
