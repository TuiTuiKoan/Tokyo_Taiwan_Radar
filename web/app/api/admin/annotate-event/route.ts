import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { CATEGORIES, EVENT_FORMS } from "@/lib/types";
import {
  buildDescriptionPromptLines,
  sanitizeCategoryValues,
  sanitizeEventFormValues,
  shouldApplyAnnotatedLocationField,
} from "@/lib/eventFieldMerge";
import { TRANSLATION_LOCK_FIELDS } from "@/lib/eventIntakeClient";
import { PURE_PUBLICATION_EVENT_FORM_GUIDANCE } from "@/lib/intakeGuidance";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";

export const maxDuration = 60;

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36";

// ── Page fetch helpers ────────────────────────────────────────────────────

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
  const cleaned = nameJa.replace(/[「」『』《》〝〞"'()（）\[\]【】]/g, " ");
  const words = cleaned
    .split(/[\s　・…〜~‐\-―ー－—]+/)
    .filter((w) => w.length >= 2)
    .filter((w) => !/^(展示|展覧|企画|特別|研究|室|文化|2026|2025)$/.test(w));
  let nameHits = 0;
  for (const w of words) if (text.includes(w)) { score += 2; nameHits += 1; }

  // Match location by its core building name. e.g.
  // "日比谷図書文化館4階 特別研究室" → also try "日比谷図書文化館" and
  // any token >= 4 chars.
  let locHit = false;
  if (locationName) {
    const locParts = locationName
      .split(/[\s　・]+/)
      .flatMap((p) => [p, p.replace(/\d+階.*$/, "").replace(/[ホール会議室]+$/, "")])
      .filter((p) => p.length >= 4);
    for (const p of locParts) {
      if (text.includes(p)) { locHit = true; break; }
    }
    if (!locHit && text.includes(locationName)) locHit = true;
  }
  if (locHit) score += 5;

  if (nameHits === 0) return -1;
  if (nameHits === 1 && !locHit) return -1;
  for (const kw of ["開催", "会場", "主催", "チケット", "入場", "日時"])
    if (text.includes(kw)) score += 1;
  return score;
}

// ── Main handler ──────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) {
    return NextResponse.json({ error: "maintenance_active" }, { status: 503 });
  }

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

  const { eventId, lockedFields, overwriteableFields, lockedTranslationFields } =
    (await req.json()) as {
      eventId: string;
      lockedFields?: string[];
      overwriteableFields?: string[];
      lockedTranslationFields?: string[];
    };
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
      "name_ja,name_zh,name_en,description_ja,description_zh,description_en,location_name,location_address,location_url,organizer,organizer_url,performer,price_info,business_hours,category,event_form,primary_language,has_japanese_support,has_chinese_support,has_english_support,is_paid,start_date,end_date,source_url,official_url,annotation_status"
    )
    .eq("id", eventId)
    .single();

  if (fetchErr || !event) {
    return NextResponse.json({ error: "Event not found" }, { status: 404 });
  }

  // 3. Web search enrichment
  // Trigger when ANY URL field is missing (source_url / official_url /
  // organizer_url / location_url). OCR may have filled source_url from the
  // poster but left the others empty — we still need to fetch a page so GPT
  // can extract the remaining URLs.
  let webText = "";
  let foundUrl = "";
  const returnedFields: Record<string, unknown> = {};
  const searchDebug = null;
  let sourceUrlFetchOk: boolean | null = null;
  let bestScore = -1;
  const manualLockedFields = Array.isArray(lockedFields)
    ? lockedFields.filter((field): field is string => typeof field === "string")
    : [];
  const overwriteableLocationFields = Array.isArray(overwriteableFields)
    ? overwriteableFields.filter((field): field is string => typeof field === "string")
    : [];
  const lockedTranslationSet = new Set<string>(TRANSLATION_LOCK_FIELDS as readonly string[]);
  const manualLockedTranslations = Array.isArray(lockedTranslationFields)
    ? lockedTranslationFields.filter(
        (field): field is string =>
          typeof field === "string" && lockedTranslationSet.has(field),
      )
    : [];

  const needsUrlEnrichment =
    !event.source_url ||
    !event.official_url ||
    !event.organizer_url ||
    !event.location_url;

  // Wizard URL policy: the user owns every URL field. We never run a web search
  // to guess URLs, and we never write source_url / official_url / organizer_url
  // from search results — doing so produced hallucinated links for manually
  // created events. If the user (or OCR) already provided a source_url, fetch it
  // ONLY to give GPT extra page context for translation/extraction; the URL
  // fields themselves stay exactly as the user left them.
  if (event.source_url && event.name_ja) {
    const text = await fetchPageText(event.source_url as string);
    sourceUrlFetchOk = text.length > 0;
    const score = text
      ? scorePage(text, event.name_ja as string, (event.location_name as string) || "")
      : -1;
    bestScore = score;
    if (text && score >= 3) {
      foundUrl = event.source_url as string;
      webText = text;
      await adminClient
        .from("events")
        .update({ raw_description: webText })
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
    ...buildDescriptionPromptLines({
      ja: event.description_ja,
      zh: event.description_zh,
      en: event.description_en,
    }),
    foundUrl && `参考ウェブページのURL: ${foundUrl}`,
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
    // Full three-language bodies are far larger than the old summary output.
    max_tokens: 8000,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content: `You annotate Taiwan-related cultural events held in Japan for a multilingual event database.

Given event info AND a fetched web page (if provided), return a JSON with these fields. Extract data from the web page when fields are missing or to enrich existing values.

Classification fields (always required):
- category: array of 1–3 values from: ${CATEGORIES.join(" | ")}
- event_form: array of 1–2 values from: ${EVENT_FORMS.join(" | ")}
- primary_language: "ja" | "zh" | "en" | "mixed"
- has_japanese_support: boolean
- has_chinese_support: boolean
- has_english_support: boolean
- is_paid: boolean (true = admission fee required, false = free)

${PURE_PUBLICATION_EVENT_FORM_GUIDANCE}

Name translations (always required — fill ALL three languages):
- name_ja: event name in Japanese
- name_zh: event name in Traditional Chinese (繁體中文)
- name_en: event name in English
- The event name may be provided in ANY one of the three languages. Translate from whichever language is present into the other two. If only the Chinese name is given, produce the Japanese and English names from it; if only Japanese is given, produce Chinese and English. NEVER leave a name field empty when any language version is provided.

Description text (always required — fill ALL three languages):
- description_ja: full Japanese description (丁寧体)
- description_zh: full Traditional Chinese (繁體中文) description
- description_en: full English description
- When a description is provided in ANY language, translate it COMPLETELY into the other two. Translate the whole text from the first line to the last — every paragraph, list item, menu line, schedule row, venue line, price line and organizer line. Never summarise, never condense it into a few sentences, and never stop partway.
- Preserve the source layout: keep line breaks, bullet markers, emoji, headings, dates, times, prices and numbers in the same positions. Keep proper nouns, venue names and personal names accurate.
- NEVER leave a description field empty when any language version is provided. Text that merely repeats the source language is NOT a translation — always output real target-language text.
- If ALL three description languages are empty, generate a coherent, factual 2–4 sentence description in each language from the event name and any available info (dates, venue, organizer, category); the three languages must convey the same content. Never leave the descriptions blank.

Extraction fields (omit if not visible in the web page):
- organizer: organizer name in Japanese (e.g. "千代田区立日比谷図書文化館")
- organizer_url: organizer official URL (full https URL, the org's homepage). LOOK CAREFULLY in the web page header/footer/contact section. If the page is hosted on the organizer's own domain (e.g. www.library.chiyoda.tokyo.jp), the homepage URL of that domain IS the organizer_url.
- location_name: venue name in Japanese
- location_address: full Japanese postal address (with 〒)
- location_url: venue official website URL (full https URL, the venue's OWN homepage — e.g. https://www.bunkamura.co.jp for Bunkamura). IMPORTANT: location_url is a COMPLETELY DIFFERENT URL from organizer_url and from the event page URL. The venue is a physical place; its URL is its own website. Do NOT use the event page URL, Peatix URL, or organizer domain as location_url. Only set this if you can identify a URL that specifically belongs to the venue building/facility itself. If unsure, omit it.
- business_hours: opening hours / show times (e.g. "10:00〜20:00")
- performer: main performer or speaker name (single person or group)
- price_info: ticket price text (e.g. "入場無料" or "一般 ¥1,500")
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD

Rules:
- For Chinese, use Traditional Chinese characters only (繁體字). Never simplified.
- Use "history" when a featured author, artist, creator, or performer is explicitly Taiwan-born, 台湾出身, 台湾生まれ, or born in/from a Taiwan city. Do not use history for education or work experience in Taiwan alone.
- If no 主催 label appears, organizer may be the small venue/shop/gallery/museum public name only when the web page is clearly hosted by that venue. Do not use generic rental halls, universities, convention centers, aggregator platforms, or source names as organizer.
- Glossary: translate 記念講演会 as 紀念演講 in Traditional Chinese.
- Glossary: translate 記念講演会 as Commemorative Lecture in English.
- Do not fabricate. If the web page does not mention a field, omit it.
- Descriptions should be factual and event-focused. No marketing fluff.
- Return ONLY valid JSON.`,
      },
      { role: "user", content: eventInfo || "（no info provided）" },
    ],
  };

  const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(40000), // 40s — full-body translation is slower than the old summary; page fetch (10s) + this stays under maxDuration 60
  });

  if (!openaiRes.ok) {
    let detail = "";
    try { detail = (await openaiRes.text()).slice(0, 300); } catch { /* ignore */ }
    console.error("[annotate-event] OpenAI error:", openaiRes.status, detail);
    return NextResponse.json(
      { error: "annotateAiFailed", detail: `OpenAI ${openaiRes.status}${detail ? `: ${detail}` : ""}` },
      { status: 502 }
    );
  }

  {
    const openaiData = (await openaiRes.json()) as {
      choices: Array<{ message: { content: string } }>;
    };
    const content = openaiData.choices?.[0]?.message?.content ?? "{}";
    try {
      const annotated = JSON.parse(content) as Record<string, unknown>;
      const extractionFields = [
        "organizer", "organizer_url", "location_name", "location_address", "location_url",
        "business_hours", "performer", "price_info", "start_date", "end_date",
      ];
      const alwaysOverwriteFields = [
        "name_ja", "name_zh", "name_en",
        "description_ja", "description_zh", "description_en",
      ];
      for (const [k, v] of Object.entries(annotated)) {
        if (v === null || v === undefined || v === "") continue;
        if (alwaysOverwriteFields.includes(k)) {
          returnedFields[k] = v;
        } else if (extractionFields.includes(k)) {
          const cur = (event as Record<string, unknown>)[k];
          if (k === "location_name" || k === "location_address") {
            if (shouldApplyAnnotatedLocationField(k, cur, v, {
              bestScore,
              lockedFields: manualLockedFields,
              overwriteableFields: overwriteableLocationFields,
              currentLocationName: typeof event.location_name === "string" ? event.location_name : null,
              currentLocationAddress:
                typeof event.location_address === "string" ? event.location_address : null,
            })) {
              returnedFields[k] = v;
            }
            continue;
          }

          if (cur === null || cur === undefined || cur === "") {
            returnedFields[k] = v;
          }
        } else {
          returnedFields[k] = v;
        }
      }
      if (existingCategory) returnedFields.category = event.category;
      if (existingEventForm) returnedFields.event_form = event.event_form;
    } catch (parseErr) {
      console.error("[annotate-event] JSON parse failed:", parseErr);
      if (Object.keys(returnedFields).length === 0) {
        return NextResponse.json(
          { error: "annotateAiFailed", detail: "AI response was not valid JSON" },
          { status: 502 }
        );
      }
    }
  }

  // ── Enum whitelist validation (OWASP A03) ───────────────────────────────
  const sanitizedCategories = sanitizeCategoryValues(returnedFields.category);
  if (sanitizedCategories) returnedFields.category = sanitizedCategories;
  else delete returnedFields.category;

  const sanitizedEventForms = sanitizeEventFormValues(returnedFields.event_form);
  if (sanitizedEventForms) returnedFields.event_form = sanitizedEventForms;
  else delete returnedFields.event_form;

  // primary_language and the on-site language-support flags are user-selected in
  // the wizard (開催言語 + 活動現場語言対応). The user explicitly chose them on
  // step 1, so annotation must never override them — strip any value GPT returned
  // so the client keeps the user's choices.
  delete returnedFields.primary_language;
  delete returnedFields.has_japanese_support;
  delete returnedFields.has_chinese_support;
  delete returnedFields.has_english_support;

  const resolvedStartDate =
    typeof returnedFields.start_date === "string" && returnedFields.start_date.trim()
      ? returnedFields.start_date
      : typeof event.start_date === "string" && event.start_date.trim()
        ? event.start_date
        : null;

  if (
    resolvedStartDate &&
    (typeof returnedFields.end_date !== "string" || !returnedFields.end_date.trim()) &&
    (typeof event.end_date !== "string" || !event.end_date.trim())
  ) {
    returnedFields.end_date = resolvedStartDate;
  }

  // Honor user-confirmed translations: never overwrite locked name/description fields.
  for (const field of manualLockedTranslations) {
    delete returnedFields[field];
  }

  // Wizard URL policy (continued): without fetched page context GPT has no
  // factual basis for any URL, so strip fabricated URL fields and keep the
  // user's explicit (often empty) URL choices intact.
  if (!webText) {
    for (const urlField of ["source_url", "official_url", "organizer_url", "location_url"]) {
      delete returnedFields[urlField];
    }
  }

  // 5. Save annotation to DB
  if (Object.keys(returnedFields).length > 0) {
    const nextAnnotationStatus = event.annotation_status === "reviewed" ? "reviewed" : "annotated";
    const { error: updateErr } = await adminClient
      .from("events")
      .update({ ...returnedFields, annotation_status: nextAnnotationStatus })
      .eq("id", eventId);
    if (updateErr) {
      console.error("[annotate-event] DB update failed:", updateErr);
      return NextResponse.json(
        { error: "annotateSaveFailed", detail: updateErr.message },
        { status: 500 }
      );
    }
    for (const locale of ["ja", "zh", "en"] as const) {
      revalidatePath(`/${locale}/events/${eventId}`);
    }
  }

  return NextResponse.json({
    success: true,
    foundUrl: foundUrl || null,
    fields: returnedFields,
    searchDebug,
    webTextLength: webText.length,
    needsUrlEnrichment,
    sourceUrlFetchOk,
    eventUrls: {
      source_url: event.source_url || null,
      official_url: event.official_url || null,
      organizer_url: event.organizer_url || null,
      location_url: event.location_url || null,
    },
  });
}
