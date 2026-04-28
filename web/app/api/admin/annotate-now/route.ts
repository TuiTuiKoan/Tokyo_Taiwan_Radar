import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const WORKFLOW_ID = "annotate-now.yml";

export async function POST() {
  // 1. Auth check
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
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

  // 3. Count pending events
  const { count: initialPending } = await supabase
    .from("events")
    .select("*", { count: "exact", head: true })
    .eq("annotation_status", "pending");

  // 4. Trigger GitHub Actions workflow_dispatch
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  const ghRes = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );

  if (!ghRes.ok) {
    const errorText = await ghRes.text();
    console.error("[annotate-now] GitHub API error:", ghRes.status, errorText);
    return NextResponse.json({ error: "Failed to trigger workflow" }, { status: 502 });
  }

  return NextResponse.json({ ok: true, initialPending: initialPending ?? 0 });
}
