import assert from "node:assert/strict";
import test from "node:test";

import {
  BROKEN_LINK_REPORT_TYPE,
  SECURITY_REPORT_TYPE,
  SCOPE_REPORT_TYPE,
  isBulkConfirmEligible,
  isConfirmationOnlyReport,
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