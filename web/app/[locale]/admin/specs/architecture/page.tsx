import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import AdminTabNav from "@/components/AdminTabNav";
import ArchitectureFlowExplorer from "@/components/ArchitectureFlowExplorer";
import { getSystemMap } from "@/lib/specs/reader";
import type { Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

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

  const totalScrapers = map.scraperGroups.reduce((acc, g) => acc + g.members.length, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="specs" />

      <div className="mb-4">
        <Link
          href={`/${locale}/admin/specs`}
          className="text-sm text-fg-muted hover:text-green-700"
        >
          {t("back")}
        </Link>
      </div>

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-fg-strong">{t("title")}</h1>
        <p className="text-sm text-fg-muted mt-1">{t("subtitle")}</p>
      </header>

      <div className="grid grid-cols-3 gap-3 mb-6 max-w-md">
        <div className="bg-elevated rounded p-3">
          <p className="text-xs text-fg-muted">{t("scrapers")}</p>
          <p className="text-2xl font-bold text-fg-strong">{totalScrapers}</p>
        </div>
        <div className="bg-elevated rounded p-3">
          <p className="text-xs text-fg-muted">{t("agents")}</p>
          <p className="text-2xl font-bold text-fg-strong">{map.agents.length}</p>
        </div>
        <div className="bg-elevated rounded p-3">
          <p className="text-xs text-fg-muted">{t("skills")}</p>
          <p className="text-2xl font-bold text-fg-strong">{map.skills.length}</p>
        </div>
      </div>

      <ArchitectureFlowExplorer
        map={map}
        labels={{
          explorerTitle: t("explorerTitle"),
          explorerDesc: t("explorerDesc"),
          actionLabel: t("actionLabel"),
          searchLabel: t("searchLabel"),
          searchPlaceholder: t("searchPlaceholder"),
          reset: t("reset"),
          noFlow: t("noFlow"),
          stepsTitle: t("stepsTitle"),
          annotationsTitle: t("annotationsTitle"),
          evidenceLabel: t("evidenceLabel"),
          channelLabel: t("channelLabel"),
          payloadLabel: t("payloadLabel"),
          nodesCount: t("nodesCount"),
          actionsCount: t("actionsCount"),
          flowsCount: t("flowsCount"),
        }}
      />

      <section className="mb-6">
        <h2 className="text-lg font-semibold text-fg-strong mb-3">{t("scraperGroups")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {map.scraperGroups.map((g) => (
            <div key={g.id} className="border border-line rounded p-3">
              <h3 className="text-sm font-medium text-fg-strong mb-1">
                {g.label}{" "}
                <span className="text-xs text-fg-subtle">({g.members.length})</span>
              </h3>
              <p className="text-xs text-fg-muted leading-relaxed">{g.members.join(", ")}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
