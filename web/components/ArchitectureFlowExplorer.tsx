"use client";

import { useMemo, useState } from "react";
import Mermaid from "@/components/Mermaid";
import DesignSelect from "@/components/DesignSelect";
import type { SystemMap, SystemMapFlow, SystemMapFlowAction, SystemMapFlowStep, SystemMapNode } from "@/lib/specs/types";

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
  categoryAll: string;
  categoryManual: string;
  categoryBatch: string;
  categorySchedule: string;
  categoryQa: string;
}

type CategoryFilter = "all" | "manual" | "batch" | "schedule" | "qa";

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
  const flows = useMemo(() => map.flows ?? [], [map.flows]);
  const actions = useMemo(() => {
    const configured = map.actions ?? [];
    const configuredById = new Map(configured.map((a) => [a.id, a]));

    // Primary source: flows (always required for rendering)
    const derived: SystemMapFlowAction[] = [];
    const seen = new Set<string>();
    for (const f of flows) {
      if (seen.has(f.actionId)) continue;
      seen.add(f.actionId);

      const fromConfig = configuredById.get(f.actionId);
      if (fromConfig) {
        derived.push(fromConfig);
        continue;
      }

      // Fallback when action metadata is missing in JSON: still keep the flow selectable.
      derived.push({
        id: f.actionId,
        label: f.title,
        description: f.title,
      });
    }

    // Keep configured actions that currently have no flow as trailing options.
    for (const a of configured) {
      if (!seen.has(a.id)) derived.push(a);
    }

    return derived;
  }, [map.actions, flows]);
  const baseNodes = useMemo(() => map.nodes ?? [], [map.nodes]);

  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryFilter>("all");
  const [selectedActionId, setSelectedActionId] = useState<string>(actions[0]?.id ?? "");
  const [selectedStep, setSelectedStep] = useState<number | null>(null);

  const categoryCounts = useMemo(() => {
    const counts: Record<CategoryFilter, number> = { all: actions.length, manual: 0, batch: 0, schedule: 0, qa: 0 };
    for (const a of actions) {
      const cat = (a.category ?? "manual") as Exclude<CategoryFilter, "all">;
      if (cat in counts) counts[cat] += 1;
    }
    return counts;
  }, [actions]);

  const filteredActions = useMemo(() => {
    const q = search.trim().toLowerCase();
    const byCategory = selectedCategory === "all"
      ? actions
      : actions.filter((a) => (a.category ?? "manual") === selectedCategory);
    if (!q) return byCategory;
    return byCategory.filter((a) => `${a.label} ${a.description}`.toLowerCase().includes(q));
  }, [actions, search, selectedCategory]);

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
    const baseById = new Map<string, SystemMapNode>();
    for (const node of baseNodes) baseById.set(node.id, node);

    for (const step of selectedFlow?.steps ?? []) {
      const fromNode = baseById.get(step.from);
      byId.set(
        step.from,
        fromNode ?? {
          id: step.from,
          label: virtualLabel(step.from),
          kind: "external",
          sourcePath: step.from,
        },
      );

      const toNode = baseById.get(step.to);
      byId.set(
        step.to,
        toNode ?? {
          id: step.to,
          label: virtualLabel(step.to),
          kind: "external",
          sourcePath: step.to,
        },
      );
    }

    return Array.from(byId.values());
  }, [baseNodes, selectedFlow]);

  const chart = useMemo(
    () => buildChart(flowNodes, selectedFlow?.steps ?? [], effectiveSelectedStep),
    [flowNodes, selectedFlow, effectiveSelectedStep],
  );

  const resetView = () => {
    setSearch("");
    setSelectedCategory("all");
    setSelectedActionId(actions[0]?.id ?? "");
    setSelectedStep(null);
  };

  const categoryChips: Array<{ key: CategoryFilter; label: string }> = [
    { key: "all", label: labels.categoryAll },
    { key: "manual", label: labels.categoryManual },
    { key: "batch", label: labels.categoryBatch },
    { key: "schedule", label: labels.categorySchedule },
    { key: "qa", label: labels.categoryQa },
  ];

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

        <div className="mt-4 flex flex-wrap gap-2 mb-3">
          {categoryChips.map((chip) => {
            const isActive = selectedCategory === chip.key;
            const count = categoryCounts[chip.key];
            return (
              <button
                key={chip.key}
                type="button"
                onClick={() => {
                  setSelectedCategory(chip.key);
                  setSelectedStep(null);
                }}
                aria-pressed={isActive}
                className={
                  isActive
                    ? "bg-[var(--color-brand-soft)] text-[var(--color-brand-strong)] border border-[var(--color-brand)] rounded-full px-3 py-1 text-sm font-medium"
                    : "text-fg-muted border border-line rounded-full px-3 py-1 text-sm hover:border-fg-muted hover:text-fg"
                }
              >
                {chip.label}
                <span className="ml-1 text-xs opacity-70">({count})</span>
              </button>
            );
          })}
        </div>

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
            <DesignSelect
              value={effectiveSelectedActionId}
              onChange={(e) => {
                setSelectedActionId(e);
                setSelectedStep(null);
              }}
              options={filteredActions.map((a) => ({ value: a.id, label: a.label }))}
            />
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
