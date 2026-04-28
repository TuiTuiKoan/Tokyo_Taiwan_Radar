"use server";

import { createClient } from "@/lib/supabase/server";

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
}

interface ConfirmReportResult {
  ok: boolean;
  githubUpdated: boolean;
  error?: string;
}

export async function confirmReport(
  input: ConfirmReportInput
): Promise<ConfirmReportResult> {
  const supabase = await createClient();

  // Verify admin session
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, githubUpdated: false, error: "Unauthorized" };

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") {
    return { ok: false, githubUpdated: false, error: "Forbidden" };
  }

  const now = new Date().toISOString();

  // Parse field:xxx entries from report_types
  const wrongFields = input.reportTypes
    .filter((t) => t.startsWith("field:"))
    .map((t) => t.replace("field:", ""));
  const hasAnnotatorFixableFields = wrongFields.some((f) => f in ANNOTATOR_FIELDS);
  const hasScraperOnlyFields = wrongFields.some((f) => SCRAPER_FIELDS.includes(f));

  // 1. Update event_reports
  const { error: reportError } = await supabase
    .from("event_reports")
    .update({
      status: "confirmed",
      confirmed_at: now,
      admin_notes: input.adminNotes || null,
    })
    .eq("id", input.reportId);

  if (reportError) {
    return { ok: false, githubUpdated: false, error: reportError.message };
  }

  // 2. Update the event based on what was reported wrong
  const eventUpdate: Record<string, unknown> = {};
  const isWrongCategory = input.reportTypes.includes("wrongCategory");
  const isWrongDetails = input.reportTypes.includes("wrongDetails") && wrongFields.length > 0;
  const isIrrelevant = input.reportTypes.includes("irrelevant");
  const corrections = input.fieldCorrections ?? {};

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
      eventUpdate["annotation_status"] = "annotated";
    } else {
      // No category provided — clear and re-annotate
      eventUpdate["category"] = [];
      eventUpdate["is_active"] = false;
      eventUpdate["annotation_status"] = "pending";
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
      } else if (field === "name") {
        // Partially corrected: null out any locale column not explicitly provided
        // so annotator re-fills missing translations
        for (const [loc, dbCol] of Object.entries(localeColMap) as [string, string][]) {
          if (!localeCorrs[loc]?.trim()) {
            eventUpdate[dbCol] = null;
          }
        }
        needsReannotation.push(field);
      }
    }

    // Determine is_active: re-activate only if all fixable fields were corrected
    // and none require annotator re-fill (name and description always do)
    const directlyFixableFields = wrongFields.filter(
      (f) => f !== "description" && Object.keys(FIELD_LOCALE_COL[f] ?? {}).length > 0
    );
    const allDirectlyFixed =
      directlyFixableFields.length === wrongFields.length &&
      directlyFixableFields.every((f) => {
        const localeCorrs = corrections[f] ?? {};
        return Object.values(localeCorrs).some((v) => v?.trim());
      });
    const nameInvolved = wrongFields.includes("name");

    if (allDirectlyFixed && !nameInvolved && !wrongFields.includes("description")) {
      eventUpdate["is_active"] = true;
      eventUpdate["annotation_status"] = "annotated";
    } else {
      eventUpdate["is_active"] = false;
      eventUpdate["annotation_status"] = "pending";
    }
  }

  if (isIrrelevant && !isWrongCategory && !isWrongDetails) {
    eventUpdate["is_active"] = false;
    eventUpdate["annotation_status"] = "pending";
  }

  if (Object.keys(eventUpdate).length > 0) {
    const { error: eventError } = await supabase
      .from("events")
      .update(eventUpdate)
      .eq("id", input.eventId);

    if (eventError) {
      return { ok: false, githubUpdated: false, error: eventError.message };
    }
  }

  // 3. If wrongCategory report: save correction record (admin selection > user suggestion)
  const finalCategory = (input.correctCategory && input.correctCategory.length > 0)
    ? input.correctCategory
    : (input.suggestedCategory && input.suggestedCategory.length > 0)
      ? input.suggestedCategory
      : null;

  if (input.reportTypes.includes("wrongCategory") && finalCategory) {
    const { data: eventData } = await supabase
      .from("events")
      .select("raw_title, raw_description")
      .eq("id", input.eventId)
      .single();

    await supabase.from("category_corrections").upsert(
      {
        event_id: input.eventId,
        raw_title: eventData?.raw_title ?? null,
        raw_description: eventData?.raw_description ?? null,
        ai_category: input.currentCategory ?? [],
        corrected_category: finalCategory,
        corrected_by: user.id,
      },
      { onConflict: "event_id" }
    );
  }

  // 4. Append entry to scraper-expert history.md via GitHub API
  const githubUpdated = await appendToHistoryFile(input, wrongFields, hasScraperOnlyFields);

  // 5. Append "Pending Rule" to per-source SKILL.md if one exists
  const skillPath = input.sourceName ? SOURCE_SKILL_PATHS[input.sourceName] : undefined;
  if (skillPath) {
    await appendPendingRuleToSkill(skillPath, input, wrongFields);
  }

  return { ok: true, githubUpdated };
}


async function appendToHistoryFile(
  input: ConfirmReportInput,
  wrongFields: string[],
  hasScraperOnlyFields: boolean
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
    // GET current file
    const getRes = await fetch(apiBase, { headers });
    if (!getRes.ok) {
      console.error("[confirm-report] GitHub GET failed:", getRes.status, await getRes.text());
      return false;
    }
    const fileData = await getRes.json();
    const currentContent = Buffer.from(fileData.content, "base64").toString("utf-8");
    const sha: string = fileData.sha;

    // Build new entry
    const date = new Date().toISOString().slice(0, 10);
    const baseTypes = input.reportTypes.filter((t) => !t.startsWith("field:"));
    const types = baseTypes.join(", ");
    const notes = input.adminNotes?.trim() || "—";
    const source = input.sourceName ?? "unknown";

    // Before / After diff for category changes
    const isWrongCat = input.reportTypes.includes("wrongCategory");
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
    if (input.reportTypes.includes("irrelevant")) {
      actionLine = "Event hidden (is_active=false). Irrelevant content.";
    } else if (isWrongCat && finalCat) {
      actionLine = "Category corrected inline — event remains active (is_active=true, annotation_status=annotated).";
    } else if (isWrongCat && !finalCat) {
      actionLine = "Category cleared — re-annotation triggered (annotation_status=pending).";
    } else if (wrongFields.some(f => f in ANNOTATOR_FIELDS)) {
      actionLine = "Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.";
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

    // PUT updated file
    const putRes = await fetch(apiBase, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `docs(skills): record confirmed report — ${input.eventName} [${source}]`,
        content: Buffer.from(updatedContent, "utf-8").toString("base64"),
        sha,
      }),
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
    const getRes = await fetch(apiBase, { headers });
    if (!getRes.ok) return;
    const fileData = await getRes.json();
    const currentContent = Buffer.from(fileData.content, "base64").toString("utf-8");
    const sha: string = fileData.sha;

    const date = new Date().toISOString().slice(0, 10);
    const baseTypes = input.reportTypes.filter((t) => !t.startsWith("field:"));
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
    const classifierHint = input.reportTypes.includes("wrongCategory") && finalCat
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
    });
  } catch (err) {
    console.error("[confirm-report] per-source SKILL.md update error:", err);
  }
}
