"use client";

/**
 * FloatingShapesAuto — pathname-aware mount of <FloatingShapes variant="subtle" />.
 *
 * Mounted in [locale]/layout.tsx so every page gets a quiet background of
 * 2–6 small floating shapes. The homepage and the /design preview already
 * mount their own full-tier FloatingShapes — we skip there to avoid stacking
 * two layers. Admin pages stay distraction-free.
 */

import { usePathname } from "next/navigation";
import { FloatingShapes } from "./FloatingShapes";

const LOCALES = new Set(["zh", "en", "ja"]);

export function FloatingShapesAuto() {
  const pathname = usePathname() ?? "";
  const segments = pathname.split("/").filter(Boolean);

  // /<locale> (homepage) — homepage mounts the full background itself.
  const isHomepage = segments.length === 1 && LOCALES.has(segments[0]);
  // /<locale>/design — design preview page also mounts the full background.
  const isDesignPage =
    segments.length === 2 && LOCALES.has(segments[0]) && segments[1] === "design";
  // /<locale>/admin/... — admin should stay quiet.
  const isAdmin =
    segments.length >= 2 && LOCALES.has(segments[0]) && segments[1] === "admin";

  if (isHomepage || isDesignPage || isAdmin) return null;
  return <FloatingShapes variant="subtle" />;
}

export default FloatingShapesAuto;
