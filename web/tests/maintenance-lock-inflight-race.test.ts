import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

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
const BROWSER_WRITER_COMPONENTS = [
  "components/AdminEditClient.tsx",
  "components/AdminEventTable.tsx",
  "components/IsActiveToggle.tsx",
] as const;
const MUTATION_METHODS = new Set(["insert", "update", "upsert", "delete"]);
const REQUIRED_ACTION_IMPORTS = {
  "components/AdminEditClient.tsx": {
    "@/app/actions/admin-events": ["saveAdminEditedEvent"],
  },
  "components/AdminEventTable.tsx": {
    "@/app/actions/admin-events": [
      "changeAdminEventCategories",
      "reannotateAdminEvent",
      "setAdminEventActive",
      "setAdminEventForceRescrape",
      "setAdminEventsActive",
      "setAdminEventsForceRescrape",
    ],
    "@/app/actions/works": ["assignWorkToEvent", "assignWorkToEvents"],
  },
  "components/IsActiveToggle.tsx": {
    "@/app/actions/admin-events": ["setAdminEventActive"],
  },
} as const;

type LockState = "inactive" | "active" | "missing" | "malformed";
type WriterRole = "authenticated" | "service_role";
type MaintenanceLockRow = { value: unknown } | null;

function migrationAllowsAuthenticatedWrite(row: MaintenanceLockRow): boolean {
  if (row === null || typeof row.value !== "object" || row.value === null) return false;
  if (Array.isArray(row.value)) return false;
  return (row.value as Record<string, unknown>).active === false;
}

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
    /SELECT NOT EXISTS \( SELECT 1 FROM public\.app_settings WHERE key = 'admin_reports_cleanup_maintenance' AND value->'active' = 'false'::jsonb \);/,
  );
  assert.doesNotMatch(NORMALIZED_SQL, /value->>'active'\s*=\s*'false'/);

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

test("migration 094 typed predicate allows only exact JSON boolean false", () => {
  const cases: Array<{
    label: string;
    row: MaintenanceLockRow;
    expected: boolean;
  }> = [
    {
      label: "boolean false",
      row: { value: { active: false, window_id: null } },
      expected: true,
    },
    { label: "missing row", row: null, expected: false },
    { label: "missing key", row: { value: {} }, expected: false },
    { label: "JSON null", row: { value: { active: null } }, expected: false },
    { label: "string false", row: { value: { active: "false" } }, expected: false },
    { label: "number zero", row: { value: { active: 0 } }, expected: false },
    { label: "object", row: { value: { active: {} } }, expected: false },
    { label: "array", row: { value: { active: [] } }, expected: false },
    { label: "boolean true", row: { value: { active: true } }, expected: false },
  ];

  for (const { label, row, expected } of cases) {
    assert.equal(migrationAllowsAuthenticatedWrite(row), expected, label);
  }
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

function guardedTableForMutation(call: ts.CallExpression): string | null {
  if (!ts.isPropertyAccessExpression(call.expression)) return null;
  if (!MUTATION_METHODS.has(call.expression.name.text)) return null;

  let current: ts.Expression = call.expression.expression;
  while (ts.isCallExpression(current)) {
    if (ts.isPropertyAccessExpression(current.expression)) {
      if (current.expression.name.text === "from") {
        const table = current.arguments[0];
        return table && ts.isStringLiteral(table) ? table.text : null;
      }
      current = current.expression.expression;
      continue;
    }
    break;
  }
  return null;
}

test("Slice 3 browser components cannot mutate cleanup dependency tables", () => {
  for (const relativePath of BROWSER_WRITER_COMPONENTS) {
    const fullPath = path.join(WEB_ROOT, relativePath);
    const source = fs.readFileSync(fullPath, "utf8");
    const sourceFile = ts.createSourceFile(
      fullPath,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const mutations: string[] = [];

    const visit = (node: ts.Node) => {
      if (ts.isCallExpression(node)) {
        const table = guardedTableForMutation(node);
        if (table && GUARDED_TABLES.includes(table as (typeof GUARDED_TABLES)[number])) {
          const method = (node.expression as ts.PropertyAccessExpression).name.text;
          const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
          mutations.push(`${table}.${method} at ${position.line + 1}:${position.character + 1}`);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);

    assert.deepEqual(
      mutations,
      [],
      `${relativePath} must use guarded Server Actions for dependency mutations`,
    );
  }
});

test("Slice 3 browser components use the guarded action entry points", () => {
  for (const [relativePath, modules] of Object.entries(REQUIRED_ACTION_IMPORTS)) {
    const fullPath = path.join(WEB_ROOT, relativePath);
    const source = fs.readFileSync(fullPath, "utf8");
    const sourceFile = ts.createSourceFile(
      fullPath,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const imports = new Map<string, Set<string>>();

    for (const statement of sourceFile.statements) {
      if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) {
        continue;
      }
      const namedBindings = statement.importClause?.namedBindings;
      if (!namedBindings || !ts.isNamedImports(namedBindings)) continue;
      imports.set(
        statement.moduleSpecifier.text,
        new Set(namedBindings.elements.map((element) => element.name.text)),
      );
    }

    for (const [moduleName, actionNames] of Object.entries(modules)) {
      const importedNames = imports.get(moduleName);
      assert.ok(importedNames, `${relativePath} must import ${moduleName}`);
      for (const actionName of actionNames) {
        assert.ok(
          importedNames.has(actionName),
          `${relativePath} must import guarded action ${actionName}`,
        );
      }
    }
  }
});