"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  proposalMd: string;
  tasksMd: string;
  notesMd: string;
  labels: {
    proposal: string;
    tasks: string;
    notes: string;
    noNotes: string;
    noTasks: string;
  };
}

type Tab = "proposal" | "tasks" | "notes";

export default function SpecTabs({ proposalMd, tasksMd, notesMd, labels }: Props) {
  const [tab, setTab] = useState<Tab>("proposal");

  const content =
    tab === "proposal"
      ? proposalMd
      : tab === "tasks"
        ? tasksMd || ""
        : notesMd || "";

  const fallback =
    tab === "tasks" && !tasksMd
      ? labels.noTasks
      : tab === "notes" && !notesMd
        ? labels.noNotes
        : null;

  function tabBtn(key: Tab, label: string) {
    const isActive = tab === key;
    return (
      <button
        key={key}
        type="button"
        onClick={() => setTab(key)}
        className={
          isActive
            ? "px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600"
            : "px-4 py-2 text-sm text-gray-500 hover:text-green-700"
        }
      >
        {label}
      </button>
    );
  }

  return (
    <div>
      <div className="flex gap-1 border-b border-gray-200 mb-4">
        {tabBtn("proposal", labels.proposal)}
        {tabBtn("tasks", labels.tasks)}
        {tabBtn("notes", labels.notes)}
      </div>
      {fallback ? (
        <p className="text-sm text-gray-400 italic">{fallback}</p>
      ) : (
        <article className="prose prose-sm max-w-none prose-headings:font-semibold prose-a:text-green-700 prose-code:before:content-none prose-code:after:content-none prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </article>
      )}
    </div>
  );
}
