import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import AdminTabNav from "@/components/AdminTabNav";
import { listSpecs, getSnapshotMeta } from "@/lib/specs/reader";
import type { Locale } from "@/lib/types";
import type { SpecColumn } from "@/lib/specs/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

const COLUMNS: SpecColumn[] = ["parked", "todo", "doing", "done"];

function formatDate(iso: string): string {
  try {
    return iso.slice(0, 10);
  } catch {
    return iso;
  }
}

export default async function AdminSpecsPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin.specs");
  const tCard = await getTranslations("admin.specs.card");
  const tKanban = await getTranslations("admin.specs.kanban");

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

  const specs = listSpecs();
  const meta = getSnapshotMeta();

  const grouped: Record<SpecColumn, typeof specs> = {
    parked: [],
    todo: [],
    doing: [],
    done: [],
  };
  for (const s of specs) grouped[s.column].push(s);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="specs" />

      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg-strong">{t("title")}</h1>
          <p className="text-sm text-fg-muted mt-1">{t("subtitle")}</p>
        </div>
        <Link
          href={`/${locale}/admin/specs/architecture`}
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-green-600 text-green-700 rounded hover:bg-green-50 transition"
        >
          {t("architecture.viewArchitecture")}
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {COLUMNS.map((col) => (
          <section
            key={col}
            className="bg-elevated rounded-lg p-3 border border-line min-h-[120px]"
          >
            <header className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-fg">{tKanban(col)}</h2>
              <span className="text-xs text-fg-subtle px-2 py-0.5 bg-surface rounded">
                {grouped[col].length}
              </span>
            </header>
            <div className="space-y-2">
              {grouped[col].length === 0 ? (
                <p className="text-xs text-fg-subtle italic px-1">{tKanban("empty")}</p>
              ) : (
                grouped[col].map((spec) => (
                  <Link
                    key={spec.slug}
                    href={`/${locale}/admin/specs/${spec.slug}`}
                    className="block bg-surface rounded border border-line p-3 hover:border-green-500 hover:shadow-sm transition"
                  >
                    <h3 className="text-sm font-medium text-fg-strong leading-snug mb-2">
                      {spec.title}
                    </h3>
                    {spec.tasks.total > 0 && (
                      <div className="mb-2">
                        <div className="flex items-center justify-between text-xs text-fg-muted mb-1">
                          <span>
                            {tCard("tasksProgress", {
                              done: spec.tasks.done,
                              total: spec.tasks.total,
                            })}
                          </span>
                          <span>
                            {Math.round((spec.tasks.done / spec.tasks.total) * 100)}%
                          </span>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500"
                            style={{
                              width: `${Math.min(
                                100,
                                (spec.tasks.done / spec.tasks.total) * 100,
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                    {spec.branch && (
                      <p className="text-[11px] text-fg-muted font-mono truncate mb-1">
                        {spec.branch}
                      </p>
                    )}
                    {spec.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-1">
                        {spec.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-1.5 py-0.5 bg-muted text-fg-muted rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="text-[11px] text-fg-subtle">
                      {tCard("updatedAt", { date: formatDate(spec.updatedAt) })}
                    </p>
                  </Link>
                ))
              )}
            </div>
          </section>
        ))}
      </div>

      <p className="mt-6 text-[11px] text-fg-subtle">
        snapshot: {formatDate(meta.generatedAt)}
        {meta.commitSha ? ` · ${meta.commitSha.slice(0, 7)}` : ""}
      </p>
    </div>
  );
}
