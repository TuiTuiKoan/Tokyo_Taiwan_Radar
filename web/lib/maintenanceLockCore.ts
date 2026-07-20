export type WritesAllowed =
  | { allowed: true }
  | { allowed: false; reason: "maintenance_active" };

export type MaintenanceLockReader = (
  url: string,
  serviceKey: string,
) => Promise<{ data: unknown; error: unknown }>;

const DENIED: WritesAllowed = { allowed: false, reason: "maintenance_active" };

export async function evaluateMaintenanceLockRead(options: {
  url: string | undefined;
  serviceKey: string | undefined;
  readLock: MaintenanceLockReader;
}): Promise<WritesAllowed> {
  const { url, serviceKey, readLock } = options;
  if (!url || !serviceKey) return DENIED;

  try {
    const { data, error } = await readLock(url, serviceKey);
    if (error || !Array.isArray(data) || data.length === 0) return DENIED;

    const row = data[0];
    if (row === null || typeof row !== "object" || Array.isArray(row)) return DENIED;

    const value = (row as { value?: unknown }).value;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      if ((value as { active?: unknown }).active === false) {
        return { allowed: true };
      }
    }
  } catch {
    return DENIED;
  }

  return DENIED;
}
