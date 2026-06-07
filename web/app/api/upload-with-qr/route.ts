import { createClient as createServerClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import sharp from "sharp";
import QRCode from "qrcode";

// QR watermark dimensions
const QR_PX = 120;
const MARGIN = 14;
const LABEL_H = 16;
const OVERLAY_W = QR_PX + MARGIN * 2;
const OVERLAY_H = QR_PX + LABEL_H + MARGIN * 3;

const SITE_URL = "https://tokyotaiwanradar.com";
const LABEL_TEXT = "Tokyo Taiwan Radar";

type Corner = "top-left" | "top-right" | "bottom-left" | "bottom-right";

// Use gpt-4o-mini (nano banana) to pick the most blank corner
async function detectBestCorner(imageBase64: string, mimeType: string): Promise<Corner> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return "bottom-right";

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      max_tokens: 12,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image_url",
              image_url: {
                url: `data:${mimeType};base64,${imageBase64}`,
                detail: "low",
              },
            },
            {
              type: "text",
              text: `Which corner of this image has the most blank, uniform, or low-contrast area suitable for a ${OVERLAY_W}x${OVERLAY_H}px watermark? Reply with exactly one of: top-left, top-right, bottom-left, bottom-right`,
            },
          ],
        },
      ],
    }),
  });

  if (!res.ok) return "bottom-right";
  const data = (await res.json()) as { choices?: { message?: { content?: string } }[] };
  const answer = (data.choices?.[0]?.message?.content ?? "").trim().toLowerCase();
  const valid: Corner[] = ["top-left", "top-right", "bottom-left", "bottom-right"];
  return valid.find((c) => answer.includes(c)) ?? "bottom-right";
}

// Build a semi-transparent SVG overlay: label text + placeholder for QR
function makeSvgOverlay(): Buffer {
  const w = OVERLAY_W;
  const h = OVERLAY_H;
  const svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="${w}" height="${h}" rx="7" ry="7" fill="rgba(255,255,255,0.85)"/>
  <text
    x="${w / 2}"
    y="${MARGIN + LABEL_H - 2}"
    font-family="Arial, Helvetica, sans-serif"
    font-size="10.5"
    font-weight="bold"
    letter-spacing="0.3"
    text-anchor="middle"
    fill="#0d1f3c"
  >${LABEL_TEXT}</text>
</svg>`;
  return Buffer.from(svg);
}

export async function POST(request: Request) {
  try {
    // Auth check — admin only
    const supabase = await createServerClient();
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

    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    if (!file) return NextResponse.json({ error: "No file provided" }, { status: 400 });

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type))
      return NextResponse.json({ error: "Unsupported file type" }, { status: 400 });
    if (file.size > 4 * 1024 * 1024)
      return NextResponse.json({ error: "File too large (max 4MB)" }, { status: 400 });

    const originalBuffer = Buffer.from(await file.arrayBuffer());

    // 1. GPT-4o-mini picks the best corner
    const imageBase64 = originalBuffer.toString("base64");
    const corner = await detectBestCorner(imageBase64, file.type);

    // 2. Generate QR code PNG
    const qrBuffer: Buffer = await QRCode.toBuffer(SITE_URL, {
      type: "png",
      width: QR_PX,
      margin: 1,
      color: { dark: "#0d1f3c", light: "#ffffff" },
    });

    // 3. Get image size
    const meta = await sharp(originalBuffer).metadata();
    const imgW = meta.width ?? 1080;
    const imgH = meta.height ?? 1080;

    // 4. Compute overlay position
    const m = 16; // edge margin
    let left: number, top: number;
    if (corner === "top-left") {
      left = m;
      top = m;
    } else if (corner === "top-right") {
      left = imgW - OVERLAY_W - m;
      top = m;
    } else if (corner === "bottom-left") {
      left = m;
      top = imgH - OVERLAY_H - m;
    } else {
      // bottom-right (default)
      left = imgW - OVERLAY_W - m;
      top = imgH - OVERLAY_H - m;
    }

    const qrLeft = left + MARGIN;
    const qrTop = top + LABEL_H + MARGIN * 2;

    // 5. Composite: SVG background → QR code on top
    const resultBuffer = await sharp(originalBuffer)
      .composite([
        { input: makeSvgOverlay(), left, top },
        { input: qrBuffer, left: qrLeft, top: qrTop },
      ])
      .jpeg({ quality: 92 })
      .toBuffer();

    // 6. Upload to Supabase Storage (same pattern as /api/upload)
    const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!serviceKey)
      return NextResponse.json({ error: "Server misconfiguration" }, { status: 500 });

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
    const objectPath = `covers/${Date.now()}-${Math.random().toString(36).slice(2)}-qr.jpg`;
    const uploadUrl = `${supabaseUrl}/storage/v1/object/announcements/${objectPath}`;

    const uploadRes = await fetch(uploadUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${serviceKey}`,
        "Content-Type": "image/jpeg",
        "x-upsert": "true",
        apikey: serviceKey,
      },
      body: new Uint8Array(resultBuffer),
    });

    if (!uploadRes.ok) {
      const errText = await uploadRes.text().catch(() => "unknown");
      return NextResponse.json(
        { error: `Storage error ${uploadRes.status}: ${errText}` },
        { status: 500 }
      );
    }

    const publicUrl = `${supabaseUrl}/storage/v1/object/public/announcements/${objectPath}`;
    return NextResponse.json({ url: publicUrl, corner });
  } catch (err: unknown) {
    console.error("[upload-with-qr]", err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
