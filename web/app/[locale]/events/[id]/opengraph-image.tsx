import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale } from "@/lib/types";
import { getSemanticSymbol } from "@/lib/design/organicMotifs";

export const runtime = "edge";
export const size = { width: 1200, height: 1200 };
export const contentType = "image/png";

const PALETTES = [
  { bg: "#FFE9DD", fg: "#E84860", accent: "#1F5E2B" },
  { bg: "#E8F6D6", fg: "#1F5E2B", accent: "#E84860" },
  { bg: "#FFF1C2", fg: "#C9A227", accent: "#3A261F" },
  { bg: "#FFD9D0", fg: "#F47A86", accent: "#3A261F" },
  { bg: "#E0EBFF", fg: "#3B5BA9", accent: "#E84860" },
  { bg: "#FFE0EF", fg: "#D85862", accent: "#1F5E2B" },
  { bg: "#F0E6FF", fg: "#7B4FB8", accent: "#C9A227" },
  { bg: "#D6F0EA", fg: "#2C8A7A", accent: "#E84860" },
];

function hashForId(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export default async function Image({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { id } = await params;

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data: event } = await supabase
    .from("events")
    .select("category")
    .eq("id", id)
    .single();

  const categoryKey = event?.category?.[0] ?? "art";
  const h = hashForId(id);
  const palette = PALETTES[h % PALETTES.length];
  const motifVariant = h % 5;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: palette.bg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg width="880" height="880" viewBox="0 0 100 100">
          {getSemanticSymbol(categoryKey, motifVariant, palette.fg, palette.accent)}
        </svg>
      </div>
    ),
    { ...size }
  );
}
