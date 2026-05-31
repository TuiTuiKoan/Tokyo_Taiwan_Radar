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
const LINE_TEXT_LIMIT = 5000;
const LINE_MESSAGES_PER_REQUEST = 5;

interface MulticastResult {
  ok: boolean;
  status?: number;
  error?: any;
}

function splitLineTextMessage(text: string): string[] {
  if (text.length <= LINE_TEXT_LIMIT) return [text];

  const segments: string[] = [];
  let remaining = text;

  while (remaining.length > LINE_TEXT_LIMIT) {
    // LINE text message max length is 5000 chars; prefer splitting at newlines.
    const newlineIndex = remaining.lastIndexOf("\n", LINE_TEXT_LIMIT - 1);
    const splitIndex = newlineIndex > 0 ? newlineIndex + 1 : LINE_TEXT_LIMIT;
    segments.push(remaining.slice(0, splitIndex));
    remaining = remaining.slice(splitIndex);
  }

  if (remaining.length > 0) segments.push(remaining);
  return segments;
}

async function lineMulticast(
  userIds: string[],
  messages: string | string[],
  token: string
): Promise<MulticastResult> {
  const msgsArray = Array.isArray(messages) ? messages : [messages];
  const lineMessages = msgsArray
    .flatMap(splitLineTextMessage)
    .map(m => ({ type: "text", text: m }));

  for (let i = 0; i < userIds.length; i += 500) {
    const batch = userIds.slice(i, i + 500);
    for (let j = 0; j < lineMessages.length; j += LINE_MESSAGES_PER_REQUEST) {
      const messageBatch = lineMessages.slice(j, j + LINE_MESSAGES_PER_REQUEST);
      try {
        const res = await fetch(LINE_MULTICAST_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ to: batch, messages: messageBatch }),
          signal: AbortSignal.timeout(10000),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          console.error("LINE multicast error", res.status, err);
          return {
            ok: false,
            status: res.status,
            error: err,
          };
        }
      } catch (error: any) {
        console.error("LINE multicast fetch error", error);
        return {
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        };
      }
    }
  }
  return { ok: true };
}

// POST /api/admin/weekly-broadcast/send
// Body: { id: string, adminOnly?: boolean }
export async function POST(request: Request) {
  const { supabase, error: authError } = await requireAdmin();
  if (authError) return authError;
  const serviceSupabase = getServiceSupabase();

  const body = await request.json();
  const { id, adminOnly = false } = body;
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
  if (ann.published_at && !adminOnly) return NextResponse.json({ error: "Already published" }, { status: 409 });

  // Admin-only sandbox path
  if (adminOnly) {
    const rawIds = process.env.ADMIN_LINE_USER_IDS || "";
    const adminIds = rawIds.split(",").map(uid => uid.trim()).filter(Boolean);
    if (adminIds.length === 0) {
      return NextResponse.json({ error: "ADMIN_LINE_USER_IDS not configured" }, { status: 400 });
    }

    const testMessages: string[] = [];
    if (ann.body_zh) testMessages.push(ann.body_zh);
    if (ann.body_ja) testMessages.push(ann.body_ja);
    if (ann.body_en) testMessages.push(ann.body_en);

    if (testMessages.length === 0) {
      return NextResponse.json({ error: "No content available in weekly broadcast" }, { status: 400 });
    }

    const multicastRes = await lineMulticast(adminIds, testMessages, token);
    if (!multicastRes.ok) {
      return NextResponse.json(
        {
          error: `LINE multicast failed for admin-only: ${multicastRes.error ? JSON.stringify(multicastRes.error) : "Unknown error"}`,
          status: multicastRes.status,
          mode: "admin_only"
        },
        { status: 502 }
      );
    }

    return NextResponse.json({
      mode: "admin_only",
      status: "success",
      sent_to: adminIds.length,
      admin_count: adminIds.length,
    });
  }

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
  const failedLangs: Array<{ lang: string; error?: any; status?: number }> = [];
  for (const lang of ["zh", "ja", "en"] as const) {
    const userIds = byLang[lang];
    if (!userIds.length) continue;
    const msg = (ann[`body_${lang}` as keyof typeof ann] as string | null) ?? ann.body_zh;
    if (!msg) continue;
    const multicastRes = await lineMulticast(userIds, msg, token);
    if (multicastRes.ok) {
      sentTotal += userIds.length;
    } else {
      failedLangs.push({
        lang,
        status: multicastRes.status,
        error: multicastRes.error,
      });
    }
  }

  const totalSubscribers = byLang.zh.length + byLang.ja.length + byLang.en.length;
  if (failedLangs.length > 0) {
    return NextResponse.json(
      {
        error: `LINE multicast failed for languages: ${failedLangs.map(f => f.lang).join(", ")}`,
        failed_languages: failedLangs,
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
    mode: "broadcast",
    sent_to: sentTotal,
    subscriber_count: {
      zh: byLang.zh.length,
      ja: byLang.ja.length,
      en: byLang.en.length,
      total: totalSubscribers,
    },
  });
}
