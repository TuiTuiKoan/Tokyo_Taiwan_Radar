"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useState, useEffect } from "react";
import { useMaybeEventFilters } from "@/components/EventFilterContext";

export type SortKey = "newest" | "date" | "endingSoon";

const ORDER: SortKey[] = ["newest", "date", "endingSoon"];

const LABEL_KEY: Record<SortKey, string> = {
  newest: "sortNewest",
  date: "sortDate",
  endingSoon: "sortEndingSoon",
};

function normalizeSortKey(value: string | undefined | null): SortKey {
  return value === "date" || value === "endingSoon" ? value : "newest";
}

interface Props {
  value: SortKey;
}

export default function SortControl({ value }: Props) {
  const t = useTranslations("home");
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const shared = useMaybeEventFilters();

  // Eager client visual state for instant interactive transitions.
  const incomingValue = normalizeSortKey(shared?.filters.sort ?? value);
  const [activeValue, setActiveValue] = useState<SortKey>(incomingValue);
  const [prevValue, setPrevValue] = useState<SortKey>(incomingValue);

  // Instantly reflect external/prop value changes (e.g. backward history navigations or initial loads).
  if (incomingValue !== prevValue) {
    setActiveValue(incomingValue);
    setPrevValue(incomingValue);
  }

  const setSort = useCallback(
    (key: SortKey) => {
      setActiveValue(key); // Instant animation triggers on first frame
      if (shared) {
        shared.setFilters((prev) => ({ ...prev, sort: key }));
        return;
      }
      const params = new URLSearchParams(sp.toString());
      if (key === "newest") params.delete("sort");
      else params.set("sort", key);
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, sp, shared],
  );

  const activeIndex = ORDER.indexOf(activeValue);

  return (
    <div
      role="radiogroup"
      aria-label={t("sortLabel")}
      className="relative inline-flex items-center rounded-full bg-mascot-pink/20 p-1.5 text-xs font-medium w-[270px] sm:w-[300px]"
    >
      {/* Sliding selected indicator */}
      <span
        aria-hidden
        className="absolute top-1 bottom-1 left-1 rounded-full bg-blush dark:bg-elevated shadow-sm motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out"
        style={{
          width: `calc((100% - 0.75rem) / ${ORDER.length})`,
          transform: `translateX(${activeIndex * 100}%)`,
        }}
      />
      {ORDER.map((key) => {
        const selected = key === activeValue;
        return (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setSort(key)}
            className={`flex-1 text-center relative z-10 px-1 sm:px-3 py-1.75 rounded-full whitespace-nowrap leading-none transition-colors hover:text-fg-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
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
