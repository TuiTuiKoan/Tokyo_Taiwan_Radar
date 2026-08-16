export type ParallelOrganizerFields = {
  names: string[] | null;
  types: string[] | null;
};

export function normalizeCommaSeparatedArray(value: unknown): string[] | null {
  const parts = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : typeof value === "string"
      ? value.split(/[,，、]/)
      : [];
  const cleaned = parts.map((item) => item.trim()).filter(Boolean);
  return cleaned.length > 0 ? cleaned : null;
}

export function alignParallelOrganizerTypes(
  value: unknown,
  previousNames?: unknown,
  previousTypes?: unknown,
): ParallelOrganizerFields {
  const names = normalizeCommaSeparatedArray(value);
  if (!names) return { names: null, types: null };

  const oldNames = normalizeCommaSeparatedArray(previousNames) ?? [];
  const oldTypes = Array.isArray(previousTypes) ? previousTypes : [];
  const typeQueues = new Map<string, string[]>();

  oldNames.forEach((name, index) => {
    const type = typeof oldTypes[index] === "string" && oldTypes[index].trim()
      ? oldTypes[index].trim()
      : "unknown";
    const queue = typeQueues.get(name) ?? [];
    queue.push(type);
    typeQueues.set(name, queue);
  });

  const types = names.map((name) => typeQueues.get(name)?.shift() ?? "unknown");
  return { names, types };
}
