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
    recordEventView(eventId, locale);
    // Run once on mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
