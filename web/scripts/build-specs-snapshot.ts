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

  // Copy system-map.json (best-effort)
  try {
    const sm = await fs.readFile(SYSTEM_MAP_SRC, "utf8");
    await fs.writeFile(OUT_SYSTEM_MAP, sm, "utf8");
  } catch {
    await fs.writeFile(
      OUT_SYSTEM_MAP,
      JSON.stringify(
        { version: "0.0.0", updated: "", agents: [], skills: [], scraperGroups: [], dataFlow: [] },
        null,
        2,
      ) + "\n",
      "utf8",
    );
  }

  // eslint-disable-next-line no-console
  console.log(`[specs-snapshot] wrote ${all.length} specs → ${path.relative(REPO_ROOT, OUT_SPECS)}`);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[specs-snapshot] failed:", err);
  process.exit(1);
});
