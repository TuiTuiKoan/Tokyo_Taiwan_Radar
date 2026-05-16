/**
 * MascotAvatar — wax-apple radar mascot in multiple presentations.
 *
 * Variants:
 *  - "inline": just the mascot, transparent background. Default. Use for
 *    navbar logos, hero illustrations, slide accents.
 *  - "framed": mascot inside a Bauhaus-decorated card (matches SNS avatar).
 *    Use for profile images, OG cards, large hero blocks.
 *
 * Shape:
 *  - "square" | "circle" — applies to "framed" only. Circle is for
 *    Twitter/LINE profile, square for Instagram post / OG cards.
 *
 * The mascot SVG is also available standalone via <DesignDefs /> + <use href="#waxMascot" />,
 * which avoids duplicating the path data when multiple instances appear on one page.
 */
import { mascot as mascotTokens } from "./tokens";
import { useId } from "react";

type Variant = "inline" | "framed";
type Shape = "square" | "circle";

export interface MascotAvatarProps {
  /** Render mode. `inline` = bare mascot, `framed` = with Bauhaus background. */
  variant?: Variant;
  /** Frame shape; only applies when variant="framed". */
  shape?: Shape;
  /** Pixel size of the rendered square. Default 64. */
  size?: number;
  /** Disable the 3° rightward tilt (for symmetrical logo uses). */
  upright?: boolean;
  /** Optional className passed to the root <svg>. */
  className?: string;
  /** Accessible label; defaults to "Tokyo Taiwan Radar mascot". */
  title?: string;
  /** Bright yellow-white flow that travels along antenna into the body. */
  antennaFlowAnimation?: boolean;
}

function MascotBody({
  upright,
  antennaFlowAnimation,
  flowGradientId,
  flowGlowId,
  tipRingGradientId,
}: {
  upright?: boolean;
  antennaFlowAnimation?: boolean;
  flowGradientId?: string;
  flowGlowId?: string;
  tipRingGradientId?: string;
}) {
  const rotate = upright ? 0 : mascotTokens.tilt;
  const antennaPath = "M100,80 C110,30 60,0 80,20 C100,40 140,50 160,30";
  const antennaPathReverse = "M160,30 C140,50 100,40 80,20 C60,0 110,30 100,80";
  const bodyPath =
    "M100,80 C 86,80 78,88 74,98 C 72,108 66,116 60,128 C 46,146 30,166 36,190 C 44,210 72,216 102,216 C 132,216 160,210 164,190 C 170,166 154,146 140,128 C 134,116 128,108 126,98 C 122,88 114,80 100,80 Z";

  return (
    <g transform={`rotate(${rotate} 100 150)`}>
      <path
        d={antennaPath}
        fill="none"
        stroke="#1F5E2B"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      {antennaFlowAnimation && flowGradientId && flowGlowId && (
        <>
          <path
            className="lianbu-antenna-flow-line"
            d={antennaPathReverse}
            fill="none"
            stroke={`url(#${flowGradientId})`}
            strokeWidth="3.6"
            strokeLinecap="round"
            opacity={0}
            visibility="hidden"
          />
          <circle
            className="lianbu-antenna-flow-dot"
            cx="100"
            cy="80"
            r="4.2"
            fill="#FFFFFF"
            filter={`url(#${flowGlowId})`}
            opacity={0}
            visibility="hidden"
          >
            <animateMotion
              dur="12s"
              repeatCount="indefinite"
              rotate="auto"
              path={antennaPathReverse}
              keyTimes="0;0.17;0.22;1"
              keyPoints="0;0;1;1"
              calcMode="linear"
            />
          </circle>
        </>
      )}
      <g>
        {/* Static thin stroke circle — always visible regardless of animation state */}
        <circle cx="164" cy="26" r="11" fill="none" stroke="#1F5E2B" strokeWidth="1.4" opacity="0.4" />
        {/* Animated gradient ring — flashes via SMIL <animate> (Safari does not animate CSS `r` property) */}
        {tipRingGradientId && (
          <circle className="lianbu-tip-ring" cx="164" cy="26" r="11" fill={`url(#${tipRingGradientId})`} opacity={0}>
            <animate
              attributeName="r"
              values="11;64;64;11;11"
              keyTimes="0;0.07;0.17;0.18;1"
              dur="12s"
              repeatCount="indefinite"
              calcMode="linear"
            />
            <animate
              attributeName="opacity"
              values="0;0.95;0;0;0"
              keyTimes="0;0.07;0.17;0.18;1"
              dur="12s"
              repeatCount="indefinite"
              calcMode="linear"
            />
          </circle>
        )}
        <circle className="lianbu-tip-core" cx="164" cy="26" r="6" fill="#1F5E2B" />
        <circle className="lianbu-tip-spark" cx="164" cy="26" r="2.2" fill="#C4E86F" />
      </g>
      <path
        d={bodyPath}
        fill="#E84860"
      />
      <ellipse cx="58" cy="142" rx="13.3" ry="8" fill="#FF7AA0" opacity="0.65" transform="rotate(-10 58 142)" />
      <ellipse cx="146" cy="150" rx="12" ry="6.5" fill="#FF7AA0" opacity="0.75" transform="rotate(12 146 150)" />
      <ellipse cx="80" cy="116" rx="13" ry="14" fill="white" />
      <circle cx="78" cy="118" r="7" fill="#1A1818" />
      <circle cx="75" cy="115" r="2.6" fill="white" />
      <path
        d="M116,128 Q124,118 132,128"
        fill="none"
        stroke="#1A1818"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
    </g>
  );
}

export function MascotAvatar({
  variant = "inline",
  shape = "square",
  size = 64,
  upright = false,
  className,
  title = "Tokyo Taiwan Radar mascot",
  antennaFlowAnimation = false,
}: MascotAvatarProps) {
  const baseId = useId().replace(/:/g, "");
  const flowGradientId = `${baseId}-antenna-flow-gradient`;
  const flowGlowId = `${baseId}-antenna-flow-glow`;
  const tipRingGradientId = `${baseId}-antenna-tip-ring-gradient`;

  if (variant === "inline") {
    // Expand viewBox when antenna flow is on so the SMIL-animated tip ring
    // (peak r=64 at the upper-right tip) is fully contained inside the SVG's own
    // CSS box. Avoids relying on `overflow="visible"`, which iOS Safari clips
    // when parent containers have `overflow: hidden` / transforms.
    const inlineViewBox = antennaFlowAnimation ? "0 -50 250 270" : mascotTokens.viewBox;
    return (
      <svg
        viewBox={inlineViewBox}
        width={size}
        height={size}
        className={className}
        role="img"
        aria-label={title}
        data-antenna-flow={antennaFlowAnimation ? "on" : "off"}
        overflow={antennaFlowAnimation ? "visible" : undefined}
      >
        <title>{title}</title>
        {antennaFlowAnimation && (
          <defs>
            <linearGradient id={flowGradientId} x1="160" y1="30" x2="100" y2="80" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#FAEAB0" stopOpacity="1" />
              <stop offset="50%" stopColor="#C4E86F" stopOpacity="1" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="1" />
            </linearGradient>
            {/* Gradient r matches SMIL peak (r=64) so the glow scales correctly.
                Edge fades to transparent (not white) so it's visible on light backgrounds too. */}
            <radialGradient id={tipRingGradientId} cx="164" cy="26" r="64" gradientUnits="userSpaceOnUse">
              <stop offset="0%"   stopColor="#C4E86F" stopOpacity="0.95" /> {/* leaf-green center */}
              <stop offset="50%"  stopColor="#FFD700" stopOpacity="0.6"  /> {/* yellow mid */}
              <stop offset="100%" stopColor="#A8D840" stopOpacity="0"    /> {/* fade to transparent */}
            </radialGradient>
            <filter id={flowGlowId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3.4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
        )}
        <MascotBody
          upright={upright}
          antennaFlowAnimation={antennaFlowAnimation}
          flowGradientId={flowGradientId}
          flowGlowId={flowGlowId}
          tipRingGradientId={antennaFlowAnimation ? tipRingGradientId : undefined}
        />
      </svg>
    );
  }

  // framed: Bauhaus background + decorative shapes + mascot
  // Locally-scoped pattern IDs so multiple framed avatars on one page don't collide.
  const uid = `m${baseId}`;
  const id = (key: string) => `${uid}-${key}`;

  return (
    <svg
      viewBox="0 0 1024 1024"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <linearGradient id={id("bg")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFFDF5" />
          <stop offset="58%" stopColor="#FFF1EE" />
          <stop offset="100%" stopColor="#F7FFE8" />
        </linearGradient>
        <radialGradient id={id("vig")} cx="0.5" cy="0.4" r="0.7">
          <stop offset="0%" stopColor="#FFFDF5" stopOpacity="0" />
          <stop offset="100%" stopColor="#D85862" stopOpacity="0.15" />
        </radialGradient>
        <pattern id={id("grid")} width="48" height="48" patternUnits="userSpaceOnUse">
          <path d="M48,0 L0,0 L0,48" fill="none" stroke="#F56A82" strokeWidth="2.2" opacity="0.18" />
        </pattern>
        <pattern id={id("htPink")} width="20" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(15)">
          <circle cx="5" cy="5" r="5.5" fill="#F56A82" opacity="0.75" />
        </pattern>
        <pattern id={id("htGreen")} width="20" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <circle cx="5" cy="5" r="5.5" fill="#78B94E" opacity="0.55" />
        </pattern>
        <pattern id={id("stripes")} width="32" height="32" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="16" height="32" fill="#F56A82" opacity="0.7" />
          <rect x="16" width="16" height="32" fill="#FFFDF5" />
        </pattern>
        {shape === "circle" && (
          <clipPath id={id("clip")}>
            <circle cx="512" cy="512" r="512" />
          </clipPath>
        )}
      </defs>

      <g clipPath={shape === "circle" ? `url(#${id("clip")})` : undefined}>
        <rect width="1024" height="1024" fill={`url(#${id("bg")})`} />
        <rect width="1024" height="1024" fill={`url(#${id("grid")})`} />
        {/* Bauhaus decorative shapes (matches Hero) */}
        <path d="M1024,80 A260,260 0 0,1 1024,600 L1024,80 Z" fill={`url(#${id("htPink")})`} opacity="0.78" />
        <polygon points="640,40 950,10 990,250 680,290" fill={`url(#${id("stripes")})`} opacity="0.78" />
        <path d="M0,640 A220,220 0 0,1 440,640 L440,820 L0,820 Z" fill={`url(#${id("htGreen")})`} opacity="0.7" />
        <polygon points="60,500 380,460 430,610 80,650" fill={`url(#${id("htGreen")})`} opacity="0.55" />
        <rect x="700" y="780" width="380" height="60" fill={`url(#${id("stripes")})`} transform="rotate(-12 890 810)" opacity="0.85" />
        <polygon points="880,650 980,610 990,720" fill="#78B94E" opacity="0.5" />
        <path d="M0,40 A140,140 0 0,1 280,40 L280,180 L0,180 Z" fill="#C4E86F" opacity="0.55" />
        <polygon points="40,240 200,200 230,320 60,340" fill={`url(#${id("htPink")})`} opacity="0.45" />
        <rect width="1024" height="1024" fill={`url(#${id("vig")})`} />

        {/* Mascot (scaled into frame) */}
        <svg x="232" y="160" width="560" height="616" viewBox={mascotTokens.viewBox}>
          <MascotBody upright={upright} />
        </svg>

        {shape === "circle" && (
          <circle cx="512" cy="512" r="504" fill="none" stroke="#3A261F" strokeWidth="8" opacity="0.15" />
        )}
      </g>
    </svg>
  );
}
