import { Suspense } from "react";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient as createAnonClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import AccountHomeClient, { type AccountEvent } from "@/components/AccountHomeClient";
import type { Event, Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

const EVENT_SELECT = "id, source_name, source_id, source_url, original_language, name_ja, name_zh, name_en, description_ja, description_zh, description_en, category, start_date, end_date, location_name, location_name_zh, location_name_en, location_address, location_address_zh, location_address_en, location_url, location_prefectures, business_hours, business_hours_zh, business_hours_en, is_paid, price_info, is_active, parent_event_id, raw_title, raw_description, secondary_source_urls, record_links, official_url, selection_reason, annotation_status, annotated_at, scraped_at, created_at, updated_at, organizer, organizer_zh, organizer_en, organizer_url, organizer_type, co_organizers, co_organizer_types, sponsors, sponsor_types, event_form, primary_language, has_japanese_support, has_english_support, has_chinese_support, price_amount, price_currency, event_status, performer, performers, performers_zh, performers_en, director, performer_zh, performer_en, performer_url, performer_urls, director_zh, director_en, work_id, merged_into_event_id, deactivated_reason, owner_user_id, closed_by_owner, is_user_submitted";

export default async function AccountPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("account");
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  const { data: profileRow } = await supabase
    .from("creators")
    .select("user_handle, avatar_url")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!profileRow?.user_handle) {
    redirect(`/${locale}/account/profile`);
  }

  const [{ data: savedRows }, { data: ownRows }] = await Promise.all([
    supabase
      .from("saved_events")
      .select(`event_id, events(${EVENT_SELECT})`)
      .eq("user_id", user.id)
      .order("created_at", { ascending: false }),
    supabase
      .from("events")
      .select(EVENT_SELECT)
      .eq("owner_user_id", user.id)
      .order("created_at", { ascending: false }),
  ]);

  const favoriteEvents: Event[] = (savedRows ?? [])
    .map((row: any) => row.events)
    .filter(Boolean) as Event[];

  const myEvents = ((ownRows ?? []) as unknown as AccountEvent[]);

  const parentIds = [
    ...new Set(
      [...favoriteEvents, ...myEvents]
        .map((event) => event.parent_event_id)
        .filter(Boolean),
    ),
  ] as string[];
  const parentMap: Record<string, Event> = {};

  if (parentIds.length > 0) {
    const anonSupabase = createAnonClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    );
    const { data: parents } = await anonSupabase
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .in("id", parentIds);

    for (const parent of parents ?? []) {
      parentMap[parent.id] = parent as unknown as Event;
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-fg-strong">{t("title")}</h1>
        <p className="mt-2 text-sm text-fg-muted">{t("intro")}</p>
      </div>

      <Suspense fallback={<p className="text-sm text-fg-muted">{t("loading")}</p>}>
        <AccountHomeClient
          locale={locale}
          favoriteEvents={favoriteEvents}
          myEvents={myEvents}
          parentMap={parentMap}
          hasProfile={Boolean(profileRow?.user_handle)}
          displayName={profileRow?.user_handle || user.email || null}
          avatarUrl={profileRow?.avatar_url ?? null}
        />
      </Suspense>
    </div>
  );
}
