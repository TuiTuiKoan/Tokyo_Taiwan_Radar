"use server";

import type { SupabaseClient } from "@supabase/supabase-js";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";

/**
 * Dismiss an event report.  Runs server-side so the admin session is resolved
 * from the cookie by createClient (no RLS/JWT issues from browser client).
 */
export async function dismissReport(reportId: string): Promise<{ ok: boolean; error?: string }> {
  // Maintenance-lock gate (decision-16a): refuse the write while the Admin
  // Reports cleanup window is open. Placed on the entry (not the testable core)
  // so runDismissReport's injected-client CAS logic stays untouched.
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  // Dynamic import so unit tests can import this module (and the testable core
  // below) without pulling next/headers at load time; createClient reads cookies.
  const { createClient } = await import("@/lib/supabase/server");
  const supabase = await createClient();
  return runDismissReport(supabase, reportId);
}

// Testable core. Accepts an injected Supabase client so the pending compare-and-set
// and exactly-one-row semantics can be unit-tested with a fake. Exported (async) from
// this "use server" module; no client component imports it, so it is never invoked as
// a client-callable action with a non-serializable argument.
export async function runDismissReport(
  supabase: SupabaseClient,
  reportId: string
): Promise<{ ok: boolean; error?: string }> {
  const { error, data } = await supabase
    .from("event_reports")
    // Pending compare-and-set: filter on id + status='pending' so a report a
    // concurrent confirm/dismiss already moved off pending loses the race instead of
    // being double-dismissed. .select("id") + exactly-one-row is the guard.
    //
    // Write confirmed_at as the handled timestamp so the security-report lifecycle
    // treats a dismissed finding as resolved (mirrors auto_qa.py, which also stamps
    // confirmed_at on dismissed rows). Without this the handled_at falls back to
    // created_at and a later event update would wrongly re-open the pending report.
    .update({ status: "dismissed", confirmed_at: new Date().toISOString() })
    .eq("id", reportId)
    .eq("status", "pending")
    .select("id");

  if (error) {
    return { ok: false, error: error.message };
  }
  if (!data || data.length === 0) {
    return { ok: false, error: "0 rows updated — report not found or not pending" };
  }
  if (data.length > 1) {
    return { ok: false, error: "Multiple pending reports for id" };
  }
  return { ok: true };
}
