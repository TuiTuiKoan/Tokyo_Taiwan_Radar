"use client";

import { useEffect } from "react";
import { recordEventView } from "@/app/actions/record-view";

interface Props {
  eventId: string;
  locale: string;
}

/**
 * Invisible client component that fires a view record on mount.
 * Placed once in event detail pages — no visible output.
 */
export default function ViewTracker({ eventId, locale }: Props) {
  useEffect(() => {
    const utmSource = new URLSearchParams(window.location.search).get("utm_source");
    recordEventView(eventId, locale, utmSource);
    // Run once on mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
