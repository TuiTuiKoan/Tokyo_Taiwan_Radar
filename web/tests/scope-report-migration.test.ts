import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const migrationPath = fileURLToPath(
  new URL("../../supabase/migrations/098_scope_report_transaction.sql", import.meta.url),
);
const sql = readFileSync(migrationPath, "utf8");

test("scope confirmation RPC is invoker-secured and locks both rows", () => {
  assert.match(sql, /CREATE OR REPLACE FUNCTION public\.confirm_scope_report\(/);
  assert.match(sql, /SECURITY INVOKER/);
  assert.doesNotMatch(sql, /confirm_scope_report[\s\S]*SECURITY DEFINER/);
  assert.equal((sql.match(/FOR UPDATE;/g) ?? []).length, 2);
  assert.match(sql, /reports\.status = 'pending'/);
  assert.match(sql, /token\.value = 'scopeHash:' \|\| p_expected_scope_hash/);
  assert.equal((sql.match(/is_active IS TRUE/g) ?? []).length, 2);
  assert.match(
    sql,
    /UPDATE public\.events[\s\S]*WHERE id = v_event_id\s+AND is_active IS TRUE;/,
  );
  assert.match(sql, /UPDATE public\.events[\s\S]*UPDATE public\.event_reports/);
  assert.match(sql, /REVOKE ALL ON FUNCTION[\s\S]*FROM PUBLIC, anon/);
  assert.match(sql, /GRANT EXECUTE ON FUNCTION[\s\S]*TO authenticated, service_role/);
});

test("public inserts cannot mint machine-owned report tokens", () => {
  assert.match(sql, /AS RESTRICTIVE[\s\S]*FOR INSERT[\s\S]*TO anon, authenticated/);
  for (const token of [
    "scopeReviewNonJapan",
    "auto_security_prompt_injection",
    "scopeDecision:%",
    "scopeRegion:%",
    "scopeHash:%",
    "securityHash:%",
    "securitySeverity:%",
  ]) {
    assert.ok(sql.includes(`'${token}'`), `migration reserves ${token}`);
  }
});
