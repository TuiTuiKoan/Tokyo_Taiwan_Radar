import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import { ACCOUNT_AI_LIMITS, quotaRefusal } from "../lib/llm/accountQuota.server";

const webRoot = path.resolve(__dirname, "..");
const read = (rel: string) => readFileSync(path.join(webRoot, rel), "utf8");

test("a positive count lets the call through", () => {
  assert.equal(quotaRefusal("annotate", 1, null), null);
  assert.equal(quotaRefusal("extract", ACCOUNT_AI_LIMITS.extract.perUser, null), null);
});

test("-1 refuses with the per-user limit, -2 with the site-wide error", () => {
  assert.deepEqual(quotaRefusal("extract", -1, null), {
    status: 429,
    body: { error: "aiQuotaExceeded", limit: ACCOUNT_AI_LIMITS.extract.perUser },
  });
  assert.deepEqual(quotaRefusal("annotate", -2, null), {
    status: 429,
    body: { error: "aiSystemQuotaExceeded" },
  });
});

test("an RPC error or a non-number result fails closed", () => {
  assert.equal(quotaRefusal("annotate", null, { message: "function does not exist" })?.status, 503);
  assert.equal(quotaRefusal("annotate", null, null)?.status, 503);
  assert.equal(quotaRefusal("annotate", "3", null)?.status, 503);
});

for (const [route, kind] of [
  ["app/api/account/annotate-event/route.ts", "annotate"],
  ["app/api/account/extract-from-image/route.ts", "extract"],
] as const) {
  test(`${route} consumes the ${kind} quota before calling OpenAI`, () => {
    const src = read(route);
    const quota = src.indexOf(`consumeAccountAiQuota(serviceClient, user.id, "${kind}")`);
    const call = src.indexOf("openaiChat({");
    assert.ok(quota > 0, "quota check missing");
    assert.ok(call > quota, "quota must be consumed before the OpenAI call");
  });
}

test("every quota error the routes return has a message in all three locales", () => {
  for (const locale of ["ja", "zh", "en"]) {
    const intake = JSON.parse(read(`messages/${locale}.json`)).eventIntake as Record<string, string>;
    for (const key of ["aiQuotaExceeded", "aiSystemQuotaExceeded", "aiQuotaUnavailable"]) {
      assert.ok(intake[key], `${locale} eventIntake.${key} missing`);
    }
    assert.match(intake.aiQuotaExceeded, /\{limit\}/);
  }
  const wizard = read("components/EventIntakeWizard.tsx");
  for (const key of ["aiQuotaExceeded", "aiSystemQuotaExceeded", "aiQuotaUnavailable"]) {
    assert.ok(wizard.includes(`error === "${key}"`), `wizard does not map ${key}`);
  }
});

test("migration 104 keeps the quota RPC service-role only", () => {
  const sql = read("../supabase/migrations/104_account_ai_quota.sql");
  assert.match(sql, /security invoker/);
  assert.match(sql, /set search_path = pg_catalog/);
  assert.match(sql, /revoke execute on function public\.consume_account_ai_quota\(uuid, text, integer, integer\)\s+from public, anon, authenticated/);
  assert.match(sql, /grant execute on function public\.consume_account_ai_quota\(uuid, text, integer, integer\)\s+to service_role/);
  assert.match(sql, /at time zone 'Asia\/Tokyo'/);
});
