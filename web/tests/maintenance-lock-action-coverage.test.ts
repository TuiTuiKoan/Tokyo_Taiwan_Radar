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
