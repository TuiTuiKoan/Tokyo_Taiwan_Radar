import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { supabase, user: null, error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) };
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return { supabase, user: null, error: NextResponse.json({ error: "Forbidden" }, { status: 403 }) };
  return { supabase, user, error: null };
}

// GET /api/admin/weekly-broadcast
// Returns: { auto_publish: boolean, draft: { id, slug, title_zh, created_at } | null }
export async function GET() {
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;

  const { data: setting } = await supabase
    .from("app_settings")
    .select("value")
    .eq("key", "weekly_broadcast")
    .maybeSingle();

  const auto_publish = (setting?.value as Record<string, unknown> | null)?.auto_publish ?? false;

  const { data: draft } = await supabase
    .from("announcements")
    .select("id, slug, title_zh, title_ja, created_at, published_at")
    .eq("type", "weekly_broadcast")
    .is("published_at", null)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  return NextResponse.json({ auto_publish, draft: draft ?? null });
}

// PATCH /api/admin/weekly-broadcast
// Body: { auto_publish: boolean }
export async function PATCH(request: Request) {
  const { supabase, user, error: authError } = await requireAdmin();
  if (authError) return authError;

  const body = await request.json();
  const auto_publish = Boolean(body.auto_publish);

  const { error } = await supabase
    .from("app_settings")
    .upsert(
      { key: "weekly_broadcast", value: { auto_publish }, updated_at: new Date().toISOString(), updated_by: user!.id },
      { onConflict: "key" }
    );

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ auto_publish });
}
