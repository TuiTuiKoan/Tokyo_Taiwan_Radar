"use server";

import { assertWritesAllowed } from "@/lib/maintenanceLock.server";
import { runDismissReport } from "@/lib/reportActionsCore";

export async function dismissReport(reportId: string): Promise<{ ok: boolean; error?: string }> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const { createClient } = await import("@/lib/supabase/server");
  const supabase = await createClient();
  return runDismissReport(supabase, reportId);
}
