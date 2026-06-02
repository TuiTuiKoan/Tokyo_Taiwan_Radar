"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export interface DesignSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface DesignSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: DesignSelectOption[];
  placeholder?: string;
  className?: string;
  panelClassName?: string;
  disabled?: boolean;
  id?: string;
}

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export default function DesignSelect({
  value,
  onChange,
  options,
  placeholder,
  className,
  panelClassName,
  disabled = false,
  id,
}: DesignSelectProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const panelId = id ? `${id}-panel` : undefined;

  useEffect(() => {
    function onDocMouseDown(e: MouseEvent) {
      if (!rootRef.current || rootRef.current.contains(e.target as Node)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, []);

  const current = useMemo(
    () => options.find((o) => o.value === value),
    [options, value],
  );

  const label = current?.label ?? placeholder ?? "-";

  return (
    <div className={cx("relative", className)} ref={rootRef}>
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={panelId}
        className={cx(
          "h-9 w-full flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm",
          "bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        <span className={current ? "text-fg" : "text-fg-muted"}>{label}</span>
        <span className="text-fg-subtle text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && !disabled && (
        <div
          id={panelId}
          role="listbox"
          className={cx(
            "absolute z-50 top-10 left-0 w-full min-w-[10rem] bg-surface border border-line rounded-xl shadow-lg py-2 max-h-72 overflow-y-auto",
            panelClassName,
          )}
        >
          {options.map((o) => (
            <button
              key={`${o.value}-${o.label}`}
              type="button"
              disabled={o.disabled}
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
              className={cx(
                "w-full text-left px-4 py-1.5 text-sm",
                "hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400",
                value === o.value ? "text-green-700 dark:text-green-400 font-medium" : "text-fg",
                o.disabled && "opacity-50 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent",
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
