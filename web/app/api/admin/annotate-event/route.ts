import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

export const maxDuration = 60;

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36";

// ── Web search helpers ────────────────────────────────────────────────────

async function ddgSearch(query: string): Promise<string[]> {
  try {
    const body = new URLSearchParams({ q: query, kl: "jp-jp" });
    const res = await fetch("https://html.duckduckgo.com/html/", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": UA,
        "Accept-Language": "ja,en;q=0.9",
        Accept: "text/html",
      },
      body: body.toString(),
      signal: AbortSignal.timeout(10000),
    });
    const html = await res.text();
    const urls: string[] = [];
    const seen = new Set<string>();
    // Match both /l/?uddg= redirect form and any direct https URL in result links
    for (const m of html.matchAll(/(?:uddg=|href=")(https?%3A[^"&]+|https?:\/\/[^"\s<>]+)/g)) {
      let u = m[1];
      try { u = decodeURIComponent(u); } catch { /* skip */ }
      // Filter out DDG infrastructure / static asset URLs
      if (!u.startsWith("http")) continue;
      if (u.includes("duckduckgo.com")) continue;
      if (/\.(css|js|ico|png|svg|woff)/.test(u)) continue;
      if (seen.has(u)) continue;
      seen.add(u);
      urls.push(u);
      if (urls.length >= 5) break;
    }
    return urls;
  } catch {
    return [];
  }
}

async function fetchPageText(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": UA, "Accept-Language": "ja,en;q=0.9", Accept: "text/html" },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return "";
    const html = await res.text();
    const text = html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return text.slice(0, 8000);
  } catch {
    return "";
  }
}

function scorePage(text: string, nameJa: string, locationName: string): number {
  let score = 0;
  const words = nameJa.split(/[\s　]+/).filter((w) => w.length >= 2);
  for (const w of words) if (text.includes(w)) score += 2;
  if (locationName && text.includes(locationName)) score += 3;
  for (const kw of ["開催", "会場", "主催", "チケット", "入場", "日時"])
    if (text.includes(kw)) score += 1;
  return score;
}

async function enrichEvent(
  nameJa: string,
  locationName: string,
  startDate: string
): Promise<{ url: string; text: string } | null> {
  const year = (startDate || "").slice(0, 4);
  const queries: string[] = [];
  if (locationName) queries.push(`"${nameJa}" ${year} ${locationName}`);
  queries.push(`"${nameJa}" ${year} 公式`);
  queries.push(`${nameJa} ${year}`);

  const seen = new Set<string>();
  const candidates: string[] = [];
  for (const q of queries) {
    for (const u of await ddgSearch(q)) {
      if (!seen.has(u)) { seen.add(u); candidates.push(u); }
    }
    if (candidates.length >= 5) break;
  }

  let bestUrl = "", bestText = "", bestScore = -1;
  for (const url of candidates.slice(0, 5)) {
    const text = await fetchPageText(url);
    if (!text) continue;
    const score = scorePage(text, nameJa, locationName);
    if (score > bestScore) { bestScore = score; bestUrl = url; bestText = text; }
  }
  return bestScore >= 2 ? { url: bestUrl, text: bestText } : null;
}

// ── Main handler ──────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  // 1. Admin auth check (anon client for session)
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin")
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const { eventId } = (await req.json()) as { eventId: string };
  if (!eventId) return NextResponse.json({ error: "eventId required" }, { status: 400 });

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey)
    return NextResponse.json({ error: "OPENAI_API_KEY not configured" }, { status: 500 });

  // 2. Read event via service role (may be is_active=false)
  const adminClient = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  const { data: event, error: fetchErr } = await adminClient
    .from("events")
    .select(
      "name_ja,name_zh,name_en,description_ja,location_name,location_address,organizer,performer,price_info,business_hours,category,event_form,primary_language,has_japanese_support,has_chinese_support,has_english_support,is_paid,start_date,source_url,official_url"
    )
    .eq("id", eventId)
    .single();

  if (fetchErr || !event) {
    return NextResponse.json({ error: "Event not found" }, { status: 404 });
  }

  // 3. Web search enrichment (skip if already has source_url)
  let webText = "";
  let foundUrl = "";
  const returnedFields: Record<string, unknown> = {};

  if (!event.source_url && event.name_ja) {
    const enriched = await enrichEvent(
      event.name_ja,
      event.location_name || "",
      (event.start_date || "").toString()
    );
    if (enriched) {
      foundUrl = enriched.url;
      webText = enriched.text;
      returnedFields.source_url = foundUrl;
      returnedFields.official_url = foundUrl;
      // Save raw_description immediately (annotation may time-out)
      await adminClient
        .from("events")
        .update({ source_url: foundUrl, official_url: foundUrl, raw_description: webText })
        .eq("id", eventId);
    }
  }

  // 4. GPT annotation using all available info
  const existingCategory = Array.isArray(event.category) && event.category.length > 0;
  const existingEventForm = Array.isArray(event.event_form) && event.event_form.length > 0;

  const eventInfo = [
    event.name_ja && `活動名（日文）: ${event.name_ja}`,
    event.name_zh && `活動名（中文）: ${event.name_zh}`,
    event.name_en && `活動名（英文）: ${event.name_en}`,
    event.description_ja && `説明: ${String(event.description_ja).slice(0, 400)}`,
    webText && `参考ウェブページ全文（最重要・主催/会場/料金等を抜き出すこと）:\n${webText.slice(0, 4000)}`,
    event.location_name && `現在の場地: ${event.location_name}`,
    event.location_address && `現在の住所: ${event.location_address}`,
    event.organizer && `現在の主催: ${event.organizer}`,
    event.performer && `現在の出演者: ${event.performer}`,
    event.price_info && `現在の料金: ${event.price_info}`,
    event.business_hours && `現在の時間: ${event.business_hours}`,
  ]
    .filter(Boolean)
    .join("\n");

  const payload = {
    model: "gpt-4o-mini",
    max_tokens: 1200,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content: `You annotate Taiwan-related cultural events held in Japan for a multilingual event database.

Given event info AND a fetched web page (if provided), return a JSON with these fields. Extract data from the web page when fields are missing or to enrich existing values.

Classification fields (always required):
- category: array of 1–3 values from: movie | performing_arts | senses | retail | nature | tech | tourism | lifestyle_food | books_media | gender | geopolitics | art | lecture | taiwan_japan | business | academic | competition | report
- event_form: array of 1–2 values from: exhibition | concert | lecture_seminar | film_screening | festival | market | sports | study_abroad | other
- primary_language: "ja" | "zh" | "en" | "mixed"
- has_japanese_support: boolean
- has_chinese_support: boolean
- has_english_support: boolean
- is_paid: boolean (true = admission fee required, false = free)

Extraction fields (omit if not visible in the web page):
- organizer: organizer name in Japanese (e.g. "千代田区立日比谷図書文化館")
- organizer_url: organizer official URL (full https URL)
- location_name: venue name in Japanese
- location_address: full Japanese postal address (with 〒)
- business_hours: opening hours / show times (e.g. "10:00〜20:00")
- performer: main performer or speaker name (single person or group)
- price_info: ticket price text (e.g. "入場無料" or "一般 ¥1,500")
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD

Return ONLY valid JSON. All classification fields required. Omit extraction fields you cannot confidently determine. Do not fabricate data.`,
      },
      { role: "user", content: eventInfo || "（no info provided）" },
    ],
  };

  const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (openaiRes.ok) {
    const openaiData = (await openaiRes.json()) as {
      choices: Array<{ message: { content: string } }>;
    };
    const content = openaiData.choices?.[0]?.message?.content ?? "{}";
    try {
      const annotated = JSON.parse(content) as Record<string, unknown>;
      // Preserve OCR-filled values: only fill extraction fields that are currently empty
      const extractionFields = [
        "organizer", "organizer_url", "location_name", "location_address",
        "business_hours", "performer", "price_info", "start_date", "end_date",
      ];
      for (const [k, v] of Object.entries(annotated)) {
        if (v === null || v === undefined || v === "") continue;
        if (extractionFields.includes(k)) {
          // Only set if event currently has no value
          const cur = (event as Record<string, unknown>)[k];
          if (cur === null || cur === undefined || cur === "") {
            returnedFields[k] = v;
          }
        } else {
          returnedFields[k] = v;
        }
      }
      // Preserve OCR-filled category / event_form
      if (existingCategory) returnedFields.category = event.category;
      if (existingEventForm) returnedFields.event_form = event.event_form;
    } catch { /* GPT parse error — still return web-search results */ }
  }

  // 5. Save annotation to DB
  if (Object.keys(returnedFields).length > 0) {
    await adminClient
      .from("events")
      .update({ ...returnedFields, annotation_status: "annotated" })
      .eq("id", eventId);
  }

  return NextResponse.json({ success: true, foundUrl: foundUrl || null, fields: returnedFields });
}
