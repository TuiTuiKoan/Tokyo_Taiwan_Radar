/**
 * FilterChip — a removable Badge used to display active filters.
 *
 * Composed from Badge (success tone, outlined) + a small ✕ button.
 * Used in EventList active-filters strip and mobile horizontal chip row.
 *
 * Accessibility:
 *  - Renders as a single button; clicking anywhere removes the chip.
 *  - aria-label combines the label and the action ("Remove filter X").
 */
"use client";

import { Badge, type BadgeTone } from "./Badge";

export interface FilterChipProps {
  label: string;
  /** Called when the chip is clicked / dismissed. */
  onRemove: () => void;
  /** Visual tone — defaults to success (matches selected-state green). */
  tone?: BadgeTone;
  /** aria-label override; defaults to "Remove {label}". */
  removeLabel?: string;
  className?: string;
}

export function FilterChip({
  label,
  onRemove,
  tone = "success",
  removeLabel,
  className = "",
}: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onRemove}
      aria-label={removeLabel ?? `Remove ${label}`}
      className={`inline-flex items-center hover:opacity-80 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-green-400 rounded-full ${className}`.trim()}
    >
      <Badge tone={tone} size="sm" outlined>
        {label}
        <span aria-hidden="true" className="ml-1 text-fg-muted">
          ✕
        </span>
      </Badge>
    </button>
  );
}
