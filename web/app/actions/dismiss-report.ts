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
    // Write confirmed_at as the handled timestamp so the security-report
    // lifecycle treats a dismissed finding as resolved (mirrors auto_qa.py,
    // which also stamps confirmed_at on dismissed rows). Without this the
    // handled_at falls back to created_at and a later event update would
    // wrongly re-open the pending report.
    .update({ status: "dismissed", confirmed_at: new Date().toISOString() })
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
