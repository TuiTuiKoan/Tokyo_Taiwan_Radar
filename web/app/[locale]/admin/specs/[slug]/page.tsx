import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import AdminTabNav from "@/components/AdminTabNav";
import SpecTabs from "@/components/SpecTabs";
import CopyCopilotPrompt from "@/components/CopyCopilotPrompt";
import { getSpec, buildCopilotPrompt } from "@/lib/specs/reader";
import type { Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale; slug: string }>;
}

export const dynamic = "force-dynamic";

function formatDate(iso: string | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

export default async function SpecDetailPage({ params }: PageProps) {
  const { locale, slug } = await params;
  const t = await getTranslations("admin.specs");
  const tDetail = await getTranslations("admin.specs.detail");

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

  const spec = getSpec(slug);
  if (!spec) notFound();

  const prompt = buildCopilotPrompt(spec);
  const statusBadge =
    spec.status === "active"
      ? "bg-green-100 text-green-700"
      : spec.status === "parked"
        ? "bg-gray-100 text-gray-600"
        : "bg-blue-100 text-blue-700";

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="specs" />

      <div className="mb-4">
        <Link
          href={`/${locale}/admin/specs`}
          className="text-sm text-gray-500 hover:text-green-700"
        >
          {tDetail("back")}
        </Link>
      </div>

      <header className="mb-6 pb-4 border-b border-gray-200">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded ${statusBadge}`}>
                {spec.status}
              </span>
              {spec.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded"
                >
                  {tag}
                </span>
              ))}
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">{spec.title}</h1>
            <dl className="text-sm text-gray-500 space-y-1">
              {spec.branch && (
                <div className="flex gap-2">
                  <dt className="font-medium">{tDetail("branch")}:</dt>
                  <dd className="font-mono">{spec.branch}</dd>
                </div>
              )}
              {spec.created && (
                <div className="flex gap-2">
                  <dt className="font-medium">{tDetail("created")}:</dt>
                  <dd>{formatDate(spec.created)}</dd>
                </div>
              )}
              <div className="flex gap-2">
                <dt className="font-medium">{tDetail("updated")}:</dt>
                <dd>{formatDate(spec.updatedAt)}</dd>
              </div>
              {spec.tasks.total > 0 && (
                <div className="flex gap-2">
                  <dt className="font-medium">
                    {tDetail("tasksProgress", {
                      done: spec.tasks.done,
                      total: spec.tasks.total,
                    })}
                  </dt>
                  <dd>
                    {Math.round((spec.tasks.done / spec.tasks.total) * 100)}%
                  </dd>
                </div>
              )}
            </dl>
          </div>
          <CopyCopilotPrompt
            prompt={prompt}
            label={tDetail("copyPrompt")}
            copiedLabel={tDetail("copied")}
          />
        </div>
      </header>

      <SpecTabs
        proposalMd={spec.proposalMd}
        tasksMd={spec.tasksMd}
        notesMd={spec.notesMd}
        labels={{
          proposal: tDetail("tabProposal"),
          tasks: tDetail("tabTasks"),
          notes: tDetail("tabNotes"),
          noNotes: tDetail("noNotes"),
          noTasks: tDetail("noTasks"),
        }}
      />

      <p className="sr-only">{t("title")}</p>
    </div>
  );
}
