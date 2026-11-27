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
    // document.referrer, not the action's Referer header: the header is this
    // page itself. In a client-side navigation it keeps the landing referrer,
    // so views in one visit share the visit's source.
    recordEventView(eventId, locale, utmSource, document.referrer);
    // Run once on mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
