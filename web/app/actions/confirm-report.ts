"use server";

import type { SupabaseClient } from "@supabase/supabase-js";
import { isConfirmationOnlyReport, BROKEN_LINK_REPORT_TYPE } from "@/lib/reportTypes";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const HISTORY_PATH = ".github/skills/scraper-expert/history.md";

// Maps source_name to the per-source SKILL.md path (if one exists)
const SOURCE_SKILL_PATHS: Record<string, string> = {
  peatix: ".github/skills/peatix/SKILL.md",
  taiwan_cultural_center: ".github/skills/taiwan_cultural_center/SKILL.md",
  connpass: ".github/skills/community-platforms/SKILL.md",
  doorkeeper: ".github/skills/community-platforms/SKILL.md",
};

// Fields that the annotator can re-fill — null these out so re-annotation fixes them
const ANNOTATOR_FIELDS: Record<string, string[]> = {
  name: ["name_zh", "name_en"],
  description: ["description_zh", "description_en"],
  price: ["is_paid", "price_info"],
};

// Scraper-only fields — annotator cannot fix, needs scraper rule update
const SCRAPER_FIELDS = ["start_date", "end_date", "venue", "address", "business_hours"];

// Direct DB column to write when admin provides a correction for a field (per locale)
const FIELD_LOCALE_COL: Record<string, Partial<Record<string, string>>> = {
  name:           { zh: "name_zh",            en: "name_en",           ja: "name_ja" },
  venue:          { zh: "location_name_zh",   en: "location_name_en",  ja: "location_name" },
  address:        { zh: "location_address_zh",en: "location_address_en",ja: "location_address" },
  business_hours: { zh: "business_hours_zh",  en: "business_hours_en", ja: "business_hours" },
  description:    { zh: "description_zh",     en: "description_en",    ja: "description_ja" },
  start_date:     { ja: "start_date" },
  end_date:       { ja: "end_date" },
  price:          { ja: "price_info" },
};

interface ConfirmReportInput {
  reportId: string;
  eventId: string;
  adminNotes: string;
  reportTypes: string[];
  eventName: string;
  sourceName: string | null;
  currentCategory?: string[] | null;
  correctCategory?: string[] | null;   // admin-selected (overrides suggestedCategory)
  suggestedCategory?: string[] | null; // user-submitted suggestion
  fieldCorrections?: Record<string, Record<string, string>>; // field → locale → corrected value
  correctedSelectionReason?: string; // pre-built JSON string {zh,en,ja} for wrongSelectionReason
}

interface ConfirmReportResult {
  ok: boolean;
  githubUpdated: boolean;
  wasReviewed?: boolean;
  error?: string;
}

export async function confirmReport(
  input: ConfirmReportInput
): Promise<ConfirmReportResult> {
  // Maintenance-lock gate (decision-16a): refuse the write while the Admin
  // Reports cleanup window is open. Placed on the entry (not the testable core)
  // so runConfirmReport's injected-client G4b logic stays untouched.
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, githubUpdated: false, error: "maintenance_active" };
  // Dynamic import so unit tests can import this module (and the testable core
  // below) without pulling next/headers at load time; createClient reads cookies.
  const { createClient } = await import("@/lib/supabase/server");
  const supabase = await createClient();
  return runConfirmReport(supabase, input);
}

// Testable core. Accepts an injected Supabase client so the status-last ordering,
// identity-from-DB, pending compare-and-set, and idempotent retry semantics can be
// unit-tested with a fake. Exported (async) from this "use server" module; no client
// component imports it, so it is never invoked as a client-callable action with a
// non-serializable argument.
export async function runConfirmReport(
  supabase: SupabaseClient,
  input: ConfirmReportInput
): Promise<ConfirmReportResult> {
  // Verify admin session
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, githubUpdated: false, error: "Unauthorized" };

  const { data: roleRow, error: roleError } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (roleError || !roleRow || roleRow.role !== "admin") {
    return { ok: false, githubUpdated: false, error: "Forbidden" };
  }

  const now = new Date().toISOString();

  // 1. Identity from the DB, not from client input. Read the unique PENDING report by
  //    full reportId; derive eventId and report types from that row. A 0-row or a
  //    multi-row lookup fails (a report that was already handled is no longer pending).
  const { data: reportRows, error: reportLookupError } = await supabase
    .from("event_reports")
    .select("id,event_id,report_types,status")
    .eq("id", input.reportId)
    .eq("status", "pending");
  if (reportLookupError) {
    return { ok: false, githubUpdated: false, error: reportLookupError.message };
  }
  if (!reportRows || reportRows.length === 0) {
    return { ok: false, githubUpdated: false, error: "Report not found or not pending" };
  }
  if (reportRows.length > 1) {
    return { ok: false, githubUpdated: false, error: "Multiple pending reports for id" };
  }
  const report = reportRows[0] as { event_id: string; report_types: string[] | null };
  const eventId = report.event_id;
  const reportTypes = report.report_types ?? [];

  // Parse field:xxx entries from the DB report types (client reportTypes never drive writes)
  const wrongFields = reportTypes
    .filter((t) => t.startsWith("field:"))
    .map((t) => t.replace("field:", ""));
  const hasScraperOnlyFields = wrongFields.some((f) => SCRAPER_FIELDS.includes(f));

  // 2. Capture the complete event before-image in ONE read, BEFORE any write, so that
  //    field_corrections.original_value and selection_reason ai_sr record the true
  //    originals instead of values a later event update already overwrote.
  const isWrongCategory = reportTypes.includes("wrongCategory");
  const isWrongDetails = reportTypes.includes("wrongDetails") && wrongFields.length > 0;
  const isIrrelevant = reportTypes.includes("irrelevant");
  const isWrongSelectionReason = reportTypes.includes("wrongSelectionReason");
  const corrections = input.fieldCorrections ?? {};

  const fcOriginalCols = isWrongDetails
    ? wrongFields
        .flatMap((f) => Object.values(FIELD_LOCALE_COL[f] ?? {}))
        .filter((v): v is string => Boolean(v))
    : [];
  const beforeCols = Array.from(
    new Set([
      "annotation_status",
      "updated_at",
      "raw_title",
      "raw_description",
      "selection_reason",
      ...fcOriginalCols,
    ])
  );
  const { data: beforeEvent, error: beforeEventError } = await supabase
    .from("events")
    .select(beforeCols.join(","))
    .eq("id", eventId)
    .single();
  if (beforeEventError) {
    return { ok: false, githubUpdated: false, error: beforeEventError.message };
  }
  if (!beforeEvent) {
    return { ok: false, githubUpdated: false, error: "Event not found" };
  }
  const before = beforeEvent as unknown as Record<string, unknown>;
  const currentAnnotationStatus =
    typeof before["annotation_status"] === "string"
      ? (before["annotation_status"] as string)
      : undefined;

  // 3. Build the event update from the DB-derived report types.
  const eventUpdate: Record<string, unknown> = {};

  if (isWrongCategory) {
    // Determine the category to apply: admin > user suggestion > keep empty for re-annotation
    const resolvedCategory = (input.correctCategory && input.correctCategory.length > 0)
      ? input.correctCategory
      : (input.suggestedCategory && input.suggestedCategory.length > 0)
        ? input.suggestedCategory
        : null;

    if (resolvedCategory) {
      // Apply category immediately — no need for full re-annotation
      eventUpdate["category"] = resolvedCategory;
      eventUpdate["is_active"] = true;
      eventUpdate["annotation_status"] = currentAnnotationStatus === "reviewed" ? "reviewed" : "annotated";
      eventUpdate["deactivated_at"] = null;
      eventUpdate["deactivated_reason"] = null;
      eventUpdate["deactivated_by_pass"] = null;
    } else {
      // No category provided — clear and re-annotate
      eventUpdate["category"] = [];
      eventUpdate["is_active"] = false;
      eventUpdate["annotation_status"] = "pending";
      eventUpdate["deactivated_at"] = new Date().toISOString();
      eventUpdate["deactivated_reason"] = "admin reported wrong category; awaiting re-annotation";
      eventUpdate["deactivated_by_pass"] = "admin_manual";
    }
  }

  if (isWrongDetails) {
    // Track which fields still need re-annotation after direct corrections
    const needsReannotation: string[] = [];

    for (const field of wrongFields) {
      const localeCorrs = corrections[field] ?? {};
      const localeColMap = FIELD_LOCALE_COL[field] ?? {};
      let anyProvided = false;

      for (const [loc, dbCol] of Object.entries(localeColMap) as [string, string][]) {
        const value = localeCorrs[loc]?.trim();
        if (value) {
          eventUpdate[dbCol] = value;
          anyProvided = true;
        }
      }

      if (!anyProvided) {
        // No correction for any locale — null out translatable columns for re-annotation
        const dbCols = ANNOTATOR_FIELDS[field];
        if (dbCols) {
          for (const col of dbCols) {
            eventUpdate[col] = null;
          }
          needsReannotation.push(field);
        }
      }
      // If any locale was provided (even partial), apply as-is and mark reviewed.
      // Do NOT null out unprovided locales — keep existing DB values intact.
    }

    if (needsReannotation.length === 0) {
      // All wrong fields fully corrected by admin — mark as reviewed (human-confirmed).
      // Reviewed events are protected from AI re-annotation on subsequent scraper/annotator runs.
      eventUpdate["is_active"] = true;
      eventUpdate["annotation_status"] = "reviewed";
      eventUpdate["deactivated_at"] = null;
      eventUpdate["deactivated_reason"] = null;
      eventUpdate["deactivated_by_pass"] = null;
    } else {
      // Some fields still need AI re-fill
      eventUpdate["is_active"] = false;
      eventUpdate["annotation_status"] = "pending";
      eventUpdate["deactivated_at"] = new Date().toISOString();
      eventUpdate["deactivated_reason"] = `admin reported wrong details (${needsReannotation.join(",")}); awaiting re-annotation`;
      eventUpdate["deactivated_by_pass"] = "admin_manual";
    }
  }

  if (isIrrelevant && !isWrongCategory && !isWrongDetails) {
    eventUpdate["is_active"] = false;
    eventUpdate["deactivated_at"] = new Date().toISOString();
    eventUpdate["deactivated_reason"] = "admin confirmed irrelevant";
    eventUpdate["deactivated_by_pass"] = "admin_manual";
    // annotation_status intentionally NOT set to 'pending' — keeps current value
    // ('annotated' or 'reviewed') so the annotator never re-processes an event
    // that an admin has confirmed as irrelevant. Setting to 'pending' would cause
    // the annotator to re-activate the event on the next daily run.
  }

  // Handle wrongSelectionReason: correctedSelectionReason is already a merged JSON string.
  // Does NOT touch annotation_status or is_active — the event data itself is still valid.
  if (isWrongSelectionReason && input.correctedSelectionReason) {
    eventUpdate["selection_reason"] = input.correctedSelectionReason;
  }

  const finalAnnotationStatus =
    typeof eventUpdate["annotation_status"] === "string"
      ? (eventUpdate["annotation_status"] as string)
      : currentAnnotationStatus;

  // 4. Pre-status write: event update. A value-setting update is idempotent on retry;
  //    .select("id") + exactly-one-row is the 0-row guard so a deleted or
  //    permission-filtered event returns an error instead of a silent success.
  if (Object.keys(eventUpdate).length > 0) {
    const { data: updatedRows, error: eventError } = await supabase
      .from("events")
      .update(eventUpdate)
      .eq("id", eventId)
      .select("id");

    if (eventError) {
      return { ok: false, githubUpdated: false, error: eventError.message };
    }
    if (!updatedRows || updatedRows.length !== 1) {
      return { ok: false, githubUpdated: false, error: "Event not found or changed" };
    }
  }

  // 5. If wrongCategory report: save correction record (admin selection > user suggestion).
  //    A failed correction write returns before the status flip so the report stays
  //    pending and a retry re-runs the identical writes.
  const finalCategory = (input.correctCategory && input.correctCategory.length > 0)
    ? input.correctCategory
    : (input.suggestedCategory && input.suggestedCategory.length > 0)
      ? input.suggestedCategory
      : null;

  if (isWrongCategory && finalCategory) {
    const { error: ccError } = await supabase.from("category_corrections").upsert(
      {
        event_id: eventId,
        raw_title: (before["raw_title"] as string | null) ?? null,
        raw_description: (before["raw_description"] as string | null) ?? null,
        ai_category: input.currentCategory ?? [],
        corrected_category: finalCategory,
        corrected_by: user.id,
      },
      { onConflict: "event_id" }
    );
    if (ccError) {
      return { ok: false, githubUpdated: false, error: ccError.message };
    }
    const { error: catFcError } = await supabase.from("field_corrections").upsert(
      { event_id: eventId, field_name: "category", corrected_value: JSON.stringify(finalCategory) },
      { onConflict: "event_id,field_name" }
    );
    if (catFcError) {
      return { ok: false, githubUpdated: false, error: catFcError.message };
    }
  }

  // 5b. Persist field-level corrections to field_corrections table (P1).
  //     One row per (event_id, field_name). Upserts overwrite on repeat corrections.
  //     The annotator reads this table at startup and skips AI output for any
  //     (event_id, field_name) pair already corrected by a human. Original values come
  //     from the before-image captured prior to the event update above.
  if (isWrongDetails) {
    const fcRows: {
      event_id: string;
      field_name: string;
      original_value: string | null;
      corrected_value: string;
      corrected_by: string;
      report_id: string | null;
    }[] = [];

    for (const field of wrongFields) {
      const localeColMap = FIELD_LOCALE_COL[field] ?? {};
      for (const [loc, dbCol] of Object.entries(localeColMap) as [string, string][]) {
        const corrected = (corrections[field]?.[loc] ?? "").trim();
        if (corrected) {
          fcRows.push({
            event_id: eventId,
            field_name: dbCol,
            original_value: (before[dbCol] as string | null) ?? null,
            corrected_value: corrected,
            corrected_by: user.id,
            report_id: input.reportId ?? null,
          });
        }
      }
    }

    if (fcRows.length > 0) {
      const { error: fcError } = await supabase
        .from("field_corrections")
        .upsert(fcRows, { onConflict: "event_id,field_name" });
      if (fcError) {
        return { ok: false, githubUpdated: false, error: fcError.message };
      }
    }
  }

  // 5c. Persist selection_reason correction to selection_reason_corrections (P3.3 — migration 040).
  //     Records the original AI output vs admin correction as a few-shot training example.
  //     annotator.py reads this table at startup via selection_reason_feedback.py.
  //     The AI original comes from the before-image, not a post-update re-read.
  if (isWrongSelectionReason && input.correctedSelectionReason) {
    const aiSr: unknown = before["selection_reason"]
      ? (() => { try { return JSON.parse(before["selection_reason"] as string); } catch { return null; } })()
      : null;
    const correctedSrParsed: unknown = (() => {
      try { return JSON.parse(input.correctedSelectionReason); } catch { return null; }
    })();

    if (correctedSrParsed) {
      const { error: srError } = await supabase.from("selection_reason_corrections").upsert(
        {
          event_id: eventId,
          raw_title: (before["raw_title"] as string | null) ?? null,
          raw_description: (before["raw_description"] as string | null) ?? null,
          ai_sr: aiSr ?? null,
          corrected_sr: correctedSrParsed,
          corrected_by: user.id,
        },
        { onConflict: "event_id" }
      );
      if (srError) {
        return { ok: false, githubUpdated: false, error: srError.message };
      }
    }
  }
  // 6. STATUS LAST. Every event/correction write above has already succeeded; only now
  //    flip the report to confirmed with a pending compare-and-set. .select("id") +
  //    exactly-one-row means a concurrent confirm/dismiss that already moved this report
  //    off pending loses the race and this call reports the conflict instead of
  //    double-confirming an already-handled report.
  const { data: statusRows, error: statusError } = await supabase
    .from("event_reports")
    .update({
      status: "confirmed",
      confirmed_at: now,
      admin_notes: input.adminNotes || null,
    })
    .eq("id", input.reportId)
    .eq("status", "pending")
    .select("id");
  if (statusError) {
    return { ok: false, githubUpdated: false, error: statusError.message };
  }
  if (!statusRows || statusRows.length !== 1) {
    return { ok: false, githubUpdated: false, error: "Report already handled or not pending" };
  }

  // 7. Best-effort GitHub audit trail AFTER the status commit. A GitHub failure must not
  //    falsify the DB outcome — the report is already confirmed, so githubUpdated=false is
  //    reported while ok stays true.
  const githubUpdated = await appendToHistoryFile(
    input,
    reportTypes,
    wrongFields,
    hasScraperOnlyFields,
    finalAnnotationStatus
  );

  //    Append "Pending Rule" to per-source SKILL.md if one exists. Confirmation-only
  //    reports (security / brokenLink) are not scraper extraction defects, so they must
  //    not write a per-source pending rule.
  const skillPath = input.sourceName ? SOURCE_SKILL_PATHS[input.sourceName] : undefined;
  if (skillPath && !isConfirmationOnlyReport(reportTypes)) {
    await appendPendingRuleToSkill(skillPath, input, reportTypes, wrongFields);
  }

  return { ok: true, githubUpdated, wasReviewed: finalAnnotationStatus === "reviewed" };
}


async function appendToHistoryFile(
  input: ConfirmReportInput,
  reportTypes: string[],
  wrongFields: string[],
  hasScraperOnlyFields: boolean,
  finalAnnotationStatus?: string
): Promise<boolean> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    console.warn("[confirm-report] GITHUB_TOKEN not set — skipping history.md update");
    return false;
  }

  const apiBase = `https://api.github.com/repos/${GITHUB_REPO}/contents/${HISTORY_PATH}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  try {
    // GET current file (10s timeout — prevents button lock-up if GitHub API is slow)
    const getRes = await fetch(apiBase, { headers, signal: AbortSignal.timeout(10_000) });
    if (!getRes.ok) {
      console.error("[confirm-report] GitHub GET failed:", getRes.status, await getRes.text());
      return false;
    }
    const fileData = await getRes.json();
    const currentContent = Buffer.from(fileData.content, "base64").toString("utf-8");
    const sha: string = fileData.sha;

    // Build new entry
    const date = new Date().toISOString().slice(0, 10);
    // Hide machine / payload tokens from the audit trail (hash / severity / field payloads).
    const baseTypes = reportTypes.filter(
      (t) =>
        !t.startsWith("field:") &&
        !t.startsWith("fieldEdit:") &&
        !t.startsWith("selectionReason:") &&
        !t.startsWith("securityHash:") &&
        !t.startsWith("securitySeverity:")
    );
    const types = baseTypes.join(", ");
    const notes = input.adminNotes?.trim() || "—";
    const source = input.sourceName ?? "unknown";

    // Before / After diff for category changes
    const isWrongCat = reportTypes.includes("wrongCategory");
    const finalCat = (input.correctCategory && input.correctCategory.length > 0)
      ? input.correctCategory
      : (input.suggestedCategory && input.suggestedCategory.length > 0)
        ? input.suggestedCategory
        : null;
    const beforeLine = isWrongCat && (input.currentCategory && input.currentCategory.length > 0)
      ? `**Before (AI category):** ${input.currentCategory.join(", ")}\n`
      : "";
    const afterLine = isWrongCat
      ? `**After (corrected):** ${finalCat ? finalCat.join(", ") : "cleared — re-annotation triggered"}\n`
      : "";

    const fieldsLine = wrongFields.length > 0
      ? `**Wrong fields:** ${wrongFields.join(", ")}\n`
      : "";
    const scraperNote = hasScraperOnlyFields
      ? `**⚠ Scraper fix needed:** Fields [${wrongFields.filter(f => SCRAPER_FIELDS.includes(f)).join(", ")}] can only be fixed in the scraper source, not by re-annotation.\n`
      : "";

    // Action description
    let actionLine: string;
    if (reportTypes.includes("irrelevant")) {
      actionLine = "Event hidden (is_active=false). Irrelevant content.";
    } else if (isWrongCat && finalCat) {
      actionLine = `Category corrected inline — event remains active (is_active=true, annotation_status=${finalAnnotationStatus ?? "annotated"}).`;
    } else if (isWrongCat && !finalCat) {
      actionLine = "Category cleared — re-annotation triggered (annotation_status=pending).";
    } else if (wrongFields.some(f => f in ANNOTATOR_FIELDS)) {
      actionLine = "Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.";
    } else if (isConfirmationOnlyReport(reportTypes)) {
      // Confirmation-only report — event data is left untouched.
      actionLine = reportTypes.includes(BROKEN_LINK_REPORT_TYPE)
        ? "Broken link report confirmed; event data unchanged (source link flagged for manual review)"
        : "Security report confirmed; event data unchanged";
    } else {
      actionLine = "Event deactivated — re-annotation triggered (annotation_status=pending).";
    }

    const newEntry = [
      `## ${date} — ${input.eventName} [${source}] — user report confirmed`,
      "",
      `**Report types:** ${types}`,
      beforeLine.trimEnd(),
      afterLine.trimEnd(),
      fieldsLine.trimEnd(),
      scraperNote.trimEnd(),
      `**Admin notes:** ${notes}`,
      `**Action:** ${actionLine}`,
      "",
      "---",
      "",
    ].filter(line => line !== "").join("\n") + "\n\n---\n\n";

    // Prepend after the file header comment (after the first blank line following <!-- ... -->)
    const insertMarker = "<!-- Append new entries at the top -->";
    let updatedContent: string;
    if (currentContent.includes(insertMarker)) {
      updatedContent = currentContent.replace(
        insertMarker + "\n",
        insertMarker + "\n\n" + newEntry
      );
    } else {
      // Fallback: prepend after first line
      const lines = currentContent.split("\n");
      lines.splice(1, 0, "", newEntry);
      updatedContent = lines.join("\n");
    }

    // PUT updated file (10s timeout)
    const putRes = await fetch(apiBase, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `docs(skills): record confirmed report — ${input.eventName} [${source}]`,
        content: Buffer.from(updatedContent, "utf-8").toString("base64"),
        sha,
      }),
      signal: AbortSignal.timeout(10_000),
    });

    if (!putRes.ok) {
      console.error("[confirm-report] GitHub PUT failed:", putRes.status, await putRes.text());
      return false;
    }

    return true;
  } catch (err) {
    console.error("[confirm-report] GitHub API error:", err);
    return false;
  }
}

async function appendPendingRuleToSkill(
  skillPath: string,
  input: ConfirmReportInput,
  reportTypes: string[],
  wrongFields: string[]
): Promise<void> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) return;

  const apiBase = `https://api.github.com/repos/${GITHUB_REPO}/contents/${skillPath}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  try {
    const getRes = await fetch(apiBase, { headers, signal: AbortSignal.timeout(10_000) });
    if (!getRes.ok) return;
    const fileData = await getRes.json();
    const currentContent = Buffer.from(fileData.content, "base64").toString("utf-8");
    const sha: string = fileData.sha;

    const date = new Date().toISOString().slice(0, 10);
    // Hide machine / payload tokens from the audit trail (hash / severity / field payloads).
    const baseTypes = reportTypes.filter(
      (t) =>
        !t.startsWith("field:") &&
        !t.startsWith("fieldEdit:") &&
        !t.startsWith("selectionReason:") &&
        !t.startsWith("securityHash:") &&
        !t.startsWith("securitySeverity:")
    );
    const types = baseTypes.join(", ");
    const notes = input.adminNotes?.trim() || "—";
    const fieldsLine = wrongFields.length > 0
      ? `- **Wrong fields:** ${wrongFields.join(", ")}\n`
      : "";
    const scraperFields = wrongFields.filter(f => SCRAPER_FIELDS.includes(f));
    const scraperNote = scraperFields.length > 0
      ? `- **⚠ Scraper fix needed for:** ${scraperFields.join(", ")} — investigate selector/parsing logic.\n`
      : "";

    // Classifier hint: only when wrongCategory + correction provided + admin left notes
    const finalCat = (input.correctCategory && input.correctCategory.length > 0)
      ? input.correctCategory
      : (input.suggestedCategory && input.suggestedCategory.length > 0)
        ? input.suggestedCategory
        : null;
    const classifierHint = reportTypes.includes("wrongCategory") && finalCat
      ? `- **Classifier hint:** AI labelled as [${(input.currentCategory ?? []).join(", ") || "unknown"}] → should be [${finalCat.join(", ")}]. Admin notes: "${notes}". Update annotator prompt or category_corrections if this pattern recurs.\n`
      : "";

    const newEntry = [
      `### ${date} — ${input.eventName}`,
      `- **Report type:** ${types}`,
      fieldsLine.trimEnd(),
      scraperNote.trimEnd(),
      classifierHint.trimEnd(),
      `- **Admin notes:** ${notes}`,
      `- **Action needed:** ${scraperFields.length > 0 ? "Fix scraper field extraction; add test case." : finalCat ? "Category corrected — monitor if same event type keeps misfiring; add to annotator prompt if pattern." : "Re-annotation triggered automatically."}`,
      "",
    ].filter(line => line !== "").join("\n") + "\n";

    const SECTION_HEADER = "## Pending Rules\n\n<!-- Added automatically by confirm-report -->";
    let updatedContent: string;

    if (currentContent.includes("## Pending Rules")) {
      // Insert after the section header
      updatedContent = currentContent.replace(
        /## Pending Rules\n+<!-- Added automatically by confirm-report -->\n+/,
        `## Pending Rules\n\n<!-- Added automatically by confirm-report -->\n\n${newEntry}`
      );
    } else {
      // Append new section at the end
      updatedContent = currentContent.trimEnd() + "\n\n" + SECTION_HEADER + "\n\n" + newEntry;
    }

    await fetch(apiBase, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `docs(skills): add pending rule — ${input.eventName}`,
        content: Buffer.from(updatedContent, "utf-8").toString("base64"),
        sha,
      }),
      signal: AbortSignal.timeout(10_000),
    });
  } catch (err) {
    console.error("[confirm-report] per-source SKILL.md update error:", err);
  }
}
