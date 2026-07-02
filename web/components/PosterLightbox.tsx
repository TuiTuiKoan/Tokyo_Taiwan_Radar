"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { IconButton } from "@/components/UiControls";

interface Props {
  src: string;
  alt?: string;
  onClose: () => void;
}

const MIN_SCALE = 1;
const MAX_SCALE = 5;
const STEP = 0.5;
const TAP_MS = 300;
const TAP_SLOP = 30;
const MOVE_SLOP = 10;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Fullscreen poster viewer with zoom + pan. Desktop: wheel zoom, +/-/reset
 * controls, double-click toggle. Mobile: pinch-to-zoom, single-finger pan,
 * double-tap toggle (unified via Pointer Events). Controls reuse the shared
 * IconButton design-system component (44px touch targets, focus ring, aria).
 */
export default function PosterLightbox({ src, alt, onClose }: Props) {
  const t = useTranslations("eventIntake");
  const [mounted, setMounted] = useState(false);
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [animating, setAnimating] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const pointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const pinchRef = useRef<{ dist: number; scale: number } | null>(null);
  const panRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const movedRef = useRef(false);
  const lastTapRef = useRef<{ time: number; x: number; y: number } | null>(null);

  useEffect(() => setMounted(true), []);

  // ESC closes the viewer.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Lock background scroll while open.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const maxTranslate = useCallback((s: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const w = rect?.width ?? 0;
    const h = rect?.height ?? 0;
    return { x: ((s - 1) * w) / 2, y: ((s - 1) * h) / 2 };
  }, []);

  const applyScale = useCallback(
    (nextScale: number) => {
      const s = clamp(nextScale, MIN_SCALE, MAX_SCALE);
      const m = maxTranslate(s);
      setScale(s);
      setTx((x) => (s === 1 ? 0 : clamp(x, -m.x, m.x)));
      setTy((y) => (s === 1 ? 0 : clamp(y, -m.y, m.y)));
    },
    [maxTranslate],
  );

  const reset = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const toggleZoom = useCallback(() => {
    setScale((s) => {
      if (s > 1) {
        setTx(0);
        setTy(0);
        return 1;
      }
      return 2;
    });
  }, []);

  function onPointerDown(e: React.PointerEvent) {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    movedRef.current = false;
    setAnimating(false);
    const pts = Array.from(pointersRef.current.values());
    if (pts.length === 2) {
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      pinchRef.current = { dist, scale };
      panRef.current = null;
    } else if (pts.length === 1) {
      panRef.current = { x: e.clientX, y: e.clientY, tx, ty };
    }
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!pointersRef.current.has(e.pointerId)) return;
    pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pts = Array.from(pointersRef.current.values());
    if (pts.length === 2 && pinchRef.current) {
      movedRef.current = true;
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      const base = pinchRef.current.dist || dist;
      applyScale(pinchRef.current.scale * (dist / base));
      return;
    }
    if (pts.length === 1 && panRef.current) {
      const dx = e.clientX - panRef.current.x;
      const dy = e.clientY - panRef.current.y;
      if (Math.abs(dx) > MOVE_SLOP || Math.abs(dy) > MOVE_SLOP) movedRef.current = true;
      if (scale > 1) {
        const m = maxTranslate(scale);
        setTx(clamp(panRef.current.tx + dx, -m.x, m.x));
        setTy(clamp(panRef.current.ty + dy, -m.y, m.y));
      }
    }
  }

  function endPointer(e: React.PointerEvent) {
    const wasSingle = pointersRef.current.size === 1;
    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size < 2) pinchRef.current = null;
    if (pointersRef.current.size === 0) {
      panRef.current = null;
      setAnimating(true);
    }
    // Double-tap / double-click toggle: only for a clean single-pointer tap.
    if (wasSingle && !movedRef.current) {
      const now = Date.now();
      const last = lastTapRef.current;
      if (
        last &&
        now - last.time < TAP_MS &&
        Math.hypot(e.clientX - last.x, e.clientY - last.y) < TAP_SLOP
      ) {
        toggleZoom();
        lastTapRef.current = null;
      } else {
        lastTapRef.current = { time: now, x: e.clientX, y: e.clientY };
      }
    }
  }

  function onWheel(e: React.WheelEvent) {
    applyScale(scale + (e.deltaY < 0 ? STEP : -STEP));
  }

  function onBackgroundClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget && !movedRef.current) onClose();
  }

  if (!mounted) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-black/80"
    >
      <div
        ref={containerRef}
        className="flex h-full w-full items-center justify-center overflow-hidden"
        style={{ touchAction: "none" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
        onWheel={onWheel}
        onClick={onBackgroundClick}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt ?? ""}
          draggable={false}
          className="max-h-full max-w-full select-none object-contain"
          style={{
            transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
            cursor: scale > 1 ? "grab" : "zoom-in",
            transition: animating ? "transform 0.15s ease-out" : "none",
            willChange: "transform",
          }}
        />
      </div>

      {/* Close (top-right) */}
      <div
        className="absolute right-3 top-3"
        style={{ paddingTop: "env(safe-area-inset-top)", paddingRight: "env(safe-area-inset-right)" }}
      >
        <IconButton
          label={t("lightboxClose")}
          onClick={onClose}
          style={{ minWidth: 44, minHeight: 44 }}
          className="bg-surface text-fg shadow-lg hover:bg-elevated"
        >
          <span aria-hidden className="text-lg leading-none">
            {"\u2715"}
          </span>
        </IconButton>
      </div>

      {/* Zoom controls (bottom-center) */}
      <div
        className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-surface px-2 py-1.5 text-fg shadow-lg"
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}
      >
        <IconButton
          label={t("lightboxZoomOut")}
          onClick={() => applyScale(scale - STEP)}
          disabled={scale <= MIN_SCALE}
          style={{ minWidth: 44, minHeight: 44 }}
          className="hover:bg-elevated disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span aria-hidden className="text-2xl leading-none">
            {"\u2212"}
          </span>
        </IconButton>
        <IconButton
          label={t("lightboxReset")}
          onClick={reset}
          style={{ minWidth: 44, minHeight: 44 }}
          className="hover:bg-elevated"
        >
          <span aria-hidden className="text-sm font-semibold leading-none">
            1:1
          </span>
        </IconButton>
        <IconButton
          label={t("lightboxZoomIn")}
          onClick={() => applyScale(scale + STEP)}
          disabled={scale >= MAX_SCALE}
          style={{ minWidth: 44, minHeight: 44 }}
          className="hover:bg-elevated disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span aria-hidden className="text-2xl leading-none">
            {"\uFF0B"}
          </span>
        </IconButton>
      </div>
    </div>,
    document.body,
  );
}
