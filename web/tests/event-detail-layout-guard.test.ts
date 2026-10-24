import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const read = (relative: string) =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const layout = read("../app/[locale]/events/[id]/layout.tsx");
const page = read("../app/[locale]/events/[id]/page.tsx");

test("event detail layout settles 404 and redirect before the loading boundary", () => {
  assert.match(layout, /\.from\("events"\)/);
  assert.match(layout, /merged_into_event_id/);
  assert.match(layout, /permanentRedirect\(/);
  assert.match(layout, /!stub \|\| !stub\.is_active/);
  assert.match(layout, /annotation_status !== "annotated" && stub\.annotation_status !== "reviewed"/);
  assert.equal((layout.match(/^\s+notFound\(\);/gm) ?? []).length, 2);
  assert.match(layout, /return children;/);
});

test("event detail layout uses the service-role client and never a cookie client", () => {
  assert.match(layout, /SUPABASE_SERVICE_ROLE_KEY/);
  assert.doesNotMatch(layout, /lib\/supabase\/server/);
  assert.doesNotMatch(layout, /"use client"/);
});

test("page.tsx keeps its own inactive and annotation gates", () => {
  assert.match(page, /if \(!stub \|\| !stub\.is_active\) \{\s*notFound\(\);/);
  assert.match(page, /if \(!event\.is_active\) \{\s*notFound\(\);/);
});
