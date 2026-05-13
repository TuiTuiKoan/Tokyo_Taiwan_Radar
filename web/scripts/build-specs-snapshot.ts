/**
 * Build-time snapshot generator for the spec dashboard.
 *
 * Reads `docs/specs/{parked,active,archive}/...` and `docs/architecture/system-map.json`
 * from the repo root, then writes JSON snapshots into `web/lib/specs/` so that the
 * Next.js runtime can read them via `import` without filesystem access.
 *
 * Vercel-safe: pure fs operations, no git subprocess. Uses `process.env.VERCEL_GIT_COMMIT_SHA`
 * when available; falls back to file mtime for `updatedAt`.
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import type {
  Spec,
  SpecColumn,
  SpecStatus,
  SpecsSnapshot,
  SpecTaskProgress,
  SystemMap,
  SystemMapNode,
  SystemMapNodeKind,
} from "../lib/specs/types";

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const DOCS_SPECS = path.join(REPO_ROOT, "docs", "specs");
const SYSTEM_MAP_SRC = path.join(REPO_ROOT, "docs", "architecture", "system-map.json");
const OUT_DIR = path.resolve(__dirname, "..", "lib", "specs");
const OUT_SPECS = path.join(OUT_DIR, "specs-snapshot.json");
const OUT_SYSTEM_MAP = path.join(OUT_DIR, "system-map.json");

const STATUS_DIRS: SpecStatus[] = ["parked", "active", "archived"];
const STATUS_DIR_MAP: Record<SpecStatus, string> = {
  parked: "parked",
  active: "active",
  archived: "archive",
};

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

function parseTaskProgress(md: string): SpecTaskProgress {
  if (!md) return { done: 0, total: 0 };
  const done = (md.match(/^\s*[-*]\s+\[x\]/gim) ?? []).length;
  const todo = (md.match(/^\s*[-*]\s+\[ \]/gim) ?? []).length;
  return { done, total: done + todo };
}

function deriveColumn(status: SpecStatus, tasks: SpecTaskProgress): SpecColumn {
  if (status === "archived") return "done";
  if (status === "parked") return "parked";
  if (tasks.total === 0) return "todo";
  if (tasks.done >= tasks.total) return "done";
  if (tasks.done === 0) return "todo";
  return "doing";
}

async function readIfExists(p: string): Promise<string> {
  try {
    return await fs.readFile(p, "utf8");
  } catch {
    return "";
  }
}

async function statMtime(p: string): Promise<Date | null> {
  try {
    const st = await fs.stat(p);
    return st.mtime;
  } catch {
    return null;
  }
}

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

async function loadSpecFromDir(
  status: SpecStatus,
  slug: string,
  dir: string,
): Promise<Spec | null> {
  const proposalPath = path.join(dir, "proposal.md");
  const tasksPath = path.join(dir, "tasks.md");
  const notesPath = path.join(dir, "notes.md");

  const proposalRaw = await readIfExists(proposalPath);
  if (!proposalRaw) return null;

  const tasksRaw = await readIfExists(tasksPath);
  const notesRaw = await readIfExists(notesPath);

  const fm = matter(proposalRaw);
  const data = fm.data as Record<string, unknown>;

  const title = typeof data.title === "string" && data.title.trim() ? data.title : slug;
  const branch = typeof data.branch === "string" ? data.branch : undefined;
  const created = typeof data.created === "string" ? data.created : undefined;
  const tags = Array.isArray(data.tags)
    ? (data.tags.filter((t) => typeof t === "string") as string[])
    : [];
  const fmStatus = (typeof data.status === "string" ? data.status : status) as SpecStatus;
  const finalStatus: SpecStatus = STATUS_DIRS.includes(fmStatus) ? fmStatus : status;

  const tasks = parseTaskProgress(tasksRaw);
  const column = deriveColumn(finalStatus, tasks);

  // Latest mtime among the three files = "last touched"
  const mtimes = await Promise.all([proposalPath, tasksPath, notesPath].map(statMtime));
  const latest = mtimes
    .filter((m): m is Date => m !== null)
    .reduce<Date | null>((acc, m) => (acc && acc > m ? acc : m), null);

  return {
    slug,
    title,
    status: finalStatus,
    column,
    branch,
    created,
    tags,
    relativePath: `${STATUS_DIR_MAP[finalStatus]}/${slug}`,
    proposalMd: fm.content.trimStart(),
    tasksMd: tasksRaw,
    notesMd: notesRaw,
    tasks,
    updatedAt: (latest ?? new Date()).toISOString(),
  };
}

async function loadSingleFileSpec(
  status: SpecStatus,
  fileName: string,
  filePath: string,
): Promise<Spec | null> {
  const slug = fileName.replace(/\.md$/, "");
  const proposalRaw = await readIfExists(filePath);
  if (!proposalRaw) return null;

  const fm = matter(proposalRaw);
  const data = fm.data as Record<string, unknown>;
  const title = typeof data.title === "string" && data.title.trim() ? data.title : slug;
  const branch = typeof data.branch === "string" ? data.branch : undefined;
  const created = typeof data.created === "string" ? data.created : undefined;
  const tags = Array.isArray(data.tags)
    ? (data.tags.filter((t) => typeof t === "string") as string[])
    : [];
  const fmStatus = (typeof data.status === "string" ? data.status : status) as SpecStatus;
  const finalStatus: SpecStatus = STATUS_DIRS.includes(fmStatus) ? fmStatus : status;

  const tasks: SpecTaskProgress = { done: 0, total: 0 };
  const column = deriveColumn(finalStatus, tasks);
  const mt = await statMtime(filePath);

  return {
    slug,
    title,
    status: finalStatus,
    column,
    branch,
    created,
    tags,
    relativePath: `${STATUS_DIR_MAP[finalStatus]}/${fileName}`,
    proposalMd: fm.content.trimStart(),
    tasksMd: "",
    notesMd: "",
    tasks,
    updatedAt: (mt ?? new Date()).toISOString(),
  };
}

async function listSpecsForStatus(status: SpecStatus): Promise<Spec[]> {
  const dirName = STATUS_DIR_MAP[status];
  const root = path.join(DOCS_SPECS, dirName);
  let entries: import("node:fs").Dirent[];
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    return [];
  }
  const specs: Spec[] = [];
  for (const entry of entries) {
    if (entry.name.startsWith("_") || entry.name.startsWith(".")) continue;
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) {
      const spec = await loadSpecFromDir(status, entry.name, full);
      if (spec) specs.push(spec);
    } else if (entry.isFile() && entry.name.endsWith(".md") && entry.name !== "README.md") {
      const spec = await loadSingleFileSpec(status, entry.name, full);
      if (spec) specs.push(spec);
    }
  }
  return specs;
}

async function main(): Promise<void> {
  await fs.mkdir(OUT_DIR, { recursive: true });

  const all: Spec[] = [];
  for (const status of STATUS_DIRS) {
    const list = await listSpecsForStatus(status);
    all.push(...list);
  }
  all.sort((a, b) => (a.updatedAt > b.updatedAt ? -1 : 1));

  const snapshot: SpecsSnapshot = {
    generatedAt: new Date().toISOString(),
    commitSha: process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA || undefined,
    specs: all,
  };

  await fs.writeFile(OUT_SPECS, JSON.stringify(snapshot, null, 2) + "\n", "utf8");

  const systemMapSnapshot = await buildSystemMapSnapshot();
  await fs.writeFile(OUT_SYSTEM_MAP, JSON.stringify(systemMapSnapshot, null, 2) + "\n", "utf8");

  console.log(`[specs-snapshot] wrote ${all.length} specs → ${path.relative(REPO_ROOT, OUT_SPECS)}`);
}

main().catch((err) => {
  console.error("[specs-snapshot] failed:", err);
  process.exit(1);
});
