import type { Announcement, Locale } from "@/lib/types";
import Link from "next/link";
import Image from "next/image";

interface Props {
  announcement: Announcement;
  locale: Locale;
}

// Deterministic FNV-1a hash → pick a pattern color slot from the brand palette.
function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}

const PATTERN_COLORS = ["#E84860", "#C4E86F", "#1F5E2B", "#3A261F"];

export default function AnnouncementCard({ announcement, locale }: Props) {
  const title =
    announcement[`title_${locale}`] ??
    announcement.title_zh ??
    announcement.title_ja ??
    announcement.title_en ??
    "";

  const image =
    announcement[`image_${locale}`] ??
    announcement.cover_image_url ??
    null;

  // Kicker: numeric date in YYYY.MM.DD, locale-neutral.
  const kicker = announcement.published_at
    ? (() => {
        const d = new Date(announcement.published_at);
        const y = d.getUTCFullYear();
        const m = String(d.getUTCMonth() + 1).padStart(2, "0");
        const dd = String(d.getUTCDate()).padStart(2, "0");
        return `${y}.${m}.${dd}`;
      })()
    : null;

  const seed = hashString(announcement.id ?? announcement.slug ?? title);
  const patternColor = PATTERN_COLORS[seed % PATTERN_COLORS.length];
  const patternVariant = (seed >>> 4) % 3; // 0: dots, 1: stripes, 2: grid
  const patternId = `ann-pat-${announcement.id ?? announcement.slug}`;

  return (
    <Link
      href={`/${locale}/announcements/${announcement.slug}`}
      className="group relative flex shrink-0 w-[260px] overflow-hidden rounded-xl border border-line/70 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition"
      style={{ background: "linear-gradient(135deg, #FFF6D1 0%, #FFE9A8 100%)" }}
      data-preserve-theme="light"
    >
      {/* Left thumbnail — square, full-bleed cover */}
      {image && (
        <div className="relative z-20 shrink-0 aspect-square w-16 sm:w-20 self-stretch overflow-hidden bg-paper/60">
          <Image
            src={image}
            alt={title}
            fill
            sizes="(max-width: 768px) 64px, 80px"
            className="object-cover group-hover:scale-105 transition duration-300"
            unoptimized
          />
        </div>
      )}

      {/* Right content area — date badge + title */}
      <div className="relative flex-1 min-w-0 px-3 py-2 flex flex-col justify-center gap-1">
        {/* Decorative top-right pattern swatch */}
        <svg
          aria-hidden
          className="absolute top-0 right-0 h-7 w-14 opacity-60 pointer-events-none"
        >
          <defs>
            {patternVariant === 0 && (
              <pattern id={patternId} x="0" y="0" width="8" height="8" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1.2" fill={patternColor} />
              </pattern>
            )}
            {patternVariant === 1 && (
              <pattern id={patternId} x="0" y="0" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
                <rect width="2" height="6" fill={patternColor} />
              </pattern>
            )}
            {patternVariant === 2 && (
              <pattern id={patternId} x="0" y="0" width="8" height="8" patternUnits="userSpaceOnUse">
                <path d="M0 0L8 0M0 0L0 8" stroke={patternColor} strokeWidth="1" fill="none" />
              </pattern>
            )}
          </defs>
          <rect width="100%" height="100%" fill={`url(#${patternId})`} />
        </svg>

        {kicker && (
          <div
            className="relative inline-block self-start px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-widest rounded-sm bg-paper"
            style={{ color: "#3A261F" }}
          >
            {kicker}
            {announcement.is_featured && (
              <span className="ml-1 text-mascot-red">●</span>
            )}
          </div>
        )}
        <h2 className="relative font-display font-bold text-[#3A261F] text-[12px] sm:text-[13px] leading-snug line-clamp-2 group-hover:text-green-800 transition-colors">
          {title}
        </h2>
      </div>
    </Link>
  );
}

