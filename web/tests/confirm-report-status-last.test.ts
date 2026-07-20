// Web slice G4b — confirmReport status-last + identity-from-DB tests.
//
// Exercises the testable core runConfirmReport(supabase, input) with an injected
// fake Supabase client. Asserts: identity is derived from the DB pending row (not
// client input), the event before-image is captured before any write, a failed
// required read/write returns an error WITHOUT flipping report status, the status
// write happens after every data write, and a best-effort GitHub failure never
// falsifies a verified DB success.
//
// No network: globalThis.fetch is stubbed to reject so the best-effort GitHub
// history append can never reach the real API during tests.

import assert from "node:assert/strict";
import test from "node:test";
import type { SupabaseClient } from "@supabase/supabase-js";

import { runConfirmReport } from "../lib/reportActionsCore";

globalThis.fetch = (async () => {
  throw new Error("network disabled in tests");
}) as unknown as typeof fetch;

type Op = "select" | "update" | "upsert" | "insert" | "delete";

interface RecordedCall {
  table: string;
  op: Op;
  columns?: string;
  filters: Array<[string, unknown]>;
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

  upsert(payload: unknown, opts?: { onConflict?: string }): this {
    this.call.op = "upsert";
    this.call.payload = payload;
    this.call.onConflict = opts?.onConflict;
    this.opSet = true;
    return this;
  }

  insert(payload: unknown): this {
    this.call.op = "insert";
    this.call.payload = payload;
    this.opSet = true;
    return this;
  }

  delete(): this {
    this.call.op = "delete";
    this.opSet = true;
    return this;
  }

  eq(column: string, value: unknown): this {
    this.call.filters.push([column, value]);
    return this;
  }

  single(): Promise<Resp> {
    this.call.single = true;
    return this.settle();
  }

  maybeSingle(): Promise<Resp> {
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
    const resp = this.responder(this.call, this.calls.length - 1);
    return Promise.resolve({ data: resp.data ?? null, error: resp.error ?? null });
  }
}

function makeClient(opts: {
  user?: { id: string } | null;
  responder: Responder;
}): { client: SupabaseClient; calls: RecordedCall[] } {
  const calls: RecordedCall[] = [];
  const user = opts.user === undefined ? { id: "admin-1" } : opts.user;
  const client = {
    auth: {
      getUser: async () => ({ data: { user }, error: null }),
    },
    from: (table: string) => new FakeBuilder(calls, opts.responder, table),
  };
  return { client: client as unknown as SupabaseClient, calls };
}

function route(map: Record<string, Resp | Responder>): Responder {
  return (call, index) => {
    const entry = map[`${call.table}:${call.op}`];
    if (typeof entry === "function") return entry(call, index);
    if (entry) return entry;
    return { data: null, error: null };
  };
}

function okRoute(over: Record<string, Resp | Responder> = {}): Responder {
  return route({
    "user_roles:select": { data: { role: "admin" }, error: null },
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["irrelevant"], status: "pending" }],
      error: null,
    },
    "events:select": {
      data: {
        annotation_status: "annotated",
        updated_at: "2026-07-18T00:00:00Z",
        raw_title: "RT",
        raw_description: "RD",
        selection_reason: null,
      },
      error: null,
    },
    "events:update": { data: [{ id: "db-event" }], error: null },
    "category_corrections:upsert": { data: null, error: null },
    "field_corrections:upsert": { data: null, error: null },
    "selection_reason_corrections:upsert": { data: null, error: null },
    "event_reports:update": { data: [{ id: "report-1" }], error: null },
    ...over,
  });
}

type ConfirmInput = Parameters<typeof runConfirmReport>[1];

function baseInput(overrides: Partial<ConfirmInput> = {}): ConfirmInput {
  return {
    reportId: "report-1",
    eventId: "client-event",
    adminNotes: "",
    reportTypes: ["irrelevant"],
    eventName: "Test Event",
    sourceName: "unmapped_source",
    currentCategory: [],
    correctCategory: null,
    suggestedCategory: null,
    fieldCorrections: {},
    correctedSelectionReason: undefined,
    ...overrides,
  };
}

function callsOf(calls: RecordedCall[], table: string, op: Op): RecordedCall[] {
  return calls.filter((c) => c.table === table && c.op === op);
}

function firstIndex(calls: RecordedCall[], pred: (c: RecordedCall) => boolean): number {
  return calls.findIndex(pred);
}

function hasFilter(call: RecordedCall, column: string, value: unknown): boolean {
  return call.filters.some(([c, v]) => c === column && v === value);
}

test("derives event id and report types from the DB pending row, not client input", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["wrongCategory"], status: "pending" }],
      error: null,
    },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(
    client,
    baseInput({
      eventId: "CLIENT-BOGUS",
      reportTypes: ["irrelevant"],
      currentCategory: ["movie"],
      correctCategory: ["art"],
    }),
  );

  assert.equal(res.ok, true);

  const lookup = callsOf(calls, "event_reports", "select")[0];
  assert.ok(lookup, "report lookup issued");
  assert.ok(hasFilter(lookup, "id", "report-1"), "lookup filtered by full report id");
  assert.ok(hasFilter(lookup, "status", "pending"), "lookup filtered by status=pending");

  const eventUpdate = callsOf(calls, "events", "update")[0];
  assert.ok(eventUpdate, "event update issued");
  assert.ok(hasFilter(eventUpdate, "id", "db-event"), "event write targets DB event id");
  assert.ok(
    !calls.some((c) => c.filters.some(([, v]) => v === "CLIENT-BOGUS")),
    "client-supplied eventId never drives a write",
  );

  const category = callsOf(calls, "category_corrections", "upsert")[0];
  assert.ok(category, "DB report type wrongCategory drove a category correction");
  assert.equal((category.payload as { event_id: string }).event_id, "db-event");
});

test("rejects when the pending report lookup returns zero rows", async () => {
  const responder = okRoute({ "event_reports:select": { data: [], error: null } });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(client, baseInput());

  assert.equal(res.ok, false);
  assert.match(res.error ?? "", /not found or not pending/i);
  assert.equal(callsOf(calls, "events", "update").length, 0);
  assert.equal(callsOf(calls, "event_reports", "update").length, 0);
});

test("rejects when the pending report lookup returns multiple rows", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [
        { id: "report-1", event_id: "e1", report_types: ["irrelevant"], status: "pending" },
        { id: "report-1", event_id: "e2", report_types: ["irrelevant"], status: "pending" },
      ],
      error: null,
    },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(client, baseInput());

  assert.equal(res.ok, false);
  assert.match(res.error ?? "", /multiple/i);
  assert.equal(callsOf(calls, "event_reports", "update").length, 0);
});

test("captures the event before-image before any write", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [
        { id: "report-1", event_id: "db-event", report_types: ["wrongDetails", "field:name"], status: "pending" },
      ],
      error: null,
    },
    "events:select": {
      data: {
        annotation_status: "annotated",
        updated_at: "2026-07-18T00:00:00Z",
        raw_title: "RT",
        raw_description: "RD",
        selection_reason: null,
        name_zh: "舊ZH",
        name_en: "OldEN",
        name_ja: "JA",
      },
      error: null,
    },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(
    client,
    baseInput({ fieldCorrections: { name: { zh: "新ZH", en: "NewEN" } } }),
  );

  assert.equal(res.ok, true);

  const beforeIdx = firstIndex(calls, (c) => c.table === "events" && c.op === "select");
  const eventUpdateIdx = firstIndex(calls, (c) => c.table === "events" && c.op === "update");
  const fcIdx = firstIndex(calls, (c) => c.table === "field_corrections" && c.op === "upsert");
  assert.ok(beforeIdx >= 0, "before-image read happened");
  assert.ok(eventUpdateIdx >= 0, "event update happened");
  assert.ok(fcIdx >= 0, "field_corrections write happened");
  assert.ok(beforeIdx < eventUpdateIdx, "before-image read precedes the event update");
  assert.ok(beforeIdx < fcIdx, "before-image read precedes the field_corrections write");

  const beforeCall = callsOf(calls, "events", "select")[0];
  assert.match(beforeCall.columns ?? "", /updated_at/, "before-image includes updated_at");
  assert.match(beforeCall.columns ?? "", /name_zh/, "before-image includes the corrected field original columns");
  assert.match(beforeCall.columns ?? "", /name_en/);

  const fcCall = callsOf(calls, "field_corrections", "upsert")[0];
  const rows = fcCall.payload as Array<{ field_name: string; original_value: string | null; corrected_value: string }>;
  const zh = rows.find((r) => r.field_name === "name_zh");
  assert.ok(zh, "name_zh correction row present");
  assert.equal(zh.original_value, "舊ZH", "original_value comes from the before-image, not a post-update read");
  assert.equal(zh.corrected_value, "新ZH");
});

test("writes report status only after every data write", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [
        {
          id: "report-1",
          event_id: "db-event",
          report_types: ["wrongCategory", "wrongDetails", "field:name", "wrongSelectionReason"],
          status: "pending",
        },
      ],
      error: null,
    },
    "events:select": {
      data: {
        annotation_status: "annotated",
        updated_at: "2026-07-18T00:00:00Z",
        raw_title: "RT",
        raw_description: "RD",
        selection_reason: '{"zh":"舊理由"}',
        name_zh: "舊ZH",
        name_en: "OldEN",
        name_ja: "JA",
      },
      error: null,
    },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(
    client,
    baseInput({
      correctCategory: ["art"],
      fieldCorrections: { name: { zh: "新ZH" } },
      correctedSelectionReason: '{"zh":"新理由"}',
    }),
  );

  assert.equal(res.ok, true);

  const statusIdx = firstIndex(calls, (c) => c.table === "event_reports" && c.op === "update");
  const dataWriteIdxs = calls
    .map((c, i) => ({ c, i }))
    .filter(
      ({ c }) =>
        (c.table === "events" && c.op === "update") ||
        (c.table === "category_corrections" && c.op === "upsert") ||
        (c.table === "field_corrections" && c.op === "upsert") ||
        (c.table === "selection_reason_corrections" && c.op === "upsert"),
    )
    .map(({ i }) => i);

  assert.ok(dataWriteIdxs.length >= 4, "event + category + field + selection writes all happened");
  assert.ok(statusIdx >= 0, "status write happened");
  assert.ok(statusIdx > Math.max(...dataWriteIdxs), "status write is strictly after every data write");
});

test("returns an error and does not touch status when the before-image read fails", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["wrongCategory"], status: "pending" }],
      error: null,
    },
    "events:select": { data: null, error: { message: "read boom" } },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(client, baseInput({ correctCategory: ["art"] }));

  assert.equal(res.ok, false);
  assert.equal(res.error, "read boom");
  assert.equal(res.githubUpdated, false);
  assert.equal(callsOf(calls, "events", "update").length, 0);
  assert.equal(callsOf(calls, "event_reports", "update").length, 0, "status never written after a read failure");
});

test("returns an error and does not touch status when the event write fails", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["wrongCategory"], status: "pending" }],
      error: null,
    },
    "events:update": { data: null, error: { message: "event boom" } },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(client, baseInput({ correctCategory: ["art"] }));

  assert.equal(res.ok, false);
  assert.equal(res.error, "event boom");
  assert.equal(res.githubUpdated, false);
  assert.equal(callsOf(calls, "event_reports", "update").length, 0, "status never written after an event failure");
});

test("returns an error and does not touch status when a correction write fails", async () => {
  const responder = okRoute({
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["wrongCategory"], status: "pending" }],
      error: null,
    },
    "category_corrections:upsert": { data: null, error: { message: "cc boom" } },
  });
  const { client, calls } = makeClient({ responder });

  const res = await runConfirmReport(client, baseInput({ correctCategory: ["art"] }));

  assert.equal(res.ok, false);
  assert.equal(res.error, "cc boom");
  assert.equal(callsOf(calls, "event_reports", "update").length, 0, "status never written after a correction failure");
});

test("a verified DB success is not falsified by a GitHub history failure", async () => {
  const originalToken = process.env.GITHUB_TOKEN;
  process.env.GITHUB_TOKEN = "test-token"; // force the best-effort path to reach the stubbed fetch
  try {
    const { client } = makeClient({ responder: okRoute() });
    const res = await runConfirmReport(client, baseInput());
    assert.equal(res.ok, true, "DB writes succeeded");
    assert.equal(res.githubUpdated, false, "GitHub failure surfaces as githubUpdated=false, not ok=false");
  } finally {
    if (originalToken === undefined) delete process.env.GITHUB_TOKEN;
    else process.env.GITHUB_TOKEN = originalToken;
  }
});

test("rejects an unauthenticated caller before any query", async () => {
  const { client, calls } = makeClient({ user: null, responder: okRoute() });
  const res = await runConfirmReport(client, baseInput());
  assert.equal(res.ok, false);
  assert.equal(res.error, "Unauthorized");
  assert.equal(calls.length, 0);
});

test("rejects a non-admin caller before the report lookup", async () => {
  const responder = okRoute({ "user_roles:select": { data: { role: "user" }, error: null } });
  const { client, calls } = makeClient({ responder });
  const res = await runConfirmReport(client, baseInput());
  assert.equal(res.ok, false);
  assert.equal(res.error, "Forbidden");
  assert.equal(callsOf(calls, "event_reports", "select").length, 0);
  assert.equal(callsOf(calls, "event_reports", "update").length, 0);
});
