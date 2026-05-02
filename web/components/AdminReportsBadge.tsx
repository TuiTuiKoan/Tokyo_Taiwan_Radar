"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

interface Props {
  initialCount: number;
}

/**
 * Client component that shows the pending-reports badge and keeps it
 * in sync via Supabase Realtime, without requiring a page refresh.
 *
 * - INSERT  → increment count by 1 (new report is always "pending")
 * - UPDATE  → re-fetch accurate count (report confirmed / dismissed)
 */
export default function AdminReportsBadge({ initialCount }: Props) {
  const [count, setCount] = useState(initialCount);

  useEffect(() => {
    const supabase = createClient();

    async function refreshCount() {
      const { count: fresh } = await supabase
        .from("event_reports")
        .select("*", { count: "exact", head: true })
        .eq("status", "pending");
      setCount(fresh ?? 0);
    }

    const channel = supabase
      .channel("admin-reports-badge")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "event_reports" },
        () => {
          // New report is always created with status = "pending"
          setCount((c) => c + 1);
        }
      )
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "event_reports" },
        () => {
          // A report was confirmed or dismissed — re-fetch accurate count
          void refreshCount();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  if (count === 0) return null;
  return (
    <span className="inline-flex items-center justify-center min-w-[1.1rem] h-4 px-1 text-[10px] font-bold rounded-full bg-red-500 text-white leading-none">
      {count}
    </span>
  );
}
