"use server";

import { createClient } from "@/lib/supabase/server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const HISTORY_PATH = ".github/skills/scraper-expert/history.md";

interface ConfirmReportInput {
  reportId: string;
  eventId: string;
  adminNotes: string;
  reportTypes: string[];
  eventName: string;
  sourceName: string | null;
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

  // 3. Append entry to scraper-expert history.md via GitHub API
  const githubUpdated = await appendToHistoryFile(input);

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
