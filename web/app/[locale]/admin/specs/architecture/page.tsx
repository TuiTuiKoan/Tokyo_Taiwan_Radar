import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import AdminTabNav from "@/components/AdminTabNav";
import Mermaid from "@/components/Mermaid";
import { getSystemMap } from "@/lib/specs/reader";
import type { Locale } from "@/lib/types";
import type { SystemMap } from "@/lib/specs/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

function sanitize(id: string): string {
  return id.replace(/[^a-zA-Z0-9_]/g, "_");
}

function buildMermaid(map: SystemMap): string {
  const lines: string[] = ["graph TD"];
  // Subgraph: Scrapers (groups)
  lines.push("  subgraph Scrapers");
  for (const g of map.scraperGroups) {
    const gid = `g_${sanitize(g.id)}`;
    lines.push(`    ${gid}["${g.label}<br/>(${g.members.length})"]`);
  }
  lines.push("  end");

  // Pipeline nodes
  lines.push('  merger["merger.py"]');
  lines.push('  annotator["annotator.py"]');
  lines.push('  supabase[("Supabase DB")]');
  lines.push('  web["Next.js Web"]');
  lines.push('  auto_qa["auto_qa.py"]');
  lines.push('  reports["event_reports"]');

  // Scrapers → merger
  for (const g of map.scraperGroups) {
    const gid = `g_${sanitize(g.id)}`;
    lines.push(`  ${gid} --> merger`);
  }
  // Pipeline edges
  lines.push("  merger --> annotator");
  lines.push("  annotator --> supabase");
  lines.push("  supabase --> web");
  lines.push("  auto_qa --> reports");
  lines.push("  reports --> web");

  // Agents subgraph
  lines.push("  subgraph Agents");
  for (const a of map.agents) {
    const aid = `a_${sanitize(a.id)}`;
    lines.push(`    ${aid}["${a.label}"]`);
  }
  lines.push("  end");

  // Style
  lines.push("  classDef pipeline fill:#dcfce7,stroke:#16a34a;");
  lines.push("  class merger,annotator,supabase,web,auto_qa,reports pipeline;");
  return lines.join("\n");
}

export default async function ArchitecturePage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin.specs.architecture");

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  const map = getSystemMap();
  const chart = buildMermaid(map);

  const totalScrapers = map.scraperGroups.reduce((acc, g) => acc + g.members.length, 0);

  const fallback = (
    <div className="space-y-3 text-sm">
      <details className="border border-gray-200 rounded p-3">
        <summary className="font-medium cursor-pointer">JSON</summary>
        <pre className="mt-2 text-xs overflow-x-auto bg-gray-50 p-3 rounded">
          {JSON.stringify(map, null, 2)}
        </pre>
      </details>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="specs" />

      <div className="mb-4">
        <Link
          href={`/${locale}/admin/specs`}
          className="text-sm text-gray-500 hover:text-green-700"
        >
          {t("back")}
        </Link>
      </div>

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
      </header>

      <div className="grid grid-cols-3 gap-3 mb-6 max-w-md">
        <div className="bg-gray-50 rounded p-3">
          <p className="text-xs text-gray-500">{t("scrapers")}</p>
          <p className="text-2xl font-bold text-gray-900">{totalScrapers}</p>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <p className="text-xs text-gray-500">{t("agents")}</p>
          <p className="text-2xl font-bold text-gray-900">{map.agents.length}</p>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <p className="text-xs text-gray-500">{t("skills")}</p>
          <p className="text-2xl font-bold text-gray-900">{map.skills.length}</p>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <Mermaid chart={chart} fallback={fallback} />
      </div>

      <section className="mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">{t("scraperGroups")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {map.scraperGroups.map((g) => (
            <div key={g.id} className="border border-gray-200 rounded p-3">
              <h3 className="text-sm font-medium text-gray-900 mb-1">
                {g.label}{" "}
                <span className="text-xs text-gray-400">({g.members.length})</span>
              </h3>
              <p className="text-xs text-gray-500 leading-relaxed">{g.members.join(", ")}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
