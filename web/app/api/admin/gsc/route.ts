import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

// Google Search Console API via OAuth2 refresh token
// Required env vars:
//   GSC_CLIENT_ID      — OAuth2 client ID
//   GSC_CLIENT_SECRET  — OAuth2 client secret
//   GSC_REFRESH_TOKEN  — refresh token from OAuth Playground
//   GSC_SITE_URL       — e.g. https://tokyotaiwanradar.com/

const GSC_SITE_URL =
  process.env.GSC_SITE_URL ?? process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com/";

async function getAccessToken(): Promise<string> {
  const clientId = process.env.GSC_CLIENT_ID;
  const clientSecret = process.env.GSC_CLIENT_SECRET;
  const refreshToken = process.env.GSC_REFRESH_TOKEN;
  if (!clientId || !clientSecret || !refreshToken) throw new Error("GSC credentials not configured");

  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
  });
  const data = await res.json();
  if (!data.access_token) throw new Error(`Token error: ${JSON.stringify(data)}`);
  return data.access_token;
}

export async function GET() {
  // Auth check
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  // Check credentials configured
  if (!process.env.GSC_CLIENT_ID || !process.env.GSC_CLIENT_SECRET || !process.env.GSC_REFRESH_TOKEN) {
    return NextResponse.json({ configured: false });
  }

  try {
    const token = await getAccessToken();
    const siteEncoded = encodeURIComponent(GSC_SITE_URL);

    const endDate = new Date().toISOString().slice(0, 10);
    const startDate = new Date(Date.now() - 28 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

    const [indexRes, queryRes] = await Promise.all([
      fetch(
        `https://searchconsole.googleapis.com/webmasters/v3/sites/${siteEncoded}/searchAnalytics/query`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            startDate,
            endDate,
            dimensions: ["page"],
            rowLimit: 1000,
            aggregationType: "byPage",
          }),
        }
      ),
      fetch(
        `https://searchconsole.googleapis.com/webmasters/v3/sites/${siteEncoded}/searchAnalytics/query`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            startDate,
            endDate,
            dimensions: ["query"],
            rowLimit: 20,
          }),
        }
      ),
    ]);

    const [indexData, queryData] = await Promise.all([indexRes.json(), queryRes.json()]);

    const indexedPages = (indexData.rows ?? []).length;
    const totalClicks = (indexData.rows ?? []).reduce((s: number, r: { clicks: number }) => s + r.clicks, 0);
    const totalImpressions = (indexData.rows ?? []).reduce((s: number, r: { impressions: number }) => s + r.impressions, 0);

    const topQueries = (queryData.rows ?? []).slice(0, 10).map((r: {
      keys: string[];
      clicks: number;
      impressions: number;
      ctr: number;
      position: number;
    }) => ({
      query: r.keys[0],
      clicks: r.clicks,
      impressions: r.impressions,
      ctr: Math.round(r.ctr * 1000) / 10,
      position: Math.round(r.position * 10) / 10,
    }));

    return NextResponse.json({
      configured: true,
      period: { startDate, endDate },
      indexedPages,
      totalClicks,
      totalImpressions,
      topQueries,
    });
  } catch (err) {
    return NextResponse.json({ configured: true, error: String(err) }, { status: 500 });
  }
}
