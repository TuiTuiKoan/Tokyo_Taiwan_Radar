/**
 * DateChip — locale-aware date / range display.
 *
 * Renders:
 *  - single date:   "5月13日 (水)" / "May 13" / "5/13 (三)"
 *  - range:         "5月13日 – 5月20日"
 *  - stacked block: weekday + month/day + optional time (used in mobile cards)
 *
 * Variants:
 *  - "inline" — one-line "📅 5月13日 – 5月20日"
 *  - "stacked" — block with WED / 05/13 / 19:00 (mobile-style)
 *
 * Falls back gracefully if start_date is null.
 */
import type { Locale } from "@/lib/types";

export type DateChipVariant = "inline" | "stacked";

export interface DateChipProps {
  start: string | null;
  end?: string | null;
  /** Optional human time string (e.g. "19:00", "全日") for stacked variant. */
  time?: string | null;
  locale: Locale;
  variant?: DateChipVariant;
  className?: string;
}

function formatDate(iso: string, locale: Locale, opts: Intl.DateTimeFormatOptions) {
  const bcp = locale === "zh" ? "zh-TW" : locale === "ja" ? "ja-JP" : "en-US";
  return new Date(iso).toLocaleDateString(bcp, opts);
}

function weekdayLabel(iso: string, locale: Locale) {
  const bcp = locale === "zh" ? "zh-TW" : locale === "ja" ? "ja-JP" : "en-US";
  return new Date(iso).toLocaleDateString(bcp, { weekday: "short" });
}

export function DateChip({
  start,
  end,
  time,
  locale,
  variant = "inline",
  className = "",
}: DateChipProps) {
  if (!start) return null;

  if (variant === "stacked") {
    // 2026-05-13 → "05/13"
    const md = start.slice(5).replace("-", "/");
    return (
      <div className={`inline-flex flex-col items-center text-center ${className}`.trim()}>
        <span className="text-[10px] font-bold uppercase text-[var(--color-mascot-pink-deep)] tracking-wider">
          {weekdayLabel(start, locale)}
        </span>
        <span className="font-mono text-lg font-black text-fg-strong leading-tight">
          {md}
        </span>
        {time && <span className="text-[10px] text-fg-muted mt-0.5">{time}</span>}
      </div>
    );
  }

  // inline variant
  const startStr = formatDate(start, locale, { month: "short", day: "numeric" });
  const endStr =
    end && end !== start ? formatDate(end, locale, { month: "short", day: "numeric" }) : null;

  return (
    <span className={`inline-flex items-center gap-1 text-xs text-fg-muted ${className}`.trim()}>
      <span aria-hidden="true">📅</span>
      <span>
        {startStr}
        {endStr && <> – {endStr}</>}
      </span>
    </span>
  );
}
