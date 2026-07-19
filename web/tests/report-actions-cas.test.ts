// Web slice G4b — pending compare-and-set + exactly-one-row + idempotency tests.
//
// Covers BOTH runConfirmReport and runDismissReport: the report status write must
// filter on id + status='pending', .select('id'), and require exactly one row (0
// rows OR an explicit error OR >1 rows all fail). Also proves an interrupted
// confirm is idempotent on retry and never claims a rollback: a pre-status failure
// leaves the report pending (status write never issued) and issues no compensating
// write, and the retry re-applies identical writes before flipping status.
//
// No network: globalThis.fetch is stubbed to reject.

import assert from "node:assert/strict";
import test from "node:test";
import type { SupabaseClient } from "@supabase/supabase-js";

import { runConfirmReport } from "../app/actions/confirm-report";
import { runDismissReport } from "../app/actions/dismiss-report";

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

function confirmRoute(over: Record<string, Resp | Responder> = {}): Responder {
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

function hasFilter(call: RecordedCall, column: string, value: unknown): boolean {
  return call.filters.some(([c, v]) => c === column && v === value);
}

// --- confirmReport status CAS -------------------------------------------------

test("confirm status write uses id + status=pending and selects the id", async () => {
  const { client, calls } = makeClient({ responder: confirmRoute() });
  const res = await runConfirmReport(client, baseInput());

  assert.equal(res.ok, true);
  const statusCall = callsOf(calls, "event_reports", "update")[0];
  assert.ok(statusCall, "status write issued");
  assert.ok(hasFilter(statusCall, "id", "report-1"), "CAS filters full report id");
  assert.ok(hasFilter(statusCall, "status", "pending"), "CAS filters status=pending");
  assert.equal(statusCall.returning, true, ".select('id') applied");
  assert.equal(statusCall.columns, "id");
  assert.equal((statusCall.payload as { status: string }).status, "confirmed");
});

test("confirm fails when the status CAS matches zero rows", async () => {
  const { client } = makeClient({ responder: confirmRoute({ "event_reports:update": { data: [], error: null } }) });
  const res = await runConfirmReport(client, baseInput());
  assert.equal(res.ok, false);
  assert.match(res.error ?? "", /already handled|not pending/i);
});

test("confirm fails when the status CAS returns an explicit error", async () => {
  const { client } = makeClient({
    responder: confirmRoute({ "event_reports:update": { data: null, error: { message: "status boom" } } }),
  });
  const res = await runConfirmReport(client, baseInput());
  assert.equal(res.ok, false);
  assert.equal(res.error, "status boom");
});

test("confirm fails when the status CAS returns more than one row", async () => {
  const { client } = makeClient({
    responder: confirmRoute({
      "event_reports:update": { data: [{ id: "report-1" }, { id: "other" }], error: null },
    }),
  });
  const res = await runConfirmReport(client, baseInput());
  assert.equal(res.ok, false, "exactly-one-row: >1 row is a failure");
  assert.match(res.error ?? "", /already handled|not pending/i);
});

// --- dismissReport status CAS -------------------------------------------------

test("dismiss uses id + status=pending, selects id, and requires exactly one row", async () => {
  const { client, calls } = makeClient({
    responder: route({ "event_reports:update": { data: [{ id: "report-1" }], error: null } }),
  });
  const res = await runDismissReport(client, "report-1");

  assert.equal(res.ok, true);
  const call = callsOf(calls, "event_reports", "update")[0];
  assert.ok(call, "dismiss status write issued");
  assert.ok(hasFilter(call, "id", "report-1"), "CAS filters full report id");
  assert.ok(hasFilter(call, "status", "pending"), "CAS filters status=pending");
  assert.equal(call.returning, true, ".select('id') applied");
  assert.equal(call.columns, "id");
  assert.equal((call.payload as { status: string }).status, "dismissed");
});

test("dismiss fails on a zero-row status CAS", async () => {
  const { client } = makeClient({
    responder: route({ "event_reports:update": { data: [], error: null } }),
  });
  const res = await runDismissReport(client, "report-1");
  assert.equal(res.ok, false);
});

test("dismiss fails on an explicit status-CAS error", async () => {
  const { client } = makeClient({
    responder: route({ "event_reports:update": { data: null, error: { message: "dismiss boom" } } }),
  });
  const res = await runDismissReport(client, "report-1");
  assert.equal(res.ok, false);
  assert.equal(res.error, "dismiss boom");
});

test("dismiss fails when the status CAS returns more than one row", async () => {
  const { client } = makeClient({
    responder: route({ "event_reports:update": { data: [{ id: "a" }, { id: "b" }], error: null } }),
  });
  const res = await runDismissReport(client, "report-1");
  assert.equal(res.ok, false, "exactly-one-row: >1 row is a failure");
});

// --- idempotent retry, no rollback claim -------------------------------------

test("an interrupted confirm is idempotent on retry and never claims a rollback", async () => {
  let phase = 1;
  const responder = confirmRoute({
    "event_reports:select": {
      data: [{ id: "report-1", event_id: "db-event", report_types: ["wrongCategory"], status: "pending" }],
      error: null,
    },
    "category_corrections:upsert": () =>
      phase === 1 ? { data: null, error: { message: "transient" } } : { data: null, error: null },
  });

  // Phase 1: the event write succeeds, then a correction write fails.
  const p1 = makeClient({ responder });
  const r1 = await runConfirmReport(p1.client, baseInput({ correctCategory: ["art"] }));

  assert.equal(r1.ok, false);
  assert.equal(r1.error, "transient");
  assert.equal(callsOf(p1.calls, "events", "update").length, 1, "event update was applied");
  assert.equal(
    callsOf(p1.calls, "event_reports", "update").length,
    0,
    "status never flipped -> report stays pending",
  );
  assert.equal(callsOf(p1.calls, "events", "delete").length, 0, "no compensating delete");
  assert.ok(!("rolledBack" in r1), "result never claims a rollback");

  // Phase 2: retry with the transient failure cleared.
  phase = 2;
  const p2 = makeClient({ responder });
  const r2 = await runConfirmReport(p2.client, baseInput({ correctCategory: ["art"] }));

  assert.equal(r2.ok, true);
  const ev1 = callsOf(p1.calls, "events", "update")[0].payload as Record<string, unknown>;
  const ev2 = callsOf(p2.calls, "events", "update")[0].payload as Record<string, unknown>;
  assert.deepEqual(ev2, ev1, "retry re-applies the identical event update (idempotent, not a diff/patch)");
  assert.equal(
    callsOf(p2.calls, "event_reports", "update").length,
    1,
    "status flipped exactly once on the successful retry",
  );

  for (const c of [...p1.calls, ...p2.calls]) {
    assert.notEqual(c.op, "delete", "neither phase issues a compensating/reverse write");
  }
});
