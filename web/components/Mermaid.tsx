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
          // Remove Mermaid's max-width constraint so large graphs scroll horizontally
          // instead of being compressed to fit the container width (unreadable).
          const svgEl = ref.current.querySelector("svg");
          if (svgEl) {
            svgEl.style.maxWidth = "none";
            svgEl.style.height = "auto";
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
