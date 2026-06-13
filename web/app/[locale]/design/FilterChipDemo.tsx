"use client";

import { FilterChip } from "@/lib/design";
import { useTranslations } from "next-intl";

/**
 * Client-side wrapper for the FilterChip demo on /design.
 * Wrapping in "use client" is required because FilterChip needs onRemove
 * (a function), which cannot cross the RSC boundary.
 */
export function FilterChipDemo() {
  const t = useTranslations("designPreview.components");

  return (
    <div className="flex flex-wrap gap-2">
      <FilterChip label={t("filterMovie")} onRemove={() => console.log("remove movie")} />
      <FilterChip label={t("filterPerformingArts")} onRemove={() => console.log("remove music")} />
      <FilterChip label={t("filterTaiwanJapan")} onRemove={() => console.log("remove tj")} />
      <FilterChip label={t("filterKeyword")} onRemove={() => console.log("remove q")} />
    </div>
  );
}
