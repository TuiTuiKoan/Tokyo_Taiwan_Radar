/**
 * Badge — small pill/chip used across cards, filter chips, and stats.
 *
 * Tones map to semantic intents:
 *  - neutral   gray, default labels (category, city)
 *  - success   green, open/active states
 *  - info      blue, free / informational
 *  - warning   amber, paid / cautionary
 *  - danger    pink-deep, errors / cancelled
 *  - accent    purple, organizer type
 *  - brand     mascot-red, primary highlight
 *
 * Use atoms; do not hand-roll bg- / text- combinations in feature code.
 */
import type { ReactNode } from "react";

export type BadgeTone =
  | "neutral"
  | "success"
  | "info"
  | "warning"
  | "danger"
  | "accent"
  | "brand";

export type BadgeSize = "xs" | "sm" | "md";

export interface BadgeProps {
  tone?: BadgeTone;
  size?: BadgeSize;
  children: ReactNode;
  /** Render with stronger border for filter-chip style. */
  outlined?: boolean;
  className?: string;
}

const toneStyles: Record<BadgeTone, string> = {
  neutral: "bg-muted text-fg-muted",
  success: "bg-[#C4E86F]/40 text-[#1F5E2B]",
  info: "bg-blue-50 text-blue-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-rose-50 text-rose-700",
  accent: "bg-purple-50 text-purple-700",
  brand: "bg-[var(--color-blush)] text-[var(--color-mascot-pink-deep)]",
};

const toneOutlineStyles: Record<BadgeTone, string> = {
  neutral: "border-line",
  success: "border-green-300",
  info: "border-blue-300",
  warning: "border-amber-300",
  danger: "border-rose-300",
  accent: "border-purple-300",
  brand: "border-[var(--color-mascot-pink-deep)]",
};

const sizeStyles: Record<BadgeSize, string> = {
  xs: "text-[10px] px-1.5 py-0.5",
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-1",
};

export function Badge({
  tone = "neutral",
  size = "sm",
  outlined = false,
  className = "",
  children,
}: BadgeProps) {
  const base = "inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap";
  const border = outlined ? `border ${toneOutlineStyles[tone]}` : "";
  return (
    <span className={`${base} ${toneStyles[tone]} ${sizeStyles[size]} ${border} ${className}`.trim()}>
      {children}
    </span>
  );
}
