import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(req: NextRequest) {
  // 1. Admin auth check
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

  // 2. Parse body
  const { image } = (await req.json()) as { image: string };
  if (!image) return NextResponse.json({ error: "image required" }, { status: 400 });

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey)
    return NextResponse.json({ error: "OPENAI_API_KEY not configured" }, { status: 500 });

  // 3. Call GPT-4o Vision via REST API
  const payload = {
    model: "gpt-4o",
    max_tokens: 1500,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content: `You are extracting event information from a promotional poster image for a Japan-Taiwan cultural event database.

Extract all visible information and return a JSON object with these fields (omit fields you cannot confidently read):
- name_ja: event name in Japanese
- name_zh: event name in Traditional Chinese
- name_en: event name in English
- start_date: YYYY-MM-DD format
- end_date: YYYY-MM-DD format (if range shown)
- location_name: venue name (Japanese)
- location_address: full address in Japanese
- business_hours: show times or opening hours (e.g. "14:00〜16:00" or "10:00-18:00")
- performer: main performer/artist name (single person or group, Japanese)
- organizer: organizer name (Japanese)
- organizer_url: organizer website URL if visible
- source_url: event official URL if visible
- price_info: ticket price info as string (e.g. "一般 ¥1,500 / 学生 ¥1,000")
- is_paid: true if admission fee shown, false if free, omit if unclear
- primary_language: "ja" | "zh" | "en" | "mixed"
- has_japanese_support: true/false
- has_chinese_support: true/false
- has_english_support: true/false
- event_form: array using only these values: exhibition | screening | lecture | performance | market | workshop | conference | networking | screening_with_talk | tour | competition | tasting | other
- category: array using only these values: movie | performing_arts | senses | retail | nature | tech | tourism | lifestyle_food | books_media | gender | geopolitics | art | lecture | taiwan_japan | business | academic | competition | report

Return ONLY the JSON. Omit any field you are not confident about. Do not guess or fabricate data.`,
      },
      {
        role: "user",
        content: [
          {
            type: "image_url",
            image_url: { url: image, detail: "high" },
          },
          {
            type: "text",
            text: "Extract all event information from this promotional poster.",
          },
        ],
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
      { error: `OpenAI API error ${openaiRes.status}`, raw: errText },
      { status: 502 }
    );
  }

  const openaiData = (await openaiRes.json()) as {
    choices: Array<{ message: { content: string } }>;
  };
  const content = openaiData.choices?.[0]?.message?.content ?? "{}";

  let fields: Record<string, unknown> = {};
  try {
    fields = JSON.parse(content);
  } catch {
    return NextResponse.json(
      { error: "Failed to parse GPT response", raw: content },
      { status: 500 }
    );
  }

  return NextResponse.json({ fields });
}
