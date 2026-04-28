import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const WORKFLOW_ID = "scrape-now.yml";

export async function GET() {
  // 1. Auth check
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. Admin role check
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // 3. Query GitHub for the latest scrape-now.yml run
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  const ghRes = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/runs?per_page=1`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
      // No-store to always get fresh status
      cache: "no-store",
    }
  );

  if (!ghRes.ok) {
    return NextResponse.json({ error: "GitHub API error" }, { status: 502 });
  }

  const body = await ghRes.json();
  const run = body.workflow_runs?.[0];

  if (!run) {
    return NextResponse.json({ status: "none" });
  }

  return NextResponse.json({
    status: run.status,           // "queued" | "in_progress" | "completed"
    conclusion: run.conclusion,   // "success" | "failure" | null
    startedAt: run.run_started_at ?? run.created_at,
    runUrl: run.html_url,
  });
}
