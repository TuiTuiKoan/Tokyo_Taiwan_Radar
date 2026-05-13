/**
 * Google Fonts loader (next/font/google).
 *
 * Exposes CSS variables consumed by `globals.css` and tokens.ts:
 *  --font-display  → Zen Maru Gothic  (Hero, slide title, OG title)
 *  --font-body     → Noto Sans JP     (UI, EventCard, FilterBar)
 *  --font-mono     → JetBrains Mono   (timestamps, IDs)
 *  --font-accent   → Bagel Fat One    (slide numbers, retro accents)
 *
 * Apply by spreading the className onto <html> in app/layout.tsx.
 *
 * Why next/font:
 *  - Self-hosted, no FOIT, no extra network request to Google CDN.
 *  - Automatic subset based on declared scripts.
 *  - Stable URLs at build time → safe for SSR + edge OG routes.
 */
import { Zen_Maru_Gothic, Noto_Sans_JP, JetBrains_Mono, Bagel_Fat_One } from "next/font/google";

export const fontDisplay = Zen_Maru_Gothic({
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
  variable: "--font-display",
  display: "swap",
  preload: true,
});

export const fontBody = Noto_Sans_JP({
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
  variable: "--font-body",
  display: "swap",
  preload: true,
});

export const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-mono",
  display: "swap",
  preload: false,
});

export const fontAccent = Bagel_Fat_One({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-accent",
  display: "swap",
  preload: false,
});

/** Aggregated class string applied to <html>. */
export const fontVariables = [
  fontDisplay.variable,
  fontBody.variable,
  fontMono.variable,
  fontAccent.variable,
].join(" ");
