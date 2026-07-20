/**
 * Server-only maintenance-lock READ helper for the Admin Reports (#204) cleanup
 * window (decision-16a / 16b).
 *
 * SERVER-ONLY: this module uses the Supabase SERVICE-ROLE key and must never be
 * imported into a Client Component. It is imported only from "use server" action
 * modules (the app/actions/*.ts files); the `.server.ts` suffix + that import
 * discipline is the server-only guard. (The `server-only` npm package is not a
 * dependency of this workspace, so a literal `import "server-only"` is not used.)
 *
 * READ-ONLY: it never acquires or releases the lock. The operator CLI
 * scraper/_oneoff_admin_reports_maintenance.py is the sole lifecycle owner
 * (decision-16b). This helper only answers "are writes currently allowed?".
 *
 * FAIL-CLOSED: writes are allowed ONLY when the single app_settings row keyed
 * `admin_reports_cleanup_maintenance` exists AND its value.active is exactly the
 * boolean false. A missing row, a read error, unconfigured env, or any malformed
 * / non-`false` value all deny — mirroring the DB predicate installed by
 * migration 094 (`admin_reports_maintenance_active()`), which allows writes only
 * when `value->'active' = 'false'::jsonb` (the exact JSON boolean false).
 */
import { createClient } from "@supabase/supabase-js";
import {
  evaluateMaintenanceLockRead,
  type WritesAllowed,
} from "@/lib/maintenanceLockCore";

const LOCK_KEY = "admin_reports_cleanup_maintenance";

/**
 * Reads the maintenance lock through a service-role client and reports whether
 * writes are currently permitted. Never throws — every failure path returns the
 * fail-closed DENIED result.
 */
export async function assertWritesAllowed(): Promise<WritesAllowed> {
  return evaluateMaintenanceLockRead({
    url: process.env.NEXT_PUBLIC_SUPABASE_URL,
    serviceKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
    readLock: async (url, serviceKey) => {
      const admin = createClient(url, serviceKey, {
        auth: { persistSession: false, autoRefreshToken: false },
      });
      return admin
        .from("app_settings")
        .select("value")
        .eq("key", LOCK_KEY)
        .limit(1);
    },
  });
}
