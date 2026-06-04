"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  variant?: ButtonVariant;
  children: ReactNode;
}

const variantClassName: Record<ButtonVariant, string> = {
  primary: "border border-green-600 bg-green-600 text-white hover:bg-green-700",
  secondary: "border border-line-strong bg-paper text-fg hover:bg-elevated",
  ghost: "border border-transparent bg-transparent text-fg-muted hover:bg-elevated hover:text-fg",
};

export default function Button({ loading = false, variant = "primary", children, className = "", disabled, type, ...props }: Props) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type ?? "button"}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium leading-none transition disabled:cursor-not-allowed disabled:opacity-60 ${variantClassName[variant]} ${className}`}
      {...props}
    >
      {loading && (
        <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden />
      )}
      <span className="leading-none">{children}</span>
    </button>
  );
}