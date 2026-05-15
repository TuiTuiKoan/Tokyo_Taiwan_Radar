import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Locale } from "@/lib/types";
import type { SourceInfo, SourceType } from "@/lib/sources";
import { CARD_LINK } from "@/lib/classNames";

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
    <section className="max-w-4xl mx-auto">
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="text-green-500 hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span className="text-fg-muted">{t("pageTitle")}</span>
      </nav>

      <h1 className="text-3xl font-bold mb-3 text-fg-strong">{t("pageTitle")}</h1>
      <p className="text-base leading-relaxed text-fg mb-6">
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
                <li
                  key={s.id}
                  className={`${CARD_LINK} justify-between gap-3 px-4 py-3 text-sm cursor-default`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-fg truncate">{s.name}</div>
                    <div className="text-xs text-fg-subtle font-mono">{s.id}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-400">
                      {s.frequency === "daily" ? t("frequencyDaily") : t("frequencyWeekly")}
                    </span>
                    <a
                      href={s.officialUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs whitespace-nowrap text-fg-subtle group-hover:text-[#1F5E2B] dark:group-hover:text-green-400 hover:underline"
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
    </section>
  );
}
