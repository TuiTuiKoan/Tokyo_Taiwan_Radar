import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { createClient as createSsrClient } from "@/lib/supabase/server";
import { unstable_noStore } from "next/cache";
import { notFound, permanentRedirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName, getEventDescription, getEventLocationName, getEventLocationAddress, getEventBusinessHours, getEventPerformer, getEventDirector, getEventOrganizer } from "@/lib/types";
import SaveButton from "@/components/SaveButton";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import RawDataSection from "@/components/RawDataSection";
import ReportSection from "@/components/ReportSection";
import ViewTracker from "@/components/ViewTracker";
import AdminEventActions from "@/components/AdminEventActions";
import EventCard from "@/components/EventCard";
import BackToListButton from "@/components/BackToListButton";
import Link from "next/link";

export const revalidate = 3600;

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

const LOCALES = ["zh", "en", "ja"] as const;

/**
 * Service-role client for cross-status lookups (e.g. resolving merged events
 * whose is_active=false). Only `select` minimum required fields. Never expose
 * SUPABASE_SERVICE_ROLE_KEY to client components.
 */
function adminClient() {
  return createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}

/** Extract prefecture name (都道府県) from a Japanese address string. */
function extractPrefecture(address: string | null): string | null {
  if (!address) return null;
  const m = address.match(/^(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県]{2,4}[都道府県])/);
  if (!m) return null;
  const full = m[1];
  if (full === "北海道") return "北海道";
  if (full === "大阪市" || full === "大阪府") return "大阪";
  if (full === "京都市" || full === "京都府") return "京都";
  return full.replace(/[都道府県]$/, "");
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, id } = await params;
  // Resolve merged events first using service role (RLS bypass — is_active may be false).
  const admin = adminClient();
  const { data: stub } = await admin
    .from("events")
    .select("id, merged_into_event_id, is_active")
    .eq("id", id)
    .maybeSingle();
  if (stub?.merged_into_event_id) {
    permanentRedirect(`/${locale}/events/${stub.merged_into_event_id}`);
  }
  if (!stub || !stub.is_active) return {};
  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data: event } = await supabase
    .from("events")
    .select("name_ja, name_zh, name_en, description_ja, description_zh, description_en, updated_at, start_date")
    .eq("id", id)
    .single();

  if (!event) return {};

  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const name = getEventName(event as Event, locale);
  const description = getEventDescription(event as Event, locale);

  const SITE_NAMES: Record<string, string> = {
    zh: "Tokyo Taiwan Radar 東京台灣雷達",
    en: "Tokyo Taiwan Radar",
    ja: "Tokyo Taiwan Radar 東京台湾レーダー",
  };
  const siteName = SITE_NAMES[locale] ?? "Tokyo Taiwan Radar";

  return {
    title: name ? `${name} | ${siteName}` : siteName,
    description: description?.slice(0, 160) ?? undefined,
    alternates: {
      canonical: `${base}/${locale}/events/${id}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/events/${id}`])),
        "x-default": `${base}/zh/events/${id}`,
      },
    },
    openGraph: {
      title: name ?? undefined,
      description: description?.slice(0, 160) ?? undefined,
      url: `${base}/${locale}/events/${id}`,
      siteName,
      type: "article",
      publishedTime: event.start_date ?? undefined,
      modifiedTime: event.updated_at,
    },
    twitter: {
      card: "summary_large_image",
      title: name ?? undefined,
      description: description?.slice(0, 160) ?? undefined,
    },
  };
}

export default async function EventDetailPage({ params }: PageProps) {
  const { locale, id } = await params;
  const t = await getTranslations("event");
  const tAdmin = await getTranslations("admin");
  const tCat = await getTranslations("categories");
  const tOrgType = await getTranslations("organizerType");
  const tEventForm = await getTranslations("eventForm");
  const tNarr = await getTranslations("eventNarrative");

  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  // Resolve merged events first using service role (RLS bypass — is_active may be false).
  const admin = adminClient();
  const { data: stub } = await admin
    .from("events")
    .select("id, merged_into_event_id, is_active")
    .eq("id", id)
    .maybeSingle();
  if (stub?.merged_into_event_id) {
    permanentRedirect(`/${locale}/events/${stub.merged_into_event_id}`);
  }
  if (!stub || !stub.is_active) {
    notFound();
  }

  const { data: event } = await supabase
    .from("events")
    .select("*")
    .eq("id", id)
    .single();

  if (!event) {
    notFound();
  }

  // 308 redirect for merged events (preserves link equity)
  if (event.merged_into_event_id) {
    permanentRedirect(`/${locale}/events/${event.merged_into_event_id}`);
  }

  // Inactive (non-merged) events → 404
  if (!event.is_active) {
    notFound();
  }

  // Fetch sub-events (children of this event)
  const { data: subEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, start_date, end_date, category, location_address")
    .eq("parent_event_id", id)
    .eq("is_active", true)
    .order("start_date", { ascending: true });

  // Fetch parent event if this is a sub-event.
  // Use service role to bypass RLS so inactive parent events still show
  // (a parent may be archived/de-listed while its sub-events remain active).
  let parentEvent: { id: string; name_ja: string | null; name_zh: string | null; name_en: string | null } | null = null;
  if (event.parent_event_id) {
    const supabaseAdmin = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );
    const { data: parent } = await supabaseAdmin
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .eq("id", event.parent_event_id)
      .single();
    parentEvent = parent;
  }

  // Fetch primary (merged-into) event if this event was merged into another.
  // Service role so inactive primaries still resolve.
  let primaryEvent: { id: string } | null = null;
  if (event.merged_into_event_id) {
    const supabaseAdmin = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );
    const { data: primary } = await supabaseAdmin
      .from("events")
      .select("id")
      .eq("id", event.merged_into_event_id)
      .single();
    primaryEvent = primary;
  }

  // Fetch related screenings: other active events sharing the same work_id.
  // Service role used so query bypasses RLS — only minimum fields selected.
  let relatedScreenings: Event[] = [];
  if (event.work_id) {
    const supabaseAdmin = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );
    const { data: related } = await supabaseAdmin
      .from("events")
      .select("id, name_ja, name_zh, name_en, start_date, end_date, location_name, location_name_zh, location_name_en, location_address, source_name, category, is_paid, is_active")
      .eq("work_id", event.work_id)
      .neq("id", id)
      .order("start_date", { ascending: true });
    relatedScreenings = (related ?? []) as Event[];
  }

  // Fetch work distributor for film events
  let workDistributor: { distributor_ja: string | null; distributor_zh: string | null; distributor_en: string | null; distributor_url: string | null } | null = null;
  if (event.work_id) {
    const supabaseAdmin2 = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );
    const { data: wData } = await supabaseAdmin2
      .from("works")
      .select("distributor_ja, distributor_zh, distributor_en, distributor_url")
      .eq("id", event.work_id)
      .single();
    if (wData?.distributor_ja) workDistributor = wData;
  }

  // Admin detection — opt-out of ISR cache for this check only
  unstable_noStore();
  let isAdmin = false;
  try {
    const ssrClient = await createSsrClient();
    const { data: { user } } = await ssrClient.auth.getUser();
    if (user) {
      const { data: roleRow } = await ssrClient
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .single();
      isAdmin = roleRow?.role === "admin";
    }
  } catch {
    // non-admin / unauthenticated — fall through
  }

  const upcomingScreenings = relatedScreenings.filter((r) => r.is_active);
  const pastScreenings = relatedScreenings.filter((r) => !r.is_active);

  const name = getEventName(event as Event, locale);
  const description = getEventDescription(event as Event, locale);
  const locationName = getEventLocationName(event as Event, locale);
  const locationAddress = getEventLocationAddress(event as Event, locale);
  const businessHours = getEventBusinessHours(event as Event, locale);
  const now = new Date();
  const ended = event.end_date && new Date(event.end_date) < now;

  // Aggregate unique prefecture names from sub-events (only for parent events with 2+ prefectures)
  const subEventPrefectures: string[] =
    !event.parent_event_id && subEvents && subEvents.length > 0
      ? [
          ...new Set(
            subEvents
              .map((s: { location_address: string | null }) => extractPrefecture(s.location_address))
              .filter((p): p is string => p !== null)
          ),
        ]
      : [];

  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const BREADCRUMB_LABELS: Record<string, string> = {
    zh: "活動列表",
    ja: "イベント一覧",
    en: "Event List",
  };
  const jsonLd = (() => {
    const EVENT_STATUS_MAP: Record<string, string> = {
      scheduled: "https://schema.org/EventScheduled",
      cancelled: "https://schema.org/EventCancelled",
      postponed: "https://schema.org/EventPostponed",
      rescheduled: "https://schema.org/EventRescheduled",
    };

    const ev = event as Event;

    // organizer：有資料用真實主辦方，無資料 fallback 本站
    const organizerLd = ev.organizer
      ? {
          "@type": "Organization",
          name: getEventOrganizer(ev as Event, locale) || ev.organizer,
          ...(ev.organizer_url ?? ev.official_url
            ? { url: ev.organizer_url ?? ev.official_url }
            : {}),
        }
      : { "@type": "Organization", name: "Tokyo Taiwan Radar", url: base };

    // performer: output only when DB has a real person name
    const _performerStr = getEventPerformer(ev as Event, locale);
    const performerLd =
      ev.performers && ev.performers.length > 0
        ? ev.performers.map(n => ({ "@type": "Person", name: n }))
        : _performerStr
          ? { "@type": "Person", name: _performerStr }
          : null;

    const directorLd = ev.director
      ? { "@type": "Person", name: getEventDirector(ev as Event, locale) }
      : null;

    // location → Schema.org Event location MUST be present (required field).
    // Detect online events across all three locale labels.
    const isOnline =
      locationName === "オンライン" ||
      locationName === "線上" ||
      locationName === "Online";

    let placeLd: Record<string, unknown>;
    let attendanceMode: string;
    if (isOnline) {
      attendanceMode = "https://schema.org/OnlineEventAttendanceMode";
      placeLd = {
        "@type": "VirtualLocation",
        url:
          ev.official_url ??
          ev.source_url ??
          `${base}/${locale}/events/${id}`,
      };
    } else if (locationName) {
      attendanceMode = "https://schema.org/OfflineEventAttendanceMode";
      placeLd = {
        "@type": "Place",
        name: locationName,
        address: locationAddress
          ? {
              "@type": "PostalAddress",
              streetAddress: locationAddress,
              addressCountry: "JP",
            }
          : { "@type": "PostalAddress", addressCountry: "JP" },
      };
    } else {
      // Fallback: physical event with no venue name (rare) — use country-only address.
      attendanceMode = "https://schema.org/OfflineEventAttendanceMode";
      placeLd = {
        "@type": "Place",
        name: locale === "en" ? "Japan" : "日本",
        address: { "@type": "PostalAddress", addressCountry: "JP" },
      };
    }

    // offers
    const offerUrl = ev.official_url ?? ev.source_url;
    const priceCurrency = ev.price_currency ?? "JPY";
    let offersLd: Record<string, unknown> | null = null;
    if (ev.is_paid === false) {
      offersLd = {
        "@type": "Offer",
        price: "0",
        priceCurrency,
        availability: "https://schema.org/InStock",
        ...(ev.scraped_at ? { validFrom: ev.scraped_at } : {}),
        ...(offerUrl ? { url: offerUrl } : {}),
      };
    } else if (ev.is_paid === true) {
      offersLd = {
        "@type": "Offer",
        priceCurrency,
        ...(ev.price_amount != null ? { price: String(ev.price_amount) } : {}),
        availability: "https://schema.org/InStock",
        ...(ev.scraped_at ? { validFrom: ev.scraped_at } : {}),
        ...(offerUrl ? { url: offerUrl } : {}),
      };
    }

    return {
      "@context": "https://schema.org",
      "@type": "Event",
      name: name ?? ev.name_ja ?? undefined,
      startDate: ev.start_date ?? undefined,
      endDate: ev.end_date ?? undefined,
      description: description ?? undefined,
      url: `${base}/${locale}/events/${id}`,
      image: `${base}/${locale}/events/${id}/opengraph-image`,
      eventAttendanceMode: attendanceMode,
      eventStatus: EVENT_STATUS_MAP[ev.event_status ?? "scheduled"],
      location: placeLd,
      organizer: organizerLd,
      ...(performerLd ? { performer: performerLd } : {}),
      ...(directorLd ? { director: directorLd } : {}),
      ...(offersLd ? { offers: offersLd } : {}),
      ...(ev.is_paid === false ? { isAccessibleForFree: true } : {}),
    };
  })();
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Tokyo Taiwan Radar",
        item: `${base}/${locale}`,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: BREADCRUMB_LABELS[locale] ?? BREADCRUMB_LABELS.zh,
        item: `${base}/${locale}`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: name ?? event.name_ja ?? id,
      },
    ],
  };

  // ===== FAQ JSON-LD — only include questions whose answer is available =====
  const FAQ_LABELS: Record<string, {
    when: string; whenA: (s: string, e: string | null) => string;
    where: string; whereA: (loc: string, addr: string | null) => string;
    price: string; priceFree: string; pricePaid: (info: string | null) => string;
    source: string; sourceA: (host: string) => string;
  }> = {
    zh: {
      when: "活動何時舉辦？",
      whenA: (s, e) => e && e !== s ? `活動於 ${s} 至 ${e} 舉辦。` : `活動於 ${s} 舉辦。`,
      where: "活動地點在哪裡？",
      whereA: (loc, addr) => addr ? `活動於${loc}舉辦，地址：${addr}。` : `活動於${loc}舉辦。`,
      price: "活動費用是多少？",
      priceFree: "本活動為免費入場。",
      pricePaid: (info) => info ? `本活動為付費活動。${info}` : "本活動為付費活動，詳細費用請見官方網站。",
      source: "活動資訊來源是什麼？",
      sourceA: (host) => `活動資訊來自 ${host}。`,
    },
    ja: {
      when: "イベントはいつ開催されますか？",
      whenA: (s, e) => e && e !== s ? `${s} から ${e} まで開催されます。` : `${s} に開催されます。`,
      where: "開催場所はどこですか？",
      whereA: (loc, addr) => addr ? `${loc}で開催されます。住所：${addr}` : `${loc}で開催されます。`,
      price: "参加費はいくらですか？",
      priceFree: "本イベントは入場無料です。",
      pricePaid: (info) => info ? `有料イベントです。${info}` : "有料イベントです。詳細は公式サイトをご確認ください。",
      source: "情報の出典は？",
      sourceA: (host) => `情報は ${host} から取得しています。`,
    },
    en: {
      when: "When is this event held?",
      whenA: (s, e) => e && e !== s ? `The event runs from ${s} to ${e}.` : `The event takes place on ${s}.`,
      where: "Where is the event held?",
      whereA: (loc, addr) => addr ? `The event is held at ${loc} (${addr}).` : `The event is held at ${loc}.`,
      price: "How much does it cost?",
      priceFree: "This event is free to attend.",
      pricePaid: (info) => info ? `This is a paid event. ${info}` : "This is a paid event. Please check the official website for details.",
      source: "What is the source of this information?",
      sourceA: (host) => `Event information sourced from ${host}.`,
    },
  };
  const faqL = FAQ_LABELS[locale] ?? FAQ_LABELS.zh;
  const faqQuestions: Array<{ q: string; a: string }> = [];
  if (event.start_date) {
    faqQuestions.push({
      q: faqL.when,
      a: faqL.whenA(event.start_date, event.end_date ?? null),
    });
  }
  if (subEventPrefectures.length > 1) {
    faqQuestions.push({
      q: faqL.where,
      a: faqL.whereA(subEventPrefectures.join("・"), null),
    });
  } else if (locationName) {
    faqQuestions.push({
      q: faqL.where,
      a: faqL.whereA(locationName, locationAddress ?? null),
    });
  }
  if (event.is_paid === false) {
    faqQuestions.push({ q: faqL.price, a: faqL.priceFree });
  } else if (event.is_paid === true) {
    faqQuestions.push({ q: faqL.price, a: faqL.pricePaid(event.price_info ?? null) });
  }
  const sourceUrl = (event as Event).official_url ?? event.source_url;
  if (sourceUrl) {
    try {
      const host = new URL(sourceUrl).hostname.replace(/^www\./, "");
      faqQuestions.push({ q: faqL.source, a: faqL.sourceA(host) });
    } catch {
      // ignore malformed URLs
    }
  }
  const faqLd = faqQuestions.length >= 2
    ? {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: faqQuestions.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      }
    : null;

  return (
    <article className="max-w-3xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }}
      />
      {faqLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
        />
      )}
      <ViewTracker eventId={id} locale={locale} />
      {/* Back to list button */}
      <BackToListButton locale={locale} />
      {/* Back to parent event */}
      {parentEvent && (
        <Link
          href={`/${locale}/events/${parentEvent.id}`}
          className="inline-flex items-center gap-1 text-sm text-[#1F5E2B] mb-4"
        >
          ← {t("viewParent")}：{getEventName(parentEvent as Event, locale)}
        </Link>
      )}

      {/* Header: [thumbnail + save button stacked] | [title] */}
      <div className="flex items-start gap-4 mb-4">
        {/* Left column: thumbnail and save button share the same width */}
        <div className="flex flex-col gap-2 shrink-0">
          <CategoryThumbnail
            id={event.id}
            categories={event.category ?? undefined}
            className="w-[108px] h-[108px]"
          />
          <SaveButton
            eventId={event.id}
            initialSaved={false}
            locale={locale}
          />
        </div>
        {/* Right column: merged badge + title + admin actions */}
        <div className="flex-1 min-w-0">
          {/* Merged-into badge */}
          {event.merged_into_event_id && primaryEvent && (
            <div className="flex items-center gap-1 mb-1">
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium border border-amber-300 whitespace-nowrap">
                {tAdmin("mergedIntoBadge")}
              </span>
              <span className="text-green-600 font-bold text-sm">→</span>
              <Link
                href={`/${locale}/events/${primaryEvent.id}`}
                className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-bold border border-green-300 hover:bg-green-200 whitespace-nowrap"
                title={tAdmin("mergedIntoBadgeTitle")}
              >
                1
              </Link>
            </div>
          )}
          <h1 className="font-display font-bold text-[#3A261F] text-2xl sm:text-[26px] leading-snug">{name}</h1>
          <AdminEventActions
            eventId={event.id}
            locale={locale}
            initialIsActive={event.is_active}
            isAdmin={isAdmin}
          />
        </div>
      </div>

      {/* ===== Narrative summary (SEO content thickening) ===== */}
      {(() => {
        const ev = event as Event;
        const fmtDate = (iso: string | null | undefined) =>
          iso
            ? new Date(iso).toLocaleDateString(locale, {
                year: "numeric",
                month: "long",
                day: "numeric",
              })
            : null;
        const startStr = fmtDate(ev.start_date ?? null);
        const endStr = fmtDate(ev.end_date ?? null);
        const isOnline =
          locationName === "オンライン" ||
          locationName === "線上" ||
          locationName === "Online";
        const displayName = name ?? ev.name_ja ?? "";

        // Paragraph 1 — when / where overview
        let p1 = "";
        if (startStr && displayName) {
          if (isOnline) {
            p1 = endStr && endStr !== startStr
              ? tNarr("p1OnlineWithEnd", { name: displayName, start: startStr, end: endStr })
              : tNarr("p1Online", { name: displayName, start: startStr });
          } else if (locationName) {
            p1 = endStr && endStr !== startStr
              ? tNarr("p1WithEnd", { name: displayName, start: startStr, end: endStr, location: locationName })
              : tNarr("p1", { name: displayName, start: startStr, location: locationName });
          } else {
            p1 = endStr && endStr !== startStr
              ? tNarr("p1JapanWithEnd", { name: displayName, start: startStr, end: endStr })
              : tNarr("p1Japan", { name: displayName, start: startStr });
          }
        }

        // Paragraph 2 — categories + organizer
        const catLabels = (ev.category ?? []).map((c) => tCat(c as never));
        const organizerName = getEventOrganizer(ev, locale) || ev.organizer || null;
        const p2Parts: string[] = [];
        if (catLabels.length > 0) {
          p2Parts.push(
            tNarr("p2Categories", { categories: catLabels.join(locale === "en" ? ", " : "、") })
          );
        }
        if (organizerName) {
          p2Parts.push(tNarr("p2Organizer", { organizer: organizerName }));
        }
        const p2 = p2Parts.join(" ");

        // Paragraph 3 — pricing
        let p3 = "";
        if (ev.is_paid === false) {
          p3 = tNarr("p3Free");
        } else if (ev.is_paid === true) {
          if (ev.price_amount != null) {
            p3 = tNarr("p3PaidWithAmount", {
              amount: String(ev.price_amount),
              info: ev.price_info ?? "",
            });
          } else if (ev.price_info) {
            p3 = tNarr("p3PaidWithInfo", { info: ev.price_info });
          } else {
            p3 = tNarr("p3Paid");
          }
        } else {
          p3 = tNarr("p3Unknown");
        }

        // Paragraph 4 — venue / access
        let p4 = "";
        if (isOnline) {
          p4 = tNarr("p4Online");
        } else if (locationName && locationAddress) {
          p4 = tNarr("p4VenueWithAddress", { venue: locationName, address: locationAddress });
        } else if (locationName) {
          p4 = tNarr("p4VenueOnly", { venue: locationName });
        }

        const paragraphs = [p1, p2, p3, p4].filter((s) => s && s.trim().length > 0);
        if (paragraphs.length === 0) return null;
        return (
          <section className="mb-6 space-y-2 text-sm leading-relaxed text-fg-muted">
            {paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </section>
        );
      })()}

      {/* ===== Summary Card ===== */}
      <div className="border border-line rounded-xl overflow-hidden mb-6 bg-paper dark:bg-paper">
        <table className="w-full text-sm">
          <tbody className="divide-y divide-line">
            {/* Categories */}
            {event.category?.length > 0 && (
              <tr>
                <td className="px-4 py-3 text-fg-subtle w-28 align-top whitespace-nowrap">{t("category")}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {event.category.map((cat: string) => (
                      <span key={cat} className="bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">
                        {tCat(cat as any)}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            )}
            {/* Start date */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("startDate")}</td>
              <td className="px-4 py-3">
                {event.start_date
                  ? <time dateTime={event.start_date}>{new Date(event.start_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}</time>
                  : "—"}
              </td>
            </tr>
            {/* End date */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("endDate")}</td>
              <td className="px-4 py-3">
                {event.end_date
                  ? <time dateTime={event.end_date}>{new Date(event.end_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}</time>
                  : "—"}
                {ended && (
                  <>
                    <span className="ml-2 text-xs bg-muted text-fg-subtle px-2 py-0.5 rounded-full">
                      {t("ended")}
                    </span>
                    {(() => {
                      const recordLinks = (event as Event).record_links ?? [];
                      const featured = recordLinks.find((l) => l.recommended) ?? recordLinks[0];
                      return featured ? (
                        <a
                          href={featured.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-2 text-xs bg-[#F7FFE8] text-[#1F5E2B] px-2 py-0.5 rounded-full hover:underline"
                        >
                          {t("recordLinksBadge")} ↗
                        </a>
                      ) : null;
                    })()}
                  </>
                )}
              </td>
            </tr>
            {/* Location */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("location")}</td>
              <td className="px-4 py-3">
                {subEventPrefectures.length > 1
                  ? subEventPrefectures.join("・")
                  : event.source_name === "rti_jp"
                    ? <a href="https://www.rti.org.tw/jp" target="_blank" rel="noopener noreferrer" className="hover:underline">RTI台湾国際放送（日本語部門）↗</a>
                    : locationName
                      ? event.location_url
                        ? <a href={event.location_url} target="_blank" rel="noopener noreferrer" className="hover:underline">{locationName} ↗</a>
                        : locationName
                      : "—"}
              </td>
            </tr>
            {/* Address */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("address")}</td>
              <td className="px-4 py-3">
                {subEventPrefectures.length > 1
                  ? subEventPrefectures.join("・")
                  : event.source_name === "gguide_tv"
                  ? t("tvChannel")
                  : event.source_name === "rti_jp"
                  ? t("radioChannel")
                  : (locationAddress || locationName) ? (
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locationAddress || locationName || "")}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {locationAddress || locationName} ↗
                    </a>
                  ) : "—"}
              </td>
            </tr>
            {/* Business hours */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("hours")}</td>
              <td className="px-4 py-3 whitespace-pre-wrap">{businessHours || "—"}</td>
            </tr>
            {/* Price */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 whitespace-nowrap">{t("paid")}</td>
              <td className="px-4 py-3">
                {event.is_paid === false ? (
                  <span className="text-[#1F5E2B] font-medium">{t("free")}</span>
                ) : event.is_paid === true ? (
                  <span>
                    <span className="text-amber-600 font-medium">{t("paid")}</span>
                    {event.price_info && <span className="text-fg-muted ml-2">{event.price_info}</span>}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
            {/* Source link — official first */}
            <tr>
              <td className="px-4 py-3 text-fg-subtle w-28 align-top whitespace-nowrap">{t("source")}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col gap-1">
                  {(event as Event).official_url ? (
                    <a
                      href={(event as Event).official_url!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium hover:underline"
                    >
                      {t("officialSite")} ↗
                    </a>
                  ) : null}
                  {event.source_url && event.source_url !== (event as Event).official_url ? (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {t("viewOriginal")} ↗
                    </a>
                  ) : event.source_url && !(event as Event).official_url ? (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {t("viewOriginal")} ↗
                    </a>
                  ) : null}
                  {!(event as Event).official_url && !event.source_url && "—"}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ===== Organizer / Event Form / Language Support ===== */}
      {((event as Event).organizer ||
        ((event as Event).co_organizers ?? []).length > 0 ||
        ((event as Event).sponsors ?? []).length > 0 ||
        ((event as Event).event_form ?? []).length > 0 ||
        ((event as Event).performers ?? []).length > 0 ||
        (event as Event).performer ||
        (event as Event).director ||
        (event as Event).has_japanese_support ||
        (event as Event).has_english_support ||
        (event as Event).has_chinese_support ||
        (workDistributor !== null && !(event as Event).organizer)) && (
        <section className="mb-8 border border-line rounded-xl p-4 bg-paper dark:bg-paper">
          <h2 className="font-display font-bold text-[#3A261F] text-base mb-3">{t("organizerSection")}</h2>
          <dl className="space-y-2 text-sm">
            {(event as Event).organizer && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("organizer")}：</dt>
                <dd className="text-fg-strong">
                  {(event as Event).organizer_url ? (
                    <a
                      href={(event as Event).organizer_url!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {getEventOrganizer(event as Event, locale)} ↗
                    </a>
                  ) : (
                    getEventOrganizer(event as Event, locale)
                  )}
                  {((event as Event).organizer_type ?? [])[0] &&
                    ((event as Event).organizer_type ?? [])[0] !== "unknown" && (
                      <span className="ml-2 text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                        {tOrgType(((event as Event).organizer_type ?? [])[0] as any)}
                      </span>
                  )}
                </dd>
              </div>
            )}
            {workDistributor && !(event as Event).organizer && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("distributor")}：</dt>
                <dd className="text-fg-strong">
                  {workDistributor.distributor_url ? (
                    <a
                      href={workDistributor.distributor_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {(locale === "zh" ? workDistributor.distributor_zh : locale === "en" ? workDistributor.distributor_en : null) || workDistributor.distributor_ja} ↗
                    </a>
                  ) : (
                    (locale === "zh" ? workDistributor.distributor_zh : locale === "en" ? workDistributor.distributor_en : null) || workDistributor.distributor_ja
                  )}
                </dd>
              </div>
            )}
            {(((event as Event).performers ?? []).length > 0 || (event as Event).performer) && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("performers")}：</dt>
                <dd className="text-fg-strong">
                  {getEventPerformer(event as Event, locale)}
                </dd>
              </div>
            )}
            {(event as Event).director && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("director")}：</dt>
                <dd className="text-fg-strong">{getEventDirector(event as Event, locale)}</dd>
              </div>
            )}
            {((event as Event).co_organizers ?? []).length > 0 && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("coOrganizers")}：</dt>
                <dd className="text-fg-strong flex flex-wrap gap-x-2 gap-y-1">
                  {((event as Event).co_organizers ?? []).map((name, i) => (
                    <span key={name} className="flex items-center gap-1">
                      {name}
                      {((event as Event).co_organizer_types ?? [])[i] &&
                        ((event as Event).co_organizer_types ?? [])[i] !== "unknown" && (
                          <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                            {tOrgType(((event as Event).co_organizer_types ?? [])[i] as any)}
                          </span>
                      )}
                    </span>
                  ))}
                </dd>
              </div>
            )}
            {((event as Event).sponsors ?? []).length > 0 && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("sponsors")}：</dt>
                <dd className="text-fg-strong flex flex-wrap gap-x-2 gap-y-1">
                  {((event as Event).sponsors ?? []).map((name, i) => (
                    <span key={name} className="flex items-center gap-1">
                      {name}
                      {((event as Event).sponsor_types ?? [])[i] &&
                        ((event as Event).sponsor_types ?? [])[i] !== "unknown" && (
                          <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                            {tOrgType(((event as Event).sponsor_types ?? [])[i] as any)}
                          </span>
                      )}
                    </span>
                  ))}
                </dd>
              </div>
            )}
            {((event as Event).event_form ?? []).length > 0 && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("eventForm")}：</dt>
                <dd className="flex flex-wrap gap-1">
                  {((event as Event).event_form ?? []).map((f) => (
                    <span key={f} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                      {tEventForm(f as any)}
                    </span>
                  ))}
                </dd>
              </div>
            )}
            {((event as Event).has_japanese_support ||
              (event as Event).has_english_support ||
              (event as Event).has_chinese_support) && (
              <div className="flex gap-2 pt-1">
                <dt className="shrink-0 text-fg-muted min-w-[5rem]">{t("languageSupport")}：</dt>
                <dd className="flex flex-wrap gap-1">
                  {(event as Event).has_japanese_support && (
                    <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">🇯🇵 日本語</span>
                  )}
                  {(event as Event).has_english_support && (
                    <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">🇬🇧 English</span>
                  )}
                  {(event as Event).has_chinese_support && (
                    <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full">🇹🇼 中文</span>
                  )}
                </dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* ===== Description ===== */}
      {description && (
        <div className="mb-8">
          <h2 className="font-display font-bold text-[#3A261F] text-base mb-2">{t("description")}</h2>
          <div className="prose prose-gray max-w-none">
            <p className="whitespace-pre-wrap text-fg leading-relaxed text-sm">
              {description}
            </p>
          </div>
        </div>
      )}

      {/* ===== Primary CTA ===== */}
      {((event as Event).official_url || event.source_url) && (
        <a
          href={((event as Event).official_url ?? event.source_url)!}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-700 active:bg-green-800 text-white font-medium py-3 px-4 rounded-xl mb-6 transition"
        >
          {(event as Event).official_url ? t("officialSite") : t("viewOriginal")}
          <span aria-hidden="true">↗</span>
        </a>
      )}

      {/* ===== AI Selection Reason ===== */}
      <RawDataSection
        rawTitle={event.raw_title}
        rawDescription={event.raw_description}
        selectionReason={event.selection_reason}
        locale={locale}
        reportSection={<ReportSection eventId={event.id} locale={locale} currentCategories={(event.category ?? []) as import("@/lib/types").Category[]} selectionReasonAll={(() => {
          if (!event.selection_reason) return null;
          try {
            const parsed = JSON.parse(event.selection_reason);
            if (parsed && typeof parsed === "object") {
              return parsed as Record<string, string | null>;
            }
          } catch {}
          return null;
        })()} eventFields={{
          name: { zh: event.name_zh, en: event.name_en, ja: event.name_ja },
          start_date: { zh: event.start_date, en: event.start_date, ja: event.start_date },
          end_date: { zh: event.end_date, en: event.end_date, ja: event.end_date },
          venue: { zh: event.location_name_zh, en: event.location_name_en, ja: event.location_name },
          address: { zh: event.location_address_zh, en: event.location_address_en, ja: event.location_address },
          business_hours: { zh: event.business_hours_zh, en: event.business_hours_en, ja: event.business_hours },
          price: { zh: event.price_info, en: event.price_info, ja: event.price_info },
          description: { zh: event.description_zh, en: event.description_en, ja: event.description_ja },
        }} />}
      />

      {/* ===== Sub-events ===== */}
      {subEvents && subEvents.length > 0 && (
        <div className="mb-8">
          <h2 className="font-display font-bold text-[#3A261F] text-base mb-3">{t("subEvents")}</h2>
          <div className="border border-line rounded-xl overflow-hidden divide-y divide-line">
            {subEvents.map((sub) => {
              const subName = getEventName(sub as Event, locale);
              return (
                <Link
                  key={sub.id}
                  href={`/${locale}/events/${sub.id}`}
                  className="group flex items-center gap-3 px-4 py-3 bg-[#FFFDF5] hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400 transition"
                >
                  <div className="w-12 text-center flex-shrink-0">
                    {sub.start_date ? (
                      <time dateTime={sub.start_date}>
                        <div className="text-[10px] text-fg-subtle">
                          {new Date(sub.start_date).toLocaleDateString(locale, { month: "short" })}
                        </div>
                        <div className="text-lg font-bold text-fg-muted leading-none">
                          {new Date(sub.start_date).getDate()}
                        </div>
                      </time>
                    ) : (
                      <span className="text-fg-subtle">—</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-fg-strong line-clamp-1">{subName}</p>
                    {sub.category?.slice(0, 2).map((cat: string) => (
                      <span key={cat} className="text-xs bg-muted text-fg-muted px-1.5 py-0.5 rounded mr-1">
                        {tCat(cat as any)}
                      </span>
                    ))}
                  </div>
                  <span className="text-fg-subtle text-sm group-hover:text-[#1F5E2B] dark:group-hover:text-green-400 shrink-0">→</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== 報導・活動紀錄 ===== */}
      {(() => {
        const hasOfficialUrl = !!(event as Event).official_url;
        const isMovie = event.category?.includes("movie");
        const hasRecordLinks = ((event as Event).record_links?.length || 0) > 0;
        const hasSecondaryUrls = ((event as Event).secondary_source_urls?.length || 0) > 0;
        const showSection = hasOfficialUrl || hasRecordLinks || hasSecondaryUrls || isMovie;
        if (!showSection) return null;
        return (
          <div className="mb-8">
            <h2 className="font-display font-bold text-[#3A261F] text-base mb-3">{t("recordLinksSection")}</h2>
            <div className="border border-line rounded-xl overflow-hidden divide-y divide-line">
              {/* Movie: official promotional site link */}
              {hasOfficialUrl && isMovie && (
                <a
                  href={(event as Event).official_url!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center px-4 py-3 bg-[#FFFDF5] hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400 transition text-sm hover:underline gap-2"
                >
                  <span className="flex-1">{t("movieOfficialSite")}</span>
                  <span className="text-fg-subtle shrink-0 group-hover:text-[#1F5E2B] dark:group-hover:text-green-400">↗</span>
                </a>
              )}
              {(event as Event).record_links?.map((link: { title: string; url: string; recommended?: boolean }, i: number) => {
                const totalLinks = ((event as Event).record_links?.length || 0) + ((event as Event).secondary_source_urls?.length || 0);
                const showBadge = link.recommended && totalLinks > 1;
                return (
                  <a
                    key={i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center px-4 py-3 bg-[#FFFDF5] hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400 transition text-sm hover:underline gap-2"
                  >
                    <span className="flex-1">{link.title || link.url}</span>
                    {showBadge && (
                      <span className="shrink-0 text-xs bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
                        {t("recordLinksRecommended")}
                      </span>
                    )}
                    <span className="text-fg-subtle shrink-0 group-hover:text-[#1F5E2B] dark:group-hover:text-green-400">↗</span>
                  </a>
                );
              })}
              {(event as Event).secondary_source_urls?.map((secUrl: string, idx: number) => (
                <a
                  key={`sec-${idx}`}
                  href={secUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center px-4 py-3 bg-[#FFFDF5] hover:bg-[#F7FFE8] dark:hover:bg-green-900/40 hover:text-[#1F5E2B] dark:hover:text-green-400 transition text-sm hover:underline gap-2"
                >
                  <span className="flex-1">{t("viewAltSource", { n: idx + 1 })}</span>
                  <span className="text-fg-subtle shrink-0 group-hover:text-[#1F5E2B] dark:group-hover:text-green-400">↗</span>
                </a>
              ))}
              {/* Movie without official_url: Google search fallback */}
              {isMovie && !hasOfficialUrl && (
                <a
                  href={`https://www.google.com/search?q=${encodeURIComponent(((event as Event).name_ja || event.raw_title || name || "") + " 公式サイト")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center px-4 py-3 bg-[#FFFDF5] hover:bg-elevated dark:hover:bg-green-900/40 transition text-sm hover:underline gap-2"
                >
                  <span className="flex-1">{t("searchOfficialSite")}</span>
                  <span className="text-fg-subtle shrink-0 group-hover:text-[#1F5E2B] dark:group-hover:text-green-400">↗</span>
                </a>
              )}
            </div>
          </div>
        );
      })()}

      {/* ===== Related screenings (same work, other venues/dates) ===== */}
      {(upcomingScreenings.length > 0 || (isAdmin && pastScreenings.length > 0)) && (
        <section className="mb-8" aria-labelledby="related-screenings-heading">
          <h2 id="related-screenings-heading" className="font-display font-bold text-[#3A261F] text-base mb-3">
            {t("relatedScreeningsTitle")}
          </h2>
          {upcomingScreenings.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {upcomingScreenings.map((rel) => (
                <EventCard key={rel.id} event={rel} locale={locale} />
              ))}
            </div>
          )}
          {isAdmin && pastScreenings.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-fg-subtle mb-2">{t("pastScreeningsLabel")}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 opacity-50">
                {pastScreenings.map((rel) => (
                  <EventCard key={rel.id} event={rel} locale={locale} />
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ===== FAQ section (visible counterpart to FAQPage JSON-LD) ===== */}
      {faqLd && (
        <section className="mb-8" aria-labelledby="faq-heading">
          <h2 id="faq-heading" className="font-display font-bold text-[#3A261F] text-base mb-3">
            {locale === "ja" ? "よくある質問" : locale === "en" ? "FAQ" : "常見問題"}
          </h2>
          <dl className="border border-line rounded-xl overflow-hidden divide-y divide-line">
            {faqQuestions.map((f, i) => (
              <div key={i} className="px-4 py-3 transition-colors duration-150 hover:bg-paper hover:shadow-sm dark:hover:bg-paper">
                <dt className="font-medium text-fg-strong text-sm mb-1">{f.q}</dt>
                <dd className="text-sm text-fg">{f.a}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

    </article>
  );
}
