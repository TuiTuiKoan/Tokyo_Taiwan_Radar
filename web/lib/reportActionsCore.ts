import type { SupabaseClient } from "@supabase/supabase-js";
import {
  BROKEN_LINK_REPORT_TYPE,
  SCOPE_REPORT_TYPE,
  isConfirmationOnlyReport,
  shouldWriteScraperHistory,
} from "@/lib/reportTypes";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const HISTORY_PATH = ".github/skills/scraper-expert/history.md";

const SOURCE_SKILL_PATHS: Record<string, string> = {
  peatix: ".github/skills/peatix/SKILL.md",
  taiwan_cultural_center: ".github/skills/taiwan_cultural_center/SKILL.md",
  connpass: ".github/skills/community-platforms/SKILL.md",
  doorkeeper: ".github/skills/community-platforms/SKILL.md",
};

const ANNOTATOR_FIELDS: Record<string, string[]> = {
  name: ["name_zh", "name_en"],
  description: ["description_zh", "description_en"],
  price: ["is_paid", "price_info"],
};

const SCRAPER_FIELDS = ["start_date", "end_date", "venue", "address", "business_hours"];

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

export interface ConfirmReportInput {
  reportId: string;
  eventId: string;
  adminNotes: string;
  reportTypes: string[];
  scopeAcknowledged?: boolean;
  eventName: string;
  sourceName: string | null;
  currentCategory?: string[] | null;
  correctCategory?: string[] | null;
  suggestedCategory?: string[] | null;
  fieldCorrections?: Record<string, Record<string, string>>;
  correctedSelectionReason?: string;
}

export type HistoryStatus = "written" | "not_applicable" | "skipped";

export interface ConfirmReportResult {
  ok: boolean;
  githubUpdated: boolean;
  historyStatus?: HistoryStatus;
  wasReviewed?: boolean;
  error?: string;
}

export async function runConfirmReport(
  supabase: SupabaseClient,
  input: ConfirmReportInput
): Promise<ConfirmReportResult> {
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

  const { data: reportRows, error: reportLookupError } = await supabase
    .from("event_reports")
    .select("id,event_id,report_types,status,admin_notes")
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
  const report = reportRows[0] as {
    event_id: string;
    report_types: string[] | null;
    admin_notes: string | null;
  };
  const eventId = report.event_id;
  const reportTypes = report.report_types ?? [];
  const isScopeReport = reportTypes.includes(SCOPE_REPORT_TYPE);
  if (isScopeReport && input.scopeAcknowledged !== true) {
    return {
      ok: false,
      githubUpdated: false,
      error: "scope report requires per-row review",
    };
  }

  const wrongFields = reportTypes
    .filter((t) => t.startsWith("field:"))
    .map((t) => t.replace("field:", ""));
  const hasScraperOnlyFields = wrongFields.some((f) => SCRAPER_FIELDS.includes(f));

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
  const before: Record<string, unknown> = {
    ...(beforeEvent as unknown as Record<string, unknown>),
    admin_notes: report.admin_notes,
  };
  const currentAnnotationStatus =
    typeof before["annotation_status"] === "string"
      ? (before["annotation_status"] as string)
      : undefined;

  const eventUpdate: Record<string, unknown> = {};

  if (isWrongCategory) {
    const resolvedCategory = (input.correctCategory && input.correctCategory.length > 0)
      ? input.correctCategory
      : (input.suggestedCategory && input.suggestedCategory.length > 0)
        ? input.suggestedCategory
        : null;

    if (resolvedCategory) {
      eventUpdate["category"] = resolvedCategory;
      eventUpdate["is_active"] = true;
      eventUpdate["annotation_status"] = currentAnnotationStatus === "reviewed" ? "reviewed" : "annotated";
      eventUpdate["deactivated_at"] = null;
      eventUpdate["deactivated_reason"] = null;
      eventUpdate["deactivated_by_pass"] = null;
    } else {
      eventUpdate["category"] = [];
      eventUpdate["is_active"] = false;
      eventUpdate["annotation_status"] = "pending";
      eventUpdate["deactivated_at"] = new Date().toISOString();
      eventUpdate["deactivated_reason"] = "admin reported wrong category; awaiting re-annotation";
      eventUpdate["deactivated_by_pass"] = "admin_manual";
    }
  }

  if (isWrongDetails) {
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
        const dbCols = ANNOTATOR_FIELDS[field];
        if (dbCols) {
          for (const col of dbCols) {
            eventUpdate[col] = null;
          }
          needsReannotation.push(field);
        }
      }
    }

    if (needsReannotation.length === 0) {
      eventUpdate["is_active"] = true;
      eventUpdate["annotation_status"] = "reviewed";
      eventUpdate["deactivated_at"] = null;
      eventUpdate["deactivated_reason"] = null;
      eventUpdate["deactivated_by_pass"] = null;
    } else {
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
    eventUpdate["deactivated_reason"] = isScopeReport
      ? "out_of_scope: non-Japan audience — admin confirmed"
      : "admin confirmed irrelevant";
    eventUpdate["deactivated_by_pass"] = "admin_manual";
  }

  if (isWrongSelectionReason && input.correctedSelectionReason) {
    eventUpdate["selection_reason"] = input.correctedSelectionReason;
  }

  const finalAnnotationStatus =
    typeof eventUpdate["annotation_status"] === "string"
      ? (eventUpdate["annotation_status"] as string)
      : currentAnnotationStatus;

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

  const { data: statusRows, error: statusError } = await supabase
    .from("event_reports")
    .update({
      status: "confirmed",
      confirmed_at: now,
      admin_notes: isScopeReport
        ? [before["admin_notes"], input.adminNotes].filter(Boolean).join("\n---\n") || null
        : input.adminNotes || null,
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

  const writeScraperHistory = shouldWriteScraperHistory(reportTypes);
  const historyStatus: HistoryStatus = !writeScraperHistory
    ? "not_applicable"
    : (await appendToHistoryFile(
        input,
        reportTypes,
        wrongFields,
        hasScraperOnlyFields,
        finalAnnotationStatus
      ))
      ? "written"
      : "skipped";
  const githubUpdated = historyStatus === "written";

  const skillPath = input.sourceName ? SOURCE_SKILL_PATHS[input.sourceName] : undefined;
  if (writeScraperHistory && skillPath && !isConfirmationOnlyReport(reportTypes)) {
    await appendPendingRuleToSkill(skillPath, input, reportTypes, wrongFields);
  }

  return {
    ok: true,
    githubUpdated,
    historyStatus,
    wasReviewed: finalAnnotationStatus === "reviewed",
  };
}

export async function runDismissReport(
  supabase: SupabaseClient,
  reportId: string
): Promise<{ ok: boolean; error?: string }> {
  const { error, data } = await supabase
    .from("event_reports")
    .update({ status: "dismissed", confirmed_at: new Date().toISOString() })
    .eq("id", reportId)
    .eq("status", "pending")
    .select("id");

  if (error) {
    return { ok: false, error: error.message };
  }
  if (!data || data.length === 0) {
    return { ok: false, error: "0 rows updated — report not found or not pending" };
  }
  if (data.length > 1) {
    return { ok: false, error: "Multiple pending reports for id" };
  }
  return { ok: true };
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
    const getRes = await fetch(apiBase, { headers, signal: AbortSignal.timeout(10_000) });
    if (!getRes.ok) {
      console.error("[confirm-report] GitHub GET failed:", getRes.status, await getRes.text());
      return false;
    }
    const fileData = await getRes.json();
    const currentContent = Buffer.from(fileData.content, "base64").toString("utf-8");
    const sha: string = fileData.sha;

    const date = new Date().toISOString().slice(0, 10);
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

    const insertMarker = "<!-- Append new entries at the top -->";
    let updatedContent: string;
    if (currentContent.includes(insertMarker)) {
      updatedContent = currentContent.replace(
        insertMarker + "\n",
        insertMarker + "\n\n" + newEntry
      );
    } else {
      const lines = currentContent.split("\n");
      lines.splice(1, 0, "", newEntry);
      updatedContent = lines.join("\n");
    }

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
      updatedContent = currentContent.replace(
        /## Pending Rules\n+<!-- Added automatically by confirm-report -->\n+/,
        `## Pending Rules\n\n<!-- Added automatically by confirm-report -->\n\n${newEntry}`
      );
    } else {
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