"use server";

import { assertWritesAllowed } from "@/lib/maintenanceLock.server";
import {
  runConfirmReport,
  type ConfirmReportInput,
  type ConfirmReportResult,
} from "@/lib/reportActionsCore";

export async function confirmReport(
  input: ConfirmReportInput
): Promise<ConfirmReportResult> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, githubUpdated: false, error: "maintenance_active" };
  const { createClient } = await import("@/lib/supabase/server");
  const supabase = await createClient();
  return runConfirmReport(supabase, input);
}
