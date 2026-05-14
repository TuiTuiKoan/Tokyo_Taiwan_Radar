import { ImageResponse } from "next/og";
import { createClient } from "@supabase/supabase-js";
import { type Locale } from "@/lib/types";
import { satoriTokens } from "@/lib/design/tokens";

// Brand colors
const c = satoriTokens.color;
const MOCHA  = c.primitive.cocoa;     // #3A261F

export const runtime = "edge";
export const size = { width: 1200, height: 1200 };
export const contentType = "image/png";

// ── Deterministic PRNG (mirrors CategoryThumbnail.tsx) ──────────────────────
function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Palette (mirrors CategoryThumbnail.tsx) ──────────────────────────────────
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

// ── Category display labels ──────────────────────────────────────────────────
const CATEGORY_LABEL: Record<string, string> = {
  movie: "CINEMA", performing_arts: "STAGE", art: "ART",
  senses: "FLAVOR", lifestyle_food: "FOOD", lecture: "LECTURE",
  academic: "ACADEMY", books_media: "BOOK", taiwan_japan: "TWxJP",
  retail: "STORE", nature: "NATURE", tech: "TECH",
  tourism: "TRAVEL", gender: "GENDER", geopolitics: "INTL",
  competition: "RIVAL", business: "BIZ", report: "NEWS",
};

function getCategoryLabel(cats: string[]): string {
  for (const cat of cats) if (CATEGORY_LABEL[cat]) return CATEGORY_LABEL[cat];
  return "EVENT";
}

type MotifKey =
  | "movie" | "performing_arts" | "art" | "senses" | "lifestyle_food"
  | "lecture" | "academic" | "books_media" | "taiwan_japan"
  | "retail" | "nature" | "tech" | "tourism" | "gender"
  | "geopolitics" | "competition" | "business" | "report";

const SEMANTIC_RULES: { words: string[]; motif: MotifKey }[] = [
  { words: ["屋台", "夜市", "市集", "market", "フェス", "festival", "祭", "園遊", "grocery"], motif: "taiwan_japan" },
  { words: ["音楽", "音樂", "music", "concert", "コンサート", "演唱", "band", "ライブ"], motif: "performing_arts" },
  { words: ["電影", "映画", "film", "cinema", "movie", "シネマ"], motif: "movie" },
  { words: ["展", "exhibition", "個展", "展覽", "ギャラリー", "gallery"], motif: "art" },
  { words: ["講座", "講演", "lecture", "talk", "トーク", "座談"], motif: "lecture" },
  { words: ["公園", "park", "森", "forest", "綠", "green", "雲", "霧", "濛", "fog"], motif: "nature" },
  { words: ["書", "本", "book", "読書", "書房", "library", "書店"], motif: "books_media" },
];

function pickSemanticMotif(primaryCat: string, titleBlob: string): MotifKey {
  if (primaryCat === "movie") return "movie";
  if (["business", "academic", "tech"].includes(primaryCat)) return primaryCat as MotifKey;
  const lower = titleBlob.toLowerCase();
  for (const rule of SEMANTIC_RULES) {
    if (rule.words.some((word) => lower.includes(word.toLowerCase()))) return rule.motif;
  }
  return CATEGORY_LABEL[primaryCat] ? (primaryCat as MotifKey) : "report";
}

type HeroObjectKey =
  | "filmFrame" | "musicNote" | "galleryFrame" | "coffeeCup" | "marketStall"
  | "openBook" | "tvScreen" | "mountainSun" | "talkCard" | "storeBag"
  | "globe" | "bars" | "trophy" | "filmClap" | "ticket" | "microphone"
  | "podium" | "graduationCap" | "projector" | "surrealEye" | "meltClock"
  | "cyborgFace" | "dadaScrap" | "paperclipNote" | "clothespinTape" | "tornNewspaper"
  | "lipsStamp" | "noseProfile" | "faceCollage";

const SEMANTIC_OBJECT_RULES: { words: string[]; object: HeroObjectKey }[] = [
  { words: ["屋台", "夜市", "市集", "market", "festival", "フェス", "祭"], object: "marketStall" },
  { words: ["珈琲", "咖啡", "coffee", "cafe", "喫茶", "tea", "茶"], object: "coffeeCup" },
  { words: ["音楽", "音樂", "music", "concert", "コンサート", "演唱", "band", "ライブ"], object: "musicNote" },
  { words: ["展", "exhibition", "個展", "展覽", "gallery", "ギャラリー", "art"], object: "faceCollage" },
  { words: ["書", "本", "book", "読書", "書房", "library", "書店"], object: "openBook" },
  { words: ["講座", "講演", "lecture", "talk", "トーク", "座談"], object: "lipsStamp" },
  { words: ["映画", "電影", "film", "cinema", "movie", "シネマ"], object: "cyborgFace" },
  { words: ["digital", "tech", "screen", "video", "テレビ", "映像"], object: "cyborgFace" },
  { words: ["山", "公園", "park", "森", "forest", "雲", "霧", "濛", "fog"], object: "mountainSun" },
  { words: ["夢", "dream", "超現実", "surreal", "幻想", "fantasy"], object: "dadaScrap" },
];

const CATEGORY_OBJECT: Partial<Record<MotifKey, HeroObjectKey>> = {
  movie: "cyborgFace",
  performing_arts: "lipsStamp",
  art: "faceCollage",
  senses: "lipsStamp",
  lifestyle_food: "coffeeCup",
  lecture: "lipsStamp",
  academic: "graduationCap",
  books_media: "tornNewspaper",
  taiwan_japan: "marketStall",
  retail: "storeBag",
  nature: "mountainSun",
  tech: "cyborgFace",
  tourism: "mountainSun",
  gender: "faceCollage",
  geopolitics: "globe",
  competition: "trophy",
  business: "paperclipNote",
  report: "tornNewspaper",
};

const HERO_OBJECT_POOLS: Partial<Record<MotifKey, HeroObjectKey[]>> = {
  movie: ["cyborgFace", "filmClap", "ticket", "dadaScrap"],
  performing_arts: ["musicNote", "microphone", "lipsStamp", "faceCollage"],
  art: ["faceCollage", "dadaScrap", "surrealEye", "meltClock", "lipsStamp"],
  senses: ["coffeeCup", "lipsStamp", "noseProfile", "dadaScrap"],
  lifestyle_food: ["coffeeCup", "marketStall", "lipsStamp"],
  lecture: ["lipsStamp", "microphone", "paperclipNote", "faceCollage"],
  academic: ["openBook", "graduationCap", "paperclipNote", "tornNewspaper"],
  books_media: ["tornNewspaper", "openBook", "paperclipNote"],
  taiwan_japan: ["marketStall", "coffeeCup", "faceCollage"],
  retail: ["storeBag", "marketStall", "clothespinTape"],
  nature: ["mountainSun", "galleryFrame"],
  tech: ["cyborgFace", "tvScreen", "projector", "surrealEye"],
  tourism: ["mountainSun", "ticket", "clothespinTape"],
  gender: ["faceCollage", "lipsStamp", "noseProfile", "surrealEye"],
  geopolitics: ["globe", "podium", "tornNewspaper"],
  competition: ["trophy", "bars"],
  business: ["paperclipNote", "bars", "tornNewspaper"],
  report: ["tornNewspaper", "paperclipNote", "faceCollage"],
};

function pickHeroObject(motifKey: MotifKey, titleBlob: string): HeroObjectKey {
  if (motifKey === "business") return "paperclipNote";
  if (motifKey === "academic") return "graduationCap";
  if (motifKey === "tech") return "cyborgFace";
  const lower = titleBlob.toLowerCase();
  for (const rule of SEMANTIC_OBJECT_RULES) {
    if (rule.words.some((word) => lower.includes(word.toLowerCase()))) return rule.object;
  }
  return CATEGORY_OBJECT[motifKey] ?? "faceCollage";
}

// ── Font loader ──────────────────────────────────────────────────────────────
async function loadFont(text: string): Promise<ArrayBuffer | null> {
  const family = "Zen+Maru+Gothic:wght@700";
  const url = `https://fonts.googleapis.com/css2?family=${family}&text=${encodeURIComponent(text)}&display=swap`;
  try {
    const css = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17" },
    }).then((r) => r.text());
    const match = css.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);
    if (!match) return null;
    const fontRes = await fetch(match[1]);
    return fontRes.ok ? fontRes.arrayBuffer() : null;
  } catch { return null; }
}

// ── Motifs (inline JSX for Satori, mirrors CategoryThumbnail.tsx) ────────────
// Drawn in a 100×100 viewBox; SVG element sized 520×520 for display.
function renderMotif(cat: string, fg: string, accent: string): React.ReactNode {
  switch (cat) {
    case "movie":
      return <g><rect x="20" y="30" width="60" height="40" fill={fg} /><rect x="20" y="30" width="60" height="6" fill={accent} /><rect x="20" y="64" width="60" height="6" fill={accent} /><circle cx="50" cy="50" r="8" fill="#fff" /></g>;
    case "performing_arts":
      return <g><circle cx="50" cy="50" r="28" fill={fg} /><circle cx="50" cy="50" r="18" fill={accent} /><circle cx="50" cy="50" r="6" fill="#fff" /></g>;
    case "art":
      return <g><polygon points="50,22 78,70 22,70" fill={fg} /><circle cx="50" cy="60" r="10" fill={accent} /></g>;
    case "senses": case "lifestyle_food":
      return <g><path d="M 18 50 Q 30 30 42 50 T 66 50 T 82 50" stroke={fg} strokeWidth="5" fill="none" strokeLinecap="round" /><path d="M 18 62 Q 30 42 42 62 T 66 62 T 82 62" stroke={accent} strokeWidth="5" fill="none" strokeLinecap="round" /></g>;
    case "lecture":
      return <g><rect x="28" y="32" width="44" height="32" fill={fg} /><rect x="32" y="36" width="36" height="4" fill={accent} /><rect x="32" y="44" width="28" height="4" fill={accent} /><rect x="32" y="52" width="32" height="4" fill={accent} /></g>;
    case "academic":
      return <g><polygon points="50,20 80,40 50,60 20,40" fill={fg} /><line x1="50" y1="60" x2="50" y2="76" stroke={accent} strokeWidth="3" /><circle cx="78" cy="48" r="3" fill={accent} /></g>;
    case "books_media":
      return <g><path d="M 22 28 L 50 36 L 78 28 L 78 70 L 50 78 L 22 70 Z" fill={fg} /><line x1="50" y1="36" x2="50" y2="78" stroke={accent} strokeWidth="3" /></g>;
    case "taiwan_japan":
      return <g><circle cx="36" cy="50" r="14" fill={fg} /><circle cx="64" cy="50" r="14" fill={accent} /></g>;
    case "retail":
      return <g><rect x="28" y="38" width="44" height="36" fill={fg} /><path d="M 38 38 Q 38 26 50 26 Q 62 26 62 38" stroke={accent} strokeWidth="3" fill="none" /></g>;
    case "nature":
      return <g><path d="M 30 70 Q 40 30 60 40 Q 70 50 50 70 Z" fill={fg} /><path d="M 50 70 L 50 40" stroke={accent} strokeWidth="2" /></g>;
    case "tech":
      return <g><rect x="26" y="30" width="48" height="36" fill={fg} /><rect x="32" y="36" width="36" height="24" fill={accent} /><rect x="40" y="66" width="20" height="6" fill={fg} /></g>;
    case "tourism":
      return <g><path d="M 24 70 L 24 44 Q 24 28 50 28 Q 76 28 76 44 L 76 70 Z" fill={fg} /><rect x="44" y="50" width="12" height="20" fill={accent} /></g>;
    case "gender":
      return <g><circle cx="38" cy="44" r="14" fill="none" stroke={fg} strokeWidth="4" /><circle cx="62" cy="56" r="14" fill="none" stroke={accent} strokeWidth="4" /></g>;
    case "geopolitics":
      return <g><circle cx="50" cy="50" r="28" fill="none" stroke={fg} strokeWidth="3" /><ellipse cx="50" cy="50" rx="28" ry="10" fill="none" stroke={accent} strokeWidth="2" /><line x1="22" y1="50" x2="78" y2="50" stroke={accent} strokeWidth="2" /></g>;
    case "competition":
      return <g><polygon points="50,18 60,38 82,42 66,58 70,80 50,68 30,80 34,58 18,42 40,38" fill={fg} /><circle cx="50" cy="48" r="6" fill={accent} /></g>;
    case "business":
      return <g><rect x="22" y="56" width="12" height="20" fill={fg} /><rect x="40" y="44" width="12" height="32" fill={accent} /><rect x="58" y="32" width="12" height="44" fill={fg} /><polyline points="22,46 40,38 58,28 76,18" stroke={accent} strokeWidth="2.5" fill="none" /></g>;
    case "report":
      return <g><rect x="26" y="22" width="48" height="56" fill={fg} /><line x1="34" y1="36" x2="66" y2="36" stroke={accent} strokeWidth="2" /><line x1="34" y1="46" x2="66" y2="46" stroke={accent} strokeWidth="2" /><line x1="34" y1="56" x2="58" y2="56" stroke={accent} strokeWidth="2" /></g>;
    default:
      return <g><circle cx="40" cy="46" r="20" fill={fg} /><rect x="48" y="38" width="28" height="28" fill={accent} /></g>;
  }
}

function renderHeroObject(kind: HeroObjectKey, fg: string, accent: string, bg: string, variant: number): React.ReactNode {
  const ink = MOCHA;
  const soft = variant === 1 ? accent : fg;
  switch (kind) {
    case "musicNote":
      return (
        <g>
          <rect x="14" y="70" width="28" height="16" rx="8" fill={soft} transform="rotate(-12 28 78)" />
          <rect x="68" y="72" width="28" height="16" rx="8" fill={fg} transform="rotate(-12 82 80)" />
          <rect x="29" y="23" width="7" height="56" fill={ink} />
          <rect x="82" y="20" width="7" height="60" fill={ink} />
          <polygon points="36,23 89,16 89,34 36,41" fill={accent} />
        </g>
      );
    case "galleryFrame":
      return (
        <g>
          <rect x="14" y="22" width="72" height="54" fill={ink} />
          <rect x="19" y="27" width="62" height="44" fill={bg} />
          <polygon points="20,71 42,42 60,71" fill={ink} />
          <circle cx="67" cy="39" r="10" fill={accent} />
          <path d="M 54 62 L 75 47" stroke={fg} strokeWidth="4" strokeLinecap="round" />
        </g>
      );
    case "coffeeCup":
      return (
        <g>
          <path d="M 30 42 L 72 42 L 68 78 Q 50 88 32 78 Z" fill={accent} />
          <rect x="28" y="36" width="46" height="8" fill={ink} />
          <path d="M 72 51 Q 88 50 88 64 Q 88 78 70 76" fill="none" stroke={ink} strokeWidth="6" />
          <path d="M 41 28 Q 37 20 42 14" fill="none" stroke={fg} strokeWidth="4" strokeLinecap="round" />
          <path d="M 52 28 Q 48 20 53 14" fill="none" stroke={fg} strokeWidth="4" strokeLinecap="round" />
          <path d="M 63 28 Q 59 20 64 14" fill="none" stroke={fg} strokeWidth="4" strokeLinecap="round" />
        </g>
      );
    case "marketStall":
      return (
        <g>
          <rect x="24" y="56" width="52" height="28" fill={bg} stroke={ink} strokeWidth="5" />
          <rect x="18" y="44" width="64" height="10" fill={accent} />
          <polygon points="22,28 38,44 22,44" fill={fg} />
          <polygon points="38,28 54,44 38,44" fill={accent} />
          <polygon points="54,28 78,44 54,44" fill={fg} />
          <circle cx="35" cy="69" r="5" fill={fg} />
          <circle cx="50" cy="69" r="5" fill={accent} />
          <circle cx="65" cy="69" r="5" fill="#6FAE4E" />
        </g>
      );
    case "openBook":
      return (
        <g>
          <path d="M 12 76 Q 30 68 50 78 L 50 26 Q 30 16 12 26 Z" fill={bg} stroke={ink} strokeWidth="5" />
          <path d="M 88 76 Q 70 68 50 78 L 50 26 Q 70 16 88 26 Z" fill={accent} stroke={ink} strokeWidth="5" />
          <line x1="50" y1="26" x2="50" y2="78" stroke={ink} strokeWidth="5" />
          <path d="M 22 42 Q 35 36 44 42" stroke={ink} strokeWidth="4" strokeLinecap="round" fill="none" />
          <path d="M 22 56 Q 35 50 44 56" stroke={ink} strokeWidth="4" strokeLinecap="round" fill="none" />
          <path d="M 78 42 Q 65 36 56 42" stroke={bg} strokeWidth="4" strokeLinecap="round" fill="none" />
        </g>
      );
    case "surrealEye":
      return (
        <g>
          <path d="M 10 50 Q 50 10 90 50 Q 50 90 10 50 Z" fill={bg} stroke={ink} strokeWidth="5" />
          <circle cx="50" cy="50" r="22" fill={fg} stroke={ink} strokeWidth="5" />
          <circle cx="50" cy="50" r="8" fill={accent} />
          <line x1="50" y1="10" x2="50" y2="22" stroke={ink} strokeWidth="5" />
          <line x1="50" y1="78" x2="50" y2="90" stroke={ink} strokeWidth="5" />
          <line x1="16" y1="26" x2="26" y2="34" stroke={ink} strokeWidth="4" />
          <line x1="84" y1="26" x2="74" y2="34" stroke={ink} strokeWidth="4" />
        </g>
      );
    case "meltClock":
      return (
        <g>
          <path d="M 20 50 C 20 20, 80 20, 80 50 C 80 70, 60 90, 40 90 C 20 90, 10 70, 20 50 Z" fill={bg} stroke={ink} strokeWidth="5" />
          <circle cx="45" cy="55" r="3" fill={ink} />
          <line x1="45" y1="55" x2="60" y2="40" stroke={accent} strokeWidth="4" strokeLinecap="round" />
          <line x1="45" y1="55" x2="40" y2="75" stroke={fg} strokeWidth="5" strokeLinecap="round" />
          <path d="M 75 50 Q 80 65 90 90" fill="none" stroke={ink} strokeWidth="5" strokeLinecap="round" />
        </g>
      );
    case "tvScreen":
      return (
        <g>
          <rect x="16" y="24" width="68" height="50" fill={ink} />
          <rect x="22" y="30" width="28" height="38" fill={fg} />
          <rect x="52" y="30" width="26" height="38" fill={accent} />
          <rect x="44" y="74" width="12" height="10" fill={ink} />
          <rect x="34" y="84" width="32" height="5" fill={ink} />
        </g>
      );
    case "mountainSun":
      return (
        <g>
          <rect x="16" y="26" width="68" height="48" fill={bg} stroke={ink} strokeWidth="5" />
          <polygon points="22,74 43,42 62,74" fill={ink} />
          <polygon points="46,74 65,51 79,74" fill={fg} opacity="0.7" />
          <circle cx="69" cy="38" r="9" fill={accent} />
        </g>
      );
    case "talkCard":
      return (
        <g>
          <rect x="17" y="30" width="66" height="44" fill={bg} stroke={ink} strokeWidth="5" />
          <rect x="17" y="30" width="66" height="10" fill={MOCHA} />
          <line x1="31" y1="52" x2="68" y2="52" stroke={accent} strokeWidth="5" />
          <line x1="31" y1="63" x2="55" y2="63" stroke={MOCHA} strokeWidth="4" />
          <line x1="31" y1="72" x2="67" y2="72" stroke={MOCHA} strokeWidth="4" />
        </g>
      );
    case "storeBag":
      return (
        <g>
          <rect x="24" y="38" width="52" height="42" fill={fg} stroke={ink} strokeWidth="5" />
          <path d="M 36 38 Q 36 22 50 22 Q 64 22 64 38" fill="none" stroke={accent} strokeWidth="5" />
          <circle cx="50" cy="60" r="8" fill={bg} />
        </g>
      );
    case "globe":
      return (
        <g>
          <circle cx="50" cy="50" r="34" fill={bg} stroke={ink} strokeWidth="5" />
          <ellipse cx="50" cy="50" rx="18" ry="34" fill="none" stroke={fg} strokeWidth="4" />
          <line x1="18" y1="50" x2="82" y2="50" stroke={accent} strokeWidth="5" />
          <path d="M 26 34 Q 50 44 74 34" fill="none" stroke={fg} strokeWidth="4" />
          <path d="M 26 66 Q 50 56 74 66" fill="none" stroke={fg} strokeWidth="4" />
        </g>
      );
    case "bars":
      return (
        <g>
          <rect x="22" y="58" width="14" height="26" fill={fg} />
          <rect x="43" y="42" width="14" height="42" fill={accent} />
          <rect x="64" y="28" width="14" height="56" fill={fg} />
          <polyline points="22,46 43,36 64,22 82,16" fill="none" stroke={ink} strokeWidth="5" />
        </g>
      );
    case "trophy":
      return (
        <g>
          <path d="M 34 24 L 66 24 L 62 58 Q 50 68 38 58 Z" fill={accent} stroke={ink} strokeWidth="5" />
          <path d="M 34 32 Q 20 34 24 48 Q 28 58 39 54" fill="none" stroke={ink} strokeWidth="5" />
          <path d="M 66 32 Q 80 34 76 48 Q 72 58 61 54" fill="none" stroke={ink} strokeWidth="5" />
          <rect x="45" y="65" width="10" height="14" fill={ink} />
          <rect x="34" y="79" width="32" height="7" fill={ink} />
        </g>
      );
    case "filmClap":
      return (
        <g>
          <rect x="17" y="38" width="68" height="42" fill={bg} stroke={ink} strokeWidth="5" />
          <polygon points="16,24 83,14 86,32 19,42" fill={ink} />
          <polygon points="25,25 36,23 47,36 36,38" fill={fg} />
          <polygon points="49,21 60,20 71,33 60,35" fill={accent} />
          <rect x="28" y="53" width="44" height="6" fill={accent} />
          <rect x="28" y="66" width="28" height="5" fill={MOCHA} />
        </g>
      );
    case "ticket":
      return (
        <g>
          <path d="M 17 36 L 83 27 L 88 65 L 22 74 Z" fill={bg} stroke={ink} strokeWidth="5" />
          <circle cx="25" cy="55" r="8" fill={fg} />
          <circle cx="80" cy="47" r="8" fill={accent} />
          <line x1="42" y1="36" x2="48" y2="72" stroke={MOCHA} strokeWidth="4" strokeDasharray="4 5" />
          <rect x="54" y="43" width="18" height="7" fill={accent} />
          <rect x="55" y="56" width="22" height="6" fill={fg} />
        </g>
      );
    case "microphone":
      return (
        <g>
          <rect x="38" y="18" width="24" height="44" rx="12" fill={accent} stroke={ink} strokeWidth="5" />
          <path d="M 28 48 Q 28 76 50 76 Q 72 76 72 48" fill="none" stroke={ink} strokeWidth="6" strokeLinecap="round" />
          <line x1="50" y1="76" x2="50" y2="88" stroke={ink} strokeWidth="6" />
          <rect x="32" y="87" width="36" height="6" fill={ink} />
          <line x1="43" y1="31" x2="57" y2="31" stroke={bg} strokeWidth="4" />
          <line x1="43" y1="43" x2="57" y2="43" stroke={bg} strokeWidth="4" />
        </g>
      );
    case "podium":
      return (
        <g>
          <rect x="22" y="46" width="56" height="34" fill={accent} stroke={ink} strokeWidth="5" />
          <rect x="16" y="38" width="68" height="11" fill={fg} />
          <path d="M 32 36 L 24 22" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          <path d="M 68 36 L 76 22" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          <circle cx="24" cy="20" r="5" fill={fg} />
          <circle cx="76" cy="20" r="5" fill={fg} />
          <rect x="34" y="58" width="32" height="6" fill={bg} />
        </g>
      );
    case "graduationCap":
      return (
        <g>
          <polygon points="50,18 88,38 50,58 12,38" fill={ink} />
          <polygon points="50,26 74,38 50,50 26,38" fill={accent} />
          <rect x="30" y="52" width="40" height="15" fill={fg} />
          <path d="M 74 38 L 74 68" stroke={ink} strokeWidth="5" strokeLinecap="round" />
          <circle cx="74" cy="72" r="7" fill={accent} />
          <rect x="24" y="74" width="52" height="7" fill={ink} />
        </g>
      );
    case "projector":
      return (
        <g>
          <rect x="14" y="24" width="72" height="44" fill={bg} stroke={ink} strokeWidth="5" />
          <circle cx="34" cy="46" r="12" fill={fg} stroke={ink} strokeWidth="4" />
          <circle cx="34" cy="46" r="5" fill={bg} />
          <rect x="54" y="36" width="20" height="6" fill={accent} />
          <rect x="54" y="50" width="14" height="6" fill={MOCHA} />
          <rect x="31" y="68" width="38" height="7" fill={ink} />
          <path d="M 77 34 L 94 24 L 94 68 L 77 58 Z" fill={accent} stroke={ink} strokeWidth="4" />
        </g>
      );
    case "lipsStamp":
      // Simple oversized lips floating on a clean card with one small flower drifting
      return (
        <g>
          <path d="M 16 50 Q 32 28 50 48 Q 68 28 84 50 Q 68 76 50 58 Q 32 76 16 50 Z" fill={accent} stroke={ink} strokeWidth="4" />
          <path d="M 18 50 Q 50 60 82 50" stroke={ink} strokeWidth="3" fill="none" />
          {/* drifting petal escaping upper-right */}
          <circle cx="86" cy="22" r="4" fill={fg} stroke={ink} strokeWidth="2" />
          <circle cx="86" cy="22" r="1.6" fill={ink} />
          <path d="M 78 30 Q 82 26 86 22" stroke={ink} strokeWidth="2" fill="none" strokeDasharray="2 3" />
        </g>
      );
    case "noseProfile":
      // Clean profile head silhouette with one eye + one petal sprouting from forehead
      return (
        <g>
          <path d="M 28 22 Q 18 30 18 50 Q 18 70 30 78 L 30 88 L 56 88 L 56 78 Q 70 70 70 56 L 80 50 L 70 44 Q 68 28 56 22 Z" fill={bg} stroke={ink} strokeWidth="4" />
          <circle cx="46" cy="48" r="3" fill={ink} />
          <path d="M 56 62 Q 50 64 48 62" stroke={ink} strokeWidth="3" fill="none" strokeLinecap="round" />
          {/* sprouting flower */}
          <line x1="40" y1="22" x2="36" y2="10" stroke={ink} strokeWidth="3" strokeLinecap="round" />
          <circle cx="34" cy="8" r="5" fill={accent} stroke={ink} strokeWidth="2.5" />
        </g>
      );
    case "cyborgFace":
      // Single clean head, two eyes (one mechanical), small mouth, one flower antenna
      return (
        <g>
          {/* head */}
          <circle cx="50" cy="54" r="34" fill={bg} stroke={ink} strokeWidth="4" />
          {/* eyes */}
          <rect x="28" y="46" width="14" height="10" fill={ink} />
          <circle cx="35" cy="51" r="3" fill={accent} />
          <circle cx="63" cy="51" r="6" fill={ink} />
          <circle cx="61" cy="49" r="1.6" fill={bg} />
          {/* mouth */}
          <path d="M 38 70 Q 50 74 62 70" stroke={ink} strokeWidth="3" fill="none" strokeLinecap="round" />
          {/* antenna with flower bursting */}
          <line x1="50" y1="20" x2="50" y2="6" stroke={ink} strokeWidth="3" strokeLinecap="round" />
          <circle cx="50" cy="4" r="4" fill={accent} stroke={ink} strokeWidth="2" />
          <circle cx="50" cy="4" r="1.6" fill={bg} />
          {/* ear bolts */}
          <circle cx="14" cy="56" r="3" fill={accent} stroke={ink} strokeWidth="2" />
          <circle cx="86" cy="56" r="3" fill={accent} stroke={ink} strokeWidth="2" />
        </g>
      );
    case "faceCollage":
      // Bouquet — one vase, three flowers (one with an eye as center), petals drifting
      return (
        <g>
          {/* vase */}
          <path d="M 32 64 L 68 64 L 64 90 L 36 90 Z" fill={accent} stroke={ink} strokeWidth="4" />
          <rect x="30" y="60" width="40" height="6" fill={ink} />
          {/* stems */}
          <path d="M 50 64 Q 48 50 44 32" stroke={ink} strokeWidth="3" fill="none" strokeLinecap="round" />
          <path d="M 50 64 Q 62 52 70 36" stroke={ink} strokeWidth="3" fill="none" strokeLinecap="round" />
          <path d="M 50 64 Q 40 56 28 44" stroke={ink} strokeWidth="3" fill="none" strokeLinecap="round" />
          {/* leaf */}
          <path d="M 50 56 Q 58 48 54 60 Z" fill={fg} stroke={ink} strokeWidth="2" />
          {/* flower 1 — eye-flower */}
          <circle cx="44" cy="28" r="11" fill={fg} stroke={ink} strokeWidth="3" />
          <ellipse cx="44" cy="28" rx="6" ry="4" fill={bg} stroke={ink} strokeWidth="2" />
          <circle cx="44" cy="28" r="2" fill={ink} />
          {/* flower 2 — petal cluster */}
          <circle cx="70" cy="32" r="5" fill={bg} stroke={ink} strokeWidth="2.5" />
          <circle cx="76" cy="36" r="5" fill={bg} stroke={ink} strokeWidth="2.5" />
          <circle cx="74" cy="26" r="5" fill={bg} stroke={ink} strokeWidth="2.5" />
          <circle cx="73" cy="32" r="3" fill={accent} />
          {/* flower 3 */}
          <circle cx="26" cy="40" r="6" fill={accent} stroke={ink} strokeWidth="2.5" />
          <circle cx="26" cy="40" r="2" fill={bg} />
          {/* drifting petal */}
          <circle cx="14" cy="14" r="3" fill={accent} stroke={ink} strokeWidth="2" />
          <path d="M 22 22 Q 18 18 14 14" stroke={ink} strokeWidth="1.5" strokeDasharray="2 3" fill="none" />
        </g>
      );
    case "dadaScrap":
      // Painting in a frame with shapes bursting out beyond the frame
      return (
        <g>
          {/* frame */}
          <rect x="14" y="20" width="62" height="58" fill={ink} />
          <rect x="20" y="26" width="50" height="46" fill={bg} />
          {/* inside: horizon + sun */}
          <rect x="20" y="56" width="50" height="16" fill={fg} />
          <circle cx="34" cy="44" r="7" fill={accent} stroke={ink} strokeWidth="2" />
          <path d="M 40 56 L 50 46 L 58 56 Z" fill={ink} />
          {/* bursting out elements */}
          <circle cx="80" cy="18" r="5" fill={accent} stroke={ink} strokeWidth="2.5" />
          <circle cx="80" cy="18" r="1.6" fill={bg} />
          <path d="M 70 20 Q 76 18 80 18" stroke={ink} strokeWidth="2" fill="none" strokeDasharray="2 3" />
          {/* butterfly escaping */}
          <ellipse cx="88" cy="42" rx="6" ry="4" fill={fg} stroke={ink} strokeWidth="2" transform="rotate(-20 88 42)" />
          <ellipse cx="92" cy="48" rx="5" ry="3" fill={accent} stroke={ink} strokeWidth="2" transform="rotate(-20 92 48)" />
          {/* lips escaping bottom-left */}
          <path d="M 4 88 Q 12 80 22 88 Q 12 94 4 88 Z" fill={accent} stroke={ink} strokeWidth="2.5" />
        </g>
      );
    case "paperclipNote":
      // Clean note with one flower sprouting through the page + paperclip on top
      return (
        <g>
          <rect x="20" y="18" width="58" height="68" fill={bg} stroke={ink} strokeWidth="4" />
          <line x1="28" y1="34" x2="68" y2="34" stroke={MOCHA} strokeWidth="2.5" />
          <line x1="28" y1="44" x2="60" y2="44" stroke={MOCHA} strokeWidth="2.5" />
          <line x1="28" y1="54" x2="64" y2="54" stroke={MOCHA} strokeWidth="2.5" />
          {/* paperclip */}
          <path d="M 36 8 L 36 60 Q 36 68 44 68 Q 52 68 52 60 L 52 20 Q 52 14 48 14 Q 44 14 44 20 L 44 56" fill="none" stroke={ink} strokeWidth="4" />
          {/* flower sprouting through page */}
          <line x1="64" y1="70" x2="80" y2="86" stroke={ink} strokeWidth="3" strokeLinecap="round" />
          <circle cx="82" cy="88" r="6" fill={accent} stroke={ink} strokeWidth="2.5" />
          <circle cx="82" cy="88" r="2" fill={bg} />
        </g>
      );
    case "clothespinTape":
      // Single hanging sheet with a face poking through + clothespin at top
      return (
        <g>
          <path d="M 30 18 L 70 18 L 72 86 L 28 88 Z" fill={fg} stroke={ink} strokeWidth="4" />
          {/* face hint */}
          <circle cx="42" cy="44" r="2.5" fill={ink} />
          <circle cx="58" cy="44" r="2.5" fill={ink} />
          <path d="M 42 58 Q 50 62 58 58" stroke={ink} strokeWidth="2.5" fill="none" strokeLinecap="round" />
          {/* drifting petal */}
          <circle cx="84" cy="34" r="4" fill={accent} stroke={ink} strokeWidth="2" />
          {/* clothespin */}
          <rect x="44" y="6" width="6" height="20" fill={ink} />
          <rect x="50" y="6" width="6" height="20" fill={ink} />
          <rect x="42" y="12" width="16" height="4" fill={accent} />
        </g>
      );
    case "tornNewspaper":
      // Open book with content flying out — letters and a small bird escaping the pages
      return (
        <g>
          {/* open book base */}
          <path d="M 8 76 Q 28 70 50 78 L 50 38 Q 28 32 8 38 Z" fill={bg} stroke={ink} strokeWidth="4" />
          <path d="M 92 76 Q 72 70 50 78 L 50 38 Q 72 32 92 38 Z" fill={bg} stroke={ink} strokeWidth="4" />
          <line x1="50" y1="38" x2="50" y2="78" stroke={ink} strokeWidth="4" />
          {/* text lines */}
          <line x1="16" y1="50" x2="44" y2="48" stroke={MOCHA} strokeWidth="2" />
          <line x1="16" y1="58" x2="42" y2="56" stroke={MOCHA} strokeWidth="2" />
          <line x1="56" y1="48" x2="84" y2="50" stroke={MOCHA} strokeWidth="2" />
          <line x1="56" y1="56" x2="82" y2="58" stroke={MOCHA} strokeWidth="2" />
          {/* content flying out */}
          <circle cx="34" cy="22" r="4" fill={accent} stroke={ink} strokeWidth="2" />
          <path d="M 30 30 Q 32 26 34 22" stroke={ink} strokeWidth="1.5" strokeDasharray="2 3" fill="none" />
          {/* small bird escaping */}
          <path d="M 62 16 Q 68 10 76 14 Q 72 18 68 18 Q 70 22 66 22 Z" fill={fg} stroke={ink} strokeWidth="2" />
          <circle cx="74" cy="14" r="1" fill={ink} />
          {/* letter A flying */}
          <text x="22" y="14" fontSize="10" fontWeight="bold" fill={ink} transform="rotate(-15 22 14)">A</text>
        </g>
      );
    case "filmFrame":
    default:
      return (
        <g>
          <rect x="16" y="26" width="68" height="50" fill={ink} />
          <rect x="22" y="34" width="56" height="34" fill={bg} />
          <polygon points="36,42 62,51 36,60" fill={accent} />
          <rect x="16" y="26" width="68" height="8" fill={fg} />
          <rect x="22" y="26" width="8" height="8" fill={bg} />
          <rect x="42" y="26" width="8" height="8" fill={bg} />
          <rect x="62" y="26" width="8" height="8" fill={bg} />
        </g>
      );
  }
}

function renderLabelHero(label: string, fg: string, accent: string, bg: string, fontFamily: string, variant: number, rand: () => number): React.ReactNode {
  const letters = label.split("");
  const L = letters.length;
  const fontFamilies = [fontFamily, "serif", "monospace", "sans-serif"];

  // Per-letter Dadaist jitter — always applied across all variants
  type LS = { rot: number; font: string; sizeMult: number; colorPick: number };
  const styles: LS[] = letters.map(() => ({
    rot: -14 + rand() * 28,
    font: fontFamilies[Math.floor(rand() * fontFamilies.length)],
    sizeMult: 0.85 + rand() * 0.32,
    colorPick: rand(),
  }));
  const colorFor = (s: LS, defaultColor: string) =>
    s.colorPick < 0.18 ? accent : s.colorPick < 0.32 ? fg : defaultColor;

  // Variant 0 — Bold single row inside Mocha box
  if (variant === 0) {
    const baseSize = Math.min(230, Math.floor(960 / L));
    return (
      <div style={{ display: "flex", background: MOCHA, padding: "26px 38px 36px", boxShadow: `18px 18px 0 ${fg}`, transform: `rotate(${-5 + rand() * 4}deg)`, alignItems: "center" }}>
        {letters.map((ch, i) => (
          <span key={i} style={{
            fontSize: Math.round(baseSize * styles[i].sizeMult),
            fontWeight: "bold",
            color: colorFor(styles[i], bg),
            fontFamily: styles[i].font,
            lineHeight: 1,
            margin: `0 ${Math.round(2 + rand() * 8)}px`,
            transform: `rotate(${styles[i].rot * 0.6}deg) translateY(${Math.round(-8 + rand() * 16)}px)`,
            display: "flex",
          }}>{ch}</span>
        ))}
      </div>
    );
  }

  // Variant 1 — Tile grid (wrap to multi-row), each letter in own colored block
  if (variant === 1) {
    const cols = L <= 4 ? L : Math.ceil(L / 2);
    const tile = Math.min(260, Math.floor(940 / cols));
    return (
      <div style={{ display: "flex", flexWrap: "wrap", width: tile * cols + 16, gap: 12, transform: `rotate(${-3 + rand() * 8}deg)` }}>
        {letters.map((ch, i) => {
          const bgSwap = i % 3 === 0 ? MOCHA : i % 3 === 1 ? accent : fg;
          const fgSwap = bgSwap === fg ? MOCHA : bg;
          return (
            <div key={i} style={{
              width: tile,
              height: Math.round(tile * 0.92),
              background: bgSwap,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `${6 + Math.round(rand() * 8)}px ${6 + Math.round(rand() * 8)}px 0 ${i % 2 ? MOCHA : fg}`,
              transform: `rotate(${styles[i].rot * 0.4}deg)`,
            }}>
              <span style={{
                fontSize: Math.round(tile * 0.78 * styles[i].sizeMult),
                fontWeight: "bold",
                color: fgSwap,
                fontFamily: styles[i].font,
                lineHeight: 1,
              }}>{ch}</span>
            </div>
          );
        })}
      </div>
    );
  }

  // Variant 2 — Staircase: each letter on own line, indented progressively
  if (variant === 2) {
    const baseSize = Math.min(280, Math.floor(820 / L) + 90);
    const stepX = Math.round(60 + rand() * 70);
    const stepY = Math.round(baseSize * 0.78);
    return (
      <div style={{ position: "relative", width: stepX * (L - 1) + baseSize + 80, height: stepY * (L - 1) + baseSize + 40, display: "flex" }}>
        {letters.map((ch, i) => (
          <span key={i} style={{
            position: "absolute",
            left: stepX * i,
            top: stepY * i,
            fontSize: Math.round(baseSize * styles[i].sizeMult),
            fontWeight: "bold",
            color: colorFor(styles[i], MOCHA),
            fontFamily: styles[i].font,
            lineHeight: 0.9,
            transform: `rotate(${styles[i].rot}deg)`,
            WebkitTextStroke: `4px ${i % 2 ? accent : MOCHA}`,
            textShadow: `10px 10px 0 ${i % 2 ? fg : accent}`,
          }}>{ch}</span>
        ))}
      </div>
    );
  }

  // Variant 3 — Broken-line wrap: split label at uneven midpoint, second line indented
  if (variant === 3) {
    const breakAt = L <= 3 ? 1 : Math.max(2, Math.min(L - 2, Math.floor(L / 2) + (rand() < 0.5 ? 0 : 1)));
    const line1 = letters.slice(0, breakAt);
    const line2 = letters.slice(breakAt);
    const maxLen = Math.max(line1.length, line2.length);
    const baseSize = Math.min(320, Math.floor(880 / maxLen));
    const indent = Math.round(baseSize * (0.4 + rand() * 0.4));
    const renderLine = (chars: string[], offsetIdx: number, indentPx: number) => (
      <div style={{ display: "flex", marginLeft: indentPx, alignItems: "flex-end" }}>
        {chars.map((ch, j) => {
          const i = offsetIdx + j;
          return (
            <span key={i} style={{
              fontSize: Math.round(baseSize * styles[i].sizeMult),
              fontWeight: "bold",
              color: colorFor(styles[i], MOCHA),
              fontFamily: styles[i].font,
              lineHeight: 0.9,
              transform: `rotate(${styles[i].rot}deg)`,
              WebkitTextStroke: `4px ${MOCHA}`,
              textShadow: `${8 + Math.round(rand() * 6)}px ${8 + Math.round(rand() * 6)}px 0 ${j % 2 ? fg : accent}`,
              margin: `0 ${Math.round(2 + rand() * 10)}px`,
              display: "flex",
            }}>{ch}</span>
          );
        })}
      </div>
    );
    return (
      <div style={{ display: "flex", flexDirection: "column", transform: `rotate(${-3 + rand() * 6}deg)` }}>
        {renderLine(line1, 0, 0)}
        {renderLine(line2, line1.length, indent)}
      </div>
    );
  }

  // Variant 4 — Scatter: large random anchors across canvas
  const W = 1040;
  const H = 930;
  const cellsX = Math.min(4, L);
  const cellsY = Math.ceil(L / cellsX);
  const cellW = W / cellsX;
  const cellH = H / cellsY;
  return (
    <div style={{ position: "relative", width: W, height: H, display: "flex" }}>
      {letters.map((ch, i) => {
        const cx = i % cellsX;
        const cy = Math.floor(i / cellsX);
        const x = Math.round(cellW * cx + cellW * 0.1 + rand() * cellW * 0.3);
        const y = Math.round(cellH * cy + cellH * 0.1 + rand() * cellH * 0.3);
        const size = Math.min(360, Math.round((cellW * 0.78) * styles[i].sizeMult));
        const shadowColor = i % 3 === 0 ? accent : i % 3 === 1 ? fg : MOCHA;
        return (
          <span key={i} style={{
            position: "absolute",
            left: x,
            top: y,
            fontSize: size,
            fontWeight: "bold",
            color: colorFor(styles[i], i % 2 ? MOCHA : fg),
            fontFamily: styles[i].font,
            lineHeight: 0.9,
            transform: `rotate(${styles[i].rot * 1.4}deg)`,
            WebkitTextStroke: `5px ${MOCHA}`,
            textShadow: `${10 + Math.round(rand() * 8)}px ${10 + Math.round(rand() * 8)}px 0 ${shadowColor}`,
          }}>{ch}</span>
        );
      })}
    </div>
  );
}

// ── OG Image ─────────────────────────────────────────────────────────────────
export default async function Image({ params }: { params: Promise<{ locale: Locale; id: string }> }) {
  const { locale, id } = await params;

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data: event } = await supabase
    .from("events")
    .select("name_ja, name_zh, name_en, category, location_name")
    .eq("id", id)
    .single();

  // Category + title keywords drive the visual metaphor; no title/date/venue rendered.
  const cats: string[] = event?.category ?? [];
  const primaryCat = cats[0] ?? "";
  const secondaryCat = cats[1] ?? "";
  const categoryLabel = cats.length ? getCategoryLabel(cats) : "EVENT";
  const titleBlob = [event?.name_zh, event?.name_ja, event?.name_en, event?.location_name].filter(Boolean).join(" ");
  const motifKey = pickSemanticMotif(primaryCat, titleBlob);
  const baseHeroObjectKey = pickHeroObject(motifKey, titleBlob);

  // Palette — drive from semantic motif + secondary category for visual variety.
  const paletteIdx = (hashString((motifKey || "x") + ":" + (secondaryCat || "y")) + cats.length) % PALETTES.length;
  const palette = PALETTES[paletteIdx];
  const accentColor = secondaryCat
    ? PALETTES[hashString(secondaryCat) % PALETTES.length].fg
    : palette.accent;

  // Background pattern. Seed with event id only; locale should not create a new design direction.
  const rand = mulberry32(hashString(id || "default"));
  const heroObjectPool = HERO_OBJECT_POOLS[motifKey] ?? [baseHeroObjectKey];
  const heroObjectKey = heroObjectPool[Math.floor(rand() * heroObjectPool.length)] ?? baseHeroObjectKey;
  const bgKinds = ["halftoneDense", "halftoneSparse", "stripes", "grid", "wavy", "checker"] as const;
  type BgKind = typeof bgKinds[number];
  const bgKind: BgKind = bgKinds[Math.floor(rand() * bgKinds.length)];
  const patRotation = Math.floor(rand() * 90) - 45;
  const bgPatColor = rand() > 0.5 ? palette.fg : palette.accent;

  // Motif transform
  const motifRotate = Math.floor(rand() * 24) - 12;
  const motifOffsetX = Math.floor(rand() * 8) - 4;
  const motifOffsetY = Math.floor(rand() * 8) - 4;

  // Corner accent
  const cornerShape = Math.floor(rand() * 4);
  const cornerOpacity = 0.55 + rand() * 0.25;

  const labelVariant = Math.floor(rand() * 5);
  const objectVariant = Math.floor(rand() * 3);
  const objectRot = -8 + Math.floor(rand() * 17);
  const objectX = 280 + Math.floor(rand() * 90);
  const objectY = 560; // Keep hero object placed below for large labels
  const objectSize = 380; // Keep hero object smaller since label dominates

  // Font (category labels and split letters only)
  const fontData = await loadFont("ABCDEFGHIJKLMNOPQRSTUVWXYZx");
  const fontName = "Zen Maru Gothic";
  const FF = fontData ? fontName : "sans-serif";

  // Pattern defs (scaled up 12× from 100px viewBox)
  function patternDef(kind: BgKind, color: string, rot: number) {
    switch (kind) {
      case "halftoneDense":
        return <pattern id="ogpat" width="96" height="96" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><circle cx="48" cy="48" r="20" fill={color} /></pattern>;
      case "halftoneSparse":
        return <pattern id="ogpat" width="168" height="168" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><circle cx="84" cy="84" r="14" fill={color} /></pattern>;
      case "stripes":
        return <pattern id="ogpat" width="120" height="120" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><line x1="0" y1="0" x2="0" y2="120" stroke={color} strokeWidth="42" /></pattern>;
      case "grid":
        return <pattern id="ogpat" width="144" height="144" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><path d="M 144 0 L 0 0 0 144" stroke={color} strokeWidth="9.6" fill="none" /></pattern>;
      case "wavy":
        return <pattern id="ogpat" width="240" height="120" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><path d="M 0 60 Q 60 0 120 60 T 240 60" stroke={color} strokeWidth="16.8" fill="none" /></pattern>;
      case "checker":
        return <pattern id="ogpat" width="168" height="168" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rot})`}><rect width="84" height="84" fill={color} /><rect x="84" y="84" width="84" height="84" fill={color} /></pattern>;
    }
  }

  // ── Bauhaus collage: 5 deterministic overlay primitives over an anchor motif ──
  type Prim = "disk" | "ring" | "tri" | "slab" | "arc" | "dash" | "plus" | "diamond";
  const PRIMS: Prim[] = ["disk", "ring", "tri", "slab", "arc", "dash", "plus", "diamond"];
  const pickPrim = (): Prim => PRIMS[Math.floor(rand() * PRIMS.length)];

  // Sectors avoid the main hero object zone and keep collage as support.
  const sectors: [number, number, number, number][] = [
    [60, 70, 260, 260],
    [820, 80, 300, 300],
    [70, 720, 300, 300],
    [810, 700, 320, 320],
    [420, 900, 340, 220],
  ];
  const sectorOrder = sectors.map((s) => ({ s, k: rand() })).sort((a, b) => a.k - b.k).map(x => x.s);
  type Overlay = { kind: Prim; cx: number; cy: number; size: number; rot: number; color: string; opacity: number };
  const overlays: Overlay[] = Array.from({ length: 2 }, (_, i) => {
    const [sx, sy, sw, sh] = sectorOrder[i] ?? sectorOrder[0];
    return {
      kind: pickPrim(),
      cx: Math.round(sx + sw * (0.3 + rand() * 0.4)),
      cy: Math.round(sy + sh * (0.3 + rand() * 0.4)),
      size: Math.round(140 + rand() * 140),
      rot: Math.round(rand() * 360),
      color: rand() > 0.5 ? palette.fg : accentColor,
      opacity: 0.18 + rand() * 0.12,
    };
  });

  function renderPrim(p: Overlay) {
    const { kind, cx, cy, size, rot, color, opacity } = p;
    const half = size / 2;
    const t = `rotate(${rot} ${cx} ${cy})`;
    switch (kind) {
      case "disk":
        return <circle cx={cx} cy={cy} r={half * 0.85} fill={color} opacity={opacity} />;
      case "ring":
        return <circle cx={cx} cy={cy} r={half * 0.85} fill="none" stroke={color} strokeWidth={Math.max(10, size * 0.09)} opacity={opacity} />;
      case "tri":
        return <polygon points={`${cx},${cy - half} ${cx + half},${cy + half} ${cx - half},${cy + half}`} fill={color} opacity={opacity} transform={t} />;
      case "slab":
        return <rect x={cx - half} y={cy - size * 0.14} width={size} height={size * 0.28} fill={color} opacity={opacity} transform={t} />;
      case "arc":
        return <path d={`M ${cx - half} ${cy} A ${half} ${half} 0 0 1 ${cx + half} ${cy}`} fill="none" stroke={color} strokeWidth={Math.max(12, size * 0.12)} strokeLinecap="round" opacity={opacity} transform={t} />;
      case "dash":
        return <line x1={cx - half} y1={cy} x2={cx + half} y2={cy} stroke={color} strokeWidth={Math.max(14, size * 0.15)} strokeLinecap="round" opacity={opacity} transform={t} />;
      case "plus":
        return (
          <g transform={t} opacity={opacity}>
            <rect x={cx - half} y={cy - size * 0.13} width={size} height={size * 0.26} fill={color} />
            <rect x={cx - size * 0.13} y={cy - half} width={size * 0.26} height={size} fill={color} />
          </g>
        );
      case "diamond":
        return <polygon points={`${cx},${cy - half} ${cx + half},${cy} ${cx},${cy + half} ${cx - half},${cy}`} fill={color} opacity={opacity} transform={t} />;
    }
  }

  const labelRot = -7 + Math.floor(rand() * 15);
  const labelX = 84;
  const labelY = 96;

  // ── Typographic collage: scatter individual label chars as visual objects ──
  // Each char placed in a peripheral zone, away from the main hero.
  // Treats letters as Bauhaus elements: huge, rotated, low opacity, varied colors.
  const charZones: [number, number, number, number][] = [
    [780, 80, 360, 320],   // top-right
    [80, 480, 320, 280],   // mid-left
    [820, 520, 320, 320],  // mid-right
    [320, 800, 380, 240],  // mid-bottom-center
    [60, 760, 280, 240],   // bottom-left
    [880, 820, 280, 240],  // bottom-right (above watermark)
  ];
  const charZoneOrder = charZones.map((z) => ({ z, k: rand() })).sort((a, b) => a.k - b.k).map(x => x.z);
  const numChars = 1 + Math.floor(rand() * 2);
  const labelChars = categoryLabel.split("");
  const charLayouts = Array.from({ length: numChars }, (_, i) => {
    const [zx, zy, zw, zh] = charZoneOrder[i] ?? charZoneOrder[0];
    const ch = labelChars[i % labelChars.length];
    const variant = Math.floor(rand() * 3); // 0=outline, 1=solid-low-opacity, 2=mocha-tape
    return {
      ch,
      cx: Math.round(zx + zw * (0.3 + rand() * 0.4)),
      cy: Math.round(zy + zh * (0.3 + rand() * 0.4)),
      size: 200 + Math.floor(rand() * 160),    // 200–360px
      rot: -25 + Math.floor(rand() * 50),
      variant,
      color: variant === 0 ? palette.accent : variant === 1 ? palette.fg : MOCHA,
      opacity: variant === 0 ? 0.45 : variant === 1 ? 0.32 : 0.18,
    };
  });
  const showCornerLetters = categoryLabel.length <= 4 && rand() > 0.45;
  const cornerLetterSlots = [
    { x: 36, y: 28, rot: -13 },
    { x: 930, y: 42, rot: 10 },
    { x: 44, y: 900, rot: 8 },
    { x: 910, y: 895, rot: -11 },
  ];

  return new ImageResponse(
    (
      <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", background: palette.bg }}>

        {/* 1. Background pattern — full bleed (stripes/grid/halftone/wavy/checker) */}
        <svg style={{ position: "absolute", top: 0, left: 0 }} width="1200" height="1200" viewBox="0 0 1200 1200">
          <defs>{patternDef(bgKind, bgPatColor, patRotation)}</defs>
          <rect width="1200" height="1200" fill="url(#ogpat)" opacity="0.4" />
        </svg>

        {/* 2. Corner accent — bold shape */}
        <svg style={{ position: "absolute", top: 0, left: 0 }} width="1200" height="1200" viewBox="0 0 1200 1200">
          {cornerShape === 0 && <circle cx="1080" cy="120" r="200" fill={palette.accent} opacity={cornerOpacity} />}
          {cornerShape === 1 && <polygon points="1200,0 1200,420 820,0" fill={palette.accent} opacity={cornerOpacity} />}
          {cornerShape === 2 && <rect x="-60" y="900" width="540" height="540" fill={palette.fg} opacity={cornerOpacity * 0.6} transform="rotate(20 180 1080)" />}
          {cornerShape === 3 && <path d="M 0 1200 Q 320 880 640 1200 Z" fill={palette.accent} opacity={cornerOpacity * 0.7} />}
        </svg>

        {/* 3. Background collage — support shapes only; hero object stays dominant */}
        <svg style={{ position: "absolute", top: 0, left: 0 }} width="1200" height="1200" viewBox="0 0 1200 1200">
          <g opacity="0.28" transform={`translate(620 610) rotate(${motifRotate} 400 400) scale(5.8) translate(${motifOffsetX} ${motifOffsetY})`}>
            {renderMotif(motifKey, palette.fg, accentColor)}
          </g>
          {overlays.map((p, i) => (
            <g key={i}>{renderPrim(p)}</g>
          ))}
        </svg>

        {/* 4. Typographic collage — supporting letter-shapes, not the main object */}
        {showCornerLetters && categoryLabel.split("").map((letter, i) => (
          <span
            key={`corner-${i}`}
            style={{
              position: "absolute",
              left: cornerLetterSlots[i]?.x ?? 0,
              top: cornerLetterSlots[i]?.y ?? 0,
              fontSize: 250,
              fontWeight: "bold",
              color: i % 2 ? palette.accent : palette.fg,
              fontFamily: i % 2 ? "serif" : FF,
              lineHeight: 1,
              opacity: 0.26,
              transform: `rotate(${cornerLetterSlots[i]?.rot ?? 0}deg)`,
              WebkitTextStroke: `4px ${MOCHA}`,
            }}
          >
            {letter}
          </span>
        ))}
        {charLayouts.map((cl, i) => (
          <div
            key={`ch-${i}`}
            style={{
              position: "absolute",
              left: cl.cx,
              top: cl.cy,
              transform: `translate(-50%, -50%) rotate(${cl.rot}deg)`,
              transformOrigin: "center",
              display: "flex",
            }}
          >
            <span style={{
              fontSize: `${cl.size}px`,
              fontWeight: "bold",
              color: cl.color,
              fontFamily: FF,
              opacity: cl.opacity,
              lineHeight: 1,
              ...(cl.variant === 0 ? { WebkitTextStroke: `5px ${cl.color}`, color: "transparent" } : {}),
            }}>
              {cl.ch}
            </span>
          </div>
        ))}

        {/* 5. Main hero label block */}
        <div style={{ position: "absolute", left: labelX, top: labelY, display: "flex" }}>
          {renderLabelHero(categoryLabel, palette.fg, accentColor, palette.bg, FF, labelVariant, rand)}
        </div>

        <div
          style={{
            position: "absolute",
            left: objectX,
            top: objectY,
            transform: `rotate(${objectRot}deg)`,
            transformOrigin: "center",
            display: "flex",
            filter: "drop-shadow(18px 18px 0 rgba(58,38,31,0.22))",
          }}
        >
          <svg viewBox="0 0 100 100" width={objectSize} height={objectSize}>
            {renderHeroObject(heroObjectKey, palette.fg, accentColor, palette.bg, objectVariant)}
          </svg>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fontData ? [{ name: fontName, data: fontData, weight: 700, style: "normal" }] : [],
    }
  );
}
