"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Dispatch, SetStateAction } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { EventFilters } from "@/lib/eventFilter";

const EventFilterContext = createContext<{
  filters: EventFilters;
  setFilters: Dispatch<SetStateAction<EventFilters>>;
} | null>(null);

export function useMaybeEventFilters() {
  return useContext(EventFilterContext);
}

export function EventFilterProvider({
  children,
  initialFilters,
}: {
  children: ReactNode;
  initialFilters: EventFilters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [filters, setFilters] = useState<EventFilters>(initialFilters);

  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  useEffect(() => {
    const next = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value && !(key === "sort" && value === "newest") && !(key === "timeMode" && value === "active")) {
        next.set(key, value);
      }
    });
    const nextUrl = next.toString() ? `${pathname}?${next.toString()}` : pathname;
    const current = `${pathname}${sp.toString() ? `?${sp.toString()}` : ""}`;
    if (nextUrl !== current) {
      const id = setTimeout(() => {
        router.replace(nextUrl, { scroll: false });
      }, 0);
      return () => clearTimeout(id);
    }
  }, [filters, pathname, router, sp]);

  const value = useMemo(() => ({ filters, setFilters }), [filters]);

  return <EventFilterContext.Provider value={value}>{children}</EventFilterContext.Provider>;
}

export function useEventFilters() {
  const ctx = useMaybeEventFilters();
  if (!ctx) throw new Error("useEventFilters must be used within EventFilterProvider");
  return ctx;
}
