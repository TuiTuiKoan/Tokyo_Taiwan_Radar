/**
 * Runtime API for the spec dashboard. Reads the JSON snapshot generated
 * by `scripts/build-specs-snapshot.ts` at build time.
 */
import type { Spec, SpecColumn, SpecsSnapshot, SystemMap } from "./types";
import snapshotJson from "./specs-snapshot.json";
import systemMapJson from "./system-map.json";

const snapshot = snapshotJson as SpecsSnapshot;
const systemMap = systemMapJson as SystemMap;

export function listSpecs(): Spec[] {
  return snapshot.specs;
}

export function getSpec(slug: string): Spec | undefined {
  return snapshot.specs.find((s) => s.slug === slug);
}

export function listSpecsByColumn(column: SpecColumn): Spec[] {
  return snapshot.specs.filter((s) => s.column === column);
}

export function getSnapshotMeta(): { generatedAt: string; commitSha?: string } {
  return { generatedAt: snapshot.generatedAt, commitSha: snapshot.commitSha };
}

export function getSystemMap(): SystemMap {
  return systemMap;
}

export function buildCopilotPrompt(spec: Spec): string {
  const unchecked: string[] = [];
  const re = /^\s*[-*]\s+\[ \]\s+(.*)$/gim;
  let m: RegExpExecArray | null;
  while ((m = re.exec(spec.tasksMd)) !== null) {
    unchecked.push(m[1].trim());
  }
  const refs = `docs/specs/${spec.relativePath}/proposal.md, docs/specs/${spec.relativePath}/tasks.md, docs/specs/${spec.relativePath}/notes.md`;
  const lines = [
    `請依 docs/specs/${spec.relativePath}/tasks.md 繼續執行。`,
    "",
    "未完成項目：",
    ...(unchecked.length > 0 ? unchecked.map((t) => `- ${t}`) : ["（全部已完成）"]),
    "",
    `參考：${refs}`,
  ];
  return lines.join("\n");
}
