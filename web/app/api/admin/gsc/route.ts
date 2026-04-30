import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

// Google Search Console API via service account
// Required env vars:
//   GSC_SERVICE_ACCOUNT_EMAIL  — service account email
//   GSC_SERVICE_ACCOUNT_KEY    — private key (PEM, newlines as \n)
//   GSC_SITE_URL               — e.g. https://tokyo-taiwan-radar.vercel.app/
//
// Setup steps:
//   1. Google Cloud Console → Create service account → Download JSON key
//   2. Google Search Console → Settings → Users and permissions → Add service account email (Restricted)
//   3. Set the three env vars above in Vercel dashboard

const GSC_SITE_URL =
  process.env.GSC_SITE_URL ?? process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app/";

async function getAccessToken(): Promise<string> {
  const email = process.env.GSC_SERVICE_ACCOUNT_EMAIL;
  const key = process.env.GSC_SERVICE_ACCOUNT_KEY?.replace(/\\n/g, "\n");
  if (!email || !key) throw new Error("GSC credentials not configured");

  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const payload = {
    iss: email,
    scope: "https://www.googleapis.com/auth/webmasters.readonly",
    aud: "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now,
  };

  const encode = (obj: object) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");

  const signingInput = `${encode(header)}.${encode(payload)}`;

  // Import RSA private key
  const pemBody = key.replace(/-----[^-]+-----/g, "").replace(/\s/g, "");
  const der = Uint8Array.from(atob(pemBody), (c) => c.charCodeAt(0));
  const cryptoKey = await crypto.subtle.importKey(
    "pkcs8",
    der,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    cryptoKey,
    new TextEncoder().encode(signingInput)
  );

  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");

  const jwt = `${signingInput}.${sigB64}`;

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
  });

  const tokenData = await tokenRes.json();
  if (!tokenData.access_token) throw new Error(`Token error: ${JSON.stringify(tokenData)}`);
  return tokenData.access_token;
}

export async function GET() {
  // Auth check
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  // Check credentials configured
  if (!process.env.GSC_SERVICE_ACCOUNT_EMAIL || !process.env.GSC_SERVICE_ACCOUNT_KEY) {
    return NextResponse.json({ configured: false });
  }

  try {
    const token = await getAccessToken();
    const siteEncoded = encodeURIComponent(GSC_SITE_URL);

    // Parallel: indexed pages count + top queries (last 28 days)
    const endDate = new Date().toISOString().slice(0, 10);
    const startDate = new Date(Date.now() - 28 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

    const [indexRes, queryRes] = await Promise.all([
      // Indexed pages via URL Inspection is limited; use Search Analytics sum instead
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
