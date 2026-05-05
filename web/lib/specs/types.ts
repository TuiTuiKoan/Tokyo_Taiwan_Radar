/**
 * Shared types for the spec dashboard.
 */

export type SpecStatus = "parked" | "active" | "archived";
export type SpecColumn = "parked" | "todo" | "doing" | "done";

export interface SpecFrontmatter {
  slug: string;
  title: string;
  status: SpecStatus;
  branch?: string;
  created?: string;
  tags?: string[];
}

export interface SpecTaskProgress {
  done: number;
  total: number;
}

export interface Spec {
  slug: string;
  title: string;
  status: SpecStatus;
  column: SpecColumn;
  branch?: string;
  created?: string;
  tags: string[];
  /** Path under docs/specs/ (e.g. "active/foo" or "parked/bar") */
  relativePath: string;
  proposalMd: string;
  tasksMd: string;
  notesMd: string;
  tasks: SpecTaskProgress;
  /** Last modified time (ISO string), based on file mtime. */
  updatedAt: string;
  /** Optional commit hash from build environment. */
  commitSha?: string;
}

export interface SpecsSnapshot {
  generatedAt: string;
  commitSha?: string;
  specs: Spec[];
}

export interface SystemMapAgent {
  id: string;
  label: string;
  owns: string[];
  description?: string;
}

export interface SystemMapSkill {
  id: string;
  label: string;
  appliesTo: string[];
}

export interface SystemMapScraperGroup {
  id: string;
  label: string;
  members: string[];
}

export interface SystemMapDataFlow {
  from: string;
  to: string;
  label?: string;
}

export interface SystemMap {
  version: string;
  updated: string;
  agents: SystemMapAgent[];
  skills: SystemMapSkill[];
  scraperGroups: SystemMapScraperGroup[];
  dataFlow: SystemMapDataFlow[];
}
