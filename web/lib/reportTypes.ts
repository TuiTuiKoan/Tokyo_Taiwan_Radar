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
