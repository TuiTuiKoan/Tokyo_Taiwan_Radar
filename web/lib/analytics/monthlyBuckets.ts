/**
 * Analytics Monthly Buckets Helper
 */

/**
 * Generates an array of YYYY-MM string buckets within the date range.
 * Clamps or returns a max range of 24 months to avoid excessive payloads.
 */
export function buildMonthRange(fromMonth: string, toMonth: string): string[] {
  const months: string[] = [];
  const start = new Date(fromMonth + "-01T00:00:00Z");
  const end = new Date(toMonth + "-01T00:00:00Z");

  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return [];
  }

  // Swap if start is after end
  let curr = new Date(Math.min(start.getTime(), end.getTime()));
  const target = new Date(Math.max(start.getTime(), end.getTime()));

  // Cap loop to maximum of 24 months to avoid infinite loops or memory bloat
  let count = 0;
  while (curr <= target && count < 24) {
    const yyyy = curr.getUTCFullYear();
    const mm = String(curr.getUTCMonth() + 1).padStart(2, "0");
    months.push(`${yyyy}-${mm}`);
    
    // Add 1 month
    curr.setUTCMonth(curr.getUTCMonth() + 1);
    count++;
  }

  return months;
}

export interface MonthlyBucketResult {
  month: string;
  collected: number;
  ongoing: number;
}

interface EventLike {
  created_at: string;
  start_date: string;
  end_date?: string | null;
}

/**
 * Matches collected count for each month (bucketed by created_at)
 */
export function bucketCollected(events: EventLike[], months: string[]): Record<string, number> {
  const result: Record<string, number> = {};
  for (const m of months) {
    result[m] = 0;
  }

  for (const e of events) {
    if (!e.created_at) continue;
    // created_at is JST/UTC string, just check prefix YYYY-MM
    const yymm = e.created_at.substring(0, 7);
    if (yymm in result) {
      result[yymm]++;
    }
  }

  return result;
}

/**
 * Matches ongoing count for each month:
 * start_date <= monthEnd AND coalesce(end_date, start_date) >= monthStart
 */
export function bucketOngoing(events: EventLike[], months: string[]): Record<string, number> {
  const result: Record<string, number> = {};
  for (const m of months) {
    result[m] = 0;
  }

  for (const e of events) {
    if (!e.start_date) continue;
    const startStr = e.start_date; // YYYY-MM-DD
    const endStr = e.end_date || startStr; // coalesce

    for (const m of months) {
      const startDayStr = `${m}-01`;
      // Calculate last day of this month
      const parts = m.split("-");
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10);
      const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
      const endDayStr = `${m}-${String(lastDay).padStart(2, "0")}`;

      if (startStr <= endDayStr && endStr >= startDayStr) {
        result[m]++;
      }
    }
  }

  return result;
}
