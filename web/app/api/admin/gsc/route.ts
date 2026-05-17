import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { fetchGscStats } from "@/lib/gsc";

export async function GET() {
  // Auth check
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const stats = await fetchGscStats();
  return NextResponse.json(stats);
}
