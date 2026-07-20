import assert from "node:assert/strict";
import test from "node:test";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { FormState } from "../components/AdminEventForm";
import {
  runAssignWorkToEvents,
  runChangeAdminEventCategories,
  runDeactivateOwnerEventExact,
  runDeleteAdminEventExact,
  runDeleteOwnerEventExact,
  runDeleteWorkExact,
  runReannotateAdminEvent,
  runSaveAdminEditedEvent,
  runSetAdminEventsActive,
  runSetAdminEventsForceRescrape,
  runUpdateWorkExact,
} from "../lib/adminEventMutationsCore";

type Op = "select" | "update" | "upsert" | "delete";

interface RecordedCall {
  table: string;
  op: Op;
  columns?: string;
  filters: Array<["eq" | "in", string, unknown]>;
  payload?: unknown;
  onConflict?: string;
  single: boolean;
  returning: boolean;
}

interface Resp {
  data?: unknown;
  error?: { message: string } | null;
}

type Responder = (call: RecordedCall, index: number) => Resp;

class FakeBuilder {
  private readonly call: RecordedCall;
  private opSet = false;
  private settled = false;

  constructor(
    private readonly calls: RecordedCall[],
    private readonly responder: Responder,
    table: string,
  ) {
    this.call = { table, op: "select", filters: [], single: false, returning: false };
  }

  select(columns?: string): this {
    if (!this.opSet) {
      this.call.op = "select";
      this.call.columns = columns;
      this.opSet = true;
    } else {
      this.call.returning = true;
      this.call.columns = columns;
    }
    return this;
  }

  update(payload: unknown): this {
    this.call.op = "update";
    this.call.payload = payload;
    this.opSet = true;
    return this;
  }

  upsert(payload: unknown, options?: { onConflict?: string }): this {
    this.call.op = "upsert";
    this.call.payload = payload;
    this.call.onConflict = options?.onConflict;
    this.opSet = true;
    return this;
  }

  delete(): this {
    this.call.op = "delete";
    this.opSet = true;
    return this;
  }

  eq(column: string, value: unknown): this {
    this.call.filters.push(["eq", column, value]);
    return this;
  }

  in(column: string, values: unknown[]): this {
    this.call.filters.push(["in", column, values]);
    return this;
  }

  single(): Promise<Resp> {
    this.call.single = true;
    return this.settle();
  }

  then<TResult1 = Resp, TResult2 = never>(
    onfulfilled?: ((value: Resp) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
  ): Promise<TResult1 | TResult2> {
    return this.settle().then(onfulfilled, onrejected);
  }

  private settle(): Promise<Resp> {
    if (!this.settled) {
      this.settled = true;
      this.calls.push(this.call);
    }
    const response = this.responder(this.call, this.calls.length - 1);
    return Promise.resolve({ data: response.data ?? null, error: response.error ?? null });
  }
}

function makeClient(responder: Responder): { client: SupabaseClient; calls: RecordedCall[] } {
  const calls: RecordedCall[] = [];
  const client = {
    from: (table: string) => new FakeBuilder(calls, responder, table),
  };
  return { client: client as unknown as SupabaseClient, calls };
}

function route(map: Record<string, Resp | Responder>): Responder {
  return (call, index) => {
    const entry = map[`${call.table}:${call.op}`];
    if (typeof entry === "function") return entry(call, index);
    return entry ?? { data: null, error: null };
  };
}

function callsOf(calls: RecordedCall[], table: string, op: Op): RecordedCall[] {
  return calls.filter((call) => call.table === table && call.op === op);
}

const EVENT_1 = "11111111-1111-4111-8111-111111111111";
const EVENT_2 = "22222222-2222-4222-8222-222222222222";
const EVENT_3 = "33333333-3333-4333-8333-333333333333";
const WORK_1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const ADMIN_1 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const BASE_FORM: FormState = {
  name_ja: "更新名",
  name_zh: "",
  name_en: "",
  description_ja: "説明",
  description_zh: "",
  description_en: "",
  category: ["art"],
  start_date: "2026-07-20",
  end_date: "",
  location_name: "会場",
  location_address: "住所",
  location_url: "",
  business_hours: "",
  performer: "",
  organizer: "主催",
  organizer_url: "",
  event_form: ["exhibition"],
  co_organizers: null,
  sponsors: null,
  primary_language: "ja",
  has_japanese_support: false,
  has_english_support: false,
  has_chinese_support: false,
  is_paid: false,
  price_info: "",
  official_url: "",
  submission_url: "",
  source_url: "https://example.test/event",
  source_name: "source",
  original_language: "ja",
  is_active: true,
  parent_event_id: "",
  record_links: [],
};

function beforeEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: EVENT_1,
    raw_title: "原題",
    raw_description: "原文",
    category: ["movie"],
    event_form: ["screening"],
    co_organizers: [],
    sponsors: [],
    primary_language: "ja",
    has_japanese_support: false,
    has_english_support: false,
    has_chinese_support: false,
    name_ja: "旧名",
    name_zh: null,
    name_en: null,
    description_ja: "旧説明",
    description_zh: null,
    description_en: null,
    location_name: "旧会場",
    location_address: "旧住所",
    business_hours: null,
    price_info: null,
    performer: null,
    organizer: "旧主催",
    organizer_url: null,
    ...overrides,
  };
}

test("single event update fails when zero rows are returned", async () => {
  const { client } = makeClient(route({ "events:update": { data: [], error: null } }));
  const result = await runSetAdminEventsActive(client, [EVENT_1], true, "single");
  assert.equal(result.ok, false);
  assert.match(result.error ?? "", /exact/i);
});

test("bulk event update rejects zero, partial, and unexpected ID sets", async (t) => {
  for (const [name, rows] of [
    ["zero", []],
    ["partial", [{ id: EVENT_1 }]],
    ["unexpected", [{ id: EVENT_1 }, { id: EVENT_3 }]],
  ] as const) {
    await t.test(name, async () => {
      const { client } = makeClient(route({ "events:update": { data: rows, error: null } }));
      const result = await runSetAdminEventsForceRescrape(client, [EVENT_1, EVENT_2], true, "bulk");
      assert.equal(result.ok, false);
      assert.match(result.error ?? "", /exact/i);
    });
  }
});

test("bulk event update deduplicates IDs and accepts an exact returned set", async () => {
  const { client, calls } = makeClient(route({
    "events:update": { data: [{ id: EVENT_2 }, { id: EVENT_1 }], error: null },
  }));
  const result = await runSetAdminEventsForceRescrape(
    client,
    [EVENT_1, EVENT_2, EVENT_1],
    true,
    "bulk",
  );
  assert.equal(result.ok, true);
  assert.deepEqual(result.data?.ids, [EVENT_1, EVENT_2]);
  assert.deepEqual(callsOf(calls, "events", "update")[0].filters, [
    ["in", "id", [EVENT_1, EVENT_2]],
  ]);
});

test("runtime ID, category, and boolean inputs fail without database calls", async (t) => {
  const cases: Array<[string, (client: SupabaseClient) => Promise<{ ok: boolean; error?: string }>, string]> = [
    ["undefined ID list", (client) => runSetAdminEventsActive(client, undefined, true, "bulk"), "active_ids_invalid"],
    ["null ID", (client) => runReannotateAdminEvent(client, null), "reannotate_ids_invalid"],
    ["non-string ID member", (client) => runSetAdminEventsActive(client, [EVENT_1, null], true, "bulk"), "active_ids_invalid"],
    ["undefined categories", (client) => runChangeAdminEventCategories(client, [EVENT_1], "add", undefined, ADMIN_1), "categories_invalid"],
    ["null categories", (client) => runChangeAdminEventCategories(client, [EVENT_1], "add", null, ADMIN_1), "categories_invalid"],
    ["non-string category member", (client) => runChangeAdminEventCategories(client, [EVENT_1], "add", ["art", null], ADMIN_1), "categories_invalid"],
    ["string active flag", (client) => runSetAdminEventsActive(client, [EVENT_1], "false", "single"), "active_value_invalid"],
    ["null active flag", (client) => runSetAdminEventsActive(client, [EVENT_1], null, "single"), "active_value_invalid"],
    ["string rescrape flag", (client) => runSetAdminEventsForceRescrape(client, [EVENT_1], "true", "single"), "force_rescrape_value_invalid"],
  ];

  for (const [name, run, expectedError] of cases) {
    await t.test(name, async () => {
      const { client, calls } = makeClient(() => {
        throw new Error("invalid input must not reach the database");
      });
      const result = await run(client);
      assert.deepEqual(result, { ok: false, error: expectedError });
      assert.equal(calls.length, 0);
    });
  }
});

test("malformed AdminEdit forms fail before reading or writing", async (t) => {
  for (const [name, form, expectedError] of [
    ["undefined", undefined, "form_invalid"],
    ["null", null, "form_invalid"],
    ["string", "not-a-form", "form_invalid"],
    ["array", [], "form_invalid"],
    ["missing arrays", {}, "categories_invalid"],
    ["string boolean", { ...BASE_FORM, is_active: "true" }, "form_invalid"],
  ] as const) {
    await t.test(name, async () => {
      const { client, calls } = makeClient(() => {
        throw new Error("invalid form must not reach the database");
      });
      const result = await runSaveAdminEditedEvent(client, EVENT_1, form, ADMIN_1);
      assert.deepEqual(result, { ok: false, error: expectedError });
      assert.equal(calls.length, 0);
    });
  }
});

test("single reannotation requires exactly the requested event", async () => {
  const { client } = makeClient(route({
    "events:update": { data: [{ id: EVENT_2 }], error: null },
  }));
  const result = await runReannotateAdminEvent(client, EVENT_1);
  assert.equal(result.ok, false);
});

test("category mutation derives before-image on the server and writes both corrections", async () => {
  const { client, calls } = makeClient((call) => {
    if (call.table === "events" && call.op === "select") {
      return {
        data: [{
          id: EVENT_1,
          category: ["movie"],
          raw_title: "題\u0000名",
          raw_description: "説明\u0000文",
        }],
        error: null,
      };
    }
    if (call.table === "events" && call.op === "update") {
      return { data: [{ id: EVENT_1 }], error: null };
    }
    return { data: null, error: null };
  });

  const result = await runChangeAdminEventCategories(
    client,
    [EVENT_1],
    "add",
    ["art"],
    ADMIN_1,
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.data?.events, [{ id: EVENT_1, category: ["movie", "art"] }]);
  const eventWrite = callsOf(calls, "events", "update")[0];
  assert.deepEqual(eventWrite.payload, { category: ["movie", "art"] });

  const categoryCorrection = callsOf(calls, "category_corrections", "upsert")[0]
    .payload as Record<string, unknown>;
  assert.deepEqual(categoryCorrection.ai_category, ["movie"]);
  assert.deepEqual(categoryCorrection.corrected_category, ["movie", "art"]);
  assert.equal(categoryCorrection.corrected_by, ADMIN_1);
  assert.equal(String(categoryCorrection.raw_title).includes("\u0000"), false);
  assert.equal(String(categoryCorrection.raw_description).includes("\u0000"), false);

  const fieldCorrection = callsOf(calls, "field_corrections", "upsert")[0]
    .payload as Record<string, unknown>;
  assert.equal(fieldCorrection.original_value, JSON.stringify(["movie"]));
  assert.equal(fieldCorrection.corrected_value, JSON.stringify(["movie", "art"]));
  assert.equal(fieldCorrection.corrected_by, ADMIN_1);
});

test("category mutation reports correction write errors", async () => {
  const { client, calls } = makeClient(route({
    "events:select": {
      data: [{ id: EVENT_1, category: ["movie"], raw_title: "題名", raw_description: "説明" }],
      error: null,
    },
    "events:update": { data: [{ id: EVENT_1 }], error: null },
    "category_corrections:upsert": { data: null, error: { message: "category correction failed" } },
  }));
  const result = await runChangeAdminEventCategories(
    client,
    [EVENT_1],
    "remove",
    ["movie"],
    ADMIN_1,
  );
  assert.equal(result.ok, false);
  assert.equal(result.error, "category correction failed");
  assert.equal(callsOf(calls, "events", "update").length, 0);
});

test("category correction-first writes return failure when the event write fails", async (t) => {
  for (const [name, eventResponse, expectedError] of [
    ["database error", { data: null, error: { message: "event update failed" } }, "event update failed"],
    ["zero rows", { data: [], error: null }, "category_update_exact_id_mismatch"],
  ] as const) {
    await t.test(name, async () => {
      const { client, calls } = makeClient(route({
        "events:select": {
          data: [{ id: EVENT_1, category: ["movie"], raw_title: "題名", raw_description: "説明" }],
          error: null,
        },
        "events:update": eventResponse,
      }));

      const result = await runChangeAdminEventCategories(
        client,
        [EVENT_1],
        "add",
        ["art"],
        ADMIN_1,
      );

      assert.deepEqual(result, { ok: false, error: expectedError });
      assert.equal(callsOf(calls, "category_corrections", "upsert").length, 1);
      assert.equal(callsOf(calls, "field_corrections", "upsert").length, 1);
      assert.equal(callsOf(calls, "events", "update").length, 1);
    });
  }
});

test("category field-correction failure stops before the event update", async () => {
  const { client, calls } = makeClient(route({
    "events:select": {
      data: [{ id: EVENT_1, category: ["movie"], raw_title: "題名", raw_description: "説明" }],
      error: null,
    },
    "field_corrections:upsert": { data: null, error: { message: "field correction failed" } },
  }));
  const result = await runChangeAdminEventCategories(
    client,
    [EVENT_1],
    "add",
    ["art"],
    ADMIN_1,
  );
  assert.deepEqual(result, { ok: false, error: "field correction failed" });
  assert.equal(callsOf(calls, "category_corrections", "upsert").length, 1);
  assert.equal(callsOf(calls, "events", "update").length, 0);
});

test("AdminEdit uses DB before-image and server actor for corrections", async () => {
  const { client, calls } = makeClient((call) => {
    if (call.table === "events" && call.op === "select") {
      return { data: beforeEvent(), error: null };
    }
    if (call.table === "events" && call.op === "update") {
      return { data: { ...beforeEvent(), id: EVENT_1, name_ja: BASE_FORM.name_ja }, error: null };
    }
    return { data: null, error: null };
  });

  const result = await runSaveAdminEditedEvent(client, EVENT_1, BASE_FORM, ADMIN_1);
  assert.equal(result.ok, true);

  const eventWrite = callsOf(calls, "events", "update")[0]
    .payload as Record<string, unknown>;
  assert.equal(eventWrite.annotation_status, "reviewed");

  const fieldRows = callsOf(calls, "field_corrections", "upsert")[0]
    .payload as Array<Record<string, unknown>>;
  const nameRow = fieldRows.find((row) => row.field_name === "name_ja");
  assert.ok(nameRow);
  assert.equal(nameRow.original_value, "旧名");
  assert.equal(nameRow.corrected_value, BASE_FORM.name_ja);
  assert.equal(nameRow.corrected_by, ADMIN_1);

  const categoryRow = callsOf(calls, "category_corrections", "upsert")[0]
    .payload as Record<string, unknown>;
  assert.deepEqual(categoryRow.ai_category, ["movie"]);
  assert.equal(categoryRow.corrected_by, ADMIN_1);
});

test("AdminEdit never reports success when a correction write fails", async () => {
  const { client, calls } = makeClient(route({
    "events:select": { data: beforeEvent(), error: null },
    "events:update": { data: { ...beforeEvent(), name_ja: BASE_FORM.name_ja }, error: null },
    "field_corrections:upsert": { data: null, error: { message: "field correction failed" } },
  }));
  const result = await runSaveAdminEditedEvent(client, EVENT_1, BASE_FORM, ADMIN_1);
  assert.equal(result.ok, false);
  assert.equal(result.error, "field correction failed");
  assert.equal(callsOf(calls, "events", "update").length, 0);
});

test("AdminEdit stops before the event update when a later correction write fails", async () => {
  const { client, calls } = makeClient(route({
    "events:select": { data: beforeEvent(), error: null },
    "category_corrections:upsert": {
      data: null,
      error: { message: "category correction failed" },
    },
  }));
  const result = await runSaveAdminEditedEvent(client, EVENT_1, BASE_FORM, ADMIN_1);
  assert.deepEqual(result, { ok: false, error: "category correction failed" });
  assert.equal(callsOf(calls, "field_corrections", "upsert").length, 1);
  assert.equal(callsOf(calls, "category_corrections", "upsert").length, 1);
  assert.equal(callsOf(calls, "events", "update").length, 0);
});

test("AdminEdit correction-first writes return failure when the event write fails", async (t) => {
  for (const [name, eventResponse, expectedError] of [
    ["database error", { data: null, error: { message: "event update failed" } }, "event update failed"],
    ["zero rows", { data: null, error: null }, "admin_edit_exact_id_mismatch"],
  ] as const) {
    await t.test(name, async () => {
      const { client, calls } = makeClient(route({
        "events:select": { data: beforeEvent(), error: null },
        "events:update": eventResponse,
      }));

      const result = await runSaveAdminEditedEvent(client, EVENT_1, BASE_FORM, ADMIN_1);

      assert.deepEqual(result, { ok: false, error: expectedError });
      assert.equal(callsOf(calls, "field_corrections", "upsert").length, 2);
      assert.equal(callsOf(calls, "category_corrections", "upsert").length, 1);
      assert.equal(callsOf(calls, "events", "update").length, 1);
    });
  }
});

test("AdminEdit drops runtime fields outside the editable allowlist", async () => {
  const { client, calls } = makeClient((call) => {
    if (call.table === "events" && call.op === "select") {
      return { data: beforeEvent(), error: null };
    }
    if (call.table === "events" && call.op === "update") {
      return { data: { ...beforeEvent(), id: EVENT_1 }, error: null };
    }
    return { data: null, error: null };
  });
  const hostileForm = {
    ...BASE_FORM,
    owner_user_id: ADMIN_1,
    annotation_status: "annotated",
    source_name: "attacker",
  } as FormState;

  const result = await runSaveAdminEditedEvent(client, EVENT_1, hostileForm, ADMIN_1);
  assert.equal(result.ok, true);
  const payload = callsOf(calls, "events", "update")[0].payload as Record<string, unknown>;
  assert.equal("owner_user_id" in payload, false);
  assert.equal("source_name" in payload, false);
  assert.equal(payload.annotation_status, "reviewed");
});

test("work update, work delete, assignments, owner mutations, and admin delete reject 0 rows", async (t) => {
  const cases: Array<[string, (client: SupabaseClient) => Promise<{ ok: boolean }>]> = [
    ["work update", (client) => runUpdateWorkExact(client, WORK_1, { original_title: "Work" })],
    ["work delete", (client) => runDeleteWorkExact(client, WORK_1)],
    ["work assignment", (client) => runAssignWorkToEvents(client, [EVENT_1], WORK_1, "single")],
    ["owner deactivate", (client) => runDeactivateOwnerEventExact(client, EVENT_1)],
    ["owner delete", (client) => runDeleteOwnerEventExact(client, EVENT_1)],
    ["admin delete", (client) => runDeleteAdminEventExact(client, EVENT_1)],
  ];

  for (const [name, run] of cases) {
    await t.test(name, async () => {
      const { client } = makeClient(route({
        "events:update": { data: [], error: null },
        "events:delete": { data: [], error: null },
        "works:update": { data: [], error: null },
        "works:delete": { data: [], error: null },
      }));
      const result = await run(client);
      assert.equal(result.ok, false);
    });
  }
});

test("exact single-row work, owner, and admin mutations succeed", async (t) => {
  const cases: Array<[string, (client: SupabaseClient) => Promise<{ ok: boolean }>]> = [
    ["work update", (client) => runUpdateWorkExact(client, WORK_1, { original_title: "Work" })],
    ["work delete", (client) => runDeleteWorkExact(client, WORK_1)],
    ["owner deactivate", (client) => runDeactivateOwnerEventExact(client, EVENT_1)],
    ["owner delete", (client) => runDeleteOwnerEventExact(client, EVENT_1)],
    ["admin delete", (client) => runDeleteAdminEventExact(client, EVENT_1)],
  ];

  for (const [name, run] of cases) {
    await t.test(name, async () => {
      const { client } = makeClient(route({
        "events:update": { data: [{ id: EVENT_1 }], error: null },
        "events:delete": { data: [{ id: EVENT_1 }], error: null },
        "works:update": { data: [{ id: WORK_1 }], error: null },
        "works:delete": { data: [{ id: WORK_1 }], error: null },
      }));
      const result = await run(client);
      assert.equal(result.ok, true);
    });
  }
});
