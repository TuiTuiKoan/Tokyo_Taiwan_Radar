import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

export const maxDuration = 60;

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36";

// ── Web search helpers ────────────────────────────────────────────────────

async function braveSearch(query: string): Promise<string[]> {
  const key = process.env.BRAVE_SEARCH_API_KEY;
  if (!key) return [];
  try {
    const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&country=JP&search_lang=jp&count=10`;
    const res = await fetch(url, {
      headers: { "X-Subscription-Token": key, Accept: "application/json" },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { web?: { results?: Array<{ url: string }> } };
    const urls = data.web?.results?.map((r) => r.url).filter(Boolean) ?? [];
    return urls.slice(0, 5);
  } catch {
    return [];
  }
}

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
    for (const m of html.matchAll(/(?:uddg=|href=")(https?%3A[^"&]+|https?:\/\/[^"\s<>]+)/g)) {
      let u = m[1];
      try { u = decodeURIComponent(u); } catch { /* skip */ }
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

async function bingSearch(query: string): Promise<string[]> {
  try {
    const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}&cc=jp&setlang=ja`;
    const res = await fetch(url, {
      headers: { "User-Agent": UA, "Accept-Language": "ja,en;q=0.9", Accept: "text/html" },
      signal: AbortSignal.timeout(10000),
    });
    const html = await res.text();
    const urls: string[] = [];
    const seen = new Set<string>();
    // Bing wraps result links as <a href="https://...">; pull any external link
    for (const m of html.matchAll(/<a[^>]+href="(https?:\/\/[^"]+)"/gi)) {
      const u = m[1];
      if (u.includes("bing.com") || u.includes("microsoft.com") || u.includes("msn.com")) continue;
      if (u.includes("go.microsoft.com")) continue;
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

async function enrichEvent(
  nameJa: string,
  locationName: string,
  startDate: string
): Promise<{ url: string; text: string; debug: { braveCount: number; ddgCount: number; bingCount: number; candidateCount: number; bestScore: number; queries: string[]; topCandidates: Array<{ url: string; score: number }> } }> {
  const year = (startDate || "").slice(0, 4);
  // Strip phrase-search quotes — Brave/DDG often miss when title contains
  // wrapping brackets like 「」『』 or unusual punctuation. Use plain keywords.
  const cleanName = nameJa.replace(/[「」『』《》〝〞"]/g, " ").replace(/\s+/g, " ").trim();
  const queries: string[] = [];
  if (locationName) queries.push(`${cleanName} ${locationName} ${year}`);
  queries.push(`${cleanName} ${year} 公式`);
  queries.push(`${cleanName} ${year}`);

  const seen = new Set<string>();
  const candidates: string[] = [];
  let braveCount = 0;
  let ddgCount = 0;
  let bingCount = 0;

  // 1. Brave Search API (paid, requires BRAVE_SEARCH_API_KEY env var)
  for (const q of queries) {
    const r = await braveSearch(q);
    braveCount += r.length;
    for (const u of r) {
      if (!seen.has(u)) { seen.add(u); candidates.push(u); }
    }
    if (candidates.length >= 5) break;
  }

  // 2. DDG fallback
  if (candidates.length === 0) {
    for (const q of queries) {
      const r = await ddgSearch(q);
      ddgCount += r.length;
      for (const u of r) {
        if (!seen.has(u)) { seen.add(u); candidates.push(u); }
      }
      if (candidates.length >= 5) break;
    }
  }

  // 3. Bing fallback
  if (candidates.length === 0) {
    for (const q of queries) {
      const r = await bingSearch(q);
      bingCount += r.length;
      for (const u of r) {
        if (!seen.has(u)) { seen.add(u); candidates.push(u); }
      }
      if (candidates.length >= 5) break;
    }
  }

  let bestUrl = "", bestText = "", bestScore = -1;
  const candidateScores: Array<{ url: string; score: number }> = [];
  for (const url of candidates.slice(0, 5)) {
    const text = await fetchPageText(url);
    if (!text) { candidateScores.push({ url, score: -2 }); continue; }
    const score = scorePage(text, nameJa, locationName);
    candidateScores.push({ url, score });
    if (score > bestScore) { bestScore = score; bestUrl = url; bestText = text; }
  }

  // Require bestScore >= 3 to count as a real match (covers ≥1 name token + a
  // generic keyword, OR a location_name hit). Below that, the page is too
  // weakly related and risks polluting the event with unrelated info.
  return {
    url: bestScore >= 3 ? bestUrl : "",
    text: bestScore >= 3 ? bestText : "",
    debug: {
      braveCount, ddgCount, bingCount,
      candidateCount: candidates.length,
      bestScore,
      queries,
      topCandidates: candidateScores,
    },
  };
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
      "name_ja,name_zh,name_en,description_ja,location_name,location_address,location_url,organizer,organizer_url,performer,price_info,business_hours,category,event_form,primary_language,has_japanese_support,has_chinese_support,has_english_support,is_paid,start_date,source_url,official_url"
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
  let searchDebug: { braveCount: number; ddgCount: number; bingCount: number; candidateCount: number; bestScore: number; queries: string[]; topCandidates: Array<{ url: string; score: number }> } | null = null;
  let sourceUrlFetchOk: boolean | null = null;

  const needsUrlEnrichment =
    !event.source_url ||
    !event.official_url ||
    !event.organizer_url ||
    !event.location_url;

  if (needsUrlEnrichment && event.name_ja) {
    if (event.source_url) {
      const text = await fetchPageText(event.source_url as string);
      sourceUrlFetchOk = text.length > 0;
      // Verify the existing source_url actually matches the event — a wrong
      // URL persisted from a previous bad search must NOT be reused.
      const score = text ? scorePage(text, event.name_ja as string, (event.location_name as string) || "") : -1;
      if (text && score >= 3) {
        foundUrl = event.source_url as string;
        webText = text;
      }
      // else: fall through to fresh search; do not trust the stored URL
    }
    if (!webText) {
      const enriched = await enrichEvent(
        event.name_ja,
        event.location_name || "",
        (event.start_date || "").toString()
      );
      searchDebug = enriched.debug;
      console.info(
        `[annotate-event] enrich name="${event.name_ja}" loc="${event.location_name}" ` +
        `bestScore=${enriched.debug.bestScore} candidates=${JSON.stringify(enriched.debug.topCandidates)} ` +
        `queries=${JSON.stringify(enriched.debug.queries)}`
      );
      if (enriched.url && enriched.text) {
        foundUrl = enriched.url;
        webText = enriched.text;
      } else {
        console.warn(
          `[annotate-event] no usable page for "${event.name_ja}" location=${event.location_name} year=${(event.start_date || "").slice(0, 4)} debug=${JSON.stringify(enriched.debug)}`
        );
      }
    }
    if (webText) {
      const persist: Record<string, unknown> = { raw_description: webText };
      let originUrl = "";
      try { originUrl = new URL(foundUrl).origin; } catch { /* skip */ }

      // If the existing source_url was rejected by the score check (foundUrl
      // came from a fresh search and differs), OVERWRITE it. This is critical
      // when a previous run persisted a wrong URL.
      const sourceUrlIsStale = event.source_url && event.source_url !== foundUrl;

      if (!event.source_url || sourceUrlIsStale) {
        persist.source_url = foundUrl;
        returnedFields.source_url = foundUrl;
      }
      if (!event.official_url || sourceUrlIsStale) {
        persist.official_url = foundUrl;
        returnedFields.official_url = foundUrl;
      }
      if (!event.organizer_url && originUrl) {
        persist.organizer_url = originUrl;
        returnedFields.organizer_url = originUrl;
      }
      if (!event.location_url && originUrl) {
        persist.location_url = originUrl;
        returnedFields.location_url = originUrl;
      }
      await adminClient.from("events").update(persist).eq("id", eventId);
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
    max_tokens: 2500,
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

Name translations (always required when name_ja is provided):
- name_ja: event name in Japanese (use existing if provided, else extract)
- name_zh: event name in Traditional Chinese (繁體中文)
- name_en: event name in English

Description text (always required — generate based on web page or existing info):
- description_ja: 2–4 sentence description in natural Japanese (丁寧体)
- description_zh: 2–4 sentence description in Traditional Chinese (繁體中文)
- description_en: 2–4 sentence description in natural English

Extraction fields (omit if not visible in the web page):
- organizer: organizer name in Japanese (e.g. "千代田区立日比谷図書文化館")
- organizer_url: organizer official URL (full https URL, the org's homepage). LOOK CAREFULLY in the web page header/footer/contact section. If the page is hosted on the organizer's own domain (e.g. www.library.chiyoda.tokyo.jp), the homepage URL of that domain IS the organizer_url.
- location_name: venue name in Japanese
- location_address: full Japanese postal address (with 〒)
- location_url: venue official website URL (full https URL, the venue's homepage). Same heuristic as organizer_url — if the venue runs the page, the site root is the location_url.
- business_hours: opening hours / show times (e.g. "10:00〜20:00")
- performer: main performer or speaker name (single person or group)
- price_info: ticket price text (e.g. "入場無料" or "一般 ¥1,500")
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD

Rules:
- For Chinese, use Traditional Chinese characters only (繁體字). Never simplified.
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
    signal: AbortSignal.timeout(25000), // 25s — prevents OpenAI slow response from exceeding Vercel maxDuration
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
        "organizer", "organizer_url", "location_name", "location_address", "location_url",
        "business_hours", "performer", "price_info", "start_date", "end_date",
        "name_ja", "name_zh", "name_en",
      ];
      // Description and translation fields always overwrite (annotator-generated)
      const alwaysOverwriteFields = [
        "description_ja", "description_zh", "description_en",
      ];
      for (const [k, v] of Object.entries(annotated)) {
        if (v === null || v === undefined || v === "") continue;
        if (alwaysOverwriteFields.includes(k)) {
          returnedFields[k] = v;
        } else if (extractionFields.includes(k)) {
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
