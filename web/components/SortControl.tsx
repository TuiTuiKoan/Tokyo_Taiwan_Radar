"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";

export type SortKey = "newest" | "date" | "endingSoon";

const ORDER: SortKey[] = ["newest", "date", "endingSoon"];

const LABEL_KEY: Record<SortKey, string> = {
  newest: "sortNewest",
  date: "sortDate",
  endingSoon: "sortEndingSoon",
};

interface Props {
  value: SortKey;
}

export default function SortControl({ value }: Props) {
  const t = useTranslations("home");
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const setSort = useCallback(
    (key: SortKey) => {
      const params = new URLSearchParams(sp.toString());
      if (key === "newest") params.delete("sort");
      else params.set("sort", key);
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, sp],
  );

  const activeIndex = ORDER.indexOf(value);

  return (
    <div
      role="radiogroup"
      aria-label={t("sortLabel")}
      className="relative inline-flex items-center rounded-full bg-muted p-1 text-xs font-medium"
    >
      {/* Sliding selected indicator */}
      <span
        aria-hidden
        className="absolute top-1 bottom-1 left-1 rounded-full bg-surface dark:bg-elevated shadow-sm motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out"
        style={{
          width: `calc((100% - 0.5rem) / ${ORDER.length})`,
          transform: `translateX(${activeIndex * 100}%)`,
        }}
      />
      {ORDER.map((key) => {
        const selected = key === value;
        return (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setSort(key)}
            className={`relative z-10 px-3 py-1.5 rounded-full whitespace-nowrap transition-colors hover:text-fg-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
              selected
                ? "text-fg-strong font-bold"
                : "text-fg-muted"
            }`}
          >
            {t(LABEL_KEY[key])}
          </button>
        );
      })}
    </div>
  );
}
