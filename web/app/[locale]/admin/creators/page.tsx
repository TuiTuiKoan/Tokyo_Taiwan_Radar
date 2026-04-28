import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";
import AdminCreatorsClient from "@/components/AdminCreatorsClient";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

export interface Creator {
  id: string;
  name: string;
  name_zh: string | null;
  platform: string;
  handle: string | null;
  profile_url: string;
  category: string | null;
  base_location: string | null;
  nationality: string | null;
  is_active: boolean;
  approx_followers: number | null;
  last_post_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export default async function AdminCreatorsPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");

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

  const { data: creators, error } = await supabase
    .from("creators")
    .select("*")
    .order("is_active", { ascending: false })
    .order("name");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6 flex-wrap">
        <Link
          href={`/${locale}/admin`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("eventsTab")}
        </Link>
        <Link
          href={`/${locale}/admin/reports`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("reports")}
        </Link>
        <Link
          href={`/${locale}/admin/stats`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("statsTab")}
        </Link>
        <Link
          href={`/${locale}/admin/research`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("researchTab")}
        </Link>
        <Link
          href={`/${locale}/admin/sources`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("sourcesTab")}
        </Link>
        <Link
          href={`/${locale}/admin/users`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("usersTab")}
        </Link>
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {t("creatorsTab")}
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
          {error.message}
        </div>
      )}

      <AdminCreatorsClient
        initialCreators={(creators ?? []) as Creator[]}
        locale={locale}
      />
    </div>
  );
}
