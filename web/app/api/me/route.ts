import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ isAdmin: false, user: null });
  }
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  const { data: creatorRow } = await supabase
    .from("creators")
    .select("user_handle")
    .eq("user_id", user.id)
    .maybeSingle();
  return NextResponse.json({
    isAdmin: roleRow?.role === "admin",
    user: {
      id: user.id,
      email: user.email,
      displayName: creatorRow?.user_handle || user.email,
    },
  });
}
