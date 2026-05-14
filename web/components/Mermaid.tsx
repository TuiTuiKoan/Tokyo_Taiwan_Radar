"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  chart: string;
  fallback?: React.ReactNode;
}

export default function Mermaid({ chart, fallback }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
        });
        const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;
        const { svg } = await mermaid.render(id, chart);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          // Mermaid renders SVG with inline width:100% + max-width. For wide
          // graphs this compresses all labels into unreadable size.
          // Force natural pixel width from viewBox and rely on horizontal scroll.
          const svgEl = ref.current.querySelector("svg");
          if (svgEl) {
            const vb = svgEl.getAttribute("viewBox");
            const vbWidth = vb ? parseFloat(vb.trim().split(/[\s,]+/)[2]) : 0;
            if (vbWidth > 0) {
              svgEl.setAttribute("width", String(vbWidth));
              svgEl.style.width = `${vbWidth}px`;
              svgEl.style.maxWidth = "none";
              svgEl.style.minWidth = `${vbWidth}px`;
              svgEl.style.height = "auto";
            }
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <div>
        <p className="text-xs text-red-600 mb-2">Mermaid error: {error}</p>
        {fallback}
      </div>
    );
  }

  return <div ref={ref} className="overflow-x-auto" />;
}
