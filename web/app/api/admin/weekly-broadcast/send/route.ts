import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";

async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { supabase, user: null, error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) };
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return { supabase, user: null, error: NextResponse.json({ error: "Forbidden" }, { status: 403 }) };
  return { supabase, user, error: null };
}

function getServiceSupabase() {
  const url = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceKey) {
    throw new Error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured");
  }
  return createServiceClient(url, serviceKey);
}

const LINE_MULTICAST_URL = "https://api.line.me/v2/bot/message/multicast";

async function lineMulticast(userIds: string[], message: string, token: string): Promise<boolean> {
  for (let i = 0; i < userIds.length; i += 500) {
    const batch = userIds.slice(i, i + 500);
    const res = await fetch(LINE_MULTICAST_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ to: batch, messages: [{ type: "text", text: message }] }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      console.error("LINE multicast error", res.status, err);
      return false;
    }
  }
  return true;
}

// POST /api/admin/weekly-broadcast/send
// Body: { id: string }
export async function POST(request: Request) {
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;
  const serviceSupabase = getServiceSupabase();

  const body = await request.json();
  const { id } = body;
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  const token = process.env.LINE_CHANNEL_ACCESS_TOKEN ?? process.env.LINE_CHANNEL_TOKEN;
  if (!token) return NextResponse.json({ error: "LINE_CHANNEL_ACCESS_TOKEN not configured" }, { status: 500 });

  // Fetch announcement
  const { data: ann, error: fetchErr } = await supabase
    .from("announcements")
    .select("id, slug, title_zh, body_zh, body_ja, body_en, published_at")
    .eq("id", id)
    .single();

  if (fetchErr || !ann) return NextResponse.json({ error: "Announcement not found" }, { status: 404 });
  if (ann.published_at) return NextResponse.json({ error: "Already published" }, { status: 409 });

  // Fetch subscribers by language
  const { data: subs, error: subsError } = await serviceSupabase
    .from("line_subscribers")
    .select("line_user_id, language_preference")
    .eq("status", "active");

  if (subsError) {
    return NextResponse.json(
      { error: `Failed to load LINE subscribers: ${subsError.message}` },
      { status: 500 },
    );
  }

  const byLang: Record<string, string[]> = { zh: [], ja: [], en: [] };
  for (const s of subs ?? []) {
    const lang = (s.language_preference as string) ?? "zh";
    if (lang in byLang) byLang[lang].push(s.line_user_id as string);
  }

  let sentTotal = 0;
  const failedLangs: string[] = [];
  for (const lang of ["zh", "ja", "en"] as const) {
    const userIds = byLang[lang];
    if (!userIds.length) continue;
    const msg = (ann[`body_${lang}` as keyof typeof ann] as string | null) ?? ann.body_zh;
    if (!msg) continue;
    const ok = await lineMulticast(userIds, msg, token);
    if (ok) {
      sentTotal += userIds.length;
    } else {
      failedLangs.push(lang);
    }
  }

  const totalSubscribers = byLang.zh.length + byLang.ja.length + byLang.en.length;
  if (failedLangs.length > 0) {
    return NextResponse.json(
      {
        error: `LINE multicast failed for languages: ${failedLangs.join(", ")}`,
        sent_to: sentTotal,
        subscriber_count: {
          zh: byLang.zh.length,
          ja: byLang.ja.length,
          en: byLang.en.length,
          total: totalSubscribers,
        },
      },
      { status: 502 },
    );
  }

  if (totalSubscribers > 0 && sentTotal === 0) {
    return NextResponse.json(
      {
        error: "No LINE messages were delivered. Announcement remains draft.",
        sent_to: sentTotal,
        subscriber_count: {
          zh: byLang.zh.length,
          ja: byLang.ja.length,
          en: byLang.en.length,
          total: totalSubscribers,
        },
      },
      { status: 502 },
    );
  }

  // Mark as published
  await supabase.from("announcements").update({
    published_at: new Date().toISOString(),
    social_status: { line: { status: "published", published_at: new Date().toISOString() } },
  }).eq("id", id);

  return NextResponse.json({
    sent_to: sentTotal,
    subscriber_count: {
      zh: byLang.zh.length,
      ja: byLang.ja.length,
      en: byLang.en.length,
      total: byLang.zh.length + byLang.ja.length + byLang.en.length,
    },
  });
}
