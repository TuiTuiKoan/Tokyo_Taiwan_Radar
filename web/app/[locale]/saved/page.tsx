import type { Metadata } from "next";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event } from "@/lib/types";
import SavedListClient from "@/components/SavedListClient";
import { Suspense } from "react";
import { createClient as createAnonClient } from "@supabase/supabase-js";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

const LOCALES: Locale[] = ["zh", "en", "ja"];

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "saved" });
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const title = t("title");
  const description = t("loginPrompt");
  const image = `${base}/${locale}/saved/opengraph-image`;

  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}/saved`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/saved`])),
        "x-default": `${base}/ja/saved`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}/saved`,
      type: "website",
      images: [{ url: image, width: 1200, height: 1200, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

export default async function SavedPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("saved");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login?next=/${locale}/saved`);
  }

  const { data: savedRows } = await supabase
    .from("saved_events")
    .select(
      "event_id, events(id, source_name, name_ja, name_zh, name_en, organizer, location_name, location_address, location_prefectures, category, start_date, end_date, is_paid, image_url, parent_event_id, work_id)"
    )
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const events: Event[] = (savedRows ?? [])
    .map((row: any) => row.events)
    .filter(Boolean);

  // Build parentMap for child events
  const parentIds = [
    ...new Set(events.map((e) => e.parent_event_id).filter(Boolean)),
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
    if (parents) {
      for (const p of parents) {
        parentMap[p.id] = p as unknown as Event;
      }
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>
      {events.length === 0 ? (
        <p className="text-fg-muted text-center mt-16">{t("empty")}</p>
      ) : (
        <Suspense fallback={null}>
          <SavedListClient
            initialEvents={events}
            parentMap={parentMap}
            locale={locale}
          />
        </Suspense>
      )}
    </div>
  );
}
