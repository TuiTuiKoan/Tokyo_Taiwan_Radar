"use server";

import { createClient } from "@/lib/supabase/server";

/**
 * Dismiss an event report.  Runs server-side so the admin session is resolved
 * from the cookie by createClient (no RLS/JWT issues from browser client).
 */
export async function dismissReport(reportId: string): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();

  const { error, data } = await supabase
    .from("event_reports")
    .update({ status: "dismissed" })
    .eq("id", reportId)
    .select("id");

  if (error) {
    return { ok: false, error: error.message };
  }
  if (!data || data.length === 0) {
    return { ok: false, error: "0 rows updated — report not found or permission denied" };
  }
  return { ok: true };
}
