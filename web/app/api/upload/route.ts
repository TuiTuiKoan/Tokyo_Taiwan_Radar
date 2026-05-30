import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/upload
// Body: FormData with field "file"
// Returns: { url: string }
export async function POST(request: Request) {
  try {
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

    const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!serviceKey) return NextResponse.json({ error: "Server misconfiguration: storage key not set" }, { status: 500 });

    const rawExt = file.name.split(".").pop() ?? "jpg";
    const ext = rawExt.replace(/[^a-zA-Z0-9]/g, "").slice(0, 10) || "jpg";
    const objectPath = `covers/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

    // Call Supabase Storage REST API directly — bypasses storage-js SDK
    // multipart/FormData serialisation issues that caused 422 errors in Node.js runtime.
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
    const uploadUrl = `${supabaseUrl}/storage/v1/object/announcements/${objectPath}`;

    const buffer = Buffer.from(await file.arrayBuffer());
    const uploadRes = await fetch(uploadUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${serviceKey}`,
        "Content-Type": file.type,
        "x-upsert": "true",
        apikey: serviceKey,
      },
      body: buffer,
    });

    if (!uploadRes.ok) {
      const errText = await uploadRes.text().catch(() => "unknown");
      return NextResponse.json({ error: `Storage error ${uploadRes.status}: ${errText}` }, { status: 500 });
    }

    const publicUrl = `${supabaseUrl}/storage/v1/object/public/announcements/${objectPath}`;
    return NextResponse.json({ url: publicUrl });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Upload failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
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
