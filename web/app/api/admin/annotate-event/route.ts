import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

export const maxDuration = 60;

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
      "name_ja,name_zh,name_en,description_ja,location_name,location_address,organizer,performer,price_info,business_hours,category,event_form,primary_language,has_japanese_support,has_chinese_support,has_english_support,is_paid"
    )
    .eq("id", eventId)
    .single();

  if (fetchErr || !event) {
    return NextResponse.json({ error: "Event not found" }, { status: 404 });
  }

  // 3. Build annotation prompt from existing fields
  const eventInfo = [
    event.name_ja && `活動名（日文）: ${event.name_ja}`,
    event.name_zh && `活動名（中文）: ${event.name_zh}`,
    event.name_en && `活動名（英文）: ${event.name_en}`,
    event.description_ja && `説明: ${String(event.description_ja).slice(0, 600)}`,
    event.location_name && `場地: ${event.location_name}`,
    event.location_address && `住所: ${event.location_address}`,
    event.organizer && `主催: ${event.organizer}`,
    event.performer && `出演者: ${event.performer}`,
    event.price_info && `料金: ${event.price_info}`,
    event.business_hours && `時間: ${event.business_hours}`,
  ]
    .filter(Boolean)
    .join("\n");

  // Only annotate fields that are empty / need completion
  const existingCategory = Array.isArray(event.category) && event.category.length > 0;
  const existingEventForm = Array.isArray(event.event_form) && event.event_form.length > 0;

  const payload = {
    model: "gpt-4o-mini",
    max_tokens: 400,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content: `You annotate Taiwan-related cultural events held in Japan for a multilingual event database.

Given event info, return a JSON with EXACTLY these fields:
- category: array of 1–3 values from: movie | performing_arts | senses | retail | nature | tech | tourism | lifestyle_food | books_media | gender | geopolitics | art | lecture | taiwan_japan | business | academic | competition | report
- event_form: array of 1–2 values from: exhibition | concert | lecture_seminar | film_screening | festival | market | sports | study_abroad | other
- primary_language: "ja" | "zh" | "en" | "mixed"
- has_japanese_support: boolean
- has_chinese_support: boolean
- has_english_support: boolean
- is_paid: boolean (true = admission fee required, false = free)

Return ONLY valid JSON. All fields required. No extra keys.`,
      },
      {
        role: "user",
        content: eventInfo || "（no info provided）",
      },
    ],
  };

  const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!openaiRes.ok) {
    const errText = await openaiRes.text();
    return NextResponse.json(
      { error: `OpenAI error ${openaiRes.status}`, raw: errText },
      { status: 502 }
    );
  }

  const openaiData = (await openaiRes.json()) as {
    choices: Array<{ message: { content: string } }>;
  };
  const content = openaiData.choices?.[0]?.message?.content ?? "{}";

  let annotated: Record<string, unknown> = {};
  try {
    annotated = JSON.parse(content);
  } catch {
    return NextResponse.json(
      { error: "Failed to parse GPT response", raw: content },
      { status: 500 }
    );
  }

  // Keep existing category / event_form if OCR already set them
  const finalFields: Record<string, unknown> = { ...annotated };
  if (existingCategory) finalFields.category = event.category;
  if (existingEventForm) finalFields.event_form = event.event_form;

  // 4. Update DB
  const { error: updateErr } = await adminClient
    .from("events")
    .update({ ...finalFields, annotation_status: "annotated" })
    .eq("id", eventId);

  if (updateErr) {
    return NextResponse.json({ error: updateErr.message }, { status: 500 });
  }

  return NextResponse.json({ success: true, fields: finalFields });
}
