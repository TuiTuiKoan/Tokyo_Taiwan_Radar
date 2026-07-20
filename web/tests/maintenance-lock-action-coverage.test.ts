import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const WEB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const ACTION_CONTRACTS = [
  {
    path: "app/actions/admin-events.ts",
    guarded: [
      "createDraftEvent",
      "createEventNoAnnotate",
      "updateAdminEvent",
      "publishEvent",
      "publishAdminWizardEvent",
      "deleteUserSubmittedEvent",
      "deleteAdminEvent",
    ],
    exempt: ["fetchParentEventCandidates"],
  },
  {
    path: "app/actions/confirm-report.ts",
    guarded: ["confirmReport"],
    exempt: [],
    extraDeniedFalseProperties: ["githubUpdated"],
  },
  {
    path: "app/actions/dismiss-report.ts",
    guarded: ["dismissReport"],
    exempt: [],
  },
  {
    path: "app/actions/submit-report.ts",
    guarded: ["submitReport"],
    exempt: [],
  },
  {
    path: "app/actions/works.ts",
    guarded: ["createWork", "updateWork", "deleteWork", "assignWorkToEvent"],
    exempt: [],
  },
  {
    path: "app/actions/owner-events.ts",
    guarded: [
      "createOwnerEvent",
      "createOwnerDraft",
      "updateOwnerEvent",
      "updateOwnerDraft",
      "deactivateOwnEvent",
      "deleteOwnEvent",
    ],
    exempt: [],
  },
] as const;

const ROUTE_CONTRACTS = [
  {
    path: "app/api/account/annotate-event/route.ts",
    handler: "POST",
    runtimeExports: ["POST", "maxDuration"],
    dispatch: false,
  },
  {
    path: "app/api/admin/annotate-event/route.ts",
    handler: "POST",
    runtimeExports: ["POST", "maxDuration"],
    dispatch: false,
  },
  {
    path: "app/api/admin/events/[id]/review-status/route.ts",
    handler: "PATCH",
    runtimeExports: ["PATCH"],
    dispatch: false,
  },
  {
    path: "app/api/admin/annotate-now/route.ts",
    handler: "POST",
    runtimeExports: ["POST"],
    dispatch: true,
  },
  {
    path: "app/api/admin/scrape-now/route.ts",
    handler: "POST",
    runtimeExports: ["POST"],
    dispatch: true,
  },
  {
    path: "app/api/admin/enrich-and-annotate/route.ts",
    handler: "POST",
    runtimeExports: ["POST"],
    dispatch: true,
  },
] as const;

function hasExportModifier(node: ts.Node): boolean {
  return ts.canHaveModifiers(node)
    && (ts.getModifiers(node)?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword) ?? false);
}

function readAction(relativePath: string) {
  const fullPath = path.join(WEB_ROOT, relativePath);
  const source = fs.readFileSync(fullPath, "utf8");
  return {
    source,
    sourceFile: ts.createSourceFile(fullPath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS),
  };
}

function findExportedFunction(sourceFile: ts.SourceFile, name: string): ts.FunctionDeclaration {
  const declaration = sourceFile.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement)
      && statement.name?.text === name
      && hasExportModifier(statement),
  );
  assert.ok(declaration, `${name} must remain an exported function`);
  assert.ok(declaration.body, `${name} must have a function body`);
  assert.ok(
    ts.getModifiers(declaration)?.some((modifier) => modifier.kind === ts.SyntaxKind.AsyncKeyword),
    `${name} must remain async`,
  );
  return declaration;
}

function runtimeExportNames(sourceFile: ts.SourceFile): string[] {
  const names: string[] = [];

  for (const statement of sourceFile.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name && hasExportModifier(statement)) {
      names.push(statement.name.text);
    } else if (ts.isVariableStatement(statement) && hasExportModifier(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) names.push(declaration.name.text);
      }
    } else if (ts.isClassDeclaration(statement) && statement.name && hasExportModifier(statement)) {
      names.push(statement.name.text);
    } else if (ts.isEnumDeclaration(statement) && hasExportModifier(statement)) {
      names.push(statement.name.text);
    } else if (ts.isExportAssignment(statement)) {
      names.push("default");
    } else if (ts.isExportDeclaration(statement) && !statement.isTypeOnly) {
      if (!statement.exportClause) {
        names.push("*");
      } else if (ts.isNamedExports(statement.exportClause)) {
        for (const element of statement.exportClause.elements) {
          if (!element.isTypeOnly) names.push(element.name.text);
        }
      } else {
        names.push(statement.exportClause.name.text);
      }
    }
  }

  return names.sort();
}

function namedProperty(
  object: ts.ObjectLiteralExpression,
  name: string,
): ts.PropertyAssignment | undefined {
  return object.properties.find(
    (property): property is ts.PropertyAssignment =>
      ts.isPropertyAssignment(property)
      && ((ts.isIdentifier(property.name) && property.name.text === name)
        || (ts.isStringLiteral(property.name) && property.name.text === name)),
  );
}

function assertGuardIsFirst(
  sourceFile: ts.SourceFile,
  functionName: string,
  extraDeniedFalseProperties: readonly string[] = [],
) {
  const declaration = findExportedFunction(sourceFile, functionName);
  const statements = declaration.body!.statements;
  assert.ok(statements.length >= 2, `${functionName} must start with a gate and denied return`);

  const gateStatement = statements[0];
  assert.ok(ts.isVariableStatement(gateStatement), `${functionName} must read the lock first`);
  assert.equal(gateStatement.declarationList.declarations.length, 1);
  const gateDeclaration = gateStatement.declarationList.declarations[0];
  assert.ok(ts.isIdentifier(gateDeclaration.name));
  assert.equal(gateDeclaration.name.text, "gate");
  assert.ok(gateDeclaration.initializer && ts.isAwaitExpression(gateDeclaration.initializer));
  const gateCall = gateDeclaration.initializer.expression;
  assert.ok(ts.isCallExpression(gateCall));
  assert.ok(ts.isIdentifier(gateCall.expression));
  assert.equal(gateCall.expression.text, "assertWritesAllowed");
  assert.equal(gateCall.arguments.length, 0);

  const deniedStatement = statements[1];
  assert.ok(ts.isIfStatement(deniedStatement), `${functionName} must return immediately when denied`);
  assert.ok(ts.isPrefixUnaryExpression(deniedStatement.expression));
  assert.equal(deniedStatement.expression.operator, ts.SyntaxKind.ExclamationToken);
  const allowedExpression = deniedStatement.expression.operand;
  assert.ok(ts.isPropertyAccessExpression(allowedExpression));
  assert.ok(ts.isIdentifier(allowedExpression.expression));
  assert.equal(allowedExpression.expression.text, "gate");
  assert.equal(allowedExpression.name.text, "allowed");

  const returnStatement = ts.isBlock(deniedStatement.thenStatement)
    ? deniedStatement.thenStatement.statements[0]
    : deniedStatement.thenStatement;
  assert.ok(ts.isReturnStatement(returnStatement));
  assert.ok(returnStatement.expression && ts.isObjectLiteralExpression(returnStatement.expression));

  const deniedResult = returnStatement.expression;
  const ok = namedProperty(deniedResult, "ok");
  const error = namedProperty(deniedResult, "error");
  assert.ok(ok && ok.initializer.kind === ts.SyntaxKind.FalseKeyword);
  assert.ok(error && ts.isStringLiteral(error.initializer));
  assert.equal(error.initializer.text, "maintenance_active");

  for (const propertyName of extraDeniedFalseProperties) {
    const property = namedProperty(deniedResult, propertyName);
    assert.ok(property && property.initializer.kind === ts.SyntaxKind.FalseKeyword);
  }
}

function assertRouteGuardIsFirst(sourceFile: ts.SourceFile, functionName: string) {
  const declaration = findExportedFunction(sourceFile, functionName);
  const statements = declaration.body!.statements;
  assert.ok(statements.length >= 2, `${functionName} must start with a gate and denied return`);

  const gateStatement = statements[0];
  assert.ok(ts.isVariableStatement(gateStatement), `${functionName} must read the lock first`);
  assert.equal(gateStatement.declarationList.declarations.length, 1);
  const gateDeclaration = gateStatement.declarationList.declarations[0];
  assert.ok(ts.isIdentifier(gateDeclaration.name));
  assert.equal(gateDeclaration.name.text, "gate");
  assert.ok(gateDeclaration.initializer && ts.isAwaitExpression(gateDeclaration.initializer));
  const gateCall = gateDeclaration.initializer.expression;
  assert.ok(ts.isCallExpression(gateCall));
  assert.ok(ts.isIdentifier(gateCall.expression));
  assert.equal(gateCall.expression.text, "assertWritesAllowed");
  assert.equal(gateCall.arguments.length, 0);

  const deniedStatement = statements[1];
  assert.ok(ts.isIfStatement(deniedStatement), `${functionName} must return immediately when denied`);
  assert.ok(ts.isPrefixUnaryExpression(deniedStatement.expression));
  assert.equal(deniedStatement.expression.operator, ts.SyntaxKind.ExclamationToken);
  const allowedExpression = deniedStatement.expression.operand;
  assert.ok(ts.isPropertyAccessExpression(allowedExpression));
  assert.ok(ts.isIdentifier(allowedExpression.expression));
  assert.equal(allowedExpression.expression.text, "gate");
  assert.equal(allowedExpression.name.text, "allowed");

  const returnStatement = ts.isBlock(deniedStatement.thenStatement)
    ? deniedStatement.thenStatement.statements[0]
    : deniedStatement.thenStatement;
  assert.ok(ts.isReturnStatement(returnStatement));
  assert.ok(returnStatement.expression && ts.isCallExpression(returnStatement.expression));

  const responseCall = returnStatement.expression;
  assert.ok(ts.isPropertyAccessExpression(responseCall.expression));
  assert.ok(ts.isIdentifier(responseCall.expression.expression));
  assert.equal(responseCall.expression.expression.text, "NextResponse");
  assert.equal(responseCall.expression.name.text, "json");
  assert.equal(responseCall.arguments.length, 2);

  const [body, init] = responseCall.arguments;
  assert.ok(ts.isObjectLiteralExpression(body));
  const error = namedProperty(body, "error");
  assert.ok(error && ts.isStringLiteral(error.initializer));
  assert.equal(error.initializer.text, "maintenance_active");
  assert.ok(ts.isObjectLiteralExpression(init));
  const status = namedProperty(init, "status");
  assert.ok(status && ts.isNumericLiteral(status.initializer));
  assert.equal(Number(status.initializer.text), 503);
}

function collectCallExpressions(sourceFile: ts.SourceFile): ts.CallExpression[] {
  const calls: ts.CallExpression[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node)) calls.push(node);
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return calls;
}

function assertWorkflowDispatchTimeout(sourceFile: ts.SourceFile, relativePath: string) {
  const timeoutDeclaration = sourceFile.statements
    .filter(ts.isVariableStatement)
    .flatMap((statement) => [...statement.declarationList.declarations])
    .find(
      (declaration) =>
        ts.isIdentifier(declaration.name)
        && declaration.name.text === "WORKFLOW_DISPATCH_TIMEOUT_MS",
    );
  assert.ok(timeoutDeclaration, `${relativePath} must name the dispatch timeout`);
  assert.ok(timeoutDeclaration.initializer && ts.isNumericLiteral(timeoutDeclaration.initializer));
  assert.equal(Number(timeoutDeclaration.initializer.text), 10_000);

  const dispatchFetches = collectCallExpressions(sourceFile).filter(
    (call) =>
      ts.isIdentifier(call.expression)
      && call.expression.text === "fetch"
      && call.arguments[0]?.getText(sourceFile).includes("api.github.com")
      && call.arguments[0]?.getText(sourceFile).includes("/dispatches"),
  );
  assert.equal(dispatchFetches.length, 1, `${relativePath} must have one GitHub dispatch fetch`);

  const dispatchFetch = dispatchFetches[0];
  const options = dispatchFetch.arguments[1];
  assert.ok(ts.isObjectLiteralExpression(options));
  const method = namedProperty(options, "method");
  const headers = namedProperty(options, "headers");
  const body = namedProperty(options, "body");
  const signal = namedProperty(options, "signal");
  assert.ok(method && ts.isStringLiteral(method.initializer));
  assert.equal(method.initializer.text, "POST");
  assert.ok(headers && headers.initializer.getText(sourceFile).includes("Authorization"));
  assert.ok(body, `${relativePath} must preserve the workflow dispatch body`);
  assert.ok(signal && ts.isCallExpression(signal.initializer));

  const timeoutCall = signal.initializer;
  assert.ok(ts.isPropertyAccessExpression(timeoutCall.expression));
  assert.ok(ts.isIdentifier(timeoutCall.expression.expression));
  assert.equal(timeoutCall.expression.expression.text, "AbortSignal");
  assert.equal(timeoutCall.expression.name.text, "timeout");
  assert.equal(timeoutCall.arguments.length, 1);
  assert.ok(ts.isIdentifier(timeoutCall.arguments[0]));
  assert.equal(timeoutCall.arguments[0].text, "WORKFLOW_DISPATCH_TIMEOUT_MS");

  let ancestor: ts.Node | undefined = dispatchFetch.parent;
  while (ancestor && !ts.isTryStatement(ancestor)) ancestor = ancestor.parent;
  assert.ok(ancestor && ts.isTryStatement(ancestor), `${relativePath} must catch timeout/abort errors`);
  assert.ok(ancestor.catchClause, `${relativePath} must return a controlled dispatch error`);
  assert.match(ancestor.catchClause.getText(sourceFile), /return\s+NextResponse\.json/);
  assert.match(ancestor.catchClause.getText(sourceFile), /status:\s*502/);
}

test("all Slice 2a action writers guard before auth, client, or database initialization", () => {
  for (const contract of ACTION_CONTRACTS) {
    const { source, sourceFile } = readAction(contract.path);
    assert.match(
      source,
      /import\s+\{\s*assertWritesAllowed\s*\}\s+from\s+"@\/lib\/maintenanceLock\.server";/,
      `${contract.path} must import the shared maintenance guard`,
    );

    const exportedFunctions = runtimeExportNames(sourceFile);
    const classifiedFunctions = [...contract.guarded, ...contract.exempt].sort();
    assert.deepEqual(
      exportedFunctions,
      classifiedFunctions,
      `${contract.path} has an unclassified exported entry point`,
    );

    for (const functionName of contract.guarded) {
      assertGuardIsFirst(
        sourceFile,
        functionName,
        "extraDeniedFalseProperties" in contract
          ? contract.extraDeniedFalseProperties
          : [],
      );
    }
  }
});

test("all Slice 2b route writers guard before params, body, auth, clients, or dispatch", () => {
  for (const contract of ROUTE_CONTRACTS) {
    const { source, sourceFile } = readAction(contract.path);
    assert.match(
      source,
      /import\s+\{\s*assertWritesAllowed\s*\}\s+from\s+"@\/lib\/maintenanceLock\.server";/,
      `${contract.path} must import the shared maintenance guard`,
    );
    assert.deepEqual(
      runtimeExportNames(sourceFile),
      [...contract.runtimeExports].sort(),
      `${contract.path} has an unclassified runtime export`,
    );
    assertRouteGuardIsFirst(sourceFile, contract.handler);
  }
});

test("every GitHub workflow dispatch preserves its request and has a bounded abort", () => {
  for (const contract of ROUTE_CONTRACTS) {
    if (!contract.dispatch) continue;
    const { sourceFile } = readAction(contract.path);
    assertWorkflowDispatchTimeout(sourceFile, contract.path);
  }
});

test("report action modules do not expose injected-client cores", async () => {
  const confirmAction = readAction("app/actions/confirm-report.ts").sourceFile;
  const dismissAction = readAction("app/actions/dismiss-report.ts").sourceFile;

  assert.deepEqual(runtimeExportNames(confirmAction), ["confirmReport"]);
  assert.deepEqual(runtimeExportNames(dismissAction), ["dismissReport"]);

  const confirmModule = await import("../app/actions/confirm-report");
  const dismissModule = await import("../app/actions/dismiss-report");
  assert.equal("runConfirmReport" in confirmModule, false);
  assert.equal("runDismissReport" in dismissModule, false);
});

test("shared helper is read-only and cannot acquire or release the lock", () => {
  const helperPath = path.join(WEB_ROOT, "lib/maintenanceLock.server.ts");
  const source = fs.readFileSync(helperPath, "utf8");
  const sourceFile = ts.createSourceFile(
    helperPath,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const exportedFunctions = sourceFile.statements
    .filter(
      (statement): statement is ts.FunctionDeclaration =>
        ts.isFunctionDeclaration(statement) && Boolean(statement.name) && hasExportModifier(statement),
    )
    .map((statement) => statement.name!.text);

  assert.deepEqual(exportedFunctions, ["assertWritesAllowed"]);
  assert.match(source, /url:\s*process\.env\.NEXT_PUBLIC_SUPABASE_URL/);
  assert.match(source, /serviceKey:\s*process\.env\.SUPABASE_SERVICE_ROLE_KEY/);
  assert.match(source, /createClient\(url,\s*serviceKey,/);
  assert.match(source, /\.from\("app_settings"\)/);
  assert.match(source, /\.select\("value"\)/);
  assert.match(source, /\.eq\("key",\s*LOCK_KEY\)/);
  assert.match(source, /\.limit\(1\)/);
  assert.doesNotMatch(source, /\.(?:insert|update|upsert|delete|rpc)\s*\(/);
  assert.doesNotMatch(source, /\b(?:acquire|release)\w*\s*\(/i);
});
