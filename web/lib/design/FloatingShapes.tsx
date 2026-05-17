"use client";

/**
 * FloatingShapes — Bauhaus background for /design.
 *
 * Rules:
 *   - At any moment, ONLY 10 floaters are on screen (2 per size tier × 5 tiers).
 *   - Each floater is drawn from a pool of ~3,888 procedural combos:
 *       9 shapes × 9 fills × 6 colors × 8 drift directions × shape rotation.
 *   - When a floater finishes one drift cycle, it is replaced by a fresh
 *     random pick from the pool — so the rotation never repeats visibly.
 *   - Pairs in the same tier are staggered by half-cycle so they never collide.
 */

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

// ----- Palette + drift ------------------------------------------------------
// Only the two brand accent colors, used at low opacity for a soft pastel field.
const COLORS = ["#E84860", "#C4E86F"];
const DRIFTS = [
  "drift-tl-br", "drift-tr-bl", "drift-bl-tr", "drift-br-tl",
  "drift-l-r", "drift-r-l", "drift-t-b", "drift-b-t",
];

// Tier: [minPx, maxPx, minSec, maxSec]
// 2 floaters per tier × 5 tiers = 10 on screen.
const TIERS: [number, number, number, number][] = [
  [40, 75, 8, 12],
  [110, 150, 16, 24],
  [200, 290, 32, 48],
  [380, 460, 60, 85],
  [560, 700, 95, 130],
];

const SPRITE_PADDING_RATIO = 0.2;
const SPRITE_VIEWBOX_PAD = 20;
const SPRITE_VIEWBOX_SIZE = 100 + SPRITE_VIEWBOX_PAD * 2;

// ----- Shapes ---------------------------------------------------------------
type ShapeKind =
  | "triangle" | "pentagon" | "hexagon" | "star8" | "star10"
  | "sector" | "halfCircle" | "circle" | "diamond";

const SHAPES: ShapeKind[] = ["triangle", "pentagon", "hexagon", "star8", "star10", "sector", "halfCircle", "circle", "diamond"];

function shapePath(kind: ShapeKind): { tag: "polygon" | "path" | "circle"; attrs: Record<string, string | number> } {
  switch (kind) {
    case "triangle":   return { tag: "polygon", attrs: { points: "50,8 92,92 8,92" } };
    case "pentagon":   return { tag: "polygon", attrs: { points: "50,6 95,38 78,93 22,93 5,38" } };
    case "hexagon":    return { tag: "polygon", attrs: { points: "50,5 90,27 90,73 50,95 10,73 10,27" } };
    case "star8":      return { tag: "polygon", attrs: { points: "50,8 60,40 92,50 60,60 50,92 40,60 8,50 40,40" } };
    case "star10":     return { tag: "polygon", attrs: { points: "50,4 58,36 92,40 66,58 76,92 50,72 24,92 34,58 8,40 42,36" } };
    case "sector":     return { tag: "path", attrs: { d: "M 50 50 L 50 5 A 45 45 0 0 1 88 70 Z" } };
    case "halfCircle": return { tag: "path", attrs: { d: "M 50 0 A 50 50 0 0 1 50 100 Z" } };
    case "diamond":    return { tag: "polygon", attrs: { points: "50,5 92,50 50,95 8,50" } };
    case "circle":
    default:           return { tag: "circle", attrs: { cx: 50, cy: 50, r: 46 } };
  }
}

// ----- Fills ----------------------------------------------------------------
type FillKind = "solid" | "outlineThin" | "outlineThick" | "dashed" | "dotsDense" | "dotsSparse" | "stripes" | "hatch" | "grid";
const FILLS: FillKind[] = ["solid", "outlineThin", "outlineThick", "dashed", "dotsDense", "dotsSparse", "stripes", "hatch", "grid"];

function PatternDef({ id, fill, color, rotation }: { id: string; fill: FillKind; color: string; rotation: number }) {
  const t = `rotate(${rotation})`;
  switch (fill) {
    case "dotsDense":
      return (
        <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform={t}>
          <circle cx="3" cy="3" r="1.6" fill={color} />
        </pattern>
      );
    case "dotsSparse":
      return (
        <pattern id={id} width="11" height="11" patternUnits="userSpaceOnUse" patternTransform={t}>
          <circle cx="5.5" cy="5.5" r="1.4" fill={color} />
        </pattern>
      );
    case "stripes":
      return (
        <pattern id={id} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform={t}>
          <line x1="0" y1="0" x2="0" y2="7" stroke={color} strokeWidth="2.4" />
        </pattern>
      );
    case "hatch":
      return (
        <pattern id={id} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform={`rotate(${rotation + 45})`}>
          <line x1="0" y1="0" x2="0" y2="9" stroke={color} strokeWidth="2" />
        </pattern>
      );
    case "grid":
      return (
        <pattern id={id} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform={t}>
          <path d="M 10 0 L 0 0 0 10" fill="none" stroke={color} strokeWidth="1.2" />
        </pattern>
      );
    default:
      return null;
  }
}

// ----- One floater ----------------------------------------------------------
interface Floater {
  shape: ShapeKind;
  fill: FillKind;
  color: string;
  size: number;
  duration: number;
  delay: number;
  drift: string;
  opacity: number;
  rotation: number;
  patternRotation: number;
  bump: number;
  tierIdx: number;
}

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function newFloater(tierIdx: number, prev?: Floater, fillCounts?: Record<string, number>, forceSolid?: boolean): Floater {
  const tier = TIERS[tierIdx];
  const [minPx, maxPx, minSec, maxSec] = tier;
  const size = Math.round(minPx + Math.random() * (maxPx - minPx));
  const duration = Math.round(minSec + Math.random() * (maxSec - minSec));
  // Initial-paint phase: a tiny 0–5% forward offset only. We deliberately do NOT
  // half-cycle stagger pair partners — a half-cycle delay drops them mid-journey
  // at full opacity, which on a narrow mobile viewport looks like the shape
  // "popping into view at the center of the screen" instead of drifting in from
  // an edge. Subsequent cycles (prev defined) always start at phase 0.
  const initialPhase = prev ? 0 : Math.random() * duration * 0.05;
  // Max 2 floaters may share the same fill kind simultaneously.
  // forceSolid overrides the diversity filter to guarantee at least 1 solid on screen.
  const fill: FillKind = forceSolid
    ? "solid"
    : (() => {
        const available = fillCounts
          ? FILLS.filter((f) => (fillCounts[f] ?? 0) < 2)
          : FILLS;
        return pick(available.length > 0 ? available : FILLS);
      })();
  // Solid pink (#E84860) is reserved for the two smallest tiers (0 & 1) so the
  // largest shapes never become heavy red blocks. Non-solid (outline/pattern)
  // fills may use pink at any size since they read as airy.
  const isSmallTier = tierIdx <= 1;
  const color = fill === "solid" && !isSmallTier ? "#C4E86F" : pick(COLORS);
  return {
    shape: pick(SHAPES),
    fill,
    color,
    size,
    duration,
    delay: -Math.round(initialPhase * 10) / 10,
    drift: pick(DRIFTS),
    opacity: 0.18 + Math.random() * 0.22,
    rotation: Math.round(Math.random() * 360),
    patternRotation: Math.round(Math.random() * 90) - 45,
    bump: prev ? prev.bump + 1 : 0,
    tierIdx,
  };
}

// ----- Render --------------------------------------------------------------
function FloaterView({ slotIdx, f, scale, onCycle }: { slotIdx: number; f: Floater; scale: number; onCycle: () => void }) {
  const { tag, attrs } = shapePath(f.shape);
  const patternId = `pat-${slotIdx}-${f.bump}`;
  const renderSize = f.size * scale;
  const spritePadding = renderSize * SPRITE_PADDING_RATIO;
  const spriteSize = renderSize + spritePadding * 2;
  const isPattern = ["dotsDense", "dotsSparse", "stripes", "hatch", "grid"].includes(f.fill);
  const isOutline = f.fill === "outlineThin" || f.fill === "outlineThick" || f.fill === "dashed";
  const strokeWidth = f.fill === "outlineThin" ? 1.4 : f.fill === "dashed" ? 2.4 : 3.2;

  let shapeFill: string = f.color;
  let shapeStroke: string = "none";
  let strokeDash: string | undefined;
  if (isPattern) {
    shapeFill = `url(#${patternId})`;
  } else if (isOutline) {
    shapeFill = "none";
    shapeStroke = f.color;
    if (f.fill === "dashed") strokeDash = "6 4";
  }

  const shapeProps: Record<string, string | number> = {
    ...attrs,
    fill: shapeFill,
    stroke: shapeStroke,
  };
  if (isOutline) shapeProps.strokeWidth = strokeWidth;
  if (strokeDash) shapeProps.strokeDasharray = strokeDash;

  // Scale animation duration with viewport so the perceived linear velocity
  // (px/sec) stays roughly constant between desktop (~1100px) and mobile
  // (~390px). Without this, durations stay 12–130s while the drift distance
  // shrinks proportionally — mobile shapes appear to crawl. Scale the delay
  // by the same factor to preserve the keyframe phase.
  const animDuration = Math.max(2, f.duration * scale);
  const animDelay = f.delay * scale;
  const style = {
    top: 0,
    left: 0,
    width: spriteSize,
    height: spriteSize,
    opacity: f.opacity,
    animation: `${f.drift} ${animDuration.toFixed(1)}s linear infinite`,
    animationDelay: `${animDelay.toFixed(1)}s`,
    "--x-min": `${-spritePadding}px`,
    "--y-min": `${-spritePadding}px`,
    "--x-mid": `calc((100svw - ${renderSize}px) / 2 - ${spritePadding}px)`,
    "--y-mid": `calc((100svh - ${renderSize}px) / 2 - ${spritePadding}px)`,
    "--x-max": `calc(100svw - ${renderSize}px - ${spritePadding}px)`,
    "--y-max": `calc(100svh - ${renderSize}px - ${spritePadding}px)`,
  } as CSSProperties;

  return (
    <svg
      className="absolute"
      style={style}
      viewBox={`${-SPRITE_VIEWBOX_PAD} ${-SPRITE_VIEWBOX_PAD} ${SPRITE_VIEWBOX_SIZE} ${SPRITE_VIEWBOX_SIZE}`}
      onAnimationIteration={onCycle}
    >
      {isPattern && (
        <defs>
          <PatternDef id={patternId} fill={f.fill} color={f.color} rotation={f.patternRotation} />
        </defs>
      )}
      <g transform={`rotate(${f.rotation} 50 50)`}>
        {tag === "polygon" && <polygon {...(shapeProps as React.SVGProps<SVGPolygonElement>)} />}
        {tag === "path" && <path {...(shapeProps as React.SVGProps<SVGPathElement>)} />}
        {tag === "circle" && <circle {...(shapeProps as React.SVGProps<SVGCircleElement>)} />}
      </g>
    </svg>
  );
}

const FULL_SLOTS = TIERS.length * 2; // 10

export interface FloatingShapesProps {
  /**
   * `full` (default) — the original homepage / design-page background:
   *   10 slots, 2 per tier, solid-fill guarantee, paired layout.
   * `subtle` — lightweight variant for inner pages:
   *   only the two smallest tiers (sizes 40–150px), random 2–6 floaters,
   *   no solid-fill guarantee. Easy on the eyes inside event lists / details.
   */
  variant?: "full" | "subtle";
}

export function FloatingShapes({ variant = "full" }: FloatingShapesProps = {}) {
  // null until mounted → avoids SSR hydration mismatch (Math.random is client-only).
  const [floaters, setFloaters] = useState<Floater[] | null>(null);
  // Viewport-responsive scale: largest tier is 700px, baseline viewport 1100px.
  // On mobile (~390px) this clamps the largest shape to ~248px so the
  // animation no longer feels brutally cropped.
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const computeScale = () => {
      const vw = window.innerWidth;
      // Below 1100px viewport, shrink proportionally; min 0.35.
      setScale(Math.max(0.35, Math.min(1, vw / 1100)));
    };
    computeScale();
    window.addEventListener("resize", computeScale);
    return () => window.removeEventListener("resize", computeScale);
  }, []);

  useEffect(() => {
    const initial: Floater[] = [];
    if (variant === "subtle") {
      // Inner pages: random 2–6 floaters, drawn from the two smallest tiers only.
      const count = 2 + Math.floor(Math.random() * 5); // 2..6
      for (let i = 0; i < count; i++) {
        const tierIdx = Math.random() < 0.5 ? 0 : 1;
        initial.push(newFloater(tierIdx, undefined, undefined, false));
      }
    } else {
      // Full background: build incrementally so each new floater sees fills already committed.
      for (let i = 0; i < FULL_SLOTS; i++) {
        const counts: Record<string, number> = {};
        for (const f of initial) counts[f.fill] = (counts[f.fill] ?? 0) + 1;
        const mustSolid = i === FULL_SLOTS - 1 && !initial.some((f) => f.fill === "solid");
        const tierIdx = Math.floor(i / 2);
        initial.push(newFloater(tierIdx, undefined, mustSolid ? { ...counts, solid: 0 } : counts, mustSolid));
      }
    }
    setFloaters(initial);
  }, [variant]);

  if (!floaters) return null;

  const handleCycle = (slotIdx: number) => {
    setFloaters((curr) => {
      if (!curr) return curr;
      const prev = curr[slotIdx];
      const next = curr.slice();
      if (variant === "subtle") {
        // Re-roll tier randomly between the two smallest tiers; no solid enforcement.
        const tierIdx = Math.random() < 0.5 ? 0 : 1;
        next[slotIdx] = newFloater(tierIdx, prev, undefined, false);
      } else {
        const counts: Record<string, number> = {};
        for (let i = 0; i < curr.length; i++) {
          if (i === slotIdx) continue;
          counts[curr[i].fill] = (counts[curr[i].fill] ?? 0) + 1;
        }
        const mustSolid = (counts["solid"] ?? 0) === 0;
        next[slotIdx] = newFloater(prev.tierIdx, prev, mustSolid ? { ...counts, solid: 0 } : counts, mustSolid);
      }
      return next;
    });
  };

  // Subtle variant: lighter base opacity so inner-page content stays the focus.
  const wrapperOpacity = variant === "subtle" ? "opacity-25" : "opacity-40";

  return (
    <div
      aria-hidden
      className={`fixed inset-0 -z-10 overflow-hidden pointer-events-none ${wrapperOpacity}`}
    >
      {floaters.map((f, i) => (
        <FloaterView
          key={`${i}-${f.bump}`}
          slotIdx={i}
          f={f}
          scale={scale}
          onCycle={() => handleCycle(i)}
        />
      ))}
    </div>
  );
}
