import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Locale } from "@/lib/types";
import type { SourceInfo, SourceType } from "@/lib/sources";

export const revalidate = 86400;

const LOCALES: Locale[] = ["zh", "en", "ja"];

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "sources" });
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const title = t("pageTitle");
  const description = t("pageDesc").slice(0, 160);
  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}/sources`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/sources`])),
        "x-default": `${base}/zh/sources`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}/sources`,
      type: "website",
    },
  };
}

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

const TYPE_ORDER: SourceType[] = [
  "government",
  "academic",
  "event_platform",
  "cinema",
  "tv",
  "venue",
  "department_store",
  "organizer",
  "ngo",
  "news_media",
  "taiwan_shop",
  "personal",
  "creator",
  "other",
];

async function fetchSources(): Promise<SourceInfo[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("sources")
    .select("id, name, type, frequency, official_url")
    .eq("is_active", true)
    .order("type")
    .order("sort_order");

  if (error) {
    console.warn("[sources page] failed to fetch sources from DB:", error.message);
    return [];
  }

  return (data ?? []).map((row) => ({
    id: row.id as string,
    name: row.name as string,
    type: row.type as SourceType,
    frequency: row.frequency as "daily" | "weekly",
    officialUrl: row.official_url as string,
  }));
}

export default async function SourcesPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "sources" });
  const tType = await getTranslations({ locale, namespace: "sourceType" });

  const sources = await fetchSources();

  // Group sources by type, preserving the TYPE_ORDER sequence.
  const grouped = new Map<SourceType, SourceInfo[]>();
  for (const ty of TYPE_ORDER) grouped.set(ty, []);
  for (const s of sources) {
    const arr = grouped.get(s.type);
    if (arr) arr.push(s);
  }

  const total = sources.length;

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span>{t("pageTitle")}</span>
      </nav>

      <h1 className="text-3xl font-bold mb-3 text-fg-strong">{t("pageTitle")}</h1>
      <p className="text-base leading-relaxed text-fg-muted mb-6">
        {t("intro", { n: total })}
      </p>
      <p className="text-sm text-fg-subtle mb-8">{t("totalLabel", { n: total })}</p>

      {TYPE_ORDER.map((type) => {
        const list = grouped.get(type);
        if (!list || list.length === 0) return null;
        return (
          <section key={type} className="mb-8">
            <h2 className="text-xl font-semibold mb-3 text-fg-strong">
              {tType(type)}
              <span className="ml-2 text-sm text-fg-subtle font-normal">
                ({list.length})
              </span>
            </h2>
            <ul className="divide-y divide-line border border-line rounded-xl overflow-hidden">
              {list.map((s) => (
                <li key={s.id} className="px-4 py-3 flex items-center justify-between gap-3 text-sm transition-colors duration-150 hover:bg-paper dark:hover:bg-elevated hover:shadow-sm cursor-default">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-fg-strong truncate">{s.name}</div>
                    <div className="text-xs text-fg-subtle font-mono">{s.id}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[#F7FFE8] text-[#1F5E2B] dark:bg-green-800/60 dark:text-green-200">
                      {s.frequency === "daily" ? t("frequencyDaily") : t("frequencyWeekly")}
                    </span>
                    <a
                      href={s.officialUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs whitespace-nowrap hover:underline"
                    >
                      {t("officialUrlLabel")} ↗
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </main>
  );
}
