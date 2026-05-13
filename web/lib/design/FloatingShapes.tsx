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
}

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function newFloater(slotIdx: number, prev?: Floater): Floater {
  const tierIdx = Math.floor(slotIdx / 2);
  const tier = TIERS[tierIdx];
  const [minPx, maxPx, minSec, maxSec] = tier;
  const size = Math.round(minPx + Math.random() * (maxPx - minPx));
  const duration = Math.round(minSec + Math.random() * (maxSec - minSec));
  // For the first paint, stagger the second floater in each pair by half-cycle.
  const initialPhase = prev ? 0 : (slotIdx % 2 === 1 ? duration / 2 : 0);
  const fill = pick(FILLS);
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
    delay: -Math.round(initialPhase),
    drift: pick(DRIFTS),
    opacity: 0.18 + Math.random() * 0.22,
    rotation: Math.round(Math.random() * 360),
    patternRotation: Math.round(Math.random() * 90) - 45,
    bump: prev ? prev.bump + 1 : 0,
  };
}

// ----- Render --------------------------------------------------------------
function FloaterView({ slotIdx, f, onCycle }: { slotIdx: number; f: Floater; onCycle: () => void }) {
  const { tag, attrs } = shapePath(f.shape);
  const patternId = `pat-${slotIdx}-${f.bump}`;
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

  return (
    <svg
      className="absolute"
      style={{
        top: 0,
        left: 0,
        width: f.size,
        height: f.size,
        opacity: f.opacity,
        animation: `${f.drift} ${f.duration}s linear infinite`,
        animationDelay: `${f.delay}s`,
      }}
      viewBox="0 0 100 100"
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

const TOTAL_SLOTS = TIERS.length * 2; // 10

export function FloatingShapes() {
  // null until mounted → avoids SSR hydration mismatch (Math.random is client-only).
  const [floaters, setFloaters] = useState<Floater[] | null>(null);

  useEffect(() => {
    setFloaters(Array.from({ length: TOTAL_SLOTS }, (_, i) => newFloater(i)));
  }, []);

  if (!floaters) return null;

  const handleCycle = (slotIdx: number) => {
    setFloaters((curr) => {
      if (!curr) return curr;
      const next = curr.slice();
      next[slotIdx] = newFloater(slotIdx, curr[slotIdx]);
      return next;
    });
  };

  return (
    <div aria-hidden className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      {floaters.map((f, i) => (
        <FloaterView
          key={`${i}-${f.bump}`}
          slotIdx={i}
          f={f}
          onCycle={() => handleCycle(i)}
        />
      ))}
    </div>
  );
}
