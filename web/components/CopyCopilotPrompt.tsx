"use client";

import { useState } from "react";

interface Props {
  prompt: string;
  label: string;
  copiedLabel: string;
}

export default function CopyCopilotPrompt({ prompt, label, copiedLabel }: Props) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: prompt user to manually copy
      window.prompt("Copy:", prompt);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition"
    >
      {copied ? copiedLabel : label}
    </button>
  );
}
