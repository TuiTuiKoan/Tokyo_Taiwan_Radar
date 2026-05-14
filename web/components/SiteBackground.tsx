import { DesignDefs } from "@/lib/design";

/**
 * SiteBackground — static Bauhaus background layer (gradient + grid).
 *
 * Mounted in [locale]/layout.tsx so every page gets the paper-gradient base
 * and the faint pink grid. The floating shapes (FloatingShapes) are a separate
 * client component mounted only on the homepage.
 *
 * The pieces are aria-hidden, pointer-events-none, fixed z-layers behind content.
 */
export function SiteBackground() {
  return (
    <div data-site-bg>
      {/* SVG <defs> for the grid pattern referenced below */}
      <DesignDefs />

      {/* 1. Paper gradient — light: paper→blush→matcha; dark: deep warm dark tones */}
      <div
        aria-hidden
        className="fixed inset-0 -z-30 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, #FFFDF5 0%, #FFF1EE 58%, #F7FFE8 100%)",
        }}
      />
      {/* Dark mode gradient layer — overlays on top of the light layer via html.dark */}
      <div
        aria-hidden
        className="fixed inset-0 -z-30 pointer-events-none opacity-0 dark:opacity-100 transition-opacity duration-300"
        style={{
          background:
            "linear-gradient(135deg, #18160f 0%, #1c1a17 45%, #131a12 100%)",
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
    </div>
  );
}

export default SiteBackground;
