import assert from "node:assert/strict";
import test from "node:test";

import {
  BROKEN_LINK_REPORT_TYPE,
  SECURITY_REPORT_TYPE,
  SCOPE_REPORT_TYPE,
  arePublicReportTypesAllowed,
  isBulkConfirmEligible,
  isConfirmationOnlyReport,
  isMachineOwnedReportToken,
  parseScopeReportEvidence,
  isSecurityOnly,
  isScopeMetadataToken,
  shouldWriteScraperHistory,
} from "../lib/reportTypes";

test("scope reports are excluded from bulk confirm without changing existing types", () => {
  assert.equal(isBulkConfirmEligible([SCOPE_REPORT_TYPE]), false);
  assert.equal(isBulkConfirmEligible([SCOPE_REPORT_TYPE, "scopeDecision:out_of_scope"]), false);
  assert.equal(isBulkConfirmEligible([SECURITY_REPORT_TYPE]), true);
  assert.equal(isBulkConfirmEligible([BROKEN_LINK_REPORT_TYPE]), true);
  assert.equal(isBulkConfirmEligible(["wrongCategory"]), true);
  assert.equal(isBulkConfirmEligible(["wrongDetails"]), true);
});

test("scope reports skip scraper history without changing existing history policy", () => {
  assert.equal(shouldWriteScraperHistory([SCOPE_REPORT_TYPE]), false);
  assert.equal(shouldWriteScraperHistory([SCOPE_REPORT_TYPE, "scopeRegion:outside_japan"]), false);
  assert.equal(shouldWriteScraperHistory([SECURITY_REPORT_TYPE]), true);
  assert.equal(shouldWriteScraperHistory([BROKEN_LINK_REPORT_TYPE]), true);
  assert.equal(shouldWriteScraperHistory(["wrongCategory"]), true);
  assert.equal(shouldWriteScraperHistory(["wrongDetails"]), true);
});

test("scope metadata helper recognizes only canonical metadata prefixes", () => {
  assert.equal(isScopeMetadataToken("scopeDecision:out_of_scope"), true);
  assert.equal(isScopeMetadataToken("scopeRegion:outside_japan"), true);
  assert.equal(isScopeMetadataToken("scopeHash:abc123"), true);
  assert.equal(isScopeMetadataToken(SCOPE_REPORT_TYPE), false);
  assert.equal(isScopeMetadataToken("scopeDecision"), false);
  assert.equal(isScopeMetadataToken("securityHash:abc123"), false);
});

test("canonical scope evidence requires the exact machine payload", () => {
  const canonical = [
    "irrelevant",
    SCOPE_REPORT_TYPE,
    "scopeDecision:out_of_scope",
    "scopeRegion:taiwan",
    "scopeHash:0123456789abcdef",
  ];
  assert.deepEqual(parseScopeReportEvidence(canonical), {
    decision: "out_of_scope",
    region: "taiwan",
    hash: "0123456789abcdef",
  });
  assert.equal(parseScopeReportEvidence(canonical.slice(0, -1)), null);
  assert.equal(parseScopeReportEvidence([...canonical, "wrongCategory"]), null);
  assert.equal(
    parseScopeReportEvidence(canonical.map((type) =>
      type.startsWith("scopeHash:") ? "scopeHash:not-a-hash" : type
    )),
    null,
  );
});

test("public report guard reserves all machine-owned tokens", () => {
  assert.equal(isMachineOwnedReportToken(SCOPE_REPORT_TYPE), true);
  assert.equal(isMachineOwnedReportToken("scopeHash:0123456789abcdef"), true);
  assert.equal(isMachineOwnedReportToken(SECURITY_REPORT_TYPE), true);
  assert.equal(isMachineOwnedReportToken("securitySeverity:4"), true);
  assert.equal(isMachineOwnedReportToken("wrongCategory"), false);
  assert.equal(arePublicReportTypesAllowed(["wrongCategory", "field:name"]), true);
  assert.equal(arePublicReportTypesAllowed([]), false);
  assert.equal(arePublicReportTypesAllowed(["wrongCategory", 7]), false);
  assert.equal(arePublicReportTypesAllowed([SCOPE_REPORT_TYPE]), false);
  assert.equal(arePublicReportTypesAllowed(["scopeHash:0123456789abcdef"]), false);
});

test("scope tokens do not loosen security or confirmation-only allowlists", () => {
  assert.equal(isSecurityOnly([SECURITY_REPORT_TYPE, "securityHash:abc123"]), true);
  assert.equal(isConfirmationOnlyReport([BROKEN_LINK_REPORT_TYPE]), true);
  assert.equal(
    isSecurityOnly([SECURITY_REPORT_TYPE, SCOPE_REPORT_TYPE, "securityHash:abc123"]),
    false,
  );
  assert.equal(
    isConfirmationOnlyReport([BROKEN_LINK_REPORT_TYPE, SCOPE_REPORT_TYPE]),
    false,
  );
});