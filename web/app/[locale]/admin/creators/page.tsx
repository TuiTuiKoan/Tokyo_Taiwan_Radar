import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
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


      <AdminTabNav locale={locale} activeTab="creators" />

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
