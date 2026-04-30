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

// GET /api/announcements/[id]
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: announcement, error } = await supabase
    .from("announcements")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !announcement) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data: links } = await supabase
    .from("announcement_events")
    .select("event_id")
    .eq("announcement_id", id);

  return NextResponse.json({ ...announcement, linked_events: links?.map((l) => l.event_id) ?? [] });
}

// PUT /api/announcements/[id] — admin: update
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;

  const body = await request.json();
  const { linked_events, ...fields } = body;

  const { data: announcement, error } = await supabase
    .from("announcements")
    .update(fields)
    .eq("id", id)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Sync junction rows
  if (Array.isArray(linked_events)) {
    await supabase.from("announcement_events").delete().eq("announcement_id", id);
    if (linked_events.length > 0) {
      await supabase.from("announcement_events").insert(
        linked_events.map((event_id: string) => ({ announcement_id: id, event_id }))
      );
    }
  }

  return NextResponse.json(announcement);
}

// DELETE /api/announcements/[id] — admin: delete
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;

  const { error } = await supabase.from("announcements").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
