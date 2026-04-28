import { createClient } from "@supabase/supabase-js";
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

// ---------------------------------------------------------------------------
// 分類對照表（數字 / ZH / JA / EN → category key）
// ---------------------------------------------------------------------------
const CATEGORY_LABELS: Record<string, string> = {
  "1": "movie",       "電影": "movie",       "映画": "movie",       "movie": "movie",
  "2": "performing_arts", "音樂": "performing_arts", "表演": "performing_arts",
  "音楽": "performing_arts", "performing_arts": "performing_arts",
  "3": "senses",      "五感": "senses",       "台灣五感": "senses",  "senses": "senses",
  "4": "retail",      "品牌": "retail",       "消費": "retail",      "retail": "retail",
  "5": "lifestyle_food", "生活": "lifestyle_food", "飲食": "lifestyle_food",
  "ライフスタイル": "lifestyle_food", "lifestyle": "lifestyle_food",
  "6": "art",         "藝術": "art",          "アート": "art",       "art": "art",
  "7": "lecture",     "講座": "lecture",      "レクチャー": "lecture", "lecture": "lecture",
  "8": "taiwan_japan", "台日": "taiwan_japan", "台日交流": "taiwan_japan", "交流": "taiwan_japan",
  "9": "books_media", "書": "books_media",    "媒體": "books_media", "本": "books_media",
  "10": "academic",   "學術": "academic",     "学術": "academic",    "academic": "academic",
  "11": "geopolitics","政治": "geopolitics",  "社會": "geopolitics", "geopolitics": "geopolitics",
  "12": "gender",     "性別": "gender",       "ジェンダー": "gender", "gender": "gender",
  "13": "tech",       "科技": "tech",         "テクノロジー": "tech", "tech": "tech",
  "14": "nature",     "自然": "nature",       "nature": "nature",
  "15": "tourism",    "旅遊": "tourism",      "旅行": "tourism",     "tourism": "tourism",
  "16": "workshop",   "工作坊": "workshop",   "ワークショップ": "workshop", "workshop": "workshop",
  "17": "exhibition", "展覽": "exhibition",   "展示": "exhibition",  "exhibition": "exhibition",
  "18": "competition","競賽": "competition",  "競技": "competition", "competition": "competition",
  "19": "indigenous", "原住民": "indigenous", "先住民": "indigenous", "indigenous": "indigenous",
  "20": "history",    "歷史": "history",      "歴史": "history",     "history": "history",
  "21": "urban",      "建築": "urban",        "都市": "urban",       "urban": "urban",
  "22": "business",   "商務": "business",     "ビジネス": "business", "business": "business",
  "23": "report",     "活動紀錄": "report",   "レポート": "report",  "report": "report",
  "24": "literature", "文學": "literature",   "文学": "literature",  "literature": "literature",
  "25": "tv_program", "電視": "tv_program",   "テレビ": "tv_program", "tv": "tv_program",
};

// 語言命令對照
const LANGUAGE_COMMANDS: Record<string, string> = {
  "中文": "zh", "繁中": "zh", "zh": "zh", "中国語": "zh", "台語": "zh",
  "日本語": "ja", "日語": "ja", "ja": "ja", "japanese": "ja",
  "english": "en", "英語": "en", "en": "en",
};

// 語言確認回覆
const LANG_CONFIRM: Record<string, string> = {
  zh: "✅ 已設定推播語言為：繁體中文",
  ja: "✅ 配信言語を日本語に設定しました",
  en: "✅ Broadcast language set to: English",
};

// 分類列表（廣播結尾用）
const CATEGORY_LIST_ZH = `📂 活動分類
1.電影  2.音樂・表演  3.台灣五感  4.品牌消費
5.生活風格  6.藝術  7.講座  8.台日交流
9.書・媒體  10.學術  11.社會・政治  12.性別
13.科技  14.自然  15.旅遊  16.工作坊
17.展覽  18.競賽  19.原住民  20.歷史
21.建築  22.商務  23.活動紀錄  24.文學

💡 輸入編號或分類名稱可客製化推播
切換語言：輸入「日本語」或「English」`;

// ---------------------------------------------------------------------------
// Supabase client（server-side only）
// ---------------------------------------------------------------------------
function getSupabase() {
  const url = process.env.SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  return createClient(url, key);
}

// ---------------------------------------------------------------------------
// Signature verification
// ---------------------------------------------------------------------------
async function verifySignature(body: string, signature: string): Promise<boolean> {
  const secret = process.env.LINE_CHANNEL_SECRET;
  if (!secret) return false;
  const expected = createHmac("sha256", secret).update(body).digest("base64");
  return expected === signature;
}

// ---------------------------------------------------------------------------
// LINE Reply API helper
// ---------------------------------------------------------------------------
async function replyMessage(replyToken: string, messages: object[]): Promise<void> {
  const token = process.env.LINE_CHANNEL_TOKEN;
  if (!token) return;
  await fetch("https://api.line.me/v2/bot/message/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ replyToken, messages }),
  });
}

// ---------------------------------------------------------------------------
// Welcome message（三語 + Quick Reply 語言按鈕）
// ---------------------------------------------------------------------------
function buildWelcomeMessage() {
  return [
    {
      type: "text",
      text: "👋 歡迎訂閱東京台灣雷達！\n東京台湾レーダーへようこそ！\nWelcome to Tokyo Taiwan Radar!\n\n請選擇語言 / 言語を選択 / Choose language：",
      quickReply: {
        items: [
          {
            type: "action",
            action: {
              type: "postback",
              label: "🇹🇼 中文",
              data: "lang:zh",
              displayText: "中文",
            },
          },
          {
            type: "action",
            action: {
              type: "postback",
              label: "🇯🇵 日本語",
              data: "lang:ja",
              displayText: "日本語",
            },
          },
          {
            type: "action",
            action: {
              type: "postback",
              label: "🇺🇸 English",
              data: "lang:en",
              displayText: "English",
            },
          },
        ],
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Parse text: detect language command or category preferences
// Returns: { type: 'lang', value } | { type: 'category', values } | { type: 'unknown' }
// ---------------------------------------------------------------------------
function parseUserInput(text: string): { type: string; value?: string; values?: string[] } {
  const normalized = text.trim().toLowerCase();

  // Language command (highest priority)
  const langKey = LANGUAGE_COMMANDS[text.trim()] ?? LANGUAGE_COMMANDS[normalized];
  if (langKey) return { type: "lang", value: langKey };

  // Category parsing: split by comma or space
  const tokens = text.trim().split(/[,，\s]+/).filter(Boolean);
  const categories: string[] = [];
  for (const token of tokens) {
    const cat = CATEGORY_LABELS[token] ?? CATEGORY_LABELS[token.toLowerCase()];
    if (cat && !categories.includes(cat)) categories.push(cat);
  }
  if (categories.length > 0) return { type: "category", values: categories };

  return { type: "unknown" };
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------
async function handleFollow(lineUserId: string, replyToken: string) {
  const sb = getSupabase();
  await sb.from("line_subscribers").upsert(
    { line_user_id: lineUserId, status: "active", updated_at: new Date().toISOString() },
    { onConflict: "line_user_id" }
  );
  await replyMessage(replyToken, buildWelcomeMessage());
}

async function handleUnfollow(lineUserId: string) {
  const sb = getSupabase();
  await sb
    .from("line_subscribers")
    .update({ status: "blocked", updated_at: new Date().toISOString() })
    .eq("line_user_id", lineUserId);
}

async function handlePostback(lineUserId: string, replyToken: string, data: string) {
  if (data.startsWith("lang:")) {
    const lang = data.slice(5) as "zh" | "en" | "ja";
    if (!["zh", "en", "ja"].includes(lang)) return;
    const sb = getSupabase();
    await sb
      .from("line_subscribers")
      .update({ language_preference: lang, updated_at: new Date().toISOString() })
      .eq("line_user_id", lineUserId);
    await replyMessage(replyToken, [{ type: "text", text: LANG_CONFIRM[lang] }]);
  }
}

async function handleMessage(lineUserId: string, replyToken: string, text: string) {
  const parsed = parseUserInput(text);
  const sb = getSupabase();

  if (parsed.type === "lang" && parsed.value) {
    await sb
      .from("line_subscribers")
      .update({ language_preference: parsed.value, updated_at: new Date().toISOString() })
      .eq("line_user_id", lineUserId);
    await replyMessage(replyToken, [
      { type: "text", text: LANG_CONFIRM[parsed.value] ?? "✅ Language updated" },
    ]);
    return;
  }

  if (parsed.type === "category" && parsed.values) {
    await sb
      .from("line_subscribers")
      .update({
        category_preferences: parsed.values,
        updated_at: new Date().toISOString(),
      })
      .eq("line_user_id", lineUserId);
    const names = parsed.values.join("、");
    await replyMessage(replyToken, [
      {
        type: "text",
        text: `✅ 已儲存您的偏好分類：${names}\n\n每週推播將包含這些分類的精選活動。\n\n${CATEGORY_LIST_ZH}`,
      },
    ]);
    return;
  }

  // Unknown input: show category list
  await replyMessage(replyToken, [{ type: "text", text: CATEGORY_LIST_ZH }]);
}

// ---------------------------------------------------------------------------
// Main POST handler
// ---------------------------------------------------------------------------
export async function POST(req: NextRequest): Promise<NextResponse> {
  const body = await req.text();
  const signature = req.headers.get("x-line-signature") ?? "";

  const valid = await verifySignature(body, signature);
  if (!valid) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
  }

  let payload: {
    events?: Array<{
      type: string;
      source?: { userId?: string };
      replyToken?: string;
      message?: { type: string; text?: string };
      postback?: { data?: string };
    }>;
  };
  try {
    payload = JSON.parse(body);
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  for (const event of payload.events ?? []) {
    const lineUserId = event.source?.userId;
    if (!lineUserId) continue;
    const replyToken = event.replyToken ?? "";

    try {
      if (event.type === "follow") {
        await handleFollow(lineUserId, replyToken);
      } else if (event.type === "unfollow") {
        await handleUnfollow(lineUserId);
      } else if (event.type === "postback") {
        await handlePostback(lineUserId, replyToken, event.postback?.data ?? "");
      } else if (event.type === "message" && event.message?.type === "text") {
        await handleMessage(lineUserId, replyToken, event.message.text ?? "");
      }
    } catch (err) {
      console.error(`[line-webhook] Error handling event type=${event.type}:`, err);
    }
  }

  return NextResponse.json({ ok: true });
}
