import { createClient } from "@/lib/supabase/server";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";
import { NextResponse } from "next/server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const WORKFLOW_ID = "scrape-now.yml";
const WORKFLOW_DISPATCH_TIMEOUT_MS = 10_000;

export async function POST(request: Request) {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) {
    return NextResponse.json({ error: "maintenance_active" }, { status: 503 });
  }

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

  // 3. Parse body: { sources: string[] } — empty array means scrape all
  let sources: string[] = [];
  try {
    const body = await request.json();
    if (Array.isArray(body.sources)) {
      sources = body.sources.filter((s: unknown) => typeof s === "string" && s.trim());
    }
  } catch {
    // ignore — default to all sources
  }

  // 4. Trigger GitHub Actions workflow_dispatch
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  let ghRes: Response;
  try {
    ghRes = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github.v3+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: { sources: sources.join(" ") },
        }),
        signal: AbortSignal.timeout(WORKFLOW_DISPATCH_TIMEOUT_MS),
      }
    );
  } catch (error) {
    console.error("[scrape-now] GitHub API request failed:", error);
    return NextResponse.json({ error: "Failed to trigger workflow" }, { status: 502 });
  }

  if (!ghRes.ok) {
    const errorText = await ghRes.text();
    console.error("[scrape-now] GitHub API error:", ghRes.status, errorText);
    return NextResponse.json({ error: "Failed to trigger workflow" }, { status: 502 });
  }

  return NextResponse.json({ ok: true, sources });
}
