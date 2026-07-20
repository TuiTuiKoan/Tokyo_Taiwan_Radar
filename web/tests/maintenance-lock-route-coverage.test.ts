import assert from "node:assert/strict";
import test from "node:test";

import { POST as accountAnnotatePost } from "../app/api/account/annotate-event/route";
import { POST as adminAnnotatePost } from "../app/api/admin/annotate-event/route";
import { POST as annotateNowPost } from "../app/api/admin/annotate-now/route";
import { POST as enrichAndAnnotatePost } from "../app/api/admin/enrich-and-annotate/route";
import { PATCH as reviewStatusPatch } from "../app/api/admin/events/[id]/review-status/route";
import { POST as scrapeNowPost } from "../app/api/admin/scrape-now/route";

const ENV_KEYS = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "SUPABASE_SERVICE_ROLE_KEY",
] as const;

test("all six routes fail closed before auth, params, body, database, or fetch", async () => {
  const originalEnv = ENV_KEYS.map((key) => [key, process.env[key]] as const);
  const originalFetch = globalThis.fetch;
  const poisonRequest = {
    json() {
      throw new Error("request body must not be read");
    },
  };
  const poisonContext = Object.defineProperty({}, "params", {
    get() {
      throw new Error("route params must not be read");
    },
  });

  const routes = [
    { name: "account annotate-event", invoke: () => accountAnnotatePost(poisonRequest as never) },
    { name: "admin annotate-event", invoke: () => adminAnnotatePost(poisonRequest as never) },
    { name: "review-status", invoke: () => reviewStatusPatch(poisonRequest as never, poisonContext as never) },
    { name: "annotate-now", invoke: () => annotateNowPost() },
    { name: "scrape-now", invoke: () => scrapeNowPost(poisonRequest as never) },
    { name: "enrich-and-annotate", invoke: () => enrichAndAnnotatePost(poisonRequest as never) },
  ];

  for (const key of ENV_KEYS) delete process.env[key];
  globalThis.fetch = (() => {
    throw new Error("external fetch must not run");
  }) as typeof fetch;

  try {
    for (const route of routes) {
      const response = await route.invoke();
      assert.equal(response.status, 503, `${route.name} must use maintenance status`);
      assert.deepEqual(
        await response.json(),
        { error: "maintenance_active" },
        `${route.name} must return the maintenance error contract`,
      );
    }
  } finally {
    for (const [key, value] of originalEnv) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    globalThis.fetch = originalFetch;
  }
});