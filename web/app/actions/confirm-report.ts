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
  iwafu: ".github/skills/iwafu/SKILL.md",
  koryu: ".github/skills/koryu/SKILL.md",
  taioan_dokyokai: ".github/skills/taioan_dokyokai/SKILL.md",
  taiwan_kyokai: ".github/skills/taiwan_kyokai/SKILL.md",
  ide_jetro: ".github/skills/ide_jetro/SKILL.md",
  taiwan_festival_tokyo: ".github/skills/taiwan_festival_tokyo/SKILL.md",
  arukikata: ".github/skills/arukikata/SKILL.md",
};

interface ConfirmReportInput {
  reportId: string;
  eventId: string;
  adminNotes: string;
  reportTypes: string[];
  eventName: string;
  sourceName: string | null;
  currentCategory?: string[] | null;
  correctCategory?: string[] | null;
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

  // 2. Deactivate event + reset annotation_status
  const { error: eventError } = await supabase
    .from("events")
    .update({ is_active: false, annotation_status: "pending" })
    .eq("id", input.eventId);

  if (eventError) {
    return { ok: false, githubUpdated: false, error: eventError.message };
  }

  // 3. If wrongCategory report and admin provided correct categories, save to category_corrections
  if (
    input.reportTypes.includes("wrongCategory") &&
    input.correctCategory &&
    input.correctCategory.length > 0
  ) {
    // Fetch raw_title + raw_description for the correction record
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
        corrected_category: input.correctCategory,
        corrected_by: user.id,
      },
      { onConflict: "event_id" }
    );
  }

  // 4. Append entry to scraper-expert history.md via GitHub API
  const githubUpdated = await appendToHistoryFile(input);
  // 4. Append "Pending Rule" to per-source SKILL.md if one exists
  const skillPath = input.sourceName ? SOURCE_SKILL_PATHS[input.sourceName] : undefined;
  if (skillPath) {
    await appendPendingRuleToSkill(skillPath, input);
  }
  return { ok: true, githubUpdated };
}

async function appendToHistoryFile(
  input: ConfirmReportInput
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
    const types = input.reportTypes.join(", ");
    const notes = input.adminNotes?.trim() || "—";
    const source = input.sourceName ?? "unknown";
    const newEntry = [
      `## ${date} — ${input.eventName} [${source}] — user report confirmed`,
      "",
      `**Report types:** ${types}`,
      `**Admin notes:** ${notes}`,
      `**Action:** Event deactivated (is_active=false), re-annotation triggered (annotation_status=pending).`,
      "",
      "---",
      "",
    ].join("\n");

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
  input: ConfirmReportInput
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
    const types = input.reportTypes.join(", ");
    const notes = input.adminNotes?.trim() || "—";
    const newEntry = [
      `### ${date} — ${input.eventName}`,
      `- **Report type:** ${types}`,
      `- **Admin notes:** ${notes}`,
      `- **Action needed:** Investigate and add scraper filter, field correction, or category rule.`,
      "",
    ].join("\n");

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
