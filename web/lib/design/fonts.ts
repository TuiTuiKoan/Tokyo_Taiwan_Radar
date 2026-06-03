/**
 * Font variable shim.
 *
 * The design system reads these CSS custom properties from globals.css.
 * Keeping this file as a tiny shim avoids next/font/google network fetches
 * during Turbopack builds while preserving the existing import surface.
 */
export const fontDisplay = { variable: "--font-display" } as const;
export const fontBody = { variable: "--font-body" } as const;
export const fontMono = { variable: "--font-mono" } as const;
export const fontAccent = { variable: "--font-accent" } as const;

/** Aggregated class string applied to <html>. */
export const fontVariables = "";
