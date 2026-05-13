/**
 * Shared SVG <defs> — patterns, gradients, mascot symbols.
 *
 * Drop <DesignDefs /> once near the root of any page that uses the design
 * library and reference them by id (`fill="url(#halftonePink)"`).
 *
 * IDs are globally unique to the document so multiple instances are safe
 * (React de-dups). All pattern IDs match the keys in `tokens.color.patterns`.
 */
import { mascot as mascotTokens } from "./tokens";

export function DesignDefs() {
  return (
    <svg
      aria-hidden="true"
      width="0"
      height="0"
      style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }}
    >
      <defs>
        {/* Gradients */}
        <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFFDF5" />
          <stop offset="58%" stopColor="#FFF1EE" />
          <stop offset="100%" stopColor="#F7FFE8" />
        </linearGradient>
        <linearGradient id="ctaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F47A86" />
          <stop offset="100%" stopColor="#D85862" />
        </linearGradient>

        {/* Halftone & textures */}
        <pattern
          id="halftonePink"
          width="8"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(15)"
        >
          <circle cx="2" cy="2" r="2.5" fill="#F56A82" opacity="0.8" />
        </pattern>
        <pattern
          id="halftoneGreen"
          width="8"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <circle cx="2" cy="2" r="2.5" fill="#78B94E" opacity="0.6" />
        </pattern>
        <pattern
          id="wavyLinesGreen"
          width="16"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(-10)"
        >
          <path
            d="M0,4 Q4,0 8,4 T16,4"
            fill="none"
            stroke="#78B94E"
            strokeWidth="2.5"
            opacity="0.8"
          />
        </pattern>
        <pattern
          id="wavyLinesPink"
          width="16"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(6)"
        >
          <path
            d="M0,4 Q4,0 8,4 T16,4"
            fill="none"
            stroke="#F56A82"
            strokeWidth="2.2"
            opacity="0.7"
          />
        </pattern>
        <pattern
          id="diagStripes"
          width="14"
          height="14"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <rect width="7" height="14" fill="#F56A82" opacity="0.75" />
          <rect x="7" width="7" height="14" fill="#FFFDF5" />
        </pattern>
        <pattern id="gridPink" width="20" height="20" patternUnits="userSpaceOnUse">
          <path
            d="M20,0 L0,0 L0,20"
            fill="none"
            stroke="#F56A82"
            strokeWidth="1.6"
            opacity="0.25"
          />
        </pattern>
        {/* Chevron / herringbone (山形千鳥) */}
        <pattern
          id="chevronPink"
          width="16"
          height="10"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(0)"
        >
          <path
            d="M0,10 L4,2 L8,10 L12,2 L16,10"
            fill="none"
            stroke="#F56A82"
            strokeWidth="1.6"
            strokeLinejoin="round"
            opacity="0.55"
          />
        </pattern>
        <pattern
          id="chevronGreen"
          width="16"
          height="10"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M0,10 L4,2 L8,10 L12,2 L16,10"
            fill="none"
            stroke="#78B94E"
            strokeWidth="1.6"
            strokeLinejoin="round"
            opacity="0.5"
          />
        </pattern>

        {/* Mascot symbol — referenced via <use href="#waxMascot" /> */}
        <symbol id="waxMascot" viewBox={mascotTokens.viewBox}>
          <g transform={`rotate(${mascotTokens.tilt} 100 150)`}>
            {/* Radar antenna */}
            <path
              d="M100,80 C110,30 60,0 80,20 C100,40 140,50 160,30"
              fill="none"
              stroke="#1F5E2B"
              strokeWidth="4.5"
              strokeLinecap="round"
            />
            <circle
              cx="164"
              cy="26"
              r="11"
              fill="none"
              stroke="#1F5E2B"
              strokeWidth="1.4"
              opacity="0.4"
            />
            <circle cx="164" cy="26" r="6" fill="#1F5E2B" />
            <circle cx="164" cy="26" r="2.2" fill="#C4E86F" />

            {/* Body */}
            <path
              d="M100,80 C 86,80 78,88 74,98 C 72,108 66,116 60,128 C 46,146 30,166 36,190 C 44,210 72,216 102,216 C 132,216 160,210 164,190 C 170,166 154,146 140,128 C 134,116 128,108 126,98 C 122,88 114,80 100,80 Z"
              fill="#E84860"
            />

            {/* Asymmetric cheeks */}
            <ellipse
              cx="58"
              cy="142"
              rx="13.3"
              ry="8"
              fill="#FF7AA0"
              opacity="0.65"
              transform="rotate(-10 58 142)"
            />
            <ellipse
              cx="146"
              cy="150"
              rx="12"
              ry="6.5"
              fill="#FF7AA0"
              opacity="0.75"
              transform="rotate(12 146 150)"
            />

            {/* Eyes — left wide open, right winking smile */}
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
        </symbol>
      </defs>
    </svg>
  );
}
