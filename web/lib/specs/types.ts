/**
 * Shared types for the architecture map (system-map.json).
 */

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

export type SystemMapNodeKind = "component" | "api" | "scraper" | "workflow" | "external";

export interface SystemMapNode {
  id: string;
  label: string;
  kind: SystemMapNodeKind;
  sourcePath: string;
  tags?: string[];
}

export interface SystemMapFlowAction {
  id: string;
  label: string;
  description: string;
  category?: "manual" | "batch" | "schedule" | "qa";
}

export interface SystemMapFlowStep {
  from: string;
  to: string;
  channel: string;
  payloadNote: string;
  evidenceRef: string;
}

export interface SystemMapFlow {
  id: string;
  actionId: string;
  title: string;
  steps: SystemMapFlowStep[];
  annotations: string[];
}

export interface SystemMap {
  version: string;
  updated: string;
  agents: SystemMapAgent[];
  skills: SystemMapSkill[];
  scraperGroups: SystemMapScraperGroup[];
  dataFlow: SystemMapDataFlow[];
  nodes?: SystemMapNode[];
  actions?: SystemMapFlowAction[];
  flows?: SystemMapFlow[];
  scanWarnings?: string[];
}
