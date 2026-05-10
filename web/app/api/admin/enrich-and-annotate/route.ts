import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";
const WORKFLOW_ID = "enrich-and-annotate.yml";

export async function POST(req: NextRequest) {
  // 1. Admin auth check
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin")
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  // 2. Parse body
  const { eventId } = (await req.json()) as { eventId: string };
  if (!eventId) return NextResponse.json({ error: "eventId required" }, { status: 400 });

  // 3. Trigger GitHub Actions workflow_dispatch
  const token = process.env.GITHUB_TOKEN;
  if (!token)
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });

  const ghRes = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs: { event_id: eventId } }),
    }
  );

  if (!ghRes.ok) {
    const errText = await ghRes.text();
    return NextResponse.json(
      { error: `GitHub API error ${ghRes.status}`, raw: errText },
      { status: 502 }
    );
  }

  return NextResponse.json({ ok: true });
}
