export interface GscTopQuery {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface GscTopPage {
  page: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface GscStats {
  configured: boolean;
  error?: string;
  period?: { startDate: string; endDate: string };
  indexedPages?: number;
  totalClicks?: number;
  totalImpressions?: number;
  avgCtr?: number;
  avgPosition?: number;
  topQueries?: GscTopQuery[];
  topPages?: GscTopPage[];
}

interface GscRow {
  keys: string[];
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

const GSC_SITE_URL =
  process.env.GSC_SITE_URL ?? process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com/";

function round(value: number, digits: number) {
  const p = 10 ** digits;
  return Math.round(value * p) / p;
}

async function getAccessToken(): Promise<string> {
  const clientId = process.env.GSC_CLIENT_ID;
  const clientSecret = process.env.GSC_CLIENT_SECRET;
  const refreshToken = process.env.GSC_REFRESH_TOKEN;

  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error("GSC credentials not configured");
  }

  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
    signal: AbortSignal.timeout(10000),
  });

  const data = await res.json();
  if (!res.ok || !data.access_token) {
    throw new Error(`Token error: ${JSON.stringify(data)}`);
  }

  return data.access_token;
}

async function fetchSearchAnalytics(token: string, body: Record<string, unknown>): Promise<GscRow[]> {
  const siteEncoded = encodeURIComponent(GSC_SITE_URL);
  const res = await fetch(
    `https://searchconsole.googleapis.com/webmasters/v3/sites/${siteEncoded}/searchAnalytics/query`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    }
  );

  const data = await res.json();
  if (!res.ok) {
    throw new Error(`GSC query error ${res.status}: ${JSON.stringify(data)}`);
  }

  return (data.rows ?? []) as GscRow[];
}

export async function fetchGscStats(): Promise<GscStats> {
  if (!process.env.GSC_CLIENT_ID || !process.env.GSC_CLIENT_SECRET || !process.env.GSC_REFRESH_TOKEN) {
    return { configured: false };
  }

  try {
    const token = await getAccessToken();
    const endDate = new Date().toISOString().slice(0, 10);
    const startDate = new Date(Date.now() - 28 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

    const [pageRows, queryRows] = await Promise.all([
      fetchSearchAnalytics(token, {
        startDate,
        endDate,
        dimensions: ["page"],
        rowLimit: 1000,
        aggregationType: "byPage",
      }),
      fetchSearchAnalytics(token, {
        startDate,
        endDate,
        dimensions: ["query"],
        rowLimit: 20,
      }),
    ]);

    const totalClicks = pageRows.reduce((sum, row) => sum + (row.clicks ?? 0), 0);
    const totalImpressions = pageRows.reduce((sum, row) => sum + (row.impressions ?? 0), 0);
    const weightedPositionNumerator = pageRows.reduce(
      (sum, row) => sum + (row.position ?? 0) * (row.impressions ?? 0),
      0
    );

    const avgCtr = totalImpressions > 0 ? round((totalClicks / totalImpressions) * 100, 1) : 0;
    const avgPosition = totalImpressions > 0 ? round(weightedPositionNumerator / totalImpressions, 1) : 0;

    const topQueries = queryRows.slice(0, 10).map((row) => ({
      query: row.keys[0] ?? "",
      clicks: row.clicks ?? 0,
      impressions: row.impressions ?? 0,
      ctr: round((row.ctr ?? 0) * 100, 1),
      position: round(row.position ?? 0, 1),
    }));

    const topPages = pageRows
      .sort((a, b) => b.clicks - a.clicks)
      .slice(0, 10)
      .map((row) => ({
        page: row.keys[0] ?? "",
        clicks: row.clicks ?? 0,
        impressions: row.impressions ?? 0,
        ctr: round((row.ctr ?? 0) * 100, 1),
        position: round(row.position ?? 0, 1),
      }));

    return {
      configured: true,
      period: { startDate, endDate },
      indexedPages: pageRows.length,
      totalClicks,
      totalImpressions,
      avgCtr,
      avgPosition,
      topQueries,
      topPages,
    };
  } catch (error) {
    return {
      configured: true,
      error: String(error),
    };
  }
}
