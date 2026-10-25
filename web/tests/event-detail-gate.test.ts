import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  EVENT_DETAIL_PATH,
  decideEventDetail,
  fetchEventStub,
  type EventStub,
} from "../lib/eventDetailGate";

const stub = (over: Partial<EventStub> = {}): EventStub => ({
  id: "3d74504d-f4bb-4697-8804-458ae0b7aafb",
  merged_into_event_id: null,
  is_active: true,
  annotation_status: "annotated",
  ...over,
});

test("decideEventDetail serves active annotated and reviewed events", () => {
  assert.deepEqual(decideEventDetail(stub()), { kind: "serve" });
  assert.deepEqual(decideEventDetail(stub({ annotation_status: "reviewed" })), { kind: "serve" });
});

test("decideEventDetail answers 404 for missing, inactive and unannotated events", () => {
  assert.deepEqual(decideEventDetail(null), { kind: "not-found" });
  assert.deepEqual(decideEventDetail(stub({ is_active: false })), { kind: "not-found" });
  assert.deepEqual(decideEventDetail(stub({ annotation_status: "pending" })), { kind: "not-found" });
  assert.deepEqual(decideEventDetail(stub({ annotation_status: null })), { kind: "not-found" });
});

test("decideEventDetail redirects merged events even when they are inactive", () => {
  const target = "9e1c9b0b-d191-4ae1-b420-305dbc19570b";
  assert.deepEqual(
    decideEventDetail(stub({ merged_into_event_id: target, is_active: false })),
    { kind: "redirect", targetId: target }
  );
});

test("EVENT_DETAIL_PATH matches only locale-prefixed detail pages", () => {
  const id = "3d74504d-f4bb-4697-8804-458ae0b7aafb";
  assert.ok(EVENT_DETAIL_PATH.test(`/ja/events/${id}`));
  assert.ok(EVENT_DETAIL_PATH.test(`/zh/events/${id}/`));
  assert.ok(!EVENT_DETAIL_PATH.test(`/ja/events/${id}/opengraph-image`));
  assert.ok(!EVENT_DETAIL_PATH.test(`/fr/events/${id}`));
  assert.ok(!EVENT_DETAIL_PATH.test(`/ja/events/not-a-uuid`));
  assert.ok(!EVENT_DETAIL_PATH.test(`/ja/events`));
});

test("fetchEventStub fails open on missing env, HTTP errors and network errors", async () => {
  const id = "3d74504d-f4bb-4697-8804-458ae0b7aafb";
  const never = (async () => {
    throw new Error("must not be called");
  }) as unknown as typeof fetch;
  assert.equal(await fetchEventStub(id, { url: undefined, serviceRoleKey: "k" }, never), undefined);
  assert.equal(await fetchEventStub(id, { url: "http://x", serviceRoleKey: undefined }, never), undefined);

  const http500 = (async () => new Response("boom", { status: 500 })) as unknown as typeof fetch;
  assert.equal(await fetchEventStub(id, { url: "http://x", serviceRoleKey: "k" }, http500), undefined);
  const down = (async () => {
    throw new Error("down");
  }) as unknown as typeof fetch;
  assert.equal(await fetchEventStub(id, { url: "http://x", serviceRoleKey: "k" }, down), undefined);
});

test("fetchEventStub returns the row, or null when the event does not exist", async () => {
  const id = "3d74504d-f4bb-4697-8804-458ae0b7aafb";
  let seen = "";
  const found = (async (url: string) => {
    seen = url;
    return Response.json([stub()]);
  }) as unknown as typeof fetch;
  const row = await fetchEventStub(id, { url: "http://x", serviceRoleKey: "k" }, found);
  assert.equal(row?.id, id);
  assert.match(seen, /id=eq\.3d74504d-f4bb-4697-8804-458ae0b7aafb/);

  const empty = (async () => Response.json([])) as unknown as typeof fetch;
  assert.equal(await fetchEventStub(id, { url: "http://x", serviceRoleKey: "k" }, empty), null);
});

test("proxy runs the gate before the auth refresh and page.tsx keeps its own gates", () => {
  const read = (p: string) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), "utf8");
  const proxy = read("../proxy.ts");
  assert.ok(proxy.indexOf("decideEventDetail(") > 0);
  assert.ok(proxy.indexOf("decideEventDetail(") < proxy.indexOf("supabase.auth.getUser()"));
  assert.match(proxy, /status: 308|NextResponse\.redirect\([^)]*308/);
  const page = read("../app/[locale]/events/[id]/page.tsx");
  assert.match(page, /if \(!stub \|\| !stub\.is_active\) \{\s*notFound\(\);/);
  assert.match(page, /if \(!event\.is_active\) \{\s*notFound\(\);/);
});
