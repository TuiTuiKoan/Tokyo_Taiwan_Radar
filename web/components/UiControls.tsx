"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ToggleSwitchProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  checked: boolean;
};

export function ToggleSwitch({ checked, className = "", ...props }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`relative inline-grid h-6 w-11 shrink-0 place-items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-1 ${
        checked ? "bg-green-500" : "bg-gray-300 dark:bg-stone-600"
      } ${className}`}
      {...props}
    >
      <span
        aria-hidden
        className={`block h-5 w-5 rounded-full bg-surface shadow transition-transform duration-200 ${
          checked ? "translate-x-2.5" : "-translate-x-2.5"
        }`}
      />
    </button>
  );
}

type PillButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean;
  tone?: "green" | "blue";
  children: ReactNode;
};

export function PillButton({ active = false, tone = "green", className = "", children, ...props }: PillButtonProps) {
  const activeClass =
    tone === "blue"
      ? "border-blue-600 bg-blue-600 text-white"
      : "border-green-600 bg-green-600 text-white";
  const idleClass =
    tone === "blue"
      ? "border-line-strong text-fg hover:border-blue-400"
      : "border-line-strong text-fg hover:border-green-400";

  return (
    <button
      type="button"
      className={`inline-flex min-h-8 items-center justify-center rounded-full border px-3 text-xs font-medium leading-none transition ${
        active ? activeClass : idleClass
      } ${className}`}
      {...props}
    >
      <span className="leading-none">{children}</span>
    </button>
  );
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string; // aria-label (required for accessibility)
  children: ReactNode;
};

export function IconButton({ label, className = "", children, ...props }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-1 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function StatusBadge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex min-h-5 items-center rounded-full px-2 text-xs leading-none ${className}`}>
      <span className="leading-none">{children}</span>
    </span>
  );
}