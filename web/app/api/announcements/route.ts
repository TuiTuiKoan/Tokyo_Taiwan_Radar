import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

// Helper: verify caller is admin
async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { supabase, user: null, error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) };
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return { supabase, user: null, error: NextResponse.json({ error: "Forbidden" }, { status: 403 }) };
  return { supabase, user, error: null };
}

// GET /api/announcements — public: list published; admin: list all
export async function GET(request: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  let isAdmin = false;
  if (user) {
    const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
    isAdmin = roleRow?.role === "admin";
  }

  const url = new URL(request.url);
  const featuredOnly = url.searchParams.get("featured") === "1";
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "20"), 100);
  const offset = parseInt(url.searchParams.get("offset") ?? "0");

  let query = supabase
    .from("announcements")
    .select("*")
    .order("published_at", { ascending: false, nullsFirst: false })
    .range(offset, offset + limit - 1);

  if (!isAdmin) {
    query = query.not("published_at", "is", null).lte("published_at", new Date().toISOString());
  }
  if (featuredOnly) {
    query = query.eq("is_featured", true);
  }

  const { data, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

// POST /api/announcements — admin: create
export async function POST(request: Request) {
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;

  const body = await request.json();
  const { linked_events, ...fields } = body;

  const { data: announcement, error } = await supabase
    .from("announcements")
    .insert({ ...fields, social_status: {} })
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Insert junction rows
  if (Array.isArray(linked_events) && linked_events.length > 0) {
    await supabase.from("announcement_events").insert(
      linked_events.map((event_id: string) => ({ announcement_id: announcement.id, event_id }))
    );
  }

  return NextResponse.json(announcement, { status: 201 });
}
