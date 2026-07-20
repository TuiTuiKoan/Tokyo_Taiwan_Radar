import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const WEB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MIGRATION_PATH = path.resolve(
  WEB_ROOT,
  "../supabase/migrations/094_admin_reports_maintenance_lock.sql",
);
const MIGRATION_SQL = fs.readFileSync(MIGRATION_PATH, "utf8");
const NORMALIZED_SQL = MIGRATION_SQL.replace(/\s+/g, " ");
const GUARDED_TABLES = [
  "events",
  "event_reports",
  "field_corrections",
  "category_corrections",
  "selection_reason_corrections",
  "works",
] as const;

type LockState = "inactive" | "active" | "missing" | "malformed";
type WriterRole = "authenticated" | "service_role";

function handlerAllows(state: LockState): boolean {
  return state === "inactive";
}

function statementAllows(role: WriterRole, state: LockState): boolean {
  return role === "service_role" || state === "inactive";
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

test("migration 094 contract rejects an authenticated write if the lock activates after handler check", () => {
  assert.match(
    NORMALIZED_SQL,
    /SELECT NOT EXISTS \( SELECT 1 FROM public\.app_settings WHERE key = 'admin_reports_cleanup_maintenance' AND value->>'active' = 'false' \);/,
  );

  let restrictivePolicies = 0;
  for (const table of GUARDED_TABLES) {
    for (const command of ["INSERT", "UPDATE", "DELETE"] as const) {
      const policyName = `${table}_maint_block_${command.toLowerCase()}`;
      const policyPattern = new RegExp(
        `CREATE POLICY "${policyName}" ON public\\.${table} AS RESTRICTIVE FOR ${command} TO public [^;]*NOT public\\.admin_reports_maintenance_active\\(\\)[^;]*;`,
      );
      assert.match(NORMALIZED_SQL, policyPattern);
      restrictivePolicies += 1;
    }
  }
  assert.equal(restrictivePolicies, 18);

  let lockState: LockState = "inactive";
  assert.equal(handlerAllows(lockState), true);
  lockState = "active";
  assert.equal(statementAllows("authenticated", lockState), false);
});

test("service-role in-flight model drains before the settle margin while new requests are blocked", async () => {
  let lockState: LockState = "inactive";
  const writeReleased = deferred();
  const inFlightStarted = deferred();
  const order: string[] = [];

  async function runServiceRoute(label: "in-flight" | "new") {
    if (!handlerAllows(lockState)) {
      order.push(`${label}:maintenance_active`);
      return "maintenance_active" as const;
    }

    order.push(`${label}:handler_allowed`);
    if (label === "in-flight") inFlightStarted.resolve();
    await writeReleased.promise;
    const result = statementAllows("service_role", lockState)
      ? "completed"
      : "statement_denied";
    order.push(`${label}:${result}`);
    return result;
  }

  const inFlight = runServiceRoute("in-flight");
  await inFlightStarted.promise;
  lockState = "active";
  order.push("lock:acquired");

  assert.equal(await runServiceRoute("new"), "maintenance_active");
  writeReleased.resolve();
  assert.equal(await inFlight, "completed");
  order.push("settle:margin_complete");

  assert.deepEqual(order, [
    "in-flight:handler_allowed",
    "lock:acquired",
    "new:maintenance_active",
    "in-flight:completed",
    "settle:margin_complete",
  ]);
});

test.todo("Slice 3 browser-bypass fixture verifies relocated client writers");