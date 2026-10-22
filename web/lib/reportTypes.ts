// Shared report-type predicates (Security Hardening v16, Phase 1).
//
// Single source of truth imported by BOTH the admin client component
// (AdminReportsTable.tsx) and the server action (confirm-report.ts). Do NOT
// duplicate equivalent logic anywhere — predicate drift silently swallows real
// user reports. All predicates are allowlist / deny-by-default: a report is
// "security-only" or "confirmation-only" ONLY when every token is explicitly
// permitted; any unknown or actionable token makes them return false.

export const SECURITY_REPORT_TYPE = "auto_security_prompt_injection";
export const BROKEN_LINK_REPORT_TYPE = "brokenLink";
export const SCOPE_REPORT_TYPE = "scopeReviewNonJapan";

export interface ScopeReportEvidence {
  decision: "out_of_scope" | "uncertain";
  region: "taiwan" | "other_foreign";
  hash: string;
}

export function isScopeMetadataToken(type: string): boolean {
  return (
    type.startsWith("scopeDecision:") ||
    type.startsWith("scopeRegion:") ||
    type.startsWith("scopeHash:")
  );
}

export function isMachineOwnedReportToken(type: string): boolean {
  return (
    type === SCOPE_REPORT_TYPE ||
    type === SECURITY_REPORT_TYPE ||
    isScopeMetadataToken(type) ||
    isSecurityMetadataToken(type)
  );
}

export function arePublicReportTypesAllowed(types: unknown): types is string[] {
  return (
    Array.isArray(types) &&
    types.length > 0 &&
    types.every(
      (type) =>
        typeof type === "string" &&
        type.length > 0 &&
        !isMachineOwnedReportToken(type),
    )
  );
}

export function parseScopeReportEvidence(types: string[]): ScopeReportEvidence | null {
  if (types.length !== 5) return null;
  if (types.filter((type) => type === "irrelevant").length !== 1) return null;
  if (types.filter((type) => type === SCOPE_REPORT_TYPE).length !== 1) return null;

  const decisionTokens = types.filter((type) => type.startsWith("scopeDecision:"));
  const regionTokens = types.filter((type) => type.startsWith("scopeRegion:"));
  const hashTokens = types.filter((type) => type.startsWith("scopeHash:"));
  if (decisionTokens.length !== 1 || regionTokens.length !== 1 || hashTokens.length !== 1) {
    return null;
  }

  const decision = decisionTokens[0].slice("scopeDecision:".length);
  const region = regionTokens[0].slice("scopeRegion:".length);
  const hash = hashTokens[0].slice("scopeHash:".length);
  if (decision !== "out_of_scope" && decision !== "uncertain") return null;
  if (region !== "taiwan" && region !== "other_foreign") return null;
  if (!/^[0-9a-f]{16}$/.test(hash)) return null;

  return { decision, region, hash };
}

export function isBulkConfirmEligible(types: string[]): boolean {
  return !types.some(
    (type) => type === SCOPE_REPORT_TYPE || isScopeMetadataToken(type),
  );
}

export function shouldWriteScraperHistory(types: string[]): boolean {
  return !types.some(
    (type) => type === SCOPE_REPORT_TYPE || isScopeMetadataToken(type),
  );
}

// Machine metadata tokens persisted alongside a security report in
// report_types[] (the finding hash + severity). They ride along in the array
// and must never count as actionable content.
export function isSecurityMetadataToken(t: string): boolean {
  return t.startsWith("securityHash:") || t.startsWith("securitySeverity:");
}

// True only when the report carries the security base type and nothing else
// except security metadata tokens. Any other base token (incl. brokenLink),
// payload token (field: / fieldEdit: / selectionReason:), or unknown future
// token → false.
export function isSecurityOnly(types: string[]): boolean {
  return (
    types.includes(SECURITY_REPORT_TYPE) &&
    types.every((t) => t === SECURITY_REPORT_TYPE || isSecurityMetadataToken(t))
  );
}

// True when the report contains only "confirmation-only" findings — ones that
// must NOT be applied back onto the event: security base, security metadata,
// and brokenLink. Covers brokenLink-only and security+brokenLink mixes. Any
// actionable token (irrelevant / wrongCategory / wrongDetails /
// wrongSelectionReason) or payload token → false.
export function isConfirmationOnlyReport(types: string[]): boolean {
  const hasConfirmationToken =
    types.includes(SECURITY_REPORT_TYPE) || types.includes(BROKEN_LINK_REPORT_TYPE);
  return (
    hasConfirmationToken &&
    types.every(
      (t) =>
        t === SECURITY_REPORT_TYPE ||
        t === BROKEN_LINK_REPORT_TYPE ||
        isSecurityMetadataToken(t),
    )
  );
}
