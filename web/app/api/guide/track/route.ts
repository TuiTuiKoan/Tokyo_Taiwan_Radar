// POST /api/guide/track — beacon endpoint for the static guide tools under /YYYYMM/*.
// spec guide-analytics. Writes guide_events with the service role after validating
// the batch; never surfaces errors to the guide (it ignores the response).

import { createClient as createServiceClient } from "@supabase/supabase-js";
import { createClient as createSessionClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { isSameOrigin, MAX_BODY_BYTES, parseBatch } from "@/lib/analytics/guideTrack";

export const dynamic = "force-dynamic";

function noContent() {
  return new NextResponse(null, { status: 204 });
}

async function isAdminVisitor(req: Request): Promise<boolean> {
  // Only visitors with a Supabase auth cookie can be admins; skip the lookup otherwise.
  const cookie = req.headers.get("cookie") ?? "";
  if (!/(^|;\s*)sb-[^=]*-auth-token/.test(cookie)) return false;
  try {
    const supabase = await createSessionClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return false;
    const { data: roleRow } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .single();
    return roleRow?.role === "admin";
  } catch {
    return false;
  }
}

export async function POST(req: Request) {
  if (!isSameOrigin(req.headers.get("origin"), req.headers.get("sec-fetch-site"), req.headers.get("host"))) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const declared = Number(req.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) return NextResponse.json({ error: "too_large" }, { status: 413 });

  const raw = await req.text();
  const parsed = parseBatch(raw, {
    userAgent: req.headers.get("user-agent"),
    country: req.headers.get("x-vercel-ip-country"),
    region: req.headers.get("x-vercel-ip-country-region"),
  });
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: parsed.status });
  if (parsed.rows.length === 0) return noContent();

  // Local dev has no Vercel geo headers and would pollute production data.
  if (process.env.NODE_ENV === "development") return noContent();
  if (await isAdminVisitor(req)) return noContent();

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceKey) return NextResponse.json({ error: "not_configured" }, { status: 500 });

  const admin = createServiceClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { error } = await admin.from("guide_events").insert(parsed.rows);
  if (error) {
    console.error("guide_events insert failed:", error.code, error.message);
    return NextResponse.json({ error: "insert_failed" }, { status: 500 });
  }
  return noContent();
}
