import { createSign } from "crypto";
import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

// Google Search Console API via Service Account (JWT bearer)
// No expiry — key is valid until revoked in Google Cloud Console.
// Required env vars:
//   GSC_SERVICE_ACCOUNT_EMAIL — service account email (xxx@project.iam.gserviceaccount.com)
//   GSC_SERVICE_ACCOUNT_KEY   — service account private key, PEM format
//                               (in Vercel: paste full PEM; literal \n stored by Vercel are fine)
//   GSC_SITE_URL              — e.g. https://tokyotaiwanradar.com/
//
// Setup:
//   1. Google Cloud Console → IAM → Service Accounts → create account
//   2. Keys tab → Add key → JSON → extract "client_email" and "private_key"
//   3. Google Search Console → Settings → Users and permissions → Add user
//      (use the service account email, at least "Restricted" permission)

const GSC_SITE_URL =
  process.env.GSC_SITE_URL ?? process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com/";

function b64url(buf: Buffer | string): string {
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(buf as string);
  return b.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

async function getAccessToken(): Promise<string> {
  const email = process.env.GSC_SERVICE_ACCOUNT_EMAIL;
  // Vercel stores newlines as literal \n — restore them
  const key = process.env.GSC_SERVICE_ACCOUNT_KEY?.replace(/\\n/g, "\n");
  if (!email || !key) throw new Error("GSC credentials not configured");

  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({
    iss: email,
    scope: "https://www.googleapis.com/auth/webmasters.readonly",
    aud: "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now,
  }));
  const signer = createSign("RSA-SHA256");
  signer.write(`${header}.${claim}`);
  signer.end();
  const jwt = `${header}.${claim}.${b64url(signer.sign(key))}`;

  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: jwt,
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
  if (!process.env.GSC_SERVICE_ACCOUNT_EMAIL || !process.env.GSC_SERVICE_ACCOUNT_KEY) {
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
