"use client";

import { useMemo, useState } from "react";
import Mermaid from "@/components/Mermaid";
import type { SystemMap, SystemMapFlow, SystemMapFlowStep, SystemMapNode } from "@/lib/specs/types";

interface Labels {
  explorerTitle: string;
  explorerDesc: string;
  actionLabel: string;
  searchLabel: string;
  searchPlaceholder: string;
  reset: string;
  noFlow: string;
  stepsTitle: string;
  annotationsTitle: string;
  evidenceLabel: string;
  channelLabel: string;
  payloadLabel: string;
  nodesCount: string;
  actionsCount: string;
  flowsCount: string;
}

interface Props {
  map: SystemMap;
  labels: Labels;
}

function sanitizeId(id: string): string {
  return `n_${id.replace(/[^a-zA-Z0-9_]/g, "_")}`;
}

function esc(text: string): string {
  return text.replace(/"/g, "\\\"");
}

function virtualLabel(id: string): string {
  if (id.startsWith("db:")) return id.replace("db:", "DB ");
  if (id.startsWith("external:")) return id.replace("external:", "External ");
  return id;
}

function buildChart(
  nodes: SystemMapNode[],
  steps: SystemMapFlowStep[],
  selectedStep: number | null,
): string {
  const lines: string[] = ["graph LR"];

  const grouped: Record<string, SystemMapNode[]> = {
    component: [],
    api: [],
    scraper: [],
    workflow: [],
    external: [],
  };
  for (const node of nodes) {
    grouped[node.kind] = [...(grouped[node.kind] ?? []), node];
  }

  const groups: Array<{ key: keyof typeof grouped; label: string }> = [
    { key: "component", label: "Components" },
    { key: "api", label: "API Routes" },
    { key: "scraper", label: "Scrapers" },
    { key: "workflow", label: "Workflows" },
    { key: "external", label: "External / DB" },
  ];

  for (const group of groups) {
    if (!grouped[group.key]?.length) continue;
    lines.push(`  subgraph ${group.label}`);
    for (const node of grouped[group.key]) {
      lines.push(`    ${sanitizeId(node.id)}[\"${esc(node.label)}\"]`);
    }
    lines.push("  end");
  }

  const flowNodeIds = new Set<string>();
  for (const step of steps) {
    flowNodeIds.add(step.from);
    flowNodeIds.add(step.to);
    lines.push(
      `  ${sanitizeId(step.from)} -->|${esc(step.channel)}| ${sanitizeId(step.to)}`,
    );
  }

  const muted = nodes.filter((n) => !flowNodeIds.has(n.id)).map((n) => sanitizeId(n.id));
  const active = nodes.filter((n) => flowNodeIds.has(n.id)).map((n) => sanitizeId(n.id));
  const virtual = nodes.filter((n) => n.kind === "external").map((n) => sanitizeId(n.id));

  lines.push("  classDef mutedNode fill:#f8fafc,stroke:#cbd5e1,color:#64748b,opacity:0.45;");
  lines.push("  classDef activeNode fill:#ecfeff,stroke:#0891b2,stroke-width:2px,color:#0f172a;");
  lines.push("  classDef virtualNode fill:#fff7ed,stroke:#f97316,stroke-dasharray: 4 3,color:#7c2d12;");

  if (muted.length > 0) lines.push(`  class ${muted.join(",")} mutedNode;`);
  if (active.length > 0) lines.push(`  class ${active.join(",")} activeNode;`);
  if (virtual.length > 0) lines.push(`  class ${virtual.join(",")} virtualNode;`);

  for (let i = 0; i < steps.length; i += 1) {
    const isSelected = selectedStep === i;
    if (isSelected) {
      lines.push(`  linkStyle ${i} stroke:#0f766e,stroke-width:4px,opacity:1;`);
    } else {
      lines.push(`  linkStyle ${i} stroke:#0ea5e9,stroke-width:2.5px,opacity:0.9;`);
    }
  }

  return lines.join("\n");
}

export default function ArchitectureFlowExplorer({ map, labels }: Props) {
  const actions = useMemo(() => map.actions ?? [], [map.actions]);
  const flows = useMemo(() => map.flows ?? [], [map.flows]);
  const baseNodes = useMemo(() => map.nodes ?? [], [map.nodes]);

  const [search, setSearch] = useState("");
  const [selectedActionId, setSelectedActionId] = useState<string>(actions[0]?.id ?? "");
  const [selectedStep, setSelectedStep] = useState<number | null>(null);

  const filteredActions = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((a) => `${a.label} ${a.description}`.toLowerCase().includes(q));
  }, [actions, search]);

  const hasSelectedAction = useMemo(
    () => filteredActions.some((a) => a.id === selectedActionId),
    [filteredActions, selectedActionId],
  );

  const effectiveSelectedActionId = useMemo(() => {
    if (!filteredActions.length) return "";
    if (hasSelectedAction) return selectedActionId;
    return filteredActions[0].id;
  }, [filteredActions, hasSelectedAction, selectedActionId]);

  const effectiveSelectedStep = hasSelectedAction ? selectedStep : null;

  const selectedFlow: SystemMapFlow | undefined = useMemo(
    () => flows.find((f) => f.actionId === effectiveSelectedActionId),
    [flows, effectiveSelectedActionId],
  );

  const flowNodes = useMemo(() => {
    const byId = new Map<string, SystemMapNode>();
    for (const node of baseNodes) byId.set(node.id, node);

    for (const step of selectedFlow?.steps ?? []) {
      if (!byId.has(step.from)) {
        byId.set(step.from, {
          id: step.from,
          label: virtualLabel(step.from),
          kind: "external",
          sourcePath: step.from,
        });
      }
      if (!byId.has(step.to)) {
        byId.set(step.to, {
          id: step.to,
          label: virtualLabel(step.to),
          kind: "external",
          sourcePath: step.to,
        });
      }
    }

    return Array.from(byId.values());
  }, [baseNodes, selectedFlow]);

  const chart = useMemo(
    () => buildChart(flowNodes, selectedFlow?.steps ?? [], effectiveSelectedStep),
    [flowNodes, selectedFlow, effectiveSelectedStep],
  );

  const resetView = () => {
    setSearch("");
    setSelectedActionId(actions[0]?.id ?? "");
    setSelectedStep(null);
  };

  const fallback = (
    <div className="space-y-3 text-sm">
      <details className="border border-line rounded p-3">
        <summary className="font-medium cursor-pointer">JSON</summary>
        <pre className="mt-2 text-xs overflow-x-auto bg-elevated p-3 rounded">
          {JSON.stringify(
            {
              action: selectedActionId,
              effectiveAction: effectiveSelectedActionId,
              flow: selectedFlow,
              nodeCount: flowNodes.length,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </div>
  );

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-4">
        <h2 className="text-lg font-semibold text-fg-strong">{labels.explorerTitle}</h2>
        <p className="mt-1 text-sm text-fg-muted">{labels.explorerDesc}</p>

        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <label className="text-sm">
            <span className="mb-1 block text-fg-muted">{labels.searchLabel}</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={labels.searchPlaceholder}
              className="w-full rounded-lg border border-line bg-background px-3 py-2 text-sm"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block text-fg-muted">{labels.actionLabel}</span>
            <select
              value={effectiveSelectedActionId}
              onChange={(e) => {
                setSelectedActionId(e.target.value);
                setSelectedStep(null);
              }}
              className="w-full rounded-lg border border-line bg-background px-3 py-2 text-sm"
            >
              {filteredActions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              type="button"
              onClick={resetView}
              className="rounded-lg border border-line px-3 py-2 text-sm hover:bg-elevated"
            >
              {labels.reset}
            </button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg bg-elevated p-3">
            <div className="text-fg-muted">{labels.nodesCount}</div>
            <div className="text-xl font-semibold text-fg-strong">{baseNodes.length}</div>
          </div>
          <div className="rounded-lg bg-elevated p-3">
            <div className="text-fg-muted">{labels.actionsCount}</div>
            <div className="text-xl font-semibold text-fg-strong">{actions.length}</div>
          </div>
          <div className="rounded-lg bg-elevated p-3">
            <div className="text-fg-muted">{labels.flowsCount}</div>
            <div className="text-xl font-semibold text-fg-strong">{flows.length}</div>
          </div>
        </div>
      </div>

      {!selectedFlow ? (
        <div className="rounded-xl border border-line bg-surface p-4 text-sm text-fg-muted">
          {labels.noFlow}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="rounded-xl border border-line bg-surface p-4">
            <Mermaid chart={chart} fallback={fallback} />
          </div>

          <aside className="rounded-xl border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold text-fg-strong">{labels.stepsTitle}</h3>
            <ol className="mt-3 space-y-2">
              {selectedFlow.steps.map((step, idx) => (
                <li key={`${step.from}-${step.to}-${idx}`}>
                  <button
                    type="button"
                    onClick={() => setSelectedStep(idx)}
                    className={[
                      "w-full rounded-lg border p-3 text-left text-xs",
                      effectiveSelectedStep === idx
                        ? "border-teal-600 bg-teal-50"
                        : "border-line hover:bg-elevated",
                    ].join(" ")}
                  >
                    <p className="font-semibold text-fg-strong">
                      {idx + 1}. {virtualLabel(step.from)}{" -> "}{virtualLabel(step.to)}
                    </p>
                    <p className="mt-1 text-fg-muted">
                      {labels.channelLabel}: {step.channel}
                    </p>
                    <p className="mt-1 text-fg-muted">
                      {labels.payloadLabel}: {step.payloadNote}
                    </p>
                    <p className="mt-1 text-fg-muted break-all">
                      {labels.evidenceLabel}: {step.evidenceRef}
                    </p>
                  </button>
                </li>
              ))}
            </ol>

            {selectedFlow.annotations.length > 0 && (
              <div className="mt-4 border-t border-line pt-3">
                <h4 className="text-sm font-semibold text-fg-strong">{labels.annotationsTitle}</h4>
                <ul className="mt-2 space-y-2 text-xs text-fg-muted">
                  {selectedFlow.annotations.map((note, idx) => (
                    <li key={`${selectedFlow.id}-note-${idx}`}>- {note}</li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
