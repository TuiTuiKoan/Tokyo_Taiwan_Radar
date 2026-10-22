/**
 * Runtime API for the architecture map at /admin/specs/architecture. Reads the
 * system map that `scripts/build-specs-snapshot.ts` writes at build time.
 */
import type { SystemMap } from "./types";
import systemMapJson from "./system-map.json";

const systemMap = systemMapJson as SystemMap;

export function getSystemMap(): SystemMap {
  return systemMap;
}
