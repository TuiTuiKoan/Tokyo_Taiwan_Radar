/**
 * Build-time generator for the architecture map at /admin/specs/architecture.
 *
 * Reads `docs/architecture/system-map.json`, scans web components, API routes,
 * scrapers and workflows, and writes `web/lib/specs/system-map.json` so the
 * Next.js runtime can import it without filesystem access.
 *
 * It also used to snapshot docs/specs for a spec kanban; that board was removed
 * on 2026-10-22 (#329) and progress now lives on the TTR Roadmap GitHub Project.
 *
 * Vercel-safe: pure fs operations, no git subprocess.
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import type { SystemMap, SystemMapNode, SystemMapNodeKind } from "../lib/specs/types";

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const SYSTEM_MAP_SRC = path.join(REPO_ROOT, "docs", "architecture", "system-map.json");
const OUT_DIR = path.resolve(__dirname, "..", "lib", "specs");
const OUT_SYSTEM_MAP = path.join(OUT_DIR, "system-map.json");

const COMPONENTS_DIR = path.join(REPO_ROOT, "web", "components");
const API_DIR = path.join(REPO_ROOT, "web", "app", "api");
const SCRAPER_DIR = path.join(REPO_ROOT, "scraper");
const WORKFLOWS_DIR = path.join(REPO_ROOT, ".github", "workflows");

const CORE_SCRAPER_MODULES = new Set<string>([
  "main.py",
  "merger.py",
  "annotator.py",
  "auto_qa.py",
  "category_feedback.py",
  "selection_reason_feedback.py",
  "weekly_line_broadcast.py",
  "enrich_ocr_event.py",
  "update_source.py",
  "movie_title_lookup.py",
  "person_name_lookup.py",
]);

function toPosix(relPath: string): string {
  return relPath.split(path.sep).join("/");
}

function toNodeId(kind: SystemMapNodeKind, sourcePath: string): string {
  const stem = sourcePath
    .toLowerCase()
    .replace(/\.tsx$|\.ts$|\.py$|\.yml$/g, "")
    .replace(/\/route$/, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return `${kind}-${stem}`;
}

function toNodeLabel(kind: SystemMapNodeKind, sourcePath: string): string {
  if (kind === "api") {
    const route = sourcePath.replace(/^web\/app\/api\//, "").replace(/\/route\.ts$/, "");
    return `/api/${route}`;
  }
  return path.basename(sourcePath).replace(/\.tsx$|\.py$|\.yml$/, "");
}

function makeNode(kind: SystemMapNodeKind, sourcePath: string, tags: string[] = []): SystemMapNode {
  return {
    id: toNodeId(kind, sourcePath),
    label: toNodeLabel(kind, sourcePath),
    kind,
    sourcePath,
    tags,
  };
}

async function walkFiles(root: string): Promise<string[]> {
  const out: string[] = [];
  async function walk(dir: string) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(full);
      } else if (entry.isFile()) {
        out.push(full);
      }
    }
  }
  await walk(root);
  return out;
}

async function scanComponents(warnings: string[]): Promise<SystemMapNode[]> {
  try {
    const entries = await fs.readdir(COMPONENTS_DIR, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".tsx"))
      .map((entry) => makeNode("component", `web/components/${entry.name}`));
  } catch {
    warnings.push("components directory missing: web/components");
    return [];
  }
}

async function scanApiRoutes(warnings: string[]): Promise<SystemMapNode[]> {
  try {
    const files = await walkFiles(API_DIR);
    return files
      .filter((f) => f.endsWith("/route.ts"))
      .map((f) => {
        const rel = toPosix(path.relative(REPO_ROOT, f));
        return makeNode("api", rel);
      });
  } catch {
    warnings.push("api directory missing: web/app/api");
    return [];
  }
}

async function scanScrapers(warnings: string[]): Promise<SystemMapNode[]> {
  try {
    const entries = await fs.readdir(SCRAPER_DIR, { withFileTypes: true });
    return entries
      .filter(
        (entry) =>
          entry.isFile() &&
          entry.name.endsWith(".py") &&
          CORE_SCRAPER_MODULES.has(entry.name),
      )
      .map((entry) => makeNode("scraper", `scraper/${entry.name}`));
  } catch {
    warnings.push("scraper directory missing: scraper");
    return [];
  }
}

async function scanWorkflows(warnings: string[]): Promise<SystemMapNode[]> {
  try {
    const entries = await fs.readdir(WORKFLOWS_DIR, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".yml"))
      .map((entry) => makeNode("workflow", `.github/workflows/${entry.name}`));
  } catch {
    warnings.push("workflow directory missing: .github/workflows");
    return [];
  }
}

function sortNodes(nodes: SystemMapNode[]): SystemMapNode[] {
  return [...nodes].sort((a, b) => {
    if (a.kind === b.kind) return a.label.localeCompare(b.label);
    return a.kind.localeCompare(b.kind);
  });
}

async function buildSystemMapSnapshot(): Promise<SystemMap> {
  const warnings: string[] = [];
  const scanned = await Promise.all([
    scanComponents(warnings),
    scanApiRoutes(warnings),
    scanScrapers(warnings),
    scanWorkflows(warnings),
  ]);

  const dedup = new Map<string, SystemMapNode>();
  for (const group of scanned) {
    for (const node of group) {
      dedup.set(node.id, node);
    }
  }

  let sourceMap: SystemMap = {
    version: "0.0.0",
    updated: "",
    agents: [],
    skills: [],
    scraperGroups: [],
    dataFlow: [],
    actions: [],
    flows: [],
  };

  try {
    const raw = await fs.readFile(SYSTEM_MAP_SRC, "utf8");
    sourceMap = JSON.parse(raw) as SystemMap;
  } catch {
    warnings.push("system map source missing or invalid: docs/architecture/system-map.json");
  }

  return {
    ...sourceMap,
    nodes: sortNodes(Array.from(dedup.values())),
    scanWarnings: warnings,
  };
}

async function main(): Promise<void> {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const systemMapSnapshot = await buildSystemMapSnapshot();
  await fs.writeFile(OUT_SYSTEM_MAP, JSON.stringify(systemMapSnapshot, null, 2) + "\n", "utf8");
  console.log(
    `[specs-snapshot] wrote system map (${systemMapSnapshot.nodes?.length ?? 0} nodes) → ${path.relative(REPO_ROOT, OUT_SYSTEM_MAP)}`,
  );
}

main().catch((err) => {
  console.error("[specs-snapshot] failed:", err);
  process.exit(1);
});
