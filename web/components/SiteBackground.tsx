import { DesignDefs } from "@/lib/design";
import { FloatingShapes } from "@/lib/design/FloatingShapes";

/**
 * SiteBackground — global Bauhaus background layer applied via [locale]/layout.tsx.
 *
 * Stack (all fixed inset-0, behind page content):
 *   1. Paper-gradient base (cream → blush → pistachio)
 *   2. Faint pink grid SVG pattern
 *   3. 10 floating geometric shapes (procedural, refreshes each cycle)
 *   4. Subtle film-noise overlay
 *
 * The pieces are aria-hidden, pointer-events-none, and live on -z layers so
 * they never interfere with content interaction.
 */
export function SiteBackground() {
  return (
    <div data-site-bg>
      {/* SVG <defs> for the grid pattern referenced below */}
      <DesignDefs />

      {/* 1. Paper gradient */}
      <div
        aria-hidden
        className="fixed inset-0 -z-30 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, #FFFDF5 0%, #FFF1EE 58%, #F7FFE8 100%)",
        }}
      />

      {/* 2. Grid pattern */}
      <svg
        aria-hidden
        className="fixed inset-0 -z-20 w-full h-full pointer-events-none"
        preserveAspectRatio="xMidYMin slice"
        viewBox="0 0 1440 1200"
      >
        <rect width="100%" height="100%" fill="url(#gridPink)" opacity="0.6" />
      </svg>

      {/* 3. Floating shapes (client component) */}
      <FloatingShapes />
    </div>
  );
}

export default SiteBackground;
