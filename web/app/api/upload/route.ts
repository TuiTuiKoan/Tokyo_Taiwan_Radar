import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/upload
// Body: FormData with field "file"
// Returns: { url: string }
export async function POST(request: Request) {
  // Auth check — must be admin
  const supabase = await createServerClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const formData = await request.formData();
  const file = formData.get("file") as File | null;
  if (!file) return NextResponse.json({ error: "No file provided" }, { status: 400 });

  const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
  if (!allowedTypes.includes(file.type)) {
    return NextResponse.json({ error: "Unsupported file type" }, { status: 400 });
  }
  if (file.size > 5 * 1024 * 1024) {
    return NextResponse.json({ error: "File too large (max 5MB)" }, { status: 400 });
  }

  // Use service role to bypass RLS on storage
  const adminClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  const ext = file.name.split(".").pop() ?? "jpg";
  const path = `covers/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

  const buffer = await file.arrayBuffer();
  const { data, error } = await adminClient.storage
    .from("announcements")
    .upload(path, buffer, { contentType: file.type, upsert: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const { data: urlData } = adminClient.storage.from("announcements").getPublicUrl(data.path);
  return NextResponse.json({ url: urlData.publicUrl });
}

// DELETE /api/upload?path=covers/xxx.jpg
// Deletes a file from the announcements storage bucket
export async function DELETE(request: Request) {
  const supabase = await createServerClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const { searchParams } = new URL(request.url);
  const path = searchParams.get("path");
  if (!path) return NextResponse.json({ error: "No path provided" }, { status: 400 });
  // Only allow deleting files under covers/ prefix for safety
  if (!path.startsWith("covers/")) return NextResponse.json({ error: "Invalid path" }, { status: 400 });

  const adminClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
  const { error } = await adminClient.storage.from("announcements").remove([path]);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
