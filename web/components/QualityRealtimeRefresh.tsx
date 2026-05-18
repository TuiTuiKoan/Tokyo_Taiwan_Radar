"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

/**
 * Invisible client component mounted inside AdminQualityPage.
 * Subscribes to postgres_changes on the `events` table and calls
 * router.refresh() so the Server Component re-fetches quality data
 * automatically whenever an event is updated in another tab.
 */
export default function QualityRealtimeRefresh() {
  const router = useRouter();

  useEffect(() => {
    const sb = createClient();
    const channel = sb
      .channel("quality-page-refresh")
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "events" },
        () => {
          router.refresh();
        }
      )
      .subscribe();
    return () => {
      sb.removeChannel(channel);
    };
  }, [router]);

  return null;
}
