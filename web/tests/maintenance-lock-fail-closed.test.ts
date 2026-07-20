import assert from "node:assert/strict";
import test from "node:test";

import {
  evaluateMaintenanceLockRead,
  type MaintenanceLockReader,
} from "../lib/maintenanceLockCore";

const URL = "https://example.supabase.co";
const SERVICE_KEY = "service-role-key";
const DENIED = { allowed: false, reason: "maintenance_active" };

function evaluate(
  readLock: MaintenanceLockReader,
  env: { url?: string; serviceKey?: string } = { url: URL, serviceKey: SERVICE_KEY },
) {
  return evaluateMaintenanceLockRead({
    url: env.url,
    serviceKey: env.serviceKey,
    readLock,
  });
}

test("maintenance lock fails closed when either environment variable is missing", async () => {
  let reads = 0;
  const readLock: MaintenanceLockReader = async () => {
    reads += 1;
    return { data: [{ value: { active: false } }], error: null };
  };

  assert.deepEqual(await evaluate(readLock, { serviceKey: SERVICE_KEY }), DENIED);
  assert.deepEqual(await evaluate(readLock, { url: URL }), DENIED);
  assert.equal(reads, 0);
});

test("maintenance lock fails closed when client construction or the read throws", async () => {
  const constructionThrow: MaintenanceLockReader = () => {
    throw new Error("construction failed");
  };
  const readThrow: MaintenanceLockReader = async () => {
    await Promise.resolve();
    throw new Error("read failed");
  };

  assert.deepEqual(await evaluate(constructionThrow), DENIED);
  assert.deepEqual(await evaluate(readThrow), DENIED);
});

test("maintenance lock fails closed on a Supabase read error or missing row", async () => {
  assert.deepEqual(
    await evaluate(async () => ({
      data: [{ value: { active: false } }],
      error: { message: "read failed" },
    })),
    DENIED,
  );
  assert.deepEqual(await evaluate(async () => ({ data: null, error: null })), DENIED);
  assert.deepEqual(await evaluate(async () => ({ data: [], error: null })), DENIED);
});

test("maintenance lock fails closed on malformed, non-object, or array values", async () => {
  const malformedValues: unknown[] = [undefined, null, 0, "false", [], [false]];

  for (const value of malformedValues) {
    assert.deepEqual(
      await evaluate(async () => ({ data: [{ value }], error: null })),
      DENIED,
    );
  }
});

test("maintenance lock fails closed for active true and non-boolean false values", async () => {
  const deniedValues: unknown[] = [
    { active: true },
    { active: "false" },
    { active: 0 },
    { active: null },
    {},
  ];

  for (const value of deniedValues) {
    assert.deepEqual(
      await evaluate(async () => ({ data: [{ value }], error: null })),
      DENIED,
    );
  }
});

test("maintenance lock allows writes only for exact boolean active false", async () => {
  assert.deepEqual(
    await evaluate(async () => ({
      data: [{ value: { active: false, window_id: null } }],
      error: null,
    })),
    { allowed: true },
  );
});
