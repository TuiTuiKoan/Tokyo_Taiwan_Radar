import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { CATEGORIES, EVENT_FORMS } from "@/lib/types";
import {
  sanitizeCategoryValues,
  sanitizeEventFormValues,
  sanitizePrimaryLanguageValue,
} from "@/lib/eventFieldMerge";

export async function POST(req: NextRequest) {
  // 1. Authenticate user
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  // 1b. Check if banned
  const { data: roleRow } = await serviceClient
    .from("user_roles")
    .select("publish_banned_until")
    .eq("user_id", user.id)
    .maybeSingle();

  if (roleRow?.publish_banned_until) {
    const banDate = new Date(roleRow.publish_banned_until);
    if (banDate > new Date()) {
      return NextResponse.json(
        { error: "publishBanned", raw: banDate.toISOString() },
        { status: 403 }
      );
    }
  }

  // 2. Parse body
  const { image } = (await req.json()) as { image: string };
  if (!image) return NextResponse.json({ error: "image required" }, { status: 400 });

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey)
    return NextResponse.json({ error: "OPENAI_API_KEY not configured" }, { status: 500 });

  // 3. Call GPT-4o Vision via REST API
  const payload = {
    model: "gpt-4o",
    max_tokens: 2500,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content: `You are extracting event information from a promotional poster image for a Japan-Taiwan cultural event database.

Extract all visible information and return a JSON object with these fields (omit fields you cannot confidently read):
- name_ja: FULL event name in Japanese, including main title AND any subtitle/series name. If the poster shows a hierarchy (large title + smaller subtitle on next line), join them with "――" or "ー" preserving both. Do NOT truncate. Example: "国立公文書館特別展　台湾と日本　歴史の中で交差する物語"
- name_zh: full event name in Traditional Chinese
- name_en: full event name in English
- start_date: YYYY-MM-DD format
- end_date: YYYY-MM-DD format (if range shown)
- location_name: venue name (Japanese)
- location_address: full address in Japanese (include 〒 if visible)
- location_url: venue official website URL (if printed on poster)
- business_hours: show times or opening hours (e.g. "14:00〜16:00" or "10:00-18:00")
- performer: main performer/artist/speaker name (single person or group, Japanese). Look for cue words like "出演", "登壇", "講師", "演奏", "ゲスト", "司会" and face-name captions near portraits/headshots.
- organizer: primary organizer name (Japanese, single string). Look for "主催" label.
- co_organizers: array of co-host / supporting organizations (Japanese). Look for "共催", "協力", "後援" labels — typically printed in small text in the credit block at the bottom of the poster. Return [] if none visible.
- sponsors: array of sponsor names (Japanese). Look for "協賛", "助成", "Sponsored by" labels in the credit block. Return [] if none visible.
- organizer_url: organizer website URL (if printed on poster)
- source_url: event official page URL (if printed on poster)
- price_info: ticket price info as string (e.g. "一般 ¥1,500 / 学生 ¥1,000" or "入場無料")
- is_paid: true if admission fee shown, false if free, omit if unclear
- primary_language: "ja" | "zh" | "en" | "mixed"
- has_japanese_support: true/false
- has_chinese_support: true/false
- has_english_support: true/false
- event_form: array using only these values: ${EVENT_FORMS.join(" | ")}
- category: array using only these values: ${CATEGORIES.join(" | ")}

Title rules:
- Read the poster top to bottom and capture the COMPLETE title (main title + sub-title + series name).
- Do not stop at the first line break. Subtitles printed below or beside the main title are part of name_ja.
- If multiple language versions of the title appear, populate name_ja / name_zh / name_en accordingly. If a language version is missing on the poster, omit that field (annotator will translate later).

URL rules:
- Only extract URLs that are LEGIBLY printed on the poster (full https:// URL or qr-code annotation).
- Do not invent URLs from organization names. If unsure, omit.

Chinese rules:
- Use Traditional Chinese characters only (繁體字), never Simplified.

Glossary:
- Translate "記念講演会" as "紀念演講" in Traditional Chinese.
- Translate "記念講演会" as "Commemorative Lecture" in English.

Return ONLY the JSON. Omit any field you cannot confidently read. Do not guess or fabricate data.`,
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
            text: "Extract ALL event information from this promotional poster. Be thorough — capture the full title including subtitles, all dates, venue address, organizer, prices, URLs, and ALL co-hosts (共催/協力/後援) and sponsors (協賛) printed in the credit block.",
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

  const sanitizedCategories = sanitizeCategoryValues(fields.category);
  if (sanitizedCategories) fields.category = sanitizedCategories;
  else delete fields.category;

  const sanitizedEventForms = sanitizeEventFormValues(fields.event_form);
  if (sanitizedEventForms) fields.event_form = sanitizedEventForms;
  else delete fields.event_form;

  const sanitizedPrimaryLanguage = sanitizePrimaryLanguageValue(fields.primary_language);
  if (sanitizedPrimaryLanguage) fields.primary_language = sanitizedPrimaryLanguage;
  else if (fields.primary_language !== undefined) {
    delete fields.primary_language;
  }

  if (
    typeof fields.start_date === "string" &&
    fields.start_date.trim() &&
    (typeof fields.end_date !== "string" || !fields.end_date.trim())
  ) {
    fields.end_date = fields.start_date;
  }

  return NextResponse.json({ fields });
}
